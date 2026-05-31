"""Semantic operation template identifiers used by preprocessing."""

FURNACE_TEMPLATE_ID = "furnace"
HEATING_TEMPERATURE_DURATION_TEMPLATE_ID = "heating.temperature_duration"
DOCUMENT_INITIAL_DATA_TEMPLATE_ID = "document_initial_data"
GEOMETRY_TEMPLATE_PREFIX = "document.geometry."

OPERATION_EMPTY_TEMPLATE_ID = "operation.empty"

UPSETTING_ROTATION_HEIGHT = "upsetting.rotation_height"
UPSETTING_TAIL_FLATTENING = "upsetting.tail_flattening"
UPSETTING_SINGLE_STROKE = "upsetting.single_stroke"
UPSETTING_THREE_STROKES = "upsetting.three_strokes"
UPSETTING_TAIL_CHAMFERING = "upsetting.tail_chamfering"
UPSETTING_TEMPLATE_IDS = frozenset(
    {
        UPSETTING_ROTATION_HEIGHT,
        UPSETTING_TAIL_FLATTENING,
        UPSETTING_SINGLE_STROKE,
        UPSETTING_THREE_STROKES,
        UPSETTING_TAIL_CHAMFERING,
    }
)
UPSETTING_LENGTH_TARGET_TEMPLATE_IDS = frozenset(
    {
        UPSETTING_ROTATION_HEIGHT,
        UPSETTING_SINGLE_STROKE,
        UPSETTING_THREE_STROKES,
    }
)
UPSETTING_PRESSURE_CONTROL_TEMPLATE_IDS = frozenset(
    {
        UPSETTING_TAIL_FLATTENING,
        UPSETTING_TAIL_CHAMFERING,
    }
)

PROLONGATION_ROTATION_HEIGHT = "prolongation.rotation_height"
PROLONGATION_HEIGHT_BITES = "prolongation.height_bites"
PROLONGATION_SKIP_BITES = "prolongation.skip_bites"
ROUNDING_SPIRAL_ONE_ROTATION = "rounding.spiral_one_rotation"
ROUNDING_SPIRAL_THREE_ROTATIONS = "rounding.spiral_three_rotations"
RADIAL_ROTATION_HEIGHT_FEED = "radial.rotation_height_feed"
RADIAL_HEIGHT_BITES = "radial.height_bites"
RADIAL_PRESS_AXIS_FEED = "radial.press_axis_feed"
RADIAL_INITIAL_ROTATIONS = "radial.initial_rotations"
TRANSVERSE_ALL_IN_ONE = "transverse.all_in_one"
TRANSVERSAL_ROTATION_HEIGHT = "transversal.rotation_height"
CUTTING_HOT_KEEP_PERCENT = "cutting.hot_keep_percent"
CUTTING_COLD_SAW_KEEP_PERCENT = "cutting.cold_saw_keep_percent"

AXIAL_PROLONGATION_TEMPLATE_IDS = frozenset(
    {
        PROLONGATION_ROTATION_HEIGHT,
        PROLONGATION_HEIGHT_BITES,
        PROLONGATION_SKIP_BITES,
    }
)
SPIRAL_PROLONGATION_TEMPLATE_IDS = frozenset(
    {
        ROUNDING_SPIRAL_ONE_ROTATION,
        ROUNDING_SPIRAL_THREE_ROTATIONS,
    }
)
RADIAL_PROLONGATION_TEMPLATE_IDS = frozenset(
    {
        RADIAL_ROTATION_HEIGHT_FEED,
        RADIAL_HEIGHT_BITES,
        RADIAL_PRESS_AXIS_FEED,
    }
)
FULL_DIE_TEMPLATE_IDS = frozenset(
    {
        TRANSVERSE_ALL_IN_ONE,
        TRANSVERSAL_ROTATION_HEIGHT,
    }
)
CUTTING_TEMPLATE_IDS = frozenset(
    {
        CUTTING_HOT_KEEP_PERCENT,
        CUTTING_COLD_SAW_KEEP_PERCENT,
    }
)
PROLONGATION_TEMPLATE_IDS = (
    AXIAL_PROLONGATION_TEMPLATE_IDS
    | SPIRAL_PROLONGATION_TEMPLATE_IDS
    | RADIAL_PROLONGATION_TEMPLATE_IDS
    | FULL_DIE_TEMPLATE_IDS
)
