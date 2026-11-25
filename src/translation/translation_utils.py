"""Validation et lecture/écriture des segments échangés entre les modules.

Contrat d'entrée (sortie de la transcription) :
    {"segments": [{"id": 1, "start": 0.0, "end": 3.5, "text": "Bonjour à tous."}, ...]}

Contrat de sortie (sortie de la traduction) :
    {"segments": [{"id": 1, "start": 0.0, "end": 3.5,
                   "original_text": "Bonjour à tous.", "translated_text": "Hello everyone."}, ...]}
"""
import json
import math
from pathlib import Path

REQUIRED_TRANSCRIPTION_FIELDS = ("id", "start", "end", "text")


def _is_number(value):
    """Vrai pour un int ou float fini. bool est exclu (en Python, True est un int)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_transcription_segments(segments):
    """Vérifie une liste de segments de transcription et lève ValueError au premier problème.

    Contrôles : liste non vide, champs requis présents, id entier unique, timestamps numériques
    avec 0 <= start < end, texte non vide, segments triés par start.
    """
    if not isinstance(segments, list):
        raise ValueError(f"'segments' doit être une liste, reçu : {type(segments).__name__}")
    if not segments:
        raise ValueError("La liste 'segments' est vide.")

    seen_ids = set()
    previous_start = None

    for position, segment in enumerate(segments):
        where = f"segment n°{position}"
        if not isinstance(segment, dict):
            raise ValueError(f"{where} : un segment doit être un objet JSON (dict).")

        missing = [field for field in REQUIRED_TRANSCRIPTION_FIELDS if field not in segment]
        if missing:
            raise ValueError(f"{where} : champ(s) manquant(s) {missing}.")

        segment_id = segment["id"]
        where = f"segment id={segment_id!r}"
        if not isinstance(segment_id, int) or isinstance(segment_id, bool):
            raise ValueError(f"{where} : 'id' doit être un entier.")
        if segment_id in seen_ids:
            raise ValueError(f"{where} : identifiant dupliqué.")
        seen_ids.add(segment_id)

        start, end = segment["start"], segment["end"]
        if not _is_number(start) or not _is_number(end):
            raise ValueError(f"{where} : 'start' et 'end' doivent être des nombres.")
        if start < 0:
            raise ValueError(f"{where} : 'start' est négatif ({start}).")
        if end <= start:
            raise ValueError(f"{where} : 'end' ({end}) doit être supérieur à 'start' ({start}).")

        if previous_start is not None and start < previous_start:
            raise ValueError(f"{where} : segments non triés par ordre chronologique.")
        previous_start = start

        text = segment["text"]
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"{where} : 'text' est vide.")


def load_segments(json_path):
    """Lit un fichier JSON {"segments": [...]} et retourne la liste des segments (non validée)."""
    json_path = Path(json_path)
    if not json_path.exists():
        raise FileNotFoundError(f"Fichier introuvable : {json_path}")

    with json_path.open(encoding="utf-8") as f:
        data = json.load(f)  # lève json.JSONDecodeError si le fichier est mal formé

    if not isinstance(data, dict) or "segments" not in data:
        raise ValueError(f"{json_path} : la clé 'segments' est absente.")
    return data["segments"]


def save_segments(segments, json_path):
    """Écrit {"segments": [...]} en UTF-8 lisible (accents conservés). Crée le dossier si besoin."""
    json_path = Path(json_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with json_path.open("w", encoding="utf-8") as f:
        json.dump({"segments": segments}, f, ensure_ascii=False, indent=2)
