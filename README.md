# خطة التنشيف وبناء العضلات — Streamlit

المشروع جاهز للنشر على GitHub ثم Streamlit Community Cloud. الواجهة نفسها مبنية بـ HTML/CSS/JavaScript داخل مكوّن iframe، حتى تستمر رسومات SVG المتحركة والتفاعل وحفظ البيانات محليًا في المتصفح.

## النشر على GitHub وStreamlit Cloud

1. ارفع كل ملفات هذا المشروع إلى مستودع GitHub.
2. افتح https://share.streamlit.io/ وسجّل الدخول بحساب GitHub.
3. اختر **Create app** وحدد المستودع والفرع `main`.
4. في خانة **Main file path** اكتب `app.py`.
5. اضغط **Deploy** وانتظر انتهاء التثبيت.

## تشغيله محليًا

```bash
py -m pip install -r requirements.txt
py -m streamlit run app.py
```

## الملفات

- `app.py`: نقطة تشغيل Streamlit؛ لا تستخدم Flask ولا `app.run()`.
- `templates/index.html`: الواجهة الأصلية مع CSS وJavaScript ورسوم SVG.
- `requirements.txt`: اعتماد Streamlit للنشر.

## ملاحظة حفظ البيانات

سجل الوزن والوجبات وأوزان التمارين وعلامات الإنجاز محفوظة في `localStorage` داخل المتصفح. قد يختلف استمرار التخزين حسب المتصفح وبيئة iframe، ولا تتم مزامنة البيانات بين الأجهزة. لا تمسح بيانات الموقع إذا كنت تريد الاحتفاظ بالسجل.

خط Cairo يأتي من Google Fonts، لذلك يحتاج الإنترنت ليظهر بالشكل المحدد؛ توجد خطوط بديلة عند تعذر تحميله.
