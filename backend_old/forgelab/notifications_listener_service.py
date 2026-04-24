from __future__ import annotations

import logging
import threading
import time
from multiprocessing import Queue
import psycopg2
import select
import psycopg2.extensions
import random

from forgelab.config import config


LOGGER = logging.getLogger(__name__)


def notifier():
    conn = psycopg2.connect(
        user=config.db['user'],
        password=config.db['pass'],
        host=config.db['host'],
        port=config.db['port'],
        dbname=config.db['base'])

    conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)

    names = tuple(config.services.keys())

    for i in range(1, 1000):
        name = random.choice(names)
        notify_channel = config.services[name]['notify_channel']
        with conn.cursor() as cur:
            cur.execute(f"NOTIFY {notify_channel}, '{i}';")
        LOGGER.info(f"Sent NOTIFY {name}, '{i}'")
        time.sleep(5 * random.random())


class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class NotificationsListenerService(threading.Thread, metaclass=Singleton):
    """Thread class with a stop() method. The thread itself has to check
    regularly for the stopped() condition."""

    def __init__(self, queues: dict[str, Queue]):
        super().__init__()
        try:
            self.notify_channels: dict = {key: v['notify_channel'] for key, v in config.services.items() if key in queues}
            assert set(self.notify_channels.keys()) == set(queues.keys()), "Allowed services are different"
            self._queues = queues
            self._stop_event = threading.Event()
        except Exception as _err:
            LOGGER.error(f"{type(_err).__name__}: {_err}")
            raise

    def stop(self):
        LOGGER.debug("Notification Listener Service: 'stop' method is called")
        self._stop_event.set()

    def is_stopped(self):
        return self._stop_event.is_set()

    def run(self):

        conn = psycopg2.connect(
            user=config.db['user'],
            password=config.db['pass'],
            host=config.db['host'],
            port=config.db['port'],
            dbname=config.db['base'])

        # conn = config.get_connection()
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)

        with conn.cursor() as cur:
            for notify_channel in self.notify_channels.values():
                cur.execute(f"LISTEN {notify_channel};")

        try:
            while not self.is_stopped():

                if select.select([conn], [], [], 5) == ([], [], []):
                    # No notification
                    # LOGGER.info("          NT           ")
                    continue

                conn.poll()

                while conn.notifies:
                    notify = conn.notifies.pop(0)
                    for service_name, notify_channel in self.notify_channels.items():
                        if notify.channel == notify_channel:
                            pvid_str: str = notify.payload
                            if pvid_str.isdigit():
                                pvid = int(pvid_str)
                                self._queues[service_name].put(pvid)
                                LOGGER.info(f"Got NOTIFY: {service_name}, {pvid = }")
                            else:
                                LOGGER.warning(
                                    f"FAILED to get PVID from NOTIFY payload. "
                                    f"Got type={type(pvid_str)} value={pvid_str}.")

                time.sleep(0.1)

        except Exception as _err:
            LOGGER.error(f"{type(_err).__name__}: {_err}")
            config.is_error = True
            return
        except KeyboardInterrupt:
            LOGGER.warning("KeyboardInterrupt received")
        finally:
            config.put_connection(conn)
            LOGGER.warning(f"Notification Listener Service Stopped")
