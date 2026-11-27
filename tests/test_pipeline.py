"""Test d'intégration du pipeline complet avec de faux modules (aucun modèle chargé).

Traduction et voix sont simulées ; extraction de durée, synchronisation et assemblage
vidéo sont réellement exécutés avec FFmpeg.
"""
import json

import pytest

from src.ffmpeg_utils import get_media_duration, run_ffmpeg
from src.pipeline import run_dubbing_pipeline


class FakeTranslator:
    def translate(self, text):
        return {"Bonjour à tous.": "Hello everyone.",
                "Bienvenue dans notre présentation.": "Welcome to our presentation."}[text]


class FakeVoice:
    """10 caractères = 1 seconde de bip."""

    def synthesize(self, text, output_path):
        run_ffmpeg(["-f", "lavfi", "-i", f"sine=frequency=440:duration={len(text) / 10}", output_path])


@pytest.fixture
def video(tmp_path):
    path = tmp_path / "video.mp4"
    run_ffmpeg(["-f", "lavfi", "-i", "testsrc=size=160x120:rate=10", "-f", "lavfi", "-i", "sine=frequency=300",
                "-t", "6", "-c:v", "libx264", "-c:a", "aac", path])
    return path


def write_transcription(tmp_path, segments):
    path = tmp_path / "transcription.json"
    path.write_text(json.dumps({"segments": segments}, ensure_ascii=False), encoding="utf-8")
    return path


def test_full_pipeline_with_fake_modules(tmp_path, video):
    transcription = write_transcription(tmp_path, [
        {"id": 1, "start": 0.0, "end": 2.0, "text": "Bonjour à tous."},                      # 15 car. -> 1,5 s
        {"id": 2, "start": 2.0, "end": 4.0, "text": "Bienvenue dans notre présentation."},   # 28 car. -> 2,8 s
    ])
    messages = []

    summary = run_dubbing_pipeline(video, transcription, tmp_path / "out", FakeTranslator(), FakeVoice(),
                                   log=messages.append)

    output_dir = tmp_path / "out"
    for name in ("translation.json", "voice.json", "english_track.wav", "dubbed_video.mp4", "final_segments.json"):
        assert (output_dir / name).is_file(), name
    assert get_media_duration(summary["video_output"]) == pytest.approx(6.0, abs=0.2)

    first, second = summary["segments"]
    assert (first["id"], first["start"], first["end"]) == (1, 0.0, 2.0)
    assert first["speed_factor"] == 1.0
    assert second["speed_factor"] == pytest.approx(1.25)   # 2,8 s pour 2 s : plafonné
    assert summary["segments_still_too_long"] == [2]
    assert summary["measured_chars_per_second"] == pytest.approx(10, abs=0.3)
    assert messages[0].startswith("1/5") and messages[-1].startswith("Terminé")


def test_transcription_longer_than_video_is_rejected_before_translation(tmp_path, video):
    transcription = write_transcription(tmp_path, [{"id": 1, "start": 0.0, "end": 30.0, "text": "Bonjour à tous."}])

    class MustNotBeCalled:
        def translate(self, text):
            raise AssertionError("la traduction n'aurait pas dû démarrer")

    with pytest.raises(ValueError, match="ne correspond pas"):
        run_dubbing_pipeline(video, transcription, tmp_path / "out", MustNotBeCalled(), FakeVoice(), log=print)


def test_invalid_transcription_is_rejected(tmp_path, video):
    transcription = write_transcription(tmp_path, [])
    with pytest.raises(ValueError, match="vide"):
        run_dubbing_pipeline(video, transcription, tmp_path / "out", FakeTranslator(), FakeVoice(), log=print)


def test_missing_video_is_rejected(tmp_path):
    transcription = write_transcription(tmp_path, [{"id": 1, "start": 0.0, "end": 2.0, "text": "Bonjour à tous."}])
    with pytest.raises(FileNotFoundError):
        run_dubbing_pipeline(tmp_path / "absent.mp4", transcription, tmp_path / "out",
                             FakeTranslator(), FakeVoice(), log=print)


class FakeCandidateTranslator(FakeTranslator):
    def translate_candidates(self, text, num_candidates):
        return [self.translate(text), "Welcome."]


def test_pipeline_with_human_review(tmp_path, video):
    """Parcours de l'interface : traduire -> corriger un segment -> produire la vidéo."""
    from src.pipeline import prepare_translation, produce_dubbed_video
    from src.translation import apply_manual_edits

    transcription = write_transcription(tmp_path, [
        {"id": 1, "start": 0.0, "end": 2.0, "text": "Bonjour à tous."},
        {"id": 2, "start": 2.0, "end": 3.5, "text": "Bienvenue dans notre présentation."},
    ])
    segments = prepare_translation(video, transcription, tmp_path / "out", FakeCandidateTranslator(),
                                   num_candidates=2, log=print)
    assert segments[1]["needs_review"] is True               # 28 car. / 14 = 2 s estimées pour 1,5 s
    assert segments[1]["alternative_translations"] == ["Welcome."]

    reviewed = apply_manual_edits(segments, {2: "Welcome."})  # le relecteur choisit la proposition courte
    summary = produce_dubbed_video(video, reviewed, tmp_path / "out", FakeVoice(), log=print)

    second = summary["segments"][1]
    assert second["dubbing_text"] == "Welcome."
    assert second["translated_text"] == "Welcome to our presentation."
    assert second["audio_duration"] == pytest.approx(0.8, abs=0.05)  # la voix a bien lu le texte corrigé
    assert summary["segments_edited"] == [2]
    assert summary["segments_still_too_long"] == []
    assert (tmp_path / "out" / "translation_reviewed.json").is_file()


def test_pipeline_without_json_calls_extraction_and_whisper(tmp_path, video, monkeypatch):
    """Sans JSON, le pipeline appelle les modules d'Abdou Aziz (simulés ici : pas de modèle Whisper)."""
    calls = []

    def fake_extract(video_path, output_audio_path):
        calls.append(("extract", str(video_path)))
        return output_audio_path

    def fake_transcribe(audio_path, output_json_path, model_size, language, device):
        calls.append(("transcribe", model_size, language, device))
        write_transcription(tmp_path, [{"id": 1, "start": 0.0, "end": 2.0, "text": "Bonjour à tous."}])
        (tmp_path / "transcription.json").replace(output_json_path)

    monkeypatch.setattr("src.pipeline.extract_audio_from_video", fake_extract)
    monkeypatch.setattr("src.pipeline.transcribe_audio", fake_transcribe)
    # Les faux modules n'existent que dans ce processus : on exécute ici au lieu d'un processus séparé.
    monkeypatch.setattr("src.pipeline.run_in_separate_process", lambda function, *args: function(*args))

    summary = run_dubbing_pipeline(video, None, tmp_path / "out", FakeTranslator(), FakeVoice(),
                                   log=print, whisper_model="small")

    assert calls == [("extract", str(video)), ("transcribe", "small", "fr", "cpu")]  # CPU par défaut
    assert (tmp_path / "out" / "transcription.json").is_file()
    assert summary["segments"][0]["translated_text"] == "Hello everyone."


def test_run_in_separate_process_returns_result_and_raises_errors():
    import math

    from src.pipeline import run_in_separate_process

    assert run_in_separate_process(math.sqrt, 16) == 4.0
    with pytest.raises(ValueError):          # l'erreur de l'autre processus remonte ici
        run_in_separate_process(math.sqrt, -1)
