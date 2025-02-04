import asyncio
import random
from asyncio import Future

from tornado.httpclient import HTTPRequest
from tornado.ioloop import IOLoop
from tornado.web import gen

from sockjs_client import sockjs_connect, SockJSConnectionException


class WSConnecterPlayer:
    def __init__(self, url):

        self.io_loop = IOLoop.current()
        self.io_loop.spawn_callback(self.main_loop)
        self.io_loop.spawn_callback(self.write_loop)

        self.url = url
        self.conn = None
        self.connected = Future()

    @gen.coroutine
    def connect(self):
        req = HTTPRequest(self.url)
        try:
            self.conn = yield sockjs_connect(req)
        except SockJSConnectionException as e:
            logging.exception("Unable to connect")
        except Exception as e:
            logging.exception("Uncaught generic exception")
        self.connected.set_result(True)

    @gen.coroutine
    def main_loop(self):
        yield self.connect()
        while self.connected and self.conn:
            msg = yield self.conn.read_message()
            if msg:
                print(msg)

    @gen.coroutine
    def write_loop(self):
        yield self.connected
        while self.conn:
            yield asyncio.sleep(1)
            if random.choice((True, False)):
                if not self.conn:
                    break
                yield self.conn.write_message("Message!")

    def close(self):
        self.conn.close()
        self.io_loop.stop()


if __name__ == '__main__':
    import logging
    import signal

    logging.basicConfig(level=logging.DEBUG)


    def on_shutdown():
        print('Shutting down')
        IOLoop.instance().stop()


    URL = 'ws://localhost:8080/echo'
    client = WSConnecterPlayer(url=URL)

    signal.signal(signal.SIGINT, lambda sig, fr: client.io_loop.add_callback_from_signal(on_shutdown))
    client.io_loop.start()
