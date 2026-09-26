"""Interpreter scheduling policy is bounded to the owned serving lifetime."""

from types import SimpleNamespace

import pytest

from web.bootstrap import thread_scheduling as policy


@pytest.fixture
def interval(monkeypatch):
    state = {"value": 0.005, "changes": []}
    def change(value):
        state["value"] = value
        state["changes"].append(value)
    # Replace this module's namespaces, never mutate the pytest interpreter.
    monkeypatch.setattr(policy, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(policy, "sys", SimpleNamespace(
        implementation=SimpleNamespace(name="cpython"), version_info=(3, 8, 10),
        getswitchinterval=lambda: state["value"], setswitchinterval=change))
    assert policy._OWNERS == 0
    yield state
    assert policy._OWNERS == 0


def test_serving_policy_restores_on_exception_and_outlives_nested_owner(interval):
    with pytest.raises(ValueError):
        with policy.responsive_thread_scheduling():
            assert interval["value"] == 0.0001
            with policy.responsive_thread_scheduling():
                assert interval["changes"] == [0.0001]
            assert interval["value"] == 0.0001
            raise ValueError("server failed")
    assert interval["changes"] == [0.0001, 0.005]


def test_preserves_shorter_interval_and_external_change(interval):
    interval["value"] = 0.00001
    with policy.responsive_thread_scheduling():
        assert interval["value"] == 0.00001
    assert interval["value"] == 0.00001
    with policy.responsive_thread_scheduling():
        interval["value"] = 0.002
    assert interval["value"] == 0.002


@pytest.mark.parametrize("name,version,implementation", [
    ("posix", (3, 8), "cpython"), ("nt", (3, 11), "cpython"), ("nt", (3, 8), "pypy")])
def test_untested_runtimes_are_unchanged(interval, name, version, implementation):
    policy.os.name = name
    policy.sys.version_info = version
    policy.sys.implementation.name = implementation
    with policy.responsive_thread_scheduling():
        assert interval["value"] == 0.005
    assert interval["changes"] == []


def test_server_keeps_policy_until_connections_close(interval, monkeypatch):
    from web.bootstrap import factory

    events = []
    class Server:
        def serve_forever(self):
            events.append(("serve", interval["value"]))
            raise ValueError("serve failed")
        def server_close(self):
            events.append(("close", interval["value"]))
    monkeypatch.setattr(factory, "RuntimeHostStopTransport", lambda app: SimpleNamespace())
    monkeypatch.setattr(factory, "make_server", lambda *args, **kwargs: Server())
    with pytest.raises(ValueError):
        factory.serve_runtime_app(SimpleNamespace(), "127.0.0.1", 5000)
    assert events == [("serve", 0.0001), ("close", 0.0001)]
    assert factory._RUNTIME_SERVER is None
    assert interval["value"] == 0.005
