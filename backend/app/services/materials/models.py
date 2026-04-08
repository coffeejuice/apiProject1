from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class MaterialSource(StrEnum):
    DEFORM = "deform"
    FORGE = "forge"
    QFORM = "qform"
    SIMUFACT = "simufact"

    @classmethod
    def from_value(cls, value: str | MaterialSource) -> MaterialSource:
        if isinstance(value, cls):
            return value

        normalized = value.strip().lower()
        aliases = {
            "deform-3d": cls.DEFORM,
            "deform3d": cls.DEFORM,
            "simufact forming": cls.SIMUFACT,
        }
        return aliases.get(normalized, cls(normalized))


@dataclass(slots=True, frozen=True)
class MaterialAxis:
    key: str
    label: str
    unit: str | None = None


@dataclass(slots=True, frozen=True)
class MaterialPoint:
    x: float
    y: float


@dataclass(slots=True)
class MaterialDiagramSeries:
    key: str
    label: str
    points: list[MaterialPoint]


@dataclass(slots=True)
class MaterialCurve:
    key: str
    title: str
    x_axis: MaterialAxis
    y_axis: MaterialAxis
    points: list[MaterialPoint]


@dataclass(slots=True)
class MaterialSurface:
    key: str
    title: str
    x_axis: MaterialAxis
    y_axis: MaterialAxis
    slice_axis: MaterialAxis
    value_axis: MaterialAxis
    x_values: list[float]
    y_values: list[float]
    slice_values: list[float]
    values: list[list[list[float]]]


@dataclass(slots=True)
class ParsedMaterialFile:
    source: MaterialSource
    file_name: str
    display_name: str | None
    vendor_metadata: dict[str, Any] = field(default_factory=dict)
    scalars: dict[str, Any] = field(default_factory=dict)
    curves: dict[str, MaterialCurve] = field(default_factory=dict)
    surfaces: dict[str, MaterialSurface] = field(default_factory=dict)
    raw_sections: dict[str, list[str]] = field(default_factory=dict)


@dataclass(slots=True)
class MaterialDiagram:
    key: str
    title: str
    kind: str
    x_axis: MaterialAxis
    y_axis: MaterialAxis
    series: list[MaterialDiagramSeries]
    controls: dict[str, Any] | None = None


@dataclass(slots=True)
class MaterialVisualPayload:
    material_id: int
    source: MaterialSource
    file_name: str
    diagrams: list[MaterialDiagram]
