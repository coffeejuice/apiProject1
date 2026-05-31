"""Storage and file-transfer helpers."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import shutil
import time
from typing import Any, Iterator, Mapping

from app.config import settings
from app.services.files.paths import (
    build_parameters_json_path,
    get_shared_runs_root,
    is_smb_path,
    join_path,
)

try:
    import numpy as np
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    np = None

try:
    import pandas as pd
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    pd = None

try:
    import smbclient
    import smbclient.path as smb_path
    import smbclient.shutil as smb_shutil
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    smbclient = None
    smb_path = None
    smb_shutil = None

StrPath = str | os.PathLike[str]

LOGGER = logging.getLogger(__name__)


def _require_smb_support() -> None:
    if smbclient is None or smb_path is None or smb_shutil is None:
        raise RuntimeError("smbclient support is required for SMB paths but is not installed.")


def _remove_retry_attempts(attempts: int | None = None) -> int:
    value = settings.FILE_REMOVE_ATTEMPTS if attempts is None else attempts
    if value <= 0:
        raise ValueError("Removal attempts must be positive.")
    return value


def _remove_retry_seconds(retry_seconds: float | None = None) -> float:
    value = settings.FILE_REMOVE_RETRY_SECONDS if retry_seconds is None else retry_seconds
    if value < 0.0:
        raise ValueError("Removal retry delay must be non-negative.")
    return value


def path_exists(path: StrPath) -> bool:
    """Return whether a local or SMB path exists."""

    text = os.fspath(path)
    if is_smb_path(text):
        _require_smb_support()
        return smb_path.exists(text)
    return os.path.exists(text)


def path_is_file(path: StrPath) -> bool:
    """Return whether a local or SMB path is a file."""

    text = os.fspath(path)
    if is_smb_path(text):
        _require_smb_support()
        return smb_path.isfile(text)
    return os.path.isfile(text)


def path_is_dir(path: StrPath) -> bool:
    """Return whether a local or SMB path is a directory."""

    text = os.fspath(path)
    if is_smb_path(text):
        _require_smb_support()
        return smb_path.isdir(text)
    return os.path.isdir(text)


def ensure_directory(path: StrPath) -> None:
    """Create a local or SMB directory if it does not exist."""

    text = os.fspath(path)
    if is_smb_path(text):
        _require_smb_support()
        if not smb_path.exists(text):
            smbclient.makedirs(text)
        return
    Path(text).mkdir(parents=True, exist_ok=True)


def is_smb_file_server_available(root: StrPath | None = None) -> bool:
    """Check whether the configured shared root is reachable."""

    target = os.fspath(root or get_shared_runs_root())
    if not is_smb_path(target):
        return path_exists(target)
    try:
        return path_exists(target)
    except Exception as err:  # pragma: no cover - depends on network/runtime
        LOGGER.warning("SMB root '%s' is not accessible: %s", target, err)
        return False


def is_local_dir_exist(path: StrPath) -> bool:
    """Return whether a local directory exists."""

    return os.path.isdir(os.fspath(path))


def silent_remove_path(
    path: StrPath,
    *,
    attempts: int | None = None,
    retry_seconds: float | None = None,
) -> bool:
    """Best-effort removal of a file or directory tree, local or SMB."""

    text = os.fspath(path)
    if not path_exists(text):
        return False

    max_attempts = _remove_retry_attempts(attempts)
    dwell = _remove_retry_seconds(retry_seconds)

    for attempt in range(1, max_attempts + 1):
        try:
            if path_is_file(text):
                if is_smb_path(text):
                    _require_smb_support()
                    smbclient.unlink(text)
                else:
                    os.unlink(text)
            elif path_is_dir(text):
                if is_smb_path(text):
                    _require_smb_support()
                    smb_shutil.rmtree(text)
                else:
                    shutil.rmtree(text)
            else:
                raise RuntimeError(f"Path is neither file nor directory: {text}")
            return True
        except Exception as err:
            should_wait = dwell > 0 and attempt < max_attempts
            LOGGER.warning(
                "REMOVE FAILED at attempt %s/%s for '%s' with %s: %s%s",
                attempt,
                max_attempts,
                text,
                type(err).__name__,
                err,
                f". Waiting {dwell} sec before retry" if should_wait else "",
            )
            if should_wait:
                time.sleep(dwell)
    return False


def silent_smb_friendly_remove_file_or_dir_tree(
    abs_file_path: StrPath,
    *,
    attempts: int | None = None,
    retry_seconds: float | None = None,
) -> bool:
    """Compatibility wrapper around silent_remove_path()."""

    return silent_remove_path(
        abs_file_path,
        attempts=attempts,
        retry_seconds=retry_seconds,
    )


def smb_friendly_remove_file(
    abs_dir_path: StrPath,
    *,
    attempts: int | None = None,
    retry_seconds: float | None = None,
) -> bool:
    """Legacy compatibility wrapper for recursive removal."""

    return silent_remove_path(
        abs_dir_path,
        attempts=attempts,
        retry_seconds=retry_seconds,
    )


def create_new_dir_or_clean_existing_dir(path: StrPath) -> None:
    """Ensure a directory exists and remove all of its direct contents."""

    text = os.fspath(path)
    ensure_directory(text)

    failed_paths: list[str] = []
    removed_paths: list[str] = []
    for child in Path(text).iterdir():
        if silent_remove_path(child):
            removed_paths.append(str(child))
        else:
            failed_paths.append(str(child))

    if removed_paths:
        LOGGER.info("Removed %s stale entries under '%s'.", len(removed_paths), text)
    if failed_paths:
        failed_list = ", ".join(failed_paths)
        raise RuntimeError(f"Failed to remove stale entries under '{text}': {failed_list}")


@contextmanager
def opened_w_error(path: StrPath, mode: str, encoding: str = "utf-8") -> Iterator[tuple[Any, OSError | None]]:
    """Context manager returning `(file, error)` instead of raising open errors immediately."""

    try:
        handle = open(os.fspath(path), mode=mode, encoding=encoding)
    except OSError as err:
        yield None, err
    else:
        try:
            yield handle, None
        finally:
            handle.close()


def convert_to_json_compatible_types(value: Any) -> Any:
    """Recursively convert runtime values to JSON-serializable structures."""

    if isinstance(value, dict):
        return {key: convert_to_json_compatible_types(item) for key, item in value.items()}
    if isinstance(value, list):
        return [convert_to_json_compatible_types(item) for item in value]
    if isinstance(value, tuple):
        return [convert_to_json_compatible_types(item) for item in value]
    if isinstance(value, set):
        return [convert_to_json_compatible_types(item) for item in value]
    if isinstance(value, bytes):
        return str(bytes(value))
    if isinstance(value, datetime):
        return value.strftime("%m/%d/%Y, %H:%M:%S")
    if np is not None and isinstance(value, np.ndarray):
        return value.item() if value.ndim == 0 else value.tolist()
    if np is not None and isinstance(value, np.generic):
        return value.item()
    if pd is not None and isinstance(value, pd.DataFrame):
        return value.to_dict(orient="records")
    if pd is not None and isinstance(value, pd.Series):
        return value.to_list()
    return value


def convert_dict_values_to_json_compatible_types(value: Any) -> Any:
    """Compatibility wrapper around convert_to_json_compatible_types()."""

    return convert_to_json_compatible_types(value)


def read_json_file(path: StrPath, *, encoding: str = "utf-8") -> Any:
    """Read JSON from a local or SMB path."""

    text = os.fspath(path)
    if is_smb_path(text):
        _require_smb_support()
        with smbclient.open_file(text, mode="r", encoding=encoding) as handle:
            return json.load(handle)
    with open(text, "r", encoding=encoding) as handle:
        return json.load(handle)


def write_json_file(
    path: StrPath,
    payload: Any,
    *,
    encoding: str = "utf-8",
    indent: int = 2,
) -> None:
    """Write JSON to a local path."""

    text = os.fspath(path)
    if is_smb_path(text):
        raise RuntimeError("write_json_file does not support SMB paths yet.")
    parent = os.path.dirname(text)
    if parent:
        ensure_directory(parent)
    with open(text, "w", encoding=encoding) as handle:
        json.dump(convert_to_json_compatible_types(payload), handle, indent=indent)


def import_previous_operation_parameters_json_from_nas(
    param: Mapping[str, Any] | None = None,
    *,
    project_dir_name: str | None = None,
    previous_operation_dir_name: str | None = None,
    shared_root: StrPath | None = None,
) -> dict[str, Any]:
    """Load the previous operation's parameters.json from shared storage."""

    if param is not None:
        project = param["project"]
        table = param["table"]
        if not isinstance(project, Mapping) or not isinstance(table, Mapping):
            raise TypeError("param must contain mapping values for 'project' and 'table'.")
        execution_order = project["execution_order"]
        if not isinstance(execution_order, int):
            raise TypeError("param['project']['execution_order'] must be an integer.")
        if execution_order == 0:
            return {}
        project_dir_name = project["project_dir_name"]
        previous_operation_dir_name = table[execution_order - 1]["operation_dir_name"]

    if not project_dir_name or not previous_operation_dir_name:
        raise ValueError("project_dir_name and previous_operation_dir_name must be provided.")

    root = os.fspath(shared_root or get_shared_runs_root())
    parameters_path = build_parameters_json_path(
        root,
        project_dir_name,
        previous_operation_dir_name,
    )
    payload = read_json_file(parameters_path)
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object in '{parameters_path}'.")
    return payload


def remove_content_of_local_dir(
    abs_path: StrPath,
    exclude_file_extensions: list[str] | tuple[str, ...] | None = None,
    exclude_dirs: list[str] | tuple[str, ...] | None = None,
    is_remove_dirs: bool = True,
    is_silent: bool = False,
    max_attempts: int = 0,
) -> None:
    """Remove local directory contents with optional exclusions."""

    path = Path(abs_path)
    if not path.exists():
        return
    if not path.is_dir():
        raise ValueError(f"Expected a directory path, got '{path}'.")

    excluded_extensions = set(exclude_file_extensions or [])
    excluded_dirs = set(exclude_dirs or [])
    attempts = _remove_retry_attempts(max_attempts if max_attempts > 0 else None)
    dwell = _remove_retry_seconds()

    file_counter = 0
    dir_counter = 0

    def _remove_dir_contents(directory: Path) -> None:
        nonlocal file_counter, dir_counter
        for child in directory.iterdir():
            if child.is_file():
                if child.suffix not in excluded_extensions:
                    child.unlink()
                    file_counter += 1
            elif child.is_dir():
                if child.name in excluded_dirs:
                    continue
                _remove_dir_contents(child)
                if is_remove_dirs:
                    child.chmod(0o777)
                    child.rmdir()
                    dir_counter += 1

    for attempt in range(1, attempts + 1):
        try:
            _remove_dir_contents(path)
            break
        except Exception as err:
            LOGGER.warning(
                "FAILED %s of %s attempts to remove content of '%s'. Wait %s sec before retry. %s: %s",
                attempt,
                attempts,
                path,
                dwell,
                type(err).__name__,
                err,
            )
            if attempt < attempts and dwell > 0:
                time.sleep(dwell)

    if not is_silent and (file_counter > 0 or dir_counter > 0):
        LOGGER.debug("REMOVED %s files and %s dirs in '%s'.", file_counter, dir_counter, path)
