(function () {
  'use strict';
  const DAY = 86400000, MINUTE = 60000, TOLERANCE = 10;
  const fields = ['source', 'dateFrom', 'dateTo', 'batch', 'resourceType', 'resource', 'search', 'focus'];
  const focuses = { all: '全部工序', due: '计划已到期工序', unclosed: '到期未确认完成', finishLate: '晚完工超过 ' + TOLERANCE + ' 分钟', incomplete: '未报或字段待补', resourceChanged: '实际资源变更' };
  const n = value => value == null ? '—' : String(Math.round(value * 10) / 10);
  const pct = value => value == null ? '—' : n(value) + '%';
  const rate = (a, b) => b ? a / b * 100 : null;
  const unique = values => [...new Set(values.filter(Boolean))].sort((a, b) => a.localeCompare(b, 'zh-CN', { numeric: true }));
  function day(value, label) {
    const parsed = typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value) ? Date.parse(value + 'T00:00:00Z') : NaN;
    if (!Number.isFinite(parsed) || new Date(parsed).toISOString().slice(0, 10) !== value) throw new Error(label + '日期无效');
    return parsed;
  }
  function defaults(sourceId = 'current', host = window) {
    const src = host.APSReportWorkbench.source(sourceId, host);
    const dates = src.model.tasks.flatMap(t => [t.planStart, t.planEnd]).filter(Boolean).map(value => value.slice(0, 10)).sort();
    const clockDate = new Date(src.model.state.clock).toISOString().slice(0, 10);
    return { source: sourceId, dateFrom: dates[0] || clockDate, dateTo: dates[dates.length - 1] || clockDate,
      batch: '', resourceType: 'all', resource: '', search: '', focus: 'all' };
  }
  function normalize(input, host) {
    const scope = defaults(input.source || 'current', host);
    fields.forEach(key => { if (input[key] !== undefined) scope[key] = input[key]; });
    fields.forEach(key => { if (typeof scope[key] !== 'string') throw new Error('筛选条件无效：' + key); });
    if (!Object.prototype.hasOwnProperty.call(focuses, scope.focus)) throw new Error('未知分析范围');
    if (!['all', 'machine', 'person'].includes(scope.resourceType)) throw new Error('未知资源类型');
    if (day(scope.dateFrom, '开始') > day(scope.dateTo, '结束')) throw new Error('开始日期不能晚于结束日期');
    if (scope.resourceType === 'all') scope.resource = '';
    return scope;
  }
  function augment(row, src) {
    const end = row.planEnd ? src.model.ms(row.planEnd) : null, done = row.status === 'done';
    const due = end !== null && end <= src.model.state.clock;
    const age = due && !done ? (src.model.state.clock - end) / MINUTE : null;
    const flags = row.flags.filter(flag => flag === 'finishLate' ? done && row.endDelta > TOLERANCE :
      flag === 'unclosedLate' ? age !== null && age > TOLERANCE : flag === 'startLate' ? row.startDelta > TOLERANCE : true);
    return { ...row, flags, due, confirmedDue: due && done, unclosed: due && !done,
      lateOpen: age !== null && age > TOLERANCE, ageMinutes: age,
      finishLate: done && row.endDelta !== null && row.endDelta > TOLERANCE,
      onTime: done && row.endDelta !== null && row.endDelta <= TOLERANCE,
      missing: row.integrity !== 'complete', resourceChanged: row.flags.includes('resourceChanged') };
  }
  function matches(row, scope) {
    if (scope.batch && row.batch !== scope.batch) return false;
    if (scope.search.trim() && !row.searchText.includes(scope.search.trim().toLowerCase())) return false;
    if (scope.resourceType !== 'all' && scope.resource) {
      const key = scope.resourceType === 'machine' ? 'machine' : 'person';
      if (![row[key], ...row.summary.reports.map(r => r[key])].some(value => (value || '__unassigned__') === scope.resource)) return false;
    }
    return true;
  }
  function focusRows(rows, focus) {
    return rows.filter(row => focus === 'all' || (focus === 'due' && row.due) || (focus === 'unclosed' && row.unclosed) ||
      (focus === 'finishLate' && row.finishLate) || (focus === 'incomplete' && row.missing) || (focus === 'resourceChanged' && row.resourceChanged));
  }
  function summary(rows) {
    const records = rows.flatMap(row => row.summary.reports), known = records.filter(r => r.hours !== null);
    const finish = rows.filter(r => r.status === 'done' && r.endDelta !== null).map(r => r.endDelta).sort((a, b) => a - b);
    const due = rows.filter(r => r.due).length, confirmedDue = rows.filter(r => r.confirmedDue).length;
    const dueOnTime = rows.filter(r => r.due && r.onTime).length, completed = rows.filter(r => r.status === 'done').length;
    const middle = Math.floor(finish.length / 2), onTime = rows.filter(r => r.onTime).length;
    return { operations: rows.length, batches: new Set(rows.map(r => r.batch)).size, due, confirmedDue,
      unclosedDue: due - confirmedDue, lateOpen: rows.filter(r => r.lateOpen).length,
      fulfilledRate: rate(confirmedDue, due), dueOnTime, ontimeRate: rate(dueOnTime, due), completed,
      completedOnTime: onTime, completedOnTimeRate: rate(onTime, finish.length), finishSample: finish.length,
      medianFinish: !finish.length ? null : finish.length % 2 ? finish[middle] : (finish[middle - 1] + finish[middle]) / 2,
      p90Finish: finish.length ? finish[Math.ceil(finish.length * .9) - 1] : null,
      knownHours: known.length ? known.reduce((sum, r) => sum + r.hours, 0) : null,
      unknownHourRecords: records.length - known.length, records: records.length,
      unreported: rows.filter(r => r.integrity === 'unreported').length,
      incompleteOperations: rows.filter(r => r.integrity === 'incomplete').length,
      missingRecords: rows.reduce((sum, r) => sum + r.missingRecords, 0), changedResources: rows.filter(r => r.resourceChanged).length };
  }
  function distribution(values) {
    const bins = [
      ['early', '提前超过 ' + TOLERANCE + ' 分钟', 'success', v => v < -10], ['within', '提前或延后不超过 ' + TOLERANCE + ' 分钟', 'notice', v => v >= -10 && v <= 10],
      ['late30', '延后超过 ' + TOLERANCE + ' 至 30 分钟', 'warning', v => v > 10 && v <= 30],
      ['late120', '延后 30-120 分钟', 'danger', v => v > 30 && v <= 120], ['lateMore', '延后 >120 分钟', 'danger', v => v > 120]
    ];
    return bins.map(([id, label, tone, predicate]) => ({ id, label, tone, count: values.filter(predicate).length }));
  }
  function aging(rows) {
    const ages = rows.filter(r => r.unclosed).map(r => r.ageMinutes);
    return [['within', '不超过 ' + TOLERANCE + ' 分钟', 'notice', 0, 10], ['a30', '超过 ' + TOLERANCE + ' 至 30 分钟', 'warning', 10, 30],
      ['a120', '30-120 分钟', 'warning', 30, 120], ['aday', '2-24 小时', 'danger', 120, 1440],
      ['along', '超过 24 小时', 'danger', 1440, Infinity]].map(([id, label, tone, low, high], i) =>
      ({ id, label, tone, count: ages.filter(value => (i === 0 ? value >= low : value > low) && value <= high).length }));
  }
  function trend(rows, src, scope) {
    if (!rows.length) return [];
    const clock = src.model.state.clock, start = day(scope.dateFrom, '开始'), end = Math.max(day(scope.dateTo, '结束') + DAY, clock);
    const span = end - start, step = span <= 4 * DAY ? DAY / 4 : Math.ceil(span / (90 * DAY)) * DAY;
    const times = [start, end];
    for (let t = start + step; t < end; t += step) times.push(t);
    if (clock >= start && clock <= end) times.push(clock);
    return [...new Set(times)].sort((a, b) => a - b).map(time => ({
      time, label: new Date(time).toISOString().slice(5, 16).replace('T', ' '),
      planned: rows.filter(r => src.model.ms(r.planEnd) <= time).length,
      actual: time > clock ? null : rows.filter(r => r.actualEnd && src.model.ms(r.actualEnd) <= time).length,
      unclosed: time > clock ? null : rows.filter(r => src.model.ms(r.planEnd) <= time && (!r.actualEnd || src.model.ms(r.actualEnd) > time)).length
    }));
  }
  function resources(rows, api, kind) {
    const key = kind === 'machines' ? 'machine' : 'person';
    return api.reportRows(rows, kind).map(group => {
      const raw = group.id.slice(key.length + 1), operations = rows.filter(row => row.summary.reports.some(r => (r[key] || '') === raw));
      return { ...group, resourceKey: raw || '__unassigned__', changedOperations: operations.filter(r => r.resourceChanged).length,
        openOperations: operations.filter(r => r.status !== 'done').length };
    });
  }
  function insights(rows, s, groups) {
    if (!rows.length) return [];
    const result = [];
    if (s.unclosedDue) result.push({ id: 'unclosed', title: s.unclosedDue + ' 道工序已到期，未确认完成',
      detail: '计划完成时间已到 ' + s.due + ' 道，已确认完成 ' + s.confirmedDue + ' 道；' + s.lateOpen + ' 道距计划完成时间已超过 ' + TOLERANCE + ' 分钟。未确认完成不等于未生产。', tone: 'warning', focus: 'unclosed', topic: 'delivery' });
    const late = rows.filter(r => r.finishLate);
    if (late.length) result.push({ id: 'finishLate', title: late.length + ' 道工序晚完工超过 ' + TOLERANCE + ' 分钟',
      detail: '最大延后 ' + n(Math.max(...late.map(r => r.endDelta))) + ' 分钟；已完工样本共 ' + s.finishSample + ' 道。', tone: 'danger', focus: 'finishLate', topic: 'delivery' });
    if (s.unreported || s.incompleteOperations) result.push({ id: 'incomplete', title: (s.unreported + s.incompleteOperations) + ' 道工序需要核对记录',
      detail: s.unreported + ' 道未报工，' + s.incompleteOperations + ' 道字段待补；不能据此认定现场未生产。', tone: 'warning', focus: 'incomplete', topic: 'quality' });
    if (s.changedResources) result.push({ id: 'resourceChanged', title: s.changedResources + ' 道工序实际资源与计划不同',
      detail: '存在换机或换人记录；这是关联线索，不是责任或效率结论。', tone: 'notice', focus: 'resourceChanged', topic: 'machines' });
    const top = groups.filter(g => g.hours !== null && g.hours > 0).sort((a, b) => b.hours - a.hours)[0];
    if (top && s.knownHours > 0) result.push({ id: 'concentration', title: top.resource + ' 占已知工时 ' + pct(top.hours / s.knownHours * 100),
      detail: n(top.hours) + ' / ' + n(s.knownHours) + ' h；另有 ' + s.unknownHourRecords + ' 条工时未知，不代表利用率。', tone: 'notice', focus: 'all', topic: 'machines', resourceType: 'machine', resource: top.resourceKey });
    if (!s.unclosedDue && s.due) result.unshift({ id: 'confirmed', title: '当前计划已到期工序均已确认完成',
      detail: s.confirmedDue + ' / ' + s.due + ' 道已确认，其中 ' + s.dueOnTime + ' 道提前完成或延后不超过 ' + TOLERANCE + ' 分钟。', tone: 'success', focus: 'due', topic: 'delivery' });
    return result;
  }
  function build(input = {}, host = window) {
    const api = host.APSReportWorkbench, scope = normalize(input, host), source = api.source(scope.source, host);
    const sourceRows = api.snapshot(source).map(r => augment(r, source));
    const candidates = sourceRows.filter(r => matches(r, scope)), low = day(scope.dateFrom, '开始'), high = day(scope.dateTo, '结束') + DAY;
    const missingDate = candidates.filter(r => !r.planEnd).length;
    const cohortRows = candidates.filter(r => r.planEnd && source.model.ms(r.planEnd) >= low && source.model.ms(r.planEnd) < high);
    const rows = focusRows(cohortRows, scope.focus), s = summary(rows), groups = { machines: resources(rows, api, 'machines'), people: resources(rows, api, 'people') };
    const list = key => unique(sourceRows.flatMap(r => [r[key], ...r.summary.reports.map(record => record[key] || '__unassigned__')]));
    const warnings = missingDate ? [missingDate + ' 道关联工序缺少计划完工日期，不能归入所选日期范围，未计入分母。'] : [];
    const limitations = [
      '日期按计划完工日期选工序，图表、指标与导出使用同一范围；资源匹配计划或实际关联工序，包含其全部报工。',
      '实际曲线按当前记录发生时间回算，不代表当时保存的历史快照；数据截至时间之后的实际值未知。',
      '晚完工指延后超过 ' + TOLERANCE + ' 分钟；提前完成或延后不超过 ' + TOLERANCE + ' 分钟计为按时。偏差分布的中间档仅含提前或延后不超过 ' + TOLERANCE + ' 分钟。P90采用最近秩，分母为0及无有效样本时显示“—”。',
      '计划完成时间已到的工序计入到期分母；完成率统计已确认完成，按时完成率还要求提前完成或延后不超过 ' + TOLERANCE + ' 分钟。未确认完成不等于未生产；工序完成情况不等于批次交付，已报工时不是利用率。未接入完整交期、产能日历与停机异常事件，不能作原因归责。'
    ];
    return { scope, source, sourceRows, cohortRows, rows, choices: { batches: unique(sourceRows.map(r => r.batch)), machines: list('machine'), people: list('person') },
      asOfLabel: new Date(source.model.state.clock).toISOString().slice(0, 16).replace('T', ' '),
      rangeLabel: scope.dateFrom + ' 至 ' + scope.dateTo + ' · 按计划完工日期 · ' + focuses[scope.focus], toleranceMinutes: TOLERANCE,
      summary: s, trend: trend(rows, source, scope), distributions: { finish: distribution(rows.filter(r => r.status === 'done' && r.endDelta !== null).map(r => r.endDelta)),
        start: distribution(rows.filter(r => r.startDelta !== null).map(r => r.startDelta)) },
      aging: aging(rows), resources: groups, insights: insights(rows, s, groups.machines), limitations, warnings };
  }
  function linkScope(analysis, patch = {}) {
    const result = {};
    fields.forEach(key => { result[key] = Object.prototype.hasOwnProperty.call(patch, key) ? patch[key] : analysis.scope[key]; });
    return result;
  }
  function tableCSV(analysis, kind, rows, host = window) {
    const api = host.APSReportWorkbench, expected = api.reportRows(analysis.rows, kind), ids = new Set(expected.map(r => r.id));
    if (rows.length !== expected.length || new Set(rows.map(r => r.id)).size !== rows.length || rows.some(r => !ids.has(r.id))) throw new Error('导出必须覆盖当前筛选全量，不能仅导出本页或其他范围');
    return api.csv(analysis.source, kind, rows, analysis.scope);
  }
  function summaryCSV(analysis, host = window) {
    if (!analysis.rows.length) throw new Error('当前筛选没有可导出的分析数据');
    const labels = { operations: '工序数', due: '计划已到期工序', confirmedDue: '到期已确认完成', unclosedDue: '到期未确认完成', lateOpen: '已超时未确认完成',
      fulfilledRate: '到期工序完成率(%)', ontimeRate: '到期工序按时完成率(%)', finishSample: '已完工偏差样本量', medianFinish: '完工偏差中位数(分钟)',
      p90Finish: '完工偏差P90(分钟)', knownHours: '已报有效工时(h)', unknownHourRecords: '工时未知记录', unreported: '未报工工序', missingRecords: '字段待补记录' };
    const meta = [analysis.source.label, analysis.source.context.version, analysis.asOfLabel, ...fields.map(k => analysis.scope[k]), TOLERANCE];
    const header = ['来源名称', '来源版本', '数据截至', '数据源', '开始日期', '结束日期', '批次', '资源类型', '关联资源', '搜索', '分析范围', '完工允许延后(分钟)', '指标', '值'];
    const data = [header, ...Object.entries(labels).map(([key, label]) => [...meta, label, analysis.summary[key]])];
    return { count: data.length - 1, filename: '执行复盘汇总-' + analysis.scope.source + '-' + analysis.scope.dateFrom + '-' + analysis.scope.dateTo + '.csv',
      text: '\uFEFF' + data.map(r => r.map(host.APSReportWorkbench.csvCell).join(',')).join('\r\n') + '\r\n' };
  }
  window.APSExecutionAnalysis = { build, defaults, linkScope, tableCSV, summaryCSV, focuses, formatNumber: n, formatPercent: pct };
})();
