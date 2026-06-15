"""回归测试：_safe_next_url 对非法 next 跳转参数（绝对 URL、协议相对 URL）每请求只 warning 一次、对缺失/空白值不告警；scheduler config/batches 路由在 next 非法时回退到本地 url_for 端点。（system ui-mode 路由已随 2026-06 双轨退役删除，其专属用例一并移除。）"""

from __future__ import annotations

import re
from types import SimpleNamespace
from typing import List

from flask import Flask, g

from core.infrastructure.errors import ValidationError
from tests._support.paths import REPO_ROOT


def _build_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = "aps-safe-next-observability"
    return app


def test_safe_next_url_logs_invalid_non_empty_value_once_per_request(monkeypatch) -> None:
    import web.routes.system_utils as utils_mod

    app = _build_app()
    warnings: List[str] = []

    def _fake_warning(message, *args, **kwargs):
        warnings.append(message % args if args else str(message))

    monkeypatch.setattr(app.logger, "warning", _fake_warning)

    with app.test_request_context("/system/ui-mode"):
        assert utils_mod._safe_next_url("http://evil.example/x") is None
        assert utils_mod._safe_next_url("//evil.example/x") is None

    assert len(warnings) == 1, warnings
    assert "检测到非法 next 跳转参数" in warnings[0]
    assert "absolute_url" in warnings[0] or "protocol_relative" in warnings[0]


def test_safe_next_url_does_not_log_when_value_is_missing(monkeypatch) -> None:
    import web.routes.system_utils as utils_mod

    app = _build_app()
    warnings: List[str] = []

    def _fake_warning(message, *args, **kwargs):
        warnings.append(message % args if args else str(message))

    monkeypatch.setattr(app.logger, "warning", _fake_warning)

    with app.test_request_context("/system/ui-mode"):
        assert utils_mod._safe_next_url(None) is None
        assert utils_mod._safe_next_url("   ") is None

    assert warnings == []


def _fake_url_for(endpoint, **values):
    def _with_next(path):
        next_url = values.get("next")
        if next_url:
            return f"{path}?next={next_url}"
        return path

    if endpoint == "dashboard.index":
        return "/"
    if endpoint == "scheduler.config_page":
        return "/scheduler/config"
    if endpoint == "scheduler.batches_manage_page":
        return "/scheduler/batches"
    if endpoint == "scheduler.batch_detail":
        return _with_next(f"/scheduler/batches/{values['batch_id']}")
    if endpoint == "scheduler.update_op_by_token":
        return _with_next(f"/scheduler/ops/update-token/{values['token']}")
    if endpoint == "personnel.list_page":
        return "/personnel/"
    if endpoint == "personnel.detail_page":
        return _with_next(f"/personnel/{values['operator_id']}")
    if endpoint == "personnel.operator_calendar_page":
        return _with_next(f"/personnel/{values['operator_id']}/calendar")
    raise AssertionError(f"unexpected endpoint: {endpoint!r}")


def test_scheduler_config_invalid_next_uses_local_fallback(monkeypatch) -> None:
    import web.routes.domains.scheduler.scheduler_config as scheduler_config_mod

    app = _build_app()
    monkeypatch.setattr(scheduler_config_mod, "url_for", _fake_url_for)

    cfg_svc = SimpleNamespace(
        apply_preset=lambda name: {
            "requested_preset": name,
            "effective_active_preset": name,
            "status": "applied",
            "adjusted_fields": [],
            "reason": None,
            "error_field": None,
            "error_message": None,
        },
        mark_active_preset_custom=lambda: None,
    )

    with app.test_request_context(
        "/scheduler/config/preset/apply",
        method="POST",
        data={"preset_name": "demo", "next": "http://evil.example/x"},
    ):
        g.services = SimpleNamespace(config_service=cfg_svc)
        response = scheduler_config_mod.preset_apply()

    assert response.location.endswith("/scheduler/config")


def test_scheduler_batches_invalid_next_uses_local_success_and_failure_fallbacks(monkeypatch) -> None:
    import web.routes.domains.scheduler.scheduler_batches as scheduler_batches_mod

    app = _build_app()
    monkeypatch.setattr(scheduler_batches_mod, "url_for", _fake_url_for)

    with app.test_request_context(
        "/scheduler/batches/B001/delete",
        method="POST",
        data={"next": "http://evil.example/x"},
    ):
        g.services = SimpleNamespace(batch_service=SimpleNamespace(delete=lambda _batch_id: None))
        response = scheduler_batches_mod.delete_batch("B001")

    assert response.location.endswith("/scheduler/batches")

    def _raise_validation(_batch_id):
        raise ValidationError("删除失败", field="batch_id")

    with app.test_request_context(
        "/scheduler/batches/B001/delete",
        method="POST",
        data={"next": "http://evil.example/x"},
    ):
        g.services = SimpleNamespace(batch_service=SimpleNamespace(delete=_raise_validation))
        response = scheduler_batches_mod.delete_batch("B001")

    assert response.location.endswith("/scheduler/batches/B001")


def test_scheduler_batch_bulk_actions_preserve_safe_next(monkeypatch) -> None:
    import web.routes.domains.scheduler.scheduler_batches as scheduler_batches_mod

    app = _build_app()
    monkeypatch.setattr(scheduler_batches_mod, "url_for", _fake_url_for)

    safe_next = "/scheduler/batches?status=&only_ready=no&page=2&per_page=20"
    with app.test_request_context(
        "/scheduler/batches/bulk/update",
        method="POST",
        data={"next": safe_next, "batch_ids": "B001"},
    ):
        g.services = SimpleNamespace(batch_service=SimpleNamespace())
        response = scheduler_batches_mod.bulk_update_batches()

    assert response.location.endswith(safe_next)

    with app.test_request_context(
        "/scheduler/batches/bulk/delete",
        method="POST",
        data={"next": "http://evil.example/x"},
    ):
        g.services = SimpleNamespace(batch_service=SimpleNamespace(delete=lambda _batch_id: None))
        response = scheduler_batches_mod.bulk_delete_batches()

    assert response.location.endswith("/scheduler/batches")


def test_scheduler_batch_detail_actions_preserve_return_context(monkeypatch) -> None:
    import web.routes.domains.scheduler.scheduler_batch_detail as batch_detail_mod
    import web.routes.domains.scheduler.scheduler_batches as scheduler_batches_mod
    import web.routes.domains.scheduler.scheduler_ops as scheduler_ops_mod

    app = _build_app()
    monkeypatch.setattr(scheduler_batches_mod, "url_for", _fake_url_for)
    monkeypatch.setattr(scheduler_ops_mod, "url_for", _fake_url_for)
    monkeypatch.setattr(batch_detail_mod, "url_for", _fake_url_for)
    monkeypatch.setattr(batch_detail_mod, "operation_update_token", lambda op_id: f"tok-{op_id}")
    safe_next = "/scheduler/batches?status=&only_ready=no&page=2&per_page=20"

    batch = SimpleNamespace(
        batch_id="B001",
        part_no="P001",
        quantity=10,
        due_date=None,
        priority="normal",
        ready_status="yes",
        remark=None,
    )

    with app.test_request_context(
        "/scheduler/batches/create",
        method="POST",
        data={"next": safe_next, "batch_id": "B001", "part_no": "P001", "quantity": "10"},
    ):
        g.services = SimpleNamespace(
            batch_service=SimpleNamespace(
                create_batch_from_template=lambda **_kwargs: batch,
                list_operations=lambda _batch_id: [],
                consume_user_visible_warnings=lambda: [],
            )
        )
        response = scheduler_batches_mod.create_batch()

    assert response.location.endswith(f"/scheduler/batches/B001?next={safe_next}")

    with app.test_request_context(
        "/scheduler/batches/B001/generate-ops",
        method="POST",
        data={"next": safe_next},
    ):
        g.services = SimpleNamespace(
            batch_service=SimpleNamespace(
                get=lambda _batch_id: batch,
                create_batch_from_template=lambda **_kwargs: None,
                list_operations=lambda _batch_id: [],
                consume_user_visible_warnings=lambda: [],
            )
        )
        response = scheduler_batches_mod.generate_ops("B001")

    assert response.location.endswith(f"/scheduler/batches/B001?next={safe_next}")

    op = SimpleNamespace(batch_id="B001", source="internal")
    with app.test_request_context(
        "/scheduler/ops/update-token/tok-1",
        method="POST",
        query_string={"next": safe_next},
        data={"machine_id": "M1", "operator_id": "O1"},
    ):
        g.services = SimpleNamespace(
            schedule_service=SimpleNamespace(
                get_operation=lambda _op_id: op,
                update_internal_operation=lambda **_kwargs: None,
            )
        )
        monkeypatch.setattr(scheduler_ops_mod, "_operation_id_from_token", lambda _token: 1)
        response = scheduler_ops_mod.update_op_by_token("tok-1")

    assert response.location.endswith(f"/scheduler/batches/B001?next={safe_next}")

    with app.test_request_context("/scheduler/batches/B001", query_string={"next": safe_next}):
        monkeypatch.setattr(batch_detail_mod, "render_template", lambda _tpl, **ctx: ctx)
        monkeypatch.setattr(batch_detail_mod, "_resolve_schedule_placement", lambda *_args, **_kwargs: None)
        g.db = object()
        g.services = SimpleNamespace(
            batch_service=SimpleNamespace(
                get=lambda _batch_id: SimpleNamespace(
                    to_dict=lambda: {
                        "batch_id": "B001",
                        "priority": "normal",
                        "ready_status": "yes",
                        "status": "pending",
                    },
                    batch_id="B001",
                    priority="normal",
                    ready_status="yes",
                    status="pending",
                )
            ),
            schedule_service=SimpleNamespace(
                list_batch_operations=lambda **_kwargs: [
                    SimpleNamespace(id=7, source="internal", to_dict=lambda: {"id": 7, "source": "internal"})
                ],
                get_external_merge_hint=lambda _op_id: {},
            ),
            machine_service=SimpleNamespace(list=lambda status=None: []),
            operator_service=SimpleNamespace(list=lambda status=None: []),
            supplier_service=SimpleNamespace(list=lambda status=None: []),
            operator_machine_query_service=SimpleNamespace(list_simple_rows_for_machine_operator_sets=lambda *_args: []),
            config_service=SimpleNamespace(get_snapshot=lambda: SimpleNamespace(prefer_primary_skill="no")),
        )
        context = batch_detail_mod.batch_detail("B001")

    assert context["batch_return_next"] == safe_next
    assert context["operation_update_actions"]["opform_1"].endswith(f"?next={safe_next}")


def test_personnel_actions_preserve_safe_next_and_reject_external_next(monkeypatch) -> None:
    import web.routes.personnel_pages as personnel_mod

    app = _build_app()
    monkeypatch.setattr(personnel_mod, "url_for", _fake_url_for)
    safe_next = "/personnel/?team_id=TEAM-01&page=2&per_page=50"

    with app.test_request_context(
        "/personnel/OP001/delete",
        method="POST",
        data={"next": safe_next},
    ):
        g.db = object()
        monkeypatch.setattr(personnel_mod, "OperatorService", lambda *_args, **_kwargs: SimpleNamespace(delete=lambda _operator_id: None))
        response = personnel_mod.delete_operator("OP001")

    assert response.location.endswith(safe_next)

    with app.test_request_context(
        "/personnel/bulk/status",
        method="POST",
        data={"next": "http://evil.example/x"},
    ):
        g.db = object()
        response = personnel_mod.bulk_set_status()

    assert response.location.endswith("/personnel/")


def test_personnel_detail_actions_preserve_return_context(monkeypatch) -> None:
    import web.routes.personnel_pages as personnel_mod

    app = _build_app()
    monkeypatch.setattr(personnel_mod, "url_for", _fake_url_for)
    safe_next = "/personnel/?team_id=TEAM-01&page=2&per_page=50"
    operator = SimpleNamespace(operator_id="OP001", name="张三", status="active")

    with app.test_request_context(
        "/personnel/create",
        method="POST",
        data={"next": safe_next, "operator_id": "OP001", "name": "张三"},
    ):
        g.db = object()
        monkeypatch.setattr(
            personnel_mod,
            "OperatorService",
            lambda *_args, **_kwargs: SimpleNamespace(create=lambda **_kwargs: operator),
        )
        response = personnel_mod.create_operator()

    assert response.location.endswith(f"/personnel/OP001?next={safe_next}")

    with app.test_request_context(
        "/personnel/OP001/update",
        method="POST",
        data={"next": safe_next, "name": "张三", "status": "active"},
    ):
        g.db = object()
        monkeypatch.setattr(
            personnel_mod,
            "OperatorService",
            lambda *_args, **_kwargs: SimpleNamespace(update=lambda **_kwargs: operator),
        )
        response = personnel_mod.update_operator("OP001")

    assert response.location.endswith(f"/personnel/OP001?next={safe_next}")

    with app.test_request_context(
        "/personnel/OP001/link/add",
        method="POST",
        data={"next": safe_next, "machine_id": "M1"},
    ):
        g.db = object()
        monkeypatch.setattr(
            personnel_mod,
            "OperatorMachineService",
            lambda *_args, **_kwargs: SimpleNamespace(add_link=lambda **_kwargs: None),
        )
        response = personnel_mod.add_link("OP001")

    assert response.location.endswith(f"/personnel/OP001?next={safe_next}")


def test_personnel_create_failure_preserves_safe_next(monkeypatch) -> None:
    import web.routes.personnel_pages as personnel_mod

    app = _build_app()
    monkeypatch.setattr(personnel_mod, "url_for", _fake_url_for)
    safe_next = "/personnel/?team_id=TEAM-01&page=3&per_page=50"

    def _raise_create(**_kwargs):
        raise ValidationError("创建失败", field="operator_id")

    with app.test_request_context(
        "/personnel/create",
        method="POST",
        data={"next": safe_next, "operator_id": "", "name": "张三"},
    ):
        g.db = object()
        monkeypatch.setattr(
            personnel_mod,
            "OperatorService",
            lambda *_args, **_kwargs: SimpleNamespace(create=_raise_create),
        )
        response = personnel_mod.create_operator()

    assert response.location.endswith(safe_next)

    with app.test_request_context(
        "/personnel/create",
        method="POST",
        data={"next": "http://evil.example/x", "operator_id": "", "name": "张三"},
    ):
        g.db = object()
        response = personnel_mod.create_operator()

    assert response.location.endswith("/personnel/")


def test_personnel_detail_accepts_safe_return_context(monkeypatch) -> None:
    import web.routes.personnel_pages as personnel_mod

    app = _build_app()
    monkeypatch.setattr(personnel_mod, "url_for", _fake_url_for)
    monkeypatch.setattr(
        personnel_mod,
        "build_personnel_detail_context",
        lambda _db, operator_id, op_logger=None: {
            "operator": SimpleNamespace(operator_id=operator_id, name="张三", team_id=None, status="active", remark=None),
            "operator_team_name": None,
            "status_options": [],
            "team_options": [],
            "linked_machines": [],
            "machine_options": [],
            "link_dirty_summary": None,
        },
    )
    monkeypatch.setattr(personnel_mod, "render_template", lambda _tpl, **ctx: ctx)
    safe_next = "/personnel/?team_id=TEAM-01&page=2&per_page=50"

    with app.test_request_context("/personnel/OP001", query_string={"next": safe_next}):
        g.db = object()
        g.op_logger = None
        context = personnel_mod.detail_page("OP001")

    assert context["personnel_return_url"] == safe_next
    assert context["personnel_return_next"] == safe_next


def test_personnel_calendar_preserves_original_list_return_context(monkeypatch) -> None:
    import web.routes.personnel_calendar_pages as calendar_mod

    app = _build_app()
    monkeypatch.setattr(calendar_mod, "url_for", _fake_url_for)
    operator = SimpleNamespace(operator_id="OP001", name="张三", to_dict=lambda: {"operator_id": "OP001", "name": "张三"})
    monkeypatch.setattr(calendar_mod, "OperatorService", lambda *_args, **_kwargs: SimpleNamespace(get=lambda _operator_id: operator))
    monkeypatch.setattr(calendar_mod, "CalendarService", lambda *_args, **_kwargs: SimpleNamespace(list_operator_calendar=lambda _operator_id: []))
    monkeypatch.setattr(
        calendar_mod,
        "ConfigService",
        lambda *_args, **_kwargs: SimpleNamespace(
            get_holiday_default_efficiency_display_state=lambda **_kwargs: (0.8, False, "")
        ),
    )
    monkeypatch.setattr(calendar_mod, "render_template", lambda _tpl, **ctx: ctx)
    safe_next = "/personnel/?team_id=TEAM-01&page=2&per_page=50"

    with app.test_request_context("/personnel/OP001/calendar", query_string={"next": safe_next}):
        g.db = object()
        g.op_logger = None
        g.app_logger = None
        context = calendar_mod.operator_calendar_page("OP001")

    assert context["personnel_return_url"] == safe_next
    assert context["personnel_return_next"] == safe_next

    with app.test_request_context("/personnel/OP001/calendar", query_string={"next": "http://evil.example/x"}):
        g.db = object()
        g.op_logger = None
        g.app_logger = None
        context = calendar_mod.operator_calendar_page("OP001")

    assert context["personnel_return_url"] == "/personnel/"
    assert context["personnel_return_next"] == "/personnel/"


def test_current_public_return_url_uses_public_plan_token_and_drops_internal_keys() -> None:
    from urllib.parse import parse_qs, urlsplit

    from web.navigation_context import current_public_return_url
    from web.routes.domains.scheduler.scheduler_plan_context_token import scenario_id_from_plan_context_token

    app = _build_app()
    scenario_id = "scenario-secret-context"

    with app.test_request_context(
        "/reports/overdue",
        query_string={
            "version": "7",
            "plan_role": "adopted",
            "scenario_id": scenario_id,
            "page": "2",
            "op_id": "99",
            "schedule_id": "100",
            "source_table": "schedule",
        },
    ):
        public_url = current_public_return_url()
        parsed = urlsplit(public_url)
        query = parse_qs(parsed.query)
        token = query.get("plan_context_token", [""])[0]
        assert parsed.path == "/reports/overdue"
        assert query["version"] == ["7"]
        assert query["page"] == ["2"]
        assert "scenario_id" not in query
        assert "op_id" not in query
        assert "schedule_id" not in query
        assert "source_table" not in query
        assert token
        assert scenario_id not in public_url
        assert scenario_id_from_plan_context_token(token) == scenario_id


def test_batch_and_personnel_bulk_forms_submit_current_page_next() -> None:
    batch_template = (REPO_ROOT / "templates/scheduler/batches_manage.html").read_text(encoding="utf-8")
    scheduler_batch_template = (REPO_ROOT / "templates/scheduler/batches.html").read_text(encoding="utf-8")
    personnel_template = (REPO_ROOT / "templates/personnel/list.html").read_text(encoding="utf-8")
    batch_detail_template = (REPO_ROOT / "templates/scheduler/batch_detail.html").read_text(encoding="utf-8")
    personnel_detail_template = (REPO_ROOT / "templates/personnel/detail.html").read_text(encoding="utf-8")

    assert batch_template.count('name="next" value="{{ current_public_return_url() }}"') >= 3
    assert "url_for('scheduler.batch_detail', batch_id=r.batch_id, next=current_public_return_url())" in batch_template
    assert scheduler_batch_template.count(
        "url_for('scheduler.batch_detail', batch_id=r.batch_id, next=current_public_return_url())"
    ) >= 2
    assert 'name="next" value="{{ batch_return_next }}"' in batch_detail_template
    assert "batch_return_url" in batch_detail_template
    assert personnel_template.count('name="next" value="{{ current_public_return_url() }}"') >= 3
    assert (
        "url_for('personnel.detail_page', operator_id=r.operator_id, next=current_public_return_url())"
        in personnel_template
    )
    assert "personnel_return_url" in personnel_detail_template
    assert 'name="next" value="{{ personnel_return_next }}"' in personnel_detail_template
    assert 'name="next" value="{{ personnel_return_next }}"' in (
        REPO_ROOT / "templates/personnel/calendar.html"
    ).read_text(encoding="utf-8")

    allowed_next_tokens = (
        "next=current_public_return_url()",
        "next=batch_return_next",
        "next=personnel_return_next",
    )
    for template_path in (REPO_ROOT / "templates").glob("**/*.html"):
        template_text = template_path.read_text(encoding="utf-8")
        for endpoint in ("scheduler.batch_detail", "personnel.detail_page"):
            pattern = re.compile(r"url_for\(['\"]" + re.escape(endpoint) + r"['\"][^)]*\)")
            offenders = [
                call.group(0)
                for call in pattern.finditer(template_text)
                if not any(token in call.group(0) for token in allowed_next_tokens)
            ]
            assert not offenders, f"{template_path.relative_to(REPO_ROOT)} detail links missing next: {offenders}"
