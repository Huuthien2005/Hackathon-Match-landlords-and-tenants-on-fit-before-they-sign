"""Simulated tenancy outcomes, a STAND-IN for real labels.

There is no real outcome data this weekend (real applicant data is off limits). So we simulate
"did the first 12 months go smoothly?" from lifestyle clashes that commonly turn into LTB
disputes: noise, cleanliness, smoking, rent stretch (arrears), slow repairs, kitchen friction.
The model then has to learn these patterns, including interactions the hand-made rule score
doesn't know (e.g. noise clashes matter far more when the landlord lives on site with a
shared entrance).

The simulator never looks at the hidden group, diet, work, days or name.

In the build phase this file is REPLACED by real labels: two-way ratings ("Paid on time",
"Cared for the home", "Quick repairs"), conduct reports, early lease ends and LTB filings.
"""
import math
import random

TIDY = {"relaxed": 0, "reasonably": 1, "very": 2}
REPAIR = {"same_day": 0, "24h": 1, "week": 2, "no_pref": 3}


def risk_terms(tenant: dict, listing: dict) -> dict:
    """Each clash's contribution to dispute risk (log-odds). Used for the label and its reason."""
    ll = listing["landlord"]
    on_site = listing.get("landlord_on_site", False)
    shared_entry = listing.get("entrance") == "shared"
    shared_kitchen = listing.get("kitchen") == "shared"
    t = {}
    if tenant.get("music") != ll.get("music"):
        t["noise"] = 1.7 * (1.5 if shared_entry else 1.0) if on_site else 0.3
    gap = TIDY.get(ll.get("tidy"), 1) - TIDY.get(tenant.get("tidy"), 1)
    if gap >= 1:
        t["cleanliness"] = 1.4 if gap >= 2 else 0.5
    if tenant.get("smoking") in ("smoker", "outdoor_only") and ll.get("smoking") == "non_smoker" and on_site:
        t["smoking"] = 1.0
    stretch = listing["rent"] / tenant["budget"] if tenant.get("budget") else 1.0
    if stretch > 0.95:
        t["rent_arrears"] = 12 * (stretch - 0.95)
    if on_site and {tenant.get("chronotype"), ll.get("chronotype")} == {"early", "night"}:
        t["schedule"] = 0.8
    if shared_kitchen and {tenant.get("cooking_smells"), ll.get("cooking_smells")} == {"rarely_cook", "strong"}:
        t["kitchen"] = 0.9
    expects, gives = REPAIR.get(tenant.get("repair_speed"), 3), REPAIR.get(ll.get("repair_speed"), 1)
    if expects < 3 and gives - expects >= 2:
        t["repairs"] = 1.0
    if tenant.get("pets") == "prefer_no_pets" and ll.get("pets") == "have_pet" and on_site:
        t["pets"] = 0.6
    return t


def dispute_probability(tenant: dict, listing: dict) -> float:
    z = -2.3 + sum(risk_terms(tenant, listing).values())
    common = set(tenant.get("hobbies") or []) & set(listing["landlord"].get("hobbies") or [])
    z -= 0.25 * min(len(common), 2)
    return 1 / (1 + math.exp(-z))


def simulate_outcome(tenant: dict, listing: dict, rng: random.Random, with_reason: bool = False):
    """1 = smooth tenancy (no dispute in 12 months), 0 = dispute / arrears / early exit.
    with_reason=True also returns the main cause of a dispute ('none' if smooth)."""
    p = dispute_probability(tenant, listing)
    p = min(0.98, max(0.02, p + rng.gauss(0, 0.05)))
    outcome = int(rng.random() > p)
    if not with_reason:
        return outcome
    terms = risk_terms(tenant, listing)
    reason = "none" if outcome else (max(terms, key=terms.get) if terms else "other")
    return outcome, reason
