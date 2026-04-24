# print(f'__file__={__file__:<35} | __name__={__name__:<25} | __package__={str(__package__):<25}')
from __future__ import annotations

import shutil
import sys
import time
import signal
import datetime
import os
import logging
import socket
import json
import uuid
from typing import Optional
import psutil
from multiprocessing import Queue as mpQueue
from pandas import StringDtype, Int64Dtype, Int16Dtype, Int32Dtype, Float64Dtype
import select
import ctypes.wintypes
import psycopg2.extensions
from psycopg2 import sql, OperationalError, DatabaseError, ProgrammingError
from pydantic import BaseModel, ValidationError
import smbclient
from smbprotocol.connection import Connection
from smbprotocol.structure import FlagField
from smbprotocol.session import Session
from smbprotocol.tree import TreeConnect
from smbprotocol.create_contexts import (
    CreateContextName,
    SMB2CreateContextRequest,
    SMB2CreateQueryMaximalAccessRequest,
)
from smbprotocol.open import (
    DirectoryAccessMask,
    FileInformationClass,
    CreateDisposition,
    CreateOptions,
    FileAttributes,
    FilePipePrinterAccessMask,
    ImpersonationLevel,
    Open,
    ShareAccess,
)
from smbprotocol.security_descriptor import (
    AccessAllowedAce,
    AccessMask,
    AclPacket,
    SDControl,
    SIDPacket,
    SMB2CreateSDBuffer,
)

from forgelab.common.matlib import Material
from forgelab.common.library_sql_query import query_library
from forgelab.srv_post.gen_class import GenPPTWorker


LOGGER = logging.getLogger(__name__)
SENTRY = True


def signal_handler(signal_number, frame):
    """Signal Handler to process signal.SIGINT: CTRL + C"""
    global SENTRY
    SENTRY = False
    LOGGER.warning(f"POS The server received system signal: SignalNumber = '{str(signal_number)}', "
                   f"Frame = '{str(frame)}'. The server cycle will break.")


class DatabaseConfig(BaseModel):
    host: str
    port: int
    user: str
    password: str


class ServerConfig(BaseModel):
    level: str
    file: Optional[str]


class NasConfig(BaseModel):
    host: str
    port: int


class TriggersConfig(BaseModel):
    host: str
    port: int


class ConfigSchema(BaseModel):
    db: DatabaseConfig
    server: ServerConfig
    nas: NasConfig
    triggers: TriggersConfig


class PostServer:
    def __init__(self):
        signal.signal(signal.SIGINT, signal_handler)  # register signal with handler
        # self.log_queue = lq
        self.connection = None
        self.config = {}

        self.data_queue = mpQueue()
        self.is_error = False
        self.missed_notifications_timer = time.time()

    def start(self):
        # LOGGER.info("START main infinite cycle of the Server till keyboard interruption.")

        while self.no_keyboard_interruption():  # Infinite loop to restart server after crash
            # LOGGER.info("START a new cycle of the Server instance.")

            try:
                self._init_server()
                self._main_cycle_body()
                self._query_update_server_pre_main_post_status()
                self._query_deactivate_server_id()
                self._restart_server()

            except Exception as _err:
                LOGGER.error(f"POS FINISHED a cycle of the Server due to an Error: {_err}")

            time.sleep(5)

        LOGGER.info("FINISHED main infinite cycle of the Server because of keyboard interruption.")

    def _init_server(self):
        # LOGGER.info("START func '_init_server'")
        try:
            self.connection = None
            self.config = {}
            self.is_error = False
            self.missed_notifications_timer = time.time()

            root_dir = self.root_dir()
            data_dir = self.data_dir()

            self.config['db'] = self._load_config(root_dir, 'database.json')
            self.config['server'] = self._load_config(root_dir, 'server.json')
            self.config['triggers'] = self._load_config(root_dir, 'triggers.json')
            # self.init_connection_pool()

            self._add_host_name()
            self._add_ip_address()
            self._add_ram_free_size_gb()
            self._add_hdd_free_size_gb()
            self._add_cpu_count()
            self._query_server_id()

            self.config['server'] |= {
                'is_active': True,
                'time_started': datetime.datetime.now(),
                'local_dir': self._get_projects_dir_local(),
                # 'public_dir': self.get_projects_dir_public(),
                'software_root_dir': root_dir,
                'data_files_dies': self._os_join_assert(data_dir, 'dies'),
                'data_files_materials': self._os_join_assert(data_dir, 'materials'),
                'data_files_operations': self._os_join_assert(data_dir, 'operations'),
                'data_files_ppt': self._os_join_assert(data_dir, 'ppt')}

            self._query_library()

            # self.config['lib']['materials']['class'] = self._import_materials_from_data_files()
            self.config['nas'] = self._query_file_server_config()
            self.config['nas']['absolute_path'] = self._build_file_server_absolute_path()

            nas_example = {'nas': {
                'ip': str,
                'public_dir': str,
                'login_name': str,
                'login_password': str,
                }
            }
            for key1 in nas_example:
                if key1 not in self.config.keys():
                    LOGGER.error(f"POS Key '{key1}' is missed in self.config")
                    self.terminate_server_now()
                for key2 in nas_example[key1]:
                    if key2 not in self.config[key1].keys():
                        LOGGER.error(f"POS Key '{key2}' is missed in self.config['{key1}']")
                        self.terminate_server_now()
                    if not isinstance(self.config[key1][key2], nas_example[key1][key2]):
                        LOGGER.error(f"POS Key '{key2}' in self.config['{key1}'] "
                                     f"has type {str(type(self.config[key1][key2]))} "
                                     f"but must be type {str(nas_example[key1][key2])}")
                        self.terminate_server_now()

            self._connect_to_file_server()

            # self.check_local_vs_public_dirs()
            self._set_listen_to_database_notifications()
            self._query_update_servers()

            self._query_server_pre_main_fix_broken_records_after_server_crash()

            self._query_set_server_is_active(True)

            self._print_server_info()
        except Exception as _err:
            LOGGER.error(f"POS Exception: {_err}")
        else:
            return
        raise RuntimeError("POS FAILED func '_init_server'")

    def _main_cycle_body(self):
        """Main cycle body of the server."""
        processes = {}
        # query_restore_path_and_status(self.get_connection(), self.config['server']['nas'], 24)
        while self.no_critical_errors():
            try:
                if not processes:

                    is_notify = self._is_channel_notifies()
                    is_time = self._is_time_to_check_missed_notifications()

                    if is_notify or is_time:
                        for eid, pvid, eo in self._query_next_pvid():
                            param = self._get_param(eid, pvid, eo)
                            _p = param.copy()
                            _w = GenPPTWorker(data_queue=self.data_queue, param=_p)
                            _w.start()
                            processes[eid] = _w

                if not self.data_queue.empty():
                    _r = self.data_queue.get()
                    if _r['is_error']:
                        LOGGER.info(f"POS {_r['process_version_id']}/{_r['execution_order']} QUEUE "
                                    f"received ERROR status from GenPPTWorker")
                        self._query_set_post_status_error(_r)
                    else:
                        eid = _r['execution_id']
                        _w = processes.pop(eid, None)
                        if _w is not None:
                            # _w.join()
                            pass

                    self._query_set_post_status_finished(_r)

            except Exception as _err:
                LOGGER.error(f"POS Exception: {_err}")
                self.is_error = True
                break

    def _get_param(self, eid: int, pvid: int, eo: int) -> dict:
        try:
            param = {
                'execution_id': eid,
                'execution_order': eo,
                'table': self._query_server_pre_main(pvid),
                'project': self._query_process_versions(pvid),
                'post': self._query_post_operations(pvid)
            }

            try:
                type_id = param['table'][eo]['type_id']
                operation_id = param['table'][eo]['operation_id']
                operation_dir_name = param['table'][eo]['operation_dir_name']
                project_dir_name: str = param['project']['project_dir_name']
                process_id = param['project']['process_id']
            except Exception as _err:
                LOGGER.error(_err)
                raise

            param |= {
                'process': self._query_processes(process_id),
                'type_id_nnn': self._query_type_id_nnn(type_id, operation_id),
                'operation': self._import_parameters_json_from_nas(eo, project_dir_name, operation_dir_name)
            }

        except Exception as _err:
            LOGGER.error(f"POS Exception: {_err}")
        else:
            # LOGGER.info(f"OK: initialized parameters with keys=({', '.join(list(param.keys()))}) "
            #             f"at server 'id'={server_id} for 'pvid'={pvid} 'eo'={eo}")
            return param
        raise RuntimeError("POS FAILED func '_get_param'")

    def _query_set_post_status_error(self, post_results: dict):
        """
        Do SQL query and set 'post_status'.
        :param post_results: dict
        """
        try:
            server_id = self.config['server']['id']

            pvid = post_results['process_version_id']
            eo = post_results['execution_order']
            eid = post_results['execution_id']
        except KeyError as _err:
            LOGGER.error(f"POS KeyError: {_err}")
            raise KeyError(_err)

        case_msg = (f"POS {pvid}/{eo} Server 'id'={server_id} FAILED UPDATE server_pre_main "
                    f"SET 'post_status'='error' where 'execution_id'={eid}")

        query = """
        UPDATE server_pre_main SET 
            post_server_id = NULL,
            post_status = 'error'::post_status_enum,
            post_time_finished = NOW(),
            post_images_abs_path = DEFAULT,
            post_pptx_abs_path = DEFAULT,
            ppt_file_name = DEFAULT 
        WHERE execution_id = %s;"""

        conn = self.get_connection()

        try:
            cur = conn.cursor()
            cur.execute(query, (eid,))
            conn.commit()
            cur.close()
        except OperationalError as _err:
            LOGGER.error(f"{case_msg} OperationalError: {_err}")
        except DatabaseError as _err:
            LOGGER.error(f"{case_msg} with DatabaseError: {_err}")
        except Exception as _err:
            LOGGER.error(f"{case_msg} with Exception: {_err}")
        else:
            LOGGER.info(f"POS {pvid}/{eo} FAILED Server 'id'={server_id} set 'post_status'='error'")
            return
        raise RuntimeError(case_msg)

    @staticmethod
    def terminate_server_now():
        LOGGER.critical("POS Terminate command received. Stopping server...")
        sys.exit(1)

    @staticmethod
    def no_keyboard_interruption() -> bool:
        """Returns True if server is allowed to run. Otherwise, returns False."""
        try:
            if SENTRY:
                LOGGER.info("POS New server instance will be started.")
            else:
                LOGGER.error("POS New server instance starting is forbidden. Restarting server is forbidden. "
                             "Terminating the server...")
        except Exception as _err:
            LOGGER.error(f"POS Exception: {_err}")
        return SENTRY

    def no_critical_errors(self) -> bool:
        """Returns True if server is allowed to run. Otherwise, returns False."""
        if not SENTRY:
            LOGGER.warning("POS Keyboard interruption received. The main server cycle is terminated. "
                           "Finalizing the server instance...")
            return False

        if self.is_error:
            LOGGER.error("POS Server has 'self.is_error' = True. Server cycle will be interrupted to stop the server.")
            return False
        return True

    def _set_listen_to_database_notifications(self):
        try:
            notify_channel = self.config['server']['notify_channel']
        except KeyError as _err:
            raise RuntimeError(f"POS FAILED func '_set_listen_to_database_notifications' with KeyError: {_err}")

        case_msg = f"occurred when setting up SQL 'LISTEN {notify_channel}'. Error:"

        try:
            conn = self.get_connection()
            cur = conn.cursor()
            cur.execute(f"LISTEN {notify_channel};")
            conn.commit()
            cur.close()
        except OperationalError as _err:
            LOGGER.error(f"POS OperationalError {case_msg} {_err}")
        except DatabaseError as _err:
            LOGGER.error(f"POS DatabaseError {case_msg} {_err}")
        except Exception as _err:
            LOGGER.error(f"Some error {case_msg} {_err}")
        else:
            return
        raise RuntimeError("POS FAILED func '_set_listen_to_database_notifications'")

    def get_connection(self) -> Optional[psycopg2.extensions.connection]:
        while True:
            try:
                if self.connection is None:
                    self.connection = psycopg2.connect(
                        user=self.config['db']['user'],
                        password=self.config['db']['pass'],
                        host=self.config['db']['host'],
                        port=self.config['db']['port'],
                        database=self.config['db']['base'])
                cur = self.connection.cursor()
                cur.execute("SELECT 1;")
                self.connection.commit()
                cur.close()
            except OperationalError as _err:
                LOGGER.error(f"Failed to create connection. Wait then retry infinitely. 'OperationalError': {_err}")
            except DatabaseError as _err:
                LOGGER.error(f"Failed to create connection. Wait then retry infinitely. 'DatabaseError': {_err}")
            except KeyError as _err:
                LOGGER.critical(f"Failed to create connection because of missed key '{_err}' in 'self.config'.")
                self.terminate_server_now()
            except Exception as _err:
                LOGGER.critical(f"Some uncategorized Error: {_err}")
                self.terminate_server_now()
            else:
                break
            time.sleep(1.0)
            self.connection = None
        return self.connection

    @staticmethod
    def root_dir() -> str:
        return os.path.dirname(os.path.dirname(__file__))

    @staticmethod
    def data_dir() -> str:
        return os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')

    @staticmethod
    def _load_config(root_dir: str, filename: str) -> dict:
        """Receives '*.json' file name. Returns dictionary. If error, stops server."""
        case_msg = f"occurred while loading config file {filename} form {root_dir} with Error:"
        try:
            abs_path = os.path.join(root_dir, 'config', filename)
            with open(abs_path, 'r', encoding='utf-8') as stream:
                config = json.load(stream)
                assert config, f"Failed loading config file '{abs_path}'."
        except AssertionError as _err:
            LOGGER.error(f"POS AssertionError {case_msg} {_err}")
        except FileNotFoundError as _err:
            LOGGER.critical(f"POS FileNotFoundError {case_msg} {_err}")
        except OSError as exception:
            LOGGER.critical(f"POS OSError {case_msg} {exception.strerror} {exception.errno}")
        except json.JSONDecodeError as _err:
            LOGGER.critical(f"POS json.JSONDecodeError {case_msg} {_err}")
        except Exception as _err:
            LOGGER.critical(f"Some Error {case_msg} {_err}")
        else:
            return config
        raise RuntimeError(f"POS FAILED func '_load_config' {case_msg}")

    def _get_projects_dir_local(self) -> str:
        """Receives '*.json' file name. If error, stops server."""
        try:
            dir_id = 28  # [LOCALAPPDATA] A typical path is C:\Users\username\AppData\Local
            type_current = 0  # Get current, not default value
            buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
            ctypes.windll.shell32.SHGetFolderPathW(None, dir_id, None, type_current, buf)
            system_dir = buf.value
            project_dir_name: str = self.config['server']['projects_dir']
            dir_local = os.path.join(system_dir, project_dir_name)
            if not os.path.exists(dir_local):
                os.makedirs(dir_local)
            assert os.path.isdir(dir_local), f"Can't find local simulation project directory '{dir_local}'"
        except KeyError as _err:
            LOGGER.critical(f"Failed to get key '{_err}'.")
        except OSError as exception:
            LOGGER.critical(f"Some 'OSError': {exception.strerror} {exception.errno}.")
        except AssertionError as _err:
            LOGGER.critical(_err)
        except Exception as _err:
            LOGGER.critical(f"Some uncategorized Error: {_err}.")
        else:
            return dir_local
        raise RuntimeError("POS FAILED func '_get_projects_dir_local'")

    @staticmethod
    def _os_join_assert(*args) -> str:
        """Receives '*.json' file name. If error, stops server."""
        try:
            _dir = str(os.path.join(*args))
            assert os.path.isdir(_dir), f"Can't find local directory '{_dir}'"
        except AssertionError as _err:
            LOGGER.critical(_err)
        except Exception as _err:
            LOGGER.critical(f"Some uncategorized Error: {_err}.")
        else:
            return _dir
        raise RuntimeError("POS FAILED func '_os_join_assert'")

    def _is_time_to_check_missed_notifications(self):
        try:
            timeout = self.config['server']['hard_timeout']
        except KeyError as _err:
            LOGGER.error(f"Failed to get Key {_err}")
            raise KeyError(f"KeyError in func '_cycle_timeout': {_err}")

        if not isinstance(timeout, (int, float)):
            _err = "ValueError of 'hard_timeout' in 'server.json'"
            LOGGER.error(_err)
            raise ValueError(_err)

        if time.time() >= self.missed_notifications_timer:
            self.missed_notifications_timer += timeout
            return True
        return False

    def _is_channel_notifies(self) -> bool:
        # LOGGER.info("Querying database for changes.")
        case_msg = "occurred when trying to query SQL for ANY notification. Error:"

        conn = self.get_connection()

        try:
            is_notify = False
            if self._is_notification(conn):
                if self._is_channel(conn):
                    is_notify = True
        except OperationalError as _err:
            LOGGER.error(f"POS OperationalError {case_msg} {_err}")
        except DatabaseError as _err:
            LOGGER.error(f"POS DatabaseError {case_msg} {_err}")
        except Exception as _err:
            LOGGER.error(f"Some error {case_msg} {_err}")
        else:
            return is_notify
        raise RuntimeError("POS FAILED func '_is_channel_notifies'")

    def _is_notification(self, conn: psycopg2.extensions.connection) -> list:
        try:
            notify_timeout = self.config['server']['notify_timeout']
        except KeyError as _err:
            raise RuntimeError(f"KeyError in func '_is_notification': {_err}")

        try:
            is_ready_for_reading, _, _ = select.select([conn], [], [], notify_timeout)
            conn.commit()
        except OperationalError as _err:
            LOGGER.error(f"POS OperationalError: {_err}")
        except DatabaseError as _err:
            LOGGER.error(f"POS DatabaseError: {_err}")
        except Exception as _err:
            LOGGER.error(f"Some error: {_err}")
        else:
            # True if data in connection socket is ready
            return is_ready_for_reading
        raise RuntimeError("POS FAILED func '_is_notification'")

    def _is_channel(self, conn: psycopg2.extensions.connection) -> bool:
        try:
            conn.poll()
            is_notify = False
            while conn.notifies:
                if conn.notifies.pop(0).channel == self.config['server']['notify_channel']:
                    is_notify = True
                    # LOGGER.info(f"Notification received on channel '{self.config['server']['notify_channel']}'.")
                    break
        except OperationalError as _err:
            LOGGER.error(f"POS OperationalError: {_err}")
        except DatabaseError as _err:
            LOGGER.error(f"POS DatabaseError: {_err}")
        except Exception as _err:
            LOGGER.error(f"Some error: {_err}")
        else:
            return is_notify
        raise RuntimeError("POS FAILED func '_is_channel'")

    def _query_next_pvid(self) -> list[tuple[int, int, int]]:
        try:
            queue_selected_eid_pvid_eo = self._query_select_eid_pvid_eo()
            queue_eid_pvid_eo = self._query_update_server_pre_main_post_set_run(queue_selected_eid_pvid_eo)

        except Exception as _err:
            LOGGER.error(f"POS Exception: {_err}.")
        else:
            return queue_eid_pvid_eo
        raise RuntimeError("POS FAILED func '_query_next_pvid'")

    def _query_select_eid_pvid_eo(self) -> list[tuple[int, int, int]]:
        try:
            if self.config['server']['is_development_mode']:
                development_condition = ""
            else:
                development_condition = "NOT"

            slots_count = self.config['server']['max_threads_count']

        except KeyError as _err:
            LOGGER.error(f"POS KeyError: {_err}")
            raise RuntimeError(f"POS FAILED func '_query_update_simulation_status_for_tasks_on_nas'")
        except Exception as _err:
            LOGGER.error(f"POS Exception: {_err}")
            raise RuntimeError(f"POS FAILED func '_query_update_simulation_status_for_tasks_on_nas'")

        case_msg = (
            f"POS FAILED func '_query_update_simulation_status_for_tasks_in_queue_threads' "
            f"when SELECT spm.execution_id, spm.process_version_id, spm.execution_order FROM server_pre_main spm "
            f"JOIN process_versions pv ON spm.process_version_id = pv.process_version_id "
            f"WHERE spm.post_server_id IS NULL "
            f"AND spm.post_status = 'queue' "
            f"AND spm.simulation_status = 'finished' "
            f"AND pv.name {development_condition} LIKE '[DEV]%' "
            f"ORDER BY spm.simulation_time_finished ASC LIMIT {slots_count};")

        select_query = f"""
SELECT spm.execution_id, spm.process_version_id, spm.execution_order 
FROM server_pre_main spm 
JOIN process_versions pv ON spm.process_version_id = pv.process_version_id 
WHERE 
spm.post_server_id IS NULL 
AND spm.post_status = 'queue' 
AND spm.simulation_status = 'finished' 
AND pv.name {development_condition} LIKE %(process_version_name)s 
ORDER BY spm.simulation_time_finished ASC LIMIT %(slots_count)s;"""

        conn = self.get_connection()

        try:
            cur = conn.cursor()
            cur.execute(select_query, {'slots_count': slots_count,
                                       'process_version_name': '[DEV]%'})
            updated_records = cur.fetchmany()
            conn.commit()
            cur.close()
            eid_pvid_eo = [(eid, pvid, eo) for eid, pvid, eo in updated_records]

        except OperationalError as _err:
            LOGGER.error(f"OperationalError: {_err}")
        except DatabaseError as _err:
            LOGGER.error(f"DatabaseError: {_err}")
        except KeyError as _err:
            LOGGER.error(f"POS KeyError: '{_err}'.")
        except Exception as _err:
            LOGGER.error(f"POS Exception: {_err}")
        else:
            return eid_pvid_eo
        raise RuntimeError(case_msg)

    def _query_update_server_pre_main_post_set_run(self, eid_pvid_eo: list[tuple[int, int, int]]
                                                   ) -> list[tuple[int, int, int]]:

        try:
            server_id = self.config['server']['id']

        except KeyError as _err:
            LOGGER.error(f"POS KeyError: {_err}")
            raise RuntimeError(f"POS FAILED func '_query_update_server_pre_main_post'")

        query = (
            f"UPDATE server_pre_main SET "
            f"post_server_id = %(server_id)s, "
            f"post_status = 'run'::post_status_enum, "
            f"post_time_started = NOW(), "
            f"post_time_finished = DEFAULT, "
            f"post_images_abs_path = DEFAULT, "
            f"post_pptx_abs_path = DEFAULT "
            f"WHERE execution_id = %(execution_id)s;")

        updated_records = []
        are_all_records_updated = []

        conn = self.get_connection()

        for eid, pvid, eo in eid_pvid_eo:
            case_msg = (
                f"UPDATE server_pre_main SET "
                f"post_server_id = {server_id}, "
                f"post_status = 'run', "
                f"post_time_started = NOW(), "
                f"post_time_finished = DEFAULT, "
                f"post_images_abs_path = DEFAULT, "
                f"post_pptx_abs_path = DEFAULT "
                f"WHERE execution_id = {eid};")
            is_one_record_updated = False
            try:
                cur = conn.cursor()
                cur.execute(query, {'server_id': server_id,
                                    'execution_id': eid})
                conn.commit()
                cur.close()
            except OperationalError as _err:
                LOGGER.error(f"OperationalError: {_err}")
            except DatabaseError as _err:
                LOGGER.error(f"DatabaseError: {_err}")
            except KeyError as _err:
                LOGGER.error(f"POS KeyError: '{_err}'.")
            except Exception as _err:
                LOGGER.error(f"POS Exception: {_err}")
            else:
                is_one_record_updated = True

            if is_one_record_updated:
                updated_records.append((eid, pvid, eo, ))
                LOGGER.info(f"POS {pvid}/{eo} SQL QUERY SUCCESS {case_msg}")
            else:
                LOGGER.warning(f"POS {pvid}/{eo}: FAILED to {case_msg}")

            are_all_records_updated.append(is_one_record_updated)

        if len(are_all_records_updated) == 0:
            return []
        elif any(are_all_records_updated):
            return updated_records
        else:
            raise RuntimeError("POS FAILED func '_query_update_server_pre_main_post'")

    def _add_host_name(self):
        """
        Retrieve the hostname of the computer.
    
        This function uses the built-in `socket` library to fetch the hostname of the computer.
        It is compatible with Windows 10, Windows 11, Linux, and macOS.
    
        Returns
        -------
        str
            The hostname of the computer.
        """
        case_msg = "occurred when trying to fetch server's hostname."
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
            self.config['server']['hostname'] = hostname
            self.config['server']['name'] = hostname
            self.config['server']['dns_domain'] = domain
        except KeyError as _err:
            LOGGER.error(f"POS KeyError {case_msg} Error: {_err}")
        except Exception as _err:
            LOGGER.critical(f"Some error {case_msg} Error: {_err}")
        else:
            return
        raise RuntimeError(f"POS FAILED func '_add_host_name' {case_msg}")

    def _add_ip_address(self):
        """
        Retrieve the ip address of the computer.
        Saves ip address to self.config['server']['ip'].
        """
        try:
            _ip = socket.gethostbyname(socket.gethostname())
            self.config['server']['ip'] = _ip
        except Exception as _err:
            LOGGER.critical(f"Failed to fetch server's IP address. Error: {_err}")
        else:
            return
        raise RuntimeError("POS FAILED func '_add_ip_address'")

    def _add_ram_free_size_gb(self):
        try:
            available_ram_bytes = psutil.virtual_memory().available
            self.config['server']['ram_free_size_gb'] = available_ram_bytes / 1073741824  # bytes to GB

        except Exception as _err:
            LOGGER.critical(f"POS FAILED func '_add_ram_free_size_gb'. Error: {_err}")
        else:
            return
        raise RuntimeError("POS FAILED func '_add_ram_free_size_gb'")

    def _add_hdd_free_size_gb(self):
        try:
            _, _, free = shutil.disk_usage(os.path.curdir)
            self.config['server']['hdd_free_size_gb'] = free / 1073741824  # bytes to GB

        except Exception as _err:
            LOGGER.critical(f"POS FAILED func '_add_hdd_free_size_gb'. Error: {_err}")
        else:
            return
        raise RuntimeError("POS FAILED func '_add_hdd_free_size_gb'")

    def _add_cpu_count(self):
        try:
            cpu_count_available = os.cpu_count()
            cpu_count_limit = self.config['server']['cpu_count_deform_license_max_limit']
            cpu_count = min(cpu_count_limit, cpu_count_available)

            self.config['server'] |= {
                'cpu_count_available': cpu_count_available,
                'cpu_count': cpu_count}

        except Exception as _err:
            LOGGER.critical(f"Failed to fetch CPU count. Error: {_err}")
        else:
            return
        raise RuntimeError("POS FAILED func '_add_cpu_count'")

    def _query_server_id(self):
        """
        Receives server name (defined in 'triggers.json').
        Queries 'servers' table for old server 'id'.
        Otherwise, insert a new one.
        Returns 'id' of the server.
        """
        err_case = "Failed to INSERT or UPDATE servers SET id, name, dns_domain, ip, version"
        try:
            _srv = self.config['server']
            _hostname = _srv['hostname']
            _name = _srv['name']
            _dns_domain = _srv['dns_domain']
            _ip = _srv['ip']
            _type = _srv['type']
            _version = _srv['version']
        except KeyError as _err:
            LOGGER.error(f"{err_case} with KeyError: {_err}")
            raise RuntimeError(f"{err_case} with KeyError: {_err}")

        err_case = (f"Failed to INSERT or UPDATE servers SET id, name, dns_domain, ip, version "
                    f"WHERE type = {_type} AND hostname='{_hostname}'")

        try:
            _id = self._query_existing_server_id(_type, _hostname)
            if _id is None:
                _id = self._insert_new_server(_type, _hostname, _name, _dns_domain, _ip, _version)
            elif _ip != _ip or _version != _version:
                _id = self._update_server_record(_type, _hostname, _name, _dns_domain, _ip, _version)

            self.config['server']['id'] = _id
        except KeyError as _err:
            LOGGER.error(f"{err_case} with KeyError: {_err}")
        except Exception as _err:
            LOGGER.error(f"{err_case} with Exception: {_err}")
        else:
            return
        raise RuntimeError(f"POS FAILED func '_query_server_id' {err_case}")

    def _query_existing_server_id(self, server_type: str, hostname: str) -> int:

        err_case = f"Failed to SELECT id FROM servers WHERE type = {server_type} AND hostname = {hostname}"

        conn = self.get_connection()

        try:
            query = ("SELECT id FROM servers"
                     " WHERE type = %s::server_type_enum AND hostname = %s LIMIT 1;")
            cur = conn.cursor()
            cur.execute(query, (server_type, hostname,))
            result = cur.fetchone()
            conn.commit()
            cur.close()

            _id = result[0] if result else None

        except (OperationalError, DatabaseError) as _err:
            LOGGER.critical(f"{err_case} with OperationalError or DatabaseError: {_err}")
        except Exception as _err:
            LOGGER.critical(f"{err_case} with Exception: {_err}")
        else:
            return _id
        raise RuntimeError(err_case)

    def _insert_new_server(self, _type: str, _hostname: str, _name: str, _dns_domain: str, _ip: str, _version: str
                           ) -> int:

        err_case = (f"Failed to INSERT INTO servers (type='{_type}', hostname='{_hostname}', name='{_name}', "
                    f"dns_domain='{_dns_domain}', ip='{_ip}', version='{_version}')")

        conn = self.get_connection()

        try:
            query = ("INSERT INTO public.servers (type, hostname, name, dns_domain, ip, version) "
                     "VALUES (%s::server_type_enum, %s, %s, %s, %s, %s) RETURNING id;")
            cur = conn.cursor()
            cur.execute(query, (_type, _hostname, _name, _dns_domain, _ip, _version))
            _id = cur.fetchone()[0]
            conn.commit()
            cur.close()
        except OperationalError as _err:
            LOGGER.critical(f"{err_case} with OperationalError: {_err}")
        except DatabaseError as _err:
            LOGGER.critical(f"{err_case} with DatabaseError: {_err}")
        except Exception as _err:
            LOGGER.critical(f"{err_case} with Exception: {_err}")
        else:
            return _id
        raise RuntimeError(err_case)

    def _update_server_record(self, _type: str, _hostname: str, _name: str, _dns_domain: str, _ip: str, _version: str
                              ) -> int:

        err_case = (f"Failed to UPDATE servers SET type='{_type}', hostname='{_hostname}', name='{_name}', "
                    f"dns_domain='{_dns_domain}', ip='{_ip}, version='{_version}")

        conn = self.get_connection()
        _id = None
        try:
            query = """
UPDATE servers SET 
    ip = %s, 
    version = %s, 
    name = %s, 
    dns_domain = %s, 
    time_updated = NOW() 
WHERE 
    type = %s::server_type_enum 
    AND 
    hostname = %s RETURNING id;"""
            cur = conn.cursor()
            cur.execute(query, (_ip, _version, _name, _dns_domain, _type, _hostname))
            _id = cur.fetchone()[0]
            conn.commit()
            cur.close()

        except OperationalError as _err:
            LOGGER.critical(f"{err_case} with OperationalError: {_err}")
        except DatabaseError as _err:
            LOGGER.critical(f"{err_case} with DatabaseError: {_err}")
        except Exception as _err:
            LOGGER.critical(f"{err_case} with Exception: {_err}")
        else:
            return _id
        raise RuntimeError(err_case)

    def _query_set_server_is_active(self, is_active: bool):

        try:
            server_id = self.config['server']['id']
            is_active_str = 'TRUE' if is_active else 'FALSE'
        except KeyError as _err:
            LOGGER.error(f"Failed to get key '{_err}' from 'self.config'.")
            raise RuntimeError(f"Failed to get key '{_err}' from 'self.config'.")

        err_case = f"Failed to UPDATE servers SET is_active = {is_active_str} WHERE id='{server_id}'"

        conn = self.get_connection()

        try:
            query = "UPDATE servers SET is_active = %s WHERE id = %s;"
            cur = conn.cursor()
            cur.execute(query, (is_active_str, server_id,))
            conn.commit()
            cur.close()

        except OperationalError as _err:
            LOGGER.critical(f"{err_case} with OperationalError: {_err}")
        except DatabaseError as _err:
            LOGGER.critical(f"{err_case} with DatabaseError: {_err}")
        except Exception as _err:
            LOGGER.critical(f"{err_case} with Exception: {_err}")
        else:
            return
        raise RuntimeError(err_case)

    def _query_file_server_config(self) -> dict:
        """
        Query NAS configuration from the database. Returns absolute network path to the NAS public directory.
        """
        columns = ('dns_domain', 'hostname', 'ip', 'public_dir', 'login_name', 'login_password')
        query = "SELECT {} FROM servers WHERE type = 'file_server' ORDER BY time_started ASC LIMIT 1;"

        case_msg = (f"occurred when query for network hostname, DNS domain, IP and 'public_dir' of the server "
                    f"with 'file_server' type, which is NAS.")

        conn = self.get_connection()

        try:
            sql_query = sql.SQL(query).format(sql.SQL(', ').join(map(sql.Identifier, columns)))

            cur = conn.cursor()
            cur.execute(sql_query)
            result = cur.fetchone()
            conn.commit()
            cur.close()

            assert result, "Query result is empty."
            values_dict = {key: val for key, val in zip(columns, result)}

        except OperationalError as _err:
            LOGGER.error(f"POS OperationalError {case_msg} Error: {_err}")
        except ProgrammingError as _err:
            LOGGER.error(f"POS ProgrammingError {case_msg} Error: {_err}")
        except DatabaseError as _err:
            LOGGER.error(f"POS DatabaseError {case_msg} Error: {_err}")
        except AssertionError as _err:
            LOGGER.error(f"Failed to parse the result of the query. {_err}")
        except Exception as _err:
            LOGGER.error(f"Some error {case_msg} Error: {_err}")
        else:
            return values_dict
        raise RuntimeError(f"POS FAILED func '_query_nas_config' {case_msg}")

    def _build_file_server_absolute_path(self) -> str:
        try:
            fs = self.config['nas']
            file_server_path = fr"\\{fs['ip']}\{fs['public_dir']}"

        except KeyError as _err:
            LOGGER.error(f"POS KeyError: {_err}")
        except Exception as _err:
            LOGGER.error(f"POS Exception: {_err}")
        else:
            return file_server_path
        raise RuntimeError(f"POS FAILED func '_build_file_server_absolute_path'")

    def _import_materials_from_data_files(self):
        case_msg = "occurred when importing Material Classes from data files."
        classes = {}
        try:
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
        except KeyError as _err:
            LOGGER.error(f"POS KeyError {case_msg} Error: {_err}")
        except Exception as _err:
            LOGGER.error(f"Some error {case_msg} Error: {_err}")
        else:
            return classes
        raise RuntimeError(f"POS FAILED func '_import_materials_from_data_files' {case_msg}")

    def _print_server_info(self):

        case_msg = "occurred when printing Initialization Main Message Status."
        _info = {}
        _msg = []

        def _len(_value):
            _backslash_count = str(_value).count('\\')
            return len(str(_value)) + _backslash_count

        try:
            _info = self.config['server']
            _info['File server / absolute path'] = self.config['nas']['absolute_path']
            _info['File server / login_name'] = self.config['nas']['login_name']

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
                if isinstance(value, datetime.datetime):
                    value = value.strftime('%Y-%m-%d %H:%M:%S')
                elif isinstance(value, bool):
                    value = 'True' if value else 'False'
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

        except KeyError as _err:
            LOGGER.error(f"POS KeyError {case_msg} Error: {_err}")
        except Exception as _err:
            LOGGER.error(f"Some error {case_msg} Error: {_err}")
        else:
            return
        raise RuntimeError(f"POS FAILED func '_print_server_info' {case_msg}")

    def _query_update_server_pre_main_post_status(self):
        """
        Call this function before terminating the server.
        """
        try:
            _id = self.config['server']['id']
        except KeyError as _err:
            raise RuntimeError(f"POS FAILED func '_query_update_server_pre_main_post_status' with KeyError: {_err}")

        query = """
            UPDATE server_pre_main 
            SET 
                post_server_id = DEFAULT,
                post_status = 'error'::post_status_enum,
                ppt_file_name = DEFAULT,
                post_time_started = DEFAULT,
                post_time_finished = DEFAULT,
                post_images_abs_path = DEFAULT,
                post_pptx_abs_path = DEFAULT
            WHERE post_server_id = %s;"""
        case_msg = (f"POS FAILED func '_query_update_server_pre_main_post_status' "
                    f"when updating 'server_pre_main' setting "
                    f"'post_status'='error' and other 'post_...'=DEFAULT where 'post_server_id'={_id} "
                    f"due to the server Terminating")

        conn = self.get_connection()

        try:
            cur = conn.cursor()
            cur.execute(query, (_id,))
            conn.commit()
            cur.close()
        except OperationalError as _errs:
            LOGGER.error(f"{case_msg} with OperationalError: {_errs}")
        except ProgrammingError as _errs:
            LOGGER.error(f"{case_msg} with ProgrammingError: {_errs}")
        except DatabaseError as _errs:
            LOGGER.error(f"{case_msg} with DatabaseError: {_errs}")
        except Exception as _errs:
            LOGGER.error(f"{case_msg} with Exception: {_errs}")
        else:
            return
        raise RuntimeError(case_msg)

    def _query_deactivate_server_id(self):
        """
        Receives 'config' dict with server's parameters.
        Connects to SQL Server and update 'servers' table where 'id' = config['server']['server_id'].
        """
        try:
            _id = self.config['server']['id']
        except KeyError as _err:
            raise RuntimeError(f"POS FAILED func '_query_deactivate_server_id' with KeyError: {_err}")

        conn = self.get_connection()

        try:
            cur = conn.cursor()
            cur.execute("UPDATE servers SET is_active = FALSE, time_finished = NOW() WHERE id = %s;", (_id,))
            conn.commit()
            cur.close()

        except OperationalError as _errs:
            LOGGER.error(f"OperationalError: {_errs}")
        except ProgrammingError as _errs:
            LOGGER.error(f"ProgrammingError: {_errs}")
        except DatabaseError as _errs:
            LOGGER.error(f"DatabaseError: {_errs}")
        except Exception as _errs:
            LOGGER.error(f"POS Exception: {_errs}")
        else:
            return
        raise RuntimeError(f"POS FAILED func '_query_deactivate_server_id' when "
                           f"UPDATE servers SET is_active = FALSE, time_finished = NOW() WHERE id = {_id};")

    def _restart_server(self):
        """
        Restart the PC neglecting all the running and hanging processes.
        """
        try:
            if self.config['server']['is_allow_restart']:
                LOGGER.info("Starting the server restarting procedure...")
            else:
                LOGGER.info("'is_allow_restart' is False. Restarting the server is prohibited.")
                return
        except KeyError as _err:
            LOGGER.error(f"POS KeyError: {_err}")
            raise RuntimeError(f"KeyError in func '_restart_server': {_err}")

        try:
            os.system("shutdown /r /t 0")
        except Exception as _err:
            LOGGER.error(f"POS Exception: {_err}")
            raise RuntimeError(f"FAILED to restart the server.")

    def _query_update_servers(self):
        """
        Receives 'config' dict with server's parameters.
        Connects to SQL Server and update 'servers' table where 'id' = config['server']['server_id'].
        """
        try:
            _id = self.config['server']['id']
        except KeyError as _err:
            raise RuntimeError(f"POS FAILED func '_query_update_servers' with KeyError: {_err}")

        case_msg = f"occurred when trying to update 'servers' table where server's 'id' = {_id} on SQL Server."

        excluded_columns = ('start_time',)

        conn = self.get_connection()

        try:
            config = self.config['server'].copy()
            config['nas'] = self.config['nas']['absolute_path']

            cur = conn.cursor()

            # Fetch current values from the database
            cur.execute("SELECT * FROM servers WHERE id = %s;", (_id,))
            conn.commit()
            current_values = cur.fetchone()
            col_names = [desc[0] for desc in cur.description]

            # Prepare and execute the update query
            update_column_names = []
            update_values = []
            for key, value in config.items():
                if key not in excluded_columns:
                    if key in col_names:
                        if current_values[col_names.index(key)] != value:
                            update_column_names.append(key)
                            update_values.append(value)

            if update_column_names:
                query = "UPDATE servers SET ({}) = ({}) WHERE id = %s;"
                sql_format_query = sql.SQL(query).format(
                    sql.SQL(', ').join(map(sql.Identifier, update_column_names)),
                    sql.SQL(', ').join(sql.Placeholder() * len(update_column_names))
                )
                cur.execute(sql_format_query, (*update_values, _id,))
                conn.commit()

            cur.close()

        except OperationalError as _errs:
            LOGGER.error(f"POS OperationalError {case_msg} Error: {_errs}")
        except ProgrammingError as _errs:
            LOGGER.error(f"POS ProgrammingError {case_msg} Error: {_errs}")
        except DatabaseError as _errs:
            LOGGER.error(f"POS DatabaseError {case_msg} Error: {_errs}")
        except Exception as _errs:
            LOGGER.error(f"Some error {case_msg} Error: {_errs}")
        else:
            return
        raise RuntimeError(f"POS FAILED func '_query_update_servers' {case_msg}")

    def _query_set_post_status_finished(self, post_results: dict):
        err_msg = f"POS FAILED func '_query_set_post_status_finished'"
        try:
            server_id = self.config['server']['id']

            pvid = post_results['process_version_id']
            eo = post_results['execution_order']
            eid = post_results['execution_id']

            values_dict = {
                'execution_id': post_results['execution_id'],
                'ppt_file_name': post_results['ppt_file_name'],
                'post_images_abs_path': post_results['remote_images_dir'],
                'post_pptx_abs_path': post_results['remote_ppt_dir']}

        except KeyError as _err:
            LOGGER.error(f"{err_msg} with KeyError: {_err}")
            raise RuntimeError(err_msg)
        except Exception as _err:
            LOGGER.error(f"{err_msg} with Error: {_err}")
            raise RuntimeError(err_msg)

        err_msg = (f"POS FAILED func '_query_set_post_status_finished' at Server 'id'={server_id} "
                   f"when update 'server_pre_main' set 'post_status'='finished' where pvid={pvid} eo={eo} eid={eid}")

        query = """
UPDATE server_pre_main
    SET 
        post_server_id = DEFAULT,
        post_status = 'finished'::post_status_enum,
        post_time_finished = NOW(),
        post_images_abs_path = %(post_images_abs_path)s,
        post_pptx_abs_path = %(post_pptx_abs_path)s,
        ppt_file_name = %(ppt_file_name)s
    WHERE execution_id = %(execution_id)s;"""

        conn = self.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(query, values_dict)
            conn.commit()
            cur.close()
        except OperationalError as _err:
            LOGGER.error(f"{err_msg} with OperationalError: {_err}")
        except DatabaseError as _err:
            LOGGER.error(f"{err_msg} with DatabaseError: {_err}")
        except Exception as _err:
            LOGGER.error(f"{err_msg} with Error: {_err}")
        else:
            return
        raise RuntimeError(err_msg)

    def _query_processes(self, process_id: int) -> dict:
        """Query 'process' table where 'process_id'"""

        conn = self.get_connection()

        try:
            cur = conn.cursor()

            cur.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = 'process';")
            _r = cur.fetchall()

            column_names = [i[0] for i in _r]
            column_str = ', '.join(column_names)

            query_text = f"SELECT {column_str} FROM process WHERE process_id = {process_id} LIMIT 1;"
            cur.execute(query_text)
            _r = cur.fetchone()

            conn.commit()
            cur.close()

            result = {column_name: _r[i] for i, column_name in enumerate(column_names)}

        except OperationalError as _err:
            LOGGER.error(f"OperationalError: {_err}")
        except ProgrammingError as _err:
            LOGGER.error(f"ProgrammingError: {_err}")
        except DatabaseError as _err:
            LOGGER.error(f"DatabaseError: {_err}")
        except Exception as _err:
            LOGGER.error(f"POS Exception: {_err}")
        else:
            return result
        raise RuntimeError(f"POS FAILED func '_query_processes' occurred when query select a record 'process' table "
                           f"where 'process_id'={process_id}")

    def _query_process_versions(self, pvid: int) -> dict:
        """Query 'process_versions' table where 'process_versions' order by 'execution_order'"""
        case_msg = (f"occurred when trying to query select a record 'process_versions' table "
                    f"where 'process_version_id'={pvid} on SQL Server.")

        conn = self.get_connection()

        try:
            cur = conn.cursor()

            cur.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = 'process_versions';")
            _r = cur.fetchall()

            column_names = [i[0] for i in _r]
            column_str = ', '.join(column_names)

            query_text = (
                f"SELECT {column_str} FROM process_versions"
                f" WHERE process_version_id = {pvid} LIMIT 1;")
            cur.execute(query_text)
            _r = cur.fetchone()

            conn.commit()
            cur.close()

            result = {column_name: _r[i] for i, column_name in enumerate(column_names)}

        except OperationalError as _err:
            LOGGER.error(f"POS OperationalError {case_msg} Error: {_err}")
        except ProgrammingError as _err:
            LOGGER.error(f"POS ProgrammingError {case_msg} Error: {_err}")
        except DatabaseError as _err:
            LOGGER.error(f"POS DatabaseError {case_msg} Error: {_err}")
        except Exception as _err:
            LOGGER.error(f"Some error {case_msg} Error: {_err}")
        else:
            return result
        raise RuntimeError(f"POS FAILED func '_query_process_versions' {case_msg}")

    def _query_server_pre_main(self, _process_version_id: int) -> dict:
        """Query 'server_pre_main' table where 'process_versions' order by 'execution_order'"""
        case_msg = (f"POS FAILED func '_query_server_pre_main' when query select all records "
                    f"of 'server_pre_main' table where 'process_version_id'={_process_version_id} "
                    f"on SQL Server.")

        conn = self.get_connection()

        try:
            cur = conn.cursor()

            cur.execute(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_name = 'server_pre_main';")
            rows = cur.fetchall()

            column_names, data_types_sql = [], {}

            for column_name, data_type in rows:
                column_names.append(column_name)
                data_types_sql[column_name] = data_type

            columns_str = ', '.join(column_names)

            query_text = (
                f"SELECT {columns_str} FROM server_pre_main "
                f"WHERE process_version_id = {_process_version_id} ORDER BY execution_order ASC")
            cur.execute(query_text)
            result_list = cur.fetchall()

            conn.commit()
            cur.close()

            result = {}
            for row in result_list:
                row_dict = {}
                for column_number, column_name in enumerate(column_names):
                    input_value = row[column_number]
                    _type = data_types_sql[column_name]

                    if input_value is None:
                        output_value = None
                    elif _type in ('timestamp', 'timestamp without time zone'):
                        output_value = input_value.strftime("%Y-%m-%d %H:%M:%S")
                    elif _type == 'boolean':
                        output_value = bool(input_value)
                    elif _type == 'bytea':
                        output_value = bytes(input_value)
                    else:
                        output_value = input_value

                    row_dict[column_name] = output_value

                execution_order = row_dict['execution_order']
                result[execution_order] = row_dict

        except OperationalError as _err:
            LOGGER.error(f"{case_msg} with OperationalError: {_err}")
        except ProgrammingError as _err:
            LOGGER.error(f"{case_msg} with ProgrammingError: {_err}")
        except DatabaseError as _err:
            LOGGER.error(f"{case_msg} with DatabaseError: {_err}")
        except Exception as _err:
            LOGGER.error(f"{case_msg} with Exception: {_err}")
        else:
            return result
        raise RuntimeError(case_msg)

    def _query_post_operations(self, pvid: int) -> dict:
        """Query 'post_operations' table where 'process_versions' order by 'execution_order'"""
        case_msg = (f"POS FAILED func '_query_post_operations' when query select all records "
                    f"of 'post_operations' table where 'process_version_id'={pvid}")

        conn = self.get_connection()

        try:
            cur = conn.cursor()
            selected_columns = ('process_version_id', 'execution_order', 'execution_id')
            pre_q = (
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_name = 'server_pre_main';")
            cur.execute(pre_q)
            pre_rows = cur.fetchall()

            column_names, data_types_sql = [], {}

            for column_name, data_type in pre_rows:
                if column_name not in selected_columns:
                    continue
                column_names.append('pre.' + column_name)
                data_types_sql[column_name] = data_type

            post_q = (
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_name = 'post_operations';")
            cur.execute(post_q)
            post_rows = cur.fetchall()
            for column_name, data_type in post_rows:
                column_names.append('post.' + column_name)
                data_types_sql[column_name] = data_type

            query = (
                "SELECT {} FROM post_operations post"
                " JOIN server_pre_main pre ON pre.execution_id = post.execution_id"
                " WHERE pre.process_version_id = %s ORDER BY pre.execution_order ASC;")
            sql_query = sql.SQL(query).format(sql.SQL(', ').join(map(sql.Identifier, column_names)))
            sql_string = sql_query.as_string(conn).replace('"', '')
            cur.execute(sql_string, (pvid,))
            result_list = cur.fetchall()

            conn.commit()
            cur.close()

            result = {}
            for row in result_list:
                row_dict = {}
                for column_number, column_name in enumerate(column_names):
                    input_value = row[column_number]
                    _type = data_types_sql[column_name]

                    if input_value is None:
                        output_value = None
                    elif _type in ('timestamp', 'timestamp without time zone'):
                        output_value = input_value.strftime("%Y-%m-%d %H:%M:%S")
                    elif _type == 'boolean':
                        output_value = bool(input_value)
                    elif _type == 'bytea':
                        output_value = bytes(input_value)
                    else:
                        output_value = input_value

                    row_dict[column_name] = output_value

                execution_order = row_dict['execution_order']
                result[execution_order] = row_dict

        except OperationalError as _err:
            LOGGER.error(f"{case_msg} with OperationalError: {_err}")
        except ProgrammingError as _err:
            LOGGER.error(f"{case_msg} with ProgrammingError: {_err}")
        except DatabaseError as _err:
            LOGGER.error(f"{case_msg} with DatabaseError: {_err}")
        except Exception as _err:
            LOGGER.error(f"{case_msg} with Exception: {_err}")
        else:
            return result
        raise RuntimeError(case_msg)

    def _query_type_id_nnn(self, type_id: int, operation_id: int) -> tuple[list, list]:
        case_msg = "occurred when trying to query select a record 'operations_type_id_nnn' table."
        conn = self.get_connection()

        try:
            db_columns_names = self.config['lib']['operations_library'].loc[type_id, 'db_column_names']

        except Exception as _err:
            LOGGER.error(_err)
            raise
        else:
            if not db_columns_names:
                # This type_id doesn't have any values in the database and
                # does not have corresponding 'operation_type_id_nnn' table.
                return [], []

        try:
            table_name = 'operations_type_id_' + str(type_id)

            sql_to_python = {
                'double precision': float,
                'real': float,
                'numeric': float,
                'decimal': float,
                'smallint': int,
                'integer': int,
                'bigint': int,
                'boolean': bool}

            cur = conn.cursor()

            query = f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table_name}';"
            cur.execute(query)
            rows = cur.fetchall()

            values, column_names, data_types = [], [], []

            for column_name, data_type in rows:
                if column_name == 'id':
                    continue
                column_names.append(column_name)
                data_types.append(sql_to_python.get(data_type, str))

            query = "SELECT {} FROM {} WHERE id = %s LIMIT 1;"
            sql_query = sql.SQL(query).format(sql.SQL(', ').join(map(sql.Identifier, column_names)),
                                              sql.Identifier(table_name))
            cur.execute(sql_query, (operation_id,))
            input_tuple = cur.fetchone()

            conn.commit()
            cur.close()

            if input_tuple:
                for _index, _name in enumerate(column_names):
                    _type = data_types[_index]
                    _input_value = input_tuple[_index]
                    _output_value = _type(_input_value)
                    values.append(_output_value)

        except OperationalError as _err:
            LOGGER.error(f"POS OperationalError {case_msg} Error: {_err}")
        except ProgrammingError as _err:
            LOGGER.error(f"POS ProgrammingError {case_msg} Error: {_err}")
        except DatabaseError as _err:
            LOGGER.error(f"POS DatabaseError {case_msg} Error: {_err}")
        except Exception as _err:
            LOGGER.error(f"Some error {case_msg} Error: {_err}")
        else:
            return column_names, values
        raise RuntimeError(f"POS FAILED func '_query_type_id_nnn' {case_msg}")

    def _import_parameters_json_from_nas(self, eo: int, project_dir_name: str, operation_dir_name: str) -> dict:
        # LOGGER.info("START func '_import_previous_operation_parameters'")
        case_msg = "Failed when importing operation parameters from 'parameters.json' located on NAS"

        try:
            nas_dir: str = self.config['nas']['absolute_path']
            filepath = os.path.join(nas_dir, project_dir_name, operation_dir_name, 'parameters.json')

            assert smbclient.path.isfile(filepath), f"File '{filepath}' not found for 'execution_order'={eo}"

            with smbclient.open_file(filepath, encoding='utf-8') as json_file:
                operation_param = json.load(json_file)
                assert operation_param, f"File '{filepath}' is empty for 'execution_order'={eo}"

        except AssertionError as _err:
            LOGGER.error(f"{case_msg} with AssertionError: {_err}")
        except Exception as _err:
            LOGGER.error(f"{case_msg} with Error: {_err}")
        else:
            return operation_param
        raise RuntimeError(case_msg)

    def _connect_to_file_server(self):
        """
        Check if an SMB network path is accessible.
        :return: True if accessible, False otherwise.
        """
        try:

            fs = self.config['nas']

            smbclient.reset_connection_cache()
            smbclient.ClientConfig(username=fs['login_name'], password=fs['login_password'])

            smb_share = rf"\\{fs['ip']}\{fs['public_dir']}"

            test_dir_name = f"simulation_test_{self.config['server']['id']}"

            file_server_test_dir = fr"{smb_share}\{test_dir_name}"

            smbclient.mkdir(file_server_test_dir)
            smbclient.rmdir(file_server_test_dir)

        except KeyError as _err:
            LOGGER.error(f"POS KeyError: {_err}")
        except Exception as _err:
            LOGGER.error(f"POS Exception: {_err}")
        else:
            return
        raise RuntimeError(f"POS FAILED func '_assert_is_file_server_accessible'")

    def _query_server_pre_main_fix_broken_records_after_server_crash(self):
        case_msg = "Failed trying UPDATE server_pre_main SET post_status='error' WHERE post_server_id IS NOT NULL"

        query = """
        UPDATE server_pre_main
            SET 
                post_status = 'queue'::post_status_enum,
                post_server_id = DEFAULT,
                post_time_started = DEFAULT
            WHERE post_server_id = %s
            RETURNING process_version_id, execution_order;"""

        conn = self.get_connection()

        try:
            server_id = self.config['server']['id']

            cur = conn.cursor()
            cur.execute(query, (server_id,))
            pvid_eo_tuples = cur.fetchmany()
            conn.commit()
            cur.close()

        except OperationalError as _err:
            LOGGER.error(f"{case_msg} with OperationalError: {_err}")
        except DatabaseError as _err:
            LOGGER.error(f"{case_msg} with DatabaseError: {_err}")
        except KeyError as _err:
            LOGGER.error(f"{case_msg} with KeyError: {_err}'.")
        except Exception as _err:
            LOGGER.error(f"{case_msg} with Error: {_err}")
        else:
            if pvid_eo_tuples:
                pvid_eo_list_str = ', '.join([f"{pvid}/{eo}" for pvid, eo in pvid_eo_tuples])
                LOGGER.info(f"POS {pvid_eo_list_str}: "
                            f"OK UPDATED server_pre_main SET post_status='error' for {len(pvid_eo_tuples)} "
                            f"broken records. The broken records left probably after the Server crash.")
            return
        raise RuntimeError(case_msg)

    def _convert_dict_values_to_json_compatible_types(self, param: dict):
        """Converts all Postgres SQL data types not supported by json.dumps() to string in place."""
        case_msg = "Failed converting all Postgres SQL data types not supported by json.dumps() to string in place"
        try:
            for key, value in param.items():
                if isinstance(value, dict):
                    self._convert_dict_values_to_json_compatible_types(value)
                elif isinstance(value, bytes):
                    param[key] = str(bytes(value))
                elif isinstance(value, datetime.datetime):
                    param[key] = value.strftime("%m/%d/%Y, %H:%M:%S")
                elif isinstance(value, set):
                    param[key] = list(value)
                elif isinstance(value, StringDtype):
                    param[key] = str(value)
                elif isinstance(value, Int64Dtype):
                    param[key] = int(value)
                elif isinstance(value, Int16Dtype):
                    param[key] = int(value)
                elif isinstance(value, Int32Dtype):
                    param[key] = int(value)
                elif isinstance(value, Float64Dtype):
                    param[key] = float(value)
        except Exception as _err:
            LOGGER.error(f"{case_msg} with Exception: {_err}")
            raise RuntimeError(f"{case_msg} with Exception: {_err}")

    def connect_to_smb(self, relative_path) -> tuple[Connection, Session, TreeConnect, str]:

        fs = self.config['nas']
        server = fs['ip']
        public_dir = fs['public_dir']
        port = 445
        username = fs['login_name']
        password = fs['login_password']
        smb_share = rf"\\{server}\{public_dir}\{relative_path}"

        smb_connection = Connection(uuid.uuid4(), server, port)
        smb_connection.connect()

        try:
            smb_session = Session(smb_connection, username, password)
            smb_session.connect()

            smb_tree = TreeConnect(smb_session, smb_share)
            smb_tree.connect()

        except Exception as _err:
            LOGGER.error(f"Failed to connect to SMB server '{server}': {_err}")
        else:
            return smb_connection, smb_session, smb_tree, smb_share
        raise RuntimeError("Error in func 'connect_to_smb'")

    @staticmethod
    def smb_open_file(smb_tree: TreeConnect, file_name: str) -> Open:
        try:
            # ensure file is created, get maximal access, and set everybody read access
            max_req = SMB2CreateContextRequest()
            max_req["buffer_name"] = CreateContextName.SMB2_CREATE_QUERY_MAXIMAL_ACCESS_REQUEST
            max_req["buffer_data"] = SMB2CreateQueryMaximalAccessRequest()

            # create security buffer that sets the ACL for everyone to have read access
            everyone_sid = SIDPacket()
            everyone_sid.from_string("S-1-1-0")

            ace = AccessAllowedAce()
            ace["mask"] = AccessMask.GENERIC_ALL
            ace["sid"] = everyone_sid

            acl = AclPacket()
            acl["aces"] = [ace]

            sec_desc = SMB2CreateSDBuffer()
            sec_desc["control"].set_flag(SDControl.SELF_RELATIVE)
            sec_desc.set_dacl(acl)
            sd_buffer = SMB2CreateContextRequest()
            sd_buffer["buffer_name"] = CreateContextName.SMB2_CREATE_SD_BUFFER
            sd_buffer["buffer_data"] = sec_desc

            create_contexts = [max_req, sd_buffer]

            open_file = Open(smb_tree, file_name)
            open_info = open_file.create(
                ImpersonationLevel.Impersonation,
                FilePipePrinterAccessMask.GENERIC_READ | FilePipePrinterAccessMask.GENERIC_WRITE,
                FileAttributes.FILE_ATTRIBUTE_NORMAL,
                ShareAccess.FILE_SHARE_READ | ShareAccess.FILE_SHARE_WRITE,
                CreateDisposition.FILE_OVERWRITE_IF,
                CreateOptions.FILE_NON_DIRECTORY_FILE,
                create_contexts,
            )

            # as the raw structure 'maximal_access' is an IntField, we create our own
            # flag field, set the value and get the human-readable string
            max_access = FlagField(size=4, flag_type=FilePipePrinterAccessMask, flag_strict=False)
            max_access.set_value(open_info[0]["maximal_access"].get_value())
            smb_share = smb_tree.share_name
            LOGGER.info("Maximum access mask for file %s\\%s: %s", smb_share, file_name, max_access)

        except Exception as _err:
            LOGGER.error(f"Failed to open file '{file_name}': {_err}")
            raise RuntimeError(f"Error in func 'smb_open_file'")
        else:
            return open_file

    def smb_write(self, relative_path: str, file_name: str, data: str):

        assert data is not None and data != '', "Data is empty"
        smb_connection, smb_session, smb_tree, smb_share = self.connect_to_smb(relative_path)
        open_file = self.smb_open_file(smb_tree, file_name)

        try:
            open_file.write(data.encode("utf-8"), 0)
            open_file.close(False)

        finally:
            smb_connection.disconnect(True)

    def smb_read(self, relative_path, file_name):

        smb_connection, smb_session, smb_tree, smb_share = self.connect_to_smb(relative_path)
        open_file = self.smb_open_file(smb_tree, file_name)

        try:
            file_text = open_file.read(0, 1024)
            LOGGER.info("Text of file %s\\%s: %s", smb_share, file_name, file_text.decode("utf-8"))
            open_file.close(False)
            return file_text

        finally:
            smb_connection.disconnect(True)

    def smb_read_and_delete(self, relative_path, file_name, data):

        smb_connection, smb_session, smb_tree, smb_share = self.connect_to_smb(relative_path)

        try:
            # read and delete a file in a single SMB packet instead of 3
            file_open = Open(smb_tree, file_name)
            delete_msgs = [
                file_open.create(
                    ImpersonationLevel.Impersonation,
                    FilePipePrinterAccessMask.GENERIC_READ | FilePipePrinterAccessMask.DELETE,
                    FileAttributes.FILE_ATTRIBUTE_NORMAL,
                    0,
                    CreateDisposition.FILE_OPEN,
                    CreateOptions.FILE_NON_DIRECTORY_FILE | CreateOptions.FILE_DELETE_ON_CLOSE,
                    send=False,
                ),
                file_open.read(0, len(data), send=False),
                file_open.close(False, send=False),
            ]
            requests = smb_connection.send_compound(
                [x[0] for x in delete_msgs], smb_session.session_id, smb_tree.tree_connect_id, related=True
            )
            responses = []
            for i, request in enumerate(requests):
                response = delete_msgs[i][1](request)
                responses.append(response)
            LOGGER.info("Text of file when reading/deleting in 1 request: %s", responses[1].decode("utf-8"))

        finally:
            smb_connection.disconnect(True)

    def smb_directory_management(self, relative_path: str):

        dir_name = "directory"

        smb_connection, smb_session, smb_tree, smb_share = self.connect_to_smb(relative_path)

        try:

            # ensure directory is created
            dir_open = Open(smb_tree, dir_name)
            dir_open.create(
                ImpersonationLevel.Impersonation,
                DirectoryAccessMask.GENERIC_READ | DirectoryAccessMask.GENERIC_WRITE,
                FileAttributes.FILE_ATTRIBUTE_DIRECTORY,
                ShareAccess.FILE_SHARE_READ | ShareAccess.FILE_SHARE_WRITE,
                CreateDisposition.FILE_OPEN_IF,
                CreateOptions.FILE_DIRECTORY_FILE,
            )

            # create some files in dir and query the contents as part of a compound
            # request
            directory_file = Open(smb_tree, r"%s\file.txt" % dir_name)
            directory_file.create(
                ImpersonationLevel.Impersonation,
                FilePipePrinterAccessMask.GENERIC_WRITE | FilePipePrinterAccessMask.DELETE,
                FileAttributes.FILE_ATTRIBUTE_NORMAL,
                ShareAccess.FILE_SHARE_READ,
                CreateDisposition.FILE_OVERWRITE_IF,
                CreateOptions.FILE_NON_DIRECTORY_FILE | CreateOptions.FILE_DELETE_ON_CLOSE,
            )

            compound_messages = [
                directory_file.write(b"Hello World", 0, send=False),
                dir_open.query_directory("*", FileInformationClass.FILE_NAMES_INFORMATION, send=False),
                directory_file.close(False, send=False),
                dir_open.close(False, send=False),
            ]
            requests = smb_connection.send_compound([x[0] for x in compound_messages],
                                                    smb_session.session_id,
                                                    smb_tree.tree_connect_id)
            responses = []
            for i, request in enumerate(requests):
                response = compound_messages[i][1](request)
                responses.append(response)

            dir_files = []
            for dir_file in responses[1]:
                dir_files.append(dir_file["file_name"].get_value().decode("utf-16-le"))

            LOGGER.info("Directory '%s\\%s' contains the files: %s",
                        smb_share, dir_name,
                        ", ".join(repr(file) for file in dir_files))

            # delete a directory (note the dir needs to be empty to delete on close)
            dir_open = Open(smb_tree, dir_name)
            delete_msgs = [
                dir_open.create(
                    ImpersonationLevel.Impersonation,
                    DirectoryAccessMask.DELETE,
                    FileAttributes.FILE_ATTRIBUTE_DIRECTORY,
                    0,
                    CreateDisposition.FILE_OPEN,
                    CreateOptions.FILE_DIRECTORY_FILE | CreateOptions.FILE_DELETE_ON_CLOSE,
                    send=False,
                ),
                dir_open.close(False, send=False),
            ]
            delete_reqs = smb_connection.send_compound(
                [x[0] for x in delete_msgs], sid=smb_session.session_id, tid=smb_tree.tree_connect_id, related=True
            )
            for i, request in enumerate(delete_reqs):
                response = delete_msgs[i][1](request)
        finally:
            smb_connection.disconnect(True)

    def validate_config(self):
        try:
            # This will raise a ValidationError if the config is invalid
            ConfigSchema(**self.config)
        except ValidationError as e:
            print("Configuration validation failed:")
            print(e)
            raise
