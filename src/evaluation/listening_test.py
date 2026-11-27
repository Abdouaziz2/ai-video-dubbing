"""Évaluation : test d'écoute à l'aveugle (similarité de voix) et différences de durée.

Test d'écoute (mesure demandée dans la répartition : « 5 auditeurs, à l'aveugle ») :
- on mélange des extraits de la VRAIE voix (témoins) et de la voix CLONÉE ;
- chaque extrait reçoit un nom anonyme (clip_01.wav, clip_02.wav...) dans un ordre aléatoire ;
- chaque auditeur écoute l'échantillon de référence puis chaque extrait, et note
  « Est-ce la même personne ? » de 1 (pas du tout) à 5 (certainement) ;
- la clé (quel clip est vrai ou cloné) est dans un fichier séparé, à ne pas montrer aux auditeurs.
Les extraits témoins donnent la note qu'obtient une vraie voix : on compare la voix clonée à cette
base plutôt qu'à un 5 parfait.
"""
import csv
import random
import shutil
from pathlib import Path
from statistics import mean

NUM_LISTENERS = 5
RATING_MIN, RATING_MAX = 1, 5


def prepare_listening_test(real_clips, cloned_clips, output_dir, num_listeners=NUM_LISTENERS, seed=0):
    """Copie les extraits sous des noms anonymes et crée la grille de notation et la clé.

    Retourne (chemin de la grille, chemin de la clé).
    seed : fixe l'ordre aléatoire pour pouvoir refaire exactement le même test.
    """
    clips = [(Path(path), "real") for path in real_clips] + [(Path(path), "cloned") for path in cloned_clips]
    if not real_clips or not cloned_clips:
        raise ValueError("Il faut au moins un extrait de vraie voix ET un extrait de voix clonée.")
    for path, _ in clips:
        if not path.is_file():
            raise FileNotFoundError(f"Extrait introuvable : {path}")

    random.Random(seed).shuffle(clips)
    output_dir = Path(output_dir)
    clips_dir = output_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    key_rows = []
    for number, (path, kind) in enumerate(clips, start=1):
        anonymous_name = f"clip_{number:02d}{path.suffix}"
        shutil.copyfile(path, clips_dir / anonymous_name)
        key_rows.append({"clip": anonymous_name, "kind": kind, "source": path.name})

    listeners = [f"auditeur_{i}" for i in range(1, num_listeners + 1)]
    sheet_path = output_dir / "grille_notation.csv"
    with open(sheet_path, "w", newline="", encoding="utf-8") as sheet:
        writer = csv.writer(sheet)
        writer.writerow(["clip", *listeners])
        for row in key_rows:
            writer.writerow([row["clip"], *[""] * num_listeners])

    key_path = output_dir / "cle_NE_PAS_MONTRER.csv"
    with open(key_path, "w", newline="", encoding="utf-8") as key_file:
        writer = csv.DictWriter(key_file, fieldnames=["clip", "kind", "source"])
        writer.writeheader()
        writer.writerows(key_rows)
    return sheet_path, key_path


def summarize_ratings(sheet_path, key_path):
    """Moyenne des notes pour la vraie voix et pour la voix clonée.

    Refuse une grille incomplète ou une note hors de 1 à 5 : un résultat partiel ne doit pas
    passer inaperçu.
    """
    with open(key_path, encoding="utf-8") as key_file:
        kind_by_clip = {row["clip"]: row["kind"] for row in csv.DictReader(key_file)}

    ratings = {"real": [], "cloned": []}
    with open(sheet_path, encoding="utf-8") as sheet:
        for row in csv.DictReader(sheet):
            clip = row.pop("clip")
            if clip not in kind_by_clip:
                raise ValueError(f"Clip inconnu dans la grille : {clip}")
            for listener, value in row.items():
                if not value.strip():
                    raise ValueError(f"Note manquante : {clip}, {listener}")
                rating = int(value)
                if not RATING_MIN <= rating <= RATING_MAX:
                    raise ValueError(f"Note hors échelle ({rating}) : {clip}, {listener}")
                ratings[kind_by_clip[clip]].append(rating)

    return {
        "real_mean": round(mean(ratings["real"]), 2),
        "cloned_mean": round(mean(ratings["cloned"]), 2),
        "num_ratings_real": len(ratings["real"]),
        "num_ratings_cloned": len(ratings["cloned"]),
    }


def summarize_durations(final_segments):
    """Différence de durée par segment (mesure demandée dans la répartition), à partir de
    final_segments.json produit par le pipeline."""
    differences = [s["duration_difference"] for s in final_segments]
    return {
        "num_segments": len(final_segments),
        "mean_abs_difference": round(mean(abs(d) for d in differences), 3),
        "max_overflow": round(max(0.0, *differences), 3),
        "num_still_too_long": sum(s["still_too_long"] for s in final_segments),
        "num_speed_adjusted": sum(s["speed_factor"] > 1.0 for s in final_segments),
        "num_shifted": sum(s["placed_start"] > s["start"] for s in final_segments),
    }
