import logging
import traceback
import time

from forgelab.common.boundary_conditions import \
    emissivity, environment_temperature, convection_coefficient
from forgelab.srv_solver.pre_functions import remove_old_operation_files, copy_operation_template, \
    import_billet_from_previous_sub_operation, convert_mst_file_to_key_file, import_db_from_previous_sub_operation, \
    apply_new_material, convert_key_to_db, export_billet_and_parameters_from_db_last_step, move_db_to_project_dir, \
    change_operations_names_in_mst_or_key_file, automatic_modification_of_values_in_moproj_file, \
    automatic_modification_of_parameters_in_files, modify_mesh_number, modify_global_time, \
    step_control_for_heat_transfer_input_process_duration, min_element_size_function, modify_usrdef_triggers, \
    modify_user_variable_names, initialize_user_nodal_variables_for_ingot_axis
from forgelab.common.file_operations import sub_operation_abs_path
from forgelab.srv_solver.solver_functions import run_solver


LOGGER = logging.getLogger(__name__)


class RemeshOp:

    required_input_key_words = ['process_duration', 'usrdef_triggers']

    files = dict(

        file_sim_ctrl_task_1=dict(
            file_path="Operations\\Task00001\\SimCtrl.KEY",
            parameters=dict(
                environment_temperature=dict(
                    s="ENVTMP       0    2.1100000000E+001", k=[0], n=2, f="\t{:>-21.10E}"),
                convection_coefficient=dict(
                    s="CNVCOF       0    2.1000000000E-002", k=[0], n=2, f="\t{:>-21.10E}"),
                global_time=dict(
                    s="TNOW     -1.0000000000E+021    0.0000000000E+000       1    0.0000000000E+000",
                    k=[0], n=1, f="\t{:>-21.10E}"),
                simulation_number_1=dict(
                    s="CURSIM       1       1       0", k=[0, 1], n=1, f="\t{:8d}"),
                operation_number=dict(
                    s="CURSIM       1       1       0", k=[0], n=2, f="\t{:8d}"))),

        file_sim_ctrl_task_2=dict(
            file_path="Operations\\Task00002\\SimCtrl.KEY",
            parameters=dict(
                process_duration=dict(
                    s="TMAX      1.1111000000E+000", k=[0], n=1, f="\t{:>-21.10E}"),
                after_remeshing_step_control_initial_time_step=dict(
                    s="DTMAX     1.8970000000E+000    0.0000000000E+000", k=[0], n=1, f="{:>-21.10E}\t"),
                after_remeshing_step_control_max_temperature=dict(
                    s="DTPMAX    4.5820000000E+000    1.5230000000E+000    2.5870000000E+001",
                    k=[0], n=1, f="\t{:>-21.10E}"),
                after_remeshing_step_control_min_time_step=dict(
                    s="DTPMAX    4.5820000000E+000    1.5230000000E+000    2.5870000000E+001",
                    k=[0], n=2, f="\t{:>-21.10E}"),
                after_remeshing_step_control_max_time_step=dict(
                    s="DTPMAX    4.5820000000E+000    1.5230000000E+000    2.5870000000E+001",
                    k=[0], n=3, f="\t{:>-21.10E}"),
                after_remeshing_environment_temperature=dict(
                    s="ENVTMP       0    1.9850000000E+001", k=[0], n=2, f="\t{:>-21.10E}"),
                after_remeshing_convection_coefficient=dict(
                    s="CNVCOF       0    1.8400000000E-002", k=[0], n=2, f="\t{:>-21.10E}"))),

        file_object_1=dict(
            file_path="Objects\\Object00001.KEY",
            parameters=dict(
                target_volume=dict(
                    s="TRGVOL       1       2    3.1105200000E+008", k=[0, 1], n=3, f="\t{:>-21.10E}"))),

        file_material=dict(
            file_path="Materials\\Material00001.KEY",
            parameters=dict(
                emissivity=dict(s="EMSVTY       1       0    7.0000000000E-001", k=[0, 1], n=3, f="{:>-21.10E}"))),

        file_key=dict(
            file_path="remesh_0001.KEY",
            parameters=dict(
                start_step_number=dict(s="NSTART    	-2359", k=[0], n=1, f="\t{:d}"),
                global_time=dict(s="TNOW	   	  -1E21       0       1", k=[0], n=1, f="\t{:>-21.10E}"),
                simulation_number_1=dict(
                    s="CURSIM    	1	1	0", k=[0, 1], n=1, f="\t{:8d}"),
                operation_number=dict(
                    s="CURSIM    	1	1	0", k=[0], n=2, f="\t{:8d}"))),

        file_mst=dict(
            file_path="remesh_0001.MST",
            parameters=dict(
                start_step_number=dict(s="NSTART    	-2359", k=[0], n=1, f="\t{:d}"),
                simulation_number_1=dict(
                    s="CURSIM    	1	1	0", k=[0, 1], n=1, f="\t{:8d}"),
                simulation_number_2=dict(
                    s="CURSIM    	2	2	0", k=[0, 1], n=1, f="\t{:8d}"),
                simulation_number_title_1=dict(
                    s="SIMULATION	1", k=[0, 1], n=1, f="\t{:d}"),
                simulation_number_title_2=dict(
                    s="SIMULATION	2", k=[0, 1], n=1, f="\t{:d}"),
                operation_number=dict(
                    s="CURSIM    	1	1	0", k=[0], n=2, f="\t{:8d}"))),

        file_mesh_task_4=dict(
            file_path="Operations\\Task00002\\MeshSettings00001.KEY",
            parameters=dict(
                after_remeshing_interference_depth_relative=dict(
                    s="RMDPTH       1   -6.8150100000E-001", k=[0, 1], n=2, f="\t{:>-21.10E}"),
                after_remeshing_maximum_stroke_increment=dict(
                    s="RMSTRK       1    1.0054100000E+003", k=[0, 1], n=2, f="\t{:>-21.10E}"),
                after_remeshing_maximum_time_increment=dict(
                    s="RMTIME       1    8.4564100000E+003", k=[0, 1], n=2, f="\t{:>-21.10E}"),
                after_remeshing_maximum_step_increment=dict(
                    s="RMSTEP       1    8.6520000000E+003", k=[0, 1], n=2, f="\t{:>-21.10E}"),
                after_remeshing_absolute_size_ratio=dict(
                    s="MGSIZR       1    2.3108000000E+000", k=[0, 1], n=2, f="\t{:>-21.10E}"),
                after_remeshing_number_of_surface_elements=dict(
                    s="MGNELM       1      93   32000     100       0", k=[0, 1], n=2, f="\t{:8d}"),
                after_remeshing_weighting_factor_boundary_curvature=dict(
                    s="MGWCUV       1    4.6900000000E-001", k=[0, 1], n=2, f="\t{:>-21.10E}"),
                after_remeshing_weighting_factor_temperature=dict(
                    s="MGWTMP       1    3.4000000000E-002", k=[0, 1], n=2, f="\t{:>-21.10E}"),
                after_remeshing_weighting_factor_strain=dict(
                    s="MGWSTN       1    2.2100000000E-001", k=[0, 1], n=2, f="\t{:>-21.10E}"),
                after_remeshing_weighting_factor_strain_rate=dict(
                    s="MGWSTR       1    2.8900000000E-001", k=[0, 1], n=2, f="\t{:>-21.10E}"),
                after_remeshing_inverse_max_element_size=dict(
                    s="MGWUSR       1    0.0000000000E+000    2.2727272727E-003       0",
                    k=[0, 1], n=3, f="\t{:>-21.10E}"))))

    moproj_file = dict(
        file_path="remesh_0001.moproj",
        parameters=dict(
            process_duration="      <Value>1.1111 sec</Value>",
            environment_temperature="      <Value>23.4 C</Value>",
            convection_coefficient="      <Value>0.0345 N/sec/mm/C</Value>",
            after_remeshing_step_control_initial_time_step="      <Value>1.897</Value>",
            after_remeshing_step_control_min_time_step="      <Value>1.523</Value>",
            after_remeshing_step_control_max_time_step="      <Value>25.87</Value>",
            after_remeshing_step_control_max_temperature="      <Value>4.582</Value>",
            after_remeshing_environment_temperature="      <Value>21.1 C</Value>",
            after_remeshing_convection_coefficient="      <Value>0.021 N/sec/mm/C</Value>",
            start_step_number="    <StartStepNo>-2359</StartStepNo>"))

    def __init__(self, _param: dict):
        self.param: dict = _param
        self.row: dict = {}
        self.pvid: int = 0
        self.eo: int = 0

    def run(self):
        try:
            self.param['operation']['template_name'] = "remesh_0001"

            self.eo = self.param['project']['execution_order']
            self.pvid = self.param['project']['process_version_id']
            self.row = self.param['table'][self.eo]

            previous_simulation_number = self.param['previous_operation']['simulation_number']
            sub_operation_path = sub_operation_abs_path(self.param)

            LOGGER.info(f"{self.log_id} STARTED RemeshOp at '{sub_operation_path}'")
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise
        try:
            operations_count = 2
            self.param['operation']['simulation_number'] = previous_simulation_number + 1

            self.pre_processing()
            run_solver(self.param)
            self.post_processing()

            self.param['operation']['simulation_number'] = previous_simulation_number + operations_count

            LOGGER.info(f"{self.log_id} FINISHED RemeshOp at '{sub_operation_path}'")
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError(f"FAILED at {sub_operation_path}")

    def pre_processing(self):
        """Pre-Process for Remeshing Sub-Operation class"""
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
            self._modify_parameters_in_files()
            convert_key_to_db(self.param)
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError(f"FAILED at {sub_operation_path}")

    def post_processing(self):
        """Post-Process for Remeshing Sub-Operation class"""
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
            template_name = self.param['operation']['template_name']
            mst_file = template_name + '.MST'
            key_file = template_name + '.KEY'
            sub_operation_path = sub_operation_abs_path(self.param)
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise
        try:
            self.__calculate_process_parameters()
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
            raise RuntimeError(f"FAILED at {sub_operation_path}")

    def __calculate_process_parameters(self):
        try:
            sub_operation_path = sub_operation_abs_path(self.param)
            start_step_number = self.param['previous_operation']['last_step_number']
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise
        try:
            # USRDEF triggers
            self.param['operation']['usrdef_triggers'] |= {
                'start_step_number': start_step_number
            }

            # Volume
            self.param['operation']['target_volume'] = self.row['volume_final']

            # Stopping criteria
            process_duration = max(self.param['operation']['process_duration'], 0.00001)
            self.param['operation']['process_duration'] = process_duration

            # Step size
            initial_time_step, min_time_step, max_time_step, max_temperature = \
                step_control_for_heat_transfer_input_process_duration(self.param['operation']['process_duration'])
            self.param['operation']['after_remeshing_step_control_initial_time_step'] = initial_time_step
            self.param['operation']['after_remeshing_step_control_min_time_step'] = min_time_step
            self.param['operation']['after_remeshing_step_control_max_time_step'] = max_time_step
            self.param['operation']['after_remeshing_step_control_max_temperature'] = max_temperature

            # Boundary conditions
            _environment_temperature = environment_temperature(self.row)
            _convection_coefficient = convection_coefficient(self.row, self.param)
            self.param['operation']['emissivity'] = emissivity(self.row)
            self.param['operation']['environment_temperature'] = _environment_temperature
            self.param['operation']['after_remeshing_environment_temperature'] = _environment_temperature
            self.param['operation']['convection_coefficient'] = _convection_coefficient
            self.param['operation']['after_remeshing_convection_coefficient'] = _convection_coefficient

            # Final Remeshing parameters for billet after Cutting
            after_remeshing_element_size_ratio = self.param['operation']['element_size_ratio']
            after_remeshing_min_element_size = min_element_size_function(self.row, self.param)
            after_remeshing_length_of_average_element = \
                after_remeshing_min_element_size * (1 + after_remeshing_element_size_ratio) / 2
            after_remeshing_face_area_of_average_element = \
                0.43301270189221932338 * after_remeshing_length_of_average_element ** 2
            #
            self.param['operation']['after_remeshing_absolute_size_ratio'] = after_remeshing_element_size_ratio
            self.param['operation']['after_remeshing_inverse_max_element_size'] = (
                    1 / (after_remeshing_min_element_size * after_remeshing_element_size_ratio))
            self.param['operation']['after_remeshing_interference_depth_relative'] = -0.7
            self.param['operation']['after_remeshing_maximum_step_increment'] = 0
            self.param['operation']['after_remeshing_maximum_stroke_increment'] = 0.0
            self.param['operation']['after_remeshing_maximum_time_increment'] = 0.0
            self.param['operation']['after_remeshing_number_of_surface_elements'] = \
                int(self.row['initial_surface_area'] / after_remeshing_face_area_of_average_element)
            self.param['operation']['after_remeshing_weighting_factor_boundary_curvature'] = 0.75
            self.param['operation']['after_remeshing_weighting_factor_strain'] = 0.25
            self.param['operation']['after_remeshing_weighting_factor_strain_rate'] = 0.0
            self.param['operation']['after_remeshing_weighting_factor_temperature'] = 0.25

            # Simulation controls
            self.param['operation']['start_step_number'] = start_step_number
            sim_number = self.param['operation']['simulation_number']
            self.param['operation']['simulations_names_list'] = [
                f'{int(process_duration):d}s_[{sim_number:d}]',
                f'Remesh_[{sim_number + 3:d}]']
            # CURSIM 6 21 0
            # CURSIM[1] = 6 - sequential simulation number
            # CURSIM[2] = 21 - operation number

            self.param['operation']['operation_number'] = self.param['project']['execution_order']

            self.param['operation']['simulation_number_1'] = sim_number
            self.param['operation']['simulation_number_2'] = sim_number + 1
            self.param['operation']['simulation_number_title_1'] = sim_number
            self.param['operation']['simulation_number_title_2'] = sim_number + 1

        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError(f"FAILED at {sub_operation_path}")

    @property
    def log_id(self):
        return self.param['operation']['log_id'] + f" Duration {time.monotonic() - self.param['operation']['project_start_datetime']:.2f}s {traceback.format_exc()}"
