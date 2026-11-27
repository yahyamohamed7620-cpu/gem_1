"""
تعبئة البيانات الأولية: حساب أدمن + حساب مسوق تجريبي + منتجات.
شغّله مرة واحدة بعد إنشاء القاعدة. آمن للتكرار (مايكررش لو موجود).
"""
import os
from db import get_conn, init_db, hash_password

# كلمة سر الأدمن والإيميل ممكن تتحدد من إعدادات الاستضافة (Environment Variables)
# عشان تبقى آمنة. لو متحددتش بتستخدم القيم الافتراضية التجريبية.
ADMIN = {
    "name": "مدير النظام",
    "email": os.environ.get("ADMIN_EMAIL", "admin@kuwaitmarket.local"),
    "phone": "0000",
    "password": os.environ.get("ADMIN_PASSWORD", "admin123"),
    "role": "admin",
}

DEMO_MARKETER = {
    "name": "مسوّق تجريبي",
    "email": "marketer@kuwaitmarket.local",
    "phone": "1111",
    "password": "demo123",
    "role": "marketer",
}

PRODUCTS = [
    ("فرشاة أسنان كهربائية NISHICA", "فرشاة أسنان كهربائية تعمل بالبطارية، تنظيف عميق وفعال.", "العناية الشخصية", "🪥", 3.50, 4.99, 6.99, 1.0, 150),
    ("كشاف LED بالطاقة الشمسية مع ريموت", "إضاءة قوية بالطاقة الشمسية، يتحكم فيه ريموت، مقاوم للماء.", "إضاءة", "🔦", 4.00, 5.99, 7.99, 1.0, 120),
    ("بوابة أمان للأطفال 77-82 سم", "بوابة حماية للأطفال قابلة للتعديل، تركيب سهل بدون مسامير.", "مستلزمات أطفال", "🚪", 10.00, 12.99, 15.99, 1.0, 60),
    ("فانوس تخييم قابل للشحن بكرة ديسكو", "فانوس تخييم متعدد الاستخدامات بإضاءة ديسكو ممتعة.", "رحلات", "🏕️", 3.50, 5.99, 7.99, 1.0, 100),
    ("إضاءة جدارية بحساس حركة", "إضاءة جدارية ذكية تشتغل عند الحركة، توفير في الطاقة.", "إضاءة", "💡", 3.50, 5.99, 7.99, 1.0, 200),
    ("خيمة شاطئ تلقائية Splashers", "خيمة شاطئ تنصب تلقائيًا، حماية من الشمس، خفيفة وعملية.", "رحلات", "⛺", 5.00, 7.99, 10.99, 1.5, 80),
    ("ستارة إضاءة LED بشكل ثريات", "ستارة إضاءة ديكورية رائعة للمناسبات والديكور.", "ديكور", "✨", 3.50, 5.99, 7.99, 1.0, 140),
    ("إضاءة جدار شمسية بألوان متعددة", "إضاءة خارجية بالطاقة الشمسية بألوان متغيرة.", "إضاءة", "🌈", 3.50, 5.99, 7.99, 1.0, 160),
    ("طاولة لابتوب قابلة للطي مع مروحة", "طاولة لابتوب عملية بمروحة تبريد مدمجة، قابلة للطي.", "مكتبية", "💻", 5.00, 7.99, 10.99, 1.5, 90),
    ("لابتوب تعليمي للأطفال بابا مشمش", "لابتوب تعليمي تفاعلي للأطفال، ألعاب وتعليم بالعربي.", "مستلزمات أطفال", "🧸", 3.50, 5.99, 7.99, 1.0, 110),
    ("ساعة ذكية رياضية Smart Watch", "ساعة ذكية بمتابعة اللياقة ونبض القلب وإشعارات.", "إلكترونيات", "⌚", 8.00, 11.99, 15.99, 2.0, 70),
    ("سماعات بلوتوث لاسلكية", "سماعات أذن لاسلكية بجودة صوت عالية وبطارية طويلة.", "إلكترونيات", "🎧", 6.00, 9.99, 13.99, 1.5, 85),
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
        for p in PRODUCTS:
            cur.execute(
                """INSERT INTO products
                   (name,description,category,image,base_price,min_price,max_price,commission,stock)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                p,
            )

    conn.commit()
    conn.close()
    print("Seed done.")
    print("Admin   login:", ADMIN["email"], "/", ADMIN["password"])
    print("Marketer login:", DEMO_MARKETER["email"], "/", DEMO_MARKETER["password"])


if __name__ == "__main__":
    seed()
