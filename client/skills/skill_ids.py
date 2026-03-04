"""Skill name <-> ID mapping from skill_reference.json."""

import json
from functools import lru_cache
from pathlib import Path

_REFERENCE_PATH = Path(__file__).parent.parent / "data" / "skill_reference.json"


@lru_cache(maxsize=1)
def _load_reference() -> list[dict]:
    with open(_REFERENCE_PATH, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def name_to_id_map() -> dict[str, int]:
    """Return {skill_name: skill_id} mapping."""
    return {entry["name"]: entry["id"] for entry in _load_reference()}


@lru_cache(maxsize=1)
def id_to_name_map() -> dict[int, str]:
    """Return {skill_id: skill_name} mapping."""
    return {entry["id"]: entry["name"] for entry in _load_reference()}


def skill_name_to_id(name: str) -> int | None:
    """Look up a skill ID by name. Returns None if not found."""
    return name_to_id_map().get(name)


def skill_id_to_name(skill_id: int) -> str | None:
    """Look up a skill name by ID. Returns None if not found."""
    return id_to_name_map().get(skill_id)
