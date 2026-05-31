# print(f'__file__={__file__:<35} | __name__={__name__:<25} | __package__={str(__package__):<25}')
from __future__ import annotations

import logging
import os
import queue
import signal
import sys
import time
from multiprocessing import Queue, Semaphore, Manager
from smbclient import reset_connection_cache

from forgelab.config import config
from forgelab.notifications_listener_service import NotificationsListenerService
# from forgelab.plot_service import PlotWorker
from forgelab.service_file_remover import GarbageFilesRemover
from forgelab.srv_post.post_worker_class import PostWorker
from forgelab.srv_post.mayavi_worker_class import MayaviWorker
from forgelab.srv_pre.pre_worker_class import PreWorker
from forgelab.srv_solver.simulation_worker_class import SimulationWorker


LOGGER = logging.getLogger(__name__)

SENTRY: bool = True

last_query_timestamp = time.monotonic()


def signal_handler(signal_number, frame):
    """Signal Handler to process signal.SIGINT: CTRL + C"""
    global SENTRY
    SENTRY = False
    LOGGER.warning(
        f"The server received system signal: SignalNumber = '{str(signal_number)}', Frame = '{str(frame)}'."
        " The server cycle will break.")


def clean_fluent_bit_log_file():
    with open("C:\\fluent-bit\\logs\\tcp.0", "w") as _f:
        _f.write("")


def start():
    # LOGGER.info("START main infinite cycle of the Server till keyboard interruption.")
    # TODO: Removing solved passes from local PC works on fl-sim-3, but not on ADMIN-2

    signal.signal(signal.SIGINT, signal_handler)  # register signal with handler

    counter = 1

    while no_keyboard_interruption() and counter <= 2:  # Infinite loop to restart server after crash
        # LOGGER.info("START a new cycle of the Server instance.")

        try:
            # clean_fluent_bit_log_file()
            config.initialize()

            _remove_old_project_files()
            _query_update_server_pre_main_set_post_status_queue(config.server['id'])
            pvid_tuple = _query_update_process_versions_set_simulation_status_queue(config.server['id'])
            _query_update_server_pre_main_set_simulation_status_stop(pvid_tuple)
            # TODO: add function to restore 'error' -> 'queue' post_status

            _main_cycle_body()

            _query_deactivate_server_id_except_warning()
            reset_connection_cache()  # smbclient
        except Exception as _err:
            LOGGER.warning(f"{type(_err).__name__}: {_err}")
        finally:
            _restart_server()

        time.sleep(5)
        counter += 1

    LOGGER.info("FINISHED main infinite cycle of the Server because of keyboard interruption.")


def _main_cycle_body():
    """
    Every cycle this function does actions:
    1. Run or restart new simulations:
        - Wait for a SQL notification for short timeout, otherwise go step #2.
        - Count free slots for new simulations.
        - Query for 'process_versions' to change 'simulation_status' from 'queue' to 'run'.
        - Get 'process_version_id' and 'execution_order' for new simulations.
        - Restart simulations waiting in threads_keeper['queue'].
        - Run new simulations.
    2. Check running & finished simulations:
    :return:
    """
    # ---------------------- NUMBER OF WORKERS ---------------------------
    pre_workers_count = config.services['pre']['max_threads_count']
    sim_workers_count = config.services['simulation']['max_threads_count']
    post_workers_count = config.services['post']['max_threads_count']
    mayavi_workers_count = config.services['mayavi']['max_threads_count']

    # ------------------------------- QUEUE ------------------------------
    notify_services: list[str] = [n for n, v
                                  in config.services.items()
                                  if v['is_service_allowed_to_run'] and v['notify_channel']]
    notify_queues: dict[str, Queue] = {service_name: Queue() for service_name in notify_services}
    pre_queue: Queue = Queue()
    pre_local_queue: list = []
    sim_queue: Queue = Queue()
    post_queue: Queue = Queue()
    mayavi_queue: Queue = Queue()
    # plot_queue: Queue = Queue()

    # ------------------------ GARBAGE REMOVER --------------------------
    garbage_remover = GarbageFilesRemover()
    garbage_remover.start()

    # ------------------- NOTIFICATION LISTENER -------------------------
    notification_listener = NotificationsListenerService(notify_queues)
    notification_listener.start()

    # ------------------------ MAYAVI MANAGER ----------------------------
    mayavi_manager: Manager = Manager()
    mayavi_status: dict = mayavi_manager.dict()  # Shared dictionary to track task statuses

    # ------------------------- SEMAPHORE --------------------------------
    pre_semaphore: Semaphore = Semaphore(pre_workers_count)
    sim_semaphore: Semaphore = Semaphore(sim_workers_count)
    mayavi_semaphore: Semaphore = Semaphore(mayavi_workers_count)
    post_semaphore: Semaphore = Semaphore(post_workers_count)

    # --------------------------- PLOT WORKERS ---------------------------
    # plot_service = PlotWorker(1, plot_queue)
    # plot_service.start()

    # --------------------------- PRE WORKERS ----------------------------
    pre_workers: list[PreWorker] = [PreWorker(i + 1, pre_queue, pre_semaphore)
                                    for i in range(pre_workers_count)]
    for i in range(pre_workers_count):
        pre_workers[i].start()

    # --------------------- SIMULATION WORKERS ---------------------------
    sim_workers: list[SimulationWorker] = [SimulationWorker(i + 1, sim_queue, sim_semaphore)
                                           for i in range(sim_workers_count)]
    for i in range(sim_workers_count):
        sim_workers[i].start()

    # ------------------------- MAYAVI WORKERS ---------------------------
    mayavi_workers: list[MayaviWorker] = [MayaviWorker(i + 1, mayavi_queue, mayavi_status, mayavi_semaphore)
                                          for i in range(mayavi_workers_count)]
    for i in range(mayavi_workers_count):
        mayavi_workers[i].start()

    # --------------------------- POST WORKERS ---------------------------
    post_workers: list[PostWorker] = [PostWorker(i + 1, post_queue, post_semaphore,
                                                 mayavi_queue, mayavi_manager, mayavi_status, mayavi_semaphore)
                                      for i in range(post_workers_count)]
    for i in range(post_workers_count):
        post_workers[i].start()

    # ---------------------------- MAIN CYCLE ---------------------------
    conn = config.get_connection()
    try:
        while True:
            is_timeout: bool = _timeout_query_missed_tasks()

            # ---------------------------- SIMULATION ---------------------------
            if not notify_queues['simulation'].empty() or is_timeout:
                if sim_semaphore.acquire(block=False):
                    pvid, eo, task_location = query_update_process_versions_set_simulation_status_run()
                    if pvid == 0:
                        sim_semaphore.release()
                    else:
                        sim_queue.put((pvid, eo, task_location,))

            # -------------------------------- PRE ------------------------------

            # PRE: Read Notify queue and Move notifies to Local queue
            while not notify_queues['pre'].empty():
                try:
                    pvid = notify_queues['pre'].get_nowait()
                    if pvid not in pre_local_queue:
                        pre_local_queue.append(pvid)
                except queue.Empty:
                    break

            # PRE: Start new tasks
            if pre_local_queue:
                if pre_semaphore.acquire(block=False):
                    pvid = pre_local_queue.pop(0)
                    if _query_is_notify_approved(pvid):
                        # Start new workers
                        pre_queue.put((pvid,))
                    else:
                        pre_semaphore.release()

            # -------------------------------- POST -----------------------------
            if not notify_queues['post'].empty() or is_timeout:
                if post_semaphore.acquire(block=False):
                    pvid, eo, eid = _query_update_server_pre_main_post_set_run()
                    if pvid == 0:
                        post_semaphore.release()
                    else:
                        post_queue.put((pvid, eo, eid,))

            # ------------------------------- SLEEP -----------------------------
            time.sleep(0.1)

    except KeyboardInterrupt:
        LOGGER.warning("KeyboardInterrupt received")
        return
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        config.is_error = True
        return
    finally:
        config.put_connection(conn)

        # --------------- SEND STOP SIGNAL TO THREADS & PROCESSES -----------------------
        garbage_remover.stop()
        notification_listener.stop()

        # plot_queue.put((None,))
        [sim_queue.put((0, 0, "",)) for _ in sim_workers]
        [post_queue.put((0, 0, 0,)) for _ in post_workers]
        [mayavi_queue.put(({}, 0, 0,)) for _ in mayavi_workers]

        # ------------------------ WAIT FOR NORMAL TERMINATING --------------------------
        garbage_remover.join()
        notification_listener.join()

        [p.join() for p in sim_workers]
        [p.join() for p in post_workers]
        [p.join() for p in mayavi_workers]

        # ------------------------------ CLOSE QUEUE ------------------------------------
        sim_queue.close()
        post_queue.close()
        mayavi_queue.close()
        for q in notify_queues.values():
            q.close()

        # -------------------------------- LOG & EXIT -----------------------------------
        LOGGER.info("All Simulation workers have been shut down.")


def cycle_error_message(_err, trigger_set_of_notified_services,
                        queue_e_o, queue_pvid, queue_status, run_e_o, run_pvid,
                        run_status):
    if bool(trigger_set_of_notified_services):
        notify_msg = f"Notification received for {', '.join(trigger_set_of_notified_services)}"
    else:
        notify_msg = "No notification received"
    r_t_status = (f"Last Running Thread had status='{run_status}', "
                  f"'pvid'= {run_pvid}, 'execution_order'= {run_e_o}; ")
    r_t_msg = r_t_status if any((run_status, run_pvid, run_e_o)) else "Running threads are empty."
    q_t_status = (f"Last Queue Thread had status='{queue_status}', "
                  f"'pvid'= {queue_pvid}, 'execution_order'= {queue_e_o}.")
    q_t_msg = q_t_status if any((queue_status, queue_pvid, queue_e_o)) else "Queue threads are empty."
    err_msg = f"FAILED with {notify_msg}. {r_t_msg} {q_t_msg} with Error: {_err}"
    return err_msg


def terminate_server_now():
    LOGGER.critical("Terminate command received. Stopping server...")
    sys.exit(1)


def no_keyboard_interruption() -> bool:
    """Returns True if server is allowed to run. Otherwise, returns False."""
    if SENTRY:
        LOGGER.info("New server instance will be started.")
        return True
    LOGGER.error("New server instance starting is forbidden. Restarting server is forbidden. Terminating the "
                 "server...")
    return False


def no_critical_errors() -> bool:
    """Returns True if server is allowed to run. Otherwise, returns False."""
    if not SENTRY:
        LOGGER.error("Keyboard interruption received. The main server cycle is terminated. Finalizing the server "
                     "instance...")
        return False

    if config.is_error:
        LOGGER.error("Server has 'is_error' = True. Server cycle will be interrupted to stop the server.")
        return False
    return True


def _get_projects_dir_public() -> str:
    """Receives '*.json' file name. If error, stops server."""
    try:
        host_name = config.server['hostname']
        project_dir = config.server['projects_dir']
        dir_public = f"\\\\{host_name}\\{project_dir}"
        assert os.path.isdir(dir_public), f"Can't find public simulation project directory '{dir_public}'"
        return dir_public
    except Exception as _err:
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        raise


def _timeout_query_missed_tasks():
    global last_query_timestamp
    is_timer = False
    try:
        if time.monotonic() >= last_query_timestamp:
            last_query_timestamp += config.server['timeout_query_missed_tasks']
            is_timer = True
        return is_timer
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def query_update_process_versions_set_simulation_status_run() -> tuple[int, int, str]:
    pvid, eo, task_location = __query_update_process_versions_set_simulation_status_run('local')
    if pvid == 0:
        pvid, eo, task_location = __query_update_process_versions_set_simulation_status_run('remote')
    return pvid, eo, task_location


def __query_update_process_versions_set_simulation_status_run(task_location: str) -> tuple[int, int, str]:

    allowed_locations = ('remote', 'local',)

    assert isinstance(task_location, str), \
        f"Input variable 'task_location' has type {type(task_location)} but must be type of 'str'."
    assert task_location in allowed_locations, (
        f"Input variable 'task_location' has value {task_location}, "
        f"but allowed values are {', '.join(allowed_locations)}.")

    try:
        development_condition = "" if config.server['is_development_mode'] else "NOT"
        server_id = config.server['id']
    except Exception as _err:
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        raise

    conn = config.get_connection()
    try:
        query_remote = f"""
            WITH sp AS (
                SELECT process_version_id , execution_order 
                FROM process_versions 
                WHERE 
                    simulation_queue_row_number IS NOT NULL  
                    AND (
                        simulation_server_id IS NULL 
                        OR 
                        simulation_server_id = (
                            SELECT id FROM servers WHERE type = 'simulation' AND hostname = 'QUEUE' LIMIT 1)
                    )
                    AND simulation_status = 'queue' 
                    AND name {development_condition} LIKE %(process_version_name)s 
                ORDER BY simulation_queue_number ASC 
                LIMIT 1
            )"""

        query_local = f"""
            WITH sp AS (
                SELECT process_version_id, execution_order 
                FROM process_versions 
                WHERE 
                    simulation_queue_row_number = 1
                    AND simulation_server_id = %(server_id)s 
                    AND simulation_status = 'queue' 
                    AND name {development_condition} LIKE %(process_version_name)s 
                LIMIT 1
            )"""

        query_end = """
            UPDATE process_versions pv
            SET 
                simulation_status = 'run'::simulation_status_enum, 
                simulation_server_id = %(server_id)s, 
                ran_at = CASE WHEN sp.execution_order = 0 THEN NOW() ELSE pv.ran_at END 
            FROM sp
            WHERE pv.process_version_id = sp.process_version_id 
            RETURNING sp.process_version_id, sp.execution_order;"""

        query = (query_remote  if task_location == 'remote' else query_local) + query_end
        stripped_query = ' '.join([_s.strip() for _s in query.splitlines()])
        query_param = {
            'server_id': server_id,
            'process_version_name': '[DEV]%'}

        # query_mogrify = cur.mogrify(stripped_query, query_param)
        with conn.cursor() as cur:
            cur.execute(stripped_query, query_param)
            # Check if any rows were affected
            is_any_record_updated = cur.rowcount > 0
            pvid, eo = cur.fetchone() if is_any_record_updated else (0, 0,)
            conn.commit()

        if is_any_record_updated:
            LOGGER.info(
                f"[{pvid}][{eo}/X] {task_location = } SUCCESS "
                f"UPDATE process_versions SET simulation_status = 'run', simulation_server_id = {server_id}")
        # else:
        #     LOGGER.info("                      *                      ")

        return pvid, eo, task_location

    except Exception as _err:
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        if task_location == 'remote':
            raise RuntimeError(
                f"FAILED to UPDATE process_versions SET simulation_status = 'run' "
                f"WHERE simulation_queue_row_number IS NOT NULL "
                f"AND (simulation_server_id IS NULL OR simulation_server_id = 3) "
                f"AND simulation_status = 'queue' "
                f"AND name {development_condition} LIKE '[DEV]%'")
        else:
            raise RuntimeError(
                f"FAILED to UPDATE process_versions SET simulation_status = 'run' "
                f"WHERE simulation_queue_row_number = 1 "
                f"AND simulation_server_id = {server_id} "
                f"AND simulation_status = 'queue' "
                f"AND name {development_condition} LIKE '[DEV]%'")
    finally:
        config.put_connection(conn)


def _query_update_process_versions_set_simulation_status_queue_where_run_and_server_id_3():
    """
    Call this function before terminating the server.
    The function marks all simulations ran at the server as waiting in Queue on File storage.
    All data calculated will be lost.
    Queries 'process_versions' and update all records where 'simulation_server_id' = to the server's ID.
    Sets 'dp_path_name' to NULL and 'simulation_server_id' to default server emulating queue.
    """
    # LOGGER.info("starting func 'query_delete_process_versions'")
    try:
        _id = config.server['id']
    except Exception as _err:
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        raise
    conn = config.get_connection()
    try:
        with conn.cursor() as cur:
            query = """
                UPDATE process_versions 
                SET 
                    simulation_status = 
                        CASE 
                            WHEN simulation_status = 'run' 
                            THEN 'queue'::simulation_status_enum 
                            ELSE simulation_status 
                        END,
                    simulation_server_id = 
                        (SELECT id FROM servers WHERE type = 'simulation' and hostname = 'QUEUE' LIMIT 1)
                WHERE simulation_server_id = %s;"""
            cur.execute(query, (_id,))
            conn.commit()
    except Exception as _err:
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        raise RuntimeError(
            f"FAILED updating 'process_versions' and removing assignment to server 'id' = {_id} "
            f"due to the server Terminating and removing all projects data.")
    finally:
        config.put_connection(conn)


def _query_deactivate_server_id_except_warning():
    """
    Set the 'is_active' = FALSE in the 'servers' table.
    """
    try:
        _id = config.server['id']
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise
    conn = config.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE servers SET is_active = FALSE, time_finished = NOW() WHERE id = %s;", (_id,))
            conn.commit()
    except Exception as _err:
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        LOGGER.warning(f"FAILED UPDATE servers SET is_active = FALSE, time_finished = NOW() WHERE id = {_id}")
    finally:
        config.put_connection(conn)


def _restart_server():
    """
    Restart the PC neglecting all the running and hanging processes.
    """
    try:
        is_allow_restart = config.server['is_allow_restart']
    except KeyError as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise

    if is_allow_restart:
        LOGGER.info("Starting the server restarting procedure...")
        os.system("shutdown /r /t 0")
    else:
        LOGGER.info("'is_allow_restart' is False. Restarting the server is prohibited.")


def _query_get_post_operations_columns() -> list:
    """
    Receives 'post_operations' dict as result of simulation.
    Connects to SQL Server and update 'post_operations' table
    where 'process_version_id' = pvid and 'execution_order' = execution_order.
    Returns True if successful. Otherwise, returns False.
    """
    conn = config.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'post_operations';")
            rows = cur.fetchall()
            conn.commit()
        return [_name[0] for _name in rows]
    except Exception as _err:
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        raise
    finally:
        config.put_connection(conn)


def _substitute_previous_project_path_with_current(previous_param: dict) -> dict:
    try:
        previous_local_dir: str = previous_param['local_dir']
        local_dir: str = config.server['local_dir']

        corrected_previous_param = {}

        for key, value in previous_param.items():
            if isinstance(value, str) and '\\' in value:
                norm_path = os.path.normpath(value)
                new_value = norm_path.replace(previous_local_dir, local_dir)
                corrected_previous_param[key] = new_value
            else:
                corrected_previous_param[key] = value

        return corrected_previous_param

    except Exception as _err:
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        raise


def __logging_finished_whole_project_simulation():
    # _duration = duration_since(param['operation']['project_start_datetime'])
    # _hour = _duration // 3600.0
    # _min = _duration % 3600.0 // 60.0
    # LOGGER.info(
    #     "Simulation '%s' is finished at %s and total running time was %.0f hour %.0f min",
    #     param['project']['project_dir_name'],
    #     datetime.now().strftime('%H:%M:%S'),
    #     _hour,
    #     _min)
    pass


def _query_is_notify_approved(pvid: int) -> bool:
    try:
        assert isinstance(pvid, int), f"PVID type is {type(pvid)}, not 'int'"
        new_records = _query_delete_operations_changes(pvid)
        if not new_records:
            LOGGER.warning(f"Got notify for PVID = {pvid}, "
                           f"but 'operations_changes' SQL table doesn't have any record for this PVID")
            return False

        _id, pvid, is_editable, preview_status, run_switch_status, simulation_status = zip(*new_records)

        if not is_editable[0]:
            LOGGER.warning(f"Got notify for PVID = {pvid}, "
                           f"but ignore it because 'process_versions.is_editable' = FALSE")
            return False
        if run_switch_status[0]:
            LOGGER.warning(f"Got notify for PVID = {pvid}, "
                           f"but ignore it because 'process_versions.run_switch_status' = TRUE")
            return False
        if simulation_status[0] != 'stop':
            LOGGER.warning(f"Got notify for PVID = {pvid}, "
                           f"but ignore it because 'process_versions.simulation_status' <> 'stop' "
                           f"(='{simulation_status}')")
            return False
        return True
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise


def _query_delete_operations_changes(pvid: int) -> list[tuple[int, int, bool, str, bool, str]] | None:
    conn = config.get_connection()
    try:
        query = ("""
            WITH deleted_rows AS (
                DELETE FROM operations_changes
                WHERE process_version_id = %s
                RETURNING id, process_version_id
            )
            SELECT 
                dr.id,
                dr.process_version_id,
                pv.is_editable,
                pv.preview_status,
                pv.run_switch_status,
                pv.simulation_status
            FROM deleted_rows dr
            JOIN process_versions pv ON dr.process_version_id = pv.process_version_id;""")
        stripped_query = ' '.join([_s.strip() for _s in query.splitlines()])
        with conn.cursor() as cur:
            cur.execute(stripped_query, (pvid,))
            new_records = cur.fetchall()
            conn.commit()
        return new_records
    except Exception as _err:
        LOGGER.warning(f"{type(_err).__name__}: {_err}")
        raise
    finally:
        config.put_connection(conn)


def _query_update_server_pre_main_post_set_run() -> list:
    try:
        server_id = config.server['id']
        name_prefix_for_development_mode = config.server['process_version_name_prefix_for_development_mode']
        development_mode_trigger = "" if config.server['is_development_mode'] else "NOT"
        slots_count = 1
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise

    conn = config.get_connection()
    try:
        query = f"""
            UPDATE server_pre_main spm
                SET 
                    post_server_id = %(server_id)s, 
                    post_status = 'run'::post_status_enum, 
                    post_time_started = NOW(), 
                    post_time_finished = DEFAULT, 
                    post_images_abs_path = DEFAULT, 
                    post_pptx_abs_path = DEFAULT 
                FROM (
                    SELECT spm_inner.execution_id 
                    FROM server_pre_main spm_inner
                    JOIN process_versions pv 
                        ON spm_inner.process_version_id = pv.process_version_id 
                    WHERE 
                        spm_inner.post_server_id IS NULL 
                        AND spm_inner.post_status = 'queue' 
                        AND spm_inner.simulation_status = 'finished' 
                        AND pv.name {development_mode_trigger} LIKE '{name_prefix_for_development_mode}%%'
                    ORDER BY spm_inner.simulation_time_finished ASC 
                    LIMIT 1
                ) AS selected_spm
                WHERE spm.execution_id = selected_spm.execution_id
                RETURNING spm.process_version_id, spm.execution_order, spm.execution_id;
                """
        stripped_query = ' '.join([_s.strip() for _s in query.splitlines()])
        with conn.cursor() as cur:
            cur.execute(
                stripped_query,
                {'slots_count': slots_count,
                 'server_id': server_id,
                 'development_mode_trigger': development_mode_trigger,
                 'name_prefix_for_development_mode': name_prefix_for_development_mode})
            result = cur.fetchall() if cur.rowcount > 0 else []
            conn.commit()

        for pvid, eo, _ in result:
            LOGGER.info(f"{pvid}/{eo} UPDATE server_pre_main SET post_status = 'run', post_server_id = {server_id}")
        return result[0] if len(result) > 0 else (0, 0, 0,)
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise RuntimeError(
            f"FAILED to UPDATE server_pre_main SET post_status = 'run', post_server_id = {server_id} "
            f"WHERE post_server_id IS NULL AND post_status = 'queue' AND simulation_status = 'finished' "
            f"AND process_versions.name {development_mode_trigger} LIKE '{name_prefix_for_development_mode}%'")
    finally:
        config.put_connection(conn)


def _remove_old_project_files():
    """Remove project directory from the Server."""
    local_dir: str = config.server['local_dir']
    file_counter = 0
    dir_counter = 0

    def _remove(_dir):
        nonlocal file_counter
        nonlocal dir_counter
        if os.path.exists(_dir):
            for root, dirs, files in os.walk(os.path.normpath(_dir)):
                root: str
                for _file in files:
                    _file: str
                    os.remove(os.path.join(root, _file))
                    file_counter += 1
                for _dir in dirs:
                    _dir: str
                    abs_dir_path: str = os.path.join(root, _dir)
                    # Check if _dir is empty
                    if os.listdir(abs_dir_path):
                        _remove(abs_dir_path)
                    os.chmod(abs_dir_path, 0o777)
                    os.rmdir(abs_dir_path)
                    dir_counter += 1

    while True:
        try:
            _remove(local_dir)
        except Exception as _err:
            LOGGER.warning(f"{type(_err).__name__}: {_err}")
            LOGGER.warning(
                f"Wait for {config.server['file_remove_attempts_cycle_time_sec']} sec "
                f"and try again to remove content of dir {local_dir}")
            time.sleep(config.server['file_remove_attempts_cycle_time_sec'])
        else:
            break

    if file_counter > 0 or dir_counter > 0:
        LOGGER.info(f"OK removed {file_counter} files and {dir_counter} dirs in '{local_dir}'")


def _query_update_process_versions_set_simulation_status_queue(server_id: int) -> tuple:
    conn = config.get_connection()
    try:
        query = """
            UPDATE process_versions SET 
                simulation_status = 'queue'::simulation_status_enum,
                simulation_server_id = (
                    SELECT s.id FROM servers s WHERE s.type = 'simulation' AND s.hostname = 'QUEUE' LIMIT 1),
                ran_at = DEFAULT
            WHERE simulation_server_id = %s 
            RETURNING process_version_id;"""
        stripped_pv_query = ' '.join([_s.strip() for _s in query.splitlines()])

        with conn.cursor() as cur:
            cur.execute(stripped_pv_query, (server_id,))
            result = cur.fetchall() if cur.rowcount else []
            conn.commit()

        pvid_tuple = tuple(_r[0] for _r in result)

        if pvid_tuple:
            LOGGER.info(
                f"OK fixing {len(pvid_tuple)} broken records. "
                f"UPDATE process_versions SET simulation_status = 'queue' "
                f"WHERE process_version_id IN ({', '.join(map(str, pvid_tuple))}). "
                f"The broken records left probably after the Server crash.")
        return pvid_tuple
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise
    finally:
        config.put_connection(conn)


def _query_update_server_pre_main_set_simulation_status_stop(pvid_tuple: tuple):
    if not pvid_tuple:
        return
    conn = config.get_connection()
    try:
        query = """
            UPDATE server_pre_main SET
                simulation_status = 'stop'::simulation_status_enum
            WHERE 
                process_version_id = %s 
                AND simulation_status IN ('error', 'run')
            RETURNING process_version_id, execution_order;"""
        stripped_psm_query = ' '.join([_s.strip() for _s in query.splitlines()])

        with conn.cursor() as cur:
            cur.execute(stripped_psm_query, pvid_tuple)
            result = cur.fetchall() if cur.rowcount else []
            conn.commit()

        if result:
            pvid_str = ', '.join([f"{pvid}/{eo}" for pvid, eo in result])
            LOGGER.info(
                f"OK fixing {len(pvid_tuple)} broken records. "
                f"UPDATE server_pre_main SET simulation_status = 'stop' "
                f"WHERE process_version_id/execution_order IN ({pvid_str}). "
                f"The broken records left probably after the Server crash.")
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise
    finally:
        config.put_connection(conn)


def _query_update_server_pre_main_set_post_status_queue(server_id: int):
    if not server_id:
        return
    conn = config.get_connection()
    try:
        assert isinstance(server_id, int)
        assert server_id > 0

        query = """
            UPDATE server_pre_main SET
                post_server_id = NULL,
                post_status = CASE
                    WHEN simulation_status = 'finished' 
                    THEN 'queue'::post_status_enum
                    ELSE 'stop'::post_status_enum
                    END
            WHERE 
                post_server_id = %s 
                AND post_status IN ('error', 'run')
            RETURNING process_version_id, execution_order, simulation_status, post_status;"""
        stripped_psm_query = ' '.join([_s.strip() for _s in query.splitlines()])

        with conn.cursor() as cur:
            cur.execute(stripped_psm_query, (server_id,))
            result = cur.fetchall() if cur.rowcount else []
            conn.commit()

        if result:
            pvid_str = ', '.join([f"{pvid}/{eo}/{ss}/{ps}" for pvid, eo, ss, ps in result])
            LOGGER.info(
                f"OK fixing {len(result)} broken records "
                f"UPDATE server_pre_main SET post_status = 'stop' "
                f"for records [pvid/eo/simulation_status/post_status]: {pvid_str}")
    except Exception as _err:
        LOGGER.error(f"{type(_err).__name__}: {_err}")
        raise
    finally:
        config.put_connection(conn)
