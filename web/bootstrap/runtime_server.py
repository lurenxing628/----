"""Hold the Windows listener before publishing the runtime endpoint."""

from __future__ import annotations

import os
import socket
from socketserver import TCPServer
from typing import cast

from werkzeug.serving import ThreadedWSGIServer, make_server

from core.infrastructure.logging import safe_log

from .launcher_network import candidate_ports
from .launcher_shutdown import RuntimeHostStopTransport
from .workbench_request_lifecycle import WorkbenchRequestHandler


class RuntimeBindError(RuntimeError):
    """Keep Werkzeug from exiting before the launcher can record bind errors."""


class _WindowsRuntimeServer(ThreadedWSGIServer):
    allow_reuse_address = False

    def server_bind(self):
        try:
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            # HTTPServer resolves getfqdn here. The runtime publishes the bound
            # address itself and does not need a reverse DNS lookup at startup.
            TCPServer.server_bind(self)
            host, self.server_port = self.server_address[:2]
            self.server_name = cast(str, host)
        except OSError as exc:
            raise RuntimeBindError(str(exc)) from exc

    def server_activate(self):
        try:
            super().server_activate()
        except OSError as exc:
            raise RuntimeBindError(str(exc)) from exc


def create_runtime_server(app, host, port):
    transport = RuntimeHostStopTransport(app)
    if os.name == "nt":
        server = _WindowsRuntimeServer(host, int(port), transport, handler=WorkbenchRequestHandler)
    else:
        server = cast(ThreadedWSGIServer, make_server(host, int(port), transport, threaded=True,
                                                      request_handler=WorkbenchRequestHandler))
    transport.server = server
    server.daemon_threads = False
    return server


def prepare_runtime_server(app, host, preferred_port):
    candidates = [port for port in candidate_ports(preferred_port) if port <= 65535]
    hosts = [host] if host == "127.0.0.1" else [host, "127.0.0.1"]
    endpoints = [(bind_host, port) for bind_host in hosts for port in candidates]
    endpoints.extend((bind_host, 0) for bind_host in hosts)
    last_error = None
    for bind_host, port in endpoints:
        try:
            return create_runtime_server(app, bind_host, port)
        except RuntimeBindError as exc:
            last_error = exc
            safe_log(app.logger, "warning", "Runtime bind failed: host=%s port=%s error=%s", bind_host, port, exc)
    raise RuntimeBindError(f"No available runtime listener: {last_error}")
