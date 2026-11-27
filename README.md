# AI Video Dubbing

Projet de doublage vidéo automatisé par intelligence artificielle.

## Description
Ce projet vise à traduire et doubler des vidéos automatiquement en utilisant l'IA :
- Transcription audio (Speech-to-Text)
- Traduction de texte
- Synthèse vocale (Text-to-Speech)
- Synchronisation audio/vidéo

## Installation

Il faut Python 3.10 ou plus récent et FFmpeg. Les commandes ci-dessous sont à
lancer depuis la racine du dépôt.

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
