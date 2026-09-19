"""Loads the config-driven journey (sections/fields/scripts) and exposes
helpers to walk through it field by field. This is the "engine" that lets the
whole field list be swapped out on hackathon day just by editing the JSON.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

JOURNEY_PATH = Path(__file__).parent / "energy_journey.json"


@dataclass
class Field:
    id: str
    label: str
    type: str
    required: bool
    script: str
    reprompt: str
    section_id: str
    choices: Optional[list[str]] = None
    on_no: Optional[str] = None
    confirm_if_prefilled: bool = False
    confirm_script: Optional[str] = None


@dataclass
class Section:
    id: str
    title: str
    intro_script: str
    fields: list[Field]


class Journey:
    def __init__(self, raw: dict[str, Any]):
        self.raw = raw
        self.name: str = raw["journey_name"]
        self.scripts: dict[str, str] = raw["scripts"]
        self.sections: list[Section] = []
        for s in raw["sections"]:
            fields = [
                Field(
                    id=f["id"],
                    label=f["label"],
                    type=f["type"],
                    required=f.get("required", True),
                    script=f["script"],
                    reprompt=f["reprompt"],
                    section_id=s["id"],
                    choices=f.get("choices"),
                    on_no=f.get("on_no"),
                    confirm_if_prefilled=f.get("confirm_if_prefilled", False),
                    confirm_script=f.get("confirm_script"),
                )
                for f in s["fields"]
            ]
            self.sections.append(
                Section(id=s["id"], title=s["title"], intro_script=s["intro_script"], fields=fields)
            )

    @property
    def all_fields(self) -> list[Field]:
        return [f for s in self.sections for f in s.fields]

    def field(self, field_id: str) -> Optional[Field]:
        for f in self.all_fields:
            if f.id == field_id:
                return f
        return None

    def section(self, section_id: str) -> Optional[Section]:
        for s in self.sections:
            if s.id == section_id:
                return s
        return None

    def first_field(self) -> Field:
        return self.all_fields[0]

    def next_field(self, current_field_id: Optional[str], answered: set[str]) -> Optional[Field]:
        """Next unanswered required field after the given one (or from the start)."""
        fields = self.all_fields
        start_idx = 0
        if current_field_id:
            for i, f in enumerate(fields):
                if f.id == current_field_id:
                    start_idx = i + 1
                    break
        for f in fields[start_idx:]:
            if f.id not in answered:
                return f
        # also check any earlier required fields that got skipped
        for f in fields:
            if f.id not in answered:
                return f
        return None

    def resume_field_for_section(self, dropped_section_id: str) -> Field:
        """Where the customer dropped off -> resume at the first field of that section."""
        section = self.section(dropped_section_id)
        if section and section.fields:
            return section.fields[0]
        return self.first_field()

    def progress(self, answered: set[str]) -> dict[str, Any]:
        total = len(self.all_fields)
        done = len([f for f in self.all_fields if f.id in answered])
        return {"total": total, "done": done, "percent": round(done / total * 100) if total else 0}


_journey: Optional[Journey] = None


def get_journey() -> Journey:
    global _journey
    if _journey is None:
        raw = json.loads(JOURNEY_PATH.read_text(encoding="utf-8"))
        _journey = Journey(raw)
    return _journey


def reload_journey() -> Journey:
    global _journey
    _journey = None
    return get_journey()
