# print(f'__file__={__file__:<35} | __name__={__name__:<25} | __package__={str(__package__):<25}')
import sys
import time
import signal
import datetime
import os
import logging
import socket
import json
import select
from typing import LiteralString
from collections import defaultdict
import psycopg2.extensions
from psycopg2 import pool, OperationalError, DatabaseError

from forgelab.common.matlib import Material
from forgelab.common.library_sql_query import query_library
from forgelab.srv_pre.table_class import TableThread


LOGGER = logging.getLogger(__name__)
SENTRY = True


def signal_handler(signal_number, frame):
    """Signal Handler to process signal.SIGINT: CTRL + C"""
    global SENTRY
    SENTRY = False
    LOGGER.warning(
        f"The server received system signal: SignalNumber = '{str(signal_number)}', Frame = '{str(frame)}'."
        " The server cycle will break.")


class PreServer:
    def __init__(self):
        signal.signal(signal.SIGINT, signal_handler)  # register signal with handler
        self.connection = None
        self.config = None

    def start(self):

        while self.is_allowed_to_start_new_server():  # Infinite loop to restart server after crash

            try:
                self.server_instance()

            except Exception as _err:
                LOGGER.critical(f"Server instance was terminated du to unpredicted error and will be restarted: {_err}")
                time.sleep(5.0)

    def server_instance(self):

        self.init_server()

        workers = []
        while self.is_allowed_to_process_database_changes():

            ids = self.query_database_for_changes()

            if not ids:
                continue

            workers = [_w for _w in workers if _w.is_alive()]

            # Restart existing workers
            for _w in workers:
                operation_ids = ids.pop(_w.process_version_id, [])
                if operation_ids:
                    _w.stop(operation_ids)

            # Start new workers
            for _process_version_id, ids in ids.items():
                _w = TableThread(_process_version_id)
                _w.run()
                workers.append(_w)

    def init_server(self):

        try:
            root_dir = self.root_dir()
            data_dir = self.data_dir()

            self.config = {
                'is_initialization_successful': True,
                'db': self.load_config('database.json'),
                'server': self.load_config('server.json'),
                'triggers': self.load_config('triggers.json')}

            # self.init_connection_pool()

            self.add_host_name()
            self.add_ip_address()
            self.add_cpu_count()
            self.query_server_id()
            self.add_start_time()
            self.query_default_queue_simulation_server_id()

            self.config['server'] |= {
                'software_root_dir': root_dir,
                'data_files_dies': self.os_join_assert(data_dir, 'dies'),
                'data_files_materials': self.os_join_assert(data_dir, 'materials'),
                'data_files_operations': self.os_join_assert(data_dir, 'operations')}

            self.query_library()
            # self.config['lib']['materials']['class'] = self.import_materials_from_data_files()

            self.set_listen_to_database_notifications()
            self.print_server_info()

        except KeyError as _err:
            LOGGER.error(f"Failed initializing server with KeyError: {_err}")
        except Exception as _err:
            LOGGER.error(f"Failed initializing server with Exception: {_err}")
        else:
            LOGGER.info("Successfully initialized the server.")
            return

        if not self.config.pop('is_initialization_successful'):
            self.terminate_server_now()

    @staticmethod
    def terminate_server_now():
        LOGGER.critical("Terminate command received. Stopping 'forgelabPre' server...")
        sys.exit(1)

    @staticmethod
    def is_allowed_to_start_new_server() -> bool:
        """Returns True if server is allowed to run. Otherwise, returns False."""
        if SENTRY:
            LOGGER.info("New server instance will be started.")
            return True
        LOGGER.error("New server instance starting is forbidden. Restarting server is forbidden. Terminating the "
                     "server...")
        return False

    @staticmethod
    def is_allowed_to_process_database_changes() -> bool:
        """Returns True if server is allowed to run. Otherwise, returns False."""
        if not SENTRY:
            # LOGGER.info("Start new cycle of listening to database notifications.")
            LOGGER.error("Further listening to database notifications is forbidden. "
                         "The main server cycle is terminated. Finalizing the server instance...")
            return False
        return True

    def set_listen_to_database_notifications(self):
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute(f"LISTEN {self.config['server']['notify_channel']};")
        conn.commit()
        cur.close()
        # self.connection_put_back(conn)

    def init_connection_pool(self):
        """Receives database name. Make connection to it. Saves connection to self.connection."""
        timeout_sec = 1.0

        try:
            _db = self.config['db']
        except KeyError as _err:
            LOGGER.error(f"The key '{_err}' was not found in the 'self.param' dictionary.")
            self.terminate_server_now()  # Abort script
            return

        while True:
            try:
                conn_pool = psycopg2.pool.SimpleConnectionPool(
                    1, 20,
                    user=_db['user'], password=_db['pass'], host=_db['host'], database=_db['base'])

            except (OperationalError, DatabaseError) as _err:
                LOGGER.error(
                    f"Can't create connection pool. Wait for {timeout_sec} sec and try again. Database Error: {_err}")
                time.sleep(timeout_sec)

            except Exception as _err:
                LOGGER.error(f"Some uncategorized Error: {_err}")

            else:
                self.connection = conn_pool
                return

    def get_connection(self) -> psycopg2.extensions.connection | None:
        try:
            _db = self.config['db']
        except KeyError as _err:
            LOGGER.error(f"The key '{_err}' was not found in the 'self.param' dictionary.")
            self.terminate_server_now()  # Abort script
        else:
            while True:
                try:
                    if self.connection is None:
                        self.connection = psycopg2.connect(
                            user=_db['user'],
                            password=_db['pass'],
                            host=_db['host'],
                            database=_db['base'])
                    cur = self.connection.cursor()
                    cur.execute("SELECT 1;")
                    self.connection.commit()
                    cur.close()
                except (OperationalError, DatabaseError) as _err:
                    LOGGER.error(f"Failed to create connection. Wait then retry infinitely. Error: {_err}")
                    self.connection = None
                    time.sleep(0.2)
                except Exception as _err:
                    LOGGER.error(f"Some uncategorized Error: {_err}")
                    self.connection = None
                    time.sleep(0.2)
                else:
                    return self.connection

    @staticmethod
    def root_dir() -> str:
        return os.path.dirname(os.path.dirname(__file__))

    @staticmethod
    def data_dir() -> str:
        return os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')

    def os_join_assert(self, *args) -> LiteralString | str | bytes:
        """Receives '*.json' file name. If error, stops server."""
        try:
            _dir = os.path.join(*args)
            assert os.path.isdir(_dir), f"Can't find local directory '{_dir}'"
        except AssertionError as _err:
            LOGGER.critical(_err)
        except Exception as _err:
            LOGGER.critical(f"Some uncategorized Error: {_err}.")
        else:
            return _dir
        # Exception occurred
        self.terminate_server_now()

    # def connection_put_back(self, conn: psycopg2.extensions.connection):
    #     try:
    #         self.connection.putconn(conn)
    #     except OperationalError as _err:
    #         LOGGER.error(f"'OperationalError' while putting connection back to connection pool. Error: {_err}")
    #     except DatabaseError as _err:
    #         LOGGER.error(f"'DatabaseError' while putting connection back to connection pool. Error: {_err}")

    # def connection_pool_close_all(self):
    #     timeout_sec = 1.0
    #     while self.is_allowed_to_run:
    #         try:
    #             self.connection.closeall()
    #
    #         except KeyError as _err:
    #             LOGGER.error(f"The key '{_err}' was not found in the dictionary.")
    #             self.stop_server()
    #
    #         except OperationalError as _err:
    #             LOGGER.error(
    #                 "'OperationalError' while closing all connections of connection pool."
    #                 f" Wait for {timeout_sec} sec and try again infinitely. Error: {_err}")
    #             time.sleep(timeout_sec)
    #
    #         except DatabaseError as _err:
    #             LOGGER.error(
    #                 "'DatabaseError' while closing all connections of connection pool."
    #                 f" Trying to create connection pool again. Error: {_err}")
    #             self.init_connection_pool()
    #             return

    def load_config(self, filename) -> dict:
        """Receives '*.json' file name. Returns dictionary. If error, stops server."""
        config = {}
        try:
            abs_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', filename)
            with open(abs_path, 'r', encoding='utf-8') as stream:
                config = json.load(stream)

        except FileNotFoundError:
            LOGGER.error(f"ERROR: The configuration file '{filename}' was not found. Stopping server.")
            self.terminate_server_now()

        except OSError as exception:
            LOGGER.error(f"Some 'OSError': {exception.strerror} {exception.errno}.  Stopping server.")
            self.terminate_server_now()

        except json.JSONDecodeError:
            LOGGER.error(f"The configuration file '{filename}' contains invalid JSON. Stopping server.")
            self.terminate_server_now()

        except Exception as _err:
            LOGGER.error(f"Some uncategorized Error: {_err}. Stopping server.")
            self.terminate_server_now()

        return config

    def query_database_for_changes(self) -> defaultdict | None:

        conn = self.get_connection()

        if not self._is_ready_for_reading_notifications(conn):
            return

        if not self._is_notification(conn):
            return

        output = defaultdict(list)

        new_records = self._query_delete_operations_changes(conn)

        if new_records:
            LOGGER.info(f"Successfully popped {len(new_records)} records from 'operations_changes' table.")
            try:
                for _id, pvid, is_editable, preview_status, run_switch_status, simulation_status in new_records:
                    if not is_editable:
                        LOGGER.info(f"PVID[{pvid}] got notify ID {_id}, "
                                    f"but ignore it because 'process_versions.is_editable' = FALSE")
                        continue
                    # if preview_status != 'ok':
                    #     LOGGER.info(f"PVID[{pvid}] got notify ID {_id}, "
                    #                 f"but ignore it because 'process_versions.preview_status' <> 'ok' "
                    #                 f"(='{preview_status}')")
                    #     continue
                    if run_switch_status:
                        LOGGER.info(f"PVID[{pvid}] got notify ID {_id}, "
                                    f"but ignore it because 'process_versions.run_switch_status' = TRUE")
                        continue
                    if simulation_status != 'stop':
                        LOGGER.info(f"PVID[{pvid}] got notify ID {_id}, "
                                    f"but ignore it because 'process_versions.simulation_status' <> 'stop' "
                                    f"(='{simulation_status}')")
                        continue

                    LOGGER.info(f"PVID[{pvid}] got notify ID {_id} successfully.")

                    output[pvid].append(_id)

            except Exception as _err:
                LOGGER.error(f"Some error: {_err}")
        return output

    @staticmethod
    def _query_delete_operations_changes(conn: psycopg2.extensions.connection
                                         ) -> list[tuple[int, int, bool, str, bool, str]] | None:
        try:
            cur = conn.cursor()
            # cur.execute("DELETE FROM operations_changes RETURNING id, process_version_id;")
            cur.execute("""
WITH deleted_rows AS (
    DELETE FROM operations_changes
    RETURNING id, process_version_id
)
SELECT 
    dr.id,
    dr.process_version_id,
    pv.is_editable,
    pv.preview_status,
    pv.run_switch_status,
    pv.simulation_status
FROM 
    deleted_rows dr
JOIN 
    process_versions pv ON dr.process_version_id = pv.process_version_id;""")
            new_records = cur.fetchall()
            conn.commit()
            cur.close()
        except OperationalError as _err:
            LOGGER.error(f"'OperationalError': {_err}")
        except DatabaseError as _err:
            LOGGER.error(f"'DatabaseError': {_err}")
        except Exception as _err:
            LOGGER.error(f"Some error: {_err}")
        else:
            return new_records
        raise RuntimeError("Error in '_query_delete_operations_changes'")

    def _is_notification(self, conn: psycopg2.extensions.connection) -> bool:
        is_notify = False
        try:
            conn.poll()
            while conn.notifies:
                if conn.notifies.pop(0).channel == self.config['server']['notify_channel']:
                    is_notify = True
                    LOGGER.info(f"Notification received on channel '{self.config['server']['notify_channel']}'.")
                    break
        except OperationalError as _err:
            LOGGER.error(f"'OperationalError': {_err}")
        except DatabaseError as _err:
            LOGGER.error(f"'DatabaseError': {_err}")
        except Exception as _err:
            LOGGER.error(f"Some error: {_err}")
        return is_notify

    def _is_ready_for_reading_notifications(self, conn: psycopg2.extensions.connection) -> bool:
        notify_timeout = self.config['server']['notify_timeout']
        is_ready_for_reading = False
        try:
            is_ready_for_reading, _, _ = select.select([conn], [], [], notify_timeout)
            conn.commit()
        except OperationalError as _err:
            LOGGER.error(f"'OperationalError': {_err}")
        except DatabaseError as _err:
            LOGGER.error(f"'DatabaseError': {_err}")
        except Exception as _err:
            LOGGER.error(f"Some error: {_err}")
        # True if data in connection socket is ready
        return is_ready_for_reading

    def add_host_name(self):
        """
        Retrieve the hostname of the computer.
    
        This function uses the built-in `socket` library to fetch the hostname of the computer.
        It is compatible with Windows 10, Windows 11, Linux, and macOS.
    
        Returns
        -------
        str
            The hostname of the computer.
        """
        try:
            dns_name = socket.getfqdn()
            parts = dns_name.split('.', 1)
            hostname = parts[0]
            if hostname[0].isdigit():  # this is IP address
                domain = ''
            else:
                domain = parts[1] if len(parts) > 1 else ''
            self.config['server']['hostname'] = hostname
            self.config['server']['name'] = hostname
            self.config['server']['dns_domain'] = domain
        except Exception as e:
            LOGGER.error(f"Failed to fetch hostname. Error: {e}")
            self.config['is_initialization_successful'] |= False

    def add_ip_address(self):
        """
        Retrieve the ip address of the computer.
        Saves ip address to self.param['server']['ip'].
        """
        try:
            _ip = socket.gethostbyname(socket.gethostname())
            self.config['server']['ip'] = _ip
        except Exception as e:
            LOGGER.error(f"Failed to fetch ip address. Error: {e}")
            self.config['is_initialization_successful'] |= False

    def add_cpu_count(self):
        try:
            self.config['server']['cpu_number'] = os.cpu_count()

        except Exception as _err:
            LOGGER.error(f"Failed to fetch CPU count. Error: {_err}")
            self.config['is_initialization_successful'] |= False

    def query_server_id(self):
        """
        Receives server name (defined in 'config.json').
        Queries 'servers' table for old server 'id'.
        Otherwise, insert a new one.
        Returns 'id' of the server.
        """

        try:
            _srv = self.config['server']
            _hostname = _srv['hostname']
            _name = _srv['name']
            _dns_domain = _srv['dns_domain']
            _ip = _srv['ip']
            _type = _srv['type']
            _version = _srv['version']
        except KeyError as _err:
            LOGGER.error(f"The key '{_err}' was not found in the 'self.param' dictionary.")
            self.terminate_server_now()  # Abort script
            return

        conn = self.get_connection()

        _id, _database_ip, _database_version = self._query_existing_server_id(conn, _type, _hostname, _name)
        if _id is None:
            _id = self._insert_new_server(conn, _type, _hostname, _name, _dns_domain, _ip, _version)
        elif _database_ip != _ip or _database_version != _version:
            _id = self._update_server_record(conn, _type, _hostname, _name, _dns_domain, _ip, _version)

        # self.connection_put_back(conn)

        self.config['server']['id'] = _id

    def query_default_queue_simulation_server_id(self):
        """
        Queries 'servers' table for server's 'id' where 'type'='simulation' and 'name'='QUEUE'.
        Returns 'id' of the server.
        """
        case_msg = f"occurred when trying to select server's 'id' where type = 'simulation' AND name = 'QUEUE'. Error:"
        conn = self.get_connection()
        try:
            query = "SELECT id FROM servers WHERE type = 'simulation' AND name = 'QUEUE' LIMIT 1;"
            cur = conn.cursor()
            cur.execute(query)
            _id = cur.fetchone()[0]
            conn.commit()
            cur.close()
        except OperationalError as _errs:
            LOGGER.error(f"'OperationalError' {case_msg} {_errs}")
        except DatabaseError as _errs:
            LOGGER.error(f"'DatabaseError' {case_msg} {_errs}")
        except Exception as _errs:
            LOGGER.error(f"Some error {case_msg} {_errs}")
        else:
            self.config['server']['default_queue_simulation_server_id'] = _id
            return
        self.config['is_initialization_successful'] = None

    def _query_existing_server_id(
            self, conn, server_type: str, hostname: str, name: str
    ) -> tuple[int | None, str | None, str | None]:
        _id, _database_ip, _database_version = None, None, None

        try:
            query = ("SELECT id, ip, version FROM servers WHERE type = %s::server_type_enum AND hostname = %s AND "
                     "name = %s LIMIT 1;")
            cur = conn.cursor()
            cur.execute(query, (server_type, hostname, name,))
            query_result = cur.fetchone()
            conn.commit()
            cur.close()
            if query_result:
                _id, _database_ip, _database_version = query_result[0], query_result[1], query_result[2]
        except DatabaseError as _err:
            LOGGER.error(f"Failed to query the DB for existing record: {_err}")
            self.config['is_initialization_successful'] |= False

        return _id, _database_ip, _database_version

    def _insert_new_server(
            self, conn: psycopg2.extensions.connection, _type, _hostname, _name, _dns_domain, _ip, _version
    ) -> int | None:

        try:
            query = ("INSERT INTO public.servers (type, hostname, name, dns_domain, ip, version) "
                     "VALUES (%s::server_type_enum, %s, %s, %s, %s, %s) RETURNING id;")
            cur = conn.cursor()
            cur.execute(query, (_type, _hostname, _name, _dns_domain, _ip, _version))
            _id = cur.fetchone()[0]
            conn.commit()
            cur.close()
        except OperationalError as _err:
            LOGGER.error(f"Failed to register server with 'OperationalError' : {_err}")
        except DatabaseError as _err:
            LOGGER.error(f"Failed to register server with 'DatabaseError': {_err}")
        except Exception as _err:
            LOGGER.error(f"Some error during registration of the server in the DB: {_err}")
        else:
            return _id
        self.config['is_initialization_successful'] |= False

    def _update_server_record(
            self, conn: psycopg2.extensions.connection, _type, _hostname, _name, _dns_domain, _ip, _version
    ) -> int | None:

        _id = None

        try:
            query = ("UPDATE servers "
                     "SET ip = %s, version = %s, name = %s, dns_domain = %s, time_updated = CURRENT_TIMESTAMP "
                     "WHERE type = %s::server_type_enum AND hostname = %s RETURNING id;")
            cur = conn.cursor()
            cur.execute(query, (_ip, _version, _name, _dns_domain, _type, _hostname))
            _id = cur.fetchone()[0]
            conn.commit()
            cur.close()
        except OperationalError as _err:
            LOGGER.error(f"Failed to update the DB for existing record with 'OperationalError': {_err}")
        except DatabaseError as _err:
            LOGGER.error(f"Failed to update the DB for existing record with 'DatabaseError': {_err}")
        except Exception as _err:
            LOGGER.error(f"Some error during update of the server record in the DB: {_err}")
        else:
            return _id
        self.config['is_initialization_successful'] |= False

    def add_start_time(self):
        try:
            _start_time = datetime.datetime.now()
            self.config['server']['start_time'] = _start_time
        except Exception as _err:
            LOGGER.error(f"Failed to fetch start time. Error: {_err}")
            self.config['is_initialization_successful'] |= False

    def query_library(self):
        try:
            conn = self.get_connection()
            query_library(self.config)
            conn.commit()
            # self.connection_put_back(conn)
        except Exception as _err:
            LOGGER.error(f"Failed to query library with Exception: {_err}")
            self.config['is_initialization_successful'] |= False

    def import_materials_from_data_files(self):
        classes = {}
        for material_id in self.config['lib']['materials']['material_id'].keys():
            mat_dir = self.config['server']['data_files_materials']
            mat_file = self.config['lib']['materials']['material_path'][material_id]
            if mat_file:
                mat_abs_path = os.path.join(mat_dir, mat_file)
                assert os.path.exists(mat_abs_path), f"File '{mat_abs_path}' not found"
                material = Material(mat_abs_path)
            else:
                material = None
            classes[material_id] = material
        return classes

    def print_server_info(self):

        _info = {}
        _msg = []

        try:
            _info = {
                'Hostname': self.config['server']['hostname'],
                'Domain name': self.config['server']['dns_domain'],
                'IP address': self.config['server']['ip'],
                'Type': self.config['server']['type'],
                'CPU count': str(self.config['server']['cpu_number']),
                'Server ID': str(self.config['server']['id']),
                # 'Simulation Dir': self.param['server']['projects_dir_local'],
                # 'Simulation Network Dir': self.param['server']['projects_dir_public'],
            }

            title = ' SERVER INFO '
            spaces_around = 4
            separator = ': '
            max_key_len = max([len(key) for key in _info.keys()]) + spaces_around
            max_value_len = max([len(value) for value in _info.values()]) + spaces_around

            full_len = 2 + len(separator) + max_key_len + max_value_len

            first_line_left = (full_len - len(title) - 2) // 2
            first_line_right = full_len - len(title) - first_line_left - 2

            _msg = [
                f"|{'*' * first_line_left}{title}{'*' * first_line_right}|",
                f"|{' ' * (full_len - 2)}|"
            ]
            for key, value in _info.items():
                _msg.append("|{0:>{max_key_len}}: {1:<{max_value_len}}|".format(
                    key, value, max_key_len=max_key_len, max_value_len=max_value_len))
            last_rows = [
                f"|{' ' * (full_len - 2)}|",
                f"|{'*' * (full_len - 2)}|"
            ]
            _msg.extend(last_rows)

            for line in _msg:
                LOGGER.info(line)

        except (KeyError, Exception) as _err:
            LOGGER.error(f"FAILED: Parameters are lost or other problem. Error: {_err}")
            self.config['is_initialization_successful'] |= False
