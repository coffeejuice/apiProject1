from __future__ import annotations

from app.services.materials.models import (
    MaterialCurve,
    MaterialDiagram,
    MaterialDiagramSeries,
    MaterialPoint,
    MaterialSurface,
    ParsedMaterialFile,
)


def build_deform_material_diagrams(parsed: ParsedMaterialFile) -> list[MaterialDiagram]:
    diagrams: list[MaterialDiagram] = []

    flow_stress = parsed.surfaces.get("flow_stress")
    if flow_stress is not None:
        diagrams.append(build_flow_stress_slice_diagram(flow_stress))

    for curve_key in (
        "young",
        "poisson",
        "thermal_conductivity",
        "heat_capacity",
        "thermal_expansion",
    ):
        curve = parsed.curves.get(curve_key)
        if curve is None:
            continue
        diagrams.append(build_curve_diagram(curve))

    return diagrams


def build_curve_diagram(curve: MaterialCurve) -> MaterialDiagram:
    return MaterialDiagram(
        key=curve.key,
        title=curve.title,
        kind="line",
        x_axis=curve.x_axis,
        y_axis=curve.y_axis,
        series=[
            MaterialDiagramSeries(
                key=curve.key,
                label=curve.title,
                points=curve.points,
            )
        ],
    )


def build_flow_stress_slice_diagram(surface: MaterialSurface) -> MaterialDiagram:
    slice_index = len(surface.slice_values) // 2 if surface.slice_values else 0
    series_index = _nearest_index(surface.y_values, 1.0) if surface.y_values else 0

    selected_temperature = surface.slice_values[slice_index] if surface.slice_values else None
    selected_strain_rate = surface.y_values[series_index] if surface.y_values else None
    selected_grid = surface.values[slice_index][series_index] if surface.values else []

    points = [
        MaterialPoint(x=strain_value, y=stress_value)
        for strain_value, stress_value in zip(surface.x_values, selected_grid, strict=False)
    ]

    return MaterialDiagram(
        key=surface.key,
        title="Flow Stress vs Strain",
        kind="line_slice",
        x_axis=surface.x_axis,
        y_axis=surface.value_axis,
        series=[
            MaterialDiagramSeries(
                key="flow_stress_slice",
                label=_format_flow_stress_label(selected_temperature, selected_strain_rate),
                points=points,
            )
        ],
        controls={
            "slice_axis": {
                "key": surface.slice_axis.key,
                "label": surface.slice_axis.label,
                "default": selected_temperature,
                "options": surface.slice_values,
            },
            "series_axis": {
                "key": surface.y_axis.key,
                "label": surface.y_axis.label,
                "default": selected_strain_rate,
                "options": surface.y_values,
            },
        },
    )


def _format_flow_stress_label(temperature: float | None, strain_rate: float | None) -> str:
    if temperature is None and strain_rate is None:
        return "Default slice"
    if temperature is None:
        return f"Strain rate {strain_rate:g}"
    if strain_rate is None:
        return f"Temperature {temperature:g}"
    return f"Temperature {temperature:g}, strain rate {strain_rate:g}"


def _nearest_index(values: list[float], target: float) -> int:
    best_index = 0
    best_distance = abs(values[0] - target)
    for index, value in enumerate(values[1:], start=1):
        distance = abs(value - target)
        if distance < best_distance:
            best_index = index
            best_distance = distance
    return best_index
