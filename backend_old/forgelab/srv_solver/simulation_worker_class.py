import logging
import traceback
import json
import math
import os
import shutil
import time
from multiprocessing import Queue, Semaphore
from datetime import datetime
from threading import Thread

import numpy as np
import smbclient.shutil
from psycopg2 import sql

from forgelab.common.common_funcs import log_error
from forgelab.common.file_operations import (
    is_local_dir_exist, generate_operation_dir_name, sub_operation_abs_path,
    convert_dict_values_to_json_compatible_types,
    opened_w_error, is_smb_file_server_available, create_new_dir_or_clean_existing_dir,
    import_previous_operation_parameters_json_from_nas, generate_project_dir_name)
from forgelab.common.queries import (
    query_process_versions,
    query_server_pre_main,
    query_post_operations,
    query_type_id_nnn,
    query_processes
)
from forgelab.common.read_deform_keyfile import read_deform_keyfile
from forgelab.config import config
from forgelab.srv_solver.operations.billet import BilletGeometry
from forgelab.srv_solver.operations.cogging_bite import CoggingBiteOp
from forgelab.srv_solver.operations.cut import CutOp
from forgelab.srv_solver.operations.forming_frozen_speed_window_boxes import FormingFrozenSpeedWindowBoxesOp
from forgelab.srv_solver.operations.heat import HeatOp
from forgelab.srv_solver.operations.offset_and_rotation import OffsetRotationOp
from forgelab.srv_solver.operations.remesh import RemeshOp
from forgelab.srv_solver.pre_functions import set_triggers
from forgelab.common.shapely_2d_funcs import (
    basis_to_basis_transformation_as_euler_angles_zyx,
    rotate_basis)


LOGGER = logging.getLogger(__name__)


class SimulationWorker(Thread):
    """A thread that runs sequence of simulation utils according to input table of utils"""

    # TODO: Modify query - add 'Simulation Operation Num' to 'server_pre_main'
    # TODO: Modify query - add 'Simulation Step Num' to 'server_pre_main'

    def __init__(self, worker_id: int, input_queue: Queue, semaphore: Semaphore):
        """Initialize the thread"""
        super().__init__()

        self.worker_id: int = worker_id
        self.input_queue: Queue = input_queue
        self.semaphore: Semaphore = semaphore

        self.pvid: int = 0
        self.eo: int = 0
        self.eo_last: int = 0
        self.eid: int = 0
        self.task_location: str = "non defined"  # "local" or "remote"

        self.param: dict = {}
        self.row: dict = {}

        self.is_error: bool = False
        self.stop_trigger: bool = False
        self.queue_timeout: float = time.monotonic()
        self.time_start: float = time.monotonic()

        self.sub_operation_number: int = 0
        self.sub_operation_list: list = []


    def run(self):
        LOGGER.info(f"{self.log_id} started.")
        while True:
            try:
                self.eo_last = 0
                self.pvid, self.eo, self.task_location = 0, 0, "non defined"

                # =========================== WAIT FOR QUEUE =========================================
                self.pvid, self.eo, self.task_location = self.input_queue.get()

                # ============= TASK IS RECEIVED FROM QUEUE -> START SIMULATION ======================
                if self.pvid == 0:
                    LOGGER.info(f"{self.log_id} received shutdown signal.")
                    break
                LOGGER.info(f"{self.log_id} received '{self.task_location}' task")

                self._silent_worker()

                # ================ SIMULATION IS FINISHED -> RELEASE QUEUE SLOT ======================
                self.semaphore.release()

                LOGGER.info(f"{self.log_id} Released 1 slot in Simulation Semaphore")

            except Exception as _err:
                log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
                break
        LOGGER.info(f"{self.log_id} stopped.")

    def _silent_worker(self):
        """Run the thread"""
        try:
            self._initialize_parameters()

            self._query_update_server_pre_main_set_simulation_status_as_run()

            self._do_simulation()
            self._save_parameters_json()
            self._copy_to_nas()

            self._query_update_server_pre_main_set_status_queue()

            if self._query_is_last_operation():
                self._query_update_process_versions_set_progres_set_status_finish()
            else:
                self._query_update_process_versions_set_progres_set_status_queue()

            LOGGER.info(f"{self.log_id} SUCCESS finished Sim Operation")

        except Exception as _err:
            LOGGER.warning(f"{self.log_id} ERROR in Simulation worker {type(_err).__name__}: {_err}")

            self._silent_query_update_server_pre_main_error_in_simulation()
            self._silent_query_process_versions_set_simulation_status('error')

    def _initialize_parameters(self):
        try:
            if self.eo == 0:
                project_name = generate_project_dir_name(self.pvid)
                project_update = {
                    'ppt_file_name': project_name,
                    'pdf_file_name': project_name,
                    'db_file_name': project_name,
                    'project_dir_name': project_name}
                self._query_update_process_versions_set_parameters(
                    update_param=project_update)

            self.param: dict = {
                'project': query_process_versions(self.pvid),
                'table': query_server_pre_main(self.pvid),
                'post': query_post_operations(self.pvid),
                'previous_operation': {}
            }

            assert self.eo == self.param['project']['execution_order'], "Value of 'execution_order' is not correct."

            type_id = self.param['table'][self.eo]['type_id']
            operation_id = self.param['table'][self.eo]['operation_id']
            process_id = self.param['project']['process_id']

            self.param['type_id_nnn'] = query_type_id_nnn(type_id, operation_id)
            self.param['process'] = query_processes(process_id)

            if self.eo >= 1:
                self.param['previous_operation'] = import_previous_operation_parameters_json_from_nas(self.param)

            if self.task_location == 'remote':
                self._copy_files_from_nas()

            self.eo_last = self.param['project']['operations_count'] - 1
            self.eid = self.param['table'][self.eo]['execution_id']
            self.row = self.param['table'][self.eo]

            self.is_error = False
            self.stop_trigger = False
            self.queue_timeout = time.monotonic()
            self.time_start = time.monotonic()

            self.sub_operation_number: int = 0
            self.sub_operation_list: list = []

            material_id = self.row['material_id']
            self.param['material'] = config.lib['material_classes'][material_id]

            project_dir_name = self.param['project']['project_dir_name']
            operation_name = generate_operation_dir_name(self.eo)

            self.param['operation'] = {
                'worker_id': self.worker_id,
                'log_id':  f"[{self.pvid}][{self.eo}/{self.eo_last}] Pre #{self.worker_id}",
                'project_start_datetime': self.time_start,
                'simulation_time_finished': None,
                'simulation_starting_step': None,
                'simulation_finishing_step': None,
                'print_path': '',
                'print_time_started': None,
                'print_time_finished': None,
                'relative_min_element_size': 1 / int(self.param['table'][0]['mesh_elements']),
                'element_size_ratio': 1.1,
                'operation_name': operation_name,
                'template_name': '',
                'manipulator_length': 125.0,
                'rotation_angle_per_byte': 0.0,
                'sub_operation_type': '',
                'bite_number': 0,
                'positioning_dies_start': 0.0,
                'rotation_around_x': 0.0,
                'rotation_around_y': 0.0,
                'rotation_around_z': 0.0
            }

            self.param['operation'] |= {
                'project_dir_name': project_dir_name,
                'db_file_relative_path': os.path.join(project_dir_name, project_dir_name + '.DB'),
                'operation_relative_path': os.path.join(project_dir_name, operation_name),
                'sub_operation_name': '',
                'sub_operation_relative_path': '',
                'sub_operation_extract_relative_path': '',
                'billet_file_sub_operation_extract_relative_path': '',
                'sub_operation_path': ''
            }

            if 'global_time' in self.param['previous_operation']:
                self.param['operation']['global_time'] = self.param['previous_operation']['global_time']

            if self.eo == 0:
                self._create_new_local_project_dir()

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _update_parameters_after_simulation(self):
        try:
            self.param['operation'] |= {
                'simulation_time_finished': datetime.now()
            }
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _do_simulation(self):
        # LOGGER.info("START func '_do_simulation'")
        try:

            self._logging_start_simulation()  # logging

            # TODO: fix Operation Number in MO for 1st operation (now = 2, must be = 1)
            # TODO: fix Operation Number in MO: operation must correspond to 'execution_number + 1'

            _type = self.row['operation_type']
            _id = self.row['type_id']

            if _type == 'NewBillet':
                self._run_create_billet()

            elif _id == 23:
                self._run_23_heat()

            # Upsetting
            elif _id == 91:
                self._run_upsetting()  # Single or Triple bites upsetting
            elif _id == 93:
                self._run_upsetting()  # Single bite upsetting
            elif _id == 94:
                self._run_upsetting()  # Triple bites upsetting
            elif _id == 92:
                self._run_92_upset_tail_flattening()  # Tail flattening
            elif _id == 100:
                self._run_100_tail_chamfering()  # Tail chamfering

            # Axial prolongation - parent_type_id = 38
            elif _id == 46:
                self._run_prolongation()  # Feed
            elif _id == 83:
                self._run_prolongation()  # Num of Bites
            elif _id == 90:
                self._run_prolongation()  # Num of Bites, Skip Bites

            # Radial prolongation - parent_type_id = 35
            elif _id == 95:
                self._run_prolongation()  # Feed
            elif _id == 96:
                self._run_prolongation()  # Num of Bites

            # Rounding Spiral prolongation - parent_type_id = 99
            elif _id == 50:
                self._run_prolongation()
            elif _id == 51:
                self._run_prolongation()

            # Full die operations
            elif _id == 52:  # Full die simple
                self._run_52_full_die_simple()
                # pass

            # Cutting operations
            elif _id == 57:  # Cutting percentage
                self._run_cut()

            # Cutting operations
            elif _id == 86:  # Cutting percentage
                self._run_cut()

            else:
                self._logging_operation_is_not_supported()  # logging

            self._update_parameters_after_simulation()
            self._logging_successfully_finished_operation()  # logging

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def get_simulation_results(self) -> dict:
        """Return the results of simulation"""
        try:
            return self.param.copy()
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _delete_project_files(self):
        """Remove project directory from the Server."""
        # LOGGER.info("START func '_delete_project_files'")
        try:
            local_dir: str = config.server['local_dir']
            project_dir_name: str = self.param['project']['project_dir_name']
            project_dir = os.path.join(local_dir, project_dir_name)

            assert is_local_dir_exist()

            if os.path.exists(project_dir):
                shutil.rmtree(project_dir)
                LOGGER.info(f"{self.log_id} Removed local project dir '{project_dir}' on the Server.")
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _create_new_local_project_dir(self) -> bool:
        """Create new empty project directory on server"""
        # LOGGER.info("START: func 'create_new_local_project_dir'")
        try:
            local_dir: str = config.server['local_dir']
            project_dir_name = self.param['project']['project_dir_name']
            project_path = os.path.join(local_dir, project_dir_name)

            if os.path.exists(project_path):
                shutil.rmtree(project_path)
                LOGGER.info(f"{self.log_id} Removed local project dir '{project_path}' on the Server.")

            os.mkdir(project_path)
            return True
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _run_sub_operation_offset_rotation(self,name_prefix: str, target_orientation: np.ndarray):
        """call this method from operation_sequence method"""
        try:
            self._measure_billet_of_previous_sub_operation()

            _o = self.param['operation']
            _m = self.param['operation']['imported_keyfile']['objects'][1]['measurements']

            # Transform Current orientation into Target one. Then Convert to Euler angles.
            current_orientation = np.array(_m['principal_coordinate_system'])
            z_angle, y_angle, x_angle = basis_to_basis_transformation_as_euler_angles_zyx(current_orientation, target_orientation)

            # Rounded Rotation angles
            _o['rotation_around_z'] = np.round(z_angle, decimals=3)
            _o['rotation_around_y'] = np.round(y_angle, decimals=3)
            _o['rotation_around_x'] = np.round(x_angle, decimals=3)

            # Offset Billet to the Center of Mass
            center_of_mass = np.round(np.array(_m['center_of_mass']), decimals=2)
            offset = -center_of_mass
            _o['offset_x'] = offset[0]
            _o['offset_y'] = offset[1]
            _o['offset_z'] = offset[2]

            # Chamfer number
            operation_name = f"{name_prefix}_offset_and_rotate"
            LOGGER.info(f"{self.log_id} Start operation '{operation_name}'. "
                        f"Rotate billet around axes (X, Y, Z) = "
                        f"({_o['rotation_around_x']}, {_o['rotation_around_y']}, {_o['rotation_around_z']}) [deg]. "
                        f"Offset (X, Y, Z) = ({offset[0]}, {offset[1]}, {offset[2]}).")

            self._set_sub_operation_path(operation_name)

            # ----------------------------------- INITIALIZE INGOT AXIS --------------------------------------
            self.param['operation']['is_initialize_user_nodal_for_ingot_axis'] = True

            # -------------------------------------------- RUN -----------------------------------------------
            operation = OffsetRotationOp(self.param)
            operation.run()

            self._finalize_sub_operation()

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _sub_operation_run_bite(self, angle: float, positioning_dies_start: float, is_half_of_bites_done: bool):
        try:
            self._set_sub_operation_path('bite')

            # ------------------------------------------ MEASURE -----------------------------------------
            self._measure_billet_of_previous_sub_operation()
            _m = self.param['operation']['imported_keyfile']['objects'][1]['measurements']

            # ------------------------------ CALCULATE BILLET POSITION --------------------------------
            billet_centroid = np.round(np.array(_m['centroid']), decimals=2)
            billet_offset = -billet_centroid

            # ------------------------------ CALCULATE ANGULAR MISALIGNMENT ---------------------------
            _m = self.param['operation']['imported_keyfile']['objects'][1]['measurements']
            # target_basis = rotate_basis(np.array(_m['principal_coordinate_system']), list_of_rotations_xyz=[('x', angle)])
            rz, ry, rx = basis_to_basis_transformation_as_euler_angles_zyx(np.array(_m['principal_coordinate_system']), np.eye(3))

            # ------------------------------ CALCULATE MANIPULATOR POSITION --------------------------
            is_starts_from_right_tail = self.row['feed_direction_name'] == '<=='
            if is_starts_from_right_tail:
                _right = _m['length']
                _left = 50.0
            else:
                _right = 50.0
                _left = _m['length']
            if is_half_of_bites_done:
                _right, _left = _left, _right

            # ------------------------------- PRE IMPORTED PARAMETERS ---------------------------------
            osp = self.row['operation_specific_parameters']
            final_dies_gap = osp['final_dies_gap']
            initial_top_die_reference_point_z_coord = osp['initial_top_die_reference_point_z_coord'] + 85
            initial_bottom_die_reference_point_z_coord = osp['initial_bottom_die_reference_point_z_coord'] - 85

            # ---------------------------------- RECORD PARAMETERS -----------------------------------
            self.param['operation'].update({
                'parent_log_id': self.log_id,
                'rotation_angle_per_byte': 0,
                'rotation_angle_per_pass': angle,
                'billet_offset_x': billet_offset[0],
                'billet_offset_y': billet_offset[1],
                'billet_offset_z': billet_offset[2],
                'billet_rotation_around_x': rx,
                'billet_rotation_around_y': ry,
                'billet_rotation_around_z': rz,
                'top_die_offset_x': 0,
                'top_die_offset_y': 0,
                'top_die_offset_z': initial_top_die_reference_point_z_coord,
                'bottom_die_offset_x': 0,
                'bottom_die_offset_y': 0,
                'bottom_die_offset_z': initial_bottom_die_reference_point_z_coord,
                'stopping_criteria_die_distance': final_dies_gap,
                'positioning_dies_start': positioning_dies_start,
                'manipulator_handover_distance_left': _left,
                'manipulator_handover_distance_right': _right
            })

            LOGGER.info(f"{self.log_id} BITE {self.bite_index}: "
                        f"Positioning dies start = {round(positioning_dies_start, 1)} "
                        f"Angle = {round(angle, 0)} "
                        f"Billet offset = [{', '.join([str(round(val, 1)) for val in billet_offset])}] "
                        f"Dies z-offset (Top/Bottom) = {round(initial_top_die_reference_point_z_coord, 1)} "
                        f"/ {round(initial_bottom_die_reference_point_z_coord, 1)} "
                        f"Die stop criteria = {round(final_dies_gap, 1)}.")

            # ----------------------------------- INITIALIZE INGOT AXIS --------------------------------------
            self.param['operation']['is_initialize_user_nodal_for_ingot_axis'] = True

            # --------------------------------------- RUN ----------------------------------------------------
            operation = CoggingBiteOp(self.param)
            operation.run()

            self._finalize_sub_operation()
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _run_sub_chamfering_stroke_frozen_corners(self, op: dict):
        """
        2nd step of single bite for chamfering a tail edge.
        Do:
        1. centering;
        2. fix nodal velocity in X, Y and Z directions of two free billet corners;
        3. short forming stroke to form a flat contact surface between the die and the billet.
        When 2nd step is finished, then 3rd step must be called.
        """
        try:

            # INPUT
            self._measure_billet_of_previous_sub_operation()
            _m = self.param['operation']['imported_keyfile']['objects'][1]['measurements']
            centroid = np.round(np.array(_m['centroid']), decimals=2)
            upsetting_height = op['upsetting_height']

            # FREEZING
            self.param['operation']['initial_local_coordinate_system'] = op['initial_orientation']
            self.param['operation']['current_local_coordinate_system'] = np.array(_m['principal_coordinate_system'])
            self.param['operation']['velocity_boundary_condition_bounds_list'] = op['velocity_boundary_condition_bounds_list']
            self.param['operation']['fixed_directions_xyz_bool'] = op['fixed_directions_xyz_bool']

            # STOPPING CRITERIA
            self.param['operation']['stopping_criteria_die_distance'] = op['upsetting_height']
            self.param['operation']['stopping_criteria_die_displacement'] = op['upsetting_penetration']
            self.param['operation']['user_defined_limit_press_load'] = 0.0

            # CENTER & OFFSET the BILLET
            offset_to_centroid = -centroid
            self.param['operation']['offset_x'] = offset_to_centroid[0] + op['offset'][0]
            self.param['operation']['offset_y'] = offset_to_centroid[1] + op['offset'][1]
            self.param['operation']['offset_z'] = offset_to_centroid[2] + op['offset'][2]

            # Chamfer number
            operation_name = (f"{op['sub_operation_name_startswith']}_upset_with_frozen_corners_height_"
                              f"{int(round(upsetting_height, 0))}")
            LOGGER.info(f"{self.log_id} Start operation '{operation_name}'. Offset (X, Y, Z) = "
                        f"({offset_to_centroid[0]}, {offset_to_centroid[1]}, {offset_to_centroid[2]}).")

            self._set_sub_operation_path(operation_name)

            # ----------------------------------- INITIALIZE INGOT AXIS --------------------------------------
            self.param['operation']['is_initialize_user_nodal_for_ingot_axis'] = True

            # --------------------------------------- RUN ----------------------------------------------------
            operation = FormingFrozenSpeedWindowBoxesOp(self.param)
            operation.run()

            self._finalize_sub_operation()

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _sub_operation_run_remeshing(self):
        """call this method from operation_sequence method"""
        try:
            self._set_sub_operation_path('remeshing')

            self._measure_billet_of_previous_sub_operation()

            self._cut_logging_final_length()

            match self.row['type_id']:
                case 86:
                    duration = 1.0
                case _:
                    duration = self._cut_calculate_process_duration_after_cut()

            self.param['operation']['process_duration'] = duration

            # ----------------------------------- INITIALIZE INGOT AXIS --------------------------------------
            self.param['operation']['is_initialize_user_nodal_for_ingot_axis'] = True

            # --------------------------------------- RUN ----------------------------------------------------
            operation = RemeshOp(self.param)
            operation.run()

            self._finalize_sub_operation()

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _run_create_billet(self):
        """Initialize billet - create new billet"""
        try:
            self.param['operation']['simulation_number'] = 0

            self._set_sub_operation_path('new_billet')

            operation = BilletGeometry(self.param)
            operation.run()

            self._measure_billet()
            self._finalize_sub_operation()

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _run_23_heat(self):
        """Run 'Heat' operation"""
        try:
            self._measure_billet_of_previous_sub_operation()

            self.param['operation']['process_duration'] = float(self.row['control_duration'])
            self._set_sub_operation_path('cooling')

            def is_first_operation_23_in_sequence_of_operations_23() -> bool:
                previous_operation_type_id = self.param['table'][self.eo - 1]['type_id']
                is_first_operation_23 = previous_operation_type_id != 23
                return is_first_operation_23

            def is_recovering_occurs() -> bool:
                max_temp_on_heating_sequence = -273.15
                for eo in range(self.eo - 1, -1, -1):
                    operation_type_id = self.param['table'][eo]['type_id'] == 23
                    if not operation_type_id:
                        break
                    max_temp_on_heating_sequence = max(max_temp_on_heating_sequence,
                                                       self.row['control_temperature_furnace_initial'],
                                                       self.row['control_temperature_furnace_final'])
                return max_temp_on_heating_sequence > 400.0

            if self.eo == 0:
                is_new_operation = True
                is_new_heat = True
                is_new_bite = True
            else:
                is_new_operation = is_first_operation_23_in_sequence_of_operations_23()
                is_recovering = is_recovering_occurs()
                is_new_heat = is_new_operation and is_recovering
                is_new_bite = not is_new_operation

            self.param['operation']['usrdef_triggers'] = set_triggers(softening_coefficient=0.005,
                                                                      is_new_bite=is_new_bite,
                                                                      is_new_operation=is_new_operation,
                                                                      is_new_heat=is_new_heat)

            # ----------------------------------- INITIALIZE INGOT AXIS --------------------------------------
            self.param['operation']['is_initialize_user_nodal_for_ingot_axis'] = True

            # --------------------------------------- RUN ----------------------------------------------------
            operation = HeatOp(self.param)
            operation.run()

            self._finalize_sub_operation()

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _abs_die_positioning(self, feed_pointer_name: str, feed_value: float, billet_measurement: dict) -> float:
        """
        CALCULATE DIE OFFSET POSITION

        Args:
            feed_value:

        Returns:

        """
        die_length = self.die_straight_length_min(self.row)

        length_excluding_tail_barrels = billet_measurement['length_excluding_tail_barrels']

        is_starts_from_right_tail = self.row['feed_direction_name'] == '<=='
        if is_starts_from_right_tail:
            tail_barrel_length = billet_measurement['left_tail_barrel_length']
        else:
            tail_barrel_length = billet_measurement['right_tail_barrel_length']

        match feed_pointer_name:
            case 'relative_die_center':
                return feed_value * length_excluding_tail_barrels + tail_barrel_length
            case 'absolute_die_center':
                return feed_value + tail_barrel_length
            case 'relative_die_edge':
                return feed_value * length_excluding_tail_barrels + 0.5 * die_length + tail_barrel_length
            case 'absolute_die_edge':
                return feed_value + 0.5 * die_length + tail_barrel_length
            case _:
                raise KeyError(f"Unknown Feed pointer ({feed_pointer_name})")

    def _run_prolongation(self):
        """Run Radial prolongation operation"""
        try:

            # TODO: Initial position of dies - both dies in contact with billet initially
            # TODO: Speed of top vs bottom dies are different.
            # TODO: Speed of top die is proportional to top stroke
            # TODO: Speed of bottom die is proportional to bottom stroke
            # TODO: Add new Forming operation with imported dies and manipulators.
            # TODO: Change positioning of billet. Positioning by two points - tail point and dies point.

            osp = self.row['operation_specific_parameters']
            _o = self.param['operation']

            _o['process_duration'] = float(self.row['time_before_pass'])

            # ----------------------------- RUN CENTERING & COOLING ---------------------------------
            self._measure_billet_of_previous_sub_operation()
            initial_measured_basis = np.array(self.param['operation']['imported_keyfile']['objects'][1]['measurements']['principal_coordinate_system'])

            _o['usrdef_triggers'] = set_triggers(softening_coefficient=0.005,
                                                 is_new_bite=True,
                                                 is_new_operation=True,
                                                 is_new_heat=False)
            target_basis = rotate_basis(initial_measured_basis, osp['radial_rotations'])

            # ----------- LOGGING DIFFERENCE BETWEEN MEASURED BASIS AND TARGET ONE (PREVIEW) --------
            preview_initial_basis = np.array(self.row['initial_basis'])
            forming_basis_diff = np.max(target_basis - preview_initial_basis).item()
            if forming_basis_diff > 1e-4:
                preview_initial_basis_str = {', '.join(np.array2string(preview_initial_basis, precision=3).split())}
                forming_basis_str = {', '.join(np.array2string(target_basis, precision=3).split())}
                LOGGER.warning(f"{self.log_id} osp['initial_basis']={preview_initial_basis_str} is different from 'forming_basis'={forming_basis_str} with MAX error {forming_basis_diff * 100:.3f}%")

            self._run_sub_operation_offset_rotation('initial', target_basis)

            # ----------------------------- PRE IMPORTED PARAMETERS ---------------------------------
            bites_table = osp['bites_table']

            # ------------------------------ CALCULATE MANIPULATOR PARAMETERS --------------------------
            bites_count = len(bites_table)

            def is_half_of_bites_done() -> bool:
                return self.bite_index > 0.5 * bites_count

            # ------------------------------ CALCULATE DIE OFFSET POSITION -----------------------------
            self._measure_billet_of_previous_sub_operation()
            billet_measure_before_cogging = self.param['operation']['imported_keyfile']['objects'][1]['measurements']

            # ------------------------------------ RUN BITES ---------------------------------
            for self.bite_index, (feed_mode, feed_pointer_name, angle, feed_value) in enumerate(bites_table):
                _o['usrdef_triggers'] = set_triggers(softening_coefficient=0.005,
                                                     is_new_bite=True,
                                                     is_new_operation=False,
                                                     is_new_heat=False)
                die_center_position = self._abs_die_positioning(feed_pointer_name, feed_value, billet_measure_before_cogging)
                self._sub_operation_run_bite(angle, die_center_position, is_half_of_bites_done())

            # --- RETURN TO MANIPULATOR COAXIAL ORIENTATION IF RADIAL PROLONGATION -------------------

            if self.parent_type_id == 35:  # Radial prolongation
                # Transform Current orientation into Target one. Then Convert to Euler angles.
                self._measure_billet_of_previous_sub_operation()
                orientation_after_cogging = np.array(self.param['operation']['imported_keyfile']['objects'][1]['measurements']['principal_coordinate_system'])
                rz, ry, rx = basis_to_basis_transformation_as_euler_angles_zyx(orientation_after_cogging, np.eye(3))
                rotations_current_basis_to_global_basis = [('z', rz), ('y', ry), ('x', rx)]
                rotations_global_basis_to_original_basis = [(axis_name, -1 * angle) for (axis_name, angle) in osp['radial_rotations'][:: -1]]
                reversed_negative_radial_rotations = rotations_current_basis_to_global_basis + rotations_global_basis_to_original_basis
                # back_to_original_orientation_basis
                final_target_orientation = rotate_basis(orientation_after_cogging, list_of_rotations_xyz=reversed_negative_radial_rotations)
            else:
                final_target_orientation = np.eye(3)

            _o['usrdef_triggers'] = set_triggers(softening_coefficient=0.005,
                                                 is_new_bite=False,
                                                 is_new_operation=False,
                                                 is_new_heat=False)
            self._run_sub_operation_offset_rotation('rotate_to_theoretical_orientation', final_target_orientation)

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _run_upsetting(self):
        """Run 'Upset' operation"""
        try:
            self._measure_billet_of_previous_sub_operation()
            _m = self.param['operation']['imported_keyfile']['objects'][1]['measurements']
            _o = self.param['operation']

            # ----------------------------- FOR UPSETTING -------------------------------
            # Billet orientation before chamfering
            initial_orientation = np.array(_m['principal_coordinate_system'])

            # ----------------------------- ACTUAL PENETRATION -------------------------------
            # Dimensions correction factor
            actual_length = _m['length']
            # one_side_penetration = 0.5 * (actual_length - upsetting_height_final)

            # ----------------------------- TAIL BARREL -------------------------------
            length_excluding_tail_barrels = _m['length_excluding_tail_barrels']
            one_side_average_tail_barrel = 0.5 * (actual_length - length_excluding_tail_barrels)

            # ----------------------------- ELEMENT SIZE -------------------------------
            element_size = _m['elements_edges']['average']

            # ----------------------------- TAIL FROZEN DEPTH -------------------------------
            one_side_tail_frozen_depth = min(
                max(10.0, 0.75 * one_side_average_tail_barrel),  # Tail barrel related
                1.0 * element_size  # Element related
            )
            two_sides_tail_frozen_depth = 2 * one_side_tail_frozen_depth

            # ----------------------------- STROKE -------------------------------
            actual_stroke = actual_length - self.row['final_length']

            # ----------------------------- UPSETTING HEIGHTS -------------------------------
            is_upsetting_frozen = actual_stroke > 0
            is_upsetting_regular = actual_stroke > two_sides_tail_frozen_depth

            if is_upsetting_regular:
                upsetting_height_frozen = actual_length - two_sides_tail_frozen_depth
            else:
                upsetting_height_frozen = self.row['final_length']

            # ----------------------- WINDOW BOXES OF FREEZING BOUNDARY CONDITION -------------------------
            #
            relative_one_side_tail_frozen_depth = two_sides_tail_frozen_depth / actual_length
            _hl = 0.5 - relative_one_side_tail_frozen_depth
            #
            # Window boxes are specified for horizontal billet (Billet length is along X-axis)
            # Box = [[max_x, max_y, max_z],
            #        [min_x, min_y, min_z]]
            xyz = np.array([[_m['length'],
                             _m['width'],
                             _m['height']]])
            # Upsetting 1 with frozen tails
            box_window_1 = [
                xyz * np.array([[0.75, 0.75, 0.75],  # Box3 = +x, -z;
                                [_hl, -0.75, -0.75]]),
                xyz * np.array([[-_hl, 0.75, 0.75],  # Box2 = -x, +z
                                [-0.75, -0.75, -0.75]])]
            # Upsetting 2, regular forming with all free surfaces (window box is outside the billet)
            box_window_2 = [
                xyz * np.array([[1, 0.75, 0.75],  # Box3 = +x, -z;
                                [0.75, -0.75, -0.75]]),
                xyz * np.array([[-0.75, 0.75, 0.75],  # Box2 = -x, +z
                                [-1, -0.75, -0.75]])]

            _o['usrdef_triggers'] = set_triggers(softening_coefficient=0.005,
                                                 is_new_bite=True,
                                                 is_new_operation=True,
                                                 is_new_heat=False)
            forming_orientation = rotate_basis(initial_orientation, [('y', -90)])
            self._run_sub_operation_offset_rotation('initial', forming_orientation)

            if is_upsetting_frozen:
                _o['usrdef_triggers'] = set_triggers(softening_coefficient=0.005,
                                                     is_new_bite=False,
                                                     is_new_operation=False,
                                                     is_new_heat=False)
                self._run_sub_chamfering_stroke_frozen_corners({'sub_operation_name_startswith': 'frozen_tails_upset',
                                                                'remove_fins': False,
                                                                'initial_orientation': initial_orientation,
                                                                'offset': [0, 0, 0],
                                                                'upsetting_height': upsetting_height_frozen,
                                                                'upsetting_penetration': 0,
                                                                'velocity_boundary_condition_bounds_list': box_window_1,
                                                                'fixed_directions_xyz_bool': [True, True, False]})

            if is_upsetting_regular:
                _o['usrdef_triggers'] = set_triggers(softening_coefficient=0.005,
                                                     is_new_bite=False,
                                                     is_new_operation=False,
                                                     is_new_heat=False)
                self._run_sub_chamfering_stroke_frozen_corners({'sub_operation_name_startswith': 'regular_upset',
                                                                'remove_fins': False,
                                                                'initial_orientation': initial_orientation,
                                                                'offset': [0, 0, 0],
                                                                'upsetting_height': self.row['final_length'],
                                                                'upsetting_penetration': 0,
                                                                'velocity_boundary_condition_bounds_list': box_window_2,
                                                                'fixed_directions_xyz_bool': [True, True, False]})

            _o['usrdef_triggers'] = set_triggers(softening_coefficient=0.005,
                                                 is_new_bite=False,
                                                 is_new_operation=False,
                                                 is_new_heat=False)
            # Desired, target orientation
            final_orientation = rotate_basis(forming_orientation, [('y', 90)])
            self._run_sub_operation_offset_rotation('final', final_orientation)

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _run_92_upset_tail_flattening(self):
        """Run 'Upset' operation"""
        try:
            _o = self.param['operation']

            # ----------------------------- MEASUREMENTS -------------------------------
            self._measure_billet_of_previous_sub_operation()
            _m = _o['imported_keyfile']['objects'][1]['measurements']
            initial_orientation = np.array(_m['principal_coordinate_system'])
            # length_along_billet_axis = _m['length']
            element_size = _m['elements_edges']['average']

            # ------------------------ CONTROL PARAMETERS SET forgelabPre -------------------------
            control_penetration = self.row['penetration']
            control_num_of_bites = self.row['num_of_bites']
            ds = self.die_straight_length_min(self.row)

            # ------------------------------------------------------------------------------------------
            # ---------------------- OPERATION: ROTATE TO VERTICAL DIRECTION ---------------------------
            _o['usrdef_triggers'] = set_triggers(softening_coefficient=0.005,
                                                 is_new_bite=True,
                                                 is_new_operation=True,
                                                 is_new_heat=False)
            # Desired, target orientation
            forming_orientation = rotate_basis(initial_orientation, [('y', -90)])
            self._run_sub_operation_offset_rotation('initial', forming_orientation)
            # ------------------------------------------------------------------------------------------
            # ------------------------------------------------------------------------------------------

            # ------------------------------------- MEASUREMENTS ---------------------------------------
            self._measure_billet_of_previous_sub_operation()
            _m = _o['imported_keyfile']['objects'][1]['measurements']
            initial_height = _m['height']
            initial_forming_length = _m['length_excluding_tail_barrels']  # Left and right barrel widths are excluded

            def is_last_bite(_i):
                return _i == control_num_of_bites - 1

            def is_first_bite(_i):
                return _i == 0

            # ---------------------------------- PENETRATION ---------------------------------
            if control_num_of_bites < 3:
                first_penetration = control_penetration
            else:
                first_penetration = 0.7 * control_penetration

            penetration = [first_penetration if is_first_bite(_i) else control_penetration
                           for _i
                           in range(control_num_of_bites)]

            # --------------------------------- FINAL HEIGHTS --------------------------------
            final_upsetting_heights = [(initial_height - penetration[_i])
                                       for _i
                                       in range(control_num_of_bites)]

            # ----------------------------- X-OFFSET OF BILLET -------------------------------
            average_feed = initial_forming_length / control_num_of_bites

            residual_unformed_length = [initial_forming_length - average_feed * (_i + 1)
                                        for _i
                                        in range(control_num_of_bites)]

            def x_offset(_i: int, _cm: dict) -> float:
                half_l_dr = self.die_radius_half_depth_impression_length(self.row, 0.5 * penetration[_i])
                die_length = ds + 2 * half_l_dr
                barrel_length = _cm['left_tail_barrel_length']
                total_length = _cm['length']

                if is_last_bite(_i):
                    return (- 0.5 * total_length
                            + barrel_length
                            + 0.5 * average_feed)
                else:
                    return (- 0.5 * total_length
                            + 0.5 * die_length
                            + barrel_length
                            + residual_unformed_length[_i])

            # ----------------------- WINDOW BOXES OF FREEZING BOUNDARY CONDITION -------------------------
            # Window boxes are specified for horizontal billet (Billet length is along X-axis)
            #
            # Window boxes are specified for horizontal billet (Billet length is along X-axis)
            # Box = [[max_x, max_y, max_z],
            #        [min_x, min_y, min_z]]

            def box_windows_for_bites(_i: int, _bm: dict):
                xyz = np.array([[_bm['height'], _bm['width'], _bm['length']]])  # x - along billet axis

                is_half_of_bites_done = (_i + 1) > math.ceil(control_num_of_bites / 2)

                if is_half_of_bites_done:
                    _h = _bm['height']
                    _b = _bm['left_tail_barrel_length']
                else:
                    _h = final_upsetting_heights[_i]
                    _b = _bm['right_tail_barrel_length']

                axial_frozen_depth = max(0.1 * _h,
                                         1.0 * element_size)
                axial_ratio = 0.5 - axial_frozen_depth / _h

                _r = _bm['length_excluding_tail_barrels']
                radial_frozen_depth = max(0.1 * _r + _b,
                                          0.5 * element_size)
                radial_ratio = 0.5 - radial_frozen_depth / _bm['length']

                if is_half_of_bites_done:
                    return [
                        xyz * np.array([[0.75, 0.75, 0.75],  # Box3 = +x, +z;
                                        [axial_ratio, -0.75, radial_ratio]]),
                        xyz * np.array([[-axial_ratio, 0.75, 0.75],  # Box2 = -x, +z
                                        [-0.75, -0.75, radial_ratio]])]
                else:
                    return [
                        xyz * np.array([[0.75, 0.75, -radial_ratio],  # Box3 = +x, -z;
                                        [axial_ratio, -0.75, -0.75]]),
                        xyz * np.array([[-axial_ratio, 0.75, -radial_ratio],  # Box2 = -x, -z
                                        [-0.75, -0.75, -0.75]])]

            # ------------------------------------------------------------------------------------------
            # ------------------------------ OPERATIONS: BITES -----------------------------------------

            for bite_num in range(control_num_of_bites):
                self._measure_billet_of_previous_sub_operation()
                _cm = _o['imported_keyfile']['objects'][1]['measurements']

                # ------------------------------------- RUN --------------------------------------------
                _o['usrdef_triggers'] = set_triggers(softening_coefficient=0.005,
                                                     is_new_bite=True,
                                                     is_new_operation=False,
                                                     is_new_heat=False)
                self._run_sub_chamfering_stroke_frozen_corners(
                    {'sub_operation_name_startswith': 'frozen_upset',
                     'remove_fins': False,
                     'initial_orientation': initial_orientation,
                     'offset': [x_offset(bite_num, _cm), 0, 0],
                     'upsetting_height': final_upsetting_heights[bite_num],
                     'upsetting_penetration': 0,
                     'velocity_boundary_condition_bounds_list': box_windows_for_bites(bite_num, _cm),
                     'fixed_directions_xyz_bool': [True, True, False]})

            # ------------------------------------------------------------------------------------------
            # ----------------------------- ROTATE BACK TO HORIZONTAL ----------------------------------
            _o['usrdef_triggers'] = set_triggers(softening_coefficient=0.005,
                                                 is_new_bite=True,
                                                 is_new_operation=False,
                                                 is_new_heat=False)
            # Desired, target orientation
            final_orientation = rotate_basis(forming_orientation, [('y', 90)])
            self._run_sub_operation_offset_rotation('final', final_orientation)

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _run_100_tail_chamfering(self):
        """Run 'Upset' operation"""
        try:
            self._measure_billet_of_previous_sub_operation()
            _m = self.param['operation']['imported_keyfile']['objects'][1]['measurements']
            _o = self.param['operation']
            osp = self.row['operation_specific_parameters']

            # Chamfering parameters from forgelabPre
            y_proj = osp['projections']['height_to_length_projection']
            x_proj = osp['projections']['width_to_length_projection']

            # ----------------------------- FOR ROTATION -------------------------------
            # Rotation (chamfering incline) angles
            y_rotation = math.degrees(y_proj['axis_inclination_angle'])
            x_rotation = math.degrees(x_proj['axis_inclination_angle'])
            # --------------------------------------------------------------------------

            # ----------------------------- FOR BOTH, ROTATION & UPSETTING -------------------------------
            # Billet orientation before chamfering
            initial_orientation = np.array(_m['principal_coordinate_system'])
            # --------------------------------------------------------------------------------------------

            # ----------------------------- FOR UPSETTING -------------------------------
            # Dimensions correction factor
            actual_length = _m['length']
            theoretical_length = self.row['initial_length']
            factor = actual_length / theoretical_length
            #
            # Initial height of rotated billet BEFORE upsetting
            # initial_height_1_2 = factor * y_proj['initial_billet_vertical_projection']
            # initial_height_3_4 = factor * x_proj['initial_billet_vertical_projection']
            #
            # Final upsetting height of rotated billet
            upsetting_height_1_2 = factor * y_proj['final_billet_vertical_projection']
            upsetting_height_3_4 = factor * x_proj['final_billet_vertical_projection']

            # ----------------------- FREEZING BOUNDARY CONDITION for 1st UPSETTING -------------------------
            # Box = [[max_x, max_y, max_z],
            #        [min_x, min_y, min_z]]
            # Chamfer # 1
            xyz = np.array([[_m['length'],
                             _m['width'],
                             _m['height']]])
            chamfer1_bounds = [
                xyz * np.array([[0.75, 0.75, -0.15],  # Box3 = +x, -z;
                                [0.25, -0.75, -0.75]]),
                xyz * np.array([[-0.25, 0.75, 0.75],  # Box2 = -x, +z
                                [-0.75, -0.75, 0.15]])]
            # Chamfer # 2
            chamfer2_bounds = [
                xyz * np.array([[0.75, 0.75, 0.75],  # Box3 = +x, +z;
                                [0.25, -0.75, 0.15]]),
                xyz * np.array([[-0.25, 0.75, -0.15],  # Box2 = -x, -z
                                [-0.75, -0.75, -0.75]])]
            # Chamfer # 3
            chamfer3_bounds = [
                xyz * np.array([[0.75, -0.15, 0.75],  # Box3 = +x, -y;
                                [0.25, -0.75, -0.75]]),
                xyz * np.array([[-0.25, 0.75, 0.75],  # Box2 = -x, +y
                                [-0.75, 0.15, -0.75]])]
            # Chamfer # 4
            chamfer4_bounds = [
                xyz * np.array([[0.75, 0.75, 0.75],  # Box3 = +x, +y;
                                [0.25, 0.15, -0.75]]),
                xyz * np.array([[-0.25, -0.15, 0.75],  # Box2 = -x, -y
                                [-0.75, -0.75, -0.75]])]
            # -----------------------------------------------------------------------------------------------

            # ---------------------- CALL CHAMFER UPSETTING FUNCTIONS ---------------------------
            _o['usrdef_triggers'] = set_triggers(softening_coefficient=0.005,
                                                 is_new_bite=True,
                                                 is_new_operation=True,
                                                 is_new_heat=False)
            self._run_sub_chamfering_single_edge({'sub_operation_name_startswith': 'chamfer_1',
                                                  'list_of_rotations_xyz': [('y', y_rotation)],
                                                  'remove_fins': False,
                                                  'initial_orientation': initial_orientation,
                                                  'offset': [0, 0, 0],
                                                  'upsetting_height': upsetting_height_1_2,
                                                  'upsetting_penetration': 0,
                                                  'velocity_boundary_condition_bounds_list': chamfer1_bounds,
                                                  'fixed_directions_xyz_bool': [True, True, False]})
            _o['usrdef_triggers'] = set_triggers(softening_coefficient=0.005,
                                                 is_new_bite=True,
                                                 is_new_operation=False,
                                                 is_new_heat=False)
            self._run_sub_chamfering_single_edge({'sub_operation_name_startswith': 'chamfer_2',
                                                  'list_of_rotations_xyz': [('y', -y_rotation)],
                                                  'remove_fins': False,
                                                  'initial_orientation': initial_orientation,
                                                  'offset': [0, 0, 0],
                                                  'upsetting_height': upsetting_height_1_2,
                                                  'upsetting_penetration': 0,
                                                  'velocity_boundary_condition_bounds_list': chamfer2_bounds,
                                                  'fixed_directions_xyz_bool': [True, True, False]})
            _o['usrdef_triggers'] = set_triggers(softening_coefficient=0.005,
                                                 is_new_bite=True,
                                                 is_new_operation=False,
                                                 is_new_heat=False)
            self._run_sub_chamfering_single_edge({'sub_operation_name_startswith': 'chamfer_3',
                                                  'list_of_rotations_xyz': [('x', x_rotation)],
                                                  'remove_fins': True,
                                                  'initial_orientation': initial_orientation,
                                                  'offset': [0, 0, 0],
                                                  'upsetting_height': upsetting_height_3_4,
                                                  'upsetting_penetration': 0,
                                                  'velocity_boundary_condition_bounds_list': chamfer3_bounds,
                                                  'fixed_directions_xyz_bool': [True, True, False]})
            _o['usrdef_triggers'] = set_triggers(softening_coefficient=0.005,
                                                 is_new_bite=True,
                                                 is_new_operation=False,
                                                 is_new_heat=False)
            self._run_sub_chamfering_single_edge({'sub_operation_name_startswith': 'chamfer_4',
                                                  'list_of_rotations_xyz': [('x', -x_rotation)],
                                                  'remove_fins': True,
                                                  'initial_orientation': initial_orientation,
                                                  'offset': [0, 0, 0],
                                                  'upsetting_height': upsetting_height_3_4,
                                                  'upsetting_penetration': 0,
                                                  'velocity_boundary_condition_bounds_list': chamfer4_bounds,
                                                  'fixed_directions_xyz_bool': [True, True, False]})
            _o['usrdef_triggers'] = set_triggers(softening_coefficient=0.005,
                                                 is_new_bite=True,
                                                 is_new_operation=False,
                                                 is_new_heat=False)
            # Desired, target orientation
            target_orientation = rotate_basis(initial_orientation, [('y', 90)])
            self._run_sub_operation_offset_rotation('final', target_orientation)

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _run_sub_chamfering_single_edge(self, op: dict):
        try:
            target_orientation = rotate_basis(op['initial_orientation'], op['list_of_rotations_xyz'])
            self._run_sub_operation_offset_rotation(op['sub_operation_name_startswith'], target_orientation)
            self._run_sub_chamfering_stroke_frozen_corners(op)
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    @staticmethod
    def _are_fins():
        return False

    @property
    def bite_index(self):
        return self.param['operation']['bite_number']

    @bite_index.setter
    def bite_index(self, value: int):
        self.param['operation']['bite_number'] = value

    def _run_cut(self):
        """Run 'Cut' operation"""
        # TODO: Volume of the cut object MUST coincide with forgelabPre prediction
        try:
            """
            Coordinates of the cutting object (x, y, z) regarding the billet:

            ++ z2 z2 z2 z2 z2 z2 z2 z2 z2 z2 z2 z2 z2 z2 ++
            x0                                           x3
            x0                                           x3
            x0             ++ z1 z1 z1 z1 z1 ++          x3
            x0             x1                x2          x3
            x0    *********************************      x3
            x0    *        x1                x2   *      x3
            x0    *        x1                x2   *      x3
            x0    *********************************      x3
            x0             x1                x2          x3
            x0             x1                x2          x3
            x0             x1                x2          x3
            x0             x1                x2          x3
            ++ z0 z0 z0 z0 ++                ++ z0 z0 z0 ++
            """

            self._set_sub_operation_path('cut')

            self._measure_billet_of_previous_sub_operation()
            _m = self.param['operation']['imported_keyfile']['objects'][1]['measurements']

            _l = _m['length']
            _bounds = np.asarray(_m['bounds'])
            _centroid = np.asarray(_m['centroid'])
            outside_box = 2.0 * (_bounds - _centroid) + _centroid
            cutting_box = 1.5 * (_bounds - _centroid) + _centroid

            match self.row['type_id']:
                case 86:  # Cold sawing n-pieces, keep pieces number k, as long as p-percent.
                    is_skip_cutting, x_cut_bounds = self._cut_x_bounds_for_type_id_86()
                case 99:
                    is_skip_cutting, x_cut_bounds = self._cut_keep_first_tail_length()
                case 100:
                    is_skip_cutting, x_cut_bounds = self._cut_delete_first_tail_length()
                case _:
                    raise ValueError(f"Unknown 'type_id' '{self.row['type_id']}'.")

            x = np.array([outside_box[0, 0],
                          x_cut_bounds[0],
                          x_cut_bounds[1],
                          outside_box[1, 0]])
            y = outside_box[:, 1]
            z = np.array([outside_box[0, 2],
                          cutting_box[0, 2],
                          outside_box[1, 2]])

            self.param['operation']['x_cutting_limits'] = x
            self.param['operation']['y_cutting_limits'] = y
            self.param['operation']['z_cutting_limits'] = z

            self.param['operation']['process_duration'] = max(0.1, self.row['time_before_pass'])

            if is_skip_cutting:

                # ------------------------------------------- RUN HEAT -----------------------------------------
                self.param['operation']['usrdef_triggers'] = set_triggers(softening_coefficient=0.005,
                                                                          is_new_bite=True,
                                                                          is_new_operation=True,
                                                                          is_new_heat=False)

                # ----------------------------------- INITIALIZE INGOT AXIS --------------------------------------
                self.param['operation']['is_initialize_user_nodal_for_ingot_axis'] = True

                # --------------------------------------- RUN ----------------------------------------------------
                operation = HeatOp(self.param)
                operation.run()

            else:

                # ------------------------------------------- RUN CUT ------------------------------------------
                self.param['operation']['usrdef_triggers'] = set_triggers(softening_coefficient=0.005,
                                                                          is_new_bite=False,
                                                                          is_new_operation=False,
                                                                          is_new_heat=False)
                # ----------------------------------- INITIALIZE INGOT AXIS --------------------------------------
                self.param['operation']['is_initialize_user_nodal_for_ingot_axis'] = True

                # --------------------------------------- RUN ----------------------------------------------------
                operation = CutOp(self.param)
                operation.run()

                self._finalize_sub_operation()

                # ------------------------------------------- RUN REMESH ----------------------------------------

                self._set_sub_operation_path('remeshing')
                self._measure_billet_of_previous_sub_operation()
                self._cut_logging_final_length()

                match self.row['type_id']:
                    case 86:
                        duration = 1.0
                    case _:
                        duration = self._cut_calculate_process_duration_after_cut()

                self.param['operation']['process_duration'] = duration
                self.param['operation']['usrdef_triggers'] = set_triggers(softening_coefficient=0.005,
                                                                          is_new_bite=False,
                                                                          is_new_operation=False,
                                                                          is_new_heat=False)
                # ----------------------------------- INITIALIZE INGOT AXIS --------------------------------------
                self.param['operation']['is_initialize_user_nodal_for_ingot_axis'] = True

                # --------------------------------------- RUN ----------------------------------------------------
                operation = RemeshOp(self.param)
                operation.run()

            # ------------------------------------------- FINALIZE ------------------------------------------

            self._finalize_sub_operation()

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _finalize_sub_operation(self):
        try:
            self.param['previous_operation'] = self.param['operation'].copy()

            while len(self.sub_operation_list) > self.sub_operation_number:
                self.sub_operation_list.pop()
            self.sub_operation_list.append(self.param['operation'].copy())

            self.sub_operation_number += 1
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise


    def _measure_billet(self):
        """Import objects from 'operation/sub_operation_path' and measure them."""
        try:
            extract_dir_name: str = config.server['billet_extract_dir_name']
            path = sub_operation_abs_path(self.param)
            billet_file_path = os.path.join(path, extract_dir_name, 'Object00001.KEY')

            self.param['operation']['imported_keyfile'] = read_deform_keyfile(billet_file_path)
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _measure_billet_of_previous_sub_operation(self):
        """Import objects from 'previous_sub_operation_path' and measure them."""
        try:
            local_dir: str = config.server['local_dir']
            previous_billet: str = self.param['previous_operation']['billet_file_sub_operation_extract_relative_path']
            billet_file_path = os.path.join(local_dir, previous_billet)

            self.param['operation']['imported_keyfile'] = read_deform_keyfile(billet_file_path)
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _set_sub_operation_path(self, _sub_operation_type: str):
        # TODO: Move generation of Dir names into forgelabPre
        try:
            self.param['operation']['sub_operation_type'] = _sub_operation_type

            _type = _sub_operation_type

            if _type == 'cooling':
                _d = f"_cooling_{int(self.param['operation']['process_duration']):d}s"
            elif _type == 'heating':
                _d = f"_heating_{int(self.param['operation']['process_duration']):d}s"
            elif _type == 'bite':
                _d = f"_bite_{self.bite_index :d}_of_{self.row['num_of_bites'] - 1:d}"
            elif _type == 'rotate':
                _d = f"_rotate_{self.row['angle']}deg"
            elif _type == 'rotate_to_vertical':
                _d = "_rotate_to_vertical"
            elif _type == 'rotate_to_horizontal':
                _d = "_rotate_to_horizontal"
            elif _type == 'centering':
                _d = '_centering'
            elif _type == 'cut':
                _d = '_cut'
            elif _type == 'remeshing':
                _d = '_remeshing'
            elif _type == 'new_billet':
                _d = '_create_billet'
            else:
                _d = '_' + _type

            local_dir = config.server['local_dir']
            operation_relative_path = self.param['operation']['operation_relative_path']
            extract_dir_name = config.server['billet_extract_dir_name']
            sub_operation_name = f"{self.sub_operation_number:0>4d}{_d}"

            sub_operation_relative_path = os.path.join(operation_relative_path, sub_operation_name)
            sub_operation_extract_relative_path = os.path.join(sub_operation_relative_path, extract_dir_name)
            extract_file_relative_path = os.path.join(sub_operation_extract_relative_path, 'Object00001.KEY')
            sub_operation_path = os.path.join(local_dir, sub_operation_relative_path)

            self.param['operation'] |= {
                'sub_operation_name': sub_operation_name,
                'sub_operation_relative_path': sub_operation_relative_path,
                'sub_operation_relative_initial_billet_file_path': os.path.join(sub_operation_relative_path, 'Objects', 'Object00001.KEY'),
                'sub_operation_extract_relative_path': sub_operation_extract_relative_path,
                'billet_file_sub_operation_extract_relative_path': extract_file_relative_path,
                'sub_operation_path': sub_operation_path
            }

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def __previous_operation_dir(self):
        try:
            local_dir = config.server['local_dir']
            project_dir_name = self.param['project']['project_dir_name']
            previous_operation_number = self.eo - 1
            previous_operation_dir = os.path.join(local_dir, project_dir_name, str(previous_operation_number))
            return previous_operation_dir
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise


    def _logging_start_simulation(self):
        try:
            relative_elem_size = self.param['operation']['relative_min_element_size']
            project_dir_name: str = self.param['project']['project_dir_name']
            operation_dir_name: str = self.param['operation']['operation_name']
            operation_type: str = self.row['operation_type']

            number_of_elements_in_thickness = int(round(1 / relative_elem_size, 0))
            relative_operation_dir = os.path.join(project_dir_name, operation_dir_name)
            LOGGER.info(
                f"{self.log_id} "
                f"SIMULATION STARTED at %s Operation path = '%s' Operation Type = '%s' Relative element size 1/%d",
                datetime.now().strftime('%H:%M:%S'),
                relative_operation_dir,
                operation_type,
                number_of_elements_in_thickness)
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _logging_start_operation(self):
        try:
            LOGGER.info(
                "Op.Num.: %d Op.Type: %s started at %s and total running time of Simulation is %.0f min",
                self.eo,
                self.row['operation_type'],
                datetime.now().strftime('%H:%M:%S'),
                (time.monotonic() - self.param['operation']['project_start_datetime']) / 60.0)
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _logging_operation_is_not_supported(self):
        try:
            operation_type = self.row['operation_type']
            _string_of_spaces = ' ' * (9 + len(operation_type))
            LOGGER.info(
                "Op.Num.: %d %s Operation type %s is not supported",
                self.eo + 1,
                _string_of_spaces,
                operation_type)
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _logging_successfully_finished_operation(self):
        # _string_of_spaces = ' ' * (9 + len(self.row['operation_type']))
        try:
            LOGGER.info(
                f"{self.log_id} SIMULATION IS FINISHED "
                f"Running Time = {(time.monotonic() - self.param['operation']['project_start_datetime']) / 60.0: .1f} min")
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    # -----------------------------------------------------------------
    # -------------------------- UPSETTING ----------------------------

    def positioning_length_for_left_bite(self) -> float:
        """Calculate the starting position of die for Upsetting with three bites (middle + right + left)"""
        try:
            die_straight_length, forged_length_excl_barrels, total_length = self.get_lengths_for_left_and_right_bites()
            return 0.5 * total_length - 0.5 * forged_length_excl_barrels - 0.4 * die_straight_length
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def positioning_length_for_right_bite(self) -> float:
        """Calculate the starting position of die for Upsetting with three bites (middle + right + left)"""
        try:
            die_straight_length, forged_length_excl_barrels, total_length = self.get_lengths_for_left_and_right_bites()
            return 0.5 * total_length + 0.5 * forged_length_excl_barrels + 0.25 * die_straight_length
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def get_lengths_for_left_and_right_bites(self):
        """Returns die length, straight width of upset tail, total length (width) of upset billet"""
        try:
            die_straight_length = min(
                config.lib['die'].loc[self.row['top_die_id']]['dimensions']['straight_length'],
                config.lib['die'].loc[self.row['bottom_die_id']]['dimensions']['straight_length'])
            total_length = self.param['operation']['imported_keyfile']['objects'][1]['measurements']['length']
            actual_dim = self.param['operation']['imported_keyfile']['objects'][1]['measurements']
            length_excl_tail_barrels = actual_dim['length_excluding_tail_barrels']
            forged_length_excl_barrels = min(
                0.5 * die_straight_length + 0.5 * length_excl_tail_barrels,
                length_excl_tail_barrels)
            return die_straight_length, forged_length_excl_barrels, total_length
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def __residual_length_for_one_or_three_upsetting(self):
        try:
            top_die_dimensions = config.lib['die'].loc[self.row['top_die_id']]['dimensions']
            bottom_die_dimensions = config.lib['die'].loc[self.row['bottom_die_id']]['dimensions']

            die_radius = min(top_die_dimensions['edge_radius'], bottom_die_dimensions['edge_radius'])
            max_residual_height = min(
                20.0,
                0.025 * self.row['final_height'],
                0.5 * die_radius)
            allowed_residual_length = math.sqrt(2.0 * die_radius * max_residual_height - max_residual_height ** 2)

            actual_dim = self.param['operation']['imported_keyfile']['objects'][1]['measurements']
            length_excl_tail_barrels = actual_dim['length_excluding_tail_barrels']
            die_straight_length = min(top_die_dimensions['straight_length'], bottom_die_dimensions['straight_length'])
            residual_length = 0.5 * (length_excl_tail_barrels - die_straight_length)
            if residual_length > allowed_residual_length:
                return residual_length
            return 0.0
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise


    def get_actual_length(self):
        """Get actual residual and forged lengths"""
        try:
            actual_dim = self.param['operation']['imported_keyfile']['objects'][1]['measurements']
            feed = actual_dim['length_excluding_tail_barrels'] / self.row['num_of_bites']
            forged_length = feed * (self.bite_index + 1)
            length_excl_left_tail = actual_dim['length_excluding_tail_barrels'] + actual_dim['right_tail_barrel_length']
            length_excl_right_tail = actual_dim['length_excluding_tail_barrels'] + actual_dim['left_tail_barrel_length']
            return forged_length, length_excl_left_tail, length_excl_right_tail
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def get_num_of_bites_left(self):
        """Calculate residual number of bites to do"""
        try:
            num_of_bites_done = self.bite_index + 1
            return self.row['num_of_bites'] - num_of_bites_done
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def die_straight_length(self):
        try:
            top_die_dimensions = config.lib['die'].loc[self.row['top_die_id']]['dimensions']
            bottom_die_dimensions = config.lib['die'].loc[self.row['bottom_die_id']]['dimensions']
            return min(top_die_dimensions['straight_length'], bottom_die_dimensions['straight_length'])
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _tail(self):
        try:
            _m = self.param['operation']['imported_keyfile']['objects'][1]['measurements']
            right_tail = _m['right_tail_barrel_length']
            left_tail = _m['left_tail_barrel_length']
            feed_direction = self.row['feed_direction_name']
            return right_tail if (feed_direction == '==>') else left_tail
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _cut_calculate_process_duration_after_cut(self) -> float:
        """Save process duration to self.param['operation']['process_duration']"""
        try:
            num_of_pieces = self.row['num_of_bites']
            cycle_time = self.row['cycle_time']
            step_control = self.row['step_control']
            piece_number_to_keep = self.row['k1']
            time_between_bites = self.row['time_between_bites']

            is_divide_by_two = step_control != 'Equals' or num_of_pieces <= 2

            if is_divide_by_two:
                process_duration = 0.5 * cycle_time
            else:
                is_keep_last_piece = piece_number_to_keep == num_of_pieces

                if is_keep_last_piece:
                    count = piece_number_to_keep - 1
                else:
                    count = piece_number_to_keep

                process_duration = cycle_time * (num_of_pieces - count - 0.5) - 0.5 * time_between_bites

            return process_duration
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _cut_logging_final_length(self):
        try:
            _m = self.param['operation']['imported_keyfile']['objects'][1]['measurements']
            _final_length_actual = _m['length']
            x_bounds = self.param['operation']['x_cutting_limits'][1:3]
            _final_length_target = x_bounds[0] - x_bounds[1]
            _actual_length_relative_difference = abs(_final_length_actual / _final_length_target - 1.)
            if _actual_length_relative_difference > 0.01:  # Difference > 1%
                LOGGER.info(
                    f"Relative length difference after cutting is {_actual_length_relative_difference:+.1%}"
                    f" when actual length is {_final_length_actual:.1f} mm"
                    f" and target length is {_final_length_target:.1f} mm.")

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _cut_x_bounds_for_type_id_86(self) -> tuple[bool, np.array]:
        # x-coordinates of tails [x_min, x_max]
        try:
            _m = self.param['operation']['imported_keyfile']['objects'][1]['measurements']
            _bounds = np.asarray(_m['bounds'])
            _centroid = np.asarray(_m['centroid'])
            cutting_box = 1.5 * (_bounds - _centroid) + _centroid

            _o = self.row['operation_specific_parameters']
            pieces_count = _o['pieces_count']
            piece_number = _o['piece_number']
            percentage_to_keep = _o['percentage_to_keep']

            # ---------------------------- ASSERT INPUT VALUES -------------------------------------
            is_skip_cutting = any((pieces_count < 2,
                                   piece_number < 1,
                                   piece_number > pieces_count,
                                   percentage_to_keep <= 0.0,
                                   percentage_to_keep >= 100.0))
            if is_skip_cutting:
                return True, cutting_box[:, 0]

            # ---------------------------- CALCULATE CUTTING BOUNDS ---------------------------------

            # Relative lengths of pieces:
            # rl_keep = relative length of keep piece
            # rl_remove = relative length of removed piece
            rl_keep = self.row['final_length'] / self.row['initial_length']
            rl_remove = (1.0 - rl_keep) / (pieces_count - 1)

            # Relative lengths of pieces (a list)
            piece_index = piece_number - 1

            def is_keep_piece(_i):
                return _i == piece_index

            # Pieces relative lengths
            rl = [rl_keep if is_keep_piece(i) else rl_remove for i in range(pieces_count)]

            # Divide range 0..1 by pieces relative lengths 'rl'
            rl_cutting_points = np.cumsum([0.0] + rl)

            # Move external points out of billet tails
            rl_cutting_points[0] = rl_cutting_points[0] - 0.1
            rl_cutting_points[-1] = rl_cutting_points[-1] + 0.1

            # Convert relative lengths to absolute lengths
            rl_cutting_points = _m['length'] * rl_cutting_points

            # Shift cutting points to the beginning of billet x-bounds
            x_cutting_points = rl_cutting_points + _bounds[0, 0]

            # Select two points of 'piece_number'
            i1 = piece_number - 1
            i2 = i1 + 2
            x_axis_cutting_limits = x_cutting_points[i1: i2]

            return False, x_axis_cutting_limits
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _cut_keep_first_tail_length(self) -> tuple[bool, np.array]:
        try:
            _bounds = np.asarray(self.param['operation']['imported_keyfile']['objects'][1]['measurements']['bounds'])
            x_bounds = _bounds[:, 0]

            # length
            initial_length = self.row['initial_length']
            final_length = self.row['final_length']
            skip_cutting = final_length >= initial_length

            # if skip cutting
            if skip_cutting:
                return True, x_bounds
            else:
                x_axis_cutting_limits = self.__cut_calculate_cutting_bounds(final_length,
                                                                            initial_length,
                                                                            x_bounds,
                                                                            'Keep')

            return False, x_axis_cutting_limits
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _cut_keep_first_tail_percent(self):
        try:
            _bounds = np.asarray(self.param['operation']['imported_keyfile']['objects'][1]['measurements']['bounds'])
            x_bounds = _bounds[:, 0]

            # length
            initial_length = self.row['initial_length']
            percent = self.row['relative_deformation']
            skip_cutting = any((
                percent >= 100.0,
                percent <= 0.0))

            # if skip cutting
            if skip_cutting:

                self.row['final_length'] = self.row['initial_length']
                self.param['operation']['x_axis_cutting_limits'] = x_bounds
            else:
                # length
                final_length = initial_length * percent / 100.0
                x_axis_cutting_limits = self.__cut_calculate_cutting_bounds(final_length,
                                                                            initial_length,
                                                                            x_bounds,
                                                                            'Keep')

                self.row['final_length'] = final_length
                self.param['operation']['x_axis_cutting_limits'] = x_axis_cutting_limits

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _cut_delete_first_tail_length(self) -> tuple[bool, np.array]:
        try:
            _bounds = np.asarray(self.param['operation']['imported_keyfile']['objects'][1]['measurements']['bounds'])
            x_bounds = _bounds[:, 0]

            initial_length = self.row['initial_length']
            penetration = self.row['penetration']
            skip_cutting = any((
                penetration >= initial_length,
                penetration <= 0.0))

            # if skip cutting
            if skip_cutting:
                return True, x_bounds
            else:
                # length
                final_length = initial_length - penetration
                x_axis_cutting_limits = self.__cut_calculate_cutting_bounds(final_length,
                                                                            initial_length,
                                                                            x_bounds,
                                                                            'Delete')
            return False, x_axis_cutting_limits
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _cut_delete_first_tail_percent(self):
        try:
            _bounds = np.asarray(self.param['operation']['imported_keyfile']['objects'][1]['measurements']['bounds'])
            x_bounds = _bounds[:, 0]

            initial_length = self.row['initial_length']
            percent = self.row['relative_deformation']

            skip_cutting = percent >= 100.0 or percent <= 0.0

            # if skip cutting
            if skip_cutting:
                self.row['final_length'] = self.row['initial_length']
                self.param['operation']['x_axis_cutting_limits'] = x_bounds
            else:
                # length
                final_length = initial_length * (1.0 - percent / 100.0)
                x_axis_cutting_limits = self.__cut_calculate_cutting_bounds(final_length,
                                                                            initial_length,
                                                                            x_bounds,
                                                                            'Delete')

                self.row['final_length'] = final_length
                self.param['operation']['x_axis_cutting_limits'] = x_axis_cutting_limits

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def __cut_calculate_cutting_bounds(self, final_length, initial_length, x_bounds, keep_or_delete):
        try:
            left_to_right: bool
            keep_left_tail: bool
            assert keep_or_delete in ['Delete', 'Keep']

            total_x_min = x_bounds[0]
            total_x_max = x_bounds[1]

            left_to_right = self.row['feed_direction_name'] == '==>'
            keep_left_tail = not left_to_right if keep_or_delete == 'Delete' else left_to_right

            if keep_left_tail:
                bounds = [total_x_max - final_length, total_x_max + 0.1 * initial_length]  # [x_min, x_max]
            else:
                bounds = [total_x_min - 0.1 * initial_length, total_x_min + final_length]  # [x_min, x_max]
            bounds.sort()
            return np.array(bounds).T
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def feed_middle(self):
        """Return '0' if 'feed_middle' is None."""
        try:
            feed = self.row['feed_middle']
            return 0.0 if feed is None else feed
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def feed_last(self):
        """Return '0' if 'feed_last' is None."""
        try:
            feed = self.row['feed_last']
            return 0.0 if feed is None else feed
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _run_52_full_die_simple(self):
        """Run 'Upset' operation"""
        try:

            # ------------------------ CONTROL PARAMETERS SET forgelabPre -------------------------
            angle: float = self.row['angle']

            # ------------------------------------------------------------------------------------------
            # ------------- OPERATION: ROTATE TO HORIZONTAL, BUT BILLET AXIS IS ALONG Y-AXIS -----------
            # ------------------------------------------------------------------------------------------

            # TODO: Rotation around billet axis is wrong. Unknown reason.

            # Measure Actual billet orientation
            self._measure_billet_of_previous_sub_operation()
            _m = self.param['operation']['imported_keyfile']['objects'][1]['measurements']
            _o = self.param['operation']

            actual_cs = np.array(_m['principal_coordinate_system'])

            # Transform initial orientation into ideal horizontal one
            # corrected_initial_cs = correct_orientation_from_nearly_horizontal_to_ideal_horizontal(actual_cs)

            # Check difference between actual and ideal horizontal orientation
            # dr = euler_angles_of_basis_to_basis_transformation(actual_cs, corrected_initial_cs)
            # LOGGER.info(f"Execution_order {self.row['execution_order']} "
            #             f"Operation type: Full die "
            #             f"Step: 0 "
            #             f"Rotation angles: Z{round(dr[0], 1)} Y{round(dr[1], 1)} X{round(dr[2], 1)} ")

            # Rotate to vertical RY=-90
            # Then - to horizontal RX=90 (axis points to operator)
            # Finally rotate around billet axis RY=angle
            target_upsetting_orientation = rotate_basis(actual_cs, [('y', -90), ('x', 90), ('y', angle)])

            # Run operation
            _o['usrdef_triggers'] = set_triggers(softening_coefficient=0.005,
                                                 is_new_bite=True,
                                                 is_new_operation=True,
                                                 is_new_heat=False)
            self._run_sub_operation_offset_rotation_with_list_of_rotations({
                'sub_operation_name_startswith': 'initial',
                'target_orientation': target_upsetting_orientation})
            # ------------------------------------------------------------------------------------------
            # ------------------------------ END OF OPERATION ------------------------------------------
            # ------------------------------------------------------------------------------------------
            #
            #
            #
            # ------------------------------------------------------------------------------------------
            # ------------- FORMING OPERATION, STEP 1: SMALL PENETRATION WITH FROZEN NODES -------------
            # ------------------------------------------------------------------------------------------

            # Measure Billet
            self._measure_billet_of_previous_sub_operation()
            _m = _o['imported_keyfile']['objects'][1]['measurements']
            element_size = _m['elements_edges']['average']
            lx: float = _m['length']
            ly: float = _m['width']
            lz: float = _m['height']

            # Stopping criteria: Press Load for Step 1
            average_billet_strain = 0.2
            average_billet_strain_rate = self.row['speed'] / lz
            max_billet_temperature = self.row['max_temperature']
            flow_stress = self.param['material'].flow_stress(average_billet_strain,
                                                             average_billet_strain_rate,
                                                             max_billet_temperature)
            number_of_contact_elements = 5
            element_area = 0.433 * element_size ** 2
            upsetting_press_load = number_of_contact_elements * element_area * flow_stress

            # Stopping criteria: Upsetting height for Step 2
            final_upsetting_height_step_2 = self.row['final_height']

            # Stopping criteria: PENETRATION
            penetration_step_2 = lz - final_upsetting_height_step_2

            penetration_step_1 = min(0.2 * penetration_step_2,
                                     1.0 * element_size)

            # Stopping criteria: Upsetting height for Step 1
            final_upsetting_height_step_1 = lz - penetration_step_1

            # Skip forming operation TRIGGER
            if penetration_step_2 < 0.0:
                is_skip_forming = True
            else:
                is_skip_forming = False

            # Set WINDOW BOXES OF FREEZING BOUNDARY CONDITION
            # Window boxes are specified for horizontal billet (Billet length is along X-axis)
            # Box = [[max_x, max_y, max_z],
            #        [min_x, min_y, min_z]]

            dz = max(0.1 * lz,
                     0.75 * element_size)
            z_min = dz / lz

            dx = max(0.1 * lx,
                     0.5 * element_size)
            x_min = 0.5 - dx / lx

            xyz = np.array([[lx, ly, lz]])

            box_windows_for_bites = [
                xyz * np.array([[0.75, 0.75, z_min],  # Box3 = +x, -z;
                                [x_min, -0.75, -z_min]]),
                xyz * np.array([[-x_min, 0.75, z_min],  # Box2 = -x, -z
                                [-0.75, -0.75, -z_min]])]

            # Run operation
            if not is_skip_forming:
                _o['usrdef_triggers'] = set_triggers(softening_coefficient=0.005,
                                                     is_new_bite=True,
                                                     is_new_operation=False,
                                                     is_new_heat=False)
                self._run_sub_forming_with_frozen_nodes_inside_bcc_windows({
                    'sub_operation_name_startswith': 'frozen_upset',
                    'remove_fins': False,
                    'initial_orientation': None,
                    'offset': [0, 0, 0],
                    'upsetting_height': final_upsetting_height_step_1,
                    'upsetting_penetration': penetration_step_1,
                    'upsetting_press_load': upsetting_press_load,
                    'velocity_boundary_condition_bounds_list': box_windows_for_bites,
                    'fixed_directions_xyz_bool': [True, True, False]
                })
            # ------------------------------------------------------------------------------------------
            # ------------------------------ END OF OPERATION ------------------------------------------
            # ------------------------------------------------------------------------------------------
            #
            #
            #
            # ------------------------------------------------------------------------------------------
            # -------------------- FORMING OPERATION, STEP 2: NORMAL FORMING ---------------------------
            # ------------------------------------------------------------------------------------------

            # Set WINDOW BOXES OF FREEZING BOUNDARY CONDITION
            # Window boxes are specified for horizontal billet (Billet length is along X-axis)
            # Box = [[max_x, max_y, max_z],
            #        [min_x, min_y, min_z]]

            box_windows_for_bites = [
                xyz * np.array([[1.0, 0.75, 0.75],  # Box3 = +x, -z;
                                [0.75, -0.75, -0.75]]),
                xyz * np.array([[-0.75, 0.75, 0.75],  # Box2 = -x, -z
                                [-1.0, -0.75, -0.75]])]

            # Run operation
            if not is_skip_forming:
                _o['usrdef_triggers'] = set_triggers(softening_coefficient=0.005,
                                                     is_new_bite=False,
                                                     is_new_operation=False,
                                                     is_new_heat=False)
                self._run_sub_forming_with_frozen_nodes_inside_bcc_windows({
                    'sub_operation_name_startswith': 'free_upset',
                    'remove_fins': False,
                    'initial_orientation': None,
                    'offset': [0, 0, 0],
                    'upsetting_height': final_upsetting_height_step_2,
                    'upsetting_penetration': 0.0,
                    'upsetting_press_load': 0,
                    'velocity_boundary_condition_bounds_list': box_windows_for_bites,
                    'fixed_directions_xyz_bool': [True, True, False]
                })
            # ------------------------------------------------------------------------------------------
            # ------------------------------ END OF OPERATION ------------------------------------------
            # ------------------------------------------------------------------------------------------
            #
            #
            #
            # ------------------------------------------------------------------------------------------
            # -------------------------------------- ROTATE BACK  --------------------------------------
            # ------------------------------------------------------------------------------------------
            # Rotate to vertical RY=-90
            # Then - to horizontal RX=90
            # Finally rotate around billet axis RY=angle

            # After upsetting billet axis points ot Operator
            # Rotate to vertical RX=-90
            # Rotate to horizontal RY=90 (axis coincide with manipulator axis)
            manipulator_coaxial_orientation = rotate_basis(target_upsetting_orientation, [('z', -90), ('y', 90)])
            # Run operation
            _o['usrdef_triggers'] = set_triggers(softening_coefficient=0.005,
                                                 is_new_bite=True,
                                                 is_new_operation=False,
                                                 is_new_heat=False)
            self._run_sub_operation_offset_rotation_with_list_of_rotations({
                'sub_operation_name_startswith': 'final',
                'target_orientation': manipulator_coaxial_orientation
            })
            # ------------------------------------------------------------------------------------------
            # ------------------------------ END OF OPERATION ------------------------------------------
            # ------------------------------------------------------------------------------------------

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _run_sub_operation_offset_rotation_with_list_of_rotations(self, op: dict):
        """call this method from operation_sequence method"""
        try:
            self._measure_billet_of_previous_sub_operation()
            _o = self.param['operation']
            _m = self.param['operation']['imported_keyfile']['objects'][1]['measurements']
            actual_orientation = np.array(_m['principal_coordinate_system'])

            # Transform Current orientation into Target one. Then Convert to Euler angles.
            z_angle, y_angle, x_angle = basis_to_basis_transformation_as_euler_angles_zyx(actual_orientation, op['target_orientation'])

            # Rounded Rotation angles
            _o['rotation_around_z'] = np.round(z_angle, decimals=2)
            _o['rotation_around_y'] = np.round(y_angle, decimals=2)
            _o['rotation_around_x'] = np.round(x_angle, decimals=2)

            # Offset Billet to the Center of Mass
            center_of_mass = np.round(np.array(_m['center_of_mass']), decimals=2)
            offset = -center_of_mass

            _o['offset_x'] = offset[0]
            _o['offset_y'] = offset[1]
            _o['offset_z'] = offset[2]

            # Chamfer number
            operation_name = f"{op['sub_operation_name_startswith']}_offset_and_rotate"
            LOGGER.info(f"{self.log_id} Start operation '{operation_name}'. "
                        f"Rotate billet around axes (X, Y, Z) = "
                        f"({_o['rotation_around_x']}, {_o['rotation_around_y']}, {_o['rotation_around_z']}) [deg]. "
                        f"Offset (X, Y, Z) = ({_o['offset_x']}, {_o['offset_y']}, {_o['offset_z']})."
                        )

            self._set_sub_operation_path(operation_name)

            # ----------------------------------- INITIALIZE INGOT AXIS --------------------------------------
            self.param['operation']['is_initialize_user_nodal_for_ingot_axis'] = True

            # -------------------------------------------- RUN -----------------------------------------------
            operation = OffsetRotationOp(self.param)
            operation.run()

            self._finalize_sub_operation()

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _run_sub_forming_with_frozen_nodes_inside_bcc_windows(self, op: dict):
        """
        2nd step of single bite for chamfering a tail edge.
        Do:
        1. centering;
        2. fix nodal velocity in X, Y and Z directions of two free billet corners;
        3. short forming stroke to form a flat contact surface between the die and the billet.
        When 2nd step is finished, then 3rd step must be called.
        """
        try:

            # Measure Billet
            self._measure_billet_of_previous_sub_operation()
            measurements = self.param['operation']['imported_keyfile']['objects'][1]['measurements']
            actual_orientation = np.array(measurements['principal_coordinate_system'])

            # FREEZING
            self.param['operation']['initial_local_coordinate_system'] = actual_orientation
            self.param['operation']['current_local_coordinate_system'] = actual_orientation
            self.param['operation']['velocity_boundary_condition_bounds_list'] = \
                op['velocity_boundary_condition_bounds_list']
            self.param['operation']['fixed_directions_xyz_bool'] = op['fixed_directions_xyz_bool']

            # STOPPING CRITERIA
            self.param['operation']['stopping_criteria_die_distance'] = op['upsetting_height']
            self.param['operation']['stopping_criteria_die_displacement'] = op['upsetting_penetration']
            self.param['operation']['user_defined_limit_press_load'] = op['upsetting_press_load']

            # OFFSET the BILLET
            self.param['operation']['offset_x'] = op['offset'][0]
            self.param['operation']['offset_y'] = op['offset'][1]
            self.param['operation']['offset_z'] = op['offset'][2]

            # OPERATION NAME
            operation_name = (f"{op['sub_operation_name_startswith']}_upset_with_frozen_corners_height_"
                              f"{int(round(op['upsetting_height'], 0))}")
            self._set_sub_operation_path(operation_name)

            # LOGGING
            LOGGER.info(f"{self.log_id} Start operation '{operation_name}'. "
                        f"Offset (X, Y, Z) = "
                        f"({self.param['operation']['offset_x']}, "
                        f"{self.param['operation']['offset_y']}, "
                        f"{self.param['operation']['offset_z']})")

            # ----------------------------------- INITIALIZE INGOT AXIS --------------------------------------
            self.param['operation']['is_initialize_user_nodal_for_ingot_axis'] = True

            # --------------------------------------- RUN ----------------------------------------------------
            operation = FormingFrozenSpeedWindowBoxesOp(self.param)
            operation.run()

            self._finalize_sub_operation()

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _save_parameters_json(self):
        try:
            local_dir: str = config.server['local_dir']
            operation_relative_path: str = self.param['operation']['operation_relative_path']
            filepath = os.path.join(local_dir, operation_relative_path, "parameters.json")
            self.write_operation_parameters_json(filepath)
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def write_operation_parameters_json(self, filepath: str):
        try:
            param_converted = convert_dict_values_to_json_compatible_types(self.param['operation'].copy())
            _text = json.dumps(param_converted, indent=4)
            with opened_w_error(filepath, 'w', 'utf-8') as (_file, _err):
                if _err:
                    LOGGER.error(f"IOError: {_err}")
                    raise
                else:
                    _file.write(_text)
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _copy_to_nas(self):
        """Backup (copy) files from Server to NAS: DB file, solved operation dir."""
        # LOGGER.info("START func '_backup_solved_operation_and_db_file_to_nas'")
        try:
            timestamp = time.monotonic()
            LOGGER.info(f"{self.log_id} COPY to NAS: START")
            self._copy_to_nas_current_operation_dir()
            if self.eo > 0:
                self._copy_to_nas_db_file()
            _duration = time.monotonic() - timestamp
            _h, _h_fraction = int(_duration // 3600), _duration % 3600
            _m, _s = int(_h_fraction * 60 // 60), int(_h_fraction * 60 % 60)
            LOGGER.info(f"{self.log_id} COPY to NAS: FINISH (duration {_h:02}:{_m:02}:{_s:02}")
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _copy_to_nas_current_operation_dir(self):
        """
        Copy solved current operation directory from Server to NAS.
        """
        try:
            local_dir: str = config.server['local_dir']
            nas_dir: str = config.nas['absolute_path']
            project_dir_name: str = self.param['project']['project_dir_name']
            operation_relative_path: str = self.param['operation']['operation_relative_path']

            src_dir = os.path.join(local_dir, operation_relative_path)
            dst_dir = os.path.join(nas_dir, operation_relative_path)
            dst_parent_dir = os.path.join(nas_dir, project_dir_name)

            assert is_local_dir_exist()
            assert is_smb_file_server_available()
            assert os.path.exists(src_dir), f"Source directory '{src_dir}' does not exist."
            if self.eo > 0 and not smbclient.path.exists(dst_parent_dir):
                LOGGER.warning(
                    f"Project dir '{dst_parent_dir}' does not exist on NAS "
                    f"for 'execution_order'={self.eo} which may be is result of some error. "
                    f"The dir '{dst_parent_dir}' will be created automatically by 'shutil.copytree' func.")

            if self.eo == 0:
                create_new_dir_or_clean_existing_dir(dst_parent_dir), \
                    f"Failed creating empty project directory '{dst_parent_dir}' on NAS."

            if os.path.exists(dst_dir):
                shutil.rmtree(dst_dir)
                LOGGER.info(f"{self.log_id} Removed old operation dir '{dst_dir}' on NAS before copying new solved operation dir.")

            smbclient.shutil.copytree(src_dir, dst_dir)
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _copy_to_nas_db_file(self):
        """
        Copy DB file from Server to NAS.
        """
        try:
            local_dir: str = config.server['local_dir']
            db_file_path: str = self.param['operation']['db_file_relative_path']
            src_file = os.path.join(local_dir, db_file_path)

            nas_dir: str = config.nas['absolute_path']
            project_dir_name: str = self.param['project']['project_dir_name']
            dst_dir = os.path.join(nas_dir, project_dir_name)

            assert is_local_dir_exist()
            assert is_smb_file_server_available()
            _p, _f = os.path.split(src_file)
            assert os.path.exists(_p), f"Directory '{_p}' does not exist in the local Server."
            assert os.path.isfile(src_file), f"File '{src_file}' does not exist."
            assert smbclient.path.exists(dst_dir), f"Destination directory '{dst_dir}' does not exist on NAS."

            smbclient.shutil.copy2(src_file, dst_dir)

            dst_file = os.path.join(dst_dir, _f)
            assert smbclient.path.isfile(dst_file), f"File '{dst_file}' does not exist on NAS. Copying failed."

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _query_update_server_pre_main_set_status_queue(self):
        try:
            operation_dir_name: str = self.param['operation']['operation_name']
            sub_operation_relative_path: str = self.param['operation']['sub_operation_relative_path']
            billet_file: str = self.param['operation']['billet_file_sub_operation_extract_relative_path']
            simulation_starting_step = 0
            simulation_finishing_step = 0
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

        query_logging = (
            f"UPDATE server_pre_main SET "
            f"simulation_status = 'finished', "
            f"post_status = 'queue', "
            f"simulation_starting_step = {simulation_starting_step}, "
            f"simulation_finishing_step = {simulation_finishing_step}, "
            f"operation_dir_name = '{operation_dir_name}', "
            f"sub_operation_relative_path = '{sub_operation_relative_path}', "
            f"billet_file_sub_operation_extract_relative_path = '{billet_file}' "
            f"WHERE execution_id = {self.eid}"
        )

        conn = config.get_connection()
        try:
            with conn.cursor() as cur:
                query = """
                UPDATE server_pre_main
                    SET 
                        post_status = 'queue'::post_status_enum,
                        simulation_status = 'finished'::simulation_status_enum,
                        simulation_time_finished = NOW(),
                        simulation_starting_step = %(simulation_starting_step)s,
                        simulation_finishing_step = %(simulation_finishing_step)s,
                        operation_dir_name = %(operation_dir_name)s,
                        sub_operation_relative_path = %(sub_operation_relative_path)s,
                        billet_file_sub_operation_extract_relative_path = %(billet_file)s
                    WHERE execution_id = %(eid)s;"""
                cur.execute(
                    query, {
                        'eid': self.eid,
                        'simulation_starting_step': simulation_starting_step,
                        'simulation_finishing_step': simulation_finishing_step,
                        'operation_dir_name': operation_dir_name,
                        'sub_operation_relative_path': sub_operation_relative_path,
                        'billet_file': billet_file})
                conn.commit()
                record_changed = cur.rowcount
            assert record_changed == 1, (
                f"Query UPDATE server_pre_main SET simulation_status = 'finished', post_status = 'queue' "
                f"should change one record, but it changed {record_changed} records.")
            LOGGER.info(f"{self.log_id} {query_logging}")
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise RuntimeError(f"{self.log_id} FAILED {query_logging}")
        finally:
            config.put_connection(conn)

    def _query_is_last_operation(self) -> bool:
        # LOGGER.info("START: func '_query_is_last_operation'")
        conn = config.get_connection()
        try:
            cur = conn.cursor()
            query = "SELECT MAX(execution_order) FROM server_pre_main WHERE process_version_id = %s;"
            cur.execute(query, (self.pvid,))
            result = cur.fetchone()
            conn.commit()
            cur.close()

            assert result, f"Got empty result of the query"
            last_execution_order = result[0]
            assert last_execution_order, f"Error 'execution_order' is None"
            assert isinstance(last_execution_order, int), f"Error 'execution_order' is not integer"

            is_last_operation = (self.eo == last_execution_order)

            if is_last_operation:
                LOGGER.info(f"{self.log_id} It is last operation for 'pvid'={self.pvid}.")

            return is_last_operation
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise RuntimeError(
                f"{self.log_id} "
                f"FAILED to get maximum value of 'execution_order' for 'process_version_id'={self.pvid}.")
        finally:
            config.put_connection(conn)

    def _query_update_process_versions_set_progres_set_status_finish(self):
        conn = config.get_connection()
        try:
            with conn.cursor() as cur:
                query = """
                    UPDATE process_versions
                    SET 
                        simulation_status = 'finished',
                        run_switch_status = FALSE,
                        run_switch_is_active = FALSE,
                        simulation_expected_duration_days = 0.0,
                        simulation_percent = 100,
                        finished_at = NOW(),
                        simulation_server_id = NULL
                    WHERE process_version_id = %s;"""
                cur.execute(query, (self.pvid,))
                conn.commit()
                record_changed = cur.rowcount
            assert record_changed == 1, (
                f"Query UPDATE process_versions SET simulation_status = 'finished' should change one record, "
                f"but it changed {record_changed} records.")
            LOGGER.info(
                f"{self.log_id} "
                f"UPDATE process_versions SET simulation_status = 'finished', simulation_percent = 100%")
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise RuntimeError(
                f"{self.log_id} "
                f"FAILED UPDATE process_versions SET simulation_status = 'finished', simulation_percent = 100%")
        finally:
            config.put_connection(conn)

    def _query_update_process_versions_set_progres_set_status_queue(self):
        next_eo = self.eo + 1

        try:
            expected_times = [self.param['table'][_i]['simulation_expected_duration_days']
                              for _i
                              in range(len(self.param['table']))]
            assert all([isinstance(_val, float | int) for _val in expected_times]), \
                "All values of 'simulation_expected_duration_days' must be float or int."
            total_run_time = sum(expected_times)
            finished_run_time = sum(expected_times[:next_eo])
            residual_run_time = sum(expected_times[next_eo:])
            if total_run_time == 0 or residual_run_time == 0:
                percent_done = 100
            else:
                percent_done = math.floor(100 * finished_run_time / total_run_time)
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

        query_logging = (
            f"UPDATE process_versions SET simulation_status = 'queue', execution_order = {next_eo}, "
            f"simulation_expected_duration_days = {residual_run_time}, simulation_percent = {percent_done}%")

        conn = config.get_connection()
        try:
            with conn.cursor() as cur:
                update_query = """
                    UPDATE process_versions
                    SET 
                        simulation_status = 'queue',
                        execution_order = %(next_eo)s,
                        simulation_expected_duration_days = %(residual_run_time)s,
                        simulation_percent = %(percent_done)s
                    WHERE process_version_id = %(pvid)s;"""
                cur.execute(update_query, {'pvid': self.pvid,
                                           'next_eo': next_eo,
                                           'residual_run_time': residual_run_time,
                                           'percent_done': percent_done})
                conn.commit()
                record_changed = cur.rowcount
            assert record_changed == 1, (
                f"Query UPDATE process_versions SET simulation_status = 'queue' should change one record, "
                f"but it changed {record_changed} records.")
            LOGGER.info(f"{self.log_id} {query_logging}")
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise RuntimeError(f"{self.log_id} FAILED {query_logging}")
        finally:
            config.put_connection(conn)

    def _silent_query_update_server_pre_main_error_in_simulation(self):
        conn = config.get_connection()
        try:
            with conn.cursor() as cur:
                query = """
                    UPDATE server_pre_main SET 
                        simulation_status = 'error'::simulation_status_enum, 
                        simulation_time_finished = NOW() 
                        WHERE execution_id = %s;"""
                cur.execute(query, (self.eid,))
                conn.commit()
        except Exception as _err:
            LOGGER.error(
                f"{self.log_id} "
                f"FAILED UPDATE server_pre_main SET "
                f"simulation_status='error', simulation_time_finished=NOW() WHERE execution_id={self.eid} "
                f"with {type(_err).__name__}: {_err}")
        finally:
            config.put_connection(conn)

    def _silent_query_process_versions_set_simulation_status(self, simulation_status: str):
        """
        Do SQL query and set 'simulation_status'.
        Returns 'True' if successful.
        :param simulation_status: str is 'simulation_status'
        :return: bool is True if success
        """
        conn = config.get_connection()
        try:
            with conn.cursor() as cur:
                query = (
                    "UPDATE process_versions SET "
                    "simulation_status = %s::simulation_status_enum "
                    "WHERE process_version_id = %s;")
                cur.execute(query, (simulation_status, self.pvid,))
                conn.commit()

            LOGGER.info(
                f"{self.log_id} "
                f"Successfully UPDATE process_versions SET simulation_status = '{simulation_status}' "
                f"WHERE process_version_id = {self.pvid}.")
        except Exception as _err:
            LOGGER.error(
                f"{self.log_id} "
                f"FAILED UPDATE process_versions SET simulation_status = '{simulation_status}' "
                f"WHERE process_version_id = {self.pvid} "
                f"with {type(_err).__name__}: {_err}")
        finally:
            config.put_connection(conn)

    def _copy_files_from_nas(self):
        """
        Copy files from NAS to Server.
        The NAS network folder is specified in _config.nas.
        The Server's 'Local Projects Dir' is specified in _config.server['local_dir']
        The project ID is specified in _param['project']['process_version_id'].
        The project absolute path on NAS is specified in _param['project']['project_dir_on_nas'].
        """
        # LOGGER.info("START: func 'self._copy_files_from_nas'")
        try:
            assert is_local_dir_exist(), "Local dir doesn't exist on the Server."
            assert is_smb_file_server_available(), "public dir of NAS is not accessible."

            # self._create_or_clean_local_project_dir()

            if self.eo >= 1:
                self._copy_previous_operation_extract_key_files_from_nas()

            if self.eo >= 2:
                self._restore_db_file_from_nas()

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise RuntimeError(f"{self.log_id} FAILED to restore files from NAS to Server. ")

    def _create_or_clean_local_project_dir(self):
        # try:
        #     local_dir = config.server['local_dir']
        #     project_dir_name = self.param['project']['project_dir_name']
        #     local_project_path = str(os.path.join(local_dir, project_dir_name))
        #     create_new_dir_or_clean_existing_dir(local_project_path)
        # except Exception as _err:
        #     LOGGER.error(f"{self.pvid}/{self.execution_order} {type(_err).__name__}: {_err}")
        #     raise RuntimeError(f"{self.pvid}/{self.execution_order} FAILED creating empty local project dir")
        pass

    def _create_or_clean_local_previous_operation_dir(self):
        try:
            local_previous_operation_path = self.get_param_local_previous_operation_path()
            create_new_dir_or_clean_existing_dir(local_previous_operation_path)
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise RuntimeError(
                f"{self.log_id} FAILED creating or cleaning local previous operation dir.")

    def _restore_previous_parameters_json_from_nas(self):
        previous_e_o = self.eo - 1
        try:
            src_file = self.get_param_nas_previous_operation_parameters_json()
            assert smbclient.path.isfile(src_file), f"Previous operation's file '{src_file}' doesn't exist on NAS."

            dst_path = self.get_param_local_previous_operation_path()
            assert os.path.isdir(dst_path), f"Previous operation dir '{dst_path}' doesn't exist."

            smbclient.shutil.copy2(src_file, dst_path)

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise RuntimeError(
                f"{self.log_id} " 
                f"FAILED copying 'parameters.json' file of previous execution_order {previous_e_o} from NAS.")

    def _copy_previous_operation_extract_key_files_from_nas(self):
        previous_eo = self.eo - 1
        try:
            local_dir = config.server['local_dir']
            nas_dir: str = config.nas['absolute_path']
            sub_operation_relative_path: str = self.param['table'][previous_eo]['sub_operation_relative_path']
            extract_dir_name: str = config.server['billet_extract_dir_name']

            src_previous_sub_operation_path = os.path.join(nas_dir, sub_operation_relative_path)
            dst_previous_sub_operation_path = os.path.join(local_dir, sub_operation_relative_path)

            src_extract_dir = os.path.join(src_previous_sub_operation_path, extract_dir_name)
            dst_extract_dir = os.path.join(local_dir, sub_operation_relative_path, extract_dir_name)

            src_last_key_file = os.path.join(src_previous_sub_operation_path, "EXPORT_LAST_STEP.KEY")

            assert smbclient.path.isdir(src_extract_dir), \
                f"Previous operation extract dir doesn't exist on NAS ({src_extract_dir})"
            assert smbclient.path.isfile(src_last_key_file), \
                f"Previous operation last KEY file doesn't exist on NAS ({src_last_key_file})"

            if not os.path.isdir(dst_extract_dir):
                os.makedirs(dst_extract_dir)
            assert os.path.isdir(dst_extract_dir), \
                f"Previous operation extract dir on local directory doesn't exist ({dst_extract_dir})"

            for file_name in smbclient.listdir(src_extract_dir):
                src_file_path = os.path.join(src_extract_dir, file_name)
                if smbclient.path.isfile(src_file_path):
                    smbclient.shutil.copy2(src_file_path, dst_extract_dir)

            smbclient.shutil.copy2(src_last_key_file, dst_previous_sub_operation_path)

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise RuntimeError(
                f"{self.log_id} "
                f"FAILED copying previous ({previous_eo}) operation extract KEY-files from NAS.")

    def _query_update_process_versions_set_parameters(self, update_param: dict):
        """
        Receives _param['project'] dict with old project parameters and '_new_param' dict with new project parameters.
        Connects to SQL Server and update 'process_versions' table.
        Update columns as in '_new_param' dict where 'process_version_id' = _param['project']['process_version_id'].
        """
        # LOGGER.info(f"START func '_query_update_process_versions'")
        conn = config.get_connection()
        try:
            cur = conn.cursor()

            column_names = list(update_param.keys())
            values = list(update_param.values())

            query = "UPDATE process_versions SET ({}) = ({}) WHERE process_version_id = %s;"
            sql_format_query = sql.SQL(query).format(
                sql.SQL(', ').join(map(sql.Identifier, column_names)),
                sql.SQL(', ').join(sql.Placeholder() * len(column_names))
            )
            cur.execute(sql_format_query, (*values, self.pvid,))
            conn.commit()
            cur.close()

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise RuntimeError(f"{self.log_id} FAILED UPDATE 'process_versions'")
        finally:
            config.put_connection(conn)

    def _restore_db_file_from_nas(self):
        try:
            nas_dir: str = config.nas['absolute_path']
            project_dir_name: str = self.param['project']['project_dir_name']
            db_file_name: str = self.param['project']['db_file_name']
            src_file = os.path.join(nas_dir, project_dir_name, db_file_name + '.DB')
            local_dir: str = config.server['local_dir']
            local_project_path = os.path.join(local_dir, project_dir_name)
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise
        try:
            assert smbclient.path.isfile(src_file), f"DB file '{src_file}' doesn't exist on NAS."
            if not os.path.isdir(local_project_path):
                os.makedirs(local_project_path)
            assert os.path.isdir(local_project_path), f"Destination dir '{local_project_path}' doesn't exist."
            smbclient.shutil.copy2(src_file, local_project_path)
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise RuntimeError(f"{self.log_id} Failed to copy DB file from NAS ({src_file})")

    def get_param_local_previous_operation_path(self) -> str:
        try:
            previous_e_o = self.eo - 1
            assert previous_e_o >= 0, "Trying to call 'execution_order' (for Previous operation number) less than zero"
            local_dir: str = config.server['local_dir']
            project_dir_name: str = self.param['project']['project_dir_name']
            previous_operation_relative_path = generate_operation_dir_name(previous_e_o)
            _path = os.path.join(local_dir, project_dir_name, previous_operation_relative_path)
            return _path
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def get_param_nas_previous_operation_parameters_json(self) -> str:
        try:
            previous_eo = self.eo - 1
            assert previous_eo >= 0, "Trying to call 'execution_order' (for Previous operation number) less than zero"
            nas_dir: str = config.nas['absolute_path']
            project_dir_name: str = self.param['project']['project_dir_name']
            previous_operation_dir = generate_operation_dir_name(previous_eo)
            _path = os.path.join(nas_dir, project_dir_name, previous_operation_dir, 'parameters.json')
            return _path
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def _query_is_successful_update_post_operations(self, existing_columns: list) -> bool:
        columns, values = [], []
        conn = config.get_connection()
        try:
            query = "UPDATE post_operations SET ({}) = ({}) WHERE process_version_id = %s AND execution_order = %s;"
            for column, value in self.param['operation'].items():
                if column in existing_columns:
                    columns.append(column)
                    values.append(value)
                else:
                    LOGGER.error(f"Simulation output Item '{column}': '{value}' was ignored and "
                                 f"will not be updated in the SQL, "
                                 f"because there is no corresponding column in 'post_operations' table.")
            sql_format_query = sql.SQL(query).format(
                sql.SQL(', ').join(map(sql.Identifier, columns)),
                sql.SQL(', ').join(sql.Placeholder() * len(columns)))
            cur = conn.cursor()
            cur.execute(sql_format_query, (*values, self.pvid, self.eo,))
            conn.commit()
            cur.close()

            return True

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise RuntimeError(f"{self.log_id} FAILED UPDATE 'post_operations'.")
        finally:
            config.put_connection(conn)

    def _query_update_server_pre_main_set_simulation_status_as_run(self):

        conn = config.get_connection()
        try:
            cur = conn.cursor()
            query = """
                UPDATE server_pre_main SET 
                    simulation_status = 'run'::simulation_status_enum, 
                    simulation_server_retry_count = simulation_server_retry_count + 1,
                    simulation_time_started = NOW() 
                WHERE process_version_id = %s AND execution_order = %s;"""
            cur.execute(query, (self.pvid, self.eid,))
            conn.commit()
            cur.close()


        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise RuntimeError(
                f"{self.log_id} "
                f"FAILED UPDATE server_pre_main SET simulation_status='run', simulation_time_started=NOW() "
                f"WHERE process_version_id = {self.pvid} AND execution_order = {self.eo};")
        finally:
            config.put_connection(conn)

    def die_dimensions(self, row: dict) -> tuple[dict, dict]:
        """
        Extract die dimensions from 'lib' for given row

        :param row: row dictionary
        :return: tuple of top and bottom die dimensions
        """
        try:
            top_die_id = row['top_die_id']
            bottom_die_id = row['bottom_die_id']

            top_die = config.lib['die'].loc[top_die_id]['dimensions']
            bottom_die = config.lib['die'].loc[bottom_die_id]['dimensions']
            return top_die, bottom_die
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    def die_straight_length_min(self, row: dict) -> float:
        """
        Extract minimum die straight length from 'lib' for given row

        :param row: row dictionary
        :return: minimum die straight length of top and bottom dies
        """
        try:
            top_die, bottom_die = self.die_dimensions(row)
            return min(
                top_die['straight_length'],
                bottom_die['straight_length'])
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise RuntimeError(f"FAILED calculating Min 'die_straight_length'")

    def die_edge_radius_min(self, row: dict) -> float:
        """
        Extract minimum die edge radius from 'lib' for given row

        :param row: row dictionary
        :return: minimum die straight length of top and bottom dies
        """
        try:
            top_die, bottom_die = self.die_dimensions(row)
            if top_die['straight_length'] < bottom_die['straight_length']:
                _r = top_die['edge_radius']
            else:
                _r = bottom_die['edge_radius']
            return _r
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise RuntimeError(f"FAILED calculating Min 'die_straight_length'")

    def die_radius_half_depth_impression_length(self, row: dict, one_side_penetration: float) -> float:
        try:
            split_on_half_coef = 0.3
            _r = self.die_edge_radius_min(row)
            half_depth_of_impression = split_on_half_coef * one_side_penetration
            if half_depth_of_impression >= (_r / 2):  # Impression length does not exceed die radius
                half_depth_of_impression = _r / 2
            return math.sqrt(_r ** 2 - (_r - half_depth_of_impression) ** 2)

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    @property
    def parent_type_id(self) -> int:
        try:
            return config.lib['operations_library'].loc[self.row['type_id'], 'parent_type_id'].item()
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise

    # ==================================================================================================================

    def _sim_unit__measure_billet(self):
        """Run 'Heat' operation"""
        try:
            self._measure_billet_of_previous_sub_operation()
        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise


    def _sim_unit__heat_transfer(self):
        """Run 'Heat' operation"""
        try:
            self.param['operation']['process_duration'] = float(self.row['control_duration'])
            self._set_sub_operation_path('cooling')

            def is_first_operation_23_in_sequence_of_operations_23() -> bool:
                previous_operation_type_id = self.param['table'][self.eo - 1]['type_id']
                is_first_operation_23 = previous_operation_type_id != 23
                return is_first_operation_23

            def is_recovering_occurs() -> bool:
                max_temp_on_heating_sequence = -273.15
                for eo in range(self.eo - 1, -1, -1):
                    operation_type_id = self.param['table'][eo]['type_id'] == 23
                    if not operation_type_id:
                        break
                    max_temp_on_heating_sequence = max(max_temp_on_heating_sequence,
                                                       self.row['control_temperature_furnace_initial'],
                                                       self.row['control_temperature_furnace_final'])
                return max_temp_on_heating_sequence > 400.0

            if self.eo == 0:
                is_new_operation = True
                is_new_heat = True
                is_new_bite = True
            else:
                is_new_operation = is_first_operation_23_in_sequence_of_operations_23()
                is_recovering = is_recovering_occurs()
                is_new_heat = is_new_operation and is_recovering
                is_new_bite = not is_new_operation

            self.param['operation']['usrdef_triggers'] = set_triggers(softening_coefficient=0.005,
                                                                      is_new_bite=is_new_bite,
                                                                      is_new_operation=is_new_operation,
                                                                      is_new_heat=is_new_heat)

            # ----------------------------------- INITIALIZE INGOT AXIS --------------------------------------
            self.param['operation']['is_initialize_user_nodal_for_ingot_axis'] = True

            # --------------------------------------- RUN ----------------------------------------------------
            operation = HeatOp(self.param)
            operation.run()

            self._finalize_sub_operation()

        except Exception as _err:
            log_error(_err, type(_err).__name__, self.task_id_name, self.time_start, traceback.format_exc())
            raise



    @property
    def log_id(self):
        duration = str(round(time.monotonic() - self.time_start, 2))
        return f"{self.task_id_name} Duration {duration}s"

    @property
    def task_id_name(self) -> str:
        return f"[{self.pvid}][{self.eo}/{self.eo_last}] Sim #{self.worker_id}"
