import json
import os
import sys
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = '../configs/config.json'


def load_config(config_dir: str) -> dict | None:
    """Loads SQL connection parameters from config.yml file."""

    assert os.path.isdir(config_dir), f"Path '{config_dir}' does not exist."

    config_files = {
        os.path.splitext(_file)[0]: _file
        for _file in os.listdir(config_dir)
        if os.path.isfile(os.path.join(config_dir, _file))
    }

    assert config_files, f"Directory '{config_dir}' is empty."

    sql_param = {}

    for key, value in config_files.items():
        filename = os.path.join(config_dir, value)
        assert os.path.isfile(filename), f"File '{filename}' does not exist."

        try:

            with open(filename, 'r', encoding='utf-8') as stream:
                sql_param[key] = json.load(stream)

        except FileNotFoundError:
            print(f"Error: The file {filename} was not found.")
        except OSError as exception:
            error_code = exception.errno
            print(exception.strerror, error_code)
        except json.JSONDecodeError:
            print(f"Error: The file {filename} contains invalid JSON.")
        except Exception as _err:
            print(f"An unexpected error occurred: {_err}")

    return sql_param


def select_configuration(multiple_sql_param: dict) -> dict:
    """Selects configuration from multiple configurations."""

    assert isinstance(multiple_sql_param, dict)

    for _config in multiple_sql_param.values():
        assert 'db' in _config.keys()

    if len(multiple_sql_param) == 1:
        return [_value for _value in multiple_sql_param.values()][0]

    _menu = {str(_i): key for _i, key in enumerate(multiple_sql_param.keys())}

    print("\nSelect configuration:")
    for _i, _name in _menu.items():
        host = multiple_sql_param[_name]['db']['host']
        print(f"[{_i}] {_name} / {host}")
    while True:
        try:
            config_index = input('Enter configuration index: ')
            if config_index in _menu.keys():
                _config_name = _menu[config_index]
                sql_param = multiple_sql_param[_config_name]
                break
            else:
                print(f'Index {config_index} is out of range.')
        except ValueError:
            print('Please enter a number.')
    return sql_param


def print_psycopg2_exception(err):
    """function that handles and parses psycopg2 exceptions"""
    # get details about the exception
    err_type, err_obj, traceback = sys.exc_info()

    # get the line number when exception happens
    line_num = traceback.tb_lineno

    # print the connect() error
    print("\npsycopg2 ERROR:", err, "on line number:", line_num)
    print("psycopg2 traceback:", traceback, "-- type:", err_type)

    # psycopg2 extensions.Diagnostics object attribute
    print("\nextensions.Diagnostics:", err.diag)

    # print the pgcode and pgerror exceptions
    print("pgerror:", err.pgerror)
    print("pgcode:", err.pgcode, "\n")


def connect_to_db(sql_param, dbname: None | str = None) -> tuple:
    """Receives database name. Make connection to it. Returns connection and cursor."""
    con, cur = None, None

    config_db = sql_param['db']

    if dbname is None:
        dbname = config_db['base']

    try:
        # print('start connection')
        _host = config_db['host']
        _user = config_db['user']
        _pass = config_db['pass']
        _port = config_db['port']
        con = psycopg2.connect(host=_host, user=_user, password=_pass, dbname=dbname, port=_port)
        # print('start set autocommit')
        con.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        # connection.set_session(autocommit=True)
        # print('set cursor')
        cur = con.cursor()
        # print('finished connection')
    except psycopg2.DatabaseError as err:
        print(err)
    return con, cur


def close_connection(con, cur):
    """Close connection to the Postgres database server and to the database."""
    # connection.commit()
    cur.close()
    con.close()


def drop_database(sql_param):
    """Drop Forgelab database."""
    conn, cur = connect_to_db(sql_param, 'postgres')
    cur.execute(f"""
    -- Revoke CONNECT privilege
    REVOKE CONNECT ON DATABASE {sql_param['base']} FROM PUBLIC;
    
    -- Force disconnect all current connections
    SELECT pg_terminate_backend(pg_stat_activity.pid)
    FROM pg_stat_activity
    WHERE pg_stat_activity.datname = '{sql_param['base']}';""")
    cur.execute(f"DROP DATABASE {sql_param['base']};")
    close_connection(conn, cur)


def clear_database(sql_param: dict):
    """Drop Forgelab database."""
    connection, cursor = connect_to_db(sql_param)
    # cursor.execute(f"""
    # -- Revoke CONNECT privilege
    # REVOKE CONNECT ON DATABASE '{DATABASE}' FROM PUBLIC;
    #
    # -- Force disconnect all current connections
    # SELECT pg_terminate_backend(pg_stat_activity.pid)
    # FROM pg_stat_activity
    # WHERE pg_stat_activity.datname = '{DATABASE}';""")

    cursor.execute("""
    DO $$ 
    DECLARE 
        table_name text;
    BEGIN 
        FOR table_name IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') 
        LOOP
            EXECUTE 'DROP TABLE IF EXISTS ' || table_name || ' CASCADE';
        END LOOP;
    END $$;
    """)

    cursor.execute("""
    DO $$ 
    DECLARE 
        enum_type text;
    BEGIN 
        FOR enum_type IN (
            SELECT DISTINCT typname 
            FROM pg_type t 
            JOIN pg_enum e ON t.oid = e.enumtypid 
            WHERE t.typnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
        ) 
        LOOP
            EXECUTE 'DROP TYPE ' || enum_type || ' CASCADE';
        END LOOP;
    END $$;
    """)

    cursor.execute("""
    DO $$
    DECLARE 
        func_row text;
    BEGIN 
        FOR func_row IN (
            SELECT DISTINCT proname 
            FROM pg_proc 
            WHERE pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
        ) 
        LOOP
            EXECUTE 'DROP FUNCTION IF EXISTS ' || func_row || ' CASCADE';
        END LOOP;
    END $$;
    """)

    cursor.execute("""
DO $$ 
DECLARE 
    trigger_record record;
BEGIN 
    FOR trigger_record IN (
        SELECT DISTINCT tgname, tbl.relname 
        FROM pg_trigger t 
        JOIN pg_class tbl ON tbl.oid = t.tgrelid 
        WHERE tbl.relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
    ) 
    LOOP
        EXECUTE 'DROP TRIGGER IF EXISTS ' || trigger_record.tgname || ' ON ' || trigger_record.relname || ' CASCADE';
    END LOOP;
END $$;
    """)

    close_connection(connection, cursor)


def is_database_empty(sql_param: dict) -> bool:
    """Drop Forgelab database."""
    connection, cursor = connect_to_db(sql_param)

    _is_failed = False

    cursor.execute("SELECT EXISTS(SELECT tablename FROM pg_tables WHERE schemaname = 'public') LIMIT 1;")
    is_exist = cursor.fetchone()[0]
    if is_exist:
        print("Cleaning TABLES: FAILED")
        _is_failed |= True
    else:
        print("Cleaning TABLES: OK")

    cursor.execute("""
    SELECT DISTINCT typname 
    FROM pg_type t 
    JOIN pg_enum e ON t.oid = e.enumtypid 
    WHERE t.typnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public');
    """)
    records = cursor.fetchall()
    if records:
        print(
            "Cleaning ENAM: FAILED - "
            f"after cleaning there are {len(records)} ENAM types left: {[_name[0] for _name in records]}")
        _is_failed |= True
    else:
        print("Cleaning ENAM: OK")

    cursor.execute("""
    SELECT DISTINCT proname 
    FROM pg_proc 
    WHERE pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public');
    """)
    records = cursor.fetchall()
    if records:
        print(
            "Cleaning FUNCTIONS: FAILED - "
            f"after cleaning there are {len(records)} functions left: {[_name[0] for _name in records]}")
        _is_failed |= True
    else:
        print("Cleaning FUNCTIONS: OK")

    cursor.execute(f"""
    SELECT DISTINCT tgname, tbl.relname 
    FROM pg_trigger t 
    JOIN pg_class tbl ON tbl.oid = t.tgrelid 
    WHERE tbl.relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public');
    """)
    records = cursor.fetchall()
    if records:
        print(
            "Cleaning TRIGGERS: FAILED - "
            f"after cleaning there are {len(records)} triggers left: {[_name[0] for _name in records]}")
        _is_failed |= True
    else:
        print("Cleaning TRIGGERS: OK")

    close_connection(connection, cursor)
    return not _is_failed


def create_database(sql_param: dict):
    """Create Forgelab database."""
    connection, cursor = connect_to_db(sql_param, 'postgres')
    config_db = sql_param['db']
    cursor.execute(f"CREATE DATABASE {config_db['base']}")
    close_connection(connection, cursor)


def is_postgresql_db_exists(sql_param: dict) -> bool:
    """Returns True if the database exists, False otherwise."""
    connection, cursor = connect_to_db(sql_param, 'postgres')
    cursor.execute(
        """
        SELECT EXISTS(SELECT datname FROM pg_catalog.pg_database WHERE lower(datname) = lower(%s)) LIMIT 1;
        """,
        (sql_param['db']['base'],))
    is_db_exists = cursor.fetchone()[0]
    bool_is_db_exists = bool(is_db_exists)
    close_connection(connection, cursor)
    return bool_is_db_exists
