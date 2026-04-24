"""Path-construction helpers for local, temporary, and shared artifacts."""

from __future__ import annotations

import ntpath
import os
import re
from typing import Mapping

from app.config import settings

StrPath = str | os.PathLike[str]

RUNS_DIRNAME = "runs"
DIES_DIRNAME = "dies"
MATERIALS_DIRNAME = "materials"
OPERATIONS_DIRNAME = "operations"
PPT_DIRNAME = "ppt"
PARAMETERS_FILE_NAME = "parameters.json"

_WINDOWS_DRIVE_PATTERN = re.compile(r"^[A-Za-z]:[\\/]")


def is_smb_path(path: StrPath) -> bool:
    """Return True when path points to an SMB or UNC location."""

    value = os.fspath(path)
    return value.startswith("smb://") or value.startswith("\\\\")


def is_windows_drive_path(path: StrPath) -> bool:
    """Return True for absolute Windows drive-letter paths."""

    return bool(_WINDOWS_DRIVE_PATTERN.match(os.fspath(path)))


def join_path(root: StrPath, *parts: StrPath) -> str:
    """Join paths while preserving UNC/Windows path semantics on non-Windows hosts."""

    root_text = os.fspath(root)
    part_text = [os.fspath(part) for part in parts]
    if is_smb_path(root_text) or is_windows_drive_path(root_text):
        return ntpath.join(root_text, *part_text)
    return os.path.join(root_text, *part_text)


def get_local_runs_root() -> str:
    """Return the root directory for local simulation artifacts."""

    return join_path(settings.TEMP_FILES_ROOT, RUNS_DIRNAME)


def get_shared_runs_root() -> str:
    """Return the root directory for shared simulation artifacts."""

    return join_path(settings.NAS_MOUNT_ROOT, RUNS_DIRNAME)


def get_library_root() -> str:
    """Return the library data root directory."""

    return settings.LIBRARY_FILES_ROOT


def get_dies_library_root() -> str:
    return join_path(get_library_root(), DIES_DIRNAME)


def get_materials_library_root() -> str:
    return join_path(get_library_root(), MATERIALS_DIRNAME)


def get_operations_library_root() -> str:
    return join_path(get_library_root(), OPERATIONS_DIRNAME)


def get_ppt_library_root() -> str:
    return join_path(get_library_root(), PPT_DIRNAME)


def generate_project_dir_name(project_version_id: int) -> str:
    """Generate the run directory name from an integer run id."""

    if isinstance(project_version_id, bool) or not isinstance(project_version_id, int):
        raise TypeError("project_version_id must be an integer.")
    if project_version_id < 0:
        raise ValueError("project_version_id must be non-negative.")
    return str(project_version_id)


def extract_project_version_id_from_project_dir_name(dir_name: str) -> int:
    """Inverse of generate_project_dir_name()."""

    return int(dir_name)


def generate_operation_dir_name(execution_order: int) -> str:
    """Generate a zero-padded operation directory name."""

    if isinstance(execution_order, bool) or not isinstance(execution_order, int):
        raise TypeError("execution_order must be an integer.")
    if execution_order < 0:
        raise ValueError("execution_order must be non-negative.")
    return f"{execution_order:>04d}"


def extract_execution_order_from_operation_dir_name(dir_name: str) -> int:
    """Inverse of generate_operation_dir_name()."""

    return int(dir_name)


def build_project_dir(root: StrPath, project_version_id: int) -> str:
    """Return an absolute project/run directory under the given root."""

    return join_path(root, generate_project_dir_name(project_version_id))


def build_operation_dir(root: StrPath, project_version_id: int, execution_order: int) -> str:
    """Return an absolute operation directory under the given root."""

    return join_path(
        build_project_dir(root, project_version_id),
        generate_operation_dir_name(execution_order),
    )


def build_sub_operation_dir(root: StrPath, sub_operation_relative_path: StrPath) -> str:
    """Return an absolute path for a stored relative sub-operation path."""

    return join_path(root, sub_operation_relative_path)


def sub_operation_abs_path(
    param: Mapping[str, object],
    *,
    local_root: StrPath | None = None,
) -> str:
    """Compatibility helper for old worker code using param['operation']['sub_operation_relative_path']."""

    operation = param["operation"]
    if not isinstance(operation, Mapping):
        raise TypeError("param['operation'] must be a mapping.")
    relative_path = operation["sub_operation_relative_path"]
    if not isinstance(relative_path, str):
        raise TypeError("param['operation']['sub_operation_relative_path'] must be a string.")
    return build_sub_operation_dir(local_root or get_local_runs_root(), relative_path)


def build_parameters_json_path(
    root: StrPath,
    project_dir_name: str,
    operation_dir_name: str,
) -> str:
    """Return the conventional parameters.json path for an operation directory."""

    return join_path(root, project_dir_name, operation_dir_name, PARAMETERS_FILE_NAME)
