"""Retrain the global model with swipe feedback, in a background thread.

Training data = 65,000 tenancy outcomes (cached matrix) + swipes from the feedback table.
Swipes are a TASTE signal, not an outcome, so they are used carefully: each counts once, and they only
join the shared model once there are MIN_FEEDBACK of them. (Tested: 20 random demo swipes at 5x weight
moved one prediction from 95% to 71%; that is too much influence for a few clicks.) Each person's
own taste is learned immediately by the personal model (ml/personal.py) instead. After training we re-check accuracy on held-out tenants and
the four-fifths fairness rule, then swap the new model in without restarting the server.
"""
import json
import threading
import time
from pathlib import Path

import numpy as np

from .. import feedback
from . import model as model_mod
from .features import FEATURES
from .trainset import load_cache

FEEDBACK_WEIGHT = 1.0
MIN_FEEDBACK = 50          # swipes needed before they influence the shared model
GOOD, K = 0.80, 3
DATA = Path(__file__).resolve().parents[2] / "data" / "deservia.db"

status = {"state": "idle", "version": None, "message": "No retrain yet this session"}
_lock = threading.Lock()


def _fairness(p, y, groups, hidden):
    per = {False: [], True: []}
    for g in np.unique(groups):
        idx = np.where(groups == g)[0]
        if len(idx) >= K:
            top = idx[np.argsort(-p[idx])[:K]]
            per[bool(hidden[idx[0]])].append(float((p[top] >= GOOD).sum()))
    a, b = np.mean(per[False]), np.mean(per[True])
    ratio = float(min(a, b) / max(a, b)) if max(a, b) else 1.0
    return {"avg_good_fits_top_k": {"A": round(float(a), 2), "B": round(float(b), 2)},
            "disparate_impact_ratio": round(ratio, 3), "passes_four_fifths_rule": ratio >= 0.8}


def retrain_now():
    """Blocking retrain. Returns the new status dict."""
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import GroupShuffleSplit
    import joblib

    t0 = time.time()
    fX, fy = feedback.rows()
    if len(fy) < MIN_FEEDBACK:
        # Nothing new for the shared model yet: keep the live model as it is (no rewrite).
        live = model_mod.load()
        return {"state": "done", "version": live.get("version") if live else None, "feedback_rows": 0,
                "message": f"{len(fy)} swipes saved; they join the shared model at {MIN_FEEDBACK}. "
                           f"Each person's own taste is already being learned."}
    waiting = 0
    X, y, groups, hidden, _, info = load_cache(DATA)
    tr, te = next(GroupShuffleSplit(test_size=0.15, random_state=1).split(X, y, groups))

    X_train = np.vstack([X[tr], np.array(fX, float).reshape(-1, len(FEATURES))]) if fX else X[tr]
    y_train = np.concatenate([y[tr], fy]) if fy else y[tr]
    w = np.concatenate([np.ones(len(tr)), np.full(len(fy), FEEDBACK_WEIGHT)]) if fy else np.ones(len(tr))

    m = CalibratedClassifierCV(
        HistGradientBoostingClassifier(max_iter=300, learning_rate=0.06, max_leaf_nodes=24,
                                       l2_regularization=1.0, random_state=0),
        method="isotonic", cv=3)
    m.fit(X_train, y_train, sample_weight=w)

    p = m.predict_proba(X[te])[:, 1]
    fair = _fairness(p, y[te], groups[te], hidden[te])
    old = model_mod.load()
    version = (old.get("version", 1) if old else 0) + 1
    payload = {"model": m, "features": FEATURES, "version": version, "feedback_rows": len(fy)}

    if not fair["passes_four_fifths_rule"]:
        # Guardrail: never ship a model that fails the fairness check.
        return {"state": "rejected", "version": version - 1, "fairness": fair,
                "message": "New model failed the four-fifths rule; kept the previous model."}

    path = model_mod.MODEL_PATH
    tmp = path.with_suffix(".tmp")
    joblib.dump(payload, tmp)
    tmp.replace(path)
    model_mod._model = payload                   # hot-swap, no restart

    card_path = path.parent / "model_card.json"
    card = json.loads(card_path.read_text()) if card_path.exists() else {}
    card.update({"version": version, "feedback_rows": len(fy),
                 "last_retrain": {"auc_held_out": round(float(roc_auc_score(y[te], p)), 3),
                                  "fairness": fair, "outcome_rows": int(len(tr)),
                                  "feedback_rows": len(fy), "feedback_weight": FEEDBACK_WEIGHT,
                                  "seconds": round(time.time() - t0, 1)}})
    card_path.write_text(json.dumps(card, indent=2))
    return {"state": "done", "version": version, "feedback_rows": len(fy),
            "auc_held_out": card["last_retrain"]["auc_held_out"], "fairness": fair,
            "seconds": card["last_retrain"]["seconds"],
            "message": f"Model v{version} trained on {len(tr):,} outcomes + {len(fy)} swipes"
                       + (f" ({waiting} swipes saved; they join the shared model at {MIN_FEEDBACK})" if waiting else "")}


def restore_baseline():
    """Put back the model train.py produced (used by 'Reset all swipes')."""
    import shutil
    base = model_mod.MODEL_PATH.with_name("match_model_base.joblib")
    card = model_mod.MODEL_PATH.with_name("model_card_base.json")
    if base.exists():
        shutil.copyfile(base, model_mod.MODEL_PATH)
        if card.exists():
            shutil.copyfile(card, model_mod.MODEL_PATH.with_name("model_card.json"))
        model_mod._model = None
        with _lock:
            status.clear(); status.update(state="idle", version=None, message="Baseline model restored")
        return True
    return False


def start():
    """Kick off a retrain in the background (ignored if one is already running)."""
    with _lock:
        if status["state"] == "training":
            return status
        status.update(state="training", message="Retraining with your swipes...", started=time.time())

    def run():
        try:
            result = retrain_now()
        except Exception as e:                    # keep serving the old model on any error
            result = {"state": "error", "message": f"Retrain failed: {e}"}
        with _lock:
            status.clear(); status.update(result)

    threading.Thread(target=run, daemon=True).start()
    return status
