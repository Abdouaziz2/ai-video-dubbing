"""Petits outils communs pour appeler FFmpeg depuis Python.

FFmpeg est fourni par le paquet `imageio-ffmpeg` (binaire inclus, environ 27 Mo) :
pas besoin de Homebrew, et le même code marche sur le Mac et sur Colab.
Si un FFmpeg système existe déjà (ex. `apt install ffmpeg`), on peut le forcer
avec la variable d'environnement FFMPEG_PATH.
"""
import os
import re
import subprocess
from pathlib import Path


def get_ffmpeg_path():
    """Chemin de l'exécutable FFmpeg à utiliser."""
    if os.environ.get("FFMPEG_PATH"):
        return os.environ["FFMPEG_PATH"]
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def run_ffmpeg(arguments):
    """Lance FFmpeg avec la liste d'arguments donnée.

    En cas d'échec, l'erreur contient la fin du message de FFmpeg : on ne masque rien.
    """
    command = [get_ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-y", *map(str, arguments)]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg a échoué (code {result.returncode}) :\n{result.stderr.strip()[-2000:]}")
    return result


def get_media_duration(media_path):
    """Durée d'un fichier audio ou vidéo, en secondes.

    `ffmpeg -i fichier` affiche « Duration: HH:MM:SS.ss » puis s'arrête en erreur
    (aucune sortie demandée) : c'est normal, on lit seulement cette ligne.
    """
    media_path = Path(media_path)
    if not media_path.is_file():
        raise FileNotFoundError(f"Fichier introuvable : {media_path}")

    result = subprocess.run([get_ffmpeg_path(), "-hide_banner", "-i", str(media_path)],
                            capture_output=True, text=True)
    match = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", result.stderr)
    if not match:
        raise ValueError(f"Durée illisible : {media_path} n'est pas un fichier audio/vidéo valide.")
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
