"""Personal preference model: learns what ONE user likes from their own swipes.

A small logistic regression on the per-criterion match scores (tidy, quiet, budget, hobbies...).
It needs at least one like and one pass. Its coefficients are readable, so we can tell the user
"you seem to care most about: quiet home, budget". Only allowlisted criteria are used.
"""
import math

from .. import feedback
from .features import CRITERIA, FEATURES

IDX = [FEATURES.index(f"c_{c}") for c in CRITERIA]
WORDS = {"budget": "staying within budget", "area": "the area", "rental_type": "the type of home",
         "timing": "move-in timing", "parking": "parking", "smoking": "smoke-free living",
         "pets": "pets", "tidy": "tidiness", "quiet": "a quiet home", "chronotype": "similar hours",
         "social": "a similar social style", "hobbies": "shared hobbies", "travel": "travel habits",
         "cooking": "kitchen habits", "repairs": "fast repairs",
         "ideal_tenant": "your ideal-match words", "ideal_landlord": "their ideal-match words"}
MIN_SWIPES = 4


def _x(features):
    # missing criterion -> 0.8 (roughly "neutral / not applicable")
    return [0.8 if (v := features[i]) is None or (isinstance(v, float) and math.isnan(v)) else v for i in IDX]


def fit(user_id):
    """Returns a fitted model dict or None if there isn't enough signal yet."""
    X, y = feedback.rows(user_id)
    if len(y) < MIN_SWIPES or len(set(y)) < 2:
        return None
    from sklearn.linear_model import LogisticRegression
    m = LogisticRegression(C=1.0, max_iter=1000).fit([_x(f) for f in X], y)
    return {"model": m, "n": len(y)}


def predict(personal, features_list):
    if not personal:
        return None
    return [float(p) for p in personal["model"].predict_proba([_x(f) for f in features_list])[:, 1]]


def explain(personal, top=3):
    """What this user seems to care about, in words, from the strongest positive weights."""
    if not personal:
        return []
    coefs = sorted(zip(CRITERIA, personal["model"].coef_[0]), key=lambda kv: -kv[1])
    return [{"criterion": c, "words": WORDS[c], "weight": round(float(w), 2)} for c, w in coefs[:top] if w > 0.05]
