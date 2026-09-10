(function () {
  'use strict';
  // Load after both example scripts. This is a preset catalog, not a critical-chain algorithm.
  const example = window.APSFieldGanttExample;
  const density = window.APSFieldGanttDensityExample;
  if (!example || !density) {
    throw new Error('field-gantt-chains.js requires both field-gantt example scripts loaded first');
  }
  const durationLabel = '预设链·累计计划时长';
  // These are declared fixture routes, never dependencies inferred from sorted task IDs.
  const routes = [
    {
      id: 'preset-batch-a', taskIds: ['demo-a-10', 'demo-a-20', 'demo-a-30', 'demo-a-40'],
      edges: [
        { from: 'demo-a-10', to: 'demo-a-20', type: 'process', reason: 'DEMO-01 预设路线：下料完成后交给粗车。' },
        { from: 'demo-a-20', to: 'demo-a-30', type: 'process', reason: 'DEMO-01 预设路线：粗车完成后接续精加工。' },
        { from: 'demo-a-30', to: 'demo-a-40', type: 'process', reason: 'DEMO-01 预设路线：精加工完成后交给终检。' }
      ]
    },
    {
      id: 'preset-batch-b', taskIds: ['demo-b-10', 'demo-b-20', 'demo-b-30', 'demo-b-40'],
      edges: [
        { from: 'demo-b-10', to: 'demo-b-20', type: 'process', reason: 'DEMO-02 预设路线：下料完成后交给粗车。' },
        { from: 'demo-b-20', to: 'demo-b-30', type: 'process', reason: 'DEMO-02 预设路线：粗车形成定位基准后接续钻孔。' },
        { from: 'demo-b-30', to: 'demo-b-40', type: 'process', reason: 'DEMO-02 预设路线：钻孔完成后交给终检。' }
      ]
    },
    {
      id: 'preset-batch-c', taskIds: ['demo-c-10', 'demo-c-20', 'demo-c-30', 'demo-c-40'],
      edges: [
        { from: 'demo-c-10', to: 'demo-c-20', type: 'process', reason: 'DEMO-03 预设路线：下料完成后交给粗铣。' },
        { from: 'demo-c-20', to: 'demo-c-30', type: 'process', reason: 'DEMO-03 预设路线：粗铣完成后接续钻孔。' },
        { from: 'demo-c-30', to: 'demo-c-40', type: 'process', reason: 'DEMO-03 预设路线：钻孔完成后终检核对孔位及尺寸。' }
      ]
    },
    {
      id: 'preset-batch-d', taskIds: ['demo-d-10', 'demo-d-20', 'demo-d-30', 'demo-d-40'],
      edges: [
        { from: 'demo-d-10', to: 'demo-d-20', type: 'process', reason: 'DEMO-04 预设路线：下料完成后交给精车。' },
        { from: 'demo-d-20', to: 'demo-d-30', type: 'process', reason: 'DEMO-04 预设路线：精车完成后接续钻孔。' },
        { from: 'demo-d-30', to: 'demo-d-40', type: 'process', reason: 'DEMO-04 预设路线：钻孔完成后交给终检。' }
      ]
    }
  ];
  if (example.criticalChain.kind !== 'preset-example') {
    throw new Error('Expected a preset-example legacy chain');
  }
  const templates = routes.concat([{ id: 'preset-resource-chain',
    taskIds: example.criticalChain.taskIds, edges: example.criticalChain.edges }]);

  function cellReason(edge, from, to) {
    const relation = from.batch + ' ' + from.op + ' 完成后接续 ' + to.batch + ' ' + to.op;
    if (edge.type === 'process') return '本单元预设批次路线：' + relation + '。';
    const resources = [];
    if (from.machine === to.machine) resources.push(from.machine);
    if (from.person === to.person) resources.push(from.person);
    return '本单元预设资源顺序：' + relation + '；共用计划资源 ' + resources.join('、') + '。';
  }

  function buildCatalog(model, prefix) {
    const byId = new Map(model.tasks.map(task => [task.id, task]));
    return templates.map(template => {
      const taskIds = template.taskIds.map(id => prefix + id);
      const durationMinutes = taskIds.reduce((total, id) => {
        const task = byId.get(id);
        if (!task) throw new Error('Missing preset task: ' + id);
        const minutes = (model.ms(task.planEnd) - model.ms(task.planStart)) / 60000;
        if (!Number.isFinite(minutes) || minutes <= 0) throw new Error('Invalid preset plan: ' + id);
        return total + minutes;
      }, 0);
      const edges = template.edges.map(edge => {
        const from = byId.get(prefix + edge.from), to = byId.get(prefix + edge.to);
        if (!from || !to || !taskIds.includes(from.id) || !taskIds.includes(to.id) ||
            !(model.ms(from.planEnd) <= model.ms(to.planStart))) {
          throw new Error('Invalid preset edge: ' + prefix + edge.from + ' -> ' + prefix + edge.to);
        }
        return { from: from.id, to: to.id, type: edge.type,
          reason: prefix ? cellReason(edge, from, to) : edge.reason };
      });
      return { id: prefix + template.id, kind: 'preset-example', taskIds, edges, durationMinutes, durationLabel };
    });
  }

  function longest(chains) {
    return chains.reduce((best, chain) => !best || chain.durationMinutes > best.durationMinutes ||
      (chain.durationMinutes === best.durationMinutes && chain.id < best.id) ? chain : best, null);
  }

  function usesResource(task, field, key) {
    return task[field] === key ||
      (Array.isArray(task.reports) && task.reports.some(report => report[field] === key)) ||
      Boolean(task.remainingPlan && task.remainingPlan[field] === key);
  }

  // Pure selection: return an existing catalog entry or null; only null target means global.
  function choose(catalog, model, target) {
    if (!Array.isArray(catalog) || !model || !Array.isArray(model.tasks)) return null;
    const byId = new Map(model.tasks.map(task => [task.id, task]));
    // Reject foreign example/version task identities instead of displaying unrelated chains.
    const candidates = catalog.filter(chain => chain && (chain.kind === 'preset-example' ||
      chain.kind === 'computed-example' && chain.scope === 'current-example' && Number.isInteger(chain.planVersion)) &&
      typeof chain.id === 'string' && chain.id.length > 0 &&
      Number.isFinite(chain.durationMinutes) && chain.durationMinutes >= 0 &&
      Array.isArray(chain.taskIds) && chain.taskIds.length > 0 && chain.taskIds.every(id => byId.has(id)));
    if (target === null) return longest(candidates);
    if (!target || typeof target.key !== 'string' || !target.key.length) return null;
    const related = predicate => candidates.filter(chain => chain.taskIds.some(id => predicate(byId.get(id))));
    if (target.kind === 'task') {
      const task = byId.get(target.key);
      if (!task) return null;
      const direct = candidates.filter(chain => chain.taskIds.includes(task.id));
      return longest(direct.length ? direct : related(member => member.batch === task.batch));
    }
    if (target.kind === 'batch') return longest(related(task => task.batch === target.key));
    if (target.kind === 'device') return longest(related(task => usesResource(task, 'machine', target.key)));
    if (target.kind === 'person') return longest(related(task => usesResource(task, 'person', target.key)));
    return null;
  }

  const complexCatalog = buildCatalog(example.model, '');
  const denseCatalog = [];
  for (let cell = 1; cell <= 10; cell++) {
    denseCatalog.push(...buildCatalog(density.model, 'U' + String(cell).padStart(2, '0') + '-'));
  }
  // Publish only after both catalogs succeed; never change models, tasks or legacy chains.
  example.criticalChains = complexCatalog;
  density.criticalChains = denseCatalog;
  window.APSFieldGanttChains = { choose, durationLabel };
})();
