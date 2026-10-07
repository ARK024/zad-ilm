# -*- coding: utf-8 -*-
"""قوالب HTML/CSS الخاصة بنافذة الودجت (تُعرض داخل AnkiWebView)."""
from __future__ import annotations

import html as _html
import json

RATE_NAMES = {1: "أعد", 2: "صعب", 3: "جيد", 4: "سهل"}

BODY = """
<div id="zad-root">
  <div id="zad-scroll-area">
    <div id="zad-qa"></div>
    <div id="zad-opts"></div>
    <div id="zad-extra"></div>
  </div>
  <div id="zad-bar"></div>
</div>
<script>
function zadSetFont(fs) {
  if (fs) {
    document.documentElement.style.setProperty("--zad-fs", fs + "px");
  }
}
function zadRender(s) {
  if (s.bodyclass !== undefined && s.bodyclass !== null) {
    document.body.className = s.bodyclass + " zad-body";
    var isNight = s.bodyclass.indexOf("nightMode") !== -1 || s.bodyclass.indexOf("night_mode") !== -1;
    if (isNight) {
      document.documentElement.classList.add("nightMode", "night_mode");
      document.documentElement.style.setProperty("--zad-bg", "#1b1f23");
      document.documentElement.style.setProperty("--zad-fg", "#f3f4f6");
      document.documentElement.style.backgroundColor = "#1b1f23";
      document.body.style.backgroundColor = "#1b1f23";
    } else {
      document.documentElement.classList.remove("nightMode", "night_mode");
      document.documentElement.style.setProperty("--zad-bg", "#fffdf7");
      document.documentElement.style.setProperty("--zad-fg", "#1f2937");
      document.documentElement.style.backgroundColor = "#fffdf7";
      document.body.style.backgroundColor = "#fffdf7";
    }
    var qa = document.getElementById("zad-qa");
    if (qa) {
      if (isNight) {
        qa.classList.add("nightMode", "night_mode");
      } else {
        qa.classList.remove("nightMode", "night_mode");
      }
    }
  }
  if (s.fs) {
    document.documentElement.style.setProperty("--zad-fs", s.fs + "px");
  }
  var qa = document.getElementById("zad-qa");
  if (s.qa !== undefined && s.qa !== null) { $(qa).html(s.qa); }
  if (s.opts !== undefined && s.opts !== null) { document.getElementById("zad-opts").innerHTML = s.opts; }
  if (s.extra !== undefined && s.extra !== null) { document.getElementById("zad-extra").innerHTML = s.extra; }
  if (s.bar !== undefined && s.bar !== null) { document.getElementById("zad-bar").innerHTML = s.bar; }

  var scrollArea = document.getElementById("zad-scroll-area");
  if (s.scroll) {
    var a = document.getElementById("answer") || document.getElementById("zad-extra");
    if (a && a.scrollIntoView) {
      a.scrollIntoView({ behavior: "smooth", block: "start" });
    } else if (scrollArea) {
      scrollArea.scrollTop = scrollArea.scrollHeight;
    }
  } else if (s.scroll === false) {
    if (scrollArea) { scrollArea.scrollTop = 0; }
  }
}
document.addEventListener("keydown", function (e) {
  if (e.ctrlKey && (e.key === "+" || e.key === "=")) { e.preventDefault(); pycmd("zoom:in"); return; }
  if (e.ctrlKey && e.key === "-") { e.preventDefault(); pycmd("zoom:out"); return; }
  if (e.ctrlKey || e.altKey || e.metaKey) return;
  if (e.key === " " || e.key === "Enter") { e.preventDefault(); pycmd("ans"); }
  else if (e.key >= "1" && e.key <= "4") { pycmd("ease:" + e.key); }
  else if (e.key === "Escape") { pycmd("close"); }
  else if (e.key === "f" || e.key === "F") { e.preventDefault(); pycmd("toggle_expand"); }
});
</script>
"""

CSS = """
:root {
  --zad-fs: 17px;
  --zad-gold: #b8860b;
  --zad-green: #166534;
  --zad-red: #b91c1c;
  --zad-bg: #fffdf7;
  --zad-fg: #1f2937;
  --zad-border: #d9cfae;
  --zad-soft: #f4ecd2;
}

:root.night-mode,
:root.nightMode,
:root.night_mode,
:root[data-bs-theme="dark"],
html.nightMode,
html.night_mode,
body.nightMode,
body.night_mode {
  --zad-bg: #1b1f23 !important;
  --zad-fg: #f3f4f6 !important;
  --zad-border: #3b4350 !important;
  --zad-soft: #262c33 !important;
}

html, body {
  margin: 0;
  padding: 0;
  width: 100%;
  height: 100%;
  overflow: hidden !important;
  background: var(--zad-bg) !important;
  background-color: var(--zad-bg) !important;
  color: var(--zad-fg) !important;
  direction: rtl;
  box-sizing: border-box;
}

html.nightMode, html.night_mode,
body.nightMode, body.night_mode {
  background: #1b1f23 !important;
  background-color: #1b1f23 !important;
  color: #f3f4f6 !important;
}

body.nightMode #zad-root,
body.night_mode #zad-root,
body.nightMode #zad-bar,
body.night_mode #zad-bar {
  background: #1b1f23 !important;
  background-color: #1b1f23 !important;
}

body.nightMode #zad-scroll-area,
body.night_mode #zad-scroll-area,
body.nightMode #zad-qa,
body.night_mode #zad-qa {
  background: transparent !important;
  background-color: transparent !important;
  color: #f3f4f6 !important;
}

body {
  font-size: var(--zad-fs);
}

#zad-root {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100vh;
  box-sizing: border-box;
  padding: 8px 12px 6px;
  overflow: hidden;
}

/* منطقة محتوى البطاقة — تتمدد وتوفر تمريرًا داخليًا أنيقًا عند كبر البطاقة */
#zad-scroll-area {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  padding-left: 4px;
  padding-right: 4px;
  padding-bottom: 6px;
  box-sizing: border-box;
}

#zad-scroll-area::-webkit-scrollbar {
  width: 6px;
}
#zad-scroll-area::-webkit-scrollbar-track {
  background: transparent;
}
#zad-scroll-area::-webkit-scrollbar-thumb {
  background: var(--zad-border);
  border-radius: 4px;
}
#zad-scroll-area::-webkit-scrollbar-thumb:hover {
  background: var(--zad-gold);
}

#zad-qa {
  padding: 4px 2px;
  text-align: right;
  line-height: 1.85;
  min-height: 30px;
  background: transparent !important;
  margin: 0 !important;
  font-size: var(--zad-fs) !important;
  color: inherit;
}
#zad-qa img {
  max-width: 100%;
  height: auto;
}

/* أيقونة تشغيل الصوتيات (Replay / Audio Button) */
.replay-button, a.soundLink {
  text-decoration: none !important;
  display: inline-flex !important;
  align-items: center;
  justify-content: center;
  vertical-align: middle;
  margin: 0 6px;
  cursor: pointer;
}
.replay-button svg, a.soundLink svg, svg.playImage {
  width: 32px !important;
  height: 32px !important;
  max-width: 32px !important;
  max-height: 32px !important;
  display: inline-block !important;
  vertical-align: middle;
}
.replay-button svg circle, a.soundLink svg circle, svg.playImage circle {
  fill: #fffdf7 !important;
  stroke: var(--zad-gold) !important;
  stroke-width: 2.5px;
}
.replay-button svg path, a.soundLink svg path, svg.playImage path {
  fill: var(--zad-gold) !important;
}
.replay-button:hover svg circle, a.soundLink:hover svg circle {
  fill: var(--zad-soft) !important;
}

/* الوضع الليلي لأيقونة الصوت */
.nightMode .replay-button svg circle,
.night_mode .replay-button svg circle,
body.nightMode svg.playImage circle,
body.night_mode svg.playImage circle {
  fill: #262c33 !important;
  stroke: var(--zad-gold) !important;
}
.nightMode .replay-button svg path,
.night_mode .replay-button svg path,
body.nightMode svg.playImage path,
body.night_mode svg.playImage path {
  fill: #e5e7eb !important;
}
.nightMode .replay-button:hover svg circle,
.night_mode .replay-button:hover svg circle {
  fill: #3b4350 !important;
}

#zad-extra:empty, #zad-opts:empty { display: none; }
.zad-opts { display: flex; flex-direction: column; gap: 8px; margin: 10px 0; }
.zad-opt { text-align: right; font: inherit; font-size: .95em; padding: 8px 12px; cursor: pointer;
           border: 1px solid var(--zad-border); border-radius: 10px; background: var(--zad-soft); color: inherit; }
.zad-opt:hover:not(:disabled) { border-color: var(--zad-gold); }
.zad-opt.correct { background: #dcfce7; border-color: #16a34a; color: #14532d; font-weight: bold; }
.zad-opt.wrong { background: #fee2e2; border-color: #dc2626; color: #7f1d1d; }
.nightMode .zad-opt.correct, .night_mode .zad-opt.correct { background: #14532d; color: #dcfce7; }
.nightMode .zad-opt.wrong, .night_mode .zad-opt.wrong { background: #7f1d1d; color: #fee2e2; }
.zad-opt:disabled { cursor: default; opacity: 1; }
.zad-evidence { margin: 10px 0; padding: 10px 14px; border-right: 4px solid var(--zad-gold);
                background: rgba(184,134,11,.10); border-radius: 8px; font-size: .92em; line-height: 1.9; }
.zad-answer { color: var(--zad-green); font-weight: bold; margin-top: 8px; }
.nightMode .zad-answer, .night_mode .zad-answer { color: #86efac; }
.zad-source { color: #6b7280; font-size: .8em; margin-top: 6px; }
.nightMode .zad-source, .night_mode .zad-source { color: #9ca3af; }
.zad-verdict { font-weight: bold; margin: 6px 0; }
.zad-verdict.ok { color: var(--zad-green); } .zad-verdict.no { color: var(--zad-red); }

/* شريط الأزرار السفلي — ثابت دائماً في قاع النافذة ولا يطفو أو يختفي أبدًا */
#zad-bar {
  flex: 0 0 auto;
  width: 100%;
  box-sizing: border-box;
  background: var(--zad-bg);
  padding: 8px 0 2px;
  border-top: 1px solid var(--zad-border);
  margin-top: 4px;
  z-index: 100;
}

.zad-show {
  width: 100%;
  padding: 10px;
  font: inherit;
  font-weight: bold;
  cursor: pointer;
  color: #fff;
  background: var(--zad-gold);
  border: 0;
  border-radius: 10px;
  transition: opacity 0.15s ease;
}
.zad-show:hover { opacity: 0.92; }

.zad-rate {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 6px;
}
.zad-rate button {
  font: inherit;
  font-size: .88em;
  padding: 6px 2px;
  cursor: pointer;
  border-radius: 10px;
  border: 2px solid transparent;
  color: #fff !important;
  display: flex;
  flex-direction: column;
  align-items: center;
  line-height: 1.35;
  transition: transform 0.1s ease, filter 0.15s ease;
}
.zad-rate button:hover { filter: brightness(1.08); }
.zad-rate button:active { transform: scale(0.98); }
.zad-rate small {
  font-size: .74em;
  opacity: .95;
  direction: ltr;
  font-weight: normal;
  color: #fff !important;
}
.zad-rate .r1 { background: #dc2626 !important; }
.zad-rate .r2 { background: #d97706 !important; }
.zad-rate .r3 { background: #16a34a !important; }
.zad-rate .r4 { background: #2563eb !important; }
.zad-rate button.suggest {
  border-color: var(--zad-fg) !important;
  box-shadow: 0 0 0 2px var(--zad-gold);
}

.zad-hint {
  text-align: center;
  color: #6b7280;
  font-size: .75em;
  margin-top: 4px;
}
.nightMode .zad-hint, .night_mode .zad-hint { color: #9ca3af; }

.zad-done { text-align: center; padding: 28px 8px; line-height: 2; }
.zad-done b { color: var(--zad-green); font-size: 1.15em; }
.nightMode .zad-done b, .night_mode .zad-done b { color: #86efac; }
.zad-btn2 {
  margin-top: 10px; font: inherit; padding: 8px 18px; cursor: pointer; border-radius: 10px;
  border: 1px solid var(--zad-gold); background: transparent; color: inherit;
}

/* ==========================================================================
   حل تضارب ألوان النصوص في الوضع الداكن (Dark Mode Conflict Resolution)
   ========================================================================== */
/* إجبار خلفية نافذة الودجت في الوضع الداكن على الداكن الصريح */
html.nightMode, html.night_mode,
body.nightMode, body.night_mode,
body.nightMode #zad-root, body.night_mode #zad-root,
body.nightMode #zad-bar, body.night_mode #zad-bar {
  background: #1b1f23 !important;
  background-color: #1b1f23 !important;
  color: #f3f4f6 !important;
}

/* بطاقة السؤال والجواب ومحتواها تكون شفافة فوق خلفية الودجت الداكنة */
body.nightMode #zad-scroll-area, body.night_mode #zad-scroll-area,
body.nightMode #zad-qa, body.night_mode #zad-qa,
body.nightMode .card, body.night_mode .card,
.nightMode .card, .night_mode .card {
  color: #f3f4f6 !important;
  background: transparent !important;
  background-color: transparent !important;
}

/* إجبار عناصر نص السؤال والجواب على اللون الفاتح في الوضع الداكن */
body.nightMode #zad-qa *:not(button):not(.zad-opt):not(.zad-rate *):not(svg *),
body.night_mode #zad-qa *:not(button):not(.zad-opt):not(.zad-rate *):not(svg *) {
  color: inherit;
}

/* إبطال أي ألوان سوداء أو رمادية داكنة مدمجة داخل وسوم HTML في بطاقات المستخدم */
body.nightMode [style*="color: black" i],
body.nightMode [style*="color:black" i],
body.nightMode [style*="color: #000" i],
body.nightMode [style*="color:#000" i],
body.nightMode [style*="color: #1" i],
body.nightMode [style*="color: #2" i],
body.nightMode [style*="color: #3" i],
body.nightMode [style*="color: rgb(0" i],
body.nightMode [style*="color: rgb(1" i],
body.nightMode [style*="color: rgb(2" i],
body.nightMode [style*="color: rgb(3" i],
body.night_mode [style*="color: black" i],
body.night_mode [style*="color:black" i],
body.night_mode [style*="color: #000" i],
body.night_mode [style*="color:#000" i],
body.night_mode [style*="color: #1" i],
body.night_mode [style*="color: #2" i],
body.night_mode [style*="color: #3" i],
body.night_mode [style*="color: rgb(0" i],
body.night_mode [style*="color: rgb(1" i],
body.night_mode [style*="color: rgb(2" i],
body.night_mode [style*="color: rgb(3" i],
body.nightMode font[color*="black" i],
body.nightMode font[color*="#000" i],
body.night_mode font[color*="black" i],
body.night_mode font[color*="#000" i] {
  color: #f3f4f6 !important;
}

/* إزالة الخلفيات البيضاء الصريحة المضمنة حول الكلمات لمنع الرقع البيضاء المشوهة في الوضع الداكن */
body.nightMode [style*="background-color: white" i],
body.nightMode [style*="background-color:white" i],
body.nightMode [style*="background-color: #fff" i],
body.nightMode [style*="background-color:#fff" i],
body.nightMode [style*="background-color: rgb(255" i],
body.nightMode [style*="background: white" i],
body.nightMode [style*="background:white" i],
body.nightMode [style*="background: #fff" i],
body.nightMode [style*="background:#fff" i],
body.nightMode [style*="background: rgb(255" i],
body.night_mode [style*="background-color: white" i],
body.night_mode [style*="background-color:white" i],
body.night_mode [style*="background-color: #fff" i],
body.night_mode [style*="background-color:#fff" i],
body.night_mode [style*="background-color: rgb(255" i],
body.night_mode [style*="background: white" i],
body.night_mode [style*="background:white" i],
body.night_mode [style*="background: #fff" i],
body.night_mode [style*="background:#fff" i],
body.night_mode [style*="background: rgb(255" i] {
  background-color: transparent !important;
  background: transparent !important;
  color: #f3f4f6 !important;
}

/* تمييز نصوص الحفظ المفرغة (Cloze Deletions) في الوضع الليلي */
.cloze {
  color: #2563eb;
  font-weight: bold;
}
body.nightMode .cloze,
body.night_mode .cloze {
  color: #60a5fa !important;
}
"""


def esc(s: str) -> str:
    return _html.escape(s or "", quote=True)


def show_button() -> str:
    return (
        '<button class="zad-show" onclick="pycmd(\'ans\')">إظهار الإجابة'
        ' <span style="opacity:.8">(Space)</span></button>'
    )


def rate_buttons(labels, suggest: int | None = None) -> str:
    out = ['<div class="zad-rate">']
    for i in range(1, 5):
        lab = esc(labels[i - 1]) if i - 1 < len(labels) else ""
        cls = f"r{i}" + (" suggest" if suggest == i else "")
        out.append(
            f'<button class="{cls}" onclick="pycmd(\'ease:{i}\')">'
            f"<small>{lab}</small>{RATE_NAMES[i]} · {i}</button>"
        )
    out.append("</div>")
    return "".join(out)


def quiz_options(options, chosen: int | None = None, correct: int | None = None) -> str:
    letters = ["أ", "ب", "ج", "د"]
    out = ['<div class="zad-opts">']
    for i, text in enumerate(options):
        cls, dis = "zad-opt", ""
        if chosen is not None:
            dis = " disabled"
            if i == correct:
                cls += " correct"
            elif i == chosen:
                cls += " wrong"
        out.append(
            f'<button class="{cls}"{dis} onclick="pycmd(\'quiz:{i}\')">'
            f"{letters[i] if i < 4 else i + 1}) {text}</button>"
        )
    out.append("</div>")
    return "".join(out)


def quiz_feedback(ok: bool, answer: str, evidence: str, source: str) -> str:
    verdict = (
        '<div class="zad-verdict ok">✔ أحسنت، إجابة صحيحة</div>'
        if ok
        else '<div class="zad-verdict no">✘ إجابة غير صحيحة</div>'
    )
    parts = [verdict]
    if answer:
        parts.append(f'<div class="zad-answer">الإجابة: {answer}</div>')
    if evidence:
        parts.append(
            f'<div class="zad-evidence"><b>📖 التأصيل والدليل الشرعي:</b><br>{evidence}</div>'
        )
    if source:
        parts.append(f'<div class="zad-source">{source}</div>')
    return "".join(parts)


def done_screen(message: str, can_next: bool) -> str:
    nxt = (
        '<br><button class="zad-btn2" onclick="pycmd(\'next\')">بطاقة أخرى الآن</button>'
        if can_next
        else ""
    )
    return f'<div class="zad-done">{message}{nxt}</div>'


def render_call(**state) -> str:
    return f"zadRender({json.dumps(state)});"
