import json

from forgelab.sql_setup.connections import \
    close_connection, connect_to_db, is_postgresql_db_exists


def postgresql_get_processes_of_user(config, user_id):
    """Add materials to materials table in postgresql 'forgelab_db' database."""
    headers = (
        'process_id', 'material_id', 'heat_no',
        'lot_no', 'finished_size', 'standard_customer',
        'standard_wst', 'product_condition', 'product_surface',
        'product_diameter_tolerance', 'product_length_tolerance', 'product_curvature_tolerance',
        'stock_size', 'stock_weight', 'stock_no',
        'material_btt', 'material_btt_sym_tolerance', 'remarks',
        'created_at', 'user_id'
    )
    cnxn, crsr = connect_to_db(config)
    formula = f"SELECT {', '.join(headers)} FROM process WHERE user_id = {user_id}"
    crsr.execute(formula)
    process_id = crsr.fetchall()
    close_connection(cnxn, crsr)
    return process_id, headers


def postgresql_get_processes(cur):
    """Add materials to materials table in postgresql 'forgelab_db' database."""
    formula = f"SELECT process_id FROM process"
    cur.execute(formula)
    process_id_all = [i[0] for i in cur.fetchall()]
    return process_id_all


def postgresql_get_process_versions_of_process_id(cur, process_id):
    """Add materials to materials table in postgresql 'forgelab_db' database."""
    formula = f"SELECT process_version_id FROM process_versions WHERE process_id = {process_id}"
    cur.execute(formula)
    process_version_id_all = [i[0] for i in cur.fetchall()]
    return process_version_id_all


def postgresql_get_process_versions(cur):
    """Add materials to materials table in postgresql 'forgelab_db' database."""
    formula = f"SELECT process_version_id FROM process_versions"
    cur.execute(formula)
    process_version_id_all = [i[0] for i in cur.fetchall()]
    return process_version_id_all


def sql_get_list_of_processes(
        cur,
        process_name: str = None,
        user_id: int = None,
        material_id: int = None,
        offset_num: int = None,
        limit_num: int = None
) -> (list, list):
    """Receives user_id. Returns two lists: list of column names and list of processes, owned by the user."""
    sql_formula = 'SELECT * FROM process'
    #
    search_list = []
    if process_name is not None:
        search_list.append(f"proc_name LIKE '{process_name}'")
    if user_id is not None:
        search_list.append(f"user_id = {user_id}")
    if material_id is not None:
        search_list.append(f"material_id = {material_id}")
    #
    if len(search_list) > 1:
        sql_formula += f" WHERE {' AND '.join(search_list)}"
    elif len(search_list) == 1:
        sql_formula += f" WHERE {search_list[0]}"
    #
    if offset_num is not None and limit_num is not None:
        sql_formula += f" LIMIT {offset_num}, {limit_num}"
    elif limit_num is not None:
        sql_formula += f" LIMIT {limit_num}"
    else:  # elif offset_num is not None
        sql_formula += f" OFFSET {offset_num}"

    cur.execute("SHOW COLUMNS FROM pro")
    column_names = [i[0] for i in cur.fetchall()]
    cur.execute(sql_formula)
    values = cur.fetchall()
    return column_names, values


def sql_get_operations_for_process_id(cur, process_id) -> (list, list):
    """Receives process_id. Returns two lists: list of column names and list of tuples of operations."""
    #
    cur.execute("SHOW COLUMNS FROM presses")
    column_names = [i[0] for i in cur.fetchall()]
    #
    sql_formula = (
        """
        SELECT * FROM operation
        WHERE process_id = %s LIMIT %s
        """
    )
    cur.execute(sql_formula, (process_id, 1000,))
    values = cur.fetchall()
    #
    return column_names, values


def sql_query_process_columns_description(cur) -> list:
    """Returns description of columns for process, takes description from process_column_description."""
    cur.execute("SELECT * FROM process_headers LIMIT 1")
    headers = cur.fetchone()
    return headers


def sql_query_operation_types_dict(cur) -> dict:
    """Get press_id. Returns two lists: list of column names and list of tuples with press modes data."""
    cur.execute("SHOW COLUMNS FROM operation_type")
    column_names = [i[0] for i in cur.fetchall()]
    cur.execute("SELECT * FROM operation_type")
    operation_types_dict = {}
    for operation_type_input in cur.fetchall():
        value = {}
        key = operation_type_input[0]
        for i, item in enumerate(operation_type_input):
            if i == 0:
                continue
            elif i == 4:
                value[column_names[i]] = json.loads(item)
            else:
                value[column_names[i]] = item
        operation_types_dict[key] = value
    return operation_types_dict


def sql_query_operation_type_names_for_category(cur, category_id: int) -> list:
    """Get press_id. Returns two lists: list of column names and list of tuples with press modes data."""
    cur.execute(
        "SELECT operation_type_id, type_long_description FROM operation_type WHERE category_id = %s",
        (category_id,))
    values = cur.fetchall()
    return values


def sql_query_operation_type_for_operation_type_id(cur, operation_type_id: int) -> list:
    """Get press_id. Returns two lists: list of column names and list of tuples with press modes data."""
    cur.execute("SELECT * FROM operation_type WHERE operation_type_id = %s LIMIT 1", (operation_type_id,))
    values = list(cur.fetchone())
    # values[4] = json.loads(values[4])
    return values


def sql_get_operation_type_categories(cur) -> list:
    """Get press_id. Returns two lists: list of column names and list of tuples with press modes data."""
    cur.execute("SELECT * FROM operation_type_category")
    values = cur.fetchall()
    return values


def postgresql_get_press_mode_record(cur, press_mode_id: int) -> (list, list):
    """Get press_mode_id. Returns two lists: column names and press mode record."""
    cur.execute("SHOW COLUMNS FROM press_modes")
    press_mode_columns = [i[0] for i in cur.fetchall()]
    cur.execute("SELECT * FROM press_modes WHERE press_mode_id = %s LIMIT 1", (press_mode_id,))
    press_mode_data = cur.fetchone()
    return press_mode_columns, press_mode_data


def postgresql_get_press_mode_power_limit_records(cur, press_mode_id: int) -> (list, list):
    """Get press_mode_id. Returns two lists: column names and power limit list of tuples."""
    press_mode_power_limit_columns = ('force_value', 'speed_value')
    press_mode_power_limit_formula = (
        f"SELECT {press_mode_power_limit_columns[0]}, {press_mode_power_limit_columns[1]} "
        f"FROM press_mode_power_limit WHERE press_mode_id = %s ORDER BY row_num"
    )
    cur.execute(press_mode_power_limit_formula, (press_mode_id,))
    press_mode_data = cur.fetchall()
    return press_mode_power_limit_columns, press_mode_data


def get_type_ids(cur) -> list:
    """Returns all type_id."""
    cur.execute("SELECT type_id FROM operations_library ORDER BY type_id ASC")
    values = cur.fetchall()
    return [value[0] for value in values]


def print_available_type_ids(cur, sql_param: dict):
    if is_postgresql_db_exists(sql_param):
        values = get_type_ids(cur)
        max_id = max(values)
        min_id = min(values)
        # find missing integer numbers in list 'values'
        missing = [str(x) for x in range(min_id, max_id + 1) if x not in values]
        print(f"Available 'type_id': {', '.join(missing)}, {max_id + 1}, {max_id + 2}, and so on...")
    else:
        print(f"\nDatabase '{sql_param['db']['base']}' does not exists")
