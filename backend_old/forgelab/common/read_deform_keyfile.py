from __future__ import annotations

import logging
import time

import smbclient
from math import pi
import numpy as np
import pandas as pd
from pyquaternion import Quaternion
# from contextlib import contextmanager
from sklearn.linear_model import LinearRegression
from shapely.geometry import Polygon
import trimesh
from trimesh.path import Path3D


LOGGER = logging.getLogger(__name__)


VARIABLES = {
    # Global Keywords
    'title': {
        'dependency': 'global', 
        'output_arg_index': None,
        'is_double_line_keyword': True,
        'is_multiple_line_keyword': False,
        'has_indices_column': False,
        'has_fixed_number_of_columns': True,
        'number_of_data_columns': 1,
        'argument_index_with_number_of_data_columns': None,
        'value_type': 'str',
        'var_type': 'none',
        'data_type': 'none',
        'variable': None,
        'variable_name': 'title',
        'title': 'Project Title',
        'deform_keyword': 'TITLE'},

    'simulation_number': {
        'dependency': 'global',
        'output_arg_index': 0,
        'is_double_line_keyword': False,
        'is_multiple_line_keyword': False,
        'has_indices_column': False,
        'has_fixed_number_of_columns': False,
        'number_of_data_columns': 0,
        'argument_index_with_number_of_data_columns': None,
        'value_type': 'int',
        'var_type': 'none',
        'data_type': 'none',
        'variable': None,
        'variable_name': 'simulation_number',
        'title': 'Simulation Number',
        'deform_keyword': 'CURSIM'},

    'operation_number': {
        'dependency': 'global',
        'output_arg_index': 1,
        'is_double_line_keyword': False,
        'is_multiple_line_keyword': False,
        'has_indices_column': False,
        'has_fixed_number_of_columns': False,
        'number_of_data_columns': 0,
        'argument_index_with_number_of_data_columns': None,
        'value_type': 'int',
        'var_type': 'none',
        'data_type': 'none',
        'variable': None,
        'variable_name': 'operation_number',
        'title': 'Operation number',
        'deform_keyword': 'CURSIM'},

    'simulation_mode': {
        'dependency': 'global',
        'output_arg_index': 0,
        'is_double_line_keyword': False,
        'is_multiple_line_keyword': False,
        'has_indices_column': False,
        'has_fixed_number_of_columns': False,
        'number_of_data_columns': 0,
        'argument_index_with_number_of_data_columns': None,
        'value_type': 'int',
        'var_type': 'none',
        'data_type': 'none',
        'variable': None,
        'variable_name': 'simulation_mode',
        'title': 'Simulation Mode',
        'deform_keyword': 'SMODE'},

    'simulation_type': {
        'dependency': 'global',
        'output_arg_index': 0,
        'is_double_line_keyword': False,
        'is_multiple_line_keyword': False,
        'has_indices_column': False,
        'has_fixed_number_of_columns': False,
        'number_of_data_columns': 0,
        'argument_index_with_number_of_data_columns': None,
        'value_type': 'int',
        'var_type': 'none',
        'data_type': 'none',
        'variable': None,
        'variable_name': 'simulation_type',
        'title': 'Simulation Type',
        'deform_keyword': 'STYPE'},

    'mesh_number': {
        'dependency': 'global',
        'output_arg_index': 0,
        'is_double_line_keyword': False,
        'is_multiple_line_keyword': False,
        'has_indices_column': False,
        'has_fixed_number_of_columns': False,
        'number_of_data_columns': 0,
        'argument_index_with_number_of_data_columns': None,
        'value_type': 'int',
        'var_type': 'none',
        'data_type': 'none',
        'variable': None,
        'variable_name': 'mesh_number',
        'title': 'Mesh Number',
        'deform_keyword': 'MESHNO'},

    'unit_system': {
        'dependency': 'global',
        'output_arg_index': 0,
        'is_double_line_keyword': False,
        'is_multiple_line_keyword': False,
        'has_indices_column': False,
        'has_fixed_number_of_columns': False,
        'number_of_data_columns': 0,
        'argument_index_with_number_of_data_columns': None,
        'value_type': 'int',
        'var_type': 'none',
        'data_type': 'none',
        'variable': None,
        'variable_name': 'unit_system',
        'title': 'System of Units',
        'deform_keyword': 'UNIT'},

    'time_global': {
        'dependency': 'global',
        'output_arg_index': 0,
        'is_double_line_keyword': False,
        'is_multiple_line_keyword': False,
        'has_indices_column': False,
        'has_fixed_number_of_columns': False,
        'number_of_data_columns': 0,
        'argument_index_with_number_of_data_columns': None,
        'value_type': 'int',
        'var_type': 'none',
        'data_type': 'none',
        'variable': None,
        'variable_name': 'time_global',
        'title': 'Global Time',
        'deform_keyword': 'TNOW'},

    'time_local': {
        'dependency': 'global',
        'output_arg_index': 1,
        'is_double_line_keyword': False,
        'is_multiple_line_keyword': False,
        'has_indices_column': False,
        'has_fixed_number_of_columns': False,
        'number_of_data_columns': 0,
        'argument_index_with_number_of_data_columns': None,
        'value_type': 'int',
        'var_type': 'none',
        'data_type': 'none',
        'variable': None,
        'variable_name': 'time_local',
        'title': 'Local Time',
        'deform_keyword': 'TNOW'},

    'is_local_time_used_for_function': {
        'dependency': 'global',
        'output_arg_index': 2,
        'is_double_line_keyword': False,
        'is_multiple_line_keyword': False,
        'has_indices_column': False,
        'has_fixed_number_of_columns': False,
        'number_of_data_columns': 0,
        'argument_index_with_number_of_data_columns': None,
        'value_type': 'int',
        'var_type': 'none',
        'data_type': 'none',
        'variable': None,
        'variable_name': 'is_local_time_used_for_function',
        'title': 'Is Local Time Used for Function',
        'deform_keyword': 'TNOW'},

    'time_local_second_stage': {
        'dependency': 'global',
        'output_arg_index': 3,
        'is_double_line_keyword': False,
        'is_multiple_line_keyword': False,
        'has_indices_column': False,
        'has_fixed_number_of_columns': False,
        'number_of_data_columns': 0,
        'argument_index_with_number_of_data_columns': None,
        'value_type': 'int',
        'var_type': 'none',
        'data_type': 'none',
        'variable': None,
        'variable_name': 'time_local_second_stage',
        'title': 'Local Time of Second Stage',
        'deform_keyword': 'TNOW'},

    'is_heat_transfer_on': {
        'dependency': 'global',
        'output_arg_index': 0,
        'is_double_line_keyword': False,
        'is_multiple_line_keyword': False,
        'has_indices_column': False,
        'has_fixed_number_of_columns': False,
        'number_of_data_columns': 0,
        'argument_index_with_number_of_data_columns': None,
        'value_type': 'int',
        'var_type': 'none',
        'data_type': 'none',
        'variable': None,
        'variable_name': 'is_heat_transfer_on',
        'title': 'Heat Transfer',
        'deform_keyword': 'TRANS'},

    'is_deformation_on': {
        'dependency': 'global',
        'output_arg_index': 1,
        'is_double_line_keyword': False,
        'is_multiple_line_keyword': False,
        'has_indices_column': False,
        'has_fixed_number_of_columns': False,
        'number_of_data_columns': 0,
        'argument_index_with_number_of_data_columns': None,
        'value_type': 'int',
        'var_type': 'none',
        'data_type': 'none',
        'variable': None,
        'variable_name': 'is_deformation_on',
        'title': 'Deformation',
        'deform_keyword': 'TRANS'},

    'is_phase_transformation_on': {
        'dependency': 'global',
        'output_arg_index': 2,
        'is_double_line_keyword': False,
        'is_multiple_line_keyword': False,
        'has_indices_column': False,
        'has_fixed_number_of_columns': False,
        'number_of_data_columns': 0,
        'argument_index_with_number_of_data_columns': None,
        'value_type': 'int',
        'var_type': 'none',
        'data_type': 'none',
        'variable': None,
        'variable_name': 'is_phase_transformation_on',
        'title': 'Phase Transformations',
        'deform_keyword': 'TRANS'},

    'is_diffusion_on': {
        'dependency': 'global',
        'output_arg_index': 3,
        'is_double_line_keyword': False,
        'is_multiple_line_keyword': False,
        'has_indices_column': False,
        'has_fixed_number_of_columns': False,
        'number_of_data_columns': 0,
        'argument_index_with_number_of_data_columns': None,
        'value_type': 'int',
        'var_type': 'none',
        'data_type': 'none',
        'variable': None,
        'variable_name': 'is_diffusion_on',
        'title': 'Diffusion',
        'deform_keyword': 'TRANS'},

    'is_grain_evolution_on': {
        'dependency': 'global',
        'output_arg_index': 4,
        'is_double_line_keyword': False,
        'is_multiple_line_keyword': False,
        'has_indices_column': False,
        'has_fixed_number_of_columns': False,
        'number_of_data_columns': 0,
        'argument_index_with_number_of_data_columns': None,
        'value_type': 'int',
        'var_type': 'none',
        'data_type': 'none',
        'variable': None,
        'variable_name': 'is_grain_evolution_on',
        'title': 'Grain Evolution',
        'deform_keyword': 'TRANS'},

    'heating_method': {
        'dependency': 'global',
        'output_arg_index': 0,
        'is_double_line_keyword': False,
        'is_multiple_line_keyword': False,
        'has_indices_column': False,
        'has_fixed_number_of_columns': False,
        'number_of_data_columns': 0,
        'argument_index_with_number_of_data_columns': None,
        'value_type': 'int',
        'var_type': 'none',
        'data_type': 'none',
        'variable': None,
        'variable_name': 'heating_method',
        'title': 'Heating Method',
        'deform_keyword': 'HTMTHD'},

    'starting_step_number': {
        'dependency': 'global',
        'output_arg_index': 0,
        'is_double_line_keyword': False,
        'is_multiple_line_keyword': False,
        'has_indices_column': False,
        'has_fixed_number_of_columns': False,
        'number_of_data_columns': 0,
        'argument_index_with_number_of_data_columns': None,
        'value_type': 'int',
        'var_type': 'none',
        'data_type': 'none',
        'variable': None,
        'variable_name': 'starting_step_number',
        'title': 'Starting Step Number',
        'deform_keyword': 'NSTART'},

    'stopping_criteria_die_distance_reference_object_1': {
        'dependency': 'global',
        'output_arg_index': 0,
        'is_double_line_keyword': False,
        'is_multiple_line_keyword': False,
        'has_indices_column': False,
        'has_fixed_number_of_columns': False,
        'number_of_data_columns': 0,
        'argument_index_with_number_of_data_columns': None,
        'value_type': 'int',
        'var_type': 'none',
        'data_type': 'none',
        'variable': None,
        'variable_name': 'stopping_criteria_die_distance_reference_object_1',
        'title': 'Reference Object 1 for Die Distance Stopping Criteria',
        'deform_keyword': 'MDSOBJ'},

    'stopping_criteria_die_distance_reference_object_2': {
        'dependency': 'global',
        'output_arg_index': 1,
        'is_double_line_keyword': False,
        'is_multiple_line_keyword': False,
        'has_indices_column': False,
        'has_fixed_number_of_columns': False,
        'number_of_data_columns': 0,
        'argument_index_with_number_of_data_columns': None,
        'value_type': 'int',
        'var_type': 'none',
        'data_type': 'none',
        'variable': None,
        'variable_name': 'stopping_criteria_die_distance_reference_object_2',
        'title': 'Reference Object 2 for Die Distance Stopping Criteria',
        'deform_keyword': 'MDSOBJ'},

    'stopping_criteria_die_distance_measurement_method': {
        'dependency': 'global',
        'output_arg_index': 2,
        'is_double_line_keyword': False,
        'is_multiple_line_keyword': False,
        'has_indices_column': False,
        'has_fixed_number_of_columns': False,
        'number_of_data_columns': 0,
        'argument_index_with_number_of_data_columns': None,
        'value_type': 'int',
        'var_type': 'none',
        'data_type': 'none',
        'variable': None,
        'variable_name': 'stopping_criteria_die_distance_measurement_method',
        'title': 'Measurement Method for Die Distance Stopping Criteria',
        'deform_keyword': 'MDSOBJ'},

    'stopping_criteria_die_distance_value': {
        'dependency': 'global',
        'output_arg_index': 3,
        'is_double_line_keyword': False,
        'is_multiple_line_keyword': False,
        'has_indices_column': False,
        'has_fixed_number_of_columns': False,
        'number_of_data_columns': 0,
        'argument_index_with_number_of_data_columns': None,
        'value_type': 'int',
        'var_type': 'none',
        'data_type': 'none',
        'variable': None,
        'variable_name': 'stopping_criteria_die_distance_value',
        'title': 'Distance Value for Die Distance Stopping Criteria',
        'deform_keyword': 'MDSOBJ'},

    'environment_temperature_function_type': {
        'dependency': 'global',
        'output_arg_index': 0,
        'is_double_line_keyword': False,
        'is_multiple_line_keyword': False,
        'has_indices_column': False,
        'has_fixed_number_of_columns': False,
        'number_of_data_columns': 0,
        'argument_index_with_number_of_data_columns': None,
        'value_type': 'int',
        'var_type': 'none',
        'data_type': 'none',
        'variable': None,
        'variable_name': 'environment_temperature_function_type',
        'title': 'Function Type for Environment Temperature',
        'deform_keyword': 'ENVTMP'},

    'environment_temperature_value': {
        'dependency': 'global',
        'output_arg_index': 1,
        'is_double_line_keyword': False,
        'is_multiple_line_keyword': False,
        'has_indices_column': False,
        'has_fixed_number_of_columns': False,
        'number_of_data_columns': 0,
        'argument_index_with_number_of_data_columns': None,
        'value_type': 'int',
        'var_type': 'none',
        'data_type': 'none',
        'variable': None,
        'variable_name': 'environment_temperature_value',
        'title': 'Environment Temperature',
        'deform_keyword': 'ENVTMP'},

    'operation_name': {
        'dependency': 'global',
        'output_arg_index': None,
        'is_double_line_keyword': True,
        'is_multiple_line_keyword': False,
        'has_indices_column': False,
        'has_fixed_number_of_columns': False,
        'number_of_data_columns': 0,
        'argument_index_with_number_of_data_columns': None,
        'value_type': 'str',
        'var_type': 'none',
        'data_type': 'none',
        'variable': None,
        'variable_name': 'operation_name',
        'title': 'Operation Name',
        'deform_keyword': 'OPRNAM'},

    'simulation_name': {
        'dependency': 'global', 
        'output_arg_index': None,
        'is_double_line_keyword': True,
        'is_multiple_line_keyword': False,
        'has_indices_column': False,
        'has_fixed_number_of_columns': False,
        'number_of_data_columns': 0,
        'argument_index_with_number_of_data_columns': None,
        'value_type': 'str',
        'var_type': 'none',
        'data_type': 'scalar',
        'variable': None,
        'variable_name': 'simulation_name',
        'title': 'Simulation Name',
        'deform_keyword': 'SIMNAM'},

    # Double line Keywords with Material dependent values
    'material_name': {
        'dependency': 'materials', 
        'output_arg_index': None,
        'is_double_line_keyword': True,
        'is_multiple_line_keyword': False,
        'has_indices_column': False,
        'has_fixed_number_of_columns': True,
        'number_of_data_columns': 1,
        'argument_index_with_number_of_data_columns': None,
        'value_type': 'str',
        'var_type': 'none',
        'data_type': 'scalar',
        'variable': None,
        'variable_name': 'material_name',
        'title': 'Material Name',
        'deform_keyword': 'MTNAME'},

    # Double line Keywords with Object dependent values
    'object_name': {
        'dependency': 'objects',
        'output_arg_index': None,
        'is_double_line_keyword': True,
        'is_multiple_line_keyword': False,
        'has_indices_column': False,
        'has_fixed_number_of_columns': True,
        'number_of_data_columns': 1,
        'argument_index_with_number_of_data_columns': None,
        'value_type': 'str',
        'var_type': 'none',
        'data_type': 'scalar',
        'variable': None,
        'variable_name': 'object_name',
        'title': 'Object Name',
        'deform_keyword': 'OBJNAM'},

    'press_name': {
        'dependency': 'objects',
        'output_arg_index': None,
        'is_double_line_keyword': True,
        'is_multiple_line_keyword': False,
        'has_indices_column': False,
        'has_fixed_number_of_columns': True,
        'number_of_data_columns': 1,
        'argument_index_with_number_of_data_columns': None,
        'value_type': 'str',
        'var_type': 'none',
        'data_type': 'scalar',
        'variable': None,
        'variable_name': 'press_name',
        'title': 'Press Name',
        'deform_keyword': 'PRSNAM'},

    # Multiple line Keywords with multiples Names
    'user_nodal_name': {
        'dependency': 'objects',
        'output_arg_index': None,
        'is_double_line_keyword': False,
        'is_multiple_line_keyword': True,
        'has_indices_column': False,
        'has_fixed_number_of_columns': True,
        'number_of_data_columns': 1,
        'argument_index_with_number_of_data_columns': None,
        'value_type': 'str',
        'var_type': 'none',
        'data_type': 'scalar',
        'variable': None,
        'variable_name': 'user_nodal_name',
        'title': 'User Nodal Variables Names',
        'deform_keyword': 'UNNAME'},

    'user_element_name': {
        'dependency': 'objects',
        'output_arg_index': None,
        'is_double_line_keyword': False,
        'is_multiple_line_keyword': True,
        'has_indices_column': False,
        'has_fixed_number_of_columns': True,
        'number_of_data_columns': 1,
        'argument_index_with_number_of_data_columns': None,
        'value_type': 'str',
        'var_type': 'none',
        'data_type': 'scalar',
        'variable': None,
        'variable_name': 'user_element_name',
        'title': 'User Element Variables Names',
        'deform_keyword': 'UENAME'},

    # Multiple line Keywords with Object dependent values with Indices column
    'nodes': {
        'dependency': 'objects', 
        'output_arg_index': None,
        'is_double_line_keyword': False,
        'is_multiple_line_keyword': True,
        'has_indices_column': True,
        'has_fixed_number_of_columns': True,
        'number_of_data_columns': 3,
        'argument_index_with_number_of_data_columns': None,
        'value_type': 'float',
        'var_type': 'nodal',
        'data_type': 'vector',
        'variable': None,
        'variable_name': 'nodes',
        'title': 'Nodes',
        'deform_keyword': 'RZ'},

    'elements': {
        'dependency': 'objects', 
        'output_arg_index': None,
        'is_double_line_keyword': False,
        'is_multiple_line_keyword': True,
        'has_indices_column': True,
        'has_fixed_number_of_columns': False,
        'number_of_data_columns': None,
        'argument_index_with_number_of_data_columns': 2,
        'value_type': 'int',
        'var_type': 'element',
        'data_type': 'none',
        'variable': None,
        'variable_name': 'elements',
        'title': 'Elements',
        'deform_keyword': 'ELMCON'},

    'nodal_scalar_temperature': {
        'dependency': 'objects', 
        'output_arg_index': None,
        'is_double_line_keyword': False,
        'is_multiple_line_keyword': True,
        'has_indices_column': True,
        'has_fixed_number_of_columns': True,
        'number_of_data_columns': 1,
        'argument_index_with_number_of_data_columns': None,
        'value_type': 'float',
        'var_type': 'nodal',
        'data_type': 'scalar',
        'variable': None,
        'variable_name': 'nodal_scalar_temperature',
        'title': 'Temperature',
        'deform_keyword': 'NDTMP'},

    'element_tensor6_strain': {
        'dependency': 'objects', 
        'output_arg_index': None,
        'is_double_line_keyword': False,
        'is_multiple_line_keyword': True,
        'has_indices_column': True,
        'has_fixed_number_of_columns': False,
        'number_of_data_columns': None,
        'argument_index_with_number_of_data_columns': 2,
        'value_type': 'float',
        'var_type': 'element',
        'data_type': 'tensor6',
        'variable': None,
        'variable_name': 'element_tensor6_strain',
        'title': 'Strain Tensor',
        'deform_keyword': 'STNCMP'},

    'element_tensor6_stress': {
        'dependency': 'objects', 
        'output_arg_index': None,
        'is_double_line_keyword': False,
        'is_multiple_line_keyword': True,
        'has_indices_column': True,
        'has_fixed_number_of_columns': True,
        'number_of_data_columns': 6,
        'argument_index_with_number_of_data_columns': None,
        'value_type': 'float',
        'var_type': 'element',
        'data_type': 'tensor6',
        'variable': None,
        'variable_name': 'element_tensor6_stress',
        'title': 'Stress Tensor',
        'deform_keyword': 'STRESS'},

    'user_element': {
        'dependency': 'objects', 
        'output_arg_index': None,
        'is_double_line_keyword': False,
        'is_multiple_line_keyword': True,
        'has_indices_column': True,
        'has_fixed_number_of_columns': False,
        'number_of_data_columns': None,
        'argument_index_with_number_of_data_columns': 3,
        'value_type': 'float',
        'var_type': 'element',
        'data_type': 'scalar',
        'variable': None,
        'variable_name': 'user_element',
        'title': 'User Element Variables',
        'deform_keyword': 'USRELM',
        'column_names': (
            'strain_bite',
            'strain_operation',
            'strain_heat')
    },

    'user_nodal': {
        'dependency': 'objects', 
        'output_arg_index': None,
        'is_double_line_keyword': False,
        'is_multiple_line_keyword': True,
        'has_indices_column': True,
        'has_fixed_number_of_columns': False,
        'number_of_data_columns': None,
        'argument_index_with_number_of_data_columns': 3,
        'value_type': 'float',
        'var_type': 'nodal',
        'data_type': 'scalar',
        'variable': None,
        'variable_name': 'user_nodal',
        'title': 'User Nodal Variables',
        'deform_keyword': 'USRNOD',
        'column_names': (
            'max_temperature_bite',
            'max_temperature_operation',
            'temperature_change_bite',
            'temperature_change_operation',
            'ingot_axis_x',
            'ingot_axis_y',
            'ingot_axis_z')
    },

    'def_bcc_nodes': {
        'dependency': 'objects', 
        'output_arg_index': None,
        'is_double_line_keyword': False,
        'is_multiple_line_keyword': True,
        'has_indices_column': False,
        'has_fixed_number_of_columns': True,
        'number_of_data_columns': 3,
        'argument_index_with_number_of_data_columns': None,
        'value_type': 'int',
        'var_type': 'nodal',
        'data_type': 'none',
        'variable': None,
        'variable_name': 'def_bcc_nodes',
        'title': 'Deformation Boundary Conditions Nodes',
        'deform_keyword': 'BCCDEF'},

    'heat_bcc_faces': {
        'dependency': 'objects', 
        'output_arg_index': None,
        'is_double_line_keyword': False,
        'is_multiple_line_keyword': True,
        'has_indices_column': True,
        'has_fixed_number_of_columns': True,
        'number_of_data_columns': 5,
        'argument_index_with_number_of_data_columns': None,
        'value_type': 'int',
        'var_type': 'none',
        'data_type': 'none',
        'variable': None,
        'variable_name': 'heat_bcc_faces',
        'title': 'Heat Boundary Conditions Faces',
        'deform_keyword': 'ECCTMP'},

    'nodal_vector_speed': {
        'dependency': 'objects', 
        'output_arg_index': None,
        'is_double_line_keyword': False,
        'is_multiple_line_keyword': True,
        'has_indices_column': True,
        'has_fixed_number_of_columns': True,
        'number_of_data_columns': 3,
        'argument_index_with_number_of_data_columns': None,
        'value_type': 'float',
        'var_type': 'nodal',
        'data_type': 'vector',
        'variable': None,
        'variable_name': 'nodal_vector_speed',
        'title': 'Nodal Speed Vector',
        'deform_keyword': 'URZ'},

    'strain_effective': {
        'dependency': 'objects', 
        'output_arg_index': None,
        'is_double_line_keyword': False,
        'is_multiple_line_keyword': True,
        'has_indices_column': True,
        'has_fixed_number_of_columns': True,
        'number_of_data_columns': 1,
        'argument_index_with_number_of_data_columns': None,
        'value_type': 'float',
        'var_type': 'element',
        'data_type': 'scalar',
        'variable': None,
        'variable_name': 'strain_effective',
        'title': 'Strain - Effective',
        'deform_keyword': 'STRAIN'},

    'element_scalar_damage': {
        'dependency': 'objects', 
        'output_arg_index': None,
        'is_double_line_keyword': False,
        'is_multiple_line_keyword': True,
        'has_indices_column': True,
        'has_fixed_number_of_columns': True,
        'number_of_data_columns': 1,
        'argument_index_with_number_of_data_columns': None,
        'value_type': 'float',
        'var_type': 'element',
        'data_type': 'scalar',
        'variable': None,
        'variable_name': 'element_scalar_damage',
        'title': 'Damage',
        'deform_keyword': 'DAMAGE'},

    # Multiple line Keywords with Object values
    'flownet': {
        'dependency': 'objects', 
        'output_arg_index': None,
        'is_double_line_keyword': False,
        'is_multiple_line_keyword': True,
        'has_indices_column': True,
        'has_fixed_number_of_columns': False,
        'number_of_data_columns': None,
        'argument_index_with_number_of_data_columns': None,
        'value_type': 'flownet',
        'var_type': 'none',
        'data_type': 'none',
        'vertices': None,
        'triangles': None,
        'variable_name': 'flownet',
        'title': 'Flow Net',
        'deform_keyword': 'FLWNET'},

    # Stress Tensor Variables
    'stress_mean': {
        'var_type': 'element',
        'data_type': 'scalar',
        'variable_name': 'stress_mean',
        'title': 'Stress - Mean',
        'deform_keyword': None,
        'args': None,
    },

    'stress_max_principal_scalar': {
        'var_type': 'element',
        'data_type': 'scalar',
        'variable_name': 'stress_max_principal_scalar',
        'title': 'Stress - Max Principal',
        'deform_keyword': None,
        'args': None,
    },

    'stress_inter_principal_scalar': {
        'var_type': 'element',
        'data_type': 'scalar',
        'variable_name': 'stress_inter_principal_scalar',
        'title': 'Stress - Inter Principal',
        'deform_keyword': None,
        'args': None,
    },

    'stress_min_principal_scalar': {
        'var_type': 'element',
        'data_type': 'scalar',
        'variable_name': 'stress_min_principal_scalar',
        'title': 'Stress - Min Principal',
        'deform_keyword': None,
        'args': None,
    },

    'stress_max_principal_vectors': {
        'var_type': 'element',
        'data_type': 'vector',
        'variable_name': 'stress_max_principal_vectors',
        'title': 'Stress - Max Principal',
        'deform_keyword': None,
        'args': None,
    },

    'stress_min_principal_vectors': {
        'var_type': 'element',
        'data_type': 'vector',
        'variable_name': 'stress_min_principal_vectors',
        'title': 'Stress - Min Principal',
        'deform_keyword': None,
        'args': None,
    },

    'stress_x_vectors': {
        'var_type': 'element',
        'data_type': 'vector',
        'variable_name': 'stress_x_vectors',
        'title': 'Stress - X',
        'deform_keyword': None,
        'args': None,
    },

    'stress_y_vectors': {
        'var_type': 'element',
        'data_type': 'vector',
        'variable_name': 'stress_y_vectors',
        'title': 'Stress - Y',
        'deform_keyword': None,
        'args': None,
    },

    'stress_z_vectors': {
        'var_type': 'element',
        'data_type': 'vector',
        'variable_name': 'stress_z_vectors',
        'title': 'Stress - Z',
        'deform_keyword': None,
        'args': None,
    },

    # Strain Tensor Variables
    'surface': {
        'var_type': 'none',
        'data_type': 'scalar',
        'variable_name': 'surface',
        'title': 'Surface only',
        'deform_keyword': None,
        'args': None,
        'variable': None
    },

    'strain_total_von_mises': {
        'var_type': 'element',
        'data_type': 'scalar',
        'variable_name': 'strain_total_von_mises',
        'title': 'Strain Total - Von Mises',
        'deform_keyword': None,
        'args': None,
    },
    'strain_total_mean_scalar': {
        'var_type': 'element',
        'data_type': 'scalar',
        'variable_name': 'strain_total_mean_scalar',
        'title': 'Strain Total - Mean',
        'deform_keyword': None,
        'args': None,
    },
    'strain_total_max_principal_scalar': {
        'var_type': 'element',
        'data_type': 'scalar',
        'variable_name': 'strain_total_max_principal_scalar',
        'title': 'Strain Total - Max Principal',
        'deform_keyword': None,
        'args': None,
    },
    'strain_total_inter_principal_scalar': {
        'var_type': 'element',
        'data_type': 'scalar',
        'variable_name': 'strain_total_inter_principal_scalar',
        'title': 'Strain Total - Inter Principal',
        'deform_keyword': None,
        'args': None,
    },
    'strain_total_min_principal_scalar': {
        'var_type': 'element',
        'data_type': 'scalar',
        'variable_name': 'strain_total_min_principal_scalar',
        'title': 'Strain Total - Min Principal',
        'deform_keyword': None,
        'args': None,
    },
    'strain_total_max_principal_vectors': {
        'var_type': 'element',
        'data_type': 'vector',
        'variable_name': 'strain_total_max_principal_vectors',
        'title': 'Strain Total - Max Principal',
        'deform_keyword': None,
        'args': None,
    },
    'strain_total_min_principal_vectors': {
        'var_type': 'element',
        'data_type': 'vector',
        'variable_name': 'strain_total_min_principal_vectors',
        'title': 'Strain Total - Min Principal',
        'deform_keyword': None,
        'args': None,
    },
    'strain_total_x_vectors': {
        'var_type': 'element',
        'data_type': 'vector',
        'variable_name': 'strain_total_x_vectors',
        'title': 'Strain Total - X',
        'deform_keyword': None,
        'args': None,
    },
    'strain_total_y_vectors': {
        'var_type': 'element',
        'data_type': 'vector',
        'variable_name': 'strain_total_y_vectors',
        'title': 'Strain Total - Y',
        'deform_keyword': None,
        'args': None,
    },
    'strain_total_z_vectors': {
        'var_type': 'element',
        'data_type': 'vector',
        'variable_name': 'strain_total_z_vectors',
        'title': 'Strain Total - Z',
        'deform_keyword': None,
        'args': None,
    },
    'strain_total_x_scalar': {
        'var_type': 'element',
        'data_type': 'scalar',
        'variable_name': 'strain_total_x_scalar',
        'title': 'Strain Total - X',
        'deform_keyword': None,
        'args': None,
    },
    'strain_total_y_scalar': {
        'var_type': 'element',
        'data_type': 'scalar',
        'variable_name': 'strain_total_y_scalar',
        'title': 'Strain Total - Y',
        'deform_keyword': None,
        'args': None,
    },
    'strain_total_z_scalar': {
        'var_type': 'element',
        'data_type': 'scalar',
        'variable_name': 'strain_total_z_scalar',
        'title': 'Strain Total - Z',
        'deform_keyword': None,
        'args': None,
    },

    # User Nodal Variables
    'max_temperature_bite': {
        'var_type': 'nodal',
        'data_type': 'scalar',
        'variable_name': 'max_temperature_bite',
        'title': 'Max Temperature per Bite',
        'deform_keyword': None,
        'args': None,
    },
    'max_temperature_operation': {
        'var_type': 'nodal',
        'data_type': 'scalar',
        'variable_name': 'max_temperature_operation',
        'title': 'Max Temperature per Operation',
        'deform_keyword': None,
        'args': None,
    },
    'temperature_change_bite': {
        'var_type': 'nodal',
        'data_type': 'scalar',
        'variable_name': 'temperature_change_bite',
        'title': 'Temperature Change per Bite',
        'deform_keyword': None,
        'args': None,
    },
    'temperature_change_operation': {
        'var_type': 'nodal',
        'data_type': 'scalar',
        'variable_name': 'temperature_change_operation',
        'title': 'Temperature Change per Operation',
        'deform_keyword': None,
        'args': None,
    },
    'ingot_axis_x': {
        'var_type': 'nodal',
        'data_type': 'scalar',
        'variable_name': 'ingot_axis_x',
        'title': 'Ingot Initial Axis X-gradient',
        'deform_keyword': None,
        'args': None,
    },
    'ingot_axis_y': {
        'var_type': 'nodal',
        'data_type': 'scalar',
        'variable_name': 'ingot_axis_y',
        'title': 'Ingot Initial Axis Y-gradient',
        'deform_keyword': None,
        'args': None,
    },
    'ingot_axis_z': {
        'var_type': 'nodal',
        'data_type': 'scalar',
        'variable_name': 'ingot_axis_z',
        'title': 'Ingot Initial Axis Z-gradient',
        'deform_keyword': None,
        'args': None,
    },

    # User Element Variables
    'strain_bite': {
        'var_type': 'element',
        'data_type': 'scalar',
        'variable_name': 'strain_bite',
        'title': 'Effective Strain per Bite',
        'deform_keyword': None,
        'args': None,
    },
    'strain_operation': {
        'var_type': 'element',
        'data_type': 'scalar',
        'variable_name': 'strain_operation',
        'title': 'Effective Strain per Operation',
        'deform_keyword': None,
        'args': None,
    },
    'strain_heat': {
        'var_type': 'element',
        'data_type': 'scalar',
        'variable_name': 'strain_heat',
        'title': 'Effective Strain per Heat',
        'deform_keyword': None,
        'args': None,
    },
}


DEFORM_KEYWORDS = tuple(value['deform_keyword'] for value in VARIABLES.values()
                        if 'deform_keyword' in value.keys() and value['deform_keyword'] is not None)


VARIABLES_VS_DEFORM_KEYWORD = {keyword: [value for key, value in VARIABLES.items()
                                         if 'deform_keyword' in value and value['deform_keyword'] == keyword]
                               for keyword in set(DEFORM_KEYWORDS)}


TEMPLATE_DICT = {value['deform_keyword']: value for value in VARIABLES.values() if 'deform_keyword' in value.keys()}


def find_pattern_in_list(list_of_strings: list[str], pattern: str, pattern_indices: list, starting_line: int) -> list:
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
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def _read_single_line(args: list, output_arg_index: int) -> str:
    try:
        assert isinstance(output_arg_index, int), f"output_arg_index is not an integer: {output_arg_index}"
        assert len(args) > output_arg_index, f"output_arg_index is out of range: {output_arg_index}"
        return args[output_arg_index]
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise

def _read_double_line(lines: list[str], index: list) -> str:
    try:
        index[0] += 1  # Move index to the next line after Keyword line
        return lines[index[0]]
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def _read_object_empty_nodal(args: list, keyword_dict: dict, node_count) -> np.ndarray:
    try:
        # row_count = 0

        _k = keyword_dict['deform_keyword']

        if _k == 'URZ':
            if len(args) == 3:
                output = np.full(shape=(node_count, 3), fill_value=args[2], dtype=np.float64)
            elif len(args) == 5:
                default_xyz = np.array(args[2:])
                output = np.tile(default_xyz, reps=(node_count, 1))
            else:
                raise KeyError(f"URZ with row_count=0 and len(args)={len(args)}")

        elif _k == 'NDTMP':
            output = np.full(shape=(node_count, 1), fill_value=args[2], dtype=np.float64)

        elif _k == 'USRNOD':
            variables_count = 2
            default_value = 0.0
            output = np.full(shape=(node_count, variables_count), fill_value=default_value, dtype=np.float64)

        else:
            raise KeyError(f"Unknown deform_keyword: {keyword_dict['deform_keyword']}")
        return output
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def _read_object_empty_elem(args: list, keyword_dict: dict, elem_count: int) -> np.ndarray:
    try:
        # row_count = 0

        _k = keyword_dict['deform_keyword']

        if _k == 'STRAIN':
            output = np.full(shape=(elem_count, 1), fill_value=args[2], dtype=np.float64)

        elif _k == 'STNCMP':
            comp_count = args[2]
            output = np.full(shape=(elem_count, comp_count), fill_value=args[3], dtype=np.float64)

        elif _k == 'DAMAGE':
            output = np.full(shape=(elem_count, 1), fill_value=args[2], dtype=np.float64)

        elif _k == 'STRESS':
            output = np.full(shape=(elem_count, 6), fill_value=args[2], dtype=np.float64)

        elif _k == 'USRELM':
            variables_count = args[3]
            output = np.full(shape=(elem_count, variables_count), fill_value=args[2], dtype=np.float64)

        else:
            raise KeyError(f"Unknown deform_keyword: {keyword_dict['deform_keyword']}")
        return output
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def _read_object_multiple_name_lines(lines: list[str], index: list, args: list) -> list[str]:
    try:
        index[0] += 1  # Move index to the next line after Keyword line
        lines_count: int = args[1]

        start_index = index[0]  # Starting index of array
        end_index = start_index + lines_count  # Ending index of array
        index[0] = end_index - 1  # Move index to the last line of array

        output = lines[start_index:end_index]
        return output
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def _read_object_ecctmp(lines: list[str], index: list, args: list) -> np.ndarray:
    try:
        index[0] += 1  # Move index to the next line after Keyword line
        lines_count: int = args[1]

        start_index = index[0]  # Starting index of array
        end_index = start_index + lines_count  # Ending index of array
        index[0] = end_index - 1  # Move index to the last line of array

        output = np.loadtxt(lines[start_index:end_index], dtype='i')
        return output
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def _read_object_elmcon(lines: list[str], index: list, args: list) -> np.ndarray:
    try:
        index[0] += 1  # Move index to the next line after Keyword line
        lines_count: int = args[1]

        start_index = index[0]  # Starting index of array
        end_index = start_index + lines_count  # Ending index of array
        index[0] = end_index - 1  # Move index to the last line of array

        output = np.add(np.loadtxt(lines[start_index:end_index], dtype='i')[:, 1:],
                        np.array(-1))  # Renumerate node indices from 0
        return output
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def _read_object_bccdef(lines: list[str], index: list, args: list) -> np.ndarray:
    try:
        index[0] += 1  # Move index to the next line after Keyword line
        lines_count: int = args[1]

        start_index = index[0]  # Starting index of array
        end_index = start_index + lines_count  # Ending index of array
        index[0] = end_index - 1  # Move index to the last line of array

        output = np.loadtxt(lines[start_index:end_index], dtype='i', ndmin=2)
        output[:, 0] = np.add(output[:, 0], np.array(-1))  # Renumerate node indices from 0
        return output
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def read_object_keyword(keyfile_lines: list[str], keyword_line_index: list, args: list, keyword_dict: dict, expected_count_of_data_lines: int) -> np.ndarray:
    try:
        has_indices_column: bool = keyword_dict['has_indices_column']
        has_fixed_number_of_columns: bool = keyword_dict['has_fixed_number_of_columns']
        number_of_data_columns: int | None = keyword_dict['number_of_data_columns']
        argument_index_with_number_of_data_columns: int | None = \
            keyword_dict['argument_index_with_number_of_data_columns']

        keyword_line_index[0] += 1  # Move index to the next line after Keyword line
        actual_data_rows_count: int = args[1]

        if has_fixed_number_of_columns:
            data_columns_count = number_of_data_columns
        else:
            data_columns_count = args[argument_index_with_number_of_data_columns]

        total_columns_count = data_columns_count
        if has_indices_column:
            total_columns_count += 1

        # ----------------------------------------- TEST ----------------------------------------------------
        # Test if columns of single data row is separated between text rows of 'lines' list
        lines_per_row = 0
        values_count = 0
        values = []
        for l_index in range(keyword_line_index[0], len(keyfile_lines), 1):
            _v = keyfile_lines[l_index].strip().split()
            values.extend(_v)
            values_count += len(_v)
            lines_per_row += 1
            if values_count == total_columns_count:
                break
            assert values_count < total_columns_count, (f"It is expected to find exactly {total_columns_count} columns "
                                                        f"in first {lines_per_row} rows of KEY-file following KEYWORD "
                                                        f"row '{keyfile_lines[keyword_line_index[0] - 1]}'. Instead {values_count} found. "
                                                        f"Found values are: {' '.join(values[:7])} "
                                                        f"(first 7 columns are shown).")
        assert lines_per_row >= 1, (f"Failed to find any data rows in KEY-file following KEYWORD row "
                                    f"'{keyfile_lines[keyword_line_index[0] - 1]}' at line index {keyword_line_index[0] - 1}.")
        # ----------------------------------------------------------------------------------------------------

        # Correct number of data rows for case, when values of single row is separated between few lines of KEY-file
        actual_data_rows_count *= lines_per_row

        format_converter = {
            'str': 'U256',  # 'U' is for UNICODE string with 256 characters
            'float': 'f8',  # 'f8' is for float64
            'int': 'i'}  # 'i' is for signed int32
        dtype = format_converter[keyword_dict['value_type']]

        start_index = keyword_line_index[0]  # Starting index of array
        end_index = start_index + actual_data_rows_count  # Ending index of array
        keyword_line_index[0] = end_index - 1  # Move index to the last line of array

        if lines_per_row == 1:
            new_lines = keyfile_lines[start_index:end_index]
        else:  # lines_per_row > 1
            new_lines = [' '.join([_l.strip() for _l in keyfile_lines[_i:_i + lines_per_row]])
                         for _i
                         in range(start_index, end_index, lines_per_row)]

        if not has_indices_column:
            output = np.loadtxt(new_lines, dtype=dtype)
        else:
            first_column_index = 1 if keyword_dict['has_indices_column'] else 0
            value_column_numbers = tuple(range(first_column_index, total_columns_count, 1))

            actual_indices = np.add(-1,
                                    np.loadtxt(new_lines, dtype='i', usecols=(0,)))

            if expected_count_of_data_lines == actual_indices.shape[0]:
                output = np.loadtxt(new_lines, dtype=dtype, usecols=value_column_numbers)
            else:
                default_value = 0
                output = np.full(shape=(expected_count_of_data_lines, data_columns_count),
                                 fill_value=default_value,
                                 dtype=dtype)
                actual_data = np.loadtxt(new_lines, dtype=dtype, usecols=value_column_numbers)
                actual_data.shape = (actual_data.shape[0], data_columns_count)
                output[actual_indices, :] = actual_data
        return output
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def _read_flownet_keyword(lines: list[str], index: list, args: list) -> dict:
    try:
        index[0] += 1  # Move index to the next line after Keyword line

        vertices_count: int = args[2]
        triangles_count: int = args[3]

        v_start = index[0]
        v_end = v_start + vertices_count

        t_start = v_end
        t_end = t_start + triangles_count

        index[0] = t_end - 1  # Move index to the last line of array

        v_column_count = len(lines[v_start].strip().split())
        t_column_count = len(lines[t_start].strip().split())

        v_column_indices = tuple(range(1, v_column_count, 1))
        t_column_indices = tuple(range(1, t_column_count, 1))

        output = {
            'vertices': np.loadtxt(lines[v_start:v_end], dtype='f8', usecols=v_column_indices),
            'triangles': np.loadtxt(lines[t_start:t_end], dtype='i', usecols=t_column_indices),
        }

        output['triangles'] = np.where(output['triangles'] > 0,
                                       np.add(output['triangles'], np.array(-1)),
                                       output['triangles'])
        return output
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def _select_type(type_pattern, index):
    try:
        is_exceeds_length = index > len(type_pattern) - 1
        result = type_pattern[-1] if is_exceeds_length else type_pattern[index]
        return result
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def _convert_to_int_and_float(words):
    converted_words = []
    try:
        while words:
            _w = words.pop(0)
            try:
                _int = int(_w)
            except ValueError:
                try:
                    assert '.' in _w
                    _float = float(_w)
                except (AssertionError, ValueError, Exception):
                    converted_words.append(_w)
                else:
                    converted_words.append(_float)
            else:
                converted_words.append(_int)
        return converted_words
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def _root3_if_positive_q(a, r2, q, rq, arq):
    try:
        # if arq > 1. and arq <= 1. + 1e-6:
        #     if rq > 1.:
        #         rq = np.full(a.shape, 1.)
        #     else:
        #         rq = np.full(a.shape, -1.)
        rq_plus_minus_ones = np.where(rq > 1., np.full(a.shape, 1.), np.full(a.shape, -1.))
        condition = np.logical_and(arq > 1., arq <= 1. + 1e-6)
        rq = np.where(condition, rq_plus_minus_ones, rq)

        th = np.arccos(rq)
        t3 = th / 3.
        a3 = a / 3.
        qr = -2. * np.sqrt(q)
        p23 = 2. * pi / 3.
        x = np.array([
            qr * np.cos(t3) - a3,
            qr * np.cos(t3 + p23) - a3,
            qr * np.cos(t3 - p23) - a3])
        r1 = -1e8 * np.ones(a.shape)
        r3 = 1e8 * np.ones(a.shape)
        mx = np.full(a.shape, -1)
        mn = np.full(a.shape, -1)
        for i, xi in enumerate(x):
            ith = np.full(a.shape, i)
            mx = np.where(xi > r1, ith, mx)
            r1 = np.where(xi > r1, xi, r1)
            mn = np.where(xi < r3, ith, mn)
            r3 = np.where(xi < r3, xi, r3)
        pass_trigger = np.full(a.shape, True)
        for i, xi in enumerate(x):
            ith = np.full(a.shape, i)
            condition = np.logical_and(ith != mx, ith != mn)
            r2 = np.where(np.logical_and(condition, pass_trigger), xi, r2)
            pass_trigger = np.where(condition, False, pass_trigger)
        return r1, r2, r3
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def _root3(a, b, c):
    try:
        i_flag = np.zeros(a.shape)
        a2 = a * a
        a3 = a2 * a
        q = (a2 - 3. * b) / 9.
        r = (2. * a3 - 9. * a * b + 27. * c) / 54.

        allow_changing_trigger = np.full(a.shape, True)

        condition_0 = q < 0.
        i_flag = np.where(condition_0, 1, i_flag)
        allow_changing_trigger = np.logical_and(allow_changing_trigger, np.logical_not(condition_0))

        condition_1 = q == 0.
        allow_condition = np.logical_and(condition_1, allow_changing_trigger)
        allow_changing_trigger = np.logical_and(allow_changing_trigger, np.logical_not(condition_1))

        a13 = a / -3.
        r1 = np.where(allow_condition, a13, 0.)
        r2 = np.where(allow_condition, a13, 0.)
        r3 = np.where(allow_condition, a13, 0.)
        q3 = np.power(q, 3)
        sq = np.sqrt(q3)
        rq = np.divide(r, sq, out=np.zeros_like(r), where=(sq != 0.0))
        arq = np.abs(rq)

        # if arq > 1. + 1e-6:
        #     i_flag = np.ones(a.shape)
        condition_2 = arq > 1. + 1.e-6
        allow_condition = np.logical_and(condition_2, allow_changing_trigger)
        i_flag = np.where(allow_condition, 1, i_flag)
        allow_changing_trigger = np.logical_and(allow_changing_trigger, np.logical_not(condition_2))

        r1_q_pos, r2_q_pos, r3_q_pos = _root3_if_positive_q(a, r2, q, rq, arq)
        r1 = np.where(allow_changing_trigger, r1_q_pos, r1)
        r2 = np.where(allow_changing_trigger, r2_q_pos, r2)
        r3 = np.where(allow_changing_trigger, r3_q_pos, r3)

        return np.stack([r1, r2, r3], axis=1), i_flag
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def _principal_values(t):
    try:
        t0 = t[:, 0]
        t1 = t[:, 1]
        t2 = t[:, 2]
        t3 = t[:, 3]
        t4 = t[:, 4]
        t5 = t[:, 5]
        txy2 = np.square(t[:, 3])
        tyz2 = np.square(t[:, 4])
        tzx2 = np.square(t[:, 5])
        a = -1. * np.sum(t[:, [0, 1, 2]], axis=1)
        b = t0 * t1 + t1 * t2 + t2 * t0 - (txy2 + tyz2 + tzx2)
        c = t0 * tyz2 + t1 * tzx2 + t2 * txy2 - (t0 * t1 * t2 + 2. * t3 * t4 * t5)
        _principal_vectors, i_flag = _root3(a, b, c)
        return _principal_vectors
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def _tensor_to_scalar_equivalent(t):
    try:
        return np.sqrt(
            0.5 * (
                    np.square(t[:, 0] - t[:, 1]) +
                    np.square(t[:, 1] - t[:, 2]) +
                    np.square(t[:, 2] - t[:, 0]) +
                    6. * (np.square(t[:, 3]) + np.square(t[:, 4]) + np.square(t[:, 5]))
            )
        )
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def _tensor_to_scalar_mean(tensor):
    try:
        return np.sum(tensor[:, [0, 1, 2]], axis=1) / 3.
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def _tensor_to_scalar_max_principal(tensor):
    try:
        return _principal_values(tensor)[:, 0]
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def _tensor_to_scalar_inter_principal(tensor):
    try:
        return _principal_values(tensor)[:, 1]
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def _tensor_to_scalar_min_principal(tensor):
    try:
        return _principal_values(tensor)[:, 2]
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def _tensor_to_vector_min_principal(tensor):
    # TODO: Min principal is not finished
    try:
        return _tensor_to_vector_x_projection(tensor)
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def _tensor_to_vector_max_principal(tensor):
    # TODO: Max principal is not finished
    try:
        return _tensor_to_vector_x_projection(tensor)
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def _tensor_to_vector_x_projection(tensor):
    try:
        vector = tensor[:, [0, 1, 2]]
        vector[:, [1, 2]] = 0.
        return vector
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def _tensor_to_vector_y_projection(tensor):
    try:
        vector = tensor[:, [0, 1, 2]]
        vector[:, [0, 2]] = 0.
        return vector
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def _tensor_to_vector_z_projection(tensor):
    try:
        # tensor[x, y, z, xy, yz, zx]
        vector = tensor[:, [0, 1, 2]]
        vector[:, [0, 1]] = 0.
        return vector
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def _vector_to_scalar_magnitude(vector):
    try:
        return np.linalg.norm(vector, axis=1, ord=2)
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def _vector_to_vector_x_projection(vector):
    try:
        vector[:, [1, 2]] = 0.
        return vector
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def _vector_to_vector_y_projection(vector):
    try:
        vector[:, [0, 2]] = 0.
        return vector
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def _vector_to_vector_z_projection(vector):
    try:
        vector[:, [0, 1]] = 0.
        return vector
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


# Changes basis of given vector from "absolute" basis {(1, 0, 0), (0, 1, 0), (0, 0, 1)} to given basis
def _vector_relative(vector: np.ndarray, basis: np.ndarray) -> np.array:
    try:
        return np.linalg.solve(np.transpose(basis), vector)
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


# Changes basis of given from given basis to "absolute" one (see above)
def _vector_absolute(rel: np.ndarray, basis: np.ndarray) -> np.array:
    return np.add.reduce([np.multiply(rel[i], basis[i]) for i in range(len(rel))])


def _separate_user_nodal(obj_data: dict):
    try:
        if 'user_nodal' not in obj_data:
            return
        obj_data.update({
            'max_temperature_bite': obj_data['user_nodal'][:, 0],
            'max_temperature_operation': obj_data['user_nodal'][:, 1],
            'temperature_change_bite': obj_data['user_nodal'][:, 2],
            'temperature_change_operation': obj_data['user_nodal'][:, 3],
            'ingot_axis_x': obj_data['user_nodal'][:, 4],
            'ingot_axis_y': obj_data['user_nodal'][:, 5],
            'ingot_axis_z': obj_data['user_nodal'][:, 6]
        })
    except Exception as _err:
        LOGGER.error(f"FAILED separate User Nodal Variables with {type(_err).__name__}: {_err}")
        raise


def _separate_user_element(obj_data: dict):
    try:
        if 'user_element' not in obj_data:
            return
        obj_data.update({
            'strain_bite': obj_data['user_element'][:, 0],
            'strain_operation': obj_data['user_element'][:, 1],
            'strain_heat': obj_data['user_element'][:, 2]
        })
    except Exception as _err:
        LOGGER.error(f"FAILED calculate User Element Variables with {type(_err).__name__}: {_err}")
        raise


def _calculate_strain_tensor_variables(obj: dict):
    try:
        if 'element_tensor6_strain' not in obj:
            return
        obj.update({
            'strain_total_von_mises': _tensor_to_scalar_equivalent(obj['element_tensor6_strain']),
            'strain_total_mean_scalar': _tensor_to_scalar_mean(obj['element_tensor6_strain']),
            'strain_total_max_principal_scalar': _tensor_to_scalar_max_principal(obj['element_tensor6_strain']),
            'strain_total_inter_principal_scalar': _tensor_to_scalar_inter_principal(obj['element_tensor6_strain']),
            'strain_total_min_principal_scalar': _tensor_to_scalar_min_principal(obj['element_tensor6_strain']),
            'strain_total_max_principal_vectors': _tensor_to_vector_max_principal(obj['element_tensor6_strain']),
            'strain_total_min_principal_vectors': _tensor_to_vector_min_principal(obj['element_tensor6_strain']),
            'strain_total_x_vectors': _tensor_to_vector_x_projection(obj['element_tensor6_strain']),
            'strain_total_y_vectors': _tensor_to_vector_y_projection(obj['element_tensor6_strain']),
            'strain_total_z_vectors': _tensor_to_vector_z_projection(obj['element_tensor6_strain'])
        })
    except Exception as _err:
        LOGGER.error(f"FAILED calculate Strain tensor variables with {type(_err).__name__}: {_err}")
        raise


def _add_surface_variable(obj_data: dict):
    if 'nodes' not in obj_data:
        return

    try:
        nodes: np.ndarray = obj_data['nodes']

        obj_data.update({
            'surface': np.zeros_like(nodes[:, 0])
        })
    except Exception as _err:
        LOGGER.error(f"FAILED add Surface variable with {type(_err).__name__}: {_err}")
        raise


def _calculate_stress_tensor_variables(obj_data: dict):
    try:
        if 'element_tensor6_stress' not in obj_data:
            return
        obj_data.update({
            'stress_mean': _tensor_to_scalar_mean(obj_data['element_tensor6_stress']),
            'stress_max_principal_scalar': _tensor_to_scalar_max_principal(obj_data['element_tensor6_stress']),
            'stress_inter_principal_scalar': _tensor_to_scalar_inter_principal(obj_data['element_tensor6_stress']),
            'stress_min_principal_scalar': _tensor_to_scalar_min_principal(obj_data['element_tensor6_stress']),
            'stress_max_principal_vectors': _tensor_to_vector_max_principal(obj_data['element_tensor6_stress']),
            'stress_min_principal_vectors': _tensor_to_vector_min_principal(obj_data['element_tensor6_stress']),
            'stress_x_vectors': _tensor_to_vector_x_projection(obj_data['element_tensor6_stress']),
            'stress_y_vectors': _tensor_to_vector_y_projection(obj_data['element_tensor6_stress']),
            'stress_z_vectors': _tensor_to_vector_z_projection(obj_data['element_tensor6_stress'])
        })
    except Exception as _err:
        LOGGER.error(f"FAILED calculate Stress tensor variables with {type(_err).__name__}: {_err}")
        raise


def _get_tensor_data(data):
    result = {}
    try:
        node_count = result['nodes'].shape[0]
        elem_count = result['elements'].shape[0]

        for keyword, args in data:
            if args[0] != 1:  # Not a billet
                continue
            if keyword == 'URZ':
                if args[1] != node_count and len(args) == 3:
                    _r = np.full(shape=(node_count, 3), fill_value=args[2], dtype=np.float64)
                elif args[1] != node_count and len(args) == 5:
                    xyz = np.array(args[2:])
                    _r = np.tile(xyz, reps=(node_count, 1))
                else:
                    _r = np.squeeze(np.array(args[3:]), axis=1)[:, [1, 2, 3]]
                result['nodal_vector_speed'] = _r
            elif keyword == 'NDTMP':
                if args[1] != node_count:
                    _r = np.full(shape=(node_count, 1), fill_value=args[2], dtype=np.float64)
                else:
                    _r = np.squeeze(np.array(args[3:]), axis=1)[:, [1]]
                result['nodal_scalar_temperature'] = _r
            elif keyword == 'STRAIN':
                if args[1] != elem_count:
                    _r = np.full(shape=(elem_count, 1), fill_value=args[2], dtype=np.float64)
                else:
                    _r = np.squeeze(np.array(args[3:]), axis=1)[:, [1]]
                result['strain_effective'] = _r
            elif keyword == 'STNCMP':
                if args[1] != elem_count:
                    comp_count = args[2]
                    _r = np.full(shape=(elem_count, comp_count), fill_value=args[3], dtype=np.float64)
                else:
                    _r = args[4][:, [1, 2, 3, 4, 5, 6]]
                result['element_tensor6_strain'] = _r
            elif keyword == 'DAMAGE':
                if args[1] != elem_count:
                    _r = np.full(shape=(elem_count, 1), fill_value=args[2], dtype=np.float64)
                else:
                    _r = np.squeeze(np.array(args[3:]), axis=1)[:, [1]]
                result['element_scalar_damage'] = _r
            elif keyword == 'STRESS':
                if args[1] != elem_count:
                    _r = np.full(shape=(elem_count, 6), fill_value=args[2], dtype=np.float64)
                else:
                    _r = args[3][:, [1, 2, 3, 4, 5, 6]]
                result['element_tensor6_stress'] = _r
            elif keyword == 'FLWNET':
                vertices, triangles = args[2], args[3]
                vertices_index_start, vertices_index_end = 4, 4 + vertices
                triangles_index_start, triangles_index_end = vertices_index_end, vertices_index_end + triangles
                result['vertices_array'] = np.squeeze(
                    np.array(args[vertices_index_start:vertices_index_end]), axis=1)[:, [1, 2, 3]]
                result['triangles_array'] = -1 + np.squeeze(
                    np.array(args[triangles_index_start:triangles_index_end]).astype('uint32'), axis=1
                )[:, [1, 2, 3]]

        # ---------------------------------- USRNOD -----------------------------------------

        for keyword, args in data:
            if args[0] == 1:  # For billet only
                if keyword == 'USRNOD':
                    if args[1] == node_count:
                        result['user_nodal'] = args[4]
                    else:
                        variables_count = 2
                        default_value = 0.0
                        result[f'user_nodal'] = np.full(shape=(node_count, variables_count),
                                                        fill_value=default_value,
                                                        dtype=np.float64)

        # ---------------------------------- USRELM -----------------------------------------

        for keyword, args in data:
            if args[0] == 1:  # For billet only
                if keyword == 'USRELM':
                    if args[1] == elem_count:
                        result[f'user_element'] = args[4]
                    else:
                        variables_count = 2
                        default_value = 0.0
                        result['user_element'] = np.full(shape=(elem_count, variables_count),
                                                         fill_value=default_value,
                                                         dtype=np.float64)
        return result
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def gram_schmidt_1(nearly_orthogonal_unit_vectors: np.ndarray) -> np.ndarray:
    """
    Use the Gram-Schmidt process to find a coordinate system with strictly orthogonal unit vectors based on
    nearly orthogonal vectors. This process orthogonalizes a set of vectors in an inner product space.
    """
    orthogonal_vectors = []
    try:
        for v in nearly_orthogonal_unit_vectors.astype(np.float64):
            for u in orthogonal_vectors:
                v -= np.dot(v, u) / np.dot(u, u) * u

            _norm = None
            _div = None
            try:
                _norm = np.linalg.norm(v)
                _div = v / _norm
                orthogonal_vectors.append(_div)
            except RuntimeWarning as _err:
                LOGGER.error(f"Failed to get orthogonal vectors: "
                             f"'np.linalg.norm(v)'={_norm}  'v / _norm'={_div} Error: {_err}")

        return np.array(orthogonal_vectors)
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise

def weighted_gram_schmidt(nearly_orthogonal_unit_vectors: np.ndarray, r_squared_scores: np.ndarray) -> np.ndarray:
    """
    Use the Gram-Schmidt process to find a coordinate system with strictly orthogonal unit vectors based on
    nearly orthogonal vectors.  This code prioritizes the unit vectors based on their R^2 scores, ensuring
    that the most accurately determined gradients have the most influence in defining the local coordinate system.
    The orthogonalization process respects this ranking, adjusting the influence of each vector accordingly.
    """
    try:
        # Step 1: Validate near orthogonality by checking the dot products
        # print("Dot product v1 and v2:", np.dot(nearly_orthogonal_unit_vectors[0], nearly_orthogonal_unit_vectors[1]))
        # print("Dot product v1 and v3:", np.dot(nearly_orthogonal_unit_vectors[0], nearly_orthogonal_unit_vectors[2]))
        # print("Dot product v2 and v3:", np.dot(nearly_orthogonal_unit_vectors[1], nearly_orthogonal_unit_vectors[2]))

        # Step 1: Rank vectors based on R^2 scores
        ranked_indices = np.argsort(r_squared_scores)[::-1]  # Sort indices by R^2 scores in descending order
        ranked_vectors = nearly_orthogonal_unit_vectors[ranked_indices]

        # Adjusted Gram-Schmidt process (Step 2 & 3)
        # Start with the highest R^2 score vector as the most accurate one
        v1 = ranked_vectors[0]
        v1_unit = v1 / np.linalg.norm(v1)

        # Orthogonalize the second vector with respect to the first
        v2 = ranked_vectors[1] - np.dot(ranked_vectors[1], v1_unit) * v1_unit
        v2_unit = v2 / np.linalg.norm(v2)

        # Orthogonalize the third vector with respect to the first two
        v3 = ranked_vectors[2] - np.dot(ranked_vectors[2], v1_unit) * v1_unit - np.dot(ranked_vectors[2],
                                                                                       v2_unit) * v2_unit
        v3_unit = v3 / np.linalg.norm(v3)

        # Assemble the weighted local coordinate system (Step 4)
        weighted_local_coordinate_system = np.empty_like(nearly_orthogonal_unit_vectors)
        weighted_local_coordinate_system[ranked_indices] = np.array([v1_unit, v2_unit, v3_unit])
        return weighted_local_coordinate_system
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def get_nearly_orthogonal_unit_vectors_based_on_ingot_axis_gradients(nodes: np.ndarray, ingot_axes: np.ndarray
                                                                     ) -> tuple[np.ndarray, np.ndarray]:
    try:
        # Initialize results container
        lcs = np.empty((3, 3))
        r_score = np.empty(3)

        # Fit a linear regression model for each set of scalar values
        for i in range(ingot_axes.shape[1]):
            # Dependent variable 'i' for the current set
            gradient_quantity = ingot_axes[:, i]

            # Create and fit the linear regression model for the current set of scalar values
            reg = LinearRegression().fit(nodes, gradient_quantity)

            # The coefficients represent the gradient vector of 'i'
            gradient_vector_current = reg.coef_

            # Normalizing the gradient vector to obtain the unit vector
            unit_vector_current = gradient_vector_current / np.linalg.norm(gradient_vector_current)

            # Calculate the R^2 score
            r_squared_current = reg.score(nodes, gradient_quantity)

            # Append results
            lcs[i] = unit_vector_current
            r_score[i] = r_squared_current

            # print(f"Unit vector {i}: {unit_vector_current}  R^2 score: {r_squared_current}")
            # print('test')
        # print(f"Local coordinate system: {lcs}  R^2 scores: {r_score}")
        return lcs, r_score
    except Exception as _err:
        LOGGER.error(f"FAILED get unit vectors system based on ingot gradients {type(_err).__name__}: {_err}")
        raise

def get_principal_coordinate_system_based_on_ingot_gradients_2(nodes: np.ndarray, ingot_axes: np.ndarray
                                                               ) -> np.ndarray:
    try:
        unit_vectors, r_scores = get_nearly_orthogonal_unit_vectors_based_on_ingot_axis_gradients(nodes, ingot_axes)
        lcs = weighted_gram_schmidt(unit_vectors, r_scores)
        return lcs
    except Exception as _err:
        LOGGER.error(f"FAILED get principal coordinate system based on ingot gradients {type(_err).__name__}: {_err}")
        raise


def get_principal_coordinate_system_based_on_ingot_gradients(nodes: np.ndarray, elements: np.ndarray,
                                                             old_xyz: np.ndarray) -> np.ndarray:
    try:
        gradients = np.zeros((elements.shape[0], 3, 3), dtype=np.float64)
        mask = np.ones((elements.shape[0], 3, 3), dtype=bool)

        for i, node_indices in enumerate(elements):
            try:
                _xyz = np.hstack((np.ones((4, 1)), nodes[node_indices]))
                _inv = np.linalg.inv(_xyz)
                gradients[i] = np.dot(_inv, old_xyz[node_indices])[1:, :]
            except (np.linalg.LinAlgError, Exception):
                mask[i, :, :] = np.zeros((3, 3), dtype=bool)

        mean_gradient = np.mean(gradients, axis=0, where=mask)
        nearly_orthogonal_unit_vectors = mean_gradient / np.linalg.norm(mean_gradient, axis=1)
        coordinate_system_unit_vectors = gram_schmidt_1(nearly_orthogonal_unit_vectors)
        return coordinate_system_unit_vectors
    except Exception as _err:
        LOGGER.error(f"FAILED get principal coordinate system based on ingot gradients {type(_err).__name__}: {_err}")
        raise


def get_conversion_indices() -> list:
    return [
        0, 1,  # d01 = sd[:, 0]
        0, 2,  # d02 = sd[:, 1]
        0, 3,  # d03 = sd[:, 2]
        1, 2,  # d12 = sd[:, 3]
        1, 3,  # d13 = sd[:, 4]
        2, 3]  # d23 = sd[:, 5]


def get_coordinates_of_edges(nodes: np.ndarray, elements: np.ndarray, edges_of_pyramid, shape_in_2_columns
                             ) -> tuple[np.ndarray, np.ndarray]:
    try:
        element_edges = elements[:, edges_of_pyramid].reshape(shape_in_2_columns)
        return nodes[element_edges[:, 0]], nodes[element_edges[:, 1]]
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def get_length_of_element_edges(node_1: np.ndarray, node_2: np.ndarray) -> dict:
    try:
        return {
            '3d': np.linalg.norm(node_2 - node_1, axis=1),
            'xy': np.linalg.norm(node_2[:, [0, 1]] - node_1[:, [0, 1]], axis=1),
            'yz': np.linalg.norm(node_2[:, [1, 2]] - node_1[:, [1, 2]], axis=1),
            'xz': np.linalg.norm(node_2[:, [0, 2]] - node_1[:, [0, 2]], axis=1)}
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def volumes(length_of_edges: dict, number_of_elements: int) -> np.ndarray:
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
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def calculate_element_centers(nodes: np.ndarray, elements: np.ndarray) -> np.ndarray:
    # Mean along the second axis (i.e., the vertices)
    try:
        return nodes[elements].mean(axis=1)
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def calculate_center_of_mass(_volumes: np.ndarray, _centers: np.ndarray) -> np.ndarray:
    """
    Compute the weighted average of the centers, where the weights are the volumes
    The np.newaxis is necessary to align the shapes of volumes and centers for broadcasting
    """
    try:
        total_volume = _volumes.sum()
        return (_volumes[:, np.newaxis] * _centers).sum(axis=0) / total_volume
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def get_mesh_bounds(nodes: np.ndarray) -> np.ndarray:
    try:
        min_coord = np.amin(nodes, axis=0)
        max_coord = np.amax(nodes, axis=0)
        return np.concatenate([min_coord, max_coord]).reshape(2, 3)
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def get_mesh_length(mesh_bounds: np.ndarray) -> np.ndarray:
    try:
        return mesh_bounds[1, :] - mesh_bounds[0, :]
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def get_bounds_centroid(mesh_bounds: np.ndarray) -> np.ndarray:
    try:
        return np.average(mesh_bounds, axis=0)
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def _tails_x_length(nodes: np.ndarray, bounds_centroid: np.ndarray) -> np.ndarray:
    """Creating straight prism tesselation. Returns stl mesh object."""
    import math
    from scipy.spatial.transform import Rotation
    try:
        y_axis = np.array([0, 1, 0])  # Y-axis
        angle = math.radians(45.0)
        rot = Rotation.from_rotvec(angle * y_axis)

        centered_nodes = nodes - bounds_centroid
        bounds = get_mesh_bounds(centered_nodes)
        rotated_bounds = get_mesh_bounds(rot.apply(centered_nodes))

        """
            CHAMFERS:
               12      z_top       21   
        (1)    +--------------------+  (2)
             /          ^ Z          \
        11  +           |             + 22
            |           |             |
            |           o---->X       |
        42  +                         + 31
             \                       /
        (4)   +---------------------+  (3)
              41     z_bottom      32  
        """

        z_top_12_21 = np.abs(bounds[1, 2])
        z_bottom_41_32 = np.abs(bounds[0, 2])
        x_left_11_42 = np.abs(bounds[0, 0])
        x_right_22_31 = np.abs(bounds[1, 0])

        r_1 = np.abs(rotated_bounds[1, 2])  # Z-top Rotated
        r_3 = np.abs(rotated_bounds[0, 2])  # Z-bottom Rotated
        r_4 = np.abs(rotated_bounds[0, 0])  # X-left Rotated
        r_2 = np.abs(rotated_bounds[1, 0])  # X-right Rotated

        sqrt2 = np.float64(math.sqrt(2))

        chamfer_1_x_length = x_left_11_42 - (sqrt2 * r_1 - z_top_12_21)
        chamfer_4_x_length = x_left_11_42 - (sqrt2 * r_4 - z_bottom_41_32)
        chamfer_2_x_length = x_right_22_31 - (sqrt2 * r_2 - z_top_12_21)
        chamfer_3_x_length = x_right_22_31 - (sqrt2 * r_3 - z_bottom_41_32)

        left_tail_x_length = max(chamfer_1_x_length, chamfer_4_x_length)
        right_tail_x_length = max(chamfer_2_x_length, chamfer_3_x_length)

        return np.array([left_tail_x_length, right_tail_x_length])
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def get_barrels_length(nodes: np.ndarray, bounds_centroid: np.ndarray, tails_direction_bool: np.ndarray, 
                       projection_axis=None) -> np.ndarray:
    """http://kieranwynn.github.io/pyquaternion/"""
    try:
        np.set_printoptions(suppress=True)
        centered_nodes = nodes - bounds_centroid
        final_tail_coordinates = []
        # noinspection PyTypeChecker
        for rotation_angle in [45, -45]:
            my_quaternion = Quaternion(axis=projection_axis, degrees=rotation_angle)
            current_shape = centered_nodes.shape
            rotated_nodes = np.empty(current_shape, dtype=np.float64)
            for i in range(current_shape[0]):
                rotated_nodes[i, :] = my_quaternion.rotate(centered_nodes[i, :])

            # min values - represents 1st tail, max values - represents 2nd tail
            # noinspection PyTypeChecker
            node_numbers_1st_tail: list = np.argmin(rotated_nodes, axis=0).tolist()
            # noinspection PyTypeChecker
            node_numbers_2nd_tail: list = np.argmax(rotated_nodes, axis=0).tolist()

            # min coordinates - represents 1st tail, max coordinates - represents 2nd tail
            coordinates_1st_tail = nodes[node_numbers_1st_tail, :]
            coordinates_2nd_tail = nodes[node_numbers_2nd_tail, :]

            # filter coordinates in 'tails_direction'
            single_coordinate_tail_1 = coordinates_1st_tail[tails_direction_bool, :].ravel()[tails_direction_bool][0]
            single_coordinate_tail_2 = coordinates_2nd_tail[tails_direction_bool, :].ravel()[tails_direction_bool][0]

            final_tail_coordinates.append([single_coordinate_tail_1, single_coordinate_tail_2])

        return np.average(np.array(final_tail_coordinates), axis=0)
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def get_tail_lengths(mesh_bounds: np.ndarray, tails_direction_bool: np.ndarray, internal_tail_bounds: np.ndarray
                     ) -> np.ndarray:
    try:
        billet_bounds_in_tail_direction = mesh_bounds[:, tails_direction_bool].ravel()
        return np.abs(billet_bounds_in_tail_direction - internal_tail_bounds)
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def get_length_excluding_tail_barrels(mesh_dim: np.ndarray, tail_lengths: np.ndarray) -> np.array:
    try:
        return mesh_dim[0] - np.sum(tail_lengths)
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def get_flow_net_center(vertices: np.ndarray, triangles: np.ndarray) -> np.array:
    """
    Reads Flow Net Triangles vertices and connectivity array.
    Flow Net is located in the tail center.
    Returns center of Flow Net area.
    """
    # Assuming these are your input arrays
    # vertices = np.array([[x1, y1, z1], [x2, y2, z2], ..., [xn, yn, zn]])
    # triangles = np.array([[i1, i2, i3], [j1, j2, j3], ..., [kn, km, kp]])

    # Extract vertices
    try:
        v0 = vertices[triangles[:, 0]]
        v1 = vertices[triangles[:, 1]]
        v2 = vertices[triangles[:, 2]]
        areas = 0.5 * np.linalg.norm(np.cross(v1 - v0, v2 - v0), axis=1)  # Compute the area of each triangle
        total_area = np.sum(areas)
        centroids = (v0 + v1 + v2) / 3.0  # Compute the centroid of each triangle
        return np.sum(areas[:, np.newaxis] * centroids, axis=0) / total_area
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def vector_defined_by_two_points(center: np.ndarray, tail: np.ndarray) -> np.array:
    """
    Assuming these are input 3D points
    center_of_mass = np.array([x1, y1, z1])
    tail_center = np.array([x2, y2, z2])
    """
    difference_vector = tail - center  # calculate the difference vector
    return difference_vector / np.linalg.norm(difference_vector)  # normalize the difference vector


def get_principal_coordinate_system_based_on_flow_net(x_axis_unit_vector: np.ndarray) -> np.array:
    """
    Assuming this is your input unit vector for the first axis u1 = np.array([x1, y1, z1])
    """
    try:
        if abs(x_axis_unit_vector[1]) > 0.999:
            return np.array([[0, 1, 0],  # Y
                             [1, 0, 0],  # X
                             [0, 0, 1],  # Z
                             ])

        xz_plane_orthogonal_vector = np.array([0, 1, 0])  # Global y-axis
        y_axis = np.cross(x_axis_unit_vector, xz_plane_orthogonal_vector)  # orthogonal to x-axis and XZ plane
        y_axis[1] = 0  # Ensure y-axis is in the XZ plane
        y_axis_unit_vector = y_axis / np.linalg.norm(y_axis)

        z_axis_unit_vector = np.cross(x_axis_unit_vector, y_axis_unit_vector)  # orthogonal to the first two

        return np.array([x_axis_unit_vector,
                         y_axis_unit_vector,
                         z_axis_unit_vector])
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise

def intersect_stl_by_plane_return_2d_contour(surface_nodes: np.ndarray,
                                             surface_faces: np.ndarray,
                                             plane_origin: np.ndarray,
                                             plane_normal: np.ndarray
                                             ) -> Polygon:
    try:
        _m = trimesh.Trimesh(vertices=surface_nodes, faces=surface_faces)
        intersection: Path3D = _m.section(plane_origin=plane_origin, plane_normal=plane_normal)

        # Get the 2D path of the slice and convert to a shapely Polygon
        if slice is not None:
            to_xy = trimesh.geometry.align_vectors(plane_normal, [0, 0, 1])
            slice_2d, _ = intersection.to_planar(to_2D=to_xy)
            _yx = np.transpose(np.array(np.sum(slice_2d.polygons_full).boundary.xy))
            _xy = _yx[:, [1, 0]]
            _polygon = Polygon(_xy)

        else:
            _polygon = None  # Return None if no intersection is found
        return _polygon
    except Exception as _err:
        LOGGER.error(f"FAILED intersect STL by plane with {type(_err).__name__}: {_err}")
        raise


# def plot_axis(u):
#     import matplotlib.pyplot as plt
#     from mpl_toolkits.mplot3d import Axes3D
#
#     # Assuming these are your vectors
#     # u1 = np.array([x1, y1, z1])
#     # u2 = np.array([x2, y2, z2])
#     # u3 = np.array([x3, y3, z3])
#
#     u1, u2, u3 = u[0], u[1], u[2]
#
#     # Creating the figure and adding a 3d subplot
#     fig = plt.figure()
#     ax = fig.add_subplot(111, projection='3d')
#
#     # Drawing the vectors (axes)
#     ax.quiver(0, 0, 0, u1[0], u1[1], u1[2], color='r', label='axis 1')
#     ax.quiver(0, 0, 0, u2[0], u2[1], u2[2], color='g', label='axis 2')
#     ax.quiver(0, 0, 0, u3[0], u3[1], u3[2], color='b', label='axis 3')
#
#     # Setting the limit for each axis
#     ax.set_xlim([-1, 1])
#     ax.set_ylim([-1, 1])
#     ax.set_zlim([-1, 1])
#
#     # Setting the labels for each axis
#     ax.set_xlabel('X')
#     ax.set_ylabel('Y')
#     ax.set_zlabel('Z')
#
#     # Adding a legend
#     ax.legend()
#
#     # Displaying the plot
#     plt.show()


def _add_mesh_measurements(obj_data: dict) -> None:
    """Extract mesh parameters"""
    if 'nodes' not in obj_data or 'elements' not in obj_data or 'flownet' not in obj_data:
        return

    try:
        nodes: np.ndarray = obj_data['nodes']
        elements: np.ndarray = obj_data['elements']
        # triangles: np.ndarray = obj_data['flownet']['triangles']
        # vertices: np.ndarray = obj_data['flownet']['vertices']
        ingot_axes = np.column_stack((obj_data['ingot_axis_x'],
                                      obj_data['ingot_axis_y'],
                                      obj_data['ingot_axis_z']))
    except Exception as _err:
        LOGGER.error(f"FAILED extracting Node and Elements data from 'parameters' with {type(_err).__name__}: {_err}")
        raise

    try:
        edges_of_pyramid = get_conversion_indices()
        number_of_elements = elements.shape[0]
        shape_in_2_columns = (int(number_of_elements * 6), 2)
        node_1, node_2 = get_coordinates_of_edges(nodes, elements, edges_of_pyramid, shape_in_2_columns)
        length_of_edges = get_length_of_element_edges(node_1, node_2)
        elements_volumes = volumes(length_of_edges, number_of_elements)
        element_centers = calculate_element_centers(nodes, elements)
        center_of_mass = calculate_center_of_mass(elements_volumes, element_centers)
        mesh_bounds = get_mesh_bounds(nodes)
        mesh_dim = get_mesh_length(mesh_bounds)
        bounds_centroid = get_bounds_centroid(mesh_bounds)
        tails_direction_bool = np.array([1, 0, 0], dtype=bool)
        internal_tail_bounds = get_barrels_length(nodes, bounds_centroid, tails_direction_bool, projection_axis=[0, 1, 0])
        # tail_lengths = get_tail_lengths(mesh_bounds, tails_direction_bool, internal_tail_bounds)
        tail_lengths = _tails_x_length(nodes, bounds_centroid)
        length_excluding_tail_barrels = get_length_excluding_tail_barrels(mesh_dim, tail_lengths)
        # tail_center = get_flow_net_center(vertices, triangles)
        # billet_x_axis_unit_vector = vector_defined_by_two_points(center_of_mass, tail_center)
        # billet_principal_coordinate_system_as_xyz_unit_vectors_based_on_flow_net = \
        #     get_principal_coordinate_system_based_on_flow_net(billet_x_axis_unit_vector)
        local_coordinate_system = get_principal_coordinate_system_based_on_ingot_gradients_2(nodes, ingot_axes)
        # grad = average_gradient(nodes, elements, old_xyz[:, 0])
        # transformed_coords, principal_axes = restore_local_coordinate_system(nodes, old_xyz)
        # plot_axis(principal_coordinate_system)
    except Exception as _err:
        LOGGER.error(f"FAILED calculating mesh parameters with {type(_err).__name__}: {_err}")
        raise

    try:
        obj_data['measurements'] = {
            'volume': np.sum(elements_volumes).item(),
            'length': mesh_dim[0].item(),
            'width': mesh_dim[1].item(),
            'height': mesh_dim[2].item(),
            'bounds': mesh_bounds.tolist(),
            'centroid': bounds_centroid.tolist(),
            'center_of_mass': center_of_mass.tolist(),
            # 'tail_center': tail_center.tolist(),
            # 'axis_direction': billet_x_axis_unit_vector.tolist(),
            'principal_coordinate_system': local_coordinate_system.tolist(),
            'left_tail_barrel_length': tail_lengths[0].item(),
            'right_tail_barrel_length': tail_lengths[1].item(),
            'length_excluding_tail_barrels': length_excluding_tail_barrels.item(),
            '3d_dimensions': mesh_dim.tolist(),

            'elements_edges': {
                'min': np.amin(length_of_edges['3d']).item(),
                'max': np.amax(length_of_edges['3d']).item(),
                'average': np.average(length_of_edges['3d']).item(),
                'std': np.std(length_of_edges['3d']).item(),

                'xy_min': np.amin(length_of_edges['xy']).item(),
                'xy_max': np.amax(length_of_edges['xy']).item(),
                'xy_average': np.average(length_of_edges['xy']).item(),
                'xy_std': np.std(length_of_edges['xy']).item(),

                'yz_min': np.amin(length_of_edges['yz']).item(),
                'yz_max': np.amax(length_of_edges['yz']).item(),
                'yz_average': np.average(length_of_edges['yz']).item(),
                'yz_std': np.std(length_of_edges['yz']).item(),

                'xz_min': np.amin(length_of_edges['xz']).item(),
                'xz_max': np.amax(length_of_edges['xz']).item(),
                'xz_average': np.average(length_of_edges['xz']).item(),
                'xz_std': np.std(length_of_edges['xz']).item()}
        }
    except Exception as _err:
        LOGGER.error(f"FAILED adding mesh parameters to 'parameters' with {type(_err).__name__}: {_err}")
        raise


def _add_principal_coordinate_system_based_on_cross_sections(obj_data: dict) -> None:
    """Extract mesh parameters"""
    if any(('nodes' not in obj_data,
            'elements' not in obj_data,
            'surface_nodes' not in obj_data,
            'surface_faces' not in obj_data)):
        return

    try:
        nodes: np.ndarray = obj_data['nodes']
        elements: np.ndarray = obj_data['elements']
        # triangles: np.ndarray = obj_data['flownet']['triangles']
        # vertices: np.ndarray = obj_data['flownet']['vertices']
        ingot_axes = np.column_stack((obj_data['ingot_axis_x'],
                                      obj_data['ingot_axis_y'],
                                      obj_data['ingot_axis_z']))
    except Exception as _err:
        LOGGER.error(f"FAILED extracting Node and Elements data from 'parameters' with {type(_err).__name__}: {_err}")
        raise

    try:

        # polygon_2d = intersect_stl_by_plane_return_2d_contour(surface_nodes, surface_faces, plane_origin, plane_normal)

        edges_of_pyramid = get_conversion_indices()
        number_of_elements = elements.shape[0]
        shape_in_2_columns = (int(number_of_elements * 6), 2)
        node_1, node_2 = get_coordinates_of_edges(nodes, elements, edges_of_pyramid, shape_in_2_columns)
        length_of_edges = get_length_of_element_edges(node_1, node_2)
        elements_volumes = volumes(length_of_edges, number_of_elements)
        element_centers = calculate_element_centers(nodes, elements)
        center_of_mass = calculate_center_of_mass(elements_volumes, element_centers)
        mesh_bounds = get_mesh_bounds(nodes)
        mesh_dim = get_mesh_length(mesh_bounds)
        bounds_centroid = get_bounds_centroid(mesh_bounds)
        tails_direction_bool = np.array([1, 0, 0], dtype=bool)
        internal_tail_bounds = get_barrels_length(nodes, bounds_centroid, tails_direction_bool, projection_axis=[0, 1, 0])
        tail_lengths = get_tail_lengths(mesh_bounds, tails_direction_bool, internal_tail_bounds)
        length_excluding_tail_barrels = get_length_excluding_tail_barrels(mesh_dim, tail_lengths)
        # tail_center = get_flow_net_center(vertices, triangles)
        # billet_x_axis_unit_vector = vector_defined_by_two_points(center_of_mass, tail_center)
        # billet_principal_coordinate_system_as_xyz_unit_vectors_based_on_flow_net = \
        #     get_principal_coordinate_system_based_on_flow_net(billet_x_axis_unit_vector)
        local_coordinate_system = get_principal_coordinate_system_based_on_ingot_gradients_2(nodes, ingot_axes)
        # grad = average_gradient(nodes, elements, old_xyz[:, 0])
        # transformed_coords, principal_axes = restore_local_coordinate_system(nodes, old_xyz)
        # plot_axis(principal_coordinate_system)
    except Exception as _err:
        LOGGER.error(f"FAILED calculating mesh parameters with {type(_err).__name__}: {_err}")
        raise
    try:
        obj_data['measurements'] = {
            'volume': np.sum(elements_volumes).item(),
            'length': mesh_dim[0].item(),
            'width': mesh_dim[1].item(),
            'height': mesh_dim[2].item(),
            'bounds': mesh_bounds.tolist(),
            'centroid': bounds_centroid.tolist(),
            'center_of_mass': center_of_mass.tolist(),
            # 'tail_center': tail_center.tolist(),
            # 'axis_direction': billet_x_axis_unit_vector.tolist(),
            'principal_coordinate_system': local_coordinate_system.tolist(),
            'left_tail_barrel_length': tail_lengths[0].item(),
            'right_tail_barrel_length': tail_lengths[1].item(),
            'length_excluding_tail_barrels': length_excluding_tail_barrels.item(),
            'bounds_excluding_tail_barrels': internal_tail_bounds.tolist(),
            '3d_dimensions': mesh_dim.tolist(),

            'elements_edges': {
                'min': np.amin(length_of_edges['3d']).item(),
                'max': np.amax(length_of_edges['3d']).item(),
                'average': np.average(length_of_edges['3d']).item(),
                'std': np.std(length_of_edges['3d']).item(),

                'xy_min': np.amin(length_of_edges['xy']).item(),
                'xy_max': np.amax(length_of_edges['xy']).item(),
                'xy_average': np.average(length_of_edges['xy']).item(),
                'xy_std': np.std(length_of_edges['xy']).item(),

                'yz_min': np.amin(length_of_edges['yz']).item(),
                'yz_max': np.amax(length_of_edges['yz']).item(),
                'yz_average': np.average(length_of_edges['yz']).item(),
                'yz_std': np.std(length_of_edges['yz']).item(),

                'xz_min': np.amin(length_of_edges['xz']).item(),
                'xz_max': np.amax(length_of_edges['xz']).item(),
                'xz_average': np.average(length_of_edges['xz']).item(),
                'xz_std': np.std(length_of_edges['xz']).item()}
        }
    except Exception as _err:
        LOGGER.error(f"FAILED adding mesh parameters to 'parameters' with {type(_err).__name__}: {_err}")
        raise


def get_keyword(lines: list, line_index: list) -> [str, list]:
    try:
        _s = lines[line_index[0]]
        _string_args = _s.replace('\n', ' ').strip().split()
        if _string_args:
            _keyword = _string_args.pop(0)
            _args = _convert_to_int_and_float(_string_args)
            return _keyword, _args
        else:
            return '', []
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def _conversion_error_message(keyword_dict: dict) -> str:
    return (f"Following combination of KEYWORD parameters are unknown: "
            f"'dependency'='{keyword_dict['dependency']}', "
            f"'has_indices_column'='{keyword_dict['has_indices_column']}', "
            f"'value_type'='{keyword_dict['value_type']}'")


def _convert_to_dict(lines: list[str]) -> dict:

    output = dict()
    index = [0]

    try:
        node_count = get_node_count(lines)
        elem_count = _get_element_count(lines)
        lines_count = len(lines)

        while index[0] < lines_count:

            keyword, args = get_keyword(lines, index)

            if keyword and keyword in DEFORM_KEYWORDS:

                keyword: str
                starting_index_for_keyword = index[0]

                for keyword_dict in VARIABLES_VS_DEFORM_KEYWORD[keyword]:

                    keyword_dict: dict
                    index[0] = starting_index_for_keyword
                    name: str = keyword_dict['variable_name']
                    dependency: str = keyword_dict['dependency']
                    output_arg_index: bool = keyword_dict['output_arg_index']
                    is_double_line_keyword: bool = keyword_dict['is_double_line_keyword']
                    is_nodal = keyword_dict['var_type'] == 'nodal'
                    is_elemental = keyword_dict['var_type'] == 'element'
                    has_zero_rows_of_data = len(args) >= 2 and args[1] == 0

                    if dependency not in output:
                        output[dependency] = dict()
                    if _is_object(keyword_dict):
                        object_num: int = args[0]
                        if object_num not in output[dependency]:
                            output[dependency][object_num] = dict()
                    else:
                        object_num = -1

                    if dependency == 'global':
                        if is_double_line_keyword:
                            output[dependency][name] = _read_double_line(lines, index)
                        else:
                            output[dependency][name] = _read_single_line(args, output_arg_index)

                    elif keyword == 'FLWNET':
                        output[dependency][object_num][name] = _read_flownet_keyword(lines, index, args)

                    elif keyword in ('UNNAME', 'UENAME'):
                        output[dependency][object_num][name] = _read_object_multiple_name_lines(lines, index, args)

                    elif keyword == 'ECCTMP' and args[1] == 0:
                        pass

                    elif keyword == 'ECCTMP':
                        output[dependency][object_num][name] = _read_object_ecctmp(lines, index, args)

                    elif keyword == 'BCCDEF' and args[1] == 0:
                        pass

                    elif keyword == 'BCCDEF':
                        output[dependency][object_num][name] = _read_object_bccdef(lines, index, args)

                    elif keyword == 'ELMCON':
                        output[dependency][object_num][name] = _read_object_elmcon(lines, index, args)

                    elif _is_object(keyword_dict) and is_double_line_keyword:
                        output[dependency][object_num][name] = _read_double_line(lines, index)

                    elif _is_object(keyword_dict) and is_nodal:
                        if has_zero_rows_of_data:
                            output[dependency][object_num][name] = _read_object_empty_nodal(args, keyword_dict, node_count[object_num])
                        else:
                            output[dependency][object_num][name] = read_object_keyword(lines, index, args, keyword_dict, node_count[object_num])

                    elif _is_object(keyword_dict) and is_elemental:
                        if has_zero_rows_of_data:
                            output[dependency][object_num][name] = _read_object_empty_elem(args, keyword_dict, elem_count[object_num])
                        else:
                            output[dependency][object_num][name] = read_object_keyword(lines, index, args, keyword_dict, elem_count[object_num])

                    else:
                        raise KeyError(_conversion_error_message(keyword_dict))

            index[0] += 1
        return output
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def _get_element_count(lines: list[str]) -> dict:
    try:
        keyword_lines_indices = find_pattern_in_list(lines,
                                                     pattern='ELMCON       1   27630       4',
                                                     pattern_indices=[0],
                                                     starting_line=0)
        data_rows_count_per_object = {}
        for i in keyword_lines_indices:
            _, args = get_keyword(lines, [i])
            object_num = args[0]
            data_rows_count = args[1]
            data_rows_count_per_object[object_num] = data_rows_count
        return data_rows_count_per_object
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def get_node_count(lines: list[str]) -> dict:
    try:
        keyword_lines_indices = find_pattern_in_list(lines,
                                                     pattern='RZ           1    0',
                                                     pattern_indices=[0],
                                                     starting_line=0)
        data_rows_count_per_object = {}
        for i in keyword_lines_indices:
            _, args = get_keyword(lines, [i])
            object_num = args[0]
            data_rows_count = args[1]
            data_rows_count_per_object[object_num] = data_rows_count
        return data_rows_count_per_object
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def _is_object(keyword_dict):
    return keyword_dict['dependency'] in ('materials', 'objects')


def _unwrap_array_rows(lines: list[str]):

    index = [0]
    keywords = ('STRESS', 'STNCMP', 'USRNOD', 'USRELM')

    try:
        while index[0] < len(lines):
            keyword = lines[index[0]].lstrip()[:6]
            if keyword in keywords:
                _, args = get_keyword(lines, index)
                row_count = args[1]
                if row_count > 0:
                    index[0] += 1

                    is_first_line_starts_with_1 = lines[index[0]].lstrip().startswith("1 ")
                    is_second_line_starts_with_2 = lines[index[0] + 1].lstrip().startswith("2 ")
                    if is_first_line_starts_with_1 and not is_second_line_starts_with_2:
                        row_numer = 1
                        while row_numer <= row_count:
                            line = lines.pop(index[0] + 1)
                            lines[index[0]] += line
                            index[0] += 1
                            row_numer += 1

            index[0] += 1

    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def find_all_faces(elements):
    try:
        faces_indices = np.array([[0, 1, 2], [0, 2, 3], [0, 3, 1], [1, 3, 2]]).reshape(1, 12)
        all_faces = np.take(elements, faces_indices, axis=1).reshape(elements.size, 3)
        element_numbers_for_all_faces = np.take(
            np.arange(elements.shape[0]).reshape(elements.shape[0], 1),
            np.zeros((1, 4), dtype='int8'),
            axis=1).reshape(elements.size, 1)
        return all_faces, element_numbers_for_all_faces
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def pick_up_surface_faces_only(all_faces, element_numbers_for_all_faces):
    try:
        all_faces_str = np.sort(all_faces, axis=1).astype('str')
        hash_of_faces = np.apply_along_axis(func1d=','.join, axis=1, arr=all_faces_str)
        _, indices, occurrence_count = np.unique(hash_of_faces, return_index=True, return_counts=True)
        indices_of_surface_faces = indices[occurrence_count == 1]
        _faces, _ele = all_faces[indices_of_surface_faces], element_numbers_for_all_faces[indices_of_surface_faces]
        return _faces, _ele
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def _extract_surface_from_3d_mesh(obj_data):
    if 'elements' not in obj_data:
        return

    try:
        all_faces, elements_for_all_faces = find_all_faces(obj_data['elements'])
        surface_faces, surface_elements = pick_up_surface_faces_only(all_faces, elements_for_all_faces)
        pd_surface_faces = pd.DataFrame(np.hstack((surface_elements, surface_faces)),
                                        columns=('element_number', 'node_number_1', 'node_number_2', 'node_number_3'))
        surface_nodes = np.unique(surface_faces.ravel())
        obj_data |= {
            'surface_nodes': surface_nodes,
            'surface_faces': pd_surface_faces}

    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def smb_friendly_read_file(filepath: str) -> list[str]:
    try:
        """
         Reads a text file from a local or SMB network path and returns its lines as a list.

         Args:
             filepath (str): The path to the file. It can be a local path or an SMB path 
                             (e.g., 'smb://server/share/path/to/file.txt').

         Returns:
             List[str]: A list of lines from the file.
         """
        max_attempts_count = 5
        attempts_cycle_time = 30.0

        # Remove 'smb://' and replace '/' with '\\'
        path = '\\\\' + filepath[6:].replace('/', '\\') if filepath.startswith('smb://') else filepath

        # Define SMB prefixes to identify network paths
        smb_prefixes = ('\\\\', '//', )

        for i in range(1, max_attempts_count + 1):
            try:
                if filepath.startswith(smb_prefixes):
                    with smbclient.open_file(path, mode='r', encoding='utf-8') as file:
                        content = file.read()
                else:
                    with open(filepath, mode='r', encoding='utf-8') as file:
                        content = file.read()

            except Exception as _err:
                is_wait_before_next_attempt = (attempts_cycle_time > 0) and (i < max_attempts_count)
                time_message = (
                    f" Wait for {attempts_cycle_time} sec before next reading attempt."
                    if is_wait_before_next_attempt
                    else "")
                LOGGER.warning(
                    f"Read KEY file {path} failed at attempt {i}/{max_attempts_count} "
                    f"with {type(_err).__name__}: {_err}.{time_message}")
                if is_wait_before_next_attempt:
                    time.sleep(attempts_cycle_time)

        # Split the content into lines and return
        return content.splitlines()
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def read_deform_keyfile(filepath: str) -> dict:
    try:
        lines = smb_friendly_read_file(filepath)

        [lines.pop(_i) for _i in range(-1, -1, -1) if not lines[_i].strip()]
        _unwrap_array_rows(lines)
        data = _convert_to_dict(lines)

        for obj_data in data['objects'].values():
            _add_surface_variable(obj_data)
            _calculate_stress_tensor_variables(data)
            _calculate_strain_tensor_variables(data)
            _separate_user_nodal(obj_data)
            _separate_user_element(obj_data)
            _add_mesh_measurements(obj_data)
            _extract_surface_from_3d_mesh(obj_data)
            # _add_principal_coordinate_system_based_on_cross_sections(obj_data)
        return data
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise
