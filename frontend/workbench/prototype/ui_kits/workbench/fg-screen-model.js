(function () {
  'use strict';
  const fields = ['source', 'dateFrom', 'dateTo', 'batch', 'resourceType', 'resource', 'search', 'focus'];
  const sessions = new Map();
  let lastSession = null;
  const lateLabels = { all: '全部工序', finishLate: '已完晚', unclosed: '到期未确认完成', forecastLate: '剩余安排预计晚' };
  function contextKey(context = {}) {
    return JSON.stringify([context.scope ? fields.map(key => context.scope[key]) : [context.source, context.search],
      context.taskId, context.returnTo]);
  }
  function initial(context = {}) {
    if (!Object.keys(context).length && lastSession) return lastSession;
    const saved = sessions.get(contextKey(context));
    if (saved) return saved;
    const scope = context.scope ? { ...context.scope } : null;
    return { source: scope && scope.source || context.source || 'current', scope,
      search: scope ? scope.search || '' : context.search || '', selectedTaskId: context.taskId || null,
      view: scope && scope.resourceType === 'person' ? 'person' : 'device', lateFilter: 'all',
      collapsed: {}, onlySelected: false, showDetails: false, showChain: false, showLinks: true, viewport: null,
      returnTo: context.returnTo || null };
  }
  function save(context, state) { sessions.set(contextKey(context), state); lastSession = state; }
  function deadlines({ t, s }, model) {
    const planEnd = t.planEnd ? model.ms(t.planEnd) : NaN;
    const actualEnd = s.status === 'done' && s.end ? model.ms(s.end) : NaN;
    const remainingEnd = s.remaining > 0 && t.remainingPlan && t.remainingPlan.end ? model.ms(t.remainingPlan.end) : NaN;
    const knownPlan = Number.isFinite(planEnd);
    return { finishLate: knownPlan && Number.isFinite(actualEnd) && actualEnd - planEnd > 600000,
      unclosed: knownPlan && Number.isFinite(model.state.clock) && s.status !== 'done' && planEnd <= model.state.clock,
      forecastLate: knownPlan && s.status !== 'done' && Number.isFinite(remainingEnd) && remainingEnd - planEnd > 600000 };
  }
  function rows(model, source, scope, search, host = window) {
    const all = model.tasks.map(t => ({ t, s: model.summary(t) }));
    if (scope) {
      if (!host.APSExecutionAnalysis) return { rows: [], error: '来源范围无法应用：执行分析模型尚未加载。' };
      try {
        const analysis = host.APSExecutionAnalysis.build({ ...scope, source, search }, host);
        const ids = new Set(analysis.rows.map(row => row.id));
        return { rows: all.filter(row => ids.has(row.t.id)), analysis, error: '' };
      } catch (error) {
        return { rows: [], error: '来源范围无法应用：' + error.message };
      }
    }
    const query = search.trim().toLowerCase();
    return { rows: all.filter(({ t }) => {
      const terms = [t.id, t.batch, t.name, t.op, t.machine, t.person,
        ...t.reports.flatMap(r => [r.machine, r.person, r.reportNo])];
      if (t.remainingPlan) terms.push(t.remainingPlan.machine, t.remainingPlan.person);
      return !query || terms.join(' ').toLowerCase().includes(query);
    }), error: '' };
  }
  function filterRows(rows, model, lateFilter, onlySelected, selectedTaskId) {
    return rows.filter(row => (lateFilter === 'all' || deadlines(row, model)[lateFilter]) &&
      (!onlySelected || row.t.id === selectedTaskId));
  }
  function groupKey(source, view, name) { return JSON.stringify([source, view, name]); }
  window.APSFieldGanttUI = { contextKey, initial, save, deadlines, rows, filterRows, groupKey, lateLabels };
})();
