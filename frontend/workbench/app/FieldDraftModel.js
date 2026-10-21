(function () {
  'use strict';
  const C = window.FieldContract;
  function localNow(now) {
    const pad = value => String(value).padStart(2, '0');
    return now.getFullYear() + '-' + pad(now.getMonth() + 1) + '-' + pad(now.getDate()) + 'T' + pad(now.getHours()) + ':' + pad(now.getMinutes()) + ':' + pad(now.getSeconds());
  }
  function previous(task) {
    return task.execution.reports.filter(record => record.recorded_against_task_ref === task.task_ref
      && C.validTime(record.actual_end) && (record.actual_start === null || C.validTime(record.actual_start) && record.actual_start <= record.actual_end))
      .sort((a, b) => b.actual_end.localeCompare(a.actual_end) || b.report_no.localeCompare(a.report_no))[0] || null;
  }
  function legacyTime(value) {
    // Match the preserved formats accepted by parse_operation_event_time.
    const stamp = value.trim().replace(/\//g, '-').replace(/T/g, ' ').replace(/：/g, ':');
    const match = /^(\d{4})-(\d{1,2})-(\d{1,2}| [1-9])(?:\s+(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?)?$/.exec(stamp);
    if (!match) return stamp;
    const [year, month, day, hour = '0', minute = '0', second = '0'] = match.slice(1);
    return year + '-' + month.padStart(2, '0') + '-' + day.trim().padStart(2, '0') + 'T'
      + hour.padStart(2, '0') + ':' + minute.padStart(2, '0') + ':' + second.padStart(2, '0');
  }
  function legacyResources(scope, gaps) {
    const scopeRefs = new Set(scope.map(fact => fact.legacy_fact_ref)), result = {};
    for (const key of ['actual_machine_ref', 'actual_operator_ref']) {
      const unresolved = gaps.some(gap => gap.code === 'legacy_resource_identity_unresolved'
        && scopeRefs.has(gap.legacy_fact_ref) && gap.fields.includes(key));
      const refs = [...new Set(scope.map(fact => fact[key]).filter(value => value != null))];
      result[key] = !unresolved && refs.length === 1 ? refs[0] : null;
    }
    return result;
  }
  function legacyValues(task, legacyFactRef) {
    if (!legacyFactRef) return null;
    const e = task.execution, finish = e.legacy_facts.find(fact => fact.legacy_fact_ref === legacyFactRef && fact.event_type === 'finish');
    if (!finish) return null;
    const scope = e.legacy_facts.filter(fact => fact.recorded_against_task_ref === finish.recorded_against_task_ref);
    const starts = [...new Set(scope.filter(fact => fact.event_type === 'start').map(fact => legacyTime(fact.event_time)).filter(Boolean))];
    const known = {}, end = legacyTime(finish.event_time);
    if (starts.length === 1) known.actual_start = starts[0];
    if (end) known.actual_end = end;
    if (finish.quantity_done !== null && finish.quantity_done !== undefined) known.completed_quantity = String(finish.quantity_done);
    const resources = legacyResources(scope, e.data_gaps);
    for (const key of ['actual_machine_ref', 'actual_operator_ref']) if (resources[key]) known[key] = resources[key];
    return known;
  }
  function initialize({ task, record, legacy, action, retained, knownLegacy, now = new Date() }) {
    if (retained) return { draft: { ...retained.draft }, initialDraft: { ...retained.initialDraft }, suggestions: { ...retained.suggestions } };
    const draft = C.draft(record), suggestions = {};
    if (legacy) {
      Object.assign(draft, knownLegacy === undefined ? legacyValues(task, legacy.legacy_fact_ref) : knownLegacy);
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
    if (task.execution.execution_state === 'complete') return '工序已完工；已刷新结果，请按需要补齐或更正原记录。';
    const context = task.execution.write_context, blocked = C.blocked(context, 'create');
    if (blocked) return blocked;
    if (!previousContext || context.write_token === previousContext.write_token) return '本页数据已过期，没有打开新的报工草稿。请点「刷新现场记录」后再新增。';
    return '';
  }
  window.FieldDraftModel = { previous, legacyTime, legacyResources, legacyValues, initialize, copyPrevious, continuation };
})();
