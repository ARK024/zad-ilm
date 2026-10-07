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
    # قائمة بأسماء الرزم المختارة للدراسة في الودجت (فارغ = كل الرزم)
    "decks": [],
    # اسم الرزمة (للتوافق القديم)
    "deck": "",
    # طريقة ترتيب دراسة الرزم: "deck_by_deck" (رزمة تلو الأخرى) | "mix" (تنويع متوازن) | "anki" (ترتيب أنكي الأصلي)
    "order_mode": "deck_by_deck",
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
    "close_to_tray": True,
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
        # التوافق بين decks و deck
        if "decks" in user and isinstance(user["decks"], list):
            cfg["decks"] = [str(d) for d in user["decks"] if str(d).strip()]
        elif "deck" in user and user["deck"]:
            cfg["decks"] = [str(user["deck"])]
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


def resolve_deck_ids(col: Collection, deck_spec: Any = None) -> list[int]:
    """تحويل اسم رزمة أو قائمة رزم إلى معرّفات رزم صالحة ومحددة بترتيب المستخدم."""
    if deck_spec is None:
        return []
    if isinstance(deck_spec, str):
        deck_spec = [deck_spec] if deck_spec.strip() else []
    elif not isinstance(deck_spec, (list, tuple, set)):
        return []
    ids: list[int] = []
    for item in deck_spec:
        did = resolve_deck_id(col, str(item))
        if did is not None and did not in ids:
            ids.append(did)
    return ids


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


def counts(col: Collection, deck_spec: Any = "") -> tuple[int, int, int]:
    """مجموع (جديدة، تعلّم، مراجعة) في نطاق الرزم المحددة دون تغيير الرزمة الحالية."""
    dids = resolve_deck_ids(col, deck_spec)
    if not dids:
        tree = col.sched.deck_due_tree()
        if not tree:
            return 0, 0, 0
        return int(tree.new_count), int(tree.learn_count), int(tree.review_count)

    n = l = r = 0
    for did in dids:
        tree = col.sched.deck_due_tree(did)
        if tree:
            n += int(tree.new_count)
            l += int(tree.learn_count)
            r += int(tree.review_count)
    return n, l, r


def _scope_decks(col: Collection, deck_name: str) -> list[int]:
    did = resolve_deck_id(col, deck_name)
    if did is not None:
        return [did]
    return top_level_decks(col)


def tree_order_index_map(col: Collection) -> dict[int, int]:
    """خريطة تعطي ترتيب كل رزمة في شجرة أنكي الأصلية من الأعلى للأسفل (0, 1, 2...)."""
    tree = col.sched.deck_due_tree()
    if not tree:
        return {}
    order_map: dict[int, int] = {}
    idx = 0

    def walk(node):
        nonlocal idx
        if node.deck_id != 0:
            order_map[node.deck_id] = idx
            idx += 1
        for child in node.children:
            walk(child)

    walk(tree)
    return order_map


def expand_deck_candidates(
    col: Collection, did: int
) -> list[tuple[int, int, int, int, int]]:
    """استخراج الرزم القابلة للدراسة: تفكيك الرزمة إلى فروعها بترتيب الشجرة إن كانت تضم فروعًا."""
    tree = col.sched.deck_due_tree(did)
    if not tree:
        return []
    if not tree.children:
        n, l, r = int(tree.new_count), int(tree.learn_count), int(tree.review_count)
        intra = int(getattr(tree, "intraday_learning", 0))
        return [(did, n, l, r, intra)] if (n + l + r) > 0 else []

    candidates: list[tuple[int, int, int, int, int]] = []
    seen: set[int] = set()

    def walk(node):
        if not node.children:
            n = int(getattr(node, "new_count", 0))
            l = int(getattr(node, "learn_count", 0))
            r = int(getattr(node, "review_count", 0))
            intra = int(getattr(node, "intraday_learning", 0))
            if (n + l + r) > 0 and node.deck_id not in seen:
                seen.add(node.deck_id)
                candidates.append((node.deck_id, n, l, r, intra))
        else:
            if getattr(node, "total_in_deck", 0) > 0 and node.deck_id not in seen:
                n = int(getattr(node, "new_count", 0))
                l = int(getattr(node, "learn_count", 0))
                r = int(getattr(node, "review_count", 0))
                intra = int(getattr(node, "intraday_learning", 0))
                if (n + l + r) > 0:
                    seen.add(node.deck_id)
                    candidates.append((node.deck_id, n, l, r, intra))
            for child in node.children:
                walk(child)

    walk(tree)
    return candidates


def fetch_next(
    col: Collection,
    deck_spec: Any = "",
    order_mode: str = "deck_by_deck",
    rng: Optional[random.Random] = None,
) -> Optional[Fetched]:
    """البطاقة التالية بحسب طابور أنكي الأصلي (أو None إن انتهى المستحق).

    يدعم اختيار رزمة واحدة أو عدة رزم وترتيب الدراسة:
    - deck_by_deck: إنهاء الرزم بالتتابع حسب ترتيب القائمة (إنهاء الأولى ثم التالية)
    - mix: تنويع متوازن بين الرزم بنسبة المستحق (خلط ذكي ينشّط الذهن)
    - anki: ترتيب أنكي الافتراضي (شجرة أنكي الأصلية من أول فرع لآخره)
    """
    if isinstance(order_mode, random.Random):
        rng = order_mode
        order_mode = "mix"
    rng = rng or random
    dids = resolve_deck_ids(col, deck_spec)

    candidates: list[tuple[int, int, int, int, int]] = []
    if dids:
        for did in dids:
            for cand in expand_deck_candidates(col, did):
                if cand[0] not in [c[0] for c in candidates]:
                    candidates.append(cand)
    else:
        tree = col.sched.deck_due_tree()
        if tree and (tree.new_count + tree.learn_count + tree.review_count > 0):
            candidates = [
                (
                    int(c.deck_id),
                    int(c.new_count),
                    int(c.learn_count),
                    int(c.review_count),
                    int(getattr(c, "intraday_learning", 0)),
                )
                for c in tree.children
                if (c.new_count + c.learn_count + c.review_count) > 0
            ]
            if not candidates:
                candidates = [
                    (
                        int(col.decks.get_current_id()),
                        int(tree.new_count),
                        int(tree.learn_count),
                        int(tree.review_count),
                        int(getattr(tree, "intraday_learning", 0)),
                    )
                ]

    if not candidates:
        return None

    total_n = sum(n for _, n, _, _, _ in candidates)
    total_lrn = sum(l for _, _, l, _, _ in candidates)
    total_rev = sum(r for _, _, _, r, _ in candidates)

    order_pool: list[int] = []
    if order_mode == "mix":
        # في نمط التنويع: بطاقات التعلّم المستحقة الآن لها الأسبقية بالقرعة الموزونة
        learning_pool = [c for c in candidates if c[4] > 0]
        if learning_pool:
            chosen = rng.choices(
                learning_pool, weights=[max(c[1] + c[2] + c[3], 1) for c in learning_pool]
            )[0][0]
        else:
            chosen = rng.choices(
                candidates, weights=[max(n + l + r, 1) for _, n, l, r, _ in candidates]
            )[0][0]
        order_pool = [chosen] + [c[0] for c in candidates if c[0] != chosen]
    elif order_mode == "anki":
        # في نمط ترتيب أنكي: إعادة ترتيب الرزم بدقة تامة طبقًا لموقعها في شجرة أنكي الأصلية (من أول فرع لآخره)
        tree_map = tree_order_index_map(col)
        sorted_candidates = sorted(candidates, key=lambda c: tree_map.get(c[0], 999999))
        order_pool = [c[0] for c in sorted_candidates]
    else:
        # deck_by_deck: يلتزم بترتيب القائمة المحددة من قِبل المستخدم
        order_pool = [c[0] for c in candidates]

    prev = int(col.decks.get_current_id())
    undo_before = col.undo_status()
    try:
        for chosen_id in order_pool:
            if prev != chosen_id:
                col.decks.select(chosen_id)
            q = col.sched.get_queued_cards(fetch_limit=1)
            if q.cards:
                entry = q.cards[0]
                card = Card(col, backend_card=entry.card)
                card.start_timer()
                return Fetched(
                    card=card,
                    queued=entry,
                    kind=int(entry.queue),
                    labels=list(col.sched.describe_next_states(entry.states)),
                    new_count=total_n,
                    learning_count=total_lrn,
                    review_count=total_rev,
                )
        return None
    finally:
        current_after = int(col.decks.get_current_id())
        if prev != current_after:
            col.decks.select(prev)
            if undo_before.last_step > 0 and col.undo_status().last_step > undo_before.last_step:
                try:
                    col.merge_undo_entries(undo_before.last_step)
                except Exception:
                    pass


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
        raw_keys = [k for k in ("A", "B", "C", "D") if k in note]
        orig_correct_idx = int(re.sub(r"\D", "", note["Correct"] if "Correct" in note else "") or "0") - 1
        valid_pairs = [(i, note[k].strip()) for i, k in enumerate(raw_keys) if note[k].strip()]
        if len(valid_pairs) < 2:
            return None
        opts = [text for _, text in valid_pairs]
        correct_in_filtered = -1
        for new_idx, (orig_idx, _) in enumerate(valid_pairs):
            if orig_idx == orig_correct_idx:
                correct_in_filtered = new_idx
                break
        if correct_in_filtered == -1:
            return None
        correct = correct_in_filtered
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
