# Choix du modèle de traduction FR → EN

**Décision (25/11/2026) :** modèle principal `Helsinki-NLP/opus-mt-tc-big-fr-en` (MarianMT).
Alternative documentée : `facebook/nllb-200-distilled-600M`.

Le module de traduction prend le modèle en paramètre : changer de modèle ne demande
pas de réécrire le pipeline.

## 1. Protocole

- **Jeu de test :** `notebooks/translation_test_set.json` — 24 phrases de style présentation orale,
  réparties en 10 catégories de difficulté (pronoms ambigus, idiomes, hésitations, noms propres,
  phrases coupées en deux segments…). Références anglaises rédigées par l'équipe (une par phrase).
- **Modèles comparés :** opus-mt-fr-en, opus-mt-tc-big-fr-en, m2m100_418M, nllb-200-distilled-600M.
- **Conditions :** Google Colab **CPU** (pas de GPU disponible), Python 3.13, torch 2.14.1,
  transformers 5.22.1, `num_beams=4`, `max_new_tokens=256`, traduction phrase par phrase,
  une traduction d'échauffement non mesurée. Une seule exécution.
- **Notebooks :** `01_model_exploration.ipynb` (traductions, temps, mémoire),
  `03_translation_evaluation.ipynb` (BLEU, chrF avec sacrebleu 2.6.0).
- **Résultats bruts :** `docs/experiments/01_cpu_2026-11-25/`.

## 2. Résultats

| Modèle | Param. | Temps moyen / phrase (CPU) | BLEU | chrF | Licence |
|---|---|---|---|---|---|
| opus-mt-fr-en | 75 M | 0,71 s | 58,7 | 75,6 | Apache-2.0 |
| **opus-mt-tc-big-fr-en** | 233 M | 2,18 s* | **65,6** | **80,3** | CC-BY-4.0 |
| m2m100_418M | 484 M | 4,95 s | 59,0 | 75,9 | MIT |
| nllb-200-distilled-600M | 615 M | 6,44 s | 59,0 | 77,1 | CC-BY-NC-4.0 |

BLEU et chrF calculés sur 20 phrases (les 4 fragments de phrases coupées sont exclus).

\* tc-big a été chargé en demi-précision (comportement par défaut de transformers 5 pour ce
fichier) ; les autres modèles en float32. Son temps n'est donc pas mesuré dans des conditions
strictement identiques.

## 3. Analyse humaine (points décisifs)

- **opus-mt-fr-en** : rapide, mais erreurs de sens (*horodatages* → *clocks*), pronom mal résolu
  sans contexte (*She's a lot faster*), fragment laissé en français (*Baye Serigne de la voix*).
- **m2m100_418M** : éliminé — sens perdu (*we had a bit of synchronization*), mauvais sujet
  (*We will present* pour « Je vais vous présenter »), anglais incorrect (*risks to exceed*).
- **opus-mt-tc-big-fr-en** : aucune erreur de sens grave observée, bon traitement du contexte
  (pronoms, *timestamps*, *struggled*). Faiblesse : tournure orale maladroite (id 16).
- **nllb-200-distilled-600M** : anglais le plus naturel à l'oral (ids 16, 24), pas d'erreur grave,
  mais 3 fois plus lent, plus lourd, et licence non commerciale.
- **Tous les modèles** traduisent l'idiome « Ce n'est pas la mer à boire » mot à mot
  (*It's not the sea to drink*) et perdent le pluriel de « vous-mêmes ».

## 4. Justification du choix

1. Meilleurs scores BLEU et chrF, cohérents avec l'analyse humaine.
2. Aucune erreur de sens grave sur notre jeu de test.
3. Compatible avec un Mac Intel 8 Go (~0,9 Go en float32) et rapide sur CPU.
4. Licence CC-BY-4.0 : usage permis, y compris commercial, à condition de citer les auteurs
   (Helsinki-NLP / OPUS-MT).

## 5. Limites de cette évaluation

- **20 phrases seulement** : l'écart tc-big / NLLB (≈ 3 points de chrF) n'est pas statistiquement établi.
- **Une seule référence par phrase**, rédigée par une seule personne : un synonyme correct est pénalisé.
  Exemples observés : id 10 (*It's a lot faster*, correct, chrF 39,3) ; id 13 (m2m100 perd le sens
  mais obtient un meilleur chrF que NLLB).
- **Phrases inventées**, pas encore issues d'une vraie transcription Whisper : à refaire sur la vidéo
  de démonstration quand elle existera.
- **Temps mesurés sur le CPU de Colab**, une seule exécution : les temps sur le Mac seront différents.
- Les idiomes et le naturel oral ne sont résolus par aucun modèle : traités en Phase 5 (adaptation au doublage).
