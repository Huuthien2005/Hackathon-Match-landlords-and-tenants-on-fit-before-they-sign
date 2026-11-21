"""Run:  python -m unittest discover tests"""
import copy
import unittest

from deservia.audit import fairness_audit
from deservia.data import DEMO_LISTINGS, DEMO_TENANTS, generate
from deservia.engine import rank, score_pair
from deservia.fairness import check_text

ALEX, SAM = DEMO_TENANTS
MAPLE = DEMO_LISTINGS[0]


class FairnessTests(unittest.TestCase):
    def test_protected_phrase_is_excluded_and_reported(self):
        r = check_text("quiet, tidy, no kids please, no ODSP")
        self.assertEqual(r["kept"], ["quiet", "tidy"])
        grounds = {e["ground"] for e in r["excluded"]}
        self.assertIn("family status", grounds)
        self.assertIn("receipt of public assistance", grounds)

    def test_protected_phrase_does_not_change_score(self):
        clean = copy.deepcopy(ALEX); clean["ideal_text"] = "quiet, tidy"
        dirty = copy.deepcopy(ALEX); dirty["ideal_text"] = "quiet, tidy, no kids, Canadians only, under 30"
        for l in DEMO_LISTINGS:
            a, b = score_pair(clean, l), score_pair(dirty, l)
            if not a["filtered"]:
                self.assertEqual(a["match_pct"], b["match_pct"], l["id"])

    def test_not_scored_fields_never_change_score(self):
        for field, values in {"diet": ["vegan", "no_restrictions"], "work": ["student", "employed"],
                              "days": ["work_from_home", "out"], "name": ["A", "B"]}.items():
            scores = set()
            for v in values:
                t = copy.deepcopy(ALEX); t[field] = v
                scores.add(score_pair(t, MAPLE)["match_pct"])
            self.assertEqual(len(scores), 1, field)

    def test_service_animal_is_not_a_pet(self):
        no_pets = next(l for l in DEMO_LISTINGS if l["pet_policy"] == "none" and l["id"] != "l12")
        self.assertFalse(score_pair(SAM, no_pets)["filtered"])
        pet_owner = copy.deepcopy(SAM); pet_owner["service_animal"] = False
        self.assertTrue(score_pair(pet_owner, no_pets)["filtered"])

    def test_common_words_are_not_flagged(self):
        r = check_text("close to transit, tidy, communicative, older building is fine with me")
        self.assertIn("close to transit", r["kept"])

    def test_audit_passes_safe_and_catches_unsafe(self):
        t, l = generate(n_tenants=120, n_listings=40)
        a = fairness_audit(t, l)
        self.assertTrue(a["safe"]["passes_four_fifths_rule"])
        self.assertFalse(a["unsafe"]["passes_four_fifths_rule"])


class MatchingTests(unittest.TestCase):
    def test_ranked_and_explained(self):
        r = rank(ALEX, DEMO_LISTINGS, use_model=False)      # rule ranking; ML re-rank tested in test_ml
        pcts = [m["match_pct"] for m in r["matches"]]
        self.assertEqual(pcts, sorted(pcts, reverse=True))
        self.assertGreaterEqual(r["good_fits_in_top"], 1)
        self.assertGreaterEqual(pcts[0], 95)
        self.assertTrue(r["matches"][0]["in_common"])

    def test_over_budget_filtered_and_near_budget_flagged(self):
        r = rank(ALEX, DEMO_LISTINGS)
        self.assertIn("l11", [f["listing_id"] for f in r["filtered_out"]])
        spring = next(m for m in r["matches"] if m["listing_id"] == "l04")
        self.assertTrue(any("over budget" in f for f in spring["flags"]))

    def test_mismatch_scores_low(self):
        party = next(l for l in DEMO_LISTINGS if l["id"] == "l05")
        self.assertLess(score_pair(ALEX, party)["match_pct"], 65)

    def test_two_way_needs_both_sides(self):
        m = score_pair(ALEX, MAPLE)["breakdown"]
        self.assertLessEqual(m["tenant_side_pct"] * m["landlord_side_pct"] / 100, 100)

    def test_dealbreaker(self):
        t = copy.deepcopy(ALEX); t["importance"] = {"quiet": "dealbreaker"}
        party = next(l for l in DEMO_LISTINGS if l["id"] == "l05")
        self.assertTrue(score_pair(t, party)["filtered"])


if __name__ == "__main__":
    unittest.main()
