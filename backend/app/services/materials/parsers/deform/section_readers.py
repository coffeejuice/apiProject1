from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Sequence

from app.services.materials.errors import MaterialParserError
from app.services.materials.models import MaterialAxis, MaterialCurve, MaterialPoint, MaterialSurface


_SECTION_KEY_RE = re.compile(r"^[A-Z][A-Z0-9]+$")


@dataclass(slots=True)
class DeformSection:
    key: str
    material_number: int
    header_tokens: list[str]
    lines: list[str]


def is_deform_section_header(line: str) -> bool:
    tokens = line.strip().split()
    return (
        len(tokens) >= 2
        and _SECTION_KEY_RE.fullmatch(tokens[0]) is not None
        and tokens[1].isdigit()
    )


def split_deform_sections(
    lines: Sequence[str],
    *,
    target_material_number: int = 1,
) -> dict[str, DeformSection]:
    header_rows: list[tuple[int, list[str]]] = []
    for index, raw_line in enumerate(lines):
        if not is_deform_section_header(raw_line):
            continue
        header_rows.append((index, raw_line.strip().split()))

    sections: dict[str, DeformSection] = {}
    for index, (start, header_tokens) in enumerate(header_rows):
        key = header_tokens[0]
        material_number = int(header_tokens[1])
        if key != "UNIT" and material_number != target_material_number:
            continue

        end = header_rows[index + 1][0] if index + 1 < len(header_rows) else len(lines)
        body_lines = [line.rstrip("\n") for line in lines[start + 1 : end]]
        sections[key] = DeformSection(
            key=key,
            material_number=material_number,
            header_tokens=header_tokens,
            lines=body_lines,
        )

    return sections


def parse_mtname(section: DeformSection | None) -> str | None:
    if section is None:
        return None

    for raw_line in section.lines:
        line = raw_line.strip()
        if line and not line.startswith("*"):
            return line
    return None


def parse_scalar_value(section: DeformSection | None) -> float | None:
    if section is None:
        return None
    if len(section.header_tokens) < 4:
        return None

    try:
        return float(section.header_tokens[3])
    except ValueError:
        return None


def parse_temperature_curve(
    section: DeformSection | None,
    *,
    curve_key: str,
    title: str,
    value_label: str,
    value_unit: str | None = None,
) -> MaterialCurve | None:
    if section is None:
        return None
    if len(section.header_tokens) < 4:
        return None

    try:
        ftype = int(section.header_tokens[2])
    except ValueError:
        return None

    if ftype != 1:
        return None

    count = int(section.header_tokens[3])
    pairs = _read_pair_rows(section.lines, count)
    if not pairs:
        return None

    return MaterialCurve(
        key=curve_key,
        title=title,
        x_axis=MaterialAxis(key="temperature", label="Temperature"),
        y_axis=MaterialAxis(key=curve_key, label=value_label, unit=value_unit),
        points=[MaterialPoint(x=temperature, y=value) for temperature, value in pairs],
    )


def parse_flow_stress_surface(section: DeformSection | None) -> MaterialSurface | None:
    if section is None:
        return None
    if len(section.header_tokens) < 3:
        return None

    try:
        ftype = int(section.header_tokens[2])
    except ValueError:
        return None

    if ftype not in {2, 3}:
        return None

    numeric_lines = _iter_numeric_lines(section.lines)
    if not numeric_lines:
        return None

    dimension_tokens = numeric_lines[0].split()
    if len(dimension_tokens) < 3:
        raise MaterialParserError("Invalid FSTRES dimensions row")

    n_strain, n_srate, n_temperature = map(int, dimension_tokens[:3])
    flattened_values = _flatten_float_tokens(numeric_lines[1:])
    expected_values = n_strain + n_srate + n_temperature + (n_strain * n_srate * n_temperature)
    if len(flattened_values) < expected_values:
        raise MaterialParserError("Incomplete FSTRES table data")

    cursor = 0
    strain_values = flattened_values[cursor : cursor + n_strain]
    cursor += n_strain
    srate_values = flattened_values[cursor : cursor + n_srate]
    cursor += n_srate
    temperature_values = flattened_values[cursor : cursor + n_temperature]
    cursor += n_temperature

    stress_values = flattened_values[cursor : cursor + (n_strain * n_srate * n_temperature)]
    grid: list[list[list[float]]] = []
    value_cursor = 0
    for _ in range(n_temperature):
        srate_rows: list[list[float]] = []
        for _ in range(n_srate):
            row = stress_values[value_cursor : value_cursor + n_strain]
            value_cursor += n_strain
            srate_rows.append(row)
        grid.append(srate_rows)

    return MaterialSurface(
        key="flow_stress",
        title="Flow Stress",
        x_axis=MaterialAxis(key="strain", label="Strain"),
        y_axis=MaterialAxis(key="strain_rate", label="Strain Rate"),
        slice_axis=MaterialAxis(key="temperature", label="Temperature"),
        value_axis=MaterialAxis(key="flow_stress", label="Flow Stress"),
        x_values=strain_values,
        y_values=srate_values,
        slice_values=temperature_values,
        values=grid,
    )


def _read_pair_rows(lines: Sequence[str], count: int) -> list[tuple[float, float]]:
    pairs: list[tuple[float, float]] = []
    for line in _iter_numeric_lines(lines):
        tokens = line.split()
        if len(tokens) < 2:
            continue
        try:
            x_value = float(tokens[0])
            y_value = float(tokens[1])
        except ValueError:
            continue
        pairs.append((x_value, y_value))
        if len(pairs) >= count:
            break
    return pairs


def _iter_numeric_lines(lines: Sequence[str]) -> list[str]:
    numeric_lines: list[str] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("*"):
            continue
        first_token = line.split()[0]
        if _SECTION_KEY_RE.fullmatch(first_token):
            continue
        numeric_lines.append(line)
    return numeric_lines


def _flatten_float_tokens(lines: Iterable[str]) -> list[float]:
    values: list[float] = []
    for line in lines:
        for token in line.split():
            try:
                values.append(float(token))
            except ValueError as exc:
                raise MaterialParserError(f"Non-numeric value in DEFORM section: {token}") from exc
    return values
