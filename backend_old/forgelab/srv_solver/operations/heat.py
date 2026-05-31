import logging
import traceback
import time

from forgelab.common.boundary_conditions import convection_coefficient, emissivity
from forgelab.srv_solver.pre_functions import \
    remove_old_operation_files, copy_operation_template, \
    import_billet_from_previous_sub_operation, convert_mst_file_to_key_file, import_db_from_previous_sub_operation, \
    apply_new_material, convert_key_to_db, export_billet_and_parameters_from_db_last_step, move_db_to_project_dir, \
    change_operations_names_in_mst_or_key_file, automatic_modification_of_values_in_moproj_file, \
    automatic_modification_of_parameters_in_files, modify_mesh_number, modify_global_time, \
    step_control_for_heat_transfer_input_process_duration, change_environment_temperature_in_key_file, \
    assert_missing_input_parameters, modify_usrdef_triggers, modify_user_variable_names, \
    initialize_user_nodal_variables_for_ingot_axis
from forgelab.common.file_operations import sub_operation_abs_path
from forgelab.srv_solver.solver_functions import run_solver


LOGGER = logging.getLogger(__name__)


class HeatOp:

    required_input_key_words = ['process_duration', 'usrdef_triggers']

    files = dict(
        file_01=dict(
            file_path="Operations\\Task00001\\SimCtrl.KEY",
            parameters=dict(
                process_duration=dict(s="TMAX      1.1111000000E+000", k=[0], n=1, f="{:>-21.10E}"),
                step_control_initial_time_step=dict(
                    s="DTMAX     1.8970000000E+000    0.0000000000E+000", k=[0], n=1, f="{:>-21.10E}"),
                step_control_max_temperature=dict(
                    s="DTPMAX    4.5820000000E+000    1.5230000000E+000    2.5870000000E+001",
                    k=[0], n=1, f="{:>-21.10E}"),
                step_control_min_time_step=dict(
                    s="DTPMAX    4.5820000000E+000    1.5230000000E+000    2.5870000000E+001",
                    k=[0], n=2, f="{:>-21.10E}"),
                step_control_max_time_step=dict(
                    s="DTPMAX    4.5820000000E+000    1.5230000000E+000    2.5870000000E+001",
                    k=[0], n=3, f="{:>-21.10E}"),
                convection_coefficient=dict(s="CNVCOF       0    2.1000000000E-002", k=[0], n=2, f="{:>-21.10E}"),
                global_time=dict(
                    s="TNOW     -1.0000000000E+021    0.0000000000E+000       1    0.0000000000E+000",
                    k=[0], n=1, f="\t{:>-21.10E}"),
                simulation_number_1=dict(
                    s="CURSIM       1       1       0", k=[0, 1], n=1, f="\t{:8d}"),
                operation_number=dict(
                    s="CURSIM       1       1       0", k=[0], n=2, f="\t{:8d}")
            )
        ),
        file_02=dict(
            file_path="Materials\\Material00001.KEY",
            parameters=dict(
                emissivity=dict(s="EMSVTY       1       0    7.0000000000E-001", k=[0, 1], n=3, f="{:>-21.10E}")
            )
        ),
        file_03=dict(
            file_path="heat_0004.KEY",
            parameters=dict(
                start_step_number=dict(s="NSTART    	-2359", k=[0], n=1, f="\t{:d}"),
                global_time=dict(s="TNOW	   	  -1E21                 0       1", k=[0], n=1, f="\t{:>-21.10E}"),
                simulation_number_1=dict(
                    s="CURSIM    	1	1	0", k=[0, 1], n=1, f="\t{:8d}"),
                operation_number=dict(
                    s="CURSIM    	1	1	0", k=[0], n=2, f="\t{:8d}")
            )
        ),
        file_04=dict(
            file_path="heat_0004.MST",
            parameters=dict(
                start_step_number=dict(s="NSTART    	-2359", k=[0], n=1, f="\t{:d}"),
                simulation_number_1=dict(
                    s="CURSIM    	1	1	0", k=[0, 1], n=1, f="\t{:8d}"),
                simulation_number_title_1=dict(
                    s="SIMULATION	1", k=[0, 1], n=1, f="\t{:d}"),
                operation_number=dict(
                    s="CURSIM    	1	1	0", k=[0], n=2, f="\t{:8d}")
            )
        )
    )

    moproj_file = dict(
        file_path="heat_0004.moproj",
        parameters=dict(
            process_duration="      <Value>1.1111 sec</Value>",
            step_control_initial_time_step="      <Value>1.897</Value>",
            step_control_min_time_step="      <Value>1.523</Value>",
            step_control_max_time_step="      <Value>25.87</Value>",
            step_control_max_temperature="      <Value>4.582</Value>",
            convection_coefficient="      <Value>0.021 N/sec/mm/C</Value>",
            start_step_number="    <StartStepNo>-2359</StartStepNo>"
        )
    )

    def __init__(self, _param: dict):
        self.param: dict = _param
        self.row: dict = {}
        self.pvid: int = 0
        self.eo: int = 0

    def run(self):
        try:
            operations_count = 1
            self.param['operation']['template_name'] = "heat_0004"

            self.eo = self.param['project']['execution_order']
            self.pvid = self.param['project']['process_version_id']
            self.row = self.param['table'][self.eo]

            previous_simulation_number = self.param['previous_operation']['simulation_number']
            sub_operation_path = sub_operation_abs_path(self.param)

            LOGGER.info(f"{self.log_id} STARTED HeatOp at '{sub_operation_path}'")
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise
        try:
            self.param['operation']['simulation_number'] = previous_simulation_number + 1

            self.pre_processing()
            run_solver(self.param)
            self.post_processing()

            self.param['operation']['simulation_number'] = previous_simulation_number + operations_count

            LOGGER.info(f"{self.log_id} FINISHED HeatOp at '{sub_operation_path}'")
        except Exception as _err:
            LOGGER.error(f"{self.log_id}  {type(_err).__name__}: {_err}")
            raise RuntimeError(f"FAILED at '{sub_operation_path}'")

    def pre_processing(self):
        try:
            sub_operation_path = sub_operation_abs_path(self.param)
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise
        try:
            sub_operation_path = sub_operation_abs_path(self.param)
            template_name = self.param['operation']['template_name']

            remove_old_operation_files(sub_operation_path)
            copy_operation_template(self.param)
            import_billet_from_previous_sub_operation(self.param)
            convert_mst_file_to_key_file(sub_operation_path, template_name)
            import_db_from_previous_sub_operation(self.param)
            apply_new_material(self.param, self.row)
            self._modify_parameters_in_files()
            convert_key_to_db(self.param)
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError(f"FAILED at {sub_operation_path}")

    def post_processing(self):
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
            raise RuntimeError(f"FAILED at {sub_operation_path}")

    def _modify_parameters_in_files(self):
        try:
            sub_operation_path = sub_operation_abs_path(self.param)
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise
        try:
            template_name = self.param['operation']['template_name']
            mst_file = template_name + '.MST'
            key_file = template_name + '.KEY'

            assert_missing_input_parameters(self.required_input_key_words, self.param)
            self._calculate_process_parameters()
            change_operations_names_in_mst_or_key_file(self.param, mst_file)
            change_operations_names_in_mst_or_key_file(self.param, key_file)
            change_environment_temperature_in_key_file(self.param, "Operations\\Task00001\\SimCtrl.KEY")
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
            raise RuntimeError(f"FAILED at {sub_operation_path}")

    def _calculate_process_parameters(self):
        try:
            sub_operation_path = sub_operation_abs_path(self.param)
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise
        try:
            process_duration = self.param['operation']['process_duration']
            start_step_number = self.param['previous_operation']['last_step_number']

            assert process_duration >= 0.001, "'process_duration' < 0.001"

            # Stopping control
            self.param['operation']['global_time'] = self.param['previous_operation']['global_time']

            # Step control
            initial_time_step, min_time_step, max_time_step, max_temperature = (
                step_control_for_heat_transfer_input_process_duration(self.param['operation']['process_duration']))
            self.param['operation']['step_control_initial_time_step'] = initial_time_step
            self.param['operation']['step_control_min_time_step'] = min_time_step
            self.param['operation']['step_control_max_time_step'] = max_time_step
            self.param['operation']['step_control_max_temperature'] = max_temperature
            self.param['operation']['start_step_number'] = start_step_number

            # USRDEF triggers
            self.param['operation']['usrdef_triggers'] |= {
                'start_step_number': start_step_number
            }

            # Boundary conditions
            self.param['operation']['environment_temperature_1'] = self.row['control_temperature_furnace_initial']
            self.param['operation']['environment_temperature_2'] = self.row['control_temperature_furnace_final']
            self.param['operation']['convection_coefficient'] = convection_coefficient(self.row, self.param)
            self.param['operation']['emissivity'] = emissivity(self.row)

            # Simulation control
            self.param['operation']['simulations_names_list'] = [
                f"{self.param['operation']['sub_operation_name']}_{self.param['operation']['sub_operation_type']}"]
            # CURSIM 6 21 0
            # CURSIM[1] = 6 - sequential simulation number
            # CURSIM[2] = 21 - operation number

            self.param['operation']['operation_number'] = self.param['project']['execution_order']

            sim_number = self.param['operation']['simulation_number']
            self.param['operation']['simulation_number_1'] = sim_number
            self.param['operation']['simulation_number_title_1'] = sim_number

        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError(f"FAILED at {sub_operation_path}")

    @property
    def log_id(self):
        return self.param['operation']['log_id'] + f" Duration {time.monotonic() - self.param['operation']['project_start_datetime']:.2f}s {traceback.format_exc()}"
