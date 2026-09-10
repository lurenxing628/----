(function () {
  'use strict';
  const fields = ['id', 'batch', 'op', 'name', 'target', 'machine', 'person', 'planStart', 'planEnd'];
  const source = 'core.services.scheduler.gantt_critical_chain.compute_critical_chain_from_rows';
  const unavailable = reason => ({ available: false, reason, catalog: [], defaultChain: null });

  function resolveCurrent(model, context) {
    const data = window.APSFieldReports.currentChainData;
    if (!data) return unavailable('当前样例关键链数据未加载');
    if (data.schemaVersion !== 1 || data.kind !== 'computed-example' || data.source !== source ||
        !data.plan || !Array.isArray(data.tasks) || !Array.isArray(data.results)) {
      return unavailable('当前样例关键链数据无效');
    }
    if (!model || !Array.isArray(model.tasks) || typeof model.ms !== 'function' || !context ||
        ['version', 'generated', 'range'].some(key => context[key] !== data.plan[key])) {
      return unavailable('关键链结果与当前计划版本不一致');
    }
    if (model.tasks.some(task => !task || typeof task.id !== 'string' || !task.id ||
        !Number.isFinite(model.ms(task.planStart)) || !(model.ms(task.planEnd) > model.ms(task.planStart)))) {
      return unavailable('当前计划工序数据无效');
    }
    const tasks = new Map(model.tasks.map(task => [task.id, task]));
    if (!tasks.size || tasks.size !== model.tasks.length || data.tasks.length !== tasks.size ||
        new Set(data.tasks.map(task => task && task.id)).size !== tasks.size || data.tasks.some(saved => {
          const task = saved && tasks.get(saved.id);
          return !task || fields.some(key => task[key] !== saved[key]);
        })) return unavailable('关键链结果与当前计划内容不一致');

    // This snapshot covers independent sample operations only. A changed plan needs regenerated results.
    if (['batch', 'machine', 'person'].some(key => new Set(data.tasks.map(task => task[key])).size !== tasks.size)) {
      return unavailable('当前样例计划关系已变化，关键链需要重新计算');
    }
    const validResult = (result, id) => {
      const task = tasks.get(id);
      return task && result && result.available === true && result.dropped_count === 0 &&
        result.critical_chain_partial === false && Array.isArray(result.ids) && result.ids.length === 1 && result.ids[0] === id &&
        Array.isArray(result.edges) && result.edges.length === 0 && result.edge_count === 0 &&
        result.edge_type_stats && ['process', 'machine', 'operator', 'unknown'].every(type => result.edge_type_stats[type] === 0) &&
        result.reason === '' && result.reason_code === '' &&
        typeof result.makespan_end === 'string' &&
        Date.parse(result.makespan_end.replace(' ', 'T') + 'Z') === model.ms(task.planEnd);
    };
    if (data.results.length !== tasks.size || new Set(data.results.map(item => item && item.taskId)).size !== tasks.size ||
        data.results.some(item => !item || !validResult(item.criticalChain, item.taskId))) {
      return unavailable('当前样例关键链结果不完整');
    }
    const terminal = model.tasks.reduce((last, task) => !last || model.ms(task.planEnd) > model.ms(last.planEnd) ||
      (task.planEnd === last.planEnd && task.id > last.id) ? task : last, null);
    if (!validResult(data.globalResult, terminal.id)) return unavailable('当前样例整版关键链结果无效');

    const catalog = data.results.map(item => {
      const task = tasks.get(item.taskId);
      return { id: 'current-v' + context.version + '-' + task.id, kind: 'computed-example', scope: 'current-example',
        planVersion: context.version, taskIds: item.criticalChain.ids.slice(), edges: [],
        durationMinutes: (model.ms(task.planEnd) - model.ms(task.planStart)) / 60000 };
    });
    return { available: true, reason: '', catalog, defaultChain: catalog.find(chain => chain.taskIds[0] === terminal.id) };
  }

  window.APSFieldGanttChains.resolveCurrent = resolveCurrent;
})();
