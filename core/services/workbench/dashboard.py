"""Bounded dashboard catalog and details; no GET mutates identities or facts."""

from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected, input_fingerprint
from core.models.workbench_dashboard import (
    CATEGORIES,
    DashboardQuery,
    allowed_transitions,
    bounded,
    empty_handling,
    page,
    payload_size,
    reference,
)
from data.repositories.workbench_dashboard_repo import WorkbenchDashboardRepository

from .dashboard_downtime import downtime
from .dashboard_execution import actual
from .dashboard_external import external
from .dashboard_external_handling import DashboardExternalHandling
from .dashboard_facts import DashboardFacts, typed
from .dashboard_projection import category, delivery, safe_material


def navigation(item, *, current=True):
    source, kind = item["source"], item["category"]
    context = {key: source[key] for key in ("plan_ref", "batch_ref", "task_ref", "operation_ref") if source.get(key)}
    if kind == "actual":
        return [{"view": "fieldgantt", "context": context, "enabled": current,
                 "query_target": "/api/workbench/v1/execution/tasks/" + source["task_ref"],
                 "command_target": "/api/workbench/v1/execution/tasks/" + source["task_ref"] + "/reports",
                 "command_context": "read_execution_write_context", "reason": None if current else "这条安排已经不是当前正式计划里的了，请先核对原记录。"}]
    view = "batches" if kind == "material" else "gantt"
    return [{"view": view, "context": context, "enabled": current,
             "reason": None if current else "这条来源这次没有参与评估；系统保留原记录，不会换成编号相同的另一条。"}]


def _handling_view(item, stored, now):
    handling = stored["handling"] if stored else empty_handling()
    deadline = handling["deadline"]
    return {**handling, "status_label": {"new": "待分析", "following": "跟进中", "awaiting_verification": "待验证", "closed": "已关闭"}[handling["status"]],
            "deadline_overdue": bool(deadline and deadline < now.date().isoformat() and handling["status"] != "closed"),
            "evidence_verification": "not_verified", "history_count": stored["revision"] if stored else 0}


def _category_counts(categories, observations, stored):
    for name, summary in categories.items():
        scope = [row for row in observations if row["category"] == name]
        summary["known_risk_count"] = sum(row["risk"]["active"] is True for row in scope)
        known = name != "candidate" and summary["state"] in ("loaded", "no_data") and not summary["unknown_count"]
        summary["risk_count"] = summary["known_risk_count"] if known else None
        summary["evaluation_gaps"] = [{"source_ref": row["anchor_ref"], "subject": row["subject"],
                                        "code": row["risk"]["code"], "message": row["risk"]["message"]}
                                       for row in scope if row["risk"]["active"] is None]
        handled = [row for row in stored.values() if row["category"] == name]
        summary["handling_count"] = len(handled)
        summary["closed_count"] = sum(row["handling"]["status"] == "closed" for row in handled)


class WorkbenchDashboardService:
    def __init__(self, conn, *, clock=None, context_factory=None):
        self.conn, self.clock, self.context_factory = conn, clock or datetime.now, context_factory
        self.external_handling = DashboardExternalHandling(conn)
        self.repo = WorkbenchDashboardRepository(conn, external_repo=self.external_handling.repo)

    @contextmanager
    def read_snapshot(self):
        with TransactionManager(self.conn).transaction():
            self.repo.require_schema()
            yield

    def read(self, as_of=None):
        if not self.conn.in_transaction:
            raise RuntimeError("Dashboard reads require a caller-owned snapshot")
        now = as_of or self.clock().replace(microsecond=0)
        if not isinstance(now, datetime) or now.tzinfo is not None:
            raise ValueError("Dashboard time must be factory local")
        facts = DashboardFacts(self.conn, now).load()
        observations, categories = [], {}
        for name, reader in (("delivery", delivery), ("actual", actual), ("downtime", downtime), ("material", safe_material)):
            found, categories[name] = reader(facts)
            observations.extend(found)
        external_summary, facts.raw["external"] = external(self.conn, now)
        external_items, external_stored, facts.raw["external_handling"] = self.external_handling.read(external_summary, now)
        categories["candidate"] = category(facts.candidates["state"], issues=facts.candidates["issues"])
        categories["candidate"].update(kind="directory_not_risk", run_count=facts.candidates["run_count"],
                                       entry={"view": "analysis", "target": "/api/workbench/v1/scheduling/runs", "enabled": True})
        stored = self.repo.stored()
        source_state = facts.fingerprint()
        items = self._merge(observations, stored, source_state, now)
        items.extend(self._decorate(item, saved, source_state, identity, now) for item, saved, identity in external_items)
        bounded(items)
        _category_counts(categories, observations, stored)
        categories["external"] = external_summary
        fingerprint = input_fingerprint(typed({"source": source_state, "stored": stored, "external_stored": external_stored,
                                              "items": [(row["item_ref"], row["_snapshot"]) for row in items]}))
        return {"plan": facts.plan, "as_of": now.isoformat(timespec="seconds"), "items": items,
                "resource_pressure": facts.pressure, "candidate_catalog": facts.candidates,
                "categories": {name: categories[name] for name in CATEGORIES}, "fingerprint": fingerprint}

    def _merge(self, observations, stored, source_state, now):
        found = {}
        for name in ("delivery", "actual", "downtime", "material"):
            selected = [row for row in observations if row["category"] == name]
            mappings = self.repo.mappings(name, [row["anchor_ref"] for row in selected])
            for item in selected:
                identity = mappings[item["anchor_ref"]]
                ref = identity["item_ref"]
                if ref in found:
                    raise WorkbenchCommandRejected("identity_missing", "同一个风险来源出现了重复条目，系统不会合并也不会丢掉。请刷新后重试。")
                item = dict(item, item_ref=ref, navigation=navigation(item), source_state="current")
                found[ref] = self._decorate(item, stored.get(ref), source_state, identity, now)
        for ref, saved in stored.items():
            if ref in found:
                continue
            origin = saved["origin"]
            item: Dict[str, Any] = dict(origin, source_state="not_currently_evaluated", risk={"active": None, "code": "source_not_currently_evaluated",
                        "message": "原来源当前未评估或已非当前正式，不能认定风险已消除。"}, _facts={"origin": origin})
            item["navigation"] = navigation(item, current=False)
            found[ref] = self._decorate(item, saved, source_state, self.repo.identity(ref), now)
        return bounded([item for ref, item in found.items() if item["risk"]["active"] is True or ref in stored])

    def _decorate(self, item, saved, source_state, identity, now):
        handling = saved["handling"] if saved else empty_handling()
        snapshot = {"source_fingerprint": source_state, "identity": identity, "revision": saved["revision"] if saved else 0,
                    "source": item["source"], "risk": item["risk"], "handling": handling}
        item.update(handling=_handling_view(item, saved, now), allowed_transitions=allowed_transitions(handling["status"]),
                    _handling=handling, _snapshot=typed(snapshot))
        item["_facts"] = typed(item["_facts"])
        item["write_context"] = None
        return item

    def public_item(self, item):
        public = {key: value for key, value in item.items() if not key.startswith("_") and key != "anchor_ref"}
        if self.context_factory:
            actions = ["reopen"] if item["handling"]["status"] == "closed" else ["transition"]
            public["write_context"] = self.context_factory(item["item_ref"], actions, item["_snapshot"])
        return public

    @staticmethod
    def selected(data, query):
        term = query.query.strip().casefold()
        selected = []
        for item in data["items"]:
            handling = item["handling"]
            if query.category != "all" and item["category"] != query.category:
                continue
            if query.status == "open" and handling["status"] == "closed" or query.status not in ("all", "open", handling["status"]):
                continue
            text = " ".join([item["subject"]] + [handling[key] or "" for key in ("owner", "action", "remark")])
            if term not in text.casefold():
                continue
            selected.append(item)
        def key(item):
            value = item[query.sort] if query.sort in ("subject", "category") else item["handling"][query.sort]
            return value is None, value or "", item["item_ref"]
        return sorted(selected, key=key, reverse=query.direction == "desc")

    def workspace(self, data, query):
        selected = self.selected(data, query)
        items, pagination = page(selected, query.number, query.size, [{"field": query.sort, "direction": query.direction}])
        return payload_size({"plan": data["plan"], "as_of": data["as_of"], "categories": data["categories"],
                             "resource_pressure": data["resource_pressure"], "candidate_catalog": data["candidate_catalog"],
                             "items": [self.public_item(item) for item in items], "page": pagination, "scope": query.scope()})

    def detail(self, data, item_ref, query=None):
        reference(item_ref)
        selected = self.selected(data, query or DashboardQuery())
        for item in selected:
            if item["item_ref"] == item_ref:
                return item
        raise WorkbenchCommandRejected("entity_not_found", "这一条不在当前查询范围里，系统不会改去读别的来源。请刷新后重试。", 404)
