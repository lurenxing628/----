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
        bound = json.loads(resolve_public_token(INPUT_SCOPE, input_ref, message="排产检查结果已过期，这次排产没有开始。请重新点「开始排产检查」。", field="input_ref"))
    except (ValidationError, ValueError, TypeError) as exc:
        raise WorkbenchCommandRejected("snapshot_stale", "排产检查结果已过期或读不出来，这次排产没有开始。请重新点「开始排产检查」。") from exc
    normalized = normalize_preflight_input(bound["input"])
    if bound["scope"] != {"source": "production", "batch_refs": normalized["batch_refs"]} or bound["fingerprint"] != full_facts_fingerprint(conn):
        raise WorkbenchCommandRejected("snapshot_stale", "排产检查之后批次范围或现场记录有变化，这次排产没有开始。请重新点「开始排产检查」。")
    return normalized


def scheduling_preflight():
    try:
        if request.args or not request.is_json:
            raise WorkbenchCommandRejected("invalid_input", "提交的内容格式不正确，排产检查没有执行。请刷新页面后重新点「开始排产检查」。", 400)
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
        response = failure("invalid_input", "提交的内容读不出来，排产检查没有执行。请刷新页面后重新点「开始排产检查」。", exc.code or 400)
    except Exception:
        current_app.logger.exception("只读排产前检查失败")
        response = failure("storage_failure", "排产检查没有完成，没有生成这次排产，也没有改动任何业务数据。请刷新重试；仍不行请联系维护人员，并告知下方编号。", 500, committed=False)
    response.headers["Cache-Control"] = "no-store"
    return response


def register_preflight_routes(bp):
    bp.add_url_rule("/api/workbench/v1/scheduling/preflight", view_func=scheduling_preflight, methods=["POST"])
