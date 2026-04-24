from forgelab.sql_setup.insert_or_update_table_from_library import query_insert_or_update_records_from_library
from forgelab.sql_setup.library_dictionary import library


def insert_press_records_from_library(cur):
    query_insert_or_update_records_from_library(cur,
                                                table_name='press',
                                                column_name_of_unique_name='press_die_match_code',
                                                exclude_columns=[])
    query_insert_or_update_records_from_library(cur,
                                                table_name='press_mode',
                                                column_name_of_unique_name='press_mode_name',
                                                exclude_columns=['power_limit'])
    update_press_mode_set_press_id_form_library(cur)
    query_power_limit_insert_update_or_delete(cur)


def update_press_mode_set_press_id_form_library(cur):
    cur.execute("SELECT press_id, press_die_match_code FROM press;")
    result = cur.fetchall()
    press_id_dict = {record[1]: record[0] for record in result} if result else {}
    cur.execute("SELECT press_mode_name, press_die_match_code, press_id FROM press_mode;")
    result = cur.fetchall()
    if result:
        for press_mode_name, press_die_match_code, sql_press_id in result:
            assert press_die_match_code in press_id_dict.keys(), \
                f"Press die match code '{press_die_match_code}' not found"
            lib_press_id = press_id_dict[press_die_match_code]
            if not isinstance(sql_press_id, (int, str,)) or sql_press_id != lib_press_id:
                cur.execute("UPDATE press_mode SET press_id = %s WHERE press_mode_name = %s;",
                            (lib_press_id, press_mode_name))


def query_power_limit_insert_update_or_delete(cur):
    cur.execute("SELECT press_mode_name, press_mode_id FROM press_mode;")
    sql_press_mode_list = cur.fetchall()
    cur.execute("SELECT press_mode_id, row_num, force_value, speed_value FROM press_mode_power_limit;")
    sql_power_limit_list = cur.fetchall()
    lib_power_limit_list = []
    for press_mode_name, press_mode_id in sql_press_mode_list:
        power_limit = []
        for i, _pm in enumerate(library['press_mode']):
            if _pm['press_mode_name'] == press_mode_name:
                power_limit = _pm['power_limit']
        for row_num, (force_value, speed_value) in enumerate(power_limit):
            lib_power_limit_list.append((press_mode_id, row_num, force_value, speed_value))
    delete_sql_records = []
    insert_sql_records = []
    update_sql_records = []
    sql_press_mode_id_list = tuple(set([record[0] for record in lib_power_limit_list]))
    for press_mode_id in sql_press_mode_id_list:
        sql_power_limit = [record for record in sql_power_limit_list if record[0] == press_mode_id]
        sql_power_limit.sort(key=lambda x: x[1])
        lib_power_limit = [record for record in lib_power_limit_list if record[0] == press_mode_id]
        lib_power_limit.sort(key=lambda x: x[1])
        lib_len = len(lib_power_limit)
        sql_len = len(sql_power_limit)
        min_len = min(lib_len, sql_len)
        delete_sql_records.extend(sql_power_limit[lib_len:])
        insert_sql_records.extend(lib_power_limit[min_len:lib_len])

        for i in range(min_len):
            if lib_power_limit[i][2:] != sql_power_limit[i][2:]:
                update_sql_records.extend(lib_power_limit[i])
    for record in delete_sql_records:
        cur.execute("DELETE FROM press_mode_power_limit WHERE press_mode_id = %s AND row_num = %s;",
                    (record[0], record[1]))
    for record in insert_sql_records:
        cur.execute("INSERT INTO press_mode_power_limit (press_mode_id, row_num, force_value, speed_value) "
                    "VALUES (%s, %s, %s, %s);",
                    record)
    for record in update_sql_records:
        cur.execute("UPDATE press_mode_power_limit SET force_value = %s, speed_value = %s "
                    "WHERE press_mode_id = %s AND row_num = %s;",
                    (record[2], record[3], record[0], record[1]))
