# -*- coding: utf-8 -*-
"""نافذة الودجت العائمة (Qt) — مرنة وقابلة للتوسيع وتغيير الحجم بحرية."""
from __future__ import annotations

import html
import re
from typing import Callable, Optional

from anki.cards import Card
from aqt import gui_hooks, mw
from aqt.qt import *
from aqt.sound import av_player
from aqt.theme import theme_manager
from aqt.webview import AnkiWebView

from . import engine, web

_TYPE_ANS = re.compile(r"\[\[type:[^\]]+\]\]")


class ZadWidget(QWidget):
    """نافذة عائمة مرنة وقابلة للتوسيع وتغيير الحجم بسحب الحواف أو بالأزرار."""

    EDGE_NONE = 0
    EDGE_LEFT = 1
    EDGE_TOP = 2
    EDGE_RIGHT = 4
    EDGE_BOTTOM = 8

    def __init__(self, controller) -> None:
        super().__init__(None)
        self.ctl = controller
        self.fetched: Optional[engine.Fetched] = None
        self.quiz: Optional[engine.Quiz] = None
        self.state = "idle"  # idle | question | answer | done
        
        # حالة السحب وتغيير الحجم والتوسيع
        self._drag_pos: Optional[QPoint] = None
        self._resizing_edge = self.EDGE_NONE
        self._resize_start_mouse: Optional[QPoint] = None
        self._resize_start_geo: Optional[QRect] = None
        self.is_expanded = False
        self._pre_expand_geo: Optional[QRect] = None

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide_widget)

        self.setWindowTitle("زاد العلم")
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setMouseTracking(True)
        
        # حدود الحجم لمرونة كاملة
        self.setMinimumSize(320, 220)
        self.setMaximumSize(1800, 1400)
        self.apply_flags()

        # ---- شريط الرأس (للسحب والتحكم)
        self.header = QFrame(self)
        self.header.setObjectName("zadHeader")
        self.header.setCursor(Qt.CursorShape.ArrowCursor)
        self.title = QLabel("زاد العلم", self.header)
        self.counts = QLabel("", self.header)
        
        # أزرار تحكم واضحة ومرنة
        self.btn_anki = self._tool_button("📚", "فتح برنامج أنكي الرئيسي", self.ctl.open_main)
        self.btn_settings = self._tool_button("⚙", "إعدادات زاد العلم", self.ctl.open_settings)
        self.btn_expand = self._tool_button("⤢", "توسيع الودجت (F)", self.toggle_expand)
        self.btn_snooze = self._tool_button("⏰", "تأجيل 30 دقيقة", self.ctl.snooze)
        self.btn_close = self._tool_button("✕", "إخفاء (Esc)", self.hide_widget)
        
        hl = QHBoxLayout(self.header)
        hl.setContentsMargins(10, 4, 6, 4)
        hl.setSpacing(4)
        hl.addWidget(self.title)
        hl.addWidget(self.counts)
        hl.addStretch(1)
        hl.addWidget(self.btn_settings)
        hl.addWidget(self.btn_snooze)
        hl.addWidget(self.btn_expand)
        hl.addWidget(self.btn_anki)
        hl.addWidget(self.btn_close)

        # ---- محتوى البطاقة (AnkiWebView)
        self.web = AnkiWebView(self, title="zad widget")
        self.web.set_bridge_command(self._on_bridge, self)
        self.web.requiresCol = False
        self.web.stdHtml(
            web.BODY,
            head=f"<style>{web.CSS}</style>",
            context=self,
        )

        # ---- شريط المقبض السفلي (للسحب وتغيير الحجم بصرياً)
        self.footer = QFrame(self)
        self.footer.setObjectName("zadFooter")
        self.footer.setFixedHeight(12)
        fl = QHBoxLayout(self.footer)
        fl.setContentsMargins(2, 0, 2, 0)
        fl.setSpacing(0)
        
        self.grip_left = QSizeGrip(self)
        self.grip_left.setFixedSize(12, 12)
        fl.addWidget(self.grip_left)
        fl.addStretch(1)
        self.grip_right = QSizeGrip(self)
        self.grip_right.setFixedSize(12, 12)
        fl.addWidget(self.grip_right)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(0)
        lay.addWidget(self.header)
        lay.addWidget(self.web, 1)
        lay.addWidget(self.footer)
        
        self.header.installEventFilter(self)
        self.restyle()
        self._show_idle()

    # ------------------------------------------------------------------ المظهر والأنماط
    def _tool_button(self, text: str, tip: str, slot: Callable) -> QToolButton:
        b = QToolButton(self.header)
        b.setText(text)
        b.setToolTip(tip)
        b.setAutoRaise(True)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.clicked.connect(lambda *_: slot())
        return b

    def restyle(self) -> None:
        night = theme_manager.night_mode
        bg = "#262c33" if night else "#f4ecd2"
        fg = "#e5e7eb" if night else "#3b2f0b"
        border = "#3b4350" if night else "#b8860b"
        footer_bg = "#1f2429" if night else "#ebdcb4"
        self.setStyleSheet(
            f"""
            ZadWidget {{
                border: 2px solid {border};
                border-radius: 8px;
                background: {bg};
            }}
            #zadHeader {{
                background: {bg};
                border-bottom: 1px solid {border};
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }}
            #zadHeader QLabel {{ color: {fg}; }}
            #zadHeader QToolButton {{
                color: {fg};
                font-size: 14px;
                font-weight: bold;
                padding: 2px 6px;
                border-radius: 4px;
            }}
            #zadHeader QToolButton:hover {{
                background: rgba(184, 134, 11, 0.25);
            }}
            #zadFooter {{
                background: {footer_bg};
                border-top: 1px solid {border};
                border-bottom-left-radius: 6px;
                border-bottom-right-radius: 6px;
            }}
            """
        )
        f = self.title.font()
        f.setBold(True)
        self.title.setFont(f)

    def apply_flags(self) -> None:
        flags = Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
        if self.ctl.cfg.get("always_on_top", True):
            flags |= Qt.WindowType.WindowStaysOnTopHint
        was_visible = self.isVisible()
        self.setWindowFlags(flags)
        if was_visible:
            self.show()

    # ------------------------------------------------------------------ التوسيع وتغيير الحجم
    def _current_screen(self):
        pos = self.ctl.state.get("pos")
        if pos:
            scr = QGuiApplication.screenAt(QPoint(int(pos[0]) + 20, int(pos[1]) + 20))
            if scr:
                return scr
        scr = QGuiApplication.screenAt(QCursor.pos())
        if scr:
            return scr
        return QApplication.primaryScreen()

    def toggle_expand(self) -> None:
        """التبديل بين الوضع الموسّع (شاشة عريضة للقراءة المريحة) والوضع المدمج."""
        screen = self._current_screen().availableGeometry()
        if self.is_expanded:
            # العودة إلى الحجم المدمج
            self.is_expanded = False
            self.btn_expand.setText("⤢")
            self.btn_expand.setToolTip("توسيع الودجت (F)")
            if self._pre_expand_geo and any(
                s.availableGeometry().contains(self._pre_expand_geo.topLeft())
                for s in QGuiApplication.screens()
            ):
                self.setGeometry(self._pre_expand_geo)
            else:
                w = int(self.ctl.state.get("width") or self.ctl.cfg.get("width", 460))
                h = int(self.ctl.state.get("height") or self.ctl.cfg.get("height", 540))
                self.resize(w, h)
        else:
            # التوسيع لشاشة عريضة مريحة
            self.is_expanded = True
            self._pre_expand_geo = self.geometry()
            self.btn_expand.setText("⤡")
            self.btn_expand.setToolTip("تصغير إلى الوضع المدمج (F)")

            target_w = min(820, screen.width() - 40)
            target_h = min(660, screen.height() - 60)

            # التمدد بسلاسة باتجاه مركز الشاشة أو انطلاقاً من موضع الودجت
            new_x = self.x() + self.width() - target_w
            new_y = self.y() + self.height() - target_h
            new_x = max(screen.left() + 20, min(new_x, screen.right() - target_w - 20))
            new_y = max(screen.top() + 20, min(new_y, screen.bottom() - target_h - 20))

            self.setGeometry(new_x, new_y, target_w, target_h)

    # ------------------------------------------------------------------ حساب الحواف وتغيير الحجم
    def _hit_edge(self, pt: QPoint) -> int:
        m = 8  # مساحة الحافة بالسنتيمترات/البكسل لالتقاط الفأرة
        edge = self.EDGE_NONE
        w, h = self.width(), self.height()
        if pt.x() <= m:
            edge |= self.EDGE_LEFT
        elif pt.x() >= w - m:
            edge |= self.EDGE_RIGHT
        if pt.y() <= m:
            edge |= self.EDGE_TOP
        elif pt.y() >= h - m:
            edge |= self.EDGE_BOTTOM
        return edge

    def _cursor_for_edge(self, edge: int) -> Qt.CursorShape:
        if edge in (self.EDGE_LEFT, self.EDGE_RIGHT):
            return Qt.CursorShape.SizeHorCursor
        if edge in (self.EDGE_TOP, self.EDGE_BOTTOM):
            return Qt.CursorShape.SizeVerCursor
        if edge in (self.EDGE_TOP | self.EDGE_LEFT, self.EDGE_BOTTOM | self.EDGE_RIGHT):
            return Qt.CursorShape.SizeFDiagCursor
        if edge in (self.EDGE_TOP | self.EDGE_RIGHT, self.EDGE_BOTTOM | self.EDGE_LEFT):
            return Qt.CursorShape.SizeBDiagCursor
        return Qt.CursorShape.ArrowCursor

    # ------------------------------------------------------------------ أحداث الفأرة
    def mouseDoubleClickEvent(self, e) -> None:
        """النقر المزدوج على شريط الرأس يوسع الودجت أو يصغره."""
        pos = e.position().toPoint() if hasattr(e, "position") else e.pos()
        if self.header.geometry().contains(pos):
            self.toggle_expand()
            return
        super().mouseDoubleClickEvent(e)

    def eventFilter(self, watched, event) -> bool:
        if watched == self.header and event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
                child = self.header.childAt(pos)
                if not isinstance(child, QToolButton):
                    wh = self.windowHandle()
                    if wh and hasattr(wh, "startSystemMove"):
                        try:
                            if wh.startSystemMove():
                                return True
                        except Exception:
                            pass
                    gp = event.globalPosition().toPoint() if hasattr(event, "globalPosition") else event.globalPos()
                    self._drag_pos = gp - self.frameGeometry().topLeft()
                    return True
        return super().eventFilter(watched, event)

    def mousePressEvent(self, e) -> None:
        pos = e.position().toPoint() if hasattr(e, "position") else e.pos()
        gp = e.globalPosition().toPoint() if hasattr(e, "globalPosition") else e.globalPos()
        edge = self._hit_edge(pos)

        if e.button() == Qt.MouseButton.LeftButton:
            if edge != self.EDGE_NONE:
                wh = self.windowHandle()
                if wh and hasattr(wh, "startSystemResize"):
                    edges = Qt.Edge(0)
                    if edge & self.EDGE_LEFT:
                        edges |= Qt.Edge.LeftEdge
                    if edge & self.EDGE_RIGHT:
                        edges |= Qt.Edge.RightEdge
                    if edge & self.EDGE_TOP:
                        edges |= Qt.Edge.TopEdge
                    if edge & self.EDGE_BOTTOM:
                        edges |= Qt.Edge.BottomEdge
                    try:
                        if wh.startSystemResize(edges):
                            return
                    except Exception:
                        pass
                # البديل اليدوي إن لم يُدعم من النظام
                self._resizing_edge = edge
                self._resize_start_mouse = gp
                self._resize_start_geo = self.geometry()
                return
            elif self.header.geometry().contains(pos):
                wh = self.windowHandle()
                if wh and hasattr(wh, "startSystemMove"):
                    try:
                        if wh.startSystemMove():
                            return
                    except Exception:
                        pass
                # بدء سحب النافذة يدوياً
                self._drag_pos = gp - self.frameGeometry().topLeft()
                return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e) -> None:
        pos = e.position().toPoint() if hasattr(e, "position") else e.pos()
        gp = e.globalPosition().toPoint() if hasattr(e, "globalPosition") else e.globalPos()

        # أثناء سحب الحافة لتغيير الحجم
        if self._resizing_edge != self.EDGE_NONE and self._resize_start_geo and self._resize_start_mouse:
            delta = gp - self._resize_start_mouse
            geo = QRect(self._resize_start_geo)
            min_w, min_h = self.minimumWidth(), self.minimumHeight()
            max_w, max_h = self.maximumWidth(), self.maximumHeight()

            if self._resizing_edge & self.EDGE_LEFT:
                new_w = max(min_w, min(max_w, geo.width() - delta.x()))
                geo.setLeft(geo.right() - new_w)
            elif self._resizing_edge & self.EDGE_RIGHT:
                new_w = max(min_w, min(max_w, geo.width() + delta.x()))
                geo.setWidth(new_w)

            if self._resizing_edge & self.EDGE_TOP:
                new_h = max(min_h, min(max_h, geo.height() - delta.y()))
                geo.setTop(geo.bottom() - new_h)
            elif self._resizing_edge & self.EDGE_BOTTOM:
                new_h = max(min_h, min(max_h, geo.height() + delta.y()))
                geo.setHeight(new_h)

            self.setGeometry(geo)
            return

        # أثناء نقل النافذة
        elif self._drag_pos is not None:
            self.move(gp - self._drag_pos)
            return

        # تغيير المؤشر عند الاقتراب من الحواف
        else:
            edge = self._hit_edge(pos)
            self.setCursor(self._cursor_for_edge(edge))

        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e) -> None:
        if self._resizing_edge != self.EDGE_NONE:
            self._resizing_edge = self.EDGE_NONE
            self._resize_start_mouse = None
            self._resize_start_geo = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            if not self.is_expanded:
                self.ctl.remember_size(self.width(), self.height())
                self.ctl.remember_position(self.x(), self.y())
        elif self._drag_pos is not None:
            self._drag_pos = None
            if not self.is_expanded:
                self.ctl.remember_position(self.x(), self.y())
        super().mouseReleaseEvent(e)

    def leaveEvent(self, e) -> None:
        self.setCursor(Qt.CursorShape.ArrowCursor)
        super().leaveEvent(e)

    # ------------------------------------------------------------------ تموضع النافذة
    def place(self) -> None:
        """ضبط حجم وموقع الودجت مع تذكر الحجم المخصص الذي اختاره المستخدم."""
        if self.is_expanded:
            return  # الإبقاء على الوضع الموسع إن كان مفعلاً

        cfg = self.ctl.cfg
        saved_w = self.ctl.state.get("width")
        saved_h = self.ctl.state.get("height")
        w = int(saved_w or cfg.get("width", 460))
        h = int(saved_h or cfg.get("height", 540))
        self.resize(w, h)

        screen = self._current_screen()
        geo = screen.availableGeometry()
        pos = self.ctl.state.get("pos")
        if pos:
            pt = QPoint(int(pos[0]), int(pos[1]))
            for scr in QGuiApplication.screens():
                if scr.availableGeometry().contains(pt + QPoint(20, 20)):
                    self.move(int(pos[0]), int(pos[1]))
                    return
        corner = cfg.get("corner", "bottom-right")
        m = 18
        x = geo.right() - w - m if "right" in corner else geo.left() + m
        y = geo.bottom() - h - m if "bottom" in corner else geo.top() + m
        self.move(x, y)

    def show_widget(self) -> None:
        self._hide_timer.stop()
        self.place()
        self.show()
        self.raise_()

    def hide_widget(self) -> None:
        self._hide_timer.stop()
        av_player.stop_and_clear_queue()
        old_state = self.state
        self.state = "idle"
        self.fetched = None
        self.quiz = None
        self.hide()
        self.ctl.on_hidden(old_state)

    def closeEvent(self, e) -> None:
        e.ignore()
        self.hide_widget()

    def teardown(self) -> None:
        av_player.stop_and_clear_queue()
        self.web.cleanup()
        self.web.deleteLater()
        self.hide()
        self.deleteLater()

    # ------------------------------------------------------------------ عرض البطاقات
    def _bodyclass(self, card: Card) -> str:
        return theme_manager.body_classes_for_card_ord(card.ord)

    def _eval(self, **state) -> None:
        state.setdefault("fs", self.ctl.cfg.get("font_size", 17))
        self.web.eval(web.render_call(**state))

    def _show_idle(self) -> None:
        self.state = "idle"
        self._eval(qa="", bar="", bodyclass=theme_manager.body_class())

    def _munge(self, text: str, card: Card, kind: str) -> str:
        text = _TYPE_ANS.sub("", text)
        text = mw.prepare_card_text_for_display(text)
        return gui_hooks.card_will_show(text, card, kind)

    def present(self, fetched: engine.Fetched) -> None:
        """يعرض سؤال البطاقة التالية."""
        self.fetched = fetched
        card = fetched.card
        self.quiz = engine.parse_quiz(mw.col, card)
        self.state = "question"
        self._hide_timer.stop()
        self.update_header()

        tags = card.question_av_tags()
        av_player.stop_and_clear_queue()
        if self.ctl.cfg.get("autoplay_audio", True) and card.autoplay():
            self.web.setPlaybackRequiresGesture(False)
            av_player.play_tags(tags)
        else:
            self.web.setPlaybackRequiresGesture(True)

        if self.quiz:
            q = self.quiz
            self._eval(
                qa=f'<div class="zq">{q.question}</div>',
                opts=web.quiz_options(q.options),
                extra="",
                bar='<div class="zad-hint">اختر الإجابة الصحيحة</div>',
                bodyclass=self._bodyclass(card),
            )
        else:
            qtext = self._munge(card.question(), card, "reviewQuestion")
            self._eval(
                qa=qtext,
                opts="",
                extra="",
                bar=web.show_button(),
                bodyclass=self._bodyclass(card),
            )

    def update_header(self) -> None:
        f = self.fetched
        if not f:
            self.title.setText("زاد العلم")
            self.counts.setText("")
            return
        deck = mw.col.decks.name(f.card.did).split("::")[-1]
        self.title.setText(f"{deck}")
        self.counts.setText(
            f"  ● {engine.KIND_LABELS.get(f.kind, '')}"
            f"   جديدة {f.new_count} · تعلّم {f.learning_count} · مراجعة {f.review_count}"
        )

    def reveal(self, suggest: Optional[int] = None) -> None:
        if self.state != "question" or not self.fetched:
            return
        card = self.fetched.card
        self.state = "answer"
        atext = self._munge(card.answer(), card, "reviewAnswer")
        sounds = card.answer_av_tags()
        if self.ctl.cfg.get("autoplay_audio", True) and card.autoplay():
            av_player.stop_and_clear_queue()
            av_player.play_tags(sounds)
        self._eval(
            qa=atext,
            opts="",
            extra="",
            bar=web.rate_buttons(self.fetched.labels, suggest)
            + '<div class="zad-hint">1 أعد · 2 صعب · 3 جيد · 4 سهل</div>',
            bodyclass=self._bodyclass(card),
            scroll=True,
        )

    def _quiz_answer(self, idx: int) -> None:
        if self.state != "question" or not self.quiz or not self.fetched:
            return
        q = self.quiz
        ok = idx == q.correct
        self.state = "answer"
        suggest = engine.suggested_rating(ok)
        self._eval(
            qa=f'<div class="zq">{q.question}</div>',
            opts=web.quiz_options(q.options, chosen=idx, correct=q.correct),
            extra=web.quiz_feedback(
                ok, q.answer or q.options[q.correct], q.evidence, q.source
            ),
            bar=web.rate_buttons(self.fetched.labels, suggest)
            + '<div class="zad-hint">التقييم المقترح مُحدَّد — يمكنك تغييره</div>',
            bodyclass=self._bodyclass(self.fetched.card),
            scroll=True,
        )

    def show_done(self, message: str, can_next: bool, auto_hide_ms: int = 0) -> None:
        self.state = "done"
        self.fetched = None
        self.quiz = None
        self.update_header()
        self._eval(
            qa=web.done_screen(message, can_next),
            opts="",
            extra="",
            bar="",
            bodyclass=theme_manager.body_class(),
        )
        if auto_hide_ms:
            self._hide_timer.start(auto_hide_ms)

    # ------------------------------------------------------------------ جسر JS → Python
    def _on_bridge(self, cmd: str) -> bool:
        if cmd == "ans":
            if self.quiz and self.state == "question":
                return True
            self.reveal()
        elif cmd.startswith("ease:"):
            if self.state == "answer":
                self.ctl.answer(int(cmd.split(":")[1]))
        elif cmd.startswith("quiz:"):
            self._quiz_answer(int(cmd.split(":")[1]))
        elif cmd == "toggle_expand":
            self.toggle_expand()
        elif cmd.startswith("zoom:"):
            delta = 1 if cmd == "zoom:in" else -1
            cur_fs = int(self.ctl.cfg.get("font_size", 17))
            new_fs = max(12, min(36, cur_fs + delta))
            self.ctl.cfg["font_size"] = new_fs
            try:
                from .controller import ADDON_NAME
                raw = mw.addonManager.getConfig(ADDON_NAME) or {}
                raw["font_size"] = new_fs
                mw.addonManager.writeConfig(ADDON_NAME, raw)
            except Exception:
                pass
            self.web.eval(f"zadSetFont({new_fs});")
        elif cmd.startswith("play:"):
            self._play(cmd)
        elif cmd == "next":
            self.ctl.show_next_now()
        elif cmd == "close":
            self.hide_widget()
        return True

    def _play(self, cmd: str) -> None:
        if not self.fetched:
            return
        _, side, idx = cmd.split(":")
        card = self.fetched.card
        tags = card.question_av_tags() if side == "q" else card.answer_av_tags()
        i = int(idx)
        if 0 <= i < len(tags):
            av_player.play_tags([tags[i]])
