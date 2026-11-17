"""Read/display orchestration only. AJ owns every execution projection and write."""

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Mapping, Optional, Tuple

from core.models.content import content_text
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_execution import ExecutionProjection
from core.models.workbench_plan_scope import PlanReadScope
from core.services.execution.ledger_reader import ExecutionLedgerReadScope
from core.services.execution.projection import projection_resource_refs
from core.services.workbench.facts.execution_projection import attach_context
from core.services.workbench.facts.source_revisions import EXECUTION_SOURCE_KEYS, read_source_revisions
from core.services.workbench.facts.zero_duration import point_event_dto
from core.services.workbench.plan.projection import project_plan
from core.services.workbench.plan.queries import WorkbenchPlanQueryService
from core.services.workbench.plan.read_context import PlanReadContext
from core.shared.local_datetime import us_to_datetime, us_to_iso
from core.shared.strict_parse import wire_int
from data.repositories.workbench_field_query_repo import (
    WorkbenchFieldQueryRepository,
    empty_field_summary,
)


@dataclass(frozen=True)
class FieldWorkspaceReadScope:
    plan_context: PlanReadContext
    ledger_scope: ExecutionLedgerReadScope


@dataclass(frozen=True)
class FieldReadState:
    plan_ref: Optional[str]
    effective_scope: Dict[str, Any]
    state: str


@dataclass(frozen=True)
class CohortTaskExecution:
    projection: ExecutionProjection
    labels: Mapping[Optional[str], Any]

    def report_rows(self) -> List[Dict[str, Any]]:
        return [
            {
                'report_ref': report.report_ref,
                'report_no': report.report_no,
                'operation_ref': report.operation_ref,
                'recorded_against_task_ref': report.recorded_against_task_ref,
                'recorded_against_plan_ref': report.recorded_against_plan_ref,
                'source': report.source,
                'actual_start': report.actual_start,
                'actual_end': report.actual_end,
                'completed_quantity': report.completed_quantity,
                'effective_processing_hours': report.effective_processing_hours,
                'actual_machine_ref': report.actual_machine_ref,
                'actual_operator_ref': report.actual_operator_ref,
                'actual_machine_label': self.labels.get(report.actual_machine_ref),
                'actual_operator_label': self.labels.get(report.actual_operator_ref),
                'remark': report.remark,
                'recorded_at': report.recorded_at,
                'revision_ref': report.revision_ref,
                'revision_count': report.revision_count,
                'local_operator': report.local_operator,
                'declared_operator': report.declared_operator,
            }
            for report in self.projection.reports
        ]


class FieldWorkspaceService:
    def __init__(self, conn, *, context_factory=None, ledger=None):
        from .ledger import ExecutionLedgerService

        self.conn = conn
        self.ledger = ledger if ledger is not None else ExecutionLedgerService(conn, context_factory=context_factory)
        self.queries = WorkbenchFieldQueryRepository(conn)
        self.plans = WorkbenchPlanQueryService(conn)

    @contextmanager
    def read_snapshot(self) -> Iterator[FieldWorkspaceReadScope]:
        with self.plans.read_snapshot() as plan_context:
            with self.ledger.read_snapshot() as ledger_scope:
                yield FieldWorkspaceReadScope(plan_context=plan_context, ledger_scope=ledger_scope)

    @contextmanager
    def read_snapshot_with_ledger(self, ledger_scope: ExecutionLedgerReadScope) -> Iterator[FieldWorkspaceReadScope]:
        with self.plans.read_snapshot() as plan_context:
            yield FieldWorkspaceReadScope(plan_context=plan_context, ledger_scope=ledger_scope)

    def _plan_ref(self, ws_scope: FieldWorkspaceReadScope, scope):
        if scope.get('plan_ref'):
            return scope['plan_ref']
        current_plan = self.ledger.current_plan(ws_scope.ledger_scope)
        return current_plan['plan_ref'] if current_plan is not None else None

    def _selected_plan_header(
        self, ws_scope: FieldWorkspaceReadScope, plan_ref: str, scope: Mapping[str, Any]
    ) -> Tuple[int, Dict[str, Any]]:
        entry, _ = ws_scope.plan_context.selected(plan_ref)
        version = entry.locator.version
        issue = self.queries.first_plan_binding_issue(version, scope)
        if issue == 'identity_missing':
            raise WorkbenchCommandRejected('identity_missing', '安排关联的批次、设备或人员编号缺失，请到资料总览核对。')
        if issue is not None:
            raise WorkbenchCommandRejected('entity_not_found', '工序关联资料缺失，请刷新重选；仍无法打开时请联系维护人员。', 404)
        return version, project_plan(entry, plan_ref)

    def _labels(self, ledger_scope: ExecutionLedgerReadScope, projections, rows):
        refs = {
            ref
            for projection in projections.values()
            for ref in projection_resource_refs(projection)
        }
        refs.update(
            row[key]
            for row in rows
            for key in ('planned_machine_ref', 'planned_operator_ref')
            if row[key]
        )
        labels, codes = {}, {}
        for row in self.ledger.resources(ledger_scope, refs):
            labels[row['ref']] = row['label']
            codes[row['ref']] = row['business_code']
        return labels, codes

    @staticmethod
    def _build_task_row(plan_ref: str, row: Mapping[str, Any], labels: Mapping[Optional[str], Any], source: Any, execution: Any) -> Dict[str, Any]:
        sequence = wire_int(row['seq'])
        part_name = row['part_name']
        task: Dict[str, Any] = {
            'task_ref': row['task_ref'],
            'plan_ref': plan_ref,
            'operation_ref': row['operation_ref'],
            'batch_id': row['batch_id'],
            'part_name': part_name if type(part_name) is str else '',
            'sequence': sequence,
            'operation_label': f"{sequence} {row['op_type_name']}",
            'planned_start': us_to_iso(row['start_us']),
            'planned_end': us_to_iso(row['end_us']),
            'execution': execution,
            'piece_id': row['piece_id'],
            'quantity': row['quantity'],
            'batch_quantity': row['batch_quantity'],
            'quantity_basis': row['quantity_basis'],
            'quantity_reason': row['quantity_reason'],
        }
        if row['is_point_event']:
            point_dt = us_to_datetime(row['start_us'])
            task.update(point_event_dto(point_dt, point_dt))
        for kind in ('machine', 'operator'):
            ref_val = row['planned_' + kind + '_ref']
            task['planned_' + kind + '_ref'] = ref_val
            task['planned_' + kind + '_label'] = labels.get(ref_val)
        # 报工页据此对外协工序不提供实际设备、人员选择；写入时仍以服务端校验为准。
        task['source'] = source
        return task

    @staticmethod
    def _decorate_execution(task_ref, projection_dict, labels):
        if projection_dict['current_task_ref'] != task_ref:
            projection_dict['write_context'] = {
                'write_token': None,
                'expires_at': None,
                'capabilities': {'create': False},
                'blocked_reasons': [{'code': 'plan_not_writable', 'message': '这条安排属于旧计划，不能在旧任务上新增报工。'}],
            }
        for report in projection_dict['reports'] + [item['report'] for item in projection_dict['voided_reports']]:
            for kind in ('machine', 'operator'):
                report['actual_' + kind + '_label'] = labels.get(report['actual_' + kind + '_ref'])
        return projection_dict

    def _materialize_rows_with_contexts(
        self, ws_scope: FieldWorkspaceReadScope, plan_ref: str, rows: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        if not rows:
            return []
        refs = [row['operation_ref'] for row in rows]
        facts = self.ledger.load(ws_scope.ledger_scope, refs, comparison_plan_ref=plan_ref, include_history=True)
        factory = self.ledger.context_factory
        projected_by_ref: Dict[str, ExecutionProjection] = {}
        for ref in facts['operations']:
            full = self.ledger.project_operation(facts, ref, include_history=True)
            if factory is not None:
                full = attach_context(full, factory, self.ledger.fact_snapshot(facts, ref))
            projected_by_ref[ref] = full
        labels, _ = self._labels(ws_scope.ledger_scope, projected_by_ref, rows)
        result = []
        for row in rows:
            ref = row['operation_ref']
            projection_dict = self._decorate_execution(
                row['task_ref'], projected_by_ref[ref].to_dict(), labels
            )
            result.append(
                self._build_task_row(
                    plan_ref,
                    row,
                    labels,
                    facts['operations'][ref]['source'],
                    projection_dict,
                )
            )
        return result

    def _locate_task(
        self,
        version: int,
        scope: Mapping[str, Any],
        locate_task_ref: str,
        locate_operation_ref: Optional[str],
    ) -> int:
        found = self.queries.locate_task_index(version, scope, locate_task_ref)
        if found is None:
            raise WorkbenchCommandRejected('entity_not_found', '所选任务不在当前范围，请刷新后重选。', 404)
        index, op_ref = found
        if locate_operation_ref and op_ref != locate_operation_ref:
            raise WorkbenchCommandRejected('constraint_conflict', '选中的工序和这条任务对不上，安排没有变化。请刷新页面后重新选择工序。')
        return index

    def prepare_read(self, ws_scope: FieldWorkspaceReadScope, scope: Dict[str, Any]) -> FieldReadState:
        if not self.conn.in_transaction:
            raise RuntimeError('Field cohort requires caller read snapshot.')
        plan_ref = self._plan_ref(ws_scope, scope)
        if plan_ref is None:
            effective = scope
            state = content_text({
                'plan_revision': ws_scope.plan_context.plan_revision,
                'ledger_revision': self.ledger.revision_clock(ws_scope.ledger_scope),
                'revisions': read_source_revisions(self.conn, EXECUTION_SOURCE_KEYS),
            })
            return FieldReadState(None, effective, state)
        _, plan_state = self.plans.prebind_scope(
            ws_scope.plan_context,
            PlanReadScope(plan_ref, scope.get('range_start'), scope.get('range_end')),
        )
        effective = dict(scope, plan_ref=plan_ref)
        state = content_text({
            'scope': effective,
            'plan_revision': plan_state['plan_revision'],
            'ledger_revision': self.ledger.revision_clock(ws_scope.ledger_scope),
            'revisions': plan_state['sources'],
        })
        return FieldReadState(plan_ref, effective, state)

    def cohort(self, ws_scope: FieldWorkspaceReadScope, read: FieldReadState):
        if read.plan_ref is None:
            return {'plan': None, 'scope': read.effective_scope, 'tasks': [], 'summary': empty_field_summary()}, {}
        scope = read.effective_scope
        version, plan_dto = self._selected_plan_header(ws_scope, read.plan_ref, scope)
        summary = self.queries.field_summary(version, scope)
        rows = self.queries.field_task_rows(version, scope) if summary['tasks'] > 0 else []
        refs = [row['operation_ref'] for row in rows]
        facts = self.ledger.load_many(
            ws_scope.ledger_scope, refs, comparison_plan_ref=read.plan_ref, include_history=False
        )
        loaded = {ref: self.ledger.project_operation(facts, ref, include_history=False) for ref in facts['operations']}
        labels, resource_codes = self._labels(ws_scope.ledger_scope, loaded, rows)
        tasks = [
            self._build_task_row(
                read.plan_ref,
                row,
                labels,
                facts['operations'][row['operation_ref']]['source'],
                CohortTaskExecution(projection=loaded[row['operation_ref']], labels=labels),
            )
            for row in rows
        ]
        return {'plan': plan_dto, 'scope': scope, 'tasks': tasks, 'summary': summary}, resource_codes

    def page(
        self,
        ws_scope: FieldWorkspaceReadScope,
        read: FieldReadState,
        number: int,
        size: int,
        *,
        locate_task_ref: Optional[str] = None,
        locate_operation_ref: Optional[str] = None,
    ) -> Dict[str, Any]:
        scope = read.effective_scope
        if read.plan_ref is None:
            if locate_task_ref:
                raise WorkbenchCommandRejected('entity_not_found', '所选任务不在当前范围，请刷新后重选。', 404)
            if number > 1:
                raise WorkbenchCommandRejected('invalid_input', '翻页位置已失效，请回到第 1 页重新查询。', 400)
            return {
                'plan': None,
                'scope': scope,
                'tasks': [],
                'summary': empty_field_summary(),
                'page': {'number': 1, 'size': size, 'total': 0, 'pages': 1, 'sort': [{'field': 'batch_id', 'direction': 'asc'}]},
            }
        version, plan_dto = self._selected_plan_header(ws_scope, read.plan_ref, scope)
        if locate_task_ref:
            index = self._locate_task(version, scope, locate_task_ref, locate_operation_ref)
            number = index // size + 1
        summary = self.queries.field_summary(version, scope)
        total = summary['tasks']
        pages = max(1, (total + size - 1) // size)
        if number > pages:
            raise WorkbenchCommandRejected('invalid_input', '翻页位置已失效，请回到第 1 页重新查询。', 400)
        page_rows = (
            self.queries.field_task_rows(version, scope, limit=size, offset=(number - 1) * size)
            if total > 0
            else []
        )
        tasks = self._materialize_rows_with_contexts(ws_scope, read.plan_ref, page_rows)
        return {
            'plan': plan_dto,
            'scope': scope,
            'tasks': tasks,
            'summary': summary,
            'page': {
                'number': number,
                'size': size,
                'total': total,
                'pages': pages,
                'sort': [{'field': 'batch_id', 'direction': 'asc'}],
            },
        }

    def detail(
        self,
        ws_scope: FieldWorkspaceReadScope,
        read: FieldReadState,
        task_ref: str,
        *,
        locate_task_ref: Optional[str] = None,
        locate_operation_ref: Optional[str] = None,
    ) -> Dict[str, Any]:
        scope = read.effective_scope
        if read.plan_ref is None:
            raise WorkbenchCommandRejected('entity_not_found', '所选任务不在当前范围，请刷新后重选。', 404)
        version, plan_dto = self._selected_plan_header(ws_scope, read.plan_ref, scope)
        if locate_task_ref:
            self._locate_task(version, scope, locate_task_ref, locate_operation_ref)
        rows = self.queries.field_task_rows(version, scope, task_ref=task_ref)
        if not rows:
            raise WorkbenchCommandRejected('entity_not_found', '所选任务不在当前范围，请刷新后重选。', 404)
        task = self._materialize_rows_with_contexts(ws_scope, read.plan_ref, rows)[0]
        return {'task': task, 'scope': scope, 'plan': plan_dto}
