import json
import logging
import traceback
import os
import shutil
import time
from contextlib import contextmanager
from datetime import datetime

import numpy as np
import pandas as pd
import smbclient
import smbclient.shutil
import smbclient.path
from pandas import StringDtype, Int64Dtype, Int16Dtype, Int32Dtype, Float64Dtype

from forgelab.config import config


LOGGER = logging.getLogger(__name__)


def obsolete_logging_old_project_dirs_info(_old_projects: list[str]):
    """
    Receives '_param' dict with server parameters and list of local project dirs.
    Logging list of old projects if not empty.
    """
    try:
        _local_dir: str = config.server['local_dir']
    except KeyError as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise

    try:
        if _old_projects:
            if len(_old_projects) == 1:
                _old_ids = f"ID is: {_old_projects[0]}"
            else:
                _old_ids = f"IDs are: {', '.join(_old_projects)}"
            LOGGER.info(f"OK: project directory '{_local_dir}' is not empty and has {len(_old_projects)} old projects. "
                        f"The old project {_old_ids}.")

    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise RuntimeError(f"FAILED func 'logging_old_project_dirs_info' with location '{_local_dir}'")


def obsolete_move_old_projects_to_nas():
    """
    Check if there is any folder in the local directory defined at config.server['local_dir'].
    All folders are the old projects and folder names are equal to project IDs.
    Move all project folders to NAS.
    The NAS network folder is specified in config.nas['public_dir'].
    If actions were successful, then set server status to True.
    The server status is specified in config.server['is_server_ready'].
    """
    try:
        assert is_local_dir_exist()
        assert is_smb_file_server_available()

        _local_dir: str = config.server['local_dir']
        old_projects = [_f for _f in os.listdir(_local_dir) if os.path.isdir(os.path.join(_local_dir, _f))]

        obsolete_logging_old_project_dirs_info(old_projects)
        _smb_move_directory(old_projects)

    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        stop_server()
        raise


def obsolete_move_old_operations_to_nas() -> bool:
    """
    Check if there is any folder in config.server['local_dir'].
    All folders are the old projects and folder names are equal to project IDs.
    Make a list of old projects.
    Take new project name from _param['project']['process_version_id'] and exclude it from the list.
    Move all folders from the list to NAS.
    The NAS network folder is specified in config.nas['public_dir'].
    If actions were successful, then set server status to True.
    The server status is specified in config.server['is_server_ready'].
    """

    assert is_local_dir_exist()
    assert is_smb_file_server_available()
    assert _move_operations_to_nas()

    _is_success = not config.server['is_server_failed']

    return _is_success


def _smb_move_directory(_old_projects: list[str]) -> bool:
    """
    Receives '_param' dict and list of local project dirs.
    '_param' dict contain full paths to the Server's 'Local Projects Dir' and 'NAS Projects Storage Dir'.
    Moves all local project dirs to NAS.
    Do logging of moving success of fail.
    Returns True if moving was successful and 'Local Projects Dir' is empty, otherwise False.
    """

    # Server dir is empty. Nothing to move.
    if not _old_projects:
        return True

    try:
        _local_dir: str = config.server['local_dir']
        _nas_dir: str = config.nas['absolute_path']
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise

    try:
        # Move old project dirs.
        success_count, errors_count = 0, 0

        for _project_dir_name in _old_projects:
            src = os.path.join(_local_dir, _project_dir_name)
            dst = os.path.join(_nas_dir, _project_dir_name)
            try:
                smbclient.shutil.copytree(src, dst)
                success_count += 1
                LOGGER.info(f"Moved project dir '{_project_dir_name}' from '{src}' to '{dst}'")
            except Exception as _err:
                errors_count += 1
                LOGGER.error(f"FAILED moving project '{_project_dir_name}' from '{src}' to '{dst}' with Error: {_err}")

        total_count = success_count + errors_count
        assert errors_count == 0, f"FAILED: {errors_count} project dirs out of {total_count} dirs were not moved to NAS"

    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def _move_operations_to_nas() -> bool:
    """Move all operation dirs of the new project to NAS except the last one"""
    try:
        new_project_dir_name = 'CHANGE_NAME'
        local_dir: str = config.server['local_dir']
        nas_dir: str = config.nas['public_dir']
        pvid: int = config.project['process_version_id']
        current_e_o: int = config.project['execution_order']
    except KeyError as _err:
        raise RuntimeError(f"FAILED func '_move_operations_to_nas' with KeyError: {_err}")

    new_project_dir_on_server = os.path.join(local_dir, new_project_dir_name)
    if not os.path.exists(new_project_dir_on_server):
        return False

    new_project_dir_on_nas = os.path.join(nas_dir, new_project_dir_name)
    case_msg = f"happened when creating project directory '{new_project_dir_on_nas}'."
    if not os.path.exists(new_project_dir_on_nas):
        try:
            os.makedirs(new_project_dir_on_nas)
        except OSError:
            LOGGER.error(f"OSError {case_msg}")
            return False
        except Exception as _err:
            LOGGER.error(f"Some error {case_msg} Error: {_err}")
            return False

    _is_error = False

    for e_o in range(current_e_o):  # New operation number is excluded
        # operation_dir_name = generate_operation_dir_name(operation_number)
        operation_dir_name = 'ADD_GENERATE_OPERATION_DIR_NAME'
        src = os.path.join(new_project_dir_on_server, operation_dir_name)

        if os.path.exists(src):
            dst = os.path.join(new_project_dir_on_nas, operation_dir_name)
            try:
                shutil.move(src, dst)
                LOGGER.info(f"Moved operation #{e_o} of the project '{pvid}' from '{src}' to '{dst}'")
            except (OSError, Exception):
                LOGGER.error(f"Failed moving of operation #{e_o} of the project '{pvid}' from '{src}' to '{dst}'")
                _is_error |= True

    _is_success = not _is_error
    return _is_success


def is_smb_file_server_available() -> bool:
    try:
        smb_share = config.nas['absolute_path']
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise KeyError("Key or values of config.nas['absolute_path'] do not exist")

    try:
        assert smbclient.path.exists(smb_share), (
            f"Remote file server '{smb_share}' had successfully authentication, "
            f"and share path is correct, but is not accessible.")
        return True
    except Exception as _err:
        LOGGER.error(f"Remote file server '{smb_share}' is not accessible. Error: {_err}")
        return False


def is_local_dir_exist() -> bool:
    try:
        local_dir: str = config.server['local_dir']
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise
    if os.path.exists(local_dir):
        return True
    else:
        LOGGER.warning(f"Directory '{local_dir}' specified in 'config.server['local_dir']' does not exist")
        return False

def silent_smb_friendly_remove_file_or_dir_tree(abs_file_path: str) -> bool:
        is_successfully_removed = False
        try:
            max_attempts_count = config.server['file_remove_attempts_before_raising_error']
            dwell_between_cycles = config.server['file_remove_attempts_cycle_time_sec']

            assert isinstance(max_attempts_count, int)
            assert max_attempts_count > 0
            assert isinstance(dwell_between_cycles, (float, int))
            assert dwell_between_cycles >= 0.0
            assert isinstance(abs_file_path, str)

            is_smb_path = abs_file_path.startswith("\\\\")
            if is_smb_path:
                is_exist = smbclient.path.exists(abs_file_path)
            else:
                is_exist = os.path.exists(abs_file_path)
            assert is_exist, f"Path does not exist {abs_file_path}"

            if is_smb_path:
                is_file = smbclient.path.isfile(abs_file_path)
                is_dir = smbclient.path.isdir(abs_file_path)
            else:
                is_file = os.path.isfile(abs_file_path)
                is_dir = os.path.isdir(abs_file_path)

            if is_file and is_dir:
                raise RuntimeError(f"Path is detected as both a file and a dir {abs_file_path}")
            if not is_file and not is_dir:
                raise RuntimeError(f"Path is not recognized neither as a file nor as a dir {abs_file_path}")

            for i in range(1, max_attempts_count + 1):
                try:
                    if is_file:
                        if is_smb_path:
                            smbclient.unlink(abs_file_path)
                        else:
                            os.unlink(abs_file_path)
                    else:
                        if is_smb_path:
                            smbclient.shutil.rmtree(abs_file_path)
                        else:
                            shutil.rmtree(abs_file_path)
                    is_successfully_removed = True
                    break
                except Exception as _err:
                    is_wait_before_next_attempt = (dwell_between_cycles > 0) and (i < max_attempts_count)
                    time_message = (f" Wait for {dwell_between_cycles} sec before next removing attempt."
                                    if is_wait_before_next_attempt
                                    else "")
                    LOGGER.warning(
                        f"DIR REMOVE FAILED at attempt {i}/{max_attempts_count} with {type(_err).__name__}: {_err}."
                        f"{time_message}")
                    if is_wait_before_next_attempt:
                        time.sleep(dwell_between_cycles)
            return is_successfully_removed
        except Exception as _err:
            LOGGER.warning(f"{type(_err).__name__}: {_err}")
            return False


def smb_friendly_remove_file(abs_dir_path: str) -> bool:
        is_successfully_removed = False
        try:
            max_attempts_count = config.server['file_remove_attempts_before_raising_error']
            dwell_between_cycles = config.server['file_remove_attempts_cycle_time_sec']

            assert isinstance(max_attempts_count, int)
            assert max_attempts_count > 0
            assert isinstance(dwell_between_cycles, (float, int))
            assert dwell_between_cycles >= 0.0
            assert isinstance(abs_dir_path, str)

            for i in range(1, max_attempts_count + 1):
                try:
                    if abs_dir_path.startswith("\\\\"):
                        if smbclient.path.exists(abs_dir_path):
                            smbclient.shutil.rmtree(abs_dir_path)
                    else:
                        if os.path.exists(abs_dir_path):
                            shutil.rmtree(abs_dir_path)
                    is_successfully_removed = True
                    break
                except Exception as _err:
                    is_wait_before_next_attempt = (dwell_between_cycles > 0) and (i < max_attempts_count)
                    time_message = (f" Wait for {dwell_between_cycles} sec before next removing attempt."
                                    if is_wait_before_next_attempt
                                    else "")
                    LOGGER.warning(
                        f"DIR REMOVE FAILED at attempt {i}/{max_attempts_count} with {type(_err).__name__}: {_err}."
                        f"{time_message}")
                    if is_wait_before_next_attempt:
                        time.sleep(dwell_between_cycles)

        except Exception as _err:
            LOGGER.warning(f"{type(_err).__name__}: {_err}")
            return False
        return is_successfully_removed


def _remove_file(abs_file_path: str | bytes | os.PathLike):
    failed_to_remove_files, removed_files = [], []
    is_removed = silent_smb_friendly_remove_file_or_dir_tree(abs_file_path)
    if is_removed:
        failed_to_remove_files.append(abs_file_path)
    else:
        removed_files.append(abs_file_path)
    return failed_to_remove_files, removed_files

def _remove_dir(abs_path: str | bytes | os.PathLike):
    failed_to_remove_dirs, removed_dirs = [], []
    is_removed = silent_smb_friendly_remove_file_or_dir_tree(abs_path)
    if is_removed:
        removed_dirs.append(abs_path)
    else:
        failed_to_remove_dirs.append(abs_path)
    return failed_to_remove_dirs, removed_dirs

def _silent_common_path(files, dirs) -> str:
    local_dir: str = config.server['local_dir']
    nas_dir: str = config.nas['absolute_path']
    try:
        if not files and not dirs:
            return ""
        _fs_roots = set(files.keys())
        _ds_roots = set(dirs.keys())
        all_roots = list(_fs_roots.union(_ds_roots))
        try:
            _root_dir = os.path.commonpath(all_roots + [local_dir])
        except ValueError:
            try:
                _root_dir = os.path.commonpath(all_roots + [nas_dir])
            except ValueError:
                _root_dir = ""
                LOGGER.warning(f"Failed to find common root path for {_fs_roots} and {_ds_roots}")
        return _root_dir
    except Exception as _e:
        LOGGER.warning(f"{type(_e).__name__}: {_e}")

def _silent_list_files_and_dirs(common_path: str, files_and_dirs: list) -> str:
    _s = ""
    try:
        rel_paths = []
        for abs_path in files_and_dirs:
            try:
                _relative_path = os.path.relpath(abs_path, start=common_path)
            except ValueError:
                _relative_path = "COMMON_PATH_FAILED"
            rel_paths.append(_relative_path)
        rel_paths_str = ", ".join(rel_paths)
        return f" files and dirs in {common_path}\\...[{rel_paths_str}]"
    except Exception as _e:
        LOGGER.warning(f"{type(_e).__name__}: {_e}")
        return "FAILED TO BUILD LIST OF FILES AND DIRS"


def create_new_dir_or_clean_existing_dir(_path: str):
    """Create new project directory on server"""
    max_attempts_count = config.server['file_remove_attempts_before_raising_error']
    dwell_between_cycles = config.server['file_remove_attempts_cycle_time_sec']

    try:
        assert isinstance(max_attempts_count, int)
        assert max_attempts_count > 0
        assert isinstance(dwell_between_cycles, (float, int))
        assert dwell_between_cycles >= 0.0
        assert isinstance(_path, str)

        if not os.path.exists(_path):
            os.makedirs(_path)

        removed_files_and_dirs = []
        failed_files_and_dirs = []
        for i in range(1, max_attempts_count + 1):
            failed_files_and_dirs = []
            for root, dirs, files in os.walk(str(_path)):
                for _file in files:
                    failed_files, removed_files = _remove_file(os.path.join(root, _file))
                    removed_files_and_dirs.extend(removed_files)
                    failed_files_and_dirs.extend(failed_files)
                for _dir in dirs:
                    failed_dirs, removed_dirs = _remove_dir(os.path.join(root, _dir))
                    removed_files_and_dirs.extend(removed_dirs)
                    failed_files_and_dirs.extend(failed_dirs)
            if not failed_files_and_dirs:
                break
            time.sleep(dwell_between_cycles)

        if removed_files_and_dirs:
            LOGGER.info("OK removed" + _silent_list_files_and_dirs(_path, removed_files_and_dirs))
        assert not failed_files_and_dirs, \
            "FAILED to remove" + _silent_list_files_and_dirs(_path, failed_files_and_dirs)
        assert os.path.isdir(_path), "Failed, finally dir is not created after 'os.mkdirs'"
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise RuntimeError(f"Failed to create new or clean existing local project directory '{_path}'")


def sub_operation_abs_path(param: dict) -> str:
    try:
        local_dir: str = config.server['local_dir']
        sub_operation_relative_path: str = param['operation']['sub_operation_relative_path']
        _path = os.path.join(local_dir, sub_operation_relative_path)
        return _path
    except KeyError as _err:
        LOGGER.error(f"KeyError: {_err}")
        raise
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise

def generate_project_dir_name(pvid: int) -> str:
    """Generate project name"""
    try:
        return str(pvid)
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def extract_project_version_id_from_project_dir_name(dir_name: str):
    """Pair (inversion) function to 'generate_project_dir_name'"""
    try:
        return int(dir_name)
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def generate_operation_dir_name(execution_order: int) -> str:
    """Generate operation name"""
    try:
        assert isinstance(execution_order, int)
        assert execution_order >= 0
        return f"{execution_order:>04d}"
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def extract_execution_order_from_operation_dir_name(dir_name: str):
    """Pair (inversion) function to 'generate_operation_dir_name'"""
    try:
        return int(dir_name)
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def stop_server():
    config.server['is_server_failed'] |= True


@contextmanager
def opened_w_error(path: str, mode: str, encoding: str = 'utf-8'):
    try:
        _f = open(path, mode=mode, encoding=encoding)
    except IOError as err:
        yield None, err
    else:
        try:
            yield _f, None
        finally:
            _f.close()


def convert_dict_values_to_json_compatible_types(_input):
    """Converts all Postgres SQL data types not supported by json.dumps() to string in place."""
    try:
        if isinstance(_input, dict):
            output = {}
            for key, dict_val in _input.items():
                output[key] = convert_dict_values_to_json_compatible_types(dict_val)
        elif isinstance(_input, list):
            output = []
            for list_value in _input:
                output.append(convert_dict_values_to_json_compatible_types(list_value))
        elif isinstance(_input, bytes):
            output = str(bytes(_input))
        elif isinstance(_input, datetime):
            output = _input.strftime("%m/%d/%Y, %H:%M:%S")
        elif isinstance(_input, set):
            output = list(_input)
        elif isinstance(_input, StringDtype):
            output = str(_input)
        elif isinstance(_input, Int64Dtype):
            output = int(_input)
        elif isinstance(_input, Int16Dtype):
            output = int(_input)
        elif isinstance(_input, Int32Dtype):
            output = int(_input)
        elif isinstance(_input, Float64Dtype):
            output = float(_input)
        elif isinstance(_input, np.ndarray) and max(_input.shape) == 0:
            output = _input.item()
        elif isinstance(_input, np.ndarray):
            output = _input.tolist()
        elif isinstance(_input, pd.DataFrame):
            output = _input.to_dict(orient='records')
        elif isinstance(_input, pd.Series):
            output = _input.to_list()
        else:
            output = _input
        return output
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise RuntimeError(f"FAILED unsupported data type {type(_input)} for value '{_input}'")


def import_previous_operation_parameters_json_from_nas(param: dict) -> dict:
    # LOGGER.info("START func '_import_previous_operation_parameters'")
    try:
        eo = param['project']['execution_order']
        if eo == 0:
            previous_param = {}
        else:
            nas_dir: str = config.nas['absolute_path']
            project_dir_name: str = param['project']['project_dir_name']
            previous_e_o = eo - 1
            previous_operation_dir_name = param['table'][previous_e_o]['operation_dir_name']

            filepath = os.path.join(nas_dir, project_dir_name, previous_operation_dir_name, 'parameters.json')

            assert smbclient.path.isfile(filepath), f"File '{filepath}' not found for 'execution_order'={previous_e_o}"

            with smbclient.open_file(filepath, encoding='utf-8') as json_file:
                previous_param = json.load(json_file)
                assert previous_param, f"File '{filepath}' is empty for 'execution_order'={eo}"
                # corrected_previous_param = _substitute_previous_project_path_with_current(previous_param)

        return previous_param

    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise RuntimeError("Failed when importing previous operation parameters from 'parameters.json' located on NAS")


def remove_content_of_local_dir(abs_path: str,
                                exclude_file_extensions: list[str] | tuple[str] | None = None,
                                exclude_dirs: list[str] | tuple[str] | None = None,
                                is_remove_dirs: bool = True,
                                is_silent: bool = False,
                                max_attempts: int = 0):
    file_counter = 0
    dir_counter = 0
    attempts = max(1, config.server['file_remove_attempts_before_raising_error']) if max_attempts <= 0 else max_attempts
    repeat_time = config.server['file_remove_attempts_cycle_time_sec']

    def _remove(_dir):
        nonlocal file_counter
        nonlocal dir_counter
        if os.path.exists(_dir):
            for root, dirs, files in os.walk(os.path.normpath(_dir)):
                root: str
                # ----------------------------------------------------------
                for _file in files:
                    _file: str
                    file_extension = os.path.splitext(_file)[1]
                    if file_extension not in exclude_file_extensions:
                        os.remove(os.path.join(root, _file))
                        file_counter += 1
                # ----------------------------------------------------------
                if is_remove_dirs:
                    for _dir in dirs:
                        _dir: str
                        if _dir not in exclude_dirs:
                            abs_dir_path = os.path.join(root, _dir)
                            # Check if _dir is empty
                            if os.listdir(abs_dir_path):
                                _remove(abs_dir_path)
                            os.chmod(abs_dir_path, 0o777)
                            os.rmdir(abs_dir_path)
                            dir_counter += 1

    for count in range(1, attempts + 1):
        try:
            _remove(abs_path)
            break
        except Exception as _err:
            LOGGER.warning(
                f"FAILED {count} of {attempts} attempts to remove content of {abs_path} dir. "
                f"Wait {repeat_time} sec before try again. {type(_err).__name__}: {_err}")
            time.sleep(repeat_time)

    if not is_silent:
        if file_counter > 0 or dir_counter > 0:
            LOGGER.debug(f"REMOVED {file_counter} files and {dir_counter} dirs in '{abs_path}' {traceback.format_exc()}")
