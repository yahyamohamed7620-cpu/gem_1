"""
تعبئة البيانات الأولية: حساب أدمن + حساب مسوق تجريبي + منتجات.
شغّله مرة واحدة بعد إنشاء القاعدة. آمن للتكرار (مايكررش لو موجود).
"""
import os
from db import get_conn, init_db, hash_password

# كلمة سر الأدمن والإيميل ممكن تتحدد من إعدادات الاستضافة (Environment Variables)
# عشان تبقى آمنة. لو متحددتش بتستخدم القيم الافتراضية التجريبية.
ADMIN = {
    "name": "المالك",
    "email": os.environ.get("ADMIN_EMAIL", "admin@kuwaitmarket.local"),
    "phone": "0000",
    "password": os.environ.get("ADMIN_PASSWORD", "admin123"),
    "role": "owner",
}

DEMO_MARKETER = {
    "name": "مسوّق تجريبي",
    "email": "marketer@kuwaitmarket.local",
    "phone": "1111",
    "password": "demo123",
    "role": "marketer",
}

# (الاسم, الوصف, التصنيف, صورة, سعر الجملة, سعر البيع, عروض الكمية, المخزون)
PRODUCTS = [
    ("فرشاة أسنان كهربائية NISHICA", "فرشاة أسنان كهربائية تعمل بالبطارية، تنظيف عميق وفعال.", "العناية الشخصية", "🪥", 3.50, 5.99, [{"qty": 2, "price": 10.99}, {"qty": 3, "price": 14.99}], 150),
    ("كشاف LED بالطاقة الشمسية مع ريموت", "إضاءة قوية بالطاقة الشمسية، يتحكم فيه ريموت، مقاوم للماء.", "إضاءة", "🔦", 4.00, 6.99, [{"qty": 2, "price": 12.99}], 120),
    ("بوابة أمان للأطفال 77-82 سم", "بوابة حماية للأطفال قابلة للتعديل، تركيب سهل بدون مسامير.", "مستلزمات أطفال", "🚪", 10.00, 14.99, [], 60),
    ("فانوس تخييم قابل للشحن بكرة ديسكو", "فانوس تخييم متعدد الاستخدامات بإضاءة ديسكو ممتعة.", "رحلات", "🏕️", 3.50, 5.99, [], 100),
    ("إضاءة جدارية بحساس حركة", "إضاءة جدارية ذكية تشتغل عند الحركة، توفير في الطاقة.", "إضاءة", "💡", 3.50, 5.99, [{"qty": 2, "price": 10.99}, {"qty": 4, "price": 19.99}], 200),
    ("خيمة شاطئ تلقائية Splashers", "خيمة شاطئ تنصب تلقائيًا، حماية من الشمس، خفيفة وعملية.", "رحلات", "⛺", 5.00, 7.99, [], 80),
    ("ستارة إضاءة LED بشكل ثريات", "ستارة إضاءة ديكورية رائعة للمناسبات والديكور.", "ديكور", "✨", 3.50, 5.99, [], 140),
    ("إضاءة جدار شمسية بألوان متعددة", "إضاءة خارجية بالطاقة الشمسية بألوان متغيرة.", "إضاءة", "🌈", 3.50, 5.99, [{"qty": 2, "price": 10.99}], 160),
    ("طاولة لابتوب قابلة للطي مع مروحة", "طاولة لابتوب عملية بمروحة تبريد مدمجة، قابلة للطي.", "مكتبية", "💻", 5.00, 7.99, [], 90),
    ("لابتوب تعليمي للأطفال بابا مشمش", "لابتوب تعليمي تفاعلي للأطفال، ألعاب وتعليم بالعربي.", "مستلزمات أطفال", "🧸", 3.50, 5.99, [], 110),
    ("ساعة ذكية رياضية Smart Watch", "ساعة ذكية بمتابعة اللياقة ونبض القلب وإشعارات.", "إلكترونيات", "⌚", 8.00, 11.99, [{"qty": 2, "price": 21.99}], 70),
    ("سماعات بلوتوث لاسلكية", "سماعات أذن لاسلكية بجودة صوت عالية وبطارية طويلة.", "إلكترونيات", "🎧", 6.00, 9.99, [], 85),
]


def seed():
    init_db()
    conn = get_conn()
    cur = conn.cursor()

    for u in (ADMIN, DEMO_MARKETER):
        exists = cur.execute("SELECT 1 FROM users WHERE email=?", (u["email"],)).fetchone()
        if not exists:
            cur.execute(
                "INSERT INTO users (name,email,phone,password,role) VALUES (?,?,?,?,?)",
                (u["name"], u["email"], u["phone"], hash_password(u["password"]), u["role"]),
            )

    count = cur.execute("SELECT COUNT(*) AS c FROM products").fetchone()["c"]
    if count == 0:
        import json as _json
        for name, desc, cat, img, wholesale, sell, offers, stock in PRODUCTS:
            cur.execute(
                """INSERT INTO products
                   (name,description,category,image,wholesale_price,sell_price,offers,stock)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (name, desc, cat, img, wholesale, sell, _json.dumps(offers, ensure_ascii=False), stock),
            )

    conn.commit()
    conn.close()
    print("Seed done.")
    print("Admin   login:", ADMIN["email"], "/", ADMIN["password"])
    print("Marketer login:", DEMO_MARKETER["email"], "/", DEMO_MARKETER["password"])


if __name__ == "__main__":
    seed()
