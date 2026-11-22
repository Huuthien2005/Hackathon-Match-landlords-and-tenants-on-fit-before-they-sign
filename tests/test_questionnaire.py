"""Typed ("Other") answers: mapped when clear, kept-but-unscored when not, refused when they
describe who someone is."""
import unittest

from deservia.auth import _landlord_answers, _tenant_answers
from deservia.data import DEMO_LISTINGS, DEMO_TENANTS
from deservia.engine import score_pair
from deservia.questionnaire import describe, to_listing, to_tenant, validate


def tenant(**changes):
    a = _tenant_answers(DEMO_TENANTS[0])
    for k, v in changes.items():
        if v is None:
            a.pop(k, None)
        else:
            a[k] = v
    return a


class TypedAnswerTests(unittest.TestCase):
    def test_clear_typed_answer_is_mapped_and_scored(self):
        c, e = validate("tenant", tenant(chronotype=None, chronotype_other="I'm up at 5am every day"))
        self.assertEqual(e, [])
        self.assertEqual(c["chronotype"], "early")
        row = next(r for r in describe("tenant", c) if r["id"] == "chronotype")
        self.assertIn("Matched as", row["used"])

    def test_unclear_typed_answer_is_kept_but_not_scored(self):
        c, e = validate("tenant", tenant(cooking_smells=None, cooking_smells_other="dumplings on weekends"))
        self.assertEqual(e, [])
        self.assertNotIn("cooking_smells", c)
        self.assertEqual(c["cooking_smells_other"], "dumplings on weekends")
        row = next(r for r in describe("tenant", c) if r["id"] == "cooking_smells")
        self.assertIn("not used", row["used"])

    def test_typed_answer_about_who_someone_is_is_refused(self):
        for text in ("Muslim household", "no kids", "Canadians only", "young professional"):
            _, e = validate("tenant", tenant(social=None, social_other=text))
            self.assertTrue(e and "who someone is" in e[0], text)

    def test_typed_area_and_rental_type(self):
        c, e = validate("tenant", tenant(area="bolton", rental_type=None, rental_type_other="a condo"))
        self.assertEqual(e, [])
        self.assertEqual(c["area"], "Bolton")
        self.assertEqual(c["rental_type"], "apartment")
        c2, _ = validate("tenant", tenant(area="brampton"))
        self.assertEqual(c2["area"], "Brampton")             # case-insensitive match to the list

    def test_typed_hobbies_match_each_other(self):
        c, _ = validate("tenant", tenant(hobbies=[], hobbies_other=["Pickleball", "gym"]))
        self.assertIn("Fitness", c["hobbies"])                 # "gym" -> Fitness
        t = to_tenant("u_1", c)
        self.assertIn("Pickleball", t["hobbies"])

    def test_typed_landlord_answers_build_a_listing(self):
        a = _landlord_answers(DEMO_LISTINGS[0])
        a.pop("parking"); a["parking_other"] = "driveway fits two cars"
        a.pop("pet_policy"); a["pet_policy_other"] = "we'll talk about it"   # unclear -> engine default
        c, e = validate("landlord", a)
        self.assertEqual(e, [])
        l = to_listing("ul_1", c)
        self.assertEqual(l["parking"], "two_plus")
        self.assertNotIn("pet_policy", l)
        r = score_pair(to_tenant("u_1", validate("tenant", tenant())[0]), l)
        self.assertFalse(r["filtered"])

    def test_typed_answer_satisfies_required_question(self):
        c, e = validate("tenant", tenant(tidy=None, tidy_other="I clean every Sunday"))
        self.assertEqual(e, [])
        _, e2 = validate("tenant", tenant(tidy=None))
        self.assertTrue(any("tidy" in x for x in e2))


if __name__ == "__main__":
    unittest.main()
