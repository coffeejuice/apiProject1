import logging
import traceback
import os
import math
import shutil
import sys
import time

import numpy as np
from scipy.optimize import fsolve
import gmsh
from re import split

from forgelab.common.shapely_2d_funcs import binary_to_list_of_tuples
from forgelab.config import config
from forgelab.common.read_deform_keyfile import VARIABLES
from forgelab.srv_solver.pre_functions import \
    automatic_modification_of_parameters_in_lines, deform_mesh_settings, remove_old_operation_files


LOGGER = logging.getLogger(__name__)


class BilletGeometry:
    """Create 3D geometry object."""

    file_1 = dict(
        parameters=dict(
            cogging_remeshing_interference_depth_relative=dict(
                s="RMDPTH       1   -6.8150100000E-001", k=[0, 1], n=2, f="\t{:>-21.10E}"),
            cogging_remeshing_maximum_stroke_increment=dict(
                s="RMSTRK       1    1.0054100000E+003", k=[0, 1], n=2, f="\t{:>-21.10E}"),
            cogging_remeshing_maximum_time_increment=dict(
                s="RMTIME       1    8.4564100000E+003", k=[0, 1], n=2, f="\t{:>-21.10E}"),
            cogging_remeshing_maximum_step_increment=dict(
                s="RMSTEP       1    8.6520000000E+003", k=[0, 1], n=2, f="\t{:>-21.10E}"),
            cogging_remeshing_absolute_size_ratio=dict(
                s="MGSIZR       1    2.3108000000E+000", k=[0, 1], n=2, f="\t{:>-21.10E}"),
            cogging_remeshing_number_of_surface_elements=dict(
                s="MGNELM       1      93   32000     100       0", k=[0, 1], n=2, f="\t{:8d}"),
            cogging_remeshing_weighting_factor_boundary_curvature=dict(
                s="MGWCUV       1    4.6900000000E-001", k=[0, 1], n=2, f="\t{:>-21.10E}"),
            cogging_remeshing_weighting_factor_temperature=dict(
                s="MGWTMP       1    3.4000000000E-002", k=[0, 1], n=2, f="\t{:>-21.10E}"),
            cogging_remeshing_weighting_factor_strain=dict(
                s="MGWSTN       1    2.2100000000E-001", k=[0, 1], n=2, f="\t{:>-21.10E}"),
            cogging_remeshing_weighting_factor_strain_rate=dict(
                s="MGWSTR       1    2.8900000000E-001", k=[0, 1], n=2, f="\t{:>-21.10E}"),
            cogging_remeshing_inverse_max_element_size=dict(
                s="MGWUSR       1    0.0000000000E+000    2.2727272727E-003       0",
                k=[0, 1], n=3, f="\t{:>-21.10E}"),
        )
    )

    _input_key_file_template = ["""
*
*  DEFORM-3D V11.0 (Service Pack 2)   KEYWORD FILE (Qt)
*
*
*  Data for Object #     1
*
OBJTYP       1       2       0
OBJNAM       1
Workpiece
AVGSTR       1    1.0000000000E+000
LMTSTR       1    1.0000000000E-002
PENVOL       1    1.0000000000E+006
REFTMP       1    2.0000000000E+001
TMPLMT       1    0.0000000000E+000
ROTSYM       1    0.0000000000E+000
    0.0000000000E+000    0.0000000000E+000    0.0000000000E+000
    0.0000000000E+000    0.0000000000E+000    0.0000000000E+000
TRGVOL       1       0    0.0000000000E+000
ELPSOL       1       2
OTPRNG       1       0    0.0000000000E+000    0.0000000000E+000       0
PRSNAM       1

MOVCTL       1       1       0    0.0000000000E+000    0.0000000000E+000   -1.0000000000E+000    0.0000000000E+000
STROKE       1    0.0000000000E+000    0.0000000000E+000    0.0000000000E+000
FORCE        1    0.0000000000E+000    0.0000000000E+000    0.0000000000E+000
ANGMOV       1       1       0    0.0000000000E+000
CNTRAX       1   -7.5000000000E+002    0.0000000000E+000    0.0000000000E+000    0.0000000000E+000    0.0000000000E+000    0.0000000000E+000    0.0000000000E+000
ANGMO2       1       1       0    0.0000000000E+000
CNTRA2       1   -7.5000000000E+002    0.0000000000E+000    0.0000000000E+000    0.0000000000E+000    0.0000000000E+000    0.0000000000E+000    0.0000000000E+000
OBJUPD       1       0
* --------------- START OF INSERTING POINT ---------------""",

"""* --------------- END OF INSERTING POINT ---------------
DRZ          1       0    0.0000000000E+000
DRMESH       1       0    0.0000000000E+000
BCCDEF       1       0       0
BCCDFN       1       0       0
URZ          1       0    0.0000000000E+000
FRZ          1       0    0.0000000000E+000
PRZ          1       0    0.0000000000E+000
BCCTMP       1       0       0
BCCTFN       1       0       0
NDTMP        1       0    2.0000000000E+001
NDHEAT       1       0    0.0000000000E+000
NDFLUX       1       0    0.0000000000E+000
* --------------- START OF INSERTING POINT ---------------""",

"""* --------------- END OF INSERTING POINT ---------------
MTLGRP       1       0       1
STRAIN       1       0    0.0000000000E+000
STNCMP       1       0       6    0.0000000000E+000
DENSTY       1       0    1.0000000000E+000
DAMAGE       1       0    0.0000000000E+000
STRESS       1       0    0.0000000000E+000
YLDS         1       0    0.0000000000E+000
* --------------- START OF INSERTING POINT ---------------""",

"""* --------------- END OF INSERTING POINT ---------------
RMDPTH       1   -7.0000000000E-001
RMSTRK       1    0.0000000000E+000
RMTIME       1    0.0000000000E+000
RMSTEP       1    0.0000000000E+000
MGSIZR       1    2.3450000000E+000
MGWTMP       1    0.0000000000E+000
MGWSTN       1    2.5000000000E-001
MGWSTR       1    2.5000000000E-001
MGNELM       1     624   32000     100       0
MGTELM       1       4
MGWCUV       1    5.0000000000E-001
MGGRID       1      25      25
MGERR        1    1.0000000000E-002    3.2000000000E+001
MGWUSR       1    0.0000000000E+000    4.3179347146E-003       0
FRCSTP       1       0
FRCNEL       1       0
FRCMTH       1       0
CRPTIM       1       0
DATOM        1       0    0.0000000000E+000
HDNEST       1       0       0    0.0000000000E+000    0.0000000000E+000
HDNOBJ       1       0    0.0000000000E+000
BCCCRB       1       0       0
CRBFLX       1       0    0.0000000000E+000
VOTAGE       1       0    0.0000000000E+000
BCCRHT       1       0       0
RHTFLX       1       0    0.0000000000E+000
CSFREQ       1       0    0.0000000000E+000
VOLCRG       1       0    0.0000000000E+000
ZEFI         1       0    0.0000000000E+000
ZMFI         1       0    0.0000000000E+000
CURRNT       1       0    0.0000000000E+000
ECCDEF       1       0       0
ECDEFN       1       0       0
ECPRES       1       0    0.0000000000E+000
ECCTMP       1       0       2
ECTMFN       1       0       0
ECHFLX       1       0    0.0000000000E+000
ECCATM       1       0       2
ECATFN       1       0       0
ECAFLX       1       0    0.0000000000E+000
ECCRHT       1       0       0
ECRHFN       1       0       0
ECRFLX       1       0    0.0000000000E+000
NWEAR        1       0    0.0000000000E+000
OPSTOP       1       0       0"""]

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

    def __init__(self, _param: dict):

        self.param: dict = _param
        self.row: dict = {}
        self.pvid: int = 0
        self.eo: int = 0

        self._type_id: int = 0
        self._labels: list = []
        self._values: list = []

        self._volume: float = 0.0
        self._height: float = 0.0
        self._width: float = 0.0
        self._length: float = 0.0

        self._mesh_absolute_min_element_size: float = 0.0
        self._mesh_relative_min_element_size: float = 0.0
        self._mesh_element_size_ratio: float = 0.0

        self._temperature: float = 0.0

        self._nodes: list[float] = []
        self._elements: list[int] = []

        self._numpy_nodes: np.ndarray = np.array([])
        self._numpy_elements: np.ndarray = np.array([])

        self._output_key_file: list[str] = []

        self._parameters: dict = {}

    def run(self):
        """Build geometry object based on self._type_id and self._parameters."""
        try:
            self.row = self.param['table'][self.eo]
            self.eo = self.param['project']['execution_order']
            self.pvid = self.param['project']['process_version_id']

            local_dir: str = config.server['local_dir']
            operation_relative_path: str = self.param['operation']['sub_operation_relative_path']
            billet_extract_relative_path: str = self.param['operation']['billet_file_sub_operation_extract_relative_path']
            key_file_extract_abs_path = os.path.join(local_dir, operation_relative_path, 'EXPORT_LAST_STEP.KEY')
            billet_extract_abs_path = os.path.join(local_dir, billet_extract_relative_path)

            LOGGER.info(f"{self.log_id} STARTED BilletGeometry")

            # ==============================================================================================
            self.initialize_input_billet_parameters()
            self.call_gmsh()
            self.assert_output_billet_parameters()
            self._output_key_file = self._modify_billet_key()

            self.param['operation'] |= {
                'last_step_number': 0,
                'mesh_number': 1,
                'global_time': 0.0}
            # row = {
            #     'initial_height': self._height,
            #     'initial_width': self._width,
            #     'initial_length': self._length,
            #     'final_height': self._height,
            #     'final_width': self._width,
            #     'final_length': self._length}

            # get_flow_net_center(self._output_key_file, row, self.param)
            self._create_billet_export_path()
            self.save_key_file(billet_extract_abs_path)
            shutil.copy(billet_extract_abs_path, key_file_extract_abs_path)

            # ==============================================================================================
            LOGGER.info(f"{self.log_id} FINISHED BilletGeometry")

        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise

    def initialize_input_billet_parameters(self):
        """Initialize parameters of geometry object."""
        # LOGGER.info("START: func 'initialize_input_billet_parameters'")
        try:
            local_dir = config.server['local_dir']
            sub_operation_relative_path = self.param['operation']['sub_operation_relative_path']
            sub_operation_path = os.path.join(local_dir, sub_operation_relative_path)

            remove_old_operation_files(sub_operation_path)

            type_id = self.row['type_id']
            labels, values = self.param['type_id_nnn']
            volume: float = self.row['volume_initial']
            relative_min_element_size = self.param['operation']['relative_min_element_size']
            element_size_ratio: float = self.param['operation']['element_size_ratio']
            temperature: float = 20.0

            self.param['operation'] |= {
                # 'min_element_size': min_element_size,
                # 'element_size_ratio': element_size_ratio,
                'temperature': temperature}

            result = False
            if self._set_type_id(type_id):
                if self._set_labels(labels):
                    if self._set_values(values):
                        if self._set_volume(volume):
                            if self._set_mesh(relative_min_element_size, element_size_ratio):
                                if self._set_temperature(temperature):
                                    result = True
            assert result, "Missed or Wrong Input parameters for Billet key file generation"
        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise

    def call_gmsh(self):
        """Call gmsh to create 3D model of billet."""
        try:
            _type = self._type_id
            # rounds
            if _type == 68:
                self._round_68()  # Round D, flat tails
            elif _type == 69:
                self._round_69()  # Round D, rounded tails
            elif _type == 70:
                self._round_70()  # Round D, chamfered tails
            elif _type == 71:
                self._round_71()
            # squares
            elif _type == 72:
                self._extruded_polygon_by_length__then_scaled_to_fit_volume()
            elif _type == 73:
                self._square_73()
            elif _type == 74:
                self._extruded_polygon_by_length__then_scaled_to_fit_volume()
            # rectangles
            elif _type == 75:
                self._extruded_polygon_by_length__then_scaled_to_fit_volume()
            elif _type == 76:
                self._extruded_polygon_by_length__then_scaled_to_fit_volume()
            elif _type == 77:
                self._extruded_polygon_by_length__then_scaled_to_fit_volume()
            elif _type == 78:
                self._extruded_polygon_by_length__then_scaled_to_fit_volume()
            # octagons
            elif _type == 79:
                self._octagon_79()
            else:
                LOGGER.error(f"{self.log_id} Error: Unknown geometry type '{_type}' for Geometry class")
        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise

    def assert_output_billet_parameters(self):
        assert self._height and self._height > 0.0, ("Error: Geometry class failed to create 3D model. "
                                                     "Billet height is negative or not defined.")
        assert self._width and self._width > 0.0, ("Error: Geometry class failed to create 3D model. "
                                                   "Billet width is negative or not defined.")
        assert self._length and self._length > 0.0, ("Error: Geometry class failed to create 3D model. "
                                                     "Billet length is negative or not defined.")

    def _finalize_gmsh(self):
        try:
            for _l in gmsh.logger.get():
                if 'error' in _l.lower() or 'warning' in _l.lower():
                    LOGGER.info(_l)
            gmsh.logger.stop()
            gmsh.finalize()
        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise

    def _create_billet_export_path(self):
        try:
            local_dir: str = config.server['local_dir']
            billet_extract_path: str = self.param['operation']['billet_file_sub_operation_extract_relative_path']
            _file = os.path.join(local_dir, billet_extract_path)
            _dir = os.path.dirname(_file)

            if os.path.exists(_file):
                shutil.rmtree(_dir, ignore_errors=True)
                LOGGER.info(f"Removed dir '{_dir}'")
            if not os.path.exists(_dir):
                os.makedirs(_dir)

        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise

    def _set_type_id(self, type_id: int) -> bool:
        """Set type_id of geometry object. type_id is used to identify the geometry object."""
        try:
            is_set = False
            if isinstance(type_id, int):
                if type_id in self._parameters_map:
                    self._type_id = type_id
                    is_set = True

            return is_set

        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise

    def _set_labels(self, labels: list) -> bool:
        """Set labels of geometry object. Order of labels is important to read parameters in right order."""
        try:
            is_set = False
            if isinstance(labels, (list, tuple, set,)):
                if labels:
                    if self._type_id in self._parameters_map:
                        _labels_set = labels if isinstance(labels, set) else set(labels)
                        _labels_pattern = set(self._parameters_map[self._type_id]['labels'])
                        if _labels_set == _labels_pattern:
                            self._labels = labels
                            is_set = True
            return is_set

        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise

    def _set_values(self, values: list) -> bool:
        try:
            is_set = False
            if isinstance(values, (list, tuple, set,)):
                if values:
                    if self._type_id in self._parameters_map:
                        if self._labels:
                            if len(values) == len(self._labels):
                                self._values = values
                                for label, parameter in zip(self._labels, self._values):
                                    self._parameters[label] = parameter
                                is_set = True
            return is_set
        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            values_str = ', '.join([f"{v:4g}" for v in values]) if values else '[]'
            raise RuntimeError(f"FAILED setting values '{values_str}'")

    def _set_volume(self, volume: float) -> bool:
        try:
            is_set = False
            if isinstance(volume, float):
                if volume > 0.:
                    self._volume = volume
                    is_set = True
            return is_set
        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError(f"FAILED setting volume '{volume}'")

    def _set_mesh(self, relative_min_element_size: float, element_size_ratio: float) -> bool:
        try:
            is_set = False
            if isinstance(relative_min_element_size, float):
                if isinstance(element_size_ratio, float):
                    if relative_min_element_size > 0.:
                        if element_size_ratio > 0.:
                            self._mesh_relative_min_element_size = relative_min_element_size
                            self._mesh_element_size_ratio = element_size_ratio
                            is_set = True
            return is_set
        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError(f"FAILED setting mesh parameters '{relative_min_element_size}', '{element_size_ratio}'")

    def _set_temperature(self, temperature: float):
        try:
            is_set = False
            if isinstance(temperature, float):
                if temperature > -273.15:
                    self._temperature = temperature
                    is_set = True
            return is_set
        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError(f"FAILED setting temperature '{temperature}'")

    def get_labels(self, type_id: int = None) -> tuple:
        """
        Return labels of geometry object for type_id argument, if argument is given.
        Otherwise, return labels of geometry.

        :param type_id: int
        :return: tuple
        """

        # There is no argument. Return labels for geometry object
        try:
            result = tuple()
            if type_id is None:
                if self._type_id in self._parameters_map:
                    result = self._parameters_map.get(self._type_id).get('labels')

            # Return labels for argument type_id
            elif isinstance(type_id, int):
                if type_id in self._parameters_map:
                    result = self._parameters_map.get(type_id).get('labels')
            return result
        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError(f"FAILED getting labels for type_id '{type_id}'")

    def get_key_file(self):
        """Return a string, containing DEFORM's KEY-file with geometry and mesh of the object."""
        # return self._read_lines_from_file(self._geometry_file_name)
        return self._output_key_file

    def save_key_file(self, file_path: str):
        """Write a string, containing DEFORM's KEY-file with geometry and mesh of the object, to a file."""
        try:
            is_saved = False
            if isinstance(file_path, str):
                if file_path:
                    _abs_path = os.path.normpath(file_path)
                    _list = _abs_path.split(os.sep)
                    _path = os.sep.join(_list[:-1])
                    os.makedirs(_path, exist_ok=True)
                    if os.path.isabs(_path):
                        self._write_lines_to_file(_abs_path, self._output_key_file)
                        is_saved = True
            return is_saved
        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError(f"FAILED saving file '{file_path}'")

    def _round_68(self):
        """Create 3D geometry of rectangular section with chamfers."""
        # LOGGER.info("START: func '_round_68'")
        try:
            self._diameter = self._parameters['diameter']

            assert self._diameter > 0.0, "Diameter D <= 0."

            radius = self._diameter / 2
            self._width = self._diameter
            self._height = self._diameter
            cross_section_area = math.pi * self._diameter ** 2 / 4
            self._length = self._volume / cross_section_area

            LOGGER.info(f"{self.log_id} Info: Geometry created - Cylinder with flat tails: "
                        f"total dimensions D x L = {self._diameter:4g} x {self._length:4g} mm, "
                        f"area of cross-section = {cross_section_area / 1e6:4g} m2, "
                        f"volume = {self._volume / 1e9:4g} m3.")

            # gmsh_nodes, gmsh_elements = tuple(), tuple()
            self._initialize_gmsh()

            half_l = self._length / 2
            gmsh.model.occ.addCylinder(-half_l, 0, 0, self._length, 0, 0, radius)
            gmsh.model.occ.synchronize()
            self._make_mesh()
            gmsh_nodes, gmsh_elements = self._get_mesh()
            self._finalize_gmsh()

            _nodes, _elements = self._gmsh_mesh_to_numpy(gmsh_nodes, gmsh_elements)

            centroid = self._get_bounds_centroid(self._get_mesh_bounds(_nodes))

            def mesh_volume(linear_coefficient: np.ndarray) -> np.ndarray:
                _scaled_nodes = self._scale_yz_coordinates(_nodes, linear_coefficient, centroid)
                _vol = self._get_mesh_volume(_scaled_nodes, _elements)
                delta_volume = _vol - self._volume
                return np.asarray([delta_volume])

            # Solve the system of equations
            x0 = np.array([1.0])  # initial guess
            root = fsolve(mesh_volume, x0)[0]

            scaled_coordinates = self._scale_yz_coordinates(_nodes, root, centroid)

            self._nodes, self._elements = self._numpy_mesh_to_list(scaled_coordinates, _elements)
            self._numpy_nodes, self._numpy_elements = scaled_coordinates, _elements

        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError(f"FAILED creating '_round_68' geometry with diameter '{self._diameter}'")

    def _round_69(self):
        """Create 3D geometry of rectangular section with chamfers."""
        # LOGGER.info("START: func '_round_69'")
        try:
            self._diameter = self._parameters['diameter']
            self._tail_radius = self._parameters['tail_radius']

            assert self._diameter > 0.0, "Diameter D <= 0."
            assert self._tail_radius > 0.0, "Tail radius R <= 0."

            radius = self._diameter / 2
            self._width = self._diameter
            self._height = self._diameter
            cross_section_area = math.pi * self._diameter ** 2 / 4
            tr = self._tail_radius
            b = radius - tr
            v = self._volume
            vr = math.pi / 6 * tr * (4 * tr ** 2 + 3 * math.pi * tr * b + 6 * b ** 2)
            v_m = v - 2 * vr
            self._length = (v_m + 2 * math.pi * tr * radius ** 2) / (math.pi * radius ** 2)

            LOGGER.info(f"Info: Geometry created - Cylinder with rounded edges: "
                        f"total dimensions D x L = {self._diameter:4g} x {self._length:4g} mm, "
                        f"edge radius = {self._tail_radius:4g} mm, "
                        f"area of cross-section = {cross_section_area / 1e6:4g} m2, "
                        f"volume = {self._volume / 1e9:4g} m3.")

            self._initialize_gmsh()
            gmsh.option.setNumber("Geometry.OCCParallel", 1)

            half_l = self._length / 2
            tag_cylinder = gmsh.model.occ.addCylinder(-half_l, 0, 0, self._length, 0, 0, radius)

            gmsh.model.occ.synchronize()

            edge_tags = gmsh.model.getBoundary([(3, tag_cylinder)], True, False)
            gmsh.model.occ.fillet([tag_cylinder], [tag for dim, tag in edge_tags], [self._tail_radius])

            gmsh.model.occ.synchronize()

            self._make_mesh()
            gmsh_nodes, gmsh_elements = self._get_mesh()
            self._finalize_gmsh()

            _nodes, _elements = self._gmsh_mesh_to_numpy(gmsh_nodes, gmsh_elements)
            centroid = self._get_bounds_centroid(self._get_mesh_bounds(_nodes))

            def mesh_volume(linear_coefficient: np.ndarray) -> np.ndarray:
                _scaled_nodes = self._scale_yz_coordinates(_nodes, linear_coefficient, centroid)
                _vol = self._get_mesh_volume(_scaled_nodes, _elements)
                delta_volume = _vol - self._volume
                return np.asarray([delta_volume])

            # Solve the system of equations
            x0 = np.array([1.0])  # initial guess
            root = fsolve(mesh_volume, x0)[0]

            scaled_coordinates = self._scale_yz_coordinates(_nodes, root, centroid)

            self._nodes, self._elements = self._numpy_mesh_to_list(scaled_coordinates, _elements)
            self._numpy_nodes, self._numpy_elements = scaled_coordinates, _elements

        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError(f"FAILED creating '_round_69' geometry with diameter {self._diameter} and tail radius {self._tail_radius}")

    def _round_70(self):
        """Create 3D geometry of rectangular section with chamfers."""
        try:
            self._diameter = self._parameters['diameter']
            self._tail_chamfer = self._parameters['tail_chamfer']

            assert self._diameter > 0.0, "Diameter D <= 0."
            assert self._tail_chamfer > 0.0, "Chamfer height <= 0"

            radius = self._diameter / 2
            self._width = self._diameter
            self._height = self._diameter
            cross_section_area = math.pi * self._diameter ** 2 / 4
            chamfer = self._tail_chamfer
            b = radius - chamfer
            chamfer_tail_volume = math.pi / 3 * chamfer * (3 * b ** 2 + 3 * b * chamfer + chamfer ** 2)
            straight_section_volume = self._volume - 2 * chamfer_tail_volume
            self._length = (straight_section_volume + 2 * math.pi * chamfer * radius ** 2) / (math.pi * radius ** 2)

            LOGGER.info(f"Info: Geometry created - Cylinder with chamfered edges: "
                        f"total dimensions D x L = {self._diameter:4g} x {self._length:4g} mm, "
                        f"edge chamfer height = {self._tail_chamfer:4g} mm, "
                        f"area of cross-section = {cross_section_area / 1e6:4g} m2, "
                        f"volume = {self._volume / 1e9:4g} m3.")

            self._initialize_gmsh()
            gmsh.option.setNumber("Geometry.OCCParallel", 1)

            # Create cylinder
            half_l = self._length / 2
            cylinder = gmsh.model.occ.addCylinder(-half_l, 0, 0, self._length, 0, 0, radius)

            gmsh.model.occ.synchronize()

            edge_tags = gmsh.model.getEntities(1)
            surface_tags = gmsh.model.getEntities(2)

            gmsh.model.occ.chamfer(
                [cylinder], [tag for dim, tag in edge_tags],
                [tag for dim, tag in surface_tags],
                [self._tail_chamfer]
            )

            gmsh.model.occ.synchronize()

            self._make_mesh()
            gmsh_nodes, gmsh_elements = self._get_mesh()
            self._finalize_gmsh()

            numpy_nodes, numpy_elements = self._gmsh_mesh_to_numpy(gmsh_nodes, gmsh_elements)
            centroid = self._get_bounds_centroid(self._get_mesh_bounds(numpy_nodes))

            def mesh_volume(linear_coefficient: np.ndarray) -> np.ndarray:
                _scaled_nodes = self._scale_yz_coordinates(numpy_nodes, linear_coefficient, centroid)
                _vol = self._get_mesh_volume(_scaled_nodes, numpy_elements)
                delta_volume = _vol - self._volume
                return np.asarray([delta_volume])

            # Solve the system of equations
            x0 = np.array([1.0])  # initial guess
            root = fsolve(mesh_volume, x0)[0]

            scaled_coordinates = self._scale_yz_coordinates(numpy_nodes, root, centroid)

            self._nodes, self._elements = self._numpy_mesh_to_list(scaled_coordinates, numpy_elements)
            self._numpy_nodes, self._numpy_elements = scaled_coordinates, numpy_elements

        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError(f"FAILED creating '_round_70' geometry with diameter {self._diameter} and tail chamfer {self._tail_chamfer}")

    def _round_71(self):
        """Create 3D geometry of rectangular section with chamfers."""
        # LOGGER.info("START: func '_round_71'")
        try:
            self._length_to_diameter_ratio = self._parameters['length_to_diameter_ratio']

            assert self._length_to_diameter_ratio > 0.0, "L/D <= 0"

            self._length = math.cbrt(4 / math.pi * self._length_to_diameter_ratio ** 2 * self._volume)
            self._diameter = self._length / self._length_to_diameter_ratio
            self._width = self._diameter
            self._height = self._diameter
            radius = self._length / 2
            cross_section_area = math.pi * radius ** 2

            LOGGER.info(f"Info: Geometry created - Cylinder with flat tails: "
                        f"user defined L / D ratio = {self._length_to_diameter_ratio:4g}, "
                        f"total dimensions D x L = {self._diameter:4g} x {self._length:4g} mm, "
                        f"area of cross-section = {cross_section_area / 1e6:4g} m2, "
                        f"volume = {self._volume / 1e9:4g} m3.")

            self._initialize_gmsh()

            half_l = self._length / 2
            gmsh.model.occ.addCylinder(-half_l, 0, 0, self._length, 0, 0, radius)
            gmsh.model.occ.synchronize()
            self._make_mesh()
            gmsh_nodes, gmsh_elements = self._get_mesh()
            self._finalize_gmsh()

            _nodes, _elements = self._gmsh_mesh_to_numpy(gmsh_nodes, gmsh_elements)

            centroid = self._get_bounds_centroid(self._get_mesh_bounds(_nodes))

            def mesh_volume(linear_coefficient: np.ndarray) -> np.ndarray:
                _scaled_nodes = self._scale_yz_coordinates(_nodes, linear_coefficient, centroid)
                _vol = self._get_mesh_volume(_scaled_nodes, _elements)
                delta_volume = _vol - self._volume
                return np.asarray([delta_volume])

            # Solve the system of equations
            x0 = np.array([1.0])  # initial guess
            root = fsolve(mesh_volume, x0)[0]

            scaled_coordinates = self._scale_yz_coordinates(_nodes, root, centroid)

            self._nodes, self._elements = self._numpy_mesh_to_list(scaled_coordinates, _elements)
            self._numpy_nodes, self._numpy_elements = scaled_coordinates, _elements

        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError(f"FAILED creating '_round_71' geometry with length to diameter ratio L/D = {self._length_to_diameter_ratio}")

    def _square_73(self):
        """Create 3D geometry of rectangular section with chamfers."""
        # LOGGER.info("START: func '_square_73'")
        try:
            self._height = self._parameters['side_of_square']
            self._width = self._height
            diagonal = self._parameters['diagonal']
            min_diagonal = math.sqrt(0.5) * self._height

            assert diagonal >= min_diagonal, (f"Input diagonal must be bigger or equal to "
                                              f"minimum possible diagonal for given square section "
                                              f"({diagonal} >= {min_diagonal:4g})")
            half_w = self._width / 2
            half_h = self._height / 2
            half_d = diagonal / 2

            chamfer_h = math.sqrt(2) / 2 * (math.sqrt(2) * self._height - diagonal)
            chamfer_angle = math.pi / 4

            cross_section_area = self._height ** 2 - 2 * chamfer_h ** 2
            self._length = self._volume / cross_section_area

            LOGGER.info(f"{self.log_id} Info: Geometry created - Slab with chamfered square section and flat tails: "
                        f"total dimensions \u2B1C H x L = \u2B1C {self._height:4g} x {self._length:4g} mm, "
                        f"diagonal between chamfers = {diagonal:4g} mm, "
                        f"chamfer = {chamfer_h:4g} mm x 45\u00b0, "
                        f"area of cross-section = {cross_section_area / 1e6:4g} m2, "
                        f"volume = {self._volume / 1e9:4g} m3.")

            self._initialize_gmsh()

            half_l = self._length / 2
            box_tag = gmsh.model.occ.addBox(-half_l, 0, 0,
                                            self._length, half_w, half_h)
            box = [(3, box_tag)]
            gmsh.model.occ.synchronize()
            chamfer_tag = gmsh.model.occ.addBox(-1.1 * half_l, half_d, -half_h,
                                                1.1 * self._length, self._width, self._height)
            chamfer = [(3, chamfer_tag)]
            gmsh.model.occ.synchronize()
            gmsh.model.occ.rotate(chamfer, 0, 0, 0, 1, 0, 0, chamfer_angle)
            quarter_1 = gmsh.model.occ.cut(box, chamfer)[0]
            gmsh.model.occ.synchronize()
            quarter_2 = gmsh.model.occ.copy(quarter_1)
            gmsh.model.occ.rotate(quarter_2, 0, 0, 0, 1, 0, 0, math.pi / 2)
            half_model_1 = gmsh.model.occ.fuse(box, quarter_2)[0]
            half_model_2 = gmsh.model.occ.copy(half_model_1)
            gmsh.model.occ.rotate(half_model_2, 0, 0, 0, 1, 0, 0, math.pi)
            gmsh.model.occ.fuse(half_model_1, half_model_2)
            gmsh.model.occ.synchronize()

            self._make_mesh()
            gmsh_nodes, gmsh_elements = self._get_mesh()
            self._finalize_gmsh()

            _nodes, _elements = self._gmsh_mesh_to_numpy(gmsh_nodes, gmsh_elements)
            scaled_nodes = self.scale_mesh_to_fit_volume(_elements, _nodes)

            self._numpy_nodes, self._numpy_elements = scaled_nodes, _elements
            self._nodes, self._elements = self._numpy_mesh_to_list(scaled_nodes, _elements)


        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError(
                f"FAILED creating '_square_73' square section \u2B1C H = \u2B1C {self._height:4g} mm with chamfers, defined by diagonal")

    def _extruded_polygon_by_length__then_scaled_to_fit_volume(self):
        """Create 3D geometry of rectangular section with chamfers."""
        # LOGGER.info("START: func '_rectangle_78'")
        try:
            vertices = binary_to_list_of_tuples(self.row['final_polygon'])  # X,Y - local coordinates of cross-section

            self.volume = self.row['volume_final']
            self._length = self.row['final_length']
            self._width = self.row['final_width']
            self._height = self.row['final_height']

            self._initialize_gmsh()
            gmsh.model.add("ExtrudedObject")
            try:
                half_l = self._length / 2
                points = [gmsh.model.geo.addPoint(-half_l, _y, _z) for _y, _z in vertices]
                # points.append(points[0])
                lines = [gmsh.model.geo.addLine(points[i], points[i + 1]) for i in range(len(points) - 1)]
                # lines.append(gmsh.model.geo.addLine(points[-1], points[0]))
                polygon = gmsh.model.geo.addCurveLoop(lines)
                face = gmsh.model.geo.addPlaneSurface([polygon])
                gmsh.model.geo.synchronize()
                gmsh.model.geo.extrude(dimTags=[(2, face)], dx=self._length, dy=0, dz=0)
                gmsh.model.geo.synchronize()

                self._make_mesh()
                gmsh_nodes, gmsh_elements = self._get_mesh()
            except Exception as _e:
                LOGGER.error(f"{self.log_id} {type(_e).__name__}: {_e}")
                raise RuntimeError("FAILED GMSH module for extruded 3D object")
            finally:
                self._finalize_gmsh()

            _nodes, _elements = self._gmsh_mesh_to_numpy(gmsh_nodes, gmsh_elements)
            scaled_nodes = self.scale_mesh_to_fit_volume(_elements, _nodes)

            self._numpy_nodes, self._numpy_elements = scaled_nodes, _elements
            self._nodes, self._elements = self._numpy_mesh_to_list(scaled_nodes, _elements)
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError(f"FAILED generating mesh of extruded polygon by length with scaling mesh to fit volume")

    def _octagon_79(self):
        """Create 3D geometry of octagon section with flat tails."""
        # LOGGER.info("START: func '_octagon_79'")
        try:
            self._height = self._parameters['height']
            self._width = self._height

            assert self._height > 0.0, "H <= 0"

            half_h = self._height / 2

            chamfer_h = self._height * (1 - math.sqrt(2) / 2)
            chamfer_angle = math.pi / 4

            cross_section_area = self._height ** 2 - 2 * chamfer_h ** 2
            self._length = self._volume / cross_section_area

            LOGGER.info(f"Info: Geometry created - Octagon and flat tails: "
                        f"total dimensions \u2BC3 H x L = \u2BC3 {self._height:4g} x {self._length:4g} mm, "
                        f"area of cross-section = {cross_section_area / 1e6:4g} m2, "
                        f"volume = {self._volume / 1e9:4g} m3.")

            self._initialize_gmsh()

            half_l = self._length / 2
            box_tag = gmsh.model.occ.addBox(-half_l, 0, 0,
                                            self._length, half_h, half_h)
            box = [(3, box_tag)]
            gmsh.model.occ.synchronize()
            chamfer_tag = gmsh.model.occ.addBox(-1.1 * half_l, half_h, -half_h,
                                                1.1 * self._length, self._width, self._height)
            chamfer = [(3, chamfer_tag)]
            gmsh.model.occ.synchronize()
            gmsh.model.occ.rotate(chamfer, 0, 0, 0, 1, 0, 0, chamfer_angle)
            quarter_1 = gmsh.model.occ.cut(box, chamfer)[0]
            gmsh.model.occ.synchronize()
            quarter_2 = gmsh.model.occ.copy(quarter_1)
            gmsh.model.occ.rotate(quarter_2, 0, 0, 0, 1, 0, 0, math.pi / 2)
            half_model_1 = gmsh.model.occ.fuse(box, quarter_2)[0]
            half_model_2 = gmsh.model.occ.copy(half_model_1)
            gmsh.model.occ.rotate(half_model_2, 0, 0, 0, 1, 0, 0, math.pi)
            gmsh.model.occ.fuse(half_model_1, half_model_2)
            gmsh.model.occ.synchronize()

            self._make_mesh()
            gmsh_nodes, gmsh_elements = self._get_mesh()
            self._finalize_gmsh()

            _nodes, _elements = self._gmsh_mesh_to_numpy(gmsh_nodes, gmsh_elements)
            scaled_nodes = self.scale_mesh_to_fit_volume(_elements, _nodes)

            self._numpy_nodes, self._numpy_elements = scaled_nodes, _elements
            self._nodes, self._elements = self._numpy_mesh_to_list(scaled_nodes, _elements)

        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError(f"FAILED creating '_octagon_79' Octagon section with side H = {self._height}")

    def scale_mesh_to_fit_volume(self, mesh_elements: np.ndarray, mesh_nodes: np.ndarray) -> np.ndarray:
        try:
            mesh_volume = self._get_mesh_volume(mesh_nodes, mesh_elements)
            volume_difference_percent = abs(mesh_volume / self._volume - 1) * 100

            if volume_difference_percent < 1e-3:
                scaled_coordinates = mesh_nodes
            else:
                centroid = self._get_bounds_centroid(self._get_mesh_bounds(mesh_nodes))
                x0 = np.array([1.0])  # initial guess
                root = fsolve(func=self.mesh_volume, x0=x0, args=(mesh_nodes, mesh_elements, centroid))[
                    0]  # Solve the system of equations
                scaled_coordinates = self._scale_yz_coordinates(mesh_nodes, root, centroid)
            return scaled_coordinates
        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError("FAILED scaling mesh coordinates to fit actual mesh volume with theoretical 'volume_final' calculated by Preview service")

    def mesh_volume(self, linear_coefficient: np.ndarray, mesh_nodes: np.ndarray, mesh_elements: np.ndarray, centroid: np.ndarray) -> np.ndarray:
        try:
            _scaled_nodes = self._scale_yz_coordinates(mesh_nodes, linear_coefficient, centroid)
            _vol = self._get_mesh_volume(_scaled_nodes, mesh_elements)
            delta_volume = _vol - self._volume
            return np.asarray([delta_volume])
        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError("FAILED calculating mesh volume")

    def _initialize_gmsh(self):
        try:
            gmsh.initialize(sys.argv, interruptible=False)
            gmsh.option.setNumber(name='General.Terminal',
                                  value=0)  # 0 - don't display messages on the terminal; 1 - display messages
            gmsh.logger.start()
            gmsh.model.add("billet")
        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError("FAILED initializing gmsh")

    def _make_mesh(self):
        try:
            thickness = min(self._height, self._width, self._length)
            self._mesh_absolute_min_element_size = self._mesh_relative_min_element_size * thickness

            gmsh.option.setNumber("Mesh.Algorithm", 6)
            gmsh.option.setNumber("Mesh.MeshSizeMin", self._mesh_absolute_min_element_size)
            gmsh.option.setNumber("Mesh.MeshSizeMax",
                                  self._mesh_absolute_min_element_size * self._mesh_element_size_ratio)
            gmsh.model.mesh.generate(3)

        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError("FAILED making mesh")

    def _scale_yz_coordinates(self, _input_nodes: np.ndarray, _scale_factor: np.ndarray, centroid: np.ndarray) -> np.ndarray:
        try:
            _scale_factor_float = _scale_factor.item()
        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise
        try:
            _multiplier = np.sqrt(1 + _scale_factor_float / 100)
            _output_nodes = _input_nodes.copy()
            _output_nodes -= centroid
            _output_nodes[:, 1] *= _multiplier
            _output_nodes[:, 2] *= _multiplier
            _output_nodes += centroid

            return _output_nodes
        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError(f"FAILED scaling nodes with scale factor {_scale_factor_float}")

    def _get_mesh(self) -> (tuple, tuple):
        try:
            return (
                gmsh.model.mesh.getNodes(),
                gmsh.model.mesh.getElements())
        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError("FAILED getting mesh")

    def _gmsh_mesh_to_numpy(self, gmsh_nodes: tuple, gmsh_elements: tuple) -> (np.ndarray, np.ndarray):
        try:
            return (
                gmsh_nodes[1].reshape(gmsh_nodes[0].shape[0], 3),
                gmsh_elements[2][2].reshape(gmsh_elements[1][2].shape[0], 4) - 1)
        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError("FAILED converting mesh to numpy")

    def _gmsh_mesh_to_list(self, gmsh_nodes: tuple, gmsh_elements: tuple) -> (list, list):
        try:
            node_indices = gmsh_nodes[0].tolist()
            node_coordinates = gmsh_nodes[1].reshape(len(node_indices), 3).tolist()
            nodes = [[node_indices[i], *node_coordinates[i]] for i in range(len(node_indices))]

            element_indices_original = gmsh_elements[1][2].tolist()
            element_indices = list(range(1, len(element_indices_original) + 1))
            element_connectivity = gmsh_elements[2][2].reshape(len(element_indices_original), 4).tolist()
            elements = [[element_indices[i], *element_connectivity[i]] for i in range(len(element_indices))]

            return nodes, elements
        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError("FAILED converting mesh to list")

    def _numpy_mesh_to_list(self, nodes: np.ndarray, elements: np.ndarray) -> (list, list):
        """Convert mesh from numpy to list format."""
        try:
            return (
                [[i + 1, *coordinates] for i, coordinates in enumerate(nodes.tolist())],
                [[i + 1, *connectivity] for i, connectivity in enumerate((elements + 1).tolist())]
            )
        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError("FAILED converting mesh from numpy to list format")


    def _get_mesh_volume(self, nodes: np.ndarray, elements: np.ndarray) -> float:
        """Measure mesh volume and total dimensions."""

        def get_conversion_indices() -> list:
            return [
                0, 1,  # d01 = sd[:, 0]
                0, 2,  # d02 = sd[:, 1]
                0, 3,  # d03 = sd[:, 2]
                1, 2,  # d12 = sd[:, 3]
                1, 3,  # d13 = sd[:, 4]
                2, 3]  # d23 = sd[:, 5]

        def get_coordinates_of_edges() -> tuple:
            try:
                element_edges = elements[:, edges_of_pyramid].reshape(shape_in_2_columns)
                return nodes[element_edges[:, 0]], nodes[element_edges[:, 1]]
            except Exception as _e:
                LOGGER.warning(f"{self.log_id} {type(_e).__name__}: {_e}")
                raise RuntimeError("FAILED to calculate coordinates of edges")

        def get_length_of_element_edges() -> dict:
            try:
                return {
                    '3d': np.linalg.norm(node_2 - node_1, axis=1),
                    'xy': np.linalg.norm(node_2[:, [0, 1]] - node_1[:, [0, 1]], axis=1),
                    'yz': np.linalg.norm(node_2[:, [1, 2]] - node_1[:, [1, 2]], axis=1),
                    'xz': np.linalg.norm(node_2[:, [0, 2]] - node_1[:, [0, 2]], axis=1)}
            except Exception as _e:
                LOGGER.warning(f"{self.log_id} {type(_e).__name__}: {_e}")
                raise RuntimeError("FAILED to measure length of elements edges")

        def volumes() -> np.ndarray:
            try:
                _sd = np.square(length_of_edges['3d'].reshape(number_of_elements, 6))
                # Cayley–Menger determinant
                # D = d**2
                # [[0, 1,   1,   1,   1],
                #  [1, 0,   D01, D02, D03],
                #  [1, D01, 0,   D12, D13],
                #  [1, D02, D12, 0,   D23],
                #  [1, D03, D13, D23, 0]]
                zeros = np.zeros(number_of_elements)
                ones = np.ones(number_of_elements)
                _matrix = np.array([
                    zeros, ones, ones, ones, ones,
                    ones, zeros, _sd[:, 0], _sd[:, 1], _sd[:, 2],
                    ones, _sd[:, 0], zeros, _sd[:, 3], _sd[:, 4],
                    ones, _sd[:, 1], _sd[:, 3], zeros, _sd[:, 5],
                    ones, _sd[:, 2], _sd[:, 4], _sd[:, 5], zeros
                ]).T.reshape(number_of_elements, 5, 5)
                _det = np.linalg.det(_matrix)
                return np.sqrt(np.absolute(_det / 288.0))
            except Exception as _e:
                LOGGER.warning(f"{self.log_id} {type(_e).__name__}: {_e}")
                raise RuntimeError("FAILED to measure volumes of elements")

        try:
            # Main body of function
            edges_of_pyramid = get_conversion_indices()
            number_of_elements = elements.shape[0]
            shape_in_2_columns = (int(number_of_elements * 6), 2)
            node_1, node_2 = get_coordinates_of_edges()
            length_of_edges = get_length_of_element_edges()
            elements_volumes = volumes()
            return np.sum(elements_volumes).item()
        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError("FAILED to measure mesh volume and total dimensions")

    def _get_mesh_bounds(self, nodes: np.ndarray) -> np.ndarray:
        try:
            min_coord = np.amin(nodes, axis=0)
            max_coord = np.amax(nodes, axis=0)
            return np.concatenate([min_coord, max_coord]).reshape(2, 3)
        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError("FAILED to measure mesh bounds")


    def _get_bounds_centroid(self, bounds: np.ndarray) -> np.ndarray:
        try:
            return np.average(bounds, axis=0)
        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError("FAILED to calculate bounds centroid")

    def _write_lines_to_file(self, filepath: str, _list_of_strings: list):
        try:
            data = open(filepath, "w+", encoding='utf-8', newline='\n')

            try:
                data.writelines(_list_of_strings)
            except Exception as _err:
                raise RuntimeError(_err)
            finally:
                data.close()
        except IOError as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError(f"FAILED open file '{filepath}'")
        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError(f"FAILED writing lines to file '{filepath}'")

    def _read_lines_from_file(self, filepath):
        try:
            _list_of_strings = []
            with open(filepath, 'r', encoding="UTF-8") as data:
                _list_of_strings = data.readlines()
            assert len(_list_of_strings) > 0, "Import of lines from the file has failed. Import is empty."
            _list = _list_of_strings
            return _list
        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError(f"FAILED reading lines from file '{filepath}'")

    def _import_mesh_from_inp_file(self, filepath):
        try:
            _list_of_strings = self._read_lines_from_file(filepath)

            # Divide MST-file on two parts
            line_1_indices = self._find_first_pattern_in_list(_list_of_strings,
                                                              "*NODE",
                                                              [0],
                                                              0)
            line_2_indices = self._find_first_pattern_in_list(_list_of_strings,
                                                              "******* E L E M E N T S *************",
                                                              list(range(10)),
                                                              0)
            line_3_indices = self._find_first_pattern_in_list(_list_of_strings,
                                                              "*ELEMENT, type=C3D4, ELSET=Volume1",
                                                              [2],
                                                              line_2_indices)
            part_with_nodes = _list_of_strings[(line_1_indices + 1):line_2_indices]
            part_with_elements = _list_of_strings[(line_3_indices + 1):]

            # Read list_of_nodes
            list_of_nodes = []
            for string in part_with_nodes:
                words = [j.strip() for j in string.split(",")]
                node_values = [int(words[0]), *[float(k) for k in words[1:]]]
                list_of_nodes.append(node_values)

            # Read list_of_elements
            list_of_elements = []
            for i, string in enumerate(part_with_elements):
                words = [j.strip() for j in string.split(",")]
                element_values = [i + 1, *[int(k) for k in words[1:]]]
                list_of_elements.append(element_values)

            return list_of_nodes, list_of_elements
        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError(f"FAILED importing mesh from file '{filepath}'")

    def _modify_billet_key(self) -> list[str]:
        try:
            # _list_of_strings = self._read_lines_from_file(os.path.join(self._path_library,
            #                                                            'billet_slab_version_00.KEY'))
            flow_net = self._modify_billet_key_for_flow_net()
            rz = self._modify_billet_key_for_nodes()
            usrnod = self._modify_billet_key_for_user_nodal_variables()
            usrelm = self._modify_billet_key_for_user_element_variables()
            elmcon = self._modify_billet_key_for_elements()
            _list_of_strings = [string + "\n" for string in self._input_key_file_template[0].split("\n")]
            _list_of_strings.extend(flow_net)
            _list_of_strings.extend(rz)
            _list_of_strings.extend([string + "\n" for string in self._input_key_file_template[1].split("\n")])
            _list_of_strings.extend(usrnod)
            _list_of_strings.extend(elmcon)
            _list_of_strings.extend([string + "\n" for string in self._input_key_file_template[2].split("\n")])
            _list_of_strings.extend(usrelm)
            _list_of_strings.extend([string + "\n" for string in self._input_key_file_template[3].split("\n")])
            _list_of_strings = self._modify_value_in_list_of_strings(
                _list_of_strings,
                string_pattern="NDTMP        1       0    2.0000000000E+001",
                string_splitter=r"(\s+)",
                pattern_indices=[0, 1],
                modified_member_index=6,
                new_value=self._temperature,
                new_value_format="{:>-21.10E}")
            self._calculate_process_parameters()
            automatic_modification_of_parameters_in_lines(self.param, self.file_1, _list_of_strings)

            return _list_of_strings
        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError("FAILED modifying billet key")

    def _calculate_process_parameters(self):
        try:
            execution_order = self.param['project']['execution_order']
            row = self.param['table'][execution_order]

            mesh = deform_mesh_settings(row, self.param)

            # Remeshing parameters
            self.param['operation']['cogging_remeshing_absolute_size_ratio'] = mesh['element_size_ratio']
            self.param['operation']['cogging_remeshing_inverse_max_element_size'] = mesh['inverse_max_element_size']
            self.param['operation']['cogging_remeshing_interference_depth_relative'] = -0.7
            self.param['operation']['cogging_remeshing_maximum_step_increment'] = 0
            self.param['operation']['cogging_remeshing_maximum_stroke_increment'] = 0.0
            self.param['operation']['cogging_remeshing_maximum_time_increment'] = 0.0
            self.param['operation']['cogging_remeshing_number_of_surface_elements'] = mesh['number_of_surface_elements']
            self.param['operation']['cogging_remeshing_weighting_factor_boundary_curvature'] = 0.75
            self.param['operation']['cogging_remeshing_weighting_factor_strain'] = 0.25
            self.param['operation']['cogging_remeshing_weighting_factor_strain_rate'] = 0.0
            self.param['operation']['cogging_remeshing_weighting_factor_temperature'] = 0.25
        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError("FAILED calculating process parameters")

    def _modify_billet_key_for_flow_net(self) -> list[str]:
        try:
            half_l = self._length / 2
            half_h = self._height / 2
            half_w = self._width / 2
            flow_net_coordinates = [
                [half_l, 0.0, 0.0],
                [half_l, 0.0, 0.1 * half_h],
                [half_l, -0.1 * half_w, 0.0],
                [half_l, 0.0, -0.1 * half_h],
                [half_l, 0.1 * half_w, 0.0],
            ]
            flow_net_connectivity = [
                '       1       1       2       3      -1\n',
                '       2       1       3       4      -1\n',
                '       3       1       4       5      -1\n',
                '       4       1       5       2      -1\n'
            ]

            flow_net_key = ['FLWNET       1       1     5     4\n']
            flow_net_key.extend(
                f' {(i + 1):>7d}'
                f' {flow_net_coordinates[i][0]:>-20.10E}'
                f' {flow_net_coordinates[i][1]:>-20.10E}'
                f' {flow_net_coordinates[i][2]:>-20.10E}\n'
                for i in range(5))
            flow_net_key.extend(flow_net_connectivity)

            return flow_net_key
        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError("FAILED modifying billet key for flow net")

    def _modify_billet_key_for_nodes(self):
        try:
            part_1 = [f"RZ           1     {len(self._nodes):d}\n"]
            node_num: int
            _x: float
            _y: float
            _z: float
            pattern = '{:>8d} {:>-20.10E} {:>-20.10E} {:>-20.10E}\n'
            part_1.extend([pattern.format(node_num, _x, _y, _z) for (node_num, _x, _y, _z) in self._nodes])
            return part_1[:]
        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError("FAILED modifying billet key for nodes")

    def _modify_billet_key_for_elements(self):
        try:
            n0: int
            n1: int
            n2: int
            n3: int
            n4: int
            part_2 = [f"ELMCON       1    {len(self._elements):d}       4\n"]
            elements = [f' {n0:>7d} {n1:>7d} {n2:>7d} {n3:>7d} {n4:>7d}\n' for (n0, n1, n2, n3, n4) in self._elements]
            part_2.extend(elements)
            return part_2[:]
        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError("FAILED modifying billet key for elements")

    def _modify_billet_key_for_user_nodal_variables(self) -> list[str]:
        try:
            variables_count = len(VARIABLES['user_nodal']['column_names'])
            nodes_count = self._numpy_nodes.shape[0]

            user_nodal_variables = \
                np.hstack(
                    (
                        np.full(shape=(nodes_count, 2), fill_value=self._temperature, dtype=np.float64),  # Max Temp
                        np.zeros(shape=(nodes_count, 2), dtype=np.float64),  # Temp Change
                        self._user_nodal_variables_for_ingot_axis()  # Ingot Axis
                    )
                )

            # Keyfile keyword
            key_file = [f"UNNAME       1 {variables_count:>7d}\n"]
            for _i in range(variables_count):
                key_file.append(VARIABLES['user_nodal']['column_names'][_i] + '\n')

            # Keyfile data array
            key_file.append(f"USRNOD       1 {nodes_count:>7d}    0.0000000000E+000 {variables_count:>7d}\n")
            pattern = '{:>8d}' + ' {:>-20.10E}' * variables_count + '\n'
            key_file.extend([pattern.format(*[i + 1, *var]) for i, var in enumerate(user_nodal_variables.tolist())])

            return key_file
        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError("FAILED generate piece of KEY file for User Nodal Variables")

    def _modify_billet_key_for_user_element_variables(self) -> list[str]:
        try:
            variables_count = len(VARIABLES['user_element']['column_names'])
            elements_count = self._numpy_elements.shape[0]

            user_element_variables = np.zeros(shape=(elements_count, variables_count), dtype=np.float64)

            # Keyfile keyword
            key_file = [f"UENAME       1 {variables_count:>7d}\n"]
            key_file.extend([VARIABLES['user_element']['column_names'][_i] + '\n' for _i in range(variables_count)])

            # Keyfile data array
            key_file.append(f"USRELM       1 {elements_count:>7d}    0.0000000000E+000 {variables_count:>7d}\n")
            pattern = '{:>8d}' + ' {:>-20.10E}' * variables_count + '\n'
            key_file.extend([pattern.format(*[i + 1, *var]) for i, var in enumerate(user_element_variables.tolist())])

            return key_file
        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError("FAILED generate piece of KEY file for User Element Variables")

    def _user_nodal_variables_for_ingot_axis(self) -> np.ndarray:
        try:
            dimensions = np.asarray((self._length, self._width, self._height)).reshape(1, 3)
            return np.divide(self._numpy_nodes, dimensions)
        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError("FAILED calculating User Nodal variables (X, Y, Z) defining the ingot axis")

    def _find_first_pattern_in_list(self, list_of_strings: list, pattern: str, pattern_indices: list, starting_line: int) -> (str, int):
        try:
            line_indices = self._find_pattern_in_list(list_of_strings, pattern, pattern_indices, starting_line)
            return line_indices[0] if len(line_indices) > 0 else None
        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError("FAILED finding first pattern in list")

    def _modify_value_in_list_of_strings(self, list_of_strings, string_pattern, string_splitter, pattern_indices,
                                         modified_member_index, new_value, new_value_format) -> list:
        try:
            template = self._split_line(f"{string_pattern}\n", string_splitter)
            line_index = self._find_pattern_in_list(list_of_strings, string_pattern, pattern_indices, 0)
            template[modified_member_index] = new_value_format.format(new_value)

            assert len(line_index) == 1, f"There must be only 1 member in the list, but list content is {line_index}"

            list_of_strings[line_index[0]] = "".join(template)
            return list_of_strings
        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError("FAILED modifying value in list of strings")

    def _split_line(self, line: str, string_format: str) -> list:
        try:
            words = split(string_format, line)
            for index, string in enumerate(words):
                if string == '':
                    words.pop(index)
            return words
        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError("FAILED splitting line")

    def _find_pattern_in_list(self, list_of_strings: list[str], pattern: str, pattern_indices: list, starting_line: int) -> (str, int):
        try:
            line_indices = []
            split_pattern = [pattern.split()[i].lower() for i in pattern_indices]
            for i, line in enumerate(list_of_strings):
                if i < starting_line:
                    continue
                pieces_of_line = line.split()
                if (len(pieces_of_line) < pattern_indices[-1] + 1) or (len(pieces_of_line) < len(pattern_indices)):
                    continue
                pieces_of_line = [pieces_of_line[i].lower() for i in pattern_indices]
                if pieces_of_line == split_pattern:
                    line_indices.append(i)
            return line_indices
        except Exception as _err:
            LOGGER.warning(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError("FAILED finding pattern in list")

    @property
    def log_id(self):
        return self.param['operation']['log_id'] + f" Duration {time.monotonic() - self.param['operation']['project_start_datetime']:.2f}s {traceback.format_exc()}"
