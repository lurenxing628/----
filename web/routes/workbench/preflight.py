"""Independent read-only registration. Host owns mounting and worker integration."""

import json
from datetime import datetime

from flask import current_app, g, request
from werkzeug.exceptions import HTTPException

from core.errors import ValidationError
from core.models.workbench_command import WorkbenchCommandRejected, canonical_json
from core.models.workbench_preflight import normalize_preflight_input
from core.services.workbench.preflight import PreflightService
from core.services.workbench.preflight_facts import full_facts_fingerprint
from web.public_token_registry import issue_public_token_with_expiry, resolve_public_token

from .api_responses import failure, query_success
from .read_context import bind_read_snapshot

INPUT_SCOPE = "workbench-preflight-input-v1"


def resolve_preflight_input(conn, input_ref):
    """Caller must hold its admission transaction. This does not authorize a run."""
    if not conn.in_transaction:
        raise RuntimeError("Preflight input revalidation requires the caller's transaction")
    try:
        bound = json.loads(resolve_public_token(INPUT_SCOPE, input_ref, message="检查结果已失效，请重新检查。", field="input_ref"))
    except (ValidationError, ValueError, TypeError) as exc:
        raise WorkbenchCommandRejected("snapshot_stale", "检查结果已失效，请重新检查；未受理排产。") from exc
    normalized = normalize_preflight_input(bound["input"])
    if bound["scope"] != {"source": "production", "batch_refs": normalized["batch_refs"]} or bound["fingerprint"] != full_facts_fingerprint(conn):
        raise WorkbenchCommandRejected("snapshot_stale", "检查后的范围或生产事实已经变化，请重新检查；未受理排产。")
    return normalized


def scheduling_preflight():
    try:
        if request.args or not request.is_json:
            raise WorkbenchCommandRejected("invalid_input", "排产前检查只接受完整JSON参数。", 400)
        data, fingerprint = PreflightService(g.db).evaluate(request.get_json())
        binding = {"input": data["normalized_input"], "scope": data["scope"], "fingerprint": fingerprint}
        token, expires = issue_public_token_with_expiry(INPUT_SCOPE, canonical_json(binding), ttl_seconds=900)
        data.update(input_ref=token, input_expires_at=datetime.fromtimestamp(expires).strftime("%Y-%m-%dT%H:%M:%S"),
                    write_context={"write_token": None, "expires_at": None,
                                   "capabilities": {"scheduling.preflight": True, "scheduling.run": False},
                                   "blocked_reasons": data["run_blocked_reasons"]})
        response = query_success(data, bind_read_snapshot({"kind": "preflight", **binding["scope"], "input": binding["input"]}, fingerprint))
    except WorkbenchCommandRejected as exc:
        response = failure(exc.code, str(exc), exc.status)
    except HTTPException as exc:
        response = failure("invalid_input", "排产前检查请求格式不正确。", exc.code or 400)
    except Exception:
        current_app.logger.exception("只读排产前检查失败")
        response = failure("storage_failure", "排产前检查读取失败；未创建运行或写入业务数据。", 500, committed=False)
    response.headers["Cache-Control"] = "no-store"
    return response


def register_preflight_routes(bp):
    bp.add_url_rule("/api/workbench/v1/scheduling/preflight", view_func=scheduling_preflight, methods=["POST"])
