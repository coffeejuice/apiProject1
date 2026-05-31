from psycopg2 import DatabaseError


def insert_time_operation_changing_records(conn):

    time_dict = {
        7:  [ 0,  0,  0,  0,  0,  0,     0,  0,  0],  # Billets
        11: [60, 60, 60, 60, 60, 60, 86400, 60,  0],  # heat, pause
        35: [15, 15,  2, 25, 25, 90, 86400,  0,  0],  # radial_prolongation
        37: [ 2, 25, 25, 25, 25, 90, 86400,  0,  0],  # Upsetting
        38: [25,  2, 25, 25, 25, 90, 86400,  0,  0],  # axial_prolongation
        39: [25, 25, 10, 10, 10, 90, 86400,  0,  0],  # full_die
        40: [30, 30, 30, 30, 30, 12, 86400,  0,  0],  # hot_cut
        61: [ 0,  0,  0,  0,  0,  0,     0,  0,  0],  # cold_sawing
        63: [25, 25, 25, 25, 10, 90, 86400,  0,  0],  # radial forging GFM
    }
    second = [37, 38, 35, 63, 39, 40,    61, 11, 7]

    assert set(list(time_dict.keys())) == set(second)

    query_operations = "SELECT type_id FROM operations_library WHERE parent_type_id = %s ORDER BY row ASC;"

    get_parent_type_id_return_type_ids = {}
    try:
        with  conn.cursor() as cur:
            for parent_type_id in time_dict.keys():
                cur.execute(query_operations, (parent_type_id, ))
                type_ids = [type_id[0] for type_id in cur.fetchall()]
                get_parent_type_id_return_type_ids[parent_type_id] = type_ids
    except (Exception, DatabaseError) as _err:
        print(f"\nQUERY FAILED: 'type_id FROM operations_library WHERE parent_type_id'\nError: {_err}\n")

    # PRESS type_id's
    try:
        with  conn.cursor() as cur:
            cur.execute("SELECT press_id FROM press")
            press_id_list = [i[0] for i in cur.fetchall()]
    except (Exception, DatabaseError) as _err:
        print(f"\nQUERY FAILED: 'SELECT press_id FROM press'\nError: {_err}\n")
        return

    try:
        time_values = []
        for first_parent_type_id, time_list in time_dict.items():
            for second_parent_type_id, _time in zip(second, time_list):
                for press_id in press_id_list:
                    for first_type_id in get_parent_type_id_return_type_ids[first_parent_type_id]:
                        for second_type_id in get_parent_type_id_return_type_ids[second_parent_type_id]:
                            time_values.append((first_type_id, second_type_id, press_id, _time, 0.0))
    except Exception as _err:
        print(f"Error in 'insert_time_operation_changing_records_from_library': {_err}")
        return

    try:
        with  conn.cursor() as cur:
            cur.execute("DELETE FROM time_between_operations")
    except (Exception, DatabaseError) as _err:
        print(f"\nQUERY FAILED: 'DELETE FROM time_between_operations'\nError: {_err}\n")
        raise RuntimeError("Function 'INSERT INTO time_between_operations' failed")

    try:
        time_formula = """
        INSERT INTO time_between_operations (
        first_operation_type_id, second_operation_type_id, press_id, time_mean, time_sigma)
        VALUES (%s, %s, %s, %s, %s);
        """
        with  conn.cursor() as cur:
            cur.executemany(time_formula, time_values)
    except (Exception, DatabaseError) as _err:
        print(f"\nQUERY FAILED: 'INSERT INTO time_between_operations'\nError: {_err}\n")
        raise RuntimeError("Function 'INSERT INTO time_between_operations' failed")

    # for time_record in time_values:
    #     time_mean, time_sigma = _query_select_time_record(cur, time_record)
    #     if time_mean is None:
    #         _query_time_insert(cur, time_record)
    #     elif time_mean == time_record[3] and time_sigma == time_record[4]:
    #         pass
    #     else:
    #         _query_time_update(cur, time_record)


def _query_select_time_record(cur, time_record) -> tuple:
    try:

        time_formula = """
        SELECT time_mean, time_sigma FROM time_between_operations WHERE 
        first_operation_type_id = %s and second_operation_type_id = %s and press_id = %s;
        """
        cur.execute(time_formula, time_record[:3])
        result = cur.fetchall()
        if not result:
            return None, None

        assert len(result) == 1, f"Error in 'time_between_operations' table. There are {len(result)} "

        return result[0][0], result[0][1]

    except (Exception, DatabaseError) as _err:
        print(f"\nQUERY FAILED: 'INSERT INTO time_between_operations'\nError: {_err}\n")
        raise RuntimeError("Function 'INSERT INTO time_between_operations' failed")


def _query_time_insert(cur, time_values):
    try:
        time_formula = """
        INSERT INTO time_between_operations (
        first_operation_type_id, second_operation_type_id, press_id, time_mean, time_sigma)
        VALUES (%s, %s, %s, %s, %s);
        """
        cur.execute(time_formula, time_values)
    except (Exception, DatabaseError) as _err:
        print(f"\nQUERY FAILED: 'INSERT INTO time_between_operations'\nError: {_err}\n")
        raise RuntimeError("Function 'INSERT INTO time_between_operations' failed")


def _query_time_update(cur, time_values):
    try:
        time_formula = """
        UPDATE time_between_operations SET time_mean = %s, time_sigma = %s
        WHERE first_operation_type_id = %s, second_operation_type_id = %s, press_id = %s;
        """
        cur.execute(time_formula, (time_values[3], time_values[4], time_values[0], time_values[1], time_values[2]))
    except (Exception, DatabaseError) as _err:
        print(f"\nQUERY FAILED: 'INSERT INTO time_between_operations'\nError: {_err}\n")
        raise RuntimeError("Function 'INSERT INTO time_between_operations' failed")
