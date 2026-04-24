import logging
from psycopg2 import sql
from forgelab.config import config


LOGGER = logging.getLogger(__name__)


def query_process_versions(pvid: int) -> dict:
    """Query 'process_versions' table where 'process_versions' order by 'execution_order'"""
    conn = config.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = 'process_versions';")
            _r = cur.fetchall()

            column_names = [i[0] for i in _r]
            column_str = ', '.join(column_names)

            query = f"SELECT {column_str} FROM process_versions WHERE process_version_id = {pvid} LIMIT 1;"
            cur.execute(query)
            _r = cur.fetchone()

            conn.commit()

        result = {column_name: _r[i] for i, column_name in enumerate(column_names)}
        return result
    except Exception as _err:
        LOGGER.error(_err)
        raise RuntimeError(
            f"Failed to query select a record 'process_versions' table "
            f"where 'process_version_id'={pvid} on SQL Server.")
    finally:
        config.put_connection(conn)


def query_server_pre_main(_process_version_id: int) -> dict:
    """Query 'server_pre_main' table where 'process_versions' order by 'execution_order'"""
    conn = config.get_connection()
    try:
        cur = conn.cursor()

        cur.execute("SELECT column_name, data_type FROM information_schema.columns "
                    "WHERE table_name = 'server_pre_main';")
        rows = cur.fetchall()

        column_names, data_types_sql = [], {}

        for column_name, data_type in rows:
            column_names.append(column_name)
            data_types_sql[column_name] = data_type

        columns_str = ', '.join(column_names)

        cur.execute(
            f"SELECT {columns_str} FROM server_pre_main "
            f"WHERE process_version_id = {_process_version_id} ORDER BY execution_order ASC")
        result_list = cur.fetchall()

        conn.commit()
        cur.close()

        result = {}
        for row in result_list:
            row_dict = {}
            for column_number, column_name in enumerate(column_names):
                input_value = row[column_number]
                _type = data_types_sql[column_name]

                if input_value is None:
                    output_value = None
                elif _type in ('timestamp', 'timestamp without time zone'):
                    output_value = input_value.strftime("%Y-%m-%d %H:%M:%S")
                elif _type == 'boolean':
                    output_value = bool(input_value)
                elif _type == 'bytea':
                    output_value = bytes(input_value)
                else:
                    output_value = input_value

                row_dict[column_name] = output_value

            execution_order = row_dict['execution_order']
            result[execution_order] = row_dict
        return result
    except Exception as _err:
        LOGGER.error(_err)
        raise RuntimeError(
            f"FAILED to query select all records of 'server_pre_main' table "
            f"where 'process_version_id'={_process_version_id} on SQL Server.")
    finally:
        config.put_connection(conn)


def query_post_operations(pvid: int) -> dict:
    """Query 'post_operations' table where 'process_versions' order by 'execution_order'"""
    conn = config.get_connection()
    try:
        cur = conn.cursor()
        selected_columns = ('process_version_id', 'execution_order', 'execution_id')
        pre_q = ("SELECT column_name, data_type FROM information_schema.columns "
                 "WHERE table_name = 'server_pre_main';")
        cur.execute(pre_q)
        pre_rows = cur.fetchall()

        column_names, data_types_sql = [], {}

        for column_name, data_type in pre_rows:
            if column_name not in selected_columns:
                continue
            column_names.append('pre.' + column_name)
            data_types_sql[column_name] = data_type

        post_q = ("SELECT column_name, data_type FROM information_schema.columns "
                  "WHERE table_name = 'post_operations';")
        cur.execute(post_q)
        post_rows = cur.fetchall()
        for column_name, data_type in post_rows:
            column_names.append('post.' + column_name)
            data_types_sql[column_name] = data_type

        query = (
            "SELECT {} FROM post_operations post"
            " JOIN server_pre_main pre ON pre.execution_id = post.execution_id"
            " WHERE pre.process_version_id = %s ORDER BY pre.execution_order ASC;")
        sql_query = sql.SQL(query).format(sql.SQL(', ').join(map(sql.Identifier, column_names)))
        sql_string = sql_query.as_string(conn).replace('"', '')
        cur.execute(sql_string, (pvid,))
        result_list = cur.fetchall()

        conn.commit()
        cur.close()

        result = {}
        for row in result_list:
            row_dict = {}
            for column_number, column_name in enumerate(column_names):
                input_value = row[column_number]
                _type = data_types_sql[column_name]

                if input_value is None:
                    output_value = None
                elif _type in ('timestamp', 'timestamp without time zone'):
                    output_value = input_value.strftime("%Y-%m-%d %H:%M:%S")
                elif _type == 'boolean':
                    output_value = bool(input_value)
                elif _type == 'bytea':
                    output_value = bytes(input_value)
                else:
                    output_value = input_value

                row_dict[column_name] = output_value

            execution_order = row_dict['execution_order']
            result[execution_order] = row_dict
        return result
    except Exception as _err:
        LOGGER.error(_err)
        raise RuntimeError(
            f"FAILED to query select all records of 'post_operations' table "
            f"where 'process_version_id'={pvid} on SQL Server.")
    finally:
        config.put_connection(conn)


def query_type_id_nnn(type_id: int, operation_id) -> tuple[list, list]:
    try:
        db_columns_names = config.lib['operations_library'].loc[type_id, 'db_column_names']
    except Exception as _err:
        LOGGER.error(_err)
        raise
    else:
        if not db_columns_names:
            # This type_id doesn't have any values in the database and
            # does not have corresponding 'operation_type_id_nnn' table.
            return [], []

    conn = config.get_connection()
    try:
        table_name = 'operations_type_id_' + str(type_id)
        sql_to_python = {
            'double precision': float,
            'real': float,
            'numeric': float,
            'decimal': float,
            'smallint': int,
            'integer': int,
            'bigint': int,
            'boolean': bool}
        cur = conn.cursor()
        query = f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table_name}';"
        cur.execute(query)
        rows = cur.fetchall()

        values, column_names, data_types = [], [], []

        for column_name, data_type in rows:
            if column_name == 'id':
                continue
            column_names.append(column_name)
            data_types.append(sql_to_python.get(data_type, str))

        query = "SELECT {} FROM {} WHERE id = %s LIMIT 1;"
        sql_query = sql.SQL(query).format(sql.SQL(', ').join(map(sql.Identifier, column_names)),
                                          sql.Identifier(table_name))
        cur.execute(sql_query, (operation_id,))
        input_tuple = cur.fetchone()

        conn.commit()
        cur.close()

        if input_tuple:
            for _index, _name in enumerate(column_names):
                _type = data_types[_index]
                _input_value = input_tuple[_index]
                _output_value = _type(_input_value)
                values.append(_output_value)
        return column_names, values
    except Exception as _err:
        LOGGER.error(_err)
        raise RuntimeError(f"FAILED to query select a record 'operations_type_id_nnn' table.")
    finally:
        config.put_connection(conn)


def query_processes(process_id: int) -> dict:
    """Query 'process' table where 'process_id'"""

    conn = config.get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = 'process';")
        _r = cur.fetchall()

        column_names = [i[0] for i in _r]
        column_str = ', '.join(column_names)

        query_text = f"SELECT {column_str} FROM process WHERE process_id = {process_id} LIMIT 1;"
        cur.execute(query_text)
        _r = cur.fetchone()

        conn.commit()
        cur.close()

        result = {column_name: _r[i] for i, column_name in enumerate(column_names)}

        return result
    except Exception as _err:
        LOGGER.error(_err)
        raise RuntimeError(
            f"POS FAILED func '_query_processes' occurred when query select a record 'process' table "
            f"where 'process_id'={process_id}")
    finally:
        config.put_connection(conn)
