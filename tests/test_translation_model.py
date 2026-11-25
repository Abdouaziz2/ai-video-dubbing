"""Test d'intégration avec le VRAI modèle (lent : téléchargement + chargement).

Lancement explicite : pytest -m slow
Ignoré automatiquement si torch ou transformers ne sont pas installés.
"""
import pytest

pytest.importorskip("torch")
pytest.importorskip("transformers")

from src.translation import DEFAULT_MODEL_NAME, HuggingFaceTranslator, translate_segments


@pytest.fixture(scope="module")
def translator():
    # scope="module" : le modèle est chargé une seule fois pour tous les tests du fichier.
    return HuggingFaceTranslator(DEFAULT_MODEL_NAME)


@pytest.mark.slow
def test_real_model_keeps_contract(translator):
    segments = [
        {"id": 1, "start": 0.0, "end": 3.5, "text": "Bonjour à tous."},
        {"id": 2, "start": 3.5, "end": 6.2, "text": "Bienvenue dans notre présentation."},
    ]

    result = translate_segments(segments, translator)

    assert [(s["id"], s["start"], s["end"]) for s in result] == [(1, 0.0, 3.5), (2, 3.5, 6.2)]
    assert [s["original_text"] for s in result] == [s["text"] for s in segments]
    # On ne vérifie pas une phrase exacte : elle varie selon la version et la précision
    # (Mac float32 : "Good morning, everybody." ; Colab float16 : "Hello everyone...").
    # On vérifie seulement des mots qui prouvent une vraie traduction vers l'anglais.
    greeting = result[0]["translated_text"].lower()
    assert any(word in greeting for word in ("hello", "good morning", "hi ")), greeting
    assert "welcome" in result[1]["translated_text"].lower()


@pytest.mark.slow
def test_real_model_uses_float32(translator):
    assert next(translator.model.parameters()).dtype.is_floating_point
    assert str(next(translator.model.parameters()).dtype) == "torch.float32"


@pytest.mark.slow
def test_candidates_start_with_the_main_translation(translator):
    text = "Je vais vous présenter notre projet en quelques minutes."
    candidates = translator.translate_candidates(text, num_candidates=4)

    assert candidates[0] == translator.translate(text)
    assert len(candidates) == len(set(candidates))  # pas de doublons


@pytest.mark.slow
def test_too_many_candidates_is_rejected(translator):
    with pytest.raises(ValueError, match="num_beams"):
        translator.translate_candidates("Bonjour.", num_candidates=10)
