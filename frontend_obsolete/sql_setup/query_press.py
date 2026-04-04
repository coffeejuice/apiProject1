import os
from pathlib import Path

from forgelab.sql_setup.connections import close_connection, connect_to_db, load_config, select_configuration


def postgresql_get_list_of_press(cur) -> (list, list):
    """Returns two lists: list of column names and list of tuples with press data."""
    press_columns = ('press_id', 'name')
    cur.execute(f"SELECT {press_columns[0]}, {press_columns[1]} FROM presses")
    press_list = cur.fetchall()
    return press_columns, press_list


def postgresql_get_press_record(cur, press_id: int) -> (list, list):
    """Get press_id. Returns two lists: column names and press record."""
    cur.execute("SHOW COLUMNS FROM presses")
    press_columns = [i[0] for i in cur.fetchall()]
    cur.execute("SELECT * FROM presses WHERE press_id = %s LIMIT 1", (press_id,))
    press_data = cur.fetchone()
    return press_columns, press_data


def postgresql_get_list_of_press_mode(cur, press_id: int) -> (list, list):
    """Get press_id. Returns two lists: list of column names and list of tuples with press modes data."""
    press_columns = ('press_mode_id', 'name')
    cur.execute(f"SELECT {press_columns[0]}, {press_columns[1]} FROM press_modes WHERE press_id = %s", (press_id,))
    press_mode_list = cur.fetchall()
    return press_columns, press_mode_list


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


def postgresql_get_press_dict(cur, press_id: int, press_mode_id: int) -> dict:
    """Get press_id and press_mode_id. Returns dictionary with press data."""
    press_columns, press_data = postgresql_get_press_record(cur, press_id)
    press_mode_columns, press_mode_data = postgresql_get_press_mode_record(cur, press_mode_id)
    _, press_mode_power_limit_data = postgresql_get_press_mode_power_limit_records(cur, press_mode_id)
    press_dict = {}
    for i, data_name in enumerate(press_columns):
        press_dict[data_name] = press_data[i]
    for i, data_name in enumerate(press_mode_columns):
        press_dict[data_name] = press_mode_data[i]
    press_dict['press_mode_power_limit'] = press_mode_power_limit_data
    return press_dict


if __name__ == '__main__':
    _p = Path(os.path.split(__file__)[0])
    _root_dir = os.path.abspath(_p.parent)
    multiple_config = load_config(_root_dir)
    config = select_configuration(multiple_config)
    conn, cursor = connect_to_db(config)
    print(postgresql_get_list_of_press(cursor))
    print(postgresql_get_press_record(cursor, 1))
    print(postgresql_get_list_of_press_mode(cursor, 1))
    print(postgresql_get_press_mode_record(cursor, 1))
    print(postgresql_get_press_mode_power_limit_records(cursor, 1))
    print(postgresql_get_press_dict(cursor, 1, 1))
    close_connection(conn, cursor)
