import json
import subprocess
import sys
from types import ModuleType, SimpleNamespace

import pytest

from src.extraction import extract_audio_from_video
from src.transcription import transcribe_audio


def test_extract_audio_builds_wav_and_returns_path(tmp_path, monkeypatch):
    video = tmp_path / "input.mp4"
    video.write_bytes(b"video")
    output = tmp_path / "intermediate" / "audio.wav"

    def fake_run(command, **kwargs):
        assert command[:4] == ["ffmpeg", "-y", "-i", str(video)]
        assert command[-1] == str(output)
        assert kwargs["check"] is True
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"wav")

    monkeypatch.setattr("src.extraction.audio_extraction.subprocess.run", fake_run)

    assert extract_audio_from_video(video, output) == output
    assert output.read_bytes() == b"wav"


def test_extract_audio_rejects_missing_video(tmp_path):
    with pytest.raises(FileNotFoundError, match="vidéo"):
        extract_audio_from_video(tmp_path / "missing.mp4", tmp_path / "audio.wav")


def test_extract_audio_reports_ffmpeg_failure(tmp_path, monkeypatch):
    video = tmp_path / "input.mp4"
    video.write_bytes(b"video")

    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0], stderr="invalid media")

    monkeypatch.setattr("src.extraction.audio_extraction.subprocess.run", fail)

    with pytest.raises(RuntimeError, match="invalid media"):
        extract_audio_from_video(video, tmp_path / "audio.wav")


def test_transcribe_audio_outputs_contract_and_saves_json(tmp_path, monkeypatch):
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"wav")
    model_args = {}

    class FakeWhisperModel:
        def __init__(self, model_size, **kwargs):
            model_args.update(model_size=model_size, **kwargs)

        def transcribe(self, audio_path, **kwargs):
            assert audio_path == str(audio)
            assert kwargs == {
                "language": "fr",
                "beam_size": 5,
                "vad_filter": True,
            }
            return iter([
                SimpleNamespace(start=0.123, end=2.345, text=" Bonjour à tous. "),
                SimpleNamespace(start=2.345, end=3.0, text="  "),
                SimpleNamespace(start=3.0, end=4.5, text="Bienvenue."),
            ]), SimpleNamespace(language="fr")

    fake_module = ModuleType("faster_whisper")
    fake_module.WhisperModel = FakeWhisperModel
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_module)
    ctranslate2 = ModuleType("ctranslate2")
    ctranslate2.get_cuda_device_count = lambda: 0
    monkeypatch.setitem(sys.modules, "ctranslate2", ctranslate2)

    json_path = tmp_path / "intermediate" / "transcription.json"
    result = transcribe_audio(audio, json_path)

    assert result == {
        "segments": [
            {"id": 1, "start": 0.12, "end": 2.35, "text": "Bonjour à tous."},
            {"id": 2, "start": 3.0, "end": 4.5, "text": "Bienvenue."},
        ]
    }
    assert model_args == {"model_size": "base", "device": "cpu", "compute_type": "int8"}
    assert json.loads(json_path.read_text(encoding="utf-8")) == result


def test_transcribe_uses_cuda_when_auto_detected(tmp_path, monkeypatch):
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"wav")
    selected = {}

    class FakeWhisperModel:
        def __init__(self, model_size, **kwargs):
            selected.update(kwargs)

        def transcribe(self, *args, **kwargs):
            return iter([SimpleNamespace(start=0, end=1, text="Bonjour.")]), None

    fake_module = ModuleType("faster_whisper")
    fake_module.WhisperModel = FakeWhisperModel
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_module)
    ctranslate2 = ModuleType("ctranslate2")
    ctranslate2.get_cuda_device_count = lambda: 1
    monkeypatch.setitem(sys.modules, "ctranslate2", ctranslate2)

    transcribe_audio(audio)

    assert selected == {"device": "cuda", "compute_type": "float16"}


def test_transcribe_rejects_missing_audio(tmp_path):
    with pytest.raises(FileNotFoundError, match="audio"):
        transcribe_audio(tmp_path / "missing.wav")


def test_transcribe_rejects_invalid_device(tmp_path):
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"wav")
    with pytest.raises(ValueError, match="device"):
        transcribe_audio(audio, device="tpu")


def test_transcribe_rejects_empty_result(tmp_path, monkeypatch):
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"wav")

    class FakeWhisperModel:
        def __init__(self, *args, **kwargs):
            pass

        def transcribe(self, *args, **kwargs):
            return iter([]), None

    fake_module = ModuleType("faster_whisper")
    fake_module.WhisperModel = FakeWhisperModel
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_module)
    ctranslate2 = ModuleType("ctranslate2")
    ctranslate2.get_cuda_device_count = lambda: 0
    monkeypatch.setitem(sys.modules, "ctranslate2", ctranslate2)

    with pytest.raises(ValueError, match="Aucune parole"):
        transcribe_audio(audio)
