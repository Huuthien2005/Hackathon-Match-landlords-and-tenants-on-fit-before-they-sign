"""Matching engine: hard filters -> per-criterion satisfaction -> two-way percent -> explanation.

match % = sqrt(tenant_satisfaction x landlord_satisfaction) x 100
Each side's satisfaction is the importance-weighted average of how well the OTHER side meets
the criteria that side cares about. The geometric mean means a match must work for both:
100% one way and 20% the other gives 45%, not 60%.
"""
from math import sqrt

from .fairness import check_text, scorable, NOT_SCORED
from .options import AREA_TO_REGION, IMPORTANCE, RENTAL_TYPES
from .traits import parse_ideal

BUDGET_MARGIN = 0.10          # up to 10% over budget is shown with a flag, beyond that filtered
GOOD_FIT = 80                 # percent at which we call a match a "good fit"

# Default importance per criterion for each side (users can override per criterion).
DEFAULT_IMPORTANCE = {
    # Lifestyle carries most of the weight: "we match on how you live".
    "tenant": {"budget": 10, "area": 3, "rental_type": 5, "timing": 2, "parking": 3,
               "smoking": 5, "pets": 5, "tidy": 10, "quiet": 10, "chronotype": 5, "social": 3,
               "hobbies": 3, "travel": 1, "cooking": 5, "repairs": 5, "ideal": 10},
    "landlord": {"timing": 2, "smoking": 10, "pets": 5, "tidy": 10, "quiet": 10, "chronotype": 5,
                 "social": 3, "hobbies": 3, "travel": 1, "cooking": 5, "ideal": 10},
}
LIFESTYLE = {"smoking", "pets", "tidy", "quiet", "chronotype", "social", "hobbies", "travel", "cooking"}

LABELS = {"early": "Both early risers", "night": "Both night owls",
          "introvert": "Both enjoy a calm, private home", "extrovert": "Both friendly and social",
          "very": "Both very tidy", "reasonably": "Both reasonably tidy",
          "homebody": "Both homebodies", "love_travel": "Both love to travel"}


def _ordinal(a, b, scale):
    return 1 - abs(scale.index(a) - scale.index(b)) / (len(scale) - 1)


def _weights(side: str, profile: dict) -> dict:
    w = dict(DEFAULT_IMPORTANCE[side])
    for k, v in (profile.get("importance") or {}).items():
        w[k] = IMPORTANCE.get(v, 3) if isinstance(v, str) else v
    return w


def _scoring_view(tenant: dict) -> dict:
    """Allowlisted copy of the tenant. A service animal is not a pet: if it is the only animal,
    the tenant is scored as having no pet (the 'have_pet' answer is neutralised)."""
    t = scorable(tenant)
    t["role"] = "tenant"
    if tenant.get("service_animal") and t.get("pets") == "have_pet":
        t["pets"], t["pet_kind"] = "love_pets", None
    return t


def _pet_policy_ok(policy: str, kind: str | None) -> bool:
    return {"welcome": True, "none": False, "cats_only": kind == "cat",
            "dogs_only": kind == "dog", "small_only": kind in ("small", "cat")}.get(policy, True)


def score_pair(tenant_raw: dict, listing: dict, _audit_unsafe: tuple = ()) -> dict:
    """Score one tenant against one listing. Returns the card payload plus a full breakdown.

    _audit_unsafe is ONLY for audit.py: it deliberately scores not-allowed fields (e.g. diet)
    to show the bias that appears when you do. Never pass it from the API."""
    t = _scoring_view(tenant_raw)
    ll = scorable(listing["landlord"])
    ll["role"] = "landlord"
    for f in _audit_unsafe:
        t[f], ll[f] = tenant_raw.get(f), listing["landlord"].get(f)
    on_site = listing.get("landlord_on_site", False)
    shared_kitchen = listing.get("kitchen") == "shared"
    rent, budget = listing["rent"], t.get("budget")

    excluded, flags, notes = [], [], []

    # ---------- Hard filters (dealbreakers) ----------
    def reject(reason):
        return {"listing_id": listing["id"], "filtered": True, "reason": reason}

    if budget and rent > budget * (1 + BUDGET_MARGIN):
        return reject(f"Rent ${rent} is more than 10% over budget ${budget}")
    if listing.get("bedrooms", 1) < t.get("bedrooms_needed", 0):
        return reject("Not enough bedrooms")
    if tenant_raw.get("service_animal"):
        notes.append("Service/support animal: treated as an accommodation, never as a pet.")
    if t.get("pets") == "have_pet" and not _pet_policy_ok(listing.get("pet_policy", "welcome"), t.get("pet_kind")):
        return reject("Pet policy does not allow the tenant's pet")
    if t.get("smoking") == "smoker" and listing.get("smoke_policy") == "non_smoking":
        return reject("Non-smoking home")

    # ---------- Free text: fairness filter, then trait checks ----------
    t_text = check_text(tenant_raw.get("ideal_text", ""))
    l_text = check_text(listing["landlord"].get("ideal_text", ""))
    excluded += [{**e, "from": "tenant"} for e in t_text["excluded"]]
    excluded += [{**e, "from": "landlord"} for e in l_text["excluded"]]

    # ---------- Criteria: name -> (satisfaction 0..1, in-common label or None) ----------
    c = {}
    if budget:
        c["budget"] = (1.0, "Fits your budget") if rent <= budget else \
            (1 - (rent - budget) / (budget * BUDGET_MARGIN), None)
        if rent > budget:
            flags.append(f"${rent - budget} over budget")
    if t.get("area"):
        region = AREA_TO_REGION.get(t["area"])
        same_region = region is not None and region == AREA_TO_REGION.get(listing["area"])
        c["area"] = (1.0, f"In {listing['area']}") if t["area"] == listing["area"] else \
            ((0.6, None) if same_region else (0.1, None))
    if t.get("rental_type"):
        c["rental_type"] = (1.0, None) if t["rental_type"] == listing["rental_type"] else (0.3, None)
    if t.get("timing"):
        tt, lt = t["timing"], listing.get("timing", "flexible")
        c["timing"] = (1.0, "Move-in timing lines up") if tt == lt or "flexible" in (tt, lt) else (0.4, None)
    if t.get("drive") == "drives":
        p = listing.get("parking", "none")
        c["parking"] = {"none": (0.0, None), "street": (0.5, None)}.get(p, (1.0, "Parking for your car"))
        if p == "none":
            flags.append("No parking")

    ts, ls_ = t.get("smoking"), ll.get("smoking")
    policy = listing.get("smoke_policy", "non_smoking")
    if ts == "non_smoker" and policy == "non_smoking":
        c["smoking"] = (1.0, "Smoke-free home")
    elif ts == "outdoor_only" and policy == "non_smoking":
        c["smoking"] = (0.5, None)
        flags.append("Tenant smokes outdoors; home is non-smoking")
    elif ts == "non_smoker" and ls_ == "smoker" and on_site:
        c["smoking"] = (0.3, None)
    elif ts:
        c["smoking"] = (0.7, None)

    tp, lp = t.get("pets"), ll.get("pets")
    if tp == "have_pet":
        c["pets"] = (1.0, "Your pet is welcome") if lp != "prefer_no_pets" else (0.5, None)
    elif tp == "prefer_no_pets" and lp == "have_pet" and on_site:
        c["pets"] = (0.3, None)
    elif tp == "love_pets" and lp in ("love_pets", "have_pet") and listing.get("pet_policy") != "none":
        c["pets"] = (1.0, "Both pet lovers")
    elif tp:
        c["pets"] = (0.9, None)

    if t.get("tidy") and ll.get("tidy"):
        # tenant at least as tidy as the landlord = full marks
        scale = ["relaxed", "reasonably", "very"]
        s = 1.0 if scale.index(t["tidy"]) >= scale.index(ll["tidy"]) else _ordinal(t["tidy"], ll["tidy"], scale)
        c["tidy"] = (s, LABELS.get(t["tidy"]) if t["tidy"] == ll["tidy"] and t["tidy"] != "relaxed" else None)
    if t.get("music") and ll.get("music"):
        c["quiet"] = (1.0, "Both prefer a quiet home" if t["music"] == "quiet" else "Both enjoy music at home") \
            if t["music"] == ll["music"] else (0.3, None)
    if t.get("chronotype") and ll.get("chronotype"):
        a, b = t["chronotype"], ll["chronotype"]
        c["chronotype"] = (1.0, LABELS.get(a) if a != "flexible" else None) if a == b else \
            ((0.7, None) if "flexible" in (a, b) else (0.2, None))
    if t.get("social") and ll.get("social"):
        a, b = t["social"], ll["social"]
        c["social"] = (1.0, LABELS.get(a)) if a == b else ((0.75, None) if "both" in (a, b) else (0.4, None))
    if t.get("travel") and ll.get("travel"):
        c["travel"] = (1.0, LABELS[t["travel"]]) if t["travel"] == ll["travel"] else (0.6, None)
    th, lh = set(t.get("hobbies") or []), set(ll.get("hobbies") or [])
    if th and lh:
        common = sorted(th & lh)
        c["hobbies"] = (min(1.0, len(common) / min(len(th), len(lh))),
                        f"Both into {', '.join(common[:2])}" if common else None)
    if shared_kitchen and t.get("cooking_smells") and ll.get("cooking_smells"):
        c["cooking"] = (_ordinal(t["cooking_smells"], ll["cooking_smells"], ["rarely_cook", "light", "strong"]),
                        "Similar kitchen habits" if t["cooking_smells"] == ll["cooking_smells"] else None)
    exp, com = t.get("repair_speed"), ll.get("repair_speed")
    if exp and com:
        order = ["same_day", "24h", "week", "no_pref"]
        ok = exp == "no_pref" or order.index(com) <= order.index(exp)
        c["repairs"] = (1.0, "Repairs " + {"same_day": "same day", "24h": "within 24 hours",
                                          "week": "within a week", "no_pref": "as needed"}[com]) if ok else (0.4, None)

    # Ideal words, each direction scored against the other side's real answers
    t_ideal = parse_ideal(t_text["kept"], ll)
    l_ideal = parse_ideal(l_text["kept"], t)
    for who, parsed in (("tenant", t_ideal), ("landlord", l_ideal)):
        checked = [p for p in parsed if p["satisfied"] is not None]
        if checked:
            met = [p["trait"] for p in checked if p["satisfied"]]
            c[f"ideal_{who}"] = (len(met) / len(checked),
                                  f"Matches '{', '.join(met[:2])}'" if met else None)
    unverifiable = [p["trait"] for p in t_ideal + l_ideal if p["satisfied"] is None]
    if unverifiable:
        notes.append(f"Not scorable yet, confirmed later by ratings: {', '.join(sorted(set(unverifiable)))}")

    for f in _audit_unsafe:                   # audit-only: what if we scored a stand-in field?
        if t.get(f) and ll.get(f):
            c[f] = (1.0 if t[f] == ll[f] else 0.2, None)

    # ---------- Two-way weighting ----------
    wt, wl = _weights("tenant", tenant_raw), _weights("landlord", listing["landlord"])
    for f in _audit_unsafe:
        wt[f] = wl[f] = 10

    def side_score(weights, side):
        num = den = 0.0
        for name, (s, _) in c.items():
            key = "ideal" if name.startswith("ideal_") else name
            if name.startswith("ideal_") and name != f"ideal_{side}":
                continue                      # each side's ideal words count only for that side
            w = weights.get(key, 0)
            if key in LIFESTYLE and not on_site:
                w *= 0.7                      # lifestyle matters less when landlord lives elsewhere
            if w >= IMPORTANCE["dealbreaker"] and s < 0.5:
                return None                   # user-marked dealbreaker not met
            num, den = num + w * s, den + w
        return num / den if den else 1.0

    st, sl = side_score(wt, "tenant"), side_score(wl, "landlord")
    if st is None or sl is None:
        return reject("A criterion marked 'dealbreaker' is not met")

    pct = round(sqrt(st * sl) * 100)
    # lifestyle things first (that's the point of the card), then practical ones
    order = lambda kv: (kv[0] not in LIFESTYLE and not kv[0].startswith("ideal_"),
                        -(wt.get(kv[0], 0) + wl.get(kv[0], 0)))
    in_common = [lab for name, (s, lab) in sorted(c.items(), key=order) if lab and s >= 0.95]

    return {
        "listing_id": listing["id"], "filtered": False,
        "name": listing["title"], "area": listing["area"],
        "rental_type": RENTAL_TYPES.get(listing["rental_type"], listing["rental_type"]),
        "price": rent, "description": listing.get("description", ""),
        "match_pct": pct, "good_fit": pct >= GOOD_FIT,
        "in_common": in_common[:5], "in_common_count": len(in_common),
        "tags": _tags(listing), "flags": flags, "excluded": excluded, "notes": notes,
        "breakdown": {
            "tenant_side_pct": round(st * 100), "landlord_side_pct": round(sl * 100),
            "criteria": {k: round(v[0], 2) for k, v in c.items()},
        },
    }


def _tags(listing: dict) -> list[str]:
    """Card tags. Never diet, never anything touching a protected ground."""
    ll = listing["landlord"]
    tags = [{"non_smoking": "Non-smoking", "outside_only": "Smoking outside only",
             "allowed": "Smoking allowed"}.get(listing.get("smoke_policy"), "")]
    tags.append({"welcome": "Pets welcome", "none": "No pets", "cats_only": "Cats only",
                 "dogs_only": "Dogs only", "small_only": "Small pets only"}.get(listing.get("pet_policy"), ""))
    tags.append({"early": "Early riser", "night": "Night owl"}.get(ll.get("chronotype"), ""))
    tags.append("Quiet home" if ll.get("music") == "quiet" else "")
    tags += [f"• {h}" for h in (ll.get("hobbies") or [])[:2]]
    return [x for x in tags if x]


def rank(tenant: dict, listings: list[dict], limit: int = 10, use_model: bool = True) -> dict:
    """Rank listings for one tenant. Filtered listings are reported, not hidden, so an agent
    can see why something didn't show up."""
    scored = [score_pair(tenant, l) for l in listings]
    matches = sorted([s for s in scored if not s["filtered"]], key=lambda s: -s["match_pct"])
    if use_model:                              # ML re-rank when a trained model is present
        from .ml.model import rerank
        matches = rerank(tenant, {l["id"]: l for l in listings}, matches)
    return {
        "tenant_id": tenant.get("id"),
        "matches": matches[:limit],
        "good_fits_in_top": sum(m["good_fit"] for m in matches[:limit]),
        "ranked_by": "50% match + 50% predicted smooth tenancy (ML)" if matches and "ml_success_pct" in matches[0]
                     else "match % (rule score)",
        "filtered_out": [s for s in scored if s["filtered"]],
        "not_scored": {k: v for k, v in NOT_SCORED.items() if tenant.get(k) not in (None, False, "")},
    }
