"""Cutting operation math extracted from the legacy preprocessor."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any

from .geometry import GeneratedGeometry, outline_perimeter_mm, scale_generated_geometry
from .operation_keys import CUTTING_COLD_SAW_KEEP_PERCENT, CUTTING_HOT_KEEP_PERCENT, CUTTING_TEMPLATE_IDS


class CuttingMathError(ValueError):
    """Raised when cutting inputs are inconsistent or incomplete."""


@dataclass(frozen=True, slots=True)
class CuttingComputationResult:
    """All cutting-derived outputs for one control-program row."""

    final_geometry: GeneratedGeometry
    metrics: dict[str, Any]
    operation_specific_parameters: dict[str, Any] = field(default_factory=dict)
    total_time_seconds: float = 0.0
    time_before_operation_seconds: float | None = None
    simulation_expected_duration_days: float | None = None
    compiler_notes: tuple[str, ...] = ()


def calculate_cutting(
    *,
    template_id: str,
    initial_geometry: GeneratedGeometry,
    pieces_count: int,
    piece_number: int,
    percentage_to_keep: float,
    previous_total_time_seconds: float,
    time_between_operation_seconds: float | None,
) -> CuttingComputationResult:
    """Compute hot/cold cutting geometry and metadata using legacy formulas."""

    if template_id not in CUTTING_TEMPLATE_IDS:
        raise CuttingMathError(f"Unsupported cutting template_id={template_id}")
    if pieces_count < 1:
        raise CuttingMathError(f"pieces_count must be positive, got {pieces_count}")
    if piece_number < 1 or piece_number > pieces_count:
        raise CuttingMathError(
            f"piece_number must be between 1 and pieces_count={pieces_count}, got {piece_number}"
        )
    if percentage_to_keep <= 0.0 or percentage_to_keep > 100.0:
        raise CuttingMathError(
            f"percentage_to_keep must be in (0, 100], got {percentage_to_keep}"
        )

    initial_length = initial_geometry.length_mm
    initial_area = initial_geometry.cross_section_area_mm2
    initial_volume = initial_geometry.volume_mm3
    if min(initial_length, initial_area, initial_volume) <= 0.0:
        raise CuttingMathError("Initial geometry dimensions, area, and volume must be positive")

    cut_count = max(0, pieces_count - 1)
    single_cut_scrap_volume = _single_cut_scrap_volume_mm3(
        template_id=template_id,
        initial_geometry=initial_geometry,
    )
    total_scrap_volume = single_cut_scrap_volume * cut_count
    if total_scrap_volume >= initial_volume:
        raise CuttingMathError(
            "Calculated cutting scrap volume is not below initial billet volume: "
            f"scrap={total_scrap_volume:g} volume={initial_volume:g}"
        )

    available_volume = initial_volume - total_scrap_volume
    final_volume = available_volume * percentage_to_keep / 100.0
    final_length = final_volume / initial_area
    if final_length <= 0.0:
        raise CuttingMathError(f"Calculated final length must be positive, got {final_length}")

    final_geometry = scale_generated_geometry(
        initial_geometry,
        length_scale=final_length / initial_length,
        parameters_update={"length": final_length},
    )

    time_before = time_between_operation_seconds or 0.0
    total_time_seconds = previous_total_time_seconds + time_before
    x_start = initial_length * (piece_number - 1) / pieces_count
    x_stop = initial_length * piece_number / pieces_count
    num_of_bites = cut_count * 4
    scrap_rate = total_scrap_volume / initial_volume

    metrics: dict[str, Any] = {
        "initial_length": initial_length,
        "initial_width": initial_geometry.width_mm,
        "initial_height": initial_geometry.height_mm,
        "initial_cross_section_area_mm2": initial_area,
        "initial_volume_mm3": initial_volume,
        "final_length": final_geometry.length_mm,
        "final_width": final_geometry.width_mm,
        "final_height": final_geometry.height_mm,
        "final_cross_section_area_mm2": final_geometry.cross_section_area_mm2,
        "final_volume_mm3": final_geometry.volume_mm3,
        "pieces_count": pieces_count,
        "piece_number": piece_number,
        "percentage_to_keep": percentage_to_keep,
        "cut_count": cut_count,
        "num_of_bites": num_of_bites,
        "scrap_rate": scrap_rate,
        "single_cut_scrap_volume_mm3": single_cut_scrap_volume,
        "total_scrap_volume_mm3": total_scrap_volume,
        "initial_surface_area_mm2": _surface_area_mm2(initial_geometry),
        "final_surface_area_mm2": _surface_area_mm2(final_geometry),
        "time_before_pass_seconds": time_before,
    }
    operation_specific_parameters = {
        "pieces_count": pieces_count,
        "piece_number": piece_number,
        "percentage_to_keep": percentage_to_keep,
        "cut_count": cut_count,
        "num_of_bites": num_of_bites,
        "scrap_rate": scrap_rate,
        "single_cut_scrap_volume_mm3": single_cut_scrap_volume,
        "total_scrap_volume_mm3": total_scrap_volume,
        "x_axis_cutting_limits_mm": (x_start, x_stop),
        "x_axis_cutting_limits_relative": (
            x_start / initial_length,
            x_stop / initial_length,
        ),
        "is_hot_cutting": template_id == CUTTING_HOT_KEEP_PERCENT,
        "is_cold_sawing": template_id == CUTTING_COLD_SAW_KEEP_PERCENT,
        "deformation_geometry_ported": True,
    }

    return CuttingComputationResult(
        final_geometry=final_geometry,
        metrics=metrics,
        operation_specific_parameters=operation_specific_parameters,
        total_time_seconds=total_time_seconds,
        time_before_operation_seconds=time_before,
        simulation_expected_duration_days=None,
    )


def _single_cut_scrap_volume_mm3(
    *,
    template_id: str,
    initial_geometry: GeneratedGeometry,
) -> float:
    if template_id == CUTTING_HOT_KEEP_PERCENT:
        return 6.3488e5 * math.exp(3.9233e-3 * initial_geometry.equivalent_diameter_mm)
    return initial_geometry.cross_section_area_mm2 * 3.0


def _surface_area_mm2(geometry: GeneratedGeometry) -> float:
    return 2.0 * geometry.cross_section_area_mm2 + outline_perimeter_mm(geometry.cross_section_outline) * geometry.length_mm
