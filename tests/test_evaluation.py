"""Tests du test d'écoute et du résumé des durées (aucun audio réel nécessaire)."""
import csv

import pytest

from src.evaluation.listening_test import prepare_listening_test, summarize_durations, summarize_ratings


def make_clips(tmp_path, prefix, count):
    paths = []
    for i in range(count):
        path = tmp_path / f"{prefix}_{i}.wav"
        path.write_bytes(f"{prefix}{i}".encode())
        paths.append(path)
    return paths


def read_rows(path):
    with open(path, encoding="utf-8") as file:
        return list(csv.DictReader(file))


def test_prepare_anonymizes_and_writes_sheet_and_key(tmp_path):
    real = make_clips(tmp_path, "vraie", 2)
    cloned = make_clips(tmp_path, "clonee", 3)
    sheet, key = prepare_listening_test(real, cloned, tmp_path / "test", seed=1)

    key_rows = read_rows(key)
    assert sorted(r["kind"] for r in key_rows) == ["cloned"] * 3 + ["real"] * 2
    assert [r["clip"] for r in key_rows] == [f"clip_{i:02d}.wav" for i in range(1, 6)]
    # Les noms des fichiers copiés ne révèlent rien : seule la clé fait le lien.
    copied = sorted(p.name for p in (tmp_path / "test" / "clips").iterdir())
    assert copied == [f"clip_{i:02d}.wav" for i in range(1, 6)]
    assert read_rows(sheet)[0] == {"clip": "clip_01.wav", **{f"auditeur_{i}": "" for i in range(1, 6)}}


def test_same_seed_gives_same_order(tmp_path):
    real, cloned = make_clips(tmp_path, "vraie", 2), make_clips(tmp_path, "clonee", 2)
    _, key_a = prepare_listening_test(real, cloned, tmp_path / "a", seed=7)
    _, key_b = prepare_listening_test(real, cloned, tmp_path / "b", seed=7)
    assert read_rows(key_a) == read_rows(key_b)


def test_prepare_requires_both_kinds(tmp_path):
    with pytest.raises(ValueError):
        prepare_listening_test(make_clips(tmp_path, "vraie", 2), [], tmp_path / "t")


def fill_sheet(sheet, ratings_by_clip):
    rows = read_rows(sheet)
    with open(sheet, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            for i, value in enumerate(ratings_by_clip[row["clip"]], start=1):
                row[f"auditeur_{i}"] = value
            writer.writerow(row)


def test_summarize_ratings_by_kind(tmp_path):
    sheet, key = prepare_listening_test(make_clips(tmp_path, "vraie", 1), make_clips(tmp_path, "clonee", 1),
                                        tmp_path / "t", num_listeners=2)
    kinds = {r["clip"]: r["kind"] for r in read_rows(key)}
    fill_sheet(sheet, {clip: ("5", "4") if kind == "real" else ("3", "2") for clip, kind in kinds.items()})

    assert summarize_ratings(sheet, key) == {"real_mean": 4.5, "cloned_mean": 2.5,
                                             "num_ratings_real": 2, "num_ratings_cloned": 2}


@pytest.mark.parametrize("bad_value, message", [("", "manquante"), ("6", "hors échelle")])
def test_incomplete_or_invalid_sheet_is_rejected(tmp_path, bad_value, message):
    sheet, key = prepare_listening_test(make_clips(tmp_path, "vraie", 1), make_clips(tmp_path, "clonee", 1),
                                        tmp_path / "t", num_listeners=2)
    fill_sheet(sheet, {"clip_01.wav": ("4", bad_value), "clip_02.wav": ("3", "3")})
    with pytest.raises(ValueError, match=message):
        summarize_ratings(sheet, key)


def test_summarize_durations():
    segments = [
        {"start": 0.0, "placed_start": 0.0, "duration_difference": 0.4, "still_too_long": True, "speed_factor": 1.25},
        {"start": 2.0, "placed_start": 2.4, "duration_difference": -0.6, "still_too_long": False, "speed_factor": 1.0},
    ]
    assert summarize_durations(segments) == {"num_segments": 2, "mean_abs_difference": 0.5, "max_overflow": 0.4,
                                             "num_still_too_long": 1, "num_speed_adjusted": 1, "num_shifted": 1}
