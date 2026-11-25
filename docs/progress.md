# Journal de progression — partie NLP et intégration (Massamba)

## 25/11/2026 — Phases 1 à 4

**Objectif :** préparer l'environnement, choisir le modèle de traduction, développer le module de traduction.

**Fichiers créés ou modifiés :**
- `.gitignore` (ajouts : contenu de `data/*`, poids de modèles, caches), `data/*/.gitkeep`
- `requirements.txt`, `requirements-mac-intel.txt`, `requirements-dev.txt`, `pytest.ini`
- `notebooks/translation_test_set.json`, `notebooks/01_model_exploration.ipynb`, `notebooks/03_translation_evaluation.ipynb`
- `docs/experiments/01_cpu_2026-11-25/` (résultats bruts), `docs/translation_model_choice.md`
- `src/translation/` (`__init__.py`, `translation_utils.py`, `text_translation.py`)
- `tests/test_translation.py`, `tests/test_translation_model.py`

**Décisions :**
- Environnement local : `.venv` Python 3.12.0 ; torch 2.2.2, transformers 4.57.6, numpy 1.26.4, sentencepiece 0.2.1
  (versions imposées par le Mac Intel, voir `requirements-mac-intel.txt`).
- Modèle retenu : `Helsinki-NLP/opus-mt-tc-big-fr-en` ; alternative : `nllb-200-distilled-600M`.
- Le modèle est injecté dans `translate_segments(segments, translator)` : changer de modèle ne touche pas la logique.
- Modèle chargé en float32 sur toutes les machines.

**Commandes et tests exécutés :**
- Notebook 01 sur Colab CPU (pas de quota GPU) : 4 modèles × 24 phrases.
- Notebook 03 sur le Mac : BLEU / chrF (tc-big : 65,6 / 80,3, meilleur des 4).
- `pytest` : 24 tests rapides réussis ; `pytest -m slow` : 2 tests avec le vrai modèle réussis.
- Mesure sur le Mac : chargement 18,2 s, 2,16 s par segment.

**Problèmes rencontrés :**
- Quota GPU Colab épuisé, puis déconnexion de Colab → exécution sur CPU.
- `sentencepiece` 0.2.3 sans wheel pour macOS x86_64 → version fixée à < 0.2.2.
- Test trop strict ("hello" attendu, "Good morning" obtenu) → test corrigé.

**Problèmes restants :**
- Idiomes traduits mot à mot (« Ce n'est pas la mer à boire »), « vous-mêmes » rendu au singulier.
- Vidéo de test commune pas encore choisie par l'équipe.
- Rien n'est encore commité sur GitHub.

**Prochaine étape :** Phase 5 — adaptation au doublage (durées des segments).
