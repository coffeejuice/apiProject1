"""Shared engineering formulas for cogging/prolongation calculations."""

from __future__ import annotations

import math
from typing import Any

from app.services.preprocessor.geometry import (
    GeneratedGeometry,
    outline_perimeter_mm,
    scale_generated_geometry,
)
from app.services.preprocessor.upsetting import DieDimensions, PressModeParameters

from .models import (
    CoggingCalculationInput,
    CoggingComputationResult,
    CoggingMathError,
    CoggingStrains,
    CoggingVariantResult,
    FeedSchedule,
)


def validate_press_and_geometry(input_data: CoggingCalculationInput) -> None:
    """Validate inputs common to every cogging/prolongation variant."""

    if input_data.speed_mm_per_s <= 0.0:
        raise CoggingMathError(f"Working speed must be positive, got {input_data.speed_mm_per_s}")
    if input_data.speed_mm_per_s > input_data.press_mode.working_speed_mm_per_s:
        raise CoggingMathError(
            f"Working speed {input_data.speed_mm_per_s} exceeds press mode maximum "
            f"{input_data.press_mode.working_speed_mm_per_s}"
        )

    geometry = input_data.initial_geometry
    if min(
        geometry.length_mm,
        geometry.width_mm,
        geometry.height_mm,
        geometry.cross_section_area_mm2,
    ) <= 0.0:
        raise CoggingMathError("Initial geometry dimensions and area must be positive")


def require_positive(value: float | None, name: str) -> float:
    """Return a positive scalar or raise a calculation error."""

    if value is None:
        raise CoggingMathError(f"Prolongation requires {name}")
    value = float(value)
    if value <= 0.0:
        raise CoggingMathError(f"{name} must be positive, got {value}")
    return value


def require_positive_int(value: int | None, name: str) -> int:
    """Return a positive integer or raise a calculation error."""

    if value is None:
        raise CoggingMathError(f"Prolongation requires {name}")
    value = int(value)
    if value <= 0:
        raise CoggingMathError(f"{name} must be positive, got {value}")
    return value


def positive_or_default(*values: float | None) -> float:
    """Return the first positive value from an ordered fallback list."""

    for value in values:
        if value is None:
            continue
        value = float(value)
        if value > 0.0:
            return value
    raise CoggingMathError("No positive feed value is available")


def first_positive(*values: float | None) -> float:
    """Return the first positive value, or zero when every value is missing/non-positive."""

    for value in values:
        if value is None:
            continue
        value = float(value)
        if value > 0.0:
            return value
    return 0.0


def default_axial_feed_mm(input_data: CoggingCalculationInput) -> float:
    """Default axial/full-die feed from billet length, billet height, and die length."""

    initial_geometry = input_data.initial_geometry
    die_straight_length = min(input_data.top_die.straight_length_mm, input_data.bottom_die.straight_length_mm)
    return min(
        initial_geometry.length_mm,
        max(1.0, min(initial_geometry.height_mm, 0.8 * die_straight_length)),
    )


def height_reduction_geometry(
    *,
    initial_geometry: GeneratedGeometry,
    final_height_mm: float,
) -> tuple[GeneratedGeometry, float, tuple[str, ...]]:
    """Calculate the simple volume-preserving height-reduction geometry."""

    notes: list[str] = []
    if final_height_mm >= initial_geometry.height_mm:
        notes.append("Requested prolongation height is not below initial height; deformation is zero.")
        return initial_geometry, 0.0, tuple(notes)

    penetration_mm = initial_geometry.height_mm - final_height_mm
    height_scale = final_height_mm / initial_geometry.height_mm
    final_geometry = scale_generated_geometry(
        initial_geometry,
        width_scale=1.0,
        height_scale=height_scale,
        length_scale=1.0 / height_scale,
        parameters_update={"height": final_height_mm},
    )
    return final_geometry, penetration_mm, tuple(notes)


def contact_length_along_die_edge(
    *,
    top_die: DieDimensions,
    bottom_die: DieDimensions,
    total_penetration_mm: float,
    at_relative_penetration_percent: float = 100.0,
) -> float:
    """Contact length contributed by die edge radii at a penetration depth."""

    if total_penetration_mm <= 0.0 or at_relative_penetration_percent <= 0.0:
        return 0.0
    one_side_penetration = 0.5 * total_penetration_mm * at_relative_penetration_percent / 100.0
    contact_lengths: list[tuple[float, float]] = []
    for die in (top_die, bottom_die):
        radius = max(die.edge_radius_mm, 0.0)
        if radius <= 0.0:
            contact_length = 0.0
        elif one_side_penetration >= radius:
            contact_length = radius
        else:
            contact_angle = math.acos(1.0 - one_side_penetration / radius)
            contact_length = radius * math.sin(contact_angle)
        working_length = die.straight_length_mm + 2.0 * contact_length
        contact_lengths.append((working_length, contact_length))
    return min(contact_lengths, key=lambda item: item[0])[1]


def rough_bite_count(
    initial_length_mm: float,
    feed_first_mm: float,
    feed_middle_mm: float,
    feed_last_mm: float,
    num_of_bites_input: int | None,
) -> float:
    """Continuous estimate of bite count used by contact-length formulas."""

    if num_of_bites_input is not None:
        return float(max(1, num_of_bites_input))
    first_feed_count = initial_length_mm / feed_first_mm
    if first_feed_count <= 1.0:
        return first_feed_count
    last_feed = first_positive(feed_last_mm, feed_middle_mm, feed_first_mm)
    last_feed_count = (initial_length_mm - feed_first_mm) / last_feed
    if last_feed_count <= 1.0:
        return 1.0 + last_feed_count
    other_feed = first_positive(feed_middle_mm, feed_first_mm)
    return 2.0 + (initial_length_mm - feed_first_mm - last_feed) / other_feed


def feed_weighted_mean(
    initial_length_mm: float,
    feed_first_mm: float,
    feed_middle_mm: float,
    feed_last_mm: float,
    num_of_bites_input: int | None,
) -> float:
    """Mean feed weighted by first, middle, and last bites."""

    approx_count = rough_bite_count(
        initial_length_mm,
        feed_first_mm,
        feed_middle_mm,
        feed_last_mm,
        num_of_bites_input,
    )
    if approx_count < 1.0:
        return feed_first_mm
    last_feed = first_positive(feed_last_mm, feed_middle_mm, feed_first_mm)
    if approx_count < 2.0:
        return (feed_first_mm + last_feed) / 2.0
    other_feed = first_positive(feed_middle_mm, feed_first_mm)
    return (feed_first_mm + last_feed + other_feed * (approx_count - 2.0)) / approx_count


def final_length_of_contact(
    *,
    initial_length_mm: float,
    feed_first_mm: float,
    feed_middle_mm: float,
    feed_last_mm: float,
    radius_contact_length_mm: float,
    num_of_bites: float,
) -> float:
    """Final bite contact length in the manipulator axis."""

    if feed_middle_mm > 0.0 and feed_last_mm > 0.0:
        if num_of_bites < 3.0:
            return feed_first_mm + radius_contact_length_mm
        middle_bite_count = num_of_bites - 2.0
        return (
            2.0 * (feed_first_mm + radius_contact_length_mm)
            + middle_bite_count * (feed_middle_mm + 2.0 * radius_contact_length_mm)
        ) / num_of_bites
    if feed_middle_mm > 0.0:
        if num_of_bites <= 1.0:
            return feed_first_mm + radius_contact_length_mm
        middle_bite_count = num_of_bites - 1.0
        return (
            feed_first_mm
            + radius_contact_length_mm
            + middle_bite_count * (feed_middle_mm + 2.0 * radius_contact_length_mm)
        ) / num_of_bites
    return min(initial_length_mm, feed_first_mm + radius_contact_length_mm)


def height_reduction_strains(
    *,
    initial_geometry: GeneratedGeometry,
    final_geometry: GeneratedGeometry,
    penetration_mm: float,
) -> CoggingStrains:
    """Principal logarithmic strains for axial/radial/full-die height reduction."""

    strain_height = 0.0 if penetration_mm <= 0.0 else math.log(final_geometry.height_mm / initial_geometry.height_mm)
    strain_length = math.log(final_geometry.length_mm / initial_geometry.length_mm)
    strain_width = -strain_height - strain_length
    return CoggingStrains(
        strain_length=strain_length,
        strain_height=strain_height,
        strain_width=strain_width,
    )


def spiral_rounding_strains(
    *,
    initial_geometry: GeneratedGeometry,
    final_geometry: GeneratedGeometry,
) -> CoggingStrains:
    """Principal logarithmic strains for spiral rounding based on area change."""

    strain_length = math.log(initial_geometry.cross_section_area_mm2 / final_geometry.cross_section_area_mm2)
    strain_width = -0.5 * strain_length
    return CoggingStrains(
        strain_length=strain_length,
        strain_height=strain_width,
        strain_width=strain_width,
    )


def build_bites_table(
    *,
    initial_length_mm: float,
    schedule: FeedSchedule,
) -> list[list[object]]:
    """Build the old control-program manual-feed bite table."""

    if schedule.num_of_bites_input is not None:
        base_count = max(1, int(schedule.num_of_bites_input))
    else:
        base_feed = first_positive(
            schedule.feed_middle_mm,
            schedule.feed_first_mm,
            schedule.feed_last_mm,
        )
        base_count = max(1, int(math.ceil(initial_length_mm / base_feed)))

    if base_count == 1:
        feeds = [min(initial_length_mm, schedule.feed_first_mm)]
    else:
        feeds = []
        for index in range(base_count):
            if index == 0:
                feeds.append(schedule.feed_first_mm)
            elif index == base_count - 1:
                feeds.append(first_positive(schedule.feed_last_mm, schedule.feed_middle_mm, schedule.feed_first_mm))
            else:
                feeds.append(first_positive(schedule.feed_middle_mm, schedule.feed_first_mm))

    bites_table: list[list[object]] = []
    skip_set = {value for value in schedule.skip_bites if value > 0}
    for index, feed in enumerate(feeds, start=1):
        if index in skip_set:
            continue
        if index == 1:
            rotations_count = schedule.rotations_count_per_feed_list[0]
        elif index == len(feeds):
            rotations_count = schedule.rotations_count_per_feed_list[2]
        else:
            rotations_count = schedule.rotations_count_per_feed_list[1]
        rotations_count = max(1, rotations_count) if any(schedule.rotations_count_per_feed_list) else 1

        pointer = "relative_die_center" if len(feeds) == 1 or index == len(feeds) else "relative_die_edge"
        relative_position = 0.5 if len(feeds) == 1 else min(1.0, max(0.0, index / len(feeds)))
        first_rotation = 0.0 if not bites_table else schedule.rotation_per_bite_deg
        bites_table.append(["manual_feed", pointer, first_rotation, float(feed), relative_position])
        for _ in range(rotations_count - 1):
            bites_table.append(
                [
                    "manual_feed",
                    pointer,
                    schedule.rotation_per_bite_deg,
                    0.0,
                    relative_position,
                ]
            )
    return bites_table


def idle_stroke(
    *,
    press_mode: PressModeParameters,
    top_die: DieDimensions,
    bottom_die: DieDimensions,
    open_die_height_max_before_working_stroke_mm: float,
    working_approaching_stroke_mm: float,
) -> float:
    """Press idle stroke before the next working bite."""

    total_die_height = top_die.height_mm + bottom_die.height_mm
    max_open_height = press_mode.open_height_without_dies_mm - total_die_height
    if max_open_height <= 0.0:
        raise CoggingMathError("Press open height without dies is not above total die height")
    relative_required_open_die_height = open_die_height_max_before_working_stroke_mm / max_open_height
    target_idle_stroke = press_mode.min_idle_stroke_mm + (
        press_mode.max_idle_stroke_mm - press_mode.min_idle_stroke_mm
    ) * relative_required_open_die_height
    available_idle_stroke = (
        max_open_height
        - open_die_height_max_before_working_stroke_mm
        - working_approaching_stroke_mm
    )
    return max(0.0, min(target_idle_stroke, available_idle_stroke))


def surface_area_mm2(geometry: GeneratedGeometry) -> float:
    """External surface area of an extruded billet-like geometry."""

    return 2.0 * geometry.cross_section_area_mm2 + outline_perimeter_mm(geometry.cross_section_outline) * geometry.length_mm


def strain_accumulated_increment(strains: CoggingStrains) -> float:
    """Von-Mises-like accumulated strain increment from principal strains."""

    e_hl = (strains.strain_height - strains.strain_length) ** 2
    e_wh = (strains.strain_width - strains.strain_height) ** 2
    e_lw = (strains.strain_length - strains.strain_width) ** 2
    return math.sqrt(2.0) / 3.0 * math.sqrt(e_lw + e_wh + e_hl)


def relative_deformation_percent(*, initial_height_mm: float, penetration_mm: float) -> float:
    """Percent height reduction."""

    return 0.0 if initial_height_mm <= 0.0 else penetration_mm / initial_height_mm * 100.0


def billet_rotation_time(angle_deg: float) -> float:
    """Manipulator rotation time used by the legacy Pre formulas."""

    if angle_deg == 0.0:
        return 0.0
    return angle_deg / 360.0 * 1.5 + 1.0


def assemble_cogging_result(
    *,
    input_data: CoggingCalculationInput,
    variant: CoggingVariantResult,
) -> CoggingComputationResult:
    """Assemble common bite-table, timing, metric, and payload outputs."""

    initial_geometry = input_data.initial_geometry
    final_geometry = variant.final_geometry
    schedule = variant.feed_schedule

    bites_table = build_bites_table(
        initial_length_mm=initial_geometry.length_mm,
        schedule=schedule,
    )
    num_of_bites = len(bites_table)
    if num_of_bites <= 0:
        raise CoggingMathError("Calculated bites table is empty")

    operation_specific_parameters: dict[str, Any] = dict(variant.operation_specific_parameters)
    operation_specific_parameters.update(
        {
            "feed_first": schedule.feed_first_mm,
            "feed_middle": schedule.feed_middle_mm,
            "feed_last": schedule.feed_last_mm,
            "bites_table": bites_table,
            "angle": input_data.angle_deg,
            "extra_rotations": input_data.extra_rotations or {},
        }
    )

    working_stroke_mm = variant.penetration_mm
    working_approaching_stroke_mm = input_data.press_mode.approaching_distance_mm
    idle_stroke_mm = idle_stroke(
        press_mode=input_data.press_mode,
        top_die=input_data.top_die,
        bottom_die=input_data.bottom_die,
        open_die_height_max_before_working_stroke_mm=initial_geometry.height_mm,
        working_approaching_stroke_mm=working_approaching_stroke_mm,
    )
    back_stroke_mm = working_stroke_mm + working_approaching_stroke_mm + idle_stroke_mm
    time_between_bites_seconds = (
        idle_stroke_mm / input_data.press_mode.idle_speed_mm_per_s
        + back_stroke_mm / input_data.press_mode.back_speed_mm_per_s
    )
    time_bite_working_seconds = 0.0 if working_stroke_mm <= 0.0 else working_stroke_mm / input_data.speed_mm_per_s
    cycle_time_seconds = time_bite_working_seconds + time_between_bites_seconds

    manipulator_movement_time_seconds = 0.0
    if input_data.is_same_operation_type_as_previous:
        if (
            input_data.current_feed_direction_id is not None
            and input_data.previous_feed_direction_id is not None
            and input_data.current_feed_direction_id != input_data.previous_feed_direction_id
        ):
            manipulator_movement_time_seconds += initial_geometry.length_mm / 400.0 + 2.0
        manipulator_movement_time_seconds += billet_rotation_time(input_data.angle_deg)

    time_before_pass = (
        (input_data.time_between_operation_seconds or 0.0)
        + manipulator_movement_time_seconds
        - time_between_bites_seconds
    )
    total_time_seconds = (
        input_data.previous_total_time_seconds
        + time_before_pass
        + time_bite_working_seconds * num_of_bites
        + time_between_bites_seconds * (num_of_bites - 1)
    )

    initial_surface_area_mm2 = surface_area_mm2(initial_geometry)
    final_surface_area_mm2 = surface_area_mm2(final_geometry)
    accumulated_strain_increment = strain_accumulated_increment(variant.strains)

    metrics = {
        "initial_length": initial_geometry.length_mm,
        "initial_width": initial_geometry.width_mm,
        "initial_height": initial_geometry.height_mm,
        "initial_cross_section_area_mm2": initial_geometry.cross_section_area_mm2,
        "final_length": final_geometry.length_mm,
        "final_width": final_geometry.width_mm,
        "final_height": final_geometry.height_mm,
        "final_cross_section_area_mm2": final_geometry.cross_section_area_mm2,
        "initial_height_to_width_ratio": initial_geometry.height_mm / initial_geometry.width_mm,
        "final_height_to_width_ratio": final_geometry.height_mm / final_geometry.width_mm,
        "penetration": variant.penetration_mm,
        "relative_deformation_percent": relative_deformation_percent(
            initial_height_mm=initial_geometry.height_mm,
            penetration_mm=variant.penetration_mm,
        ),
        "feed_first": schedule.feed_first_mm,
        "feed_middle": schedule.feed_middle_mm,
        "feed_last": schedule.feed_last_mm,
        "num_of_bites": num_of_bites,
        "initial_length_of_contact": variant.initial_length_of_contact_mm,
        "final_length_of_contact": variant.final_length_of_contact_mm,
        "final_width_of_contact": variant.final_width_of_contact_mm,
        "strain_length": variant.strains.strain_length,
        "strain_height": variant.strains.strain_height,
        "strain_width": variant.strains.strain_width,
        "equivalent_diameter_mm": final_geometry.equivalent_diameter_mm,
        "elongation_increment": final_geometry.length_mm / initial_geometry.length_mm,
        "strain_accumulated_increment": accumulated_strain_increment,
        "actual_speed_mm_per_s": input_data.speed_mm_per_s,
        "open_die_height_max_before_working_stroke_mm": initial_geometry.height_mm,
        "open_die_height_min_after_working_stroke_mm": final_geometry.height_mm,
        "working_stroke_mm": working_stroke_mm,
        "working_approaching_stroke_mm": working_approaching_stroke_mm,
        "idle_stroke_mm": idle_stroke_mm,
        "back_stroke_mm": back_stroke_mm,
        "open_die_height_before_idle_stroke_mm": initial_geometry.height_mm + working_approaching_stroke_mm + idle_stroke_mm,
        "time_between_bites_seconds": time_between_bites_seconds,
        "time_bite_working_seconds": time_bite_working_seconds,
        "cycle_time_seconds": cycle_time_seconds,
        "time_before_pass_seconds": time_before_pass,
        "initial_surface_area_mm2": initial_surface_area_mm2,
        "final_surface_area_mm2": final_surface_area_mm2,
        "mesh_elements": input_data.mesh_elements,
    }

    return CoggingComputationResult(
        final_geometry=final_geometry,
        metrics=metrics,
        operation_specific_parameters=operation_specific_parameters,
        total_time_seconds=total_time_seconds,
        time_before_operation_seconds=time_before_pass,
        simulation_expected_duration_days=None,
        compiler_notes=variant.compiler_notes,
    )
