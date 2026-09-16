"""Trial commands and public validation, independent of legacy plan roles."""

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, NoReturn

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_plan_scope import local_time

MAX_TRIAL_TASKS = 10000
MAX_TRIAL_BYTES = 64 * 1024 * 1024
CREATE = "trial.create"
CHANGE = "trial.change"
SAVE = "trial.save"
DISCARD = "trial.discard"
ACTIONS = (CHANGE, SAVE, DISCARD)


def reject(code, message, status=409) -> NoReturn:
    raise WorkbenchCommandRejected(code, message, status)


def reference(value):
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{48}", value) is None:
        reject("invalid_input", "这条记录已失效，请刷新后重新选择。", 400)
    return value


def fields(value, required, optional=()):
    if type(value) is not dict or not set(required) <= set(value) or set(value) - set(required) - set(optional):
        reject("invalid_input", "提交内容缺少必填项或含有多余项，这次操作没有执行。请刷新页面后重试。", 400)


def create_input(value):
    fields(value, ("base",), ("scope",))
    base = value["base"]
    if type(base) is not dict or set(base) not in ({"plan_ref"}, {"candidate_ref"}):
        reject("invalid_input", "必须明确选择一个 plan_ref 或 candidate_ref，不能混用或改查最新计划。", 400)
    key = next(iter(base))
    return {"base": {key: reference(base[key])}, "scope": _scope(value.get("scope", {}))}


def _scope(scope):
    fields(scope, (), ("range_start", "range_end", "batch_refs", "resource_type", "resource_ref", "query"))
    if (scope.get("range_start") is None) != (scope.get("range_end") is None):
        reject("invalid_input", "显示范围起止时间必须一起提供。", 400)
    if scope.get("range_start") is not None:
        if local_time(scope["range_start"]) >= local_time(scope["range_end"]):
            reject("invalid_input", "显示范围开始必须早于结束。", 400)
    if "batch_refs" in scope:
        if type(scope["batch_refs"]) is not list or len(scope["batch_refs"]) > MAX_TRIAL_TASKS:
            reject("invalid_input", "请从批次列表里勾选批次。", 400)
        scope = dict(scope, batch_refs=sorted(set(reference(ref) for ref in scope["batch_refs"])))
    if "resource_type" in scope and scope["resource_type"] not in ("machine", "operator", "batch"):
        reject("invalid_input", "资源视图类型无效。", 400)
    if "resource_ref" in scope:
        reference(scope["resource_ref"])
        if "resource_type" not in scope:
            reject("invalid_input", "资源范围需要明确类型。", 400)
    if "query" in scope and (type(scope["query"]) is not str or len(scope["query"]) > 200):
        reject("invalid_input", "搜索内容无效。", 400)
    return scope


def change_input(value):
    fields(value, ("task_ref", "machine_ref", "operator_ref", "start"))
    return {"task_ref": reference(value["task_ref"]), "start": local_time(value["start"]),
            **{key: reference(value[key]) if value[key] is not None else None
               for key in ("machine_ref", "operator_ref")}}


def save_input(value):
    fields(value, ("name",))
    name = value["name"]
    if type(name) is not str or not name.strip() or len(name.strip()) > 120:
        reject("invalid_input", "试调方案名称请填 1 至 120 个字。", 400)
    return {"name": name.strip()}


def discard_input(value):
    fields(value, ("confirm",))
    if value["confirm"] is not True:
        reject("invalid_input", "请明确确认放弃指定草稿。", 400)
    return {"confirm": True}


def issue(code, message, task_ref=None, related_task_ref=None, severity="blocker"):
    result = {"code": code, "message": message, "severity": severity}
    if task_ref is not None:
        result["task_ref"] = task_ref
    if related_task_ref is not None:
        result["related_task_ref"] = related_task_ref
    return result


@dataclass(frozen=True)
class TrialValidation:
    status: str
    can_adopt: bool
    issues: List[Dict[str, Any]] = field(default_factory=list)
    constraints_status: str = "blocked"
    adoption: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


def validation(issues):
    state = "blocked" if any(row["severity"] == "blocker" for row in issues) else "warning" if issues else "valid"
    review = issue("scenario_adoption_preview_required", "保存试调方案后，正式采用前需要单独预检。", severity="warning")
    return TrialValidation(state, False, list(issues), state,
                           {"available": False, "blocked_reasons": [review]}).to_dict()
