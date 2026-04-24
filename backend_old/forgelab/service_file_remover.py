import os
import shutil
import threading
import logging
import time

from forgelab.common.file_operations import extract_project_version_id_from_project_dir_name, generate_project_dir_name
from forgelab.config import config


LOGGER = logging.getLogger(__name__)


class GarbageFilesRemover(threading.Thread):
    """Thread class with a stop() method. The thread itself has to check
    regularly for the stopped() condition."""

    def __init__(self,  *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._stop_event = threading.Event()
        self._local_dir: str = config.server['local_dir']
        self._cycle_time: float = 30.0
        self._exclude_file_extensions: list = ['json', 'db', 'tmp', 'dat', 'prob']
        self._exclude_dirs: list = ['pptx', 'images',]


    def stop(self):
        LOGGER.debug("GARBAGE REMOVER 'stop' method is called")
        self._stop_event.set()

    def is_stopped(self):
        return self._stop_event.is_set()

    def run(self):
        while not self.is_stopped():
            self._silent_projects_worker()
            time.sleep(self._cycle_time)
        LOGGER.info("GARBAGE REMOVER stopped")

    def _silent_projects_worker(self):
        try:
            self.silent_remove_files_in_root_dir()
            self.silent_remove_dirs_in_root_dir()
        except Exception as _err:
            LOGGER.warning(f"{type(_err).__name__}: {_err}")

    def silent_remove_files_in_root_dir(self):
        removed_files = []
        failed_files = []
        try:
            file_names = [f.name for f in os.scandir(self._local_dir) if f.is_file()]
            for _f in file_names:
                try:
                    file_path = os.path.join(self._local_dir, _f)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                except FileNotFoundError:
                    failed_files.append(_f)
                else:
                    removed_files.append(_f)
            if removed_files or failed_files:
                rf = f" {len(removed_files)} have been removed ({', '.join(removed_files)})." if removed_files else ""
                ff =  f" {len(failed_files)} have been removed ({', '.join(failed_files)})." if failed_files else ""
                LOGGER.warning(f"Non project files found in local simulation dir {self._local_dir}.{rf}{ff}")
        except Exception as _err:
            LOGGER.warning(f"{type(_err).__name__}: {_err}")

    def silent_remove_dirs_in_root_dir(self):
        found_pvid = []
        found_non_project_dirs = []
        try:
            dir_names = [f.name for f in os.scandir(self._local_dir) if f.is_dir()]
            for project_dir_name in dir_names:
                try:
                    pvid = extract_project_version_id_from_project_dir_name(project_dir_name)
                except Exception:
                    found_non_project_dirs.append(project_dir_name)
                else:
                    found_pvid.append(pvid)
            # ----------------------------------------------------------------------------
            self._silent_remove_non_project_dirs(found_non_project_dirs)
            finished_pvid = self.silent_query_completely_finished(found_pvid)
            non_finished_pvid = list(set(found_pvid).difference(set(finished_pvid)))
            self._silent_remove_completely_finished_projects(finished_pvid)
            self._silent_keep_project_dirs_remove_operation_dirs(non_finished_pvid)
        except Exception as _err:
            LOGGER.warning(f"{type(_err).__name__}: {_err}")

    def _silent_remove_non_project_dirs(self, dir_names_list: list):
        try:
            for dir_name in dir_names_list:
                dir_path = os.path.join(self._local_dir, dir_name)
                shutil.rmtree(dir_path, ignore_errors=True)
                LOGGER.warning(f"Removed non project dir '{dir_path}'")
        except Exception as _err:
            LOGGER.warning(f"{type(_err).__name__}: {_err}")

    def _silent_remove_completely_finished_projects(self, finished_pvid: list[int]):
        if not finished_pvid:
            return []
        try:
            for pvid in finished_pvid:
                project_dir_name = generate_project_dir_name(pvid)
                dir_path = os.path.join(self._local_dir, project_dir_name)
                if os.path.isdir(dir_path):
                    shutil.rmtree(dir_path, ignore_errors=True)
                    LOGGER.warning(f"Removed completely finished project '{dir_path}'")
        except Exception as _err:
            LOGGER.warning(f"{type(_err).__name__}: {_err}")
            return []

    def _silent_keep_project_dirs_remove_operation_dirs(self, found_projects_pvid_list: list[int]):
        if not found_projects_pvid_list:
            return []
        conn = config.get_connection()
        try:
            with conn.cursor() as cur:
                query = """
                SELECT  process_version_id, execution_order, post_status, sub_operation_relative_path 
                FROM server_pre_main
                WHERE 
                    process_version_id = ANY(%s) 
                    AND simulation_status = 'finished'
                ORDER BY process_version_id, execution_order;
                """
                stripped_query = ' '.join([_s.strip() for _s in query.splitlines()])
                cur.execute(stripped_query, (found_projects_pvid_list, ))
                pvid_eo_status_path_tuples = cur.fetchall()
                conn.commit()
            if not pvid_eo_status_path_tuples:
                return []
        except Exception as _err:
            LOGGER.warning(f"{type(_err).__name__}: {_err}")
            return []
        finally:
            config.put_connection(conn)
        try:
            for pvid in set([pvid for (pvid, _, _, _) in pvid_eo_status_path_tuples]):
                eo_status_path_tuples = [(_eo, _status, _path) for (_pvid, _eo, _status, _path) in pvid_eo_status_path_tuples if _pvid == pvid]
                last_simulation_finished_eo = max([_eo for (_eo, _, _) in eo_status_path_tuples])
                for eo, post_status, exclude_path in eo_status_path_tuples:
                    project_dir_name, operation_dir_name, last_sub_operation_dir_name = exclude_path.split(os.sep)[:3]
                    operation_path = os.path.join(self._local_dir, project_dir_name, operation_dir_name)
                    if not os.path.isdir(operation_path):
                        continue
                    if post_status == 'finish' and eo != last_simulation_finished_eo:
                        shutil.rmtree(operation_path, ignore_errors=True)
                        LOGGER.warning(f"Removed operation dir '{operation_path}'")
                    else:
                        sub_operation_dir_names = [f.name for f in os.scandir(operation_path) if f.is_dir()]
                        exclude_dir_names = self._exclude_dirs + [last_sub_operation_dir_name]
                        remove_sub_op_dir_names = tuple(set(sub_operation_dir_names).difference(set(exclude_dir_names)))
                        for sub_operation_dir_name in remove_sub_op_dir_names:
                            remove_sub_operation_path = os.path.join(operation_path, sub_operation_dir_name)
                            shutil.rmtree(remove_sub_operation_path, ignore_errors=True)
                            LOGGER.warning(f"Removed sub operation dir '{remove_sub_operation_path}'")
        except Exception as _err:
            LOGGER.warning(f"{type(_err).__name__}: {_err}")

    @staticmethod
    def silent_query_completely_finished(pvid_list: list[int]) -> list:
        if not pvid_list:
            return []
        conn = config.get_connection()
        try:
            with conn.cursor() as cur:
                query = """
                SELECT process_version_id 
                FROM server_pre_main
                WHERE process_version_id = ANY(%s)
                GROUP BY process_version_id
                    HAVING 
                        BOOL_AND(simulation_status = 'finished' AND post_status = 'finished');"""
                stripped_query = ' '.join([_s.strip() for _s in query.splitlines()])
                cur.execute(stripped_query, (pvid_list, ))
                result = cur.fetchall()
                conn.commit()
            return [row[0] for row in result] if result else []
        except Exception as _err:
            LOGGER.warning(f"{type(_err).__name__}: {_err}")
            return []
        finally:
            config.put_connection(conn)
