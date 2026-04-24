import logging
import os
import shutil
from re import split
from subprocess import run, PIPE
import numpy as np
import pandas as pd

from forgelab.common.shapely_2d_funcs import rotate_basis
from forgelab.config import config
from forgelab.common.read_deform_keyfile import \
    VARIABLES, VARIABLES_VS_DEFORM_KEYWORD, get_node_count, get_keyword, read_object_keyword
from forgelab.common.file_operations import sub_operation_abs_path


LOGGER = logging.getLogger(__name__)


def list_sim_dirs(_path: str) -> list:
    """Returns list of Dirs in Path"""

    # def int_or_none(_str: str) -> (int, None):
    #     """Get string, return signed integer or None"""
    #     try:
    #         if _str.startswith('-'):
    #             _str = _str[1:]
    #             sign = -1
    #         else:
    #             sign = 1
    #         if _str.isdigit():
    #             return sign * int(_str)
    #         return None
    #     except Exception as _e:
    #         LOGGER.warning(f"{type(_e).__name__}: {_e}")
    #         raise
    #
    # try:
    #     if os.path.exists(_path):
    #         all_dirs = [_file for _file in os.listdir(_path) if os.path.isdir(os.path.join(_path, _file))]
    #         dirs_starts_with_digit = [_dir for _dir in all_dirs if isinstance(int_or_none(_dir.split('_')[0]), int)]
    #         result = sorted(dirs_starts_with_digit)
    #     else:
    #         result = []
    #     return result
    # except Exception as _err:
    #     LOGGER.warning(f"{type(_err).__name__}: {_err}")
    #     raise
    pass


def remove_old_operation_files(operation_path):
    try:
        if os.path.exists(operation_path):
            shutil.rmtree(operation_path, ignore_errors=True)
            LOGGER.info(f"Removed dir '{operation_path}'")
    except Exception as _err:
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        raise


def copy_operation_template(_param: dict):
    try:
        template_filename = _param['operation']['template_name'] + '.zip'
        data_files_operations = config.server['data_files_operations']
        destination_path: str = sub_operation_abs_path(_param)
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise
    try:
        source_file_path = str(os.path.join(data_files_operations, template_filename))
        shutil.unpack_archive(source_file_path, destination_path)
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise RuntimeError(f"FAILED for {destination_path = }")


def copy_die_template(_param: dict, row: dict):
    dies = {
        'top_die_id': 'Object00002.KEY',
        'bottom_die_id': 'Object00003.KEY'}
    try:
        data_files_dies: str = config.server['data_files_dies']
        sub_operation_path = sub_operation_abs_path(_param)
        dst_dir = os.path.join(sub_operation_path, 'objects')
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise

    for id_key, key_file in dies.items():
        try:
            die_id = row[id_key]
            die_template_file_name: str = config.lib['die'].loc[die_id]['die_template_file_name']
            template_file_path = os.path.join(data_files_dies, die_template_file_name)
        except Exception as _err:
            LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
            raise RuntimeError(f"FAILED for {id_key = } and KEY-file {key_file = }")
        try:
            silent_remove(os.path.join(dst_dir, key_file))
            shutil.unpack_archive(template_file_path, dst_dir, 'zip')
        except Exception as _err:
            LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
            raise RuntimeError(f"FAILED copying '{template_file_path}' to '{dst_dir}' for 'die_id'={die_id} ")


def silent_remove(filename):
    try:
        if os.path.isfile(filename):
            os.remove(filename)
            LOGGER.info(f"Removed file '{filename}'")
    except Exception as _err:
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        raise RuntimeError(f"FAILED removing file {filename}")


def import_billet_from_previous_sub_operation(_param: dict):
    try:
        local_dir: str = config.server['local_dir']

        previous_extract_rel_path: str = _param['previous_operation']['billet_file_sub_operation_extract_relative_path']
        src_file = os.path.join(local_dir, previous_extract_rel_path)

        sub_operation_relative_initial_billet_file_path: str = _param['operation']['sub_operation_relative_initial_billet_file_path']
        dst_file = os.path.join(local_dir, sub_operation_relative_initial_billet_file_path)
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise
    try:
        shutil.copy(src_file, dst_file)
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise RuntimeError(f"FAILED copying {src_file = } to {dst_file = }")


def convert_mst_file_to_key_file(sub_operation_path, template_name):
    """
    Load DEFORM MST-file, find SIMULATION 1 operation and import it.
    :return: txt
    """
    try:
        mst_filepath = os.path.join(sub_operation_path, template_name + '.mst')
        if not os.path.isfile(mst_filepath):
            return
        with open(mst_filepath, 'r', encoding="UTF-8") as data:
            _list_of_strings = data.readlines()
        if not _list_of_strings:
            return
        start_reading = False
        key_file_txt = ""
    except Exception as _err:
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        raise

    try:
        while _list_of_strings:
            string = _list_of_strings.pop(0)
            try:
                key_list = string.strip().split()
                if string.startswith("SIMULATION") and key_list[1] == "1":
                    start_reading = True
                    continue
                if string.startswith("SIMULATION") and key_list[1] == "2":
                    break
                if string.startswith("*!SIMTYP"):
                    continue
                if start_reading:
                    key_file_txt += string
            except Exception as _err:
                LOGGER.error(_err)
                raise RuntimeError(f"FAILED at line '{string}'")
        filepath = os.path.join(sub_operation_path, f'{template_name}.KEY')
    except Exception as _err:
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        raise RuntimeError(f"FAILED modifying MST-file '{mst_filepath}'")
    try:
        # EXPORT Key-file
        with open(filepath, "w", encoding="UTF-8") as key_file:
            key_file.write(key_file_txt)
    except Exception as _err:
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        raise RuntimeError(f"FAILED export KEY-file '{filepath}'")


def automatic_modification_of_parameters_in_files(files: dict, _param: dict):
    try:
        for file_properties in files.values():
            filepath = os.path.join(sub_operation_abs_path(_param), file_properties['file_path'])
            lines = read_lines_from_file(filepath)
            automatic_modification_of_parameters_in_lines(_param, file_properties, lines)
            write_list_of_strings_to_file(lines, filepath)
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise


def automatic_modification_of_parameters_in_lines(_param: dict, file_properties: dict, lines: list):
    try:
        for line_index, line in enumerate(lines):
            if not line.startswith("*"):
                if new_line := process_line(file_properties, line, _param):
                    lines[line_index] = new_line
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise


def modification_of_parameter_in_files_counting_spaces(files, _param):
    try:
        for file_properties in files.values():
            filepath = os.path.join(sub_operation_abs_path(_param), file_properties['file_path'])
            list_of_strings = read_lines_from_file(filepath)
            for line_index, line in enumerate(list_of_strings):
                if not line.startswith("*"):
                    if new_line := process_line_counting_spaces(file_properties, line, _param):
                        list_of_strings[line_index] = new_line
            write_list_of_strings_to_file(list_of_strings, filepath)
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise


def read_lines_from_file(*args) -> list[str]:
    try:
        with open(os.path.join(*args), "r", encoding="UTF-8") as file:
            list_of_strings = file.readlines()
        return list_of_strings
    except Exception as _err:
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        raise


def process_line(file_properties: dict, line: str, _param: dict) -> str:
    try:
        line_is_changed = False
        line_list = line.split()
        for parameter_name, value in file_properties['parameters'].items():
            key_positions: list = value['k']
            if max(key_positions) + 1 <= len(line_list):
                _s: str = value['s']
                template = _s.split()
                if [template[i].lower() for i in key_positions] == [line_list[i].lower() for i in key_positions]:
                    line_is_changed = True
                    line = modify_line(line, _param, parameter_name, value)
        return line if line_is_changed else ''
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise


def process_line_counting_spaces(file_properties: dict, line: str, _param: dict):
    try:
        line_is_changed = False
        line_list = line.split()
        for parameter_name, value in file_properties['parameters'].items():
            key_positions: list = value['k']
            if max(key_positions) + 1 <= len(line_list):
                _s: str = value['s']
                template = _s.split()
                if [template[i].lower() for i in key_positions] == [line_list[i].lower() for i in key_positions]:
                    line_is_changed = True
                    line = modify_line_counting_spaces(line, _param, parameter_name, value)
        return line if line_is_changed else ''
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise


def modify_line(line, _param, parameter_name, value):
    for key in ('s', 'k', 'n', 'f'):
        assert key in value.keys(), \
            f"Missing '{key}' Key in 'value' input argument for {parameter_name = } and {value = }"
    assert parameter_name in _param['operation'].keys(), \
        f"Missing '{parameter_name}' Key in param['operations']"

    try:
        parameter_position = value['n']
        parameter_value = _param['operation'][parameter_name]
        words = split_line(line, r"(\s+)")
        parameter_format = value['f']
        string_parameter = parameter_format.format(parameter_value)
        new_words = split_line(string_parameter, r"(\s+)")
        i = parameter_position * 2
        if len(words) == 2:
            words[0] = new_words[0]
        else:
            words[i - 1], words[i] = new_words[0], new_words[1]
        return "".join(words)
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise


def modify_line_counting_spaces(line, _param, parameter_name, value):
    try:
        assert "s" in value.keys()
        assert "k" in value.keys()
        assert "n" in value.keys()
        assert "f" in value.keys()
        parameter_position = value['n']
        parameter_value = _param['operation'][parameter_name]
        words = split_line(line, r"(\s+)")
        parameter_format = value['f']
        string_parameter = parameter_format.format(parameter_value)
        new_words = split_line(string_parameter, r"(\s+)")
        i = parameter_position
        words[i - 1], words[i] = new_words[0], new_words[1]
        return "".join(words)
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise


def split_line(line: str, string_format: str) -> list:
    try:
        words = split(string_format, line)
        for index, string in enumerate(words):
            if string == '':
                words.pop(index)
        return words
    except Exception as _err:
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        raise


def change_environment_temperature_in_key_file(_param: dict, relative_filepath: str) -> None:
    try:
        temp_1 = _param['operation']['environment_temperature_1']
        temp_2 = _param['operation']['environment_temperature_2']
        duration = _param['operation']['process_duration']
        filepath = os.path.join(sub_operation_abs_path(_param), relative_filepath)
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise
    try:
        input_lines = read_lines_from_file(filepath)
        key_line_index = find_pattern_in_list(input_lines, 'ENVTMP', [0], 0)[0]
        new_lines = [
            f"    {0.0:>-16.10E}    {temp_1:>-16.10E}\n"
            f"    {duration:>-16.10E}    {temp_2:>-16.10E}\n"]
        output_lines = input_lines[:key_line_index + 1] + new_lines + input_lines[key_line_index + 3:]
        write_list_of_strings_to_file(output_lines, filepath)
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise


def change_operations_names_in_mst_or_key_file(_param: dict, relative_filepath: str) -> None:
    try:
        _execution_order = _param['project']['execution_order']
        operation_name = _param['table'][_execution_order]['operation_dir_name']
        simulations_names_list = _param['operation']['simulations_names_list'].copy()
        filepath = os.path.join(sub_operation_abs_path(_param), relative_filepath)
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise
    try:
        lines = read_lines_from_file(filepath)
        line_indices = find_pattern_in_list(lines, 'OPRNAM', [0], 0)

        for i in line_indices:
            lines[i + 1] = f'{operation_name}\n'

        line_indices = find_pattern_in_list(lines, 'SIMNAM', [0], 0)
        number_of_names = min(len(line_indices), len(simulations_names_list))

        while number_of_names:
            i = line_indices.pop(0)
            lines[i + 1] = f'{simulations_names_list.pop(0)}\n'
            number_of_names -= 1

        write_list_of_strings_to_file(lines, filepath)
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise


def automatic_modification_of_values_in_moproj_file(file_properties, _param: dict):
    def __split_strip_template_commands():
        try:
            return {
                _key: [s if i == 1 else s.strip() for i, s in enumerate(split_moproj_line(_val))]
                for _key, _val
                in file_properties['parameters'].items()}
        except Exception as _e:
            LOGGER.warning(f"{type(_e).__name__}: {_e}")
            raise

    def __modify_values_in_lines():
        try:
            for i, line in enumerate(lines):
                line_pieces = split_moproj_line(line)
                if all(line_pieces):
                    starting_key = line_pieces[0].strip()
                    ending_key = line_pieces[2].strip()
                    for _key, _pieces in templates_pieces.items():
                        if all((starting_key == _pieces[0],  # Starting keyword
                                line_pieces[1] == _pieces[1],  # Value
                                ending_key == _pieces[2])):  # Ending keyword
                            new_value = _param['operation'][_key]
                            if starting_key == '<Value>':
                                split_value_string = line_pieces[1].split()
                                extension = f' {split_value_string[1]}' if len(split_value_string) > 1 else ''
                                lines[i] = f'{line_pieces[0]}{new_value:.6f}{extension}{line_pieces[2]}'
                            elif starting_key == '<Keyword>':
                                keyword = line_pieces[1].split()[0]
                                lines[i] = f'{line_pieces[0]}{keyword}      {new_value:.5f}{line_pieces[2]}'
                            elif starting_key == '<StartStepNo>':
                                lines[i] = f'{line_pieces[0]}{new_value:-d}{line_pieces[2]}'
            return lines
        except Exception as _e:
            LOGGER.warning(f"{type(_e).__name__}: {_e}")
            raise

    try:
        templates_pieces = __split_strip_template_commands()
        filepath = os.path.join(sub_operation_abs_path(_param), file_properties['file_path'])
        lines = read_lines_from_file(filepath)
        lines = __modify_values_in_lines()
        write_list_of_strings_to_file(lines, filepath)
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise


def split_moproj_line(line):
    try:
        i = line.find('>')
        j = line.find('<', i + 1)

        if i == -1 and j == -1:
            return ['', '', '']

        first_part = line[:i + 1]
        value_string = line[i + 1: j]
        last_part = line[j:]
        return [first_part, value_string, last_part]
    except Exception as _err:
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        raise


def write_list_of_strings_to_file(list_of_strings: list, *args):
    try:
        with open(os.path.join(*args), "w", encoding="UTF-8") as file:
            file.writelines(list_of_strings)
    except Exception as _err:
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        raise


def convert_key_to_db(_param: dict):
    """Convert a KEY-file to a database"""
    try:
        deform_installation_path = config.server['deform_installation_path']
        sub_operation_path = sub_operation_abs_path(_param)
        template_name = _param['operation']['template_name']
        key_file = template_name + ".KEY"
        def_pre_path = os.path.join(deform_installation_path, "3D", "DEF_PRE.EXE")
        #
        commands = f"<CR>\n2\n1\n{key_file}\n<CR>\nE\nE\nY\n<CR>\n"
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise
    try:
        _i, try_count = 1, 3
        while True:
            result = run(
                def_pre_path,
                input=commands,
                encoding='ascii',
                check=False,
                text=True,
                stdout=PIPE,
                cwd=sub_operation_path)

            if is_def_pre_success(result.stdout):
                break
            else:
                LOGGER.warning(f"{_i}/{try_count} DEF_PRE.EXE failed converted '{key_file}' to "
                               f"'{template_name}.DB' with command '{commands}'")
                _i += 1
                assert _i <= try_count, f"DEF_PRE.EXE finally failed after {try_count} attempts."
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise RuntimeError(f"FAILED converting '{key_file}' to '{template_name}.DB'")


def pattern_exists(line: list, pattern: list) -> bool:
    # Check if 'line' is empty or shorter than 'pattern'
    try:
        if not line or len(line) < len(pattern):
            return False

        # Search for the sequence 'pattern' in 'line'
        len_pattern = len(pattern)
        for i in range(len(line) - len_pattern + 1):
            if line[i:i + len_pattern] == pattern:
                return True
        return False
    except Exception as _err:
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        raise


def is_def_pre_success(_stdout: str) -> bool:
    """Analyse stdout of 'DEF_PRE.EXE' for errors and return True if it is OK"""
    error_markers = [['error:'],
                     ['deform', 'database', 'can', 'not', 'be', 'generated']
                     ]
    success_markers = [['info', ':', 'deform', 'database', 'generated']
                       ]
    is_success = True
    try:
        for line in _stdout.splitlines():
            line_list = line.lower().split()
            if any([pattern_exists(line_list, marker) for marker in success_markers]):
                LOGGER.info(f"DEF_PRE.EXE stdout: {line}")
            if any([pattern_exists(line_list, marker) for marker in error_markers]):
                LOGGER.error(f"DEF_PRE.EXE stdout: {line}")
                is_success = False
        return is_success
    except Exception as _err:
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        raise


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
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        raise


def find_first_pattern_in_list(list_of_strings: list,
                               pattern: str,
                               pattern_indices: list,
                               starting_line: int
                               ) -> None | int:
    try:
        line_indices = find_pattern_in_list(list_of_strings, pattern, pattern_indices, starting_line)
        if not line_indices:
            result = None
        else:
            result = int(line_indices[0])
        return result
    except Exception as _err:
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        raise


def modify_value_in_list_of_strings(
        list_of_strings, string_pattern, string_splitter, pattern_indices, modified_member_index, new_value,
        new_value_format):
    try:
        template = split_line(f"{string_pattern}\n", string_splitter)
        line_index = find_pattern_in_list(list_of_strings, string_pattern, pattern_indices, 0)
        template[modified_member_index] = new_value_format.format(new_value)
        assert len(line_index) == 1, f"There must be only 1 member in the list, but list content is {line_index}"
        list_of_strings[line_index[0]] = "".join(template)
        return list_of_strings
    except Exception as _err:
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        raise


def export_billet_and_parameters_from_db_last_step(_param: dict):
    try:
        sub_operation_path = sub_operation_abs_path(_param)
        last_step_key_file_name = 'EXPORT_LAST_STEP'
        billet_export_path = os.path.join(sub_operation_path, config.server['billet_extract_dir_name'])
        billet_export_filename = 'Object00001'
        export_last_step_from_db_to_key(_param, last_step_key_file_name)
        lines = __read_last_step_key_file(sub_operation_path, last_step_key_file_name)
        export_billet_from_key(lines, billet_export_path, billet_export_filename)
        get_step_number(lines, _param)
        get_mesh_number(lines, _param)
        get_global_time(lines, _param)
        # get_flow_net_center(lines, row, param)
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise RuntimeError("FAILED exporting billet from DB")


def export_last_step_from_db_to_key(_param: dict, export_key_name):
    try:
        pvid = _param['project']['process_version_id']
        eo = _param['project']['execution_order']

        sub_operation_path: str = sub_operation_abs_path(_param)
        deform_installation_path: str = config.server['deform_installation_path']
        template_name: str = _param['operation']['template_name']
        db_file = template_name + ".DB"
        key_file = export_key_name + ".KEY"

        db_file = os.path.join(sub_operation_path, db_file)
        def_pre_path = os.path.join(deform_installation_path, "3D", "DEF_PRE.EXE")
        commands = f"<CR>\n2\n2\n{db_file}\n\n<CR>\nE\n8\n{key_file}\nE\nY\n"
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise
    try:
        assert os.path.exists(db_file), f"File '{db_file}' does not exist."
        result = run(
            def_pre_path,
            input=commands,
            encoding='ascii',
            check=False,
            text=True,
            stdout=PIPE,
            cwd=sub_operation_path)

        stdout_lines = result.stdout.splitlines()
        target_line = "info: new keyword file generated"
        is_error = True
        for _l in stdout_lines:
            if target_line in _l.lower():
                is_error = False
                break

        if is_error:
            for _l in stdout_lines:
                LOGGER.error(f"pvid={pvid} eo={eo} 'DEF_PRE.EXE': {_l}")
            raise AssertionError(f"'DEF_PRE.EXE' failed to generate '{key_file}'")
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise RuntimeError(f"FAILED running 'DEF_PRE.EXE' with {db_file} to {key_file}")


def export_billet_from_key(lines, billet_export_path, billet_export_key_name):
    try:
        billet_lines = cut_key_file(lines)
        export_billet(billet_export_key_name, billet_export_path, billet_lines)
    except Exception as _err:
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        raise


def cut_key_file(lines):
    try:
        line_1_indices = find_pattern_in_list(lines,
                                              "*  Data for Object #     1",
                                              list(range(6)),
                                              0)
        line_2_indices = find_pattern_in_list(lines,
                                              "*  Data for Object #     2",
                                              list(range(6)),
                                              line_1_indices[0] + 1)
        if not line_2_indices:
            line_2_indices = find_pattern_in_list(
                lines, "*  Inter-Object Data", [1, 2], line_1_indices[0] + 1)
        assert len(line_1_indices) == 1 and len(line_2_indices) == 1
        return lines[(line_1_indices[0] - 1):(line_2_indices[0] - 1)]
    except Exception as _err:
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        raise


def export_billet(billet_export_key_name, billet_export_path, billet_lines):
    err_msg = "FAILED func 'export_billet'"
    try:
        key_file = billet_export_key_name + ".KEY"
        os.makedirs(billet_export_path)
        export_filepath = os.path.join(billet_export_path, key_file)
        write_list_of_strings_to_file(billet_lines, export_filepath)
    except FileExistsError:
        LOGGER.error(f"{err_msg} with FileExistsError: Folder '{billet_export_path}' already exists")
        raise
    except Exception as _err:
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        raise


def __read_last_step_key_file(input_path, input_key_name):
    try:
        key_file = input_key_name + ".KEY"
        input_filepath = os.path.join(input_path, key_file)
        assert os.path.exists(input_filepath), f"Can't find KEY-file: {input_filepath}"
        return read_lines_from_file(input_filepath)
    except Exception as _err:
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        raise


def get_step_number(lines: list[str], _param: dict):
    try:
        line_indices = find_pattern_in_list(lines, 'NSTART      21', [0], 0)
        if len(line_indices) != 1:
            _param['operation']['last_step_number'] = 0
            return
        line_index = line_indices[0]
        #
        string_value = lines[line_index].split()[1]
        _param['operation']['last_step_number'] = int(string_value)
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise


def get_mesh_number(lines: list[str], _param: dict):
    try:
        line_indices = find_pattern_in_list(lines, 'MESHNO       1', [0], 0)
        if len(line_indices) != 1:
            return
        line_index = line_indices[0]
        #
        string_value = lines[line_index].split()[1]
        _param['operation']['mesh_number'] = int(string_value)
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise


def get_global_time(lines: list[str], _param: dict):
    try:
        line_indices = find_pattern_in_list(
            lines,
            'TNOW      6.0000000000E+001    6.0000000000E+001       1    0.0000000000E+000',
            [0],
            0)
        if len(line_indices) != 1:
            _param['operation']['global_time'] = 0.0
            return
        line_index = line_indices[0]
        #
        string_value = lines[line_index].split()[1]
        _param['operation']['global_time'] = float(string_value)
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise


def get_flow_net_center(lines: list[str], row, _param: dict):
    try:
        line_indices = find_pattern_in_list(
            lines,
            'FLWNET       1       1       5       4',
            [0, 1],
            0)
        if len(line_indices) != 1:
            _param['operation']['flow_net_center'] = [None, None, None]
            return
        line_index = line_indices[0]
        #
        list_of_strings = lines[line_index].split()
        number_of_points = int(list_of_strings[3])
        # number_of_triangles = int(list_of_strings[4])
        list_of_coordinates = []
        average_coordinates = []
        max_coordinates = []
        min_coordinates = []
        for i, line in enumerate(lines[line_index + 1: line_index + 1 + number_of_points]):
            coordinates = [float(string) for string in line.split()[1:]]
            list_of_coordinates.append(coordinates)
            if i != 0:
                average_coordinates = [average_coordinates[j] + coordinates[j] / number_of_points for j in range(3)]
                max_coordinates = [max(coordinates[j], max_coordinates[j]) for j in range(3)]
                min_coordinates = [min(coordinates[j], min_coordinates[j]) for j in range(3)]
            else:
                average_coordinates = [coordinates[j] for j in range(3)]
                max_coordinates = coordinates[:]
                min_coordinates = coordinates[:]
        dimensions = [max_coordinates[j] - min_coordinates[j] for j in range(3)]
        assert max(dimensions) < billet_thickness(row), 'Dimensions '
        _param['operation']['flow_net_center'] = average_coordinates
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise


def apply_new_material(_param: dict, row: dict):
    try:
        template_path = config.server['data_files_materials']
        material_id = row['material_id']
        material_path = config.lib['materials'].loc[material_id]['material_path']
        src_file = str(os.path.join(template_path, material_path))

        sup_op_path = sub_operation_abs_path(_param)
        dst_file = str(os.path.join(sup_op_path, 'Materials', 'Material00001.KEY'))
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise
    try:
        shutil.copyfile(src_file, dst_file)
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise RuntimeError(f"FAILED copying '{src_file}' to '{dst_file}'")


def get_material_file_path(templates_path: str, relative_material_path: str):
    materials_template_path = os.path.join(templates_path, "materials")
    assert os.path.exists(materials_template_path), \
        f"FAILED func 'get_material_file_path' with Material template path '{materials_template_path}' does not exists."
    return os.path.join(materials_template_path, relative_material_path)


def step_control_for_heat_transfer(row):
    try:
        process_duration = row['operation_time']
    except Exception as _err:
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        raise

    if process_duration <= 1.0:
        initial_time_step = process_duration
        min_time_step = process_duration
        max_time_step = process_duration
    else:
        initial_time_step = 1.0
        min_time_step = 1.0
        max_time_step = 10.0
    max_temperature = 5.0
    return initial_time_step, min_time_step, max_time_step, max_temperature


def step_control_for_heat_transfer_input_process_duration(process_duration: float):
    if process_duration <= 1.0:
        initial_time_step = process_duration
        min_time_step = process_duration
        max_time_step = process_duration
    elif process_duration <= 1000.0:
        initial_time_step = 1.0
        min_time_step = 1.0
        max_time_step = 10.0
    else:
        initial_time_step = 1.0
        min_time_step = 1.0
        max_time_step = 50.0
    max_temperature = 5.0
    return initial_time_step, min_time_step, max_time_step, max_temperature


def modify_power_limit(_param: dict, row: dict, relative_filepath: str, template_string: str,
                       speed_scale_factor: float, total_dwell_time: float):
    try:
        filepath, part_1, part_3 = __split_file_above_string(relative_filepath,
                                                             _param,
                                                             template_string,
                                                             [0, 1])
        number_of_old_elements = int(part_3[0].split()[2])
        del part_3[:number_of_old_elements + 1]
        # Create Part_2
        # SPDLMT       2       7    0.0000000000E+000    0.0000000000E+000
        power_limit = config.lib['press_mode_power_limit'][row['press_mode_id']].copy()
        number_of_new_elements = len(power_limit)
        temp_string = modify_value_in_list_of_strings(
            [template_string], template_string, r"(\s+)", [0, 1], 4, number_of_new_elements, "{:d}")
        part_2 = modify_value_in_list_of_strings(
            temp_string, template_string, r"(\s+)", [0, 1], 8, total_dwell_time, "{:>-21.10E}")

        for i in range(number_of_new_elements):
            string = (
                f' {power_limit[i][0]:>-20.10E}'
                f' {power_limit[i][1] * speed_scale_factor:>-20.10E}\n')
            part_2.append(string)
        # Join Parts 1, 2 and 3
        part_1.extend(part_2)
        part_1.extend(part_3)
        write_list_of_strings_to_file(part_1, filepath)
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise


def transform_nodes_from_lcs1_to_lcs2(nodes: pd.DataFrame, lcs_1: np.ndarray, lcs_2: np.ndarray) -> pd.DataFrame:
    """
    Transform nodes from one local coordinate system to another
    :param nodes: DataFrame with nodes coordinates
    :param lcs_1: Local coordinate system 1
    :param lcs_2: Local coordinate system 2
    :return: DataFrame with transformed nodes
    """
    try:
        # Transform global coordinates to local coordinates
        origin = nodes.mean(axis=0)
        centered_nodes = (nodes - origin).to_numpy()

        # Transform points back to global system
        # If the matrix is a proper rotation matrix (consisting of orthonormal vectors), its inverse is its transpose.
        nodes_in_global_cs = centered_nodes @ lcs_1.T

        # Transform points from global to new local system
        nodes_in_new_cs = nodes_in_global_cs @ lcs_2

        # Convert back to DataFrame
        return pd.DataFrame(nodes_in_new_cs, columns=nodes.columns, index=nodes.index)
    except Exception as _err:
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        raise


def select_points_in_box(nodes: pd.DataFrame, bounds_list: list[np.array]) -> pd.Index:
    # Select points within the bounds in the local coordinate system
    result = pd.Index([])
    try:
        for bounds in bounds_list:
            within_bounds = nodes.apply(lambda row: np.all(row >= bounds[1]) and np.all(row <= bounds[0]), axis=1)

            # Filter the original DataFrame based on the selection
            result = result.union(nodes.loc[within_bounds].index)
        return result
    except Exception as _err:
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        raise


def read_table_to_pandas(lines: list[str], pattern: str, pattern_indices: list, pattern_value_index: int,
                         has_index_column: bool, data_type, column_names: list) -> pd.DataFrame:
    try:
        index = find_first_pattern_in_list(lines, pattern, pattern_indices, starting_line=0)

        if index is None:
            return pd.DataFrame(columns=column_names)

        keyword_line = lines[index]
        nuber_of_table_lines = int(keyword_line.split()[pattern_value_index])
        start_index = index + 1
        end_index = start_index + nuber_of_table_lines
        df = pd.DataFrame([_line.split() for _line in lines[start_index:end_index]], columns=column_names)
        if has_index_column:
            df.index = pd.Index(df[column_names[0]].astype(int))
            df.drop(columns=column_names[0], inplace=True)
        for col in df.columns:
            df[col] = df[col].astype(data_type)
        return df
    except Exception as _err:
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        raise


def remove_velocity_boundary_conditions(_param: dict, relative_filepath: str):
    try:
        template_string = "BCCDEF       1      80       0"

        filepath = os.path.join(sub_operation_abs_path(_param), relative_filepath)
        lines = read_lines_from_file(filepath)

        part_1, keyword_line, data_lines, part_3 = split_lines_by_keyword(lines,
                                                                          template_string,
                                                                          pattern_indices=[0, 1],
                                                                          starting_line=0)

        df = bccdef_lines_to_pd(data_lines)

        # Notes on bcx, bcy, bcz codes:
        # 0 nodal force (This is the Default value for all nodes )
        # 1 nodal velocity
        # 2 nodal traction
        # 3 nodal movement control
        # 4 beginning surface
        # 5 ending surface
        # 6 symmetry plane
        # 7 rotational symmetry (master)
        # 8 rotational symmetry (slave)
        # -n nodal contact with object n
        # -(200+n) Sticking condition with object n

        # Extract nodes having Contact BC
        contact_df = df.where(df.lt(0).to_numpy(), other=pd.NA).dropna(how='all').fillna(0).astype(pd.Int64Dtype())

        if contact_df.empty:
            output_part_2 = [f"BCCDEF       1       0       0\n"]
        else:
            # Convert pd.DataFrame to lines
            output_data_lines = contact_df.to_string(buf=None,
                                                     header=False,
                                                     index=False,
                                                     formatters={"nodes": "{:8d}".format,
                                                                 "bcx": "{:8d}".format,
                                                                 "bcy": "{:8d}".format,
                                                                 "bcz": "{:8d}".format})
            output_part_2 = [f"BCCDEF       1 {len(output_data_lines):>7d}       0\n"]
            output_part_2.extend([output_data_lines + '\n'])

        output_lines = part_1.copy()
        output_lines.extend(output_part_2)
        output_lines.extend(part_3)

        # Write updated KEY-file
        write_list_of_strings_to_file(output_lines, filepath)
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise


def remove_wpaxis_rigid_zone(_param: dict, relative_filepath: str):
    try:
        filepath = os.path.join(sub_operation_abs_path(_param), relative_filepath)
        lines = read_lines_from_file(filepath)

        wpaxis_indices = []
        starting_line = 0
        while True:
            keyword_line_index = find_first_pattern_in_list(lines,
                                                            pattern='WPAXIS       1       1       7',
                                                            pattern_indices=[0, 1, 3],
                                                            starting_line=starting_line)
            if keyword_line_index is None:
                break
            else:
                wpaxis_indices.append(keyword_line_index)
                starting_line = keyword_line_index + 1

        if not wpaxis_indices:
            return

        keyword_lines_count = 4
        for keyword_line_index in wpaxis_indices:
            for _ in range(keyword_lines_count):
                lines.pop(keyword_line_index)

        # Write updated KEY-file
        write_list_of_strings_to_file(lines, filepath)
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise


def add_velocity_boundary_conditions(_param: dict, relative_filepath: str):  # , deform_keyfile: dict):
    try:
        deform_keyfile = _param['operation']['imported_keyfile']
        filepath = os.path.join(sub_operation_abs_path(_param), relative_filepath)
        lines = read_lines_from_file(filepath)

        # Read mesh nodes nodes.loc[N, [X, Y, Z]]
        nodes = read_table_to_pandas(lines=lines,
                                     pattern='RZ           1    5533',
                                     pattern_indices=[0, 1],
                                     pattern_value_index=2,
                                     has_index_column=True,
                                     data_type=float,
                                     column_names=['node', 'x', 'y', 'z'])

        p1, bccdef_keyword_line, bccdef_data_lines, p_left = \
            split_lines_by_keyword(lines,
                                   template_string="BCCDEF       1      80       0",
                                   pattern_indices=[0, 1],
                                   starting_line=0)

        p3, urz_keyword_line, urz_data_lines, p4 = \
            split_lines_by_keyword(p_left,
                                   template_string="URZ          1     323    0.0000000000E+000",
                                   pattern_indices=[0, 1],
                                   starting_line=0)

        bccdef_df = bccdef_lines_to_pd(bccdef_data_lines)
        # urz_df = urz_lines_to_pd(urz_data_lines)

        # Notes on bcx, bcy, bcz codes:
        # 0 nodal force (This is the Default value for all nodes )
        # 1 nodal velocity
        # 2 nodal traction
        # 3 nodal movement control
        # 4 beginning surface
        # 5 ending surface
        # 6 symmetry plane
        # 7 rotational symmetry (master)
        # 8 rotational symmetry (slave)
        # -n nodal contact with object n
        # -(200+n) Sticking condition with object n

        surface_nodes_pd = select_surface_nodes_by_box_windows(_param, bccdef_df, nodes, deform_keyfile)

        # Extract nodes having Contact BC
        contact_df = bccdef_df.where(bccdef_df.lt(0).to_numpy(), other=pd.NA).dropna(how='all').astype(pd.Int64Dtype())

        # Add old Contact BC to Selected Velocity BC
        surface_nodes_pd = union_velocity_and_contact_bcc(contact_df, surface_nodes_pd)

        # Convert pd.DataFrame to lines
        if surface_nodes_pd.empty:
            bccdef_output_data_lines = ["BCCDEF       1       0       0\n"]
        else:
            bccdef_output_data_lines = [
                f"BCCDEF       1 {surface_nodes_pd.shape[0]:>7d}       0\n" +
                surface_nodes_pd.to_string(buf=None,
                                           header=False,
                                           index=False,
                                           formatters={"nodes": "{:8d}".format,
                                                       "bcx": "{:8d}".format,
                                                       "bcy": "{:8d}".format,
                                                       "bcz": "{:8d}".format})
                + '\n']

        # if urz_df.empty:
        urz_output_data_lines = ["URZ          1       0    0.0000000000E+000"]
        # else:
        #     urz_output_data_lines = [
        #         f"URZ          1 {urz_df.shape[0]:>7d}    0.0000000000E+000\n" +
        #         urz_df.to_string(buf=None,
        #                          header=False,
        #                          index=False,
        #                          formatters={"x_speed": "{:>-21.10E}".format,
        #                                      "y_speed": "{:>-21.10E}".format,
        #                                      "z_speed": "{:>-21.10E}".format})
        #         + '\n']

        output_lines = p1.copy()
        output_lines.extend(bccdef_output_data_lines)
        output_lines.extend(p3)
        output_lines.extend(urz_output_data_lines)
        output_lines.extend(p4)

        # Write updated KEY-file
        write_list_of_strings_to_file(output_lines, filepath)
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise


def union_velocity_and_contact_bcc(contact_df, surface_nodes_pd) -> pd.DataFrame:
    try:
        # Add old contact BC
        contact_and_velocity_indices = contact_df.index.intersection(surface_nodes_pd.index)
        surface_nodes_pd.update(contact_df.loc[contact_and_velocity_indices])

        contact_only_indices = contact_df.index.difference(surface_nodes_pd.index)
        contact_only_pd = contact_df.loc[contact_only_indices].fillna(0)

        if surface_nodes_pd.empty:
            LOGGER.warning("FAILED: No nodes selected by Box Windows for Freezing Velocity BC.")
            if contact_only_pd.empty:
                result = pd.DataFrame(columns=surface_nodes_pd.columns, dtype=pd.Int64Dtype())
            else:
                result = contact_only_pd
        else:
            result = pd.concat([surface_nodes_pd,
                                contact_only_pd]).rename_axis('nodes').reset_index().astype(pd.Int64Dtype())
        return result
    except Exception as _err:
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        raise


def select_surface_nodes_by_box_windows(_param, df, nodes, obj_data):
    try:
        # Select nodes within the box bounds
        nodes_in_initial_lcs = \
            transform_nodes_from_lcs1_to_lcs2(nodes,
                                              lcs_1=_param['operation']['current_local_coordinate_system'],
                                              lcs_2=_param['operation']['initial_local_coordinate_system'])

        nodes_indices = select_points_in_box(nodes_in_initial_lcs,
                                             bounds_list=_param['operation']['velocity_boundary_condition_bounds_list'])

        surface_nodes_indices = nodes_indices.intersection(pd.Index(obj_data['objects'][1]['surface_nodes']))

        surface_nodes_np = np.repeat(np.where(np.array([_param['operation']['fixed_directions_xyz_bool']]),
                                              np.array([[1, 1, 1]]),
                                              np.array([[0, 0, 0]])
                                              ),
                                     surface_nodes_indices.shape[0],
                                     axis=0)

        return pd.DataFrame(surface_nodes_np,
                                        columns=df.columns,
                                        index=surface_nodes_indices,
                                        dtype=pd.Int64Dtype())
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise


def split_lines_by_keyword(lines: list[str], template_string: str, pattern_indices: list, starting_line: int
                           ) -> tuple[list, list, list, list]:
    try:
        # Find BCCDEF key word line and it's index
        keyword_line_index = find_first_pattern_in_list(lines, template_string, pattern_indices, starting_line)

        if keyword_line_index is None:
            return lines.copy(), [], [], []

    except Exception as _err:
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        raise
    try:
        data_lines_count = int(lines[keyword_line_index].split()[2])

        # Indices of data block lines
        data_start_index = keyword_line_index + 1
        data_end_index = data_start_index + data_lines_count
        # Divide KEY-file on two parts
        part_1 = lines[:keyword_line_index]
        data_lines = lines[data_start_index:data_end_index]
        part_3 = lines[data_end_index:]
        return part_1, [lines[keyword_line_index]], data_lines, part_3
    except Exception as _err:
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        raise


def bccdef_lines_to_pd(data_lines: list[str]):
    # Convert data lines to DataFrame
    try:
        data = [list(map(int, _line.split())) for _line in data_lines]
        df = pd.DataFrame(data, columns=['node', 'bcx', 'bcy', 'bcz'], dtype=pd.Int64Dtype())
        df.index = pd.Index(df['node'])
        df.drop(columns='node', inplace=True)
        return df
    except Exception as _err:
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        raise


def urz_lines_to_pd(data_lines: list[str]):
    # Convert data lines to DataFrame
    try:
        data = [_line.split() for _line in data_lines]
        nodes = pd.Index([row[0] for row in data])
        df = pd.DataFrame([row[1:] for row in data],
                          columns=['x_speed', 'y_speed', 'z_speed'],
                          index=nodes,
                          dtype=pd.Float64Dtype())
        return df
    except Exception as _err:
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        raise


def modify_mesh_number(_param: dict, relative_filepath):
    try:
        mesh_number = _param['previous_operation']['mesh_number']
        template_string = 'GENDB	       1	1	       2'
        filepath, part_1, part_3 = __split_file_above_string(relative_filepath, _param, template_string, [0])
        # Create Part_2
        # SPDLMT       2       7    0.0000000000E+000    0.0000000000E+000
        part_2 = [f"MESHNO       {mesh_number:d}\n"]
        part_1.extend(part_2)
        part_1.extend(part_3)
        write_list_of_strings_to_file(part_1, filepath)
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise


def modify_global_time(_param: dict, relative_path):
    try:
        global_time = _param['previous_operation']['global_time']
        sub_operation = sub_operation_abs_path(_param)
        filepath = os.path.join(sub_operation, relative_path)
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise
    try:
        lines = read_lines_from_file(filepath)
        lines = modify_value_in_list_of_strings(
            lines,
            'TNOW	     3.8018702651E+01       0       1', r"(\s+)",
            [0],
            1,
            global_time,
            "\t{:>-21.10E}")
        write_list_of_strings_to_file(lines, filepath)
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise


def __split_file_above_string(
        relative_filepath: str, _param: dict, template_string: str, template_indices: list
) -> tuple[str, list[str], list[str]]:
    try:
        sub_operation: str = sub_operation_abs_path(_param)
        filepath = os.path.join(sub_operation, relative_filepath)
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise
    try:
        lines = read_lines_from_file(filepath)
        line_1_indices = find_first_pattern_in_list(lines, template_string, template_indices, starting_line=0)
        part_1, part_3 = split_file_above_index(lines, line_1_indices)
        return filepath, part_1, part_3
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise RuntimeError(f"FAILED splitting {filepath}")


def split_file_above_index(lines: list[str], line_1_indices: int | None):
    try:
        # Divide KEY-file on two parts
        if line_1_indices is None:
            part_1 = lines.copy()
            part_3 = []
        else:
            part_1 = lines[:line_1_indices]
            part_3 = lines[line_1_indices:]
        return part_1, part_3
    except Exception as _err:
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        raise


def deform_mesh_settings(row: dict, _param: dict) -> dict:
    try:
        _size_correction_coef = 0.84
        _min_element_size = _size_correction_coef * min_element_size_function(row, _param)
        _element_size_ratio = _param['operation']['element_size_ratio']
        _length_of_average_element = 0.5 * (1 + _element_size_ratio) * _min_element_size
        _face_area_of_average_element = 0.43301270189221932338 * _length_of_average_element ** 2
        _number_of_surface_elements = int(row['initial_surface_area'] / _face_area_of_average_element)
        _inverse_max_element_size = 1 / (_min_element_size * _element_size_ratio)
        LOGGER.info(
            f"Min element size: {_min_element_size:.0f} mm; "
            f"Average element size: {_length_of_average_element:.0f} mm; "
            f"Element size ratio: {_element_size_ratio:.1f}; "
            f"Inverse max element size: {_inverse_max_element_size:.3f}; "
            f"Face area of average element: {_face_area_of_average_element:.0f} mm2; "
            f"Number of surface elements: {_number_of_surface_elements}")
        return {
            'min_element_size': _min_element_size,
            'element_size_ratio': _element_size_ratio,
            'length_of_average_element': _length_of_average_element,
            'face_area_of_average_element': _face_area_of_average_element,
            'number_of_surface_elements': _number_of_surface_elements,
            'inverse_max_element_size': _inverse_max_element_size}
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise


def min_element_size_function(row, _param: dict):
    """Returns the minimum element size for a given Billet Thickness. For Upset operation it is 5 times finer"""
    try:
        if row['operation_type'] == 'Upset':
            refinement_coef = 0.9
        else:
            refinement_coef = 1.0
        return _param['operation']['relative_min_element_size'] * billet_thickness(row) * refinement_coef
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise


def billet_thickness(row):
    try:
        return min(initial_billet_thickness(row), final_billet_thickness(row))
    except Exception as _err:
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        raise


def initial_billet_thickness(row):
    try:
        return min(row['initial_height'], row['initial_width'], row['initial_length'])
    except Exception as _err:
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        raise


def final_billet_thickness(row):
    try:
        return min(row['final_height'], row['final_width'], row['final_length'])
    except Exception as _err:
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        raise


def cogging_step_size_die_displacement(_param: dict, row: dict):
    try:
        max_billet_temperature = row['max_temperature']
        average_billet_strain = 0.0
        if row['type_id'] in (41, 44, 45):
            average_billet_strain_rate = row['speed'] / row['initial_length']
        else:
            average_billet_strain_rate = row['speed'] / row['initial_height']
        flow_stress = _param['material'].flow_stress(
            average_billet_strain,
            average_billet_strain_rate,
            max_billet_temperature)
        max_press_force = config.lib['press_mode'].loc[row['press_mode_id']]['max_force']
        contact_area = row['final_length_of_contact'] * row['final_width_of_contact']
        actual_press_force = contact_area * flow_stress
        if actual_press_force >= max_press_force:
            force_coefficient = 0.1
        elif actual_press_force <= 0.0:
            force_coefficient = 1.0
        else:
            force_coefficient = 1.0 - 0.9 * actual_press_force / max_press_force
        #
        size_coefficient = 0.05
        #
        step_size = size_coefficient * force_coefficient * min_element_size_function(row, _param)
        assert step_size > 0
        return step_size
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise


def billet_is_centered(_param: dict):
    try:
        bounds = np.asarray(_param['operation']['imported_keyfile']['objects'][1]['measurements']['bounds'])
        center_x = 0.5 * (bounds[0] + bounds[2])
        center_y = 0.5 * (bounds[1] + bounds[3])
        return max(abs(center_x).item(), abs(center_y).item()) < 0.1
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise


def import_db_from_previous_sub_operation(_param: dict):
    # sourcery skip: use-named-expression
    try:
        e_o = _param['project']['execution_order']
        pvid = _param['project']['process_version_id']
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise
    try:
        update_operation_parameters_merge_filepaths(_param)
        is_old_database_exists = is_db_final_exists(_param)

        if e_o > 1:
            assert is_old_database_exists, f"{pvid}/{e_o} Old database does not exist"

        delete_sub_operation_db_if_exists(_param)
        if is_old_database_exists:
            copy_db_final_to_to_sub_operation_path(_param)
        modify_key_and_mst_files(_param, is_old_database_exists)
    except Exception as _err:
        LOGGER.warning(f"{pvid}/{e_o} {type(_err).__name__}: {_err}")
        raise


def modify_key_and_mst_files(_param: dict, is_old_database_exists: bool):
    try:
        template_name = _param['operation']['template_name']
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise
    try:
        key_file = {
            "file_path": template_name + ".KEY",
            "parameters": {
                "generate_db_1": dict(s="GENDB     	2	1	0", k=[0], n=1, f="\t{:8d}"),
                "generate_db_3": dict(s="GENDB     	1	1	0", k=[0], n=3, f="\t{:8d}")}}
        mst_file = {
            "file_path": template_name + ".MST",
            "parameters": {
                "generate_db_1": dict(s="GENDB     	2	1	0", k=[0, 1, 2, 3], n=1, f="\t{:8d}"),
                "generate_db_3": dict(s="GENDB     	1	1	0", k=[0, 1, 2, 3], n=3, f="\t{:8d}")}}
        files = {
            "file_1": key_file,
            "file_2": mst_file}

        if is_old_database_exists:
            generate_db_1 = 1  # Generate Old database
        else:
            generate_db_1 = 2  # Generate New database

        _param['operation']['generate_db_1'] = generate_db_1
        _param['operation']['generate_db_3'] = 0  # =0 Generate negative step; =1 Keep positive step

        automatic_modification_of_parameters_in_files(files, _param)

    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise RuntimeError(
            f"FAILED modifying KEY and MST files for Template Name = '{template_name}'. Error: {_err}")


def move_db_to_project_dir(_param: dict):
    # sourcery skip: use-named-expression
    try:
        update_operation_parameters_merge_filepaths(_param)
        _delete_temp_final(_param)
        _move_sub_operation_db_to_temporary_final_path(_param)
        _try_to_copy_temp_final_to_final(_param)
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise RuntimeError("FAILED substituting old DB-file with new one")


def update_operation_parameters_merge_filepaths(_param: dict):
    try:
        db_temporary_final_name = 'FOR003.TMP'
        local_dir: str = config.server['local_dir']
        project_dir_name: str = _param['project']['project_dir_name']
        db_file_name: str = _param['project']['db_file_name']
        sub_operation_path: str = sub_operation_abs_path(_param)
        sub_operation_name: str = _param['operation']['sub_operation_name']
        template_name: str = _param['operation']['template_name']
        e_o: int = _param['project']['execution_order']
        next_e_o = e_o + 1

        abs_project_path = os.path.join(local_dir, project_dir_name)
        db_final_filepath = os.path.join(abs_project_path, db_file_name + '.DB')
        db_temporary_final_filepath = os.path.join(abs_project_path, db_temporary_final_name)
        db_sub_operation_filepath = os.path.join(sub_operation_path, template_name + '.DB')
        db_sub_operation_temporary_name = f"FOR003_ADDED_{next_e_o:0>3d}_{sub_operation_name}.TMP"
        db_sub_operation_temporary_filepath = os.path.join(abs_project_path, db_sub_operation_temporary_name)
        db_resulting_name = f"FOR003_RESULT_{next_e_o:0>3d}_{sub_operation_name}.TMP"
        db_resulting_filepath = os.path.join(abs_project_path, db_resulting_name)

        _param['operation'] |= {
            'db_final_filepath': db_final_filepath,
            'db_temporary_final_filepath': db_temporary_final_filepath,
            'db_sub_operation_filepath': db_sub_operation_filepath,
            'db_sub_operation_temporary_filepath': db_sub_operation_temporary_filepath,
            'db_resulting_filepath': db_resulting_filepath,
            'db_resulting_name': db_resulting_name,
            'db_sub_operation_temporary_name': db_sub_operation_temporary_name,
            'db_temporary_final_name': db_temporary_final_name}
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise


# def __run_merge_temp_final_and_sub_row_temp_to_resulting(operation_parameters):
#     def_dbm_path = os.path.join(operation_parameters['deform_installation_path'], "3D", "DEF_DBM.exe")
#     # commands = f"<CR>\n2\n1\n{template_name}.KEY\n<CR>\nE\nE\nY\n<CR>\n"
#     commands = (
#         "2\n"
#         f"{operation_parameters['db_temporary_final_name']}\n"
#         f"{operation_parameters['db_sub_operation_temporary_name']}\n"
#         f"{operation_parameters['db_resulting_name']}\n"
#     )
#     run(
#         def_dbm_path,
#         input=commands,
#         encoding='ascii',
#         check=False,
#         text=True,
#         stdout=PIPE,
#         cwd=operation_parameters['operation']['project_abs_path'])


def _copy_sub_operation_db_to_project_directory(_param: dict):
    try:
        src = _param['operation']['db_sub_operation_filepath']
        dst = _param['operation']['db_sub_operation_temporary_filepath']

        if os.path.exists(dst):
            os.remove(dst)
            LOGGER.info(f"Removed file/dir (as in param['operation']['db_sub_operation_temporary_filepath']) '{dst}'")

        shutil.copy(src, dst)
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise


def _move_sub_operation_db_to_temporary_final_path(_param: dict):
    try:
        src: str = _param['operation']['db_sub_operation_filepath']
        dst: str = _param['operation']['db_temporary_final_filepath']
        _file = os.path.split(src)[1]
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise
    try:
        if os.path.exists(src):
            shutil.move(src, dst)
            # LOGGER.info(f"OK moved '{src}' to '{dst}'")
        else:
            LOGGER.warning(f"Can't move '{src}' to '{dst}' because it does not exist")
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise RuntimeError(f"FAILED moving '{src}' to '{dst}'.")


def copy_db_final_to_to_sub_operation_path(_param: dict):
    try:
        src = _param['operation']['db_final_filepath']
        dst = _param['operation']['db_sub_operation_filepath']
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise
    try:
        _file = os.path.split(src)[1]
        shutil.copy2(src, dst)
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise RuntimeError(f"FAILED moving '{src}' to '{dst}'")


def _delete_resulting_db(_param: dict):
    try:
        _file = _param['operation']['db_resulting_filepath']

        if os.path.exists(_file):
            os.remove(_file)
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise


def copy_sub_operation_db_to_temporary_final(_param: dict):
    try:
        src = _param['operation']['db_sub_operation_filepath']
        dst = _param['operation']['db_temporary_final_filepath']
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise
    try:
        shutil.copy(src, dst)
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise RuntimeError(f"FAILED copying Sub Operation DB-file {src} into Temporary Final one {dst}")


def _resulting_exists(_param: dict):
    try:
        return os.path.exists(_param['operation']['db_resulting_filepath'])
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise

def _delete_temporary_sub_operation_db(_param: dict):
    try:
        _file = _param['operation']['db_sub_operation_temporary_filepath']
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise
    try:
        if os.path.exists(_file):
            os.remove(_file)
            LOGGER.info(f"Removed Sub Operation DB-file '{_file}'")
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise RuntimeError(f"FAILED deleting '{_file}'")


def _delete_temp_final(_param: dict):
    try:
        e_o: int = _param['project']['execution_order']
        _file: str = _param['operation']['db_temporary_final_filepath']
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise
    try:
        if e_o > 1:
            if os.path.exists(_file):
                os.remove(_file)
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise RuntimeError(f"FAILED deleting Temporary DB-file '{_file}'")


def delete_sub_operation_db_if_exists(_param: dict):
    try:
        db_sub_operation_filepath = _param['operation']['db_sub_operation_filepath']
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise
    try:
        if os.path.exists(db_sub_operation_filepath):
            os.remove(db_sub_operation_filepath)
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise RuntimeError(f"FAILED deleting Sub Operation DB-file '{db_sub_operation_filepath}'")


def is_db_final_exists(_param: dict) -> bool:
    try:
        db_temporary_final_filepath = _param['operation']['db_final_filepath']
        return os.path.isfile(db_temporary_final_filepath)
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise


def _move_resulting_db_to_temporary_final(_param: dict):
    try:
        src = _param['operation']['db_resulting_filepath']
        dst = _param['operation']['db_temporary_final_filepath']
        _file = os.path.split(src)[1]
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise
    try:
        shutil.move(src, dst)
        # LOGGER.info(f"Moved DB-file '{src}' to '{dst}'")
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise RuntimeError(f"FAILED moving DB-file '{src}' to '{dst}'")


def _try_to_copy_temp_final_to_final(_param: dict):
    try:
        src = _param['operation']['db_temporary_final_filepath']
        dst = _param['operation']['db_final_filepath']
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise
    try:
        if os.path.exists(dst):
            os.remove(dst)
            LOGGER.info(f"OK removed '{dst}'")
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise RuntimeError(f"Can't remove '{dst}'")
    try:
        shutil.copy(src, dst)
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise RuntimeError(f"FAILED copying {src} to {dst}")


def convert_usrdef_triggers_to_strings(_param: dict) -> list[str]:
    """
    Get the USRDEF triggers for the simulation.
    Required DEFORM DEF_SIM.exe version: 13 on date 2024.02.23

    _param (dict): The input data dictionary.

        'strain_softening_coefficient'      FLOAT   (0.005) - 'Strain Softening Coefficient'

        'start_step_number'                 INT     (0) - 'Step number where the USRDEF variables will be initialized.'

        'max_temperature_per_bite'          BOOL    (1) Nodal - 'Max Temperature per Bite'
        'max_temperature_per_operation'     BOOL    (2) Nodal - 'Max Temperature per Operation'
        'temperature_change_per_bite'       BOOL    (3) Nodal - 'Temperature Change per Bite'
        'temperature_change_per_operation'  BOOL    (4) Nodal - 'Temperature Change per Operation'

        'effective_strain_per_bite'         BOOL    (5) Elemental - 'Effective Strain per Bite'
        'effective_strain_per_operation'    BOOL    (6) Elemental - 'Effective Strain per Operation'
        'effective_strain_per_heat'         BOOL    (7) Elemental - 'Effective Strain per Heat'
    """
    try:
        triggers_dict: dict = _param['operation']['usrdef_triggers']
        keys_order = ('strain_softening_coefficient',
                      'start_step_number',
                      'max_temperature_per_bite',
                      'max_temperature_per_operation',
                      'temperature_change_per_bite',
                      'temperature_change_per_operation',
                      'effective_strain_per_bite',
                      'effective_strain_per_operation',
                      'effective_strain_per_heat')

        missed_keys = [key for key in keys_order if key not in triggers_dict]
        assert not missed_keys, f"KeyError: '{missed_keys}' not found in 'input_data' dict"

        input_list = [triggers_dict[key] for key in keys_order]
        strain_softening_coefficient = input_list.pop(0)
        last_start_step_number_of_previous_operation = input_list.pop(0)
        start_step_number = last_start_step_number_of_previous_operation + 1

        assert isinstance(start_step_number, int), "start_step_number must be an integer"

        bool_to_int = map(int, input_list)  # Convert to Boolean to integers 1 or 0
        usrdef_line_2_list = [start_step_number] + list(bool_to_int)
        usrdef_strings = [
            str(strain_softening_coefficient) + '\n',
            ' '.join(map(str, usrdef_line_2_list)) + '\n'
        ]
        return usrdef_strings
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise


def modify_usrdef_triggers(_param: dict, relative_filepath: str):
    try:
        # Read keyfile
        filepath = os.path.join(sub_operation_abs_path(_param), relative_filepath)
        lines = read_lines_from_file(filepath)

        _remove_multiple_lines_keyword(_param, lines, pattern='USRDEF 2', pattern_indices=[0], strings_counter_index=1)
        first_line_of_part_3_index = _first_line_index_after_comment_for_user_defined_variables(_param, lines)

        part_1, part_3 = split_file_above_index(lines, first_line_of_part_3_index)

        # Prepare USRDEF strings
        usrdef_strings = convert_usrdef_triggers_to_strings(_param)

        part_2 = [f"USRDEF {len(usrdef_strings):>7d}\n"]
        part_2.extend(usrdef_strings)

        # Join Parts 1, 2 and 3
        part_1.extend(part_2)
        part_1.extend(part_3)
        write_list_of_strings_to_file(part_1, filepath)
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise


def modify_user_variable_names(_param: dict, relative_filepath: str):
    try:
        # Read keyfile
        filepath = os.path.join(sub_operation_abs_path(_param), relative_filepath)
        lines = read_lines_from_file(filepath)
        nodal_variables_names = VARIABLES['user_nodal']['column_names']
        element_variables_names = VARIABLES['user_element']['column_names']

        _remove_multiple_lines_keyword(_param, lines, pattern='UNNAME 1 2', pattern_indices=[0], strings_counter_index=2)
        _remove_multiple_lines_keyword(_param, lines, pattern='UENAME 1 2', pattern_indices=[0], strings_counter_index=2)

        first_line_of_part_3_index = _first_line_index_after_comment_for_user_defined_variables(_param, lines)

        part_1, part_3 = split_file_above_index(lines, first_line_of_part_3_index)

        part_2 = [f"UNNAME       1 {len(nodal_variables_names):>7d}\n"]
        for _i in range(len(nodal_variables_names)):
            part_2.append(nodal_variables_names[_i] + '\n')

        part_2.append(f"UENAME       1 {len(element_variables_names):>7d}\n")
        for _i in range(len(element_variables_names)):
            part_2.append(element_variables_names[_i] + '\n')

        # Join Parts 1, 2 and 3
        part_1.extend(part_2)
        part_1.extend(part_3)
        write_list_of_strings_to_file(part_1, filepath)
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise


def initialize_user_nodal_variables_for_ingot_axis(_param: dict, rx: float | np.float64 = 0.0, ry: float | np.float64 = 0.0, rz: float | np.float64 = 0.0, dx: float | np.float64 = 0.0, dy: float | np.float64 = 0.0, dz: float | np.float64 = 0.0):
    """
    Initializes billet basis to be along global XYZ axes.
    Billet basis is defined by USRNOD data table in DEFORM's KEY-file.

    Additional arguments are defined in '_param' dictionary:

    _param['operation']['is_initialize_user_nodal_for_ingot_axis'] - either do or not the basis initialization

    _param['operation']['sub_operation_relative_initial_billet_file_path'] - KEY-file path is defined in relative path

    _param['operation']['log_id'] - logging prefix

    Args:
        _param (dict): Dictionary of parameters generated by SimulationWorker
        rx (float | np.float64): Rotation angle X axis
        ry (float | np.float64): Rotation angle Y axis
        rz (float | np.float64): Rotation angle Z axis
        dx (float | np.float64): Displacement along X axis
        dy (float | np.float64): Displacement along Y axis
        dz (float | np.float64): Displacement along Z axis
    """
    try:
        if 'is_initialize_user_nodal_for_ingot_axis' not in _param['operation']:
            return
        if not _param['operation']['is_initialize_user_nodal_for_ingot_axis']:
            return

        local_dir: str = config.server['local_dir']
        sub_operation_relative_initial_billet_file_path: str = _param['operation']['sub_operation_relative_initial_billet_file_path']
        filepath = os.path.join(local_dir, sub_operation_relative_initial_billet_file_path)

        keyfile_lines = read_lines_from_file(filepath)

        # ==============================================================================================================
        node_count = get_node_count(keyfile_lines)

        # ================================= READ NODE COORDINATES =============================================

        rz_keyword_index = find_first_pattern_in_list(keyfile_lines, pattern="RZ           1     277", pattern_indices=[0, 1], starting_line=0)
        if rz_keyword_index is None:
            return
        rz_keyword_index: int
        rz_keyword, rz_args = get_keyword(keyfile_lines, line_index=[rz_keyword_index])
        nodes: np.ndarray = read_object_keyword(keyfile_lines,
                                                keyword_line_index=[rz_keyword_index],
                                                args=rz_args,
                                                keyword_dict=VARIABLES_VS_DEFORM_KEYWORD[rz_keyword][0],
                                                expected_count_of_data_lines=node_count[1])

        # ==============================================================================================================

        # Find BCCDEF key word line and it's index
        usrnod_keyword_line_index = find_first_pattern_in_list(keyfile_lines, "USRNOD       1     277    0.0000000000E+000       7", pattern_indices=[0, 1], starting_line=rz_keyword_index)
        if usrnod_keyword_line_index is None:
            return
        usrnod_keyword_line_index: int

        keyword, args = get_keyword(keyfile_lines, line_index=[usrnod_keyword_line_index])

        # Indices of data block lines
        data_start_index = usrnod_keyword_line_index + 1

        nodes_count: int = args[1]
        user_nodal_variables_count: int = args[3]

        data_columns_count: int = user_nodal_variables_count + 1  # + 1 For Indices column
        total_data_values_count: int = nodes_count * data_columns_count

        # =========================== READ USER NODAL VARIABLES to LIST OF STRINGS ============================
        # Test if columns of single data row is separated on two or few KEY-file's lines
        values = []
        data_end_index = data_start_index
        for data_end_index in range(data_start_index, len(keyfile_lines), 1):
            line_values = keyfile_lines[data_end_index].strip().split()
            values.extend(line_values)
            values_count = len(values)
            if values_count == total_data_values_count:
                break
            elif values_count > total_data_values_count:
                raise IndexError(f"According KEYWORD line '{keyfile_lines[usrnod_keyword_line_index]}' it was expected "
                                 f"to find exactly {total_data_values_count} data values "
                                 f"in {nodes_count} rows x {data_columns_count} columns (including first columns which is Node numbers one),"
                                 f"but in next {data_end_index - data_start_index + 1} lines of KEY-file {values_count} data values was found. "
                                 f"Last {values_count - total_data_values_count} data values are: {' '.join(values[total_data_values_count:])}.")

        # =========================== READ USER NODAL VARIABLES to NUMPY ARRAY ================================

        new_lines: list = " ".join([(item + "/n") if (i + 1) % data_columns_count == 0 else item for i, item in enumerate(values)]).split("/n")
        node_numbers = np.loadtxt(new_lines, dtype='i', usecols=(0,))
        node_indices = np.add(-1, node_numbers)
        user_nodal_variables = np.loadtxt(new_lines, dtype='f8', usecols=tuple(range(1, data_columns_count, 1)))  # dtype='f8' is for float64

        # ======================================== OFFSET BILLET =============================================
        nodes = nodes + np.array([dx, dy, dz])

        # ======================================== ROTATE BILLET =============================================
        nodes = rotate_basis(nodes, list_of_rotations_xyz=[('z', rz), ('y', ry), ('x', rx)])

        # =========================== INITIALIZE INGOT AXIS X,Y,Z ============================================
        """
        'column_names': (
            'max_temperature_bite',
            'max_temperature_operation',
            'temperature_change_bite',
            'temperature_change_operation',
            'ingot_axis_x',
            'ingot_axis_y',
            'ingot_axis_z'
        """
        user_nodal_variables_names: tuple = VARIABLES_VS_DEFORM_KEYWORD['USRNOD'][0]['column_names']
        ingot_axis_names = ('ingot_axis_x', 'ingot_axis_y', 'ingot_axis_z')
        for key in ingot_axis_names:
            assert key in user_nodal_variables_names, f"Missed key {key} in VARIABLES_VS_DEFORM_KEYWORD['USRNOD']['column_names']"
        ingot_axis_index = tuple(user_nodal_variables_names.index(key) for key in ingot_axis_names)



        billet_bounds = np.vstack((np.min(nodes, axis=0), np.max(nodes, axis=0)))
        billet_dimensions = billet_bounds[1, :] - billet_bounds[0, :]
        scale_coef = 1 / billet_dimensions
        user_nodal_variables[:, ingot_axis_index] = np.multiply(nodes, scale_coef)[node_indices, :]

        user_nodal_variables_lines = []
        for i, values in enumerate(user_nodal_variables.tolist()):
            user_nodal_variables_lines.append(f" {(i + 1):>8d} " + " ".join([f"{item:>-20.10E}" for item in values]) + "\n")

        # =====================================================================================================
        variables_count = user_nodal_variables.shape[1]

        # Keyfile data array
        # keyfile_lines.append(f"USRNOD       1 {nodes_count:>7d}    0.0000000000E+000 {variables_count:>7d}\n")

        variables_count_per_line: int = 5
        full_lines_per_node: int = variables_count // variables_count_per_line
        residual_variables_at_additional_line: int = variables_count % variables_count_per_line

        if full_lines_per_node == 0:
            pattern = "{:>8d}   " + "   ".join(["{:>-20.10E}"] * variables_count) + "\n"
        else:
            pattern = "{:>8d}   " + "   ".join(["{:>-20.10E}"] * variables_count_per_line) + "\n"
            pattern += ("           " + "   ".join(["{:>-20.10E}"] * variables_count_per_line) + "\n") * (full_lines_per_node - 1)
            if residual_variables_at_additional_line > 0:
                pattern += "           " + "   ".join(["{:>-20.10E}"] * residual_variables_at_additional_line) + "\n"

        data_list = list(zip(node_numbers.tolist(), *user_nodal_variables.transpose().tolist()))
        user_nodal_variables_lines = [pattern.format(*var) for var in data_list]

        # =============================== ASSEMBLE AND WRITE KEY-FILE ==================================================
        # Divide KEY-file on three parts
        # keyfile_part_1 = keyfile_lines[:data_start_index]
        # keyfile_part_3 = keyfile_lines[(data_end_index + 1):]

        new_keyfile = keyfile_lines[:data_start_index]
        new_keyfile.extend(user_nodal_variables_lines)
        new_keyfile.extend(keyfile_lines[(data_end_index + 1):])

        # ==============================================================================================================

        # Write updated KEY-file
        write_list_of_strings_to_file(new_keyfile, filepath)

    except Exception as _err:
        LOGGER.error(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise RuntimeError("FAILED calculating User Nodal variables (X, Y, Z) defining the ingot axis")


def _remove_multiple_lines_keyword(_param: dict,
                                   lines: list[str],
                                   pattern: str,
                                   pattern_indices: list[int],
                                   strings_counter_index: int
                                   ):
    try:
        # Check if the file has USRDEF keyword
        usrdef_keyword_indices = find_pattern_in_list(lines,
                                                      pattern=pattern,
                                                      pattern_indices=pattern_indices,
                                                      starting_line=0)
        if usrdef_keyword_indices:
            # Remove existing USRDEF keyword and its strings (variables)
            for _i in usrdef_keyword_indices[::-1]:
                strings_count = int(lines[_i].split()[strings_counter_index])
                del lines[_i:_i + strings_count + 1]
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise


def _first_line_index_after_comment_for_user_defined_variables(_param: dict, lines: list[str]) -> int:
    try:
        # Find comment section for User Defined Variables
        usr_var_comment_section = find_pattern_in_list(lines,
                                                       pattern='*  User Defined Variables',
                                                       pattern_indices=[0, 1, 2, 3],
                                                       starting_line=0)
        if usr_var_comment_section:
            # Find last line of the comment section
            _i = usr_var_comment_section[0]
            while _i < len(lines) and lines[_i].startswith('*'):  # Find first NON-comment line
                _i += 1
            previous_line_index = _i
        else:
            previous_line_index = len(lines)
        return previous_line_index
    except Exception as _err:
        LOGGER.warning(f"{_param['operation']['log_id']} {type(_err).__name__}: {_err}")
        raise


def set_triggers(softening_coefficient: float, is_new_bite: bool, is_new_operation: bool, is_new_heat: bool
                 ) -> dict:
    try:
        assert isinstance(softening_coefficient, float), "strain_softening_coefficient must be a float"
        assert isinstance(is_new_bite, bool), "is_new_bite must be a boolean"
        assert isinstance(is_new_operation, bool), "is_new_operation must be a boolean"
        assert isinstance(is_new_heat, bool), "is_new_heat must be a boolean"

        triggers_dict = {
            'strain_softening_coefficient': softening_coefficient,
            'max_temperature_per_bite': is_new_bite,
            'max_temperature_per_operation': is_new_operation,
            'temperature_change_per_bite': is_new_bite,
            'temperature_change_per_operation': is_new_operation,
            'effective_strain_per_bite': is_new_bite,
            'effective_strain_per_operation': is_new_operation,
            'effective_strain_per_heat': is_new_heat
        }
        return triggers_dict
    except Exception as _err:
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        raise


def assert_missing_input_parameters(required_input_key_words: list[str], _param: dict):
    # Assert missing INPUT parameters.
    missing_keys = [key for key in required_input_key_words if key not in _param['operation']]
    assert not missing_keys, f"There are missed keys in self.param['operation']: '{missing_keys}'"
