from sockjs.tornado import SockJSRouter, SockJSConnection
from tornado import web, ioloop, gen


class SimpleEchoClient(SockJSConnection):
    clients = set()

    def on_open(self, request):
        self.clients.add(self)
        print(self.clients)

        # Just give me some random message back please
        self.hb = ioloop.PeriodicCallback(self.start, 5000)
        self.hb.start()

    def on_message(self, message):
        self.send(f"I received a message! {message}")

    def on_close(self):
        print(f"Closing {self.session}")
        self.hb.stop()
        self.clients.remove(self)

    @gen.coroutine
    def start(self):
        print("Sending message...")
        yield self.send(f"MESSAGE!!! {self.session}")
        yield gen.sleep(5)


if __name__ == '__main__':
    import signal

    def on_shutdown():
        ioloop.IOLoop.current().stop()

    SimpleEchoRouter = SockJSRouter(SimpleEchoClient, '/echo',
                                    user_settings={"websocket_allow_origin": "*", 'disabled_transports': []})
    app = web.Application(SimpleEchoRouter.urls)
    app.listen(8080)

    loop = ioloop.IOLoop.instance()

    signal.signal(signal.SIGINT, lambda sig, frame: loop.add_callback_from_signal(on_shutdown))
    loop.start()
