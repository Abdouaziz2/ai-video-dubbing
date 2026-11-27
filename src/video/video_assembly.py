"""Assemblage final : la vidéo d'origine + la nouvelle piste audio anglaise.

L'image n'est pas réencodée (`-c:v copy`) : c'est rapide et sans perte de qualité.
Seul l'audio est encodé en AAC, le format audio standard des fichiers MP4.
Une métadonnée signale que la voix est synthétique (exigence éthique du projet).
"""
from pathlib import Path

from src.ffmpeg_utils import run_ffmpeg

SYNTHETIC_VOICE_NOTICE = "Doublage anglais généré par IA : la voix est synthétique."


def replace_audio_track(video_path, audio_path, output_path, notice=SYNTHETIC_VOICE_NOTICE):
    """Crée output_path : image de video_path + son de audio_path. Retourne le chemin créé.

    notice : texte écrit dans les métadonnées du fichier (mention « voix synthétique », licence...).
    """
    video_path, audio_path, output_path = Path(video_path), Path(audio_path), Path(output_path)
    for path in (video_path, audio_path):
        if not path.is_file():
            raise FileNotFoundError(f"Fichier introuvable : {path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    run_ffmpeg([
        "-i", video_path,
        "-i", audio_path,
        "-map", "0:v:0",      # la piste vidéo du 1er fichier
        "-map", "1:a:0",      # la piste audio du 2e fichier (l'ancienne voix française est retirée)
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-metadata", f"comment={notice}",
        output_path,
    ])
    return output_path
