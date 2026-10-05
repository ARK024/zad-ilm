# 🚀 دليل بناء تطبيق زاد العلم - Windows EXE

هذا الدليل يوضح خطوات بناء ملف تنفيذي لويندوز (`zad-al-ilm.exe` أو حزمة التثبيت `Setup.exe`) لتطبيق **زاد العلم**.

---

## 📋 المتطلبات على جهاز ويندوز

1. **تثبيت Rust**:
   - من الموقع الرسمي: https://rustup.rs/
   - حمل `rustup-init.exe` واختر الخيار الافتراضي (Default Installation).

2. **تثبيت Visual Studio C++ Build Tools**:
   - حمل من: https://visualstudio.microsoft.com/visual-cpp-build-tools/
   - حدد: `Desktop development with C++`.

3. **WebView2**:
   - مثبت مسبقاً في Windows 10 و Windows 11.

---

## 🔨 خطوات البناء المباشر

### الطريقة 1: باستخدام Tauri CLI (موصى بها لإنشاء المثبت Installer)

افتح سطر الأوامر (PowerShell أو CMD) في مجلد المشروع:

```powershell
# 1. الانتقال إلى مجلد src-tauri
cd path\to\zad-ilm\src-tauri

# 2. بناء حزمة التثبيت وملف الـ EXE
cargo tauri build
```

ستجد ملف التثبيت الناتج في:
```
src-tauri\target\release\bundle\nsis\zad-al-ilm_1.0.0_x64-setup.exe
```

---

### الطريقة 2: البناء السريع بـ Cargo فقط (Standalone EXE)

إذا كنت ترغب فقط في ملف تنفيذي محمول (Portable `.exe` بدون تثبيت):

```powershell
cd path\to\zad-ilm\src-tauri
cargo build --release
```

الملف التنفيذي الناتج:
```
src-tauri\target\release\zad-al-ilm.exe
```
حجمه تقريباً ~6 إلى 8 ميجابايت فقط، ويمكن تشغيله مباشرة بنقرة زر!

---

## 🌐 البناء عبر GitHub Actions (بدون الحاجة لويندوز)

يمكنك رفع الكود إلى مستودع GitHub وتفعيل GitHub Action لبناء ملف الويندوز تلقائياً عبر سيرفرات مايكروسوفت وتحميل الـ `.exe` الجاهز من قسم Releases.
