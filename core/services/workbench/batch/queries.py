"""Two-stage SQL pagination, bounded selection/facets and single-batch detail."""

from collections import defaultdict
from datetime import datetime
from typing import Any, Callable, Dict, List, Mapping, Optional, Set, Tuple

from core.models.content import content_text
from core.models.enums import BATCH_PRIORITY_RANKS, BATCH_STATUS_RANKS, READY_STATUS_RANKS
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_load_limits import MAX_WINDOW_BATCHES
from core.services.material.stage_availability import MaterialReadiness
from core.services.scheduler.contracts.external_context import (
    context_group_key,
    context_problem,
    group_from_context,
    merged_supplier_problem,
)
from core.services.workbench.facts.source_revisions import BATCH_SOURCE_KEYS, read_source_revisions

from .facts import BatchFacts, read_transaction
from .projection import BatchProjection, batch_choices
from .resource_choices import BatchResourceFacts, operation_choices, operator_machine_links
from .scope import BatchFactScope
from .template_validation import template_status

#: 优先级、齐套、状态按业务先后排，与 SQL 排序（workbench_batch_facts_repo）用同一份序号；其余列按原值排。
_BUSINESS_RANKS = {"priority": BATCH_PRIORITY_RANKS, "ready_status": READY_STATUS_RANKS, "status": BATCH_STATUS_RANKS}


def _business_order(field: str, value: Any) -> Any:
    ranks = _BUSINESS_RANKS.get(field)
    return value if ranks is None or value is None else ranks[value]


def _candidate_cell(row: Mapping[str, Any], key: str) -> Any:
    if key == "business_code":
        return row["batch_id"]
    if key == "part_no":
        return row["part_no"]
    if key == "quantity":
        return row["quantity"]
    if key == "due_date":
        return row["norm_due"]
    if key == "priority":
        return row["priority"]
    if key == "ready_status":
        return row["display_ready_status"]
    return row["derived_status"]


def _needs_readiness(query: Mapping[str, Any], *, facet_field: str = "") -> bool:
    return bool(
        query["ready_status"]
        or query["focus"] == "unready"
        or "ready_status" in query["column_filters"]
        or query["sort"] == "ready_status"
        or facet_field == "ready_status"
    )


def _attach_candidate_readiness(
    repo, candidates: List[Dict[str, Any]], material_day: str
) -> None:
    with_materials = [row["batch_id"] for row in candidates if row["has_materials"]]
    availability = (
        MaterialReadiness.from_tables(repo.material_readiness_tables(with_materials))
        if with_materials
        else None
    )
    for row in candidates:
        if row["has_materials"]:
            assert availability is not None
            batch_stub = {
                "batch_id": row["batch_id"],
                "quantity": row["quantity"],
                "ready_status": row["ready_status"],
            }
            row["display_ready_status"] = availability.readiness_state(batch_stub, material_day)[0]
        else:
            row["display_ready_status"] = row["ready_status"]


def _filter_by_readiness(query: Mapping[str, Any], candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    ready_filter = query["ready_status"]
    unready_only = query["focus"] == "unready"
    col_values = query["column_filters"].get("ready_status")
    result = []
    for row in candidates:
        state = row["display_ready_status"]
        if ready_filter and state != ready_filter:
            continue
        if unready_only and state == "yes":
            continue
        if col_values is not None and state not in col_values:
            continue
        result.append(row)
    return result


def _operation_has_execution_gap(op: Mapping[str, Any], quantity: int) -> bool:
    target = 1 if (op["piece_id"] is not None and op["piece_id"] != "") else quantity
    rep_cnt = op["rep_cnt"]
    known_qty = op["known_qty"]
    unk_qty = op["unk_qty"]
    records_complete = op["records_complete"]
    if rep_cnt > 0 and known_qty == target and unk_qty == 0 and records_complete == 1:
        exec_state = "complete"
    elif known_qty > 0 or op["any_end"] == 1:
        exec_state = "partial"
    elif rep_cnt > 0:
        exec_state = "started"
    else:
        exec_state = "unreported"
    return bool(
        target is None
        or op["operation_ref"] is None
        or (rep_cnt > 0 and not records_complete)
        or (target is not None and known_qty > target)
        or exec_state not in ("complete", "unreported")
        or (op["status"] == "completed" and exec_state != "complete")
    )


def _batches_with_gaps(repo, candidates: List[Dict[str, Any]]) -> Set[str]:
    matched = {row["batch_id"] for row in candidates if row["op_cnt"] == 0}
    non_empty = [row for row in candidates if row["op_cnt"] > 0]
    if not non_empty:
        return matched
    gap_tables = repo.gap_check_tables([row["batch_id"] for row in non_empty])
    inspector = BatchProjection(
        {
            **gap_tables,
            "Parts": [],
            "BatchMaterials": [],
            "BatchMaterialReviews": [],
            "BatchMaterialStages": [],
            "BatchMaterialArrivals": [],
            "WorkbenchEntityRefs": [],
            "material_day": "",
        },
        relations={},
    )
    external_contexts = inspector.external_contexts
    external_members = inspector.external_members
    ops_by_batch: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for op in gap_tables["BatchOperations"]:
        ops_by_batch[op["batch_id"]].append(op)
    for cand in non_empty:
        batch_id = cand["batch_id"]
        for op in ops_by_batch[batch_id]:
            group = context = None
            problem = None
            if op["source"] == "external":
                context = external_contexts.get(op["id"])
                problem = context_problem(
                    context, operation_id=op["id"], part_no=cand["part_no"], sequence=op["seq"]
                )
                if not problem:
                    group = group_from_context(context)
            numbers = {key: op[key] for key in ("setup_hours", "unit_hours", "ext_days")}
            if inspector.operation_issues(op, group, numbers):
                matched.add(batch_id)
                break
            if op["source"] == "external":
                if not problem:
                    problem = merged_supplier_problem(
                        context,
                        op["supplier_id"],
                        external_members.get((op["batch_id"], context_group_key(context), op["piece_id"])),
                    )
                if problem:
                    matched.add(batch_id)
                    break
            if _operation_has_execution_gap(op, cand["quantity"]):
                matched.add(batch_id)
                break
    return matched


def _evaluate_candidates(
    facts_service: BatchFacts,
    query: Mapping[str, Any],
    *,
    material_day: str,
    facet_field: str = "",
    ordered: bool = True,
) -> List[Dict[str, Any]]:
    candidates = facts_service.repo.query_candidates_stage1(query)
    if not candidates:
        return []
    if _needs_readiness(query, facet_field=facet_field):
        _attach_candidate_readiness(facts_service.repo, candidates, material_day)
        candidates = _filter_by_readiness(query, candidates)
    if query["focus"] == "gaps" and candidates:
        gap_ids = _batches_with_gaps(facts_service.repo, candidates)
        candidates = [row for row in candidates if row["batch_id"] in gap_ids]
    if ordered and len(candidates) > 1:
        sort_field = query["sort"]

        def order(row):
            value = _candidate_cell(row, sort_field)
            return value is None, _business_order(sort_field, value)

        # Candidates arrive ordered by batch_id ASC; Python Timsort preserves batch_id ASC ties.
        candidates.sort(key=order, reverse=query["direction"] == "desc")
    return candidates


class WorkbenchBatchQueryService:
    def __init__(self, conn, logger=None, *, as_of: datetime):
        """``as_of`` is the request's read time: its date is the material day, and the route binds snapshots at it."""
        self.as_of = as_of
        self.facts = BatchFacts(conn, logger, material_day=as_of.date().isoformat())

    def _begin_query_snapshot(self, bind: Optional[Callable[[str], Any]]) -> Tuple[Dict[str, Any], str, str]:
        day = self.facts.material_day
        revisions = read_source_revisions(self.facts.conn, BATCH_SOURCE_KEYS)
        fingerprint = content_text(["batch-facts-v3", revisions, day])
        if bind is not None:
            bind(fingerprint)
        return revisions, day, fingerprint

    def _assemble_page_entities(self, closure_facts: Dict[str, Any], page_refs: Tuple[str, ...]) -> List[Dict[str, Any]]:
        if not page_refs:
            return []
        projection = BatchProjection(closure_facts)
        by_ref = {projection.ref("batch", row["batch_id"]): row for row in closure_facts["Batches"]}
        return [projection.summary(by_ref[ref]) for ref in page_refs]

    def read_page(
        self, query: Mapping[str, Any], *, bind: Optional[Callable[[str], Any]] = None
    ) -> Tuple[Dict[str, Any], str]:
        with read_transaction(self.facts.conn):
            revisions, day, fingerprint = self._begin_query_snapshot(bind)
            if not _needs_readiness(query) and query["focus"] != "gaps":
                stage1 = self.facts.repo.query_page_stage1(query)
                total, completed, page_refs = stage1["total"], stage1["completed"], tuple(stage1["page_refs"])
            else:
                rows = _evaluate_candidates(self.facts, query, material_day=day, ordered=True)
                total = len(rows)
                completed = sum(row["all_complete"] for row in rows)
                start = (query["page"] - 1) * query["size"]
                page_refs = tuple(row["batch_ref"] for row in rows[start : start + query["size"]])
            raw_closure = self.facts.capture_closure(page_refs, revisions=revisions)
        closure_facts = self.facts.project_captured(raw_closure, material_day=day)
        entities = self._assemble_page_entities(closure_facts, page_refs)
        return (
            {
                "entities": entities,
                "page": {
                    "number": query["page"],
                    "size": query["size"],
                    "total": total,
                    "pages": max(1, (total + query["size"] - 1) // query["size"]),
                    "sort": [{"field": query["sort"], "direction": query["direction"]}],
                },
                "metrics": {
                    "scope": "filtered",
                    "total": total,
                    "completed": completed,
                },
                "create_context": None,
            },
            fingerprint,
        )

    def read_facets(
        self, query: Mapping[str, Any], field: str, *, bind: Optional[Callable[[str], Any]] = None
    ) -> Tuple[Dict[str, Any], str]:
        with read_transaction(self.facts.conn):
            _, day, fingerprint = self._begin_query_snapshot(bind)
            rows = _evaluate_candidates(self.facts, query, material_day=day, facet_field=field, ordered=False)
        values = list(dict.fromkeys(_candidate_cell(row, field) for row in rows))
        if field in _BUSINESS_RANKS:
            values.sort(key=lambda value: (value is None, _business_order(field, value)))
        else:
            values.sort(key=lambda value: (value is None, str(value)))
        if len(values) > 5000:
            raise WorkbenchCommandRejected(
                "invalid_input", "这一列的可选值超过 5000 项，没有全部列出。请在搜索框里先输入关键字缩小范围。", 422
            )
        return {"field": field, "values": values, "count": len(values)}, fingerprint

    def read_selection(
        self, query: Mapping[str, Any], *, bind: Optional[Callable[[str], Any]] = None
    ) -> Tuple[Dict[str, Any], str]:
        with read_transaction(self.facts.conn):
            _, day, fingerprint = self._begin_query_snapshot(bind)
            rows = _evaluate_candidates(self.facts, query, material_day=day, ordered=True)
        refs = [row["batch_ref"] for row in rows]
        if len(refs) > MAX_WINDOW_BATCHES:
            raise WorkbenchCommandRejected("invalid_input", f"当前范围超过 {MAX_WINDOW_BATCHES} 批，请缩小范围后再选择。", 422)
        return {"refs": refs, "count": len(refs)}, fingerprint

    def detail(self, scope: BatchFactScope, ref):
        """Expand complete operation details for the requested batch."""
        facts = scope.load()
        row = scope.batch(ref)
        projection = BatchProjection(facts)
        entity = projection.entity(row)
        entity["materials"] = projection.materials(row)
        entity["template"] = template_status(facts, row, projection.resources)
        return entity

    def summaries(self, scope: BatchFactScope, refs):
        """Selected-list consumers share the same summary as filtered lists."""
        facts = scope.load()
        rows = [scope.batch(ref) for ref in refs]
        projection = BatchProjection(facts)
        return [projection.summary(row) for row in rows]

    def choices_catalog(self):
        facts = self.facts.load_choices()
        return batch_choices(facts, operator_machine_links(facts))

    def operation_choices(self, scope: BatchFactScope, batch_ref, operation_ref):
        facts = scope.load()
        resources = BatchResourceFacts(facts)
        return operation_choices(
            scope, batch_ref, operation_ref, batch_choices(facts, resources.links), resources, facts
        )
