# -*- coding: utf-8 -*-
"""المتحكّم: المؤقّت اليومي، الحالة، القائمة، الإجابة عبر جدولة أنكي."""
from __future__ import annotations

import datetime as dt
import json
import os
import time
from typing import Optional

from aqt import gui_hooks, mw
from aqt.operations.scheduling import answer_card
from aqt.qt import *
from aqt.utils import askUser, showInfo, tooltip

from . import engine

ADDON_DIR = os.path.dirname(__file__)
ADDON_NAME = mw.addonManager.addonFromModule(__name__)
STATE_PATH = os.path.join(ADDON_DIR, "user_files", "state.json")
DECKS_DIR = os.path.join(ADDON_DIR, "decks")
BUNDLED_DECKS = ["zad_islamic_sciences.apkg", "zad_hadith_cloze.apkg"]
TICK_MS = 30_000


class Controller:
    def __init__(self) -> None:
        self.cfg = engine.merged_config(mw.addonManager.getConfig(ADDON_NAME))
        self.state: dict = self._load_state()
        self.counter = engine.DayCounter.load(self.state.get("day"), dt.date.today())
        self.paused: bool = bool(self.state.get("paused", False))
        self.next_due: float = 0.0  # طابع زمني؛ 0 = الآن
        self.last_shown: float = 0.0
        self._last_peek: float = 0.0
        self.widget = None  # يُنشأ كسولًا بعد فتح الملف الشخصي
        self.timer = QTimer(mw)
        self.timer.timeout.connect(self.tick)
        self.menu = None
        self._act_pause = None

    # ------------------------------------------------------------------ الحالة
    def _load_state(self) -> dict:
        try:
            with open(STATE_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def save_state(self) -> None:
        self.state["day"] = self.counter.to_dict()
        self.state["paused"] = self.paused
        try:
            os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
            with open(STATE_PATH, "w", encoding="utf-8") as f:
                json.dump(self.state, f, ensure_ascii=False)
        except Exception:
            pass

    def remember_position(self, x: int, y: int) -> None:
        self.state["pos"] = [x, y]
        self.save_state()

    def reload_config(self) -> None:
        self.cfg = engine.merged_config(mw.addonManager.getConfig(ADDON_NAME))
        if self.widget:
            self.widget.apply_flags()
            self.widget.restyle()

    # ------------------------------------------------------------------ دورة الحياة
    def start(self) -> None:
        self._build_menu()
        self.timer.start(TICK_MS)

    def on_profile_open(self) -> None:
        self.reload_config()
        if self.widget is None:
            from .widget import ZadWidget

            self.widget = ZadWidget(self)
        self.counter.roll(dt.date.today())
        self.next_due = 0.0 if self.cfg.get("show_on_startup") else time.time() + self._interval()
        QTimer.singleShot(2500, self._maybe_first_run)

    def on_profile_close(self) -> None:
        self.save_state()
        if self.widget:
            self.widget.teardown()
            self.widget = None

    def _col(self):
        return mw.col if mw and mw.col else None

    # ------------------------------------------------------------------ الجدولة
    def _interval(self, fetched_total: int = 0) -> int:
        remaining = self.counter.remaining(self.cfg)
        return engine.next_interval_seconds(
            self.cfg, dt.datetime.now(), fetched_total or 30, remaining
        )

    def tick(self) -> None:
        """يُستدعى كل 30 ثانية: هل حان وقت بطاقة جديدة؟"""
        col, w = self._col(), self.widget
        if not col or not w:
            return
        now = dt.datetime.now()
        self.counter.roll(now.date())
        if not self.cfg.get("enabled", True) or self.paused:
            return
        if w.isVisible() and w.state in ("question", "answer", "busy"):
            return  # ما زالت هناك بطاقة بانتظار المستخدم
        if self.cfg.get("pause_while_reviewing", True) and mw.state == "review":
            return
        if not engine.is_active(now, self.cfg):
            return
        if self.counter.remaining(self.cfg) == 0:
            return

        ts = time.time()
        due_by_interval = ts >= self.next_due
        peek_learning = (
            not due_by_interval
            and self.cfg.get("learning_priority", True)
            and ts - self._last_peek >= 60
            and ts - self.last_shown >= float(self.cfg.get("learning_min_gap_minutes", 1)) * 60
        )
        if not due_by_interval and not peek_learning:
            return
        self._last_peek = ts

        fetched = engine.fetch_next(col, self.cfg.get("deck", ""))
        if fetched is None:
            self.next_due = ts + self._interval()
            return
        if due_by_interval or engine.should_bypass_interval(
            fetched, self.cfg, ts - self.last_shown
        ):
            self._show(fetched)

    def _show(self, fetched: engine.Fetched) -> None:
        w = self.widget
        if not w:
            return
        self.counter.shown += 1
        self.last_shown = time.time()
        self.save_state()
        w.present(fetched)
        w.show_widget()

    # ------------------------------------------------------------------ إجراءات المستخدم
    def show_now(self) -> None:
        """عرض بطاقة فورًا (يتجاوز ساعات النشاط والحد اليومي)."""
        col, w = self._col(), self.widget
        if not col or not w:
            tooltip("افتح ملفًا شخصيًا في أنكي أولًا")
            return
        fetched = engine.fetch_next(col, self.cfg.get("deck", ""))
        if fetched is None:
            w.show_done("<b>🎉 أتممت كل المستحق اليوم</b><br>ما شاء الله، لا توجد بطاقات الآن.", False, 4000)
            w.show_widget()
            return
        self._show(fetched)

    def show_next_now(self) -> None:
        self.show_now()

    def snooze(self) -> None:
        minutes = int(self.cfg.get("snooze_minutes", 30))
        self.next_due = time.time() + minutes * 60
        tooltip(f"سيعود الودجت بعد {minutes} دقيقة")
        if self.widget:
            self.widget.hide_widget()

    def answer(self, rating: int) -> None:
        w, col = self.widget, self._col()
        if not w or not col or not w.fetched:
            return
        fetched = w.fetched
        try:
            ans = engine.build_answer(col, fetched, rating)
        except Exception as e:  # pragma: no cover
            showInfo(f"تعذّر تسجيل الإجابة: {e}")
            return
        total = fetched.total_due
        w.state = "busy"

        def done(_changes) -> None:
            self.counter.answered += 1
            secs = engine.next_interval_seconds(
                self.cfg,
                dt.datetime.now(),
                max(total - 1, 0),
                self.counter.remaining(self.cfg),
            )
            self.next_due = time.time() + secs
            self.save_state()
            self._after_answer(secs, max(total - 1, 0))

        answer_card(parent=mw, answer=ans).success(done).run_in_background()

    def _after_answer(self, secs: int, left: int) -> None:
        w = self.widget
        if not w:
            return
        at = dt.datetime.now() + dt.timedelta(seconds=secs)
        if left <= 0:
            msg = "<b>🎉 أتممت المستحق</b><br>بارك الله في علمك وعملك."
        else:
            msg = (
                f"<b>✔ تم الحفظ</b><br>البطاقة القادمة بعد {max(secs // 60, 1)} دقيقة "
                f"(≈ {at.strftime('%H:%M')})<br><small>المتبقي اليوم: {left}</small>"
            )
        w.show_done(msg, can_next=left > 0, auto_hide_ms=3500)

    def on_hidden(self, state: str) -> None:
        pass

    def open_main(self) -> None:
        mw.show()
        mw.raise_()
        mw.activateWindow()

    # ------------------------------------------------------------------ القائمة
    def _build_menu(self) -> None:
        self.menu = QMenu("زاد العلم", mw)
        a = QAction("عرض بطاقة الآن", mw)
        a.setShortcut(QKeySequence("Ctrl+Alt+Z"))
        a.triggered.connect(self.show_now)
        self.menu.addAction(a)

        self._act_pause = QAction("", mw)
        self._act_pause.triggered.connect(self.toggle_pause)
        self.menu.addAction(self._act_pause)
        self._refresh_pause_label()

        self.menu.addSeparator()
        a = QAction("استيراد رزم العلوم الشرعية المضمّنة…", mw)
        a.triggered.connect(self.import_bundled)
        self.menu.addAction(a)
        a = QAction("الإعدادات…", mw)
        a.triggered.connect(self.open_settings)
        self.menu.addAction(a)
        a = QAction("حالة اليوم", mw)
        a.triggered.connect(self.show_status)
        self.menu.addAction(a)
        mw.form.menuTools.addMenu(self.menu)

    def _refresh_pause_label(self) -> None:
        if self._act_pause:
            self._act_pause.setText("استئناف الودجت" if self.paused else "إيقاف الودجت مؤقتًا")

    def toggle_pause(self) -> None:
        self.paused = not self.paused
        self._refresh_pause_label()
        self.save_state()
        tooltip("تم إيقاف الودجت مؤقتًا" if self.paused else "تم استئناف الودجت")

    def show_status(self) -> None:
        col = self._col()
        n = l = r = 0
        if col:
            n, l, r = engine.counts(col, self.cfg.get("deck", ""))
        cap = int(self.cfg.get("daily_cap", 0) or 0)
        nxt = (
            dt.datetime.fromtimestamp(self.next_due).strftime("%H:%M")
            if self.next_due > time.time()
            else "الآن"
        )
        showInfo(
            "📊 حالة اليوم\n\n"
            f"عُرض: {self.counter.shown}" + (f" من {cap}" if cap else "") + "\n"
            f"أُجيب: {self.counter.answered}\n"
            f"المتبقي في أنكي — جديدة: {n} · تعلّم: {l} · مراجعة: {r}\n"
            f"البطاقة القادمة: {nxt}\n"
            f"الحالة: {'متوقف مؤقتًا' if self.paused else 'يعمل'}",
            title="زاد العلم",
        )

    def open_settings(self) -> None:
        from .settings import SettingsDialog

        SettingsDialog(mw, self).exec()

    # ------------------------------------------------------------------ استيراد الرزم
    def import_bundled(self) -> None:
        from aqt.import_export.importing import import_file

        for name in BUNDLED_DECKS:
            path = os.path.join(DECKS_DIR, name)
            if os.path.exists(path):
                import_file(mw, path)

    def _maybe_first_run(self) -> None:
        col = self._col()
        if not col or self.cfg.get("first_run_done") or self.state.get("first_run_done"):
            return
        self.state["first_run_done"] = True
        self.save_state()
        has_zad = any(
            d.name.startswith("زاد العلم") for d in col.decks.all_names_and_ids()
        )
        if has_zad:
            return
        if askUser(
            "مرحبًا بك في «زاد العلم» 🌿\n\n"
            "هل تريد استيراد رزم العلوم الشرعية الجاهزة (44 بطاقة مؤصَّلة + متون الأربعين النووية)؟\n"
            "يمكنك استيرادها لاحقًا من: أدوات ← زاد العلم.",
            title="زاد العلم",
        ):
            self.import_bundled()
