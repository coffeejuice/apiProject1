"""Dependency-light prolongation deformation math extracted from the legacy preprocessor."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
from typing import Any

from .geometry import (
    GeneratedGeometry,
    outline_area_mm2,
    outline_perimeter_mm,
    scale_generated_geometry,
)
from .prolongation_geometry import (
    ProlongationGeometryError,
    apply_die_trimming_geometry,
    build_spiral_round_geometry,
)
from .upsetting import DieDimensions, PressModeParameters
from .operation_keys import (
    AXIAL_PROLONGATION_TEMPLATE_IDS,
    PROLONGATION_HEIGHT_BITES,
    PROLONGATION_SKIP_BITES,
    PROLONGATION_TEMPLATE_IDS,
    RADIAL_HEIGHT_BITES,
    RADIAL_PROLONGATION_TEMPLATE_IDS,
    RADIAL_ROTATION_HEIGHT_FEED,
    ROUNDING_SPIRAL_ONE_ROTATION,
    SPIRAL_PROLONGATION_TEMPLATE_IDS,
)


class ProlongationMathError(ValueError):
    """Raised when prolongation inputs are inconsistent or incomplete."""


@dataclass(frozen=True, slots=True)
class ProlongationComputationResult:
    """All prolongation-derived outputs for one control-program row."""

    final_geometry: GeneratedGeometry
    metrics: dict[str, Any]
    operation_specific_parameters: dict[str, Any] = field(default_factory=dict)
    total_time_seconds: float = 0.0
    time_before_operation_seconds: float | None = None
    simulation_expected_duration_days: float | None = None
    compiler_notes: tuple[str, ...] = ()


def calculate_prolongation(
    *,
    template_id: str,
    initial_geometry: GeneratedGeometry,
    press_mode: PressModeParameters,
    top_die: DieDimensions,
    bottom_die: DieDimensions,
    speed_mm_per_s: float,
    previous_total_time_seconds: float,
    time_between_operation_seconds: float | None,
    angle_deg: float = 0.0,
    final_height_mm: float | None = None,
    final_diameter_mm: float | None = None,
    radial_feed_mm: float | None = None,
    feed_mm: float | None = None,
    feed_first_mm: float | None = None,
    feed_middle_mm: float | None = None,
    feed_last_mm: float | None = None,
    num_of_bites_input: int | None = None,
    skip_bites: tuple[int, ...] = (),
    rotation_per_bite_deg: float = 0.0,
    current_feed_direction_id: int | None = None,
    previous_feed_direction_id: int | None = None,
    is_same_operation_type_as_previous: bool = False,
    mesh_elements: int | None = None,
    extra_rotations: dict[str, float] | None = None,
) -> ProlongationComputationResult:
    """Compute axial, spiral, and radial prolongation deformation and timing outputs."""

    if template_id not in PROLONGATION_TEMPLATE_IDS:
        raise ProlongationMathError(f"Unsupported prolongation template_id={template_id}")
    if speed_mm_per_s <= 0.0:
        raise ProlongationMathError(f"Working speed must be positive, got {speed_mm_per_s}")

    initial_length = initial_geometry.length_mm
    initial_width = initial_geometry.width_mm
    initial_height = initial_geometry.height_mm
    initial_area = initial_geometry.cross_section_area_mm2
    if min(initial_length, initial_width, initial_height, initial_area) <= 0.0:
        raise ProlongationMathError("Initial geometry dimensions and area must be positive")

    die_straight_length = min(top_die.straight_length_mm, bottom_die.straight_length_mm)

    notes: list[str] = []
    operation_specific_parameters: dict[str, Any] = {}

    if template_id in SPIRAL_PROLONGATION_TEMPLATE_IDS:
        try:
            spiral_geometry = build_spiral_round_geometry(
                initial_geometry=initial_geometry,
                final_diameter_mm=_require_positive(final_diameter_mm, "diameter"),
            )
            final_geometry = spiral_geometry.final_geometry
            penetration = max(0.0, initial_height - final_geometry.height_mm)
            final_width_of_contact = spiral_geometry.final_width_of_contact_mm or 0.5 * final_geometry.height_mm
        except ProlongationGeometryError as exc:
            final_geometry, penetration = _spiral_final_geometry(
                initial_geometry=initial_geometry,
                final_diameter_mm=final_diameter_mm,
            )
            final_width_of_contact = 0.5 * final_geometry.height_mm
            notes.append(f"Shapely spiral geometry fallback used: {exc}")
        base_feed_first = min(initial_height, 0.8 * die_straight_length)
        base_feed_middle = _require_positive(feed_mm, "feed")
        base_feed_last = 0.0
        rotations_count_per_feed_list = (5, 0, 5) if template_id == ROUNDING_SPIRAL_ONE_ROTATION else (5, 2, 5)
        operation_specific_parameters["diameter"] = final_geometry.height_mm
        operation_specific_parameters["rotation_per_bite"] = rotation_per_bite_deg
        operation_specific_parameters["rotations_count_per_feed_list"] = rotations_count_per_feed_list
        initial_length_of_contact = base_feed_first
        final_length_of_contact = base_feed_first
        initial_dies_gap = initial_height
        final_dies_gap = final_geometry.height_mm
        operation_specific_parameters.update(
            {
                "initial_dies_gap": initial_dies_gap,
                "final_dies_gap": final_dies_gap,
            }
        )
    else:
        target_height = _require_positive(final_height_mm, "height")
        if target_height >= initial_height:
            penetration = 0.0
            final_geometry = initial_geometry
            notes.append("Requested prolongation height is not below initial height; deformation is zero.")
        else:
            penetration = initial_height - target_height
            height_scale = target_height / initial_height
            width_scale = 1.0
            length_scale = 1.0 / height_scale
            final_geometry = scale_generated_geometry(
                initial_geometry,
                width_scale=width_scale,
                height_scale=height_scale,
                length_scale=length_scale,
                parameters_update={"height": target_height},
            )

        if template_id in RADIAL_PROLONGATION_TEMPLATE_IDS:
            if template_id == RADIAL_ROTATION_HEIGHT_FEED:
                base_feed_first = _require_positive(radial_feed_mm, "radial_feed")
                num_of_bites_input = None
            else:
                num_of_bites_input = _require_positive_int(num_of_bites_input, "num_of_bites")
                base_feed_first = initial_length / num_of_bites_input
            base_feed_middle = 0.0
            base_feed_last = 0.0
        else:
            if template_id in {PROLONGATION_HEIGHT_BITES, PROLONGATION_SKIP_BITES}:
                num_of_bites_input = _require_positive_int(num_of_bites_input, "num_of_bites")
                base_feed_first = initial_length / num_of_bites_input
                base_feed_middle = 0.0
                base_feed_last = 0.0
            else:
                base_feed_first = _positive_or_default(
                    feed_first_mm,
                    feed_mm,
                    min(initial_length, max(1.0, min(initial_height, 0.8 * die_straight_length))),
                )
                base_feed_middle = _positive_or_default(feed_middle_mm, base_feed_first)
                base_feed_last = _positive_or_default(feed_last_mm, base_feed_middle)

        radius_contact_length = _contact_length_along_die_edge(
            top_die=top_die,
            bottom_die=bottom_die,
            total_penetration_mm=penetration,
        )
        operation_specific_parameters["height"] = final_geometry.height_mm
        operation_specific_parameters["rotation_per_bite"] = 0.0
        operation_specific_parameters["rotations_count_per_feed_list"] = (0, 0, 0)
        initial_length_of_contact = min(_feed_weighted_mean(initial_length, base_feed_first, base_feed_middle, base_feed_last, num_of_bites_input), initial_length)
        final_length_of_contact = _final_length_of_contact(
            initial_length=initial_length,
            feed_first=base_feed_first,
            feed_middle=base_feed_middle,
            feed_last=base_feed_last,
            radius_contact_length=radius_contact_length,
            num_of_bites=_rough_bite_count(initial_length, base_feed_first, base_feed_middle, base_feed_last, num_of_bites_input),
        )
        final_width_of_contact = final_geometry.width_mm
        if penetration > 0.0:
            try:
                geometry_result = apply_die_trimming_geometry(
                    initial_geometry=initial_geometry,
                    final_height_mm=target_height,
                    penetration_mm=penetration,
                    top_die=top_die,
                    bottom_die=bottom_die,
                    angle_deg=angle_deg,
                    final_length_of_contact_mm=final_length_of_contact,
                    strain_height=math.log(target_height / initial_height),
                )
                final_geometry = geometry_result.final_geometry
                final_width_of_contact = geometry_result.final_width_of_contact_mm or final_geometry.width_mm
                operation_specific_parameters.update(
                    {
                        "initial_dies_gap": geometry_result.initial_dies_gap_mm,
                        "final_dies_gap": geometry_result.final_dies_gap_mm,
                        "shapely_area_error_percent": geometry_result.area_error_percent,
                        "shapely_die_trimming_used": geometry_result.used_die_trimming,
                    }
                )
                if not geometry_result.used_die_trimming:
                    notes.append("Shapely die-trimming fallback used scaled polygon.")
            except ProlongationGeometryError as exc:
                notes.append(f"Shapely die-trimming skipped: {exc}")

    bites_table = _build_bites_table(
        initial_length=initial_length,
        feed_first=base_feed_first,
        feed_middle=base_feed_middle,
        feed_last=base_feed_last,
        num_of_bites_input=num_of_bites_input,
        skip_bites=skip_bites,
        rotation_per_bite_deg=rotation_per_bite_deg if template_id in SPIRAL_PROLONGATION_TEMPLATE_IDS else 0.0,
        rotations_count_per_feed_list=operation_specific_parameters["rotations_count_per_feed_list"],
    )
    num_of_bites = len(bites_table)
    if num_of_bites <= 0:
        raise ProlongationMathError("Calculated bites table is empty")

    operation_specific_parameters.update(
        {
            "feed_first": base_feed_first,
            "feed_middle": base_feed_middle,
            "feed_last": base_feed_last,
            "bites_table": bites_table,
            "angle": angle_deg,
            "extra_rotations": extra_rotations or {},
        }
    )
    if template_id in RADIAL_PROLONGATION_TEMPLATE_IDS:
        operation_specific_parameters.update(
            {
                "radial_initial_rotations": _radial_initial_rotations(template_id),
                "radial_accumulated_billet_rotation": angle_deg,
                "radial_rotations": _radial_rotations(template_id, angle_deg, extra_rotations or {}),
            }
        )

    strain_height = 0.0 if penetration <= 0.0 else math.log(final_geometry.height_mm / initial_height)
    if template_id in SPIRAL_PROLONGATION_TEMPLATE_IDS:
        strain_length = math.log(initial_area / final_geometry.cross_section_area_mm2)
        strain_width = -0.5 * strain_length
        strain_height = strain_width
    else:
        strain_length = math.log(final_geometry.length_mm / initial_length)
        strain_width = -strain_height - strain_length

    actual_speed_mm_per_s = min(speed_mm_per_s, press_mode.working_speed_mm_per_s)
    working_stroke_mm = penetration
    working_approaching_stroke_mm = press_mode.approaching_distance_mm
    idle_stroke_mm = _idle_stroke(
        press_mode=press_mode,
        top_die=top_die,
        bottom_die=bottom_die,
        open_die_height_max_before_working_stroke_mm=initial_height,
        working_approaching_stroke_mm=working_approaching_stroke_mm,
    )
    back_stroke_mm = working_stroke_mm + working_approaching_stroke_mm + idle_stroke_mm
    time_between_bites_seconds = idle_stroke_mm / press_mode.idle_speed_mm_per_s + back_stroke_mm / press_mode.back_speed_mm_per_s
    time_bite_working_seconds = 0.0 if working_stroke_mm <= 0.0 else working_stroke_mm / actual_speed_mm_per_s
    cycle_time_seconds = time_bite_working_seconds + time_between_bites_seconds

    manipulator_movement_time_seconds = 0.0
    if is_same_operation_type_as_previous:
        if (
            current_feed_direction_id is not None
            and previous_feed_direction_id is not None
            and current_feed_direction_id != previous_feed_direction_id
        ):
            manipulator_movement_time_seconds += initial_length / 400.0 + 2.0
        manipulator_movement_time_seconds += _billet_rotation_time(angle_deg)

    time_before_pass = (
        (time_between_operation_seconds or 0.0)
        + manipulator_movement_time_seconds
        - time_between_bites_seconds
    )
    total_time_seconds = previous_total_time_seconds + time_before_pass + time_bite_working_seconds * num_of_bites + time_between_bites_seconds * (num_of_bites - 1)

    initial_surface_area_mm2 = _surface_area_mm2(initial_geometry)
    final_surface_area_mm2 = _surface_area_mm2(final_geometry)
    accumulated_strain_increment = _strain_accumulated_increment(
        strain_length=strain_length,
        strain_height=strain_height,
        strain_width=strain_width,
    )

    metrics = {
        "initial_length": initial_length,
        "initial_width": initial_width,
        "initial_height": initial_height,
        "initial_cross_section_area_mm2": initial_area,
        "final_length": final_geometry.length_mm,
        "final_width": final_geometry.width_mm,
        "final_height": final_geometry.height_mm,
        "final_cross_section_area_mm2": final_geometry.cross_section_area_mm2,
        "initial_height_to_width_ratio": initial_height / initial_width,
        "final_height_to_width_ratio": final_geometry.height_mm / final_geometry.width_mm,
        "penetration": penetration,
        "relative_deformation_percent": 0.0 if initial_height <= 0.0 else penetration / initial_height * 100.0,
        "feed_first": base_feed_first,
        "feed_middle": base_feed_middle,
        "feed_last": base_feed_last,
        "num_of_bites": num_of_bites,
        "initial_length_of_contact": initial_length_of_contact,
        "final_length_of_contact": final_length_of_contact,
        "final_width_of_contact": final_width_of_contact,
        "strain_length": strain_length,
        "strain_height": strain_height,
        "strain_width": strain_width,
        "equivalent_diameter_mm": final_geometry.equivalent_diameter_mm,
        "elongation_increment": final_geometry.length_mm / initial_length,
        "strain_accumulated_increment": accumulated_strain_increment,
        "actual_speed_mm_per_s": actual_speed_mm_per_s,
        "open_die_height_max_before_working_stroke_mm": initial_height,
        "open_die_height_min_after_working_stroke_mm": final_geometry.height_mm,
        "working_stroke_mm": working_stroke_mm,
        "working_approaching_stroke_mm": working_approaching_stroke_mm,
        "idle_stroke_mm": idle_stroke_mm,
        "back_stroke_mm": back_stroke_mm,
        "open_die_height_before_idle_stroke_mm": initial_height + working_approaching_stroke_mm + idle_stroke_mm,
        "time_between_bites_seconds": time_between_bites_seconds,
        "time_bite_working_seconds": time_bite_working_seconds,
        "cycle_time_seconds": cycle_time_seconds,
        "time_before_pass_seconds": time_before_pass,
        "initial_surface_area_mm2": initial_surface_area_mm2,
        "final_surface_area_mm2": final_surface_area_mm2,
        "mesh_elements": mesh_elements,
    }

    return ProlongationComputationResult(
        final_geometry=final_geometry,
        metrics=metrics,
        operation_specific_parameters=operation_specific_parameters,
        total_time_seconds=total_time_seconds,
        time_before_operation_seconds=time_before_pass,
        simulation_expected_duration_days=None,
        compiler_notes=tuple(notes),
    )


def _spiral_final_geometry(
    *,
    initial_geometry: GeneratedGeometry,
    final_diameter_mm: float | None,
) -> tuple[GeneratedGeometry, float]:
    diameter = _require_positive(final_diameter_mm, "diameter")
    radius = diameter / 2.0
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
        raise ProlongationMathError("Calculated spiral final cross-section area is not positive")
    length = initial_geometry.volume_mm3 / area
    equivalent_diameter = math.sqrt(4.0 * area / math.pi)
    parameters = dict(initial_geometry.parameters)
    parameters.update({"diameter": diameter})
    final_geometry = GeneratedGeometry(
        type_id=initial_geometry.type_id,
        shape="round",
        parameters=parameters,
        volume_mm3=initial_geometry.volume_mm3,
        cross_section_area_mm2=area,
        equivalent_diameter_mm=equivalent_diameter,
        width_mm=diameter,
        height_mm=diameter,
        length_mm=length,
        cross_section_outline=outline,
        parameters_json=json.dumps(parameters, sort_keys=True),
    )
    penetration = max(0.0, initial_geometry.height_mm - diameter)
    return final_geometry, penetration


def _build_bites_table(
    *,
    initial_length: float,
    feed_first: float,
    feed_middle: float,
    feed_last: float,
    num_of_bites_input: int | None,
    skip_bites: tuple[int, ...],
    rotation_per_bite_deg: float,
    rotations_count_per_feed_list: tuple[int, int, int],
) -> list[list[object]]:
    if num_of_bites_input is not None:
        base_count = max(1, int(num_of_bites_input))
    else:
        base_feed = _first_positive(feed_middle, feed_first, feed_last)
        base_count = max(1, int(math.ceil(initial_length / base_feed)))

    if base_count == 1:
        feeds = [min(initial_length, feed_first)]
    else:
        feeds = []
        for index in range(base_count):
            if index == 0:
                feeds.append(feed_first)
            elif index == base_count - 1:
                feeds.append(_first_positive(feed_last, feed_middle, feed_first))
            else:
                feeds.append(_first_positive(feed_middle, feed_first))

    bites_table: list[list[object]] = []
    skip_set = {value for value in skip_bites if value > 0}
    for index, feed in enumerate(feeds, start=1):
        if index in skip_set:
            continue
        if index == 1:
            rotations_count = rotations_count_per_feed_list[0]
        elif index == len(feeds):
            rotations_count = rotations_count_per_feed_list[2]
        else:
            rotations_count = rotations_count_per_feed_list[1]
        rotations_count = max(1, rotations_count) if any(rotations_count_per_feed_list) else 1

        pointer = "relative_die_center" if len(feeds) == 1 or index == len(feeds) else "relative_die_edge"
        relative_position = 0.5 if len(feeds) == 1 else min(1.0, max(0.0, index / len(feeds)))
        first_rotation = 0.0 if not bites_table else rotation_per_bite_deg
        bites_table.append(["manual_feed", pointer, first_rotation, float(feed), relative_position])
        for _ in range(rotations_count - 1):
            bites_table.append(["manual_feed", pointer, rotation_per_bite_deg, 0.0, relative_position])
    return bites_table


def _rough_bite_count(
    initial_length: float,
    feed_first: float,
    feed_middle: float,
    feed_last: float,
    num_of_bites_input: int | None,
) -> float:
    if num_of_bites_input is not None:
        return float(max(1, num_of_bites_input))
    first_feed_count = initial_length / feed_first
    if first_feed_count <= 1.0:
        return first_feed_count
    last_feed = _first_positive(feed_last, feed_middle, feed_first)
    last_feed_count = (initial_length - feed_first) / last_feed
    if last_feed_count <= 1.0:
        return 1.0 + last_feed_count
    other_feed = _first_positive(feed_middle, feed_first)
    return 2.0 + (initial_length - feed_first - last_feed) / other_feed


def _feed_weighted_mean(
    initial_length: float,
    feed_first: float,
    feed_middle: float,
    feed_last: float,
    num_of_bites_input: int | None,
) -> float:
    approx_count = _rough_bite_count(initial_length, feed_first, feed_middle, feed_last, num_of_bites_input)
    if approx_count < 1.0:
        return feed_first
    last_feed = _first_positive(feed_last, feed_middle, feed_first)
    if approx_count < 2.0:
        return (feed_first + last_feed) / 2.0
    other_feed = _first_positive(feed_middle, feed_first)
    return (feed_first + last_feed + other_feed * (approx_count - 2.0)) / approx_count


def _final_length_of_contact(
    *,
    initial_length: float,
    feed_first: float,
    feed_middle: float,
    feed_last: float,
    radius_contact_length: float,
    num_of_bites: float,
) -> float:
    if feed_middle > 0.0 and feed_last > 0.0:
        if num_of_bites < 3.0:
            return feed_first + radius_contact_length
        middle_bite_count = num_of_bites - 2.0
        return (2.0 * (feed_first + radius_contact_length) + middle_bite_count * (feed_middle + 2.0 * radius_contact_length)) / num_of_bites
    if feed_middle > 0.0:
        if num_of_bites <= 1.0:
            return feed_first + radius_contact_length
        middle_bite_count = num_of_bites - 1.0
        return (feed_first + radius_contact_length + middle_bite_count * (feed_middle + 2.0 * radius_contact_length)) / num_of_bites
    return min(initial_length, feed_first + radius_contact_length)


def _contact_length_along_die_edge(
    *,
    top_die: DieDimensions,
    bottom_die: DieDimensions,
    total_penetration_mm: float,
    at_relative_penetration_percent: float = 100.0,
) -> float:
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


def _idle_stroke(
    *,
    press_mode: PressModeParameters,
    top_die: DieDimensions,
    bottom_die: DieDimensions,
    open_die_height_max_before_working_stroke_mm: float,
    working_approaching_stroke_mm: float,
) -> float:
    total_die_height = top_die.height_mm + bottom_die.height_mm
    max_open_height = press_mode.open_height_without_dies_mm - total_die_height
    if max_open_height <= 0.0:
        raise ProlongationMathError("Press open height without dies is not above total die height")
    relative_required_open_die_height = open_die_height_max_before_working_stroke_mm / max_open_height
    target_idle_stroke = press_mode.min_idle_stroke_mm + (
        press_mode.max_idle_stroke_mm - press_mode.min_idle_stroke_mm
    ) * relative_required_open_die_height
    available_idle_stroke = max_open_height - open_die_height_max_before_working_stroke_mm - working_approaching_stroke_mm
    return max(0.0, min(target_idle_stroke, available_idle_stroke))


def _surface_area_mm2(geometry: GeneratedGeometry) -> float:
    return 2.0 * geometry.cross_section_area_mm2 + outline_perimeter_mm(geometry.cross_section_outline) * geometry.length_mm


def _strain_accumulated_increment(
    *,
    strain_length: float,
    strain_height: float,
    strain_width: float,
) -> float:
    e_hl = (strain_height - strain_length) ** 2
    e_wh = (strain_width - strain_height) ** 2
    e_lw = (strain_length - strain_width) ** 2
    return math.sqrt(2.0) / 3.0 * math.sqrt(e_lw + e_wh + e_hl)


def _billet_rotation_time(angle_deg: float) -> float:
    if angle_deg == 0.0:
        return 0.0
    return angle_deg / 360.0 * 1.5 + 1.0


def _radial_initial_rotations(template_id: str) -> list[tuple[str, float]]:
    if template_id in {RADIAL_ROTATION_HEIGHT_FEED, RADIAL_HEIGHT_BITES}:
        return [("y", 90.0)]
    return []


def _radial_rotations(
    template_id: str,
    angle_deg: float,
    extra_rotations: dict[str, float],
) -> list[tuple[str, float]]:
    if template_id in {RADIAL_ROTATION_HEIGHT_FEED, RADIAL_HEIGHT_BITES}:
        return [("y", 90.0), ("x", angle_deg)]
    return [
        ("x", angle_deg),
        ("y", float(extra_rotations.get("y_rotation", 0.0))),
        ("z", float(extra_rotations.get("z_rotation", 0.0))),
    ]


def _require_positive(value: float | None, name: str) -> float:
    if value is None:
        raise ProlongationMathError(f"Prolongation requires {name}")
    value = float(value)
    if value <= 0.0:
        raise ProlongationMathError(f"{name} must be positive, got {value}")
    return value


def _require_positive_int(value: int | None, name: str) -> int:
    if value is None:
        raise ProlongationMathError(f"Prolongation requires {name}")
    value = int(value)
    if value <= 0:
        raise ProlongationMathError(f"{name} must be positive, got {value}")
    return value


def _positive_or_default(*values: float | None) -> float:
    for value in values:
        if value is None:
            continue
        value = float(value)
        if value > 0.0:
            return value
    raise ProlongationMathError("No positive feed value is available")


def _first_positive(*values: float | None) -> float:
    for value in values:
        if value is None:
            continue
        value = float(value)
        if value > 0.0:
            return value
    return 0.0
