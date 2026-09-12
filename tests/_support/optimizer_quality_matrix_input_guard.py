"""Version-neutral fixture guard; candidate resources are decisions, not facts."""
from __future__ import annotations

from copy import deepcopy


class MatrixInputGuard:
    def __init__(self, scheduler, env, shared):
        self.scheduler = scheduler
        self.calendar = env["calendar"]
        self.env = env
        self.shared = shared
        self.expected = deepcopy(shared)
        self.config = deepcopy(vars(scheduler.config))
        self.facts = deepcopy({key: env[key] for key in ("data", "graph", "operations", "batches", "downtime", "resource_pool")})

    def check_source(self):
        if self.scheduler.calendar is not self.calendar or self.env["calendar"] is not self.calendar:
            raise ValueError("same-environment scheduler/calendar mismatch")
        if vars(self.scheduler.config) != self.config:
            raise ValueError("same-environment scheduler config changed")
        if self.shared != self.expected or any(self.env[key] != value for key, value in self.facts.items()):
            raise ValueError("same-environment original facts changed")
        _check_operations(self.shared["operations"], self.expected["operations"], False, self.expected["resource_pool"])

    def check_decode(self, actual_scheduler, kwargs):
        self.check_source()
        if actual_scheduler is not self.scheduler:
            raise ValueError("same-environment scheduler/calendar mismatch")
        if any(key not in kwargs or kwargs[key] != value for key, value in self.expected.items() if key != "operations"):
            raise ValueError("same-environment schedule inputs changed")
        profile = kwargs.get("strategy_params", {}).get("graph_ready_profile", {})
        repair = profile.get("candidate_origin") == "graph_ready_v2_repaired" and profile.get("candidate_policy") == "elite_repair"
        _check_operations(kwargs.get("operations"), self.expected["operations"], repair, self.expected["resource_pool"])


def _check_operations(actual, expected, repair, pool):
    if not isinstance(actual, list) or len(actual) != len(expected):
        raise ValueError("same-environment operation count/order changed")
    for chosen, original in zip(actual, expected):
        before, after = vars(original), vars(chosen)
        if set(after) != set(before):
            raise ValueError("same-environment operation fields changed")
        for field in before:
            if field in {"machine_id", "operator_id"}:
                continue
            if type(after[field]) is not type(before[field]) or after[field] != before[field]:
                raise ValueError("same-environment operation fact changed: " + field)
        _check_resource_choice(before, after, repair, pool)


def _check_resource_choice(before, after, repair, pool):
    fields = ("machine_id", "operator_id")
    changed = [key for key in fields if type(after[key]) is not type(before[key]) or after[key] != before[key]]
    if not changed:
        return
    if not repair or before["source"] != "internal":
        raise ValueError("same-environment resource override outside repair")
    for key in changed:
        if str(before[key] or "").strip():
            raise ValueError("same-environment fixed resource changed")
        if not isinstance(after[key], str) or not after[key].strip() or after[key] != after[key].strip():
            raise ValueError("same-environment invalid resource override")
    _check_pool_choice(before, after, pool)


def _check_pool_choice(before, after, pool):
    machine, operator = after["machine_id"], after["operator_id"]
    if not isinstance(pool, dict):
        raise ValueError("same-environment resource override without qualification pool")
    if machine not in pool["machines_by_op_type"].get(before["op_type_id"], ()):
        raise ValueError("same-environment machine outside original operation-type pool")
    if operator not in pool["operators_by_machine"].get(machine, ()):
        raise ValueError("same-environment operator outside original machine pool")
    if "machines_by_operator" in pool and machine not in pool["machines_by_operator"].get(operator, ()):
        raise ValueError("same-environment machine outside original operator pool")
