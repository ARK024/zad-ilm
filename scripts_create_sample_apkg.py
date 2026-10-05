# -*- coding: utf-8 -*-
import sqlite3
import json
import zipfile
import time
import os

db_path = "/tmp/sample_collection.anki2"
if os.path.exists(db_path):
    os.remove(db_path)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Create Anki tables
cur.execute("""
CREATE TABLE col (
    id integer primary key,
    crt integer not null,
    mod integer not null,
    scm integer not null,
    ver integer not null,
    dty integer not null,
    usn integer not null,
    ls integer not null,
    conf text not null,
    models text not null,
    decks text not null,
    dconf text not null,
    tags text not null
);
""")

cur.execute("""
CREATE TABLE notes (
    id integer primary key,
    guid text not null,
    mid integer not null,
    mod integer not null,
    usn integer not null,
    tags text not null,
    flds text not null,
    sfld text not null,
    csum integer not null,
    flags integer not null,
    data text not null
);
""")

cur.execute("""
CREATE TABLE cards (
    id integer primary key,
    nid integer not null,
    did integer not null,
    ord integer not null,
    mod integer not null,
    usn integer not null,
    type integer not null,
    queue integer not null,
    due integer not null,
    ivl integer not null,
    factor integer not null,
    reps integer not null,
    lapses integer not null,
    left integer not null,
    odue integer not null,
    odid integer not null,
    flags integer not null,
    data text not null
);
""")

deck_id = 1700123456789
deck_name = "الأربعين النووية (حفظ وإخفاء كلمات)"
decks_json = {
    str(deck_id): {
        "id": deck_id,
        "name": deck_name,
        "desc": "رزمة الأربعين النووية مجهزة بنظام ملء الفراغات وحفظ المتون الشرعية"
    }
}

model_id = 1700987654321
models_json = {
    str(model_id): {
        "id": model_id,
        "name": "Cloze (حفظ المتون الشرعية)",
        "type": 1, # Cloze model
        "flds": [
            {"name": "Text", "ord": 0},
            {"name": "Extra", "ord": 1}
        ],
        "tmpls": [
            {
                "name": "Cloze 1",
                "ord": 0,
                "qfmt": "<div class='hadith-matn'>{{cloze:Text}}</div>",
                "afmt": "<div class='hadith-matn'>{{cloze:Text}}</div><hr id='answer'><div class='hadith-extra'>{{Extra}}</div>"
            }
        ],
        "css": ".card { font-family: 'Amiri', serif; font-size: 22px; text-align: right; direction: rtl; } .cloze { color: #34d399; font-weight: bold; background: rgba(52,211,153,0.15); padding: 2px 6px; border-radius: 4px; }"
    }
}

now = int(time.time())
cur.execute("INSERT INTO col VALUES (1, ?, ?, ?, 11, 0, 0, 0, '{}', ?, ?, '{}', '{}')",
            (now, now, now, json.dumps(models_json), json.dumps(decks_json)))

hadiths = [
    (
        "عن عمر بن الخطاب رضي الله عنه قال: سمعت رسول الله ﷺ يقول: {{c1::إنما الأعمال بالنيات}}، وإنما لكل امرئ {{c2::ما نوى}}، فمن كانت هجرته إلى الله ورسوله فهجرته إلى {{c3::الله ورسوله}}، ومن كانت هجرته لدنيا يصيبها أو امرأة ينكحها فهجرته إلى ما هاجر إليه.",
        "رواه البخاري ومسلم. الحديث الأول من الأربعين النووية، وهو أصل عظيم من أصول الإسلام وقاعدة تدور عليها الأعمال."
    ),
    (
        "عن عبد الله بن عمر رضي الله عنهما قال: قال رسول الله ﷺ: {{c1::بُني الإسلام على خمس}}: شهادة أن لا إله إلا الله وأن محمداً رسول الله، و{{c2::إقام الصلاة}}، وإيتاء الزكاة، و{{c3::حج البيت}}، وصوم رمضان.",
        "رواه البخاري ومسلم. الحديث الثالث من الأربعين النووية، يبين دعائم الإسلام وأركانه العظام."
    ),
    (
        "عن أبي هريرة رضي الله عنه أن رجلاً قال للنبي ﷺ: أوصني، قال: {{c1::لا تغضب}}، فردد مراراً، قال: {{c1::لا تغضب}}.",
        "رواه البخاري. الحديث السادس عشر من الأربعين النووية، وصية جامعة من جوامع كلمه ﷺ في كظم الغيظ وملك النفس عند الغضب."
    ),
    (
        "عن أبي هريرة رضي الله عنه قال: قال رسول الله ﷺ: {{c1::من حسن إسلام المرء}} {{c2::تركه ما لا يعنيه}}.",
        "حديث حسن رواه الترمذي وغيره. الحديث الثاني عشر من الأربعين النووية، قاعدة عظيمة في تهذيب الأخلاق والاشتغال بما ينفع."
    )
]

card_id_counter = 1000
for i, (matn, extra) in enumerate(hadiths):
    note_id = 2000 + i
    flds_str = f"{matn}\x1f{extra}"
    cur.execute("INSERT INTO notes VALUES (?, ?, ?, ?, 0, '', ?, ?, 0, 0, '')",
                (note_id, f"guid-{i}", model_id, now, flds_str, matn[:20]))

    # Generate cloze cards (each cloze index c1, c2, etc.)
    # In note 0: c1, c2, c3 -> 3 cards (ord 0, 1, 2)
    # In note 1: c1, c2, c3 -> 3 cards
    # In note 2: c1 -> 1 card
    # In note 3: c1, c2 -> 2 cards
    import re
    cloze_indices = set(int(m) for m in re.findall(r"\{\{c(\d+)::", matn))
    for c_idx in sorted(cloze_indices):
        card_id_counter += 1
        ord_idx = c_idx - 1
        cur.execute("INSERT INTO cards VALUES (?, ?, ?, ?, ?, 0, 0, 0, ?, 0, 2500, 0, 0, 0, 0, 0, 0, '')",
                    (card_id_counter, note_id, deck_id, ord_idx, now, now))

conn.commit()
conn.close()

# Package into .apkg ZIP
output_apkg = "/teamspace/studios/this_studio/zad-ilm/data/sample_hadith_cloze.apkg"
with zipfile.ZipFile(output_apkg, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.write(db_path, "collection.anki2")
    zf.writestr("media", json.dumps({}))

print(f"Generated sample Anki package with cloze deletion: {output_apkg} ({os.path.getsize(output_apkg)} bytes)")
