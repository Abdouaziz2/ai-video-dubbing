# Voix, synchronisation et vidéo : choix techniques

> Partie initialement attribuée à Baye Serigne, reprise par Massamba avec son accord (26/11/2026).

## 1. Modèle de voix : XTTS-v2 (statut : à tester sur Colab)

**Pourquoi XTTS-v2 :** solution proposée dans la répartition officielle de l'équipe. Il clone une
voix à partir d'un court échantillon (environ 10 à 30 s) sans entraînement, et parle anglais.

| Point | Information vérifiée (26/11/2026) | Source |
|---|---|---|
| Paquet | `coqui-tts` 0.28.0 (fork maintenu de Coqui TTS), code MPL-2.0 | PyPI |
| Compatibilité | Python 3.10 à 3.14, torch>=2.2, transformers>=4.57 | métadonnées PyPI |
| Taille | `model.pth` 1,87 Go + `dvae.pth` 0,21 Go ≈ **2,1 Go** | Hugging Face `coqui/XTTS-v2` |
| **Licence du modèle** | Coqui Public Model License 1.0.0 : **usage non commercial uniquement** ; toute personne qui reçoit une sortie doit aussi recevoir l'adresse de la licence | `LICENSE.txt` du dépôt Hugging Face |

Conséquences dans le code :
- la licence n'est **jamais acceptée automatiquement** dans le code : l'utilisateur doit l'accepter
  explicitement (`I_ACCEPT_CPML` dans le notebook, `COQUI_TOS_AGREED=1` pour l'application) ;
- l'adresse de la licence est écrite dans les métadonnées de la vidéo finale.

**Résultats :** pas encore mesurés. Le notebook `notebooks/05_voice_xtts.ipynb` mesure le temps
de génération, le débit réel (caractères/s) et le CER (intelligibilité via Whisper). Les résultats
seront ajoutés ici après exécution. Aucun chiffre n'est avancé avant.

**Alternatives si XTTS-v2 déçoit :** F5-TTS, OpenVoice v2. Leurs licences restent à vérifier.

## 2. Voix de test macOS (pas un résultat du projet)

`MacOSTestVoice` utilise la synthèse intégrée à macOS (`say`, voix « Samantha »). Elle n'est
**pas clonée**. Elle sert seulement à tester toute la chaîne sur le Mac sans télécharger 2 Go.
La vidéo produite le signale dans ses métadonnées, et l'interface affiche un avertissement.

## 3. Synchronisation

| Choix | Raison |
|---|---|
| Accélération sans changement de hauteur (`atempo`) | une voix accélérée reste la même voix |
| Plafond de +25 % | au-delà, la voix devient peu naturelle ; on préfère signaler (`still_too_long`) |
| Jamais de ralentissement | une voix ralentie sonne faux ; un silence en fin de créneau est naturel |
| Pas de superposition : le segment suivant est décalé (`placed_start`) | deux phrases simultanées sont incompréhensibles ; le décalage est enregistré, pas caché |
| Pas de troncature | couper une phrase supprimerait de l'information |

## 4. Assemblage vidéo

- Image copiée sans réencodage (`-c:v copy`) : rapide et sans perte ;
- audio en AAC ; l'ancienne piste française est retirée ;
- métadonnée `comment` : mention « voix synthétique », plus la licence XTTS-v2 si cette voix est utilisée.

## 5. FFmpeg

Homebrew ne fournit plus FFmpeg précompilé pour macOS 12 (compilation de plusieurs heures).
On utilise `imageio-ffmpeg` (binaire FFmpeg 9.0.2 inclus, ~27 Mo, licence du paquet BSD-2).
Le même code fonctionne sur Colab. La variable `FFMPEG_PATH` permet d'utiliser un autre FFmpeg.

## 6. Premier essai réel (Mac, voix de test macOS)

Vidéo de démonstration de 15,2 s : 4 phrases françaises lues par la voix macOS « Thomas », avec
une transcription exacte écrite à la main (et non produite par Whisper).

| id | dispo (s) | audio (s) | accélération | après (s) | écart (s) |
|---|---|---|---|---|---|
| 1 | 1,27 | 1,71 | 1,25 | 1,37 | +0,10 |
| 2 | 3,36 | 3,31 | 1,00 | 3,31 | −0,05 |
| 3 | 5,84 | 5,62 | 1,00 | 5,62 | −0,22 |
| 4 | 2,33 | 2,19 | 1,00 | 2,19 | −0,14 |

- Débit mesuré de la voix macOS : **16,1 car./s**, supérieur aux 14 supposés. Les segments 1 et 2
  étaient donc signalés « à relire » alors que le 2 tient en réalité. Il faut calibrer ce débit avec XTTS-v2.
- Le segment 1 dépasse de 0,10 s, mais sur la pause qui suit : aucun décalage nécessaire.
- Durée totale d'exécution : environ 31 s, dont environ 18 s pour charger le modèle de traduction.

## 7. Reste à faire

1. Exécuter `05_voice_xtts.ipynb` avec un échantillon autorisé, puis reporter les résultats ici.
2. Tester XTTS-v2 dans le pipeline (Colab, ou Mac si l'installation y est validée).
3. Calibrer `chars_per_second` avec le débit mesuré.
4. Test d'écoute à l'aveugle (5 auditeurs) : préparer les extraits et la grille de notation.
