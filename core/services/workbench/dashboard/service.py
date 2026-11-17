"""Bounded dashboard catalog and details; no GET mutates identities or facts."""

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from core.infrastructure.transaction import TransactionManager
from core.models.content import read_stored_json
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_dashboard import (
    CATEGORIES,
    DashboardAnalysisQuery,
    DashboardQuery,
    allowed_transitions,
    empty_handling,
    page,
    reference,
)
from data.repositories.workbench_dashboard_repo import WorkbenchDashboardRepository

from .analysis_projection import project_dashboard_analysis
from .external import load_external, load_external_item
from .external_handling import DashboardExternalHandling, handling_counts, project_external_item
from .facts import DashboardFacts
from .policy import (
    mapped_anchors,
    read_history,
    read_stored,
    require_identity,
)
from .projection import category, delivery, safe_material

# 每类风险的目的页与一组定位键（目的页键名, 来源键名）：正式计划甘特用自己的焦点字段 selected_*，
# 现场执行（实际甘特与现场记录）和批次页保留各自的协议；当前未评估的来源不带定位，直接打开目的页概览。
_TARGETS = {
    "delivery": (("gantt",), (("plan_ref", "plan_ref"), ("selected_batch_ref", "batch_ref"))),
    "downtime": (("gantt",), (("plan_ref", "plan_ref"), ("selected_task_ref", "task_ref"))),
    "actual": (("fieldgantt", "field"), (("plan_ref", "plan_ref"), ("task_ref", "task_ref"), ("operation_ref", "operation_ref"))),
    "material": (("batches",), (("batch_ref", "batch_ref"),)),
}


def navigation(item, *, current=True):
    views, keys = _TARGETS[item["category"]]
    if not current:
        return [
            {
                "view": views[0],
                "context": {},
                "enabled": False,
                "reason": (
                    "这条安排已经不是当前正式计划里的了，请先核对原记录。"
                    if views[0] == "fieldgantt"
                    else "这条来源这次没有参与评估；系统保留原记录，不会换成编号相同的另一条。"
                ),
            }
        ]
    source = item["source"]
    return [
        {"view": view, "context": {target: source[key] for target, key in keys}, "enabled": True, "reason": None}
        for view in views
    ]


def _handling_view(stored, now):
    handling = stored["handling"] if stored else empty_handling()
    deadline = handling["deadline"]
    return {
        **handling,
        "status_label": {
            "new": "待分析",
            "following": "跟进中",
            "awaiting_verification": "待验证",
            "closed": "已关闭",
        }[handling["status"]],
        "deadline_overdue": bool(deadline and deadline < now.date().isoformat() and handling["status"] != "closed"),
        "evidence_verification": "not_verified",
        "history_count": stored["revision"] if stored else 0,
    }


def _category_counts(categories, observations_by_category, stored):
    handled_by_category = {name: [] for name in categories}
    for row in stored.values():
        if row["category"] in handled_by_category:
            handled_by_category[row["category"]].append(row)
    categories = {name: dict(summary) for name, summary in categories.items()}
    for name, summary in categories.items():
        scope = observations_by_category.get(name, ())
        summary["known_risk_count"] = sum(row["risk"]["active"] is True for row in scope)
        known = name != "candidate" and summary["state"] in ("loaded", "no_data") and not summary["unknown_count"]
        summary["risk_count"] = summary["known_risk_count"] if known else None
        summary["evaluation_gaps"] = [
            {
                "source_ref": row["anchor_ref"],
                "subject": row["subject"],
                "code": row["risk"]["code"],
                "message": row["risk"]["message"],
            }
            for row in scope
            if row["risk"]["active"] is None and row["risk"]["code"] != "due_not_applicable"
        ]
        summary.update(handling_counts(handled_by_category[name]))
    return categories


class DashboardSources:
    """Everything one dashboard read takes from SQLite; project() turns it into items without a connection."""

    def __init__(self, facts, material, external, stored, mappings, identities):
        self.facts, self.material, self.external = facts, material, external
        self.stored, self.mappings, self.identities = stored, mappings, identities


@dataclass(frozen=True)
class ExternalItemCapture:
    """One outsourcing item's receipt facts and its evaluation gap, read inside a snapshot."""

    item_ref: str
    now: datetime
    identity: Dict[str, Any]
    saved: Optional[Dict[str, Any]]
    entry: Dict[str, Any]
    gap_row: Optional[Dict[str, Any]]


@dataclass(frozen=True)
class MaterialItemCapture:
    """One batch's readiness observations, projected inside the snapshot (they look up permanent refs)."""

    item_ref: str
    now: datetime
    identity: Dict[str, Any]
    saved: Optional[Dict[str, Any]]
    observations: List[Dict[str, Any]]


@dataclass(frozen=True)
class PlanItemCapture:
    """One delivery, execution or downtime item's plan facts; their observations need no SQLite."""

    item_ref: str
    now: datetime
    identity: Dict[str, Any]
    saved: Optional[Dict[str, Any]]
    facts: DashboardFacts


CommandItemCapture = Union[ExternalItemCapture, MaterialItemCapture, PlanItemCapture]


class WorkbenchDashboardService:
    def __init__(self, conn, *, context_factory=None):
        self.conn, self.context_factory = conn, context_factory
        self.external_handling = DashboardExternalHandling(conn)
        self.repo = WorkbenchDashboardRepository(conn)

    @contextmanager
    def read_snapshot(self):
        with TransactionManager(self.conn).transaction():
            yield

    def history(self, item_ref, number, size):
        """Paged handling history for any dashboard item."""
        require_identity(self.repo, item_ref)
        return read_history(self.repo, item_ref, number, size)

    def _require_snapshot(self):
        if not self.conn.in_transaction:
            raise RuntimeError("Dashboard reads require a caller-owned snapshot")

    @staticmethod
    def _not_found():
        return WorkbenchCommandRejected(
            "entity_not_found",
            "这一条不在当前查询范围里，系统不会改去读别的来源。请刷新后重试。",
            404,
        )

    def read(self, as_of):
        """读快照内读完并投影。"""
        return self.project(self.load(as_of))

    def read_command_item(self, item_ref, as_of):
        """读快照内仅读取并投影目标条目；写命令在写锁内重算时走这里。"""
        return self.project_command_item(self.load_command_item(item_ref, as_of))

    def load_command_item(self, item_ref, as_of) -> CommandItemCapture:
        """Read only one item's source closure under the caller's snapshot; project_command_item() needs no SQLite.

        ``item_ref`` was admitted by ``WorkbenchDashboardCommandService.execute``, the only entry that reaches here."""
        self._require_snapshot()
        identity = self.repo.item_by_ref(item_ref)
        if identity is None:
            raise self._not_found()
        raw_saved = self.repo.stored_by_ref(item_ref)
        saved = (
            None
            if raw_saved is None
            else {
                **identity,
                "revision": raw_saved["revision"],
                "updated_at": raw_saved["updated_at"],
                "handling": read_stored_json(raw_saved["handling_json"], dict),
                "origin": read_stored_json(raw_saved["origin_json"], dict),
            }
        )
        category_name = identity["category"]
        if category_name == "external":
            entry, gap_row = load_external_item(self.conn, as_of, identity["outsourcing_ref"])
            return ExternalItemCapture(item_ref, as_of, identity, saved, entry, gap_row)
        if category_name == "material":
            observations = DashboardFacts(self.conn, as_of).load_material_item(identity["batch_ref"])
            return MaterialItemCapture(item_ref, as_of, identity, saved, observations)
        facts = DashboardFacts(self.conn, as_of)
        facts.load_plan_item(identity)
        return PlanItemCapture(item_ref, as_of, identity, saved, facts)

    def project_command_item(self, captured: CommandItemCapture):
        """Project a single captured command item with the exact list-side decoration and snapshot."""
        identity, saved, now = captured.identity, captured.saved, captured.now
        if isinstance(captured, ExternalItemCapture):
            projected = project_external_item(captured.item_ref, identity["outsourcing_ref"], captured.entry,
                                              captured.gap_row, saved)
            if projected is None:
                raise self._not_found()
            item = self._decorate(projected, saved, identity, now)
            self._materialize_item(item)
            return item
        if isinstance(captured, MaterialItemCapture):
            found = captured.observations
        elif identity["category"] == "delivery":
            found, _ = delivery(captured.facts)
        else:
            found, _ = captured.facts.observations(identity["category"])
        if found:
            obs = found[0]
            if obs["risk"]["active"] is not True and saved is None:
                raise self._not_found()
            item = dict(obs, item_ref=captured.item_ref, navigation=navigation(obs), source_state="current")
        else:
            if saved is None:
                raise self._not_found()
            item = self._not_currently_evaluated(saved)
        item = self._decorate(item, saved, identity, now)
        self._materialize_item(item)
        return item

    def load(self, as_of, *, source_revisions=None):
        """Read every source under the caller's snapshot; project() then needs no SQLite access."""
        self._require_snapshot()
        facts = DashboardFacts(self.conn, as_of, source_revisions=source_revisions).load()
        # 齐套要按批次查来源编号，留在读快照里判断；交期、报工、停机在 project() 里只用已读出的事实。
        material = safe_material(facts)
        stored, identities = read_stored(self.repo)
        external_summary, receipts = load_external(self.conn, as_of)
        external_items, handling = self.external_handling.read(external_summary, receipts, stored)
        return DashboardSources(
            facts,
            material,
            ({**external_summary, **handling}, external_items),
            stored,
            self._anchor_mappings(facts, material[0]),
            identities,
        )

    def _anchor_mappings(self, facts, material):
        """各类风险可能评估到的来源映射一次读出；是否条条有映射，投影时按实际评估到的来源核对。"""
        tasks = [task["task_ref"] for task in facts.tasks]
        anchors = {
            "delivery": [row["batch_ref"] for row in facts.delivery_items],
            "actual": tasks,
            "downtime": tasks,
            "material": [row["anchor_ref"] for row in material],
        }
        return {name: self.repo.mappings(name, refs) for name, refs in anchors.items()}

    def project(self, sources):
        """Pure projection of load(); callers may run it after their read snapshot has ended."""
        facts = sources.facts.project()
        delivery_obs, delivery_summary = delivery(facts)
        observations_by_category, categories = {"delivery": delivery_obs}, {"delivery": delivery_summary}
        for name in ("actual", "downtime"):
            found, categories[name] = facts.observations(name)
            observations_by_category[name] = found
        found, categories["material"] = sources.material
        observations_by_category["material"] = found
        external_summary, external_items = sources.external
        categories["candidate"] = category(facts.candidates["state"], issues=facts.candidates["issues"])
        categories["candidate"].update(
            kind="directory_not_risk",
            run_count=facts.candidates["run_count"],
            entry={"view": "analysis", "target": "/api/workbench/v1/scheduling/runs", "enabled": True},
        )
        stored = sources.stored
        items = self._merge(observations_by_category, sources, facts.now)
        items.extend(self._decorate(item, saved, identity, facts.now) for item, saved, identity in external_items)
        categories = _category_counts(categories, observations_by_category, stored)
        categories["external"] = external_summary
        return {
            "plan": facts.plan,
            "as_of": facts.now.isoformat(timespec="seconds"),
            "items": items,
            "resource_pressure": facts.pressure,
            "candidate_catalog": facts.candidates,
            "categories": {name: categories[name] for name in CATEGORIES},
        }

    @staticmethod
    def _not_currently_evaluated(saved):
        item: Dict[str, Any] = dict(
            saved["origin"],
            source_state="not_currently_evaluated",
            risk={
                "active": None,
                "code": "source_not_currently_evaluated",
                "message": "原来源当前未评估或已非当前正式，不能认定风险已消除。",
            },
            _guard={"source_revision": None},
        )
        item["navigation"] = navigation(item, current=False)
        return item

    def _merge(self, observations_by_category, sources, now):
        found, stored = self._identified(observations_by_category, sources.mappings), sources.stored
        items = []
        for ref, (item, identity) in found.items():
            # 只列出当前有风险或已有处置的条目；其余几千条无风险观察不逐条规整、不签快照。
            if item["risk"]["active"] is True or ref in stored:
                item = dict(item, item_ref=ref, navigation=navigation(item), source_state="current")
                items.append(self._decorate(item, stored.get(ref), identity, now))
        for ref, saved in stored.items():
            if ref in found or saved["category"] == "external":
                continue
            item = self._not_currently_evaluated(saved)
            identity = sources.identities[reference(ref)]
            items.append(self._decorate(item, saved, identity, now))
        return items

    @staticmethod
    def _identified(observations_by_category, loaded):
        found = {}
        for name in ("delivery", "actual", "downtime", "material"):
            selected = observations_by_category[name]
            mappings = mapped_anchors(loaded[name], [row["anchor_ref"] for row in selected])
            for item in selected:
                identity = mappings[item["anchor_ref"]]
                if identity["item_ref"] in found:
                    raise WorkbenchCommandRejected(
                        "identity_missing",
                        "同一个风险来源出现了重复条目，系统不会合并也不会丢掉。请刷新后重试。",
                    )
                found[identity["item_ref"]] = item, identity
        return found

    def _decorate(self, item, saved, identity, now):
        handling = saved["handling"] if saved else empty_handling()
        item["_guard"] = {
            "source_state": item["source_state"],
            "source_revision": item["_guard"]["source_revision"],
            "identity": identity,
            "revision": saved["revision"] if saved else 0,
            "source": item["source"],
            "risk": item["risk"],
            "handling": handling,
        }
        item.update(
            handling=_handling_view(saved, now),
            allowed_transitions=allowed_transitions(handling["status"]),
            _handling=handling,
        )
        item["write_context"] = None
        return item

    @staticmethod
    def _materialize_item(item):
        if "_snapshot" not in item:
            item["_snapshot"] = item["_guard"]

    def public_item(self, item):
        self._materialize_item(item)
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
            if (
                query.status == "open"
                and handling["status"] == "closed"
                or query.status not in ("all", "open", handling["status"])
            ):
                continue
            text = " ".join([item["subject"]] + [handling[key] or "" for key in ("owner", "action", "remark")])
            if term not in text.casefold():
                continue
            selected.append(item)

        def key(item):
            value = item[query.sort] if query.sort in ("subject", "category") else item["handling"][query.sort]
            return value is None, value, item["item_ref"]

        return sorted(selected, key=key, reverse=query.direction == "desc")

    def workspace(self, data, query):
        selected = self.selected(data, query)
        items, pagination = page(
            selected,
            query.number,
            query.size,
            [{"field": query.sort, "direction": query.direction}],
        )
        pressure = data["resource_pressure"]
        pressure_summary = dict(pressure, detail_target="/api/workbench/v1/dashboard/analysis?section=pressure")
        return {
            "plan": data["plan"],
            "as_of": data["as_of"],
            "categories": data["categories"],
            "resource_pressure": pressure_summary,
            "candidate_catalog": data["candidate_catalog"],
            "items": [self.public_item(item) for item in items],
            "page": pagination,
            "scope": query.scope(),
        }

    def analysis(self, sources, query=None):
        return project_dashboard_analysis(
            sources.facts,
            sources.material,
            query=query or DashboardAnalysisQuery("overview"),
        )

    def detail(self, data, item_ref, query=None):
        reference(item_ref)
        selected = self.selected(data, query or DashboardQuery())
        for item in selected:
            if item["item_ref"] == item_ref:
                self._materialize_item(item)
                return item
        raise self._not_found()
