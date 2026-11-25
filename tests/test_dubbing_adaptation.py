"""Tests de l'adaptation au doublage (aucun modèle nécessaire)."""
import copy

import pytest

from src.translation import adapt_segments_for_dubbing, apply_shortening_rules, estimate_speech_duration


def make_segment(translated_text, start=0.0, end=10.0, segment_id=1):
    return {"id": segment_id, "start": start, "end": end,
            "original_text": "texte français", "translated_text": translated_text}


# --- Estimation de durée ----------------------------------------------------

def test_estimate_speech_duration():
    assert estimate_speech_duration("a" * 28, chars_per_second=14) == 2.0


def test_estimate_ignores_surrounding_spaces():
    assert estimate_speech_duration("  abcd  ", chars_per_second=2) == 2.0


@pytest.mark.parametrize("bad_rate", [0, -5])
def test_estimate_rejects_invalid_rate(bad_rate):
    with pytest.raises(ValueError):
        estimate_speech_duration("texte", chars_per_second=bad_rate)


# --- Règles de raccourcissement ---------------------------------------------

@pytest.mark.parametrize("text, expected", [
    ("Uh, so, actually, the result is pretty satisfying.", "The result is pretty satisfying."),
    ("Um the demo starts now.", "The demo starts now."),
    ("In order to maintain consistency, we adjusted it.", "To maintain consistency, we adjusted it."),
    ("We stopped due to the fact that it failed.", "We stopped because it failed."),
])
def test_rules_shorten_without_changing_meaning(text, expected):
    shortened, applied = apply_shortening_rules(text)
    assert shortened == expected
    assert applied


@pytest.mark.parametrize("text", [
    "So the model fails on idioms.",       # "so" = "donc" : lien logique, conservé
    "Well-known models were compared.",    # "Well-known" n'est pas une hésitation
    "Sometimes the voice is too slow.",    # "So" dans "Sometimes" : ne doit pas être touché
    "The result is actually good.",        # "actually" au milieu de la phrase : conservé
])
def test_rules_leave_meaningful_words(text):
    assert apply_shortening_rules(text) == (text, [])


def test_rules_do_not_capitalize_a_fragment():
    shortened, _ = apply_shortening_rules("presented in order to win.")
    assert shortened == "presented to win."


# --- Adaptation des segments ------------------------------------------------

def test_segment_that_fits_is_left_unchanged():
    segment = make_segment("Uh, so, the result is good.", end=10.0)  # 27 car. / 14 ≈ 1,9 s
    adapted = adapt_segments_for_dubbing([segment])[0]

    assert adapted["dubbing_text"] == segment["translated_text"]  # hésitations conservées
    assert adapted["adaptation"] is None
    assert adapted["needs_review"] is False
    assert adapted["available_duration"] == 10.0


def test_too_long_segment_is_shortened_by_rules():
    text = "Uh, so, actually, the result is pretty satisfying."  # 50 car. -> ≈ 3,6 s
    adapted = adapt_segments_for_dubbing([make_segment(text, end=3.0)])[0]  # max 3,3 s

    assert adapted["dubbing_text"] == "The result is pretty satisfying."
    assert adapted["translated_text"] == text  # traduction initiale conservée
    assert "hésitations" in adapted["adaptation"]
    assert adapted["needs_review"] is False


def test_segment_still_too_long_is_flagged_for_review():
    text = "We tested the new method and it is much faster than before."
    adapted = adapt_segments_for_dubbing([make_segment(text, end=1.0)])[0]

    assert adapted["dubbing_text"] == text  # aucune règle applicable : texte inchangé
    assert adapted["adaptation"] is None
    assert adapted["needs_review"] is True


def test_contract_fields_are_preserved():
    segment = make_segment("Hello everyone.", start=2.5, end=4.0, segment_id=42)
    adapted = adapt_segments_for_dubbing([segment])[0]

    for field in ("id", "start", "end", "original_text", "translated_text"):
        assert adapted[field] == segment[field]


def test_input_is_not_modified():
    segments = [make_segment("Uh, so, actually, the result is pretty satisfying.", end=1.0)]
    original = copy.deepcopy(segments)
    adapt_segments_for_dubbing(segments)

    assert segments == original


def test_missing_translation_field_is_rejected():
    segment = make_segment("Hello.")
    del segment["translated_text"]

    with pytest.raises(ValueError, match="translated_text"):
        adapt_segments_for_dubbing([segment])
