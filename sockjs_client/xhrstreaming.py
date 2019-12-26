import asyncio
import functools
import json
import logging
import random
import string
from http.client import HTTPConnection
from urllib.parse import urlparse


class XHRStreamingConnectionError(Exception):
    pass


class XHRStreamingClientConnection:
    """
    Almost drop-in replacement for WebSocketClientConnection class
    which handles a SockJS XHR Streaming fallback.
    """

    def __init__(self, host, port=None, endpoint=None):
        self.host = host
        self.port = port or 80
        self.endpoint = endpoint or ''

        self.client_id = ''.join(random.choices(string.digits, k=5))
        self.connection_id = ''.join(random.choices(string.ascii_letters + string.digits, k=8))

        self.base_url = f'{self.endpoint}/{self.client_id}/{self.connection_id}'

        self.io_loop = asyncio.get_event_loop()

        self.read_queue = asyncio.Queue(maxsize=1024)

        self.connect_future = asyncio.Future()

        self.read_connection = HTTPConnection(self.host, self.port)
        self.read_stream = None

        self.connect()

    def connect(self):
        try:
            streaming_url = f"{self.base_url}/xhr_streaming"
            self.read_connection.request('POST', streaming_url)
            self.read_stream = self.read_connection.getresponse()

            if self.read_stream.status != 200:
                self.read_connection.close()
                raise Exception("Closed connection")

        except ConnectionError as e:
            self.connect_future.set_exception(XHRStreamingConnectionError(e))
            return

        self._file_no = self.read_stream.fileno()
        self.io_loop.add_reader(self._file_no, self.on_fd_message)

        self.connect_future.set_result(self)

    def close(self, code=None, reason=None):
        self.io_loop.remove_reader(self.read_stream.fileno())
        self.read_connection.close()

    def on_fd_message(self):
        if not self.read_stream.fp:
            logging.debug("Cancelling reader")
            self.io_loop.remove_reader(self._file_no)
            self.read_queue.put_nowait(None)
            self.read_stream = None
            return

        self.read_queue.put_nowait(self.read_stream.readline())

    async def write_message(self, message, binary=False):
        write_connection = HTTPConnection(self.host, self.port)
        url = f'{self.base_url}/xhr_send'
        try:
            await asyncio.wait_for(self.io_loop.run_in_executor(
                None,
                functools.partial(
                    write_connection.request,
                    'POST', url, body=json.dumps([message]), encode_chunked=False)
            ), timeout=5)
        except ConnectionError as e:
            logging.error(e)
        finally:
            write_connection.close()

    async def read_message(self, **kwargs):
        msg = await self.read_queue.get()

        if msg is None:
            logging.debug("Queue is closed")
            return

        if msg.startswith(b'h'):
            logging.debug("Heartbeat")

        if msg.startswith(b'o'):
            logging.debug("Connection opened")

        if msg.startswith(b'c'):
            logging.debug("Connection closed: %s", msg)
            return

        if msg.startswith((b'm', b'a')):
            logging.debug("Message received")
            msg = self.decode_message(msg)
            return msg[0]

        return msg

    def decode_message(self, raw_message: bytes) -> str:
        return json.loads(raw_message.lstrip(b'a'))


def xhr_streaming_connect(http_request) -> asyncio.Future:
    """
    Connect to a sockjs endpoint via xhr_streaming transport
    """
    url = http_request.url
    parsed = urlparse(url)
    conn = XHRStreamingClientConnection(host=parsed.netloc.split(':')[0], port=parsed.port, endpoint=parsed.path)
    return conn.connect_future
