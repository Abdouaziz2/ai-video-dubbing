"""Tests de la voix, de la synchronisation et de l'assemblage vidéo.

Aucun modèle de voix n'est nécessaire : FakeVoice produit un bip dont la durée dépend de la
longueur du texte. On teste ainsi la logique (fichiers, durées, placement) avec de vrais
fichiers audio générés par FFmpeg.
"""
import shutil
import subprocess
import sys
import wave

import numpy as np
import pytest

from src.ffmpeg_utils import get_ffmpeg_path, get_media_duration, run_ffmpeg
from src.synchronization import align_segments, build_audio_track, compute_speed_factor
from src.synchronization.audio_alignment import SAMPLE_RATE, read_wav_samples
from src.video import replace_audio_track
from src.voice import MacOSTestVoice, generate_segment_audio, measure_speech_rate


def make_tone(path, duration, sample_rate=22050):
    """Crée un WAV contenant un bip de `duration` secondes (fréquence volontairement != SAMPLE_RATE)."""
    run_ffmpeg(["-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}", "-ar", sample_rate, path])


class FakeVoice:
    """Fausse voix : 10 caractères = 1 seconde de bip. Enregistre les textes reçus."""

    def __init__(self):
        self.calls = []

    def synthesize(self, text, output_path):
        self.calls.append(text)
        make_tone(output_path, len(text) / 10)


class FailingVoice:
    """Écrit un début de fichier puis plante, comme une interruption en pleine synthèse."""

    def synthesize(self, text, output_path):
        output_path.write_bytes(b"debut")
        raise OSError("coupure simulée")


def make_segment(segment_id, start, end, dubbing_text):
    return {"id": segment_id, "start": start, "end": end,
            "original_text": "texte", "translated_text": dubbing_text, "dubbing_text": dubbing_text}


# --- Génération de la voix ----------------------------------------------------

def test_generate_adds_audio_fields_and_keeps_contract(tmp_path):
    segments = [make_segment(1, 0.0, 3.0, "a" * 20), make_segment(7, 3.0, 5.0, "b" * 10)]
    voiced = generate_segment_audio(segments, FakeVoice(), tmp_path)

    assert [(s["id"], s["start"], s["end"]) for s in voiced] == [(1, 0.0, 3.0), (7, 3.0, 5.0)]
    assert voiced[0]["audio_file"].endswith("segment_0001.wav")
    assert voiced[1]["audio_file"].endswith("segment_0007.wav")
    assert voiced[0]["audio_duration"] == pytest.approx(2.0, abs=0.05)
    assert voiced[1]["audio_duration"] == pytest.approx(1.0, abs=0.05)
    assert "audio_file" not in segments[0]  # l'entrée n'est pas modifiée


def test_existing_audio_is_reused_after_interruption(tmp_path):
    segments = [make_segment(1, 0.0, 3.0, "a" * 20), make_segment(2, 3.0, 5.0, "b" * 10)]
    generate_segment_audio(segments[:1], FakeVoice(), tmp_path)  # 1er passage interrompu après id=1

    voice = FakeVoice()
    generate_segment_audio(segments, voice, tmp_path)

    assert voice.calls == ["b" * 10]  # seul le segment manquant est synthétisé


def test_skip_existing_false_regenerates_everything(tmp_path):
    segments = [make_segment(1, 0.0, 3.0, "a" * 20)]
    generate_segment_audio(segments, FakeVoice(), tmp_path)
    voice = FakeVoice()
    generate_segment_audio(segments, voice, tmp_path, skip_existing=False)

    assert voice.calls == ["a" * 20]


def test_voice_error_names_the_segment_and_leaves_no_final_file(tmp_path):
    with pytest.raises(RuntimeError, match="id=3") as error:
        generate_segment_audio([make_segment(3, 0.0, 2.0, "hello")], FailingVoice(), tmp_path)

    assert isinstance(error.value.__cause__, OSError)
    assert not (tmp_path / "segment_0003.wav").exists()  # pas de fichier à moitié écrit sous le nom final


def test_missing_dubbing_text_is_rejected_before_any_synthesis(tmp_path):
    segment = make_segment(1, 0.0, 2.0, "hello")
    del segment["dubbing_text"]
    voice = FakeVoice()

    with pytest.raises(ValueError, match="dubbing_text"):
        generate_segment_audio([segment], voice, tmp_path)
    assert voice.calls == []


def test_measure_speech_rate():
    voiced = [{"dubbing_text": "a" * 30, "audio_duration": 2.0},
              {"dubbing_text": "b" * 10, "audio_duration": 2.0}]
    assert measure_speech_rate(voiced) == 10.0


@pytest.mark.skipif(sys.platform != "darwin" or not shutil.which("say"), reason="voix macOS uniquement")
def test_macos_test_voice_produces_speech(tmp_path):
    output = tmp_path / "hello.wav"
    MacOSTestVoice().synthesize("-Hello everyone.", output)  # le tiret ne doit pas être lu comme une option

    assert 0.5 < get_media_duration(output) < 5


# --- Synchronisation ----------------------------------------------------------

@pytest.mark.parametrize("audio, available, expected", [
    (2.0, 3.0, 1.0),     # tient : inchangé
    (3.0, 3.0, 1.0),     # pile la bonne durée
    (3.3, 3.0, 1.1),     # 10 % trop long : accéléré de 10 %
    (6.0, 3.0, 1.25),    # 2x trop long : plafonné à +25 %
])
def test_compute_speed_factor(audio, available, expected):
    assert compute_speed_factor(audio, available) == pytest.approx(expected)


@pytest.mark.parametrize("available, max_factor", [(0, 1.25), (-1, 1.25), (3.0, 0.9)])
def test_compute_speed_factor_rejects_invalid_values(available, max_factor):
    with pytest.raises(ValueError):
        compute_speed_factor(2.0, available, max_factor)


def voiced_segment(tmp_path, segment_id, start, end, audio_duration):
    audio_path = tmp_path / f"src_{segment_id}.wav"
    make_tone(audio_path, audio_duration)
    return {"id": segment_id, "start": start, "end": end,
            "audio_file": str(audio_path), "audio_duration": audio_duration}


def test_align_keeps_short_audio_and_speeds_up_long_audio(tmp_path):
    segments = [voiced_segment(tmp_path, 1, 0.0, 3.0, 2.0),   # tient
                voiced_segment(tmp_path, 2, 3.0, 5.0, 2.2),   # 10 % trop long -> rattrapable
                voiced_segment(tmp_path, 3, 5.0, 6.0, 2.0)]   # 2x trop long -> dépasse encore
    aligned = align_segments(segments, tmp_path / "aligned")

    assert [s["speed_factor"] for s in aligned] == [1.0, 1.1, 1.25]
    assert aligned[0]["aligned_duration"] == pytest.approx(2.0, abs=0.05)
    assert aligned[1]["aligned_duration"] == pytest.approx(2.0, abs=0.05)
    assert aligned[2]["aligned_duration"] == pytest.approx(1.6, abs=0.05)
    assert [s["still_too_long"] for s in aligned] == [False, False, True]
    assert aligned[0]["duration_difference"] == pytest.approx(-1.0, abs=0.05)
    assert aligned[2]["duration_difference"] == pytest.approx(0.6, abs=0.05)
    # Format commun, quel que soit le format de départ (ici 22050 Hz).
    with wave.open(aligned[0]["aligned_audio_file"]) as wav_file:
        assert (wav_file.getnchannels(), wav_file.getframerate()) == (1, SAMPLE_RATE)


def test_align_rejects_missing_audio_file(tmp_path):
    segment = {"id": 4, "start": 0.0, "end": 1.0, "audio_file": str(tmp_path / "absent.wav"),
               "audio_duration": 1.0}
    with pytest.raises(FileNotFoundError, match="id=4"):
        align_segments([segment], tmp_path)


def test_track_places_audio_at_segment_start(tmp_path):
    aligned = align_segments([voiced_segment(tmp_path, 1, 1.0, 3.0, 1.0)], tmp_path / "aligned")
    placed = build_audio_track(aligned, tmp_path / "track.wav", total_duration=4.0)
    track = read_wav_samples(tmp_path / "track.wav")

    assert placed[0]["placed_start"] == 1.0
    assert len(track) / SAMPLE_RATE == pytest.approx(4.0, abs=0.01)
    assert np.all(track[: int(0.95 * SAMPLE_RATE)] == 0)                       # silence avant 1 s
    assert np.abs(track[int(1.2 * SAMPLE_RATE): int(1.8 * SAMPLE_RATE)]).max() > 0  # bip après 1 s


def test_track_never_overlaps_two_segments(tmp_path):
    segments = [voiced_segment(tmp_path, 1, 0.0, 1.0, 2.0),   # dépasse de 0,4 s même accéléré
                voiced_segment(tmp_path, 2, 1.0, 3.0, 1.0)]
    aligned = align_segments(segments, tmp_path / "aligned")
    placed = build_audio_track(aligned, tmp_path / "track.wav")

    assert placed[1]["placed_start"] == pytest.approx(1.6, abs=0.02)  # décalé après le segment 1
    assert placed[1]["start"] == 1.0                                    # timestamp d'origine conservé


# --- Assemblage vidéo ---------------------------------------------------------

def test_replace_audio_track(tmp_path):
    video = tmp_path / "video.mp4"
    run_ffmpeg(["-f", "lavfi", "-i", "testsrc=size=160x120:rate=10", "-f", "lavfi", "-i", "sine=frequency=300",
                "-t", "2", "-c:v", "libx264", "-c:a", "aac", video])
    track = tmp_path / "track.wav"
    make_tone(track, 2.0)

    output = replace_audio_track(video, track, tmp_path / "out" / "dubbed.mp4", notice="Voix synthétique de test")

    assert output.is_file()
    assert get_media_duration(output) == pytest.approx(2.0, abs=0.1)
    file_info = subprocess.run([get_ffmpeg_path(), "-hide_banner", "-i", str(output)],
                               capture_output=True, text=True).stderr
    assert "Voix synthétique de test" in file_info          # mention écrite dans les métadonnées
    assert file_info.count("Stream #") == 2                 # 1 piste vidéo + 1 seule piste audio


def test_replace_audio_track_rejects_missing_video(tmp_path):
    track = tmp_path / "track.wav"
    make_tone(track, 1.0)
    with pytest.raises(FileNotFoundError):
        replace_audio_track(tmp_path / "absent.mp4", track, tmp_path / "out.mp4")


def test_invalid_media_file_is_rejected(tmp_path):
    fake_video = tmp_path / "pas_une_video.mp4"
    fake_video.write_text("ceci n'est pas une vidéo")
    with pytest.raises(ValueError, match="Durée illisible"):
        get_media_duration(fake_video)
