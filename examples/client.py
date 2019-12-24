from tornado.httpclient import HTTPRequest
from tornado.ioloop import IOLoop
from tornado.web import gen

from sockjs_client import sockjs_connect, SockJSConnectionException


class WSConnecterPlayer:
    def __init__(self, url):

        self.io_loop = IOLoop.current()
        self.io_loop.spawn_callback(self.main_loop)

        self.url = url
        self.conn = None

    @gen.coroutine
    def connect(self):
        req = HTTPRequest(self.url)
        try:
            self.conn = yield sockjs_connect(req)
        except SockJSConnectionException as e:
            logging.exception("Unable to connect")
        except Exception as e:
            logging.exception("Uncaught generic exception")

    @gen.coroutine
    def main_loop(self):
        yield self.connect()
        while self.conn:
            msg = yield self.conn.read_message()
            if msg:
                print(msg)
            else:
                break
        exit(1)

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
