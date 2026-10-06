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
        self.tray_icon = None
        self.tray_menu = None
        self._last_sync: float = 0.0
        self._force_exit = False
        self._orig_close_event = None

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

    def remember_size(self, w: int, h: int) -> None:
        self.state["width"] = w
        self.state["height"] = h
        self.save_state()

    def reload_config(self) -> None:
        self.cfg = engine.merged_config(mw.addonManager.getConfig(ADDON_NAME))
        if self.widget:
            self.widget.apply_flags()
            self.widget.restyle()

    def start(self) -> None:
        self._build_menu()
        self._setup_tray()
        self._hook_close_event()
        if hasattr(gui_hooks, "theme_did_change"):
            gui_hooks.theme_did_change.append(self.on_theme_changed)
        self.timer.start(TICK_MS)

    def on_theme_changed(self) -> None:
        if self.widget:
            self.widget.restyle()

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

    def _deck_spec(self) -> Any:
        decks = self.cfg.get("decks")
        if decks is not None and isinstance(decks, list) and decks:
            return decks
        return self.cfg.get("deck", "")

    def _order_mode(self) -> str:
        return str(self.cfg.get("order_mode", "mix") or "mix")

    # ------------------------------------------------------------------ الجدولة
    def _interval(self, fetched_total: int = 0) -> int:
        remaining = self.counter.remaining(self.cfg)
        return engine.next_interval_seconds(
            self.cfg, dt.datetime.now(), fetched_total or 30, remaining
        )

    def tick(self) -> None:
        """يُستدعى كل 30 ثانية: هل حان وقت بطاقة جديدة؟"""
        try:
            col, w = self._col(), self.widget
            if not col or not w:
                return
            now = dt.datetime.now()
            self.counter.roll(now.date())
            if not self.cfg.get("enabled", True) or self.paused:
                return
            if w.isVisible() and w.state in ("question", "answer", "busy"):
                return  # ما زالت هناك بطاقة بانتظار المستخدم
            # فحص حالة المراجعة فقط إن كانت نافذة أنكي ظاهرة للمستخدم
            if self.cfg.get("pause_while_reviewing", True) and mw.isVisible() and mw.state == "review":
                return
            if not engine.is_active(now, self.cfg):
                return
            if self.counter.remaining(self.cfg) == 0:
                return

            ts = time.time()
            # مزامنة دورية هادئة في الخلفية كل 30 دقيقة إذا كانت النافذة مخفية بجوار الساعة
            if not mw.isVisible() and ts - self._last_sync >= 1800:
                self._last_sync = ts
                if hasattr(mw, "can_auto_sync") and mw.can_auto_sync():
                    mw.maybe_auto_sync_on_open_close(lambda _: None)

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

            fetched = engine.fetch_next(col, self._deck_spec(), self._order_mode())
            if fetched is None:
                self.next_due = ts + self._interval()
                return
            if due_by_interval or engine.should_bypass_interval(
                fetched, self.cfg, ts - self.last_shown
            ):
                self._show(fetched)
        except Exception:
            pass

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
        fetched = engine.fetch_next(col, self._deck_spec(), self._order_mode())
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

        def on_fail(e: Exception) -> None:
            w.state = "answer"
            tooltip(f"تعذّر تسجيل الإجابة: {e}")

        answer_card(parent=mw, answer=ans).success(done).failure(on_fail).run_in_background()

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
        if state in ("question", "answer"):
            self.next_due = time.time() + self._interval()
            self.save_state()

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

    def _setup_tray(self) -> None:
        if not hasattr(QSystemTrayIcon, "isSystemTrayAvailable") or not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray_icon = QSystemTrayIcon(mw)
        icon = mw.windowIcon()
        if icon.isNull():
            icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogInfoView)
        self.tray_icon.setIcon(icon)
        self.tray_icon.setToolTip("زاد العلم — أنكي يعمل في الخلفية")

        self.tray_menu = QMenu(mw)
        a_show = QAction("إظهار نافذة أنكي", self.tray_menu)
        a_show.triggered.connect(self.open_main)
        self.tray_menu.addAction(a_show)

        a_card = QAction("عرض بطاقة الآن (Ctrl+Alt+Z)", self.tray_menu)
        a_card.triggered.connect(self.show_now)
        self.tray_menu.addAction(a_card)

        a_pause = QAction("إيقاف / استئناف الودجت", self.tray_menu)
        a_pause.triggered.connect(self.toggle_pause)
        self.tray_menu.addAction(a_pause)

        self.tray_menu.addSeparator()

        a_settings = QAction("الإعدادات…", self.tray_menu)
        a_settings.triggered.connect(self.open_settings)
        self.tray_menu.addAction(a_settings)

        self.tray_menu.addSeparator()

        a_quit = QAction("خروج نهائي من أنكي", self.tray_menu)
        a_quit.triggered.connect(self.force_exit)
        self.tray_menu.addAction(a_quit)

        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.open_main()

    def _on_about_to_quit(self) -> None:
        self._force_exit = True

    def _hook_close_event(self) -> None:
        if self._orig_close_event is not None:
            return
        self._orig_close_event = mw.closeEvent

        # ربط أمر الخروج (File -> Exit / Ctrl+Q) صراحةً بـ force_exit حتى لا يتم إخفاؤه
        if hasattr(mw, "form") and hasattr(mw.form, "actionExit"):
            mw.form.actionExit.triggered.connect(self.force_exit)

        app = QApplication.instance()
        if app:
            app.aboutToQuit.connect(self._on_about_to_quit)

        def custom_close(event: QCloseEvent) -> None:
            if self._force_exit:
                self._orig_close_event(event)
                return

            if not self.cfg.get("close_to_tray", True):
                self._orig_close_event(event)
                return

            if mw.state == "profileManager":
                self._orig_close_event(event)
                return

            event.ignore()
            # الانتقال لمتصفح الرزم حتى لا تعلق حالة review
            if mw.state == "review":
                mw.moveToState("deckBrowser")
            # مزامنة سريعة عند الإغلاق بجوار الساعة
            if hasattr(mw, "can_auto_sync") and mw.can_auto_sync():
                mw.maybe_auto_sync_on_open_close(lambda _: None)
            mw.hide()
            tooltip("أنكي يعمل الآن في الخلفية بجوار الساعة لتذكيرك بالبطاقات على مدار اليوم", period=3500)

        mw.closeEvent = custom_close

    def force_exit(self) -> None:
        self._force_exit = True
        if self.tray_icon:
            self.tray_icon.hide()
        mw.close()

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
            n, l, r = engine.counts(col, self._deck_spec())
        cap = int(self.cfg.get("daily_cap", 0) or 0)
        nxt = (
            dt.datetime.fromtimestamp(self.next_due).strftime("%H:%M")
            if self.next_due > time.time()
            else "الآن"
        )
        spec = self._deck_spec()
        if isinstance(spec, list) and spec:
            deck_info = f"الرزم المحددة ({len(spec)}): {', '.join(spec[:3])}{'...' if len(spec) > 3 else ''}"
        elif spec:
            deck_info = f"الرزمة: {spec}"
        else:
            deck_info = "الرزم: كل الرزم"

        order_names = {
            "mix": "تنويع متوازن",
            "deck_by_deck": "رزمة تلو الأخرى",
            "anki": "ترتيب أنكي الافتراضي",
        }
        order_info = order_names.get(self._order_mode(), self._order_mode())

        showInfo(
            "📊 حالة اليوم\n\n"
            f"عُرض: {self.counter.shown}" + (f" من {cap}" if cap else "") + "\n"
            f"أُجيب: {self.counter.answered}\n"
            f"{deck_info}\n"
            f"نمط الدراسة: {order_info}\n"
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
