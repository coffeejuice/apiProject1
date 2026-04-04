import json
import psycopg2.extensions
from psycopg2 import sql

from forgelab.sql_setup.library_dictionary import library


def query_insert_or_update_records_from_library(cur,
                                                table_name: str,
                                                column_name_of_unique_name: str,
                                                exclude_columns: list,
                                                library_key: str | None = None,
                                                is_convert_dict_to_json_str: bool = False,
                                                json_columns: list[str] | None = None):
    if library_key is None:
        library_key = table_name
    sql_column_names, sql_column_values = select_from_table(cur,
                                                            table_name=table_name,
                                                            column_name_of_unique_name=column_name_of_unique_name,
                                                            order_by='')
    common_column_names = common_keys(sql_column_names, library_key=library_key)
    [common_column_names.remove(column_name) for column_name in exclude_columns if column_name in common_column_names]

    insert_records, update_records = records_for_insert_and_update(table_name=library_key,
                                                                   matching_column_name=column_name_of_unique_name,
                                                                   sql_records_dict=sql_column_values)
    for record in library[library_key]:
        unique_name = record[column_name_of_unique_name]
        record_data = delete_columns_except_common(record, common_column_names)
        record_data = convert_dict_values_to_json_string(
            record_data,
            is_convert_dict_to_json_str,
            json_columns=json_columns,
        )
        if unique_name in insert_records:
            query_insert_record(cur,
                                table_name=table_name,
                                record_data=record_data)
        elif unique_name in update_records:
            query_update_record(cur,
                                table_name=table_name,
                                record_data=record_data,
                                where_column=column_name_of_unique_name,
                                where_value=unique_name)
        else:
            raise ValueError(f"Unique name '{unique_name}' not found in insert or update records")


def convert_dict_values_to_json_string(input_dict: dict,
                                       is_convert_dict_to_json_str: bool,
                                       json_columns: list[str] | None = None) -> dict:
    # Apply json.dumps for selected columns and optionally for dict values.
    output = {}
    json_columns_set = set(json_columns or [])
    for key in input_dict.keys():
        if key in json_columns_set:
            output[key] = json.dumps(input_dict[key], ensure_ascii=False)
        elif is_convert_dict_to_json_str and isinstance(input_dict[key], dict):
            output[key] = json.dumps(input_dict[key], ensure_ascii=False)
        else:
            output[key] = input_dict[key]
    return output


def delete_columns_except_common(record: dict, common_column_names: list[str]) -> dict:
    record_data = {}
    for column_name in common_column_names:
        if column_name in record.keys():
            record_data[column_name] = record[column_name]
    return record_data


def records_for_insert_and_update(table_name: str,
                                  matching_column_name: str,
                                  sql_records_dict: dict
                                  ) -> tuple[list, list]:
    sql_matching_name_list = [val[matching_column_name] for val in sql_records_dict.values()]
    library_press_die_match_code_list = [press[matching_column_name] for press in library[table_name]]
    update_press_records = list(set(sql_matching_name_list).intersection(set(library_press_die_match_code_list)))
    insert_press_records = list(set(library_press_die_match_code_list).difference(set(sql_matching_name_list)))
    return insert_press_records, update_press_records


def common_keys(p_c, library_key: str) -> list:
    library_column_names = []
    [library_column_names.extend(list(record.keys())) for record in library[library_key]]
    return list(set(p_c).intersection(set(library_column_names)))


def select_from_table(_cur: psycopg2.extensions.cursor,
                      table_name: str,
                      column_name_of_unique_name: str,
                      order_by: str
                      ) -> tuple[list[str], dict]:
    """
    table_name = 'press'
    index_column_name = 'press_id'
    order_by = 'press_id'
    is_exclude_index_column = True
    """
    column_names = get_columns_and_data_types(_cur, table_name=table_name, exclude_columns=[])
    records = query_table(_cur, table_name, column_names, order_by=order_by)
    table_dict = list_to_dict(column_names, column_name_of_unique_name, records)
    return column_names, table_dict


def list_to_dict(column_names, index_column_name, records):
    table_dict = {}
    index_column_value = column_names.index(index_column_name)
    for record_list in records:
        table_key = record_list[index_column_value]
        record_dict = {}
        for column_names_index, record_key in enumerate(column_names):
            record_value = record_list[column_names_index]
            record_dict[record_key] = record_value
        table_dict[table_key] = record_dict
    return table_dict


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


def query_insert_record(_cur, table_name: str, record_data: dict):
    columns = list(record_data.keys())
    static_query = "INSERT INTO {sql_table} ({sql_columns}) VALUES ({sql_values});"
    dynamic_query = sql.SQL(static_query).format(sql_table=sql.Identifier(table_name),
                                                 sql_columns=sql.SQL(",").join(map(sql.Identifier, columns)),
                                                 sql_values=sql.SQL(",").join(map(sql.Placeholder, columns))
                                                 )
    _cur.execute(dynamic_query, record_data)


def query_update_record(_cur, table_name: str, record_data: dict, where_column: str, where_value):
    static_query = ("UPDATE {sql_table} SET {sql_column_vs_value}, updated_at = NOW() "
                    "WHERE {sql_where_column} = {sql_where_value};")
    sql_column_vs_value = sql.SQL(', ').join(
        sql.Composed(
            [sql.Identifier(column_name), sql.SQL(" = "), sql.Placeholder(column_name)]
        ) for column_name in record_data.keys()
    )
    dynamic_query = sql.SQL(static_query).format(sql_table=sql.Identifier(table_name),
                                                 sql_column_vs_value=sql_column_vs_value,
                                                 sql_where_column=sql.Identifier(where_column),
                                                 sql_where_value=sql.Literal(where_value))
    _cur.execute(dynamic_query, record_data)


def get_columns_and_data_types(cur: psycopg2.extensions.cursor, table_name: str, exclude_columns: list) -> list:
    assert isinstance(exclude_columns, list), "exclude_columns must be a list"

    cur.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table_name}';")
    result = cur.fetchall()
    column_names = [record[0] for record in result] if result else []

    for column_name in column_names:
        if column_name in exclude_columns:
            column_names.remove(column_name)

    return column_names
