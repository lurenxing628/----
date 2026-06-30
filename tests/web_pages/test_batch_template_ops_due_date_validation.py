"""回归：从模板建批次时,乱码 due_date 必须在入口被 _normalize_date 挡下(与同函数的
ready_date 对称),不得裸写进库。

锁住 batch_template_ops._ensure_batch_exists_for_template_ops 的 due_date 校验漏洞修复:
此前 due_date 裸写、ready_date 却过校验,导致"从模板建批次"这条 UI 路径能塞入乱码交期。
"""

from types import SimpleNamespace
from typing import Optional

import pytest
from flask import Flask, g, get_flashed_messages

from core.infrastructure.errors import ValidationError
from core.services.scheduler.batch_service import BatchService
from core.services.scheduler.batch_template_ops import _ensure_batch_exists_for_template_ops


class _FakeBatchRepo:
    def __init__(self) -> None:
        self.created: list = []

    def get(self, _batch_id):
        return None

    def create(self, payload):
        self.created.append(dict(payload))


class _FakeSvc:
    # 用真实的 _normalize_date(批量服务的日期入口校验),其余仓库桩化。
    _normalize_date = staticmethod(BatchService._normalize_date)

    def __init__(self) -> None:
        self.batch_repo = _FakeBatchRepo()


def _ensure(svc: _FakeSvc, *, due_date) -> None:
    _ensure_batch_exists_for_template_ops(
        svc,
        batch_id="B1",
        part_no="P1",
        part_name="件",
        quantity=1,
        due_date=due_date,
        priority="normal",
        ready_status="yes",
        ready_date=None,
        remark=None,
        rebuild_ops=False,
    )


def test_template_batch_rejects_garbage_due_date() -> None:
    svc = _FakeSvc()
    with pytest.raises(ValidationError):
        _ensure(svc, due_date="2026-13-99")
    assert svc.batch_repo.created == [], "乱码交期绝不能写进库"


def test_template_batch_normalizes_valid_due_date() -> None:
    svc = _FakeSvc()
    _ensure(svc, due_date="2026/05/20")
    assert len(svc.batch_repo.created) == 1
    assert svc.batch_repo.created[0]["due_date"] == "2026-05-20"


def _post_create_batch_route(monkeypatch, *, due_date: str, service_error: Optional[ValidationError] = None):
    import web.routes.domains.scheduler.scheduler_batches as route_mod

    captured = {}

    class _StubBatch:
        batch_id = "B1"

    class _StubBatchService:
        def create_batch_from_template(self, **kwargs):
            captured["kwargs"] = dict(kwargs)
            if service_error is not None:
                raise service_error
            return _StubBatch()

        def list_operations(self, _batch_id):
            return []

        def consume_user_visible_warnings(self):
            return []

    monkeypatch.setattr(route_mod, "url_for", lambda endpoint, **_kwargs: f"/{endpoint}")

    app = Flask(__name__)
    app.secret_key = "aps-test-secret"
    with app.test_request_context(
        "/scheduler/batches/create",
        method="POST",
        data={
            "batch_id": "B1",
            "part_no": "P1",
            "quantity": "1",
            "due_date": due_date,
            "priority": "normal",
            "ready_status": "yes",
        },
    ):
        g.services = SimpleNamespace(batch_service=_StubBatchService())
        response = route_mod.create_batch()
        captured["flashes"] = get_flashed_messages(with_categories=True)
        captured["location"] = response.location
        captured["status_code"] = response.status_code
    return captured


def test_create_batch_route_passes_due_date_to_batch_service(monkeypatch) -> None:
    result = _post_create_batch_route(monkeypatch, due_date="2026/05/20")

    assert result["status_code"] in (301, 302)
    assert result["kwargs"]["due_date"] == "2026/05/20"
    assert result["flashes"][0][0] == "success"


def test_create_batch_route_surfaces_invalid_due_date_error(monkeypatch) -> None:
    result = _post_create_batch_route(
        monkeypatch,
        due_date="2026-13-99",
        service_error=ValidationError("交期格式不正确", field="交期"),
    )

    assert result["status_code"] in (301, 302)
    assert result["location"].endswith("/scheduler.batches_manage_page")
    assert result["flashes"] == [("error", "交期格式不正确")]
