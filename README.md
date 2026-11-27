# AI Video Dubbing

Doublage automatique d'une vidéo du **français vers l'anglais** : transcription, traduction,
voix anglaise générée (voix clonée avec autorisation), synchronisation et assemblage vidéo.

> **La voix produite est synthétique.** N'utiliser que sa propre voix ou une voix dont la
> personne a donné son accord écrit. Chaque vidéo produite le signale dans ses métadonnées.

## Pipeline

| Étape | Outil | Module | Responsable |
|---|---|---|---|
| 1. Extraction audio | FFmpeg | `src/extraction/` | Abdou Aziz |
| 2. Transcription française horodatée | faster-whisper | `src/transcription/` | Abdou Aziz |
| 3. Traduction FR → EN + adaptation au doublage | `Helsinki-NLP/opus-mt-tc-big-fr-en` | `src/translation/` | Massamba |
| — Relecture humaine des segments signalés | interface Gradio | `src/translation/manual_review.py` | Massamba |
| 4. Voix anglaise, un audio par segment | XTTS-v2 (voix clonée) | `src/voice/` | Baye Serigne → repris par Massamba |
| 5. Synchronisation (vitesse ≤ +25 %, sans superposition) | FFmpeg `atempo` | `src/synchronization/` | idem |
| 6. Assemblage vidéo | FFmpeg | `src/video/` | idem |

Orchestration : `src/pipeline.py` ; interface : `app/gradio_app.py`.
Format des données échangées entre les étapes : [`docs/data_contract.md`](docs/data_contract.md).

## Utilisation rapide

Interface (depuis la racine du dépôt, environnement installé, voir plus bas) :

```bash
.venv/bin/python -m app.gradio_app        # Windows : .\.venv\Scripts\python.exe -m app.gradio_app
```

Ouvrir http://127.0.0.1:7860, puis :
1. déposer la vidéo (et, facultatif, une transcription JSON ; sinon Whisper transcrit) → **1. Traduire** ;
2. relire le tableau : les segments « à relire » ont des traductions alternatives, la colonne
   `dubbing_text` (texte prononcé) est modifiable ;
3. choisir la voix → **2. Générer la voix et la vidéo**.

Ligne de commande (sans relecture) :

```bash
.venv/bin/python -m src.pipeline --video data/input/video.mp4 --voice macos-test
#   --transcription fichier.json   : utiliser une transcription existante au lieu de Whisper
#   --voice xtts --reference ma_voix.wav : voix clonée (voir « Modèles et licences »)
```

Les résultats de chaque exécution sont dans `data/output/run_<date>/` : transcription,
traduction, traduction relue, audios par segment, piste anglaise, vidéo doublée et
`final_segments.json` (durées et ajustements par segment).

La voix `macos-test` (synthèse intégrée à macOS) **n'est pas clonée** : elle sert uniquement à
tester la chaîne sans télécharger XTTS-v2.

## Installation

Il faut Python 3.10 ou plus récent. FFmpeg est fourni par le paquet Python
`imageio-ffmpeg` (dans `requirements.txt`) ; un FFmpeg système reste utile pour les
commandes manuelles ci-dessous. Les commandes sont à lancer depuis la racine du dépôt.

### Mac Intel

PyTorch ne publie plus de version récente pour les Mac Intel : des versions précises sont
imposées dans `requirements-mac-intel.txt` (torch 2.2.2, transformers 4.57, numpy < 2, gradio 6.17.3).

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-mac-intel.txt -r requirements-dev.txt
.venv/bin/python -m pytest -q
```

### Windows (PowerShell)

Installez FFmpeg (par exemple avec WinGet), puis ouvrez un nouveau terminal :

```powershell
winget install --id Gyan.FFmpeg.Shared -e
ffmpeg -version
```

Créez un environnement Python et installez les dépendances du projet :

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
```

Placez une vidéo de test (créée par l’équipe ou libre de droits) dans
`data/input/`, par exemple `data/input/video.mp4`.

### Google Colab

Activez un GPU dans **Exécution → Modifier le type d'exécution → GPU**, puis
exécutez les cellules suivantes :

```python
!git clone https://github.com/Abdouaziz2/ai-video-dubbing.git
%cd ai-video-dubbing
!apt-get -qq update
!apt-get -qq install -y ffmpeg
!pip install -r requirements.txt -r requirements-dev.txt
```

Téléversez une vidéo créée par l’équipe ou libre de droits dans le notebook,
puis définissez `video_path` ci-dessous avec le chemin réellement affiché par
Colab (souvent `/content/nom_de_la_video.mp4`).

## Tester l'extraction audio et la transcription

Le module d'extraction produit un WAV mono à 16 kHz. Faster-Whisper transcrit
ensuite en français et retourne les segments horodatés au format commun
`{"segments": [...]}`. Le premier lancement télécharge le modèle Whisper choisi.

### Tests automatiques rapides

Ces tests n'ont pas besoin de vidéo, de GPU ni de téléchargement du modèle :

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Sur Colab, utilisez plutôt :

```python
!pytest -q
```

### Essai réel du pipeline

Sur Windows, depuis PowerShell, en adaptant le chemin si ta vidéo porte un
autre nom :

```powershell
@'
from src.extraction import extract_audio_from_video
from src.transcription import transcribe_audio

audio_path = extract_audio_from_video(
    r"data\input\video.mp4",
    r"data\intermediate\audio.wav",
)
result = transcribe_audio(
    audio_path,
    r"data\intermediate\transcription_fr.json",
    model_size="base",
    language="fr",
    device="auto",
)
print(f"Segments transcrits : {len(result['segments'])}")
for segment in result["segments"][:5]:
    print(segment)
'@ | .\.venv\Scripts\python.exe -
```

Dans Colab, après avoir défini le chemin de la vidéo téléversée, lancez :

```python
from src.extraction import extract_audio_from_video
from src.transcription import transcribe_audio

video_path = "/content/nom_de_la_video.mp4"  # Remplacer par le vrai nom
audio_path = extract_audio_from_video(
    video_path,
    "data/intermediate/audio.wav",
)
result = transcribe_audio(
    audio_path,
    "data/intermediate/transcription_fr.json",
    model_size="base",
    language="fr",
    device="auto",
)
print(f"Segments transcrits : {len(result['segments'])}")
for segment in result["segments"][:5]:
    print(segment)
```

L'audio et le JSON sont enregistrés dans `data/intermediate/`. Le JSON est
également retourné en mémoire et conserve pour chaque segment un `id`, les
timestamps `start`/`end` en secondes et le texte `text`. Le modèle `base` est un
point de départ; `small` peut être comparé sur le même extrait. `device="auto"`
utilise CUDA si Faster-Whisper le détecte, sinon le CPU; on peut aussi imposer
`device="cpu"` ou `device="cuda"`.

### Dépannage

- **FFmpeg introuvable** : vérifiez `ffmpeg -version`, puis redémarrez le
  terminal après installation.
- **Vidéo/audio introuvable** : vérifiez le chemin et le nom exact du fichier.
- **Premier lancement lent** : le modèle Whisper est téléchargé une fois, puis
  mis en cache. Une vidéo longue peut aussi prendre du temps sur CPU.
- **CUDA indisponible** : le mode automatique utilise le CPU; dans Colab,
  vérifiez que le GPU est activé avant d'exécuter le notebook.
- Les fichiers placés dans `data/` sont ignorés par Git; ne versionnez pas de
  médias privés ni de voix sans consentement explicite.

## Modèles et licences

| Élément | Licence | Remarque |
|---|---|---|
| `Helsinki-NLP/opus-mt-tc-big-fr-en` (traduction) | CC-BY-4.0 | choisi après comparaison de 4 modèles, voir `docs/translation_model_choice.md` |
| faster-whisper + ctranslate2 (transcription) | MIT | modèle `Systran/faster-whisper-base` : MIT |
| **XTTS-v2** (voix clonée) | **Coqui Public Model License : usage non commercial uniquement** | licence à accepter explicitement ; son adresse est écrite dans chaque vidéo produite. Voir `docs/voice_model_choice.md` |
| coqui-tts (code) | MPL-2.0 | installé séparément : `requirements-voice.txt` |
| FFmpeg via imageio-ffmpeg | paquet : BSD-2 ; binaire FFmpeg : GPL (compilé avec libx264) | utilisé comme programme externe |
| Gradio | Apache-2.0 | |

## Tests

```bash
.venv/bin/python -m pytest -q          # tests rapides, sans modèle
.venv/bin/python -m pytest -m slow     # tests avec le vrai modèle de traduction
```

## Limites connues

- **Transcription** : une erreur de Whisper se propage dans la traduction (ex. « horodatages »
  entendu « eaux redattages » → « water retreadings ») ; Whisper peut couper une phrase en deux.
- **Traduction** : les expressions idiomatiques sont souvent traduites mot à mot ; le
  « vous » singulier/pluriel n'est pas toujours bien rendu.
- **Durée** : la durée de parole est d'abord *estimée* (caractères ÷ débit) ; la vraie durée
  n'est connue qu'après la synthèse. Un segment trop long est accéléré d'au plus 25 %, puis
  signalé (`still_too_long`) ; le segment suivant peut être légèrement décalé (`placed_start`).
- **Synchronisation labiale** : non traitée (seuls les débuts de phrases sont alignés).
- **Mac Intel** : faster-whisper et PyTorch ne peuvent pas tourner dans le même processus
  (conflit OpenMP) ; la transcription est donc lancée dans un processus séparé.

## Éthique et données

- Voix clonée : uniquement avec un consentement écrit de la personne enregistrée.
- Vidéos : créées par l'équipe ou libres de droits ; indiquer leurs sources dans ce README.
- Le contenu produit est signalé comme synthétique (métadonnées de la vidéo, interface).
- Les médias (`data/`), les voix et les modèles ne sont pas versionnés.

## Documentation

- `docs/data_contract.md` : format JSON échangé entre les modules
- `docs/translation_model_choice.md` : comparaison et choix du modèle de traduction
- `docs/voice_model_choice.md` : voix, synchronisation, vidéo
- `docs/progress.md` : journal de progression
- `notebooks/` : expériences (comparaison des modèles, évaluation, transcription, voix XTTS-v2)
