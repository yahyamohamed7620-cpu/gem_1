"""
قاعدة البيانات — SQLite خالص بدون أي مكتبات خارجية.
تحتوي على: المستخدمين (مسوقين + أدمن)، المنتجات، الطلبات، عناصر الطلب،
حركات العمولة، وطلبات سحب الأرباح.
"""
import sqlite3
import os
import hashlib
import hmac
import secrets

# مسار قاعدة البيانات: افتراضيًا جنب الكود، أو في مجلد ثابت لو اتحدد DATA_DIR
# (مفيد على الاستضافة لما يكون فيه قرص دائم عشان البيانات ماتضيعش).
_DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
os.makedirs(_DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(_DATA_DIR, "ecomerg.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ---------- تشفير كلمة المرور (PBKDF2 من المكتبة القياسية) ----------
def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000)
    return f"{salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, hexhash = stored.split("$", 1)
    except ValueError:
        return False
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000)
    return hmac.compare_digest(dk.hex(), hexhash)


SCHEMA = """
CREATE TABLE IF NOT EXISTS groups (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT UNIQUE NOT NULL,
    leader_id   INTEGER,                 -- قائد المجموعة (يشوف كل أرقامها)
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    email       TEXT UNIQUE NOT NULL,
    phone       TEXT,
    password    TEXT NOT NULL,
    role        TEXT NOT NULL DEFAULT 'marketer',   -- owner | admin | marketer
    status      TEXT NOT NULL DEFAULT 'active',       -- active | banned
    balance     REAL NOT NULL DEFAULT 0,              -- رصيد الأرباح القابل للسحب
    group_id    INTEGER REFERENCES groups(id),        -- المجموعة/الفريق التابع له
    permissions TEXT NOT NULL DEFAULT '[]',           -- صلاحيات المدير (JSON)
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS products (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    code         TEXT,                     -- كود المنتج (للربط بالإعلانات)
    description  TEXT,
    category     TEXT,
    image        TEXT,
    base_price   REAL NOT NULL DEFAULT 0,  -- (قديم) متروك للتوافق
    min_price    REAL NOT NULL DEFAULT 0,  -- (قديم)
    max_price    REAL NOT NULL DEFAULT 0,  -- (قديم)
    commission   REAL NOT NULL DEFAULT 0,  -- (قديم)
    wholesale_price REAL NOT NULL DEFAULT 0,  -- سعر الجملة (للأدمن فقط)
    sell_price      REAL NOT NULL DEFAULT 0,  -- سعر البيع (يظهر للمسوّق)
    offers          TEXT NOT NULL DEFAULT '[]', -- عروض الكمية JSON: [{qty,price}]
    images          TEXT NOT NULL DEFAULT '[]', -- صور المنتج (JSON list)
    stock        INTEGER NOT NULL DEFAULT 100,
    active       INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS orders (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    marketer_id   INTEGER NOT NULL REFERENCES users(id),
    group_id      INTEGER REFERENCES groups(id),      -- مجموعة المسوّق وقت الطلب
    customer_name TEXT NOT NULL,
    customer_phone TEXT NOT NULL,
    customer_address TEXT NOT NULL,
    governorate   TEXT,
    area          TEXT,                  -- المدينة/المنطقة
    zone          TEXT,                  -- التقسيمة (خط التوصيل)
    delivery      REAL NOT NULL DEFAULT 0,-- سعر التوصيل
    total         REAL NOT NULL,         -- إجمالي سعر بيع المنتجات (بدون توصيل)
    commission    REAL NOT NULL,         -- إجمالي ربح المسوّق من الطلب
    status        TEXT NOT NULL DEFAULT 'pending',  -- pending | confirmed | shipped | delivered | cancelled
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS order_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id    INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id  INTEGER NOT NULL REFERENCES products(id),
    product_name TEXT NOT NULL,
    qty         INTEGER NOT NULL,
    sell_price  REAL NOT NULL,          -- إجمالي سعر بيع هذا السطر
    commission  REAL NOT NULL,          -- ربح هذا السطر
    wholesale   REAL NOT NULL DEFAULT 0 -- إجمالي سعر جملة هذا السطر (لحساب الربح)
);

CREATE TABLE IF NOT EXISTS commissions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    marketer_id INTEGER NOT NULL REFERENCES users(id),
    order_id    INTEGER REFERENCES orders(id),
    amount      REAL NOT NULL,
    note        TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS withdrawals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    marketer_id INTEGER NOT NULL REFERENCES users(id),
    amount      REAL NOT NULL,
    method      TEXT NOT NULL,          -- طريقة الاستلام
    details     TEXT,                   -- رقم المحفظة / IBAN
    status      TEXT NOT NULL DEFAULT 'pending', -- pending | paid | rejected
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sessions (
    token       TEXT PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def _column_exists(conn, table, col):
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r["name"] == col for r in rows)


def migrate(conn):
    """ترحيل آمن للقواعد القديمة: يضيف الأعمدة الجديدة لو مش موجودة."""
    def add(table, col, decl):
        if not _column_exists(conn, table, col):
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")

    add("users", "group_id", "INTEGER")
    add("users", "permissions", "TEXT NOT NULL DEFAULT '[]'")
    add("orders", "group_id", "INTEGER")
    add("orders", "area", "TEXT")
    add("orders", "zone", "TEXT")
    add("orders", "delivery", "REAL NOT NULL DEFAULT 0")
    add("products", "wholesale_price", "REAL NOT NULL DEFAULT 0")
    add("products", "sell_price", "REAL NOT NULL DEFAULT 0")
    add("products", "offers", "TEXT NOT NULL DEFAULT '[]'")
    add("products", "images", "TEXT NOT NULL DEFAULT '[]'")
    add("products", "code", "TEXT")
    add("order_items", "wholesale", "REAL NOT NULL DEFAULT 0")
    add("groups", "leader_id", "INTEGER")

    # تعبئة التسعير الجديد للمنتجات القديمة من الحقول القديمة
    conn.execute("UPDATE products SET sell_price=min_price WHERE sell_price=0 AND min_price>0")
    conn.execute("UPDATE products SET wholesale_price=base_price WHERE wholesale_price=0 AND base_price>0")

    # التأكد من وجود مالك (owner) واحد على الأقل
    has_owner = conn.execute("SELECT 1 FROM users WHERE role='owner'").fetchone()
    if not has_owner:
        row = conn.execute("SELECT id FROM users WHERE role='admin' ORDER BY id LIMIT 1").fetchone()
        if row:
            conn.execute("UPDATE users SET role='owner' WHERE id=?", (row["id"],))


def init_db():
    conn = get_conn()
    conn.executescript(SCHEMA)
    migrate(conn)
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("Database initialized at", DB_PATH)
