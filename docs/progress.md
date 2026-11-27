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

## 25/11/2026 — Phase 5 : adaptation au doublage + publication

**Objectif :** adapter les traductions à la durée de chaque segment sans changer le sens.

**Fichiers :** `src/translation/dubbing_adaptation.py`, `tests/test_dubbing_adaptation.py`, `docs/data_contract.md`

**Décisions :**
- `translated_text` n'est jamais modifié. Le texte prononcé va dans `dubbing_text`.
- Seules des règles sûres sont appliquées : hésitations en début de phrase, « in order to », « due to the fact that ».
- Ce qui dépasse encore est signalé (`needs_review`), pas réécrit automatiquement.
- Abandon du choix automatique parmi plusieurs traductions : chrF ne détecte pas les erreurs de sens.

**Tests :** 43 tests rapides et 4 tests lents réussis.

**Git :** branche `feature/translation` poussée, puis fusionnée dans `main`.

## 26–27/11/2026 — Voix, synchronisation, vidéo, pipeline, Gradio

**Objectif :** reprendre la partie de Baye Serigne (avec son accord) et réaliser le pipeline et l'interface.

**Fichiers :** `src/ffmpeg_utils.py`, `src/voice/`, `src/synchronization/`, `src/video/`, `src/pipeline.py`,
`src/translation/manual_review.py`, `app/gradio_app.py`, `notebooks/05_voice_xtts.ipynb`,
`docs/voice_model_choice.md`, `docs/data_contract.md` (parties 3 et 4), `requirements*.txt`,
`tests/test_voice.py`, `tests/test_pipeline.py`, `tests/test_manual_review.py`

**Décisions :**
- FFmpeg via `imageio-ffmpeg`, parce que Homebrew n'a pas de version précompilée pour macOS 12.
- Gradio 6.17.3 : les versions plus récentes sont incompatibles avec transformers 4.57.
- Synchronisation : accélération de +25 % au maximum, jamais de ralentissement ni de troncature, pas de superposition (`placed_start`).
- XTTS-v2 sous licence CPML (usage non commercial). La licence n'est jamais acceptée automatiquement et son adresse est écrite dans la vidéo.
- Relecture humaine dans Gradio : traductions alternatives et correction de `dubbing_text`.
- Voix de test macOS (non clonée) pour tester la chaîne sur le Mac.

**Tests :**
- 76 tests rapides réussis.
- Exécution réelle sur une vidéo de démo de 15 s : vidéo doublée produite en 31 s.
- Même parcours testé dans l'interface, relecture comprise.

**Résultats :**
- Le débit de la voix macOS est de 16 caractères/s, contre 14 supposés : il faudra calibrer avec XTTS-v2.
- La relecture a supprimé le seul dépassement de la démo (segment 1).

**Git :** branche `feature/voice-pipeline` (3 commits), Pull Request #1 ouverte.

**Problèmes restants :**
- XTTS-v2 pas encore exécuté : il faut un échantillon de voix autorisé.
- Transcription Whisper (Aziz) pas encore branchée.
- Test d'écoute avec 5 auditeurs à faire.

**Prochaine étape :** enregistrer la voix de référence et exécuter `05_voice_xtts.ipynb` sur Colab.
