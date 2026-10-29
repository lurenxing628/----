"""Read/display orchestration only. AJ owns every execution projection and write."""

from contextlib import contextmanager

from core.models.content import content_text
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_plan_scope import PlanReadScope
from core.services.execution.processing_hours import hour_totals
from core.services.workbench.facts.execution_projection import attach_context
from core.services.workbench.plan.queries import WorkbenchPlanQueryService
from data.repositories.workbench_field_query_repo import WorkbenchFieldQueryRepository

from .field_workspace_scope import STATES, matches, matches_plan


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

    def _labels(self, projections, plan_tasks):
        refs = {row[key] for p in projections.values() for row in p['reports'] + [item['report'] for item in p['voided_reports']]
                for key in ('actual_machine_ref', 'actual_operator_ref') if row[key]}
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
                    content_text(self.ledger.revision_clock()), {})
        plan, plan_state = self.plans.execution_workspace(
            PlanReadScope(plan_ref, scope.get('range_start'), scope.get('range_end')),
        )
        plan_tasks = [task for task in plan['tasks'] if matches_plan(task, scope)]
        refs = [task['operation_ref'] for task in plan_tasks]
        facts = self.ledger.load_many(refs, comparison_plan_ref=plan_ref)
        # 整份计划只投影、不签发写令牌：令牌只发给本次返回的那一页或那一条（page/detail）。
        # 几千道任务逐条签发会把各页面共用的令牌登记表挤满，刚显示的报工令牌随即失效。
        loaded = {item.operation_ref: item for item in self.ledger.project_loaded(facts, contexts=False)}
        self._loaded = (facts, loaded)
        projections = {ref: item.to_dict() for ref, item in loaded.items()}
        labels, resource_codes = self._labels(projections, plan_tasks)
        names = self.queries.batch_part_names({row['batch_id'] for row in plan_tasks})
        tasks, scope_tasks = [], []
        count_scope = {key: value for key, value in scope.items()
                       if key not in ('state', 'batch_ids', 'range_start', 'range_end', 'plan_finish_date_from', 'plan_finish_date_to')}
        for row in plan_tasks:
            task = self._task(row, projections[row['operation_ref']], labels, names)
            # 报工页据此对外协工序不提供实际设备、人员选择；写入时仍以服务端校验为准。
            task['source'] = facts['operations'][row['operation_ref']]['source']
            if matches(task, count_scope):
                scope_tasks.append(task)
                if not scope.get('state') or task['execution']['execution_state'] == scope['state']:
                    tasks.append(task)
        tasks.sort(key=lambda item: (item['batch_id'], int(item['sequence']), item['planned_start'], item['task_ref']))
        effective = dict(scope, plan_ref=plan_ref)
        # Tokens have expiries and must not become part of the business fingerprint.
        state_facts = self.ledger.fact_snapshot(facts, refs[0]) if len(refs) == 1 else facts['clock']
        summary = self._summary(tasks, scope_tasks)
        state = content_text({'scope': effective, 'plan': plan_state, 'execution': state_facts, 'parts': names, 'labels': labels})
        return {'plan': plan['plan'], 'scope': effective, 'tasks': tasks, 'summary': summary}, state, resource_codes

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
    def _summary(tasks, scope_tasks=None):
        counted = tasks if scope_tasks is None else scope_tasks
        state_counts = dict.fromkeys(STATES, 0)
        for task in counted:
            state_counts[task['execution']['execution_state']] += 1
        reports = [report for task in counted for report in task['execution']['reports']]
        hours = hour_totals(reports)
        if scope_tasks is None:
            report_count, complete_count = len(reports), state_counts['complete']
        else:
            report_count = sum(len(task['execution']['reports']) for task in tasks)
            complete_count = sum(task['execution']['execution_state'] == 'complete' for task in tasks)
        return {'tasks': len(tasks), 'reports': report_count, 'complete': complete_count,
                'incomplete': sum(task['execution']['data_quality'] != 'complete' for task in tasks),
                'state_counts': state_counts, 'state_scope_tasks': len(counted),
                'effective_processing_hours': hours['effective_processing_hours'],
                'known_effective_processing_hours': hours['known_effective_processing_hours'],
                'unknown_hour_reports': hours['unknown_hour_events']}

    def _with_contexts(self, tasks):
        """Issue write contexts for the returned rows only; cohort tasks stay token-free."""
        factory = self.ledger.context_factory
        if factory is None or self._loaded is None:
            return tasks
        facts, loaded = self._loaded
        result, attached_operations = [], {}
        for task in tasks:
            ref = task['operation_ref']
            if ref not in attached_operations:
                attached_operations[ref] = attach_context(loaded[ref], factory, self.ledger.fact_snapshot(facts, ref))
            attached = attached_operations[ref]
            if attached is loaded[ref]:
                result.append(task)
                continue
            execution = task['execution']
            reports = [dict(report, write_context=row.write_context) for report, row in zip(execution['reports'], attached.reports)]
            # 旧计划上的任务保留 _task 写明的“不能新增报工”；已有报工仍可补录、更正、作废。
            context = attached.write_context if execution['current_task_ref'] == task['task_ref'] else execution['write_context']
            result.append(dict(task, execution=dict(execution, reports=reports, write_context=context)))
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
