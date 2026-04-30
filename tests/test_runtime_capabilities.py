from __future__ import annotations

import logging

import pytest

from web.bootstrap.runtime_capabilities import (
    STATE_AVAILABLE,
    STATE_DEGRADED,
    STATE_UNAVAILABLE,
    available,
    degraded,
    unavailable,
)


def test_runtime_capability_result_states() -> None:
    assert available("powershell").state == STATE_AVAILABLE
    assert available("powershell").available

    degraded_result = degraded("process-list", "wmic unavailable")
    assert degraded_result.state == STATE_DEGRADED
    assert degraded_result.degraded
    assert not degraded_result.available

    unavailable_result = unavailable("runtime-contract", "missing")
    assert unavailable_result.state == STATE_UNAVAILABLE
    assert unavailable_result.unavailable


def test_runtime_capability_degrade_and_unavailable_require_reason() -> None:
    with pytest.raises(ValueError):
        degraded("process-list", "")
    with pytest.raises(ValueError):
        unavailable("runtime-contract", "   ")


def test_runtime_capability_logs_observable_degrade(caplog) -> None:
    caplog.set_level(logging.WARNING)

    degraded("process-list", "wmic unavailable", {"command": "wmic"})
    unavailable("runtime-contract", "missing", {"path": "aps_runtime.json"})

    messages = [record.getMessage() for record in caplog.records]
    assert any("启动能力降级" in message and "wmic unavailable" in message for message in messages)
    assert any("启动能力不可用" in message and "missing" in message for message in messages)
