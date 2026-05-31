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
    automatic_modification_of_parameters_in_files, modify_mesh_number, modify_global_time, modify_power_limit, \
    cogging_step_size_die_displacement, deform_mesh_settings, modify_usrdef_triggers, modify_user_variable_names, \
    initialize_user_nodal_variables_for_ingot_axis
from forgelab.common.file_operations import sub_operation_abs_path
from forgelab.srv_solver.solver_functions import run_solver


LOGGER = logging.getLogger(__name__)


class CoggingBiteOp:
    # self.param['operation'][...]
    required_input_key_words = ['cooling_time',
                                'billet_offset_x', 'billet_offset_y', 'billet_offset_z',
                                'billet_rotation_around_x', 'billet_rotation_around_y', 'billet_rotation_around_z',
                                'top_die_offset_x', 'top_die_offset_y', 'top_die_offset_z',
                                'bottom_die_offset_x', 'bottom_die_offset_y', 'bottom_die_offset_z',
                                'stopping_criteria_die_distance',
                                'positioning_dies_start',
                                'rotation_angle_per_byte', 'rotation_angle_per_pass',
                                'usrdef_triggers',
                                'parent_log_id']

    files = dict(
        file_HT01=dict(
            file_path="Operations\\Task00001\\SimCtrl.KEY",
            parameters=dict(
                cooling_time=dict(s="TMAX      2.9860000000E+000", k=[0], n=1, f="\t{:>-21.10E}"),
                cooling_step_control_initial_time_step=dict(
                    s="DTMAX     1.8235000000E+000    1.8809278351E+000", k=[0], n=1, f="\t{:>-21.10E}"),
                force_dwell_step_size_time_increment=dict(
                    s="DTMAX     1.8235000000E+000    1.8809278351E+000", k=[0], n=2, f="\t{:>-21.10E}"),
                cooling_step_control_max_temperature=dict(
                    s="DTPMAX    4.2135800000E+000    2.0456300000E+000    9.8562000000E+000",
                    k=[0], n=1, f="\t{:>-21.10E}"),
                cooling_step_control_min_time_step=dict(
                    s="DTPMAX    4.2135800000E+000    2.0456300000E+000    9.8562000000E+000",
                    k=[0], n=2, f="\t{:>-21.10E}"),
                cooling_step_control_max_time_step=dict(
                    s="DTPMAX    4.2135800000E+000    2.0456300000E+000    9.8562000000E+000",
                    k=[0], n=3, f="\t{:>-21.10E}"),
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
        file_HT02=dict(
            file_path="Materials\\Material00001.KEY",
            parameters=dict(
                emissivity=dict(s="EMSVTY       1       0    7.0000000000E-001", k=[0, 1], n=3, f="\t{:>-21.10E}")
            )),
        file_01=dict(
            file_path="Operations\\Task00002\\Cogging.MDT",
            parameters=dict(
                rotation_angle_per_pass=dict(s="RotAng         2.1843599E+001", k=[0, 1], n=1, f="\t{:>-16.7E}"),
                rotation_angle_per_byte=dict(s="BiteAngle      1.4254800E+001", k=[0, 1], n=1, f="\t{:>-16.7E}"),
                stopping_criteria_die_distance=dict(s="MinDieDis      2.4532500E+002", k=[0], n=1, f="\t{:>-16.7E}"),
                positioning_dies_method=dict(s="DiePosMethod       2", k=[0], n=1, f="\t{:8d}"),
                positioning_dies_start=dict(s="DieStrtPos     1.9542999E+002", k=[0], n=1, f="\t{:>-16.7E}"),
                die_moving_direction=dict(s="DieMovDir         -1", k=[0], n=1, f="\t{:11d}"),
                die_half_speed=dict(s="SPDDIE     1.0548960E+001", k=[0], n=1, f="\t{:>-16.7E}"),
                manipulator_start_position=dict(s="StartPos    5.1846001E+001", k=[0], n=1, f="\t{:>-16.7E}"),
                manipulator_handover_distance_left=dict(s="LeftDis     4.2816002E+001", k=[0], n=1, f="\t{:>-16.7E}"),
                manipulator_handover_distance_right=dict(s="RightDis    3.8484001E+001", k=[0], n=1, f="\t{:>-16.7E}"),
                manipulator_stiffness=dict(s="Stiffness   4.2884601E+002", k=[0], n=1, f="\t{:>-16.7E}"),
                manipulator_preload=dict(s="Preload     2.2243400E+005", k=[0], n=1, f="\t{:>-16.7E}"),
                manipulator_max_spring_displacement=dict(s="MaxDisp     2.5441499E+003", k=[0], n=1, f="\t{:>-16.7E}")
            )
        ),
        file_02=dict(
            file_path="cogging_bite_01.MST",
            parameters=dict(
                start_step_number=dict(s="NSTART    	-2359", k=[0], n=1, f="\t{:d}"),
                stopping_criteria_die_distance=dict(s="MDSOBJ	2	3	3	245.325",
                                                    k=[0, 1, 2, 3], n=4, f="\t{:>.3f}"),
                # SIMULATION 2
                billet_offset_x=dict(s="OBJPOS	1	1	2	2	2	0	0	0	0", k=[0, 1, 2], n=3, f="\t{:.5f}"),
                billet_offset_y=dict(s="OBJPOS	1	1	2	2	2	0	0	0	0", k=[0, 1, 2], n=4, f="\t{:.5f}"),
                billet_offset_z=dict(s="OBJPOS	1	1	2	2	2	0	0	0	0", k=[0, 1, 2], n=5, f="\t{:.5f}"),
                rotation_angle_per_pass=dict(s="OBJPOS	1	3	0	0	0	1	0	0	21.8436	4",
                                             k=list(range(11)), n=9, f="\t{:.5f}"),
                billet_rotation_around_z=dict(s="OBJPOS	1	3	0	0	0	0	0	1	3",
                                              k=list(range(10)), n=9, f="\t{:.5f}"),
                billet_rotation_around_y=dict(s="OBJPOS	1	3	0	0	0	0	1	0	4",
                                              k=list(range(10)), n=9, f="\t{:.5f}"),
                billet_rotation_around_x=dict(s="OBJPOS	1	3	0	0	0	1	0	0	5",
                                              k=list(range(10)), n=9, f="\t{:.5f}"),
                top_die_offset_x=dict(s="OBJPOS	2	1	6	6	6	0	0	0	0", k=[0, 1, 2], n=3, f="\t{:.5f}"),
                top_die_offset_y=dict(s="OBJPOS	2	1	6	6	6	0	0	0	0", k=[0, 1, 2], n=4, f="\t{:.5f}"),
                top_die_offset_z=dict(s="OBJPOS	2	1	6	6	6	0	0	0	0", k=[0, 1, 2], n=5, f="\t{:.5f}"),
                bottom_die_offset_x=dict(s="OBJPOS	3	1	7	7	7	0	0	0	0", k=[0, 1, 2], n=3, f="\t{:.5f}"),
                bottom_die_offset_y=dict(s="OBJPOS	3	1	7	7	7	0	0	0	0", k=[0, 1, 2], n=4, f="\t{:.5f}"),
                bottom_die_offset_z=dict(s="OBJPOS	3	1	7	7	7	0	0	0	0", k=[0, 1, 2], n=5, f="\t{:.5f}"),

                # SIMULATION 3
                # rotation_angle_per_pass=dict(
                #     s="OBJPOS	1	3	0	0	0	1	0	0	21.8436	4", k=list(range(9)), n=9,
                #     f="\t{:>.4f}"),
                positioning_dies_start=dict(
                    s="OBJPOS	2	13	0	-1	0	0	1	2	195.43	1",
                    k=[0, 1, 2, 3, 5, 6, 7, 8], n=9, f="\t{:>.3f}"),
                die_moving_direction=dict(
                    s="OBJPOS	2	13	0	-1	0	0	1	2	195.43	1",
                    k=[0, 1, 2, 3, 5, 6, 7, 8], n=4, f="\t{:8d}"),
                manipulator_start_position_2=dict(
                    s="OBJPOS	4	13	0	-1	0	0	1	2	114.346	1",
                    k=[0, 1, 2, 3, 5, 6, 7, 8], n=9, f="\t{:>.3f}"),
                manipulator_start_position_3=dict(
                    s="OBJPOS	6	13	0	1	0	0	1	2	114.346	1",
                    k=[0, 1, 2, 3, 5, 6, 7, 8], n=9, f="\t{:>.3f}"),
                manipulator_handover_distance_left=dict(s="GENAXS	7	42.816	38.484", k=[0, 1], n=2,
                                                        f="\t{:>.3f}"),
                manipulator_handover_distance_right=dict(s="GENAXS	7	42.816	38.484", k=[0, 1], n=3,
                                                         f="\t{:>.3f}"),
                cogging_generate_contact_band=dict(s="GENCTC    	0.14789", k=[0], n=1, f="\t{:>.5f}"),
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
        file_03c=dict(
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
        file_03=dict(
            file_path="Objects\\Object00002.KEY",
            parameters=dict(
                die_half_speed=dict(
                    s="MOVCTL       2       8       0    0.0000000000E+000    0.0000000000E+000"
                      "   -1.0000000000E+000    1.0549000000E+001    0.0000000000E+000",
                    k=[0, 1], n=7, f="\t{:>-21.10E}"),
                force_dwell_stopping_criteria_time=dict(
                    s="SPDLMT       2       7    0.0000000000E+000    1.8245000000E+002",
                    k=[0, 1], n=4, f="\t{:>-21.10E}"),
                cooling_top_die_reference_temperature=dict(
                    s="REFTMP       2    3.8525500000E+002", k=[0, 1], n=2, f="\t{:>-21.10E}")
            )
        ),
        file_03a=dict(
            file_path="Objects\\Object00003.KEY",
            parameters=dict(
                cooling_bottom_die_reference_temperature=dict(
                    s="REFTMP       3    3.2545900000E+002", k=[0, 1], n=2, f="\t{:>-21.10E}")
            )
        ),
        file_04=dict(
            file_path="Equipments\\Equipment00002.KEY",
            parameters=dict(
                die_half_speed=dict(
                    s="MOVCTL       2       8       0    0.0000000000E+000    0.0000000000E+000"
                      "   -1.0000000000E+000    1.0549000000E+001    0.0000000000E+000",
                    k=[0, 1], n=7, f="\t{:>-21.10E}"),
                force_dwell_stopping_criteria_time=dict(
                    s="SPDLMT       2       7    0.0000000000E+000    1.8245000000E+002",
                    k=[0, 1], n=4, f="\t{:>-21.10E}")
            )
        ),
        file_04a=dict(
            file_path="Equipments\\Equipment00004.KEY",
            parameters=dict(
                die_half_speed=dict(
                    s="MOVCTL       2       8       0    0.0000000000E+000    0.0000000000E+000"
                      "   -1.0000000000E+000    1.0549000000E+001    0.0000000000E+000",
                    k=[0, 1], n=7, f="\t{:>-21.10E}"),
                cogging_stopping_criteria_max_load=dict(
                    s="LMAX      0.0000000000E+000    0.0000000000E+000    6.3823000000E+007",
                    k=[0], n=3, f="\t{:>-21.10E}"),
                force_dwell_stopping_criteria_time=dict(
                    s="SPDLMT       2       7    0.0000000000E+000    1.8245000000E+002",
                    k=[0, 1], n=4, f="\t{:>-21.10E}")
            )
        ),
        file_04b=dict(
            file_path="Equipments\\Equipment00006.KEY",
            parameters=dict(
                force_dwell_die_force=dict(
                    s="MOVCTL       2       0       0    0.0000000000E+000    0.0000000000E+000   "
                      "-1.0000000000E+000    6.2840500000E+007",
                    k=[0, 1, 2, 3], n=7, f="\t{:>-21.10E}")
            )
        ),
        file_04d=dict(
            file_path="Equipments\\Equipment00008.KEY",
            parameters=dict(
                die_half_speed=dict(
                    s="MOVCTL       2       8       0    0.0000000000E+000    0.0000000000E+000"
                      "   -1.0000000000E+000    1.0549000000E+001    0.0000000000E+000",
                    k=[0, 1], n=7, f="\t{:>-21.10E}"),
                force_dwell_stopping_criteria_time=dict(
                    s="SPDLMT       2       7    0.0000000000E+000    1.8245000000E+002",
                    k=[0, 1], n=4, f="\t{:>-21.10E}")
            )
        ),
        file_06=dict(
            file_path="Objects\\Object00008.KEY",
            parameters=dict(
                manipulator_temperature=dict(
                    s="REFTMP       4    2.0541200000E+002", k=[0, 1], n=2, f="\t{:>-21.10E}")
            )
        ),
        file_08=dict(
            file_path="Objects\\Object00009.KEY",
            parameters=dict(
                manipulator_temperature=dict(
                    s="REFTMP       5    2.0541200000E+002", k=[0, 1], n=2, f="\t{:>-21.10E}")
            )
        ),
        file_09=dict(
            file_path="Objects\\Object00010.KEY",
            parameters=dict(
                manipulator_temperature=dict(
                    s="REFTMP       6    2.0541200000E+002", k=[0, 1], n=2, f="\t{:>-21.10E}")
            )
        ),
        file_10=dict(
            file_path="Objects\\Object00011.KEY",
            parameters=dict(
                manipulator_temperature=dict(
                    s="REFTMP       7    2.0541200000E+002", k=[0, 1], n=2, f="\t{:>-21.10E}")
            )
        ),
        file_11a=dict(
            file_path="Operations\\Task00002\\SimCtrl.KEY",
            parameters=dict(
                cogging_step_size_die_displacement=dict(
                    s="DSMAX     1.0842800000E+000", k=[0], n=1, f="\t{:>-21.10E}"),
                cogging_step_size_initial_time_step=dict(
                    s="DTMAX     1.8235000000E+000    1.8809278351E+000", k=[0], n=1, f="\t{:>-21.10E}"),
                cogging_step_size_time_increment_for_force_dwell_control=dict(
                    s="DTMAX     1.8235000000E+000    1.8809278351E+000", k=[0], n=2, f="\t{:>-21.10E}"),
                cogging_sub_stepping_control_max_strain_in_element=dict(
                    s="DEMAX     8.4108000000E-001", k=[0], n=1, f="\t{:>-21.10E}"),
                cogging_sub_stepping_control_max_polygon_length=dict(
                    s="DPLEN     2.4046000000E-001", k=[0], n=1, f="\t{:>-21.10E}"),
                cogging_environment_temperature=dict(
                    s="ENVTMP       0    1.7540000000E+001", k=[0, 1], n=2, f="\t{:>-21.10E}"),
                cogging_convection_coefficient=dict(
                    s="CNVCOF       0    2.8400000000E-002", k=[0, 1], n=2, f="\t{:>-21.10E}"),
                cogging_stopping_criteria_time=dict(
                    s="TMAX      8.4202100000E+002", k=[0], n=1, f="\t{:>-21.10E}"),
                cogging_stopping_criteria_min_velocity=dict(
                    s="VMIN      0.0000000000E+000    0.0000000000E+000    5.4021800000E+000",
                    k=[0], n=3, f="\t{:>-21.10E}"),
                cogging_stopping_criteria_max_load=dict(
                    s="LMAX      0.0000000000E+000    0.0000000000E+000    6.3823000000E+007",
                    k=[0], n=3, f="\t{:>-21.10E}"),
                simulation_number_3=dict(
                    s="CURSIM       3       3       0", k=[0, 1], n=1, f="\t{:8d}"),
                operation_number=dict(
                    s="CURSIM       3       3       0", k=[0], n=2, f="\t{:8d}")
            )
        ),
        file_11=dict(
            file_path="Operations\\Task00004\\SimCtrl.KEY",
            parameters=dict(
                cooling_2_step_size_time_increment_for_force_dwell_control=dict(
                    s="DTMAX     1.8235000000E+000    1.8809278351E+000", k=[0], n=2, f="\t{:>-21.10E}"),
                simulation_number_2=dict(
                    s="CURSIM       2       2       0", k=[0, 1], n=1, f="\t{:8d}"),
                operation_number=dict(
                    s="CURSIM       2       2       0", k=[0], n=2, f="\t{:8d}")
            )
        ),
        file_12=dict(
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
        file_13=dict(
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
        file_15=dict(
            file_path="Operations\\Task00002\\MeshSettings00001.KEY",
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
        ),
        file_16=dict(
            file_path="cogging_bite_01.KEY",
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
        file_path="cogging_bite_01.moproj",
        parameters=dict(
            cooling_time="      <Value>2.986 sec</Value>",
            cooling_environment_temperature="      <Value>18.652 C</Value>",
            cooling_step_control_initial_time_step="      <Value>1.8235</Value>",
            cooling_step_control_min_time_step="      <Value>2.04563</Value>",
            cooling_step_control_max_time_step="      <Value>9.8562</Value>",
            cooling_step_control_max_temperature="      <Value>4.21358</Value>",
            cooling_convection_coefficient="      <Value>0.026589 N/sec/mm/C</Value>",
            cogging_generate_contact_band="    <Keyword>GENCTC    	0.14789</Keyword>",
            cogging_environment_temperature="      <Value>17.54 C</Value>",
            force_dwell_convection_coefficient="      <Value>0.0284 N/sec/mm/C</Value>",
            force_dwell_step_size_time_increment="      <Value>0.1453 sec</Value>",
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
            operations_count = 3
            self.param['operation']['template_name'] = "cogging_bite_01"
            #
            self.eo = self.param['project']['execution_order']
            self.pvid = self.param['project']['process_version_id']
            self.row = self.param['table'][self.eo]

            previous_simulation_number = self.param['previous_operation']['simulation_number']
            self.param['operation']['simulation_number'] = previous_simulation_number + 1
            sub_operation_path = sub_operation_abs_path(self.param)

            LOGGER.info(f"{self.log_id} STARTED CoggingBiteOp at '{sub_operation_path}'")
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise
        try:

            self.pre_processing()
            run_solver(self.param)
            self.post_processing()

            self.param['operation']['simulation_number'] = previous_simulation_number + operations_count

            LOGGER.info(f"{self.log_id} FINISHED CoggingBiteOp at '{sub_operation_path}'")
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
            sub_operation_path = sub_operation_abs_path(self.param)
            _o = self.param['operation']
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise
        try:
            template_name = self.param['operation']['template_name']
            mst_file = template_name + '.MST'
            key_file = template_name + '.KEY'

            self._calculate_process_parameters()
            change_operations_names_in_mst_or_key_file(self.param, mst_file)
            change_operations_names_in_mst_or_key_file(self.param, key_file)
            automatic_modification_of_values_in_moproj_file(self.moproj_file, self.param)
            automatic_modification_of_parameters_in_files(self.files, self.param)
            modify_mesh_number(self.param, key_file)
            modify_global_time(self.param, key_file)
            force_dwell_stopping_criteria_time = self.param['operation']['force_dwell_stopping_criteria_time']
            modify_power_limit(self.param, self.row,
                               "Equipments\\Equipment00002.KEY",
                               "SPDLMT       2       7    0.0000000000E+000    1.8245000000E+002", 
                               0.5,
                               force_dwell_stopping_criteria_time)
            modify_power_limit(self.param, self.row,
                               "Equipments\\Equipment00004.KEY",
                               "SPDLMT       2       7    0.0000000000E+000    1.8245000000E+002", 
                               0.5,
                               force_dwell_stopping_criteria_time)
            modify_power_limit(self.param, self.row,
                               "Equipments\\Equipment00008.KEY",
                               "SPDLMT       2       7    0.0000000000E+000    1.8245000000E+002", 
                               0.5,
                               force_dwell_stopping_criteria_time)
            modify_power_limit(self.param, self.row,
                               "Objects\\Object00002.KEY",
                               "SPDLMT       2       7    0.0000000000E+000    1.8245000000E+002", 
                               0.5,
                               force_dwell_stopping_criteria_time)
            # ----------------------- INITIALIZE INGOT AXIS --------------------------
            initialize_user_nodal_variables_for_ingot_axis(self.param, rx=_o['rotation_angle_per_pass'], dx=_o['billet_offset_x'], dy=_o['billet_offset_y'], dz=_o['billet_offset_z'])
            # ---------------------------- TRIGGERS ----------------------------------
            modify_usrdef_triggers(self.param, relative_filepath="Operations\\Task00001\\SimCtrl.KEY")
            modify_user_variable_names(self.param, relative_filepath="Operations\\Task00001\\SimCtrl.KEY")

        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise RuntimeError(f"FAILED at '{sub_operation_path}'")

    def _calculate_process_parameters(self):
        try:
            sub_operation_path = sub_operation_abs_path(self.param)
        except Exception as _err:
            LOGGER.error(f"{self.log_id} {type(_err).__name__}: {_err}")
            raise
        try:
            operation_type = self.row['operation_type']
            start_step_number = self.param['previous_operation']['last_step_number']

            # USRDEF triggers
            self.param['operation']['usrdef_triggers'] |= {
                'start_step_number': start_step_number
            }

            press_mode = config.lib['press_mode'].loc[self.row['press_mode_id']]
            mesh = deform_mesh_settings(self.row, self.param)

            max_force = press_mode['max_force']
            speed = self.row['speed']
            min_speed = press_mode['min_dwell_speed']
            deformation_time_for_constant_max_speed = self.row['penetration'] / speed
            deformation_time_for_constant_min_speed = self.row['penetration'] / min_speed
            feed_direction = self.row['feed_direction_name']

            # Initial parameters
            assert self.row['time_between_bites'] > 0.0
            self.param['operation']['cooling_bottom_die_reference_temperature'] = 400.0
            self.param['operation']['cooling_top_die_reference_temperature'] = 400.0
            self.param['operation']['cooling_die_positioning_offset_z'] = 0.2 * self.row['initial_height']
            self.param['operation']['cooling_time'] = self.row['time_between_bites']
            self.param['operation']['target_volume'] = self.row['volume_final']
            self.param['operation']['positioning_dies_method'] = 2

            # Stepping control
            self.param['operation']['start_step_number'] = start_step_number
            cogging_die_displacement_step = cogging_step_size_die_displacement(self.param, self.row)
            self.param['operation']['cogging_step_size_die_displacement'] = cogging_die_displacement_step
            self.param['operation']['cogging_step_size_initial_time_step'] = \
                cogging_die_displacement_step / (0.5 * self.row['speed'])
            self.param['operation']['cogging_sub_stepping_control_max_polygon_length'] = 0.3
            self.param['operation']['cogging_sub_stepping_control_max_strain_in_element'] = 0.7
            cooling_min_time_step = max(1.0, self.param['operation']['cooling_time'])
            self.param['operation']['cooling_step_control_initial_time_step'] = cooling_min_time_step
            self.param['operation']['cooling_step_control_max_temperature'] = 5.0
            self.param['operation']['cooling_step_control_max_time_step'] = 5.0
            self.param['operation']['cooling_step_control_min_time_step'] = cooling_min_time_step
            force_dwell_min_step_number = 5
            force_dwell_min_step_size_time_increment = (
                    deformation_time_for_constant_max_speed / force_dwell_min_step_number)
            force_dwell_min_step_size_time_increment_2 = 0.3 * mesh['min_element_size'] / (speed / 2)
            force_dwell_step_size_time_increment = min(
                force_dwell_min_step_size_time_increment, force_dwell_min_step_size_time_increment_2)
            self.param['operation']['force_dwell_step_size_time_increment'] = force_dwell_step_size_time_increment
            self.param['operation']['cogging_step_size_time_increment_for_force_dwell_control'] = (
                force_dwell_step_size_time_increment)
            self.param['operation']['cooling_2_step_size_time_increment_for_force_dwell_control'] = (
                force_dwell_step_size_time_increment)
            self.param['operation']['force_dwell_sub_stepping_control_max_polygon_length'] = 0.3
            self.param['operation']['force_dwell_sub_stepping_control_max_strain_in_element'] = 0.7

            # Stopping and Movement criteria
            self.param['operation']['cogging_stopping_criteria_max_load'] = max_force
            self.param['operation']['force_dwell_die_force'] = max_force
            self.param['operation']['cogging_stopping_criteria_min_velocity'] = 0.5 * min_speed
            self.param['operation']['cogging_stopping_criteria_time'] = deformation_time_for_constant_min_speed
            self.param['operation']['die_half_speed'] = 0.5 * self.row['speed']
            self.param['operation']['force_dwell_stopping_criteria_min_velocity'] = 0.5 * min_speed
            self.param['operation']['force_dwell_stopping_criteria_time'] = \
                deformation_time_for_constant_min_speed

            # Boundary conditions
            _convection_coefficient = convection_coefficient(self.row, self.param)
            self.param['operation']['contact_heat_transfer'] = contact_heat_transfer(self.row)
            self.param['operation']['cooling_convection_coefficient'] = _convection_coefficient
            self.param['operation']['cogging_convection_coefficient'] = _convection_coefficient
            self.param['operation']['force_dwell_convection_coefficient'] = _convection_coefficient
            self.param['operation']['cooling_environment_temperature'] = environment_temperature(self.row)
            self.param['operation']['cogging_environment_temperature'] = environment_temperature(self.row)
            self.param['operation']['force_dwell_environment_temperature'] = environment_temperature(self.row)
            self.param['operation']['cogging_generate_contact_band'] = 0.01 * mesh['min_element_size']
            self.param['operation']['emissivity'] = emissivity(self.row)
            self.param['operation']['friction'] = friction(self.row)

            # Limiting strain rate
            if operation_type == 'Draw':
                self.param['operation']['cooling_average_strain_rate'] = self.row['speed'] / self.row['initial_height']
            else:
                self.param['operation']['cooling_average_strain_rate'] = self.row['speed'] / self.row['initial_length']
            self.param['operation']['cooling_limiting_strain_rate'] = \
                0.01 * self.param['operation']['cooling_average_strain_rate']

            # Manipulator parameters
            self.param['operation']['die_moving_direction'] = 1 if feed_direction == "==>" else -1
            # self.param['operation']['manipulator_handover_distance_left'] = 50.0
            # self.param['operation']['manipulator_handover_distance_right'] = 40.0
            self.param['operation']['manipulator_start_position'] = 30.0
            manipulator_start_position_plus_half_of_manipulator_length = \
                self.param['operation']['manipulator_start_position'] + self.param['operation']['manipulator_length']
            self.param['operation']['manipulator_start_position_2'] = \
                manipulator_start_position_plus_half_of_manipulator_length
            self.param['operation']['manipulator_start_position_3'] = \
                manipulator_start_position_plus_half_of_manipulator_length
            self.param['operation']['manipulator_max_spring_displacement'] = 2540
            self.param['operation']['manipulator_preload'] = 222400
            self.param['operation']['manipulator_stiffness'] = 175.0
            self.param['operation']['manipulator_temperature'] = 200.0

            # Remeshing parameters
            self.param['operation']['cogging_remeshing_absolute_size_ratio'] = mesh['element_size_ratio']
            self.param['operation']['cogging_remeshing_inverse_max_element_size'] = mesh['inverse_max_element_size']
            self.param['operation']['cogging_remeshing_interference_depth_relative'] = -0.4
            self.param['operation']['cogging_remeshing_maximum_step_increment'] = 0
            self.param['operation']['cogging_remeshing_maximum_stroke_increment'] = 0.0
            self.param['operation']['cogging_remeshing_maximum_time_increment'] = 0.0
            self.param['operation']['cogging_remeshing_number_of_surface_elements'] = mesh['number_of_surface_elements']
            self.param['operation']['cogging_remeshing_weighting_factor_boundary_curvature'] = 0.75
            self.param['operation']['cogging_remeshing_weighting_factor_strain'] = 0.25
            self.param['operation']['cogging_remeshing_weighting_factor_strain_rate'] = 0.0
            self.param['operation']['cogging_remeshing_weighting_factor_temperature'] = 0.25

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
            raise RuntimeError(f"FAILED at '{sub_operation_path}'")

    @property
    def log_id(self):
        return self.param['operation']['log_id'] + f" Duration {time.monotonic() - self.param['operation']['project_start_datetime']:.2f}s {traceback.format_exc()}"
