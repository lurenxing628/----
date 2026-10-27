"""Scheduling input checks and remembered form input; host owns worker integration."""

from datetime import datetime
from types import MappingProxyType
from typing import TYPE_CHECKING
from uuid import uuid4

from flask import current_app, g, request
from werkzeug.exceptions import HTTPException

from core.errors import AppError, ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected, validate_request_key
from core.models.workbench_preflight import (
    SCHEDULING_PREFERENCES_ACTION,
    SCHEDULING_PREFERENCES_SUBJECT,
)
from core.models.workbench_run_job import new_run_ref
from core.services.workbench.run.preferences import SchedulingPreferencesService
from core.shared.strict_json import canonical_json
from web.api_responses import failure, json_response, query_success
from web.public_token_registry import issue_public_token_with_expiry, resolve_public_token

from .api_responses import api_endpoint, domain_failure
from .read_context import bind_read_snapshot
from .write_context import issue_write_context, validate_write_context

if TYPE_CHECKING:
    from core.services.workbench.run.preflight import PreparedPreflight

INPUT_SCOPE = "workbench-preflight-input-v1"


def _preflight_binding(conn, input_ref):
    if not conn.in_transaction:
        raise RuntimeError("Preflight input revalidation requires the caller's transaction")
    try:
        bound = resolve_public_token(INPUT_SCOPE, input_ref, message="排产检查结果已过期，这次排产没有开始。请重新点「开始排产检查」。", field="input_ref")
    except ValidationError as exc:
        raise WorkbenchCommandRejected("snapshot_stale", "排产检查结果已过期或读不出来，这次排产没有开始。请重新点「开始排产检查」。") from exc
    normalized = bound["input"]
    if bound["scope"] != {"source": "production", "batch_refs": normalized["batch_refs"]}:
        raise WorkbenchCommandRejected("snapshot_stale", "排产检查之后批次范围或现场记录有变化，这次排产没有开始。请重新点「开始排产检查」。")
    return normalized, bound["fingerprint"]


def _require_current(original, current):
    if original != current:
        raise WorkbenchCommandRejected("snapshot_stale", "排产检查之后批次范围或现场记录有变化，这次排产没有开始。请重新点「开始排产检查」。")


def evaluate_preflight_input_prepared(conn, input_ref, *, facts=None) -> "PreparedPreflight":
    """Private same-transaction continuation; it never enters the public token."""
    from core.services.workbench.run.preflight import PreflightService

    normalized, original = _preflight_binding(conn, input_ref)
    prepared = PreflightService(conn, facts=facts).evaluate_prepared(normalized)
    _require_current(original, prepared.fingerprint)
    return prepared


def scheduling_preflight():
    from core.services.workbench.run.preflight import PreflightService

    try:
        if request.args or not request.is_json:
            raise WorkbenchCommandRejected("invalid_input", "提交的内容格式不正确，排产检查没有执行。请刷新页面后重新点「开始排产检查」。", 400)
        data, fingerprint = PreflightService(g.db).evaluate(request.get_json())
        binding = {"input": data["normalized_input"], "scope": data["scope"], "fingerprint": fingerprint,
                   "check_ref": new_run_ref()}
        token, expires = issue_public_token_with_expiry(INPUT_SCOPE, MappingProxyType(binding), key=binding["check_ref"],
                                                       group=fingerprint, ttl_seconds=900)
        data.update(input_ref=token, input_expires_at=datetime.fromtimestamp(expires).strftime("%Y-%m-%dT%H:%M:%S"),
                    write_context={"write_token": None, "expires_at": None,
                                   "capabilities": {"scheduling.preflight": True, "scheduling.run": False},
                                   "blocked_reasons": data["run_blocked_reasons"]})
        response = query_success(data, {"snapshot_ref": token, "as_of": datetime.now().isoformat(timespec="seconds")})
    except WorkbenchCommandRejected as exc:
        response = failure(exc.code, str(exc), exc.status)
    except AppError as exc:
        response = domain_failure(exc)
    except HTTPException as exc:
        response = failure("invalid_input", "提交的内容读不出来，排产检查没有执行。请刷新页面后重新点「开始排产检查」。", exc.code or 400)
    except Exception:
        request_ref = uuid4().hex
        current_app.logger.exception("只读排产前检查失败 request_ref=%s", request_ref)
        response = failure("storage_failure", "排产检查没有完成，没有生成这次排产，也没有改动任何业务数据。请刷新重试；仍不行请联系维护人员，并告知下方编号。", 500,
                           committed=False, request_ref=request_ref)
    response.headers["Cache-Control"] = "no-store"
    return response


@api_endpoint
def scheduling_preferences_read():
    if request.args:
        raise WorkbenchCommandRejected("invalid_input", "排产范围读取条件不正确。", 400)
    with TransactionManager(g.db).transaction():
        data, state = SchedulingPreferencesService(g.db).snapshot()
        data["write_context"] = issue_write_context(SCHEDULING_PREFERENCES_SUBJECT, [SCHEDULING_PREFERENCES_ACTION], state)
        snapshot = bind_read_snapshot({"kind": "scheduling_preferences"}, canonical_json(state))
    response = query_success(data, snapshot)
    response.headers["Cache-Control"] = "no-store"
    return response


@api_endpoint
def scheduling_preferences_write():
    if request.args or not request.is_json:
        raise WorkbenchCommandRejected("invalid_input", "排产范围的保存内容格式不正确。", 400)
    body = request.get_json()
    if type(body) is not dict or set(body) != {"request_key", "write_token", "input"}:
        raise WorkbenchCommandRejected("invalid_input", "排产范围的保存内容不完整或有多余项。", 400)
    validate_request_key(body["request_key"])
    g.workbench_request_key = body["request_key"]
    result = SchedulingPreferencesService(g.db, current_app.logger).save(
        body["input"], request_key=body["request_key"],
        validate_context=lambda subject, action, state: validate_write_context(body["write_token"], subject, action, state))
    response = json_response(result)
    response.headers["Cache-Control"] = "no-store"
    return response


def register_preflight_routes(bp):
    bp.add_url_rule("/api/workbench/v1/scheduling/preflight", view_func=scheduling_preflight, methods=["POST"])
    bp.add_url_rule("/api/workbench/v1/scheduling/preferences", view_func=scheduling_preferences_read, methods=["GET"])
    bp.add_url_rule("/api/workbench/v1/scheduling/preferences", view_func=scheduling_preferences_write, methods=["POST"])
