"""Fairness guard: "We match on how you live, never on who you are."

Three layers:
  1. Allowlist   - only fields in SCORED_FIELDS can reach the scorer.
  2. Text filter - free text is scanned for protected-ground preferences; flagged phrases are
                   removed before scoring and reported back (demo item 2).
  3. Audit       - see audit.py: checks that scores don't differ by a hidden protected group.
"""
import re

# Fields the scorer may read. Anything else in a profile is ignored by construction.
SCORED_FIELDS = {
    "rental_type", "area", "hobbies", "pets", "pet_kind", "smoking", "chronotype", "social",
    "tidy", "music", "travel", "drive", "timing", "cooking_smells", "repair_speed",
    "budget", "bedrooms_needed", "ideal_words", "importance",
}

# Fields shown in the live UI that we store but deliberately never score, and why.
NOT_SCORED = {
    "diet": "Diet labels (vegan, vegetarian...) can stand in for creed or ethnic origin. "
            "Deservia's own questionnaire says 'cooking smells, no diet labels'. "
            "Use cooking_smells instead.",
    "work": "Student / employed / self-employed can stand in for age and for receipt of public "
            "assistance (there is no option for people not working). Income checks stay with SingleKey.",
    "days": "Working from home can stand in for disability, age or family status (caregiving).",
    "service_animal": "A service or support animal is a disability accommodation, never a pet.",
    "name": "Names can reveal origin or sex. The scorer never sees them.",
}

# Protected grounds under the Ontario Human Rights Code, with phrase patterns.
# Patterns are deliberately broad: a false positive only removes a phrase from the score
# and shows it to the user; a miss lets discrimination into a match.
_GROUNDS = {
    "family status": [r"\bkids?\b", r"\bchild(ren)?\b", r"\bbab(y|ies)\b", r"\btoddlers?\b",
                      r"\bfamil(y|ies)\b", r"\bpregnan\w*", r"\bsingles?\b", r"\bcouples?\b",
                      r"\bmarried\b", r"\bnewlyweds?\b", r"\bparents?\b"],
    "age": [r"\byoung\w*", r"\bold(er)?\b", r"\belderly\b", r"\bseniors?\b", r"\bretire(d|es?)\b",
            r"\bmature\b", r"\bmillennials?\b", r"\bgen ?z\b", r"\b(under|over) \d{2}\b",
            r"\b\d0s\b", r"\bstudents?\b"],
    "creed": [r"\bchristians?\b", r"\bmuslims?\b", r"\bhindus?\b", r"\bsikhs?\b", r"\bjewish\b",
              r"\breligio\w*", r"\bchurch\b", r"\bmosque\b", r"\bgurdwara\b", r"\bhalal\b",
              r"\bkosher\b", r"\bvegetarian\w*", r"\bvegans?\b", r"\bno meat\b", r"\bnon-?veg\w*"],
    "race / ancestry / place of origin / citizenship": [
        r"\bcanadians?( only)?\b", r"\bindians?\b", r"\bpunjabis?\b", r"\bdesi\b", r"\bchinese\b",
        r"\bwhites?\b", r"\bblacks?\b", r"\basians?\b", r"\bbrown\b", r"\bimmigrants?\b",
        r"\bnewcomers?\b", r"\bforeigners?\b", r"\binternational\b", r"\bcitizens?(hip)?\b",
        r"\bpermanent residents?\b", r"\bnative english\b", r"\baccents?\b", r"\blocal born\b"],
    "receipt of public assistance": [
        r"\bodsp\b", r"\bontario works\b", r"\bwelfare\b", r"\bsocial assistance\b",
        r"\bsubsidi[sz]ed\b", r"\bon assistance\b", r"\bgovernment cheques?\b"],
    "disability": [r"\bdisab\w*", r"\bwheelchairs?\b", r"\bable[- ]bodied\b", r"\bmental(ly)?\b",
                   r"\bhealthy\b", r"\bservice (animal|dog)s?\b", r"\bsupport animals?\b"],
    "sex / gender identity / sexual orientation": [
        r"\b(fe)?males?\b", r"\bwom[ae]n\b", r"\bmen\b", r"\bgirls?\b", r"\bguys?\b", r"\bboys?\b",
        r"\blad(y|ies)\b", r"\bgentlem[ae]n\b", r"\bgay\b", r"\bstraight\b", r"\blgbt\w*",
        r"\btrans(gender)?\b", r"\blesbians?\b"],
}
_COMPILED = [(g, re.compile(p, re.I)) for g, pats in _GROUNDS.items() for p in pats]

# Split free text into short phrases ("quiet, tidy - no kids please" -> 3 phrases)
_SPLIT = re.compile(r"[,;/\n]|\.\s|\s[-–—]\s|\band\b|\bbut\b", re.I)


def check_text(text: str) -> dict:
    """Return {'kept': [phrases], 'excluded': [{'text','ground'}]} for one free-text answer."""
    kept, excluded = [], []
    for raw in _SPLIT.split(text or ""):
        phrase = raw.strip(" .!?\"'()")
        if not phrase:
            continue
        grounds = list(dict.fromkeys(g for g, rx in _COMPILED if rx.search(phrase)))
        if grounds:
            excluded.append({"text": phrase, "ground": ", ".join(grounds)})
        else:
            kept.append(phrase)
    return {"kept": kept, "excluded": excluded}


def scorable(profile: dict) -> dict:
    """Allowlist: copy only the fields the scorer is permitted to read."""
    return {k: v for k, v in profile.items() if k in SCORED_FIELDS}
