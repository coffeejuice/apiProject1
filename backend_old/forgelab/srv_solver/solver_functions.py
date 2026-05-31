import logging
import os
import shutil
from subprocess import run, PIPE

from forgelab.config import config
from forgelab.common.file_operations import sub_operation_abs_path

LOGGER = logging.getLogger(__name__)


def run_solver(_param: dict):
    """Run DEFORM solver"""
    try:
        _set_mpi(_param)
        __run_solver(_param)
    except Exception as _err:
        LOGGER.error(f"Exception: {_err}")
        raise RuntimeError(f"FAILED func 'run_solver' with Exception: {_err}")


def _set_mpi(_param: dict):
    try:
        sub_operation_path = sub_operation_abs_path(_param)
        computer_name = config.server['name']
        cpu_count = config.server['cpu_count']
        mpi_settings = f'-env MPICH_SHMSIZE = 52000000\n{computer_name} {cpu_count}\n'
        mpi_filepath = os.path.join(sub_operation_path, "DEF_MPIenv.DAT")
        mpi_p4_filepath = os.path.join(sub_operation_path, "DEF_MPIp4penv.DAT")
    except KeyError as _err:
        raise RuntimeError(f"FAILED func '_set_mpi' with KeyError: {_err}")
    except Exception as _err:
        raise RuntimeError(f"FAILED func '_set_mpi' with Some Error: {_err}")

    case_msg = "FAILED func '_set_mpi' when setting '{mpi_filepath}'"
    try:
        with open(mpi_filepath, "w", encoding="UTF-8") as mpi_file:
            mpi_file.write(mpi_settings)
        shutil.copy(mpi_filepath, mpi_p4_filepath)
    except Exception as _err:
        raise RuntimeError(f"{case_msg} with Some Error: {_err}")


def __run_solver(_param: dict):
    try:
        # TODO: remove redundant back slashes in 'sub_operation_path'
        deform_installation_path = config.server['deform_installation_path']
        sub_operation_path = sub_operation_abs_path(_param)
        template_name = _param['operation']['template_name']
        exe_path = os.path.join(deform_installation_path, "DEF_SIMULATION.EXE")
        cmd2 = f"ENV_PROBLEM_ID_TAG={template_name}.DB"
        cmd3 = f"ENV_RUNNING_DIRECTORY_TAG={sub_operation_path}"
        cmd4 = "ENV_JOB_DIMENSION_TAG=3"
        cmd5 = "ENV_JOB_TYPE_TAG=E_MO_JOB"
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise
    try:
        run(
            [exe_path, cmd2, cmd3, cmd4, cmd5],
            encoding='ascii',
            check=False,
            text=True,
            stdout=PIPE,
            cwd=sub_operation_path)
        LOGGER.info(
            f"Run Solver with {exe_path = }, {cmd2 = }, {cmd3 = }, {cmd4 = }, {cmd5 = }, cwd = {sub_operation_path}")
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise
