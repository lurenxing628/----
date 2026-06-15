"""回归测试：批次列表的齐套筛选和分页必须下推到 service/repository。"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, List

from flask import Flask, g

from core.services.material.material_service import MaterialService
from core.services.personnel.operator_service import OperatorService
from core.services.scheduler.batch_service import BatchService
from data.repositories.batch_repo import BatchRepository
from data.repositories.material_repo import MaterialRepository
from data.repositories.operator_machine_repo import OperatorMachineRepository
from data.repositories.operator_repo import OperatorRepository


def test_batch_repository_pushes_ready_status_and_pagination_to_sql() -> None:
    repo = BatchRepository.__new__(BatchRepository)
    captured: Dict[str, Any] = {}

    def fake_fetchall(sql, params):
        captured["sql"] = sql
        captured["params"] = params
        return []

    repo.fetchall = fake_fetchall  # type: ignore[method-assign]

    rows = repo.list(status="pending", ready_status="no", limit=20, offset=40)

    assert rows == []
    assert "status = ?" in captured["sql"]
    assert "ready_status = ?" in captured["sql"]
    assert "LIMIT ? OFFSET ?" in captured["sql"]
    assert captured["params"] == ("pending", "no", 20, 40)


def test_batch_repository_count_pushes_ready_status_to_sql() -> None:
    repo = BatchRepository.__new__(BatchRepository)
    captured: Dict[str, Any] = {}

    def fake_fetchvalue(sql, params, default=0):
        captured["sql"] = sql
        captured["params"] = params
        captured["default"] = default
        return 7

    repo.fetchvalue = fake_fetchvalue  # type: ignore[method-assign]

    total = repo.count(status="pending", ready_status="no")

    assert total == 7
    assert "COUNT(1)" in captured["sql"]
    assert "status = ?" in captured["sql"]
    assert "ready_status = ?" in captured["sql"]
    assert captured["params"] == ("pending", "no")
    assert captured["default"] == 0


def test_batch_service_list_page_uses_same_filter_for_rows_and_count() -> None:
    calls: List[Dict[str, Any]] = []

    class _Repo:
        def list(self, **kwargs):
            calls.append({"method": "list", **kwargs})
            return []

        def count(self, **kwargs):
            calls.append({"method": "count", **kwargs})
            return 42

    service = BatchService.__new__(BatchService)
    service.batch_repo = _Repo()

    rows, total = service.list_page(status="pending", ready_status="partial", page=999, per_page=20)

    assert rows == []
    assert total == 42
    assert calls == [
        {"method": "count", "status": "pending", "priority": None, "part_no": None, "ready_status": "partial"},
        {
            "method": "list",
            "status": "pending",
            "priority": None,
            "part_no": None,
            "ready_status": "partial",
            "limit": 20,
            "offset": 40,
        },
    ]


def test_batches_manage_page_pushes_filters_and_pagination_to_service(monkeypatch) -> None:
    import web.routes.domains.scheduler.scheduler_batches as batches_mod

    app = Flask(__name__)
    app.secret_key = "batch-list-pushdown"
    captured: Dict[str, Any] = {}
    service_calls: List[Dict[str, Any]] = []

    class _BatchService:
        def list_page(self, **kwargs):
            service_calls.append(kwargs)
            return [], 42

    def fake_render_template(template_name: str, **kwargs: Any) -> str:
        captured["template_name"] = template_name
        captured.update(kwargs)
        return "OK"

    monkeypatch.setattr(batches_mod, "render_template", fake_render_template)

    with app.test_request_context("/scheduler/batches?status=&only_ready=no&page=3&per_page=20"):
        g.services = SimpleNamespace(
            batch_service=_BatchService(),
            part_service=SimpleNamespace(list=lambda: []),
        )
        response = batches_mod.batches_manage_page()

    assert response == "OK"
    assert captured["template_name"] == "scheduler/batches_manage.html"
    assert service_calls == [{"status": None, "ready_status": "no", "page": 3, "per_page": 20}]
    assert captured["pager"]["total"] == 42
    assert captured["pager"]["page"] == 3


def test_material_repository_pushes_pagination_to_sql() -> None:
    repo = MaterialRepository.__new__(MaterialRepository)
    captured: Dict[str, Any] = {}

    def fake_fetchall(sql, params=None):
        captured["sql"] = sql
        captured["params"] = params
        return []

    repo.fetchall = fake_fetchall  # type: ignore[method-assign]

    rows = repo.list(status="active", limit=25, offset=50)

    assert rows == []
    assert "WHERE status = ?" in captured["sql"]
    assert "LIMIT ? OFFSET ?" in captured["sql"]
    assert captured["params"] == ("active", 25, 50)


def test_material_service_list_page_uses_count_and_limited_rows() -> None:
    calls: List[Dict[str, Any]] = []

    class _Repo:
        def list(self, **kwargs):
            calls.append({"method": "list", **kwargs})
            return []

        def count(self, **kwargs):
            calls.append({"method": "count", **kwargs})
            return 42

    service = MaterialService.__new__(MaterialService)
    service.repo = _Repo()

    rows, total = service.list_page(status="active", page=999, per_page=20)

    assert rows == []
    assert total == 42
    assert calls == [
        {"method": "count", "status": "active"},
        {"method": "list", "status": "active", "limit": 20, "offset": 40},
    ]


def test_materials_page_pushes_pagination_to_service(monkeypatch) -> None:
    import web.routes.material as material_mod

    app = Flask(__name__)
    app.secret_key = "material-list-pushdown"
    captured: Dict[str, Any] = {}
    service_calls: List[Dict[str, Any]] = []

    class _MaterialService:
        def list_page(self, **kwargs):
            service_calls.append(kwargs)
            return [], 42

    def fake_render_template(template_name: str, **kwargs: Any) -> str:
        captured["template_name"] = template_name
        captured.update(kwargs)
        return "OK"

    monkeypatch.setattr(material_mod, "render_template", fake_render_template)

    with app.test_request_context("/material/materials?page=3&per_page=20"):
        g.services = SimpleNamespace(material_service=_MaterialService())
        response = material_mod.materials_page()

    assert response == "OK"
    assert captured["template_name"] == "material/materials.html"
    assert service_calls == [{"status": None, "page": 3, "per_page": 20}]
    assert captured["pager"]["total"] == 42
    assert captured["pager"]["page"] == 3


def test_operator_repository_pushes_team_filter_and_pagination_to_sql() -> None:
    repo = OperatorRepository.__new__(OperatorRepository)
    captured: Dict[str, Any] = {}

    def fake_fetchall(sql, params=None):
        captured["sql"] = sql
        captured["params"] = params
        return []

    repo.fetchall = fake_fetchall  # type: ignore[method-assign]

    rows = repo.list(team_id="TEAM-01", limit=25, offset=50)

    assert rows == []
    assert "team_id = ?" in captured["sql"]
    assert "LIMIT ? OFFSET ?" in captured["sql"]
    assert captured["params"] == ("TEAM-01", 25, 50)


def test_operator_service_list_page_uses_count_and_limited_rows() -> None:
    calls: List[Dict[str, Any]] = []

    class _Repo:
        def list(self, **kwargs):
            calls.append({"method": "list", **kwargs})
            return []

        def count(self, **kwargs):
            calls.append({"method": "count", **kwargs})
            return 42

    service = OperatorService.__new__(OperatorService)
    service.repo = _Repo()
    service.team_repo = SimpleNamespace(get=lambda _team_id: SimpleNamespace(team_id=_team_id))

    rows, total = service.list_page(team_id="TEAM-01", page=999, per_page=20)

    assert rows == []
    assert total == 42
    assert calls == [
        {"method": "count", "status": None, "team_id": "TEAM-01"},
        {"method": "list", "status": None, "team_id": "TEAM-01", "limit": 20, "offset": 40},
    ]


def test_operator_machine_repository_can_limit_links_to_page_operators() -> None:
    repo = OperatorMachineRepository.__new__(OperatorMachineRepository)
    captured: Dict[str, Any] = {}

    def fake_fetchall(sql, params=None):
        captured["sql"] = sql
        captured["params"] = params
        return []

    repo.fetchall = fake_fetchall  # type: ignore[method-assign]

    rows = repo.list_simple_rows_for_operators(["OP002", "OP001"])

    assert rows == []
    assert "operator_id IN (?,?)" in captured["sql"]
    assert captured["params"] == ("OP001", "OP002")


def test_personnel_page_pushes_team_filter_and_pagination_to_service(monkeypatch) -> None:
    import web.routes.personnel_pages as personnel_mod

    app = Flask(__name__)
    app.secret_key = "personnel-list-pushdown"
    captured: Dict[str, Any] = {}
    service_calls: List[Dict[str, Any]] = []
    link_calls: List[List[str]] = []

    class _OperatorService:
        def list_page(self, **kwargs):
            service_calls.append(kwargs)
            return [SimpleNamespace(operator_id="OP001", name="张三", team_id="TEAM-01", status="active", remark=None)], 42

    class _LinkQuery:
        def list_simple_rows_for_operators(self, operator_ids):
            link_calls.append(list(operator_ids))
            return []

    def fake_render_template(template_name: str, **kwargs: Any) -> str:
        captured["template_name"] = template_name
        captured.update(kwargs)
        return "OK"

    monkeypatch.setattr(personnel_mod, "render_template", fake_render_template)
    monkeypatch.setattr(personnel_mod, "OperatorService", lambda *_args, **_kwargs: _OperatorService())
    monkeypatch.setattr(personnel_mod, "MachineService", lambda *_args, **_kwargs: SimpleNamespace(list=lambda: []))
    monkeypatch.setattr(personnel_mod, "OperatorMachineQueryService", lambda *_args, **_kwargs: _LinkQuery())
    monkeypatch.setattr(personnel_mod, "load_team_options", lambda: [{"team_id": "TEAM-01", "name": "一组"}])

    with app.test_request_context("/personnel/?team_id=TEAM-01&page=3&per_page=20"):
        g.db = object()
        g.app_logger = None
        g.op_logger = None
        response = personnel_mod.list_page()

    assert response == "OK"
    assert captured["template_name"] == "personnel/list.html"
    assert service_calls == [{"status": None, "team_id": "TEAM-01", "page": 3, "per_page": 20}]
    assert link_calls == [["OP001"]]
    assert captured["pager"]["total"] == 42
    assert captured["pager"]["page"] == 3
