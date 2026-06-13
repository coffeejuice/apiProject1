import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pytest.importorskip("shapely")

from app.services.preprocessor.geometry import GeneratedGeometry
from app.services.preprocessor.cogging.surfaces_3d import (
    CoggingSurfaceInput,
    build_cogging_surface_pair,
)
from app.services.preprocessor.legacy_surface_mesh import LegacySurfacePair
from app.services.preprocessor.operation_keys import (
    PROLONGATION_HEIGHT_BITES,
    PROLONGATION_ROTATION_HEIGHT,
    PROLONGATION_SKIP_BITES,
    RADIAL_HEIGHT_BITES,
    RADIAL_PRESS_AXIS_FEED,
    RADIAL_ROTATION_HEIGHT_FEED,
    ROUNDING_SPIRAL_ONE_ROTATION,
    ROUNDING_SPIRAL_THREE_ROTATIONS,
    TRANSVERSAL_ROTATION_HEIGHT,
    TRANSVERSE_ALL_IN_ONE,
)
from app.services.preprocessor.prolongation import calculate_prolongation
from app.services.preprocessor.upsetting import DieDimensions, PressModeParameters


def _initial_rectangle() -> GeneratedGeometry:
    return GeneratedGeometry(
        type_id=75,
        shape="rectangle",
        parameters={"height": 100.0, "width": 80.0},
        volume_mm3=8000.0 * 500.0,
        cross_section_area_mm2=8000.0,
        equivalent_diameter_mm=math.sqrt(4.0 * 8000.0 / math.pi),
        width_mm=80.0,
        height_mm=100.0,
        length_mm=500.0,
        cross_section_outline=(
            (-40.0, -50.0),
            (-40.0, 50.0),
            (40.0, 50.0),
            (40.0, -50.0),
        ),
        parameters_json="{}",
    )


def _press_mode() -> PressModeParameters:
    return PressModeParameters(
        press_mode_id=1,
        working_speed_mm_per_s=20.0,
        back_speed_mm_per_s=100.0,
        idle_speed_mm_per_s=200.0,
        approaching_distance_mm=10.0,
        min_idle_stroke_mm=20.0,
        max_idle_stroke_mm=80.0,
        open_height_without_dies_mm=500.0,
    )


def _die() -> DieDimensions:
    return DieDimensions(
        die_id=1,
        straight_length_mm=180.0,
        edge_radius_mm=20.0,
        edge_angle_deg=90.0,
        height_mm=60.0,
    )


BASE_PARAMETERS = {
    "speed_mm_per_s": 12.0,
    "previous_total_time_seconds": 100.0,
    "time_between_operation_seconds": 30.0,
    "angle_deg": 90.0,
    "feed_mm": 70.0,
    "feed_first_mm": 60.0,
    "feed_middle_mm": 55.0,
    "feed_last_mm": 50.0,
    "radial_feed_mm": 80.0,
    "num_of_bites_input": 5,
    "rotation_per_bite_deg": 18.0,
    "current_feed_direction_id": 2,
    "previous_feed_direction_id": 3,
    "is_same_operation_type_as_previous": True,
    "mesh_elements": 12000,
    "extra_rotations": {"y_rotation": 15.0, "z_rotation": 25.0},
}


CASES = [
    (
        PROLONGATION_ROTATION_HEIGHT,
        {"final_height_mm": 80.0, "num_of_bites_input": None},
        {
            "final": (500.0, 100.0, 80.0, 8000.0),
            "feed": (60.0, 55.0, 50.0),
            "bites": 10,
            "contacts": (55.0, 86.93050437472603, 100.0),
            "strains": (0.0, -0.2231435513142097, 0.2231435513142097),
            "total_time_seconds": 157.98640350877193,
        },
    ),
    (
        PROLONGATION_HEIGHT_BITES,
        {"final_height_mm": 80.0},
        {
            "final": (500.0, 100.0, 80.0, 8000.0),
            "feed": (100.0, 0.0, 0.0),
            "bites": 5,
            "contacts": (100.0, 117.32050807568878, 100.0),
            "strains": (0.0, -0.2231435513142097, 0.2231435513142097),
            "total_time_seconds": 145.46885964912283,
        },
    ),
    (
        PROLONGATION_SKIP_BITES,
        {"final_height_mm": 80.0, "skip_bites": (2, 4)},
        {
            "final": (500.0, 100.0, 80.0, 8000.0),
            "feed": (100.0, 0.0, 0.0),
            "bites": 3,
            "contacts": (100.0, 117.32050807568878, 100.0),
            "strains": (0.0, -0.2231435513142097, 0.2231435513142097),
            "total_time_seconds": 140.46184210526317,
        },
    ),
    (
        ROUNDING_SPIRAL_ONE_ROTATION,
        {"final_diameter_mm": 90.0},
        {
            "final": (629.2093950073462, 90.0, 90.0, 6357.184161169906),
            "feed": (100.0, 70.0, 0.0),
            "bites": 13,
            "contacts": (100.0, 100.0, 45.0),
            "strains": (0.22985600432138, -0.11492800216069, -0.11492800216069),
            "total_time_seconds": 153.56359649122808,
            "rotations_count_per_feed_list": (5, 0, 5),
        },
    ),
    (
        ROUNDING_SPIRAL_THREE_ROTATIONS,
        {"final_diameter_mm": 90.0},
        {
            "final": (629.2093950073462, 90.0, 90.0, 6357.184161169906),
            "feed": (100.0, 70.0, 0.0),
            "bites": 16,
            "contacts": (100.0, 100.0, 45.0),
            "strains": (0.22985600432138, -0.11492800216069, -0.11492800216069),
            "total_time_seconds": 158.27412280701756,
            "rotations_count_per_feed_list": (5, 2, 5),
        },
    ),
    (
        RADIAL_ROTATION_HEIGHT_FEED,
        {"final_height_mm": 80.0},
        {
            "final": (500.0, 100.0, 80.0, 8000.0),
            "feed": (80.0, 0.0, 0.0),
            "bites": 7,
            "contacts": (80.0, 97.32050807568878, 100.0),
            "strains": (0.0, -0.2231435513142097, 0.2231435513142097),
            "total_time_seconds": 150.47587719298247,
            "radial_rotations": [("y", 90.0), ("x", 90.0)],
        },
    ),
    (
        RADIAL_HEIGHT_BITES,
        {"final_height_mm": 80.0},
        {
            "final": (500.0, 100.0, 80.0, 8000.0),
            "feed": (100.0, 0.0, 0.0),
            "bites": 5,
            "contacts": (100.0, 117.32050807568878, 100.0),
            "strains": (0.0, -0.2231435513142097, 0.2231435513142097),
            "total_time_seconds": 145.46885964912283,
            "radial_rotations": [("y", 90.0), ("x", 90.0)],
        },
    ),
    (
        RADIAL_PRESS_AXIS_FEED,
        {"final_height_mm": 80.0},
        {
            "final": (500.0, 100.0, 80.0, 8000.0),
            "feed": (80.0, 0.0, 0.0),
            "bites": 7,
            "contacts": (80.0, 97.32050807568878, 100.0),
            "strains": (0.0, -0.2231435513142097, 0.2231435513142097),
            "total_time_seconds": 150.47587719298247,
            "radial_rotations": [("y", 90.0), ("z", 90.0)],
        },
    ),
    (
        TRANSVERSE_ALL_IN_ONE,
        {"final_height_mm": 80.0},
        {
            "final": (500.0, 100.0, 80.0, 8000.0),
            "feed": (100.0, 0.0, 0.0),
            "bites": 5,
            "contacts": (100.0, 117.32050807568878, 100.0),
            "strains": (0.0, -0.2231435513142097, 0.2231435513142097),
            "total_time_seconds": 145.46885964912283,
            "full_die_adapter": True,
        },
    ),
    (
        TRANSVERSAL_ROTATION_HEIGHT,
        {"final_height_mm": 80.0},
        {
            "final": (500.0, 100.0, 80.0, 8000.0),
            "feed": (500.0, 0.0, 0.0),
            "bites": 1,
            "contacts": (500.0, 500.0, 100.0),
            "strains": (0.0, -0.2231435513142097, 0.2231435513142097),
            "total_time_seconds": 135.4548245614035,
            "full_die_adapter": True,
        },
    ),
]


@pytest.mark.parametrize("template_id,overrides,expected", CASES)
def test_cogging_prolongation_variant_regression(template_id, overrides, expected):
    parameters = dict(BASE_PARAMETERS)
    parameters.update(overrides)

    result = calculate_prolongation(
        template_id=template_id,
        initial_geometry=_initial_rectangle(),
        press_mode=_press_mode(),
        top_die=_die(),
        bottom_die=_die(),
        **parameters,
    )

    final_length, final_width, final_height, final_area = expected["final"]
    assert result.final_geometry.length_mm == pytest.approx(final_length)
    assert result.final_geometry.width_mm == pytest.approx(final_width)
    assert result.final_geometry.height_mm == pytest.approx(final_height)
    assert result.final_geometry.cross_section_area_mm2 == pytest.approx(final_area)

    feed_first, feed_middle, feed_last = expected["feed"]
    assert result.metrics["feed_first"] == pytest.approx(feed_first)
    assert result.metrics["feed_middle"] == pytest.approx(feed_middle)
    assert result.metrics["feed_last"] == pytest.approx(feed_last)
    assert result.metrics["num_of_bites"] == expected["bites"]

    contact_initial, contact_final, contact_width = expected["contacts"]
    assert result.metrics["initial_length_of_contact"] == pytest.approx(contact_initial)
    assert result.metrics["final_length_of_contact"] == pytest.approx(contact_final)
    assert result.metrics["final_width_of_contact"] == pytest.approx(contact_width)

    strain_length, strain_height, strain_width = expected["strains"]
    assert result.metrics["strain_length"] == pytest.approx(strain_length)
    assert result.metrics["strain_height"] == pytest.approx(strain_height)
    assert result.metrics["strain_width"] == pytest.approx(strain_width)
    assert result.total_time_seconds == pytest.approx(expected["total_time_seconds"])

    assert len(result.operation_specific_parameters["bites_table"]) == expected["bites"]
    if "rotations_count_per_feed_list" in expected:
        assert result.operation_specific_parameters["rotations_count_per_feed_list"] == expected["rotations_count_per_feed_list"]
    if "radial_rotations" in expected:
        assert result.operation_specific_parameters["radial_rotations"] == expected["radial_rotations"]
    if "full_die_adapter" in expected:
        assert result.operation_specific_parameters["full_die_adapter"] is expected["full_die_adapter"]


class _FakeSurfaceBuilder:
    def __init__(self):
        self.calls = []

    def prolongation(
        self,
        *,
        previous_final,
        initial_geometry,
        final_geometry,
        metrics,
        operation_specific_parameters,
        template_id,
    ):
        self.calls.append(
            {
                "previous_final": previous_final,
                "initial_geometry": initial_geometry,
                "final_geometry": final_geometry,
                "metrics": metrics,
                "operation_specific_parameters": operation_specific_parameters,
                "template_id": template_id,
            }
        )
        return LegacySurfacePair(initial=previous_final, final=previous_final, notes=("fake surface",))


@pytest.mark.parametrize(
    "template_id",
    [
        PROLONGATION_ROTATION_HEIGHT,
        ROUNDING_SPIRAL_ONE_ROTATION,
        RADIAL_ROTATION_HEIGHT_FEED,
        TRANSVERSE_ALL_IN_ONE,
    ],
)
def test_cogging_surface_dispatch_uses_3d_layer(template_id):
    builder = _FakeSurfaceBuilder()
    geometry = _initial_rectangle()

    result = build_cogging_surface_pair(
        CoggingSurfaceInput(
            previous_final=None,
            initial_geometry=geometry,
            final_geometry=geometry,
            metrics={},
            operation_specific_parameters={},
            template_id=template_id,
        ),
        builder=builder,
    )

    assert result.notes == ("fake surface",)
    assert len(builder.calls) == 1
    assert builder.calls[0]["template_id"] == template_id
