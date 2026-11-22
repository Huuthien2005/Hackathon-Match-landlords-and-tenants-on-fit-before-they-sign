"""The sign-up questionnaire for tenants and landlords, one question per screen.

Served to the front end by /api/questions, and used to VALIDATE every answer on the server:
only known questions and allowed options are stored, so nobody can inject extra fields
(e.g. a protected attribute) into a profile.

Deliberately NOT asked (see fairness.py NOT_SCORED): diet, work situation, where you spend
your days. "How do you eat?" is replaced by shared-kitchen habits, as in Deservia's own PDF.
"""
from .options import AREAS, AREA_TO_REGION, HOBBIES, RENTAL_TYPES


def _o(v, label, icon=""):
    return {"v": v, "label": label, "icon": icon}


RENTAL = [_o("room", "A room", "🚪"), _o("apartment", "Apartment", "🏢"), _o("basement", "Basement apartment", "🏡"),
          _o("whole_house", "Whole house", "🏠"), _o("upper_floor", "Upper floor", "🪜"), _o("rent_to_own", "Rent-to-own", "🔑")]
HOBBY_ICONS = {"Gardening": "🌱", "Fishing": "🎣", "Painting": "🎨", "Artistic / creative": "🖌️",
               "Building websites / tech": "💻", "Music": "🎵", "Travel": "✈️", "Cooking": "🍳",
               "Fitness": "🏋️", "Reading": "📚"}
BEDROOMS = [_o(0, "Studio", "🛏️"), _o(1, "1 bedroom", "1️⃣"), _o(2, "2 bedrooms", "2️⃣"),
            _o(3, "3 bedrooms", "3️⃣"), _o(4, "4+ bedrooms", "4️⃣")]

LIFESTYLE = [
    {"id": "hobbies", "type": "multi", "title": "What are you into?", "sub": "Pick all that apply.",
     "options": [_o(h, h, HOBBY_ICONS[h]) for h in HOBBIES]},
    {"id": "pets", "type": "single", "title": "Pets?", "options": [
        _o("love_pets", "Love pets", "🐾"), _o("have_pet", "I have a pet", "🐶"), _o("prefer_no_pets", "Prefer no pets", "🚫")]},
    {"id": "smoking", "type": "single", "title": "Smoking?", "options": [
        _o("non_smoker", "Non-smoker", "🚭"), _o("outdoor_only", "Outdoor only", "🌳"), _o("smoker", "Smoker", "🚬")]},
    {"id": "chronotype", "type": "single", "title": "Early bird or night owl?", "options": [
        _o("early", "Early riser", "🌅"), _o("night", "Night owl", "🌙"), _o("flexible", "Flexible", "🔁")]},
    {"id": "social", "type": "single", "title": "Introvert or extrovert?", "options": [
        _o("introvert", "Introvert", "🧘"), _o("extrovert", "Extrovert", "🎉"), _o("both", "A bit of both", "⚖️")]},
    {"id": "tidy", "type": "single", "title": "How tidy are you?", "options": [
        _o("very", "Very tidy", "✨"), _o("reasonably", "Reasonably tidy", "🙂"), _o("relaxed", "Relaxed about it", "😌")]},
    {"id": "music", "type": "single", "title": "Music at home?", "options": [
        _o("love_music", "Love music / a bit of noise", "🎶"), _o("quiet", "Prefer a quiet home", "🤫")]},
    {"id": "travel", "type": "single", "title": "Travel?", "options": [
        _o("love_travel", "Love to travel", "🧳"), _o("homebody", "Homebody", "🛋️")]},
    {"id": "cooking_smells", "type": "single", "title": "Kitchen habits?",
     "sub": "Great for shared kitchens. No diet labels, just how you cook.", "options": [
        _o("rarely_cook", "Rarely cook", "🥡"), _o("light", "Light cooking smells", "🥗"), _o("strong", "Strong smells are fine", "🍛")]},
]

TENANT = [
    {"id": "rental_type", "type": "single", "title": "What are you looking for?", "sub": "Pick the type of rental.", "options": RENTAL},
    {"id": "area", "type": "area", "title": "Which area?", "sub": "Where you want to live."},
    {"id": "budget", "type": "number", "title": "Monthly budget?", "sub": "Rent you're comfortable paying, in $ per month.",
     "min": 300, "max": 10000, "placeholder": "e.g. 1800"},
    {"id": "bedrooms_needed", "type": "single", "title": "How many bedrooms do you need?", "options": BEDROOMS},
    *LIFESTYLE[:2],
    {"id": "pet_kind", "type": "single", "title": "What kind of pet?", "show_if": {"pets": "have_pet"}, "options": [
        _o("dog", "Dog", "🐕"), _o("cat", "Cat", "🐈"), _o("small", "Small pet", "🐹"), _o("other", "Other", "🦜")]},
    {"id": "service_animal", "type": "single", "title": "Is it a service or support animal?", "show_if": {"pets": "have_pet"},
     "sub": "Private: never shown to landlords, never treated as a pet.", "options": [
        _o("yes", "Yes", "🦮"), _o("no", "No", "🐾")]},
    *LIFESTYLE[2:],
    {"id": "drive", "type": "single", "title": "Do you drive?", "options": [
        _o("drives", "I drive / have a car", "🚗"), _o("non_driver", "Non-driver", "🚶")]},
    {"id": "repair_speed", "type": "single", "title": "How quickly should issues be fixed?", "options": [
        _o("same_day", "Same day", "⚡"), _o("24h", "Within 24 hours", "🕐"), _o("week", "Within a week", "📅"), _o("no_pref", "No preference", "🤷")]},
    {"id": "timing", "type": "single", "title": "Timing?", "sub": "When do you want to move?", "options": [
        _o("within_month", "Within a month", "⚡"), _o("1_3_months", "1–3 months", "📆"), _o("flexible", "Flexible", "🍃")]},
    {"id": "ideal_text", "type": "text", "title": "Describe your ideal landlord", "check_text": True, "required": False,
     "sub": "3+ words about how they live or manage the home (e.g. quiet, responsive, respects privacy).",
     "placeholder": "quiet, responsive, fixes things fast"},
]

LANDLORD = [
    {"id": "rental_type", "type": "single", "title": "What are you offering?", "sub": "Pick the type of rental.", "options": RENTAL},
    {"id": "area", "type": "area", "title": "Which area?", "sub": "Where your place is."},
    {"id": "title", "type": "text", "title": "Give your place a short name", "required": False, "max_len": 60,
     "placeholder": "e.g. Bright basement near Bovaird"},
    {"id": "rent", "type": "number", "title": "Monthly rent?", "sub": "$ per month.", "min": 300, "max": 15000, "placeholder": "e.g. 1700"},
    {"id": "bedrooms", "type": "single", "title": "How many bedrooms?", "options": BEDROOMS},
    {"id": "parking", "type": "single", "title": "Parking?", "options": [
        _o("none", "No parking", "🚫"), _o("street", "Street parking", "🛣️"), _o("one", "1 parking spot", "🅿️"),
        _o("two_plus", "2+ parking spots", "🚙"), _o("garage", "Garage", "🏚️")]},
    {"id": "kitchen", "type": "single", "title": "Kitchen?", "options": [
        _o("private", "Private kitchen", "🍳"), _o("shared", "Shared kitchen", "👥"), _o("kitchenette", "Kitchenette", "☕")]},
    {"id": "entrance", "type": "single", "title": "Entrance?", "options": [
        _o("separate", "Separate entrance", "🚪"), _o("shared", "Shared entrance", "🏘️")]},
    {"id": "pet_policy", "type": "single", "title": "Pets in the unit?", "sub": "Service and support animals are always allowed.", "options": [
        _o("welcome", "Pets welcome", "🐾"), _o("cats_only", "Cats only", "🐈"), _o("dogs_only", "Dogs only", "🐕"),
        _o("small_only", "Small pets only", "🐹"), _o("none", "No pets", "🚫")]},
    {"id": "smoke_policy", "type": "single", "title": "Smoking rule?", "options": [
        _o("non_smoking", "Non-smoking", "🚭"), _o("outside_only", "Smoking outside only", "🌳"), _o("allowed", "Smoking allowed", "🚬")]},
    {"id": "landlord_on_site", "type": "single", "title": "Do you live on the property?", "options": [
        _o("yes", "Yes, I live there too", "🏡"), _o("no", "No, I live elsewhere", "📍")]},
    {"id": "timing", "type": "single", "title": "Timing?", "sub": "When do you want it filled?", "options": [
        _o("within_month", "Within a month", "⚡"), _o("1_3_months", "1–3 months", "📆"), _o("flexible", "Flexible", "🍃")]},
    {"id": "description", "type": "text", "title": "Describe your home", "required": False, "max_len": 300,
     "placeholder": "Bright, quiet basement, 5 min walk to the bus."},
    *LIFESTYLE,
    {"id": "repair_speed", "type": "single", "title": "How fast do you fix issues?", "options": [
        _o("same_day", "Same day", "⚡"), _o("24h", "Within 24 hours", "🕐"), _o("week", "Within a week", "📅")]},
    {"id": "ideal_text", "type": "text", "title": "Describe your ideal tenant", "check_text": True, "required": False,
     "sub": "3+ words about how they live (e.g. tidy, quiet, communicative). Lifestyle only.",
     "placeholder": "tidy, quiet, non-smoker"},
]

QUESTIONS = {"tenant": TENANT, "landlord": LANDLORD}


def questions(role):
    return {"role": role, "areas": AREAS, "questions": QUESTIONS[role]}


def _shown(q, answers):
    return all(answers.get(k) == v for k, v in (q.get("show_if") or {}).items())


def validate(role, answers: dict):
    """Keep only known questions with allowed values. Returns (clean_answers, errors)."""
    if role not in QUESTIONS or not isinstance(answers, dict):
        return {}, ["Invalid role or answers"]
    clean, errors = {}, []
    for q in QUESTIONS[role]:
        if not _shown(q, {**answers, **clean}):
            continue
        v, qid, req = answers.get(q["id"]), q["id"], q.get("required", True)
        if v in (None, "", []):
            if req and q["type"] not in ("multi", "area"):
                errors.append(f"Please answer: {q['title']}")
            continue
        allowed = [o["v"] for o in q.get("options", [])]
        if q["type"] == "single":
            if v not in allowed:
                errors.append(f"Invalid choice for {qid}")
                continue
        elif q["type"] == "multi":
            if not isinstance(v, list) or any(x not in allowed for x in v):
                errors.append(f"Invalid choices for {qid}")
                continue
        elif q["type"] == "number":
            try:
                v = int(float(v))
            except (TypeError, ValueError):
                errors.append(f"{q['title']} must be a number")
                continue
            if not q["min"] <= v <= q["max"]:
                errors.append(f"{q['title']} must be between {q['min']} and {q['max']}")
                continue
        elif q["type"] == "area":
            continue                                # handled by apply_other (typed or picked)
        elif q["type"] == "text":
            v = str(v).strip()[: q.get("max_len", 300)]
        clean[qid] = v
    apply_other(role, answers, clean, errors)
    for q in QUESTIONS[role]:                     # area is required but filled by apply_other
        if q["type"] == "area" and q["id"] not in clean and _shown(q, clean):
            errors.append(f"Please answer: {q['title']}")
    errors = list(dict.fromkeys(errors))
    return clean, sorted(errors, key=lambda e: "who someone is" not in e)   # most useful message first


def _hobbies(a):
    """Picked categories + typed hobbies (Title Case) so 'Pickleball' can match 'Pickleball'."""
    return sorted(set(a.get("hobbies", [])) | {h.strip().title() for h in a.get("hobbies_other", [])})


def to_tenant(tenant_id, a):
    t = {"id": tenant_id, "role": "tenant", "hobbies": _hobbies(a)}
    for k in ("rental_type", "area", "budget", "bedrooms_needed", "pets", "pet_kind", "smoking", "chronotype", "social",
              "tidy", "music", "travel", "drive", "timing", "cooking_smells", "repair_speed", "ideal_text"):
        if k in a:
            t[k] = a[k]
    t["service_animal"] = a.get("service_animal") == "yes"
    return t


def to_listing(listing_id, a):
    ll = {"role": "landlord", "hobbies": _hobbies(a)}
    for k in ("pets", "smoking", "chronotype", "social", "tidy", "music", "travel", "cooking_smells", "repair_speed", "ideal_text"):
        if k in a:
            ll[k] = a[k]
    listing = {
        "id": listing_id, "area": a["area"], "rental_type": a["rental_type"], "rent": a["rent"],
        "bedrooms": a.get("bedrooms", 1), "parking": a.get("parking"), "kitchen": a.get("kitchen"),
        "entrance": a.get("entrance"), "pet_policy": a.get("pet_policy"), "smoke_policy": a.get("smoke_policy"),
        "timing": a.get("timing"), "landlord_on_site": a.get("landlord_on_site") == "yes",
        "title": a.get("title") or f'{RENTAL_TYPES.get(a["rental_type"], a["rental_type"].title())} in {a["area"]}',
        "description": a.get("description", ""), "landlord": ll,
    }
    return {k: v for k, v in listing.items() if v is not None}    # unanswered -> engine defaults


# ======================================================================= "Other: type your own"
# Every choice question accepts a typed answer in "<id>_other". If the words clearly mean one of
# the options, the answer is mapped to it and scored; otherwise it is kept on the profile but not
# scored, so the match % stays explainable. Typed answers about WHO someone is are refused.
import re as _re

from .fairness import check_text

FREE_VALUE = {"rental_type", "area"}          # an unknown typed value is still useful as-is
SYNONYMS = {
    "rental_type": {"room": ["room", "bedroom in", "shared house"], "apartment": ["apartment", "condo", "flat", "suite"],
                    "basement": ["basement", "lower level", "walk-out", "walkout"],
                    "whole_house": ["house", "townhouse", "townhome", "detached", "semi"],
                    "upper_floor": ["upper", "main floor", "top floor"], "rent_to_own": ["rent to own", "rent-to-own"]},
    "pets": {"have_pet": ["dog", "cat", "puppy", "kitten", "rabbit", "bird", "fish", "hamster", "my pet"],
             "prefer_no_pets": ["allerg", "no pet", "don't like pets", "dont like pets"], "love_pets": ["love animals", "like pets", "animal lover"]},
    "pet_kind": {"dog": ["dog", "puppy"], "cat": ["cat", "kitten"], "small": ["rabbit", "hamster", "guinea", "bird", "fish", "turtle"]},
    "smoking": {"smoker": ["smoke", "vape", "cigar", "weed", "cannabis"], "non_smoker": ["never smoke", "don't smoke", "dont smoke", "no smoking", "quit"]},
    "chronotype": {"early": ["morning", "early", "5am", "6am", "sunrise", "wake up early"], "night": ["night", "late", "evening", "midnight", "night shift"],
                   "flexible": ["depends", "varies", "shift", "rotating", "both"]},
    "social": {"introvert": ["shy", "quiet person", "keep to myself", "private", "reserved"], "extrovert": ["outgoing", "social", "party", "friends over", "chatty"],
               "both": ["depends", "ambivert", "both", "in between"]},
    "tidy": {"very": ["very clean", "neat freak", "spotless", "organized", "organised", "clean"], "relaxed": ["messy", "lived-in", "chill about", "relaxed"],
             "reasonably": ["mostly", "average", "reasonably", "normal"]},
    "music": {"quiet": ["quiet", "calm", "silence", "peaceful", "headphones"], "love_music": ["loud", "music", "instrument", "piano", "guitar", "drums", "noise"]},
    "travel": {"love_travel": ["travel", "away a lot", "trips", "fly"], "homebody": ["home", "stay in", "rarely travel"]},
    "cooking_smells": {"rarely_cook": ["rarely", "takeout", "take-out", "eat out", "don't cook", "dont cook"],
                       "strong": ["spicy", "spices", "curry", "fry", "frying", "bbq", "grill", "fish"], "light": ["light", "simple", "salad", "bake"]},
    "drive": {"drives": ["car", "drive", "truck", "vehicle"], "non_driver": ["transit", "bus", "bike", "walk", "don't drive", "dont drive", "no car"]},
    "repair_speed": {"same_day": ["same day", "immediately", "asap", "right away", "urgent"], "24h": ["24", "next day", "a day"],
                     "week": ["week", "few days"], "no_pref": ["whenever", "no rush", "flexible", "don't mind", "dont mind"]},
    "timing": {"within_month": ["asap", "now", "immediately", "this month", "2 weeks", "two weeks"], "1_3_months": ["month", "spring", "summer", "fall", "winter"],
               "flexible": ["flexible", "whenever", "no rush"]},
    "parking": {"none": ["no parking", "none"], "street": ["street"], "garage": ["garage"], "two_plus": ["2 spots", "two spots", "driveway"], "one": ["1 spot", "one spot", "spot", "parking"]},
    "kitchen": {"shared": ["shared", "share"], "kitchenette": ["kitchenette", "small kitchen"], "private": ["private", "own kitchen", "full kitchen"]},
    "entrance": {"separate": ["separate", "private entrance", "own entrance", "side door"], "shared": ["shared", "same door", "front door"]},
    "pet_policy": {"none": ["no pets", "none"], "cats_only": ["cats only", "cat only"], "dogs_only": ["dogs only", "dog only"],
                   "small_only": ["small", "fish", "bird", "hamster"], "welcome": ["welcome", "any pet", "pets ok", "pets allowed", "pet friendly"]},
    "smoke_policy": {"non_smoking": ["no smoking", "non-smoking", "non smoking", "smoke-free", "smoke free"], "outside_only": ["outside", "outdoor", "balcony", "porch"],
                     "allowed": ["allowed", "ok to smoke"]},
    "landlord_on_site": {"yes": ["upstairs", "downstairs", "live there", "same house", "on site", "on-site", "next door"],
                         "no": ["elsewhere", "don't live", "dont live", "another city", "abroad", "overseas"]},
    "service_animal": {"yes": ["service", "support", "therapy", "guide"], "no": ["no", "just a pet", "regular"]},
    "hobbies": {"Fitness": ["gym", "running", "yoga", "workout", "sport", "soccer", "basketball", "cricket", "hockey", "swim"],
                "Cooking": ["cook", "baking", "bake"], "Reading": ["read", "books"], "Music": ["music", "guitar", "piano", "sing", "drum"],
                "Gardening": ["garden", "plants"], "Building websites / tech": ["coding", "programming", "tech", "computer", "gaming", "games"],
                "Painting": ["paint"], "Artistic / creative": ["art", "draw", "craft", "photo", "design", "knit", "sew"], "Travel": ["travel"],
                "Fishing": ["fish"]},
}
OTHER_MAX = 80


def match_option(q, text):
    """Map typed text to an option value, or None. Option labels count as keywords too."""
    t = " " + _re.sub(r"\s+", " ", text.lower()) + " "
    if q["type"] == "single" and q["id"] in ("bedrooms", "bedrooms_needed"):
        if "studio" in t or "bachelor" in t:
            return 0
        n = _re.search(r"\d+", t)
        return min(4, int(n.group())) if n else None
    table = dict(SYNONYMS.get(q["id"], {}))
    for o in q.get("options", []):
        table.setdefault(o["v"], [])
        table[o["v"]] = table[o["v"]] + [o["label"].lower()]
    best = None
    for value, words in table.items():
        for w in words:
            if w and w in t and (best is None or len(w) > best[1]):
                best = (value, len(w))           # longest keyword wins ("no pets" beats "pets")
    return best[0] if best else None


def _check_custom(qtitle, text):
    ex = check_text(text)["excluded"]
    if ex:
        return f'"{ex[0]["text"]}" ({qtitle}) describes who someone is ({ex[0]["ground"]}), not how they live. Please rephrase.'
    return None


def apply_other(role, raw, clean, errors):
    """Second pass of validate(): handle '<id>_other' typed answers."""
    for q in QUESTIONS[role]:
        if not _shown(q, {**raw, **clean}) or q["type"] not in ("single", "multi", "area"):
            continue
        key = f'{q["id"]}_other'
        val = raw.get(key)
        if q["type"] == "area":                   # area: typed directly into the box
            v = str(raw.get(q["id"]) or "").strip()[:OTHER_MAX]
            if not v:
                continue
            known = {a.lower(): a for a in AREA_TO_REGION}
            if v.lower() in known:
                clean[q["id"]] = known[v.lower()]
            else:
                if (e := _check_custom(q["title"], v)):
                    errors.append(e); continue
                clean[q["id"]] = v.title()
            errors[:] = [e for e in errors if "choose an area" not in e.lower()]
            continue
        if q["type"] == "multi":
            items = val if isinstance(val, list) else str(val or "").split(",")
            items = [str(x).strip()[:30] for x in items if str(x).strip()][:5]
            if not items:
                continue
            kept, chosen = [], set(clean.get(q["id"], []))
            for it in items:
                if (e := _check_custom(q["title"], it)):
                    errors.append(e); continue
                m = match_option(q, it)
                if m:
                    chosen.add(m)
                kept.append(it)
            clean[q["id"]] = sorted(chosen)
            clean[key] = kept
            continue
        text = str(val or "").strip()[:OTHER_MAX]
        if not text:
            continue
        if (e := _check_custom(q["title"], text)):
            errors.append(e); continue
        clean[key] = text
        m = match_option(q, text)
        if m is not None:
            clean[q["id"]] = m                      # a typed answer wins over a picked one
        elif q["id"] in FREE_VALUE:
            clean[q["id"]] = text.lower()
        else:
            clean.pop(q["id"], None)                # typed but unclear: not scored
        errors[:] = [e for e in errors if e != f"Please answer: {q['title']}"]


def describe(role, answers):
    """For 'My answers': each question with what the user picked or typed, and how it's used."""
    out = []
    for q in QUESTIONS.get(role, []):
        if not _shown(q, answers):
            continue
        v, typed = answers.get(q["id"]), answers.get(f'{q["id"]}_other')
        labels = {o["v"]: f'{o["icon"]} {o["label"]}'.strip() for o in q.get("options", [])}
        if q["type"] == "multi":
            shown = [labels.get(x, x) for x in (v or [])]
            out.append({"id": q["id"], "question": q["title"], "answer": ", ".join(shown) or "–",
                        "typed": ", ".join(typed) if typed else None,
                        "used": "Typed hobbies are matched to the closest category, and also kept as written" if typed else None})
            continue
        answer = labels.get(v, v) if v is not None else None
        if q["type"] == "number" and v is not None:
            answer = f"${v:,}" if q["id"] in ("budget", "rent") else str(v)
        used = None
        if typed:
            if v is not None and v in labels:
                used = f"Matched as {labels[v]}"
            elif v is not None:
                used = "Used as written"
            else:
                used = "Shown on your profile; not used for the match score"
        out.append({"id": q["id"], "question": q["title"], "answer": answer if answer is not None else ("–" if not typed else None),
                    "typed": typed, "used": used})
    return out
