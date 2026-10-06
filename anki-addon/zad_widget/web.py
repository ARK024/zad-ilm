# -*- coding: utf-8 -*-
"""قوالب HTML/CSS الخاصة بنافذة الودجت (تُعرض داخل AnkiWebView)."""
from __future__ import annotations

import html as _html
import json

RATE_NAMES = {1: "أعد", 2: "صعب", 3: "جيد", 4: "سهل"}

BODY = """
<div id="zad-root">
  <div id="zad-qa" class="card"></div>
  <div id="zad-opts"></div>
  <div id="zad-extra"></div>
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
  }
  if (s.fs) {
    document.documentElement.style.setProperty("--zad-fs", s.fs + "px");
  }
  var qa = document.getElementById("zad-qa");
  if (s.qa !== undefined && s.qa !== null) { $(qa).html(s.qa); }
  if (s.opts !== undefined && s.opts !== null) { document.getElementById("zad-opts").innerHTML = s.opts; }
  if (s.extra !== undefined && s.extra !== null) { document.getElementById("zad-extra").innerHTML = s.extra; }
  if (s.bar !== undefined && s.bar !== null) { document.getElementById("zad-bar").innerHTML = s.bar; }
  if (s.scroll) {
    var a = document.getElementById("answer") || document.getElementById("zad-extra");
    if (a && a.scrollIntoView) { a.scrollIntoView(); }
  } else if (s.scroll === false) { window.scrollTo(0, 0); }
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
:root { --zad-fs: 17px; --zad-gold: #b8860b; --zad-green: #166534; --zad-red: #b91c1c;
        --zad-bg: #fffdf7; --zad-fg: #1f2937; --zad-border: #d9cfae; --zad-soft: #f4ecd2; }
body.nightMode, body.night_mode { --zad-bg: #1b1f23; --zad-fg: #e5e7eb; --zad-border: #3b4350; --zad-soft: #262c33; }
html, body { margin: 0; padding: 0; background: var(--zad-bg) !important; color: var(--zad-fg); direction: rtl; }
body { font-size: var(--zad-fs); }
#zad-root { padding: 10px 14px 6px; }
#zad-qa { padding: 4px 2px; text-align: right; line-height: 1.9; min-height: 40px;
          background: transparent !important; margin: 0 !important; }
#zad-qa, #zad-qa.card, #zad-qa .card { font-size: var(--zad-fs) !important; }
#zad-qa img { max-width: 100%; height: auto; }
#zad-extra:empty, #zad-opts:empty { display: none; }
.zad-opts { display: flex; flex-direction: column; gap: 8px; margin: 10px 0; }
.zad-opt { text-align: right; font: inherit; font-size: .95em; padding: 8px 12px; cursor: pointer;
           border: 1px solid var(--zad-border); border-radius: 10px; background: var(--zad-soft); color: inherit; }
.zad-opt:hover:not(:disabled) { border-color: var(--zad-gold); }
.zad-opt.correct { background: #dcfce7; border-color: #16a34a; color: #14532d; font-weight: bold; }
.zad-opt.wrong { background: #fee2e2; border-color: #dc2626; color: #7f1d1d; }
.nightMode .zad-opt.correct { background: #14532d; color: #dcfce7; }
.nightMode .zad-opt.wrong { background: #7f1d1d; color: #fee2e2; }
.zad-opt:disabled { cursor: default; opacity: 1; }
.zad-evidence { margin: 10px 0; padding: 10px 14px; border-right: 4px solid var(--zad-gold);
                background: rgba(184,134,11,.10); border-radius: 8px; font-size: .92em; line-height: 1.9; }
.zad-answer { color: var(--zad-green); font-weight: bold; margin-top: 8px; }
.nightMode .zad-answer { color: #86efac; }
.zad-source { color: #6b7280; font-size: .8em; margin-top: 6px; }
.zad-verdict { font-weight: bold; margin: 6px 0; }
.zad-verdict.ok { color: var(--zad-green); } .zad-verdict.no { color: var(--zad-red); }
#zad-bar { position: sticky; bottom: 0; background: var(--zad-bg); padding: 8px 0 4px;
           border-top: 1px solid var(--zad-border); margin-top: 10px; }
.zad-show { width: 100%; padding: 10px; font: inherit; font-weight: bold; cursor: pointer; color: #fff;
            background: var(--zad-gold); border: 0; border-radius: 10px; }
.zad-rate { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; }
.zad-rate button { font: inherit; font-size: .9em; padding: 6px 2px; cursor: pointer; border-radius: 10px;
                   border: 2px solid transparent; color: #fff; display: flex; flex-direction: column;
                   align-items: center; line-height: 1.4; }
.zad-rate small { font-size: .72em; opacity: .9; direction: ltr; }
.zad-rate .r1 { background: #dc2626; } .zad-rate .r2 { background: #d97706; }
.zad-rate .r3 { background: #16a34a; } .zad-rate .r4 { background: #2563eb; }
.zad-rate button.suggest { border-color: var(--zad-fg); box-shadow: 0 0 0 2px var(--zad-gold); }
.zad-hint { text-align: center; color: #6b7280; font-size: .75em; margin-top: 4px; }
.zad-done { text-align: center; padding: 28px 8px; line-height: 2; }
.zad-done b { color: var(--zad-green); font-size: 1.15em; }
.zad-btn2 { margin-top: 10px; font: inherit; padding: 8px 18px; cursor: pointer; border-radius: 10px;
            border: 1px solid var(--zad-gold); background: transparent; color: inherit; }
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
