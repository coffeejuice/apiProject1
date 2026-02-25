import random
import socket

import psycopg2
import psycopg2.extensions

# from .create_operations import USER_SURNAMES, USER_NAMES
from forgelab.sql_setup.hash_password import hash_password, verify_password


def update_login(login: str, values: list) -> str:
    logins = [value[0] for value in values]
    new_login = login
    i = 1
    while new_login in logins:
        new_login = login + str(i)
        i += 1
    return new_login


def insert_servers(_conn: psycopg2.extensions.connection, sql_param: dict):
    """Insert NAS server into 'servers' table in postgresql."""
    for server in sql_param['servers'].values():
        if server['type'] == 'sql':
            add_ip_hostname_dns_name_for_sql_server(sql_param, server)
        columns_list, foreign_keys_set = query_table_columns(_conn, 'servers')
        query_columns = list(set(columns_list).intersection(set(server.keys())))
        query_values = [server[_column_name] for _column_name in query_columns]
        query_count = len(query_columns)
        cur = _conn.cursor()
        formula = f"INSERT INTO servers ({', '.join(query_columns)}) VALUES ({', '.join(['%s'] * query_count)});"
        cur.execute(formula, query_values)
        _conn.commit()
        cur.close()


def insert_servers_versions_compatibility(_conn: psycopg2.extensions.connection, sql_param: dict):
    """Insert NAS server into 'servers' table in postgresql."""
    for server in sql_param['servers'].values():

        type_a, version_a = server['type'], server['version']

        if not version_a:
            return

        for type_b, version_b in server['servers_versions_compatibility'].items():

            if not version_b:
                continue

            cur = _conn.cursor()
            formula = f"""
                INSERT INTO servers_versions_compatibility (type_a, version_a, type_b, version_b) 
                VALUES (%s, %s, %s, %s) 
                ON CONFLICT (type_a, version_a, type_b, version_b) DO NOTHING;"""
            cur.execute(formula, (type_a, version_a, type_b, version_b,))
            _conn.commit()
            cur.close()


def add_ip_hostname_dns_name_for_sql_server(sql_param, server):
    _ip = sql_param['db']['host']
    hostname, domain = get_hostname_and_domain_from_ip_address(_ip)
    server['ip'] = _ip
    server['hostname'] = hostname
    server['name'] = hostname
    server['dns_domain'] = domain


def assert_config_servers(sql_param):
    assert 'servers' in sql_param.keys(), "FAILED: Can't find 'servers' in config"
    assert len(sql_param['servers']) > 0, \
        "FAILED: Can't find any server in config to insert SQL and NAS configuration to 'servers' table."
    sql_servers_count = 0
    nas_servers_count = 0
    for server in sql_param['servers'].values():
        assert 'type' in server.keys(), "FAILED: Can't find 'type' in server config"
        if server['type'] == 'sql':
            sql_servers_count += 1
        if server['type'] == 'file_server':
            nas_servers_count += 1
    assert sql_servers_count != 0, ("FAILED: Can't find SQL server in config to insert SQL configuration "
                                    "to 'servers' table.")
    assert sql_servers_count < 2, "FAILED: More than one SQL server found in config. Only one SQL server is allowed."
    assert nas_servers_count != 0, ("FAILED: Can't find NAS server in config to insert NAS configuration "
                                    "to 'servers' table.")
    assert nas_servers_count < 2, "FAILED: More than one NAS server found in config. Only one NAS server is allowed."


def get_hostname_and_domain_from_ip_address(ip_address: str) -> tuple[str, str]:
    """
    This function returns the fully qualified domain name (FQDN) of a remote system given its IP address or hostname.
    """

    print(
        f"INFO: Requesting a remote PC with IP address '{ip_address}' "
        "for resolving IP address to the DNS name. Waiting for remote PC answer...")

    try:
        # This will try to resolve the remote host's FQDN
        dns_name = socket.getfqdn(ip_address)

    except Exception as _err:
        raise ConnectionError(f"FAILED: Could not resolve IP address '{ip_address}' to the DNS name. ERROR: {_err}")

    if not dns_name:
        raise ConnectionError(f"FAILED: Could not resolve IP address '{ip_address}' to the DNS name.")

    if ip_address == dns_name:
        print(
            "WARNING: Remote PC returned IP address instead of DNS name. "
            f"This IP address '{ip_address}' will be used as 'hostname' instead of NetBIOS or DNS name of the PC.")
        print("WARNING: Domain name is empty.")
        return ip_address, ''

    parts = dns_name.split('.', 1)
    hostname = parts[0]

    if hostname[0].isdigit():
        print(
            f"WARNING: Remote computer with IP address '{ip_address}' returned this IP address as Hostname. "
            "Domain name is empty.")
        return ip_address, ''

    domain = parts[1] if len(parts) > 1 else ''
    return hostname, domain


def query_table_columns(
        conn: psycopg2.extensions.connection, table_name: str, excluded_columns=None) -> tuple[list, set]:

    if excluded_columns is None:
        excluded_columns = []

    cur = conn.cursor()

    query_formula = f"""
        SELECT column_name, is_nullable
        FROM information_schema.columns
        WHERE table_name = '{table_name}';
    """

    # Execute the SQL query
    cur.execute(query_formula)
    rows = cur.fetchall()

    column_names, foreign_keys = [], []
    # unique_data_types = set()

    for column_name, nullable in rows:

        if column_name in excluded_columns:
            continue

        if nullable != 'YES':
            foreign_keys.append(column_name)

        column_names.append(column_name)

    return column_names, set(foreign_keys)


def postgresql_add_test_user(cur):
    """Add users to 'accounts' table in postgresql."""
    users_list = [
        ['no_supervisor', 'No supervisor', ''],
        ['admin', 'Administrator', '']
    ]

    def get_hashed_password(_login):
        _hashed_password = hash_password(_login)
        if verify_password(_login, _hashed_password):
            return psycopg2.Binary(_hashed_password)
        return ''

    # def add_random_users():
    #     for surname in USER_SURNAMES:
    #         for login in USER_NAMES:
    #             full_name = ' '.join((surname, login, ))
    #             login = f"{surname.lower()}{login.lower()}"
    #             login = update_login(login, users_list)
    #             users_list.append([login, full_name, ''])

    def add_hashed_passwords_to_users_list():
        for _i in range(len(users_list)):
            users_list[_i][2] = get_hashed_password(users_list[_i][0])

    def print_users_list():
        for _i in range(len(users_list)):
            print(
                f"Full name: {users_list[_i][1]:<20} | "
                f"Login: {users_list[_i][0]:<20} | "
                f"Password: {str(users_list[_i][2])}")

    def query_insert_users():
        formula = "INSERT INTO accounts (login, full_name, password_hashed) VALUES (%s, %s, %s);"
        cur.executemany(formula, users_list)

    def query_select_users():
        cur.execute("SELECT user_id FROM accounts;")
        return [i[0] for i in cur.fetchall()]

    # add_random_users()
    add_hashed_passwords_to_users_list()
    print_users_list()
    query_insert_users()
    user_id_all = query_select_users()
    print(f"Total inserted {len(user_id_all)} users")


def postgresql_add_test_process(cur):
    """Add materials to materials table in postgresql 'forgelab_db' database."""

    cur.execute("SELECT user_id FROM accounts WHERE user_id > 1;")
    user_id_all = [i[0] for i in cur.fetchall()]

    cur.execute("SELECT material_id FROM material WHERE material_id > 1;")
    material_id_all = [i[0] for i in cur.fetchall()]

    formula = (
        """
        INSERT INTO process(
            material_id, heat_no, lot_no,
            finished_size, standard_customer, standard_wst,
            product_condition, product_surface, product_diameter_tolerance,
            product_length_tolerance, product_curvature_tolerance, stock_size,
            stock_weight, stock_no, material_btt,
            material_btt_sym_tolerance, remarks, user_id)
        VALUES (
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s);
        """
    )
    values = []
    for _ in range(3):
        values.append(
            (
                random.choice(material_id_all), f"{random.randint(510, 550)}-{random.randint(10_000, 99_999)}",
                f"{random.randint(10_000, 99_999)}",
                f"diam {150 + 10 * random.randrange(35)}", 'Customer standard 1', 'WST standard 1',
                'R', 'Machined', '+/- 3 mm',
                '+/- 10 mm', '+/- 5 mm/m', f"diam {500 + 100 * random.randrange(3)}",
                500 + 100 * random.randrange(3), 'No. 1', 995,
                5, 'Remarks', random.choice(user_id_all),
            )
        )
    cur.executemany(formula, values)


def postgresql_add_test_process_versions(cur):
    """Add materials to materials table in postgresql 'forgelab_db' database."""

    cur.execute("SELECT process_id FROM process;")
    process_id_all = [i[0] for i in cur.fetchall()]

    query_text = "INSERT INTO process_versions(process_id, name) VALUES (%s, %s);"

    values = []
    for process_id in process_id_all:
        for process_version_id in range(1, 3):
            _process_name = f"Process #{process_id}, version {process_version_id}"
            _set = (process_id, _process_name,)
            values.append(_set)
    cur.executemany(query_text, values)
    # check if it worked
    cur.execute("SELECT * FROM process_versions;")
    print(f'Total inserted {len(cur.fetchall())} process versions')
