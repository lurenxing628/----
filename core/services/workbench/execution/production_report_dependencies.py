"""Snapshot-local route dependencies and final execution facts for one report command."""

from collections import defaultdict
from types import SimpleNamespace

from core.models.workbench_execution_input import reject
from core.models.workbench_piece_adoption import PieceAdoptionBlocked
from core.services.scheduler.contracts.external_context import context_group_key, require_context
from core.services.workbench.facts.piece_scope import build_piece_adoption_scope
from core.services.workbench.facts.preflight_checks import number
from data.repositories.batch_external_context_repo import BatchExternalContextRepository
from data.repositories.workbench_report_validation_repo import WorkbenchReportValidationRepository


def _predecessors(rows):
    mixed = any(row["piece_id"] is None for row in rows) and any(row["piece_id"] is not None for row in rows)
    if mixed:
        first = rows[0]
        try:
            scope = build_piece_adoption_scope([SimpleNamespace(**row) for row in rows],
                {first["batch_id"]: SimpleNamespace(quantity=first["batch_quantity"])})
        except PieceAdoptionBlocked:
            reject("共同工序和分件工序的关系不完整，请先核对工艺，未修改报工。", "execution_dependencies_unproven", 409)
        return {work.op_id: work.predecessor_op_ids for work in scope.operations}
    # Legacy piece-only routes can be heterogeneous; each piece keeps its own chain.
    chains, result = defaultdict(list), {}
    for row in rows:
        chains[row["piece_id"]].append(row)
    for chain in chains.values():
        if (any(not number(row["seq"], integer=True, positive=True) for row in chain)
                or len({row["seq"] for row in chain}) != len(chain)):
            reject("工序顺序号缺失或重复，无法核对报工前后关系，请先核对工艺。", "execution_dependencies_unproven", 409)
        previous = ()
        for row in sorted(chain, key=lambda item: item["seq"]):
            result[row["id"]] = previous
            previous = (row["id"],)
    return result


def _reachable(graph, ref):
    result, pending = set(), list(graph[ref])
    while pending:
        current = pending.pop()
        if current not in result:
            result.add(current)
            pending.extend(graph[current])
    return sorted(result)


class ReportDependencies:
    def __init__(self, ledger, projections=()):
        self.ledger = ledger
        self.repo = WorkbenchReportValidationRepository(ledger.conn)
        self.routes = {}
        self.projected = {row.operation_ref: row for row in projections}
        self.merged = {}

    def _route(self, batch_id):
        if batch_id in self.routes:
            return self.routes[batch_id]
        rows = self.repo.batch_operation_rows(batch_id)
        if len(rows) > 10000:
            reject("本次报工涉及工序过多，请缩小范围。", "query_too_large", 413)
        refs = {row["id"]: row["operation_ref"] for row in rows}
        if not rows or None in refs.values() or len(refs) != len(rows) or len(set(refs.values())) != len(rows):
            reject("工艺或工序编号不完整，无法核对报工影响，请刷新后核对。", "execution_dependencies_unproven", 409)
        parents = {refs[key]: [refs[prior] for prior in values] for key, values in _predecessors(rows).items()}
        children = {ref: [] for ref in parents}
        for ref, values in parents.items():
            for prior in values:
                children[prior].append(ref)
        self._merged_contexts(rows)
        self.routes[batch_id] = parents, children
        return parents, children

    def _merged_contexts(self, rows):
        external = {row["id"]: row for row in rows if row["source"] == "external"}
        if not external:
            return
        for context in BatchExternalContextRepository(self.ledger.conn).for_operations(external):
            if context["merge_mode"] != "merged":
                continue
            op = external[context["operation_id"]]
            require_context(context, operation_id=op["id"], part_no=op["part_no"], sequence=op["seq"])
            self.merged[op["operation_ref"]] = (op["batch_id"], op["piece_id"], context_group_key(context))

    def relatives(self, operation, *, predecessors=False):
        """Cycle members are peers; retain transitive dependencies outside the cycle."""
        parents, children = self._route(operation["batch_id"])
        ref = operation["operation_ref"]
        if ref not in parents:
            reject("原工序不在当前工艺中，未修改报工。", "execution_dependencies_unproven", 409)
        reachable = _reachable(parents if predecessors else children, ref)
        return [other for other in reachable if not self.same_merged_cycle(ref, other)]

    def projections(self, refs):
        missing = [ref for ref in refs if ref not in self.projected]
        if missing:
            # Preview/command already owns the snapshot; dependency reads do not issue edit tokens.
            rows = self.ledger.project_loaded(self.ledger.load(missing), contexts=False)
            self.projected.update((row.operation_ref, row) for row in rows)
        return [self.projected[ref] for ref in refs]

    def same_merged_cycle(self, first, second):
        return first in self.merged and self.merged[first] == self.merged.get(second)
