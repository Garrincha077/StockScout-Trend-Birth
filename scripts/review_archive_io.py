"""Lossless readers for immutable daily Review JSON or deterministic gzip archives."""
from __future__ import annotations
import gzip
import json
import re
from pathlib import Path

DAILY_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}\.json(?:\.gz)?$")

def archive_day(path: Path) -> str:
    if not DAILY_NAME.fullmatch(path.name):
        raise ValueError("Invalid Review archive path: " + path.name)
    return path.name[:10]

def archive_paths(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    found: dict[str, Path] = {}
    for path in directory.iterdir():
        if not path.is_file() or not DAILY_NAME.fullmatch(path.name):
            continue
        day = archive_day(path)
        if day in found:
            raise ValueError("Ambiguous Review archives for " + day)
        found[day] = path
    return [found[day] for day in sorted(found)]

def archive_for_day(directory: Path, day: str) -> Path:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        raise ValueError("Invalid requested archive session")
    plain = directory / (day + ".json")
    packed = directory / (day + ".json.gz")
    if plain.exists() and packed.exists():
        raise ValueError("Ambiguous Review archives for " + day)
    if plain.is_file():
        return plain
    if packed.is_file():
        return packed
    raise FileNotFoundError("Source EOD snapshot missing: " + str(plain))

def read_archive(path: Path) -> dict:
    raw = gzip.decompress(path.read_bytes()) if path.name.endswith(".json.gz") else path.read_bytes()
    return json.loads(raw)
