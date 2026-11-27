# Contrat de données entre les modules

Tous les fichiers sont en JSON UTF-8, avec une clé racine `segments` (liste ordonnée par `start`).
**Règle commune :** `id`, `start` et `end` ne sont jamais modifiés d'une étape à l'autre.

## 1. Transcription → Traduction (produit par Abdou Aziz)

```json
{"segments": [{"id": 1, "start": 0.0, "end": 3.5, "text": "Bonjour à tous."}]}
```

| Champ | Type | Contrainte |
|---|---|---|
| `id` | entier | unique |
| `start`, `end` | nombre (secondes) | `0 <= start < end` |
| `text` | texte | non vide |

Les segments doivent être triés par `start`. Les champs supplémentaires (ex. infos Whisper)
sont acceptés mais ne sont pas transmis à l'étape suivante.
Validation : `src/translation/translation_utils.py::validate_transcription_segments`.

## 2. Traduction → Voix (produit par Massamba)

```json
{"segments": [{
  "id": 17, "start": 40.0, "end": 50.0,
  "original_text": "Afin de conserver la cohérence...",
  "translated_text": "In order to maintain consistency...",
  "dubbing_text": "To maintain consistency...",
  "available_duration": 10.0,
  "estimated_duration": 11.2,
  "adaptation": "règles : 'in order to' -> 'to'",
  "needs_review": false
}]}
```

| Champ | Rôle |
|---|---|
| `original_text` | Texte français de la transcription |
| `translated_text` | Traduction fidèle du modèle — **jamais modifiée** |
| `dubbing_text` | **Texte à faire prononcer par la voix.** Égal à `translated_text` si aucune adaptation |
| `available_duration` | `end - start` (secondes) |
| `estimated_duration` | Estimation de durée de parole de `dubbing_text` (caractères ÷ débit) — **indicatif** |
| `adaptation` | Description de l'adaptation appliquée, ou `null` |
| `needs_review` | `true` si le texte risque encore de dépasser : à relire avant la synthèse |

| `alternative_translations` | Autres traductions proposées par le modèle, **seulement** pour les segments `needs_review` (liste vide sinon) |

**Relecture humaine (interface Gradio) :** le relecteur peut remplacer `dubbing_text` par une
proposition ou son propre texte. `translated_text` reste inchangé, `adaptation` vaut alors
`"corrigé à la main"` et `needs_review` est recalculé. La version relue est enregistrée dans
`translation_reviewed.json` (fonction `apply_manual_edits`, `src/translation/manual_review.py`).

**Pour le module voix (Baye Serigne) :** utiliser `dubbing_text` pour la synthèse.
Le débit de parole utilisé pour l'estimation (14 caractères/s par défaut) doit être calibré
avec la vraie voix de synthèse : mesurer la durée de quelques phrases générées et
communiquer le débit réel (caractères ÷ secondes).

## 3. Voix → Synchronisation (`src/voice/voice_cloning.py`)

Chaque segment de l'étape 2 reçoit deux champs (tous les champs précédents sont conservés) :

| Champ | Rôle |
|---|---|
| `audio_file` | Chemin du WAV généré : `segment_0001.wav` pour `id` = 1 |
| `audio_duration` | Durée **mesurée** de l'audio (secondes) |

Le débit réel de la voix (`measure_speech_rate`) remplace l'estimation de 14 caractères/s.

## 4. Synchronisation → Vidéo (`src/synchronization/audio_alignment.py`)

| Champ | Rôle |
|---|---|
| `aligned_audio_file` | Audio converti (mono, 16 bits, 24 kHz), accéléré si nécessaire |
| `speed_factor` | Accélération appliquée : 1.0 = aucune, maximum 1.25 ; jamais de ralentissement |
| `aligned_duration` | Durée après ajustement (secondes) |
| `duration_difference` | `aligned_duration - available_duration` : > 0 dépasse, < 0 silence restant |
| `still_too_long` | `true` si l'audio dépasse encore (tolérance 50 ms) |
| `placed_start` | Instant où l'audio est réellement posé. Égal à `start`, sauf si le segment précédent déborde : il est alors décalé pour éviter une superposition |

`start` et `end` ne sont jamais modifiés : le décalage éventuel est visible dans `placed_start`.
Le fichier `final_segments.json` de chaque exécution contient tous ces champs : c'est la base
de la mesure « différence de durée par segment » demandée dans la répartition.
