"""App configuration — loaded from ``config.json``.

Settings that should be tweakable *without a code change* live in
``production-support/config.json`` (machine origins, default sizes, margin
presets, delta defaults). This module loads that file once, validates it into
typed objects, and exposes read-only accessors.

Dependency-free (stdlib ``json`` only) so it can be imported from any layer.
All distances are in millimetres (mm-canonical, matching the rest of the code).

To reload after editing the file at runtime, call ``load_config.cache_clear()``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

# config.json lives at the production-support/ root, one level up from utils/.
CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"


@dataclass(frozen=True)
class Origin:
    """A selectable machine origin (mm) that positions are measured from."""

    value: str
    label: str
    x0_mm: float
    y0_mm: float


@dataclass(frozen=True)
class SizePreset:
    """A selectable job size. ``None`` dimensions mark the manual ("custom") option."""

    value: str
    label: str
    width_mm: float | None
    height_mm: float | None

    @property
    def is_custom(self) -> bool:
        return self.width_mm is None or self.height_mm is None


@dataclass(frozen=True)
class MarginPreset:
    """A selectable margin. ``margin_mm`` is a fixed margin in mm; ``None`` = custom."""

    value: str
    label: str
    margin_mm: float | None

    @property
    def is_custom(self) -> bool:
        return self.margin_mm is None


@dataclass(frozen=True)
class ProjectList:
    """Target Slack List for the ``/newproject`` cog.

    ``hidden_columns`` are kept out of the modal; ``column_defaults`` maps a
    column (by name or id) to a value written automatically on create. Both are
    matched leniently (case/space-insensitive on the column name, or exact id).
    """

    list_id: str
    command: str
    title: str
    hidden_columns: tuple[str, ...]
    column_defaults: dict


@dataclass(frozen=True)
class Config:
    origins: tuple[Origin, ...]
    default_origin_value: str
    size_presets: tuple[SizePreset, ...]
    default_size_value: str
    margin_presets: tuple[MarginPreset, ...]
    default_margin_value: str
    delta_x_mm: float
    delta_y_mm: float
    project_list: ProjectList | None

    def origin(self, value: str) -> Origin:
        return _lookup(self.origins, value, "origin")

    def size_preset(self, value: str) -> SizePreset:
        return _lookup(self.size_presets, value, "size preset")

    def margin_preset(self, value: str) -> MarginPreset:
        return _lookup(self.margin_presets, value, "margin preset")


def _lookup(items, value, what):
    for item in items:
        if item.value == value:
            return item
    raise KeyError(f"unknown {what}: {value!r}")


def _default_value(items, raw_items):
    """Return the ``value`` of the entry flagged ``is_default``, else the first."""
    for item, raw in zip(items, raw_items):
        if raw.get("is_default"):
            return item.value
    return items[0].value


def _maybe_float(x):
    return None if x is None else float(x)


def _parse(raw: dict) -> Config:
    origins = tuple(
        Origin(
            value=o["value"],
            label=o["label"],
            x0_mm=float(o["x0_mm"]),
            y0_mm=float(o["y0_mm"]),
        )
        for o in raw["origins"]
    )
    sizes = tuple(
        SizePreset(
            value=s["value"],
            label=s["label"],
            width_mm=_maybe_float(s.get("width_mm")),
            height_mm=_maybe_float(s.get("height_mm")),
        )
        for s in raw["size_presets"]
    )
    margins = tuple(
        MarginPreset(
            value=m["value"],
            label=m["label"],
            margin_mm=_maybe_float(m.get("margin_mm")),
        )
        for m in raw["margin_presets"]
    )
    if not (origins and sizes and margins):
        raise ValueError("config: origins, size_presets and margin_presets must not be empty")

    defaults = raw.get("defaults", {})

    pl = raw.get("project_list")
    project_list = (
        ProjectList(
            list_id=pl["list_id"],
            command=pl.get("command", "/newproject"),
            title=pl.get("title", "New Project"),
            hidden_columns=tuple(pl.get("hidden_columns", [])),
            column_defaults=dict(pl.get("column_defaults", {})),
        )
        if pl
        else None
    )

    return Config(
        origins=origins,
        default_origin_value=_default_value(origins, raw["origins"]),
        size_presets=sizes,
        default_size_value=_default_value(sizes, raw["size_presets"]),
        margin_presets=margins,
        default_margin_value=_default_value(margins, raw["margin_presets"]),
        delta_x_mm=float(defaults.get("delta_x_mm", 0.0)),
        delta_y_mm=float(defaults.get("delta_y_mm", 0.0)),
        project_list=project_list,
    )


@lru_cache(maxsize=1)
def load_config() -> Config:
    """Load and cache ``config.json``. Call ``.cache_clear()`` to force a reload."""
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return _parse(json.load(f))
