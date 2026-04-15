from __future__ import annotations

import inspect

from core.services.scheduler.schedule_service import ScheduleService


def test_schedule_service_signature_contract() -> None:
    signature = inspect.signature(ScheduleService.__init__)
    params = list(signature.parameters.values())

    assert [param.name for param in params] == ["self", "conn", "logger", "op_logger"]
    assert params[1].default is inspect.Signature.empty
    assert params[2].default is None
    assert params[3].default is None
