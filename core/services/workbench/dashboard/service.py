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

from .analysis_projection import project_dashboard_analysis
from .downtime import downtime
from .execution import actual
from .external import load_external
from .external_handling import DashboardExternalHandling
from .facts import DashboardFacts, typed
from .policy import (
    found_identity,
    mapped_anchors,
    read_history,
    read_stored,
    require_dashboard_schema,
    require_external_schema,
    require_identity,
)
from .projection import category, delivery, safe_material


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


class DashboardSources:
    """Everything one dashboard read takes from SQLite; project() turns it into items without a connection."""

    def __init__(self, facts, material, external, stored, mappings, identities):
        self.facts, self.material, self.external = facts, material, external
        self.stored, self.mappings, self.identities = stored, mappings, identities


class WorkbenchDashboardService:
    def __init__(self, conn, *, clock=None, context_factory=None):
        self.conn, self.clock, self.context_factory = conn, clock or datetime.now, context_factory
        self.external_handling = DashboardExternalHandling(conn)
        self.repo = WorkbenchDashboardRepository(conn)

    def require_schema(self):
        require_dashboard_schema(self.repo)

    @contextmanager
    def read_snapshot(self):
        with TransactionManager(self.conn).transaction():
            self.require_schema()
            yield

    def history(self, item_ref, number, size):
        """Paged handling history; items unknown to the dashboard ledger are read from the external ledger."""
        repo = self.repo
        if not repo.has_item(item_ref):
            repo = self.external_handling.repo
            require_external_schema(repo)
            require_identity(repo, item_ref)
        return read_history(repo, item_ref, number, size)

    def append_handling(self, *, item, before, after, facts, actor, action, reason, request_key, now):
        repo = self.repo
        if item["category"] == "external":
            repo = self.external_handling.repo
            require_external_schema(repo)
        source = {key: item[key] for key in ("item_ref", "category", "subject", "source", "risk", "navigation")}
        payload_size({"source": source, "facts": facts, "before": before, "after": after})
        return repo.append(item=item, before=before, after=after, facts=facts, actor=actor, action=action,
                           reason=reason, request_key=request_key, now=now)

    def read(self, as_of=None):
        """读快照内读完并投影；写命令在写锁里重算时也走这里。"""
        return self.project(self.load(as_of))

    def load(self, as_of=None):
        """Read every source under the caller's snapshot; project() then needs no SQLite access."""
        if not self.conn.in_transaction:
            raise RuntimeError("Dashboard reads require a caller-owned snapshot")
        now = as_of or self.clock().replace(microsecond=0)
        if not isinstance(now, datetime) or now.tzinfo is not None:
            raise ValueError("Dashboard time must be factory local")
        facts = DashboardFacts(self.conn, now).load()
        # 齐套要按批次查来源编号，留在读快照里判断；交期、报工、停机在 project() 里只用已读出的事实。
        material = safe_material(facts)
        external_summary, facts.raw["external"], receipts = load_external(self.conn, now)
        external_items, external_stored, facts.raw["external_handling"] = self.external_handling.read(external_summary, now, receipts)
        stored = read_stored(self.repo)
        return DashboardSources(facts, material, (external_summary, external_items, external_stored), stored,
                                self._anchor_mappings(facts, material[0]), {ref: self.repo.identity(ref) for ref in stored})

    def _anchor_mappings(self, facts, material):
        """各类风险可能评估到的来源映射一次读出；是否条条有映射，投影时按实际评估到的来源核对。"""
        tasks = [task["task_ref"] for task in facts.tasks]
        anchors = {"delivery": [row["batch_ref"] for row in facts.delivery["items"]] if facts.plan_state == "loaded" else [],
                   "actual": tasks, "downtime": tasks, "material": [row["anchor_ref"] for row in material]}
        return {name: self.repo.mappings(name, refs) for name, refs in anchors.items()}

    def project(self, sources):
        """Pure projection of load(); callers may run it after their read snapshot has ended."""
        facts = sources.facts.project()
        observations, categories = [], {}
        for name, reader in (("delivery", delivery), ("actual", actual), ("downtime", downtime)):
            found, categories[name] = reader(facts)
            observations.extend(found)
        found, categories["material"] = sources.material
        observations.extend(found)
        external_summary, external_items, external_stored = sources.external
        categories["candidate"] = category(facts.candidates["state"], issues=facts.candidates["issues"])
        categories["candidate"].update(kind="directory_not_risk", run_count=facts.candidates["run_count"],
                                       entry={"view": "analysis", "target": "/api/workbench/v1/scheduling/runs", "enabled": True})
        stored = sources.stored
        source_state = facts.fingerprint()
        items = self._merge(observations, sources, categories, facts.now)
        items.extend(self._decorate(item, saved, identity, facts.now) for item, saved, identity in external_items)
        bounded(items)
        _category_counts(categories, observations, stored)
        categories["external"] = external_summary
        fingerprint = input_fingerprint(typed({"source": source_state, "stored": stored, "external_stored": external_stored,
                                              "items": [(row["item_ref"], row["_snapshot"]) for row in items]}))
        return {"plan": facts.plan, "as_of": facts.now.isoformat(timespec="seconds"), "items": items,
                "resource_pressure": facts.pressure, "candidate_catalog": facts.candidates,
                "categories": {name: categories[name] for name in CATEGORIES}, "fingerprint": fingerprint}

    def _merge(self, observations, sources, categories, now):
        found, stored = self._identified(observations, sources.mappings), sources.stored
        items = []
        for ref, (item, identity) in found.items():
            # 只列出当前有风险或已有处置的条目；其余几千条无风险观察不逐条规整、不签快照。
            if item["risk"]["active"] is True or ref in stored:
                item = dict(item, item_ref=ref, navigation=navigation(item), source_state="current")
                items.append(self._decorate(item, stored.get(ref), identity, now))
        for ref, saved in stored.items():
            if ref in found:
                continue
            origin = saved["origin"]
            evaluation = categories[saved["category"]]
            item: Dict[str, Any] = dict(origin, source_state="not_currently_evaluated", risk={"active": None, "code": "source_not_currently_evaluated",
                        "message": "原来源当前未评估或已非当前正式，不能认定风险已消除。"},
                        _facts={"origin": origin, "evaluation": {"state": evaluation["state"], "issues": evaluation["issues"]}})
            item["navigation"] = navigation(item, current=False)
            identity = found_identity(sources.identities[reference(ref)])
            items.append(self._decorate(item, saved, identity, now))
        return bounded(items)

    @staticmethod
    def _identified(observations, loaded):
        found = {}
        for name in ("delivery", "actual", "downtime", "material"):
            selected = [row for row in observations if row["category"] == name]
            mappings = mapped_anchors(loaded[name], [row["anchor_ref"] for row in selected])
            for item in selected:
                identity = mappings[item["anchor_ref"]]
                if identity["item_ref"] in found:
                    raise WorkbenchCommandRejected("identity_missing", "同一个风险来源出现了重复条目，系统不会合并也不会丢掉。请刷新后重试。")
                found[identity["item_ref"]] = item, identity
        return found

    def _decorate(self, item, saved, identity, now):
        handling = saved["handling"] if saved else empty_handling()
        item["_facts"] = typed(item["_facts"])
        snapshot = {"facts": item["_facts"], "source_state": item["source_state"],
                    "identity": identity, "revision": saved["revision"] if saved else 0,
                    "source": item["source"], "risk": item["risk"], "handling": handling}
        item.update(handling=_handling_view(item, saved, now), allowed_transitions=allowed_transitions(handling["status"]),
                    _handling=handling, _snapshot=typed(snapshot))
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

    def analysis(self, sources):
        return project_dashboard_analysis(sources.facts, sources.material)

    def detail(self, data, item_ref, query=None):
        reference(item_ref)
        selected = self.selected(data, query or DashboardQuery())
        for item in selected:
            if item["item_ref"] == item_ref:
                return item
        raise WorkbenchCommandRejected("entity_not_found", "这一条不在当前查询范围里，系统不会改去读别的来源。请刷新后重试。", 404)
