"""Swipe -> feedback -> personal model -> next deck. Uses a temporary feedback database."""
import tempfile
import unittest
from pathlib import Path

from deservia import feedback as fb


class LearningLoopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._real_db = fb.DB
        fb.DB = Path(tempfile.mkdtemp()) / "fb.db"
        from deservia import service
        cls.s = service

    @classmethod
    def tearDownClass(cls):
        fb.DB = cls._real_db

    def setUp(self):
        fb.reset()

    def _deck(self, role="tenant", user="s_t000"):
        body = {"role": role, "user_id": user}
        if role == "tenant":
            body["tenant"] = self.s.ALL_TENANTS[user]
        return self.s.deck(body)

    def test_deck_has_ten_ranked_cards(self):
        d = self._deck()
        self.assertEqual(len(d["cards"]), 10)
        scores = [c["rank_score"] for c in d["cards"]]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_swiped_cards_do_not_come_back(self):
        first = self._deck()["cards"]
        for c in first:
            self.s.swipe({"user_id": "s_t000", "item_id": c["item_id"], "liked": True})
        second = {c["item_id"] for c in self._deck()["cards"]}
        self.assertFalse(second & {c["item_id"] for c in first})
        self.assertEqual(fb.counts("s_t000")["swipes"], 10)

    def test_personal_model_turns_on_and_learns(self):
        d = self._deck()
        for c in d["cards"]:      # this user only likes homes with no warnings
            self.s.swipe({"user_id": "s_t000", "item_id": c["item_id"], "liked": not c["flags"] and c["match_pct"] >= 92})
        d2 = self._deck()
        self.assertIn("your swipes", d2["blend"])
        self.assertIsNotNone(d2["cards"][0]["personal_like_pct"])

    def test_landlord_cards_hide_stand_ins(self):
        d = self._deck("landlord", next(i for i, l in self.s.ALL_LISTINGS.items() if l["area"] == "Brampton"))
        self.assertTrue(d["cards"])
        text = str(d["cards"]).lower()
        for banned in ("vegan", "vegetarian", "student", "work_from_home", "hidden", "service"):
            self.assertNotIn(banned, text)

    def test_swipe_without_deck_is_rejected(self):
        with self.assertRaises(KeyError):
            self.s.swipe({"user_id": "nobody", "item_id": "x", "liked": True})


if __name__ == "__main__":
    unittest.main()
