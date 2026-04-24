from __future__ import annotations

import json
import os
import logging

import psycopg2.extensions
from psycopg2 import sql, OperationalError, DatabaseError

LOGGER = logging.getLogger(__name__)


def walk_through_project_dir_return_list_of_last_operation_paths(root_path: str, pvid: int, eo_list: list[int]) -> dict:
    project_dir = str(pvid)
    eo_dir_names = {eo: str(eo).zfill(4) for eo in eo_list}

    assert isinstance(eo_list, list), f"Expected list of integers, got '{type(eo_list)}'."
    assert all(isinstance(eo, int) for eo in eo_list), f"Expected list of integers, got '{eo_list}'."
    assert os.path.exists(root_path), f"Root path '{root_path}' does not exist."
    assert os.path.exists(os.path.join(root_path, project_dir)), \
        f"Project directory '{project_dir}' does not exist in root path {root_path}."

    eo_relative_paths = {eo: os.path.join(project_dir, eo_dir) for eo, eo_dir in eo_dir_names.items()
                         if os.path.exists(os.path.join(root_path, project_dir, eo_dir))}

    sim_dir_names = {}
    for eo, eo_relative_path in eo_relative_paths.items():
        eo_abs_path = os.path.join(root_path, eo_relative_path)
        # List all dirs inside 'eo_relative_path' path
        eo_dirs = [d for d in os.listdir(eo_abs_path)
                   if os.path.isdir(os.path.join(eo_abs_path, d)) and d[:4].isdigit()]

        if not eo_dirs:
            continue

        # Sort dirs by first 4 symbols which are digits
        eo_dirs.sort(key=lambda x: int(x[:4]))
        # Find a dir with the biggest number
        last_sim_dir = eo_dirs[-1]
        sim_relative_path = os.path.join(eo_relative_path, last_sim_dir)
        sim_dir_names[eo] = sim_relative_path

    return sim_dir_names


def walk_through_project_dir_return_list_of_operation_dir_names(root_path: str, pvid: int, eo_list: list[int]) -> dict:
    project_dir = str(pvid)
    eo_dir_names = {eo: str(eo).zfill(4) for eo in eo_list}

    assert isinstance(eo_list, list), f"Expected list of integers, got '{type(eo_list)}'."
    assert all(isinstance(eo, int) for eo in eo_list), f"Expected list of integers, got '{eo_list}'."
    assert os.path.exists(root_path), f"Root path '{root_path}' does not exist."
    assert os.path.exists(os.path.join(root_path, project_dir)), \
        f"Project directory '{project_dir}' does not exist in root path {root_path}."

    operation_dir_names = {eo: eo_dir for eo, eo_dir in eo_dir_names.items()
                           if os.path.exists(os.path.join(root_path, project_dir, eo_dir))}

    return operation_dir_names


def _query_select_empty_sub_operation_relative_path(conn: psycopg2.extensions.connection, pvid: int, column_name: str
                                                    ) -> list[int]:
    select_query = (
        f"SELECT execution_order FROM server_pre_main "
        f"WHERE process_version_id = %s "
        f"AND ({column_name} IS NULL OR {column_name} = '') "
        f"ORDER BY execution_order;")

    try:
        cur = conn.cursor()
        cur.execute(select_query, (pvid,))
        records = cur.fetchall()
        conn.commit()
        cur.close()
        eo_list = [record[0] for record in records]

    except OperationalError as _err:
        print(f"OperationalError: {_err}")
    except DatabaseError as _err:
        print(f"DatabaseError: {_err}")
    except KeyError as _err:
        print(f"POS KeyError: '{_err}'.")
    except Exception as _err:
        print(f"POS Exception: {_err}")
    else:
        return eo_list
    raise RuntimeError("POS FAILED func '_query_select_empty_sub_operation_relative_path'")


def _query_set_path_and_post_status(conn: psycopg2.extensions.connection, pvid: int, column_name: str, values: dict):
    """
    Set 'sub_operation_relative_path' and 'post_status'='queue' for every record in 'eo_list'.
    """

    query = f"""
    UPDATE server_pre_main SET {column_name} = %(value_str)s 
    WHERE process_version_id = %(pvid)s AND execution_order = %(eo)s;"""

    for eo, _val in values.items():
        case_msg = f"FAILED: SET sub_operation_relative_path = '{_val}' WHERE eo = {eo}"
        try:
            cur = conn.cursor()
            cur.execute(query, {'value_str': _val, 'pvid': pvid, 'eo': eo})
            conn.commit()
            cur.close()
        except OperationalError as _err:
            print(f"{case_msg} OperationalError: {_err}")
        except DatabaseError as _err:
            print(f"{case_msg} DatabaseError: {_err}")
        except Exception as _err:
            print(f"{case_msg} Exception: {_err}")
        else:
            print(f"OK: SET sub_operation_relative_path = '{_val}' WHERE eo = {eo}")


def _load_config(root_dir: str, filename: str) -> dict:
    """Receives '*.json' file name. Returns dictionary. If error, stops server."""
    case_msg = f"occurred while loading config file {filename} form {root_dir} with Error:"
    try:
        abs_path = os.path.join(root_dir, 'config', filename)
        with open(abs_path, 'r', encoding='utf-8') as stream:
            config = json.load(stream)
            assert config, f"Failed loading config file '{abs_path}'."
    except AssertionError as _err:
        LOGGER.error(f"POS AssertionError {case_msg} {_err}")
    except FileNotFoundError as _err:
        LOGGER.critical(f"POS FileNotFoundError {case_msg} {_err}")
    except OSError as exception:
        LOGGER.critical(f"POS OSError {case_msg} {exception.strerror} {exception.errno}")
    except json.JSONDecodeError as _err:
        LOGGER.critical(f"POS json.JSONDecodeError {case_msg} {_err}")
    except Exception as _err:
        LOGGER.critical(f"Some Error {case_msg} {_err}")
    else:
        return config
    raise RuntimeError(f"POS FAILED func '_load_config' {case_msg}")


def get_connection(config: dict) -> psycopg2.extensions.connection:
    conn = psycopg2.connect(
        user=config['user'],
        password=config['pass'],
        host=config['host'],
        port=config['port'],
        database=config['base'])
    cur = conn.cursor()
    cur.execute("SELECT 1;")
    conn.commit()
    cur.close()
    return conn


def _query_nas_config(conn) -> dict:
    columns = ('dns_domain', 'hostname', 'ip', 'public_dir')
    query = "SELECT {} FROM servers WHERE type = 'file_server' ORDER BY time_started ASC LIMIT 1;"

    sql_query = sql.SQL(query).format(sql.SQL(', ').join(map(sql.Identifier, columns)))

    cur = conn.cursor()
    cur.execute(sql_query)
    result = cur.fetchone()
    conn.commit()
    cur.close()

    assert result, "Query result is empty."
    values_dict = {key: val for key, val in zip(columns, result)}
    return values_dict


def _query_absolute_path_to_file_server_public_dir(conn) -> str:
    file_server_config = _query_nas_config(conn)

    _ip = file_server_config['ip']
    _public_dir = file_server_config['public_dir']
    file_server_path = fr"\\{_ip}\{_public_dir}"
    assert os.path.isdir(file_server_path), (f"File Server's public directory '{_public_dir}' "
                                             f"does not exist or not accessible.")
    return file_server_path


def fill_empty_sub_operation_relative_path(conn: psycopg2.extensions.connection, pvid: int, file_server_path: str):
    eo_list = _query_select_empty_sub_operation_relative_path(conn, pvid, column_name='sub_operation_relative_path')
    sim_dir_names = walk_through_project_dir_return_list_of_last_operation_paths(file_server_path, pvid, eo_list)
    _query_set_path_and_post_status(conn, pvid, column_name='sub_operation_relative_path', values=sim_dir_names)


def fill_empty_extract_path(conn: psycopg2.extensions.connection, pvid: int, file_server_path: str):
    eo_list = _query_select_empty_sub_operation_relative_path(
        conn, pvid, column_name='billet_file_sub_operation_extract_relative_path')
    sim_dir_names = walk_through_project_dir_return_list_of_last_operation_paths(file_server_path, pvid, eo_list)
    extract_names = {eo: os.path.join(values, r"extract\Object00001.KEY") for eo, values in sim_dir_names.items()}
    _query_set_path_and_post_status(conn, pvid, column_name='billet_file_sub_operation_extract_relative_path',
                                    values=extract_names)


def fill_simulation_status(conn: psycopg2.extensions.connection, pvid: int, file_server_path: str):
    select_query = "SELECT execution_order FROM server_pre_main WHERE process_version_id = %s ORDER BY execution_order;"
    cur = conn.cursor()
    cur.execute(select_query, (pvid,))
    records = cur.fetchall()
    conn.commit()
    cur.close()
    eo_list = [record[0] for record in records]

    sim_dir_names = walk_through_project_dir_return_list_of_last_operation_paths(file_server_path, pvid, eo_list)
    simulation_status = {eo: 'finished' if eo in sim_dir_names.keys() else 'stop' for eo in eo_list}
    _query_set_path_and_post_status(conn, pvid, column_name='simulation_status', values=simulation_status)


def fill_empty_operation_dir_name(conn: psycopg2.extensions.connection, pvid: int, file_server_path: str):
    eo_list = _query_select_empty_sub_operation_relative_path(conn, pvid, column_name='operation_dir_name')
    operation_dir_names = walk_through_project_dir_return_list_of_operation_dir_names(file_server_path, pvid, eo_list)

    pptx_dirs = {eo: os.path.join(file_server_path, str(pvid), val, 'pptx')
                 for eo, val in operation_dir_names.items()}
    is_pptx_dir = {eo: True if os.path.isdir(pptx_dir) else False for eo, pptx_dir in pptx_dirs.items()}
    pptx_files = {eo: os.path.join(pptx_dir, f"{str(pvid)}_{str(eo).zfill(4)}.pptx")
                  for eo, pptx_dir
                  in pptx_dirs.items()}
    is_pptx_file = {eo: True if os.path.isfile(pptx_file) else False
                    for eo, pptx_file
                    in pptx_files.items()}

    post_status = {}
    for eo in pptx_dirs.keys():
        if is_pptx_dir[eo] and is_pptx_file[eo]:
            post_status[eo] = 'finished'
        elif eo == 0:
            post_status[eo] = 'stop'
        else:
            post_status[eo] = 'queue'

    _query_set_path_and_post_status(conn, pvid, column_name='operation_dir_name', values=operation_dir_names)
    _query_set_path_and_post_status(conn, pvid, column_name='post_status', values=post_status)


def query_restore_path_and_status(pvid: int):
    root_dir = os.path.dirname(os.path.dirname(__file__))
    config = _load_config(root_dir, 'database.json')
    conn = get_connection(config)
    file_server_path = _query_absolute_path_to_file_server_public_dir(conn)
    fill_empty_extract_path(conn, pvid, file_server_path)
    fill_empty_sub_operation_relative_path(conn, pvid, file_server_path)
    fill_empty_operation_dir_name(conn, pvid, file_server_path)
    fill_simulation_status(conn, pvid, file_server_path)
