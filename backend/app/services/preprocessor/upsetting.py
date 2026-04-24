"""Dependency-light upsetting deformation math extracted from the legacy preprocessor."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any

from .geometry import (
    GeneratedGeometry,
    outline_perimeter_mm,
    scale_generated_geometry,
)


class UpsettingMathError(ValueError):
    """Raised when upsetting inputs are inconsistent or incomplete."""


@dataclass(frozen=True, slots=True)
class DieDimensions:
    """Subset of die geometry needed by upsetting formulas."""

    die_id: int | None
    straight_length_mm: float
    edge_radius_mm: float
    edge_angle_deg: float
    height_mm: float

    @classmethod
    def from_mapping(cls, payload: dict[str, Any], *, default_id: int | None = None) -> "DieDimensions":
        return cls(
            die_id=int(payload.get("id", default_id)) if payload.get("id", default_id) is not None else None,
            straight_length_mm=float(payload["straight_length"]),
            edge_radius_mm=float(payload["edge_radius"]),
            edge_angle_deg=float(payload.get("edge_angle", 90.0)),
            height_mm=float(payload["height"]),
        )


@dataclass(frozen=True, slots=True)
class PressModeParameters:
    """Subset of press-mode parameters needed by upsetting formulas."""

    press_mode_id: int | None
    working_speed_mm_per_s: float
    back_speed_mm_per_s: float
    idle_speed_mm_per_s: float
    approaching_distance_mm: float
    min_idle_stroke_mm: float
    max_idle_stroke_mm: float
    open_height_without_dies_mm: float
    max_force: float | None = None

    @classmethod
    def from_mapping(
        cls,
        payload: dict[str, Any],
        *,
        default_id: int | None = None,
    ) -> "PressModeParameters":
        return cls(
            press_mode_id=int(payload.get("id", default_id)) if payload.get("id", default_id) is not None else None,
            working_speed_mm_per_s=float(payload["working_speed"]),
            back_speed_mm_per_s=float(payload["back_speed"]),
            idle_speed_mm_per_s=float(payload["idle_speed"]),
            approaching_distance_mm=float(payload["approaching_distance"]),
            min_idle_stroke_mm=float(payload["min_idle_stroke"]),
            max_idle_stroke_mm=float(payload["max_idle_stroke"]),
            open_height_without_dies_mm=float(payload["open_height_without_dies"]),
            max_force=float(payload["max_force"]) if payload.get("max_force") is not None else None,
        )


@dataclass(frozen=True, slots=True)
class UpsettingComputationResult:
    """All upsetting-derived outputs for one control-program row."""

    final_geometry: GeneratedGeometry
    metrics: dict[str, Any]
    operation_specific_parameters: dict[str, Any] = field(default_factory=dict)
    total_time_seconds: float = 0.0
    time_before_operation_seconds: float | None = None
    simulation_expected_duration_days: float | None = None
    compiler_notes: tuple[str, ...] = ()


def calculate_upsetting(
    *,
    type_id: int,
    initial_geometry: GeneratedGeometry,
    press_mode: PressModeParameters,
    top_die: DieDimensions,
    bottom_die: DieDimensions,
    speed_mm_per_s: float,
    previous_total_time_seconds: float,
    previous_type_id: int | None,
    time_between_operation_seconds: float | None,
    angle_deg: float = 0.0,
    final_length_input_mm: float | None = None,
    stroke_mm: float | None = None,
    is_same_operation_type_as_previous: bool = False,
    current_feed_direction_id: int | None = None,
    previous_feed_direction_id: int | None = None,
    mesh_elements: int | None = None,
) -> UpsettingComputationResult:
    """Compute upsetting deformation, geometry, and timing outputs."""

    if type_id not in {91, 92, 93, 94, 100}:
        raise UpsettingMathError(f"Unsupported upsetting type_id={type_id}")
    if speed_mm_per_s <= 0.0:
        raise UpsettingMathError(f"Working speed must be positive, got {speed_mm_per_s}")

    operation_specific_parameters: dict[str, Any] = {}

    initial_length = initial_geometry.length_mm
    initial_width = initial_geometry.width_mm
    initial_height = initial_geometry.height_mm

    if type_id in {91, 93, 94}:
        if final_length_input_mm is None:
            raise UpsettingMathError("Upsetting types 91/93/94 require final_length_input_mm")
        final_length = min(initial_length, float(final_length_input_mm))
        penetration = max(0.0, initial_length - final_length)
    elif type_id == 92:
        if stroke_mm is None:
            raise UpsettingMathError("Tail flattening type 92 requires stroke_mm")
        penetration = max(0.0, float(stroke_mm))
        final_length = max(0.0, initial_length - penetration)
    else:
        projections = _tail_chamfering_projections(
            billet_length_along_axis=initial_length,
            billet_height=initial_height,
            billet_width=initial_width,
            relative_chamfer_leg_orthogonal_to_billet_axis=1.0 / 3.0,
        )
        operation_specific_parameters["projections"] = projections
        penetration = max(
            0.0,
            0.5
            * (
                projections["height_to_length_projection"]["axial_virtual_penetration"]
                + projections["width_to_length_projection"]["axial_virtual_penetration"]
            ),
        )
        final_length = max(0.0, initial_length - penetration)

    relative_deformation_pct = (
        0.0 if initial_length <= 0.0 else max(0.0, (1.0 - final_length / initial_length) * 100.0)
    )

    feed_first_mm, feed_middle_mm, feed_last_mm = _upsetting_feeds(
        type_id=type_id,
        billet_width_mm=initial_height,
        top_die=top_die,
        bottom_die=bottom_die,
    )
    num_of_bites = _num_of_bites(
        type_id=type_id,
        billet_width_mm=initial_height,
        feed_first_mm=feed_first_mm,
        feed_middle_mm=feed_middle_mm,
    )

    initial_width_of_contact_mm = initial_width
    initial_length_of_contact_mm = _initial_length_of_contact(
        type_id=type_id,
        billet_width_mm=initial_height,
        penetration_mm=penetration,
        feed_first_mm=feed_first_mm,
        top_die=top_die,
        bottom_die=bottom_die,
    )

    strain_length = math.log(final_length / initial_length) if final_length > 0.0 else 0.0
    _, strain_height = _strain_length_based_on_contact_shape(
        initial_width_of_contact_mm,
        initial_length_of_contact_mm,
        initial_width,
        initial_height,
        strain_length,
    )
    strain_width = -strain_length - strain_height

    final_geometry = scale_generated_geometry(
        initial_geometry,
        width_scale=math.exp(strain_width),
        height_scale=math.exp(strain_height),
        length_scale=math.exp(strain_length),
    )

    final_length_of_contact_mm = _final_length_of_contact(
        type_id=type_id,
        billet_width_mm=initial_height,
        penetration_mm=penetration,
        initial_length_of_contact_mm=initial_length_of_contact_mm,
        top_die=top_die,
        bottom_die=bottom_die,
    )
    final_width_of_contact_mm = final_geometry.width_mm

    actual_speed_mm_per_s = min(speed_mm_per_s, press_mode.working_speed_mm_per_s)

    open_die_height_max_before_working_stroke_mm = _open_die_height_max_before_working_stroke(
        type_id=type_id,
        initial_length_mm=initial_length,
        projections=operation_specific_parameters.get("projections"),
    )
    open_die_height_min_after_working_stroke_mm = _open_die_height_min_after_working_stroke(
        type_id=type_id,
        final_length_mm=final_length,
        projections=operation_specific_parameters.get("projections"),
    )
    working_stroke_mm = _working_stroke(
        type_id=type_id,
        penetration_mm=penetration,
        projections=operation_specific_parameters.get("projections"),
    )
    working_approaching_stroke_mm = press_mode.approaching_distance_mm
    idle_stroke_mm = _idle_stroke(
        press_mode=press_mode,
        top_die=top_die,
        bottom_die=bottom_die,
        open_die_height_max_before_working_stroke_mm=open_die_height_max_before_working_stroke_mm,
        working_approaching_stroke_mm=working_approaching_stroke_mm,
    )
    back_stroke_mm = working_stroke_mm + working_approaching_stroke_mm + idle_stroke_mm

    time_between_bites_seconds = idle_stroke_mm / press_mode.idle_speed_mm_per_s + back_stroke_mm / press_mode.back_speed_mm_per_s
    time_bite_working_seconds = working_stroke_mm / actual_speed_mm_per_s
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
    elongation_increment = (
        max(final_geometry.length_mm, initial_length) / min(final_geometry.length_mm, initial_length)
        if min(final_geometry.length_mm, initial_length) > 0.0
        else 1.0
    )
    accumulated_strain_increment = _strain_accumulated_increment(
        strain_length=strain_length,
        strain_height=strain_height,
        strain_width=strain_width,
    )

    metrics: dict[str, Any] = {
        "angle_deg": angle_deg,
        "press_mode_id": press_mode.press_mode_id,
        "top_die_id": top_die.die_id,
        "bottom_die_id": bottom_die.die_id,
        "penetration_mm": penetration,
        "relative_deformation_pct": relative_deformation_pct,
        "feed_first_mm": feed_first_mm,
        "feed_middle_mm": feed_middle_mm,
        "feed_last_mm": feed_last_mm,
        "num_of_bites": num_of_bites,
        "speed_mm_per_s": actual_speed_mm_per_s,
        "initial_length_of_contact_mm": initial_length_of_contact_mm,
        "initial_width_of_contact_mm": initial_width_of_contact_mm,
        "final_length_of_contact_mm": final_length_of_contact_mm,
        "final_width_of_contact_mm": final_width_of_contact_mm,
        "strain_length": strain_length,
        "strain_height": strain_height,
        "strain_width": strain_width,
        "initial_cross_section_area_mm2": initial_geometry.cross_section_area_mm2,
        "final_cross_section_area_mm2": final_geometry.cross_section_area_mm2,
        "equivalent_diameter_mm": final_geometry.equivalent_diameter_mm,
        "initial_surface_area_mm2": initial_surface_area_mm2,
        "final_surface_area_mm2": final_surface_area_mm2,
        "initial_height_to_width_ratio": initial_height / initial_width if initial_width else None,
        "final_height_to_width_ratio": final_geometry.height_mm / final_geometry.width_mm if final_geometry.width_mm else None,
        "volume_initial_mm3": initial_geometry.volume_mm3,
        "volume_final_mm3": final_geometry.volume_mm3,
        "time_between_bites_seconds": time_between_bites_seconds,
        "manipulator_movement_time_seconds": manipulator_movement_time_seconds,
        "time_bite_working_seconds": time_bite_working_seconds,
        "cycle_time_seconds": cycle_time_seconds,
        "total_time_minutes": total_time_seconds / 60.0,
        "open_die_height_max_before_working_stroke_mm": open_die_height_max_before_working_stroke_mm,
        "open_die_height_min_after_working_stroke_mm": open_die_height_min_after_working_stroke_mm,
        "working_stroke_mm": working_stroke_mm,
        "working_approaching_stroke_mm": working_approaching_stroke_mm,
        "idle_stroke_mm": idle_stroke_mm,
        "back_stroke_mm": back_stroke_mm,
        "open_die_height_before_idle_stroke_mm": open_die_height_max_before_working_stroke_mm + working_approaching_stroke_mm + idle_stroke_mm,
        "elongation_increment": elongation_increment,
        "strain_accumulated_increment": accumulated_strain_increment,
        "mesh_elements": mesh_elements,
    }

    return UpsettingComputationResult(
        final_geometry=final_geometry,
        metrics=metrics,
        operation_specific_parameters=operation_specific_parameters,
        total_time_seconds=total_time_seconds,
        time_before_operation_seconds=time_before_pass,
        simulation_expected_duration_days=None,
    )


def _surface_area_mm2(geometry: GeneratedGeometry) -> float:
    return 2.0 * geometry.cross_section_area_mm2 + outline_perimeter_mm(geometry.cross_section_outline) * geometry.length_mm


def _first_non_zero(*values: float) -> float:
    for value in values:
        if value > 0.0:
            return value
    return 0.0


def _die_straight_length(top_die: DieDimensions, bottom_die: DieDimensions) -> float:
    return min(top_die.straight_length_mm, bottom_die.straight_length_mm)


def _max_working_length_of_dies(top_die: DieDimensions, bottom_die: DieDimensions) -> float:
    def working_length(die: DieDimensions) -> float:
        return die.straight_length_mm + 2.0 * 0.525 * die.edge_radius_mm

    return min(working_length(top_die), working_length(bottom_die))


def _edge_radius_of_shortest_die(top_die: DieDimensions, bottom_die: DieDimensions) -> tuple[float, int | None]:
    top_length = top_die.straight_length_mm + 2.0 * top_die.edge_radius_mm
    bottom_length = bottom_die.straight_length_mm + 2.0 * bottom_die.edge_radius_mm
    if top_length <= bottom_length:
        return top_die.edge_radius_mm, top_die.die_id
    return bottom_die.edge_radius_mm, bottom_die.die_id


def _actual_working_length_of_dies(
    one_side_penetration_mm: float,
    top_die: DieDimensions,
    bottom_die: DieDimensions,
) -> float:
    radius, die_id = _edge_radius_of_shortest_die(top_die, bottom_die)
    if one_side_penetration_mm >= radius:
        radius_length = radius
    else:
        radius_length = math.sqrt(one_side_penetration_mm * (2.0 * radius - one_side_penetration_mm))
    straight_length = top_die.straight_length_mm if top_die.die_id == die_id else bottom_die.straight_length_mm
    return straight_length + 2.0 * radius_length


def _upsetting_feeds(
    *,
    type_id: int,
    billet_width_mm: float,
    top_die: DieDimensions,
    bottom_die: DieDimensions,
) -> tuple[float, float, float]:
    min_die_working_length = _max_working_length_of_dies(top_die, bottom_die)
    half_die_length = 0.5 * min_die_working_length
    first_feed_till_billet_center = 0.5 * billet_width_mm + 0.5 * min_die_working_length

    if type_id == 93:
        return (first_feed_till_billet_center, 0.0, 0.0)
    if type_id == 91:
        if billet_width_mm >= min_die_working_length:
            return (first_feed_till_billet_center, half_die_length, min_die_working_length)
        return (first_feed_till_billet_center, 0.0, 0.0)
    if type_id == 94:
        return (first_feed_till_billet_center, half_die_length, min_die_working_length)
    if type_id == 92:
        average_feed = 200.0
        average_num_of_bites = billet_width_mm / average_feed
        num_of_bites = max(2, round(average_num_of_bites))
        feed = billet_width_mm / num_of_bites
        return (feed, 0.0, 0.0)
    if type_id == 100:
        if billet_width_mm >= min_die_working_length:
            return (first_feed_till_billet_center, half_die_length, min_die_working_length)
        return (first_feed_till_billet_center, 0.0, 0.0)
    raise UpsettingMathError(f"Unsupported upsetting type_id={type_id}")


def _num_of_bites(
    *,
    type_id: int,
    billet_width_mm: float,
    feed_first_mm: float,
    feed_middle_mm: float,
) -> int:
    if type_id == 93:
        return 1
    if type_id == 91:
        return 3 if feed_middle_mm > 0.0 else 1
    if type_id == 94:
        return 3
    if type_id == 92:
        return max(1, round(billet_width_mm / feed_first_mm))
    if type_id == 100:
        return 8 if feed_middle_mm > 0.0 else 4
    raise UpsettingMathError(f"Unsupported upsetting type_id={type_id}")


def _initial_length_of_contact(
    *,
    type_id: int,
    billet_width_mm: float,
    penetration_mm: float,
    feed_first_mm: float,
    top_die: DieDimensions,
    bottom_die: DieDimensions,
) -> float:
    if type_id in {91, 93, 94}:
        return min(_die_straight_length(top_die, bottom_die), billet_width_mm)
    if type_id == 92:
        radius, _ = _edge_radius_of_shortest_die(top_die, bottom_die)
        half_penetration = penetration_mm / 2.0
        radius_y = half_penetration / 2.0
        radius_x = radius if radius_y >= radius else math.sqrt(radius_y * (2.0 * radius - radius_y))
        return feed_first_mm - radius_x
    if type_id == 100:
        return 1.0
    raise UpsettingMathError(f"Unsupported upsetting type_id={type_id}")


def _final_length_of_contact(
    *,
    type_id: int,
    billet_width_mm: float,
    penetration_mm: float,
    initial_length_of_contact_mm: float,
    top_die: DieDimensions,
    bottom_die: DieDimensions,
) -> float:
    one_side_penetration = penetration_mm / 2.0
    if type_id in {91, 93, 94}:
        return min(_actual_working_length_of_dies(one_side_penetration, top_die, bottom_die), billet_width_mm)
    if type_id == 92:
        radius, _ = _edge_radius_of_shortest_die(top_die, bottom_die)
        radius_impression_length = (
            radius
            if one_side_penetration >= radius
            else math.sqrt(one_side_penetration * (2.0 * radius - one_side_penetration))
        )
        return initial_length_of_contact_mm + radius_impression_length
    if type_id == 100:
        return 1.0
    raise UpsettingMathError(f"Unsupported upsetting type_id={type_id}")


def _strain_length_based_on_contact_shape(
    contact_w_mm: float,
    contact_l_mm: float,
    initial_width_mm: float,
    initial_height_mm: float,
    strain_vertical: float,
) -> tuple[float, float]:
    contact_area_actual = contact_l_mm * contact_w_mm
    contact_area = max(0.1, contact_area_actual)
    contact_size_of_equiv_square = math.sqrt(contact_area)
    contact_area_shape_factor_with_sign = contact_w_mm / contact_size_of_equiv_square - 1.0
    elongation_coef_in_manip_axis = 0.5 + math.atan(contact_area_shape_factor_with_sign) / math.pi
    strain_horizontal_in_manip_axis = -1.0 * elongation_coef_in_manip_axis * strain_vertical
    return elongation_coef_in_manip_axis, strain_horizontal_in_manip_axis


def _tail_chamfering_projection(
    billet_length_along_axis: float,
    billet_width_orthogonal_to_axis: float,
    relative_chamfer_leg_orthogonal_to_billet_axis: float,
) -> dict[str, float]:
    length_axis = billet_length_along_axis
    width_axis = billet_width_orthogonal_to_axis
    factor = relative_chamfer_leg_orthogonal_to_billet_axis
    chamfer_leg_orthogonal = factor * width_axis
    chamfer_leg_along = 0.5 * (
        length_axis
        - math.sqrt(length_axis ** 2 - 4 * factor * width_axis ** 2 + 4 * (factor * width_axis) ** 2)
    )
    axis_inclination_angle_rad = math.atan(chamfer_leg_along / factor / width_axis)
    initial_vertical_projection = math.cos(axis_inclination_angle_rad) * length_axis + math.sin(axis_inclination_angle_rad) * width_axis
    chamfer_hypotenuse = chamfer_leg_along / math.sin(axis_inclination_angle_rad)
    chamfer_vertical_projection = chamfer_leg_along * chamfer_leg_orthogonal / chamfer_hypotenuse
    final_vertical_projection = initial_vertical_projection - 2.0 * chamfer_vertical_projection
    initial_horizontal_projection = math.sin(axis_inclination_angle_rad) * length_axis + math.cos(axis_inclination_angle_rad) * width_axis
    p_value = 4 * factor ** 3 - 6 * factor ** 2 + 3 * factor - 1
    axial_relative_one_side_penetration = 1 - (math.cbrt(p_value) + 1) / (2 * factor)
    axial_virtual_penetration = 2 * chamfer_leg_along * axial_relative_one_side_penetration
    return {
        "axis_inclination_angle": axis_inclination_angle_rad,
        "chamfer_leg_along_billet_axis": chamfer_leg_along,
        "chamfer_leg_orthogonal_to_billet_axis": chamfer_leg_orthogonal,
        "chamfer_hypotenuse": chamfer_hypotenuse,
        "chamfer_vertical_projection": chamfer_vertical_projection,
        "initial_billet_vertical_projection": initial_vertical_projection,
        "initial_billet_horizontal_projection": initial_horizontal_projection,
        "final_billet_vertical_projection": final_vertical_projection,
        "axial_virtual_penetration": axial_virtual_penetration,
    }


def _tail_chamfering_projections(
    *,
    billet_length_along_axis: float,
    billet_height: float,
    billet_width: float,
    relative_chamfer_leg_orthogonal_to_billet_axis: float,
) -> dict[str, dict[str, float]]:
    return {
        "height_to_length_projection": _tail_chamfering_projection(
            billet_length_along_axis,
            billet_height,
            relative_chamfer_leg_orthogonal_to_billet_axis,
        ),
        "width_to_length_projection": _tail_chamfering_projection(
            billet_length_along_axis,
            billet_width,
            relative_chamfer_leg_orthogonal_to_billet_axis,
        ),
    }


def _open_die_height_max_before_working_stroke(
    *,
    type_id: int,
    initial_length_mm: float,
    projections: dict[str, dict[str, float]] | None,
) -> float:
    if type_id == 100 and projections is not None:
        return max(
            projections["height_to_length_projection"]["initial_billet_vertical_projection"],
            projections["width_to_length_projection"]["initial_billet_vertical_projection"],
        )
    return initial_length_mm


def _open_die_height_min_after_working_stroke(
    *,
    type_id: int,
    final_length_mm: float,
    projections: dict[str, dict[str, float]] | None,
) -> float:
    if type_id == 100 and projections is not None:
        return min(
            projections["height_to_length_projection"]["final_billet_vertical_projection"],
            projections["width_to_length_projection"]["final_billet_vertical_projection"],
        )
    return final_length_mm


def _working_stroke(
    *,
    type_id: int,
    penetration_mm: float,
    projections: dict[str, dict[str, float]] | None,
) -> float:
    if type_id == 100 and projections is not None:
        penetration_1 = 2.0 * projections["height_to_length_projection"]["chamfer_vertical_projection"]
        penetration_2 = 2.0 * projections["width_to_length_projection"]["chamfer_vertical_projection"]
        return (penetration_1 + penetration_2) / 2.0
    return penetration_mm


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
        raise UpsettingMathError("Press open height must exceed total die height")
    relative_required_open_die_height = open_die_height_max_before_working_stroke_mm / max_open_height
    target_idle_stroke = (
        press_mode.min_idle_stroke_mm
        + (press_mode.max_idle_stroke_mm - press_mode.min_idle_stroke_mm) * relative_required_open_die_height
    )
    available_idle_stroke = max_open_height - open_die_height_max_before_working_stroke_mm - working_approaching_stroke_mm
    return max(0.0, min(target_idle_stroke, available_idle_stroke))


def _billet_rotation_time(angle_deg: float, *, is_full_die: bool = False) -> float:
    if angle_deg == 0.0:
        return 0.0
    rotation_speed = 0.25 if is_full_die else 1.5
    rotation_dwell = 1.0
    return angle_deg / 360.0 * rotation_speed + rotation_dwell


def _strain_accumulated_increment(
    *,
    strain_length: float,
    strain_height: float,
    strain_width: float,
) -> float:
    ehl = (strain_height - strain_length) ** 2
    ewh = (strain_width - strain_height) ** 2
    elw = (strain_length - strain_width) ** 2
    return math.sqrt(2.0) / 3.0 * math.sqrt(elw + ewh + ehl)
