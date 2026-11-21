"""Pair features for the ML model. Built ONLY from allowlisted answers (via the rule engine's
criteria) plus listing context. No diet, work, days, name or hidden group can get in."""
import math

from ..engine import score_pair
from ..fairness import scorable

CRITERIA = ["budget", "area", "rental_type", "timing", "parking", "smoking", "pets", "tidy", "quiet",
            "chronotype", "social", "hobbies", "travel", "cooking", "repairs", "ideal_tenant", "ideal_landlord"]
TIDY = {"relaxed": 0, "reasonably": 1, "very": 2}
COOK = {"rarely_cook": 0, "light": 1, "strong": 2}
REPAIR = {"same_day": 0, "24h": 1, "week": 2, "no_pref": 3}

FEATURES = (
    [f"c_{k}" for k in CRITERIA]
    + ["rule_tenant_side", "rule_landlord_side", "rule_match_pct",
       "on_site", "shared_kitchen", "shared_entrance", "rent_to_budget",
       "t_tidy", "l_tidy", "tidy_gap", "t_quiet", "l_quiet", "noise_clash_on_site",
       "opposite_hours_on_site", "cook_gap_shared", "repair_gap", "t_smokes", "hobby_overlap"]
)


def pair_features(tenant: dict, listing: dict, result: dict | None = None) -> list[float] | None:
    """Feature vector for one pair, or None if the rule engine's hard filters removed it."""
    r = result or score_pair(tenant, listing)
    if r["filtered"]:
        return None
    t, ll = scorable(tenant), scorable(listing["landlord"])
    crit = r["breakdown"]["criteria"]
    on_site = float(listing.get("landlord_on_site", False))
    shared_k = float(listing.get("kitchen") == "shared")
    t_q, l_q = float(t.get("music") == "quiet"), float(ll.get("music") == "quiet")
    hours = {t.get("chronotype"), ll.get("chronotype")} == {"early", "night"}
    th, lh = set(t.get("hobbies") or []), set(ll.get("hobbies") or [])
    f = [crit.get(k, math.nan) for k in CRITERIA] + [
        r["breakdown"]["tenant_side_pct"] / 100, r["breakdown"]["landlord_side_pct"] / 100, r["match_pct"] / 100,
        on_site, shared_k, float(listing.get("entrance") == "shared"),
        listing["rent"] / t["budget"] if t.get("budget") else math.nan,
        TIDY.get(t.get("tidy"), math.nan), TIDY.get(ll.get("tidy"), math.nan),
        TIDY.get(ll.get("tidy"), 1) - TIDY.get(t.get("tidy"), 1),
        t_q, l_q, float(t_q != l_q) * on_site,
        float(hours) * on_site,
        abs(COOK.get(t.get("cooking_smells"), 1) - COOK.get(ll.get("cooking_smells"), 1)) * shared_k,
        REPAIR.get(ll.get("repair_speed"), 1) - REPAIR.get(t.get("repair_speed"), 1),
        float(t.get("smoking") in ("smoker", "outdoor_only")),
        len(th & lh) / max(1, min(len(th), len(lh))) if th and lh else 0.0,
    ]
    return f
