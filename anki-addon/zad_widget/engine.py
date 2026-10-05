# -*- coding: utf-8 -*-
"""
زاد العلم — منطق الجدولة على مدار اليوم (بدون أي اعتماد على واجهة Qt).

هذا الملف يستخدم جدولة أنكي الأصلية (V3 / FSRS) كما هي، ولا يعيد تنفيذها:
  * جلب البطاقة التالية من طابور أنكي الحقيقي (يحترم حدود اليوم والخطوات).
  * بناء الإجابة بنفس الدالة التي يستخدمها المراجِع الرسمي.
وإضافةً إلى ذلك يحدد «متى» تظهر البطاقة التالية في الودجت خلال اليوم.
"""
from __future__ import annotations

import datetime as _dt
import random
import re
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

from anki.cards import Card
from anki.collection import Collection
from anki.scheduler_pb2 import CardAnswer, QueuedCards

# ---------------------------------------------------------------------------
# الإعدادات الافتراضية
# ---------------------------------------------------------------------------

DEFAULT_CONFIG: dict[str, Any] = {
    "enabled": True,
    # "interval": فاصل ثابت بالدقائق | "spread": توزيع المستحق على ساعات النشاط
    "mode": "interval",
    "interval_minutes": 20,
    "min_interval_minutes": 3,
    "max_interval_minutes": 120,
    "active_from": "08:00",
    "active_to": "22:00",
    # أقصى عدد بطاقات يعرضها الودجت يوميًا (0 = بلا حد)
    "daily_cap": 0,
    # اسم الرزمة (فارغ = رزمة أنكي الحالية وما تحتها)
    "deck": "",
    # بطاقات التعلّم (الدقائق) تظهر في موعدها حتى لو لم يحن الفاصل
    "learning_priority": True,
    "learning_min_gap_minutes": 1,
    "pause_while_reviewing": True,
    "snooze_minutes": 30,
    "autoplay_audio": True,
    "always_on_top": True,
    "show_on_startup": False,
    "corner": "bottom-right",  # bottom-right | bottom-left | top-right | top-left
    "width": 460,
    "height": 540,
    "font_size": 17,
    "first_run_done": False,
}

QUIZ_NOTETYPE_PREFIX = "زاد – اختبار"
QUIZ_LETTERS = ["أ", "ب", "ج", "د"]

KIND_NEW, KIND_LEARNING, KIND_REVIEW = 0, 1, 2
KIND_LABELS = {KIND_NEW: "جديدة", KIND_LEARNING: "قيد التعلّم", KIND_REVIEW: "مراجعة"}

RATINGS = {
    1: CardAnswer.AGAIN,
    2: CardAnswer.HARD,
    3: CardAnswer.GOOD,
    4: CardAnswer.EASY,
}


def merged_config(user: Optional[dict]) -> dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    if user:
        cfg.update({k: v for k, v in user.items() if k in DEFAULT_CONFIG})
    return cfg


# ---------------------------------------------------------------------------
# الوقت وساعات النشاط
# ---------------------------------------------------------------------------

_HHMM = re.compile(r"^\s*(\d{1,2})\s*:\s*(\d{2})\s*$")


def parse_hhmm(text: str, fallback: int) -> int:
    """يحوّل 'HH:MM' إلى دقائق من منتصف الليل."""
    m = _HHMM.match(text or "")
    if not m:
        return fallback
    h, mi = int(m.group(1)), int(m.group(2))
    if not (0 <= h <= 24 and 0 <= mi < 60):
        return fallback
    return min(h * 60 + mi, 24 * 60)


def active_window(cfg: dict) -> tuple[int, int]:
    return (
        parse_hhmm(cfg.get("active_from", "08:00"), 8 * 60),
        parse_hhmm(cfg.get("active_to", "22:00"), 22 * 60),
    )


def minutes_of(now: _dt.datetime) -> int:
    return now.hour * 60 + now.minute


def is_active(now: _dt.datetime, cfg: dict) -> bool:
    """هل نحن داخل ساعات النشاط؟ (يدعم النافذة الليلية مثل 20:00 → 02:00)."""
    start, end = active_window(cfg)
    cur = minutes_of(now)
    if start == end:
        return True
    if start < end:
        return start <= cur < end
    return cur >= start or cur < end


def minutes_left_in_window(now: _dt.datetime, cfg: dict) -> int:
    start, end = active_window(cfg)
    cur = minutes_of(now)
    if start == end:
        return 24 * 60 - cur
    if start < end:
        return max(end - cur, 0)
    if cur >= start:
        return (24 * 60 - cur) + end
    return max(end - cur, 0)


def next_window_start(now: _dt.datetime, cfg: dict) -> _dt.datetime:
    """أقرب بداية لساعات النشاط بعد الآن."""
    start, _ = active_window(cfg)
    candidate = now.replace(
        hour=(start // 60) % 24, minute=start % 60, second=0, microsecond=0
    )
    if candidate <= now:
        candidate += _dt.timedelta(days=1)
    return candidate


def next_interval_seconds(
    cfg: dict, now: _dt.datetime, remaining_cards: int, remaining_cap: Optional[int]
) -> int:
    """الفاصل حتى البطاقة التالية.

    - interval: فاصل ثابت.
    - spread: يقسم الوقت المتبقي من ساعات النشاط على عدد البطاقات المتبقية
      فتتوزع المراجعة بالتساوي على اليوم كله بدل أن تتكدس.
    """
    lo = max(int(cfg.get("min_interval_minutes", 3)), 1) * 60
    hi = max(int(cfg.get("max_interval_minutes", 120)), 1) * 60
    if hi < lo:
        hi = lo
    if cfg.get("mode") == "spread":
        n = max(remaining_cards, 1)
        if remaining_cap is not None:
            n = max(min(n, remaining_cap), 1)
        secs = int(minutes_left_in_window(now, cfg) * 60 / n)
        return max(lo, min(hi, secs))
    return max(int(cfg.get("interval_minutes", 20)), 1) * 60


# ---------------------------------------------------------------------------
# عدّاد اليوم
# ---------------------------------------------------------------------------


@dataclass
class DayCounter:
    """يحصي ما عرضه الودجت اليوم، ويتصفر مع بداية يوم جديد."""

    date: str = ""
    shown: int = 0
    answered: int = 0

    @classmethod
    def load(cls, raw: Optional[dict], today: _dt.date) -> "DayCounter":
        d = today.isoformat()
        if raw and raw.get("date") == d:
            return cls(d, int(raw.get("shown", 0)), int(raw.get("answered", 0)))
        return cls(d, 0, 0)

    def roll(self, today: _dt.date) -> None:
        d = today.isoformat()
        if self.date != d:
            self.date, self.shown, self.answered = d, 0, 0

    def to_dict(self) -> dict:
        return {"date": self.date, "shown": self.shown, "answered": self.answered}

    def remaining(self, cfg: dict) -> Optional[int]:
        cap = int(cfg.get("daily_cap", 0) or 0)
        if cap <= 0:
            return None
        return max(cap - self.shown, 0)


# ---------------------------------------------------------------------------
# جلب البطاقة من طابور أنكي
# ---------------------------------------------------------------------------


@dataclass
class Fetched:
    card: Card
    queued: Any  # anki.scheduler_pb2.QueuedCards.QueuedCard
    kind: int
    labels: Sequence[str]
    new_count: int
    learning_count: int
    review_count: int

    @property
    def total_due(self) -> int:
        return self.new_count + self.learning_count + self.review_count


def resolve_deck_id(col: Collection, name: str) -> Optional[int]:
    name = (name or "").strip()
    if not name:
        return None
    did = col.decks.id_for_name(name)
    return int(did) if did else None


def top_level_decks(col: Collection) -> list[int]:
    """الرزم العليا (تشمل فروعها) — بدون المصفّاة ولا Default الفارغة."""
    out = []
    for d in col.decks.all_names_and_ids(
        skip_empty_default=True, include_filtered=False
    ):
        if "::" not in d.name:
            out.append(int(d.id))
    return out


def _queue_for(col: Collection, did: int) -> QueuedCards:
    col.decks.select(did)  # type: ignore[arg-type]
    return col.sched.get_queued_cards(fetch_limit=1)


def _due_total(q: QueuedCards) -> int:
    return q.new_count + q.learning_count + q.review_count


def counts(col: Collection, deck_name: str = "") -> tuple[int, int, int]:
    """مجموع (جديدة، تعلّم، مراجعة) في نطاق الودجت."""
    prev = col.decks.get_current_id()
    try:
        scope = _scope_decks(col, deck_name)
        n = l = r = 0
        for did in scope:
            q = _queue_for(col, did)
            n, l, r = n + q.new_count, l + q.learning_count, r + q.review_count
        return n, l, r
    finally:
        col.decks.select(prev)


def _scope_decks(col: Collection, deck_name: str) -> list[int]:
    did = resolve_deck_id(col, deck_name)
    if did is not None:
        return [did]
    return top_level_decks(col)


def fetch_next(
    col: Collection, deck_name: str = "", rng: Optional[random.Random] = None
) -> Optional[Fetched]:
    """البطاقة التالية بحسب طابور أنكي الأصلي (أو None إن انتهى المستحق).

    طابور أنكي يعمل على «الرزمة الحالية» فقط، لذا نمرّ على رزم النطاق ونختار
    بطاقة من إحداها باحتمال يتناسب مع عدد المستحق فيها (فتتنوّع العلوم)،
    ثم نُعيد تحديد الرزمة الحالية للمستخدم كما كانت.
    """
    rng = rng or random
    prev = col.decks.get_current_id()
    try:
        queues: list[tuple[int, QueuedCards]] = []
        for did in _scope_decks(col, deck_name):
            q = _queue_for(col, did)
            if q.cards:
                queues.append((did, q))
        if not queues:
            return None
        n = sum(q.new_count for _, q in queues)
        lrn = sum(q.learning_count for _, q in queues)
        rev = sum(q.review_count for _, q in queues)

        # بطاقات التعلّم المستحقة لها الأولوية دائمًا (مثل أنكي)
        learning = [(d, q) for d, q in queues if int(q.cards[0].queue) == KIND_LEARNING]
        pool = learning or queues
        did, q = rng.choices(pool, weights=[max(_due_total(x), 1) for _, x in pool])[0]
        # نعيد بناء الطابور لهذه الرزمة حتى تكون الحالة متسقة عند الإجابة
        q = _queue_for(col, did)
        entry = q.cards[0]
        card = Card(col, backend_card=entry.card)
        card.start_timer()
        return Fetched(
            card=card,
            queued=entry,
            kind=int(entry.queue),
            labels=list(col.sched.describe_next_states(entry.states)),
            new_count=n,
            learning_count=lrn,
            review_count=rev,
        )
    finally:
        col.decks.select(prev)


def build_answer(col: Collection, fetched: Fetched, rating: int) -> CardAnswer:
    """يبني الإجابة بالدالة الرسمية (1=أعد، 2=صعب، 3=جيد، 4=سهل)."""
    if rating not in RATINGS:
        raise ValueError(f"تقييم غير صالح: {rating}")
    return col.sched.build_answer(
        card=fetched.card, states=fetched.queued.states, rating=RATINGS[rating]
    )


def should_bypass_interval(
    fetched: Optional[Fetched], cfg: dict, secs_since_last_shown: float
) -> bool:
    """بطاقة التعلّم المستحقة الآن تتجاوز الفاصل (مثل خطوة 10 دقائق بعد «أعد»)."""
    if not fetched or not cfg.get("learning_priority", True):
        return False
    if fetched.kind != KIND_LEARNING:
        return False
    return secs_since_last_shown >= float(cfg.get("learning_min_gap_minutes", 1)) * 60


# ---------------------------------------------------------------------------
# بطاقات الاختبار المؤصَّل (نوع الملاحظة «زاد – اختبار»)
# ---------------------------------------------------------------------------


@dataclass
class Quiz:
    question: str
    options: list[str]
    correct: int  # فهرس يبدأ من 0
    answer: str = ""
    evidence: str = ""
    source: str = ""


def parse_quiz(col: Collection, card: Card) -> Optional[Quiz]:
    """إن كانت البطاقة من نوع «زاد – اختبار» يرجع بنيتها التفاعلية."""
    note = card.note()
    nt = note.note_type()
    if not nt or not str(nt.get("name", "")).startswith(QUIZ_NOTETYPE_PREFIX):
        return None
    try:
        opts = [note[k] for k in ("A", "B", "C", "D") if k in note and note[k].strip()]
        correct = int(re.sub(r"\D", "", note["Correct"]) or "0") - 1
    except KeyError:
        return None
    if len(opts) < 2 or not (0 <= correct < len(opts)):
        return None
    return Quiz(
        question=note["Question"],
        options=opts,
        correct=correct,
        answer=note["Answer"] if "Answer" in note else "",
        evidence=note["Evidence"] if "Evidence" in note else "",
        source=note["Source"] if "Source" in note else "",
    )


def suggested_rating(is_correct: bool) -> int:
    """اقتراح التقييم بعد الاختبار: صحيح → جيد، خطأ → أعد."""
    return 3 if is_correct else 1
