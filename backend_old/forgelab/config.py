from __future__ import annotations

import ctypes.wintypes
import json
import logging
import os
import shutil
import socket
import time
from datetime import datetime
import psutil
import psycopg2.extensions
import smbclient
from psycopg2 import sql, pool

from forgelab.common.fluent_bit_logger import set_fluent_bit_logger
from forgelab.common.library_sql_query import query_library


LOGGER = logging.getLogger(__name__)


class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


# @dataclass
class Config(metaclass=Singleton):

    # connection: psycopg2.extensions.connection
    _thread_pool: psycopg2.pool.ThreadedConnectionPool
    is_error: bool
    db: dict
    server: dict
    services: dict
    lib: dict
    nas: dict

    def initialize(self):
        try:
            self.is_error = False

            _root_dir = self.root_dir()
            _data_dir = os.path.join(_root_dir, 'data')

            _cnf = self._load_config(_data_dir, 'config.json')
            self.db = _cnf['db']
            self.server = _cnf['server']
            self.services = _cnf['services']

            set_fluent_bit_logger(_cnf['logger'])

            min_connections_count = (1 + sum([val['max_threads_count'] for val in self.services.values()]))

            self._thread_pool = pool.ThreadedConnectionPool(
                minconn=min_connections_count,
                maxconn=max(20, min_connections_count),
                user=self.db['user'],
                password=self.db['pass'],
                host=self.db['host'],
                port=self.db['port'],
                dbname=self.db['base'])

            _hostname, _dns_domain = self._add_host_name()
            _ip = self._add_ip_address()
            _type = 'simulation'
            _version = self.server['version']
            _id = self._query_server_id(_hostname, _dns_domain, _ip, _type, _version)
            cpu_count_available, cpu_count = self._add_cpu_count(self.server['cpu_count_deform_license_max_limit'])

            self.server |= {
                'hostname': _hostname,
                'name': _hostname,
                'dns_domain': _dns_domain,
                'ip': _ip,
                'id': _id,
                'ram_free_size_gb': self._add_ram_free_size_gb(),
                'hdd_free_size_gb': self._add_hdd_free_size_gb(),
                'cpu_count_available': cpu_count_available,
                'cpu_count': cpu_count,
                'default_queue_simulation_server_id': self.query_default_queue_simulation_server_id(),
                'start_time': datetime.now(),
                'time_started': datetime.now(),
                'notify_channel_hash': {vals['notify_channel']: service for service, vals in self.services.items()},
                'local_dir': self._get_projects_dir_local(),
                # 'public_dir': get_projects_dir_public(),
                'software_root_dir': _root_dir,
                'data_files_dies': self._os_join_assert(_data_dir, 'dies'),
                'data_files_materials': self._os_join_assert(_data_dir, 'materials'),
                'data_files_operations': self._os_join_assert(_data_dir, 'operations'),
                'data_files_ppt': self._os_join_assert(_data_dir, 'ppt')}

            self.lib = self._query_library()
            self.nas = self._query_parameters_register_and_test_remote_file_server()

            self._test_smb_path_create_and_delete_test_dir(self.nas['absolute_path'])
            self._permanently_register_smb_connection()

            # config.lib['materials']['class'] = _import_materials_from_data_files()
            # check_local_vs_public_dirs()

            # self._set_listen_to_database_notifications()
            for service_name in ('simulation', ):
                self._query_update_servers(_id, service_name)

            self._print_server_info()

        except Exception as _err:
            LOGGER.error(f"{type(_err).__name__}: {_err}")
            raise

    @staticmethod
    def root_dir() -> str:
        return os.path.dirname(__file__)

    @staticmethod
    def _load_config(data_dir: str, filename: str) -> dict:
        """Receives '*.json' file name. Returns dictionary. If error, stops server."""
        try:
            abs_path = os.path.join(data_dir, 'config', filename)
        except Exception as _err:
            LOGGER.error(f"{type(_err).__name__}: {_err}")
            raise
        try:
            with open(abs_path, 'r', encoding='utf-8') as stream:
                _config = json.load(stream)
                assert _config, f"Failed loading config file '{abs_path}'."
            return _config

        except Exception as _err:
            LOGGER.error(f"{type(_err).__name__}: {_err}")
            raise RuntimeError(f"Failed loading config file '{abs_path}'.")

    @staticmethod
    def _add_host_name() -> [str, str]:
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
            if parts[0][0].isdigit():  # this is IP address
                hostname = dns_name
                domain = ''
            elif len(parts) > 1:
                hostname = parts[0]
                domain = parts[1]
            else:
                hostname = parts[0]
                domain = ''
            return hostname, domain

        except Exception as _err:
            LOGGER.error(f"{type(_err).__name__}: {_err}")
            raise RuntimeError("Failed to fetch server's hostname and domain name.")

    @staticmethod
    def _add_ip_address() -> str:
        """
        Retrieve the ip address of the computer.
        Saves ip address to config.server['ip'].
        """
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception as _err:
            LOGGER.error(f"{type(_err).__name__}: {_err}")
            raise

    @staticmethod
    def _add_ram_free_size_gb() -> float:
        try:
            available_ram_bytes = psutil.virtual_memory().available
            return available_ram_bytes / 1073741824  # bytes to GB

        except Exception as _err:
            LOGGER.error(f"{type(_err).__name__}: {_err}")
            raise RuntimeError("Failed ot fetch available RAM memory size.")

    @staticmethod
    def _add_hdd_free_size_gb() -> float:
        try:
            _, _, free = shutil.disk_usage(os.path.curdir)
            return free / 1073741824  # bytes to GB

        except Exception as _err:
            LOGGER.error(f"{type(_err).__name__}: {_err}")
            raise RuntimeError(f"Failed to fetch HDD available size.")

    @staticmethod
    def _add_cpu_count(cpu_count_limit: int) -> [int, int]:
        try:
            cpu_count_available = os.cpu_count()
            cpu_count = min(cpu_count_limit, cpu_count_available)
            return cpu_count_available, cpu_count

        except Exception as _err:
            LOGGER.error(f"{type(_err).__name__}: {_err}")
            raise RuntimeError("Failed to fetch CPU count of the PC.")

    def get_connection(self) -> psycopg2.extensions.connection:
        sleep_time = 0.1
        while sleep_time < 300.0:
            try:
                connection = self._thread_pool.getconn()
                assert connection, "Failed to get connection from Threaded Connection Pool."
                return connection

            except Exception as _err:
                LOGGER.error(f"{type(_err).__name__}: {_err}")
                raise RuntimeError("Failed to get connection from Threaded Connection Pool.")
            finally:
                time.sleep(sleep_time)
                sleep_time *= 2

    def put_connection(self, connection: psycopg2.extensions.connection):
        try:
            assert isinstance(connection, psycopg2.extensions.connection), (
                f"Connection has wrong type = '{type(connection)}', but it must be type "
                f"'psycopg2.extensions.connection'.")
            self._thread_pool.putconn(connection)
        except Exception as _err:
            LOGGER.error(f"{type(_err).__name__}: {_err}")
            raise

    def _query_server_id(self, _hostname: str, _dns_domain: str, _ip: str, _type: str, _version: str) -> int:
        """
        Receives server name (defined in 'triggers.json').
        Queries 'servers' table for old server 'id'.
        Otherwise, insert a new one.
        Returns 'id' of the server.
        """

        try:
            _id, _database_ip, _database_version = self._query_existing_server_id(_type, _hostname)
            if _id is None:
                _id = self._insert_new_server(_type, _hostname, _hostname, _dns_domain, _ip, _version)
            elif _database_ip != _ip or _database_version != _version:
                _id = self._update_server_record(_type, _hostname, _hostname, _dns_domain, _ip, _version)

            assert isinstance(_id, int), f"Server ID must be integer, but has type '{type(_id)}' and value '{str(_id)}'"
            return _id

        except Exception as _err:
            LOGGER.error(f"{type(_err).__name__}: {_err}")
            raise RuntimeError(f"Can't query Server 'id' in SQL for a PC with Hostname='{_hostname}': {_err}")

    def _query_existing_server_id(self, server_type: str, hostname: str) -> tuple[int, str, str]:
        conn = self.get_connection()
        try:
            query = "SELECT id, ip, version FROM servers WHERE type = %s::server_type_enum AND hostname = %s LIMIT 1;"
            cur = conn.cursor()
            cur.execute(query, (server_type, hostname,))
            query_result = cur.fetchone()
            conn.commit()
            cur.close()

            if query_result:
                _id, _database_ip, _database_version = query_result[0], query_result[1], query_result[2]
            else:
                _id, _database_ip, _database_version = None, None, None
            return _id, _database_ip, _database_version
        except Exception as _err:
            LOGGER.error(f"{type(_err).__name__}: {_err}")
            raise RuntimeError(
                f"Failed to query existing record for a server with type = '{server_type}' and "
                f"host name = '{hostname}'.")
        finally:
            self.put_connection(conn)

    def query_default_queue_simulation_server_id(self) -> int:
        """
        Queries 'servers' table for server's 'id' where 'type'='simulation' and 'name'='QUEUE'.
        Returns 'id' of the server.
        """
        conn = self.get_connection()
        try:
            query = "SELECT id FROM servers WHERE type = 'simulation' AND name = 'QUEUE' LIMIT 1;"
            cur = conn.cursor()
            cur.execute(query)
            _id = cur.fetchone()[0]
            conn.commit()
            cur.close()

            assert isinstance(_id, int), "SQL returned 'servers.id' value, but it is not integer"
            return _id

        except Exception as _err:
            LOGGER.error(f"{type(_err).__name__}: {_err}")
            raise RuntimeError("Failed to select server's 'id' where type = 'simulation' AND name = 'QUEUE'.")
        finally:
            self.put_connection(conn)

    def _get_projects_dir_local(self) -> str:
        """Receives '*.json' file name. If error, stops server."""
        try:
            dir_id = 28  # [LOCALAPPDATA] A typical path is C:\Users\username\AppData\Local
            type_current = 0  # Get current, not default value
            buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
            ctypes.windll.shell32.SHGetFolderPathW(None, dir_id, None, type_current, buf)
            system_dir = buf.value
            project_dir_name: str = self.server['projects_dir']
            dir_local = os.path.join(system_dir, project_dir_name)
            if not os.path.exists(dir_local):
                os.makedirs(dir_local)
            assert os.path.isdir(dir_local), f"Can't find local simulation project directory '{dir_local}'"

            return dir_local

        except Exception as _err:
            LOGGER.error(f"{type(_err).__name__}: {_err}")
            raise

    @staticmethod
    def _os_join_assert(*args) -> str:
        """Receives '*.json' file name. If error, stops server."""
        try:
            assert args
            for _s in args:
                assert isinstance(_s, str)
            _l: list[str] = list(args)
            _dir = os.path.normpath(_l.pop(0))
            while _l:
                _dir = os.path.join(_dir, _l.pop(0))
            assert os.path.isdir(_dir), f"Path points to non existing directory '{_dir}'"
            return _dir
        except Exception as _err:
            LOGGER.error(f"{type(_err).__name__}: {_err}")
            raise

    def _query_library(self) -> dict:
        conn = self.get_connection()
        try:
            conn.autocommit = True
            _lib = query_library(conn, self.server['data_files_materials'])
            conn.autocommit = False
            return _lib

        except Exception as _err:
            LOGGER.error(f"{type(_err).__name__}: {_err}")
            raise
        finally:
            conn.autocommit = False
            self.put_connection(conn)

    def _query_parameters_register_and_test_remote_file_server(self) -> dict:
        """
        Call 'query_nas_config()' function for getting 'dns_domain', 'hostname', 'ip', 'public_dir' of the File Server.
        Try to use DNS domain name and hostname first to generate full DNS network name of the File Server.
        Otherwise, use IP address of the File Server.
        Finally, generate absolute network path to the File Server's public directory.
        Check if the network directory exists and accessible.
        Returns the absolute network path to the NAS public directory if successful. Otherwise, returns empty string.
        """

        columns = ('dns_domain', 'hostname', 'ip', 'public_dir', 'login_name', 'login_password')
        query = "SELECT {} FROM servers WHERE type = 'file_server' ORDER BY time_started ASC LIMIT 1;"

        conn = self.get_connection()

        try:
            cur = conn.cursor()
            sql_query = sql.SQL(query).format(sql.SQL(', ').join(map(sql.Identifier, columns)))
            cur.execute(sql_query)
            result = cur.fetchone()
            conn.commit()
            cur.close()

            assert result, \
                f"Query result is empty for SELECT {', '.join(columns)} FROM servers WHERE type = 'file_server'"

            values = {key: val for key, val in zip(columns, result)}
            values['absolute_path'] = fr"\\{values['ip']}\{values['public_dir']}"

            return values

        except Exception as _err:
            LOGGER.error(f"{type(_err).__name__}: {_err}")
            raise
        finally:
            self.put_connection(conn)

    def _test_smb_path_create_and_delete_test_dir(self, absolute_smb_path: str):
        """
        Check if an SMB network path is accessible.
        :return: True if accessible, False otherwise.
        """
        try:
            test_dir = f"simulation_test_{self.server['id']}"
            file_server_test_dir = os.path.join(absolute_smb_path, test_dir)
        except Exception as _err:
            LOGGER.error(f"{type(_err).__name__}: {_err}")
            raise

        timestamp = time.monotonic()
        try:
            smbclient.mkdir(file_server_test_dir)
            smbclient.rmdir(file_server_test_dir)

        except Exception as _err:
            LOGGER.error(f"{type(_err).__name__}: {_err}")
            raise RuntimeError(
                f"Failed ot make create and delete a temporary directory '{file_server_test_dir}'. "
                f"Test duration = {time.monotonic() - timestamp:4f} sec")

    def _permanently_register_smb_connection(self):
        try:
            server = self.nas['ip']
        except Exception as _err:
            LOGGER.error(f"{type(_err).__name__}: {_err}")
            raise
        timestamp = time.monotonic()
        try:
            smbclient.ClientConfig(username=self.nas['login_name'], password=self.nas['login_password'])
            smbclient.register_session(self.nas['ip'])
        except Exception as _err:
            LOGGER.error(f"{type(_err).__name__}: {_err}")
            raise RuntimeError(
                f"Failed to permanently register credentials or establish a SMB session to remote SMB "
                f"file server '{server}'. Duration = {time.monotonic() - timestamp:4f} sec")


    # def _set_listen_to_database_notifications(self):
    #
    #     conn = self.get_connection()
    #     try:
    #         cur = conn.cursor()
    #         for service_name, service_config in self.services.items():
    #             if service_config['is_service_allowed_to_run']:
    #                 notify_channel = service_config['notify_channel']
    #                 try:
    #                     cur.execute(f"LISTEN {notify_channel};")
    #                     conn.commit()
    #                 except Exception as _err:
    #                     LOGGER.error(
    #                         f"Exception occurred when setting up SQL 'LISTEN {notify_channel}' for "
    #                         f"'{service_name}' server. Error: {_err}")
    #                     raise
    #         cur.close()
    #     except Exception as _err:
    #         LOGGER.error(f"{type(_err).__name__}: {_err}")
    #         raise
    #     finally:
    #         self.put_connection(conn)

    def _query_update_servers(self, _id: int, service_name: str):
        """
        Receives 'config' dict with server's parameters.
        Connects to SQL Server and update 'servers' table where 'id' = config.server['server_id'].
        """

        excluded_columns = ('start_time', 'is_service_allowed_to_run')

        additional_columns = {
            'is_active': True
        }

        conn = self.get_connection()

        try:
            _service_config = {'type': service_name}
            _service_config |= self.server.copy()
            _service_config |= self.services[service_name]
            _service_config |= additional_columns
            [_service_config.pop(excluded_key) for excluded_key in excluded_columns if excluded_key in _service_config]

            with conn.cursor() as cur:
                cur.execute("SELECT * FROM servers WHERE id = %s;", (_id,))
                conn.commit()
                sql_values = cur.fetchone()
            # '0' stands for column name in cur.description
            sql_config = {desc[0]: sql_values[i] for i, desc in enumerate(cur.description)}

            # Prepare and execute the update query
            updated_config = {}
            for key, value in _service_config.items():
                if key in sql_config and sql_config[key] != value:
                    updated_config[key] = value

            if updated_config:
                query = "UPDATE servers SET ({}) = ({}) WHERE id = %s;"
                sql_format_query = sql.SQL(query).format(
                    sql.SQL(', ').join(map(sql.Identifier, updated_config.keys())),
                    sql.SQL(', ').join(sql.Placeholder() * len(updated_config))
                )
                with conn.cursor() as cur:
                    # LOGGER.debug(cur.mogrify(sql_format_query, (*updated_config.values(), _id,)))
                    cur.execute(sql_format_query, (*updated_config.values(), _id,))
                    conn.commit()
        except Exception as _err:
            LOGGER.error(f"{type(_err).__name__}: {_err}")
            raise RuntimeError(f"Failed to update 'servers' table where server's 'id' = {_id} on SQL Server.")
        finally:
            self.put_connection(conn)

    def _print_server_info(self):

        excluded_keys = ('start_time', 'notify_channel_hash',)
        _info = {}
        _msg = []

        def _len(_value):
            _backslash_count = str(_value).count('\\')
            return len(str(_value)) + _backslash_count

        try:
            _info = {
                'running_services': ', '.join([service for service, service_config in self.services.items()
                                               if service_config['is_service_allowed_to_run']])
            }
            _info |= self.server.copy()
            _info['nas'] = self.nas['absolute_path']
            [_info.pop(excluded_key) for excluded_key in excluded_keys]

            title = ' SERVER INFO '
            spaces_around = 4
            separator = ': '
            max_key_len = max([_len(key) for key in _info.keys()]) + spaces_around
            max_value_len = max([_len(value) for value in _info.values()]) + spaces_around

            full_len = 2 + _len(separator) + max_key_len + max_value_len

            first_line_left = (full_len - _len(title) - 2) // 2
            first_line_right = full_len - _len(title) - first_line_left - 2

            _msg = [
                f"|{'*' * first_line_left}{title}{'*' * first_line_right}|",
                f"|{' ' * (full_len - 2)}|"
            ]
            for key, value in _info.items():
                backslash_count = str(value).count('\\')
                if isinstance(value, datetime):
                    value = value.strftime('%Y-%m-%d %H:%M:%S')
                elif isinstance(value, bool):
                    value = 'True' if value else 'False'
                elif isinstance(value, list):
                    value = ", ".join([str(_item) for _item in value])
                _max_value_len = max_value_len - backslash_count
                _line = "|{_k:>{_k_len}}: {_v:<{_v_len}}|".format(_k=key,
                                                                  _v=value,
                                                                  _k_len=max_key_len,
                                                                  _v_len=_max_value_len)
                _msg.append(_line)
            last_rows = [
                f"|{' ' * (full_len - 2)}|",
                f"|{'*' * (full_len - 2)}|"
            ]
            _msg.extend(last_rows)

            for line in _msg:
                LOGGER.info(line)

        except Exception as _err:
            LOGGER.error(f"{type(_err).__name__}: {_err}")
            raise

    def _insert_new_server(self, _type, _hostname, _name, _dns_domain, _ip, _version) -> int | None:
        conn = self.get_connection()
        try:
            query = ("INSERT INTO public.servers (type, hostname, name, dns_domain, ip, version) "
                     "VALUES (%s::server_type_enum, %s, %s, %s, %s, %s) RETURNING id;")
            cur = conn.cursor()
            cur.execute(query, (_type, _hostname, _name, _dns_domain, _ip, _version))
            _id = cur.fetchone()[0]
            conn.commit()
            cur.close()
            return _id

        except Exception as _err:
            LOGGER.error(f"{type(_err).__name__}: {_err}")
            raise RuntimeError("Failed to register the server in the SQL 'servers' table.")
        finally:
            self.put_connection(conn)

    def _update_server_record(self, _type, _hostname, _name, _dns_domain, _ip, _version) -> int | None:
        conn = self.get_connection()
        _id = None
        try:
            query = ("UPDATE servers "
                     "SET ip = %s, version = %s, name = %s, dns_domain = %s, time_updated = CURRENT_TIMESTAMP "
                     "WHERE type = %s::server_type_enum AND hostname = %s "
                     "RETURNING id;")
            cur = conn.cursor()
            cur.execute(query, (_ip, _version, _name, _dns_domain, _type, _hostname))
            _id = cur.fetchone()[0]
            conn.commit()
            cur.close()
            return _id

        except Exception as _err:
            LOGGER.error(f"{type(_err).__name__}: {_err}")
            raise RuntimeError("Failed to update of the server record in the DB.")
        finally:
            self.put_connection(conn)


config = Config()
