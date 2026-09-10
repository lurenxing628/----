"""Finalize on the serving thread even if Werkzeug's socket cleanup fails."""

from werkzeug.serving import WSGIRequestHandler

from .workbench_request_lifecycle_wsgi import close_workbench_response


class WorkbenchRequestHandler(WSGIRequestHandler):
    """Pass as make_server(..., request_handler=WorkbenchRequestHandler).

    Werkzeug's run_wsgi finally drains unread socket input BEFORE iterable.close.
    A connection reset while draining can skip that close. Only after run_wsgi
    exits, on the SAME request thread, finish the saved response in our finally.
    This is not cancellation; an executing view/generator must still return.
    """

    def run_wsgi(self):
        try:
            return super().run_wsgi()
        finally:
            environ = getattr(self, "environ", None)
            if environ is not None:
                close_workbench_response(environ)
