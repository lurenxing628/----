"""Observe a factory hook inside a real WSGI request and close its response."""

from typing import Any, Callable

import pytest
from flask import Flask


def run_request_probe(
    app: Flask,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    probe: Callable[[], Any],
    *,
    hook_name: str = "_open_db",
    expected_status: int = 204,
) -> None:
    hooks = list(app.before_request_funcs[None])
    indices = [index for index, hook in enumerate(hooks) if hook.__name__ == hook_name]
    assert len(indices) == 1, "Expected exactly one factory hook: " + hook_name
    calls = []

    def observe():
        calls.append(path)
        result = probe()
        return app.response_class(status=204) if result is None else result

    # Keep admission before the probe, and real teardown/WSGI close after it.
    hooks[indices[0]] = observe
    with monkeypatch.context() as scoped:
        scoped.setitem(app.before_request_funcs, None, hooks)
        scoped.setitem(app.config, "PROPAGATE_EXCEPTIONS", True)
        response = app.test_client().get(path, buffered=True)
        try:
            assert response.status_code == expected_status
            assert calls == [path]
        finally:
            response.close()
