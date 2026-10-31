"""Read/display orchestration only. AJ owns every execution projection and write."""

from contextlib import contextmanager

from core.models.content import content_text
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_plan_scope import PlanReadScope
from core.services.execution.processing_hours import hour_totals
from core.services.execution.projection import materialize_operation_history, validated_correction_history
from core.services.workbench.facts.execution_projection import attach_context
from core.services.workbench.facts.source_revisions import EXECUTION_SOURCE_KEYS, read_source_revisions
from core.services.workbench.plan.queries import WorkbenchPlanQueryService
from data.repositories.workbench_field_query_repo import WorkbenchFieldQueryRepository

from .field_workspace_scope import STATES, matches, matches_plan


class _LazyReportDict(dict):
    def __init__(self, values, *, history):
        super().__init__(values)
        self._history = history

    def __getitem__(self, key):
        if key == 'correction_history' and 'correction_history' not in self:
            self['correction_history'] = validated_correction_history(self._history)
        return super().__getitem__(key)


def _build_lazy_reports(projection, histories, labels):
    return [
        _LazyReportDict(
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
                'actual_machine_label': labels.get(report.actual_machine_ref),
                'actual_operator_label': labels.get(report.actual_operator_ref),
                'remark': report.remark,
                'recorded_at': report.recorded_at,
                'revision_ref': report.revision_ref,
                'local_operator': report.local_operator,
                'declared_operator': report.declared_operator,
            },
            history=histories[report.report_ref],
        )
        for report in projection.reports
    ]


class _CohortExecutionDict(dict):
    def __init__(self, values, *, projection, histories, labels):
        super().__init__(values)
        self._projection = projection
        self._histories = histories
        self._labels = labels

    def __getitem__(self, key):
        if key == 'reports' and 'reports' not in self:
            self['reports'] = _build_lazy_reports(self._projection, self._histories, self._labels)
        return super().__getitem__(key)


class FieldWorkspaceService:
    def __init__(self, conn, *, context_factory=None, ledger=None):
        from .ledger import ExecutionLedgerService

        self.conn = conn
        self.ledger = ledger if ledger is not None else ExecutionLedgerService(conn, context_factory=context_factory)
        self.queries = WorkbenchFieldQueryRepository(conn)
        self.plans = WorkbenchPlanQueryService(conn)
        self._loaded = None

    @contextmanager
    def read_snapshot(self):
        with self.plans.read_snapshot():
            with self.ledger.read_snapshot():
                yield

    def _plan_ref(self, scope):
        if scope.get('plan_ref'):
            return scope['plan_ref']
        current_plan = self.ledger._current_plan()
        return current_plan['plan_ref'] if current_plan is not None else None

    def _labels(self, facts, plan_tasks):
        refs = {
            history[-1]['values'][key]
            for group in facts['reports'].values()
            for history in group.values()
            for key in ('actual_machine_ref', 'actual_operator_ref')
            if history[-1]['values'].get(key)
        }
        refs.update(task[key] for task in plan_tasks for key in ('machine_ref', 'operator_ref') if task[key])
        labels, codes = {}, {}
        for row in self.ledger.resources(refs):
            labels[row['ref']] = row['label']
            codes[row['ref']] = row['business_code']
        return labels, codes

    def cohort(self, scope):
        if not self.conn.in_transaction:
            raise RuntimeError('Field cohort requires caller read snapshot.')
        plan_ref = self._plan_ref(scope)
        if plan_ref is None:
            return ({'plan': None, 'scope': dict(scope), 'tasks': [], 'summary': self._summary([])},
                    content_text({'plan_revision': self.plans.references.read_revision(),
                                  'ledger_revision': self.ledger.revision_clock(),
                                  'revisions': read_source_revisions(self.conn, EXECUTION_SOURCE_KEYS)}), {})
        plan = self.plans.execution_workspace(
            PlanReadScope(plan_ref, scope.get('range_start'), scope.get('range_end')),
        )
        plan_tasks = [task for task in plan['tasks'] if matches_plan(task, scope)]
        refs = [task['operation_ref'] for task in plan_tasks]
        facts = self.ledger.load_many(refs, comparison_plan_ref=plan_ref)
        # 整份计划只做轻量投影、不展开更正历史和作废字典、不签发写令牌：
        # 完整报工 DTO 与写令牌只发给本次返回的那一页或那一条（page/detail）。
        loaded = {ref: self.ledger.project_operation(facts, ref, include_history=False) for ref in facts['operations']}
        labels, resource_codes = self._labels(facts, plan_tasks)
        self._loaded = (facts, loaded, labels)
        names = self.queries.batch_part_names({row['batch_id'] for row in plan_tasks})
        tasks, scope_tasks = [], []
        count_scope = {key: value for key, value in scope.items()
                       if key not in ('state', 'batch_ids', 'range_start', 'range_end', 'plan_finish_date_from', 'plan_finish_date_to')}
        for row in plan_tasks:
            ref = row['operation_ref']
            task = self._cohort_task(row, loaded[ref], facts['reports'].get(ref, {}), facts['voids'], labels, names)
            # 报工页据此对外协工序不提供实际设备、人员选择；写入时仍以服务端校验为准。
            task['source'] = facts['operations'][ref]['source']
            if matches(task, count_scope):
                scope_tasks.append(task)
                if not scope.get('state') or task['execution']['execution_state'] == scope['state']:
                    tasks.append(task)
        tasks.sort(key=lambda item: (item['batch_id'], int(item['sequence']), item['planned_start'], item['task_ref']))
        effective = dict(scope, plan_ref=plan_ref)
        summary = self._summary(tasks, scope_tasks)
        state = content_text({
            'scope': effective,
            'plan_revision': self.plans.references.read_revision(),
            'ledger_revision': facts['clock'],
            'revisions': read_source_revisions(self.conn, EXECUTION_SOURCE_KEYS),
        })
        return {'plan': plan['plan'], 'scope': effective, 'tasks': tasks, 'summary': summary}, state, resource_codes

    @staticmethod
    def _cohort_task(row, projection, histories, voids, labels, names):
        execution = _CohortExecutionDict(
            {
                'operation_ref': projection.operation_ref,
                'current_task_ref': projection.current_task_ref,
                'comparison_task_ref': projection.comparison_task_ref,
                'target_quantity': projection.target_quantity,
                'target_basis': projection.target_basis,
                'known_completed_quantity': projection.known_completed_quantity,
                'quantity_complete': projection.quantity_complete,
                'unknown_record_count': projection.unknown_record_count,
                'records_complete': projection.records_complete,
                'first_actual_start': projection.first_actual_start,
                'confirmed_finish': projection.confirmed_finish,
                'execution_state': projection.execution_state,
                'completion_basis': projection.completion_basis,
                'data_quality': projection.data_quality,
                'report_count': len(projection.reports),
                'voided_report_count': sum(report_ref in voids for report_ref in histories),
                'remaining_quantity': projection.remaining_quantity,
                'remaining_plan': projection.remaining_plan,
                'data_gaps': projection.data_gaps,
                'voided_reports': [],
            },
            projection=projection,
            histories=histories,
            labels=labels,
        )
        name = names.get(row['batch_id'])
        task = {'task_ref': row['task_ref'], 'plan_ref': row['plan_ref'], 'operation_ref': row['operation_ref'],
                'batch_id': row['batch_id'], 'part_name': name if type(name) is str else '',
                'sequence': row['sequence'], 'operation_label': str(row['sequence']) + ' ' + row['process_label'],
                'planned_start': row['start'], 'planned_end': row['end'], 'execution': execution}
        for key in ('piece_id', 'quantity', 'batch_quantity', 'quantity_basis', 'quantity_reason'):
            task[key] = row[key]
        for key in ('event_kind', 'duration_seconds', 'occupies_resources'):
            if key in row:
                task[key] = row[key]
        for kind in ('machine', 'operator'):
            task['planned_' + kind + '_ref'] = row[kind + '_ref']
            task['planned_' + kind + '_label'] = labels.get(row[kind + '_ref'])
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

    @staticmethod
    def _task_reports(task):
        return task['execution']._projection.reports

    @classmethod
    def _summary(cls, tasks, scope_tasks=None):
        counted = tasks if scope_tasks is None else scope_tasks
        state_counts = dict.fromkeys(STATES, 0)
        for task in counted:
            state_counts[task['execution']['execution_state']] += 1
        reports = [report for task in counted for report in cls._task_reports(task)]
        hours = hour_totals(reports)
        if scope_tasks is None:
            report_count, complete_count = len(reports), state_counts['complete']
        else:
            report_count = sum(len(cls._task_reports(task)) for task in tasks)
            complete_count = sum(task['execution']['execution_state'] == 'complete' for task in tasks)
        return {'tasks': len(tasks), 'reports': report_count, 'complete': complete_count,
                'incomplete': sum(task['execution']['data_quality'] != 'complete' for task in tasks),
                'state_counts': state_counts, 'state_scope_tasks': len(counted),
                'effective_processing_hours': hours['effective_processing_hours'],
                'known_effective_processing_hours': hours['known_effective_processing_hours'],
                'unknown_hour_reports': hours['unknown_hour_events']}

    def _with_contexts(self, tasks):
        """Materialize full report/correction DTOs and issue write contexts for returned rows only."""
        if self._loaded is None:
            return tasks
        facts, loaded, labels = self._loaded
        factory = self.ledger.context_factory
        result, materialized_operations = [], {}
        for task in tasks:
            ref = task['operation_ref']
            if ref not in materialized_operations:
                full = materialize_operation_history(
                    loaded[ref], facts['reports'].get(ref, {}), facts['voids']
                )
                if factory is not None:
                    full = attach_context(full, factory, self.ledger.fact_snapshot(facts, ref))
                materialized_operations[ref] = full
            projection_dict = self._decorate_execution(
                task['task_ref'], materialized_operations[ref].to_dict(), labels
            )
            result.append(dict(task, execution=projection_dict))
        return result

    def page(self, cohort, number, size):
        total = len(cohort['tasks'])
        pages = max(1, (total + size - 1) // size)
        if number > pages:
            raise WorkbenchCommandRejected('invalid_input', '翻页位置已失效，请回到第 1 页重新查询。', 400)
        return dict(cohort, tasks=self._with_contexts(cohort['tasks'][(number - 1) * size:number * size]),
                    page={'number': number, 'size': size, 'total': total, 'pages': pages, 'sort': [{'field': 'batch_id', 'direction': 'asc'}]})

    def detail(self, cohort, task_ref):
        for task in cohort['tasks']:
            if task['task_ref'] == task_ref:
                return {'task': self._with_contexts([task])[0], 'scope': cohort['scope'], 'plan': cohort['plan']}
        raise WorkbenchCommandRejected('entity_not_found', '所选任务不在当前范围，请刷新后重选。', 404)
