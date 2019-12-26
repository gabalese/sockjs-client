import logging

from tornado.websocket import websocket_connect, WebSocketError

from sockjs_client.xhrstreaming import xhr_streaming_connect, XHRStreamingConnectionError


class SockJSConnectionException(Exception):
    pass


async def sockjs_connect(http_request):
    conn = None
    for connection in (websocket_connect, xhr_streaming_connect):
        try:
            conn = await connection(http_request)
        except (WebSocketError, XHRStreamingConnectionError, ConnectionError):
            logging.debug(f"Unable to connect using {connection.__name__}")
        except Exception:
            logging.exception("Uncaught exception!")
        else:
            logging.info(f"Connected with {connection.__name__}")
            break

    if not conn:
        raise SockJSConnectionException(f"Unable to connect to {http_request.url}")

    return await conn.connect_future
