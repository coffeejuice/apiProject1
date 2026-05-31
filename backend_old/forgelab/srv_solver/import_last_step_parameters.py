import logging
import itertools
import numpy as np

from forgelab.srv_solver.pre_functions import find_first_pattern_in_list


LOGGER = logging.getLogger(__name__)


def import_billet_parameters_from_last_step(lines) -> dict:
    case_msg = f"FAILED func 'import_billet_parameters_from_last_step'"
    try:
        result = {
            'nodes': read_table(
                lines=lines,
                pattern='RZ           1    5533',
                pattern_indices=[0],
                pattern_value_index=2,
                type_pattern=['', 'float']),

            'elements': -1 + read_table(
                lines=lines,
                pattern='ELMCON       1   25096       4',
                pattern_indices=[0],
                pattern_value_index=2,
                type_pattern=['', 'int']),

            'nodal_temperature': read_table(
                lines=lines,
                pattern='NDTMP        1    5574    0.0000000000E+000',
                pattern_indices=[0, 1],
                pattern_value_index=2,
                type_pattern=['', 'float']),

            'elemental_strain': read_table(
                lines=lines,
                pattern='USRELM       1   25096    0.0000000000E+000       2',
                pattern_indices=[0],
                pattern_value_index=2,
                type_pattern=['', 'float']),

            'def_bcc_nodes': read_table(
                lines=lines,
                pattern='BCCDEF       1     472       0',
                pattern_indices=[0],
                pattern_value_index=2,
                type_pattern=['int']),

            'heat_bcc_faces': read_table(
                lines=lines,
                pattern='ECCTMP       1     126       0',
                pattern_indices=[0],
                pattern_value_index=2,
                type_pattern=['int'])}

    except KeyError as _err:
        LOGGER.error(f"{case_msg} with KeyError: {_err}")
    except Exception as _err:
        LOGGER.error(f"{case_msg} with Some Error: {_err}")
    else:
        return result
    raise RuntimeError(case_msg)


def assert_surface_faces_form_closed_surface(surface_faces):
    case_msg = f"FAILED func 'assert_surface_faces_form_closed_surface'"
    try:
        surface_faces = surface_faces.tolist()
        common_edges = []
        surface_is_closed = True
        for element_i in surface_faces:
            three_faces = [element_i]
            edges_i = [
                [element_i[0], element_i[1]],
                [element_i[1], element_i[2]],
                [element_i[3], element_i[0]]]

            for element_j in surface_faces:
                edges_j = [
                    [element_j[0], element_j[1]],
                    [element_j[1], element_j[2]],
                    [element_j[3], element_j[0]]]

                three_faces.extend(
                    element_j for edge_i, edge_j in itertools.product(edges_i, edges_j) if set(edge_i) == set(edge_j))

            common_edges.append(three_faces)
            if len(three_faces) != 3:
                surface_is_closed = False
    except KeyError as _err:
        LOGGER.error(f"{case_msg} with KeyError: {_err}")
    except Exception as _err:
        LOGGER.error(f"{case_msg} with Some Error: {_err}")
    else:
        return surface_is_closed
    raise RuntimeError(case_msg)


def read_table(
        lines, pattern='', pattern_indices=None, pattern_value_index=None, type_pattern: list = None
) -> np.ndarray:
    case_msg = f"FAILED func 'read_table'"
    try:
        ind_nodes = find_first_pattern_in_list(lines, pattern, pattern_indices, 0)
        if ind_nodes is None:
            return np.empty((0, 0))
        nuber_of_table_lines = int(lines[ind_nodes].split()[pattern_value_index])
        table_lines = lines[ind_nodes + 1: ind_nodes + 1 + nuber_of_table_lines]
        result = np.array(lines_to_values(table_lines, type_pattern))
    except KeyError as _err:
        LOGGER.error(f"{case_msg} with KeyError: {_err}")
    except Exception as _err:
        LOGGER.error(f"{case_msg} with Some Error: {_err}")
    else:
        return result
    raise RuntimeError(case_msg)


def lines_to_values(lines, type_pattern):
    case_msg = f"FAILED func 'lines_to_values'"
    try:
        lines = [line.split() for line in lines]
        table = []
        for line in lines:
            values_list = []
            for index, value_string in enumerate(line):
                selected_type = select_type(type_pattern, index)
                if selected_type == 'int':
                    values_list.append(int(value_string))
                elif selected_type == 'float':
                    values_list.append(float(value_string))
            table.append(values_list)
    except KeyError as _err:
        LOGGER.error(f"{case_msg} with KeyError: {_err}")
    except Exception as _err:
        LOGGER.error(f"{case_msg} with Some Error: {_err}")
    else:
        return table
    raise RuntimeError(case_msg)


def write_table(lines=None, table: np.ndarray = None, add_index_column_to_table: bool = True,
                pattern: str = None, pattern_indices: list = None, pattern_value_index: int = None,
                pattern_format: str = None) -> list:
    case_msg = f"FAILED func 'write_table'"
    try:
        result = []
        index = find_first_pattern_in_list(lines, pattern, pattern_indices, 0)
        if index:
            old_table_length = int(lines[index].split()[pattern_value_index])
            new_table_length = table.shape[0]
            if old_table_length == new_table_length:
                _l = values_to_lines(table, add_index_column_to_table, pattern_format)
                lines[index + 1: index + 1 + old_table_length] = _l
                result = lines
    except KeyError as _err:
        LOGGER.error(f"{case_msg} with KeyError: {_err}")
    except Exception as _err:
        LOGGER.error(f"{case_msg} with Some Error: {_err}")
    else:
        return result
    raise RuntimeError(case_msg)


def values_to_lines(values: np.ndarray, add_index_column_to_table: bool = True, pattern_format: str = None) -> list:
    case_msg = "FAILED func 'values_to_lines'"
    try:
        lines = []
        values_length = values.shape[0]

        index_column = np.arange(1, 1 + values_length, dtype='uint32') if add_index_column_to_table else None

        for i in range(values_length):
            table_row_as_list = values[i].tolist()
            list_of_values = [index_column[i], *table_row_as_list] if add_index_column_to_table else table_row_as_list
            lines.append(pattern_format.format(*list_of_values))
    except KeyError as _err:
        LOGGER.error(f"{case_msg} with KeyError: {_err}")
    except Exception as _err:
        LOGGER.error(f"{case_msg} with Some Error: {_err}")
    else:
        return lines
    raise RuntimeError(case_msg)


def select_type(type_pattern, index):
    case_msg = f"FAILED func 'select_type'"
    try:
        is_exceeds_length = index > len(type_pattern) - 1
        result = type_pattern[-1] if is_exceeds_length else type_pattern[index]
    except KeyError as _err:
        LOGGER.error(f"{case_msg} with KeyError: {_err}")
    except Exception as _err:
        LOGGER.error(f"{case_msg} with Some Error: {_err}")
    else:
        return result
    raise RuntimeError(case_msg)
