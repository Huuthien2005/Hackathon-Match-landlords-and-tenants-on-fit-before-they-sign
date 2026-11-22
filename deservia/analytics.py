"""What the agent (website owner) sees: how matching is performing across users."""
from collections import Counter, defaultdict
from statistics import mean

from . import auth, feedback as fb
from .fairness import check_text


def _avg(xs):
    xs = [x for x in xs if x is not None]
    return round(mean(xs), 1) if xs else None


def overview():
    from . import service
    from .ml import personal

    users = auth.list_users()
    by_pool = {u["pool_id"]: u for u in users if u["pool_id"]}
    rows = fb.all_rows()
    likes = [r for r in rows if r["liked"]]
    passes = [r for r in rows if not r["liked"]]

    # Do higher match scores get more likes? (the core "is matching working" signal)
    buckets = defaultdict(lambda: [0, 0])
    for r in rows:
        if r["match_pct"] is not None:
            b = min(90, max(50, r["match_pct"] // 10 * 10))
            buckets[b][0] += 1
            buckets[b][1] += r["liked"]
    like_rate_by_match = [{"bucket": f"{b}–{b + 9 if b < 90 else 100}%", "swipes": n,
                           "like_rate": round(k / n, 3) if n else 0} for b, (n, k) in sorted(buckets.items())]

    mutual = []
    for tid, lid, pct in fb.mutual_pairs():
        t, l = by_pool.get(tid), by_pool.get(lid)
        listing = service.ALL_LISTINGS.get(lid, {})
        mutual.append({"tenant": t["email"] if t else tid, "landlord": l["email"] if l else lid,
                       "home": listing.get("title", lid), "match_pct": pct})

    per_user, flagged = [], []
    swipes_by_user = Counter(r["user_id"] for r in rows)
    likes_by_user = Counter(r["user_id"] for r in likes)
    mutual_by = Counter([m[0] for m in fb.mutual_pairs()] + [m[1] for m in fb.mutual_pairs()])
    for u in users:
        if u["role"] == "agent":
            continue
        pid = u["pool_id"]
        learned = personal.explain(personal.fit(pid)) if swipes_by_user[pid] >= personal.MIN_SWIPES else []
        per_user.append({"email": u["email"], "role": u["role"], "plan": u.get("plan", "free"), "profile_done": bool(u["answers"]),
                         "swipes": swipes_by_user[pid], "likes": likes_by_user[pid], "mutual_matches": mutual_by[pid],
                         "learned": [x["words"] for x in learned]})
        for e in check_text((u["answers"] or {}).get("ideal_text", ""))["excluded"]:
            flagged.append({"email": u["email"], "role": u["role"], "text": e["text"], "ground": e["ground"]})

    return {
        "kpis": {
            "tenants": sum(u["role"] == "tenant" for u in users),
            "landlords": sum(u["role"] == "landlord" for u in users),
            "profiles_done": sum(bool(u["answers"]) for u in users if u["role"] != "agent"),
            "swipes": len(rows), "likes": len(likes),
            "like_rate": round(len(likes) / len(rows), 3) if rows else None,
            "mutual_matches": len(mutual),
            "paid_members": sum(u.get("plan", "free") != "free" for u in users if u["role"] != "agent"),
            "pool_homes": len(service.ALL_LISTINGS), "pool_tenants": len(service.ALL_TENANTS),
        },
        "like_rate_by_match": like_rate_by_match,
        "liked_vs_passed": {"avg_match_liked": _avg(r["match_pct"] for r in likes),
                            "avg_match_passed": _avg(r["match_pct"] for r in passes),
                            "avg_ai_liked": _avg(r["ml_success_pct"] for r in likes),
                            "avg_ai_passed": _avg(r["ml_success_pct"] for r in passes)},
        "by_role": {role: {"swipes": sum(r["role"] == role for r in rows),
                           "likes": sum(r["role"] == role and r["liked"] for r in rows)} for role in ("tenant", "landlord")},
        "mutual": mutual,
        "users": per_user,
        "flagged_text": flagged,
        "flagged_by_ground": dict(Counter(g for f in flagged for g in f["ground"].split(", "))),
        "model": service.learning_status(),
    }
