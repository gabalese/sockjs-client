import asyncio
import json
import logging
import random
import string
from http.client import HTTPConnection
from urllib.parse import urlparse

from tornado.concurrent import Future, future_set_result_unless_cancelled
from tornado.httpclient import HTTPRequest


class XHRStreamingConnectionError(Exception):
    pass


class XHRStreamingClientConnection:
    """
    Almost drop-in replacement for WebSocketClientConnection
    which handles a SockJS XHR Streaming fallback
    """

    def __init__(self, host, port=None, endpoint=None):
        self.host = host
        self.port = port
        self.endpoint = endpoint

        self.io_loop = asyncio.get_event_loop()

        self.read_queue = asyncio.Queue(maxsize=2048)

        self.connect_future = Future()

        self.client_id = ''.join(random.choices(string.digits, k=5))
        self.connection_id = ''.join(random.choices(string.ascii_letters + string.digits, k=8))

        self.conn = HTTPConnection(self.host, self.port)
        self.read_resp = None

        self.base_url = f'{self.endpoint}/{self.client_id}/{self.connection_id}'
        self.connect()

    @property
    def running(self):
        return self.read_resp is not None

    def connect(self):
        try:
            streaming_url = f"{self.base_url}/xhr_streaming"
            self.conn.request('POST', streaming_url)
            self.read_resp = self.conn.getresponse()
            if self.read_resp.status != 200:
                self.conn.close()
                raise Exception("Closed connection")
        except Exception as e:
            # TODO: Handle this
            self.connect_future.set_exception(XHRStreamingConnectionError(e))
            return

        self._file_no = self.read_resp.fileno()
        self.io_loop.add_reader(self._file_no, self.on_fd_message)
        future_set_result_unless_cancelled(self.connect_future, self)

    def close(self, code=None, reason=None):
        self.io_loop.remove_reader(self.read_resp.fileno())
        self.conn.close()

    def on_fd_message(self):
        if not self.read_resp.fp:
            logging.debug("Cancelling reader")
            self.io_loop.remove_reader(self._file_no)
            self.read_queue.put_nowait(None)
            self.read_resp = None
            return

        self.read_queue.put_nowait(self.read_resp.readline())

    async def write_message(self, message, binary=False):
        url = f'{self.base_url}/xhr_send'
        local_conn = HTTPConnection(self.host, self.port)
        local_conn.request('POST', url, body=json.dumps([message]), encode_chunked=False)
        local_conn.close()

    async def read_message(self, **kwargs):
        logging.debug("Await queue")
        msg = await self.read_queue.get()
        if msg is None:
            logging.debug("Queue is closed")
            return

        if msg.startswith(b'h'):
            logging.debug("Heartbeat")

        if msg.startswith(b'o'):
            logging.debug("Connection opened")

        if msg.startswith(b'c'):
            logging.debug("Connection closed!")
            return

        if msg.startswith((b'm', b'a')):
            logging.debug("Message received")

        return msg

    def decode_message(self, raw_message: bytes) -> str:
        pass


def xhr_streaming_connect(request: HTTPRequest) -> Future:
    """
    Connect to a sockjs endpoint via xhr_streaming transport
    """
    url = request.url
    parsed = urlparse(url)
    conn = XHRStreamingClientConnection(host=parsed.netloc.split(':')[0], port=parsed.port, endpoint=parsed.path)
    return conn.connect_future
