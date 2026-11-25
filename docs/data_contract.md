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

**Pour le module voix (Baye Serigne) :** utiliser `dubbing_text` pour la synthèse.
Le débit de parole utilisé pour l'estimation (14 caractères/s par défaut) doit être calibré
avec la vraie voix de synthèse : mesurer la durée de quelques phrases générées et
communiquer le débit réel (caractères ÷ secondes).

## 3. Voix → Synchronisation (à définir avec Baye Serigne)

Proposition : ajouter à chaque segment `audio_file` (chemin du fichier généré) et
`audio_duration` (durée réelle mesurée, en secondes).
