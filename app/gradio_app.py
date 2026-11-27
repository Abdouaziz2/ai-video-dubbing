"""Interface Gradio du doublage FR -> EN, avec relecture humaine.

Lancement (depuis la racine du projet) :
    .venv/bin/python -m app.gradio_app
puis ouvrir l'adresse affichée (http://127.0.0.1:7860).

Déroulement en deux temps :
  1. « Traduire » : traduction + adaptation. Le tableau affiche chaque segment ; ceux marqués
     « à relire » ont des propositions de traduction alternatives.
  2. Le relecteur corrige si besoin la colonne `dubbing_text` (seule colonne modifiable).
  3. « Générer la voix et la vidéo » : voix, synchronisation, assemblage avec les textes relus.

Transcription : automatique avec Whisper (modules d'Abdou Aziz), ou fichier JSON fourni
(par exemple une transcription corrigée à la main).
"""
import sys

import gradio as gr

from src.pipeline import build_voice, default_output_dir, prepare_translation, produce_dubbed_video
from src.translation import apply_manual_edits

VOICE_CHOICES = {
    "Voix de test macOS (NON clonée, pour tester la chaîne)": "macos-test",
    "XTTS-v2 : voix clonée (échantillon autorisé obligatoire)": "xtts",
}
# La voix de test macOS n'existe que sur Mac : ailleurs (Colab...), XTTS-v2 est proposé par défaut.
DEFAULT_VOICE_LABEL = list(VOICE_CHOICES)[0 if sys.platform == "darwin" else 1]
REVIEW_COLUMNS = ["id", "start", "end", "original_text", "translated_text", "dubbing_text",
                  "à relire", "autres propositions"]
EDITABLE_COLUMN = REVIEW_COLUMNS.index("dubbing_text")
RESULT_COLUMNS = ["id", "start", "dubbing_text", "available_duration", "aligned_duration",
                  "speed_factor", "duration_difference", "still_too_long", "placed_start"]

_translator = None


def get_translator():
    """Le modèle de traduction (≈ 0,9 Go en mémoire) n'est chargé qu'une fois, au 1er usage."""
    global _translator
    if _translator is None:
        from src.translation import HuggingFaceTranslator
        _translator = HuggingFaceTranslator()
    return _translator


def review_rows(segments):
    return [[s["id"], s["start"], s["end"], s["original_text"], s["translated_text"], s["dubbing_text"],
             "OUI" if s["needs_review"] else "", "  |  ".join(s["alternative_translations"])]
            for s in segments]


def translate_step(video_path, transcription_path, whisper_model, progress=gr.Progress()):
    if not video_path:
        raise gr.Error("Ajoutez une vidéo.")

    progress(0.1, desc="Chargement du modèle de traduction (≈ 20 s la première fois)")
    translator = get_translator()
    output_dir = default_output_dir()
    # transcription_path vide (None) : Whisper transcrit la vidéo.
    # Les erreurs (JSON invalide, vidéo illisible, FFmpeg absent...) ne sont pas interceptées :
    # Gradio affiche leur message (show_error=True) et le détail reste dans le terminal.
    segments = prepare_translation(video_path, transcription_path or None, output_dir, translator,
                                   num_candidates=4, whisper_model=whisper_model,
                                   log=lambda message: progress(None, desc=message))

    flagged = [s["id"] for s in segments if s["needs_review"]]
    source = "fichier JSON fourni" if transcription_path else f"Whisper ({whisper_model})"
    message = (f"Transcription : {source}. {len(segments)} segments traduits. "
               + (f"À relire (texte estimé trop long) : {flagged}. Les propositions sont dans la dernière colonne."
                  if flagged else "Aucun segment signalé.")
               + "\nVous pouvez modifier la colonne dubbing_text, puis lancer l'étape 2.")
    state = {"video_path": video_path, "output_dir": str(output_dir), "segments": segments}
    return review_rows(segments), message, state


def dub_step(state, review_table, voice_label, reference_audio, consent_given, progress=gr.Progress()):
    if not state:
        raise gr.Error("Lancez d'abord l'étape 1 (Traduire).")
    voice_name = VOICE_CHOICES[voice_label]
    if voice_name == "xtts":
        if not reference_audio:
            raise gr.Error("La voix clonée nécessite un échantillon de voix de référence.")
        if not consent_given:
            raise gr.Error("Confirmez que la personne a donné son accord écrit pour le clonage de sa voix.")

    # Textes relus : colonne dubbing_text du tableau, associée à l'id de chaque ligne.
    edited_texts = {int(row[0]): str(row[EDITABLE_COLUMN]) for row in review_table}
    try:
        segments = apply_manual_edits(state["segments"], edited_texts)
    except ValueError as error:  # texte vidé par erreur : message clair au relecteur
        raise gr.Error(str(error)) from error

    progress(0.05, desc="Chargement de la voix")
    voice = build_voice(voice_name, reference_audio)
    summary = produce_dubbed_video(state["video_path"], segments, state["output_dir"], voice,
                                   log=lambda message: progress(None, desc=message))

    report = "\n".join([
        f"Vidéo : {summary['video_output']}",
        f"Débit mesuré de la voix : {summary['measured_chars_per_second']} caractères/s",
        f"Segments corrigés à la main : {summary['segments_edited'] or 'aucun'}",
        f"Segments encore trop longs après accélération : {summary['segments_still_too_long'] or 'aucun'}",
        f"Segments décalés pour éviter une superposition : {summary['segments_shifted'] or 'aucun'}",
    ])
    if voice_name == "macos-test":
        report += "\n\nATTENTION : voix de test macOS, ce n'est PAS la voix clonée du projet."
    rows = [[s[column] for column in RESULT_COLUMNS] for s in summary["segments"]]
    return summary["video_output"], report, rows


with gr.Blocks(title="AI Video Dubbing FR → EN") as demo:
    gr.Markdown(
        "# AI Video Dubbing : français → anglais\n"
        "**La voix produite est synthétique.** N'utilisez que votre propre voix ou une voix "
        "dont la personne a donné son accord écrit."
    )
    pipeline_state = gr.State(None)

    gr.Markdown("## Étape 1 — Traduction")
    with gr.Row():
        video_input = gr.Video(label="Vidéo en français", sources=["upload"])
        with gr.Column():
            transcription_input = gr.File(label="Transcription JSON (facultatif : sinon Whisper transcrit la vidéo)",
                                          file_types=[".json"])
            whisper_input = gr.Radio(["tiny", "base", "small"], value="base",
                                     label="Modèle Whisper (si pas de JSON) : small = plus précis mais plus lent")
    translate_button = gr.Button("1. Traduire", variant="primary")
    translate_message = gr.Textbox(label="Résultat de la traduction", lines=3)

    gr.Markdown("## Relecture — seule la colonne `dubbing_text` (texte prononcé) est modifiable")
    review_table = gr.Dataframe(headers=REVIEW_COLUMNS, type="array", interactive=True, wrap=True,
                                static_columns=[i for i in range(len(REVIEW_COLUMNS)) if i != EDITABLE_COLUMN])

    gr.Markdown("## Étape 2 — Voix et vidéo")
    with gr.Row():
        with gr.Column():
            voice_input = gr.Radio(list(VOICE_CHOICES), value=DEFAULT_VOICE_LABEL, label="Voix")
            reference_input = gr.Audio(label="Voix de référence (10 à 30 s, pour XTTS-v2)",
                                       sources=["upload", "microphone"], type="filepath")
            consent_input = gr.Checkbox(label="La personne dont la voix est clonée a donné son accord écrit")
            dub_button = gr.Button("2. Générer la voix et la vidéo", variant="primary")
        with gr.Column():
            video_output = gr.Video(label="Vidéo doublée")
            report_output = gr.Textbox(label="Compte rendu", lines=7)
    result_table = gr.Dataframe(headers=RESULT_COLUMNS, label="Synchronisation par segment", wrap=True)

    translate_button.click(translate_step, inputs=[video_input, transcription_input, whisper_input],
                           outputs=[review_table, translate_message, pipeline_state])
    dub_button.click(dub_step,
                     inputs=[pipeline_state, review_table, voice_input, reference_input, consent_input],
                     outputs=[video_output, report_output, result_table])


if __name__ == "__main__":
    demo.launch(show_error=True)
