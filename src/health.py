import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Optional

from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

logger = logging.getLogger(__name__)

_handler: Optional[AsyncSocketModeHandler] = None


def set_handler(handler: AsyncSocketModeHandler) -> None:
    global _handler
    _handler = handler


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self, *args: Any) -> None:
        connected = _handler is not None and _handler.client.is_connected()
        self.send_response(200 if connected else 503)
        self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        pass


def start() -> None:
    port = int(os.environ.get("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("Health check server listening on port %d", port)
