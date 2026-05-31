import os
from pathlib import Path

from forgelab.sql_setup.insert_press_records_from_library import insert_press_records_from_library
from forgelab.sql_setup.connections import connect_to_db, close_connection, load_config, select_configuration
from forgelab.sql_setup.create_operations import assert_library, load_operations


# print(f'__file__={__file__:<35} | __name__={__name__:<25} | __package__={str(__package__):<25}')


def run():
    _p = Path(os.path.split(__file__)[0])
    root_dir = os.path.abspath(_p.parent)

    # Assert
    operations_json = load_operations()
    assert_library(operations_json)

    multiple_config = load_config(root_dir)

    config = select_configuration(multiple_config)

    connection, cursor = connect_to_db(config)

    insert_press_records_from_library(cursor)

    close_connection(connection, cursor)


if __name__ == "__main__":
    """Start main window"""
    run()
