"""Train the match model from the dataset files.

    python generate_dataset.py          # once: writes data/deservia.db + data/*.csv
    python train.py                     # trains from data/deservia.db
    python train.py --data data         # ...or from the CSV folder

Learns P(smooth tenancy | tenant, listing) from pair features, then:
  - compares it with the hand-made rule score and logistic regression,
  - checks it on tenants it never saw (split by tenant, not by pair),
  - checks fairness: can the features predict the hidden group? do top-10s differ by group?
  - saves models/match_model.joblib and models/model_card.json
"""
import argparse
import json
from collections import Counter
from pathlib import Path

import joblib
import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from deservia.ml.features import FEATURES
from deservia.ml.trainset import build_dataset, save_cache

OUT = Path(__file__).parent / "models"
GOOD = 0.80   # predicted success >= 80% counts as a good fit
K = 3         # each tenant has ~13 past tenancies in the data, so we judge their top 3


def precision_at_k(scores, y, groups, k=K):
    """Average share of smooth tenancies among each tenant's top-k ranked listings."""
    vals = []
    for g in np.unique(groups):
        idx = np.where(groups == g)[0]
        if len(idx) >= k:
            top = idx[np.argsort(-scores[idx])[:k]]
            vals.append(y[top].mean())
    return float(np.mean(vals))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/deservia.db", help="data/deservia.db or a folder of CSVs")
    a = ap.parse_args()
    if not Path(a.data).exists():
        raise SystemExit(f"{a.data} not found. Run: python generate_dataset.py")
    print(f"Loading dataset from {a.data} ...")
    X, y, groups, hidden, rule, info = build_dataset(a.data)
    save_cache(X, y, groups, hidden, rule, info)      # lets swipe-feedback retrains start in seconds
    print(f"  {info['tenants']} tenants, {info['listings']} listings, {info['tenancies']} tenancies "
          f"-> {len(y)} training rows, smooth rate {y.mean():.2f}")

    tr, te = next(GroupShuffleSplit(test_size=0.2, random_state=0).split(X, y, groups))
    models = {
        "logistic_regression": make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                                             LogisticRegression(max_iter=2000)),
        "gradient_boosting": CalibratedClassifierCV(
            HistGradientBoostingClassifier(max_iter=300, learning_rate=0.06, max_leaf_nodes=24,
                                           l2_regularization=1.0, random_state=0),
            method="isotonic", cv=3),
    }
    results = {"rule_score_only": {
        "auc": round(roc_auc_score(y[te], rule[te]), 3),
        "precision_at_k": round(precision_at_k(rule[te], y[te], groups[te]), 3)}}
    print("  rule score only:", results["rule_score_only"])
    for name, m in models.items():
        m.fit(X[tr], y[tr])
        p = m.predict_proba(X[te])[:, 1]
        results[name] = {"auc": round(roc_auc_score(y[te], p), 3),
                         "brier": round(brier_score_loss(y[te], p), 4),
                         "precision_at_k": round(precision_at_k(p, y[te], groups[te]), 3)}
        print(f"  {name}:", results[name])
    results["random_ranking_precision_at_k"] = round(float(y[te].mean()), 3)

    best = models["gradient_boosting"]
    p_te = best.predict_proba(X[te])[:, 1]

    print("Feature importance (permutation, held-out tenants)...")
    imp = permutation_importance(best, X[te], y[te], scoring="roc_auc", n_repeats=5, random_state=0)
    importance = sorted(zip(FEATURES, imp.importances_mean), key=lambda kv: -kv[1])[:12]

    print("Fairness checks...")
    # 1) Leakage: can our features predict the hidden group at all? AUC ~0.5 means no.
    leak = HistGradientBoostingClassifier(max_iter=200, random_state=0).fit(X[tr], hidden[tr])
    leak_auc = roc_auc_score(hidden[te], leak.predict_proba(X[te])[:, 1])
    # 2) Outcome parity: good fits (>=80%) in each held-out tenant's top K, by group
    per_group = {False: [], True: []}
    for g in np.unique(groups[te]):
        idx = np.where(groups[te] == g)[0]
        if len(idx) < K:
            continue
        top = idx[np.argsort(-p_te[idx])[:K]]
        per_group[bool(hidden[te][idx[0]])].append(float((p_te[top] >= GOOD).sum()))
    a, b = np.mean(per_group[False]), np.mean(per_group[True])
    fairness = {
        "group_leakage_auc": round(float(leak_auc), 3),
        "group_leakage_note": "AUC near 0.5 = features carry no information about the hidden group",
        "avg_good_fits_top_k": {"A": round(float(a), 2), "B": round(float(b), 2)},
        "disparate_impact_ratio": round(float(min(a, b) / max(a, b)), 3),
    }
    fairness["passes_four_fifths_rule"] = fairness["disparate_impact_ratio"] >= 0.8
    print("  ", fairness)

    print("Refitting on all data and saving...")
    best.fit(X, y)
    OUT.mkdir(exist_ok=True)
    joblib.dump({"model": best, "features": FEATURES, "version": 1, "feedback_rows": 0}, OUT / "match_model.joblib")
    card = {
        "model": "Calibrated gradient boosting (scikit-learn HistGradientBoostingClassifier + isotonic)",
        "predicts": "P(smooth first 12 months | tenant answers, listing, landlord answers)",
        "training_data": f"{info['tenancies']} SIMULATED past tenancies read from {info['source']} "
                         f"({info['tenants']} tenants, {info['listings']} listings). No real person's data. "
                         "Replace the tenancies table with real outcomes (ratings, reports, early exits) in the build phase.",
        "dataset": info,
        "inputs": "Allowlisted lifestyle and home answers only. Never diet, work, days, name or any protected ground.",
        "pairs": int(len(y)), "evaluation": "held-out tenants (split by tenant)", "k": K,
        "results": results, "top_features": [{"feature": f, "auc_drop": round(float(v), 4)} for f, v in importance],
        "fairness": fairness,
        "version": 1, "feedback_rows": 0,
        "use": "Ranking = 50% rule match % (criteria both sides set) + 50% predicted success. "
               "Deservia suggests, never decides: the landlord chooses from screened matches.",
    }
    (OUT / "model_card.json").write_text(json.dumps(card, indent=2))
    # protected baseline: "Reset all swipes" restores these, so demo swipes never permanently change the model
    import shutil
    shutil.copyfile(OUT / "match_model.joblib", OUT / "match_model_base.joblib")
    shutil.copyfile(OUT / "model_card.json", OUT / "model_card_base.json")
    print(json.dumps(card["results"], indent=2))


if __name__ == "__main__":
    main()
