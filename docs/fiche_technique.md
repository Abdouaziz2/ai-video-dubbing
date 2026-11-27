# Fiche technique — AI Video Dubbing (FR → EN)

**Équipe :** Abdou Aziz (extraction, transcription) · Massamba Fall Séne (traduction, intégration,
interface ; voix/synchronisation/vidéo reprises avec l'accord de Baye Serigne) · Baye Serigne.

**Objectif :** doubler une vidéo française en anglais avec une voix clonée autorisée, en
conservant le sens et les repères temporels.

## Chaîne de traitement

Vidéo → **FFmpeg** (audio 16 kHz) → **faster-whisper `base`** (segments horodatés) →
**opus-mt-tc-big-fr-en** (traduction) → adaptation au doublage + **relecture humaine** →
**XTTS-v2** (voix clonée, un audio par segment) → synchronisation (**FFmpeg `atempo`**, ≤ +25 %)
→ assemblage vidéo (**FFmpeg**). Interface **Gradio** ; tout transite en JSON (contrat documenté).

## Choix et mesures

| Élément | Choix | Justification / mesure |
|---|---|---|
| Traduction | opus-mt-tc-big-fr-en (233 M paramètres) | meilleur des 4 modèles testés sur 20 phrases : BLEU 65,6 / chrF 80,3 (NLLB-600M : 59,0 / 77,1) ; 2,2 s/phrase sur CPU |
| Adaptation | règles sûres + signalement `needs_review` | ne jamais changer le sens automatiquement ; l'humain tranche avec des traductions alternatives |
| Transcription | faster-whisper `base` | fonctionne sur CPU ; WER : *à compléter (Abdou Aziz)* |
| Voix | XTTS-v2 | clonage à partir de 10 à 30 s ; CER, débit et similarité : *à compléter après le notebook 05 et le test d'écoute* |
| Synchronisation | accélération ≤ 25 %, pas de ralentissement, pas de superposition | démo de 15 s : écart moyen de 0,13 s (transcription exacte), 0,43 s (Whisper) |
| Performance | Mac Intel i5, 8 Go, CPU | vidéo de 15 s doublée en 34 s (voix de test, modèles en cache) |

## Limites

- Les erreurs de transcription se propagent dans la traduction (« horodatages » → « water retreadings »).
- Les idiomes sont traduits mot à mot ; il n'y a pas de synchronisation labiale.
- La durée n'est qu'estimée avant la synthèse, et certains segments restent trop longs, ce qui est signalé.
- XTTS-v2 : **usage non commercial uniquement** (Coqui Public Model License).

## Éthique

Voix clonée uniquement avec un consentement écrit ; contenu signalé comme synthétique (métadonnées
de la vidéo, interface) ; vidéos créées par l'équipe ou libres de droits.
