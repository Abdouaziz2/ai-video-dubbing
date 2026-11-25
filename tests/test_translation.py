"""Tests de la logique de traduction (sans modèle réel).

FakeTranslator NE traduit PAS : il préfixe le texte par "EN: ". Il permet de vérifier
que translate_segments conserve id, timestamps et ordre, indépendamment du modèle.
"""
import copy
import json

import pytest

from src.translation import (
    load_segments,
    save_segments,
    translate_segments,
    validate_transcription_segments,
)


class FakeTranslator:
    """Faux traducteur pour les tests : renvoie 'EN: <texte>'."""

    def __init__(self):
        self.calls = []

    def translate(self, text):
        self.calls.append(text)
        return f"EN: {text}"


class FailingTranslator:
    """Simule un modèle qui plante sur un texte précis."""

    def translate(self, text):
        if "plante" in text:
            raise OSError("erreur simulée du modèle")
        return "ok"


class EmptyTranslator:
    """Simule un modèle qui renvoie une traduction vide."""

    def translate(self, text):
        return "   "


@pytest.fixture
def segments():
    return [
        {"id": 1, "start": 0.0, "end": 3.5, "text": "Bonjour à tous."},
        {"id": 2, "start": 3.5, "end": 6.2, "text": "Bienvenue dans notre présentation."},
        {"id": 7, "start": 6.2, "end": 9, "text": "Merci."},
    ]


# --- Cas normal --------------------------------------------------------------

def test_output_follows_contract(segments):
    result = translate_segments(segments, FakeTranslator())

    assert result[0] == {
        "id": 1,
        "start": 0.0,
        "end": 3.5,
        "original_text": "Bonjour à tous.",
        "translated_text": "EN: Bonjour à tous.",
    }


def test_ids_timestamps_and_order_are_preserved(segments):
    result = translate_segments(segments, FakeTranslator())

    assert [s["id"] for s in result] == [1, 2, 7]
    assert [(s["start"], s["end"]) for s in result] == [(0.0, 3.5), (3.5, 6.2), (6.2, 9)]


def test_each_segment_translated_once_in_order(segments):
    translator = FakeTranslator()
    translate_segments(segments, translator)

    assert translator.calls == [s["text"] for s in segments]


def test_input_is_not_modified(segments):
    original = copy.deepcopy(segments)
    translate_segments(segments, FakeTranslator())

    assert segments == original


def test_extra_input_fields_are_not_forwarded(segments):
    segments[0]["avg_logprob"] = -0.2
    result = translate_segments(segments, FakeTranslator())

    assert "avg_logprob" not in result[0]


# --- Validation de l'entrée -------------------------------------------------

@pytest.mark.parametrize("bad_segments, message", [
    ([], "vide"),
    ("pas une liste", "liste"),
    ([{"id": 1, "start": 0, "end": 1}], "manquant"),
    ([{"id": "1", "start": 0, "end": 1, "text": "a"}], "entier"),
    ([{"id": True, "start": 0, "end": 1, "text": "a"}], "entier"),
    ([{"id": 1, "start": 0, "end": 1, "text": "a"},
      {"id": 1, "start": 1, "end": 2, "text": "b"}], "dupliqué"),
    ([{"id": 1, "start": "0", "end": 1, "text": "a"}], "nombres"),
    ([{"id": 1, "start": float("nan"), "end": 1, "text": "a"}], "nombres"),
    ([{"id": 1, "start": -1, "end": 1, "text": "a"}], "négatif"),
    ([{"id": 1, "start": 2, "end": 2, "text": "a"}], "supérieur"),
    ([{"id": 1, "start": 0, "end": 1, "text": "   "}], "vide"),
    ([{"id": 1, "start": 5, "end": 6, "text": "a"},
      {"id": 2, "start": 1, "end": 2, "text": "b"}], "chronologique"),
])
def test_invalid_segments_are_rejected(bad_segments, message):
    with pytest.raises(ValueError, match=message):
        validate_transcription_segments(bad_segments)


def test_nothing_is_translated_when_input_is_invalid(segments):
    segments[2]["text"] = ""
    translator = FakeTranslator()

    with pytest.raises(ValueError):
        translate_segments(segments, translator)
    assert translator.calls == []  # validation AVANT traduction : pas de calcul inutile


# --- Erreurs du modèle ------------------------------------------------------

def test_model_error_names_the_failing_segment(segments):
    segments[1]["text"] = "Ici le modèle plante."

    with pytest.raises(RuntimeError, match="id=2") as error_info:
        translate_segments(segments, FailingTranslator())
    assert isinstance(error_info.value.__cause__, OSError)  # l'erreur d'origine est conservée


def test_empty_translation_is_rejected(segments):
    with pytest.raises(ValueError, match="id=1"):
        translate_segments(segments, EmptyTranslator())


# --- Lecture / écriture JSON ------------------------------------------------

def test_save_then_load_roundtrip(tmp_path, segments):
    path = tmp_path / "sub" / "segments.json"
    save_segments(segments, path)

    assert load_segments(path) == segments
    assert "Bienvenue dans notre présentation" in path.read_text(encoding="utf-8")  # accents lisibles


def test_load_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_segments(tmp_path / "absent.json")


def test_load_invalid_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{ pas du json", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        load_segments(path)


def test_load_without_segments_key(tmp_path):
    path = tmp_path / "no_key.json"
    path.write_text('{"items": []}', encoding="utf-8")

    with pytest.raises(ValueError, match="segments"):
        load_segments(path)
