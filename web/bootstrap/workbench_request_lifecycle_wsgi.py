"""Keep request tickets through Flask teardown AND WSGI iteration/close."""

from contextlib import contextmanager

from flask import Response, g, request

from .workbench_request_lifecycle_state import _LOCAL, RequestFrame, current_frame

_FRAME_KEY = "aps.workbench.request_lifecycle"
_RESPONSE_KEY = "aps.workbench.request_lifecycle_response"


def stopping_response():
    message = "系统正在退出或维护，这次操作没有执行。请稍后重新打开页面，并核对上次操作的结果。"
    if request.path.startswith("/api/workbench/"):
        from web.routes.workbench.api_responses import failure

        return failure("request_lifecycle_stopping", message, 503, committed=False)
    return Response(message, status=503, content_type="text/plain; charset=utf-8",
                    headers={"Cache-Control": "no-store"})


@contextmanager
def frame_scope(frame):
    previous = current_frame()
    _LOCAL.frame = frame
    try:
        yield
    finally:
        _LOCAL.frame = previous


class RequestIterable:
    def __init__(self, iterable, frame):
        self._source, self._iterator = iterable, iter(iterable)
        self._frame, self._closed = frame, False

    def __iter__(self):
        return self

    def __next__(self):
        if self._closed:
            raise StopIteration
        with frame_scope(self._frame):
            try:
                return next(self._iterator)
            except BaseException:
                self.close()
                raise

    def close(self):
        if self._closed:
            return
        self._closed = True
        with frame_scope(self._frame):
            try:
                close = getattr(self._source, "close", None)
                if close is not None:
                    close()
            finally:
                self._frame.finish()


def wrap_wsgi(app, gate):
    original = app.wsgi_app

    def wsgi(environ, start_response):
        frame = RequestFrame(app, gate)
        environ[_FRAME_KEY] = frame
        with frame_scope(frame):
            try:
                response = RequestIterable(original(environ, start_response), frame)
                environ[_RESPONSE_KEY] = response
                return response
            except BaseException:
                frame.finish()
                raise

    app.wsgi_app = wsgi


def close_workbench_response(environ):
    response = environ.pop(_RESPONSE_KEY, None)
    if response is not None:
        response.close()


def install_admission_hook(app, gate, normalize):
    @app.before_request
    def admit_request():
        frame = request.environ.get(_FRAME_KEY)
        if frame is None or frame.app is not app or current_frame() is not frame:
            raise RuntimeError("Request lifecycle WSGI envelope is missing")
        if frame.ticket is not None:
            return None
        if normalize(app.config.get("DATABASE_PATH")) != gate.db_path:
            raise RuntimeError("Request lifecycle database configuration changed")
        frame.ticket = gate.admit(app)
        if frame.ticket is not None:
            return None
        return stopping_response()

    original_teardown = app.do_teardown_appcontext

    def teardown(exc):
        # Capture before factory pops g.db. This also detects a missing tracking
        # hook; it does NOT pretend an unreported factory close was successful.
        frame = current_frame()
        conn = g.get("db")
        if frame is not None and frame.ticket is not None and conn is not None:
            if not any(item.connection is conn for item in frame.ticket.connections):
                frame.ticket.failures.append("unregistered_connection")
                frame.track(conn)
        return original_teardown(exc)

    app.do_teardown_appcontext = teardown


def track_workbench_request_connection(conn):
    """Factory: immediately after get_connection, BEFORE container assembly."""
    frame = current_frame()
    if frame is None:
        raise RuntimeError("No HTTP request lifecycle envelope for DB connection")
    return frame.track(conn)


def close_workbench_request_connection(conn):
    """Factory: replace BOTH mount-failure and appcontext teardown conn.close.

    Close exceptions still propagate to existing logging. They additionally
    poison drain, even if the WSGI finalizer's cleanup retry later succeeds.
    Ordinary non-request app contexts keep their existing close behavior.
    """
    frame = current_frame()
    if frame is None or frame.ticket is None:
        conn.close()
    else:
        frame.close_connection(conn)
