import logging
import warnings
import socket
from logging.handlers import SocketHandler
from pythonjsonlogger import jsonlogger


def get_hostname():
    try:
        dns_name = socket.getfqdn()
        parts = dns_name.split('.', 1)
        if parts[0][0].isdigit():  # this is IP address
            hostname = dns_name
        else:
            hostname = parts[0]
        return hostname
    except Exception as _err:
        print(f"{type(_err).__name__}: {_err}")
        return 'ERROR'


# def get_ip():
#     try:
#         _ip = socket.gethostbyname(socket.gethostname())
#     except Exception as _err:
#         print(f"Failed to fetch server's IP address")
#         return 'ERROR'
#     else:
#         return _ip


class FluentBitHandler(SocketHandler):
    def emit(self, record):
        # noinspection PyBroadException
        try:
            self.send((self.format(record)).encode())
        except Exception:
            self.handleError(record)


# IP = get_ip()
HOSTNAME = get_hostname()


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        # if log_record.get('hostname'):
        log_record['hostname'] = HOSTNAME


def set_fluent_bit_logger(settings: dict):
    """
    Setup sending logs to remote server using TCP protocol (default port 3130).
    Remote server must run FluentBit service and listen to TCP 3130 port.
    NOTE: Allow incoming connections on port 3130 for TCP protocol

    Args:
        settings: dict
                'root_module_name': str name of directory located next ot main.py file and containing all Python modules
                'host': str IP address of remote server running FluentBit service
                'port': int Port number of remote server running FluentBit service where service is listening
                            TCP packets (default 3130)
    """
    _hostname = get_hostname()
    # _ip = get_ip()

    _format = '%(asctime)s [%(levelname)s] %(hostname)s %(message)s %(name)s %(funcName)s %(process)d'
    formatter = CustomJsonFormatter(fmt=_format)

    socket_handler = FluentBitHandler(host=settings['host'], port=settings['port'])
    socket_handler.setFormatter(formatter)

    # logging.captureWarnings(capture=True)

    errors_logger = logging.getLogger(settings['root_module_name'])
    errors_logger.setLevel(logging.DEBUG)
    errors_logger.addHandler(socket_handler)

    # warnings_logger = logging.getLogger("py.warnings")
    # warnings_logger.addHandler(socket_handler)

    # logger.info("Fluent Bit logger is set.")
