import os
import json
# import psycopg2
import psycopg2.extensions


def find_all_files_id_dir(_json_dir: str) -> list:
    """Returns a list of full paths to files, found in the '_json_dir' directory."""
    _json_files = []
    for root, dirs, files in os.walk(_json_dir):
        for file in files:
            if file.endswith(".json"):
                _json_files.append(file)
    return _json_files


def load_config(filename: str) -> dict | None:
    """Loads SQL connection parameters from config.json file."""
    try:
        with open(filename, 'r', encoding='utf-8') as stream:
            return json.load(stream)
    except FileNotFoundError:
        print(f"Error: The file {filename} was not found.")
    except OSError as exception:
        error_code = exception.errno
        print(exception.strerror, error_code)
    except json.JSONDecodeError:
        print(f"Error: The file {filename} contains invalid JSON.")
    except Exception as _err:
        print(f"An unexpected error occurred: {_err}")
    return None


def insert_config_json(_cur: psycopg2.extensions.cursor, _server_type: str, _config_dict: dict):
    """
    Receives a cursor and a dict.
    Makes a query to insert a dict into the 'config_json' column of 'config' table as 'jsonb' type.
    """
    assert isinstance(_config_dict, dict), "Error in 'insert_config_json': config is not a dict."
    _config_json = json.dumps(_config_dict)
    _cur.execute(
        f"INSERT INTO config (server_type, config_json) VALUES ('{_server_type}', '{_config_json}');"
    )


def drop_records_in_config(_cur: psycopg2.extensions.cursor):
    """Drop all records in 'config' table if existed."""
    _cur.execute(
        f"DELETE FROM config;"
    )


def insert_config(_cur: psycopg2.extensions.cursor, _root_dir: str):
    drop_records_in_config(_cur)
    _json_dir = f"{_root_dir}\\config_json\\"
    _json_files = find_all_files_id_dir(_json_dir)
    for _file in _json_files:
        _full_path = os.path.join(_json_dir, _file)
        _config_json = load_config(_full_path)
        _server_type = os.path.splitext(_file)[0]
        insert_config_json(_cur, _server_type, _config_json)
