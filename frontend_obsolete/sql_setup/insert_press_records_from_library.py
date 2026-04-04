import json

from forgelab.sql_setup.library_dictionary import library


def insert_press_records_from_library(cur):
    upsert_press_records_from_library(cur)
    upsert_press_mode_records_from_library(cur)
    update_press_mode_set_press_id_form_library(cur)
    update_press_set_default_press_mode_id(cur)
    query_power_limit_insert_update_or_delete(cur)


def _normalize_name_key(value):
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _parse_json_text(value):
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except Exception:
        return value


def upsert_press_records_from_library(cur):
    cur.execute("SELECT press_id, name::text FROM presses;")
    result = cur.fetchall()
    sql_press_id_by_name = {
        _normalize_name_key(_parse_json_text(name_text)): press_id
        for press_id, name_text in result
    } if result else {}

    for lib_press in library['press']:
        name_key = _normalize_name_key(lib_press['name'])
        if name_key in sql_press_id_by_name:
            continue
        cur.execute("INSERT INTO presses (name) VALUES (%s::json);",
                    (json.dumps(lib_press['name'], ensure_ascii=False),))


def upsert_press_mode_records_from_library(cur):
    cur.execute("SELECT press_mode_id, name::text FROM press_modes;")
    result = cur.fetchall()
    sql_press_mode_id_by_name = {
        _normalize_name_key(_parse_json_text(name_text)): press_mode_id
        for press_mode_id, name_text in result
    } if result else {}

    update_sql = (
        "UPDATE press_modes "
        "SET name = %s::json, "
        "is_left_manipulator = %s, "
        "is_right_manipulator = %s, "
        "automatic_feed_mode_is_on_when_bites_count = %s, "
        "max_force = %s, "
        "back_speed = %s, "
        "idle_speed = %s, "
        "working_speed = %s, "
        "min_dwell_speed = %s, "
        "max_dwell_time = %s, "
        "min_idle_stroke = %s, "
        "max_idle_stroke = %s, "
        "approaching_distance = %s, "
        "open_height_without_dies = %s "
        "WHERE press_mode_id = %s;"
    )
    insert_sql = (
        "INSERT INTO press_modes ("
        "name, "
        "is_left_manipulator, "
        "is_right_manipulator, "
        "automatic_feed_mode_is_on_when_bites_count, "
        "max_force, "
        "back_speed, "
        "idle_speed, "
        "working_speed, "
        "min_dwell_speed, "
        "max_dwell_time, "
        "min_idle_stroke, "
        "max_idle_stroke, "
        "approaching_distance, "
        "open_height_without_dies"
        ") VALUES (%s::json, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);"
    )

    for lib_press_mode in library['press_mode']:
        mode_name_key = _normalize_name_key(lib_press_mode['name'])
        manip_count = int(lib_press_mode.get('manipulators_count') or 0)
        values = (
            json.dumps(lib_press_mode['name'], ensure_ascii=False),
            manip_count >= 1,
            manip_count >= 2,
            lib_press_mode.get('automatic_feed_mode_is_on_when_bites_count'),
            lib_press_mode.get('max_force'),
            lib_press_mode.get('back_speed'),
            lib_press_mode.get('idle_speed'),
            lib_press_mode.get('working_speed'),
            lib_press_mode.get('min_dwell_speed'),
            lib_press_mode.get('max_dwell_time'),
            lib_press_mode.get('min_idle_stroke'),
            lib_press_mode.get('max_idle_stroke'),
            lib_press_mode.get('approaching_distance'),
            lib_press_mode.get('open_height_without_dies'),
        )

        press_mode_id = sql_press_mode_id_by_name.get(mode_name_key)
        if press_mode_id is None:
            cur.execute(insert_sql, values)
            continue
        cur.execute(update_sql, values + (press_mode_id,))


def update_press_mode_set_press_id_form_library(cur):
    cur.execute("SELECT press_id, name::text FROM presses;")
    result = cur.fetchall()
    sql_press_id_by_name = {
        _normalize_name_key(_parse_json_text(name_text)): press_id
        for press_id, name_text in result
    } if result else {}

    lib_press_name_by_code = {
        press_record['press_die_match_code']: press_record['name']
        for press_record in library['press']
    }
    press_id_dict = {
        code: sql_press_id_by_name[_normalize_name_key(name)]
        for code, name in lib_press_name_by_code.items()
        if _normalize_name_key(name) in sql_press_id_by_name
    }

    lib_press_mode_code_by_name = {
        _normalize_name_key(record['name']): record['press_die_match_code']
        for record in library['press_mode']
    }

    cur.execute("SELECT press_mode_id, name::text, press_id FROM press_modes;")
    result = cur.fetchall()
    if result:
        for press_mode_id, name_text, sql_press_id in result:
            press_mode_name_key = _normalize_name_key(_parse_json_text(name_text))
            press_die_match_code = lib_press_mode_code_by_name.get(press_mode_name_key)
            assert press_die_match_code is not None, \
                f"Press mode '{press_mode_name_key}' not found in library"
            assert press_die_match_code in press_id_dict.keys(), \
                f"Press die match code '{press_die_match_code}' not found"
            lib_press_id = press_id_dict[press_die_match_code]
            if sql_press_id != lib_press_id:
                cur.execute("UPDATE press_modes SET press_id = %s WHERE press_mode_id = %s;",
                            (lib_press_id, press_mode_id))


def update_press_set_default_press_mode_id(cur):
    cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'presses'
          AND column_name = 'default_press_mode_id'
        LIMIT 1;
        """
    )
    if not cur.fetchone():
        return

    lib_default_mode_name_by_code = {}
    for lib_press in library['press']:
        press_code = lib_press.get('press_die_match_code')
        if not press_code:
            continue
        # Prefer explicit default flag from library and fallback to first mode.
        default_mode = next(
            (pm for pm in library['press_mode']
             if pm.get('press_die_match_code') == press_code and bool(pm.get('is_default_press_mode'))),
            None,
        )
        if default_mode is None:
            default_mode = next(
                (pm for pm in library['press_mode'] if pm.get('press_die_match_code') == press_code),
                None,
            )
        if default_mode is not None:
            lib_default_mode_name_by_code[press_code] = _normalize_name_key(default_mode['name'])

    cur.execute("SELECT press_mode_id, name::text FROM press_modes;")
    result = cur.fetchall()
    mode_id_by_name = {
        _normalize_name_key(_parse_json_text(name_text)): press_mode_id
        for press_mode_id, name_text in result
    } if result else {}

    cur.execute("SELECT press_id, name::text FROM presses;")
    result = cur.fetchall()
    press_id_by_name = {
        _normalize_name_key(_parse_json_text(name_text)): press_id
        for press_id, name_text in result
    } if result else {}

    press_name_by_code = {
        press_record['press_die_match_code']: _normalize_name_key(press_record['name'])
        for press_record in library['press']
    }

    for press_code, default_mode_name in lib_default_mode_name_by_code.items():
        press_name = press_name_by_code.get(press_code)
        if press_name is None:
            continue
        press_id = press_id_by_name.get(press_name)
        default_mode_id = mode_id_by_name.get(default_mode_name)
        if press_id is None or default_mode_id is None:
            continue
        cur.execute("UPDATE presses SET default_press_mode_id = %s WHERE press_id = %s;",
                    (default_mode_id, press_id))


def query_power_limit_insert_update_or_delete(cur):
    cur.execute("SELECT press_mode_id, name::text FROM press_modes;")
    sql_press_mode_list = cur.fetchall()
    cur.execute("SELECT press_mode_id, row_num, force_value, speed_value FROM press_mode_power_limit;")
    sql_power_limit_list = cur.fetchall()
    lib_power_limit_list = []
    lib_power_limit_by_name = {
        _normalize_name_key(record['name']): record['power_limit']
        for record in library['press_mode']
    }
    for press_mode_id, name_text in sql_press_mode_list:
        mode_name_key = _normalize_name_key(_parse_json_text(name_text))
        power_limit = lib_power_limit_by_name.get(mode_name_key, [])
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
