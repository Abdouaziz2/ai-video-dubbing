"""Extraction d'une piste audio WAV mono 16 kHz depuis une vidéo avec FFmpeg."""
import subprocess
from pathlib import Path

from src.ffmpeg_utils import get_ffmpeg_path


def extract_audio_from_video(video_path, output_audio_path):
    """Extrait l'audio et retourne le chemin WAV créé.

    Lève FileNotFoundError si l'entrée ou FFmpeg est absent, et RuntimeError si
    FFmpeg échoue. Le fichier vidéo source n'est jamais écrasé.
    """
    video_file = Path(video_path)
    output_file = Path(output_audio_path)

    if not video_file.is_file():
        raise FileNotFoundError(f"Fichier vidéo introuvable : {video_file}")
    if video_file.resolve() == output_file.resolve():
        raise ValueError("Le fichier audio de sortie ne peut pas écraser la vidéo source.")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    command = [
        # get_ffmpeg_path() : FFmpeg de imageio-ffmpeg (ou FFMPEG_PATH), même sans ffmpeg dans le PATH.
        get_ffmpeg_path(), "-y", "-i", str(video_file),
        "-vn", "-ac", "1", "-ar", "16000",
        "-c:a", "pcm_s16le", str(output_file),
    ]

    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as error:
        raise FileNotFoundError(
            "FFmpeg est introuvable. Installez-le et vérifiez qu'il est dans le PATH."
        ) from error
    except subprocess.CalledProcessError as error:
        details = (error.stderr or "").strip()
        raise RuntimeError(f"Échec de l'extraction FFmpeg : {details}") from error

    if not output_file.is_file() or output_file.stat().st_size == 0:
        raise RuntimeError(f"FFmpeg n'a pas produit de fichier audio valide : {output_file}")

    return output_file
