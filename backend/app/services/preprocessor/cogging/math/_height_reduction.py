"""Shared calculation block for height-reduction cogging variants."""

from __future__ import annotations

from collections.abc import Callable

from app.services.preprocessor.prolongation_geometry import (
    ProlongationGeometryError,
    ProlongationGeometryResult,
)

from ..contours_2d.models import HeightReductionContourInput
from ..models import CoggingCalculationInput, CoggingVariantResult, FeedSchedule
from ..shared_formulas import (
    contact_length_along_die_edge,
    feed_weighted_mean,
    final_length_of_contact,
    height_reduction_geometry,
    height_reduction_strains,
    require_positive,
    rough_bite_count,
)


HeightContourBuilder = Callable[[HeightReductionContourInput], ProlongationGeometryResult]


def calculate_height_reduction_variant(
    *,
    input_data: CoggingCalculationInput,
    feed_schedule: FeedSchedule,
    contour_builder: HeightContourBuilder,
    operation_specific_parameters: dict[str, object] | None = None,
    full_die_single_bite: bool = False,
) -> CoggingVariantResult:
    """Calculate one height-reduction variant without operation-family dispatch."""

    target_height_mm = require_positive(input_data.final_height_mm, "height")
    final_geometry, penetration_mm, notes = height_reduction_geometry(
        initial_geometry=input_data.initial_geometry,
        final_height_mm=target_height_mm,
    )

    initial_length_mm = input_data.initial_geometry.length_mm
    radius_contact_length_mm = contact_length_along_die_edge(
        top_die=input_data.top_die,
        bottom_die=input_data.bottom_die,
        total_penetration_mm=penetration_mm,
    )
    initial_length_of_contact_mm = min(
        feed_weighted_mean(
            initial_length_mm,
            feed_schedule.feed_first_mm,
            feed_schedule.feed_middle_mm,
            feed_schedule.feed_last_mm,
            feed_schedule.num_of_bites_input,
        ),
        initial_length_mm,
    )
    if full_die_single_bite:
        final_length_of_contact_mm = initial_length_mm
    else:
        final_length_of_contact_mm = final_length_of_contact(
            initial_length_mm=initial_length_mm,
            feed_first_mm=feed_schedule.feed_first_mm,
            feed_middle_mm=feed_schedule.feed_middle_mm,
            feed_last_mm=feed_schedule.feed_last_mm,
            radius_contact_length_mm=radius_contact_length_mm,
            num_of_bites=rough_bite_count(
                initial_length_mm,
                feed_schedule.feed_first_mm,
                feed_schedule.feed_middle_mm,
                feed_schedule.feed_last_mm,
                feed_schedule.num_of_bites_input,
            ),
        )

    parameters: dict[str, object] = {
        "height": final_geometry.height_mm,
        "rotation_per_bite": 0.0,
        "rotations_count_per_feed_list": (0, 0, 0),
    }
    if operation_specific_parameters:
        parameters.update(operation_specific_parameters)

    final_width_of_contact_mm = final_geometry.width_mm
    compiler_notes = list(notes)
    if penetration_mm > 0.0:
        try:
            contour_result = contour_builder(
                HeightReductionContourInput(
                    initial_geometry=input_data.initial_geometry,
                    final_height_mm=target_height_mm,
                    penetration_mm=penetration_mm,
                    top_die=input_data.top_die,
                    bottom_die=input_data.bottom_die,
                    angle_deg=input_data.angle_deg,
                    final_length_of_contact_mm=final_length_of_contact_mm,
                    strain_height=height_reduction_strains(
                        initial_geometry=input_data.initial_geometry,
                        final_geometry=final_geometry,
                        penetration_mm=penetration_mm,
                    ).strain_height,
                )
            )
            final_geometry = contour_result.final_geometry
            final_width_of_contact_mm = contour_result.final_width_of_contact_mm or final_geometry.width_mm
            parameters.update(
                {
                    "initial_dies_gap": contour_result.initial_dies_gap_mm,
                    "final_dies_gap": contour_result.final_dies_gap_mm,
                    "shapely_area_error_percent": contour_result.area_error_percent,
                    "shapely_die_trimming_used": contour_result.used_die_trimming,
                }
            )
            if not contour_result.used_die_trimming:
                compiler_notes.append("Shapely die-trimming fallback used scaled polygon.")
        except ProlongationGeometryError as exc:
            compiler_notes.append(f"Shapely die-trimming skipped: {exc}")

    return CoggingVariantResult(
        final_geometry=final_geometry,
        penetration_mm=penetration_mm,
        feed_schedule=feed_schedule,
        initial_length_of_contact_mm=initial_length_of_contact_mm,
        final_length_of_contact_mm=final_length_of_contact_mm,
        final_width_of_contact_mm=final_width_of_contact_mm,
        strains=height_reduction_strains(
            initial_geometry=input_data.initial_geometry,
            final_geometry=final_geometry,
            penetration_mm=penetration_mm,
        ),
        operation_specific_parameters=parameters,
        compiler_notes=tuple(compiler_notes),
    )
