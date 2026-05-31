import logging
import traceback
import json
import time
import math
import numpy as np
from scipy.optimize import fsolve
from shapely.affinity import scale
from shapely.geometry import Polygon
from trimesh import Trimesh

from forgelab.common.shapely_2d_funcs import polygon_to_3d_trimesh_object, \
    convert_trimesh_object_to_memory_buffer_object

# create logger
LOGGER = logging.getLogger(__name__)


class Geometry:
    """Create 3D geometry object."""

    try:
        _parameters_map = {
    
            68: {
                'shape': 'round',
                'parent_type_id': 64,
                'labels': ('diameter',),
                'value_types': (float,),
            },
            69: {
                'shape': 'round',
                'parent_type_id': 64,
                'labels': ('diameter', 'tail_radius',),
                'value_types': (float, float,),
            },
            70: {
                'shape': 'round',
                'parent_type_id': 64,
                'labels': ('diameter', 'tail_chamfer',),
                'value_types': (float, float,),
            },
            71: {
                'shape': 'round',
                'parent_type_id': 64,
                'labels': ('length_to_diameter_ratio',),
                'value_types': (float,),
            },
    
            72: {
                'shape': 'square',
                'parent_type_id': 65,
                'labels': ('side_of_square',),
                'value_types': (float,),
            },
            73: {
                'shape': 'square',
                'parent_type_id': 65,
                'labels': ('side_of_square', 'diagonal'),
                'value_types': (float, float,),
            },
            74: {
                'shape': 'square',
                'parent_type_id': 65,
                'labels': ('length_to_side_ratio',),
                'value_types': (float,),
            },
    
            75: {
                'shape': 'rectangle',
                'parent_type_id': 66,
                'labels': ('height', 'width'),
                'value_types': (float, float,),
            },
            76: {
                'shape': 'rectangle',
                'parent_type_id': 66,
                'labels': ('height_to_width_ratio', 'length_to_thickness_ratio',),
                'value_types': (float,),
            },
            77: {
                'shape': 'rectangle',
                'parent_type_id': 66,
                'labels': ('height', 'width', 'diagonal',),
                'value_types': (float, float, float,),
            },
            78: {
                'shape': 'rectangle',
                'parent_type_id': 66,
                'labels': ('height', 'width', 'diagonal_1', 'diagonal_2',),
                'value_types': (float, float, float, float,),
            },
    
            79: {
                'shape': 'octagon',
                'parent_type_id': 67,
                'labels': ('height',),
                'value_types': (float,),
            },
        }
    except NameError:
        LOGGER.error("Failed to create dictionary with 'NameError'.")
    except Exception as _err:
        LOGGER.error(f"Failed to create dictionary with '{_err}'.")

    def __init__(
            self,
            worker_id: int,
            pvid: int,
            execution_order: int,
            execution_order_count: int,
            time_start: float,
            type_id: int,
            labels: [list, set, tuple],
            values: [list, set, tuple],
            volume: float
    ):
        self.worker_id: int = worker_id
        self.pvid: int = pvid
        self.eo: int = execution_order
        self.eo_last: int = execution_order_count
        self.time_start: float = time_start
        self.type_id: int = type_id

        self._volume: float = volume
        self._labels = labels
        self._values = values
        self._parameters: dict = {}

        self.cross_section_area: float | None = None
        self.equivalent_diameter: float | None = None
        self.height: float | None = None
        self.width: float | None = None
        self.length: float | None = None
        self.parameters_3d_json = None
        self.cross_section_polygon: Polygon | None = None
        self.trimesh_obj: Trimesh | None = None
        self._temporary_polygon = None

        self._is_error: bool = True


        LOGGER.error_message = []
        LOGGER.info_message = []

    def create(self):
        """Create 3D geometry object."""
        try:
            assert self.type_id in self._parameters_map, (f"Error: Entered geometry 'type_id' = '{self.type_id}', "
                                                           f"but it is not recognized as valid.")
            assert float(self._volume) > 0.0, (f"Error: Volume of 3D model = '{self._volume}'. "
                                               f"The value does not satisfy 'not negative' requirement.")
            assert self._assert_labels(), (f"Error: Entered geometry 'labels' = '{self._labels}', "
                                           f"but it is not recognized as valid.")
            assert self._assert_values(), (f"Error: Entered geometry 'values' = '{self._values}', "
                                           f"but it is not recognized as valid.")

            for label, parameter in zip(self._labels, self._values):
                self._parameters[label] = parameter

            self._polygon_and_dimensions()
            self._json_3d()
            self._equivalent_diameter()
            self._trimesh_obj()
            self._binary_3d_stl()

            self._is_error = False
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__} Geometry class failed to create 3D model: {_err}")
            raise

    @property
    def is_created(self):
        return not self._is_error

    def _polygon_and_dimensions(self):
        """Build geometry object based on self._type_id and self._parameters."""
        try:
            match self.type_id:
                case 68:
                    self._round_68()  # Round D, flat tails
                case 69:
                    self._round_69()  # Round D, rounded tails
                case 70:
                    self._round_70()  # Round D, chamfered tails
                case 71:
                    self._round_71()  # length_to_diameter_ratio
                case 72:
                    self._square_72()  # side_of_square
                case 73:
                    self._square_73()  # Square + chamfers, 'side_of_square', 'diagonal'
                case 74:
                    self._square_74()  # Pure square, length_to_side_ratio
                case 75:
                    self._rectangle_75()
                case 76:
                    self._rectangle_76()  # Rectangle, 'height_to_width_ratio', 'length_to_thickness_ratio'
                case 77:
                    self._rectangle_77()  # Rectangle, 'height', 'width', 'diagonal'
                case 78:
                    self._rectangle_78()  # Rectangle, 'height', 'width', 'diagonal_1', 'diagonal_2'
                case 79:
                    self._octagon_79()  # Octagon
                case _:
                    raise f"Unknown geometry type '{self.type_id}'."

            assert self.height is not None, "Billet height is not defined"
            assert self.height > 0.0, "Billet height is negative"
            assert self.width is not None, "Billet width is not defined"
            assert self.width > 0.0, "Billet width is negative"
            assert self.length is not None, "Billet length is not defined"
            assert self.length > 0.0, "Billet length is negative"

        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError("Failure in 3D model geometry core")

    def _json_3d(self):
        try:
            geometry_input_parameters = {k: v for k, v in zip(self._labels, self._values)}
            self.parameters_3d_json = json.dumps(geometry_input_parameters)
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError("Failed convert 3D to JSON with error")

    def _equivalent_diameter(self):
        try:
            self.equivalent_diameter = math.sqrt(self.cross_section_area / math.pi) * 2
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError("Failed to calculate equivalent diameter with error")

    def _trimesh_obj(self):
        try:
            assert isinstance(self.cross_section_polygon, Polygon)
            self.trimesh_obj = polygon_to_3d_trimesh_object(self.cross_section_polygon, self.length)
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError("Failed to calculate equivalent diameter with error")

    def _binary_3d_stl(self):
        try:
            assert isinstance(self.trimesh_obj, Trimesh)
            self.binary_3d_stl = convert_trimesh_object_to_memory_buffer_object(self.trimesh_obj)
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError("Failed to calculate equivalent diameter with error")

    def _assert_labels(self) -> bool:
        """Set labels of geometry object. Order of labels is important to read parameters in right order."""
        try:
            if isinstance(self._labels, (list, tuple, set,)):
                if self._labels:
                    _labels_set = self._labels if isinstance(self._labels, set) else set(self._labels)
                    _labels_pattern = set(self._parameters_map[self.type_id]['labels'])
                    if _labels_set == _labels_pattern:
                        return True
            return False
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise

    def _assert_values(self) -> bool:
        try:
            if isinstance(self._values, (list, tuple, set,)):
                if self._values:
                    if len(self._values) == len(self._labels):
                        return True
            return False
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise

    def get_labels(self, type_id: int = None) -> tuple:
        """
        Return labels of geometry object for type_id argument, if argument is given.
        Otherwise, return labels of geometry.

        :param type_id: int
        :return: tuple
        """
        try:
            # There is no argument. Return labels for geometry object
            if type_id is None:
                if self.type_id in self._parameters_map:
                    return self._parameters_map.get(self.type_id).get('labels')

            # Return labels for argument type_id
            elif isinstance(type_id, int):
                if type_id in self._parameters_map:
                    return self._parameters_map.get(type_id).get('labels')

            return tuple()
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise

    def create_polygon_circle(self, _diameter: float, _vertices_count: int = 100) -> Polygon:
        """Receives diameter. Returns polygon of circle."""
        try:
            _diameter_numpy = np.array([_diameter])
            angle = np.linspace(0, 2 * np.pi, _vertices_count)
            x = (_diameter_numpy / 2) * np.cos(angle)
            y = (_diameter_numpy / 2) * np.sin(angle)
            vertices = np.column_stack((x, y))
            return Polygon(vertices)
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise

    def create_polygon_rectangle(self, height: float, width: float) -> Polygon:
        """Receives height and width of Rectangle. Returns polygon of rectangle shape."""
        try:
            return Polygon([
                (-width / 2, -height / 2),
                (-width / 2, height / 2),
                (width / 2, height / 2),
                (width / 2, -height / 2),
                (-width / 2, -height / 2)
            ])
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise

    def create_polygon_square(self, side: float) -> Polygon:
        """Receives side size of Square. Returns polygon of Square."""
        try:
            return Polygon([
                (-side / 2, -side / 2),
                (-side / 2, side / 2),
                (side / 2, side / 2),
                (side / 2, -side / 2),
                (-side / 2, -side / 2)
            ])
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise

    def create_polygon_chamfered_square(self, side: float, _diagonal_1: float, _diagonal_2: float) -> Polygon:
        """Receives side size of Square. Returns polygon of Square."""
        try:
            sqrt_2 = math.sqrt(2)

            pure_square_diagonal = sqrt_2 * side

            chamfer_height_1 = (pure_square_diagonal - _diagonal_1) / 2
            chamfer_height_2 = (pure_square_diagonal - _diagonal_2) / 2

            chamfer_length_1 = chamfer_height_1 * sqrt_2
            chamfer_length_2 = chamfer_height_2 * sqrt_2

            return Polygon([
                (-side/2 + chamfer_length_2, -side/2),
                (-side/2, -side/2 + chamfer_length_2),
                (-side/2, side/2 - chamfer_length_1),
                (-side/2 + chamfer_length_1, side/2),
                (side/2 - chamfer_length_1, side/2),
                (side/2, side/2 - chamfer_length_1),
                (side/2, -side/2 + chamfer_length_2),
                (side/2 - chamfer_length_2, -side/2),
                (-side/2 + chamfer_length_2, -side/2)
            ])
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise

    def create_polygon_chamfered_rectangle(self, height: float, width: float, _diagonal_1: float, _diagonal_2: float) -> Polygon:
        """Receives side size of Square. Returns polygon of Square."""
        try:
            sqrt_2 = math.sqrt(2)

            pure_square_diagonal = sqrt_2 * height

            chamfer_height_1 = (pure_square_diagonal - _diagonal_1) / 2
            chamfer_height_2 = (pure_square_diagonal - _diagonal_2) / 2

            chamfer_length_1 = chamfer_height_1 * sqrt_2
            chamfer_length_2 = chamfer_height_2 * sqrt_2

            return Polygon([
                (-width / 2 + chamfer_length_2, -height / 2),
                (-width / 2, -height / 2 + chamfer_length_2),
                (-width / 2, height / 2 - chamfer_length_1),
                (-width / 2 + chamfer_length_1, height / 2),
                (width / 2 - chamfer_length_1, height / 2),
                (width / 2, height / 2 - chamfer_length_1),
                (width / 2, -height / 2 + chamfer_length_2),
                (width / 2 - chamfer_length_2, -height / 2),
                (-width / 2 + chamfer_length_2, -height / 2)
            ])
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise

    def scale_polygon(self, input_polygon: Polygon) -> Polygon:
        try:
            scale_factor = math.sqrt(self.cross_section_area / input_polygon.area)
            return scale(input_polygon, xfact=scale_factor, yfact=scale_factor)
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise

    def _round_68(self):
        """Create 3D geometry of rectangular section with chamfers."""
        try:
            _diameter = self._parameters["diameter"]
            if _diameter < 0.0:
                LOGGER.error(
                    "Error: Geometry class failed to create 3D model."
                    " User wants to build round section with diameter D <= 0.")
                return

            self.width = _diameter
            self.height = _diameter
            self.cross_section_area = 0.25 * math.pi * _diameter ** 2
            self.length = self._volume / self.cross_section_area

            _temporary_polygon = self.create_polygon_circle(_diameter)
            self.cross_section_polygon = self.scale_polygon(_temporary_polygon)

            LOGGER.info(
                f"{self.log_id} Geometry created - Cylinder with flat tails:"
                f" D x L = {_diameter:4g} x {self.length:4g} mm,"
                f" A = {self.cross_section_area / 1e6:4g} m2,"
                f" V = {self._volume / 1e9:4g} m3."
            )
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise

    def _round_69(self):
        """Create 3D geometry of Round D with rounded tails."""
        try:
            true_diameter = self._parameters["diameter"]
            tr = self._parameters["tail_radius"]

            if true_diameter < 0.0:
                LOGGER.error(
                    "Error: Geometry class failed to create 3D model."
                    " User wants to build round section with diameter D <= 0.")
                return

            if tr < 0.0:
                LOGGER.error(
                    "Error: Geometry class failed to create 3D model."
                    " User wants to round cylinder edges with rounding radius R <= 0.")
                return

            # First, calculate True values, which will be used to create 3D model

            radius = true_diameter / 2
            b = radius - tr
            v = self._volume
            vr = math.pi / 6 * tr * (4 * tr ** 2 + 3 * math.pi * tr * b + 6 * b ** 2)
            v_m = v - 2 * vr
            self.length = (v_m + 2 * math.pi * tr * radius ** 2) / (math.pi * radius ** 2)

            # Second, calculate fake values, fixing Length and assuming there is no rounding

            self.cross_section_area = self._volume / self.length
            fake_diameter = math.sqrt(self.cross_section_area / math.pi) * 2
            self.width = fake_diameter
            self.height = fake_diameter

            _temporary_polygon = self.create_polygon_circle(fake_diameter)
            self.cross_section_polygon = self.scale_polygon(_temporary_polygon)

            LOGGER.info(
                f"{self.log_id} Geometry created - Cylinder with rounded edges:"
                f" D x L = {fake_diameter:4g} x {self.length:4g} mm,"
                f" edge R = {tr:4g} mm,"
                f" A = {self.cross_section_area / 1e6:4g} m2,"
                f" V = {self._volume / 1e9:4g} m3."
            )
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise

    def _round_70(self):
        """Create 3D geometry of Round with tail chamfers."""
        try:
            _d = self._parameters["diameter"]
            chamfer = self._parameters["tail_chamfer"]
            if _d < 0.0:
                LOGGER.error(
                    "Error: Geometry class failed to create 3D model."
                    " User wants to build round section with diameter D <= 0.")
                return

            if chamfer < 0.0:
                LOGGER.error(
                    "Error: Geometry class failed to create 3D model."
                    " User wants to chamfer cylinder edges with chamfer height <= 0.")
                return

            # First, calculate True values, which will be used to create 3D model

            _r = _d / 2

            self.cross_section_area = math.pi * _r ** 2
            self.width = _d
            self.height = _d

            fake_length = self._volume / self.cross_section_area

            # Second, calculate fake values, fixing Length and assuming there are no tail chamfers

            self.length = fake_length

            _temporary_polygon = self.create_polygon_circle(_d)
            self.cross_section_polygon = self.scale_polygon(_temporary_polygon)

            LOGGER.info(
                f"{self.log_id} Geometry created - Cylinder with tail chamfers:"
                f" D x L = {_d:4g} x {self.length:4g} mm,"
                f" edge chamfer = {chamfer:4g} mm,"
                f" A = {self.cross_section_area / 1e6:4g} m2,"
                f" V = {self._volume / 1e9:4g} m3."
            )
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise

    def _round_71(self):
        """Create 3D geometry of Round, specified with length_to_diameter_ratio."""
        try:
            length_to_diameter_ratio = self._parameters["length_to_diameter_ratio"]
            if length_to_diameter_ratio < 0.0:
                LOGGER.error(
                    "Error: Geometry class failed to create 3D model."
                    " User wants to build a cylinder with length to diameter ratio L/D <= 0.")
                return

            self.length = math.cbrt(4 / math.pi * length_to_diameter_ratio ** 2 * self._volume)
            _diameter = self.length / length_to_diameter_ratio
            self.width = _diameter
            self.height = _diameter
            self.cross_section_area = 0.25 * math.pi * _diameter ** 2

            _temporary_polygon = self.create_polygon_circle(_diameter)
            self.cross_section_polygon = self.scale_polygon(_temporary_polygon)

            LOGGER.info(
                f"{self.log_id} Geometry created - Cylinder with flat tails:"
                f" D x L = {_diameter:4g} x {self.length:4g} mm,"
                f" A = {self.cross_section_area / 1e6:4g} m2,"
                f" V = {self._volume / 1e9:4g} m3."
            )
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise

    def _square_72(self):
        """Create 3D geometry of square section with flat tails."""
        try:
            self.height = self._parameters["side_of_square"]
            if self.height < 0.0:
                LOGGER.error(
                    "Error: Geometry class failed to create 3D model."
                    " User wants to build a square section with side H <= 0.")
                return

            self.width = self.height
            self.cross_section_area = self.height ** 2
            self.length = self._volume / self.cross_section_area

            self.cross_section_polygon = self.create_polygon_square(self.height)

            LOGGER.info(
                f"{self.log_id} Geometry created - Square section with flat tails:"
                f" \u2B1C H x L = \u2B1C {self.height:4g} x {self.length:4g} mm,"
                f" A = {self.cross_section_area / 1e6:4g} m2,"
                f" V = {self._volume / 1e9:4g} m3."
            )
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise

    def _square_73(self):
        """Create 3D geometry of rectangular section with chamfers."""
        try:
            self.height = self._parameters["side_of_square"]
            self.width = self.height
            diagonal = self._parameters["diagonal"]

            # --------------------------------
            # Check diagonal
            # minimum diagonal is

            min_diagonal = math.sqrt(0.5) * self.height
            if diagonal < min_diagonal:
                LOGGER.error(
                    "Error: Geometry class failed to create 3D model."
                    f" User wants to build a square section \u2B1C H = \u2B1C {self.height:4g} mm with"
                    f" chamfers, defined by diagonal {diagonal:4g} mm, but minimum possible diagonal for given"
                    f" square section is {min_diagonal:4g} mm."
                )
                return

            chamfer_h = math.sqrt(2) / 2 * (math.sqrt(2) * self.height - diagonal)
            self.cross_section_area = self.height ** 2 - 2 * chamfer_h ** 2
            self.length = self._volume / self.cross_section_area

            self.cross_section_polygon = self.create_polygon_chamfered_square(self.height, diagonal, diagonal)

            LOGGER.info(
                f"{self.log_id} Geometry created - Slab with chamfered square section and flat tails:"
                f" \u2B1C H x L = \u2B1C {self.height:4g} x {self.length:4g} mm,"
                f" diagonal = {diagonal:4g} mm,"
                f" chamfer = {chamfer_h:4g} mm x 45\u00b0,"
                f" A = {self.cross_section_area / 1e6:4g} m2,"
                f" V = {self._volume / 1e9:4g} m3."
            )
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise

    def _square_74(self):
        """Create 3D geometry of slab with square section with length to section-height ratio L/H."""
        try:
            length_to_side_ratio = self._parameters["length_to_side_ratio"]
            if length_to_side_ratio < 0.0:
                LOGGER.error(
                    "Error: Geometry class failed to create 3D model."
                    " User wants to build a slab with square section with length to section-height ratio L/H <= 0.")
                return

            self.length = math.cbrt(length_to_side_ratio ** 2 * self._volume)
            self.height = self.length / length_to_side_ratio
            self.width = self.height
            self.cross_section_area = self.height ** 2

            self.cross_section_polygon = self.create_polygon_square(self.height)

            LOGGER.info(
                f"{self.log_id} Geometry created - Slab with square section with length to section-height ratio L/\u2B1CH:"
                f" \u2B1C H x L = \u2B1C {self.height:4g} x {self.length:4g} mm,"
                f" A = {self.cross_section_area / 1e6:4g} m2,"
                f" V = {self._volume / 1e9:4g} m3."
            )
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise

    def _rectangle_75(self):
        """Create 3D geometry of rectangular section with flat trails."""
        try:
            self.height = self._parameters["height"]
            self.width = self._parameters["width"]

            if self.height < 0.0:
                LOGGER.error(
                    "Error: Geometry class failed to create 3D model."
                    " User wants to build a slab with rectangle section with height H <= 0.")
                return

            if self.width < 0.0:
                LOGGER.error(
                    "Error: Geometry class failed to create 3D model."
                    " User wants to build a slab with rectangle section with width W <= 0.")
                return

            self.length = self._volume / self.height / self.width
            self.cross_section_area = self.height * self.width

            self.cross_section_polygon = self.create_polygon_rectangle(self.height, self.width)

            LOGGER.info(
                f"{self.log_id} Geometry created - Rectangular section with flat tails:"
                f" H x W x L = {self.height:4g} x {self.width:4g} x {self.length:4g} mm,"
                f" A = {self.cross_section_area / 1e6:4g} m2,"
                f" V = {self._volume / 1e9:4g} m3."
            )
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise

    def _rectangle_76(self):
        """
        Create 3D geometry of slab with rectangular section with defined section-height to section-width ratio H/W.
        """
        try:
            height_to_width_ratio = self._parameters["height_to_width_ratio"]
            length_to_thickness_ratio = self._parameters["length_to_thickness_ratio"]

            if height_to_width_ratio < 0.0:
                LOGGER.error(
                    "Error: Geometry class failed to create 3D model."
                    " User wants to build a slab with rectangular section"
                    " with defined section-height to section-width ratio H/W <= 0.")
                return

            if length_to_thickness_ratio < 0.0:
                LOGGER.error(
                    "Error: Geometry class failed to create 3D model."
                    " User wants to build a slab with rectangular section"
                    " with defined length to section-thickness ratio L/Thickness <= 0.")
                return

            if height_to_width_ratio > 1.0:
                _w = math.cbrt(self._volume / height_to_width_ratio / length_to_thickness_ratio)
                _h = _w * height_to_width_ratio
                _l = _w * length_to_thickness_ratio
            else:
                _h = math.cbrt(self._volume * height_to_width_ratio / length_to_thickness_ratio)
                _w = _h / height_to_width_ratio
                _l = _h * length_to_thickness_ratio

            self.height = _h
            self.width = _w
            self.length = _l
            self.cross_section_area = _h * _w

            self.cross_section_polygon = self.create_polygon_rectangle(self.height, self.width)

            LOGGER.info(
                f"{self.log_id} Geometry created - Slab with square section with length to section-height ratio L/\u2B1CH:"
                f" \u2B1C H x L = \u2B1C {self.height:4g} x {self.length:4g} mm,"
                f" A = {self.cross_section_area / 1e6:4g} m2,"
                f" V = {self._volume / 1e9:4g} m3."
            )
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise

    def _rectangle_77(self):
        """Create 3D geometry of rectangular section with chamfers."""
        try:
            self.height = self._parameters["height"]
            self.width = self._parameters["width"]
            diagonal = self._parameters["diagonal"]

            # --------------------------------
            # Check diagonal
            # minimum diagonal is

            _min_size, _max_size = sorted([self.height, self.width])
            min_diagonal = math.sqrt(_max_size * (_max_size + math.sqrt(_max_size ** 2 - _min_size ** 2)) / 2)
            max_diagonal = math.sqrt(self.height ** 2 + self.width ** 2)

            if diagonal < min_diagonal:
                LOGGER.error(
                    "Error: Geometry class failed to create 3D model."
                    f" User wants to build rectangular section H x W = {self.width:4g}x{self.height:4g} mm with"
                    f" chamfers, defined by diagonal {diagonal:4g} mm, but minimum possible diagonal for given"
                    f" H x W is {min_diagonal:4g} mm."
                )
                return

            half_width = self.width / 2
            half_height = self.height / 2

            if diagonal >= max_diagonal:  # No chamfer - Sharp corner
                chamfer_x, chamfer_y = half_width, half_height
                chamfer_height = 0.0
                chamfer_width = 0.0
                chamfer_angle = 0.0
            else:
                # Define the system of equations
                _d = diagonal / 2
                _a = 4 * (_d ** 2 - half_height ** 2)
                _b = half_height ** 2 - half_width ** 2

                def equations(_vars):
                    x, y = _vars
                    eq1 = (half_width - x) ** 2 + (half_height - y) ** 2 - 4 * x ** 2 + _a
                    eq2 = x ** 2 - y ** 2 + _b
                    return [eq1, eq2]

                # Solve the system of equations
                x0 = np.array([0, 0])  # initial guess
                root: np.ndarray = fsolve(equations, x0)[0]

                chamfer_x, chamfer_y = root.tolist()
                chamfer_height = half_height - chamfer_y
                chamfer_width = half_width - chamfer_x
                chamfer_angle = math.atan(chamfer_width / chamfer_height)

            self.cross_section_area = self.height * self.width - 2 * chamfer_height * chamfer_width
            self.length = self._volume / self.cross_section_area

            if diagonal >= max_diagonal:  # No chamfer - Sharp corner
                self.cross_section_polygon = Polygon([
                    [half_width, half_height],
                    [half_width, -half_height],
                    [-half_width, -half_height],
                    [-half_width, half_height],
                ])
                LOGGER.info(
                    f"{self.log_id} Geometry created - Slab with flat tails:"
                    f" H x W x L = {self.height:4g} x {self.width:4g} x {self.length:4g} mm,"
                    f" A = {self.cross_section_area / 1e6:4g} m2,"
                    f" V = {self._volume / 1e9:4g} m3."
                )
            else:
                self.cross_section_polygon = Polygon([
                    [chamfer_x, half_height],
                    [half_width, chamfer_y],
                    [half_width, -chamfer_y],
                    [chamfer_x, -half_height],
                    [-chamfer_x, -half_height],
                    [-half_width, -chamfer_y],
                    [-half_width, chamfer_y],
                    [-chamfer_x, half_height],
                ])
                LOGGER.info(
                    f"{self.log_id} Geometry created - Slab with chamfers and flat tails:"
                    f" H x W x L = {self.height:4g} x {self.width:4g} x {self.length:4g} mm,"
                    f" diagonal = {diagonal:4g} mm,"
                    f" chamfer = {chamfer_height:4g} x {chamfer_width:4g} mm,"
                    f" chamfer angle = {chamfer_angle * 180 / math.pi:4g}\u00b0,"
                    f" A = {self.cross_section_area / 1e6:4g} m2,"
                    f" V = {self._volume / 1e9:4g} m3."
                )
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise

    def _rectangle_78(self):
        """Create 3D geometry of rectangular section with chamfers."""
        try:
            self.height = self._parameters["height"]
            self.width = self._parameters["width"]
            diagonals = (self._parameters["diagonal_1"], self._parameters["diagonal_2"])

            _min_size, _max_size = sorted([self.height, self.width])
            min_diagonal = math.sqrt(_max_size * (_max_size + math.sqrt(_max_size ** 2 - _min_size ** 2)) / 2)
            max_diagonal = math.sqrt(self.height ** 2 + self.width ** 2)

            if any([diagonal < min_diagonal for diagonal in diagonals]):
                LOGGER.error(
                    "Error: Geometry class failed to create 3D model."
                    f" User wants to build rectangular section H x W = {self.width:4g}x{self.height:4g} mm with"
                    f" chamfers, defined by diagonals {diagonals[0]:4g} and {diagonals[1]:4g} mm,"
                    f" but minimum possible diagonal for given section H x W is {min_diagonal:4g} mm."
                )
                return

            # Define the system of equations
            half_width = self.width / 2
            half_height = self.height / 2

            is_chamfer, chamfer_x, chamfer_y, chamfer_height, chamfer_width, chamfer_angle = [], [], [], [], [], []
            for i, diagonal in enumerate(diagonals):
                if diagonal >= max_diagonal:  # No chamfer - Sharp corner
                    is_chamfer.append(False)
                    chamfer_x.append(half_width)
                    chamfer_y.append(half_height)
                    chamfer_height.append(0.0)
                    chamfer_width.append(0.0)
                    chamfer_angle.append(0.0)
                else:
                    is_chamfer.append(True)
                    _d = diagonal / 2
                    _a = 4 * (_d ** 2 - half_height ** 2)
                    _b = half_height ** 2 - half_width ** 2

                    def equations(_vars):
                        x, y = _vars
                        eq1 = (half_width - x) ** 2 + (half_height - y) ** 2 - 4 * x ** 2 + _a
                        eq2 = x ** 2 - y ** 2 + _b
                        return [eq1, eq2]

                    # Solve the system of equations
                    x0 = np.array([0, 0])  # initial guess
                    root = fsolve(equations, x0)
                    chamfer_x.append(root[0])
                    chamfer_y.append(root[1])
                    chamfer_height.append(half_height - chamfer_y[i])
                    chamfer_width.append(half_width - chamfer_x[i])
                    chamfer_angle.append(math.atan(chamfer_width[i] / chamfer_height[i]))

            self.cross_section_area = (
                    self.height * self.width
                    - chamfer_height[0] * chamfer_width[0]
                    - chamfer_height[1] * chamfer_width[1])
            self.length = self._volume / self.cross_section_area

            if all(is_chamfer):
                self.cross_section_polygon = Polygon([
                    [chamfer_x[0], half_height],
                    [half_width, chamfer_y[0]],
                    [half_width, -chamfer_y[1]],
                    [chamfer_x[1], -half_height],
                    [-chamfer_x[0], -half_height],
                    [-half_width, -chamfer_y[0]],
                    [-half_width, chamfer_y[1]],
                    [-chamfer_x[1], half_height],
                ])
                LOGGER.info(
                    f"{self.log_id} Geometry created - Slab with rectangular chamfered section"
                    " with different diagonals and with flat tails:"
                    f" H x W x L = {self.height:4g} x {self.width:4g} x {self.length:4g} mm,"
                    f" diagonal #1  = {diagonals[0]:4g} mm,"
                    f" chamfer #1 = {chamfer_height[0]:4g} x {chamfer_width[0]:4g} mm,"
                    f" chamfer # 1 angle = {chamfer_angle[0] * 180 / math.pi:4g}\u00b0,"
                    f" diagonal #2 = {diagonals[1]:4g} mm,"
                    f" chamfer #2 = {chamfer_height[1]:4g} x {chamfer_width[1]:4g} mm,"
                    f" chamfer #2 angle = {chamfer_angle[1] * 180 / math.pi:4g}\u00b0,"
                    f" A = {self.cross_section_area / 1e6:4g} m2,"
                    f" V = {self._volume / 1e9:4g} m3."
                )
            elif is_chamfer[0]:
                self.cross_section_polygon = Polygon([
                    [chamfer_x[0], half_height],
                    [half_width, chamfer_y[0]],
                    [half_width, -half_height],
                    [-chamfer_x[0], -half_height],
                    [-half_width, -chamfer_y[0]],
                    [-half_width, half_height],
                ])
                LOGGER.info(
                    f"{self.log_id} Geometry created - Slab with rectangular chamfered section"
                    " with two chamfered and two sharp corners and with flat tails:"
                    f" H x W x L = {self.height:4g} x {self.width:4g} x {self.length:4g} mm,"
                    f" diagonal #1  = {diagonals[0]:4g} mm,"
                    f" chamfer #1 = {chamfer_height[0]:4g} x {chamfer_width[0]:4g} mm,"
                    f" chamfer # 1 angle = {chamfer_angle[0] * 180 / math.pi:4g}\u00b0,"
                    f" chamfer #2 is zero (shapr corners),"
                    f" A = {self.cross_section_area / 1e6:4g} m2,"
                    f" V = {self._volume / 1e9:4g} m3."
                )
            elif is_chamfer[1]:
                self.cross_section_polygon = Polygon([
                    [half_width, half_height],
                    [half_width, -chamfer_y[1]],
                    [chamfer_x[1], -half_height],
                    [-half_width, -half_height],
                    [-half_width, chamfer_y[1]],
                    [-chamfer_x[1], half_height],
                ])
                LOGGER.info(
                    f"{self.log_id} Geometry created - Slab with rectangular chamfered section"
                    " with different diagonals and with flat tails:"
                    f" H x W x L = {self.height:4g} x {self.width:4g} x {self.length:4g} mm,"
                    f" chamfer #1 is zero (shapr corners),"
                    f" diagonal #2 = {diagonals[1]:4g} mm,"
                    f" chamfer #2 = {chamfer_height[1]:4g} x {chamfer_width[1]:4g} mm,"
                    f" chamfer #2 angle = {chamfer_angle[1] * 180 / math.pi:4g}\u00b0,"
                    f" A = {self.cross_section_area / 1e6:4g} m2,"
                    f" V = {self._volume / 1e9:4g} m3."
                )
            else:
                self.cross_section_polygon = Polygon([
                    [half_width, half_height],
                    [half_width, -half_height],
                    [-half_width, -half_height],
                    [-half_width, half_height],
                ])
                LOGGER.info(
                    f"{self.log_id} Geometry created - Slab with flat tails:"
                    f" H x W x L = {self.height:4g} x {self.width:4g} x {self.length:4g} mm,"
                    f" A = {self.cross_section_area / 1e6:4g} m2,"
                    f" V = {self._volume / 1e9:4g} m3."
                )

            LOGGER.info(
                f"{self.log_id} Geometry created - Slab with rectangular chamfered section"
                " with different diagonals and with flat tails:"
                f" H x W x L = {self.height:4g} x {self.width:4g} x {self.length:4g} mm,"
                f" diagonal #1  = {diagonals[0]:4g} mm,"
                f" chamfer #1 = {chamfer_height[0]:4g} x {chamfer_width[0]:4g} mm,"
                f" chamfer # 1 angle = {chamfer_angle[0] * 180 / math.pi:4g}\u00b0,"
                f" diagonal #2 = {diagonals[1]:4g} mm,"
                f" chamfer #2 = {chamfer_height[1]:4g} x {chamfer_width[1]:4g} mm,"
                f" chamfer #2 angle = {chamfer_angle[1] * 180 / math.pi:4g}\u00b0,"
                f" A = {self.cross_section_area / 1e6:4g} m2,"
                f" V = {self._volume / 1e9:4g} m3."
            )
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise

    def _octagon_79(self):
        """Create 3D geometry of octagon section with flat tails."""
        try:
            self.height = self._parameters["height"]
            self.width = self.height

            chamfer_h = self.height * (1 - math.sqrt(2) / 2)

            self.cross_section_area = self.height ** 2 - 2 * chamfer_h ** 2
            self.length = self._volume / self.cross_section_area

            self.cross_section_polygon = self.create_polygon_chamfered_square(self.height, self.height, self.height)

            LOGGER.info(
                f"{self.log_id} Geometry created - Octagon and flat tails:"
                f" \u2BC3 H x L = \u2BC3 {self.height:4g} x {self.length:4g} mm,"
                f" A = {self.cross_section_area / 1e6:4g} m2,"
                f" V = {self._volume / 1e9:4g} m3."
            )
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise

    @property
    def log_id(self):
        duration = str(round(time.monotonic() - self.time_start, 2))
        return f"[{self.pvid}][{self.eo}/{self.eo_last}] Pre/Geom #{self.worker_id} Duration {duration}s {traceback.format_exc()}"
