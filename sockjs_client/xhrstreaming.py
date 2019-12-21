import json
import logging
import random
import string
from http.client import HTTPConnection
from urllib.parse import urlparse

from tornado import gen
from tornado.concurrent import Future, future_set_result_unless_cancelled
from tornado.httpclient import HTTPRequest
from tornado.ioloop import IOLoop


class XHRStreamingConnectionError(Exception):
    pass


class XHRStreamingClientConnection:
    """
    Almost drop-in replacement for WebSocketClientConnection
    which handles a SockJS XHR Streaming fallback
    """

    # noinspection PyMissingConstructor
    def __init__(self, host, port, endpoint):
        self.host = host
        self.port = port
        self.endpoint = endpoint

        self.io_loop = IOLoop.current()

        self.connect_future = Future()

        self.client_id = ''.join(random.choices(string.digits, k=5))
        self.connection_id = ''.join(random.choices(string.ascii_letters + string.digits, k=8))

        self.conn = HTTPConnection(self.host, self.port)
        self.resp = None

        self.base_url = f'{self.endpoint}/{self.client_id}/{self.connection_id}'
        self.connect()

    def connect(self):
        try:
            streaming_url = f"{self.base_url}/xhr_streaming"
            self.conn.request('POST', streaming_url)
            response = self.conn.getresponse()
            if response.status != 200:
                self.conn.close()
                raise Exception("Closed connection")
            self.resp = response


        except Exception as e:
            self.connect_future.set_exception(XHRStreamingConnectionError())
            return

        future_set_result_unless_cancelled(self.connect_future, self)

    def close(self, code=None, reason=None):
        self.conn.close()

    @gen.coroutine
    def write_message(self, message, binary=False):
        url = f'{self.base_url}/xhr_send'
        local_conn = HTTPConnection(self.host, self.port)
        local_conn.request('POST', url, body=json.dumps([message]), encode_chunked=False)
        local_conn.close()

    @gen.coroutine
    def _read_one(self):
        try:
            char = yield self.io_loop.run_in_executor(None, self.resp.read, 1)
        except Exception as e:
            logging.exception()
        else:
            return char

    @gen.coroutine
    def _readline(self):
        try:
            line = yield self.io_loop.run_in_executor(None, self.resp.readline)
        except Exception as e:
            logging.exception()
        else:
            return line

    @gen.coroutine
    def read_message(self, **kwargs):
        data = 1
        while data:
            data = yield self._read_one()
            if data == b'o':
                logging.debug("XHR Connected")
            if data == b'c':
                logging.debug("XHR Disconnected")
                return
            if data == b'h':
                pass
            if data in (b'm', b'a'):
                msg = yield self._readline()
                logging.debug("Message: %s", msg)


def xhr_streaming_connect(request: HTTPRequest) -> Future:
    """
    Connect to a sockjs endpoint via xhr_streaming transport
    """
    url = request.url
    parsed = urlparse(url)
    conn = XHRStreamingClientConnection(host=parsed.netloc.split(':')[0], port=parsed.port, endpoint=parsed.path)
    return conn.connect_future
