"""Génération de la voix anglaise, un fichier audio par segment.

Entrée  : segments produits par la traduction (champ `dubbing_text`, voir docs/data_contract.md).
Sortie  : mêmes segments + `audio_file` (chemin du WAV) + `audio_duration` (durée mesurée, s).

Deux voix sont disponibles, avec la même méthode `synthesize(text, output_path)` :
- XTTSVoiceCloner : la vraie voix clonée (XTTS-v2), à partir d'un échantillon autorisé.
- MacOSTestVoice  : voix système de macOS, NON clonée. Uniquement pour tester la chaîne
  (synchronisation, vidéo, interface) sur le Mac sans télécharger XTTS-v2.

`generate_segment_audio` accepte n'importe quel objet qui possède cette méthode : c'est ce
qui permet de tester sans modèle (même principe que `translate_segments`).
"""
import os
import subprocess
import tempfile
from pathlib import Path

from src.ffmpeg_utils import get_media_duration, run_ffmpeg
from src.video.video_assembly import SYNTHETIC_VOICE_NOTICE

REQUIRED_VOICE_FIELDS = ("id", "start", "end", "dubbing_text")
XTTS_MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"
XTTS_LICENSE_URL = "https://coqui.ai/cpml.txt"


class XTTSVoiceCloner:
    """Voix clonée avec XTTS-v2 (paquet `coqui-tts`, modèle d'environ 1,9 Go).

    Licence : le modèle est sous Coqui Public Model License (usage NON commercial).
    coqui-tts demande d'accepter cette licence au premier téléchargement ; on ne l'accepte
    pas à la place de l'utilisateur dans le code (voir docs/voice_model_choice.md).
    La licence impose de transmettre son adresse avec toute sortie du modèle : `notice`
    est écrit dans les métadonnées de la vidéo finale.
    """

    notice = f"{SYNTHETIC_VOICE_NOTICE} Voix clonée avec XTTS-v2, licence : {XTTS_LICENSE_URL} (usage non commercial)."

    def __init__(self, reference_wav, language="en", device=None):
        self.reference_wav = Path(reference_wav)
        if not self.reference_wav.is_file():
            raise FileNotFoundError(f"Échantillon de voix de référence introuvable : {self.reference_wav}")

        # Imports lourds ici : le reste du module (et les tests) fonctionne sans coqui-tts.
        import torch
        from TTS.api import TTS

        self.language = language
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.tts = TTS(XTTS_MODEL_NAME).to(self.device)

    def synthesize(self, text, output_path):
        self.tts.tts_to_file(text=text, speaker_wav=str(self.reference_wav),
                             language=self.language, file_path=str(output_path))


class MacOSTestVoice:
    """Voix de TEST : synthèse intégrée à macOS (commande `say`). Ce n'est PAS un clonage.

    Sert uniquement à vérifier la chaîne complète sur le Mac. Ne jamais la présenter
    comme le résultat final du projet.
    """

    notice = f"{SYNTHETIC_VOICE_NOTICE} Voix de test macOS, non clonée."

    def __init__(self, voice_name="Samantha"):
        self.voice_name = voice_name

    def synthesize(self, text, output_path):
        with tempfile.TemporaryDirectory() as temp_dir:
            aiff_path = Path(temp_dir) / "speech.aiff"
            # Le texte passe par l'entrée standard : aucun risque qu'il soit lu comme une option.
            subprocess.run(["say", "-v", self.voice_name, "-o", str(aiff_path)],
                           input=text, text=True, check=True, capture_output=True)
            run_ffmpeg(["-i", aiff_path, output_path])


def segment_audio_path(output_dir, segment_id):
    """Nom de fichier stable par segment : segment_0001.wav, segment_0002.wav..."""
    return Path(output_dir) / f"segment_{segment_id:04d}.wav"


def generate_segment_audio(segments, voice, output_dir, skip_existing=True):
    """Génère un WAV par segment et retourne des copies complétées par audio_file / audio_duration.

    skip_existing=True : un fichier déjà généré est réutilisé. Si Colab coupe au milieu,
    on relance la même commande et on reprend là où on s'était arrêté.
    """
    for segment in segments:
        missing = [field for field in REQUIRED_VOICE_FIELDS if field not in segment]
        if missing:
            raise ValueError(f"segment id={segment.get('id')!r} : champ(s) manquant(s) {missing}.")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    voiced_segments = []
    for segment in segments:
        audio_path = segment_audio_path(output_dir, segment["id"])

        if not (skip_existing and audio_path.is_file()):
            # On écrit d'abord dans un fichier temporaire, renommé seulement à la fin :
            # une interruption ne laisse jamais un WAV à moitié écrit sous le nom final.
            temp_path = audio_path.with_name(audio_path.stem + ".partial.wav")
            try:
                voice.synthesize(segment["dubbing_text"], temp_path)
            except Exception as error:
                raise RuntimeError(f"Échec de la synthèse vocale du segment id={segment['id']}") from error
            if not temp_path.is_file():
                raise RuntimeError(f"Aucun fichier audio produit pour le segment id={segment['id']}")
            os.replace(temp_path, audio_path)

        audio_duration = get_media_duration(audio_path)
        if audio_duration <= 0:
            raise ValueError(f"Audio vide pour le segment id={segment['id']} : {audio_path}")

        voiced = dict(segment)
        voiced["audio_file"] = str(audio_path)
        voiced["audio_duration"] = round(audio_duration, 3)
        voiced_segments.append(voiced)
    return voiced_segments


def measure_speech_rate(voiced_segments):
    """Débit réel de la voix (caractères de dubbing_text par seconde d'audio).

    C'est la valeur qui doit remplacer DEFAULT_CHARS_PER_SECOND (14) dans l'adaptation.
    """
    total_chars = sum(len(s["dubbing_text"].strip()) for s in voiced_segments)
    total_seconds = sum(s["audio_duration"] for s in voiced_segments)
    if total_seconds <= 0:
        raise ValueError("Durée audio totale nulle : impossible de mesurer le débit.")
    return total_chars / total_seconds
