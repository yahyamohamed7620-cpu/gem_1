# نشر Kuwait Market على PythonAnywhere (مجاني تماماً — بدون بطاقة)

الموقع هيبقى على رابط شكله: `https://USERNAME.pythonanywhere.com`
والبيانات بتتخزّن وتفضل محفوظة. كله من المتصفح.

## 1) اعمل حساب
- افتح **pythonanywhere.com** ➜ **Pricing & signup** ➜ اختار **Create a Beginner account** (مجاني).
- اكمل التسجيل وفعّل الإيميل.

## 2) نزّل الكود من GitHub
- من القائمة فوق افتح **Consoles** ➜ ابدأ **Bash** console جديدة.
- اكتب الأمر ده واضغط Enter:
  ```
  git clone https://github.com/yahyamohamed7620-cpu/gem_1
  ```
  هيتعمل فولدر اسمه `gem_1` فيه كل الكود.

## 3) اعمل الـ Web App
- من فوق افتح تبويب **Web** ➜ **Add a new web app** ➜ **Next**.
- اختار **Manual configuration** (مش Flask) ➜ اختار **Python 3.10** (أو أحدث) ➜ **Next**.

## 4) اظبط المسارات
في صفحة إعدادات الـ Web app:
- **Source code:** اكتب `/home/USERNAME/gem_1`  (بدّل USERNAME باسمك).
- **Working directory:** `/home/USERNAME/gem_1`
- في خانة **WSGI configuration file** اضغط على الرابط عشان تعدّله، **امسح كل اللي فيه**
  وحط ده (بدّل USERNAME):
  ```python
  import sys
  path = "/home/USERNAME/gem_1"
  if path not in sys.path:
      sys.path.insert(0, path)
  from wsgi import application
  ```
  بعدين **Save**.

## 5) شغّل
- ارجع لتبويب **Web** واضغط الزر الأخضر الكبير **Reload**.
- افتح الرابط `https://USERNAME.pythonanywhere.com` ➜ الموقع اشتغل 🎉

## حسابات الدخول
- أدمن: `admin@kuwaitmarket.local` / `admin123`  ← **غيّر الباسورد ده**
- مسوّق تجريبي: `marketer@kuwaitmarket.local` / `demo123`

## تغيير باسورد الأدمن (مهم)
في Bash console:
```
cd gem_1
python3 -c "import os,db; db.init_db(); c=db.get_conn(); c.execute('UPDATE users SET password=? WHERE role=\"admin\"',(db.hash_password('كلمة_السر_الجديدة'),)); c.commit(); print('done')"
```

## ملاحظات
- الباقة المجانية بتسيب الموقع شغّال، بس بتطلب تضغط **Reload** مرة كل ~3 شهور.
- لو عدّلت الكود على GitHub لاحقاً: في Bash اكتب `cd gem_1 && git pull` بعدين اضغط **Reload**.
