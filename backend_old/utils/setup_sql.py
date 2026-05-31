import sys
import os

from forgelab.sql_setup.create_admin_management_functions import CreateAdminManagementFunctions
from forgelab.sql_setup.create_functions_communicate_with_client import CreateToClientCommunicationFunctions
from forgelab.sql_setup.create_operations_table_functions import CreateOperationFunctions
from forgelab.sql_setup.create_run_stop_buttons_functions import CreateRunStopButtonsFunctions
from forgelab.sql_setup.create_queue_functions import CreateQueueFunctions
from forgelab.sql_setup.create_functions_and_triggers import CreateFunctionsAndTriggers
from forgelab.sql_setup.create_tables import CreateTables
from forgelab.sql_setup.import_json import insert_config
from forgelab.sql_setup.test_records_add import \
    postgresql_add_test_user, postgresql_add_test_process, postgresql_add_test_process_versions, insert_servers, \
    assert_config_servers, insert_servers_versions_compatibility
from forgelab.sql_setup.query_operation import print_available_type_ids
from forgelab.sql_setup.connections import \
    is_postgresql_db_exists, clear_database, is_database_empty, connect_to_db, close_connection, load_config, \
    select_configuration, create_database
from forgelab.sql_setup.insert_time_records import insert_time_operation_changing_records
from forgelab.sql_setup.create_operations import \
    print_tables, insert_operations, insert_process_headers, assert_library, load_operations
from forgelab.sql_setup.insert_press_records_from_library import insert_press_records_from_library
from forgelab.sql_setup.insert_die_records_from_library import insert_die_records_from_library
from forgelab.sql_setup.insert_material_records import insert_material_records
from forgelab.sql_setup.insert_feed_direction_records import \
    insert_feed_direction_records, insert_furnace_class_records, insert_languages, insert_departments_records, \
    insert_tail_side_records


# print(f'__file__={__file__:<35} | __name__={__name__:<25} | __package__={str(__package__):<25}')

def get_config_dir() -> str:
    _root_dir = os.path.dirname(__file__)
    _config_dir = os.path.join(_root_dir, 'forgelab', 'data', 'config')
    return _config_dir


def init_db():
    config_dir = get_config_dir()
    # Assert
    operations_json = load_operations()
    assert_library(operations_json)

    multiple_config = load_config(config_dir)

    sql_param = select_configuration(multiple_config)

    # Drop db
    if is_postgresql_db_exists(sql_param):
        print(f"\nDatabase '{sql_param['db']['base']}' already exists. Trying clear the database.")
        # drop_database()
        # is_database_empty()
        clear_database(sql_param)
        if not is_database_empty(sql_param):
            sys.exit(1)  # Exit with status 1 (error)
    else:
        create_database(sql_param)

    # else:
        # create_database()
    connection, cursor = connect_to_db(sql_param)

    CreateTables.create(connection)
    CreateFunctionsAndTriggers.create(connection)
    CreateToClientCommunicationFunctions.create(connection)
    CreateQueueFunctions.create(connection)
    CreateAdminManagementFunctions.create(connection)
    CreateOperationFunctions.create(connection)
    CreateRunStopButtonsFunctions.create(connection)

    insert_operations(connection, operations_json)

    # Print
    print_tables(cursor)

    # insert_operation_type_category()
    insert_config(cursor, config_dir)
    insert_languages(cursor)
    insert_process_headers(cursor)
    insert_material_records(cursor)
    insert_feed_direction_records(cursor)
    insert_tail_side_records(cursor)
    insert_furnace_class_records(cursor)
    insert_departments_records(cursor)

    # Add Real data from Library Dictionary to SQL DB
    insert_press_records_from_library(cursor)
    insert_die_records_from_library(cursor)
    insert_time_operation_changing_records(connection)

    # ----------------------------------
    # Add Servers
    # ----------------------------------

    assert_config_servers(sql_param)
    insert_servers(connection, sql_param)
    insert_servers_versions_compatibility(connection, sql_param)

    # ----------------------------------
    # Add Test records to DB
    # ----------------------------------

    # Add test Users
    postgresql_add_test_user(cursor)

    # Add test Processes
    postgresql_add_test_process(cursor)

    # Add test process versions
    postgresql_add_test_process_versions(cursor)

    # Get User's processes and process versions
    # process_id_list, headers = postgresql_get_processes_of_user(config, user_id)
    # process_id_all = postgresql_get_processes(cur)
    # process_version_id_all = postgresql_get_process_versions_of_process_id(cur, process_id)

    # Get All test Process versions
    # postgresql_get_process_versions(cur)

    # Print available type_id's
    print_available_type_ids(cursor, sql_param)

    close_connection(connection, cursor)


def print_available_operation_numbers():
    config_dir = get_config_dir()
    multiple_config = load_config(config_dir)
    sql_param = select_configuration(multiple_config)
    connection, cursor = connect_to_db(sql_param)

    # Print available type_id's
    print_available_type_ids(cursor, sql_param)

    close_connection(connection, cursor)


def update_operations_library():
    config_dir = get_config_dir()
    multiple_config = load_config(config_dir)
    sql_param = select_configuration(multiple_config)
    connection, cursor = connect_to_db(sql_param)

    operations_json = load_operations()
    assert_library(operations_json)
    insert_operations(connection, operations_json)
    insert_time_operation_changing_records(connection)

    # Print available type_id's
    print_available_type_ids(cursor, sql_param)

    close_connection(connection, cursor)


def update_time_between_operation():
    config_dir = get_config_dir()
    multiple_config = load_config(config_dir)
    sql_param = select_configuration(multiple_config)
    connection, cursor = connect_to_db(sql_param)

    # operations_json = load_operations()
    # assert_library(operations_json)
    insert_time_operation_changing_records(connection)

    # Print available type_id's
    print_available_type_ids(cursor, sql_param)

    close_connection(connection, cursor)


def update_die_and_die_assembly():
    config_dir = get_config_dir()
    multiple_config = load_config(config_dir)
    sql_param = select_configuration(multiple_config)
    connection, cursor = connect_to_db(sql_param)

    # operations_json = load_operations()
    # assert_library(operations_json)
    insert_die_records_from_library(cursor)

    # Print available type_id's
    print_available_type_ids(cursor, sql_param)

    close_connection(connection, cursor)


def add_config():
    root_dir = os.path.split(__file__)[0]
    multiple_sql_param = load_config(root_dir)
    sql_param = select_configuration(multiple_sql_param)
    connection, cursor = connect_to_db(sql_param)
    insert_config(cursor, root_dir)


def select_option():
    while True:
        option_num = 0
        options = {
            0: "Exit.",
            1: "Erase (if exist) old DB and install new fresh DB.",
            2: "Update 'operations' table according to 'operations.json' template.",
            3: "Show available operation numbers in 'operations' table.",
            4: "Update 'time_between_operations' table according to records inside 'insert_time_records.py'.",
            5: "Update 'die' and 'die_assembly' tables."
        }

        print("\nOptions:")
        for key, value in options.items():
            print(str(key), value)

        def confirm_selected_option() -> bool:
            print("\nUser selected: ", str(option_num), options[option_num])
            while True:
                is_confirmed = input("Please enter [Y] to confirm or press [Enter] to cancel: ")
                if is_confirmed.lower() == "y":
                    return True
                elif is_confirmed == "":
                    return False
                # else:
                    # continue

        try:
            option_str = input("Enter option number [Enter]: ")
            assert option_str.strip() != "", "You entered empty string."
            assert option_str.isdigit(), (
                f"You entered not a number. "
                f"Enter a number from {list(options.keys())[0]} to {list(options.keys())[-1]}.")
            option_num = int(option_str)
            assert option_num in list(options.keys()), (
                f"You entered a number {option_num}, but there is no such an option. "
                f"Enter a number from {list(options.keys())[0]} to {list(options.keys())[-1]}.")
        except Exception as _err:
            print(f"Wrong input.\n{type(_err).__name__}: {_err}")
            continue
        match option_num:
            case 0:
                    return
            case 1:
                if confirm_selected_option():
                    init_db()
                continue
            case 2:
                if confirm_selected_option():
                    update_operations_library()
                continue
            case 3:
                print_available_operation_numbers()
                continue
            case 4:
                if confirm_selected_option():
                    update_time_between_operation()
                continue
            case 5:
                if confirm_selected_option():
                    update_die_and_die_assembly()
                continue
            case _:
                print(f"Program has Error:\nThere is no such option ({option_num} in the algorith yet.")
                continue


if __name__ == "__main__":
    """Start main window"""
    select_option()
