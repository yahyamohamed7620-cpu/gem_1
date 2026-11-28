"""
محوّل WSGI لتشغيل Kuwait Market على استضافات WSGI زي PythonAnywhere.
بيعيد استخدام نفس منطق التوجيه والـ API الموجود في app.py، من غير أي تكرار.

على PythonAnywhere: في تبويب Web، خلّي ملف الـ WSGI يستورد التطبيق من هنا:
    from wsgi import application
"""
import json
import os
from urllib.parse import urlparse, parse_qs

from app import (
    PUBLIC_POST, PUBLIC_GET, AUTH_GET, AUTH_POST, POST_WITH_BODY,
    current_user, STATIC_DIR, bootstrap,
)

# تجهيز القاعدة والبيانات أول تشغيل (زي ما بيعمل app.py عند التشغيل المباشر).
bootstrap()

CTYPES = {
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
}


# رؤوس أمان تُضاف لكل الردود
SEC_HEADERS = [
    ("X-Content-Type-Options", "nosniff"),
    ("X-Frame-Options", "DENY"),
    ("Referrer-Policy", "no-referrer"),
    ("Strict-Transport-Security", "max-age=31536000; includeSubDomains"),
    ("Content-Security-Policy",
     "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
     "script-src 'self' 'unsafe-inline'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"),
]

_STATIC_REAL = os.path.realpath(STATIC_DIR)


class _Shim:
    """كائن بسيط بيوفّر .headers زي اللي بتستخدمه دوال app.py."""
    def __init__(self, environ):
        self.headers = {"Authorization": environ.get("HTTP_AUTHORIZATION", "")}


def _json(start_response, code, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    status = f"{code} OK" if code == 200 else f"{code} ERROR"
    start_response(status, [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Content-Length", str(len(body))),
    ])
    return [body]


def _file(start_response, path):
    # حماية من الخروج خارج مجلد static (path traversal)
    real = os.path.realpath(path)
    if not (real == _STATIC_REAL or real.startswith(_STATIC_REAL + os.sep)) or not os.path.isfile(real):
        start_response("404 Not Found", [("Content-Type", "text/plain; charset=utf-8")])
        return [b"Not Found"]
    path = real
    ext = os.path.splitext(path)[1]
    ctype = CTYPES.get(ext, "application/octet-stream")
    with open(path, "rb") as f:
        data = f.read()
    # منع الكاش على ملفات الواجهة عشان أي تحديث يظهر فورًا للمستخدم
    headers = [("Content-Type", ctype), ("Content-Length", str(len(data)))]
    if ext in (".html", ".js", ".css"):
        headers.append(("Cache-Control", "no-cache, no-store, must-revalidate"))
    start_response("200 OK", headers)
    return [data]


def application(environ, _start_response):
    # إضافة رؤوس الأمان لكل رد
    def start_response(status, headers):
        return _start_response(status, headers + SEC_HEADERS)

    method = environ.get("REQUEST_METHOD", "GET")
    parsed = urlparse(environ.get("PATH_INFO", "/"))
    path = parsed.path
    shim = _Shim(environ)

    # قراءة جسم الطلب (JSON)
    def read_body():
        try:
            length = int(environ.get("CONTENT_LENGTH", 0) or 0)
        except (ValueError, TypeError):
            length = 0
        if length <= 0:
            return {}
        raw = environ["wsgi.input"].read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    # في WSGI سلسلة الاستعلام في QUERY_STRING مش في PATH_INFO
    query = parse_qs(environ.get("QUERY_STRING", ""))
    if method == "GET":
        if path in PUBLIC_GET:
            code, payload = PUBLIC_GET[path](shim, query)
            return _json(start_response, code, payload)
        if path in AUTH_GET:
            user = current_user(shim)
            if not user:
                return _json(start_response, 401, {"error": "سجّل الدخول أولاً"})
            code, payload = AUTH_GET[path](shim, user, query)
            if isinstance(payload, dict) and "_csv" in payload:
                data = payload["_csv"].encode("utf-8")
                start_response("200 OK", [
                    ("Content-Type", "text/csv; charset=utf-8"),
                    ("Content-Disposition", f'attachment; filename="{payload.get("filename", "export.csv")}"'),
                    ("Content-Length", str(len(data))),
                ])
                return [data]
            if isinstance(payload, dict) and "_bytes" in payload:
                data = payload["_bytes"]
                start_response("200 OK", [
                    ("Content-Type", payload.get("ctype", "application/octet-stream")),
                    ("Content-Disposition", f'attachment; filename="{payload.get("filename", "file")}"'),
                    ("Content-Length", str(len(data))),
                ])
                return [data]
            return _json(start_response, code, payload)
        # ملفات ثابتة
        if path in ("/", ""):
            return _file(start_response, os.path.join(STATIC_DIR, "index.html"))
        safe = os.path.normpath(path).lstrip("/\\")
        return _file(start_response, os.path.join(STATIC_DIR, safe))

    if method == "POST":
        body = read_body()
        if path in PUBLIC_POST:
            code, payload = PUBLIC_POST[path](shim, body)
            return _json(start_response, code, payload)
        if path in AUTH_POST:
            user = current_user(shim)
            if not user:
                return _json(start_response, 401, {"error": "سجّل الدخول أولاً"})
            fn = AUTH_POST[path]
            if path in POST_WITH_BODY or path.startswith("/api/admin/") or path == "/api/withdraw":
                code, payload = fn(shim, user, body)
            else:
                code, payload = fn(shim, user)
            return _json(start_response, code, payload)
        return _json(start_response, 404, {"error": "مسار غير موجود"})

    start_response("405 Method Not Allowed", [("Content-Type", "text/plain")])
    return [b"Method Not Allowed"]
