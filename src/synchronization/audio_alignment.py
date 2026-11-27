"""Synchronisation : faire tenir chaque audio dans son créneau, puis construire la piste complète.

Étape 1 (align_segments), pour chaque segment :
- l'audio tient dans `end - start` : on le garde tel quel (le reste du créneau sera du silence) ;
- il est trop long : on l'accélère SANS changer la hauteur de la voix (filtre FFmpeg `atempo`),
  mais au maximum de MAX_SPEED_FACTOR. Au-delà, la voix devient peu naturelle : on préfère
  laisser dépasser et le signaler (`still_too_long`) plutôt que de déformer la voix.
On ne ralentit jamais un audio trop court : une voix ralentie sonne faux, un silence non.

Étape 2 (build_audio_track) : on pose chaque audio à son `start` dans une piste silencieuse.
Si l'audio précédent déborde encore, le segment suivant est décalé juste après lui
(`placed_start`) pour que deux phrases ne se superposent jamais. Le décalage est enregistré.

Tous les audios sont convertis au même format (WAV mono 16 bits, SAMPLE_RATE Hz) pour pouvoir
être assemblés simplement avec numpy.
"""
import wave
from pathlib import Path

import numpy as np

from src.ffmpeg_utils import get_media_duration, run_ffmpeg

SAMPLE_RATE = 24000          # fréquence de sortie de XTTS-v2
MAX_SPEED_FACTOR = 1.25      # accélération maximale acceptée (+25 %)
REQUIRED_ALIGNMENT_FIELDS = ("id", "start", "end", "audio_file", "audio_duration")


def compute_speed_factor(audio_duration, available_duration, max_speed_factor=MAX_SPEED_FACTOR):
    """Facteur d'accélération à appliquer (1.0 = vitesse inchangée)."""
    if available_duration <= 0:
        raise ValueError("La durée disponible doit être strictement positive.")
    if max_speed_factor < 1:
        raise ValueError("max_speed_factor doit être >= 1 (on ne ralentit pas).")
    if audio_duration <= available_duration:
        return 1.0
    return min(audio_duration / available_duration, max_speed_factor)


def convert_audio(input_path, output_path, speed_factor=1.0):
    """Convertit au format commun (mono, 16 bits, SAMPLE_RATE) et applique l'accélération éventuelle."""
    arguments = ["-i", input_path]
    if speed_factor != 1.0:
        arguments += ["-filter:a", f"atempo={speed_factor:.4f}"]
    arguments += ["-ac", "1", "-ar", SAMPLE_RATE, "-sample_fmt", "s16", output_path]
    run_ffmpeg(arguments)


def align_segments(segments, output_dir, max_speed_factor=MAX_SPEED_FACTOR):
    """Ajuste la durée de chaque audio. Retourne des copies des segments enrichies de :
    aligned_audio_file, speed_factor, aligned_duration, duration_difference, still_too_long.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    aligned_segments = []
    for segment in segments:
        missing = [field for field in REQUIRED_ALIGNMENT_FIELDS if field not in segment]
        if missing:
            raise ValueError(f"segment id={segment.get('id')!r} : champ(s) manquant(s) {missing}.")
        if not Path(segment["audio_file"]).is_file():
            raise FileNotFoundError(f"Audio introuvable pour le segment id={segment['id']} : {segment['audio_file']}")

        available_duration = segment["end"] - segment["start"]
        speed_factor = compute_speed_factor(segment["audio_duration"], available_duration, max_speed_factor)

        aligned_path = output_dir / f"aligned_{segment['id']:04d}.wav"
        convert_audio(segment["audio_file"], aligned_path, speed_factor)
        aligned_duration = get_media_duration(aligned_path)

        aligned = dict(segment)
        aligned.update({
            "aligned_audio_file": str(aligned_path),
            "speed_factor": round(speed_factor, 3),
            "aligned_duration": round(aligned_duration, 3),
            # Positif = l'audio dépasse le créneau ; négatif = il reste du silence.
            "duration_difference": round(aligned_duration - available_duration, 3),
            # Tolérance de 50 ms : la mesure de durée de FFmpeg est arrondie au centième.
            "still_too_long": aligned_duration > available_duration + 0.05,
        })
        aligned_segments.append(aligned)
    return aligned_segments


def read_wav_samples(wav_path):
    """Lit un WAV au format commun et retourne ses échantillons (numpy int16)."""
    with wave.open(str(wav_path), "rb") as wav_file:
        if (wav_file.getnchannels(), wav_file.getsampwidth(), wav_file.getframerate()) != (1, 2, SAMPLE_RATE):
            raise ValueError(f"{wav_path} n'est pas au format commun (mono, 16 bits, {SAMPLE_RATE} Hz).")
        return np.frombuffer(wav_file.readframes(wav_file.getnframes()), dtype=np.int16)


def write_wav_samples(samples, wav_path):
    Path(wav_path).parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(wav_path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(samples.astype(np.int16).tobytes())


def build_audio_track(aligned_segments, output_path, total_duration=None):
    """Assemble la piste anglaise complète. Retourne les segments complétés par `placed_start`.

    total_duration : durée de la vidéo ; la piste fait au moins cette longueur (silence à la fin).
    """
    placed_segments = []
    clips = []
    previous_end = 0.0
    for segment in aligned_segments:
        samples = read_wav_samples(segment["aligned_audio_file"])
        placed_start = max(segment["start"], previous_end)  # jamais de superposition
        previous_end = placed_start + len(samples) / SAMPLE_RATE
        clips.append((placed_start, samples))

        placed = dict(segment)
        placed["placed_start"] = round(placed_start, 3)
        placed_segments.append(placed)

    track_duration = max(previous_end, total_duration or 0.0)
    track = np.zeros(int(round(track_duration * SAMPLE_RATE)) + 1, dtype=np.int16)
    for placed_start, samples in clips:
        first_sample = int(round(placed_start * SAMPLE_RATE))
        track[first_sample:first_sample + len(samples)] = samples[:len(track) - first_sample]

    write_wav_samples(track, output_path)
    return placed_segments
