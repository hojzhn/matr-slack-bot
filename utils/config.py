from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"


@dataclass(frozen=True)
class Origin:

    value: str
    label: str
    x0_mm: float
    y0_mm: float


@dataclass(frozen=True)
class SizePreset:

    value: str
    label: str
    width_mm: float | None
    height_mm: float | None

    @property
    def is_custom(self) -> bool:
        return self.width_mm is None or self.height_mm is None


@dataclass(frozen=True)
class MarginPreset:

    value: str
    label: str
    margin_mm: float | None

    @property
    def is_custom(self) -> bool:
        return self.margin_mm is None


@dataclass(frozen=True)
class ProjectList:

    list_id: str
    command: str
    title: str
    notify_channel: str | None
    fields: tuple
    column_defaults: dict
    size_select: dict | None
    created_by_column: str | None
    placeholder_image_url: str | None


@dataclass(frozen=True)
class Alerts:

    enabled: bool
    channel: str | None
    poll_seconds: float


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
    proof_alerts: Alerts | None
    order_alerts: Alerts | None
    submission_alerts: Alerts | None

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

    for item, raw in zip(items, raw_items):
        if raw.get("is_default"):
            return item.value
    return items[0].value


def _maybe_float(x):
    return None if x is None else float(x)


def _parse_alerts(a: dict | None) -> Alerts | None:
    if not a:
        return None
    return Alerts(
        enabled=bool(a.get("enabled", True)),
        channel=a.get("channel"),
        poll_seconds=float(a.get("poll_seconds", 15)),
    )


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
            notify_channel=pl.get("notify_channel"),
            fields=tuple(pl.get("fields", [])),
            column_defaults=dict(pl.get("column_defaults", {})),
            size_select=pl.get("size_select"),
            created_by_column=pl.get("created_by_column"),
            placeholder_image_url=pl.get("placeholder_image_url"),
        )
        if pl
        else None
    )

    proof_alerts = _parse_alerts(raw.get("proof_alerts"))
    order_alerts = _parse_alerts(raw.get("order_alerts"))
    submission_alerts = _parse_alerts(raw.get("submission_alerts"))

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
        proof_alerts=proof_alerts,
        order_alerts=order_alerts,
        submission_alerts=submission_alerts,
    )


@lru_cache(maxsize=1)
def load_config() -> Config:

    with open(CONFIG_PATH, encoding="utf-8") as f:
        return _parse(json.load(f))
