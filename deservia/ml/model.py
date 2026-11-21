"""Loads the trained model (if present) and adds a predicted "smooth tenancy" chance to each
match. If the model file or scikit-learn is missing, matching falls back to the rule score."""
from pathlib import Path

from .features import pair_features

MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "match_model.joblib"
BLEND = 0.5   # ranking = 50% rule match (criteria both sides set) + 50% predicted success
_model = None


def load():
    global _model
    if _model is None and MODEL_PATH.exists():
        try:
            import joblib
            _model = joblib.load(MODEL_PATH)
        except ImportError:
            _model = False
    return _model or None


def predict_success(pairs: list[tuple[dict, dict, dict]]) -> list[float] | None:
    """pairs: (tenant, listing, rule_result). Returns P(smooth tenancy) per pair, or None."""
    m = load()
    if not m or not pairs:
        return None
    X = [pair_features(t, l, r) for t, l, r in pairs]
    return [float(p) for p in m["model"].predict_proba(X)[:, 1]]


def rerank(tenant: dict, listings: dict, matches: list[dict]) -> list[dict]:
    """Attach ml_success_pct and re-rank by the blend. No-op without a model."""
    probs = predict_success([(tenant, listings[m["listing_id"]], m) for m in matches])
    if probs is None:
        return matches
    for m, p in zip(matches, probs):
        m["ml_success_pct"] = round(p * 100)
        m["rank_score"] = round((1 - BLEND) * m["match_pct"] + BLEND * p * 100, 1)
    return sorted(matches, key=lambda m: -m["rank_score"])
