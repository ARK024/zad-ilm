# -*- coding: utf-8 -*-
"""نافذة إعدادات الودجت."""
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
        self.setMinimumWidth(440)

        form = QFormLayout()

        self.enabled = QCheckBox("تفعيل ظهور البطاقات تلقائيًا على مدار اليوم")
        self.enabled.setChecked(self.cfg["enabled"])
        form.addRow(self.enabled)

        self.mode = QComboBox()
        self.mode.addItem("فاصل ثابت بين البطاقات", "interval")
        self.mode.addItem("توزيع المستحق على ساعات النشاط تلقائيًا", "spread")
        self.mode.setCurrentIndex(0 if self.cfg["mode"] == "interval" else 1)
        form.addRow("طريقة الجدولة:", self.mode)

        self.interval = QSpinBox()
        self.interval.setRange(1, 600)
        self.interval.setSuffix(" دقيقة")
        self.interval.setValue(int(self.cfg["interval_minutes"]))
        form.addRow("الفاصل (للفاصل الثابت):", self.interval)

        self.t_from = QLineEdit(self.cfg["active_from"])
        self.t_to = QLineEdit(self.cfg["active_to"])
        self.t_from.setPlaceholderText("08:00")
        self.t_to.setPlaceholderText("22:00")
        row = QHBoxLayout()
        row.addWidget(QLabel("من"))
        row.addWidget(self.t_from)
        row.addWidget(QLabel("إلى"))
        row.addWidget(self.t_to)
        form.addRow("ساعات النشاط:", row)

        self.cap = QSpinBox()
        self.cap.setRange(0, 5000)
        self.cap.setSpecialValueText("بلا حد")
        self.cap.setValue(int(self.cfg["daily_cap"]))
        form.addRow("أقصى عدد بطاقات يوميًا:", self.cap)

        self.deck = QComboBox()
        self.deck.addItem("كل الرزم", "")
        col = mw.col
        if col:
            names = sorted(
                d.name for d in col.decks.all_names_and_ids(include_filtered=False)
            )
            for n in names:
                self.deck.addItem(n, n)
        idx = self.deck.findData(self.cfg["deck"])
        self.deck.setCurrentIndex(max(idx, 0))
        form.addRow("الرزمة:", self.deck)

        self.learning = QCheckBox("بطاقات «قيد التعلّم» تظهر في موعدها دون انتظار الفاصل")
        self.learning.setChecked(self.cfg["learning_priority"])
        form.addRow(self.learning)

        self.pause_review = QCheckBox("لا تُظهر الودجت أثناء المراجعة في نافذة أنكي")
        self.pause_review.setChecked(self.cfg["pause_while_reviewing"])
        form.addRow(self.pause_review)

        self.snooze = QSpinBox()
        self.snooze.setRange(1, 600)
        self.snooze.setSuffix(" دقيقة")
        self.snooze.setValue(int(self.cfg["snooze_minutes"]))
        form.addRow("مدة التأجيل:", self.snooze)

        self.audio = QCheckBox("تشغيل الصوت تلقائيًا")
        self.audio.setChecked(self.cfg["autoplay_audio"])
        form.addRow(self.audio)

        self.top = QCheckBox("إبقاء الودجت فوق النوافذ")
        self.top.setChecked(self.cfg["always_on_top"])
        form.addRow(self.top)

        self.startup = QCheckBox("إظهار بطاقة عند فتح أنكي")
        self.startup.setChecked(self.cfg["show_on_startup"])
        form.addRow(self.startup)

        self.close_tray = QCheckBox("تشغيل أنكي في الخلفية (بجوار الساعة) عند إغلاق النافذة")
        self.close_tray.setChecked(self.cfg.get("close_to_tray", True))
        form.addRow(self.close_tray)

        self.corner = QComboBox()
        for label, val in (
            ("أسفل اليمين", "bottom-right"),
            ("أسفل اليسار", "bottom-left"),
            ("أعلى اليمين", "top-right"),
            ("أعلى اليسار", "top-left"),
        ):
            self.corner.addItem(label, val)
        self.corner.setCurrentIndex(max(self.corner.findData(self.cfg["corner"]), 0))
        form.addRow("موضع الودجت:", self.corner)

        self.font = QSpinBox()
        self.font.setRange(12, 40)
        self.font.setValue(int(self.cfg["font_size"]))
        form.addRow("حجم الخط:", self.font)

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        bb.accepted.connect(self.save)
        bb.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(bb)

    def save(self) -> None:
        raw = mw.addonManager.getConfig(ADDON_NAME) or {}
        raw.update(
            {
                "enabled": self.enabled.isChecked(),
                "mode": self.mode.currentData(),
                "interval_minutes": self.interval.value(),
                "active_from": self.t_from.text().strip() or "08:00",
                "active_to": self.t_to.text().strip() or "22:00",
                "daily_cap": self.cap.value(),
                "deck": self.deck.currentData() or "",
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
        mw.addonManager.writeConfig(ADDON_NAME, raw)
        self.ctl.reload_config()
        self.ctl.next_due = 0.0
        tooltip("تم حفظ الإعدادات")
        self.accept()
