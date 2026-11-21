"""Builds the training matrix from the dataset's tenancies table, with a disk cache so a
retrain after each swipe round takes seconds instead of re-scoring 65,000 pairs."""
import json
from collections import Counter
from pathlib import Path

import numpy as np

from ..dataset import load
from ..engine import score_pair
from .features import pair_features

CACHE = Path(__file__).resolve().parents[2] / "models" / "train_cache.npz"


def build_dataset(source):
    """Read tenants, listings and labelled tenancies; turn each tenancy into a feature row."""
    tenants, listings, tenancies = load(source)
    T = {t["id"]: t for t in tenants}
    L = {l["id"]: l for l in listings}
    X, y, groups, hidden, rule = [], [], [], [], []
    skipped = 0
    for row in tenancies:
        t, l = T.get(row["tenant_id"]), L.get(row["listing_id"])
        if t is None or l is None:
            skipped += 1
            continue
        r = score_pair(t, l)
        f = pair_features(t, l, r)
        if f is None:
            skipped += 1
            continue
        X.append(f); y.append(row["outcome"]); groups.append(row["tenant_id"])
        hidden.append(t.get("group") == "B"); rule.append(r["match_pct"] / 100)
    info = {"source": str(source), "tenants": len(tenants), "listings": len(listings),
            "tenancies": len(tenancies), "used": len(y), "skipped": skipped,
            "dispute_reasons": dict(Counter(r["dispute_reason"] for r in tenancies if not r["outcome"]))}
    return np.array(X, float), np.array(y), np.array(groups), np.array(hidden), np.array(rule), info


def save_cache(X, y, groups, hidden, rule, info):
    CACHE.parent.mkdir(exist_ok=True)
    np.savez_compressed(CACHE, X=X, y=y, groups=groups, hidden=hidden, rule=rule, info=np.array([json.dumps(info)]))


def load_cache(source):
    """Cached matrix if it's newer than the dataset file, else rebuild and cache."""
    src = Path(source)
    if CACHE.exists() and (not src.exists() or CACHE.stat().st_mtime >= src.stat().st_mtime):
        d = np.load(CACHE, allow_pickle=False)
        info = json.loads(str(d["info"][0]))
        return d["X"], d["y"], d["groups"], d["hidden"], d["rule"], info
    out = build_dataset(source)
    save_cache(*out)
    return out
