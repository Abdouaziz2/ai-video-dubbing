# Protocole d'évaluation

Mesures demandées dans la répartition officielle, et comment le projet les produit.

| Mesure | Outil | État |
|---|---|---|
| WER de la transcription (échantillon corrigé) | partie d'Abdou Aziz | à faire |
| Qualité et fidélité de la traduction | BLEU / chrF + analyse humaine (`docs/translation_model_choice.md`) | fait |
| Différence de durée par segment | `summarize_durations` (`src/evaluation`) sur `final_segments.json` | fait sur la démo (voix de test) ; à refaire avec XTTS-v2 |
| Similarité vocale, 5 auditeurs, à l'aveugle | `prepare_listening_test` / `summarize_ratings` | outils prêts ; à faire avec XTTS-v2 |
| CER de la voix synthétique | Whisper relit l'audio généré (`notebooks/05_voice_xtts.ipynb`) | à faire avec XTTS-v2 |

## 1. Différence de durée par segment

`duration_difference = aligned_duration - available_duration` (après accélération éventuelle) :
positif = dépassement, négatif = silence restant. Résumé sur la vidéo de démo de 15 s
(voix de test macOS, **pas** la voix clonée) :

| Transcription | Segments | Écart absolu moyen | Dépassement max | Accélérés | Décalés |
|---|---|---|---|---|---|
| exacte (écrite à la main) | 4 | 0,13 s | 0,10 s | 1 | 0 |
| Whisper `base` | 5 | 0,43 s | 0,37 s | 2 | 2 |

Avec Whisper, les segments se touchent (pas de pause entre eux) et une phrase est coupée en
deux : les écarts sont plus grands et deux segments sont décalés pour éviter une superposition.

## 2. Test d'écoute à l'aveugle (similarité de voix)

**Matériel :**
- l'échantillon de référence (vraie voix) ;
- 3 extraits de la **vraie** voix (autres phrases que la référence) : témoins ;
- 5 extraits de la voix **clonée** (sorties de XTTS-v2).

**Préparation :**
```python
from src.evaluation import prepare_listening_test
prepare_listening_test(["vraie_1.wav", "vraie_2.wav", "vraie_3.wav"],
                       ["clone_1.wav", "clone_2.wav", "clone_3.wav", "clone_4.wav", "clone_5.wav"],
                       "data/output/test_ecoute", seed=0)
```
Ce code crée `clips/clip_01.wav…` (ordre aléatoire, noms anonymes), `grille_notation.csv`
et `cle_NE_PAS_MONTRER.csv`.

**Déroulement, pour chacun des 5 auditeurs :** écouter la référence, puis chaque clip, et répondre
à « Est-ce la même personne que la référence ? » de **1** (pas du tout) à **5** (certainement).
L'auditeur ne sait pas quels clips sont clonés. Les notes vont dans la grille.

**Résultat :**
```python
from src.evaluation import summarize_ratings
summarize_ratings("data/output/test_ecoute/grille_notation.csv",
                  "data/output/test_ecoute/cle_NE_PAS_MONTRER.csv")
```
On compare la moyenne de la voix clonée à celle des vraies voix témoins, pas à 5.

**Limites :** 5 auditeurs, c'est peu, donc pas de conclusion statistique, seulement une tendance.
Les auditeurs qui connaissent la personne jugent différemment des autres : le noter.

## 3. CER de la voix synthétique

Whisper retranscrit chaque audio généré, et on compte les erreurs de caractères par rapport au texte demandé
(`notebooks/05_voice_xtts.ipynb`, section 7). Une erreur de Whisper compte aussi comme une erreur
de la voix : le CER mesure l'intelligibilité « pour une machine », à compléter par l'écoute.
