(function () {
  'use strict';
  const C = window.FieldContract;
  function localNow(now) {
    const pad = value => String(value).padStart(2, '0');
    return now.getFullYear() + '-' + pad(now.getMonth() + 1) + '-' + pad(now.getDate()) + 'T' + pad(now.getHours()) + ':' + pad(now.getMinutes()) + ':' + pad(now.getSeconds());
  }
  function previous(task) {
    return task.execution.reports.filter(record => C.report(record)
      && record.recorded_against_task_ref === task.task_ref && record.operation_ref === task.operation_ref
      && C.validTime(record.actual_end) && (record.actual_start === null || C.validTime(record.actual_start) && record.actual_start <= record.actual_end))
      .slice().sort((a, b) => b.actual_end.localeCompare(a.actual_end) || b.report_no.localeCompare(a.report_no))[0] || null;
  }
  function initialize({ task, record, legacy, action, retained, now = new Date() }) {
    if (retained) return { draft: { ...retained.draft }, initialDraft: { ...retained.initialDraft }, suggestions: { ...retained.suggestions } };
    const draft = C.draft(record), suggestions = {};
    if (legacy) {
      draft.actual_end = legacy.event_time.replace(' ', 'T');
      draft.completed_quantity = legacy.quantity_done === null ? '' : String(legacy.quantity_done);
    } else if (action === 'create' && !record) {
      const last = previous(task), current = localNow(now);
      draft.actual_start = last && last.actual_end <= current ? last.actual_end : current;
      draft.actual_end = current;
      suggestions.actual_start = last && last.actual_end <= current ? '同任务上一条实际完工' : '本机当前时间';
      suggestions.actual_end = '本机当前时间';
    }
    return { draft, initialDraft: { ...draft }, suggestions };
  }
  function copyPrevious(draft, task) {
    const last = previous(task);
    if (!last) return { ...draft };
    return { ...C.draft(last), reason: draft.reason, declared_operator: draft.declared_operator };
  }
  function continuation(previousContext, task, identity) {
    if (task.task_ref !== identity.taskRef || task.operation_ref !== identity.operationRef) return '原任务或工序已变化，未打开新的报工草稿。';
    if (task.execution.execution_state === 'complete') return '工序已完工；已重读结果，请按需要补齐或更正原记录。';
    const context = task.execution.write_context, blocked = C.blocked(context, 'create');
    if (blocked) return blocked;
    if (!previousContext || context.write_token === previousContext.write_token) return '尚未取得新的报工写入上下文，未打开新的草稿。请重读后再新增。';
    return '';
  }
  window.FieldDraftModel = { previous, initialize, copyPrevious, continuation };
})();
