"""Tests de la relecture humaine (aucun modèle nécessaire)."""
import copy

import pytest

from src.translation import add_alternative_translations, apply_manual_edits


def make_segment(segment_id, dubbing_text, needs_review, start=0.0, end=2.0):
    return {"id": segment_id, "start": start, "end": end, "original_text": f"phrase {segment_id}",
            "translated_text": dubbing_text, "dubbing_text": dubbing_text,
            "available_duration": end - start, "estimated_duration": 0.0,
            "adaptation": None, "needs_review": needs_review}


class FakeCandidateTranslator:
    """Renvoie la traduction principale puis deux variantes ; enregistre les appels."""

    def __init__(self):
        self.calls = []

    def translate_candidates(self, text, num_candidates):
        self.calls.append((text, num_candidates))
        return ["main translation", "variant A", "variant B"]


# --- Propositions de traduction ----------------------------------------------

def test_alternatives_only_for_flagged_segments():
    segments = [make_segment(1, "main translation", needs_review=True),
                make_segment(2, "fine", needs_review=False)]
    translator = FakeCandidateTranslator()

    result = add_alternative_translations(segments, translator, num_candidates=3)

    assert result[0]["alternative_translations"] == ["variant A", "variant B"]  # sans la traduction actuelle
    assert result[1]["alternative_translations"] == []
    assert translator.calls == [("phrase 1", 3)]  # le modèle n'est appelé que pour le segment signalé
    assert "alternative_translations" not in segments[0]  # entrée non modifiée


# --- Corrections manuelles ----------------------------------------------------

def test_edit_replaces_dubbing_text_but_keeps_original_translation():
    segments = [make_segment(1, "It's not the sea to drink.", needs_review=True)]
    result = apply_manual_edits(segments, {1: "  It's not that hard.  "})[0]

    assert result["dubbing_text"] == "It's not that hard."          # espaces retirés
    assert result["translated_text"] == "It's not the sea to drink."  # traduction du modèle conservée
    assert result["adaptation"] == "corrigé à la main"
    assert (result["id"], result["start"], result["end"]) == (1, 0.0, 2.0)


def test_edit_recomputes_duration_and_review_flag():
    long_text = "x" * 100  # 100 car. / 14 ≈ 7,1 s pour 2 s disponibles
    segments = [make_segment(1, long_text, needs_review=True)]

    shorter = apply_manual_edits(segments, {1: "Short."})[0]
    assert shorter["needs_review"] is False
    assert shorter["estimated_duration"] == pytest.approx(6 / 14, abs=0.001)

    still_long = apply_manual_edits(segments, {1: "y" * 90})[0]
    assert still_long["needs_review"] is True  # la correction ne suffit pas : toujours signalé


def test_unchanged_text_is_not_counted_as_an_edit():
    segments = [make_segment(1, "Hello everyone.", needs_review=False)]
    result = apply_manual_edits(segments, {1: "Hello everyone. "})[0]

    assert result["adaptation"] is None


def test_empty_edit_is_rejected():
    with pytest.raises(ValueError, match="id=1.*vide"):
        apply_manual_edits([make_segment(1, "Hello.", needs_review=False)], {1: "   "})


def test_edit_for_unknown_segment_is_rejected():
    with pytest.raises(ValueError, match=r"\[9\]"):
        apply_manual_edits([make_segment(1, "Hello.", needs_review=False)], {9: "Hi."})


def test_edits_do_not_modify_input():
    segments = [make_segment(1, "Hello.", needs_review=False)]
    original = copy.deepcopy(segments)
    apply_manual_edits(segments, {1: "Hi."})

    assert segments == original
