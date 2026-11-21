"""Shared request handling used by both servers (api.py = FastAPI, server.py = no dependencies)."""
from functools import lru_cache

from .audit import fairness_audit, launch_metrics
from .data import DEMO_LISTINGS, DEMO_TENANTS, generate
from .engine import rank
from .fairness import NOT_SCORED, check_text

from pathlib import Path

TENANTS = {t["id"]: t for t in DEMO_TENANTS}
DB = Path(__file__).resolve().parents[1] / "data" / "deservia.db"


def _population():
    """Audit/metrics sample: 600 tenants x 100 listings from the dataset if present, else generated.
    (Smaller samples are noisy: at 200 tenants the ratio wobbles around 0.8 by chance.)"""
    if DB.exists():
        from .dataset import load
        t, l, _ = load(DB)
        return t[:600], l[:100]
    return generate()


SYN_TENANTS, SYN_LISTINGS = _population()


def list_tenants():
    return [{"id": t["id"], "name": t["name"], "profile": t} for t in DEMO_TENANTS]


def list_listings():
    return DEMO_LISTINGS


def match(body: dict):
    """body: {"tenant_id": "t_demo"} or {"tenant": {...full profile...}}, optional "limit"."""
    tenant = body.get("tenant") or TENANTS.get(body.get("tenant_id", ""))
    if not tenant:
        raise KeyError("Unknown tenant: send tenant_id or a tenant profile")
    result = rank(tenant, DEMO_LISTINGS, limit=int(body.get("limit", 10)))
    return result


def check(body: dict):
    out = check_text(body.get("text", ""))
    out["note"] = "Excluded phrases never reach the score. Kept phrases are checked against the other side's answers."
    return out


def model_card():
    import json
    from pathlib import Path
    p = Path(__file__).resolve().parents[1] / "models" / "model_card.json"
    return json.loads(p.read_text()) if p.exists() else {"detail": "No model trained yet: run python train.py"}


@lru_cache(maxsize=1)
def audit():
    return fairness_audit(SYN_TENANTS, SYN_LISTINGS)


@lru_cache(maxsize=1)
def metrics():
    return {**launch_metrics(SYN_TENANTS, SYN_LISTINGS), "not_scored_fields": NOT_SCORED}


# ======================================================================= swipe deck + learning
# Matching pool = the whole dataset (1,000 listings / 5,000 tenants) + the demo records.
from . import feedback as fb
from .engine import _scoring_view, score_pair
from .fairness import check_text
from .options import AREA_TO_REGION, RENTAL_TYPES


def _load_pool():
    if DB.exists():
        from .dataset import load
        t, l, _ = load(DB)
    else:
        t, l = generate(1000, 300, seed=42)
    return {x["id"]: x for x in DEMO_TENANTS + t}, {x["id"]: x for x in DEMO_LISTINGS + l}


ALL_TENANTS, ALL_LISTINGS = _load_pool()
_profiles = {}        # user_id -> latest tenant profile sent by the front end
_shown = {}           # (user_id, item_id) -> what was on the card, for the feedback row


def profiles(role):
    """Who you can swipe as: demo records first, then a sample from the dataset."""
    if role == "landlord":
        items = DEMO_LISTINGS[:10] + [l for l in ALL_LISTINGS.values() if l["id"].startswith("s_")][:20]
        return [{"id": l["id"], "label": f'{l["title"]} · {l["area"]} · ${l["rent"]}'} for l in items]
    items = DEMO_TENANTS + [t for t in ALL_TENANTS.values() if t["id"].startswith("s_")][:20]
    return [{"id": t["id"], "label": t.get("name") or f'Tenant {t["id"]} · {t["area"]} · ${t["budget"]}',
             "profile": t} for t in items]


# "in common" labels are written from the tenant's side; reword them for a landlord's view
_LANDLORD_WORDS = {"Your pet is welcome": "Their pet fits your pet policy", "Fits your budget": "Rent fits their budget",
                   "Parking for your car": "Parking for their car", "Move-in timing lines up": "Move-in timing lines up"}


def _tenant_card(t, r):
    """What a landlord sees about a tenant: lifestyle only. No name, diet, work, days, or
    anything that could reveal a protected ground (a service animal shows as 'loves pets')."""
    v = _scoring_view(t)
    L = {"very": "Very tidy", "reasonably": "Reasonably tidy", "relaxed": "Relaxed about tidiness",
         "quiet": "Prefers a quiet home", "love_music": "Enjoys music at home",
         "early": "Early riser", "night": "Night owl", "introvert": "Introvert", "extrovert": "Extrovert",
         "non_smoker": "Non-smoker", "outdoor_only": "Smokes outdoors only", "smoker": "Smoker",
         "love_pets": "Loves pets", "have_pet": {"dog": "Has a dog", "cat": "Has a cat", "small": "Has a small pet"}.get(v.get("pet_kind"), "Has a pet"), "prefer_no_pets": "Prefers no pets"}
    tags = [L[x] for x in (v.get("tidy"), v.get("music"), v.get("chronotype"), v.get("smoking"), v.get("pets"))
            if x in L] + [f"• {h}" for h in (v.get("hobbies") or [])[:2]]
    kept = check_text(t.get("ideal_text", ""))["kept"]
    return {"name": f'Tenant in {t.get("area", "?")}',
            "rental_type": f'Wants: {RENTAL_TYPES.get(t.get("rental_type"), "")}',
            "area": t.get("area"), "price": t.get("budget"), "price_label": "budget",
            "description": ("Looking for a landlord who is " + ", ".join(kept)) if kept else "", "tags": tags}


def deck(body):
    """Next `limit` cards for a user, best first, skipping anything they already swiped.
    body: {role: 'tenant'|'landlord', user_id, tenant?: {...}, limit?: 10}"""
    from .ml import personal
    from .ml.features import pair_features
    from .ml.model import predict_success

    role, user_id, limit = body.get("role", "tenant"), body.get("user_id"), int(body.get("limit", 10))
    seen = fb.swiped_ids(user_id, role)

    if role == "tenant":
        me = body.get("tenant") or _profiles.get(user_id) or ALL_TENANTS.get(user_id)
        if not me:
            raise KeyError("Unknown tenant")
        _profiles[user_id] = me
        pairs = [(me, l) for lid, l in ALL_LISTINGS.items() if lid not in seen]
    else:
        me = ALL_LISTINGS.get(user_id)
        if not me:
            raise KeyError("Unknown listing")
        region = AREA_TO_REGION.get(me["area"])
        pairs = [(t, me) for tid, t in ALL_TENANTS.items() if tid not in seen
                 and AREA_TO_REGION.get(t.get("area")) == region]

    scored = [(t, l, r) for t, l in pairs if not (r := score_pair(t, l))["filtered"]]
    scored.sort(key=lambda x: -x[2]["match_pct"])
    scored = scored[:max(60, limit * 4)]                       # ML re-ranks the strongest candidates
    feats = [pair_features(t, l, r) for t, l, r in scored]
    ml = predict_success(scored) or [None] * len(scored)
    pers_model = personal.fit(user_id)
    pers = personal.predict(pers_model, feats) or [None] * len(scored)

    cards = []
    for (t, l, r), f, p_ml, p_me in zip(scored, feats, ml, pers):
        parts = [(0.5, r["match_pct"])]
        if p_ml is not None:
            parts.append((0.5, p_ml * 100))
        if p_me is not None:
            parts = [(0.4, r["match_pct"]), (0.4, (p_ml if p_ml is not None else r["match_pct"] / 100) * 100),
                     (0.2, p_me * 100)]
        score = sum(w * v for w, v in parts) / sum(w for w, _ in parts)
        item_id = l["id"] if role == "tenant" else t["id"]
        card = {"item_id": item_id, "match_pct": r["match_pct"], "good_fit": r["good_fit"],
                "ml_success_pct": None if p_ml is None else round(p_ml * 100),
                "personal_like_pct": None if p_me is None else round(p_me * 100),
                "rank_score": round(score, 1), "in_common": r["in_common"],
                "in_common_count": r["in_common_count"], "flags": r["flags"],
                "excluded": r["excluded"], "notes": r["notes"] if role == "tenant" else []}
        if role == "tenant":
            card.update(name=r["name"], area=r["area"], rental_type=r["rental_type"], price=r["price"],
                        price_label="/mo", description=r["description"], tags=r["tags"])
        else:
            card.update(_tenant_card(t, r))
            card["in_common"] = [_LANDLORD_WORDS.get(x, x) for x in card["in_common"]]
        cards.append(card)
        _shown[(user_id, item_id)] = (role, t["id"], l["id"], f, r["match_pct"], card["ml_success_pct"])
    cards.sort(key=lambda c: -c["rank_score"])
    return {"cards": cards[:limit], "remaining": max(0, len(scored) - limit),
            "learned": personal.explain(pers_model), "swipes": fb.counts(user_id),
            "blend": "40% match + 40% AI + 20% your swipes" if pers_model else "50% match + 50% AI"}


def swipe(body):
    """body: {user_id, item_id, liked: true/false}"""
    key = (body.get("user_id"), body.get("item_id"))
    if key not in _shown:
        raise KeyError("Card not found: fetch a deck first")
    role, tid, lid, feats, mpct, mlpct = _shown[key]
    fb.add(key[0], role, tid, lid, bool(body.get("liked")), feats, mpct, mlpct)
    return {"saved": True, "swipes": fb.counts(key[0]), "all_users": fb.counts()}


def retrain(_body=None):
    from .ml import retrain as rt
    return rt.start()


def learning_status():
    from .ml import retrain as rt
    from .ml.model import load
    m = load()
    return {**rt.status, "live_model_version": m.get("version") if m else None,
            "feedback_in_live_model": m.get("feedback_rows") if m else 0, "all_swipes": fb.counts()}


def reset_feedback(body):
    fb.reset(body.get("user_id"))
    return {"reset": True, "all_swipes": fb.counts()}
