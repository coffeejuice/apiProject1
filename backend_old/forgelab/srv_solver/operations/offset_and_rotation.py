import logging
import traceback
import time

from forgelab.common.boundary_conditions import emissivity
from forgelab.srv_solver.pre_functions import remove_old_operation_files, copy_operation_template, \
    import_billet_from_previous_sub_operation, convert_mst_file_to_key_file, import_db_from_previous_sub_operation, \
    apply_new_material, convert_key_to_db, export_billet_and_parameters_from_db_last_step, move_db_to_project_dir, \
    change_operations_names_in_mst_or_key_file, automatic_modification_of_values_in_moproj_file, \
    automatic_modification_of_parameters_in_files, modification_of_parameter_in_files_counting_spaces, \
    modify_mesh_number, modify_global_time, remove_velocity_boundary_conditions, remove_wpaxis_rigid_zone, \
    modify_usrdef_triggers, modify_user_variable_names, initialize_user_nodal_variables_for_ingot_axis
from forgelab.common.file_operations import sub_operation_abs_path
from forgelab.srv_solver.solver_functions import run_solver


LOGGER = logging.getLogger(__name__)


class OffsetRotationOp:

    required_input_key_words = [
        'offset_x', 'offset_y', 'offset_z',
        'rotation_around_x', 'rotation_around_y', 'rotation_around_z',
        'usrdef_triggers'
    ]

    files = dict(
        file_01=dict(
            file_path="offset_rotation_z_y_x_01.MST",
            parameters=dict(
                start_step_number=dict(s="NSTART    	-2359", k=[0], n=1, f="\t{:d}"),
                offset_x=dict(
                    s="OBJPOS	1	1	7.777	8.888	9.999	0	0	0	0", k=[0, 1, 2], n=3, f="\t{:.5f}"),
                offset_y=dict(
                    s="OBJPOS	1	1	7.777	8.888	9.999	0	0	0	0", k=[0, 1, 2], n=4, f="\t{:.5f}"),
                offset_z=dict(
                    s="OBJPOS	1	1	7.777	8.888	9.999	0	0	0	0", k=[0, 1, 2], n=5, f="\t{:.5f}"),
                rotation_around_x=dict(
                    s="OBJPOS	1	3	0	0	0	1	0	0	1.234", k=list(range(9)), n=9, f="\t{:.5f}"),
                rotation_around_y=dict(
                    s="OBJPOS	1	3	0	0	0	0	1	0	2.345", k=list(range(9)), n=9, f="\t{:.5f}"),
                rotation_around_z=dict(
                    s="OBJPOS	1	3	0	0	0	0	0	1	3.456", k=list(range(9)), n=9, f="\t{:.5f}"),
                simulation_number_1=dict(
                    s="CURSIM    	1	1	0", k=[0, 1], n=1, f="\t{:8d}"),
                simulation_number_2=dict(
                    s="CURSIM    	2	2	0", k=[0, 1], n=1, f="\t{:8d}"),
                simulation_number_title_1=dict(
                    s="SIMULATION	1", k=[0, 1], n=1, f="\t{:d}"),
                simulation_number_title_2=dict(
                    s="SIMULATION	2", k=[0, 1], n=1, f="\t{:d}"),
                operation_number=dict(
                    s="CURSIM    	1	1	0", k=[0], n=2, f="\t{:8d}")
            )
        ),
        file_02=dict(
            file_path="offset_rotation_z_y_x_01.moproj",
            parameters=dict(
                rotation_around_y=dict(
                    s="OBJPOS	1	3	0	0	0	0	1	0	2.345", k=list(range(9)), n=9, f="\t{:.5f}"),
                rotation_around_z=dict(
                    s="OBJPOS	1	3	0	0	0	0	0	1	3.456", k=list(range(9)), n=9, f="\t{:.5f}")
            )
        ),
        file_03=dict(
            file_path="Materials\\Material00001.KEY",
            parameters=dict(
                emissivity=dict(s="EMSVTY       1       0    7.0000000000E-001", k=[0, 1], n=3, f="{:>-21.10E}")
            )
        ),
        file_04=dict(
            file_path="Operations\\Task00001\\SimCtrl.KEY",
            parameters=dict(
                global_time=dict(
                    s="TNOW     -1.0000000000E+021    0.0000000000E+000       1    0.0000000000E+000",
                    k=[0], n=1, f="\t{:>-21.10E}"),
                simulation_number_1=dict(
                    s="CURSIM       1       1       0", k=[0, 1], n=1, f="\t{:8d}"),
                operation_number=dict(
                    s="CURSIM       1       1       0", k=[0], n=2, f="\t{:8d}")
            )
        ),
        file_04a=dict(
            file_path="Operations\\Task00002\\SimCtrl.KEY",
            parameters=dict(
                simulation_number_2=dict(
                    s="CURSIM       2       2       0", k=[0, 1], n=1, f="\t{:8d}"),
                operation_number=dict(
                    s="CURSIM       2       2       0", k=[0], n=2, f="\t{:8d}")
            )
        ),
        file_05=dict(
            file_path="offset_rotation_z_y_x_01.KEY",
            parameters=dict(
                start_step_number=dict(s="NSTART    	-2359", k=[0], n=1, f="\t{:d}"),
                global_time=dict(s="TNOW	   	  -1E21       0       1", k=[0], n=1, f="\t{:>-21.10E}"),
                simulation_number_1=dict(
                    s="CURSIM    	1	1	0", k=[0, 1], n=1, f="\t{:8d}"),
                operation_number=dict(
                    s="CURSIM    	1	1	0", k=[0], n=2, f="\t{:8d}")
            )
        )
    )

    files_2 = dict(
        file_02=dict(
            file_path="offset_rotation_z_y_x_01.moproj",
            parameters=dict(
                rotation_around_x=dict(
                    s="    <Keyword>OBJPOS	1	3	0	0	0	1	0	0	1.234",
                    k=list(range(9)), n=19, f="\t{:.5f}"),
                rotation_around_y=dict(
                    s="    <Keyword>OBJPOS	1	3	0	0	0	0	1	0	2.345",
                    k=list(range(9)), n=19, f="\t{:.5f}"),
                rotation_around_z=dict(
                    s="    <Keyword>OBJPOS	1	3	0	0	0	0	0	1	3.456",
                    k=list(range(9)), n=19, f="\t{:.5f}")
            ))
    )

    moproj_file = dict(
        file_path="offset_rotation_z_y_x_01.moproj",
        parameters=dict(
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
            self.param['operation']['template_name'] = "offset_rotation_z_y_x_01"

            self.eo = self.param['project']['execution_order']
            self.pvid = self.param['project']['process_version_id']
            self.row = self.param['table'][self.eo]

            previous_simulation_number = self.param['previous_operation']['simulation_number']
            sub_operation_path = sub_operation_abs_path(self.param)

            LOGGER.info(f"{self.log_id} STARTED OffsetRotationOp at '{sub_operation_path}'")
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

            LOGGER.info(f"{self.log_id} FINISHED OffsetRotationOp at '{sub_operation_path}'")
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError(f"FAILED at '{sub_operation_path}'")

    def pre_processing(self):
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
            raise RuntimeError(f"FAILED at '{sub_operation_path}'")

    def post_processing(self):
        """Post-Process for Rotation Sub-Operation class"""
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
            _o = self.param['operation']
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise
        try:
            template_name = self.param['operation']['template_name']
            mst_file = template_name + ".MST"
            key_file = template_name + ".KEY"

            self._calculate_process_parameters()
            change_operations_names_in_mst_or_key_file(self.param, mst_file)
            change_operations_names_in_mst_or_key_file(self.param, key_file)
            automatic_modification_of_values_in_moproj_file(self.moproj_file, self.param)
            automatic_modification_of_parameters_in_files(self.files, self.param)
            modification_of_parameter_in_files_counting_spaces(self.files_2, self.param)
            modify_mesh_number(self.param, key_file)
            modify_global_time(self.param, key_file)
            remove_velocity_boundary_conditions(self.param, relative_filepath="Objects\\Object00001.KEY")
            remove_wpaxis_rigid_zone(self.param, relative_filepath="Objects\\Object00001.KEY")
            # ----------------------- INITIALIZE INGOT AXIS --------------------------
            initialize_user_nodal_variables_for_ingot_axis(self.param, rx=_o['rotation_around_x'], ry=_o['rotation_around_y'], rz=_o['rotation_around_z'], dx=_o['offset_x'], dy=_o['offset_y'], dz=_o['offset_z'])
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
            missed_keys = [key for key in self.required_input_key_words if key not in self.param['operation'].keys()]
            assert not missed_keys, f"Missed keys {', '.join(missed_keys)} in param['operation']"

            start_step_number = self.param['previous_operation']['last_step_number']

            # Boundary conditions
            self.param['operation']['emissivity'] = emissivity(self.row)

            # Step control
            self.param['operation']['start_step_number'] = start_step_number

            # USRDEF triggers
            self.param['operation']['usrdef_triggers'] |= {
                'start_step_number': start_step_number
            }

            # Simulation control
            self.param['operation']['simulations_names_list'] = [
                f"{self.param['operation']['sub_operation_name']}_{self.param['operation']['sub_operation_type']}_1",
                f"{self.param['operation']['sub_operation_name']}_{self.param['operation']['sub_operation_type']}_2"]
            # CURSIM 6 21 0
            # CURSIM[1] = 6 - sequential simulation number
            # CURSIM[2] = 21 - operation number

            self.param['operation']['operation_number'] = self.param['project']['execution_order']

            sim_number = self.param['operation']['simulation_number']
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
