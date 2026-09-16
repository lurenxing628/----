"""Read/display orchestration only. AJ owns every execution projection and write."""

from contextlib import contextmanager

from core.models.workbench_command import WorkbenchCommandRejected, input_fingerprint
from core.models.workbench_plan_reference import WorkbenchPlanLocator
from core.models.workbench_plan_scope import PlanReadScope
from core.services.workbench.field_workspace_scope import STATES, matches
from core.services.workbench.plan_fact_serialization import plain_plan_facts
from core.services.workbench.plan_queries import WorkbenchPlanQueryService
from data.repositories.workbench_execution_repo import WorkbenchExecutionRepository
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository


class FieldWorkspaceService:
    def __init__(self, conn, *, context_factory=None):
        from core.services.workbench.execution_ledger import ExecutionLedgerService

        self.conn = conn
        self.ledger = ExecutionLedgerService(conn, context_factory=context_factory)
        self.repo = WorkbenchExecutionRepository(conn)
        self.plans = WorkbenchPlanQueryService(conn)

    @contextmanager
    def read_snapshot(self):
        self.repo.require_schema()
        with self.plans.read_snapshot():
            yield

    def _plan_ref(self, scope):
        if scope.get('plan_ref'):
            return scope['plan_ref']
        version = self.conn.execute('SELECT MAX(version) FROM ScheduleHistory').fetchone()[0]
        if version is None:
            return None
        return WorkbenchPlanIdentityRepository(self.conn).get_plan_ref(WorkbenchPlanLocator(version, 'adopted'))

    def _labels(self, projections, plan):
        refs = {row[key] for p in projections.values() for row in p['reports'] + [item['report'] for item in p['voided_reports']]
                for key in ('actual_machine_ref', 'actual_operator_ref') if row[key]}
        refs.update(task[key] for task in plan['tasks'] for key in ('machine_ref', 'operator_ref') if task[key])
        return {row['ref']: row['label'] for row in self.repo.resources(refs)}

    def cohort(self, scope):
        if not self.conn.in_transaction:
            raise RuntimeError('Field cohort requires caller read snapshot.')
        self.repo.require_schema()
        plan_ref = self._plan_ref(scope)
        if plan_ref is None:
            return {'plan': None, 'scope': dict(scope), 'tasks': [], 'summary': self._summary([])}, input_fingerprint(self.repo.clock())
        plan, plan_state = self.plans.workspace(PlanReadScope(plan_ref))
        refs = [task['operation_ref'] for task in plan['tasks']]
        projections = {item.operation_ref: item.to_dict() for item in self.ledger.project_operations(refs, comparison_plan_ref=plan_ref)}
        labels = self._labels(projections, plan)
        names = {row[0]: row[1] for row in self.conn.execute('SELECT b.batch_id,p.part_name FROM Batches b LEFT JOIN Parts p ON p.part_no=b.part_no')}
        tasks, scope_tasks = [], []
        count_scope = {key: value for key, value in scope.items() if key != 'state'}
        for row in plan['tasks']:
            task = self._task(row, projections[row['operation_ref']], labels, names)
            if matches(task, count_scope):
                scope_tasks.append(task)
                if not scope.get('state') or task['execution']['execution_state'] == scope['state']:
                    tasks.append(task)
        tasks.sort(key=lambda item: (item['batch_id'], int(item['sequence']), item['planned_start'], item['task_ref']))
        effective = dict(scope, plan_ref=plan_ref)
        # Tokens have expiries and must not become part of the business fingerprint.
        facts = self.ledger.snapshot(refs[0]) if len(refs) == 1 else self.repo.clock()
        summary = self._summary(tasks, scope_tasks)
        state = input_fingerprint({'scope': effective, 'plan': plan_state, 'execution': plain_plan_facts(facts),
                                   'data': self._without_context(tasks), 'summary': summary})
        return {'plan': plan['plan'], 'scope': effective, 'tasks': tasks, 'summary': summary}, state

    @staticmethod
    def _task(row, projection, labels, names):
        if projection['current_task_ref'] != row['task_ref']:
            projection['write_context'] = {'write_token': None, 'expires_at': None, 'capabilities': {'create': False},
                'blocked_reasons': [{'code': 'plan_not_writable', 'message': '这条安排属于旧计划，不能在旧任务上新增报工。'}]}
        for report in projection['reports'] + [item['report'] for item in projection['voided_reports']]:
            for kind in ('machine', 'operator'):
                report['actual_' + kind + '_label'] = labels.get(report['actual_' + kind + '_ref'])
        name = names.get(row['batch_id'])
        task = {'task_ref': row['task_ref'], 'plan_ref': row['plan_ref'], 'operation_ref': row['operation_ref'],
                'batch_id': row['batch_id'], 'part_name': name if type(name) is str else '',
                'sequence': row['sequence'], 'operation_label': str(row['sequence']) + ' ' + row['process_label'],
                'planned_start': row['start'], 'planned_end': row['end'], 'execution': projection}
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
    def _without_context(value):
        if isinstance(value, dict):
            return {key: FieldWorkspaceService._without_context(item) for key, item in value.items() if key != 'write_context'}
        if isinstance(value, list):
            return [FieldWorkspaceService._without_context(item) for item in value]
        return plain_plan_facts(value)

    @staticmethod
    def _summary(tasks, scope_tasks=None):
        counted = tasks if scope_tasks is None else scope_tasks
        state_counts = {state: sum(task['execution']['execution_state'] == state for task in counted) for state in STATES}
        reports = [report for task in counted for report in task['execution']['reports']]
        unknown = sum(report['effective_processing_hours'] is None for report in reports)
        known = sum(report['effective_processing_hours'] for report in reports if report['effective_processing_hours'] is not None)
        return {'tasks': len(tasks), 'reports': sum(len(task['execution']['reports']) for task in tasks),
                'complete': sum(task['execution']['execution_state'] == 'complete' for task in tasks),
                'incomplete': sum(task['execution']['data_quality'] != 'complete' for task in tasks),
                'state_counts': state_counts, 'state_scope_tasks': len(counted),
                'effective_processing_hours': None if unknown else known,
                'known_effective_processing_hours': known, 'unknown_hour_reports': unknown}

    @staticmethod
    def page(cohort, number, size):
        total = len(cohort['tasks'])
        pages = max(1, (total + size - 1) // size)
        if number > pages:
            raise WorkbenchCommandRejected('invalid_input', '翻页位置已失效，请回到第 1 页重新查询。', 400)
        return dict(cohort, tasks=cohort['tasks'][(number - 1) * size:number * size],
                    page={'number': number, 'size': size, 'total': total, 'pages': pages, 'sort': [{'field': 'batch_id', 'direction': 'asc'}]})

    @staticmethod
    def detail(cohort, task_ref):
        for task in cohort['tasks']:
            if task['task_ref'] == task_ref:
                return {'task': task, 'scope': cohort['scope'], 'plan': cohort['plan']}
        raise WorkbenchCommandRejected('entity_not_found', '所选任务不在当前范围，请刷新后重选。', 404)
