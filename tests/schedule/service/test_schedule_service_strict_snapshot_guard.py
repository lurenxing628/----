"""回归测试：schedule_service._get_snapshot_with_strict_mode 必须以显式关键字 strict_mode 调用 config_service.get_snapshot；遇到不接受该关键字的旧签名实现应直接抛 TypeError，不得静默退回无参调用。"""

from __future__ import annotations

import pytest

from core.services.scheduler.schedule_service import _get_snapshot_with_strict_mode


class _ConfigServiceStub:
    def __init__(self) -> None:
        self.called_with = []

    def get_snapshot(self, *, strict_mode: bool = False):
        self.called_with.append(bool(strict_mode))
        return {"strict_mode": bool(strict_mode)}


class _LegacyConfigServiceStub:
    def get_snapshot(self):
        return {"legacy": True}


def test_get_snapshot_with_strict_mode_passes_keyword_explicitly() -> None:
    svc = _ConfigServiceStub()

    snapshot = _get_snapshot_with_strict_mode(svc, strict_mode=True)

    assert snapshot == {"strict_mode": True}
    assert svc.called_with == [True]


def test_get_snapshot_with_strict_mode_rejects_legacy_signature() -> None:
    with pytest.raises(TypeError):
        _get_snapshot_with_strict_mode(_LegacyConfigServiceStub(), strict_mode=True)
