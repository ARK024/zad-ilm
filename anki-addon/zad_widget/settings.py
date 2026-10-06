# -*- coding: utf-8 -*-
"""نافذة إعدادات الودجت — تدعم اختيار عدة رزم وترتيب دراستها."""
from __future__ import annotations

from aqt import mw
from aqt.qt import *
from aqt.utils import tooltip

from . import engine
from .controller import ADDON_NAME


class SettingsDialog(QDialog):
    def __init__(self, parent, controller) -> None:
        super().__init__(parent)
        self.ctl = controller
        self.cfg = dict(controller.cfg)
        self.setWindowTitle("إعدادات زاد العلم")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setMinimumWidth(500)
        self.setMinimumHeight(560)
        self.resize(520, 600)

        tabs = QTabWidget()

        # -------------------------------------------------------------
        # تبويب 1: الجدولة والمواعيد
        # -------------------------------------------------------------
        tab_schedule = QWidget()
        form_schedule = QFormLayout(tab_schedule)

        self.enabled = QCheckBox("تفعيل ظهور البطاقات تلقائيًا على مدار اليوم")
        self.enabled.setChecked(self.cfg.get("enabled", True))
        form_schedule.addRow(self.enabled)

        self.mode = QComboBox()
        self.mode.addItem("فاصل ثابت بين البطاقات", "interval")
        self.mode.addItem("توزيع المستحق على ساعات النشاط تلقائيًا", "spread")
        self.mode.setCurrentIndex(0 if self.cfg.get("mode") == "interval" else 1)
        form_schedule.addRow("طريقة الجدولة:", self.mode)

        self.interval = QSpinBox()
        self.interval.setRange(1, 600)
        self.interval.setSuffix(" دقيقة")
        self.interval.setValue(int(self.cfg.get("interval_minutes", 20)))
        form_schedule.addRow("الفاصل (للفاصل الثابت):", self.interval)

        self.t_from = QLineEdit(str(self.cfg.get("active_from", "08:00")))
        self.t_to = QLineEdit(str(self.cfg.get("active_to", "22:00")))
        self.t_from.setPlaceholderText("08:00")
        self.t_to.setPlaceholderText("22:00")
        row_time = QHBoxLayout()
        row_time.addWidget(QLabel("من"))
        row_time.addWidget(self.t_from)
        row_time.addWidget(QLabel("إلى"))
        row_time.addWidget(self.t_to)
        form_schedule.addRow("ساعات النشاط:", row_time)

        self.cap = QSpinBox()
        self.cap.setRange(0, 5000)
        self.cap.setSpecialValueText("بلا حد")
        self.cap.setValue(int(self.cfg.get("daily_cap", 0)))
        form_schedule.addRow("أقصى عدد بطاقات يوميًا:", self.cap)

        self.snooze = QSpinBox()
        self.snooze.setRange(1, 600)
        self.snooze.setSuffix(" دقيقة")
        self.snooze.setValue(int(self.cfg.get("snooze_minutes", 30)))
        form_schedule.addRow("مدة زر «أجّل»:", self.snooze)

        tabs.addTab(tab_schedule, "⏰ الجدولة والمواعيد")

        # -------------------------------------------------------------
        # تبويب 2: الرزم ونمط الدراسة
        # -------------------------------------------------------------
        tab_decks = QWidget()
        lay_decks = QVBoxLayout(tab_decks)

        form_order = QFormLayout()
        self.order_mode = QComboBox()
        self.order_mode.addItem("تنويع متوازن بين الرزم (بنسبة المستحق)", "mix")
        self.order_mode.addItem("رزمة تلو الأخرى (حسب ترتيب القائمة)", "deck_by_deck")
        self.order_mode.addItem("ترتيب أنكي الافتراضي", "anki")
        idx_order = self.order_mode.findData(self.cfg.get("order_mode", "mix"))
        self.order_mode.setCurrentIndex(max(idx_order, 0))
        form_order.addRow("نمط دراسة الرزم:", self.order_mode)
        lay_decks.addLayout(form_order)

        grp_decks = QGroupBox("الرزم المحددة للدراسة")
        v_grp = QVBoxLayout(grp_decks)

        btn_row = QHBoxLayout()
        self.btn_select_all = QPushButton("تحديد الكل")
        self.btn_deselect_all = QPushButton("إلغاء التحديد")
        self.btn_move_up = QPushButton("▲ لأعلى")
        self.btn_move_down = QPushButton("▼ لأسفل")
        btn_row.addWidget(self.btn_select_all)
        btn_row.addWidget(self.btn_deselect_all)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_move_up)
        btn_row.addWidget(self.btn_move_down)
        v_grp.addLayout(btn_row)

        self.deck_list = QListWidget()
        self.deck_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        dnd_mode = getattr(getattr(QAbstractItemView, "DragDropMode", None), "InternalMove", None) or getattr(QAbstractItemView, "InternalMove", None)
        if dnd_mode is not None:
            self.deck_list.setDragDropMode(dnd_mode)
        drop_action = getattr(getattr(Qt, "DropAction", None), "MoveAction", None) or getattr(Qt, "MoveAction", None)
        if drop_action is not None:
            self.deck_list.setDefaultDropAction(drop_action)

        self._populate_deck_list()
        v_grp.addWidget(self.deck_list)

        hint = QLabel(
            "💡 يمكنك إعادة ترتيب الرزم بالأزرار أو بالسحب والإفلات لتحديد أولويتها في نمط «رزمة تلو الأخرى».\n"
            "إذا لم تحدد أي رزمة، ستشمل الدراسة جميع رزم أنكي تلقائيًا."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #666; font-size: 11px;")
        v_grp.addWidget(hint)

        lay_decks.addWidget(grp_decks)

        self.learning = QCheckBox("تقديم بطاقات «قيد التعلّم» في موعدها دون انتظار الفاصل")
        self.learning.setChecked(self.cfg.get("learning_priority", True))
        lay_decks.addWidget(self.learning)

        self.btn_select_all.clicked.connect(lambda: self._set_all_decks(True))
        self.btn_deselect_all.clicked.connect(lambda: self._set_all_decks(False))
        self.btn_move_up.clicked.connect(lambda: self._move_deck(-1))
        self.btn_move_down.clicked.connect(lambda: self._move_deck(1))

        tabs.addTab(tab_decks, "📚 الرزم ونمط الدراسة")

        # -------------------------------------------------------------
        # تبويب 3: المظهر وسلوك النافذة
        # -------------------------------------------------------------
        tab_ui = QWidget()
        form_ui = QFormLayout(tab_ui)

        self.corner = QComboBox()
        for label, val in (
            ("أسفل اليمين", "bottom-right"),
            ("أسفل اليسار", "bottom-left"),
            ("أعلى اليمين", "top-right"),
            ("أعلى اليسار", "top-left"),
        ):
            self.corner.addItem(label, val)
        idx_corner = self.corner.findData(self.cfg.get("corner", "bottom-right"))
        self.corner.setCurrentIndex(max(idx_corner, 0))
        form_ui.addRow("موضع الودجت:", self.corner)

        self.font = QSpinBox()
        self.font.setRange(12, 40)
        self.font.setValue(int(self.cfg.get("font_size", 16)))
        form_ui.addRow("حجم الخط:", self.font)

        self.top = QCheckBox("إبقاء الودجت فوق النوافذ الأخرى دائمًا")
        self.top.setChecked(self.cfg.get("always_on_top", True))
        form_ui.addRow(self.top)

        self.startup = QCheckBox("إظهار بطاقة فور فتح برنامج أنكي")
        self.startup.setChecked(self.cfg.get("show_on_startup", True))
        form_ui.addRow(self.startup)

        self.audio = QCheckBox("تشغيل الملفات الصوتية تلقائيًا")
        self.audio.setChecked(self.cfg.get("autoplay_audio", False))
        form_ui.addRow(self.audio)

        self.close_tray = QCheckBox("تشغيل أنكي في الخلفية (بجوار الساعة) عند إغلاق النافذة")
        self.close_tray.setChecked(self.cfg.get("close_to_tray", True))
        form_ui.addRow(self.close_tray)

        self.pause_review = QCheckBox("عدم إظهار الودجت أثناء المراجعة داخل نافذة أنكي")
        self.pause_review.setChecked(self.cfg.get("pause_while_reviewing", True))
        form_ui.addRow(self.pause_review)

        tabs.addTab(tab_ui, "🎨 المظهر وسلوك النافذة")

        # أزرار الحفظ والإلغاء
        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        bb.accepted.connect(self.save)
        bb.rejected.connect(self.reject)

        main_lay = QVBoxLayout(self)
        main_lay.addWidget(tabs)
        main_lay.addWidget(bb)

    # -------------------------------------------------------------
    # مساعدات قائمة الرزم
    # -------------------------------------------------------------
    def _populate_deck_list(self) -> None:
        col = mw.col
        all_decks: list[str] = []
        if col:
            all_decks = sorted(
                d.name for d in col.decks.all_names_and_ids(include_filtered=False)
            )

        saved_decks = self.cfg.get("decks")
        saved_single = self.cfg.get("deck", "")

        if isinstance(saved_decks, list) and len(saved_decks) > 0:
            checked_names = set(saved_decks)
            display_order = [d for d in saved_decks if d in all_decks] + [
                d for d in all_decks if d not in saved_decks
            ]
        elif saved_single:
            checked_names = {saved_single}
            display_order = [saved_single] + [d for d in all_decks if d != saved_single]
        else:
            checked_names = set(all_decks)
            display_order = list(all_decks)

        _flag = getattr(getattr(Qt, "ItemFlag", None), "ItemIsUserCheckable", None) or getattr(Qt, "ItemIsUserCheckable", 1)
        _chk = getattr(getattr(Qt, "CheckState", None), "Checked", None) or getattr(Qt, "Checked", 2)
        _unchk = getattr(getattr(Qt, "CheckState", None), "Unchecked", None) or getattr(Qt, "Unchecked", 0)

        for name in display_order:
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | _flag)
            item.setCheckState(_chk if name in checked_names else _unchk)
            self.deck_list.addItem(item)

    def _move_deck(self, delta: int) -> None:
        row = self.deck_list.currentRow()
        if row < 0:
            return
        new_row = row + delta
        if 0 <= new_row < self.deck_list.count():
            item = self.deck_list.takeItem(row)
            self.deck_list.insertItem(new_row, item)
            self.deck_list.setCurrentRow(new_row)

    def _set_all_decks(self, checked: bool) -> None:
        _chk = getattr(getattr(Qt, "CheckState", None), "Checked", None) or getattr(Qt, "Checked", 2)
        _unchk = getattr(getattr(Qt, "CheckState", None), "Unchecked", None) or getattr(Qt, "Unchecked", 0)
        st = _chk if checked else _unchk
        for i in range(self.deck_list.count()):
            self.deck_list.item(i).setCheckState(st)

    def _get_checked_decks(self) -> list[str]:
        _chk = getattr(getattr(Qt, "CheckState", None), "Checked", None) or getattr(Qt, "Checked", 2)
        out: list[str] = []
        for i in range(self.deck_list.count()):
            item = self.deck_list.item(i)
            if item.checkState() == _chk:
                out.append(item.text())
        return out

    # -------------------------------------------------------------
    # الحفظ
    # -------------------------------------------------------------
    def save(self) -> None:
        raw = mw.addonManager.getConfig(ADDON_NAME) or {}
        checked_decks = self._get_checked_decks()
        single_deck = checked_decks[0] if len(checked_decks) == 1 else ""

        raw.update(
            {
                "enabled": self.enabled.isChecked(),
                "mode": self.mode.currentData(),
                "interval_minutes": self.interval.value(),
                "active_from": self.t_from.text().strip() or "08:00",
                "active_to": self.t_to.text().strip() or "22:00",
                "daily_cap": self.cap.value(),
                "deck": single_deck,
                "decks": checked_decks,
                "order_mode": self.order_mode.currentData() or "mix",
                "learning_priority": self.learning.isChecked(),
                "pause_while_reviewing": self.pause_review.isChecked(),
                "snooze_minutes": self.snooze.value(),
                "autoplay_audio": self.audio.isChecked(),
                "always_on_top": self.top.isChecked(),
                "show_on_startup": self.startup.isChecked(),
                "close_to_tray": self.close_tray.isChecked(),
                "corner": self.corner.currentData(),
                "font_size": self.font.value(),
            }
        )

        old_corner = self.cfg.get("corner")
        new_corner = self.corner.currentData()
        if old_corner != new_corner:
            self.ctl.state.pop("pos", None)
            self.ctl.save_state()

        mw.addonManager.writeConfig(ADDON_NAME, raw)
        self.ctl.reload_config()
        import time as _t

        self.ctl.next_due = _t.time() + self.ctl._interval()
        tooltip("تم حفظ الإعدادات")
        self.accept()
