"""
Kuwait Market — منصة دروبشيبينج.
سيرفر HTTP بمكتبة Python القياسية فقط (بدون أي اعتماديات خارجية).

التشغيل:
    python3 seed.py      # مرة واحدة لتجهيز البيانات
    python3 app.py       # تشغيل السيرفر على http://localhost:8000

API يرجع JSON. الواجهات ملفات ثابتة في مجلد static/.
"""
import base64
import csv
import io
import json
import os
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from db import get_conn, init_db, hash_password, verify_password

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
HOST = "0.0.0.0"
# السيرفر (زي Render) بيحدد المنفذ في متغير PORT. محليًا بيستخدم 8000.
PORT = int(os.environ.get("PORT", "8000"))


# ------------------------- أدوات مساعدة -------------------------
def row_to_dict(row):
    return {k: row[k] for k in row.keys()} if row else None


def current_user(handler):
    """يرجع المستخدم الحالي من التوكن في الهيدر Authorization: Bearer <token>."""
    auth = handler.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:].strip()
    conn = get_conn()
    row = conn.execute(
        """SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id
           WHERE s.token = ?""",
        (token,),
    ).fetchone()
    conn.close()
    return row_to_dict(row)


# ------------------------- معالِجات الـ API -------------------------
def api_register(handler, body):
    name = (body.get("name") or "").strip()
    email = (body.get("email") or "").strip().lower()
    phone = (body.get("phone") or "").strip()
    password = body.get("password") or ""
    if not name or not email or len(password) < 6:
        return 400, {"error": "البيانات ناقصة أو كلمة المرور أقل من 6 أحرف"}
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO users (name,email,phone,password,role) VALUES (?,?,?,?,'marketer')",
            (name, email, phone, hash_password(password)),
        )
        conn.commit()
        uid = cur.lastrowid
    except Exception:
        conn.close()
        return 409, {"error": "الإيميل مسجّل بالفعل"}
    token = secrets.token_urlsafe(32)
    conn.execute("INSERT INTO sessions (token,user_id) VALUES (?,?)", (token, uid))
    conn.commit()
    conn.close()
    return 200, {"token": token, "user": {"id": uid, "name": name, "email": email, "role": "marketer", "balance": 0}}


def api_login(handler, body):
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE email=? OR phone=?", (email, email)).fetchone()
    if not row or not verify_password(password, row["password"]):
        conn.close()
        return 401, {"error": "الإيميل أو كلمة المرور غير صحيحة"}
    if row["status"] == "banned":
        conn.close()
        return 403, {"error": "الحساب محظور، تواصل مع الإدارة"}
    token = secrets.token_urlsafe(32)
    conn.execute("INSERT INTO sessions (token,user_id) VALUES (?,?)", (token, row["id"]))
    conn.commit()
    conn.close()
    u = row_to_dict(row)
    return 200, {"token": token, "user": {"id": u["id"], "name": u["name"], "email": u["email"], "role": u["role"], "balance": u["balance"]}}


def api_me(handler, user):
    return 200, {"id": user["id"], "name": user["name"], "email": user["email"],
                 "phone": user["phone"], "role": user["role"], "balance": round(user["balance"], 3)}


def api_logout(handler, user):
    auth = handler.headers.get("Authorization", "")
    token = auth[7:].strip() if auth.startswith("Bearer ") else ""
    conn = get_conn()
    conn.execute("DELETE FROM sessions WHERE token=?", (token,))
    conn.commit()
    conn.close()
    return 200, {"ok": True}


def api_products(handler, qs):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM products WHERE active=1 ORDER BY id DESC").fetchall()
    conn.close()
    return 200, {"products": [row_to_dict(r) for r in rows]}


def api_create_order(handler, user, body):
    """المسوّق بيعمل طلب لعميل. items = [{product_id, qty, sell_price}]"""
    items = body.get("items") or []
    cust = body.get("customer") or {}
    if not items or not cust.get("name") or not cust.get("phone") or not cust.get("address"):
        return 400, {"error": "بيانات الطلب أو العميل ناقصة"}

    conn = get_conn()
    total = 0.0
    total_comm = 0.0
    prepared = []
    for it in items:
        p = conn.execute("SELECT * FROM products WHERE id=? AND active=1", (it.get("product_id"),)).fetchone()
        if not p:
            conn.close()
            return 400, {"error": "منتج غير موجود"}
        qty = max(1, int(it.get("qty", 1)))
        sell = float(it.get("sell_price", p["min_price"]))
        if sell < p["min_price"] or sell > p["max_price"]:
            conn.close()
            return 400, {"error": f"سعر «{p['name']}» لازم بين {p['min_price']} و {p['max_price']} د.ك"}
        if p["stock"] < qty:
            conn.close()
            return 400, {"error": f"الكمية غير متوفرة لـ «{p['name']}»"}
        line_comm = p["commission"] * qty
        total += sell * qty
        total_comm += line_comm
        prepared.append((p, qty, sell, line_comm))

    grp = conn.execute("SELECT group_id FROM users WHERE id=?", (user["id"],)).fetchone()
    group_id = grp["group_id"] if grp else None
    cur = conn.execute(
        """INSERT INTO orders (marketer_id,group_id,customer_name,customer_phone,customer_address,governorate,total,commission)
           VALUES (?,?,?,?,?,?,?,?)""",
        (user["id"], group_id, cust["name"], cust["phone"], cust["address"], cust.get("governorate", ""), total, total_comm),
    )
    oid = cur.lastrowid
    for p, qty, sell, line_comm in prepared:
        conn.execute(
            """INSERT INTO order_items (order_id,product_id,product_name,qty,sell_price,commission)
               VALUES (?,?,?,?,?,?)""",
            (oid, p["id"], p["name"], qty, sell, line_comm),
        )
        conn.execute("UPDATE products SET stock = stock - ? WHERE id=?", (qty, p["id"]))
    conn.commit()
    conn.close()
    return 200, {"ok": True, "order_id": oid, "total": round(total, 3), "commission": round(total_comm, 3)}


def api_my_orders(handler, user):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM orders WHERE marketer_id=? ORDER BY id DESC", (user["id"],)).fetchall()
    orders = []
    for r in rows:
        o = row_to_dict(r)
        items = conn.execute("SELECT * FROM order_items WHERE order_id=?", (r["id"],)).fetchall()
        o["items"] = [row_to_dict(i) for i in items]
        orders.append(o)
    conn.close()
    return 200, {"orders": orders}


def api_stats(handler, user):
    conn = get_conn()
    total_orders = conn.execute("SELECT COUNT(*) c FROM orders WHERE marketer_id=?", (user["id"],)).fetchone()["c"]
    delivered = conn.execute("SELECT COUNT(*) c FROM orders WHERE marketer_id=? AND status='delivered'", (user["id"],)).fetchone()["c"]
    pending_comm = conn.execute(
        "SELECT COALESCE(SUM(commission),0) s FROM orders WHERE marketer_id=? AND status IN ('pending','confirmed','shipped')",
        (user["id"],),
    ).fetchone()["s"]
    earned = conn.execute(
        "SELECT COALESCE(SUM(amount),0) s FROM commissions WHERE marketer_id=?", (user["id"],)
    ).fetchone()["s"]
    u = conn.execute("SELECT balance FROM users WHERE id=?", (user["id"],)).fetchone()
    conn.close()
    return 200, {
        "total_orders": total_orders,
        "delivered": delivered,
        "pending_commission": round(pending_comm, 3),
        "total_earned": round(earned, 3),
        "balance": round(u["balance"], 3),
    }


def api_withdraw(handler, user, body):
    amount = float(body.get("amount", 0))
    method = (body.get("method") or "").strip()
    details = (body.get("details") or "").strip()
    if amount <= 0 or not method:
        return 400, {"error": "ادخل مبلغ وطريقة استلام صحيحة"}
    conn = get_conn()
    bal = conn.execute("SELECT balance FROM users WHERE id=?", (user["id"],)).fetchone()["balance"]
    if amount > bal:
        conn.close()
        return 400, {"error": "المبلغ أكبر من رصيدك المتاح"}
    conn.execute("UPDATE users SET balance = balance - ? WHERE id=?", (amount, user["id"]))
    conn.execute(
        "INSERT INTO withdrawals (marketer_id,amount,method,details) VALUES (?,?,?,?)",
        (user["id"], amount, method, details),
    )
    conn.commit()
    conn.close()
    return 200, {"ok": True}


def api_my_withdrawals(handler, user):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM withdrawals WHERE marketer_id=? ORDER BY id DESC", (user["id"],)).fetchall()
    conn.close()
    return 200, {"withdrawals": [row_to_dict(r) for r in rows]}


# ------------------------- معالِجات الأدمن -------------------------
def require_admin(user):
    return user and user["role"] == "admin"


def api_admin_orders(handler, user, qs=None):
    group_id = None
    if qs and qs.get("group_id"):
        try:
            group_id = int(qs["group_id"][0])
        except (ValueError, TypeError):
            group_id = None
    conn = get_conn()
    base = """SELECT o.*, u.name AS marketer_name, g.name AS group_name
             FROM orders o
             JOIN users u ON u.id=o.marketer_id
             LEFT JOIN groups g ON g.id=o.group_id"""
    if group_id:
        rows = conn.execute(base + " WHERE o.group_id=? ORDER BY o.id DESC", (group_id,)).fetchall()
    else:
        rows = conn.execute(base + " ORDER BY o.id DESC").fetchall()
    conn.close()
    return 200, {"orders": [row_to_dict(r) for r in rows]}


def api_admin_export_orders(handler, user, qs=None):
    """تصدير الأوردرات كـ CSV (يفتح على Excel). فلتر اختياري بالمجموعة."""
    group_id = None
    if qs and qs.get("group_id"):
        try:
            group_id = int(qs["group_id"][0])
        except (ValueError, TypeError):
            group_id = None
    conn = get_conn()
    base = """SELECT o.id, o.created_at, u.name AS marketer_name, g.name AS group_name,
                     o.customer_name, o.customer_phone, o.governorate, o.customer_address,
                     o.total, o.commission, o.status
              FROM orders o
              JOIN users u ON u.id=o.marketer_id
              LEFT JOIN groups g ON g.id=o.group_id"""
    if group_id:
        rows = conn.execute(base + " WHERE o.group_id=? ORDER BY o.id DESC", (group_id,)).fetchall()
    else:
        rows = conn.execute(base + " ORDER BY o.id DESC").fetchall()
    # عناصر كل أوردر كنص واحد
    items_map = {}
    for r in rows:
        its = conn.execute("SELECT product_name, qty, sell_price FROM order_items WHERE order_id=?", (r["id"],)).fetchall()
        items_map[r["id"]] = " | ".join(f"{i['product_name']} x{i['qty']} ({i['sell_price']})" for i in its)
    conn.close()

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["رقم الطلب", "التاريخ", "المسوّق", "المجموعة", "اسم العميل", "هاتف العميل",
                "المحافظة", "العنوان", "المنتجات", "إجمالي البيع", "العمولة", "الحالة"])
    status_ar = {"pending": "قيد الانتظار", "confirmed": "مؤكد", "shipped": "قيد الشحن",
                 "delivered": "تم التسليم", "cancelled": "ملغي"}
    for r in rows:
        w.writerow([r["id"], r["created_at"], r["marketer_name"], r["group_name"] or "—",
                    r["customer_name"], r["customer_phone"], r["governorate"] or "", r["customer_address"],
                    items_map.get(r["id"], ""), r["total"], r["commission"],
                    status_ar.get(r["status"], r["status"])])
    # BOM عشان العربي يظهر صح في Excel
    csv_text = "﻿" + buf.getvalue()
    return 200, {"_csv": csv_text, "filename": "orders.csv"}


def api_admin_groups(handler, user):
    conn = get_conn()
    rows = conn.execute(
        """SELECT g.*, (SELECT COUNT(*) FROM users u WHERE u.group_id=g.id) AS members
           FROM groups g ORDER BY g.id DESC"""
    ).fetchall()
    conn.close()
    return 200, {"groups": [row_to_dict(r) for r in rows]}


def api_admin_add_group(handler, user, body):
    name = (body.get("name") or "").strip()
    if not name:
        return 400, {"error": "اكتب اسم المجموعة"}
    conn = get_conn()
    try:
        conn.execute("INSERT INTO groups (name) VALUES (?)", (name,))
        conn.commit()
    except Exception:
        conn.close()
        return 409, {"error": "فيه مجموعة بنفس الاسم"}
    conn.close()
    return 200, {"ok": True}


def api_admin_assign_group(handler, user, body):
    uid = body.get("user_id")
    gid = body.get("group_id")  # ممكن تبقى None/فاضية = بدون مجموعة
    gid = int(gid) if gid else None
    conn = get_conn()
    conn.execute("UPDATE users SET group_id=? WHERE id=? AND role='marketer'", (gid, uid))
    conn.commit()
    conn.close()
    return 200, {"ok": True}


def api_admin_update_order(handler, user, body):
    """تحديث حالة الطلب. لما يبقى delivered بتتسجّل العمولة في رصيد المسوق."""
    oid = body.get("order_id")
    status = body.get("status")
    valid = {"pending", "confirmed", "shipped", "delivered", "cancelled"}
    if status not in valid:
        return 400, {"error": "حالة غير صحيحة"}
    conn = get_conn()
    o = conn.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
    if not o:
        conn.close()
        return 404, {"error": "الطلب غير موجود"}
    if status == "delivered" and o["status"] != "delivered":
        # صرف العمولة
        conn.execute("UPDATE users SET balance = balance + ? WHERE id=?", (o["commission"], o["marketer_id"]))
        conn.execute(
            "INSERT INTO commissions (marketer_id,order_id,amount,note) VALUES (?,?,?,?)",
            (o["marketer_id"], oid, o["commission"], f"عمولة الطلب #{oid}"),
        )
    conn.execute("UPDATE orders SET status=? WHERE id=?", (status, oid))
    conn.commit()
    conn.close()
    return 200, {"ok": True}


def api_admin_withdrawals(handler, user):
    conn = get_conn()
    rows = conn.execute(
        """SELECT w.*, u.name AS marketer_name, u.email FROM withdrawals w
           JOIN users u ON u.id=w.marketer_id ORDER BY w.id DESC"""
    ).fetchall()
    conn.close()
    return 200, {"withdrawals": [row_to_dict(r) for r in rows]}


def api_admin_update_withdrawal(handler, user, body):
    wid = body.get("withdrawal_id")
    status = body.get("status")
    if status not in {"pending", "paid", "rejected"}:
        return 400, {"error": "حالة غير صحيحة"}
    conn = get_conn()
    w = conn.execute("SELECT * FROM withdrawals WHERE id=?", (wid,)).fetchone()
    if not w:
        conn.close()
        return 404, {"error": "غير موجود"}
    # لو اترفض نرجّع الفلوس لرصيد المسوق
    if status == "rejected" and w["status"] != "rejected":
        conn.execute("UPDATE users SET balance = balance + ? WHERE id=?", (w["amount"], w["marketer_id"]))
    conn.execute("UPDATE withdrawals SET status=? WHERE id=?", (status, wid))
    conn.commit()
    conn.close()
    return 200, {"ok": True}


UPLOAD_DIR = os.path.join(STATIC_DIR, "uploads")
ALLOWED_IMG = {"jpg", "jpeg", "png", "webp", "gif"}


def api_admin_upload_image(handler, user, body):
    """يستقبل صورة Base64 ويحفظها في مجلد uploads ويرجّع رابطها."""
    data = body.get("data") or ""
    ext = (body.get("ext") or "jpg").lower().lstrip(".")
    if ext not in ALLOWED_IMG:
        ext = "jpg"
    # يقبل مع أو بدون بادئة data:
    if "," in data:
        data = data.split(",", 1)[1]
    try:
        raw = base64.b64decode(data)
    except Exception:
        return 400, {"error": "صورة غير صالحة"}
    if len(raw) > 5 * 1024 * 1024:
        return 400, {"error": "حجم الصورة كبير (الحد 5 ميجا)"}
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    fname = f"{secrets.token_hex(12)}.{ext}"
    with open(os.path.join(UPLOAD_DIR, fname), "wb") as f:
        f.write(raw)
    return 200, {"url": f"/uploads/{fname}"}


def api_admin_add_product(handler, user, body):
    try:
        conn = get_conn()
        conn.execute(
            """INSERT INTO products (name,description,category,image,base_price,min_price,max_price,commission,stock)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (body["name"], body.get("description", ""), body.get("category", ""), body.get("image") or "📦",
             float(body["base_price"]), float(body["min_price"]), float(body["max_price"]),
             float(body["commission"]), int(body.get("stock", 100))),
        )
        conn.commit()
        conn.close()
        return 200, {"ok": True}
    except Exception as e:
        return 400, {"error": f"بيانات المنتج غير صحيحة: {e}"}


def api_admin_products(handler, user):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    conn.close()
    return 200, {"products": [row_to_dict(r) for r in rows]}


def api_admin_update_product(handler, user, body):
    pid = body.get("id")
    if not pid:
        return 400, {"error": "منتج غير محدد"}
    try:
        conn = get_conn()
        conn.execute(
            """UPDATE products SET name=?, description=?, category=?, image=?,
                   base_price=?, min_price=?, max_price=?, commission=?, stock=?
               WHERE id=?""",
            (body["name"], body.get("description", ""), body.get("category", ""), body.get("image") or "📦",
             float(body["base_price"]), float(body["min_price"]), float(body["max_price"]),
             float(body["commission"]), int(body.get("stock", 100)), pid),
        )
        conn.commit()
        conn.close()
        return 200, {"ok": True}
    except Exception as e:
        return 400, {"error": f"بيانات غير صحيحة: {e}"}


def api_admin_toggle_product(handler, user, body):
    """إخفاء/إظهار منتج (بدل الحذف النهائي حفاظًا على سجل الطلبات)."""
    pid = body.get("id")
    conn = get_conn()
    row = conn.execute("SELECT active FROM products WHERE id=?", (pid,)).fetchone()
    if not row:
        conn.close()
        return 404, {"error": "غير موجود"}
    new = 0 if row["active"] else 1
    conn.execute("UPDATE products SET active=? WHERE id=?", (new, pid))
    conn.commit()
    conn.close()
    return 200, {"ok": True, "active": new}


def api_admin_marketers(handler, user):
    conn = get_conn()
    rows = conn.execute(
        """SELECT u.id,u.name,u.email,u.phone,u.status,u.balance,u.created_at,
                  u.group_id, g.name AS group_name
           FROM users u LEFT JOIN groups g ON g.id=u.group_id
           WHERE u.role='marketer' ORDER BY u.id DESC"""
    ).fetchall()
    conn.close()
    return 200, {"marketers": [row_to_dict(r) for r in rows]}


def api_admin_toggle_ban(handler, user, body):
    uid = body.get("user_id")
    conn = get_conn()
    u = conn.execute("SELECT status FROM users WHERE id=?", (uid,)).fetchone()
    if not u:
        conn.close()
        return 404, {"error": "غير موجود"}
    new_status = "banned" if u["status"] == "active" else "active"
    conn.execute("UPDATE users SET status=? WHERE id=?", (new_status, uid))
    conn.commit()
    conn.close()
    return 200, {"ok": True, "status": new_status}


# ------------------------- التوجيه (Routing) -------------------------
PUBLIC_POST = {"/api/register": api_register, "/api/login": api_login}
PUBLIC_GET = {"/api/products": api_products}

_DENY = (403, {"error": "ممنوع"})
AUTH_GET = {
    "/api/me": lambda h, u, q: api_me(h, u),
    "/api/my-orders": lambda h, u, q: api_my_orders(h, u),
    "/api/stats": lambda h, u, q: api_stats(h, u),
    "/api/my-withdrawals": lambda h, u, q: api_my_withdrawals(h, u),
    "/api/admin/orders": lambda h, u, q: api_admin_orders(h, u, q) if require_admin(u) else _DENY,
    "/api/admin/export-orders": lambda h, u, q: api_admin_export_orders(h, u, q) if require_admin(u) else _DENY,
    "/api/admin/withdrawals": lambda h, u, q: api_admin_withdrawals(h, u) if require_admin(u) else _DENY,
    "/api/admin/marketers": lambda h, u, q: api_admin_marketers(h, u) if require_admin(u) else _DENY,
    "/api/admin/groups": lambda h, u, q: api_admin_groups(h, u) if require_admin(u) else _DENY,
    "/api/admin/products": lambda h, u, q: api_admin_products(h, u) if require_admin(u) else _DENY,
}
AUTH_POST = {
    "/api/logout": api_logout,
    "/api/orders": api_create_order,
    "/api/withdraw": api_withdraw,
    "/api/admin/update-order": lambda h, u, b: api_admin_update_order(h, u, b) if require_admin(u) else _DENY,
    "/api/admin/update-withdrawal": lambda h, u, b: api_admin_update_withdrawal(h, u, b) if require_admin(u) else _DENY,
    "/api/admin/add-product": lambda h, u, b: api_admin_add_product(h, u, b) if require_admin(u) else _DENY,
    "/api/admin/toggle-ban": lambda h, u, b: api_admin_toggle_ban(h, u, b) if require_admin(u) else _DENY,
    "/api/admin/add-group": lambda h, u, b: api_admin_add_group(h, u, b) if require_admin(u) else _DENY,
    "/api/admin/assign-group": lambda h, u, b: api_admin_assign_group(h, u, b) if require_admin(u) else _DENY,
    "/api/admin/upload-image": lambda h, u, b: api_admin_upload_image(h, u, b) if require_admin(u) else _DENY,
    "/api/admin/update-product": lambda h, u, b: api_admin_update_product(h, u, b) if require_admin(u) else _DENY,
    "/api/admin/toggle-product": lambda h, u, b: api_admin_toggle_product(h, u, b) if require_admin(u) else _DENY,
}

# المعالِجات اللي بتاخد body
POST_WITH_BODY = {"/api/orders", "/api/withdraw"}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, payload):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_csv(self, text, filename):
        data = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_file(self, path):
        if not os.path.isfile(path):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")
            return
        ext = os.path.splitext(path)[1]
        ctype = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".svg": "image/svg+xml",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".gif": "image/gif",
            ".ico": "image/x-icon",
        }.get(ext, "application/octet-stream")
        with open(path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path in PUBLIC_GET:
            code, payload = PUBLIC_GET[path](self, parse_qs(parsed.query))
            return self._send(code, payload)

        if path in AUTH_GET:
            user = current_user(self)
            if not user:
                return self._send(401, {"error": "سجّل الدخول أولاً"})
            code, payload = AUTH_GET[path](self, user, parse_qs(parsed.query))
            if isinstance(payload, dict) and "_csv" in payload:
                return self._send_csv(payload["_csv"], payload.get("filename", "export.csv"))
            return self._send(code, payload)

        # ملفات ثابتة
        if path == "/" or path == "":
            return self._send_file(os.path.join(STATIC_DIR, "index.html"))
        safe = os.path.normpath(path).lstrip("/\\")
        return self._send_file(os.path.join(STATIC_DIR, safe))

    def do_POST(self):
        path = urlparse(self.path).path
        body = self._read_body()

        if path in PUBLIC_POST:
            code, payload = PUBLIC_POST[path](self, body)
            return self._send(code, payload)

        if path in AUTH_POST:
            user = current_user(self)
            if not user:
                return self._send(401, {"error": "سجّل الدخول أولاً"})
            handler_fn = AUTH_POST[path]
            if path in POST_WITH_BODY or path.startswith("/api/admin/") or path == "/api/withdraw":
                code, payload = handler_fn(self, user, body)
            else:
                code, payload = handler_fn(self, user)
            return self._send(code, payload)

        return self._send(404, {"error": "مسار غير موجود"})

    def log_message(self, fmt, *args):
        pass  # تعطيل اللوج المزعج


def bootstrap():
    """تجهيز القاعدة والبيانات الأولية أوتوماتيك أول تشغيل (مفيد على الاستضافة)."""
    init_db()
    try:
        from seed import seed
        conn = get_conn()
        empty = conn.execute("SELECT COUNT(*) c FROM products").fetchone()["c"] == 0
        conn.close()
        if empty:
            seed()
    except Exception as e:
        print("Seed skipped:", e)


def main():
    bootstrap()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Kuwait Market running on http://localhost:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
