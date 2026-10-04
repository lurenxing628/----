"""Hold the Windows listener before publishing the runtime endpoint."""

from __future__ import annotations

import os
import socket
from http.server import HTTPServer

from werkzeug.serving import BaseWSGIServer, ThreadedWSGIServer, make_server

from core.infrastructure.logging import safe_log

from .launcher_network import _candidate_ports
from .launcher_shutdown import RuntimeHostStopTransport
from .workbench_request_lifecycle import WorkbenchRequestHandler


class RuntimeBindError(RuntimeError):
    """Keep Werkzeug from exiting before the launcher can record bind errors."""


class _WindowsExclusiveBinding(HTTPServer):
    allow_reuse_address = False

    def server_bind(self):
        try:
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            super().server_bind()
        except OSError as exc:
            raise RuntimeBindError(str(exc)) from exc

    def server_activate(self):
        try:
            super().server_activate()
        except OSError as exc:
            raise RuntimeBindError(str(exc)) from exc


class _WindowsRuntimeServer(_WindowsExclusiveBinding, ThreadedWSGIServer):
    pass


class _WindowsSingleRuntimeServer(_WindowsExclusiveBinding, BaseWSGIServer):
    pass


def make_runtime_server(host, port, app, threaded=False, processes=1, request_handler=None,
                        passthrough_errors=False, ssl_context=None, fd=None):
    if os.name != "nt":
        return make_server(host, port, app, threaded=threaded, processes=processes, request_handler=request_handler,
                           passthrough_errors=passthrough_errors, ssl_context=ssl_context, fd=fd)
    if processes != 1:
        raise ValueError("The Windows runtime requires one server process")
    server_class = _WindowsRuntimeServer if threaded else _WindowsSingleRuntimeServer
    return server_class(host, int(port), app, handler=request_handler, passthrough_errors=passthrough_errors,
                        ssl_context=ssl_context, fd=fd)


def create_runtime_server(app, host, port, *, server_factory=make_runtime_server):
    transport = RuntimeHostStopTransport(app)
    server = server_factory(host, int(port), transport, threaded=True, request_handler=WorkbenchRequestHandler)
    transport.server = server
    server.daemon_threads = False
    return server


def prepare_runtime_server(app, host, preferred_port, *, server_factory=make_runtime_server):
    candidates = [port for port in _candidate_ports(preferred_port) if port <= 65535]
    hosts = [host] if host == "127.0.0.1" else [host, "127.0.0.1"]
    endpoints = [(bind_host, port) for bind_host in hosts for port in candidates]
    endpoints.extend((bind_host, 0) for bind_host in hosts)
    last_error = None
    for bind_host, port in endpoints:
        try:
            return create_runtime_server(app, bind_host, port, server_factory=server_factory)
        except RuntimeBindError as exc:
            last_error = exc
            safe_log(app.logger, "warning", "Runtime bind failed: host=%s port=%s error=%s", bind_host, port, exc)
    raise RuntimeBindError(f"No available runtime listener: {last_error}")
