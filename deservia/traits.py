"""Turns "describe your ideal tenant / landlord in 3+ words" into checks against the other
side's actual answers. Explainable on purpose: every word maps to a concrete answer, so the
percent can always be justified. Words we can't check (honest, respectful...) are neutral now
and become checkable later through two-way ratings."""

# trait -> (phrases that mean it, check(other_profile) -> True/False)
TRAITS = {
    "tidy": (["tidy", "clean", "neat", "organized", "organised", "spotless"],
             lambda o: o.get("tidy") in ("reasonably", "very")),
    "quiet": (["quiet", "calm", "peaceful", "low-key", "low key"],
              lambda o: o.get("music") == "quiet"),
    "early riser": (["early", "morning person", "morning"],
                    lambda o: o.get("chronotype") in ("early", "flexible")),
    "night owl": (["night owl", "late night", "night person"],
                  lambda o: o.get("chronotype") in ("night", "flexible")),
    "non-smoker": (["non-smoker", "non smoker", "nonsmoker", "smoke-free", "smoke free", "no smoking"],
                   lambda o: o.get("smoking") == "non_smoker"),
    "pet lover": (["pet lover", "pet friendly", "pet-friendly", "loves pets", "animal lover"],
                  lambda o: o.get("pets") in ("love_pets", "have_pet")),
    "pet-free": (["no pets", "pet-free", "pet free"],
                 lambda o: o.get("pets") == "prefer_no_pets"),
    "responsive": (["responsive", "communicative", "quick repairs", "fixes things", "fast repairs",
                    "prompt", "handy"],
                   lambda o: o.get("repair_speed") in ("same_day", "24h") if o.get("role") == "landlord" else None),
    "private": (["private", "privacy", "independent", "keeps to themselves"],
                lambda o: o.get("social") in ("introvert", "both")),
    "friendly": (["friendly", "social", "outgoing", "chatty"],
                 lambda o: o.get("social") in ("extrovert", "both")),
    "homebody": (["homebody", "home body", "stays in"],
                 lambda o: o.get("travel") == "homebody"),
}
UNVERIFIABLE = ["respectful", "honest", "reliable", "responsible", "kind", "considerate",
                "trustworthy", "fair", "polite", "pays on time"]


def parse_ideal(phrases: list[str], other: dict) -> list[dict]:
    """For each trait mentioned, did the other side satisfy it? satisfied=None means
    'can't check yet' and does not count toward the score."""
    out, seen = [], set()
    text = " | ".join(p.lower() for p in phrases)
    for trait, (syns, check) in TRAITS.items():
        if any(s in text for s in syns) and trait not in seen:
            seen.add(trait)
            out.append({"trait": trait, "satisfied": check(other)})
    for w in UNVERIFIABLE:
        if w in text and w not in seen:
            seen.add(w)
            out.append({"trait": w, "satisfied": None})
    return out
