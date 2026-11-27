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
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    email       TEXT UNIQUE NOT NULL,
    phone       TEXT,
    password    TEXT NOT NULL,
    role        TEXT NOT NULL DEFAULT 'marketer',   -- marketer | admin
    status      TEXT NOT NULL DEFAULT 'active',       -- active | banned
    balance     REAL NOT NULL DEFAULT 0,              -- رصيد العمولة القابل للسحب
    group_id    INTEGER REFERENCES groups(id),        -- المجموعة/الفريق التابع له
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS products (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    description  TEXT,
    category     TEXT,
    image        TEXT,
    base_price   REAL NOT NULL,       -- السعر الأساسي (تكلفة المنصة)
    min_price    REAL NOT NULL,       -- أقل سعر بيع مسموح
    max_price    REAL NOT NULL,       -- أعلى سعر بيع مسموح
    commission   REAL NOT NULL,       -- العمولة الثابتة للمسوق
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
    total         REAL NOT NULL,         -- إجمالي سعر البيع للعميل
    commission    REAL NOT NULL,         -- إجمالي عمولة المسوق من الطلب
    status        TEXT NOT NULL DEFAULT 'pending',  -- pending | confirmed | shipped | delivered | cancelled
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS order_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id    INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id  INTEGER NOT NULL REFERENCES products(id),
    product_name TEXT NOT NULL,
    qty         INTEGER NOT NULL,
    sell_price  REAL NOT NULL,          -- سعر البيع للوحدة (حدده المسوق)
    commission  REAL NOT NULL           -- عمولة الوحدة
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
    if not _column_exists(conn, "users", "group_id"):
        conn.execute("ALTER TABLE users ADD COLUMN group_id INTEGER")
    if not _column_exists(conn, "orders", "group_id"):
        conn.execute("ALTER TABLE orders ADD COLUMN group_id INTEGER")


def init_db():
    conn = get_conn()
    conn.executescript(SCHEMA)
    migrate(conn)
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("Database initialized at", DB_PATH)
