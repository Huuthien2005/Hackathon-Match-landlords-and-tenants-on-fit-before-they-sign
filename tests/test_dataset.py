"""Dataset tests: CSV and SQLite round-trip without changing any score."""
import tempfile
import unittest
from pathlib import Path

from deservia.data import generate
from deservia.dataset import load, write_csv, write_sqlite
from deservia.engine import score_pair


class DatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.tenants, cls.listings = generate(40, 15, seed=3)
        cls.tenancies = [{"tenant_id": t["id"], "listing_id": l["id"], "start_date": "2024-01-01",
                          "outcome": i % 2, "dispute_reason": "none" if i % 2 else "noise"}
                         for i, (t, l) in enumerate(zip(cls.tenants, cls.listings))]
        write_csv(cls.tmp / "csv", cls.tenants, cls.listings, cls.tenancies)
        write_sqlite(cls.tmp / "d.db", cls.tenants, cls.listings, cls.tenancies)

    def test_csv_and_sqlite_load_the_same(self):
        self.assertEqual(load(self.tmp / "csv"), load(self.tmp / "d.db"))

    def test_round_trip_keeps_every_score(self):
        tenants, listings, tenancies = load(self.tmp / "d.db")
        self.assertEqual(len(tenancies), len(self.tenancies))
        for t0, t1 in zip(self.tenants, tenants):
            for l0, l1 in zip(self.listings, listings):
                a, b = score_pair(t0, l0), score_pair(t1, l1)
                self.assertEqual(a.get("match_pct"), b.get("match_pct"))
                self.assertEqual(a["filtered"], b["filtered"])

    def test_types_are_restored(self):
        t, l, x = load(self.tmp / "d.db")
        self.assertIsInstance(t[0]["budget"], int)
        self.assertIsInstance(t[0]["hobbies"], list)
        self.assertIsInstance(l[0]["landlord_on_site"], bool)
        self.assertIn(x[0]["outcome"], (0, 1))

    def test_hidden_group_never_reaches_scorer(self):
        from deservia.fairness import scorable
        t, _, _ = load(self.tmp / "d.db")
        self.assertNotIn("group", scorable(t[0]))


if __name__ == "__main__":
    unittest.main()
