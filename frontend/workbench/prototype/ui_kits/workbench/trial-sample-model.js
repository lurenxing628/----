(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module && module.exports) module.exports = api;
  if (root) root.APSTrialSample = api;
})(typeof window === 'undefined' ? null : window, function () {
  'use strict';
  const HOUR = 3600000;
  const businessKinds = ['process', 'locked', 'calendar', 'precedence', 'resource-overlap', 'person-overlap'];
  const clone = value => JSON.parse(JSON.stringify(value));
  const record = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const batches = [
    { id: 'B202609-018', name: '回转壳体A', qty: 12, priority: '特急', due: '2026-09-08T14:00' },
    { id: 'B202609-024', name: '端盖C', qty: 6, priority: '急件', due: '2026-09-08T16:00' },
    { id: 'B202609-021', name: '回转壳体B', qty: 8, priority: '普通', due: '2026-09-09T11:00' },
    { id: 'B202609-029', name: '定位环', qty: 6, priority: '普通', due: '2026-09-08T12:00' }
  ];
  const resources = [
    { id: 'M-03', name: '加工中心 M-03', person: '张三', capacityHours: 20 },
    { id: 'M-08', name: '加工中心 M-08', person: '李四', capacityHours: 20 },
    { id: 'M-12', name: '检验台 M-12', person: '王五', capacityHours: 20 }
  ];
  const resourceById = id => resources.find(resource => resource.id === id);
  const plans = [
    { batch: batches[0].id, resource: 'M-03', locked: false,
      machining: ['2026-09-08T11:00', '2026-09-08T15:00'], inspection: ['2026-09-08T15:00', '2026-09-08T16:00'] },
    { batch: batches[1].id, resource: 'M-03', locked: false,
      machining: ['2026-09-08T15:00', '2026-09-08T18:00'], inspection: ['2026-09-09T08:00', '2026-09-09T09:00'] },
    { batch: batches[2].id, resource: 'M-03', locked: false,
      machining: ['2026-09-09T08:00', '2026-09-09T11:00'], inspection: ['2026-09-09T11:00', '2026-09-09T12:00'] },
    { batch: batches[3].id, resource: 'M-08', locked: true,
      machining: ['2026-09-08T08:00', '2026-09-08T10:00'], inspection: ['2026-09-08T10:00', '2026-09-08T11:00'] }
  ];
  const baseTasks = [];
  plans.forEach(plan => {
    ['加工', '检验'].forEach((op, index) => {
      const resource = index ? 'M-12' : plan.resource, times = index ? plan.inspection : plan.machining;
      baseTasks.push({ id: plan.batch + (index ? '-20' : '-10'), batch: plan.batch, op, resource,
        person: resourceById(resource).person, start: times[0], end: times[1], locked: plan.locked,
        predecessor: index ? plan.batch + '-10' : null });
    });
  });
  function presetTasks(changes) {
    return baseTasks.map(task => {
      const result = Object.assign({}, task, changes[task.id]);
      result.person = resourceById(result.resource).person;
      return result;
    });
  }
  const scenarios = [
    { id: 'base', name: '基准方案', summary: '保留当前预置工序安排，3 批延期，共 20 小时。',
      tradeoff: '未调整工序；换型 2 次为预置属性，不是计算结果。', recommended: false, changeovers: 2,
      tasks: presetTasks({}) },
    { id: 'balanced', name: '均衡方案', summary: '018 转至 M-08，024 提前；2 批各延期 1 小时。',
      tradeoff: '换设备 1 道；换型 3 次为预置代价，不是计算结果。', recommended: true, changeovers: 3,
      tasks: presetTasks({
        'B202609-018-10': { resource: 'M-08', start: '2026-09-08T10:00', end: '2026-09-08T14:00' },
        'B202609-018-20': { start: '2026-09-08T14:00', end: '2026-09-08T15:00' },
        'B202609-024-10': { start: '2026-09-08T11:00', end: '2026-09-08T14:00' },
        'B202609-024-20': { start: '2026-09-08T15:00', end: '2026-09-08T16:00' }
      }) },
    { id: 'delivery', name: '交付优先', summary: '018、024 提前，021 转至 M-08；4 批全部准时。',
      tradeoff: '换设备 1 道；换型 5 次为更高的预置代价，不是计算结果。', recommended: false, changeovers: 5,
      tasks: presetTasks({
        'B202609-018-10': { start: '2026-09-08T08:00', end: '2026-09-08T12:00' },
        'B202609-018-20': { start: '2026-09-08T12:00', end: '2026-09-08T13:00' },
        'B202609-024-10': { start: '2026-09-08T12:00', end: '2026-09-08T15:00' },
        'B202609-024-20': { start: '2026-09-08T15:00', end: '2026-09-08T16:00' },
        'B202609-021-10': { resource: 'M-08', start: '2026-09-08T10:00', end: '2026-09-08T13:00' },
        'B202609-021-20': { start: '2026-09-08T13:00', end: '2026-09-08T14:00' }
      }) }
  ];

  // Use UTC only as a wall-clock arithmetic container; never convert the local ISO values.
  function time(value) {
    if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value)) return null;
    const parsed = Date.parse(value + 'Z');
    return Number.isFinite(parsed) && new Date(parsed).toISOString().slice(0, 16) === value ? parsed : null;
  }
  function requireTime(value, label) {
    const parsed = time(value);
    if (parsed === null) throw new Error(label + '必须是有效的本地时间 YYYY-MM-DDTHH:mm');
    return parsed;
  }
  function inCalendar(task) {
    const day = task.start.slice(0, 10);
    return ['2026-09-08', '2026-09-09'].includes(day) && task.end.slice(0, 10) === day &&
      task.start.slice(11) >= '08:00' && task.end.slice(11) <= '18:00';
  }
  function checkTask(task, add) {
    const ids = typeof task.id === 'string' ? [task.id] : [];
    const base = baseTasks.find(item => item.id === task.id), resource = resourceById(task.resource);
    if (!base) add('identity', '未知工序 ID：' + String(task.id), ids);
    else if (task.batch !== base.batch || task.op !== base.op) add('identity', task.id + '的批次或工序名称与基准不一致', ids);
    if (!resource) add('resource', String(task.id) + '使用了未知设备：' + String(task.resource), ids);
    if (!resource || task.person !== resource.person) add('person', String(task.id) + '的人员必须与设备对应', ids);
    if ((task.op === '加工' && !['M-03', 'M-08'].includes(task.resource)) ||
        (task.op === '检验' && task.resource !== 'M-12')) add('process', String(task.id) + '工艺不匹配：仅 M-03/M-08 可加工，M-12 可检验', ids);
    if (typeof task.locked !== 'boolean') add('input', String(task.id) + '的 locked 必须是布尔值', ids);
    if ((task.predecessor !== null && (typeof task.predecessor !== 'string' || !task.predecessor)) ||
        (base && task.predecessor !== base.predecessor)) add('dependency', String(task.id) + '的前序关联必须保持本批加工后检验', ids);
    if (base && (base.locked || task.locked === true) && (!task.locked || task.resource !== base.resource ||
        task.start !== base.start || task.end !== base.end)) add('locked', task.id + '是固定工序，必须保持基准时段与设备，不能解冻', ids);
    const start = time(task.start), end = time(task.end);
    if (start === null || end === null || end <= start) {
      add('time', String(task.id) + '时段无效：使用 YYYY-MM-DDTHH:mm，结束必须晚于开始', ids);
      return { task, start: null, end: null };
    }
    if (!inCalendar(task)) add('calendar', task.id + '超出工作日历：仅 2026-09-08/09 每天 08:00-18:00，不可跨夜', ids);
    return { task, start, end };
  }
  function checkRelations(entries, add) {
    entries.forEach((entry, index) => {
      const task = entry.task, previous = entries.find(item => item.task.id === task.predecessor);
      if (typeof task.predecessor === 'string') {
        if (!previous || previous.task.batch !== task.batch) add('dependency', task.id + '的前序不存在或不属于本批次', [task.id, task.predecessor]);
        else if (entry.start !== null && previous.end !== null && previous.end > entry.start) {
          add('precedence', task.id + '开始早于前序 ' + previous.task.id + ' 完成', [previous.task.id, task.id]);
        }
      }
      entries.slice(index + 1).forEach(other => {
        if (entry.start === null || other.start === null || entry.start >= other.end || other.start >= entry.end) return;
        const ids = [task.id, other.task.id];
        if (resourceById(task.resource) && task.resource === other.task.resource) add('resource-overlap', task.resource + '设备时段重叠：' + ids.join('、'), ids);
        if (typeof task.person === 'string' && task.person && task.person === other.task.person) add('person-overlap', task.person + '人员时段重叠：' + ids.join('、'), ids);
      });
    });
  }
  function validate(tasks) {
    const issues = [], entries = [], seen = new Set();
    const add = (kind, message, taskIds) => issues.push({ kind, message, taskIds });
    if (!Array.isArray(tasks)) {
      add('input', 'tasks 必须是包含 8 道工序的数组', []);
      return issues;
    }
    for (let index = 0; index < tasks.length; index += 1) {
      const task = tasks[index];
      if (!record(task)) { add('input', '第 ' + (index + 1) + ' 道工序必须是对象', []); continue; }
      if (seen.has(task.id)) add('identity', '工序 ID 重复：' + String(task.id), typeof task.id === 'string' ? [task.id] : []);
      seen.add(task.id);
      entries.push(checkTask(task, add));
    }
    baseTasks.forEach(task => { if (!seen.has(task.id)) add('identity', '缺少工序：' + task.id, [task.id]); });
    checkRelations(entries, add);
    return issues;
  }
  function tasksOf(value, label) {
    const tasks = Array.isArray(value) ? value : record(value) ? value.tasks : null;
    if (!Array.isArray(tasks)) throw new Error(label + '必须是含 tasks 数组的方案对象或 tasks 数组');
    return tasks;
  }
  function assertIssues(issues, label) {
    if (issues.length) throw new Error(label + '无效：' + issues.map(issue => issue.message).join('；'));
  }
  function changed(task, baseline) {
    return task.resource !== baseline.resource || task.start !== baseline.start || task.end !== baseline.end;
  }
  // Preview totals describe raw task intervals, not a feasible schedule when issues exist.
  function inspect(scenarioOrTasks, baselineScenario = scenarios[0]) {
    const tasks = tasksOf(scenarioOrTasks, '方案'), baseline = tasksOf(baselineScenario, '基准方案');
    const issues = validate(tasks);
    assertIssues(issues.filter(issue => !businessKinds.includes(issue.kind)), '方案');
    assertIssues(validate(baseline), '基准方案');
    const baselineById = new Map(baseline.map(task => [task.id, task]));
    const rows = batches.map(batch => {
      const operations = tasks.filter(task => task.batch === batch.id);
      const finish = operations.reduce((latest, task) => task.end > latest ? task.end : latest, '');
      const baselineFinish = baseline.filter(task => task.batch === batch.id).reduce((latest, task) => task.end > latest ? task.end : latest, '');
      return { ...batch, baselineFinish, finish, lateHours: Math.max(0, (time(finish) - time(batch.due)) / HOUR),
        improvementHours: (time(baselineFinish) - time(finish)) / HOUR,
        changed: operations.some(task => changed(task, baselineById.get(task.id))),
        moved: operations.some(task => task.resource !== baselineById.get(task.id).resource) };
    });
    const loads = resources.map(resource => {
      const hours = tasks.filter(task => task.resource === resource.id).reduce((sum, task) => sum + (time(task.end) - time(task.start)) / HOUR, 0);
      return { ...resource, hours, percent: hours / resource.capacityHours * 100 };
    });
    const report = { lateCount: rows.filter(row => row.lateHours > 0).length,
      totalDelayHours: rows.reduce((sum, row) => sum + row.lateHours, 0),
      changedOperations: tasks.filter(task => changed(task, baselineById.get(task.id))).length,
      movedOperations: tasks.filter(task => task.resource !== baselineById.get(task.id).resource).length, rows, loads };
    return { report, issues };
  }
  function evaluate(scenarioOrTasks, baselineScenario = scenarios[0]) {
    const preview = inspect(scenarioOrTasks, baselineScenario);
    assertIssues(preview.issues, '方案');
    return preview.report;
  }
  function checkScenario(scenario, label) {
    if (!record(scenario) || !['id', 'name', 'summary', 'tradeoff'].every(key => typeof scenario[key] === 'string') ||
        typeof scenario.recommended !== 'boolean' || !((Number.isInteger(scenario.changeovers) && scenario.changeovers >= 0) ||
        (scenario.id === 'draft' && scenario.changeovers === null))) {
      throw new Error(label + '元信息无效：需要 id/name/summary/tradeoff 字符串、recommended 布尔值和非负整数 changeovers；仅 draft 的 changeovers 可为 null（未评估）');
    }
  }
  function adjust(scenario, taskId, patch) {
    checkScenario(scenario, '方案');
    const tasks = tasksOf(scenario, '方案');
    // Existing business conflicts must remain editable; malformed task data must not.
    assertIssues(validate(tasks).filter(issue => !businessKinds.includes(issue.kind)), '方案');
    const original = tasks.find(task => task.id === taskId);
    if (!original) throw new Error('未知工序 taskId：' + String(taskId));
    if (!record(patch) || Object.keys(patch).some(key => !['resource', 'start'].includes(key))) throw new Error('试调参数仅支持 resource 和 start');
    const resource = resourceById(patch.resource);
    if (!resource) throw new Error('未知设备 resource：' + String(patch.resource));
    const start = requireTime(patch.start, '开始时间 start');
    const end = new Date(start + time(original.end) - time(original.start)).toISOString().slice(0, 16);
    requireTime(end, '结束时间 end');
    const draft = clone(scenario), target = draft.tasks.find(task => task.id === taskId);
    Object.assign(target, { resource: resource.id, person: resource.person, start: patch.start, end });
    return Object.assign(draft, { id: 'draft', name: '手工试调' });
  }
  function formatTime(iso) {
    requireTime(iso, '时间');
    return iso.slice(5, 10) + ' ' + iso.slice(11);
  }
  function csv(scenario, baseline = scenarios[0]) {
    checkScenario(scenario, '方案');
    checkScenario(baseline, '基准方案');
    const result = evaluate(scenario, baseline);
    const header = ['方案(示例)', '方案摘要', '方案取舍', '基准方案', '换型次数(预置)',
      '批次', '产品', '数量', '优先级', '交期', '基准完工', '方案完工', '延期(h)', '完工提前(h)', '工序调整', '换设备'];
    const rows = result.rows.map(row => [scenario.name, scenario.summary, scenario.tradeoff, baseline.name,
      scenario.changeovers === null ? '未评估' : scenario.changeovers, row.id, row.name, row.qty, row.priority, row.due, row.baselineFinish, row.finish,
      row.lateHours, row.improvementHours, row.changed, row.moved]);
    const cell = value => '"' + String(value).replace(/"/g, '""') + '"';
    return '\uFEFF' + [header, ...rows].map(row => row.map(cell).join(',')).join('\r\n') + '\r\n';
  }
  function freeze(value) {
    Object.keys(value).forEach(key => { if (value[key] && typeof value[key] === 'object') freeze(value[key]); });
    return Object.freeze(value);
  }
  freeze(batches); freeze(resources); freeze(scenarios);
  function layoutIntervals(tasks) {
    const ends = [], tracks = {}, overlaps = [];
    const ordered = tasks.slice().sort((a, b) => a.start.localeCompare(b.start) || a.end.localeCompare(b.end) || a.id.localeCompare(b.id));
    ordered.forEach((task, index) => {
      let track = ends.findIndex(end => end <= task.start);
      if (track < 0) track = ends.length;
      ends[track] = task.end; tracks[task.id] = track;
      ordered.slice(0, index).forEach(other => {
        if (task.start >= other.end || other.start >= task.end || (task.resource !== other.resource && task.person !== other.person)) return;
        overlaps.push({ start: task.start > other.start ? task.start : other.start, end: task.end < other.end ? task.end : other.end, taskIds: [other.id, task.id] });
      });
    });
    return { tracks, count: Math.max(1, ends.length), overlaps };
  }
  return { scenarios, batches, resources, evaluate, inspect, validate, adjust, formatTime, csv, layoutIntervals };
});
