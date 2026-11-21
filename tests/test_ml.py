"""ML tests. Skipped if scikit-learn or the trained model is missing (run python train.py)."""
import copy
import json
import unittest
from pathlib import Path

from deservia.data import DEMO_LISTINGS, DEMO_TENANTS
from deservia.engine import rank
from deservia.ml.features import FEATURES, pair_features
from deservia.ml.model import MODEL_PATH, predict_success

ALEX = DEMO_TENANTS[0]
CARD = MODEL_PATH.parent / "model_card.json"


@unittest.skipUnless(MODEL_PATH.exists(), "no trained model")
class ModelTests(unittest.TestCase):
    def test_no_protected_or_stand_in_features(self):
        banned = ("diet", "work", "days", "name", "group", "service_animal", "age", "family")
        self.assertFalse([f for f in FEATURES if any(b in f for b in banned)])

    def test_stand_in_fields_do_not_change_prediction(self):
        l = DEMO_LISTINGS[0]
        preds = set()
        for diet, work, days in [("vegan", "student", "work_from_home"), ("no_restrictions", "employed", "out")]:
            t = copy.deepcopy(ALEX); t.update(diet=diet, work=work, days=days, group="B")
            preds.add(round(predict_success([(t, l, rank(t, [l], use_model=False)["matches"][0])])[0], 6))
        self.assertEqual(len(preds), 1)

    def test_rank_attaches_prediction_and_blends(self):
        r = rank(ALEX, DEMO_LISTINGS)
        self.assertIn("ml_success_pct", r["matches"][0])
        scores = [m["rank_score"] for m in r["matches"]]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_noise_clash_on_site_lowers_success(self):
        quiet_l = copy.deepcopy(DEMO_LISTINGS[0])
        loud_l = copy.deepcopy(DEMO_LISTINGS[0]); loud_l["landlord"]["music"] = "love_music"
        pq, pl = (predict_success([(ALEX, l, rank(ALEX, [l], use_model=False)["matches"][0])])[0]
                  for l in (quiet_l, loud_l))
        self.assertLess(pl, pq)

    def test_model_beats_rules_and_is_fair(self):
        c = json.loads(CARD.read_text())
        r = c["results"]
        self.assertGreater(r["gradient_boosting"]["auc"], r["rule_score_only"]["auc"])
        self.assertGreater(r["gradient_boosting"]["precision_at_k"], r["random_ranking_precision_at_k"])
        self.assertTrue(c["fairness"]["passes_four_fifths_rule"])
        self.assertLess(c["fairness"]["group_leakage_auc"], 0.6)

    def test_filtered_pairs_have_no_features(self):
        self.assertIsNone(pair_features(ALEX, DEMO_LISTINGS[10]))   # over budget


if __name__ == "__main__":
    unittest.main()
