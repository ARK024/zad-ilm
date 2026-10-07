# -*- coding: utf-8 -*-
"""اختبارات منطق الإضافة على نواة أنكي الحقيقية (مجموعة مؤقتة حقيقية).

التشغيل:
    PYTHONPATH=vendor-scratch/pylibs:anki-addon python -m unittest discover -s anki-addon/tests -v
"""
import datetime as dt
import os
import tempfile
import unittest
from pathlib import Path

from anki.collection import Collection
from anki.import_export_pb2 import ImportAnkiPackageOptions, ImportAnkiPackageRequest

from zad_widget import engine

DECKS = Path(__file__).resolve().parents[1] / "zad_widget" / "decks"


def import_apkg(col: Collection, name: str):
    return col.import_anki_package(
        ImportAnkiPackageRequest(
            package_path=str(DECKS / name),
            options=ImportAnkiPackageOptions(
                merge_notetypes=True, with_scheduling=False, with_deck_configs=False
            ),
        )
    )


class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.col = Collection(os.path.join(cls.tmp.name, "collection.anki2"))
        import_apkg(cls.col, "zad_islamic_sciences.apkg")
        import_apkg(cls.col, "zad_hadith_cloze.apkg")

    @classmethod
    def tearDownClass(cls):
        cls.col.close()
        cls.tmp.cleanup()

    # ---- الاستيراد
    def test_imported_all_cards(self):
        self.assertGreaterEqual(self.col.card_count(), 44)
        names = {n.name for n in self.col.decks.all_names_and_ids()}
        self.assertTrue(any(n.startswith("زاد العلم::") for n in names), names)

    def test_notetypes_present(self):
        nts = {n.name for n in self.col.models.all_names_and_ids()}
        self.assertIn("زاد – اختبار مؤصل", nts)
        self.assertIn("زاد – بطاقة مؤصلة", nts)

    # ---- جلب وإجابة على طابور أنكي الحقيقي
    def test_fetch_and_answer_cycle(self):
        f = engine.fetch_next(self.col)
        self.assertIsNotNone(f)
        self.assertEqual(len(f.labels), 4)  # أعد/صعب/جيد/سهل بفواصل أنكي الحقيقية
        self.assertGreater(f.total_due, 0)
        cid = f.card.id
        before = f.total_due
        logs_before = self.col.db.scalar("select count() from revlog where cid=?", cid)
        ans = engine.build_answer(self.col, f, 3)
        self.col.sched.answer_card(ans)
        # البطاقة خرجت من الطابور (أو انتقلت لخطوة تعلّم لاحقة)
        nxt = engine.fetch_next(self.col)
        if nxt is not None:
            self.assertTrue(nxt.card.id != cid or nxt.kind == engine.KIND_LEARNING)
        self.assertEqual(
            self.col.db.scalar("select count() from revlog where cid=?", cid),
            logs_before + 1,
        )
        c = engine.counts(self.col)
        self.assertLessEqual(sum(c), before)

    def test_all_decks_scope_and_current_deck_restored(self):
        col = self.col
        other = col.decks.id("رزمة أخرى")
        nt = col.models.by_name("Basic")
        note = col.new_note(nt)
        note["Front"], note["Back"] = "سؤال", "جواب"
        col.add_note(note, other)
        col.decks.select(1)
        seen = set()
        import random as _r

        rng = _r.Random(7)
        for _ in range(60):
            f = engine.fetch_next(col, "", rng)
            self.assertIsNotNone(f)
            top = col.decks.name(f.card.did).split("::")[0]
            seen.add(top)
        self.assertEqual(seen, {"زاد العلم", "رزمة أخرى"})
        # لا نغيّر رزمة المستخدم الحالية
        self.assertEqual(int(col.decks.get_current_id()), 1)
        # المجموع يشمل الرزمتين ويحترم حد أنكي اليومي (20 جديدة لكل رزمة افتراضيًا)
        n, l, r = engine.counts(col)
        self.assertGreaterEqual(n + l + r, 20)
        self.assertEqual(int(col.decks.get_current_id()), 1)
        # الإجابة تعمل بعد إعادة الرزمة الحالية
        f = engine.fetch_next(col, "رزمة أخرى")
        lb = col.db.scalar("select count() from revlog where cid=?", f.card.id)
        col.sched.answer_card(engine.build_answer(col, f, 3))
        self.assertEqual(col.db.scalar("select count() from revlog where cid=?", f.card.id), lb + 1)

    def test_again_creates_learning_step(self):
        f = engine.fetch_next(self.col)
        engine.build_answer(self.col, f, 1)
        self.col.sched.answer_card(engine.build_answer(self.col, f, 1))
        card = self.col.get_card(f.card.id)
        self.assertEqual(card.queue, 1)  # QUEUE_TYPE_LRN

    def test_invalid_rating(self):
        f = engine.fetch_next(self.col)
        with self.assertRaises(ValueError):
            engine.build_answer(self.col, f, 9)

    # ---- الاختبار المؤصَّل
    def test_quiz_parse(self):
        cids = self.col.find_cards('"note:زاد – اختبار مؤصل"')
        self.assertGreater(len(cids), 0)
        quiz = engine.parse_quiz(self.col, self.col.get_card(cids[0]))
        self.assertIsNotNone(quiz)
        self.assertGreaterEqual(len(quiz.options), 2)
        self.assertTrue(0 <= quiz.correct < len(quiz.options))
        self.assertTrue(quiz.evidence)

    def test_undo_stack_not_polluted(self):
        col = self.col
        undo_before = col.undo_status().undo
        _ = engine.counts(col)
        self.assertEqual(col.undo_status().undo, undo_before)
        _ = engine.fetch_next(col)
        self.assertEqual(col.undo_status().undo, undo_before)

    def test_quiz_parse_with_blank_options_no_shift(self):
        cids = self.col.find_cards('"note:زاد – اختبار مؤصل"')
        self.assertGreater(len(cids), 0)
        card = self.col.get_card(cids[0])
        note = card.note()
        note["A"] = "خيار 1"
        note["B"] = ""  # فارغ
        note["C"] = "خيار 3 الصحيح"
        note["D"] = "خيار 4"
        note["Correct"] = "3"
        self.col.update_note(note)
        quiz = engine.parse_quiz(self.col, self.col.get_card(cids[0]))
        self.assertIsNotNone(quiz)
        self.assertEqual(len(quiz.options), 3)
        self.assertEqual(quiz.options[quiz.correct], "خيار 3 الصحيح")

    def test_flash_is_not_quiz(self):
        cids = self.col.find_cards('"note:زاد – بطاقة مؤصلة"')
        self.assertGreater(len(cids), 0)
        self.assertIsNone(engine.parse_quiz(self.col, self.col.get_card(cids[0])))

    def test_cloze_card_renders(self):
        cids = self.col.find_cards('"note:زاد – حفظ المتون (Cloze)"')
        self.assertGreaterEqual(len(cids), 8)  # 3+3+1+2 بطاقة من 4 متون
        card = self.col.get_card(cids[0])
        self.assertIn("[...]", card.question())
        self.assertIn("class=cloze", card.answer().replace('"', ""))

    def test_suggested_rating(self):
        self.assertEqual(engine.suggested_rating(True), 3)
        self.assertEqual(engine.suggested_rating(False), 1)

    def test_deck_scope(self):
        name = next(
            n.name for n in self.col.decks.all_names_and_ids() if n.name.startswith("زاد العلم::")
        )
        f = engine.fetch_next(self.col, name)
        self.assertIsNotNone(f)
        deck = self.col.decks.name(f.card.did)
        self.assertTrue(deck == name or deck.startswith(name + "::"), (deck, name))

    def test_resolve_deck_ids(self):
        col = self.col
        names = [n.name for n in col.decks.all_names_and_ids() if "::" not in n.name][:2]
        self.assertGreaterEqual(len(names), 2)
        dids = engine.resolve_deck_ids(col, names)
        self.assertEqual(len(dids), 2)
        # يحافظ على الترتيب الممرر بدقة
        self.assertEqual(col.decks.name(dids[0]), names[0])
        self.assertEqual(col.decks.name(dids[1]), names[1])
        # دعم الاسم المنفرد كنص
        single_did = engine.resolve_deck_ids(col, names[0])
        self.assertEqual(single_did, [dids[0]])
        # مدخلات فارغة أو غير صالحة
        self.assertEqual(engine.resolve_deck_ids(col, ""), [])
        self.assertEqual(engine.resolve_deck_ids(col, ["رزمة غير موجودة مطلقا"]), [])

    def test_multi_deck_counts(self):
        col = self.col
        names = [n.name for n in col.decks.all_names_and_ids() if "::" not in n.name][:2]
        c1 = engine.counts(col, names[0])
        c2 = engine.counts(col, names[1])
        combined = engine.counts(col, names)
        self.assertEqual(combined, (c1[0] + c2[0], c1[1] + c2[1], c1[2] + c2[2]))

    def test_deck_by_deck_order(self):
        col = self.col
        d1_name = "زاد العلم::أصول الفقه"
        d2_name = "زاد العلم::الحديث ومصطلحه"

        # الترتيب [d1, d2] يفضل d1 دائمًا طالما به بطاقات مستحقة
        f1 = engine.fetch_next(col, [d1_name, d2_name], order_mode="deck_by_deck")
        self.assertIsNotNone(f1)
        self.assertEqual(col.decks.name(f1.card.did), d1_name)

        # الترتيب المعكوس [d2, d1] يفضل d2 دائمًا
        f2 = engine.fetch_next(col, [d2_name, d1_name], order_mode="deck_by_deck")
        self.assertIsNotNone(f2)
        self.assertEqual(col.decks.name(f2.card.did), d2_name)

        # الافتراضي بدون تمرير order_mode يجب أن يلتزم بترتيب القائمة (deck_by_deck)
        f_def1 = engine.fetch_next(col, [d1_name, d2_name])
        self.assertIsNotNone(f_def1)
        self.assertEqual(col.decks.name(f_def1.card.did), d1_name)

        f_def2 = engine.fetch_next(col, [d2_name, d1_name])
        self.assertIsNotNone(f_def2)
        self.assertEqual(col.decks.name(f_def2.card.did), d2_name)

    def test_mix_order_draws_from_both(self):
        col = self.col
        d1_name = "زاد العلم::العقيدة والتوحيد"
        d2_name = "زاد العلم::فقه العبادات"
        decks = [d1_name, d2_name]
        import random as _r
        rng = _r.Random(42)
        seen_decks = set()
        for _ in range(30):
            f = engine.fetch_next(col, decks, order_mode="mix", rng=rng)
            if f:
                seen_decks.add(col.decks.name(f.card.did))
        self.assertEqual(seen_decks, set(decks))


class PacingTests(unittest.TestCase):
    cfg = engine.merged_config({})

    def at(self, hh, mm=0):
        return dt.datetime(2026, 10, 5, hh, mm)

    def test_active_hours(self):
        self.assertFalse(engine.is_active(self.at(7, 59), self.cfg))
        self.assertTrue(engine.is_active(self.at(8, 0), self.cfg))
        self.assertTrue(engine.is_active(self.at(21, 59), self.cfg))
        self.assertFalse(engine.is_active(self.at(22, 0), self.cfg))

    def test_overnight_window(self):
        cfg = engine.merged_config({"active_from": "20:00", "active_to": "02:00"})
        self.assertTrue(engine.is_active(self.at(23), cfg))
        self.assertTrue(engine.is_active(self.at(1), cfg))
        self.assertFalse(engine.is_active(self.at(12), cfg))
        self.assertEqual(engine.minutes_left_in_window(self.at(23), cfg), 180)

    def test_next_window_start(self):
        n = engine.next_window_start(self.at(23), self.cfg)
        self.assertEqual((n.day, n.hour, n.minute), (6, 8, 0))
        n = engine.next_window_start(self.at(6), self.cfg)
        self.assertEqual((n.day, n.hour), (5, 8))

    def test_interval_mode(self):
        self.assertEqual(engine.next_interval_seconds(self.cfg, self.at(10), 100, None), 20 * 60)

    def test_spread_mode(self):
        cfg = engine.merged_config({"mode": "spread"})
        # 12 ساعة متبقية / 36 بطاقة = 20 دقيقة
        self.assertEqual(engine.next_interval_seconds(cfg, self.at(10), 24, None), 30 * 60)
        # الحد الأدنى 3 دقائق
        self.assertEqual(engine.next_interval_seconds(cfg, self.at(10), 5000, None), 3 * 60)
        # الحد الأقصى 120 دقيقة
        self.assertEqual(engine.next_interval_seconds(cfg, self.at(10), 1, None), 120 * 60)
        # الحد اليومي يُقلّل المقسوم عليه
        self.assertEqual(engine.next_interval_seconds(cfg, self.at(10), 100, 4), 120 * 60)

    def test_bad_times_fall_back(self):
        cfg = engine.merged_config({"active_from": "abc", "active_to": "99:99"})
        self.assertEqual(engine.active_window(cfg), (8 * 60, 22 * 60))

    def test_day_counter(self):
        d1, d2 = dt.date(2026, 10, 5), dt.date(2026, 10, 6)
        c = engine.DayCounter.load({"date": d1.isoformat(), "shown": 7, "answered": 5}, d1)
        self.assertEqual(c.shown, 7)
        c.roll(d2)
        self.assertEqual((c.date, c.shown, c.answered), (d2.isoformat(), 0, 0))
        cfg = engine.merged_config({"daily_cap": 10})
        c.shown = 4
        self.assertEqual(c.remaining(cfg), 6)
        self.assertIsNone(c.remaining(engine.merged_config({})))

    def test_learning_bypass(self):
        class F:  # بطاقة تعلّم مستحقة
            kind = engine.KIND_LEARNING

        class R:
            kind = engine.KIND_REVIEW

        self.assertTrue(engine.should_bypass_interval(F(), self.cfg, 120))
        self.assertFalse(engine.should_bypass_interval(F(), self.cfg, 10))
        self.assertFalse(engine.should_bypass_interval(R(), self.cfg, 9999))
        self.assertFalse(engine.should_bypass_interval(None, self.cfg, 9999))
        off = engine.merged_config({"learning_priority": False})
        self.assertFalse(engine.should_bypass_interval(F(), off, 9999))

    def test_merged_config_decks_and_order(self):
        c1 = engine.merged_config({"decks": ["رزمة 1", "رزمة 2"], "order_mode": "deck_by_deck"})
        self.assertEqual(c1["decks"], ["رزمة 1", "رزمة 2"])
        self.assertEqual(c1["order_mode"], "deck_by_deck")

        # التوافق مع الإعداد القديم المنفرد deck
        c2 = engine.merged_config({"deck": "رزمة قديمة"})
        self.assertEqual(c2["decks"], ["رزمة قديمة"])
        self.assertEqual(c2["deck"], "رزمة قديمة")
        self.assertEqual(c2["order_mode"], "deck_by_deck")


if __name__ == "__main__":
    unittest.main()
