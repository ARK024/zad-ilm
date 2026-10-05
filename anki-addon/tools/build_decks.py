#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يبني رزمة «العلوم الشرعية» (.apkg) من data/islamic_sciences_cards.json

الاستخدام:
    python anki-addon/tools/build_decks.py

الناتج: anki-addon/zad_widget/decks/zad_islamic_sciences.apkg
وهي رزمة أنكي عادية (تُستورد في أنكي بالطريقة المعتادة) فيها نوعان من الملاحظات:
  «زاد – بطاقة مؤصلة»  : سؤال/جواب + حقل «التأصيل والدليل»
  «زاد – اختبار مؤصل»   : اختيار من متعدد + تصحيح + التأصيل (يتفاعل معه الودجت)
"""
import hashlib
import html
import json
import shutil
import sys
from pathlib import Path

import genanki

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "islamic_sciences_cards.json"
OUT_DIR = ROOT / "anki-addon" / "zad_widget" / "decks"

ROOT_DECK = "زاد العلم"

CSS = """
.card {
  font-family: "Amiri", "Scheherazade New", "Traditional Arabic", "Noto Naskh Arabic", Arial, sans-serif;
  font-size: 22px; line-height: 1.9; direction: rtl; text-align: right;
  color: #1f2937; background: #fffdf7; padding: 12px;
}
.nightMode.card, .night_mode.card { color: #e5e7eb; background: #1b1f23; }
.zq { font-weight: bold; font-size: 1.1em; margin-bottom: 10px; }
.zopts { list-style: none; padding: 0; margin: 8px 0; }
.zopts li { border: 1px solid #d6c9a8; border-radius: 10px; padding: 6px 12px; margin: 6px 0; }
.za { color: #14532d; font-weight: bold; }
.nightMode .za { color: #86efac; }
.ze { margin-top: 12px; padding: 10px 14px; border-right: 4px solid #b8860b;
      background: rgba(184,134,11,.10); border-radius: 8px; font-size: .92em; }
.zs { margin-top: 8px; color: #6b7280; font-size: .8em; }
hr#answer { border: 0; border-top: 1px dashed #b8860b; margin: 14px 0; }
"""

FLASH_MODEL_ID = 1760000001
QUIZ_MODEL_ID = 1760000002


def stable_id(text: str) -> int:
    return int(hashlib.sha1(text.encode("utf-8")).hexdigest()[:8], 16) + 1_760_100_000


FLASH_MODEL = genanki.Model(
    FLASH_MODEL_ID,
    "زاد – بطاقة مؤصلة",
    fields=[{"name": "Front"}, {"name": "Back"}, {"name": "Evidence"}, {"name": "Source"}],
    templates=[
        {
            "name": "سؤال ← جواب",
            "qfmt": '<div class="zq">{{Front}}</div>',
            "afmt": (
                "{{FrontSide}}<hr id=answer>"
                '<div class="za">{{Back}}</div>'
                "{{#Evidence}}"
                '<div class="ze"><b>📖 التأصيل والدليل الشرعي:</b><br>{{Evidence}}</div>'
                "{{/Evidence}}"
                '{{#Source}}<div class="zs">{{Source}}</div>{{/Source}}'
            ),
        }
    ],
    css=CSS,
)

QUIZ_MODEL = genanki.Model(
    QUIZ_MODEL_ID,
    "زاد – اختبار مؤصل",
    fields=[
        {"name": "Question"},
        {"name": "A"},
        {"name": "B"},
        {"name": "C"},
        {"name": "D"},
        {"name": "Correct"},
        {"name": "Answer"},
        {"name": "Evidence"},
        {"name": "Source"},
    ],
    templates=[
        {
            "name": "اختيار من متعدد",
            "qfmt": (
                '<div class="zq">{{Question}}</div>'
                '<ul class="zopts">'
                "<li>أ) {{A}}</li><li>ب) {{B}}</li>"
                "{{#C}}<li>ج) {{C}}</li>{{/C}}{{#D}}<li>د) {{D}}</li>{{/D}}"
                "</ul>"
            ),
            "afmt": (
                "{{FrontSide}}<hr id=answer>"
                '<div class="za">✔ الإجابة الصحيحة: {{Answer}}</div>'
                "{{#Evidence}}"
                '<div class="ze"><b>📖 التأصيل والدليل الشرعي:</b><br>{{Evidence}}</div>'
                "{{/Evidence}}"
                '{{#Source}}<div class="zs">{{Source}}</div>{{/Source}}'
            ),
        }
    ],
    css=CSS,
)


def h(text: str) -> str:
    return html.escape(text or "", quote=False).replace("\n", "<br>")


def build(cards: list[dict]) -> genanki.Package:
    decks: dict[str, genanki.Deck] = {}

    def deck_for(category: str) -> genanki.Deck:
        name = f"{ROOT_DECK}::{category}"
        if name not in decks:
            decks[name] = genanki.Deck(stable_id(name), name)
        return decks[name]

    for c in cards:
        deck = deck_for(c["category"])
        tags = [
            c["category"].replace(" ", "_"),
            c.get("topic", "").replace(" ", "_"),
            c.get("difficulty", "").replace(" ", "_"),
        ]
        tags = [t for t in tags if t]
        source = f"{c['category']} — {c.get('topic', '')}".strip(" —")
        guid = genanki.guid_for("zad-ilm", c["id"])

        if c["type"] == "quiz" and len(c.get("options", [])) >= 2:
            opts = list(c["options"]) + [""] * (4 - len(c["options"]))
            note = genanki.Note(
                model=QUIZ_MODEL,
                fields=[
                    h(c["question"]),
                    h(opts[0]), h(opts[1]), h(opts[2]), h(opts[3]),
                    str(int(c["correct_index"]) + 1),
                    h(c.get("answer", "")),
                    h(c.get("explanation", "")),
                    h(source),
                ],
                tags=tags,
                guid=guid,
            )
        else:
            note = genanki.Note(
                model=FLASH_MODEL,
                fields=[
                    h(c["question"]),
                    h(c.get("answer", "")),
                    h(c.get("explanation", "")),
                    h(source),
                ],
                tags=tags,
                guid=guid,
            )
        deck.add_note(note)

    return genanki.Package(list(decks.values()))


CLOZE_MODEL_ID = 1760000003

CLOZE_MODEL = genanki.Model(
    CLOZE_MODEL_ID,
    "زاد – حفظ المتون (Cloze)",
    model_type=genanki.Model.CLOZE,
    fields=[{"name": "Text"}, {"name": "Extra"}],
    templates=[
        {
            "name": "Cloze",
            "qfmt": '<div class="zq">{{cloze:Text}}</div>',
            "afmt": (
                '<div class="zq">{{cloze:Text}}</div><hr id=answer>'
                '{{#Extra}}<div class="ze">{{Extra}}</div>{{/Extra}}'
            ),
        }
    ],
    css=CSS
    + ".cloze { color: #0f766e; font-weight: bold; }"
    + ".nightMode .cloze { color: #5eead4; }",
)

# متون الأربعين النووية (ملء الفراغات)
HADITHS = [
    (
        "عن عمر بن الخطاب رضي الله عنه قال: سمعت رسول الله ﷺ يقول: {{c1::إنما الأعمال بالنيات}}، وإنما لكل امرئ {{c2::ما نوى}}، فمن كانت هجرته إلى الله ورسوله فهجرته إلى {{c3::الله ورسوله}}، ومن كانت هجرته لدنيا يصيبها أو امرأة ينكحها فهجرته إلى ما هاجر إليه.",
        "رواه البخاري ومسلم. الحديث الأول من الأربعين النووية، وهو أصل عظيم من أصول الإسلام وقاعدة تدور عليها الأعمال.",
    ),
    (
        "عن عبد الله بن عمر رضي الله عنهما قال: قال رسول الله ﷺ: {{c1::بُني الإسلام على خمس}}: شهادة أن لا إله إلا الله وأن محمداً رسول الله، و{{c2::إقام الصلاة}}، وإيتاء الزكاة، و{{c3::حج البيت}}، وصوم رمضان.",
        "رواه البخاري ومسلم. الحديث الثالث من الأربعين النووية، يبين دعائم الإسلام وأركانه العظام.",
    ),
    (
        "عن أبي هريرة رضي الله عنه أن رجلاً قال للنبي ﷺ: أوصني، قال: {{c1::لا تغضب}}، فردد مراراً، قال: {{c1::لا تغضب}}.",
        "رواه البخاري. الحديث السادس عشر من الأربعين النووية، وصية جامعة في كظم الغيظ وملك النفس عند الغضب.",
    ),
    (
        "عن أبي هريرة رضي الله عنه قال: قال رسول الله ﷺ: {{c1::من حسن إسلام المرء}} {{c2::تركه ما لا يعنيه}}.",
        "حديث حسن رواه الترمذي وغيره. الحديث الثاني عشر من الأربعين النووية، قاعدة عظيمة في تهذيب الأخلاق.",
    ),
]


def build_cloze() -> genanki.Package:
    name = f"{ROOT_DECK}::الأربعين النووية (حفظ المتون)"
    deck = genanki.Deck(stable_id(name), name)
    for i, (text, extra) in enumerate(HADITHS):
        deck.add_note(
            genanki.Note(
                model=CLOZE_MODEL,
                fields=[text, extra],
                tags=["الأربعين_النووية", "حديث"],
                guid=genanki.guid_for("zad-ilm-hadith", i),
            )
        )
    return genanki.Package([deck])


def main() -> int:
    cards = json.loads(DATA.read_text(encoding="utf-8"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "zad_islamic_sciences.apkg"
    build(cards).write_to_file(str(out))
    print(f"✔ {len(cards)} بطاقة → {out}")

    out2 = OUT_DIR / "zad_hadith_cloze.apkg"
    build_cloze().write_to_file(str(out2))
    print(f"✔ {len(HADITHS)} متون (Cloze) → {out2}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
