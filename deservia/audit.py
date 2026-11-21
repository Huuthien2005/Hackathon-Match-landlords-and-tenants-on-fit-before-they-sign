"""Fairness audit and launch metrics.

Audit: each synthetic person has a hidden `group` (stands in for a protected ground). The
scorer never sees it. We check that outcomes don't differ by group anyway, using the
four-fifths rule: each group's average number of good fits in its top 10 should be at least
80% of the best group's. We run it twice:
  safe   - the real engine
  unsafe - the same engine also scoring diet, days and work (the stand-ins on the live site)
"""
from collections import Counter, defaultdict
from statistics import mean

from .engine import GOOD_FIT, score_pair
from .fairness import check_text

UNSAFE_FIELDS = ("diet", "days", "work")


def _outcomes(tenants, listings, unsafe=()):
    per_group = defaultdict(list)
    all_scores = []
    for t in tenants:
        scores = sorted((s["match_pct"] for l in listings
                         if not (s := score_pair(t, l, _audit_unsafe=unsafe))["filtered"]), reverse=True)
        top = scores[:10]
        all_scores += top
        per_group[t.get("group", "?")].append({
            "best": top[0] if top else 0,
            "good_fits": sum(x >= GOOD_FIT for x in top),
        })
    return per_group, all_scores


def fairness_audit(tenants, listings):
    report = {}
    for mode, unsafe in (("safe", ()), ("unsafe", UNSAFE_FIELDS)):
        per_group, _ = _outcomes(tenants, listings, unsafe)
        groups = {}
        for g, rows in sorted(per_group.items()):
            groups[g] = {
                "tenants": len(rows),
                "avg_best_match": round(mean(r["best"] for r in rows), 1),
                "avg_good_fits_in_top10": round(mean(r["good_fits"] for r in rows), 2),
            }
        rates = [v["avg_good_fits_in_top10"] for v in groups.values()]
        ratio = round(min(rates) / max(rates), 3) if max(rates) else 1.0
        report[mode] = {"scored_extra_fields": list(unsafe), "groups": groups,
                        "disparate_impact_ratio": ratio, "passes_four_fifths_rule": ratio >= 0.8}
    return report


def launch_metrics(tenants, listings):
    """What Deservia's dashboard would show from day one."""
    per_group, scores = _outcomes(tenants, listings)
    rows = [r for g in per_group.values() for r in g]
    fired = Counter()
    for p in tenants + [l["landlord"] for l in listings]:
        for e in check_text(p.get("ideal_text", ""))["excluded"]:
            for g in e["ground"].split(", "):
                fired[g] += 1
    buckets = Counter(min(s // 10 * 10, 90) for s in scores)
    return {
        "tenants": len(tenants), "listings": len(listings),
        "share_with_1_to_3_plus_good_fits_in_top10": round(mean(r["good_fits"] >= 1 for r in rows), 3),
        "avg_good_fits_in_top10": round(mean(r["good_fits"] for r in rows), 2),
        "avg_best_match": round(mean(r["best"] for r in rows), 1),
        "score_histogram_top10": {f"{k}-{k + 9}": buckets[k] for k in sorted(buckets)},
        "text_filter_fired_by_ground": dict(fired),
        "target": "1-3 good fits (>=80%) in each tenant's top 10, best matches near 98%",
    }
