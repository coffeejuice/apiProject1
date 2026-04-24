import logging
import time
import io


LOGGER = logging.getLogger(__name__)


UNICODE_BORDER_CHARS = {
    '\\' : b'\xe2\x95\x9a',
    '-'  : b'\xe2\x95\x90',
    '/'  : b'\xe2\x95\x9d',
    '|'  : b'\xe2\x95\x91',
    '+'  : b'\xe2\x95\x94',
    '%'  : b'\xe2\x95\x97',
}


def is_samba_path(_path: str) -> bool:
    return _path.startswith('smb://') or _path.startswith('\\\\')


def decode(x):
    return ''.join(UNICODE_BORDER_CHARS.get(i, i.encode('utf-8')).decode('utf-8') for i in x)


def log_error(_err, err_name, task_id: str, time_start, traceback_string: str):
    # coding: utf8
    try:
        duration = str(round(time.monotonic() - time_start, 2))

        msg_list = [f"Duration {duration}s {err_name}: {_err}",
                    "TRACEBACK:"]

        if isinstance(traceback_string, str) and len(traceback_string) > 0:
            msg_list.extend(traceback_string.splitlines())

        msg_len = max(3, max([len(msg) for msg in msg_list]))

        f = io.StringIO()
        print("\n".join(msg_list), file=f)
        msg_str = f.getvalue()
        f.close()

        LOGGER.error(task_id + " " + b'\xe2\x95\x94'.decode('utf-8') + b'\xe2\x95\x90'.decode('utf-8') * msg_len + b'\xe2\x95\x97'.decode('utf-8'))
        for msg in msg_str.splitlines():
            LOGGER.error(task_id + " " + b'\xe2\x95\x91'.decode('utf-8') + msg.ljust(msg_len) + b'\xe2\x95\x91'.decode('utf-8'))
        LOGGER.error(task_id + " " + b'\xe2\x95\x9a'.decode('utf-8') + b'\xe2\x95\x90'.decode('utf-8') * msg_len + b'\xe2\x95\x9d'.decode('utf-8'))
    except Exception as _internal_err:
        LOGGER.error(f"{type(_internal_err).__name__}: {_internal_err}")
        raise
