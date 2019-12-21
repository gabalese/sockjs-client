import logging
from logging import NullHandler

logging.getLogger(__name__).addHandler(NullHandler())

from sockjs_client.connect import sockjs_connect, SockJSConnectionException

__version__ = '0.1.0'
