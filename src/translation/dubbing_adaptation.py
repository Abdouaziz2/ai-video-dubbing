"""Adaptation des traductions à la durée disponible de chaque segment.

Principe : on n'intervient que sur les segments qui risquent de dépasser.
- La traduction initiale (translated_text) n'est jamais modifiée.
- La version destinée à la voix est stockée dans dubbing_text.
- Seules des règles sûres (sans perte de sens) sont appliquées automatiquement.
- Un segment qui dépasse encore est marqué needs_review=True pour une relecture humaine.

L'estimation de durée (caractères / débit) n'est qu'un signal d'alerte : la vraie durée
n'est connue qu'après la synthèse vocale.
"""
import re

# Débit de parole anglais approximatif. À calibrer avec la voix de synthèse réelle.
DEFAULT_CHARS_PER_SECOND = 14.0
# Au-delà de 10 % de dépassement estimé, le segment est considéré trop long.
DEFAULT_MAX_RATIO = 1.1

REQUIRED_TRANSLATION_FIELDS = ("id", "start", "end", "original_text", "translated_text")

# (expression régulière, remplacement, description). Chaque règle raccourcit sans changer le sens.
SHORTENING_RULES = [
    # "uh"/"um" : toujours des hésitations. "so", "well"... seulement suivis d'une virgule :
    # "So the model fails" ("donc") est un lien logique, "Well-known" n'est pas une hésitation.
    (re.compile(r"^(?:(?:uh|um)\b[,.]?\s+|(?:so|well|actually|in fact|you know),\s*)+", re.IGNORECASE),
     "", "hésitations en début de phrase supprimées"),
    (re.compile(r"\bin order to\b", re.IGNORECASE), "to", "'in order to' -> 'to'"),
    (re.compile(r"\bdue to the fact that\b", re.IGNORECASE), "because", "'due to the fact that' -> 'because'"),
]


def estimate_speech_duration(text, chars_per_second=DEFAULT_CHARS_PER_SECOND):
    """Durée de parole estimée en secondes (espaces et ponctuation comptés : ils prennent du temps)."""
    if chars_per_second <= 0:
        raise ValueError("chars_per_second doit être strictement positif.")
    return len(text.strip()) / chars_per_second


def apply_shortening_rules(text):
    """Applique les règles de raccourcissement. Retourne (texte, liste des règles appliquées)."""
    started_with_capital = text[:1].isupper()
    applied = []
    for pattern, replacement, description in SHORTENING_RULES:
        new_text = pattern.sub(replacement, text)
        if new_text != text:
            applied.append(description)
            text = new_text

    text = text.strip()
    # Une suppression en début de phrase laisse une minuscule ("the result...") : on la corrige,
    # sauf si le texte d'origine commençait déjà par une minuscule (fragment de phrase).
    if applied and text and started_with_capital:
        text = text[0].upper() + text[1:]
    return text, applied


def adapt_segment_for_dubbing(segment, chars_per_second=DEFAULT_CHARS_PER_SECOND,
                              max_ratio=DEFAULT_MAX_RATIO):
    """Retourne une copie du segment complétée par les champs de doublage."""
    missing = [field for field in REQUIRED_TRANSLATION_FIELDS if field not in segment]
    if missing:
        raise ValueError(f"segment id={segment.get('id')!r} : champ(s) manquant(s) {missing}.")

    available_duration = segment["end"] - segment["start"]
    max_duration = available_duration * max_ratio

    dubbing_text = segment["translated_text"]
    adaptation = None

    if estimate_speech_duration(dubbing_text, chars_per_second) > max_duration:
        shortened_text, applied_rules = apply_shortening_rules(dubbing_text)
        if applied_rules and shortened_text:
            dubbing_text = shortened_text
            adaptation = "règles : " + ", ".join(applied_rules)

    estimated_duration = estimate_speech_duration(dubbing_text, chars_per_second)

    adapted = dict(segment)
    adapted.update({
        "dubbing_text": dubbing_text,
        "available_duration": round(available_duration, 3),
        "estimated_duration": round(estimated_duration, 3),
        "adaptation": adaptation,
        "needs_review": estimated_duration > max_duration,
    })
    return adapted


def adapt_segments_for_dubbing(segments, chars_per_second=DEFAULT_CHARS_PER_SECOND,
                               max_ratio=DEFAULT_MAX_RATIO):
    """Adapte une liste de segments traduits. La liste d'entrée n'est pas modifiée."""
    return [adapt_segment_for_dubbing(s, chars_per_second, max_ratio) for s in segments]
