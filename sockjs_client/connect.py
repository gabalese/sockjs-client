import logging

from tornado.websocket import websocket_connect, WebSocketError

from sockjs_client.xhrstreaming import xhr_streaming_connect, XHRStreamingConnectionError


class SockJSConnectionException(Exception):
    pass


async def sockjs_connect(request):
    conn = None
    for connection in (websocket_connect, xhr_streaming_connect):
        try:
            conn = await connection(request)
        except (WebSocketError, XHRStreamingConnectionError, ConnectionError):
            logging.debug("Unable to connect using {}".format(connection.__name__))
        except Exception:
            logging.exception("Uncaught exception!")
        else:
            logging.info("Connected with {}".format(connection.__name__))
            break

    if not conn:
        raise SockJSConnectionException("Unable to connect to {}".format(request.url))

    return await conn.connect_future
