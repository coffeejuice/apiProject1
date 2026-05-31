"""Geometry helpers migrated from the legacy preprocessing service."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import math
from typing import Any, Mapping

from app.services.preprocessor.mesh_primitives import (
    extruded_polygon_surface_mesh,
    round_tail_chamfer_surface_mesh,
    round_tail_radius_surface_mesh,
)
from app.services.preprocessor.surface_mesh import SurfaceMesh, SurfaceMeshError

Point2D = tuple[float, float]
LOGGER = logging.getLogger(__name__)


class GeometryError(ValueError):
    """Raised when billet geometry input parameters are invalid."""

    def __init__(
        self,
        message: str,
        *,
        type_id: int | None = None,
        parameter: str | None = None,
        value: object | None = None,
        limits: Mapping[str, object] | None = None,
        details: Mapping[str, object] | None = None,
    ) -> None:
        self.message = message
        self.type_id = type_id
        self.parameter = parameter
        self.value = value
        self.limits = dict(limits or {})
        self.details = dict(details or {})
        super().__init__(message)

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "category": "geometry_validation",
            "message": self.message,
        }
        if self.type_id is not None:
            payload["type_id"] = self.type_id
        if self.parameter is not None:
            payload["parameter"] = self.parameter
        if self.value is not None:
            payload["value"] = self.value
        if self.limits:
            payload["limits"] = self.limits
        if self.details:
            payload["details"] = self.details
        return payload


@dataclass(frozen=True, slots=True)
class GeometryTypeDefinition:
    """Static metadata for one supported billet geometry type."""

    type_id: int
    shape: str
    parent_type_id: int
    labels: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GeneratedGeometry:
    """Computed billet geometry derived from one document operation output."""

    type_id: int
    shape: str
    parameters: dict[str, float]
    volume_mm3: float
    cross_section_area_mm2: float
    equivalent_diameter_mm: float
    width_mm: float
    height_mm: float
    length_mm: float
    cross_section_outline: tuple[Point2D, ...]
    parameters_json: str
    surface_mesh: SurfaceMesh | None = None


def outline_area_mm2(outline: tuple[Point2D, ...]) -> float:
    """Return polygon area via the shoelace formula."""

    if len(outline) < 3:
        return 0.0
    total = 0.0
    for index, point in enumerate(outline):
        next_point = outline[(index + 1) % len(outline)]
        total += point[0] * next_point[1] - next_point[0] * point[1]
    return abs(total) / 2.0


def outline_perimeter_mm(outline: tuple[Point2D, ...]) -> float:
    """Return the perimeter of a closed polygon outline."""

    if len(outline) < 2:
        return 0.0
    total = 0.0
    for index, point in enumerate(outline):
        next_point = outline[(index + 1) % len(outline)]
        total += math.dist(point, next_point)
    return total


def outline_bounds_mm(outline: tuple[Point2D, ...]) -> tuple[float, float, float, float]:
    """Return min_x, min_y, max_x, max_y for an outline."""

    if not outline:
        return (0.0, 0.0, 0.0, 0.0)
    xs = [point[0] for point in outline]
    ys = [point[1] for point in outline]
    return (min(xs), min(ys), max(xs), max(ys))


def scale_outline_mm(
    outline: tuple[Point2D, ...],
    *,
    width_scale: float = 1.0,
    height_scale: float = 1.0,
) -> tuple[Point2D, ...]:
    """Scale an outline around the origin along its local X/Y axes."""

    return tuple((point[0] * width_scale, point[1] * height_scale) for point in outline)


def horizontal_intersection_width_mm(outline: tuple[Point2D, ...], y_coord: float) -> float:
    """Return the total polygon intersection length with a horizontal line."""

    intersections: list[float] = []
    for index, start in enumerate(outline):
        end = outline[(index + 1) % len(outline)]
        x1, y1 = start
        x2, y2 = end
        if y1 == y2:
            if abs(y_coord - y1) < 1e-9:
                intersections.extend((min(x1, x2), max(x1, x2)))
            continue
        lower_y = min(y1, y2)
        upper_y = max(y1, y2)
        if y_coord < lower_y or y_coord >= upper_y:
            continue
        ratio = (y_coord - y1) / (y2 - y1)
        intersections.append(x1 + ratio * (x2 - x1))

    if len(intersections) < 2:
        return 0.0
    intersections.sort()
    width = 0.0
    for index in range(0, len(intersections) - 1, 2):
        width += intersections[index + 1] - intersections[index]
    return max(0.0, width)


def scale_generated_geometry(
    geometry: GeneratedGeometry,
    *,
    width_scale: float = 1.0,
    height_scale: float = 1.0,
    length_scale: float = 1.0,
    parameters_update: Mapping[str, float] | None = None,
) -> GeneratedGeometry:
    """Return a scaled copy of generated geometry."""

    scaled_outline = scale_outline_mm(
        geometry.cross_section_outline,
        width_scale=width_scale,
        height_scale=height_scale,
    )
    cross_section_area_mm2 = outline_area_mm2(scaled_outline)
    width_mm = geometry.width_mm * width_scale
    height_mm = geometry.height_mm * height_scale
    length_mm = geometry.length_mm * length_scale
    volume_mm3 = cross_section_area_mm2 * length_mm
    equivalent_diameter_mm = math.sqrt(4.0 * cross_section_area_mm2 / math.pi)
    parameters = dict(geometry.parameters)
    if parameters_update:
        parameters.update(parameters_update)
    return GeneratedGeometry(
        type_id=geometry.type_id,
        shape=geometry.shape,
        parameters=parameters,
        volume_mm3=volume_mm3,
        cross_section_area_mm2=cross_section_area_mm2,
        equivalent_diameter_mm=equivalent_diameter_mm,
        width_mm=width_mm,
        height_mm=height_mm,
        length_mm=length_mm,
        cross_section_outline=scaled_outline,
        parameters_json=json.dumps(parameters, sort_keys=True),
    )


GEOMETRY_TYPES: dict[int, GeometryTypeDefinition] = {
    68: GeometryTypeDefinition(68, "round", 64, ("diameter",)),
    69: GeometryTypeDefinition(69, "round", 64, ("diameter", "tail_radius")),
    70: GeometryTypeDefinition(70, "round", 64, ("diameter", "tail_chamfer")),
    71: GeometryTypeDefinition(71, "round", 64, ("length_to_diameter_ratio",)),
    72: GeometryTypeDefinition(72, "square", 65, ("side_of_square",)),
    73: GeometryTypeDefinition(73, "square", 65, ("side_of_square", "diagonal")),
    74: GeometryTypeDefinition(74, "square", 65, ("length_to_side_ratio",)),
    75: GeometryTypeDefinition(75, "rectangle", 66, ("height", "width")),
    76: GeometryTypeDefinition(
        76,
        "rectangle",
        66,
        ("height_to_width_ratio", "length_to_thickness_ratio"),
    ),
    77: GeometryTypeDefinition(77, "rectangle", 66, ("height", "width", "diagonal")),
    78: GeometryTypeDefinition(
        78,
        "rectangle",
        66,
        ("height", "width", "diagonal_1", "diagonal_2"),
    ),
    79: GeometryTypeDefinition(79, "octagon", 67, ("height",)),
}


class GeometryBuilder:
    """Build billet geometry records for the first migrated preprocessing slice."""

    def build(
        self,
        *,
        type_id: int,
        parameters: Mapping[str, object],
        volume_mm3: float,
    ) -> GeneratedGeometry:
        definition = GEOMETRY_TYPES.get(type_id)
        if definition is None:
            raise GeometryError(f"Unsupported billet geometry type_id={type_id}", type_id=type_id)
        if volume_mm3 <= 0.0:
            raise GeometryError(
                "Billet volume must be positive",
                type_id=type_id,
                parameter="volume_mm3",
                value=volume_mm3,
                limits={"min_exclusive": 0.0},
            )

        normalized_parameters = self._normalize_parameters(definition, parameters)
        try:
            match type_id:
                case 68:
                    geometry = self._round_diameter(definition, normalized_parameters, volume_mm3)
                case 69:
                    geometry = self._round_tail_radius(definition, normalized_parameters, volume_mm3)
                case 70:
                    geometry = self._round_tail_chamfer(definition, normalized_parameters, volume_mm3)
                case 71:
                    geometry = self._round_length_ratio(definition, normalized_parameters, volume_mm3)
                case 72:
                    geometry = self._square_side(definition, normalized_parameters, volume_mm3)
                case 73:
                    geometry = self._square_diagonal(definition, normalized_parameters, volume_mm3)
                case 74:
                    geometry = self._square_length_ratio(definition, normalized_parameters, volume_mm3)
                case 75:
                    geometry = self._rectangle_size(definition, normalized_parameters, volume_mm3)
                case 76:
                    geometry = self._rectangle_ratios(definition, normalized_parameters, volume_mm3)
                case 77:
                    geometry = self._rectangle_single_diagonal(definition, normalized_parameters, volume_mm3)
                case 78:
                    geometry = self._rectangle_double_diagonal(definition, normalized_parameters, volume_mm3)
                case 79:
                    geometry = self._octagon(definition, normalized_parameters, volume_mm3)
                case _:
                    raise GeometryError(f"Unsupported billet geometry type_id={type_id}", type_id=type_id)
            self._validate_geometry(geometry)
            return geometry
        except GeometryError:
            raise
        except SurfaceMeshError as exc:
            raise GeometryError(
                f"Billet 3D geometry generation failed: {exc}",
                type_id=type_id,
                details={"source_error": str(exc)},
            ) from exc

    def supported_type_ids(self) -> tuple[int, ...]:
        """Return all currently supported billet geometry type ids."""

        return tuple(sorted(GEOMETRY_TYPES))

    def get_labels(self, type_id: int) -> tuple[str, ...]:
        """Return the parameter label order for one billet geometry type."""

        definition = GEOMETRY_TYPES.get(type_id)
        if definition is None:
            return ()
        return definition.labels

    def _normalize_parameters(
        self,
        definition: GeometryTypeDefinition,
        parameters: Mapping[str, object],
    ) -> dict[str, float]:
        normalized: dict[str, float] = {}
        for label in definition.labels:
            if label not in parameters:
                raise GeometryError(
                    f"Missing parameter {label!r} for billet geometry type_id={definition.type_id}",
                    type_id=definition.type_id,
                    parameter=label,
                )
            raw_value = parameters[label]
            try:
                normalized[label] = float(raw_value)
            except (TypeError, ValueError) as exc:
                raise GeometryError(
                    f"Parameter {label!r} must be numeric for type_id={definition.type_id}",
                    type_id=definition.type_id,
                    parameter=label,
                    value=raw_value,
                ) from exc
        return normalized

    def _round_diameter(
        self,
        definition: GeometryTypeDefinition,
        parameters: dict[str, float],
        volume_mm3: float,
    ) -> GeneratedGeometry:
        diameter = self._require_positive(parameters["diameter"], "diameter")
        area = 0.25 * math.pi * diameter ** 2
        length = volume_mm3 / area
        outline = self._circle_outline(diameter)
        return self._build_result(
            definition,
            parameters,
            volume_mm3,
            area,
            diameter,
            diameter,
            length,
            outline,
        )

    def _round_tail_radius(
        self,
        definition: GeometryTypeDefinition,
        parameters: dict[str, float],
        volume_mm3: float,
    ) -> GeneratedGeometry:
        true_diameter = self._require_positive(parameters["diameter"], "diameter")
        tail_radius = self._require_positive(parameters["tail_radius"], "tail_radius")
        radius = true_diameter / 2.0
        if tail_radius > radius:
            raise GeometryError(
                "Tail radius must not exceed billet radius",
                type_id=definition.type_id,
                parameter="tail_radius",
                value=tail_radius,
                limits={"min": 0.0, "max": radius},
            )
        b_value = radius - tail_radius
        end_volume = math.pi / 6.0 * tail_radius * (
            4 * tail_radius ** 2 + 3 * math.pi * tail_radius * b_value + 6 * b_value ** 2
        )
        if volume_mm3 <= 2.0 * end_volume:
            raise GeometryError(
                "Billet volume is too small for two rounded tail ends",
                type_id=definition.type_id,
                parameter="volume_mm3",
                value=volume_mm3,
                limits={"min_exclusive": 2.0 * end_volume},
                details={"single_tail_end_volume_mm3": end_volume},
            )
        area = math.pi * radius ** 2
        straight_length = (volume_mm3 - 2.0 * end_volume) / area
        length = straight_length + 2.0 * tail_radius
        outline = self._circle_outline(true_diameter)
        return self._build_result(
            definition,
            {
                **parameters,
                "tail_straight_length": straight_length,
                "tail_end_volume_mm3": end_volume,
            },
            volume_mm3,
            area,
            true_diameter,
            true_diameter,
            length,
            outline,
            surface_mesh=round_tail_radius_surface_mesh(
                diameter=true_diameter,
                tail_radius=tail_radius,
                length=length,
            ),
        )

    def _round_tail_chamfer(
        self,
        definition: GeometryTypeDefinition,
        parameters: dict[str, float],
        volume_mm3: float,
    ) -> GeneratedGeometry:
        true_diameter = self._require_positive(parameters["diameter"], "diameter")
        tail_chamfer = self._require_positive(parameters["tail_chamfer"], "tail_chamfer")
        radius = true_diameter / 2.0
        if tail_chamfer > radius:
            raise GeometryError(
                "Tail chamfer must not exceed billet radius",
                type_id=definition.type_id,
                parameter="tail_chamfer",
                value=tail_chamfer,
                limits={"min": 0.0, "max": radius},
            )
        flat_radius = radius - tail_chamfer
        end_volume = math.pi * tail_chamfer / 3.0 * (
            radius ** 2 + radius * flat_radius + flat_radius ** 2
        )
        if volume_mm3 <= 2.0 * end_volume:
            raise GeometryError(
                "Billet volume is too small for two chamfered tail ends",
                type_id=definition.type_id,
                parameter="volume_mm3",
                value=volume_mm3,
                limits={"min_exclusive": 2.0 * end_volume},
                details={"single_tail_end_volume_mm3": end_volume},
            )
        area = math.pi * radius ** 2
        straight_length = (volume_mm3 - 2.0 * end_volume) / area
        length = straight_length + 2.0 * tail_chamfer
        outline = self._circle_outline(true_diameter)
        return self._build_result(
            definition,
            {
                **parameters,
                "tail_straight_length": straight_length,
                "tail_end_volume_mm3": end_volume,
            },
            volume_mm3,
            area,
            true_diameter,
            true_diameter,
            length,
            outline,
            surface_mesh=round_tail_chamfer_surface_mesh(
                diameter=true_diameter,
                tail_chamfer=tail_chamfer,
                length=length,
            ),
        )

    def _round_length_ratio(
        self,
        definition: GeometryTypeDefinition,
        parameters: dict[str, float],
        volume_mm3: float,
    ) -> GeneratedGeometry:
        ratio = self._require_positive(
            parameters["length_to_diameter_ratio"], "length_to_diameter_ratio"
        )
        length = math.cbrt(4 / math.pi * ratio ** 2 * volume_mm3)
        diameter = length / ratio
        area = 0.25 * math.pi * diameter ** 2
        outline = self._circle_outline(diameter)
        return self._build_result(
            definition,
            parameters,
            volume_mm3,
            area,
            diameter,
            diameter,
            length,
            outline,
        )

    def _square_side(
        self,
        definition: GeometryTypeDefinition,
        parameters: dict[str, float],
        volume_mm3: float,
    ) -> GeneratedGeometry:
        side = self._require_positive(parameters["side_of_square"], "side_of_square")
        area = side ** 2
        length = volume_mm3 / area
        outline = self._square_outline(side)
        return self._build_result(
            definition,
            parameters,
            volume_mm3,
            area,
            side,
            side,
            length,
            outline,
        )

    def _square_diagonal(
        self,
        definition: GeometryTypeDefinition,
        parameters: dict[str, float],
        volume_mm3: float,
    ) -> GeneratedGeometry:
        side = self._require_positive(parameters["side_of_square"], "side_of_square")
        diagonal = self._require_positive(parameters["diagonal"], "diagonal")
        minimum_diagonal = math.sqrt(0.5) * side
        if diagonal < minimum_diagonal:
            raise GeometryError(
                f"Diagonal {diagonal} is too small for square side {side}; minimum is {minimum_diagonal}"
            )
        chamfer_height = math.sqrt(2) / 2 * (math.sqrt(2) * side - diagonal)
        area = side ** 2 - 2 * chamfer_height ** 2
        length = volume_mm3 / area
        outline = self._chamfered_square_outline(side, diagonal, diagonal)
        return self._build_result(
            definition,
            parameters,
            volume_mm3,
            area,
            side,
            side,
            length,
            outline,
        )

    def _square_length_ratio(
        self,
        definition: GeometryTypeDefinition,
        parameters: dict[str, float],
        volume_mm3: float,
    ) -> GeneratedGeometry:
        ratio = self._require_positive(parameters["length_to_side_ratio"], "length_to_side_ratio")
        length = math.cbrt(ratio ** 2 * volume_mm3)
        side = length / ratio
        area = side ** 2
        outline = self._square_outline(side)
        return self._build_result(
            definition,
            parameters,
            volume_mm3,
            area,
            side,
            side,
            length,
            outline,
        )

    def _rectangle_size(
        self,
        definition: GeometryTypeDefinition,
        parameters: dict[str, float],
        volume_mm3: float,
    ) -> GeneratedGeometry:
        height = self._require_positive(parameters["height"], "height")
        width = self._require_positive(parameters["width"], "width")
        area = height * width
        length = volume_mm3 / area
        outline = self._rectangle_outline(height, width)
        return self._build_result(
            definition,
            parameters,
            volume_mm3,
            area,
            width,
            height,
            length,
            outline,
        )

    def _rectangle_ratios(
        self,
        definition: GeometryTypeDefinition,
        parameters: dict[str, float],
        volume_mm3: float,
    ) -> GeneratedGeometry:
        height_to_width_ratio = self._require_positive(
            parameters["height_to_width_ratio"], "height_to_width_ratio"
        )
        length_to_thickness_ratio = self._require_positive(
            parameters["length_to_thickness_ratio"], "length_to_thickness_ratio"
        )
        if height_to_width_ratio > 1.0:
            width = math.cbrt(volume_mm3 / height_to_width_ratio / length_to_thickness_ratio)
            height = width * height_to_width_ratio
            length = width * length_to_thickness_ratio
        else:
            height = math.cbrt(volume_mm3 * height_to_width_ratio / length_to_thickness_ratio)
            width = height / height_to_width_ratio
            length = height * length_to_thickness_ratio
        area = height * width
        outline = self._rectangle_outline(height, width)
        return self._build_result(
            definition,
            parameters,
            volume_mm3,
            area,
            width,
            height,
            length,
            outline,
        )

    def _rectangle_single_diagonal(
        self,
        definition: GeometryTypeDefinition,
        parameters: dict[str, float],
        volume_mm3: float,
    ) -> GeneratedGeometry:
        height = self._require_positive(parameters["height"], "height")
        width = self._require_positive(parameters["width"], "width")
        diagonal = self._require_positive(parameters["diagonal"], "diagonal")
        (
            is_chamfer,
            chamfer_x,
            chamfer_y,
            chamfer_height,
            chamfer_width,
        ) = self._rectangle_diagonal_solution(height, width, diagonal)
        area = height * width - 2 * chamfer_height * chamfer_width
        length = volume_mm3 / area
        if is_chamfer:
            half_width = width / 2.0
            half_height = height / 2.0
            outline = (
                (chamfer_x, half_height),
                (half_width, chamfer_y),
                (half_width, -chamfer_y),
                (chamfer_x, -half_height),
                (-chamfer_x, -half_height),
                (-half_width, -chamfer_y),
                (-half_width, chamfer_y),
                (-chamfer_x, half_height),
            )
        else:
            outline = self._rectangle_outline(height, width)
        return self._build_result(
            definition,
            parameters,
            volume_mm3,
            area,
            width,
            height,
            length,
            outline,
        )

    def _rectangle_double_diagonal(
        self,
        definition: GeometryTypeDefinition,
        parameters: dict[str, float],
        volume_mm3: float,
    ) -> GeneratedGeometry:
        height = self._require_positive(parameters["height"], "height")
        width = self._require_positive(parameters["width"], "width")
        diagonal_1 = self._require_positive(parameters["diagonal_1"], "diagonal_1")
        diagonal_2 = self._require_positive(parameters["diagonal_2"], "diagonal_2")
        first = self._rectangle_diagonal_solution(height, width, diagonal_1)
        second = self._rectangle_diagonal_solution(height, width, diagonal_2)
        area = height * width - first[3] * first[4] - second[3] * second[4]
        length = volume_mm3 / area
        half_width = width / 2.0
        half_height = height / 2.0
        if first[0] and second[0]:
            outline = (
                (first[1], half_height),
                (half_width, first[2]),
                (half_width, -second[2]),
                (second[1], -half_height),
                (-first[1], -half_height),
                (-half_width, -first[2]),
                (-half_width, second[2]),
                (-second[1], half_height),
            )
        elif first[0]:
            outline = (
                (first[1], half_height),
                (half_width, first[2]),
                (half_width, -half_height),
                (-first[1], -half_height),
                (-half_width, -first[2]),
                (-half_width, half_height),
            )
        elif second[0]:
            outline = (
                (half_width, half_height),
                (half_width, -second[2]),
                (second[1], -half_height),
                (-half_width, -half_height),
                (-half_width, second[2]),
                (-second[1], half_height),
            )
        else:
            outline = self._rectangle_outline(height, width)
        return self._build_result(
            definition,
            parameters,
            volume_mm3,
            area,
            width,
            height,
            length,
            outline,
        )

    def _octagon(
        self,
        definition: GeometryTypeDefinition,
        parameters: dict[str, float],
        volume_mm3: float,
    ) -> GeneratedGeometry:
        height = self._require_positive(parameters["height"], "height")
        chamfer_height = height * (1 - math.sqrt(2) / 2)
        area = height ** 2 - 2 * chamfer_height ** 2
        length = volume_mm3 / area
        outline = self._chamfered_square_outline(height, height, height)
        return self._build_result(
            definition,
            parameters,
            volume_mm3,
            area,
            height,
            height,
            length,
            outline,
        )

    def _rectangle_diagonal_solution(
        self,
        height: float,
        width: float,
        diagonal: float,
    ) -> tuple[bool, float, float, float, float]:
        minimum_size, maximum_size = sorted((height, width))
        minimum_diagonal = math.sqrt(
            maximum_size * (maximum_size + math.sqrt(maximum_size ** 2 - minimum_size ** 2)) / 2.0
        )
        maximum_diagonal = math.sqrt(height ** 2 + width ** 2)
        if diagonal < minimum_diagonal:
            raise GeometryError(
                f"Diagonal {diagonal} is too small for rectangle {height}x{width}; minimum is {minimum_diagonal}"
            )

        half_width = width / 2.0
        half_height = height / 2.0
        if diagonal >= maximum_diagonal:
            return (False, half_width, half_height, 0.0, 0.0)

        chamfer_x, chamfer_y = self._solve_rectangle_chamfer_point(
            half_height=half_height,
            half_width=half_width,
            diagonal=diagonal,
        )
        chamfer_height = half_height - chamfer_y
        chamfer_width = half_width - chamfer_x
        return (True, chamfer_x, chamfer_y, chamfer_height, chamfer_width)

    def _solve_rectangle_chamfer_point(
        self,
        *,
        half_height: float,
        half_width: float,
        diagonal: float,
    ) -> tuple[float, float]:
        half_diagonal = diagonal / 2.0
        a_value = 4.0 * (half_diagonal ** 2 - half_height ** 2)
        b_value = half_height ** 2 - half_width ** 2

        def f_value(x_value: float) -> float:
            y_squared = x_value ** 2 + b_value
            if y_squared < 0.0:
                return float("nan")
            y_value = math.sqrt(y_squared)
            return (
                (half_width - x_value) ** 2
                + (half_height - y_value) ** 2
                - 4.0 * x_value ** 2
                + a_value
            )

        lower = max(0.0, math.sqrt(max(0.0, -b_value)))
        upper = half_width
        scan_points = 128
        previous_x = lower
        previous_f = f_value(previous_x)
        bracket: tuple[float, float] | None = None

        for index in range(1, scan_points + 1):
            current_x = lower + (upper - lower) * index / scan_points
            current_f = f_value(current_x)
            if math.isnan(previous_f):
                previous_x, previous_f = current_x, current_f
                continue
            if math.isnan(current_f):
                previous_x, previous_f = current_x, current_f
                continue
            if previous_f == 0.0:
                bracket = (previous_x, previous_x)
                break
            if current_f == 0.0 or previous_f * current_f < 0.0:
                bracket = (previous_x, current_x)
                break
            previous_x, previous_f = current_x, current_f

        if bracket is None:
            raise GeometryError("Failed to solve rectangle chamfer geometry")

        left, right = bracket
        if left == right:
            x_value = left
        else:
            for _ in range(80):
                middle = (left + right) / 2.0
                middle_f = f_value(middle)
                left_f = f_value(left)
                if abs(middle_f) < 1e-10:
                    left = right = middle
                    break
                if left_f * middle_f <= 0.0:
                    right = middle
                else:
                    left = middle
            x_value = (left + right) / 2.0

        y_squared = x_value ** 2 + b_value
        if y_squared < 0.0:
            raise GeometryError("Rectangle chamfer solver produced an invalid point")
        return x_value, math.sqrt(y_squared)

    def _build_result(
        self,
        definition: GeometryTypeDefinition,
        parameters: dict[str, float],
        volume_mm3: float,
        cross_section_area_mm2: float,
        width_mm: float,
        height_mm: float,
        length_mm: float,
        outline: tuple[Point2D, ...],
        surface_mesh: SurfaceMesh | None = None,
    ) -> GeneratedGeometry:
        equivalent_diameter_mm = math.sqrt(cross_section_area_mm2 / math.pi) * 2.0
        mesh = surface_mesh or extruded_polygon_surface_mesh(
            outline,
            length_mm,
            cross_section_point_count=len(outline),
        )
        return GeneratedGeometry(
            type_id=definition.type_id,
            shape=definition.shape,
            parameters=parameters,
            volume_mm3=volume_mm3,
            cross_section_area_mm2=cross_section_area_mm2,
            equivalent_diameter_mm=equivalent_diameter_mm,
            width_mm=width_mm,
            height_mm=height_mm,
            length_mm=length_mm,
            cross_section_outline=outline,
            parameters_json=json.dumps(parameters, sort_keys=True),
            surface_mesh=mesh,
        )

    def _circle_outline(self, diameter: float, *, vertices_count: int = 96) -> tuple[Point2D, ...]:
        radius = diameter / 2.0
        return tuple(
            (
                radius * math.cos(angle),
                radius * math.sin(angle),
            )
            for angle in (2.0 * math.pi * index / vertices_count for index in range(vertices_count))
        )

    def _square_outline(self, side: float) -> tuple[Point2D, ...]:
        half_side = side / 2.0
        return (
            (-half_side, -half_side),
            (-half_side, half_side),
            (half_side, half_side),
            (half_side, -half_side),
        )

    def _rectangle_outline(self, height: float, width: float) -> tuple[Point2D, ...]:
        half_width = width / 2.0
        half_height = height / 2.0
        return (
            (-half_width, -half_height),
            (-half_width, half_height),
            (half_width, half_height),
            (half_width, -half_height),
        )

    def _chamfered_square_outline(
        self,
        side: float,
        diagonal_1: float,
        diagonal_2: float,
    ) -> tuple[Point2D, ...]:
        sqrt_two = math.sqrt(2.0)
        pure_diagonal = sqrt_two * side
        chamfer_height_1 = (pure_diagonal - diagonal_1) / 2.0
        chamfer_height_2 = (pure_diagonal - diagonal_2) / 2.0
        chamfer_length_1 = chamfer_height_1 * sqrt_two
        chamfer_length_2 = chamfer_height_2 * sqrt_two
        half_side = side / 2.0
        return (
            (-half_side + chamfer_length_2, -half_side),
            (-half_side, -half_side + chamfer_length_2),
            (-half_side, half_side - chamfer_length_1),
            (-half_side + chamfer_length_1, half_side),
            (half_side - chamfer_length_1, half_side),
            (half_side, half_side - chamfer_length_1),
            (half_side, -half_side + chamfer_length_2),
            (half_side - chamfer_length_2, -half_side),
        )

    def _require_positive(self, value: float, label: str) -> float:
        if value <= 0.0:
            raise GeometryError(
                f"Parameter {label!r} must be positive",
                parameter=label,
                value=value,
                limits={"min_exclusive": 0.0},
            )
        return value

    def _validate_geometry(self, geometry: GeneratedGeometry) -> None:
        errors: list[dict[str, Any]] = []
        for label, value in (
            ("volume_mm3", geometry.volume_mm3),
            ("cross_section_area_mm2", geometry.cross_section_area_mm2),
            ("equivalent_diameter_mm", geometry.equivalent_diameter_mm),
            ("width_mm", geometry.width_mm),
            ("height_mm", geometry.height_mm),
            ("length_mm", geometry.length_mm),
        ):
            if not math.isfinite(value) or value <= 0.0:
                errors.append({"parameter": label, "value": value, "message": f"{label} must be positive and finite"})
        if len(geometry.cross_section_outline) < 3:
            errors.append({"parameter": "cross_section_outline", "message": "Cross-section outline must have at least three points"})
        outline_area = outline_area_mm2(geometry.cross_section_outline)
        if outline_area <= 0.0:
            errors.append({"parameter": "cross_section_outline", "message": "Cross-section outline area must be positive"})
        if geometry.surface_mesh is None:
            errors.append({"parameter": "surface_mesh", "message": "3D surface mesh is missing"})
        else:
            mesh = geometry.surface_mesh
            if not mesh.vertices or not mesh.faces:
                errors.append({"parameter": "surface_mesh", "message": "3D surface mesh must contain vertices and faces"})
            if mesh.surface_area_mm2 <= 0.0 or not math.isfinite(mesh.surface_area_mm2):
                errors.append({"parameter": "surface_mesh.surface_area_mm2", "value": mesh.surface_area_mm2, "message": "3D surface area must be positive and finite"})
            if mesh.volume_mm3 <= 0.0 or not math.isfinite(mesh.volume_mm3):
                errors.append({"parameter": "surface_mesh.volume_mm3", "value": mesh.volume_mm3, "message": "3D mesh volume must be positive and finite"})
            volume_tolerance = max(1.0, abs(geometry.volume_mm3) * 0.02)
            if abs(mesh.volume_mm3 - geometry.volume_mm3) > volume_tolerance:
                errors.append(
                    {
                        "parameter": "surface_mesh.volume_mm3",
                        "value": mesh.volume_mm3,
                        "expected": geometry.volume_mm3,
                        "message": "3D mesh volume does not match analytical billet volume within tolerance",
                    }
                )
            bounds = mesh.bounds
            if bounds:
                mesh_dimensions = (
                    abs(bounds.get("x_max", 0.0) - bounds.get("x_min", 0.0)),
                    abs(bounds.get("y_max", 0.0) - bounds.get("y_min", 0.0)),
                    abs(bounds.get("z_max", 0.0) - bounds.get("z_min", 0.0)),
                )
                expected_dimensions = (geometry.length_mm, geometry.width_mm, geometry.height_mm)
                for axis, actual, expected in zip(("x", "y", "z"), mesh_dimensions, expected_dimensions):
                    tolerance = max(1e-6, abs(expected) * 0.002)
                    if abs(actual - expected) > tolerance:
                        errors.append(
                            {
                                "parameter": f"surface_mesh.bounds.{axis}",
                                "value": actual,
                                "expected": expected,
                                "message": "3D mesh bounds do not match analytical billet dimensions",
                            }
                        )

        if errors:
            error = GeometryError(
                "Billet geometry validation failed",
                type_id=geometry.type_id,
                details={"errors": errors},
            )
            LOGGER.error("Billet geometry validation failed type_id=%s details=%s", geometry.type_id, error.to_payload())
            raise error
