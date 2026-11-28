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
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import kuwait
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
           WHERE s.token = ? AND s.created_at > datetime('now','-30 day')
             AND u.status = 'active'""",
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
        # الحساب الجديد "قيد المراجعة" لحد ما المالك يوافق
        conn.execute(
            "INSERT INTO users (name,email,phone,password,role,status) VALUES (?,?,?,?,'marketer','pending')",
            (name, email, phone, hash_password(password)),
        )
        conn.commit()
    except Exception:
        conn.close()
        return 409, {"error": "الإيميل مسجّل بالفعل"}
    conn.close()
    return 200, {"pending": True, "message": "تم التسجيل بنجاح! حسابك قيد المراجعة من الإدارة، هيتفعّل بعد الموافقة."}


# حماية من تخمين كلمة المرور (brute-force)
_login_attempts = {}


def _rate_limited(key, limit=8, window=300):
    now = time.time()
    arr = [t for t in _login_attempts.get(key, []) if now - t < window]
    _login_attempts[key] = arr
    return len(arr) >= limit


def _record_fail(key):
    _login_attempts.setdefault(key, []).append(time.time())


def api_login(handler, body):
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    if _rate_limited(email):
        return 429, {"error": "محاولات دخول كتيرة، استنى ٥ دقائق وجرّب تاني"}
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE email=? OR phone=?", (email, email)).fetchone()
    if not row or not verify_password(password, row["password"]):
        conn.close()
        _record_fail(email)
        return 401, {"error": "الإيميل أو كلمة المرور غير صحيحة"}
    if row["status"] == "pending":
        conn.close()
        return 403, {"error": "حسابك قيد المراجعة من الإدارة، انتظر الموافقة على التفعيل"}
    if row["status"] == "rejected":
        conn.close()
        return 403, {"error": "تم رفض تفعيل حسابك، تواصل مع الإدارة"}
    if row["status"] == "banned":
        conn.close()
        return 403, {"error": "الحساب محظور، تواصل مع الإدارة"}
    token = secrets.token_urlsafe(32)
    conn.execute("INSERT INTO sessions (token,user_id) VALUES (?,?)", (token, row["id"]))
    conn.commit()
    conn.close()
    _login_attempts.pop(email, None)
    u = row_to_dict(row)
    return 200, {"token": token, "user": {"id": u["id"], "name": u["name"], "email": u["email"], "role": u["role"], "balance": u["balance"]}}


def api_change_password(handler, user, body):
    old = body.get("old_password") or ""
    new = body.get("new_password") or ""
    if len(new) < 6:
        return 400, {"error": "كلمة المرور الجديدة لازم 6 أحرف على الأقل"}
    conn = get_conn()
    row = conn.execute("SELECT password FROM users WHERE id=?", (user["id"],)).fetchone()
    if not row or not verify_password(old, row["password"]):
        conn.close()
        return 400, {"error": "كلمة المرور الحالية غير صحيحة"}
    conn.execute("UPDATE users SET password=? WHERE id=?", (hash_password(new), user["id"]))
    conn.commit()
    conn.close()
    return 200, {"ok": True}


def api_admin_pending(handler, user):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id,name,email,phone,created_at FROM users WHERE role='marketer' AND status='pending' ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return 200, {"pending": [row_to_dict(r) for r in rows]}


def api_admin_approve_user(handler, user, body):
    uid = body.get("user_id")
    action = body.get("action")
    if action not in ("approve", "reject"):
        return 400, {"error": "إجراء غير صحيح"}
    new_status = "active" if action == "approve" else "rejected"
    conn = get_conn()
    conn.execute("UPDATE users SET status=? WHERE id=? AND role='marketer'", (new_status, uid))
    conn.commit()
    conn.close()
    return 200, {"ok": True, "status": new_status}


def api_me(handler, user):
    perms = []
    if user["role"] == "owner":
        perms = list(PERMISSIONS.keys())
    else:
        try:
            perms = json.loads(user.get("permissions") or "[]")
        except Exception:
            perms = []
    return 200, {"id": user["id"], "name": user["name"], "email": user["email"],
                 "phone": user["phone"], "role": user["role"], "balance": round(user["balance"], 3),
                 "permissions": perms}


def api_logout(handler, user):
    auth = handler.headers.get("Authorization", "")
    token = auth[7:].strip() if auth.startswith("Bearer ") else ""
    conn = get_conn()
    conn.execute("DELETE FROM sessions WHERE token=?", (token,))
    conn.commit()
    conn.close()
    return 200, {"ok": True}


def _offers_of(r):
    try:
        return json.loads(r["offers"] or "[]")
    except Exception:
        return []


def _images_of(r):
    try:
        imgs = json.loads(r["images"] or "[]")
    except Exception:
        imgs = []
    if not imgs and r["image"]:
        imgs = [r["image"]]
    return imgs


def public_product(r):
    """نسخة المنتج اللي يشوفها المسوّق/الزائر — بدون سعر الجملة."""
    return {"id": r["id"], "name": r["name"], "description": r["description"],
            "category": r["category"], "image": r["image"], "images": _images_of(r), "code": r["code"],
            "sell_price": r["sell_price"], "offers": _offers_of(r), "stock": r["stock"], "active": r["active"]}


def api_products(handler, qs):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM products WHERE active=1 ORDER BY id DESC").fetchall()
    conn.close()
    return 200, {"products": [public_product(r) for r in rows]}


def api_cities(handler, qs):
    return 200, {"cities": kuwait.all_cities()}


def line_price(product_row, qty):
    """سعر سطر الطلب: لو فيه عرض كمية مطابق استخدمه، وإلا سعر البيع × الكمية."""
    offers = _offers_of(product_row)
    for o in offers:
        try:
            if int(o.get("qty")) == int(qty):
                return float(o.get("price"))
        except (ValueError, TypeError):
            continue
    return float(product_row["sell_price"]) * int(qty)


def api_create_order(handler, user, body):
    """المسوّق بيعمل طلب لعميل. items = [{product_id, qty}] + customer{name,phone,city,address}"""
    items = body.get("items") or []
    cust = body.get("customer") or {}
    if not items or not cust.get("name") or not cust.get("phone") or not cust.get("address"):
        return 400, {"error": "بيانات الطلب أو العميل ناقصة"}

    city = (cust.get("city") or "").strip()
    zone = kuwait.zone_for(city)
    delivery = kuwait.delivery_for(city) if city else kuwait.DEFAULT_DELIVERY

    conn = get_conn()
    subtotal = 0.0
    total_wholesale = 0.0
    prepared = []
    for it in items:
        p = conn.execute("SELECT * FROM products WHERE id=? AND active=1", (it.get("product_id"),)).fetchone()
        if not p:
            conn.close()
            return 400, {"error": "منتج غير موجود"}
        qty = max(1, int(it.get("qty", 1)))
        if p["stock"] < qty:
            conn.close()
            return 400, {"error": f"الكمية غير متوفرة لـ «{p['name']}»"}
        lp = line_price(p, qty)                       # إجمالي سعر بيع السطر (يراعي عروض الكمية)
        lw = float(p["wholesale_price"]) * qty        # إجمالي جملة السطر
        subtotal += lp
        total_wholesale += lw
        prepared.append((p, qty, lp, lw))

    # ربح المسوّق متوقف مؤقتًا (هيتظبط لاحقًا)
    profit = 0.0

    grp = conn.execute("SELECT group_id FROM users WHERE id=?", (user["id"],)).fetchone()
    group_id = grp["group_id"] if grp else None
    cur = conn.execute(
        """INSERT INTO orders (marketer_id,group_id,customer_name,customer_phone,customer_address,
               governorate,area,zone,delivery,total,commission)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (user["id"], group_id, cust["name"], cust["phone"], cust["address"],
         cust.get("governorate", ""), city, zone, delivery, subtotal, profit),
    )
    oid = cur.lastrowid
    for p, qty, lp, lw in prepared:
        conn.execute(
            """INSERT INTO order_items (order_id,product_id,product_name,qty,sell_price,commission,wholesale)
               VALUES (?,?,?,?,?,?,?)""",
            (oid, p["id"], p["name"], qty, lp, 0.0, lw),
        )
        conn.execute("UPDATE products SET stock = stock - ? WHERE id=?", (qty, p["id"]))
    conn.commit()
    conn.close()
    grand = subtotal + delivery
    return 200, {"ok": True, "order_id": oid, "subtotal": round(subtotal, 3),
                 "delivery": round(delivery, 3), "total": round(grand, 3), "zone": zone}


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
    return user and user["role"] in ("admin", "owner")


def require_owner(user):
    return user and user["role"] == "owner"


# مفاتيح الصلاحيات ومسمياتها
PERMISSIONS = {
    "products": "إدارة المنتجات",
    "wholesale": "رؤية سعر الجملة",
    "orders": "إدارة الطلبات",
    "export": "تحميل شيت الأوردرات",
    "marketers": "إدارة المسوّقين",
    "groups": "إدارة المجموعات",
    "withdrawals": "إدارة طلبات السحب",
}


def has_perm(user, key):
    if not user:
        return False
    # المالك والمدير عندهم كل الصلاحيات التشغيلية.
    # الصلاحيات الحصرية للمالك (الموافقة على التسجيلات، إدارة المدراء،
    # النسخة الاحتياطية) محميّة بـ require_owner مش has_perm.
    if user["role"] in ("owner", "admin"):
        return True
    return False


def api_admin_orders(handler, user, qs=None):
    qs = qs or {}
    def g1(k):
        v = qs.get(k)
        return v[0] if v else None
    where, params = [], []
    if g1("group_id"):
        try:
            where.append("o.group_id=?")
            params.append(int(g1("group_id")))
        except (ValueError, TypeError):
            pass
    if g1("status"):
        where.append("o.status=?")
        params.append(g1("status"))
    if g1("from"):
        where.append("date(o.created_at) >= date(?)")
        params.append(g1("from"))
    if g1("to"):
        where.append("date(o.created_at) <= date(?)")
        params.append(g1("to"))
    if g1("q"):
        where.append("(o.customer_phone LIKE ? OR o.customer_name LIKE ?)")
        like = "%" + g1("q") + "%"
        params += [like, like]
    conn = get_conn()
    base = """SELECT o.*, u.name AS marketer_name, g.name AS group_name
             FROM orders o
             JOIN users u ON u.id=o.marketer_id
             LEFT JOIN groups g ON g.id=o.group_id"""
    wsql = (" WHERE " + " AND ".join(where)) if where else ""
    rows = conn.execute(base + wsql + " ORDER BY o.id DESC", params).fetchall()
    orders = []
    for r in rows:
        o = row_to_dict(r)
        items = conn.execute("SELECT product_name, qty, sell_price FROM order_items WHERE order_id=?", (r["id"],)).fetchall()
        o["items"] = [row_to_dict(i) for i in items]
        orders.append(o)
    conn.close()
    return 200, {"orders": orders}


def api_admin_bulk_update(handler, user, body):
    ids = body.get("order_ids") or []
    status = body.get("status")
    if status not in {"pending", "confirmed", "shipped", "delivered", "cancelled", "returned"}:
        return 400, {"error": "حالة غير صحيحة"}
    conn = get_conn()
    for oid in ids:
        conn.execute("UPDATE orders SET status=? WHERE id=?", (status, oid))
    conn.commit()
    conn.close()
    return 200, {"ok": True, "count": len(ids)}


def api_admin_add_spend(handler, user, body):
    pid = body.get("product_id")
    try:
        amount = float(body.get("amount"))
    except (TypeError, ValueError):
        return 400, {"error": "ادخل مبلغ صحيح"}
    if amount <= 0 or not pid:
        return 400, {"error": "بيانات الصرف ناقصة"}
    date = (body.get("date") or "").strip() or time.strftime("%Y-%m-%d")
    conn = get_conn()
    conn.execute("INSERT INTO ad_spend (product_id,amount,spend_date,note) VALUES (?,?,?,?)",
                 (pid, amount, date, (body.get("note") or "").strip()))
    conn.commit()
    conn.close()
    return 200, {"ok": True}


def api_admin_spend_entries(handler, user, qs):
    qs = qs or {}
    pid = (qs.get("product_id") or [None])[0]
    conn = get_conn()
    rows = conn.execute("SELECT * FROM ad_spend WHERE product_id=? ORDER BY id DESC", (pid,)).fetchall()
    conn.close()
    return 200, {"entries": [row_to_dict(r) for r in rows]}


def api_admin_delete_spend(handler, user, body):
    conn = get_conn()
    conn.execute("DELETE FROM ad_spend WHERE id=?", (body.get("id"),))
    conn.commit()
    conn.close()
    return 200, {"ok": True}


def api_product_stats(handler, user, qs):
    qs = qs or {}
    frm = (qs.get("from") or [None])[0]
    to = (qs.get("to") or [None])[0]
    where, params = [], []
    if frm:
        where.append("date(o.created_at) >= date(?)")
        params.append(frm)
    if to:
        where.append("date(o.created_at) <= date(?)")
        params.append(to)
    wsql = (" WHERE " + " AND ".join(where)) if where else ""
    conn = get_conn()
    rows = conn.execute(
        f"""SELECT oi.product_id, oi.product_name, o.status, o.id AS oid, oi.qty,
                   oi.sell_price, oi.wholesale, pr.code AS code
            FROM order_items oi JOIN orders o ON o.id=oi.order_id
            LEFT JOIN products pr ON pr.id=oi.product_id{wsql}""", params
    ).fetchall()
    # صرف الإعلانات لكل منتج (بنفس فلتر التاريخ)
    swhere, sparams = [], []
    if frm:
        swhere.append("spend_date >= ?")
        sparams.append(frm)
    if to:
        swhere.append("spend_date <= ?")
        sparams.append(to)
    sw = (" WHERE " + " AND ".join(swhere)) if swhere else ""
    spend_rows = conn.execute(f"SELECT product_id, COALESCE(SUM(amount),0) s FROM ad_spend{sw} GROUP BY product_id", sparams).fetchall()
    spend_map = {r["product_id"]: r["s"] for r in spend_rows}
    conn.close()
    prod = {}
    for r in rows:
        p = prod.setdefault(r["product_id"], {"name": r["product_name"], "code": r["code"], "orders": set(), "qty": 0, "by_status": {}, "revenue": 0.0, "cogs": 0.0})
        if r["status"] == "delivered":
            p["revenue"] += r["sell_price"] or 0
            p["cogs"] += r["wholesale"] or 0
        p["orders"].add(r["oid"])
        p["qty"] += r["qty"] or 0
        p["by_status"].setdefault(r["status"], set()).add(r["oid"])
    out = []
    for pid, p in prod.items():
        def cnt(s):
            return len(p["by_status"].get(s, set()))
        total = len(p["orders"])
        confirmed_total = cnt("confirmed") + cnt("shipped") + cnt("delivered") + cnt("returned")
        delivered, returned = cnt("delivered"), cnt("returned")
        def rate(a, b):
            return round(100.0 * a / b, 1) if b else 0.0
        margin = p["revenue"] - p["cogs"]              # ربح قبل الإعلانات (بيع − جملة للمسلّم)
        spend = spend_map.get(pid, 0.0)                # صرف الإعلانات في الفترة
        net = round(margin - spend, 3)                 # صافي الربح = الربح − الإعلانات
        out.append({"product_id": pid, "name": p["name"], "code": p["code"] or "", "total": total, "qty": p["qty"],
                    "pending": cnt("pending"), "confirmed_total": confirmed_total, "delivered": delivered,
                    "returned": returned, "cancelled": cnt("cancelled"),
                    "deliver_rate": rate(delivered, confirmed_total), "return_rate": rate(returned, confirmed_total),
                    "cancel_rate": rate(cnt("cancelled"), total),
                    "revenue": round(p["revenue"], 3), "cogs": round(p["cogs"], 3),
                    "margin": round(margin, 3), "spend": round(spend, 3), "net_profit": net})
    # ضيف المنتجات اللي ليها صرف لكن مفيش أوردرات عليها في الفترة
    seen = {x["product_id"] for x in out}
    for pid, s in spend_map.items():
        if pid not in seen:
            conn2 = get_conn()
            pr = conn2.execute("SELECT name, code FROM products WHERE id=?", (pid,)).fetchone()
            conn2.close()
            out.append({"product_id": pid, "name": pr["name"] if pr else "?", "code": (pr["code"] if pr else "") or "",
                        "total": 0, "qty": 0, "pending": 0, "confirmed_total": 0, "delivered": 0, "returned": 0,
                        "cancelled": 0, "deliver_rate": 0.0, "return_rate": 0.0, "cancel_rate": 0.0,
                        "revenue": 0.0, "cogs": 0.0, "margin": 0.0, "spend": round(s, 3), "net_profit": round(-s, 3)})
    out.sort(key=lambda x: -x["total"])
    return 200, {"products": out}


def api_admin_export_orders(handler, user, qs=None):
    """تصدير الأوردرات كـ CSV (يفتح على Excel) — بنفس فلاتر صفحة الطلبات."""
    qs = qs or {}
    def g1(k):
        v = qs.get(k)
        return v[0] if v else None
    where, params = [], []
    if g1("group_id"):
        try:
            where.append("o.group_id=?")
            params.append(int(g1("group_id")))
        except (ValueError, TypeError):
            pass
    if g1("status"):
        where.append("o.status=?")
        params.append(g1("status"))
    if g1("from"):
        where.append("date(o.created_at) >= date(?)")
        params.append(g1("from"))
    if g1("to"):
        where.append("date(o.created_at) <= date(?)")
        params.append(g1("to"))
    if g1("q"):
        where.append("(o.customer_phone LIKE ? OR o.customer_name LIKE ?)")
        like = "%" + g1("q") + "%"
        params += [like, like]
    conn = get_conn()
    base = """SELECT o.id, o.created_at, u.name AS marketer_name, g.name AS group_name,
                     o.customer_name, o.customer_phone, o.zone, o.area, o.customer_address,
                     o.total, o.delivery, o.status
              FROM orders o
              JOIN users u ON u.id=o.marketer_id
              LEFT JOIN groups g ON g.id=o.group_id"""
    wsql = (" WHERE " + " AND ".join(where)) if where else ""
    rows = conn.execute(base + wsql + " ORDER BY o.id DESC", params).fetchall()
    # عناصر كل أوردر كنص واحد
    items_map = {}
    for r in rows:
        its = conn.execute("SELECT product_name, qty FROM order_items WHERE order_id=?", (r["id"],)).fetchall()
        items_map[r["id"]] = " | ".join(f"{i['product_name']} x{i['qty']}" for i in its)
    conn.close()

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["رقم الطلب", "التاريخ", "المسوّق", "المجموعة", "اسم العميل", "هاتف العميل",
                "التقسيمة", "المنطقة", "العنوان", "المنتجات", "السعر", "التوصيل", "الإجمالي", "الحالة"])
    status_ar = {"pending": "قيد الانتظار", "confirmed": "مؤكد", "shipped": "قيد الشحن",
                 "delivered": "تم التسليم", "cancelled": "ملغي", "returned": "مرتجع"}
    for r in rows:
        price = r["total"] or 0
        delivery = r["delivery"] or 0
        grand = price + delivery
        w.writerow([r["id"], r["created_at"], r["marketer_name"], r["group_name"] or "—",
                    r["customer_name"], r["customer_phone"], r["zone"] or "—", r["area"] or "",
                    r["customer_address"], items_map.get(r["id"], ""),
                    round(price, 3), round(delivery, 3), round(grand, 3),
                    status_ar.get(r["status"], r["status"])])
    csv_text = "﻿" + buf.getvalue()
    return 200, {"_csv": csv_text, "filename": "orders.csv"}


def api_admin_groups(handler, user):
    conn = get_conn()
    rows = conn.execute(
        """SELECT g.*, (SELECT COUNT(*) FROM users u WHERE u.group_id=g.id) AS members,
                  (SELECT name FROM users lu WHERE lu.id=g.leader_id) AS leader_name
           FROM groups g ORDER BY g.id DESC"""
    ).fetchall()
    # أعضاء كل مجموعة (لاختيار القائد)
    members = conn.execute("SELECT id,name,group_id FROM users WHERE role='marketer' AND group_id IS NOT NULL").fetchall()
    conn.close()
    mmap = {}
    for m in members:
        mmap.setdefault(m["group_id"], []).append({"id": m["id"], "name": m["name"]})
    out = []
    for r in rows:
        d = row_to_dict(r)
        d["member_list"] = mmap.get(r["id"], [])
        out.append(d)
    return 200, {"groups": out}


def api_admin_set_leader(handler, user, body):
    gid = body.get("group_id")
    uid = body.get("user_id")
    conn = get_conn()
    if uid:
        m = conn.execute("SELECT id FROM users WHERE id=? AND role='marketer' AND group_id=?", (uid, gid)).fetchone()
        if not m:
            conn.close()
            return 400, {"error": "لازم تختار عضو من نفس المجموعة"}
    conn.execute("UPDATE groups SET leader_id=? WHERE id=?", (uid or None, gid))
    conn.commit()
    conn.close()
    return 200, {"ok": True}


# ------------------------- لوحة الإحصائيات -------------------------
def _stats_from(rows):
    total = len(rows)
    def c(s):
        return sum(1 for r in rows if r["status"] == s)
    confirmed, shipped, delivered, returned = c("confirmed"), c("shipped"), c("delivered"), c("returned")
    confirmed_total = confirmed + shipped + delivered + returned
    sales = sum((r["total"] or 0) + (r["delivery"] or 0) for r in rows if r["status"] == "delivered")
    def rate(a, b):
        return round(100.0 * a / b, 1) if b else 0.0
    return {
        "total": total, "pending": c("pending"), "confirmed": confirmed, "shipped": shipped,
        "delivered": delivered, "cancelled": c("cancelled"), "returned": returned,
        "confirmed_total": confirmed_total,
        "confirm_rate": rate(confirmed_total, total),
        "deliver_rate": rate(delivered, confirmed_total),
        "return_rate": rate(returned, confirmed_total),
        "sales": round(sales, 3),
    }


def api_dashboard(handler, user, qs):
    qs = qs or {}
    frm = (qs.get("from") or [None])[0]
    to = (qs.get("to") or [None])[0]
    conn = get_conn()
    where, params = [], []
    if frm:
        where.append("date(o.created_at) >= date(?)")
        params.append(frm)
    if to:
        where.append("date(o.created_at) <= date(?)")
        params.append(to)

    scope = "admin"
    if user["role"] == "marketer":
        g = conn.execute("SELECT id FROM groups WHERE leader_id=?", (user["id"],)).fetchone()
        if g:
            scope = "leader"
            where.append("o.group_id=?")
            params.append(g["id"])
        else:
            scope = "member"
            where.append("o.marketer_id=?")
            params.append(user["id"])
    else:
        if not has_perm(user, "orders"):
            conn.close()
            return 403, {"error": "ممنوع"}

    wsql = (" WHERE " + " AND ".join(where)) if where else ""
    rows = conn.execute(
        f"SELECT o.status,o.total,o.delivery,o.group_id,o.marketer_id FROM orders o{wsql}", params
    ).fetchall()
    result = {"scope": scope, "overall": _stats_from(rows)}

    if scope in ("admin", "leader"):
        marketers = {m["id"]: m["name"] for m in conn.execute("SELECT id,name FROM users WHERE role='marketer'").fetchall()}
        bym = {}
        for r in rows:
            bym.setdefault(r["marketer_id"], []).append(r)
        result["by_marketer"] = sorted(
            [{"name": marketers.get(mid, "?"), "stats": _stats_from(rs)} for mid, rs in bym.items()],
            key=lambda x: -x["stats"]["total"])
    if scope == "admin":
        groups = {g["id"]: g["name"] for g in conn.execute("SELECT id,name FROM groups").fetchall()}
        byg = {}
        for r in rows:
            byg.setdefault(r["group_id"], []).append(r)
        result["by_group"] = sorted(
            [{"name": (groups.get(gid) if gid else "بدون مجموعة"), "stats": _stats_from(rs)} for gid, rs in byg.items()],
            key=lambda x: -x["stats"]["total"])
    conn.close()
    return 200, result


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
    valid = {"pending", "confirmed", "postponed", "shipped", "delivered", "cancelled", "returned"}
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


def _clean_offers(raw):
    """يتحقق من عروض الكمية ويرجّعها كـ JSON نصّي."""
    out = []
    for o in (raw or []):
        try:
            q = int(o.get("qty"))
            pr = float(o.get("price"))
            if q >= 2 and pr > 0:
                out.append({"qty": q, "price": pr})
        except (ValueError, TypeError, AttributeError):
            continue
    return json.dumps(out, ensure_ascii=False)


def _clean_images(raw):
    imgs = [u for u in (raw or []) if isinstance(u, str) and u]
    return json.dumps(imgs, ensure_ascii=False)


def api_admin_add_product(handler, user, body):
    try:
        imgs = [u for u in (body.get("images") or []) if isinstance(u, str) and u]
        main = imgs[0] if imgs else (body.get("image") or "📦")
        conn = get_conn()
        conn.execute(
            """INSERT INTO products (name,code,description,category,image,images,wholesale_price,sell_price,offers,stock)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (body["name"], (body.get("code") or "").strip(), body.get("description", ""), body.get("category", ""), main, _clean_images(imgs),
             float(body["wholesale_price"]), float(body["sell_price"]),
             _clean_offers(body.get("offers")), int(body.get("stock", 100))),
        )
        conn.commit()
        conn.close()
        return 200, {"ok": True}
    except Exception as e:
        return 400, {"error": f"بيانات المنتج غير صحيحة: {e}"}


def api_admin_products(handler, user):
    show_wholesale = has_perm(user, "wholesale")
    conn = get_conn()
    rows = conn.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    conn.close()
    out = []
    for r in rows:
        d = {"id": r["id"], "name": r["name"], "description": r["description"],
             "category": r["category"], "image": r["image"], "images": _images_of(r), "code": r["code"],
             "sell_price": r["sell_price"], "offers": _offers_of(r), "stock": r["stock"], "active": r["active"]}
        if show_wholesale:
            d["wholesale_price"] = r["wholesale_price"]
        out.append(d)
    return 200, {"products": out, "can_see_wholesale": show_wholesale}


def api_admin_update_product(handler, user, body):
    pid = body.get("id")
    if not pid:
        return 400, {"error": "منتج غير محدد"}
    try:
        conn = get_conn()
        # لو المدير ماعندوش صلاحية الجملة، نحافظ على القيمة القديمة
        if has_perm(user, "wholesale") and body.get("wholesale_price") not in (None, ""):
            wholesale = float(body["wholesale_price"])
        else:
            cur = conn.execute("SELECT wholesale_price FROM products WHERE id=?", (pid,)).fetchone()
            wholesale = cur["wholesale_price"] if cur else 0
        imgs = [u for u in (body.get("images") or []) if isinstance(u, str) and u]
        main = imgs[0] if imgs else (body.get("image") or "📦")
        conn.execute(
            """UPDATE products SET name=?, code=?, description=?, category=?, image=?, images=?,
                   wholesale_price=?, sell_price=?, offers=?, stock=?
               WHERE id=?""",
            (body["name"], (body.get("code") or "").strip(), body.get("description", ""), body.get("category", ""), main, _clean_images(imgs),
             wholesale, float(body["sell_price"]), _clean_offers(body.get("offers")),
             int(body.get("stock", 100)), pid),
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
PUBLIC_GET = {"/api/cities": api_cities}

def api_admin_backup(handler, user, qs):
    """تنزيل نسخة احتياطية من قاعدة البيانات (للمالك)."""
    from db import DB_PATH
    with open(DB_PATH, "rb") as f:
        data = f.read()
    return 200, {"_bytes": data, "filename": "kuwait-market-backup.db", "ctype": "application/octet-stream"}


def api_admin_list_admins(handler, user):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id,name,email,phone,status,role,permissions,created_at FROM users WHERE role IN ('admin','owner') ORDER BY id"
    ).fetchall()
    conn.close()
    admins = []
    for r in rows:
        d = row_to_dict(r)
        try:
            d["permissions"] = json.loads(d.get("permissions") or "[]")
        except Exception:
            d["permissions"] = []
        admins.append(d)
    return 200, {"admins": admins, "perm_catalog": PERMISSIONS}


def api_admin_add_admin(handler, user, body):
    name = (body.get("name") or "").strip()
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    perms = [p for p in (body.get("permissions") or []) if p in PERMISSIONS]
    if not name or not email or len(password) < 6:
        return 400, {"error": "البيانات ناقصة أو كلمة المرور أقل من 6 أحرف"}
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO users (name,email,phone,password,role,permissions) VALUES (?,?,?,?,'admin',?)",
            (name, email, body.get("phone", ""), hash_password(password), json.dumps(perms, ensure_ascii=False)),
        )
        conn.commit()
    except Exception:
        conn.close()
        return 409, {"error": "الإيميل مسجّل بالفعل"}
    conn.close()
    return 200, {"ok": True}


def api_admin_update_admin(handler, user, body):
    uid = body.get("user_id")
    conn = get_conn()
    target = conn.execute("SELECT role FROM users WHERE id=?", (uid,)).fetchone()
    if not target:
        conn.close()
        return 404, {"error": "غير موجود"}
    if target["role"] == "owner":
        conn.close()
        return 403, {"error": "لا يمكن تعديل المالك"}
    if "permissions" in body:
        perms = [p for p in (body.get("permissions") or []) if p in PERMISSIONS]
        conn.execute("UPDATE users SET permissions=? WHERE id=?", (json.dumps(perms, ensure_ascii=False), uid))
    if body.get("status") in ("active", "banned"):
        conn.execute("UPDATE users SET status=? WHERE id=?", (body["status"], uid))
    conn.commit()
    conn.close()
    return 200, {"ok": True}


_DENY = (403, {"error": "ممنوع"})
AUTH_GET = {
    "/api/me": lambda h, u, q: api_me(h, u),
    "/api/products": lambda h, u, q: api_products(h, q),
    "/api/dashboard": lambda h, u, q: api_dashboard(h, u, q),
    "/api/my-orders": lambda h, u, q: api_my_orders(h, u),
    "/api/stats": lambda h, u, q: api_stats(h, u),
    "/api/my-withdrawals": lambda h, u, q: api_my_withdrawals(h, u),
    "/api/admin/orders": lambda h, u, q: api_admin_orders(h, u, q) if has_perm(u, "orders") else _DENY,
    "/api/admin/export-orders": lambda h, u, q: api_admin_export_orders(h, u, q) if has_perm(u, "export") else _DENY,
    "/api/admin/withdrawals": lambda h, u, q: api_admin_withdrawals(h, u) if has_perm(u, "withdrawals") else _DENY,
    "/api/admin/marketers": lambda h, u, q: api_admin_marketers(h, u) if has_perm(u, "marketers") else _DENY,
    "/api/admin/groups": lambda h, u, q: api_admin_groups(h, u) if (has_perm(u, "groups") or has_perm(u, "marketers") or has_perm(u, "orders")) else _DENY,
    "/api/admin/products": lambda h, u, q: api_admin_products(h, u) if has_perm(u, "products") else _DENY,
    "/api/admin/admins": lambda h, u, q: api_admin_list_admins(h, u) if require_owner(u) else _DENY,
    "/api/admin/pending": lambda h, u, q: api_admin_pending(h, u) if require_owner(u) else _DENY,
    "/api/admin/product-stats": lambda h, u, q: api_product_stats(h, u, q) if has_perm(u, "products") else _DENY,
    "/api/admin/spend-entries": lambda h, u, q: api_admin_spend_entries(h, u, q) if has_perm(u, "products") else _DENY,
    "/api/admin/backup": lambda h, u, q: api_admin_backup(h, u, q) if require_owner(u) else _DENY,
}
AUTH_POST = {
    "/api/logout": api_logout,
    "/api/orders": api_create_order,
    "/api/withdraw": api_withdraw,
    "/api/change-password": api_change_password,
    "/api/admin/approve-user": lambda h, u, b: api_admin_approve_user(h, u, b) if require_owner(u) else _DENY,
    "/api/admin/update-order": lambda h, u, b: api_admin_update_order(h, u, b) if has_perm(u, "orders") else _DENY,
    "/api/admin/update-withdrawal": lambda h, u, b: api_admin_update_withdrawal(h, u, b) if has_perm(u, "withdrawals") else _DENY,
    "/api/admin/add-product": lambda h, u, b: api_admin_add_product(h, u, b) if has_perm(u, "products") else _DENY,
    "/api/admin/toggle-ban": lambda h, u, b: api_admin_toggle_ban(h, u, b) if has_perm(u, "marketers") else _DENY,
    "/api/admin/add-group": lambda h, u, b: api_admin_add_group(h, u, b) if has_perm(u, "groups") else _DENY,
    "/api/admin/assign-group": lambda h, u, b: api_admin_assign_group(h, u, b) if (has_perm(u, "groups") or has_perm(u, "marketers")) else _DENY,
    "/api/admin/set-leader": lambda h, u, b: api_admin_set_leader(h, u, b) if has_perm(u, "groups") else _DENY,
    "/api/admin/upload-image": lambda h, u, b: api_admin_upload_image(h, u, b) if has_perm(u, "products") else _DENY,
    "/api/admin/update-product": lambda h, u, b: api_admin_update_product(h, u, b) if has_perm(u, "products") else _DENY,
    "/api/admin/toggle-product": lambda h, u, b: api_admin_toggle_product(h, u, b) if has_perm(u, "products") else _DENY,
    "/api/admin/add-admin": lambda h, u, b: api_admin_add_admin(h, u, b) if require_owner(u) else _DENY,
    "/api/admin/update-admin": lambda h, u, b: api_admin_update_admin(h, u, b) if require_owner(u) else _DENY,
    "/api/admin/bulk-update-orders": lambda h, u, b: api_admin_bulk_update(h, u, b) if has_perm(u, "orders") else _DENY,
    "/api/admin/add-spend": lambda h, u, b: api_admin_add_spend(h, u, b) if has_perm(u, "products") else _DENY,
    "/api/admin/delete-spend": lambda h, u, b: api_admin_delete_spend(h, u, b) if has_perm(u, "products") else _DENY,
}

# المعالِجات اللي بتاخد body
POST_WITH_BODY = {"/api/orders", "/api/withdraw", "/api/change-password"}


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

    def _send_bytes(self, data, filename, ctype):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
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
            if isinstance(payload, dict) and "_bytes" in payload:
                return self._send_bytes(payload["_bytes"], payload.get("filename", "file"), payload.get("ctype", "application/octet-stream"))
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
