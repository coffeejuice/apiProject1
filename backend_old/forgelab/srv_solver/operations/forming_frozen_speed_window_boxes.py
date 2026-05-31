import logging
import traceback
import time

from forgelab.config import config
from forgelab.common.boundary_conditions import \
    convection_coefficient, contact_heat_transfer, environment_temperature, friction, emissivity
from forgelab.srv_solver.pre_functions import remove_old_operation_files, copy_operation_template, \
    import_billet_from_previous_sub_operation, copy_die_template, convert_mst_file_to_key_file, \
    import_db_from_previous_sub_operation, apply_new_material, convert_key_to_db, \
    export_billet_and_parameters_from_db_last_step, move_db_to_project_dir, \
    change_operations_names_in_mst_or_key_file, automatic_modification_of_values_in_moproj_file, \
    automatic_modification_of_parameters_in_files, modify_mesh_number, modify_global_time, \
    deform_mesh_settings, cogging_step_size_die_displacement, add_velocity_boundary_conditions, \
    assert_missing_input_parameters, modify_usrdef_triggers, modify_user_variable_names, \
    initialize_user_nodal_variables_for_ingot_axis
from forgelab.common.file_operations import sub_operation_abs_path
from forgelab.srv_solver.solver_functions import run_solver


LOGGER = logging.getLogger(__name__)


class FormingFrozenSpeedWindowBoxesOp:

    required_input_key_words = ['offset_x', 'offset_y', 'offset_z', 'stopping_criteria_die_distance',
                                'stopping_criteria_die_displacement', 'user_defined_limit_press_load',
                                'usrdef_triggers']

    files = dict(
        file_HT_1=dict(
            file_path="Operations\\Task00001\\SimCtrl.KEY",
            parameters=dict(
                cooling_environment_temperature=dict(
                    s="ENVTMP       0    1.8652000000E+001", k=[0], n=2, f="\t{:>-21.10E}"),
                cooling_convection_coefficient=dict(
                    s="CNVCOF       0    2.6589000000E-002", k=[0], n=2, f="\t{:>-21.10E}"),
                global_time=dict(
                    s="TNOW     -1.0000000000E+021    0.0000000000E+000       1    0.0000000000E+000",
                    k=[0], n=1, f="\t{:>-21.10E}"),
                simulation_number_1=dict(
                    s="CURSIM       1       1       0", k=[0, 1], n=1, f="\t{:8d}"),
                operation_number=dict(
                    s="CURSIM       1       1       0", k=[0], n=2, f="\t{:8d}")
            )
        ),
        file_HT_2=dict(
            file_path="Operations\\Task00004\\SimCtrl.KEY",
            parameters=dict(
                simulation_number_2=dict(
                    s="CURSIM       2       2       0", k=[0, 1], n=1, f="\t{:8d}"),
                operation_number=dict(
                    s="CURSIM       2       2       0", k=[0], n=2, f="\t{:8d}")
            )
        ),
        file_forming_operation=dict(
            file_path="Operations\\Task00002\\SimCtrl.KEY",
            parameters=dict(
                stopping_criteria_die_distance=dict(
                    s="MDSOBJ       2       3       3    8.8870000000E+002", k=[0, 1, 2, 3], n=4, f="\t{:>-21.10E}"),
                forming_step_size_die_displacement=dict(
                    s="DSMAX     1.0842800000E+000", k=[0], n=1, f="\t{:>-21.10E}"),
                forming_sub_stepping_control_max_strain_in_element=dict(
                    s="DEMAX     8.4108000000E-001", k=[0], n=1, f="\t{:>-21.10E}"),
                forming_sub_stepping_control_max_polygon_length=dict(
                    s="DPLEN     2.4046000000E-001", k=[0], n=1, f="\t{:>-21.10E}"),
                forming_environment_temperature=dict(
                    s="ENVTMP       0    1.7540000000E+001", k=[0, 1], n=2, f="\t{:>-21.10E}"),
                forming_convection_coefficient=dict(
                    s="CNVCOF       0    2.8400000000E-002", k=[0, 1], n=2, f="\t{:>-21.10E}"),
                forming_stopping_criteria_time=dict(
                    s="TMAX      8.4202100000E+002", k=[0], n=1, f="\t{:>-21.10E}"),
                forming_stopping_criteria_max_load=dict(
                    s="LMAX      0.0000000000E+000    0.0000000000E+000    6.6610000000E+002",
                    k=[0], n=3, f="\t{:>-21.10E}"),
                stopping_criteria_die_displacement=dict(
                    s="SMAX      0.0000000000E+000    0.0000000000E+000    4.1230000000E+000",
                    k=[0], n=3, f="\t{:>-21.10E}"),
                simulation_number_3=dict(
                    s="CURSIM       3       3       0", k=[0, 1], n=1, f="\t{:8d}"),
                operation_number=dict(
                    s="CURSIM       3       3       0", k=[0], n=2, f="\t{:8d}")
            )
        ),
        file_mat=dict(
            file_path="Materials\\Material00001.KEY",
            parameters=dict(
                emissivity=dict(s="EMSVTY       1       0    7.0000000000E-001", k=[0, 1], n=3, f="\t{:>-21.10E}")
            )),
        file_mst=dict(
            file_path="forming_frozen_speed_window_boxes_01.MST",
            parameters=dict(
                start_step_number=dict(s="NSTART    	-2359", k=[0], n=1, f="\t{:d}"),
                offset_x=dict(
                    s="OBJPOS	1	1	1	0	0	0	0	0	0", k=list(range(10)), n=3, f="\t{:.5f}"),
                offset_y=dict(
                    s="OBJPOS	1	1	0	2	0	0	0	0	0", k=list(range(10)), n=4, f="\t{:.5f}"),
                offset_z=dict(
                    s="OBJPOS	1	1	0	0	3	0	0	0	0", k=list(range(10)), n=5, f="\t{:.5f}"),
                stopping_criteria_die_distance=dict(
                    s="MDSOBJ	2	3	3	245.325", k=[0, 1, 2, 3], n=4, f="\t{:>.3f}"),
                forming_generate_contact_band=dict(s="GENCTC    	0.14789", k=[0], n=1, f="\t{:>.5f}"),
                simulation_number_1=dict(
                    s="CURSIM    	1	1	0", k=[0, 1], n=1, f="\t{:8d}"),
                simulation_number_2=dict(
                    s="CURSIM    	2	2	0", k=[0, 1], n=1, f="\t{:8d}"),
                simulation_number_3=dict(
                    s="CURSIM    	3	3	0", k=[0, 1], n=1, f="\t{:8d}"),
                simulation_number_title_1=dict(
                    s="SIMULATION	1", k=[0, 1], n=1, f="\t{:d}"),
                simulation_number_title_2=dict(
                    s="SIMULATION	2", k=[0, 1], n=1, f="\t{:d}"),
                simulation_number_title_3=dict(
                    s="SIMULATION	3", k=[0, 1], n=1, f="\t{:d}"),
                operation_number=dict(
                    s="CURSIM    	3	3	0", k=[0], n=2, f="\t{:8d}")
            )
        ),
        file_billet=dict(
            file_path="Objects\\Object00001.KEY",
            parameters=dict(
                target_volume=dict(
                    s="TRGVOL       1       2    6.9644300000E+007", k=[0, 1], n=3, f="\t{:>-21.10E}"),
                cooling_average_strain_rate=dict(
                    s="AVGSTR       1    1.8563000000E+000", k=[0, 1], n=2, f="\t{:>-21.10E}"),
                cooling_limiting_strain_rate=dict(
                    s="LMTSTR       1    1.2157800000E-002", k=[0, 1], n=2, f="\t{:>-21.10E}"),
            )
        ),
        file_top_die=dict(
            file_path="Objects\\Object00002.KEY",
            parameters=dict(
                top_die_half_speed=dict(
                    s="MOVCTL       2       1       0    "
                      "0.0000000000E+000    0.0000000000E+000   -1.0000000000E+000    6.7770000000E+000",
                    k=[0, 1], n=7, f="\t{:>-21.10E}"),
                cooling_top_die_reference_temperature=dict(
                    s="REFTMP       2    3.8525500000E+002", k=[0, 1], n=2, f="\t{:>-21.10E}")
            )
        ),
        file_bottom_die=dict(
            file_path="Objects\\Object00003.KEY",
            parameters=dict(
                cooling_bottom_die_reference_temperature=dict(
                    s="REFTMP       3    3.2545900000E+002", k=[0, 1], n=2, f="\t{:>-21.10E}")
            )
        ),
        file_equipment_02=dict(
            file_path="Equipments\\Equipment00002.KEY",
            parameters=dict(
                top_die_half_speed=dict(
                    s="MOVCTL       2       1       0    "
                      "0.0000000000E+000    0.0000000000E+000   -1.0000000000E+000    6.7770000000E+000",
                    k=[0, 1], n=7, f="\t{:>-21.10E}"
                )
            )
        ),
        file_equipment_08=dict(
            file_path="Equipments\\Equipment00008.KEY",
            parameters=dict(
                top_die_half_speed=dict(
                    s="MOVCTL       2       1       0    "
                      "0.0000000000E+000    0.0000000000E+000   -1.0000000000E+000    6.7770000000E+000",
                    k=[0, 1], n=7, f="\t{:>-21.10E}")
            )
        ),
        file_equipment_16=dict(
            file_path="Equipments\\Equipment00016.KEY",
            parameters=dict(
                top_die_half_speed=dict(
                    s="MOVCTL       2       1       0    "
                      "0.0000000000E+000    0.0000000000E+000   -1.0000000000E+000    6.7770000000E+000",
                    k=[0, 1, 2, 3], n=7, f="\t{:>-21.10E}")
            )
        ),
        file_lubricant=dict(
            file_path="Lubricants\\Lubricant00001.KEY",
            parameters=dict(
                friction=dict(
                    s="FRCFAC       1       1       1       0    6.4580000000E-001",
                    k=[0], n=5, f="\t{:>-21.10E}"),
                contact_heat_transfer=dict(
                    s="IHTCOF       1       1       0    4.1585000000E+000",
                    k=[0], n=4, f="\t{:>-21.10E}")
            )
        ),
        file_inter_object=dict(
            file_path="Operations\\Task00002\\InterObject.KEY",
            parameters=dict(
                friction=dict(
                    s="FRCFAC       1       2       1       0    6.4580000000E-001",
                    k=[0], n=5, f="\t{:>-21.10E}"),
                contact_heat_transfer=dict(
                    s="IHTCOF       1       1       0    4.1585000000E+000",
                    k=[0], n=4, f="\t{:>-21.10E}")
            )
        ),
        # file_remeshing=dict(
        #     file_path="Operations\\Task00002\\MeshSettings00001.KEY",
        #     parameters=dict(
        #         forming_remeshing_interference_depth_relative=dict(
        #             s="RMDPTH       1   -6.8150100000E-001", k=[0, 1], n=2, f="\t{:>-21.10E}"),
        #         forming_remeshing_maximum_stroke_increment=dict(
        #             s="RMSTRK       1    1.0054100000E+003", k=[0, 1], n=2, f="\t{:>-21.10E}"),
        #         forming_remeshing_maximum_time_increment=dict(
        #             s="RMTIME       1    8.4564100000E+003", k=[0, 1], n=2, f="\t{:>-21.10E}"),
        #         forming_remeshing_maximum_step_increment=dict(
        #             s="RMSTEP       1    8.6520000000E+003", k=[0, 1], n=2, f="\t{:>-21.10E}"),
        #         forming_remeshing_absolute_size_ratio=dict(
        #             s="MGSIZR       1    2.3108000000E+000", k=[0, 1], n=2, f="\t{:>-21.10E}"),
        #         forming_remeshing_number_of_surface_elements=dict(
        #             s="MGNELM       1      93   32000     100       0", k=[0, 1], n=2, f="\t{:8d}"),
        #         forming_remeshing_weighting_factor_boundary_curvature=dict(
        #             s="MGWCUV       1    4.6900000000E-001", k=[0, 1], n=2, f="\t{:>-21.10E}"),
        #         forming_remeshing_weighting_factor_temperature=dict(
        #             s="MGWTMP       1    3.4000000000E-002", k=[0, 1], n=2, f="\t{:>-21.10E}"),
        #         forming_remeshing_weighting_factor_strain=dict(
        #             s="MGWSTN       1    2.2100000000E-001", k=[0, 1], n=2, f="\t{:>-21.10E}"),
        #         forming_remeshing_weighting_factor_strain_rate=dict(
        #             s="MGWSTR       1    2.8900000000E-001", k=[0, 1], n=2, f="\t{:>-21.10E}"),
        #         forming_remeshing_inverse_max_element_size=dict(
        #             s="MGWUSR       1    0.0000000000E+000    2.2727272727E-003       0",
        #             k=[0, 1], n=3, f="\t{:>-21.10E}"),
        #     )
        # ),
        file_keyfile=dict(
            file_path="forming_frozen_speed_window_boxes_01.KEY",
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

    moproj_file = dict(
        file_path="forming_frozen_speed_window_boxes_01.moproj",
        parameters=dict(
            cooling_environment_temperature="      <Value>18.652 C</Value>",
            cooling_convection_coefficient="      <Value>0.026589 N/sec/mm/C</Value>",
            forming_generate_contact_band="    <Keyword>GENCTC    	0.14789</Keyword>",
            forming_environment_temperature="      <Value>17.54 C</Value>",
            force_dwell_convection_coefficient="      <Value>0.0284 N/sec/mm/C</Value>",
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
            self.param['operation']['template_name'] = "forming_frozen_speed_window_boxes_01"

            self.eo = self.param['project']['execution_order']
            self.pvid = self.param['project']['process_version_id']
            self.row = self.param['table'][self.eo]

            previous_simulation_number = self.param['previous_operation']['simulation_number']
            sub_operation_path = sub_operation_abs_path(self.param)

            LOGGER.info(f"{self.log_id} STARTED FormingFrozenSpeedWindowBoxesOp at '{sub_operation_path}'")
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise
        try:
            operations_count = 3
            self.param['operation']['simulation_number'] = previous_simulation_number + 1

            self.pre_processing()
            run_solver(self.param)
            self.post_processing()

            self.param['operation']['simulation_number'] = previous_simulation_number + operations_count

            LOGGER.info(f"{self.log_id} FINISHED FormingFrozenSpeedWindowBoxesOp at '{sub_operation_path}'")
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError(f"FAILED at {sub_operation_path}")

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
            copy_die_template(self.param, self.row)
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
            template_name = self.param['operation']['template_name']
            mst_file = template_name + '.MST'
            key_file = template_name + '.KEY'
            sub_operation_path = sub_operation_abs_path(self.param)
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise
        try:
            assert_missing_input_parameters(self.required_input_key_words, self.param)
            self._calculate_process_parameters()
            change_operations_names_in_mst_or_key_file(self.param, mst_file)
            change_operations_names_in_mst_or_key_file(self.param, key_file)
            automatic_modification_of_values_in_moproj_file(self.moproj_file, self.param)
            automatic_modification_of_parameters_in_files(self.files, self.param)
            modify_mesh_number(self.param, key_file)
            modify_global_time(self.param, key_file)
            add_velocity_boundary_conditions(self.param, relative_filepath="Objects\\Object00001.KEY")
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
            measurements = self.param['operation']['imported_keyfile']['objects'][1]['measurements']
            sub_operation_path = sub_operation_abs_path(self.param)
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise
        try:
            # operation_type = self.row['operation_type']
            # sub_operation_path = sub_operation_abs_path(self.param)

            press_mode = config.lib['press_mode'].loc[self.row['press_mode_id']]
            mesh = deform_mesh_settings(self.row, self.param)

            user_limit_force = self.param['operation']['user_defined_limit_press_load']
            max_press_force = press_mode['max_force']
            if user_limit_force > 0.0:
                max_force = min(max_press_force, user_limit_force)
            else:
                max_force = max_press_force

            min_speed = press_mode['min_dwell_speed']

            start_step_number = self.param['previous_operation']['last_step_number']

            # USRDEF triggers
            self.param['operation']['usrdef_triggers'] |= {
                'start_step_number': start_step_number
            }

            # Initial parameters
            self.param['operation']['cooling_bottom_die_reference_temperature'] = 400.0
            self.param['operation']['cooling_top_die_reference_temperature'] = 400.0

            self.param['operation']['target_volume'] = self.row['volume_final']
            self.param['operation']['positioning_dies_method'] = 2

            # Stepping control
            self.param['operation']['start_step_number'] = start_step_number
            self.param['operation']['forming_step_size_die_displacement'] = \
                cogging_step_size_die_displacement(self.param, self.row)
            self.param['operation']['forming_sub_stepping_control_max_polygon_length'] = 0.3
            self.param['operation']['forming_sub_stepping_control_max_strain_in_element'] = 0.7
            self.param['operation']['force_dwell_sub_stepping_control_max_polygon_length'] = 0.3
            self.param['operation']['force_dwell_sub_stepping_control_max_strain_in_element'] = 0.7

            # Stopping criteria
            stopping_criteria_die_displacement = self.param['operation']['stopping_criteria_die_displacement']
            initial_height = measurements['height']
            stopping_criteria_die_distance = self.param['operation']['stopping_criteria_die_distance']
            if stopping_criteria_die_displacement > 0:
                stopping_criteria_stroke = min(stopping_criteria_die_displacement,
                                               initial_height - stopping_criteria_die_distance)
            else:
                stopping_criteria_stroke = initial_height - stopping_criteria_die_distance
            deformation_time_for_constant_min_speed = stopping_criteria_stroke / min_speed
            #
            self.param['operation']['forming_stopping_criteria_max_load'] = max_force
            self.param['operation']['forming_stopping_criteria_time'] = deformation_time_for_constant_min_speed

            # Movement criteria
            self.param['operation']['top_die_half_speed'] = 0.5 * self.row['speed']
            # self.param['operation']['force_dwell_die_force'] = max_force
            # self.param['operation']['force_dwell_stopping_criteria_min_velocity'] = 0.5 * min_speed

            # Boundary conditions
            _convection_coefficient = convection_coefficient(self.row, self.param)
            self.param['operation']['contact_heat_transfer'] = contact_heat_transfer(self.row)
            self.param['operation']['cooling_convection_coefficient'] = _convection_coefficient
            self.param['operation']['forming_convection_coefficient'] = _convection_coefficient
            self.param['operation']['force_dwell_convection_coefficient'] = _convection_coefficient
            self.param['operation']['cooling_environment_temperature'] = environment_temperature(self.row)
            self.param['operation']['forming_environment_temperature'] = environment_temperature(self.row)
            self.param['operation']['force_dwell_environment_temperature'] = environment_temperature(self.row)
            self.param['operation']['forming_generate_contact_band'] = 0.01 * mesh['min_element_size']
            self.param['operation']['emissivity'] = emissivity(self.row)
            self.param['operation']['friction'] = friction(self.row)

            # Limiting strain rate
            self.param['operation']['cooling_average_strain_rate'] = self.row['speed'] / self.row['initial_length']
            self.param['operation']['cooling_limiting_strain_rate'] = \
                0.01 * self.param['operation']['cooling_average_strain_rate']

            # Remeshing parameters
            self.param['operation']['forming_remeshing_absolute_size_ratio'] = mesh['element_size_ratio']
            self.param['operation']['forming_remeshing_inverse_max_element_size'] = mesh['inverse_max_element_size']
            self.param['operation']['forming_remeshing_interference_depth_relative'] = -0.4
            self.param['operation']['forming_remeshing_maximum_step_increment'] = 0
            self.param['operation']['forming_remeshing_maximum_stroke_increment'] = 0.0
            self.param['operation']['forming_remeshing_maximum_time_increment'] = 0.0
            self.param['operation']['forming_remeshing_number_of_surface_elements'] = mesh['number_of_surface_elements']
            self.param['operation']['forming_remeshing_weighting_factor_boundary_curvature'] = 0.75
            self.param['operation']['forming_remeshing_weighting_factor_strain'] = 0.25
            self.param['operation']['forming_remeshing_weighting_factor_strain_rate'] = 0.0
            self.param['operation']['forming_remeshing_weighting_factor_temperature'] = 0.25

            self.param['operation']['simulations_names_list'] = [
                f"RH1-PS{self.param['operation']['bite_number'] + 1:d}-PHT",
                f"RH1-PS{self.param['operation']['bite_number'] + 1:d}-PDWL",
                f"RH1-PS{self.param['operation']['bite_number'] + 1:d}-BDEF1"
            ]

            # CURSIM 6 21 0
            # CURSIM[1] = 6 - sequential simulation number
            # CURSIM[2] = 21 - operation number

            self.param['operation']['operation_number'] = self.param['project']['execution_order']

            sim_number = self.param['operation']['simulation_number']
            self.param['operation']['simulation_number_1'] = sim_number
            self.param['operation']['simulation_number_2'] = sim_number + 1
            self.param['operation']['simulation_number_3'] = sim_number + 2
            self.param['operation']['simulation_number_title_1'] = sim_number
            self.param['operation']['simulation_number_title_2'] = sim_number + 1
            self.param['operation']['simulation_number_title_3'] = sim_number + 2
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError(f"FAILED at {sub_operation_path}")

    @property
    def log_id(self):
        return self.param['operation']['log_id'] + f" Duration {time.monotonic() - self.param['operation']['project_start_datetime']:.2f}s {traceback.format_exc()}"
