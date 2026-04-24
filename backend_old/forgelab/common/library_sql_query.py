# print(f'__file__={__file__:<35} | __name__={__name__:<25} | __package__={str(__package__):<25}')
import logging
import os
import json
import numpy as np
import pandas as pd
import psycopg2
import psycopg2.extensions
from psycopg2 import sql

from forgelab.common.matlib import Material


# create logger
LOGGER = logging.getLogger(__name__)


SQL_TO_PANDAS = {
    'double precision': pd.Float64Dtype(),
    'real': pd.Float64Dtype(),
    'numeric': pd.Float64Dtype(),
    'decimal': pd.Float64Dtype(),
    #
    'smallint': pd.Int16Dtype(),
    'integer': pd.Int32Dtype(),
    'bigint': pd.Int64Dtype(),
    #
    # 'bytea': memoryview,
    #
    'boolean': pd.BooleanDtype(),
    #
    'character varying': pd.StringDtype(),
    'USER-DEFINED': pd.StringDtype(),
    #
    'timestamp without time zone': pd.StringDtype()
}


def select_language(_string_value: str, _language_code: str = 'EN') -> str:
    """Receives string, containing translation in many languages. Returns list of strings in selected language."""
    if not isinstance(_string_value, str):
        return _string_value
    result = [_block.split('|')[1] for _block in _string_value.split('LANGUAGE|') if _block.startswith(_language_code)]
    if result:
        return result[0]
    return ''


def convert_string(_string_value):
    """Receives a string. Returns list. If string contains multiple languages, then select only 'EN' translation."""

    if not isinstance(_string_value, str):
        return _string_value

    if _string_value.startswith('LANGUAGE|'):
        return select_language(_string_value, 'EN')

    if _string_value.startswith('{') and _string_value.endswith('}'):
        return json.loads(_string_value)

    if '|' in _string_value:
        return _string_value.split('|')

    return _string_value


def convert_records_to_dict(columns, records):
    return [
        {column_name: record[index] for index, column_name in enumerate(columns)}
        for record in records
    ]


def convert_records_to_pandas(data_array,
                              column_names,
                              data_types: dict,
                              index_column: str = None,
                              is_exclude_index_column=True
                              ) -> pd.DataFrame:
    try:
        if index_column:
            index_of_index_column = column_names.index(index_column)
            indices = [record[index_of_index_column] for record in data_array]
        else:
            indices = list(range(len(data_array)))
        df = pd.DataFrame(data_array, columns=column_names, index=indices)
        if data_types:
            dtc = data_types.copy()
            if 'tooltip_image' in dtc:
                del dtc['tooltip_image']
            df = df.astype(dtc)
        if is_exclude_index_column:
            df.drop(columns=[index_column], inplace=True)

    except KeyError as _err:
        LOGGER.error(f"KeyError: {_err}")
        raise KeyError(_err)
    except ValueError as _err:
        LOGGER.error(f"ValueError: {_err}")
        raise KeyError(_err)
    except Exception as _err:
        LOGGER.error(f"Exception: {_err}")
        raise RuntimeError(_err)
    else:
        return df


def sorting_generator(_list: list, _scores: list) -> list:
    """Generator for sorting list by scores"""
    for _i in range(len(_list)):
        _min_score = min(_scores)
        _min_score_index = _scores.index(_min_score)
        _next_item = _list.pop(_min_score_index)
        del _scores[_min_score_index]
        yield _next_item


def get_operations_library(_cur):
    table_name = 'operations_library'
    index_column_name = 'type_id'
    is_exclude_index_column = False
    order_by = 'type_id'

    column_names, data_types = get_columns_and_data_types(_cur, table_name=table_name, exclude_columns=[])
    records = query_table(_cur, table_name, column_names, order_by=order_by)
    ol = convert_records_to_pandas(records, column_names, data_types,
                                   index_column=index_column_name,
                                   is_exclude_index_column=is_exclude_index_column)
    ol['library_name'] = ol['library_name'].apply(select_language)
    ol['process_name'] = ol['process_name'].apply(select_language)
    ol['labels'] = ol['labels'].apply(select_language)
    ol['db_column_names'] = ol['db_column_names'].apply(string_to_list)
    return ol, records, column_names


def query_table(_cur, table_name: str, column_names: list, order_by: str = '') -> list:
    sql_table = sql.Identifier(table_name)
    sql_columns = sql.SQL(',').join(map(sql.Identifier, column_names))
    if order_by:
        order_by_sql = sql.Identifier(order_by)
        dynamic_query = sql.SQL("SELECT {} FROM {} ORDER BY {} ASC;").format(sql_columns, sql_table, order_by_sql)
    else:
        dynamic_query = sql.SQL("SELECT {} FROM {};").format(sql_columns, sql_table)
    _cur.execute(dynamic_query)
    records = _cur.fetchall()
    return records


def find_child_ids_for_dataframe(operations_library: pd.DataFrame) -> dict:
    child_parent = operations_library[['type_id', 'parent_type_id']].replace(pd.NA, 0)
    result = {parent_type_id: [] for parent_type_id in set(child_parent['parent_type_id'].unique())}
    _ = {result[parent_type_id].append(type_id) for type_id, parent_type_id in child_parent.values}
    return result


def string_to_list(value) -> list:
    if value is None:
        return []
    if pd.isna(value):
        return []
    # if isinstance(value, list):
    #     return value
    if isinstance(value, str) and len(value) == 0:
        return []
    if isinstance(value, str):
        return value.split('|')
    raise ValueError(f"Value '{value}' is not a <NA> or a string")


def collect_unique_strings(_column_names_dict: dict):
    unique_strings = set()

    for value in _column_names_dict.values():
        if isinstance(value, str):
            unique_strings.add(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    unique_strings.add(item)

    return list(unique_strings)


def reorder_by_row(input_type_ids: dict, row_dict: dict) -> dict:
    """Reorder 'child_type_ids' by 'row' in 'lib' in place."""
    result = {}
    for parent_id, type_ids in input_type_ids.items():
        type_ids: list
        order_mask = row_dict[type_ids].to_list()
        result[parent_id] = [x for x in sorting_generator(type_ids, order_mask)]
    return result


def _build_library_dict(columns, records_dict):
    lib = {column_name: {} for column_name in columns}
    for record_dict in records_dict:
        type_id: int = record_dict.get('type_id')
        for column_name in columns:
            lib[column_name][type_id] = convert_string(record_dict.get(column_name))
    return lib


def build_tree(lib):
    """Build tree of 'child_type_ids'."""

    def recursive_tree(_parent_id: int) -> dict:
        """Recursive function for building tree of child_type_ids"""
        _parent_ids = lib.get('child_type_ids').keys()
        if _parent_id in _parent_ids:
            _tree = {}
            for __child_id in lib.get('child_type_ids')[_parent_id]:
                _tree[__child_id] = recursive_tree(__child_id)
            return _tree
        return {}

    root_id = min(lib.get('child_type_ids').keys())
    return recursive_tree(root_id)


def query_press(_cur: psycopg2.extensions.cursor) -> pd.DataFrame:
    table_name = 'press'
    index_column_name = 'press_id'
    is_exclude_index_column = True
    order_by = 'press_id'
    column_names, data_types = get_columns_and_data_types(_cur, table_name=table_name, exclude_columns=[])
    records = query_table(_cur, table_name, column_names, order_by=order_by)
    _df = convert_records_to_pandas(records, column_names, data_types,
                                    index_column=index_column_name,
                                    is_exclude_index_column=is_exclude_index_column)
    _df['name'] = _df['name'].apply(convert_string)
    return _df


def query_press_mode(_cur: psycopg2.extensions.cursor, _presses: pd.DataFrame) -> pd.DataFrame:
    """Queries 'press_mode' table for all columns."""
    table_name = 'press_mode'
    index_column_name = 'press_mode_id'
    is_exclude_index_column = True
    order_by = 'press_mode_id'

    column_names, data_types = get_columns_and_data_types(_cur, table_name=table_name, exclude_columns=[])
    records = query_table(_cur, table_name, column_names, order_by=order_by)
    _df = convert_records_to_pandas(records, column_names, data_types,
                                    index_column=index_column_name,
                                    is_exclude_index_column=is_exclude_index_column)
    _df['press_mode_name'] = _df['press_mode_name'].apply(convert_string)

    return _df


def query_press_mode_power_limit(cur: psycopg2.extensions.cursor) -> dict:
    """Queries 'press_mode' table for all columns."""

    cur.execute(f"SELECT DISTINCT press_mode_id FROM press_mode_power_limit ORDER BY press_mode_id ASC;")
    press_mode_ids = [value[0] for value in cur.fetchall()]

    power_limit = {}

    for press_mode_id in press_mode_ids:
        query_text = f"""
        SELECT force_value, speed_value FROM press_mode_power_limit 
        WHERE press_mode_id = %s ORDER BY row_num ASC;"""
        cur.execute(query_text, (press_mode_id,))
        records = cur.fetchall()
        power_limit[press_mode_id] = records

    return power_limit


def feed_direction(_cur: psycopg2.extensions.cursor) -> pd.DataFrame:
    table_name = 'feed_direction'
    index_column_name = 'feed_direction_id'
    is_exclude_index_column = True
    order_by = 'feed_direction_id'
    column_names, data_types = get_columns_and_data_types(_cur, table_name=table_name, exclude_columns=[])
    records = query_table(_cur, table_name, column_names, order_by=order_by)
    _df = convert_records_to_pandas(records, column_names, data_types,
                                    index_column=index_column_name,
                                    is_exclude_index_column=is_exclude_index_column)
    _df['feed_direction_name'] = _df['feed_direction_name'].apply(convert_string)
    return _df


def query_die(_cur: psycopg2.extensions.cursor) -> pd.DataFrame:
    table_name = 'die'
    index_column_name = 'id'
    is_exclude_index_column = True
    order_by = 'id'
    column_names, data_types = get_columns_and_data_types(_cur, table_name=table_name, exclude_columns=[])
    records = query_table(_cur, table_name, column_names, order_by=order_by)
    _df = convert_records_to_pandas(records, column_names, data_types,
                                    index_column=index_column_name,
                                    is_exclude_index_column=is_exclude_index_column)
    _df['dimensions'] = _df['dimensions'].apply(convert_string).astype('object')
    _df['name'] = _df['name'].apply(convert_string)
    return _df


def query_die_assembly(_cur: psycopg2.extensions.cursor) -> pd.DataFrame:
    table_name = 'die_assembly'
    index_column_name = 'id'
    is_exclude_index_column = True
    order_by = 'id'
    column_names, data_types = get_columns_and_data_types(_cur, table_name=table_name, exclude_columns=[])
    records = query_table(_cur, table_name, column_names, order_by=order_by)
    _df = convert_records_to_pandas(records, column_names, data_types,
                                    index_column=index_column_name,
                                    is_exclude_index_column=is_exclude_index_column)
    _df['name'] = _df['name'].apply(convert_string)
    return _df


def query_material(_cur: psycopg2.extensions.cursor) -> pd.DataFrame:
    """
    Queries 'material' table for all columns. Returns pd.DataFrame.
    'material_id' columns is dataframe index.
    """
    table_name = 'material'
    index_column_name = 'material_id'
    is_exclude_index_column = True
    order_by = 'material_id'
    column_names, data_types = get_columns_and_data_types(_cur, table_name=table_name, exclude_columns=[])
    records = query_table(_cur, table_name, column_names, order_by=order_by)
    _df = convert_records_to_pandas(records, column_names, data_types,
                                    index_column=index_column_name,
                                    is_exclude_index_column=is_exclude_index_column)
    _df['material_name'] = _df['material_name'].apply(convert_string)

    return _df


def _import_materials_from_data_files(_cur: psycopg2.extensions.cursor, mat_dir: str, materials: pd.DataFrame) -> dict:
    classes = {}
    try:
        for material_id in np.array(materials.index):
            mat_file = materials.loc[material_id]['material_path']
            if mat_file:
                mat_abs_path = os.path.join(mat_dir, mat_file)
                assert os.path.exists(mat_abs_path), f"File '{mat_abs_path}' not found"
                material = Material(mat_abs_path)
            else:
                material = None
            classes[material_id] = material
    except KeyError as _err:
        LOGGER.error(f"KeyError: {_err}")
    except Exception as _err:
        LOGGER.error(f"Exception: {_err}")
    else:
        return classes
    raise RuntimeError(f"FAILED func '_import_materials_from_data_files' occurred "
                       f"when importing Material Classes from data files.")


def query_time_between_operations(_cur: psycopg2.extensions.cursor) -> pd.DataFrame:
    """Queries 'time_between_operations' table for all columns."""
    try:
        table_name = 'time_between_operations'
        column_names, data_types = get_columns_and_data_types(_cur, table_name=table_name, exclude_columns=[])
        records = query_table(_cur, table_name, column_names)
        _df = convert_records_to_pandas(records, column_names, data_types,
                                        index_column=None,
                                        is_exclude_index_column=False)

    except Exception as _e:
        LOGGER.error(f"Exception: {_e}")
    else:
        return _df
    raise RuntimeError("Error while querying 'time_between_operations' table.")


def query_columns_structure_of_server_pre_main(cur: psycopg2.extensions.cursor) -> tuple[list, set, dict]:
    # Exclude SERIAL columns

    excluded = ['execution_id']

    # Execute the SQL query
    cur.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'server_pre_main';
    """)
    rows = cur.fetchall()

    column_names, not_null_columns, data_types = [], [], {}
    # unique_data_types = set()

    for column_name, data_type, nullable in rows:

        if column_name in excluded:
            continue

        if nullable != 'YES':
            not_null_columns.append(column_name)

        column_names.append(column_name)
        data_types[column_name] = SQL_TO_PANDAS.get(data_type, 'object')

    return column_names, set(not_null_columns), data_types


def get_columns_and_data_types(cur: psycopg2.extensions.cursor, table_name: str, exclude_columns: list
                               ) -> tuple[list, dict]:
    data_types_dict = {}
    try:
        assert isinstance(exclude_columns, list), "exclude_columns must be a list"

        cur.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table_name}';")
        rows = cur.fetchall()

        for column_name, data_type in rows:
            if column_name == exclude_columns:
                continue

            pandas_data_type = SQL_TO_PANDAS.get(data_type, 'object')
            if column_name in data_types_dict:
                assert data_types_dict[column_name] == pandas_data_type, \
                    f"Data type mismatch for column '{column_name}' in table '{table_name}'"
            else:
                data_types_dict[column_name] = pandas_data_type

        # column_names, data_types = zip(*data_types_dict.items())

        column_names = list(data_types_dict.keys())

    except AssertionError as _err:
        LOGGER.error(f"AssertionError: {_err}")
        raise AssertionError(_err)
    except KeyError as _err:
        LOGGER.error(f"KeyError: {_err}")
        raise KeyError(_err)
    except Exception as _err:
        LOGGER.error(f"Exception: {_err}")
        raise RuntimeError(_err)
    else:
        return column_names, data_types_dict


def query_operations_type_nnn(cur: psycopg2.extensions.cursor, columns_dict: pd.Series) -> tuple[list, dict]:
    # Execute the SQL query

    data_types = {}
    # unique_data_types = set()

    for type_id in set(columns_dict.index.to_list()):

        if not columns_dict[type_id]:
            continue

        cur.execute(f"""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'operations_type_id_{type_id}';
        """)

        rows = cur.fetchall()

        for column_name, data_type in rows:
            if column_name == 'id':
                continue

            # unique_data_types.add(data_type)

            pandas_data_type = SQL_TO_PANDAS.get(data_type, 'object')
            if column_name in data_types:
                assert data_types[column_name] == pandas_data_type, \
                    f"Data type mismatch for column '{column_name}' in table 'operations_type_id_{type_id}'"
            else:
                data_types[column_name] = pandas_data_type

    # LOGGER.info(unique_data_types)

    column_names = list(set(data_types.keys()))

    return column_names, data_types


def convert_sql_data_types_to_pandas_ones(_df, _data_types: dict):
    # Convert each column to its designated type
    # all_types = []
    # for column, data_type in _data_types.items():
    #     if data_type not in all_types:
    #         all_types.append(data_type)
    # LOGGER.info(all_types)
    for column, data_type in _data_types.items():
        if data_type == 'double precision':
            _df[column] = _df[column].astype('float64')
        elif data_type in ('integer', 'bigint', 'smallint'):
            _df[column] = _df[column].astype(pd.Int64Dtype())
        elif data_type == 'bytea':
            _df[column] = _df[column].astype('bytes')
        elif data_type == 'character varying':
            _df[column] = _df[column].astype('object')
        elif data_type == 'boolean':
            _df[column] = _df[column].astype('boolean')
        elif data_type == 'jsonb':
            _df[column] = _df[column].astype('object')
        elif data_type == 'USER-DEFINED':
            _df[column] = _df[column].astype('object')


def print_sql_data_types(_data_types: dict):
    all_types = []
    for column, data_type in _data_types.items():
        if data_type not in all_types:
            all_types.append(data_type)
    LOGGER.info(all_types)


def query_preview_status_enum(cur: psycopg2.extensions.cursor) -> list:
    try:
        query = (f"SELECT enumlabel AS category FROM pg_enum WHERE enumtypid = 'preview_status_enum'::regtype "
                 f"ORDER BY enumsortorder;")
        cur.execute(query)
        _records = cur.fetchall()

        if not _records:
            return []

        return [_record[0] for _record in _records]

    except (Exception, psycopg2.DatabaseError) as _e:
        LOGGER.error("Error while executing Postgres command: ", _e)
        return []


def query_simulation_status_enum(cur: psycopg2.extensions.cursor) -> list:
    try:
        query = (f"SELECT enumlabel AS category FROM pg_enum WHERE enumtypid = 'simulation_status_enum'::regtype "
                 f"ORDER BY enumsortorder;")
        cur.execute(query)
        _records = cur.fetchall()

        if not _records:
            return []

        return [_record[0] for _record in _records]

    except (Exception, psycopg2.DatabaseError) as _e:
        LOGGER.error("Error while executing Postgres command: ", _e)
        return []


def query_library(conn: psycopg2.extensions.connection, mat_dir: str) -> dict:
    """Queries 'operations_library'."""
    _cur = conn.cursor()
    try:

        ol, ol_records, ol_columns = get_operations_library(_cur)

        # records_dict = convert_records_to_dict(columns, records)
        # designate_root_as_0(records_dict)
        # operations_dict = build_library_dict(columns, records_dict)

        _lib = {
            'operations_library': ol,
            # 'operations_dict': operations_dict,
        }

        type_ids = find_child_ids_for_dataframe(ol)

        # _lib['db_column_names_unique'] = collect_unique_strings(ol['db_column_names'])

        _lib['child_type_ids'] = reorder_by_row(type_ids.copy(), ol['row'])

        _lib['type_id_tree'] = build_tree(_lib)

        _lib['feed_direction'] = feed_direction(_cur)

        _lib['die'] = query_die(_cur)

        _lib['die_assembly'] = query_die_assembly(_cur)

        _lib['press'] = query_press(_cur)

        _lib['press_mode'] = query_press_mode(_cur, _lib['press'])

        _lib['press_mode_power_limit'] = query_press_mode_power_limit(_cur)

        _lib['materials'] = query_material(_cur)

        _lib['material_classes'] = _import_materials_from_data_files(_cur, mat_dir, _lib['materials'])

        _lib['time_between_operations'] = query_time_between_operations(_cur)

        # ------------------------------------------------
        # SQL 'server_pre_main'

        spm_columns, spm_not_null_columns, spm_sql_types = query_columns_structure_of_server_pre_main(_cur)
        extra_output_columns = {
            'TEMPORARY.initial_polygon': object,
            'TEMPORARY.final_polygon': object}
        output_columns = spm_columns + list(extra_output_columns.keys())
        output_data_types = spm_sql_types.copy()
        output_data_types.update(extra_output_columns)
        _lib |= {
            'output_columns': output_columns,
            'output_data_types': output_data_types,

            'server_pre_main_columns': pd.Index(spm_columns),
            'server_pre_main_types': spm_sql_types,
            'server_pre_main_not_null_columns': pd.Index(spm_not_null_columns)}

        # ------------------------------------------------

        input_columns, input_data_types = query_operations_type_nnn(_cur, ol['db_column_names'])
        extra_input_columns = {
            'type_id': pd.Int64Dtype(),
            'operation_id': pd.Int64Dtype(),
            'type_id_feed_type': pd.Int64Dtype(),
            # 'press_mode_id': pd.Int64Dtype(),
            'operation_type_new': pd.StringDtype(),
            'deformation_type': pd.StringDtype(),
            'speed': pd.Float64Dtype(),
            'input_index': pd.Int64Dtype(),
            'output_index': pd.Int64Dtype(),
            'press': pd.StringDtype()}
        input_columns = list(extra_input_columns.keys()) + input_columns
        extra_input_columns.update(input_data_types)
        _lib |= {
            'input_columns': input_columns,
            'input_data_types': extra_input_columns}

        # ------------------------------------------------

        _lib['operations_columns'] = ('id', 'parent_id', 'type_id', 'row')

        _lib['preview_status_enum'] = query_preview_status_enum(_cur)

        _lib['simulation_status_enum'] = query_simulation_status_enum(_cur)

        # add_attributes_to_operations_json(ol, _lib)

    except KeyError as _err:
        LOGGER.error(f"KeyError: {_err}")
    except Exception as _err:
        LOGGER.error(f"Exception: {_err}")
    else:
        _cur.close()
        return _lib

    _cur.close()
    raise RuntimeError(f"FAILED func 'query_library'")
