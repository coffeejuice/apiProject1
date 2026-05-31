import logging
import traceback
import time

import numpy as np

from forgelab.common.boundary_conditions import \
    emissivity, environment_temperature, convection_coefficient
from forgelab.srv_solver.pre_functions import \
    remove_old_operation_files, copy_operation_template, \
    import_billet_from_previous_sub_operation, convert_mst_file_to_key_file, import_db_from_previous_sub_operation, \
    apply_new_material, convert_key_to_db, export_billet_and_parameters_from_db_last_step, move_db_to_project_dir, \
    change_operations_names_in_mst_or_key_file, automatic_modification_of_values_in_moproj_file, \
    automatic_modification_of_parameters_in_files, modify_mesh_number, modify_global_time, \
    step_control_for_heat_transfer_input_process_duration, find_first_pattern_in_list, write_list_of_strings_to_file, \
    read_lines_from_file, modify_usrdef_triggers, modify_user_variable_names, \
    initialize_user_nodal_variables_for_ingot_axis
from forgelab.common.file_operations import sub_operation_abs_path
from forgelab.srv_solver.solver_functions import run_solver
from forgelab.srv_solver.import_last_step_parameters import read_table, write_table


LOGGER = logging.getLogger(__name__)


class CutOp:

    required_input_key_words = ['x_axis_cutting_limits', 'usrdef_triggers']

    files = dict(

        file_sim_ctrl_task_1=dict(
            file_path="Operations\\Task00001\\SimCtrl.KEY",
            parameters=dict(
                before_cutting_process_duration=dict(
                    s="TMAX      1.1111000000E+000", k=[0], n=1, f="\t{:>-21.10E}"),
                before_cutting_step_control_initial_time_step=dict(
                    s="DTMAX     1.8970000000E+000    0.0000000000E+000", k=[0], n=1, f="{:>-21.10E}\t"),
                before_cutting_step_control_max_temperature=dict(
                    s="DTPMAX    4.5820000000E+000    1.5230000000E+000    2.5870000000E+001",
                    k=[0], n=1, f="\t{:>-21.10E}"),
                before_cutting_step_control_min_time_step=dict(
                    s="DTPMAX    4.5820000000E+000    1.5230000000E+000    2.5870000000E+001",
                    k=[0], n=2, f="\t{:>-21.10E}"),
                before_cutting_step_control_max_time_step=dict(
                    s="DTPMAX    4.5820000000E+000    1.5230000000E+000    2.5870000000E+001",
                    k=[0], n=3, f="\t{:>-21.10E}"),
                before_cutting_environment_temperature=dict(
                    s="ENVTMP       0    2.1100000000E+001", k=[0], n=2, f="\t{:>-21.10E}"),
                before_cutting_convection_coefficient=dict(
                    s="CNVCOF       0    2.1000000000E-002", k=[0], n=2, f="\t{:>-21.10E}"),
                global_time=dict(
                    s="TNOW     -1.0000000000E+021    0.0000000000E+000       1    0.0000000000E+000",
                    k=[0], n=1, f="\t{:>-21.10E}"),
                simulation_number_1=dict(
                    s="CURSIM       1       1       0", k=[0, 1], n=1, f="\t{:8d}"),
                operation_number=dict(
                    s="CURSIM       1       1       0", k=[0], n=2, f="\t{:8d}"))),

        file_sim_ctrl_task_4=dict(
            file_path="Operations\\Task00004\\SimCtrl.KEY",
            parameters=dict(
                after_cutting_environment_temperature=dict(
                    s="ENVTMP       0    1.9850000000E+001", k=[0], n=2, f="\t{:>-21.10E}"),
                after_cutting_convection_coefficient=dict(
                    s="CNVCOF       0    1.8400000000E-002", k=[0], n=2, f="\t{:>-21.10E}"))),

        file_material=dict(
            file_path="Materials\\Material00001.KEY",
            parameters=dict(
                emissivity=dict(s="EMSVTY       1       0    7.0000000000E-001", k=[0, 1], n=3, f="{:>-21.10E}"))),

        file_key=dict(
            file_path="cut_0002.KEY",
            parameters=dict(
                start_step_number=dict(s="NSTART    	-2359", k=[0], n=1, f="\t{:d}"),
                global_time=dict(s="TNOW	   	  -1E21       0       1", k=[0], n=1, f="\t{:>-21.10E}"),
                simulation_number_1=dict(
                    s="CURSIM    	1	1	0", k=[0, 1], n=1, f="\t{:8d}"),
                operation_number=dict(
                    s="CURSIM    	1	1	0", k=[0], n=2, f="\t{:8d}"))),

        file_mst=dict(
            file_path="cut_0002.MST",
            parameters=dict(
                start_step_number=dict(s="NSTART    	-2359", k=[0], n=1, f="\t{:d}"),
                simulation_number_1=dict(
                    s="CURSIM    	1	1	0", k=[0, 1], n=1, f="\t{:8d}"),
                simulation_number_2=dict(
                    s="CURSIM    	2	2	0", k=[0, 1], n=1, f="\t{:8d}"),
                simulation_number_3=dict(
                    s="CURSIM    	3	3	0", k=[0, 1], n=1, f="\t{:8d}"),
                simulation_number_4=dict(
                    s="CURSIM    	4	4	0", k=[0, 1], n=1, f="\t{:8d}"),
                simulation_number_title_1=dict(
                    s="SIMULATION	1", k=[0, 1], n=1, f="\t{:d}"),
                simulation_number_title_2=dict(
                    s="SIMULATION	2", k=[0, 1], n=1, f="\t{:d}"),
                simulation_number_title_3=dict(
                    s="SIMULATION	3", k=[0, 1], n=1, f="\t{:d}"),
                simulation_number_title_4=dict(
                    s="SIMULATION	4", k=[0, 1], n=1, f="\t{:d}"),
                operation_number=dict(
                    s="CURSIM    	1	1	0", k=[0], n=2, f="\t{:8d}"))))

    moproj_file = dict(
        file_path="cut_0002.moproj",
        parameters=dict(
            before_cutting_process_duration="      <Value>1.1111 sec</Value>",
            before_cutting_step_control_initial_time_step="      <Value>1.897</Value>",
            before_cutting_step_control_min_time_step="      <Value>1.523</Value>",
            before_cutting_step_control_max_time_step="      <Value>25.87</Value>",
            before_cutting_step_control_max_temperature="      <Value>4.582</Value>",
            before_cutting_environment_temperature="      <Value>21.1 C</Value>",
            before_cutting_convection_coefficient="      <Value>0.021 N/sec/mm/C</Value>",
            after_cutting_environment_temperature="      <Value>19.85 C</Value>",
            after_cutting_convection_coefficient="      <Value>0.0184 N/sec/mm/C</Value>",
            start_step_number="    <StartStepNo>-2359</StartStepNo>"))

    def __init__(self, _param: dict):
        self.param: dict = _param
        self.row: dict = {}
        self.pvid: int = 0
        self.eo: int = 0

    def run(self):
        """Runs Simulation for Cut class"""
        try:
            self.param['operation']['template_name'] = "cut_0002"

            self.eo = self.param['project']['execution_order']
            self.pvid = self.param['project']['process_version_id']
            self.row = self.param['table'][self.eo]

            previous_simulation_number = self.param['previous_operation']['simulation_number']
            sub_operation_path = sub_operation_abs_path(self.param)

            LOGGER.info(f"{self.log_id} STARTED CutOp at '{sub_operation_path}'")
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise
        try:
            operations_count = 4

            self.param['operation']['simulation_number'] = previous_simulation_number + 1

            self.pre_processing()
            run_solver(self.param)
            self.post_processing()

            self.param['operation']['simulation_number'] = previous_simulation_number + operations_count

            LOGGER.info(f"{self.log_id} FINISHED CutOp at '{sub_operation_path}'")
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError(f"FAILED at '{sub_operation_path}'")

    def pre_processing(self):
        """Pre-Processing for Cut class"""
        try:
            sub_operation_path = sub_operation_abs_path(self.param)
            template_name = self.param['operation']['template_name']
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise
        try:
            remove_old_operation_files(sub_operation_path)
            copy_operation_template(self.param)
            import_billet_from_previous_sub_operation(self.param)
            convert_mst_file_to_key_file(sub_operation_path, template_name)
            import_db_from_previous_sub_operation(self.param)
            apply_new_material(self.param, self.row)
            self._calculate_process_parameters()
            self._modify_parameters_in_files()
            convert_key_to_db(self.param)
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError(f"FAILED at '{sub_operation_path}'")

    def post_processing(self):
        """Post-Processing for Cut class"""
        try:
            sub_operation_path = sub_operation_abs_path(self.param)
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise
        try:
            export_billet_and_parameters_from_db_last_step(self.param)
            move_db_to_project_dir(self.param)
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError(f"FAILED at '{sub_operation_path}'")

    def _modify_parameters_in_files(self):
        try:
            template_name = self.param['operation']['template_name']
            key_file = template_name + ".KEY"
            mst_file = template_name + ".MST"
            sub_operation_path = sub_operation_abs_path(self.param)
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise
        try:
            self._modify_dimensions_of_cutting_object(sub_operation_path, relative_filepath='Objects\\Object00002.KEY')
            self._cut_move_nodes_out_of_cutting_bounds(sub_operation_path, relative_filepath='Objects\\Object00001.KEY')

            change_operations_names_in_mst_or_key_file(self.param, mst_file)
            change_operations_names_in_mst_or_key_file(self.param, key_file)
            automatic_modification_of_values_in_moproj_file(self.moproj_file, self.param)
            automatic_modification_of_parameters_in_files(self.files, self.param)
            modify_mesh_number(self.param, key_file)
            modify_global_time(self.param, key_file)
            # ----------------------- INITIALIZE INGOT AXIS --------------------------
            initialize_user_nodal_variables_for_ingot_axis(self.param)
            # ---------------------------- TRIGGERS ----------------------------------
            modify_usrdef_triggers(self.param, relative_filepath="Operations\\Task00001\\SimCtrl.KEY")
            modify_user_variable_names(self.param, relative_filepath="Operations\\Task00001\\SimCtrl.KEY")

        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError(f"FAILED at '{sub_operation_path}'")

    def _calculate_process_parameters(self):
        # Stopping criteria
        try:
            sub_operation_path: str = sub_operation_abs_path(self.param)
            start_step_number = self.param['previous_operation']['last_step_number']
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise
        try:
            before_cutting_process_duration = max(self.param['operation']['process_duration'], 0.00001)
            self.param['operation']['before_cutting_process_duration'] = before_cutting_process_duration

            # USRDEF triggers
            self.param['operation']['usrdef_triggers'] |= {
                'start_step_number': start_step_number
            }

            # Step size
            initial_time_step, min_time_step, max_time_step, max_temperature = \
                step_control_for_heat_transfer_input_process_duration(self.param['operation']['process_duration'])
            self.param['operation']['before_cutting_step_control_initial_time_step'] = initial_time_step
            self.param['operation']['before_cutting_step_control_min_time_step'] = min_time_step
            self.param['operation']['before_cutting_step_control_max_time_step'] = max_time_step
            self.param['operation']['before_cutting_step_control_max_temperature'] = max_temperature

            # Boundary conditions
            _environment_temperature = environment_temperature(self.row)
            _convection_coefficient = convection_coefficient(self.row, self.param)
            self.param['operation']['emissivity'] = emissivity(self.row)
            self.param['operation']['before_cutting_environment_temperature'] = _environment_temperature
            self.param['operation']['after_cutting_environment_temperature'] = _environment_temperature
            self.param['operation']['before_cutting_convection_coefficient'] = _convection_coefficient
            self.param['operation']['after_cutting_convection_coefficient'] = _convection_coefficient

            # Simulation controls
            self.param['operation']['start_step_number'] = start_step_number
            self.param['operation']['operation_number'] = self.param['project']['execution_order']
            sim_number = self.param['operation']['simulation_number']
            self.param['operation']['simulations_names_list'] = [
                f'{int(before_cutting_process_duration):d}s_[{sim_number:d}]',
                f'Cutter_[{sim_number + 1:d}]',
                f'Boolean_[{sim_number + 2:d}]',
                f'0.01s_[{sim_number + 3:d}]']
            # CURSIM 6 21 0
            # CURSIM[1] = 6 - sequential simulation number
            # CURSIM[2] = 21 - operation number

            self.param['operation']['simulation_number_1'] = sim_number
            self.param['operation']['simulation_number_2'] = sim_number + 1
            self.param['operation']['simulation_number_3'] = sim_number + 2
            self.param['operation']['simulation_number_4'] = sim_number + 3
            self.param['operation']['simulation_number_title_1'] = sim_number
            self.param['operation']['simulation_number_title_2'] = sim_number + 1
            self.param['operation']['simulation_number_title_3'] = sim_number + 2
            self.param['operation']['simulation_number_title_4'] = sim_number + 3
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError(f"FAILED at '{sub_operation_path}'")

    def _modify_dimensions_of_cutting_object(self, sub_operation_path, relative_filepath):
        """Modifies the dimensions of the cutting object"""
        try:
            lines = read_lines_from_file(sub_operation_path, relative_filepath)

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

            x = self.param['operation']['x_cutting_limits']
            y = self.param['operation']['y_cutting_limits']
            z = self.param['operation']['z_cutting_limits']

            box = [
                f'       1   {x[3]:>-18.10E}   {y[0]:>-18.10E}   {z[0]:>-18.10E}\n',
                f'       2   {x[3]:>-18.10E}   {y[1]:>-18.10E}   {z[0]:>-18.10E}\n',
                f'       3   {x[3]:>-18.10E}   {y[0]:>-18.10E}   {z[2]:>-18.10E}\n',
                f'       4   {x[3]:>-18.10E}   {y[1]:>-18.10E}   {z[2]:>-18.10E}\n',
                f'       5   {x[0]:>-18.10E}   {y[0]:>-18.10E}   {z[0]:>-18.10E}\n',
                f'       6   {x[0]:>-18.10E}   {y[1]:>-18.10E}   {z[0]:>-18.10E}\n',
                f'       7   {x[0]:>-18.10E}   {y[0]:>-18.10E}   {z[2]:>-18.10E}\n',
                f'       8   {x[0]:>-18.10E}   {y[1]:>-18.10E}   {z[2]:>-18.10E}\n',
                f'       9   {x[1]:>-18.10E}   {y[0]:>-18.10E}   {z[2]:>-18.10E}\n',
                f'      10   {x[1]:>-18.10E}   {y[1]:>-18.10E}   {z[2]:>-18.10E}\n',
                f'      11   {x[1]:>-18.10E}   {y[0]:>-18.10E}   {z[1]:>-18.10E}\n',
                f'      12   {x[1]:>-18.10E}   {y[1]:>-18.10E}   {z[1]:>-18.10E}\n',
                f'      13   {x[2]:>-18.10E}   {y[0]:>-18.10E}   {z[1]:>-18.10E}\n',
                f'      14   {x[2]:>-18.10E}   {y[1]:>-18.10E}   {z[1]:>-18.10E}\n',
                f'      15   {x[2]:>-18.10E}   {y[0]:>-18.10E}   {z[2]:>-18.10E}\n',
                f'      16   {x[2]:>-18.10E}   {y[1]:>-18.10E}   {z[2]:>-18.10E}\n']

            pattern = 'DIEGEO       2       1      16      28'
            index = find_first_pattern_in_list(lines,
                                               pattern=pattern,
                                               pattern_indices=[0, 1, 2, 3, 4],
                                               starting_line=0)
            if index is None:
                raise ValueError(f"Pattern '{pattern}' not found in the list of strings.")

            new_lines = lines[:index + 1] + box + lines[index + 17:]

            write_list_of_strings_to_file(new_lines, sub_operation_path, relative_filepath)

        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError(f"FAILED at '{sub_operation_path}'")

    def _move_nodes(self, nodes: np.ndarray, x_bounds: np.ndarray, tolerance: float):
        is_moved = []
        try:
            sub_operation_path = sub_operation_abs_path(self.param)
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise
        try:
            old_x = nodes[:, 0]
            for x_coord in x_bounds:
                new_x = np.random.choice([x_coord - tolerance, x_coord + tolerance], size=int(nodes.size / 3))
                condition = np.abs(old_x - x_coord) < tolerance
                nodes[:, 0] = np.where(condition, new_x, old_x)

                is_moved.append(np.any(condition))

            return any(is_moved)

        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError(f"FAILED at '{sub_operation_path}'")

    def _cut_move_nodes_out_of_cutting_bounds(self, sub_operation_path, relative_filepath):
        try:
            _m = self.param['operation']['imported_keyfile']['objects'][1]['measurements']
            average_element = _m['elements_edges']['average']
            final_length = self.row['final_length']
            x_bounds = self.param['operation']['x_cutting_limits'][1:3]

            lines = read_lines_from_file(sub_operation_path, relative_filepath)
            nodes = read_table(lines=lines,
                               pattern='RZ           1    5533',
                               pattern_indices=[0],
                               pattern_value_index=2,
                               type_pattern=['', 'float'])
            tolerance = min(0.01 * final_length, 0.001 * average_element)
            some_nodes_are_moved = self._move_nodes(nodes, x_bounds, tolerance)
            if some_nodes_are_moved:
                lines = write_table(lines=lines,
                                    table=nodes,
                                    pattern='RZ           1    5533', pattern_indices=[0],
                                    pattern_value_index=2,
                                    pattern_format='{:>8d} {:>-21.10E} {:>-21.10E} {:>-21.10E}\n')
                write_list_of_strings_to_file(lines, sub_operation_path, relative_filepath)

        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError(f"FAILED at '{sub_operation_path}'")

    @property
    def log_id(self):
        return self.param['operation']['log_id'] + f" Duration {time.monotonic() - self.param['operation']['project_start_datetime']:.2f}s {traceback.format_exc()}"
