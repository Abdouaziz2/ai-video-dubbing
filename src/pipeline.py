"""Orchestration du doublage complet : vidéo française -> vidéo doublée en anglais.

Étapes et responsables :
  1. Extraction audio + transcription Whisper ... Abdou Aziz — PAS ENCORE INTÉGRÉ :
     en attendant, la transcription est fournie sous forme de fichier JSON (contrat partie 1).
  2. Traduction + adaptation au doublage ....... Massamba (src/translation)
     -> pause possible : relecture humaine des segments signalés (interface Gradio)
  3. Voix anglaise, un audio par segment ....... src/voice
  4. Synchronisation + piste audio complète .... src/synchronization
  5. Assemblage vidéo .......................... src/video

Chaque étape écrit ses résultats dans output_dir : en cas d'erreur, on voit jusqu'où le
pipeline est allé, et la voix (l'étape la plus lente) reprend là où elle s'était arrêtée.

Utilisation en ligne de commande (depuis la racine du projet) :
    python -m src.pipeline --video data/input/video.mp4 \
        --transcription data/intermediate/transcription.json --voice macos-test
"""
import argparse
from datetime import datetime
from pathlib import Path

from src.ffmpeg_utils import get_media_duration
from src.synchronization import align_segments, build_audio_track
from src.translation import (adapt_segments_for_dubbing, add_alternative_translations, load_segments,
                             save_segments, translate_segments, validate_transcription_segments)
from src.translation.manual_review import MANUAL_EDIT_LABEL
from src.translation.dubbing_adaptation import DEFAULT_CHARS_PER_SECOND
from src.video import SYNTHETIC_VOICE_NOTICE, replace_audio_track
from src.voice import generate_segment_audio, measure_speech_rate

# Une transcription qui dépasse la vidéo de plus de 0,5 s ne correspond pas à cette vidéo.
TIMESTAMP_TOLERANCE = 0.5


def check_transcription_matches_video(segments, video_duration):
    last_end = segments[-1]["end"]
    if last_end > video_duration + TIMESTAMP_TOLERANCE:
        raise ValueError(f"La transcription se termine à {last_end:.2f} s mais la vidéo dure "
                         f"{video_duration:.2f} s : ce JSON ne correspond pas à cette vidéo.")


def prepare_translation(video_path, transcription_json, output_dir, translator,
                        chars_per_second=DEFAULT_CHARS_PER_SECOND, num_candidates=4, log=print):
    """Partie 1 (étapes 1-2) : lecture, traduction, adaptation, propositions pour la relecture.

    Retourne les segments traduits. Ils peuvent être corrigés (apply_manual_edits) avant
    d'être passés à produce_dubbed_video. num_candidates=0 : pas de propositions.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    log("1/5 Lecture de la transcription et de la vidéo")
    segments = load_segments(transcription_json)
    validate_transcription_segments(segments)
    check_transcription_matches_video(segments, get_media_duration(video_path))  # avant les étapes lentes

    log(f"2/5 Traduction de {len(segments)} segments et adaptation au doublage")
    translated = translate_segments(segments, translator)
    adapted = adapt_segments_for_dubbing(translated, chars_per_second)
    if num_candidates:
        adapted = add_alternative_translations(adapted, translator, num_candidates)
    save_segments(adapted, output_dir / "translation.json")
    return adapted


def produce_dubbed_video(video_path, segments, output_dir, voice, log=print):
    """Partie 2 (étapes 3-5) : voix, synchronisation, assemblage. Retourne un résumé.

    voice : objet avec .synthesize(text, output_path) (ex. XTTSVoiceCloner)
    """
    output_dir = Path(output_dir)
    video_duration = get_media_duration(video_path)
    save_segments(segments, output_dir / "translation_reviewed.json")  # version effectivement prononcée

    log("3/5 Génération de la voix anglaise")
    # skip_existing=False : après une correction, l'ancien audio d'un segment ne doit pas être réutilisé.
    voiced = generate_segment_audio(segments, voice, output_dir / "audio_segments", skip_existing=False)
    save_segments(voiced, output_dir / "voice.json")

    log("4/5 Synchronisation des segments")
    aligned = align_segments(voiced, output_dir / "aligned_segments")
    track_path = output_dir / "english_track.wav"
    final_segments = build_audio_track(aligned, track_path, total_duration=video_duration)

    log("5/5 Assemblage de la vidéo doublée")
    # Chaque voix fournit sa mention (voix synthétique, licence) ; mention générique sinon.
    notice = getattr(voice, "notice", SYNTHETIC_VOICE_NOTICE)
    video_output = replace_audio_track(video_path, track_path, output_dir / "dubbed_video.mp4", notice)

    summary = {
        "video_output": str(video_output),
        "segments": final_segments,
        "video_duration": round(video_duration, 3),
        "measured_chars_per_second": round(measure_speech_rate(voiced), 2),
        "segments_needing_review": [s["id"] for s in final_segments if s["needs_review"]],
        "segments_edited": [s["id"] for s in final_segments if s["adaptation"] == MANUAL_EDIT_LABEL],
        "segments_still_too_long": [s["id"] for s in final_segments if s["still_too_long"]],
        "segments_shifted": [s["id"] for s in final_segments if s["placed_start"] > s["start"]],
    }
    save_segments(final_segments, output_dir / "final_segments.json")
    log(f"Terminé : {video_output}")
    return summary


def run_dubbing_pipeline(video_path, transcription_json, output_dir, translator, voice,
                         chars_per_second=DEFAULT_CHARS_PER_SECOND, log=print):
    """Pipeline complet SANS relecture humaine (ligne de commande, tests)."""
    segments = prepare_translation(video_path, transcription_json, output_dir, translator,
                                   chars_per_second, num_candidates=0, log=log)
    return produce_dubbed_video(video_path, segments, output_dir, voice, log=log)


def default_output_dir():
    return Path("data/output") / datetime.now().strftime("run_%Y%m%d_%H%M%S")


def build_voice(voice_name, reference_wav=None):
    """Crée la voix demandée. Import local : XTTS n'est chargé que si on le choisit."""
    from src.voice import MacOSTestVoice, XTTSVoiceCloner
    if voice_name == "macos-test":
        return MacOSTestVoice()
    if voice_name == "xtts":
        if not reference_wav:
            raise ValueError("La voix XTTS nécessite --reference (échantillon de voix autorisé).")
        return XTTSVoiceCloner(reference_wav)
    raise ValueError(f"Voix inconnue : {voice_name}")


def main():
    parser = argparse.ArgumentParser(description="Doublage FR -> EN d'une vidéo.")
    parser.add_argument("--video", required=True)
    parser.add_argument("--transcription", required=True, help="JSON de transcription (contrat partie 1)")
    parser.add_argument("--voice", choices=["macos-test", "xtts"], default="macos-test",
                        help="macos-test = voix système NON clonée, pour tester ; xtts = voix clonée")
    parser.add_argument("--reference", help="WAV de la voix de référence (obligatoire avec xtts)")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--chars-per-second", type=float, default=DEFAULT_CHARS_PER_SECOND)
    args = parser.parse_args()

    from src.translation import HuggingFaceTranslator
    voice = build_voice(args.voice, args.reference)
    print("Chargement du modèle de traduction...")
    translator = HuggingFaceTranslator()

    summary = run_dubbing_pipeline(args.video, args.transcription, args.output_dir or default_output_dir(),
                                   translator, voice, chars_per_second=args.chars_per_second)
    print(f"Débit mesuré de la voix : {summary['measured_chars_per_second']} caractères/s")
    print(f"À relire (texte trop long estimé) : {summary['segments_needing_review']}")
    print(f"Encore trop longs après accélération : {summary['segments_still_too_long']}")
    print(f"Décalés pour éviter une superposition : {summary['segments_shifted']}")


if __name__ == "__main__":
    main()
