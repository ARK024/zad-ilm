# -*- coding: utf-8 -*-
"""نافذة إعدادات الودجت — شجرة هرمية تدعم مئات الرزم والبحث الفوري وتحديد ترتيب الدراسة."""
from __future__ import annotations

from typing import Any, Optional

from aqt import mw
from aqt.qt import *
from aqt.utils import tooltip

from . import engine
from .controller import ADDON_NAME

# ثوابت Qt المتوافقة عبر PyQt6 و PyQt5
_FLAG_CHECKABLE = getattr(Qt.ItemFlag, "ItemIsUserCheckable", None) or getattr(Qt, "ItemIsUserCheckable", 1)
_FLAG_ENABLED = getattr(Qt.ItemFlag, "ItemIsEnabled", None) or getattr(Qt, "ItemIsEnabled", 32)
_FLAG_SELECTABLE = getattr(Qt.ItemFlag, "ItemIsSelectable", None) or getattr(Qt, "ItemIsSelectable", 2)

_CHECKED = getattr(Qt.CheckState, "Checked", None) or getattr(Qt, "Checked", 2)
_UNCHECKED = getattr(Qt.CheckState, "Unchecked", None) or getattr(Qt, "Unchecked", 0)
_PARTIAL = getattr(Qt.CheckState, "PartiallyChecked", None) or getattr(Qt, "PartiallyChecked", 1)

_USER_ROLE = getattr(Qt.ItemDataRole, "UserRole", None) or getattr(Qt, "UserRole", 256)


class SettingsDialog(QDialog):
    def __init__(self, parent, controller) -> None:
        super().__init__(parent)
        self.ctl = controller
        self.cfg = dict(controller.cfg)
        self.setWindowTitle("إعدادات زاد العلم")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setMinimumWidth(540)
        self.setMinimumHeight(620)
        self.resize(560, 680)

        # حالات داخلية لإدارة الشجرة وقائمة الأولويات
        self._updating_tree = False
        self._syncing_priority = False
        self._unpacked_mode = False
        self._item_by_full_name: dict[str, QTreeWidgetItem] = {}

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
        # تبويب 2: الرزم ونمط الدراسة (شجرة هرمية + بحث فوري + أولويات)
        # -------------------------------------------------------------
        tab_decks = QWidget()
        lay_decks = QVBoxLayout(tab_decks)

        # 1. نمط الدراسة
        form_order = QFormLayout()
        self.order_mode = QComboBox()
        self.order_mode.addItem("تنويع متوازن بين الرزم (بنسبة المستحق)", "mix")
        self.order_mode.addItem("رزمة تلو الأخرى (حسب ترتيب القائمة)", "deck_by_deck")
        self.order_mode.addItem("ترتيب أنكي الافتراضي", "anki")
        idx_order = self.order_mode.findData(self.cfg.get("order_mode", "mix"))
        self.order_mode.setCurrentIndex(max(idx_order, 0))
        form_order.addRow("نمط دراسة الرزم:", self.order_mode)
        lay_decks.addLayout(form_order)

        # 2. شجرة الرزم والبحث
        grp_tree = QGroupBox("اختيار الرزم (شجرة تفاعلية تدعم مئات الرزم)")
        v_tree_grp = QVBoxLayout(grp_tree)

        # شريط البحث وتصفية الرزم
        search_row = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍 ابحث في مئات الرزم والفروع...")
        self.search_box.textChanged.connect(self._apply_search_filter)

        self.btn_clear_search = QPushButton("مسح")
        self.btn_clear_search.clicked.connect(lambda: self.search_box.setText(""))

        self.chk_top_level_only = QCheckBox("الرزم الرئيسية فقط")
        self.chk_top_level_only.setToolTip("إخفاء الفروع الفرعية والتركيز على الرزم الأم لتسهيل إدارتها وترتيبها")
        self.chk_top_level_only.toggled.connect(self._apply_search_filter)

        search_row.addWidget(self.search_box)
        search_row.addWidget(self.btn_clear_search)
        search_row.addWidget(self.chk_top_level_only)
        v_tree_grp.addLayout(search_row)

        # أزرار الإجراءات السريعة على الشجرة
        tree_btn_row = QHBoxLayout()
        self.btn_select_all = QPushButton("☑ تحديد الكل")
        self.btn_deselect_all = QPushButton("☐ إلغاء التحديد")
        self.btn_expand_all = QPushButton("📂 فرد الفروع")
        self.btn_collapse_all = QPushButton("📁 طي الفروع")

        self.btn_select_all.clicked.connect(lambda: self._set_all_tree_state(_CHECKED))
        self.btn_deselect_all.clicked.connect(lambda: self._set_all_tree_state(_UNCHECKED))
        self.btn_expand_all.clicked.connect(self._expand_all_tree)
        self.btn_collapse_all.clicked.connect(self._collapse_all_tree)

        tree_btn_row.addWidget(self.btn_select_all)
        tree_btn_row.addWidget(self.btn_deselect_all)
        tree_btn_row.addStretch()
        tree_btn_row.addWidget(self.btn_expand_all)
        tree_btn_row.addWidget(self.btn_collapse_all)
        v_tree_grp.addLayout(tree_btn_row)

        # عنصر الشجرة
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setMinimumHeight(180)
        self.tree.setMaximumHeight(260)
        self.tree.itemChanged.connect(self._on_tree_item_changed)
        v_tree_grp.addWidget(self.tree)

        lay_decks.addWidget(grp_tree)

        # 3. أولويات وترتيب الرزم المحددة للدراسة
        grp_priority = QGroupBox("ترتيب دراسة الرزم المحددة (الأولويات)")
        v_prio = QVBoxLayout(grp_priority)

        hint_prio = QLabel(
            "💡 تظهر هنا الرزم المحددة فقط لتسهيل ترتيبها في نمط «رزمة تلو الأخرى» (الرزم بالأعلى تُدرس أولاً)."
        )
        hint_prio.setWordWrap(True)
        hint_prio.setStyleSheet("color: #666; font-size: 11px;")
        v_prio.addWidget(hint_prio)

        prio_btn_row = QHBoxLayout()
        self.btn_move_up = QPushButton("▲ لأعلى")
        self.btn_move_down = QPushButton("▼ لأسفل")
        self.btn_toggle_unpack = QPushButton("🔀 تفكيك كافة الفروع")
        self.btn_toggle_unpack.setToolTip("عرض كل الفروع الفرعية مفككة في قائمة الترتيب لتحديد ترتيب دقيق بينها")

        self.btn_move_up.clicked.connect(lambda: self._move_priority_item(-1))
        self.btn_move_down.clicked.connect(lambda: self._move_priority_item(1))
        self.btn_toggle_unpack.clicked.connect(self._toggle_unpack)

        prio_btn_row.addWidget(self.btn_move_up)
        prio_btn_row.addWidget(self.btn_move_down)
        prio_btn_row.addStretch()
        prio_btn_row.addWidget(self.btn_toggle_unpack)
        v_prio.addLayout(prio_btn_row)

        self.priority_list = QListWidget()
        self.priority_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.priority_list.setMinimumHeight(110)
        self.priority_list.setMaximumHeight(160)
        dnd_mode = getattr(getattr(QAbstractItemView, "DragDropMode", None), "InternalMove", None) or getattr(QAbstractItemView, "InternalMove", None)
        if dnd_mode is not None:
            self.priority_list.setDragDropMode(dnd_mode)
        drop_action = getattr(getattr(Qt, "DropAction", None), "MoveAction", None) or getattr(Qt, "MoveAction", None)
        if drop_action is not None:
            self.priority_list.setDefaultDropAction(drop_action)

        v_prio.addWidget(self.priority_list)
        lay_decks.addWidget(grp_priority)

        # 4. أولوية بطاقات التعلم
        self.learning = QCheckBox("تقديم بطاقات «قيد التعلّم» في موعدها دون انتظار الفاصل")
        self.learning.setChecked(self.cfg.get("learning_priority", True))
        lay_decks.addWidget(self.learning)

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

        # بناء محتويات الشجرة وقائمة الأولويات
        self._populate_tree()

    # -------------------------------------------------------------
    # بناء شجرة الرزم
    # -------------------------------------------------------------
    def _populate_tree(self) -> None:
        self._updating_tree = True
        self.tree.clear()
        self._item_by_full_name.clear()

        col = mw.col
        all_deck_names: list[str] = []
        if col:
            all_deck_names = sorted(
                d.name for d in col.decks.all_names_and_ids(include_filtered=False)
            )

        # بناء هيكل هرمي متداخل
        hierarchy: dict[str, Any] = {}
        for name in all_deck_names:
            parts = name.split("::")
            curr = hierarchy
            for p in parts:
                curr = curr.setdefault(p, {})

        # دالة تكرارية لإضافة عناصر الشجرة
        def add_nodes(parent_widget_or_item: Any, node_dict: dict[str, Any], prefix: str = "") -> None:
            for part in sorted(node_dict.keys()):
                full_name = f"{prefix}::{part}" if prefix else part
                item = QTreeWidgetItem(parent_widget_or_item)
                item.setText(0, part)
                item.setData(0, _USER_ROLE, full_name)
                item.setFlags(item.flags() | _FLAG_CHECKABLE | _FLAG_ENABLED | _FLAG_SELECTABLE)
                item.setCheckState(0, _UNCHECKED)
                self._item_by_full_name[full_name] = item
                add_nodes(item, node_dict[part], full_name)

        add_nodes(self.tree, hierarchy, "")

        # تطبيق الاختيارات المحفوظة
        saved_decks = self.cfg.get("decks")
        saved_single = self.cfg.get("deck", "")

        active_selection: list[str] = []
        if isinstance(saved_decks, list) and len(saved_decks) > 0:
            active_selection = [d for d in saved_decks if d in self._item_by_full_name]
        elif saved_single and saved_single in self._item_by_full_name:
            active_selection = [saved_single]

        if active_selection:
            for name in active_selection:
                item = self._item_by_full_name[name]
                item.setCheckState(0, _CHECKED)
                self._cascade_down(item, _CHECKED)
                self._update_parent_check_state(item)
        else:
            # افتراضيًا: كل الرزم محددة
            for i in range(self.tree.topLevelItemCount()):
                top_item = self.tree.topLevelItem(i)
                top_item.setCheckState(0, _CHECKED)
                self._cascade_down(top_item, _CHECKED)

        # فرد المستوى الأول افتراضيًا
        for i in range(self.tree.topLevelItemCount()):
            self.tree.topLevelItem(i).setExpanded(True)

        self._updating_tree = False

        # مزامنة قائمة الأولويات مع الحفاظ على الترتيب المحفوظ
        self._sync_priority_list(initial_order=active_selection)

    # -------------------------------------------------------------
    # منطق التحديد المتسلسل في الشجرة (Cascading Checkboxes)
    # -------------------------------------------------------------
    def _on_tree_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if self._updating_tree:
            return
        self._updating_tree = True
        try:
            state = item.checkState(0)
            if state in (_CHECKED, _UNCHECKED):
                self._cascade_down(item, state)
            self._update_parent_check_state(item)
        finally:
            self._updating_tree = False
            self._sync_priority_list()

    def _cascade_down(self, item: QTreeWidgetItem, state: Any) -> None:
        for i in range(item.childCount()):
            child = item.child(i)
            child.setCheckState(0, state)
            self._cascade_down(child, state)

    def _update_parent_check_state(self, item: QTreeWidgetItem) -> None:
        p = item.parent()
        if not p:
            return
        count = p.childCount()
        checked_cnt = 0
        unchecked_cnt = 0
        for i in range(count):
            c_state = p.child(i).checkState(0)
            if c_state == _CHECKED:
                checked_cnt += 1
            elif c_state == _UNCHECKED:
                unchecked_cnt += 1

        if checked_cnt == count:
            p.setCheckState(0, _CHECKED)
        elif unchecked_cnt == count:
            p.setCheckState(0, _UNCHECKED)
        else:
            p.setCheckState(0, _PARTIAL)

        self._update_parent_check_state(p)

    def _set_all_tree_state(self, state: Any) -> None:
        self._updating_tree = True
        try:
            for i in range(self.tree.topLevelItemCount()):
                it = self.tree.topLevelItem(i)
                it.setCheckState(0, state)
                self._cascade_down(it, state)
        finally:
            self._updating_tree = False
            self._sync_priority_list()

    def _expand_all_tree(self) -> None:
        self.tree.expandAll()

    def _collapse_all_tree(self) -> None:
        self.tree.collapseAll()

    # -------------------------------------------------------------
    # البحث والتصفية الفورية للشجرة
    # -------------------------------------------------------------
    def _apply_search_filter(self) -> None:
        query = self.search_box.text().strip().lower()
        top_only = self.chk_top_level_only.isChecked()

        def hide_all(it: QTreeWidgetItem) -> None:
            it.setHidden(True)
            for idx in range(it.childCount()):
                hide_all(it.child(idx))

        def filter_node(item: QTreeWidgetItem) -> bool:
            full_name = str(item.data(0, _USER_ROLE) or "").lower()
            label = item.text(0).lower()
            match_self = (not query) or (query in label) or (query in full_name)

            if top_only and item.parent() is not None:
                hide_all(item)
                return False

            has_child_match = False
            for i in range(item.childCount()):
                if filter_node(item.child(i)):
                    has_child_match = True

            visible = match_self or has_child_match
            item.setHidden(not visible)
            if visible and query:
                item.setExpanded(True)
            return visible

        for i in range(self.tree.topLevelItemCount()):
            filter_node(self.tree.topLevelItem(i))

    # -------------------------------------------------------------
    # إدارة قائمة أولويات وترتيب الرزم المحددة
    # -------------------------------------------------------------
    def _sync_priority_list(self, initial_order: Optional[list[str]] = None) -> None:
        if self._syncing_priority:
            return
        self._syncing_priority = True
        try:
            # الحفاظ على الترتيب الحالي إن وُجد
            existing_order: list[str] = []
            if initial_order:
                existing_order = list(initial_order)
            else:
                for i in range(self.priority_list.count()):
                    val = self.priority_list.item(i).data(_USER_ROLE)
                    if val:
                        existing_order.append(str(val))

            selected_map: dict[str, str] = {}

            if self._unpacked_mode:
                # وضع تفكيك الفروع: إدراج كل الفروع المحددة بدقة
                def collect_unpacked(it: QTreeWidgetItem) -> None:
                    if it.checkState(0) == _CHECKED:
                        fname = str(it.data(0, _USER_ROLE))
                        selected_map[fname] = fname
                    for idx in range(it.childCount()):
                        collect_unpacked(it.child(idx))

                for i in range(self.tree.topLevelItemCount()):
                    collect_unpacked(self.tree.topLevelItem(i))
            else:
                # الوضع المجمع الذكي: إذا كانت الرزمة الأم محددة كاملة، تُمثل بعنصر واحد
                def collect_grouped(it: QTreeWidgetItem) -> None:
                    st = it.checkState(0)
                    fname = str(it.data(0, _USER_ROLE))
                    if st == _CHECKED:
                        if it.childCount() > 0:
                            selected_map[fname] = f"📁 {fname} [كاملة بكافة فروعها]"
                        else:
                            selected_map[fname] = fname
                    elif st == _PARTIAL:
                        for idx in range(it.childCount()):
                            collect_grouped(it.child(idx))

                for i in range(self.tree.topLevelItemCount()):
                    collect_grouped(self.tree.topLevelItem(i))

            # ترتيب العناصر: العناصر الموجودة مسبقًا تظل بترتيبها، والجديدة تُضاف في النهاية
            final_keys = [k for k in existing_order if k in selected_map]
            for k in sorted(selected_map.keys()):
                if k not in final_keys:
                    final_keys.append(k)

            self.priority_list.clear()
            for k in final_keys:
                title = selected_map[k]
                list_item = QListWidgetItem(title)
                list_item.setData(_USER_ROLE, k)
                self.priority_list.addItem(list_item)
        finally:
            self._syncing_priority = False

    def _toggle_unpack(self) -> None:
        self._unpacked_mode = not self._unpacked_mode
        if self._unpacked_mode:
            self.btn_toggle_unpack.setText("📦 تجميع في رزم رئيسية")
        else:
            self.btn_toggle_unpack.setText("🔀 تفكيك كافة الفروع")
        self._sync_priority_list()

    def _move_priority_item(self, delta: int) -> None:
        row = self.priority_list.currentRow()
        if row < 0:
            return
        new_row = row + delta
        if 0 <= new_row < self.priority_list.count():
            item = self.priority_list.takeItem(row)
            self.priority_list.insertItem(new_row, item)
            self.priority_list.setCurrentRow(new_row)

    # -------------------------------------------------------------
    # الحفظ
    # -------------------------------------------------------------
    def save(self) -> None:
        raw = mw.addonManager.getConfig(ADDON_NAME) or {}

        # جمع الرزم بالترتيب المحدد من قائمة الأولويات
        ordered_decks: list[str] = []
        for i in range(self.priority_list.count()):
            dname = self.priority_list.item(i).data(_USER_ROLE)
            if dname:
                ordered_decks.append(str(dname))

        single_deck = ordered_decks[0] if len(ordered_decks) == 1 else ""

        raw.update(
            {
                "enabled": self.enabled.isChecked(),
                "mode": self.mode.currentData(),
                "interval_minutes": self.interval.value(),
                "active_from": self.t_from.text().strip() or "08:00",
                "active_to": self.t_to.text().strip() or "22:00",
                "daily_cap": self.cap.value(),
                "deck": single_deck,
                "decks": ordered_decks,
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
