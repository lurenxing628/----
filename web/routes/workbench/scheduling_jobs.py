"""Explicit registration only. The host must connect and enable its worker dispatcher."""

from functools import wraps
from uuid import uuid4

from flask import current_app, g, request
from werkzeug.exceptions import HTTPException

from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain
from core.models.workbench_run_job import valid_data_context_ref
from core.shared.key_sets import keys_conform
from web.api_responses import failure, json_response, query_success
from web.runtime_host import wall_clock

from .api_responses import rejection_failure
from .data_context import request_data_context
from .preflight import evaluate_preflight_input_prepared
from .read_context import current_snapshot_time, unbound_snapshot
from .request_json import BodyTexts, command_body, read_json_body, rejecter, single_value_arguments
from .write_context import issue_write_context, validate_write_context


def _service():
    from core.services.workbench.run.jobs import WorkbenchRunService

    dispatcher = current_app.extensions.get("workbench_run_dispatcher")
    enabled = current_app.config.get("WORKBENCH_RUN_JOBS_ENABLED") is True and callable(dispatcher)
    return WorkbenchRunService(g.db, integration_enabled=enabled, input_resolver=evaluate_preflight_input_prepared,
                               context_factory=issue_write_context, context_validator=validate_write_context,
                               clock=wall_clock(current_app), data_context=request_data_context())


def _boundary(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            response = function(*args, **kwargs)
        except WorkbenchCommandRejected as exc:
            response = rejection_failure(exc)
        except WorkbenchCommandUncertain as exc:
            request_ref = uuid4().hex
            current_app.logger.exception("排产受理结果待核实 request_ref=%s", request_ref)
            response = failure("storage_failure", str(exc), 500, committed="unknown", request_key=exc.request_key,
                               result_target="/api/workbench/v1/scheduling/requests/" + exc.request_key,
                               request_ref=request_ref)
        except HTTPException as exc:
            response = failure("invalid_input", "提交的内容格式不正确，这次排产没有开始。请刷新页面后重新点「确认开始排产」。", exc.code or 400)
        except Exception:
            request_ref = uuid4().hex
            current_app.logger.exception("排产运行接口失败 request_ref=%s", request_ref)
            is_accept = function.__name__ == "accept_scheduling_run"
            request_key = g.get("workbench_request_key") if is_accept else None
            response = failure("storage_failure", "排产记录没有读出来。请刷新重试；仍不行请联系维护人员，并告知下方编号。", 500,
                               committed="unknown" if is_accept else False, request_key=request_key,
                               result_target=("/api/workbench/v1/scheduling/requests/" + request_key) if request_key else None,
                               request_ref=request_ref)
        return response
    return wrapped


_BODY = BodyTexts(transport="提交的内容不完整，这次排产没有开始。请刷新页面后重新点「确认开始排产」。",
                  malformed="提交的内容格式不正确，这次排产没有开始。请刷新页面后重新点「确认开始排产」。",
                  incomplete="提交的内容不完整或有多余项，这次排产没有开始。请刷新页面后重新点「确认开始排产」。")


def _query(data, as_of):
    # Run and request lookups read live state; no read snapshot backs them.
    return query_success(data, unbound_snapshot(as_of))


@_boundary
def preview_scheduling_run():
    value = read_json_body(_BODY)
    if not keys_conform(value, ("input_ref",)):
        rejecter(_BODY.incomplete)()
    now = current_snapshot_time()
    return _query(_service().preview(value["input_ref"], now=now), now)


@_boundary
def accept_scheduling_run():
    # 排产受理的业务输入是排产检查交回的 input_ref，不是普通命令的 input。
    value = command_body(_BODY, payload="input_ref",
                         stale="还没有确认开始排产，这次排产没有开始。请在排产检查页点「开始排产」。")
    result = _service().accept(**value)
    if not result["replayed"]:
        try:
            current_app.extensions["workbench_run_dispatcher"](result["run_ref"])
        except Exception:
            current_app.logger.exception("排产已受理，但交给本机worker失败；不得重新受理")
            result["dispatch_pending"] = True
    response = json_response(result)
    response.status_code = 202
    return response


@_boundary
def get_scheduling_run(run_ref):
    if request.args:
        raise WorkbenchCommandRejected("invalid_input", "查询这次排产不需要其他条件。请直接点「刷新」。", 400)
    as_of = current_snapshot_time()
    return _query(_service().get(run_ref), as_of)


@_boundary
def get_scheduling_request(request_key):
    # The browser always sends the data generation it submitted under.
    incomplete = "查询这次排产的条件不完整或有多余项。请刷新页面后重新查询。"
    previous = single_value_arguments({"data_context_ref"}, required={"data_context_ref"}, message=incomplete)["data_context_ref"]
    if not valid_data_context_ref(previous):
        raise WorkbenchCommandRejected("invalid_input", incomplete, 400)
    as_of = current_snapshot_time()
    service = _service()
    data = service.lookup(request_key)
    records = service.data_context.capture()
    resolution = "found" if data is not None else service.data_context.resolve_missing(previous, records=records)
    return _query({"found": data is not None, "run": data, "resolution": resolution,
                   "data_context_ref": service.data_context.ref(records=records)}, as_of)


def register_scheduling_job_routes(bp):
    bp.add_url_rule("/api/workbench/v1/scheduling/runs/preview", view_func=preview_scheduling_run, methods=["POST"])
    bp.add_url_rule("/api/workbench/v1/scheduling/runs", view_func=accept_scheduling_run, methods=["POST"])
    bp.add_url_rule("/api/workbench/v1/scheduling/runs/<run_ref>", view_func=get_scheduling_run, methods=["GET"])
    bp.add_url_rule("/api/workbench/v1/scheduling/requests/<request_key>", view_func=get_scheduling_request, methods=["GET"])
