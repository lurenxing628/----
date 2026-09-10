"""Explicit registration only. The host must connect and enable its worker dispatcher."""

import json
from functools import wraps

from flask import current_app, g, jsonify, request
from werkzeug.exceptions import HTTPException

from core.models.workbench_command import (
    WorkbenchCommandRejected,
    WorkbenchCommandUncertain,
    input_fingerprint,
    validate_request_key,
)
from core.services.workbench.run_jobs import WorkbenchRunService

from .api_responses import failure, query_success
from .preflight import resolve_preflight_input
from .read_context import bind_read_snapshot
from .write_context import issue_write_context, validate_write_context


def _service():
    dispatcher = current_app.extensions.get("workbench_run_dispatcher")
    enabled = current_app.config.get("WORKBENCH_RUN_JOBS_ENABLED") is True and callable(dispatcher)
    return WorkbenchRunService(g.db, integration_enabled=enabled, input_resolver=resolve_preflight_input,
                               context_factory=issue_write_context, context_validator=validate_write_context)


def _boundary(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            response = function(*args, **kwargs)
        except WorkbenchCommandRejected as exc:
            response = failure(exc.code, str(exc), exc.status)
        except WorkbenchCommandUncertain as exc:
            current_app.logger.exception("排产受理结果待核实")
            response = failure("storage_failure", str(exc), 500, committed="unknown")
            data = response.get_json()
            data["error"].update(request_key=exc.request_key,
                                 result_target="/api/workbench/v1/scheduling/requests/" + exc.request_key)
            response.set_data(json.dumps(data, ensure_ascii=False))
        except HTTPException as exc:
            response = failure("invalid_input", "排产请求格式不正确。", exc.code or 400)
        except Exception:
            current_app.logger.exception("排产运行接口失败")
            response = failure("storage_failure", "排产运行记录读取失败，请核对台账。", 500,
                               committed="unknown" if function.__name__ == "accept_scheduling_run" else False)
        response.headers["Cache-Control"] = "no-store"
        return response
    return wrapped


def _input(keys):
    if request.args or not request.is_json:
        raise WorkbenchCommandRejected("invalid_input", "排产接口只接受完整JSON参数。", 400)
    value = request.get_json()
    if not isinstance(value, dict) or set(value) != set(keys):
        raise WorkbenchCommandRejected("invalid_input", "排产参数缺失或含不支持字段。", 400)
    return value


def _query(data, scope):
    return query_success(data, bind_read_snapshot({"source": "production", **scope}, input_fingerprint(data)))


@_boundary
def preview_scheduling_run():
    value = _input(("input_ref",))
    return _query(_service().preview(value["input_ref"]), {"kind": "scheduling-run-preview", **value})


@_boundary
def accept_scheduling_run():
    value = _input(("input_ref", "write_token", "request_key"))
    validate_request_key(value["request_key"])
    result = _service().accept(**value)
    if not result["replayed"]:
        try:
            current_app.extensions["workbench_run_dispatcher"](result["run_ref"])
        except Exception:
            current_app.logger.exception("排产已受理，但交给本机worker失败；不得重新受理")
            result["dispatch_pending"] = True
    response = jsonify(result)
    response.status_code = 202
    return response


@_boundary
def get_scheduling_run(run_ref):
    if request.args:
        raise WorkbenchCommandRejected("invalid_input", "运行查询不接受额外参数。", 400)
    return _query(_service().get(run_ref), {"kind": "scheduling-run", "run_ref": run_ref})


@_boundary
def get_scheduling_request(request_key):
    if request.args:
        raise WorkbenchCommandRejected("invalid_input", "运行查询不接受额外参数。", 400)
    data = _service().lookup(request_key)
    return _query({"found": data is not None, "run": data}, {"kind": "scheduling-request", "request_key": request_key})


def register_scheduling_job_routes(bp):
    bp.add_url_rule("/api/workbench/v1/scheduling/runs/preview", view_func=preview_scheduling_run, methods=["POST"])
    bp.add_url_rule("/api/workbench/v1/scheduling/runs", view_func=accept_scheduling_run, methods=["POST"])
    bp.add_url_rule("/api/workbench/v1/scheduling/runs/<run_ref>", view_func=get_scheduling_run, methods=["GET"])
    bp.add_url_rule("/api/workbench/v1/scheduling/requests/<request_key>", view_func=get_scheduling_request, methods=["GET"])
