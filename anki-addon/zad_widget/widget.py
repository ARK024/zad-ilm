# -*- coding: utf-8 -*-
"""نافذة الودجت العائمة (Qt) — تعرض بطاقة أنكي الحقيقية بقالبها الأصلي."""
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


def _qs(name: str, *parts):
    """مختصر لقيم Qt المتوافقة مع PyQt5/6."""
    obj = Qt
    for p in (name, *parts):
        obj = getattr(obj, p)
    return obj


class ZadWidget(QWidget):
    """نافذة صغيرة بلا إطار تبقى فوق النوافذ ولا تسرق التركيز عند ظهورها."""

    def __init__(self, controller) -> None:
        super().__init__(None)
        self.ctl = controller
        self.fetched: Optional[engine.Fetched] = None
        self.quiz: Optional[engine.Quiz] = None
        self.state = "idle"  # idle | question | answer | done
        self._drag: Optional[QPoint] = None
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide_widget)

        self.setWindowTitle("زاد العلم")
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.apply_flags()

        # ---- الرأس (للسحب)
        self.header = QFrame(self)
        self.header.setObjectName("zadHeader")
        self.title = QLabel("زاد العلم", self.header)
        self.counts = QLabel("", self.header)
        self.btn_open = self._tool_button("⤢", "فتح نافذة أنكي الرئيسية", self.ctl.open_main)
        self.btn_snooze = self._tool_button("⏰", "تأجيل", self.ctl.snooze)
        self.btn_close = self._tool_button("✕", "إخفاء (Esc)", self.hide_widget)
        hl = QHBoxLayout(self.header)
        hl.setContentsMargins(10, 4, 6, 4)
        hl.addWidget(self.title)
        hl.addWidget(self.counts)
        hl.addStretch(1)
        hl.addWidget(self.btn_snooze)
        hl.addWidget(self.btn_open)
        hl.addWidget(self.btn_close)

        # ---- المحتوى
        self.web = AnkiWebView(self, title="zad widget")
        self.web.set_bridge_command(self._on_bridge, self)
        self.web.requiresCol = False
        self.web.stdHtml(
            web.BODY,
            head=f"<style>{web.CSS}</style>",
            context=self,
        )

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.header)
        lay.addWidget(self.web, 1)
        self.restyle()
        self._show_idle()

    # ------------------------------------------------------------------ مظهر
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
        self.setStyleSheet(
            f"""
            ZadWidget {{ border: 1px solid {border}; }}
            #zadHeader {{ background: {bg}; }}
            #zadHeader QLabel {{ color: {fg}; }}
            #zadHeader QToolButton {{ color: {fg}; font-size: 15px; padding: 2px 6px; }}
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

    # ------------------------------------------------------------------ نافذة
    def place(self) -> None:
        cfg = self.ctl.cfg
        w, h = int(cfg.get("width", 460)), int(cfg.get("height", 540))
        self.resize(w, h)
        screen = QApplication.primaryScreen()
        geo = screen.availableGeometry()
        pos = self.ctl.state.get("pos")
        if pos and geo.contains(QPoint(int(pos[0]) + 20, int(pos[1]) + 20)):
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
        self.hide()
        self.ctl.on_hidden(self.state)

    def mousePressEvent(self, e) -> None:  # سحب النافذة من الرأس
        if e.button() == Qt.MouseButton.LeftButton and self.header.geometry().contains(
            e.position().toPoint() if hasattr(e, "position") else e.pos()
        ):
            gp = e.globalPosition().toPoint() if hasattr(e, "globalPosition") else e.globalPos()
            self._drag = gp - self.frameGeometry().topLeft()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e) -> None:
        if self._drag is not None:
            gp = e.globalPosition().toPoint() if hasattr(e, "globalPosition") else e.globalPos()
            self.move(gp - self._drag)
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e) -> None:
        if self._drag is not None:
            self._drag = None
            self.ctl.remember_position(self.x(), self.y())
        super().mouseReleaseEvent(e)

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
                return True  # في الاختبار يجب اختيار إجابة أولًا
            self.reveal()
        elif cmd.startswith("ease:"):
            if self.state == "answer":
                self.ctl.answer(int(cmd.split(":")[1]))
        elif cmd.startswith("quiz:"):
            self._quiz_answer(int(cmd.split(":")[1]))
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
