"""Relecture humaine des segments signalés `needs_review`, avant la génération de la voix.

Pourquoi : les règles automatiques ne raccourcissent que les cas sûrs (hésitations, « in order
to »...). Pour le reste — phrase trop longue, expression idiomatique traduite mot à mot — c'est
un humain qui décide, pour ne jamais déformer le sens.

1. add_alternative_translations : pour chaque segment signalé, on propose d'autres traductions
   du modèle (recherche en faisceau). Le relecteur peut en choisir une ou écrire la sienne.
2. apply_manual_edits : applique les textes corrigés dans `dubbing_text`.
   `translated_text` (la traduction d'origine du modèle) n'est jamais modifié.
"""
from .dubbing_adaptation import DEFAULT_CHARS_PER_SECOND, DEFAULT_MAX_RATIO, estimate_speech_duration

MANUAL_EDIT_LABEL = "corrigé à la main"


def add_alternative_translations(segments, translator, num_candidates=4):
    """Ajoute `alternative_translations` (liste, vide si le segment n'est pas signalé).

    translator doit avoir la méthode translate_candidates (ex. HuggingFaceTranslator).
    """
    completed = []
    for segment in segments:
        alternatives = []
        if segment["needs_review"]:
            candidates = translator.translate_candidates(segment["original_text"], num_candidates)
            # La 1re proposition est la traduction déjà retenue : on ne garde que les autres.
            alternatives = [c for c in candidates if c != segment["translated_text"]]
        completed.append(dict(segment, alternative_translations=alternatives))
    return completed


def apply_manual_edits(segments, edited_texts, chars_per_second=DEFAULT_CHARS_PER_SECOND,
                       max_ratio=DEFAULT_MAX_RATIO):
    """Applique les corrections {id: nouveau texte}. Retourne de nouvelles copies des segments.

    Un texte identique à l'actuel est ignoré ; un texte vide est refusé (le segment serait muet).
    La durée estimée et `needs_review` sont recalculés pour le nouveau texte.
    """
    known_ids = {segment["id"] for segment in segments}
    unknown_ids = sorted(set(edited_texts) - known_ids)
    if unknown_ids:
        raise ValueError(f"Correction pour des segments inexistants : id={unknown_ids}")

    result = []
    for segment in segments:
        new_text = edited_texts.get(segment["id"])
        if new_text is None or new_text.strip() == segment["dubbing_text"]:
            result.append(dict(segment))
            continue

        new_text = new_text.strip()
        if not new_text:
            raise ValueError(f"Le texte corrigé du segment id={segment['id']} est vide.")

        estimated_duration = estimate_speech_duration(new_text, chars_per_second)
        max_duration = (segment["end"] - segment["start"]) * max_ratio
        result.append(dict(segment,
                           dubbing_text=new_text,
                           estimated_duration=round(estimated_duration, 3),
                           adaptation=MANUAL_EDIT_LABEL,
                           needs_review=estimated_duration > max_duration))
    return result
