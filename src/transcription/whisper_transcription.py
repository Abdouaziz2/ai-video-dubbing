"""Transcription française horodatée avec Faster-Whisper."""
from pathlib import Path

from src.translation.translation_utils import save_segments, validate_transcription_segments


def _resolve_device(device):
    if device not in {"auto", "cpu", "cuda"}:
        raise ValueError("device doit être 'auto', 'cpu' ou 'cuda'.")
    if device != "auto":
        return device

    import ctranslate2

    return "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"


def transcribe_audio(
    audio_path,
    output_json_path=None,
    model_size="base",
    language="fr",
    device="auto",
    beam_size=5,
    vad_filter=True,
):
    """Transcrit l'audio et retourne ``{"segments": [...]}``.

    Si ``output_json_path`` est fourni, la transcription est aussi sauvegardée
    en UTF-8 selon le contrat partagé avec le module de traduction.
    Le modèle Faster-Whisper est chargé à la demande; aucune dépendance GPU
    n'est nécessaire pour importer ce module.
    """
    audio_file = Path(audio_path)
    if not audio_file.is_file():
        raise FileNotFoundError(f"Fichier audio introuvable : {audio_file}")
    if not model_size:
        raise ValueError("model_size ne peut pas être vide.")
    if not language:
        raise ValueError("language ne peut pas être vide.")
    if beam_size < 1:
        raise ValueError("beam_size doit être supérieur ou égal à 1.")

    selected_device = _resolve_device(device)
    from faster_whisper import WhisperModel

    compute_type = "float16" if selected_device == "cuda" else "int8"
    model = WhisperModel(model_size, device=selected_device, compute_type=compute_type)
    whisper_segments, _ = model.transcribe(
        str(audio_file),
        language=language,
        beam_size=beam_size,
        vad_filter=vad_filter,
    )

    segments = []
    for whisper_segment in whisper_segments:
        text = whisper_segment.text.strip()
        if not text:
            continue
        segments.append({
            "id": len(segments) + 1,
            "start": round(float(whisper_segment.start), 2),
            "end": round(float(whisper_segment.end), 2),
            "text": text,
        })

    if not segments:
        raise ValueError(f"Aucune parole détectée dans le fichier audio : {audio_file}")

    validate_transcription_segments(segments)
    result = {"segments": segments}
    if output_json_path is not None:
        save_segments(segments, output_json_path)

    return result
