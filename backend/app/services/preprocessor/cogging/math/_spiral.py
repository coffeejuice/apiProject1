"""Shared calculation block for spiral-rounding variants."""

from __future__ import annotations

import json
import math

from app.services.preprocessor.geometry import GeneratedGeometry, outline_area_mm2
from app.services.preprocessor.prolongation_geometry import ProlongationGeometryError

from ..contours_2d import SpiralRoundContourInput, build_spiral_contour
from ..models import CoggingCalculationInput, CoggingVariantResult, FeedSchedule
from ..shared_formulas import require_positive, spiral_rounding_strains


def calculate_spiral_variant(
    *,
    input_data: CoggingCalculationInput,
    rotations_count_per_feed_list: tuple[int, int, int],
) -> CoggingVariantResult:
    """Calculate a spiral rounding variant from final diameter and feed."""

    final_diameter_mm = require_positive(input_data.final_diameter_mm, "diameter")
    notes: list[str] = []
    try:
        contour_result = build_spiral_contour(
            SpiralRoundContourInput(
                initial_geometry=input_data.initial_geometry,
                final_diameter_mm=final_diameter_mm,
            )
        )
        final_geometry = contour_result.final_geometry
        penetration_mm = max(0.0, input_data.initial_geometry.height_mm - final_geometry.height_mm)
        final_width_of_contact_mm = contour_result.final_width_of_contact_mm or 0.5 * final_geometry.height_mm
    except ProlongationGeometryError as exc:
        final_geometry, penetration_mm = dependency_light_round_geometry(
            initial_geometry=input_data.initial_geometry,
            final_diameter_mm=final_diameter_mm,
        )
        final_width_of_contact_mm = 0.5 * final_geometry.height_mm
        notes.append(f"Shapely spiral geometry fallback used: {exc}")

    feed_first_mm = min(
        input_data.initial_geometry.height_mm,
        0.8 * min(input_data.top_die.straight_length_mm, input_data.bottom_die.straight_length_mm),
    )
    feed_middle_mm = require_positive(input_data.feed_mm, "feed")
    feed_last_mm = 0.0

    return CoggingVariantResult(
        final_geometry=final_geometry,
        penetration_mm=penetration_mm,
        feed_schedule=FeedSchedule(
            feed_first_mm=feed_first_mm,
            feed_middle_mm=feed_middle_mm,
            feed_last_mm=feed_last_mm,
            num_of_bites_input=input_data.num_of_bites_input,
            rotations_count_per_feed_list=rotations_count_per_feed_list,
            rotation_per_bite_deg=input_data.rotation_per_bite_deg,
        ),
        initial_length_of_contact_mm=feed_first_mm,
        final_length_of_contact_mm=feed_first_mm,
        final_width_of_contact_mm=final_width_of_contact_mm,
        strains=spiral_rounding_strains(
            initial_geometry=input_data.initial_geometry,
            final_geometry=final_geometry,
        ),
        operation_specific_parameters={
            "diameter": final_geometry.height_mm,
            "rotation_per_bite": input_data.rotation_per_bite_deg,
            "rotations_count_per_feed_list": rotations_count_per_feed_list,
            "initial_dies_gap": input_data.initial_geometry.height_mm,
            "final_dies_gap": final_geometry.height_mm,
        },
        compiler_notes=tuple(notes),
    )


def dependency_light_round_geometry(
    *,
    initial_geometry: GeneratedGeometry,
    final_diameter_mm: float,
) -> tuple[GeneratedGeometry, float]:
    """Build a round final cross-section without Shapely."""

    radius = final_diameter_mm / 2.0
    segments = max(32, len(initial_geometry.cross_section_outline) * 2)
    outline = tuple(
        (
            radius * math.cos(2.0 * math.pi * index / segments),
            radius * math.sin(2.0 * math.pi * index / segments),
        )
        for index in range(segments)
    )
    area = outline_area_mm2(outline)
    if area <= 0.0:
        raise ProlongationGeometryError("Calculated spiral final cross-section area is not positive")
    length = initial_geometry.volume_mm3 / area
    equivalent_diameter = math.sqrt(4.0 * area / math.pi)
    parameters = dict(initial_geometry.parameters)
    parameters.update({"diameter": final_diameter_mm})
    final_geometry = GeneratedGeometry(
        type_id=initial_geometry.type_id,
        shape="round",
        parameters=parameters,
        volume_mm3=initial_geometry.volume_mm3,
        cross_section_area_mm2=area,
        equivalent_diameter_mm=equivalent_diameter,
        width_mm=final_diameter_mm,
        height_mm=final_diameter_mm,
        length_mm=length,
        cross_section_outline=outline,
        parameters_json=json.dumps(parameters, sort_keys=True),
    )
    penetration_mm = max(0.0, initial_geometry.height_mm - final_diameter_mm)
    return final_geometry, penetration_mm
