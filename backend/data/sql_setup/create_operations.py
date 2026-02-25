import os
import re

from PIL import Image, ImageDraw, ImageFont
import io
import json
import psycopg2
from psycopg2 import OperationalError, DatabaseError, sql
from forgelab.sql_setup.connections import connect_to_db, close_connection


USER_SURNAMES = ('Smith', 'Johnson', 'Williams')
USER_NAMES = ('James', 'Robert', 'John')


def print_tables(cur):
    """Print tables"""
    print('\nSHOW DATABASES:')
    cur.execute("SELECT datname FROM pg_database;")
    databases = cur.fetchall()
    print([name[0] for name in databases])
    print('\nSHOW TABLES:')
    cur.execute("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname='public';")
    print([name[0] for name in cur])


def load_operations() -> dict:
    """Receives '*.json' file name. Returns dictionary. If error, stops server."""
    _config = {}
    abs_path = os.path.join(os.path.dirname(__file__), 'operations.json')
    try:
        with open(abs_path, 'r', encoding='utf-8') as stream:
            _config = json.load(stream)

    except FileNotFoundError:
        print(f"ERROR: The configuration file '{abs_path}' was not found. Stopping server.")
    except OSError as exception:
        print(f"Some 'OSError': {exception.strerror} {exception.errno}.  Stopping server.")
    except json.JSONDecodeError:
        print(f"The configuration file '{abs_path}' contains invalid JSON. Stopping server.")
    except Exception as _err:
        print(f"Some uncategorized Error: {_err}. Stopping server.")
    return _config


def assert_library(operations_json: dict):
    """Assert library for missing or duplicate indices."""
    print('\nAssert Operations JSON dictionary:')
    # Check if id's of operations_json are unique
    id_list = [_operation['type_id'] for _operation in operations_json.values()]
    # sort id_list in ascending order
    id_list.sort()
    # max value of id_list
    max_id = id_list[-1]
    if len(id_list) != len(set(id_list)):
        # Find duplicate indices
        duplicate_indices = [i for i in id_list if id_list.count(i) > 1]
        raise ValueError(f'operations_json has ERROR: it has duplicate indices: {duplicate_indices}')
    else:
        print(f"operations_json is OKAY: no duplicates.")
    # find missing indices
    missing_indices = [i for i in range(1, max_id + 1) if i not in id_list]
    print(f'NOTE: available indices in operations_json are {missing_indices}')


def insert_operations(conn, operations_json: dict):
    """Create operation_nnn tables using auto generator."""
    failed_list = []

    existing_records_count = 0
    success_upsert_records_count = 0

    existing_images_count = 0
    success_tooltip_images_count = 0

    existing_tables_count = 0
    success_tables_count = 0
    skipped_tables_count = 0

    existing_triggers_count = 0
    success_triggers_count = 0
    skipped_triggers_count = 0

    for operation in operations_json.values():
        record = operation.copy()
        sql_col = record.pop('sql_query_formula')
        table_name = f"operations_type_id_{str(record['type_id'])}"
        type_id = record['type_id']
        is_obsolete = record['is_obsolete']
        if type_id == 84:
            print("")

        success_upsert_records_count += _query_upsert_operations_library(conn, record)
        success_tooltip_images_count += _add_tooltip_image_into_operations_library(conn, type_id)

        if len(sql_col) == 0 or is_obsolete:
            skipped_tables_count += 1
            skipped_triggers_count += 1
        else:
            success_tables_count += create_or_update_tables_operations_type_id_nnn(conn, type_id, table_name, sql_col)
            success_triggers_count += _create_trigger_on_update_operations_type_id_nnn(conn, type_id, table_name)

    # --------------- COUNT TOTAL RECORDS, IMAGES, TABLES, TRIGGERS ---------------
    total_records_count = (success_upsert_records_count + existing_records_count)
    total_images_count = (success_tooltip_images_count + existing_images_count)
    total_tables_count = (success_tables_count + existing_tables_count)
    total_triggers_count = (success_triggers_count + existing_triggers_count)

    are_counts_failed = not all((
            total_records_count == len(operations_json),
            total_images_count == len(operations_json),
            total_tables_count == len(operations_json) - skipped_tables_count,
            total_triggers_count == len(operations_json) - skipped_triggers_count
    ))

    if failed_list or are_counts_failed:
        print(
            f"FAILED INSERTING OPERATIONS:\n"
            f"       FAILED records for type_id's: {failed_list};\n"
            f"                            DETAILS:\n"
        )
    else:
        print(
            f"OK, INSERTING OPERATIONS ARE SUCCESSFUL:\n"
        )

    print(
        f"             'operations.json' file: {len(operations_json)} operations are in the file;\n"
        f"         'operations_library' table: {total_records_count} operations are in  now;\n"
        f"         'operations_library' table: {total_images_count} tooltip images are set;\n"
        f"    'operations_type_id_NNN' tables: {total_tables_count} tables exist;\n"
        f"    'operations_type_id_NNN' tables: {skipped_tables_count} tables must not exist;\n"
        f"  'operations_type_id_NNN' triggers: {total_triggers_count} triggers exist;\n"
        f"  'operations_type_id_NNN' triggers: {skipped_triggers_count} triggers must not exist;\n"
    )

    if failed_list or are_counts_failed:
        raise ValueError(f"Failed to insert records into operations_library for type_id's: {failed_list}")


def create_image(type_id: int) -> io.BytesIO:
    # os.chdir('../images')

    # Set the dimensions of the images
    img_width = 500
    img_height = 500

    # Create a font object
    font = ImageFont.truetype(font="arial.ttf", size=470)

    left, top, right, bottom = range(4)

    # Create a new image with a white background
    img = Image.new(mode='RGB', size=(img_width, img_height), color='white')

    # Get a drawing context
    draw = ImageDraw.Draw(img)

    # Create a text box for the number
    text_box = draw.textbbox((0, 0), str(type_id), font=font)

    # Calculate the x and y coordinates for the center of the image
    x = (img_width - (text_box[right] - text_box[left])) / 2
    y = (img_height - (text_box[bottom] - text_box[top])) / 2 - text_box[top]

    # Draw the number in the center of the image
    draw.text((x, y), str(type_id), fill='black', font=font)

    # Save the image with the appropriate file name
    # file_name = f"tooltip_image_{type_id}.png"
    # img.save(file_name)
    file_buffer = io.BytesIO()
    img.save(file_buffer, format='PNG')
    # file_buffer.write(file_name)
    return file_buffer


# def _is_type_id_in_operations_library(conn, type_id: int):
#     cur = conn.cursor()
#
#     try:
#         cur.execute(f"SELECT 1 FROM operations_library WHERE type_id = %s LIMIT 1;", (type_id, ))
#         result = len(cur.fetchone()) == 1
#     except (OperationalError, Exception):
#         result = False
#
#     cur.close()
#
#     return result


def _is_exists_table_operations_type_id_nnn(conn, table_name: str):

    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT 1 FROM {table_name} LIMIT 1;")
        return True
    except Exception:
        return False


def _create_table_operations_type_id_nnn(conn, type_id: int, table_name: str, columns: str) -> bool:
    try:
        with conn.cursor() as cur:
            create_query_text = (
                f"CREATE TABLE IF NOT EXISTS {table_name} "
                f"(id BIGINT PRIMARY KEY, {columns}, FOREIGN KEY (id) REFERENCES operations(id) ON DELETE CASCADE);")
            cur.execute(create_query_text)
            conn.commit()
        return True
    except Exception as _err:
        print(f"FAILED {type_id = } {type(_err).__name__}: {_err}")
        return False


# __________________________________________________________________________


def __get_existing_columns(cursor, table_name):
    cursor.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s AND table_schema = 'public'
    """, (table_name,))
    return {row[0] for row in cursor.fetchall()}


def __get_existing_foreign_keys(cursor, table_name):
    cursor.execute("""
        SELECT
            tc.constraint_name,
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM 
            information_schema.table_constraints AS tc 
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
        WHERE tc.table_name = %s AND tc.table_schema = 'public' AND tc.constraint_type = 'FOREIGN KEY';
    """, (table_name,))
    fk_list = []
    for row in cursor.fetchall():
        fk = {
            'constraint_name': row[0],
            'column': row[1],
            'references_table': row[2],
            'references_field': row[3]
        }
        fk_list.append(fk)
    return fk_list


def __get_columns_to_drop(existing_columns, desired_columns, primary_column: str):
    assert isinstance(primary_column, str)
    return existing_columns - set(desired_columns) - {primary_column}


def __generate_drop_columns_sql(type_id, table_name, columns_to_drop):
    try:
        statements = []
        for column in columns_to_drop:
            stmt = sql.SQL("ALTER TABLE {table} DROP COLUMN IF EXISTS {column};").format(
                table=sql.Identifier(table_name),
                column=sql.Identifier(column)
            )
            statements.append(stmt)
        return statements
    except Exception as _err:
        print(f"FAILED {type_id = } {type(_err).__name__}: {_err}")


def __generate_alter_column_types_sql(table_name, names, types):
    statements = []
    for name, dtype in zip(names, types):
        stmt = sql.SQL("ALTER TABLE {table} ALTER COLUMN {column} TYPE {dtype} USING {column}::{dtype};").format(
            table=sql.Identifier(table_name),
            column=sql.Identifier(name),
            dtype=sql.SQL(dtype)
        )
        statements.append(stmt)
    return statements


def __generate_drop_foreign_keys_sql(table_name, existing_foreign_keys):
    statements = []
    for fk in existing_foreign_keys:
        stmt = sql.SQL("ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {constraint};").format(
            table=sql.Identifier(table_name),
            constraint=sql.Identifier(fk['constraint_name'])
        )
        statements.append(stmt)
    return statements


def __generate_add_foreign_keys_sql(type_id, table_name, foreign_keys):
    statements = []
    try:
        for fk in foreign_keys:
            delimiters = [' ', '(', ')']
            pattern = '[' + ''.join(map(re.escape, delimiters)) + ']'
            fk_l = [
                _s.strip() for _s in
                re.split(pattern, fk.lower().replace('foreign', '').replace('key', '').replace('references', ''))
                if _s.strip()]
            column = fk_l.pop(0)
            references_table = fk_l.pop(0)
            references_field = fk_l.pop(0)
            constraint_name = f"fk_{table_name}_{column}_{references_table}_{references_field}"
            conditions = ' '.join(fk_l).upper() if fk_l else ''
            stmt = sql.SQL(
                "ALTER TABLE {tab} ADD CONSTRAINT {const} FOREIGN KEY ({col}) REFERENCES {ref_tab} ({ref_col}) "
                + conditions
                + ";"
            ).format(
                tab=sql.Identifier(table_name),
                const=sql.Identifier(constraint_name),
                col=sql.Identifier(column),
                ref_tab=sql.Identifier(references_table),
                ref_col=sql.Identifier(references_field)
            )
            statements.append(stmt)
        return statements
    except Exception as _err:
        print(f"FAILED {type_id = } {type(_err).__name__}: {_err}")


def __create_or_update_tables_operations_type_id_nnn(conn, type_id: int, table_name: str, columns: str) -> int:
    try:

        columns = columns.strip().strip(',')

        if not _is_exists_table_operations_type_id_nnn(conn, table_name):
            if not _create_table_operations_type_id_nnn(conn, type_id, table_name, columns):
                return 0

        columns_list = [_s.strip() for _s in columns.split(',')]
        foreign_keys = [columns_list.pop(i)
                        for i, _s in enumerate(columns_list)
                        if 'foreign' in _s.lower().split()]
        unzipped  = zip(*[_s.split(maxsplit=1) for _s in columns_list])
        names, types = map(tuple, unzipped)

        with (conn.cursor() as cur):
            # Retrieve existing columns and foreign keys
            existing_columns = __get_existing_columns(cur, table_name)
            existing_foreign_keys = __get_existing_foreign_keys(cur, table_name)

            # Determine columns to drop
            columns_to_drop = __get_columns_to_drop(existing_columns, names, 'id')
            if columns_to_drop:
                message = (f"Press [Y] to confirm to DROP columns '{', '.join(columns_to_drop)} "
                           f"of table '{table_name}' [Y/N]:")
                if input(message).lower() != "y":
                    return 0

            # Generate SQL statements
            drop_columns_sql = __generate_drop_columns_sql(type_id, table_name, columns_to_drop)
            alter_columns_sql = __generate_alter_column_types_sql(table_name, names, types)
            drop_fks_sql = __generate_drop_foreign_keys_sql(table_name, existing_foreign_keys)
            add_fks_sql = __generate_add_foreign_keys_sql(type_id, table_name, foreign_keys)

            # Combine all SQL statements
            all_statements = drop_columns_sql + alter_columns_sql + drop_fks_sql + add_fks_sql

            # Execute all statements
            for stmt in all_statements:
                print(f"Executing: {stmt.as_string(cur)}")
                cur.execute(stmt)
        return 1
    except Exception as _err:
        print(f"FAILED {type_id = } {type(_err).__name__}: {_err}")
        return 0


# __________________________________________________________
# __________________________________________________________
# __________________________________________________________
# __________________________________________________________
# __________________________________________________________


def get_existing_columns(cursor, table_name, primary_key: str):
    """
    Retrieves existing column properties from the specified table.

    Parameters:
        cursor (psycopg2.extensions.cursor): The database cursor.
        table_name (str): The name of the table.
        primary_key (str): Column name with Primary key contstraint

    Returns:
        dict: A dictionary where keys are column names and values are dictionaries of properties.
    """
    cursor.execute("""
        SELECT column_name, data_type, column_default, is_nullable
        FROM information_schema.columns
        WHERE table_name = %s AND table_schema = 'public';
    """, (table_name,))

    existing_columns = {}
    for row in cursor.fetchall():
        column_name, data_type, column_default, is_nullable = row
        if column_name == primary_key:
            continue
        existing_columns[column_name] = {
            'type': data_type.upper(),
            'default': column_default,
            'not_null': is_nullable == 'NO'
        }
    return existing_columns


def get_existing_foreign_keys(cursor, table_name, primary_key: str):
    """
    Retrieves existing foreign key constraints from the specified table.

    Parameters:
        cursor (psycopg2.extensions.cursor): The database cursor.
        table_name (str): The name of the table.
        primary_key (str): Column name with Primary key constraint. Do not modify foreign key constraint for this column.

    Returns:
        list: A list of dictionaries containing foreign key details.
    """
    cursor.execute("""
        SELECT
            tc.constraint_name,
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM 
            information_schema.table_constraints AS tc 
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
              AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
              AND ccu.table_schema = tc.table_schema
        WHERE tc.table_name = %s 
          AND tc.table_schema = 'public' 
          AND tc.constraint_type = 'FOREIGN KEY';
    """, (table_name,))

    fk_list = []
    for row in cursor.fetchall():
        column = row[1]
        if column == primary_key:
            continue
        fk = {
            'constraint_name': row[0],
            'column': column,
            'references_table': row[2],
            'references_field': row[3]
        }
        fk_list.append(fk)
    return fk_list


def get_columns_to_drop(existing_columns, desired_columns, primary_key: str):
    """
    Determines which columns need to be dropped.

    Parameters:
        existing_columns (dict): Existing columns with their properties.
        desired_columns (dict): Desired columns with their properties.
        primary_key (str): Column name

    Returns:
        set: A set of column names to be dropped.
    """
    assert isinstance(primary_key, str)
    return set(existing_columns.keys()) - set(desired_columns.keys()) - {primary_key}


def generate_drop_columns_sql(type_id, table_name, columns_to_drop):
    """
    Generates SQL statements to drop specified columns from a table without using CASCADE.

    Parameters:
        type_id (int): operation number as in operations_library
        table_name (str): The name of the table from which to drop columns.
        columns_to_drop (set): A set of column names to be dropped.

    Returns:
        list: A list of psycopg2.sql.SQL objects representing the DROP COLUMN statements.
    """
    statements = []
    try:
        for column in columns_to_drop:
            stmt = sql.SQL("ALTER TABLE {table} DROP COLUMN IF EXISTS {column};").format(
                table=sql.Identifier(table_name),
                column=sql.Identifier(column)
            )
            statements.append(stmt)
        return statements
    except Exception as _err:
        print(f"FAILED {type_id = } {type(_err).__name__}: {_err}")


def generate_add_columns_sql(table_name: str, new_columns: dict, existing_columns: dict):
    """
    Generates SQL statements to alter existing columns based on differences.

    Parameters:
        table_name (str): The name of the table.
        new_columns (dict): Desired columns with their properties.
        existing_columns (dict): Existing columns with their properties.

    Returns:
        list: A list of psycopg2.sql.SQL objects representing the ALTER COLUMN statements.
    """
    statements = []
    for new_col, props in new_columns.items():
        if new_col in existing_columns:
            continue  # Existing columns will be altered separately

        desired_type = props['type'].upper()
        desired_default = props['default']
        desired_not_null = props['not_null']

        # Handle different default types (e.g., strings need quotes)
        if isinstance(desired_default, str) and desired_default.lower() == "null":
            default_sql = sql.SQL(desired_default)
        elif isinstance(desired_default, str) and not desired_default.upper().startswith(
                ('NEXTVAL', 'CURRENT_TIMESTAMP')):
            default_sql = sql.Literal(desired_default)
        else:
            default_sql = sql.SQL(desired_default)
        stmt = sql.SQL(
            "ALTER TABLE {table} ADD COLUMN {column} {new_type}"
            + " DEFAULT {default}" if desired_default is not None else ""
            + " NOT NULL" if desired_not_null else ""
            + ";"
        ).format(
            table=sql.Identifier(table_name),
            column=sql.Identifier(new_col),
            new_type=sql.SQL(desired_type),
            default=default_sql
        )
        statements.append(stmt)

    return statements


def generate_alter_columns_sql(table_name: str, new_columns: dict, existing_columns: dict):
    """
    Generates SQL statements to alter existing columns based on differences.

    Parameters:
        table_name (str): The name of the table.
        new_columns (dict): Desired columns with their properties.
        existing_columns (dict): Existing columns with their properties.

    Returns:
        list: A list of psycopg2.sql.SQL objects representing the ALTER COLUMN statements.
    """
    statements = []
    for new_col, props in new_columns.items():
        if new_col not in existing_columns:
            continue  # New columns can be added separately if needed

        # 1. Alter Data Type if different
        desired_type = props['type'].upper()
        existing_type = existing_columns[new_col]['type']
        if desired_type != existing_type:
            stmt = sql.SQL(
                "ALTER TABLE {table} ALTER COLUMN {column} TYPE {new_type} USING {column}::{new_type};"
            ).format(
                table=sql.Identifier(table_name),
                column=sql.Identifier(new_col),
                new_type=sql.SQL(desired_type)
            )
            statements.append(stmt)

        # 2. Alter Default Value
        desired_default = props['default']
        existing_default = existing_columns[new_col]['default']
        if desired_default != existing_default:
            if desired_default is not None:
                # Handle different default types (e.g., strings need quotes)
                if isinstance(desired_default, str) and desired_default.lower() == "null":
                    default_sql = sql.SQL(desired_default)
                elif isinstance(desired_default, str) and not desired_default.upper().startswith(
                        ('NEXTVAL', 'CURRENT_TIMESTAMP')):
                    default_sql = sql.Literal(desired_default)
                else:
                    default_sql = sql.SQL(desired_default)
                stmt = sql.SQL(
                    "ALTER TABLE {table} ALTER COLUMN {column} SET DEFAULT {default};"
                ).format(
                    table=sql.Identifier(table_name),
                    column=sql.Identifier(new_col),
                    default=default_sql
                )
            else:
                stmt = sql.SQL(
                    "ALTER TABLE {table} ALTER COLUMN {column} DROP DEFAULT;"
                ).format(
                    table=sql.Identifier(table_name),
                    column=sql.Identifier(new_col)
                )
            statements.append(stmt)

        # 3. Alter NOT NULL Constraint
        desired_not_null = props['not_null']
        existing_not_null = existing_columns[new_col]['not_null']
        if desired_not_null != existing_not_null:
            if desired_not_null:
                stmt = sql.SQL("""
                    ALTER TABLE {table}
                    ALTER COLUMN {column} SET NOT NULL;
                """).format(
                    table=sql.Identifier(table_name),
                    column=sql.Identifier(new_col)
                )
            else:
                stmt = sql.SQL("""
                    ALTER TABLE {table}
                    ALTER COLUMN {column} DROP NOT NULL;
                """).format(
                    table=sql.Identifier(table_name),
                    column=sql.Identifier(new_col)
                )
            statements.append(stmt)

    return statements


def generate_drop_foreign_keys_sql(table_name, existing_foreign_keys):
    """
    Generates SQL statements to drop existing foreign key constraints.

    Parameters:
        table_name (str): The name of the table.
        existing_foreign_keys (list): List of dictionaries containing foreign key details.

    Returns:
        list: A list of psycopg2.sql.SQL objects representing the DROP CONSTRAINT statements.
    """
    statements = []
    for fk in existing_foreign_keys:
        stmt = sql.SQL("ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {constraint};").format(
            table=sql.Identifier(table_name),
            constraint=sql.Identifier(fk['constraint_name'])
        )
        statements.append(stmt)
    return statements


def generate_add_foreign_keys_sql(type_id: int, table_name, foreign_keys: list[dict]):
    """
    Generates SQL statements to add new foreign key constraints.

    Parameters:
        type_id (int): type_id column
        table_name (str): The name of the table.
        foreign_keys (list): List of dictionaries containing foreign key definitions.

    Returns:
        list: A list of psycopg2.sql.SQL objects representing the ADD CONSTRAINT statements.
    """
    statements = []
    try:
        for fk in foreign_keys:
            stmt = sql.SQL("""
                ALTER TABLE {table}
                ADD CONSTRAINT {constraint_name}
                FOREIGN KEY ({column})
                REFERENCES {ref_table} ({ref_column})
                ON DELETE {on_delete}
                ON UPDATE {on_update};
            """).format(
                table=sql.Identifier(table_name),
                constraint_name=sql.Identifier(fk['constraint_name']),
                column=sql.Identifier(fk['column']),
                ref_table=sql.Identifier(fk['references_table']),
                ref_column=sql.Identifier(fk['references_field']),
                on_delete=sql.SQL(fk.get('on_delete', 'NO ACTION')),
                on_update=sql.SQL(fk.get('on_update', 'NO ACTION'))
            )
            statements.append(stmt)
        return statements
    except Exception as _err:
        print(f"FAILED {type_id = } {type(_err).__name__}: {_err}")


def build_new_foreign_keys(type_id: int, table_name: str, foreign_keys_list: list) -> list[dict]:
    try:
        fk_l_d = []
        for fk in foreign_keys_list:
            delimiters = [' ', '(', ')']
            pattern = '[' + ''.join(map(re.escape, delimiters)) + ']'
            fk_l = [
                _s.strip() for _s in
                re.split(pattern, fk.lower().replace('foreign', '').replace('key', '').replace('references', ''))
                if _s.strip()]
            column = fk_l.pop(0)
            references_table = fk_l.pop(0)
            references_field = fk_l.pop(0)
            constraint_name = f"fk_{table_name}_{column}_{references_table}_{references_field}"
            on_delete = []
            on_update = []
            while fk_l:
                _s = fk_l.pop(0)
                if _s == "on":
                    continue
                elif _s == "delete":
                    while _s != "on" and fk_l:
                        _s = fk_l.pop(0)
                        on_delete.append(_s)
                elif _s == "update":
                    while _s != "on" and fk_l:
                        _s = fk_l.pop(0)
                        on_update.append(_s)
            fk_l_d.append({
                'column': column,
                'constraint_name': constraint_name,
                'references_table': references_table,
                'references_field': references_field,
                'on_delete': " ".join(on_delete).upper() if on_delete else "CASCADE",
                'on_update': " ".join(on_update).upper() if on_update else "CASCADE"
            })
        return fk_l_d
    except Exception as _err:
        print(f"FAILED {type_id = } {type(_err).__name__}: {_err}")
        raise


def build_new_columns(type_id: int, columns: list) -> dict:
    try:
        # if type_id == 84:
        #     print("")
        col_dict: dict = {}
        for col in columns:
            fk_l_raw = [_s for _s in col.lower().split() if _s.strip()]
            # Glue together split data types like NUMERIC(9, 6) mistakenly split with *.split(",")
            fk_l = [fk_l_raw.pop(0)]
            while fk_l_raw:
                _s = fk_l_raw.pop(0)
                if _s.strip()[0].isdigit() and _s.strip()[-1] == ")":
                    fk_l[-1] += " " + _s
                else:
                    fk_l.append(_s)
            column = fk_l.pop(0)
            data_type = ""
            default = ""
            not_null = ""
            _s = fk_l.pop(0)
            while fk_l:
                if _s == "default":
                    _s = fk_l.pop(0)
                    while _s != "not":
                        default += " " + _s
                        if not fk_l:
                            break
                        _s = fk_l.pop(0)
                elif _s == "not":
                    _s = fk_l.pop(0)
                    while _s != "default":
                        not_null += " " + _s
                        if not fk_l:
                            break
                        _s = fk_l.pop(0)
                else:
                    while _s not in ("default", "not",):
                        data_type += " " + _s
                        if not fk_l:
                            break
                        _s = fk_l.pop(0)
            col_dict[column] = {
                'type': data_type.strip().upper(),
                'default': default.strip().upper(),
                'not_null': True if not_null.strip().upper() == "NULL" else False
            }
        return col_dict
    except Exception as _err:
        print(f"FAILED {type_id = } {type(_err).__name__}: {_err}")
        raise


def execute_sql_statements(conn, type_id: int, statements):
    """
    Executes a list of SQL statements within a transaction.

    Parameters:
        conn (psycopg2.extensions.connection): The database connection object.
        type_id (str): Primary Key column
        statements (list): A list of psycopg2.sql.SQL objects to execute.

    Raises:
        Exception: If any SQL statement fails.
    """
    try:
        with conn.cursor() as cursor:
            for stmt in statements:
                try:
                    cursor.execute(stmt)
                except Exception as _err:
                    print(f"FAILED {type_id = } {type(_err).__name__}: {_err}")
                    raise RuntimeError(f"{type_id = }") # Re-raise to trigger rollback
    except Exception as _err:
        print(f"FAILED {type_id = } {type(_err).__name__}: {_err}")
        raise RuntimeError(f"{type_id = }")


def create_or_update_tables_operations_type_id_nnn(conn, type_id: int, table_name: str, columns: str) -> int:
    try:
        if type_id == 66:
            print("")

        columns = columns.strip().strip(',')

        if not _is_exists_table_operations_type_id_nnn(conn, table_name):
            if not _create_table_operations_type_id_nnn(conn, type_id, table_name, columns):
                return 0

        columns_list_raw = [_s for _s in columns.split(',') if _s.strip()]

        # Glue together split data types like NUMERIC(9, 6) mistakenly split with *.split(",")
        columns_list = [columns_list_raw.pop(0)]
        while columns_list_raw:
            _s = columns_list_raw.pop(0)
            if _s.strip()[0].isdigit():
                columns_list[-1] += "," + _s
            else:
                columns_list.append(_s)

        foreign_keys_list = [
            columns_list.pop(i)
            for i, _s in enumerate(columns_list)
            if 'foreign' in _s.lower().split()]

        foreign_keys_new = build_new_foreign_keys(type_id, table_name, foreign_keys_list)
        columns_new = build_new_columns(type_id, columns_list)

        with conn.cursor() as cursor:
            # Retrieve existing columns and foreign keys
            existing_columns = get_existing_columns(cursor, table_name, primary_key="id")
            existing_foreign_keys = get_existing_foreign_keys(cursor, table_name, primary_key="id")

            # Determine columns to drop
            columns_to_drop = get_columns_to_drop(existing_columns, columns_new, 'id')
            drop_columns_sql = []
            if columns_to_drop:
                message = (f"Press [Y] to confirm to DROP columns '{', '.join(columns_to_drop)}' "
                           f"of table '{table_name}' [Y/N]:")
                if input(message).lower() != "y":
                    drop_columns_sql = generate_drop_columns_sql(type_id, table_name, columns_to_drop)

            # Generate SQL statements

            add_columns_sql = generate_add_columns_sql(table_name, columns_new, existing_columns)
            alter_columns_sql = generate_alter_columns_sql(table_name, columns_new, existing_columns)
            drop_fks_sql = generate_drop_foreign_keys_sql(table_name, existing_foreign_keys)
            add_fks_sql = generate_add_foreign_keys_sql(type_id, table_name, foreign_keys_new)

            # Combine all SQL statements
            all_statements = drop_columns_sql + add_columns_sql + alter_columns_sql + drop_fks_sql + add_fks_sql

            # Execute all statements
            execute_sql_statements(conn, type_id, all_statements)

        return 1
    except Exception as _err:
        print(f"FAILED {type_id = } {type(_err).__name__}: {_err}")
        return 0


# __________________________________________________________


def _create_trigger_on_update_operations_type_id_nnn(conn, type_id: int, table_name: str) -> int:
    try:
        trigger_name = f"on_update_{table_name}_trigger"

        with conn.cursor() as cur:
            cur.execute(
                "SELECT EXISTS (SELECT 1 FROM information_schema.triggers WHERE trigger_name = %s);",
                (trigger_name,)
            )
            is_exist = cur.fetchone()[0]

        if is_exist:
            return 1

        with conn.cursor() as cur:
            cur.execute(
                f"CREATE TRIGGER {trigger_name} AFTER UPDATE ON {table_name} "
                f"FOR EACH ROW EXECUTE FUNCTION function_add_operations_changes();")
            conn.commit()
        return 1
    except Exception as _err:
        print(f"FAILED {type_id = } {type(_err).__name__}: {_err}")
        return 0


def update_triggers_operations_type_id_nnn(config, operations_json: dict):
    """Create operation_nnn tables using auto generator."""
    cnxn, crsr = connect_to_db(config)
    create_count = 0
    trigger_count = 0
    operations_type_id_count = len(operations_json)
    for i, record in enumerate(operations_json):
        insert_txt = record['sql_query_formula']
        if not insert_txt:
            operations_type_id_count -= 1
            continue  # Don't create table if sql_query_formula is empty

        create_count += 1

        table_name = f"operations_type_id_{str(record['type_id'])}"

        try:
            drop_query = f"DROP TRIGGER on_update_{table_name}_trigger ON {table_name};"
            crsr.execute(drop_query)
            create_trigger_query_text = f"""
                CREATE TRIGGER trigger_on_update_{table_name}
                AFTER UPDATE ON {table_name}
                FOR EACH ROW
                EXECUTE FUNCTION function_add_operations_changes();"""
            crsr.execute(create_trigger_query_text)
            trigger_count += 1
        except OperationalError:
            pass

    if create_count == operations_type_id_count:
        print(f"Total created all {operations_type_id_count} 'operations_type_id_NNN' tables.")
    else:
        print(f"ERROR: failed to create {operations_type_id_count - create_count} 'operations_type_id_NNN' table(s).")

    if trigger_count == operations_type_id_count:
        print(f"Total created all {operations_type_id_count} TRIGGER's for update on 'operations_type_id_NNN' tables.")
    else:
        print(
            f"ERROR: failed to create {operations_type_id_count - trigger_count} "
            f"TRIGGER's for update on 'operations_type_id_NNN' tables.")

    close_connection(cnxn, crsr)


def _query_upsert_operations_library(conn, record) -> int:

    try:
        for key in ('process_fixed_row', 'labels', 'labels_regex', 'db_column_names', 'foreign_keys'):
            if not record[key]:
                record[key] = None

        record |= {
            'parent_type_id': record['parent_type_id'] if record['parent_type_id'] > 0 else None,
            # 'allow_copies': 'TRUE' if record['allow_copies'] else 'FALSE',
            # 'is_simulation': 'TRUE' if record['is_simulation'] else 'FALSE'
        }

        names = list(record)

        # Define the unique key column(s)
        unique_key = 'type_id'

        # Create the SQL query
        dynamic_query = sql.SQL(
            "INSERT INTO operations_library ({fields}) VALUES ({values})"
            "ON CONFLICT ({conflict_field}) DO UPDATE SET {update_fields}"
        ).format(
            fields=sql.SQL(', ').join(map(sql.Identifier, names)),
            values=sql.SQL(', ').join(map(sql.Placeholder, names)),
            conflict_field=sql.Identifier(unique_key),
            update_fields=sql.SQL(', ').join(
                sql.Composed([
                    sql.Identifier(field),
                    sql.SQL(" = EXCLUDED."),
                    sql.Identifier(field)
                ]) for field in names if field != unique_key
            )
        )

        with  conn.cursor() as cur:
            # a = cur.mogrify(dynamic_query, values)
            cur.execute(dynamic_query, record)
            conn.commit()
        return 1
    except Exception as _err:
        print(f"FAILED type_id = {record['type_id']} {type(_err).__name__}: {_err}")
        return 0


def _add_tooltip_image_into_operations_library(conn, type_id: int) -> int:
    file_buffer: io.BytesIO = create_image(type_id)
    try:
        tooltip_image_data = file_buffer.getvalue()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE operations_library SET tooltip_image = %s WHERE type_id = %s",
                (psycopg2.Binary(tooltip_image_data), type_id))
            conn.commit()
        return 1
    except Exception as _err:
        print(f"FAILED {type_id = } {type(_err).__name__}: {_err}")
        return 0


def _assert_tooltip_image_in_operations_library(conn, type_id, file_buffer: io.BytesIO) -> bool:
    cur = conn.cursor()

    try:
        cur.execute("SELECT tooltip_image FROM operations_library WHERE type_id = %s", (type_id,))
        result = cur.fetchone()
        if result is not None:
            if len(result) == 1:
                sql_tooltip_image_memory_view = result[0]
                if sql_tooltip_image_memory_view is not None:
                    buf = io.BytesIO(sql_tooltip_image_memory_view)
                    sql_tooltip_image_data = buf.read()
                    tooltip_image_data = file_buffer.getvalue()
                    assert tooltip_image_data == sql_tooltip_image_data
    except (OperationalError, DatabaseError, AssertionError, Exception):
        print(f"FAILED to assert Tooltip image for 'type_id' = {type_id}.")
        cur.close()
        return False

    return True


def insert_process_headers(cur):
    """Insert die types."""
    values = (
        'Process ID',  # process_id
        'Material',  # material_id
        'Heat No.',  # heat_no
        'Lot No.',  # lot_no
        'Finished size',  # finished_size
        'Customer standard',  # standard_customer
        'Standard of WST',  # standard_wst
        'Product condition',  # product_condition
        'Product surface',  # product_surface
        'Product diameter tolerance',  # product_diameter_tolerance
        'Product length tolerance',  # product_length_tolerance
        'Product curvature tolerance',  # product_curvature_tolerance
        'Stock size [mm]',  # stock_size
        'Stock weight [kg]',  # stock_weight
        'Stock No.',  # stock_no
        'Btt of material [C]',  # material_btt
        'Btt +/- tolerance [C]',  # material_btt_sym_tolerance
        'Remarks',  # remarks
        'Created date, time',  # created_at
        'User'  # user_id
    )
    sql_formula = (
        """
        INSERT INTO process_headers
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """
    )
    cur.execute(sql_formula, values)
