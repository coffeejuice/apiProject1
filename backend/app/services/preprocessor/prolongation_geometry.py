"""Shapely-backed 2D die/polygon helpers for prolongation preprocessing."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from typing import Any

from .geometry import GeneratedGeometry, Point2D
from .upsetting import DieDimensions

try:  # Shapely is an optional runtime dependency for high-fidelity geometry.
    from shapely.affinity import rotate, scale, translate
    from shapely.geometry import GeometryCollection, LineString, Point, Polygon
    from shapely.ops import split, unary_union
except ModuleNotFoundError:  # pragma: no cover - exercised only when dependency is absent.
    rotate = scale = translate = None  # type: ignore[assignment]
    GeometryCollection = LineString = Point = Polygon = None  # type: ignore[assignment]
    split = unary_union = None  # type: ignore[assignment]


class ProlongationGeometryError(ValueError):
    """Raised when Shapely prolongation geometry cannot be produced."""


@dataclass(frozen=True, slots=True)
class DieGapResult:
    """Initial/final die gap metadata and positioned die polygons."""

    gap_mm: float
    die_polygons: tuple[Any, Any]


@dataclass(frozen=True, slots=True)
class ProlongationGeometryResult:
    """High-fidelity 2D polygon result for one prolongation operation."""

    final_geometry: GeneratedGeometry
    initial_dies_gap_mm: float | None
    final_dies_gap_mm: float | None
    final_width_of_contact_mm: float | None
    area_error_percent: float
    used_die_trimming: bool


def shapely_available() -> bool:
    """Return whether Shapely is importable in the current environment."""

    return Polygon is not None


def geometry_to_polygon(geometry: GeneratedGeometry, *, angle_deg: float = 0.0) -> Any:
    """Convert `GeneratedGeometry` outline into a centered Shapely polygon."""

    _require_shapely()
    polygon = Polygon(geometry.cross_section_outline)
    polygon = _normalize_polygon(polygon)
    if angle_deg:
        polygon = rotate(polygon, angle_deg, origin=(0.0, 0.0))
        polygon = _normalize_polygon(polygon)
    centroid = polygon.centroid
    return translate(polygon, xoff=-centroid.x, yoff=-centroid.y)


def polygon_to_geometry(
    polygon: Any,
    *,
    source_geometry: GeneratedGeometry,
    shape: str | None = None,
    parameters_update: dict[str, float] | None = None,
) -> GeneratedGeometry:
    """Convert a Shapely polygon back into `GeneratedGeometry` preserving billet volume."""

    _require_shapely()
    polygon = _normalize_polygon(polygon)
    area = float(polygon.area)
    if area <= 0.0:
        raise ProlongationGeometryError("Final polygon area is not positive")
    min_x, min_y, max_x, max_y = polygon.bounds
    width = float(max_x - min_x)
    height = float(max_y - min_y)
    length = source_geometry.volume_mm3 / area
    equivalent_diameter = math.sqrt(4.0 * area / math.pi)
    parameters = dict(source_geometry.parameters)
    if parameters_update:
        parameters.update(parameters_update)
    outline = _polygon_outline(polygon)
    return GeneratedGeometry(
        type_id=source_geometry.type_id,
        shape=shape or source_geometry.shape,
        parameters=parameters,
        volume_mm3=source_geometry.volume_mm3,
        cross_section_area_mm2=area,
        equivalent_diameter_mm=equivalent_diameter,
        width_mm=width,
        height_mm=height,
        length_mm=length,
        cross_section_outline=outline,
        parameters_json=json.dumps(parameters, sort_keys=True),
    )


def build_die_cross_section_polygons(
    *,
    top_die: DieDimensions,
    bottom_die: DieDimensions,
) -> tuple[Any, Any]:
    """Build simplified die cross-section polygons from library die dimensions."""

    _require_shapely()
    return (
        _build_single_die_polygon(top_die, is_top=True),
        _build_single_die_polygon(bottom_die, is_top=False),
    )


def gap_between_dies(billet_polygon: Any, die_polygons: tuple[Any, Any]) -> DieGapResult:
    """Position top/bottom dies against a billet polygon and return the die gap."""

    _require_shapely()
    top_die, bottom_die = die_polygons
    billet_bounds = billet_polygon.bounds

    top_die = translate(top_die, yoff=billet_bounds[3] - top_die.bounds[1])
    bottom_die = translate(bottom_die, yoff=billet_bounds[1] - bottom_die.bounds[3])

    top_die = _position_polygon_till_contact(top_die, billet_polygon, direction="down")
    bottom_die = _position_polygon_till_contact(bottom_die, billet_polygon, direction="up")

    gap = float(top_die.bounds[1] - bottom_die.bounds[3])
    return DieGapResult(gap_mm=gap, die_polygons=(top_die, bottom_die))


def final_dies_polygons(input_polygons: tuple[Any, Any], penetration_mm: float) -> tuple[Any, Any]:
    """Move positioned dies by half of the total penetration."""

    _require_shapely()
    return (
        translate(input_polygons[0], yoff=-penetration_mm / 2.0),
        translate(input_polygons[1], yoff=penetration_mm / 2.0),
    )


def apply_die_trimming_geometry(
    *,
    initial_geometry: GeneratedGeometry,
    final_height_mm: float,
    penetration_mm: float,
    top_die: DieDimensions,
    bottom_die: DieDimensions,
    angle_deg: float = 0.0,
    final_length_of_contact_mm: float | None = None,
    strain_height: float | None = None,
) -> ProlongationGeometryResult:
    """Apply the old Shapely-style die/polygon trimming path for prolongation."""

    _require_shapely()
    if final_height_mm <= 0.0:
        raise ProlongationGeometryError("final_height_mm must be positive")

    input_polygon = geometry_to_polygon(initial_geometry, angle_deg=angle_deg)
    input_height = _height_of_polygon(input_polygon)
    input_width = _width_of_polygon(input_polygon)
    if input_height <= 0.0:
        raise ProlongationGeometryError("Initial polygon height is not positive")

    die_polygons = build_die_cross_section_polygons(top_die=top_die, bottom_die=bottom_die)
    initial_gap = gap_between_dies(input_polygon, die_polygons)
    final_die_polygons = final_dies_polygons(initial_gap.die_polygons, penetration_mm)
    final_gap = float(initial_gap.gap_mm - penetration_mm)

    try:
        y_scale_factor = _polygon_y_scale_factor(
            input_polygon=input_polygon,
            die_polygons=final_die_polygons,
            initial_width_mm=input_width,
            initial_height_mm=input_height,
            penetration_mm=penetration_mm,
        )
    except ProlongationGeometryError:
        y_scale_factor = final_height_mm / input_height
    y_scaled_polygon = _normalize_polygon(scale(input_polygon, xfact=1.0, yfact=y_scale_factor, origin=(0.0, 0.0)))
    fallback_polygon = _normalize_polygon(scale(input_polygon, xfact=1.0, yfact=final_height_mm / input_height, origin=(0.0, 0.0)))

    used_die_trimming = False
    try:
        final_polygon, final_width_of_contact, area_error_percent = _validated_trim_middle(
            y_scaled_polygon,
            final_die_polygons,
            final_height_mm=final_height_mm,
            final_length_of_contact_mm=final_length_of_contact_mm,
            strain_height=strain_height,
            initial_width_mm=input_width,
            initial_height_mm=input_height,
            initial_area_mm2=input_polygon.area,
        )
        used_die_trimming = True
    except Exception:
        try:
            final_polygon, final_width_of_contact, area_error_percent = _validated_trim_middle(
                y_scaled_polygon,
                final_die_polygons,
                final_height_mm=final_height_mm,
                final_length_of_contact_mm=None,
                strain_height=None,
                initial_width_mm=input_width,
                initial_height_mm=input_height,
                initial_area_mm2=input_polygon.area,
            )
            used_die_trimming = True
        except Exception:
            final_polygon = fallback_polygon
            final_width_of_contact = _width_of_polygon(fallback_polygon)
            area_error_percent = 0.0

    final_geometry = polygon_to_geometry(
        final_polygon,
        source_geometry=initial_geometry,
        parameters_update={"height": float(final_height_mm)},
    )
    return ProlongationGeometryResult(
        final_geometry=final_geometry,
        initial_dies_gap_mm=float(initial_gap.gap_mm),
        final_dies_gap_mm=final_gap,
        final_width_of_contact_mm=float(final_width_of_contact),
        area_error_percent=float(area_error_percent),
        used_die_trimming=used_die_trimming,
    )


def build_spiral_round_geometry(
    *,
    initial_geometry: GeneratedGeometry,
    final_diameter_mm: float,
    segments: int = 96,
) -> ProlongationGeometryResult:
    """Build a round final cross-section for spiral prolongation through Shapely."""

    _require_shapely()
    if final_diameter_mm <= 0.0:
        raise ProlongationGeometryError("final_diameter_mm must be positive")
    final_polygon = Point(0.0, 0.0).buffer(final_diameter_mm / 2.0, resolution=max(8, segments // 4))
    final_geometry = polygon_to_geometry(
        final_polygon,
        source_geometry=initial_geometry,
        shape="round",
        parameters_update={"diameter": float(final_diameter_mm)},
    )
    return ProlongationGeometryResult(
        final_geometry=final_geometry,
        initial_dies_gap_mm=None,
        final_dies_gap_mm=None,
        final_width_of_contact_mm=final_diameter_mm / 2.0,
        area_error_percent=0.0,
        used_die_trimming=True,
    )


def _validated_trim_middle(
    polygon: Any,
    die_polygons: tuple[Any, Any],
    *,
    final_height_mm: float,
    final_length_of_contact_mm: float | None,
    strain_height: float | None,
    initial_width_mm: float,
    initial_height_mm: float,
    initial_area_mm2: float,
) -> tuple[Any, float, float]:
    final_polygon, final_width_of_contact, expected_area = _trim_middle_and_preserve_area(
        polygon,
        die_polygons,
        final_height_mm=final_height_mm,
        final_length_of_contact_mm=final_length_of_contact_mm,
        strain_height=strain_height,
        initial_width_mm=initial_width_mm,
        initial_height_mm=initial_height_mm,
        initial_area_mm2=initial_area_mm2,
    )
    area_error_percent = _area_error_percent(final_polygon.area, expected_area)
    height_error_percent = _dimension_error_percent(_height_of_polygon(final_polygon), final_height_mm)
    if area_error_percent > 2.0:
        raise ProlongationGeometryError(f"Die-trimmed polygon area error is {area_error_percent:.3f}%")
    if height_error_percent > 2.0:
        raise ProlongationGeometryError(f"Die-trimmed polygon height error is {height_error_percent:.3f}%")
    return final_polygon, final_width_of_contact, area_error_percent


def _trim_middle_and_preserve_area(
    polygon: Any,
    die_polygons: tuple[Any, Any],
    *,
    final_height_mm: float,
    final_length_of_contact_mm: float | None,
    strain_height: float | None,
    initial_width_mm: float,
    initial_height_mm: float,
    initial_area_mm2: float,
) -> tuple[Any, float, float]:
    area_except_middle, split_lines, split_polygons, gaps = _trim_middle_return_residual_area(
        polygon,
        die_polygons[0],
        die_polygons[1],
        final_height_mm,
    )
    width_of_contact = _optimized_width_of_contact(
        area_except_middle=area_except_middle,
        final_height_mm=final_height_mm,
        width_initial_guess=gaps[0],
        polygon_width_mm=_width_of_polygon(polygon),
        polygon_area_mm2=polygon.area,
        final_length_of_contact_mm=final_length_of_contact_mm,
        strain_height=strain_height,
        initial_width_mm=initial_width_mm,
        initial_height_mm=initial_height_mm,
        initial_area_mm2=initial_area_mm2,
    )
    min_width = max(0.001, 0.01 * _width_of_polygon(polygon))
    max_width = max(min_width, 1.25 * _width_of_polygon(polygon))
    width_of_contact = max(min_width, min(max_width, width_of_contact))
    expected_area = area_except_middle + final_height_mm * width_of_contact

    boundary_list = _translate_geoms_increase_gap(gaps[0], split_lines)
    polygon_list = _translate_geoms_increase_gap(gaps[0], split_polygons)
    middle_polygon = _middle_polygon_fill_gap(boundary_list, width_of_contact)
    side_polygons = _translate_polygons_after_optimization(polygon_list, width_of_contact)
    pieces = [*side_polygons[0], middle_polygon, *side_polygons[1]]
    output = _union_polygons(pieces)
    if output.is_empty:
        raise ProlongationGeometryError("Die-trimmed polygon is empty")
    return output, width_of_contact, expected_area


def _polygon_y_scale_factor(
    *,
    input_polygon: Any,
    die_polygons: tuple[Any, Any],
    initial_width_mm: float,
    initial_height_mm: float,
    penetration_mm: float,
) -> float:
    top_points, bottom_points = _intersection_with_dies(input_polygon, die_polygons[0], die_polygons[1])
    gaps = _gap_width_after_split(top_points, bottom_points)
    return _upsetting_like_vertical_scale_factor(
        input_width_mm=gaps[1],
        initial_width_mm=initial_width_mm,
        initial_height_mm=initial_height_mm,
        penetration_mm=penetration_mm,
    )


def _upsetting_like_vertical_scale_factor(
    *,
    input_width_mm: float,
    initial_width_mm: float,
    initial_height_mm: float,
    penetration_mm: float,
) -> float:
    if min(input_width_mm, initial_width_mm, initial_height_mm) <= 0.0:
        raise ProlongationGeometryError("Cannot calculate vertical scale factor from non-positive dimensions")
    relative_contact_width = input_width_mm / initial_width_mm
    upset_penetration = penetration_mm * relative_contact_width * 0.5
    upset_height = initial_height_mm - upset_penetration
    scale_factor = upset_height / initial_height_mm
    if not 0.0 < scale_factor <= 1.0:
        raise ProlongationGeometryError(f"Invalid vertical scale factor {scale_factor}")
    return float(scale_factor)


def _optimized_width_of_contact(
    *,
    area_except_middle: float,
    final_height_mm: float,
    width_initial_guess: float,
    polygon_width_mm: float,
    polygon_area_mm2: float,
    final_length_of_contact_mm: float | None,
    strain_height: float | None,
    initial_width_mm: float,
    initial_height_mm: float,
    initial_area_mm2: float,
) -> float:
    if (
        final_length_of_contact_mm is None
        or strain_height is None
        or final_length_of_contact_mm <= 0.0
        or min(initial_width_mm, initial_height_mm, initial_area_mm2) <= 0.0
    ):
        return _area_preserving_width_of_contact(
            area_except_middle=area_except_middle,
            final_height_mm=final_height_mm,
            target_area_mm2=polygon_area_mm2,
        )

    rough_width = _rough_width_of_contact(
        width_initial_guess=width_initial_guess,
        area_except_middle=area_except_middle,
        final_length_of_contact_mm=final_length_of_contact_mm,
        strain_height=strain_height,
        initial_width_mm=initial_width_mm,
        initial_height_mm=initial_height_mm,
        final_height_mm=final_height_mm,
        initial_area_mm2=initial_area_mm2,
    )
    scale_width = max(rough_width, width_initial_guess, polygon_width_mm, 1.0)
    lower = max(0.001, 0.02 * scale_width)
    upper = max(lower * 10.0, 3.0 * scale_width)
    return _minimize_scalar_bounded(
        lambda width: _strain_error(
            width_of_contact=width,
            area_except_middle=area_except_middle,
            length_of_contact=final_length_of_contact_mm,
            strain_height=strain_height,
            initial_width=initial_width_mm,
            initial_height=initial_height_mm,
            final_height=final_height_mm,
            initial_area=initial_area_mm2,
        ),
        lower,
        upper,
    )


def _area_preserving_width_of_contact(
    *,
    area_except_middle: float,
    final_height_mm: float,
    target_area_mm2: float,
) -> float:
    if final_height_mm <= 0.0:
        raise ProlongationGeometryError("Cannot calculate contact width with non-positive final height")
    return (target_area_mm2 - area_except_middle) / final_height_mm


def _rough_width_of_contact(
    *,
    width_initial_guess: float,
    area_except_middle: float,
    final_length_of_contact_mm: float,
    strain_height: float,
    initial_width_mm: float,
    initial_height_mm: float,
    final_height_mm: float,
    initial_area_mm2: float,
) -> float:
    _, strain_length_contact = _strain_length_based_on_contact_shape(
        width_initial_guess,
        final_length_of_contact_mm,
        initial_width_mm,
        initial_height_mm,
        strain_height,
    )
    final_cross_section_area_guess = initial_area_mm2 / math.exp(strain_length_contact)
    rough_width = (final_cross_section_area_guess - area_except_middle) / final_height_mm
    if math.isfinite(rough_width) and rough_width > 0.0:
        return float(rough_width)
    return max(width_initial_guess, 0.001)


def _strain_error(
    *,
    width_of_contact: float,
    area_except_middle: float,
    length_of_contact: float,
    strain_height: float,
    initial_width: float,
    initial_height: float,
    final_height: float,
    initial_area: float,
) -> float:
    try:
        _, strain_length_contact = _strain_length_based_on_contact_shape(
            width_of_contact,
            length_of_contact,
            initial_width,
            initial_height,
            strain_height,
        )
        area_actual = area_except_middle + final_height * width_of_contact
        if area_actual <= 0.0:
            return 1e6
        strain_length_based_on_area = math.log(initial_area / area_actual)
        if abs(strain_length_based_on_area) <= 1e-12:
            return 1e6
        return abs(1.0 - strain_length_contact / strain_length_based_on_area)
    except Exception:
        return 1e6


def _strain_length_based_on_contact_shape(
    contact_width: float,
    contact_length: float,
    initial_width: float,
    initial_height: float,
    strain_vertical: float,
) -> tuple[float, float]:
    if min(contact_width, contact_length, initial_width, initial_height) <= 0.0:
        raise ProlongationGeometryError("Contact-shape strain inputs must be positive")
    contact_area = max(0.1, contact_length * contact_width)
    contact_size_of_equivalent_square = math.sqrt(contact_area)
    contact_area_shape_factor = contact_width / contact_size_of_equivalent_square - 1.0
    elongation_coefficient = 0.5 + math.atan(contact_area_shape_factor) / math.pi
    strain_horizontal_in_manipulator_axis = -elongation_coefficient * strain_vertical
    return float(elongation_coefficient), float(strain_horizontal_in_manipulator_axis)


def _minimize_scalar_bounded(function: Any, lower: float, upper: float, *, iterations: int = 80) -> float:
    if lower <= 0.0 or upper <= lower:
        raise ProlongationGeometryError("Invalid scalar minimization bounds")
    inv_phi = (math.sqrt(5.0) - 1.0) / 2.0
    inv_phi_squared = (3.0 - math.sqrt(5.0)) / 2.0
    x1 = lower + inv_phi_squared * (upper - lower)
    x2 = lower + inv_phi * (upper - lower)
    y1 = function(x1)
    y2 = function(x2)
    for _ in range(iterations):
        if y1 > y2:
            lower = x1
            x1 = x2
            y1 = y2
            x2 = lower + inv_phi * (upper - lower)
            y2 = function(x2)
        else:
            upper = x2
            x2 = x1
            y2 = y1
            x1 = lower + inv_phi_squared * (upper - lower)
            y1 = function(x1)
    return float((lower + upper) / 2.0)


def _area_error_percent(actual_area: float, expected_area: float) -> float:
    if expected_area <= 0.0:
        raise ProlongationGeometryError("Cannot calculate area error against non-positive expected area")
    return abs(1.0 - actual_area / expected_area) * 100.0


def _dimension_error_percent(actual_dimension: float, expected_dimension: float) -> float:
    if expected_dimension <= 0.0:
        raise ProlongationGeometryError("Cannot calculate dimension error against non-positive expected dimension")
    return abs(1.0 - actual_dimension / expected_dimension) * 100.0


def _trim_middle_return_residual_area(
    polygon: Any,
    top_die: Any,
    bottom_die: Any,
    final_height_mm: float,
) -> tuple[float, list[list[Any]], list[list[Any]], list[float]]:
    top_points, bottom_points = _intersection_with_dies(polygon, top_die, bottom_die)
    split_lines = _splitting_lines(top_points, bottom_points)
    split_polygons = [
        _split_polygon_by_line(polygon, split_lines[0][0], is_return_left=True),
        _split_polygon_by_line(polygon, split_lines[1][0], is_return_left=False),
    ]
    gaps = _gap_width_after_split(top_points, bottom_points)
    area_of_trapezoid = 0.5 * final_height_mm * (gaps[1] - gaps[0])
    area_except_middle = sum(sum(poly.area for poly in side) for side in split_polygons) + area_of_trapezoid
    return area_except_middle, split_lines, split_polygons, gaps


def _intersection_with_dies(polygon: Any, top_die: Any, bottom_die: Any) -> tuple[tuple[Any, Any], tuple[Any, Any]]:
    points_by_die = []
    for die in (top_die, bottom_die):
        intersection = die.exterior.intersection(polygon.exterior)
        points = _collect_points(intersection)
        if len(points) < 2:
            raise ProlongationGeometryError("Die must intersect polygon exterior in at least two points")
        points = sorted(points, key=lambda point: point.x)
        points_by_die.append((points[0], points[-1]))
    return points_by_die[0], points_by_die[1]


def _splitting_lines(top_points: tuple[Any, Any], bottom_points: tuple[Any, Any]) -> list[list[Any]]:
    return [
        [LineString((bottom_points[0], top_points[0]))],
        [LineString((bottom_points[1], top_points[1]))],
    ]


def _translate_geoms_increase_gap(gap: float, geom_list: list[list[Any]]) -> list[list[Any]]:
    factors = [1.0, -1.0]
    output: list[list[Any]] = []
    for side_index, side_list in enumerate(geom_list):
        side_output = []
        for geom in side_list:
            side_output.append(translate(geom, xoff=factors[side_index] * 0.5 * gap))
        output.append(side_output)
    return output


def _middle_polygon_fill_gap(boundary_list: list[list[Any]], width_of_contact: float) -> Any:
    shift_x = 0.5 * width_of_contact
    left_middle = translate(boundary_list[0][0], xoff=-shift_x)
    right_middle = translate(boundary_list[1][0], xoff=shift_x)
    left_points = sorted(left_middle.coords, key=lambda point: point[1])
    right_points = sorted(right_middle.coords, key=lambda point: point[1], reverse=True)
    return _normalize_polygon(Polygon((*left_points, *right_points)))


def _translate_polygons_after_optimization(polygon_list: list[list[Any]], width_of_contact: float) -> list[list[Any]]:
    factors = [-1.0, 1.0]
    output: list[list[Any]] = []
    for side_index, side_list in enumerate(polygon_list):
        side_output = []
        for polygon in side_list:
            side_output.append(translate(polygon, xoff=factors[side_index] * 0.5 * width_of_contact))
        output.append(side_output)
    return output


def _split_polygon_by_line(polygon: Any, line: Any, *, is_return_left: bool) -> list[Any]:
    extended_line = scale(line, xfact=2.0, yfact=2.0, origin=line.centroid)
    pieces = split(polygon, extended_line)
    selected = []
    area_limit = 1e-5 * polygon.area
    for piece in pieces.geoms:
        if piece.is_empty or piece.area <= area_limit:
            continue
        if _is_left(piece.centroid, line) == is_return_left:
            selected.append(piece)
    if not selected:
        raise ProlongationGeometryError("Polygon split produced no selected side pieces")
    return selected


def _gap_width_after_split(top_points: tuple[Any, Any], bottom_points: tuple[Any, Any]) -> list[float]:
    top_width = abs(top_points[0].x - top_points[1].x)
    bottom_width = abs(bottom_points[0].x - bottom_points[1].x)
    return [float(min(top_width, bottom_width)), float(max(top_width, bottom_width))]


def _is_left(point: Any, line: Any) -> bool:
    x1, y1, x2, y2 = line.bounds
    return (x2 - x1) * (point.y - y1) - (y2 - y1) * (point.x - x1) > 0.0


def _position_polygon_till_contact(moved_polygon: Any, reference_polygon: Any, *, direction: str) -> Any:
    dy = 5.0
    direction_coef = 1.0 if direction == "up" else -1.0
    while dy > 1e-2:
        while True:
            candidate = translate(moved_polygon, yoff=direction_coef * dy)
            if _is_intersection(candidate, reference_polygon):
                break
            moved_polygon = candidate
        dy *= 0.1
    return moved_polygon


def _is_intersection(moved_polygon: Any, reference_polygon: Any) -> bool:
    if not moved_polygon.intersects(reference_polygon):
        return False
    intersection_area = moved_polygon.intersection(reference_polygon).area
    return intersection_area >= 0.1 or intersection_area / reference_polygon.area >= 5e-7


def _build_single_die_polygon(die: DieDimensions, *, is_top: bool) -> Any:
    straight = max(float(die.straight_length_mm), 0.001)
    height = max(float(die.height_mm), 0.001)
    side_extension = max(float(die.edge_radius_mm), 0.001)
    if 0.0 < die.edge_angle_deg < 90.0:
        side_extension += height / math.tan(math.radians(die.edge_angle_deg))
    half_straight = straight / 2.0
    half_total = half_straight + side_extension
    if is_top:
        coords = [
            (-half_total, height),
            (half_total, height),
            (half_straight, 0.0),
            (-half_straight, 0.0),
        ]
    else:
        coords = [
            (-half_straight, 0.0),
            (half_straight, 0.0),
            (half_total, -height),
            (-half_total, -height),
        ]
    return _normalize_polygon(Polygon(coords))


def _union_polygons(polygons: list[Any]) -> Any:
    output = unary_union([polygon for polygon in polygons if polygon is not None and not polygon.is_empty])
    if isinstance(output, Polygon):
        return _normalize_polygon(output)
    if hasattr(output, "geoms"):
        polygon_parts = [geom for geom in output.geoms if isinstance(geom, Polygon)]
        if polygon_parts:
            return _normalize_polygon(max(polygon_parts, key=lambda item: item.area))
    raise ProlongationGeometryError("Cannot combine die-trimmed polygon pieces into one polygon")


def _collect_points(geometry: Any) -> list[Any]:
    if geometry.is_empty:
        return []
    if isinstance(geometry, Point):
        return [geometry]
    if isinstance(geometry, LineString):
        coords = list(geometry.coords)
        return [Point(coords[0]), Point(coords[-1])]
    if isinstance(geometry, GeometryCollection) or hasattr(geometry, "geoms"):
        points: list[Any] = []
        for part in geometry.geoms:
            points.extend(_collect_points(part))
        return points
    return []


def _polygon_outline(polygon: Any) -> tuple[Point2D, ...]:
    coords = list(polygon.exterior.coords)
    if len(coords) > 1 and coords[0] == coords[-1]:
        coords = coords[:-1]
    return tuple((float(x), float(y)) for x, y in coords)


def _normalize_polygon(polygon: Any) -> Any:
    if polygon.is_empty:
        raise ProlongationGeometryError("Polygon is empty")
    if not polygon.is_valid:
        polygon = polygon.buffer(0.0)
    if not isinstance(polygon, Polygon):
        if hasattr(polygon, "geoms"):
            polygon_parts = [geom for geom in polygon.geoms if isinstance(geom, Polygon)]
            if polygon_parts:
                polygon = max(polygon_parts, key=lambda item: item.area)
    if not isinstance(polygon, Polygon) or polygon.is_empty or polygon.area <= 0.0:
        raise ProlongationGeometryError("Cannot normalize polygon")
    return polygon


def _height_of_polygon(polygon: Any) -> float:
    return float(polygon.bounds[3] - polygon.bounds[1])


def _width_of_polygon(polygon: Any) -> float:
    return float(polygon.bounds[2] - polygon.bounds[0])


def _require_shapely() -> None:
    if not shapely_available():
        raise ProlongationGeometryError("Shapely is not installed")
