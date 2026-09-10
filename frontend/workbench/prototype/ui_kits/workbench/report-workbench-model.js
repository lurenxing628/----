(function () {
  'use strict';
  const SOURCE_DEFS = [
    { id: 'current', label: '当前报工', namespace: 'APSFieldReports', provenance: '当前内存 · 示例会话 · 未连接生产数据' },
    { id: 'complex', label: '复杂样例', namespace: 'APSFieldGanttExample', provenance: '独立复杂样例 · 非生产数据' },
    { id: 'dense', label: '密集样例', namespace: 'APSFieldGanttDensityExample', provenance: '独立密集样例 · 非生产数据' }
  ];
  const anomalies = { startLate: '晚开工', finishLate: '晚完工', unclosedLate: '已过计划完成时间，未确认完成', resourceChanged: '实际资源变更', quantityOver: '超报数量' };
  const capabilities = [
    { id: 'overdue', name: '超期批次', available: '后台支持', basis: '批次交期、完整计划工序及排程结果', gap: '未接入批次交期与完整工序清单', boundary: '单道工序完工不等于批次交付', evidence: 'report_engine.py · overdue_batches' },
    { id: 'utilization', name: '资源负荷 / 利用率', available: '后台支持', basis: '窗口内计划占用时长 / 日历可用产能', gap: '未接入工作日历、窗口产能与完整计划', boundary: '已报工时不是利用率；零产能时比率不可计算', evidence: 'report_engine.py · utilization；utilization.py · compute_utilization' },
    { id: 'downtime', name: '停机影响', available: '后台支持', basis: '设备停机记录与计划时段交集', gap: '未接入有效停机台账', boundary: '报工间空档不是已确认停机', evidence: 'report_engine.py · downtime_impact' },
    { id: 'official', name: '正式执行复盘 / Excel', available: '后台支持', basis: '正式采用计划与现场执行事件', gap: '未连接正式计划身份、执行事件及导出接口', boundary: '暂停时长、异常原因和严重程度不能从备注推断', evidence: 'execution_review.py · execution_review / export_execution_review_xlsx' }
  ];
  const kinds = { operations: '工序汇总', reports: '报工记录', machines: '设备已报工时', people: '人员已报工时' };
  const present = value => value !== null && value !== undefined && value !== '';
  const number = value => value == null ? '未报' : String(Math.round(value * 100) / 100);
  const time = value => value ? value.replace('T', ' ') : '未填写';
  const delta = value => value == null ? '不可比较' : (value > 0 ? '+' : '') + number(value) + ' 分钟';

  function sources(host = window) {
    return SOURCE_DEFS.map(def => ({ ...def, available: Boolean(host[def.namespace] && host[def.namespace].model) }));
  }
  function source(id, host = window) {
    const def = SOURCE_DEFS.find(item => item.id === id);
    if (!def) throw new Error('未知报表数据源：' + id);
    const ns = host[def.namespace];
    if (!ns || !ns.model) throw new Error(def.label + '数据尚未加载');
    const model = ns.model, context = id === 'current' ? ns.planContext : ns.context;
    if (!Array.isArray(model.tasks) || typeof model.summary !== 'function' || typeof model.ms !== 'function' || !context) {
      throw new Error(def.label + '数据结构不完整');
    }
    if (!model.labels || !model.state || !Number.isFinite(model.state.clock) || !Number.isFinite(new Date(model.state.clock).getTime())) throw new Error(def.label + '缺少状态标签或有效数据截至时间');
    return { ...def, model, context };
  }
  function dateMs(value, model, label) {
    if (!present(value)) return null;
    if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value)) throw new Error(label + '时间格式不正确');
    const result = model.ms(value);
    if (!Number.isFinite(result) || new Date(result).toISOString().slice(0, 16) !== value) throw new Error(label + '时间无效');
    return result;
  }
  function validateTask(task, model) {
    if (!task.id || !Array.isArray(task.reports)) throw new Error('工序身份或报工记录缺失');
    if (!Number.isInteger(task.target) || task.target < 0) throw new Error(task.id + '应做数量无效');
    const start = dateMs(task.planStart, model, task.id + '计划开工'), end = dateMs(task.planEnd, model, task.id + '计划完工');
    if (start != null && end != null && end < start) throw new Error(task.id + '计划时间倒置');
    task.reports.forEach(record => {
      if (!record.id) throw new Error(task.id + '报工身份缺失');
      ['qty', 'hours'].forEach(key => {
        if (record[key] !== null && (!Number.isFinite(record[key]) || record[key] < 0 || (key === 'qty' && !Number.isInteger(record[key])))) {
          throw new Error(record.id + (key === 'qty' ? '数量' : '工时') + '无效');
        }
      });
      const rs = dateMs(record.start, model, record.id + '实际开工'), re = dateMs(record.end, model, record.id + '本次结束');
      dateMs(record.recorded, model, record.id + '录入时间');
      if (rs != null && re != null && re <= rs) throw new Error(record.id + '实际时间倒置或零跨度');
      if (rs > model.state.clock || re > model.state.clock) throw new Error(record.id + '实际时间晚于数据截至时间');
      if (rs != null && re != null && record.hours !== null && record.hours > (re - rs) / 3600000 + 0.001) throw new Error(record.id + '有效工时超过作业跨度');
    });
    return { start, end };
  }
  function recordGaps(record) {
    return [['start', '实际开工'], ['end', '本次结束'], ['qty', '数量'], ['hours', '工时'], ['machine', '设备'], ['person', '人员']]
      .filter(([key]) => !present(record[key])).map(([, label]) => label);
  }
  function reviewRow(task, src) {
    const bounds = validateTask(task, src.model), s = src.model.summary(task);
    const actualStart = dateMs(s.start, src.model, task.id + '首段开工');
    const actualEnd = s.status === 'done' ? dateMs(s.end, src.model, task.id + '整道完工') : null;
    const startDelta = actualStart != null && bounds.start != null ? (actualStart - bounds.start) / 60000 : null;
    const endDelta = actualEnd != null && bounds.end != null ? (actualEnd - bounds.end) / 60000 : null;
    const flags = [];
    if (startDelta > 0) flags.push('startLate');
    if (endDelta > 0) flags.push('finishLate');
    if (s.status !== 'done' && bounds.end != null && src.model.state.clock > bounds.end) flags.push('unclosedLate');
    if (s.reports.some(r => (r.machine && task.machine && r.machine !== task.machine) || (r.person && task.person && r.person !== task.person))) flags.push('resourceChanged');
    if (s.qty > task.target) flags.push('quantityOver');
    const missingRecords = s.reports.filter(r => recordGaps(r).length).length;
    const planMissing = !present(task.planStart) || !present(task.planEnd) || !present(task.machine) || !present(task.person);
    const integrity = !s.reports.length ? 'unreported' : missingRecords || planMissing ? 'incomplete' : 'complete';
    return {
      id: task.id, sourceId: src.id, task, summary: s, batch: task.batch, name: task.name, op: task.op,
      status: s.status, statusLabel: src.model.labels[s.status], flags, integrity, missingRecords, planMissing,
      target: task.target, qty: s.reports.some(r => r.qty !== null) ? s.qty : null, remaining: s.remaining,
      hours: s.reports.some(r => r.hours !== null) ? s.hours : null, unknownHours: s.reports.filter(r => r.hours === null).length,
      planStart: task.planStart, planEnd: task.planEnd, actualStart: s.start, actualEnd: s.status === 'done' ? s.end : '', latestEnd: s.latest,
      startDelta, endDelta, planSpan: bounds.start != null && bounds.end != null ? (bounds.end - bounds.start) / 3600000 : null,
      actualSpan: actualStart != null && actualEnd != null ? (actualEnd - actualStart) / 3600000 : null,
      machine: task.machine, person: task.person,
      searchText: [task.id, task.batch, task.name, task.op, task.machine, task.person,
        ...s.reports.flatMap(r => [r.id, r.reportNo, r.machine, r.person, r.remark])].join(' ').toLowerCase()
    };
  }
  function snapshot(src) {
    const ids = new Set(), recordIds = new Set();
    return src.model.tasks.map(task => {
      const row = reviewRow(task, src);
      if (ids.has(row.id)) throw new Error('工序身份重复：' + row.id);
      ids.add(row.id);
      row.summary.reports.forEach(r => {
        if (recordIds.has(r.id)) throw new Error('报工身份重复：' + r.id);
        recordIds.add(r.id);
      });
      return row;
    });
  }
  function filterRows(rows, filters = {}) {
    requireSingleSource(rows);
    const query = (filters.search || '').trim().toLowerCase();
    return rows.filter(row => (!query || row.searchText.includes(query)) &&
      (!filters.status || filters.status === 'all' || row.status === filters.status) &&
      (!filters.integrity || filters.integrity === 'all' || row.integrity === filters.integrity) &&
      (!filters.anomaly || filters.anomaly === 'all' || (filters.anomaly === 'any' ? row.flags.length > 0 : filters.anomaly === 'none' ? !row.flags.length : row.flags.includes(filters.anomaly))));
  }
  function requireSingleSource(rows) {
    if (rows.some(row => !SOURCE_DEFS.some(def => def.id === row.sourceId))) throw new Error('报表行缺少数据来源');
    if (new Set(rows.map(row => row.sourceId)).size > 1) throw new Error('不能混合数据源生成报表');
  }
  function metrics(rows) {
    requireSingleSource(rows);
    const records = rows.flatMap(row => row.summary.reports), known = records.filter(r => r.hours !== null);
    return { operations: rows.length, batches: new Set(rows.map(r => r.batch)).size, done: rows.filter(r => r.status === 'done').length,
      anomalies: rows.filter(r => r.flags.length).length, missing: rows.filter(r => r.integrity !== 'complete').length,
      records: records.length, hours: known.length ? known.reduce((n, r) => n + r.hours, 0) : null,
      unknownHours: records.length - known.length };
  }
  function reportRows(rows, kind) {
    requireSingleSource(rows);
    if (kind === 'operations') return rows;
    const records = rows.flatMap(row => row.summary.reports.map(record => ({
      ...record, id: row.id + ':' + record.id, sourceId: row.sourceId, recordId: record.id, taskId: row.id,
      batch: row.batch, name: row.name, op: row.op, status: row.statusLabel, gaps: recordGaps(record), row
    })));
    if (kind === 'reports') return records;
    if (kind !== 'machines' && kind !== 'people') throw new Error('未知报表类型：' + kind);
    const key = kind === 'machines' ? 'machine' : 'person', groups = new Map();
    records.forEach(record => {
      const resource = record[key] || '', id = key + ':' + resource;
      if (!groups.has(id)) groups.set(id, { id, sourceId: record.sourceId, resource: resource || '未填写实际资源', records: 0, hours: null, unknownHours: 0, operations: new Set(), batches: new Set() });
      const group = groups.get(id);
      group.records++; group.operations.add(record.taskId); group.batches.add(record.batch);
      if (record.hours === null) group.unknownHours++;
      else group.hours = (group.hours === null ? 0 : group.hours) + record.hours;
    });
    return [...groups.values()].map(g => ({ ...g, operations: g.operations.size, batches: g.batches.size }));
  }
  function sortRows(rows, key = 'batch', direction = 'asc') {
    const sign = direction === 'desc' ? -1 : 1;
    return rows.slice().sort((a, b) => {
      const av = a[key], bv = b[key];
      if (!present(av) || !present(bv)) return present(av) ? -1 : present(bv) ? 1 : String(a.id).localeCompare(String(b.id));
      const compared = typeof av === 'number' && typeof bv === 'number' ? av - bv : String(av).localeCompare(String(bv), 'zh-Hans-CN', { numeric: true });
      return compared * sign || String(a.id).localeCompare(String(b.id), 'zh-Hans-CN', { numeric: true });
    });
  }
  function paginate(rows, page = 1, size = 20) {
    const pageSize = [10, 20, 50].includes(size) ? size : 20, pages = Math.max(1, Math.ceil(rows.length / pageSize));
    const current = Math.min(pages, Math.max(1, Number.isFinite(page) ? Math.floor(page) : 1));
    return { rows: rows.slice((current - 1) * pageSize, current * pageSize), page: current, pages, size: pageSize, total: rows.length };
  }
  function csvCell(value) {
    let text = value == null ? '' : String(value);
    // Quote escaping alone does not stop spreadsheet formulas, including after leading whitespace/control characters.
    if (typeof value === 'string' && (/^[\s\u0000-\u001f\u200b-\u200f\u202a-\u202e\u2060]*[=+\-@＝＋－＠]/.test(text) || /^[\t\r\n]/.test(text))) text = "'" + text;
    return '"' + text.replace(/"/g, '""') + '"';
  }
  function exportCells(kind, row) {
    if (kind === 'operations') return [row.id, row.batch, row.name, row.op, row.statusLabel, row.target, row.qty, row.remaining,
      row.planStart, row.planEnd, row.actualStart, row.actualEnd, row.latestEnd, row.startDelta, row.endDelta,
      row.planSpan, row.actualSpan, row.hours, row.machine, row.person, row.summary.reports.length, row.missingRecords,
      row.flags.map(f => anomalies[f]).join('；'), integrityLabel(row.integrity), row.planMissing ? '计划字段待补' : ''];
    if (kind === 'reports') return [row.taskId, row.recordId, row.reportNo, row.batch, row.name, row.op, row.qty,
      row.start, row.end, row.hours, row.machine, row.person, row.recorded, row.revision, row.gaps.join('、'), row.remark];
    return [row.resource, row.operations, row.batches, row.records, row.hours, row.unknownHours];
  }
  function csv(src, kind, rows, scope = null) {
    if (!rows.length) throw new Error('当前筛选没有可导出数据');
    if (!Object.prototype.hasOwnProperty.call(kinds, kind)) throw new Error('未知报表类型：' + kind);
    requireSingleSource(rows);
    if (rows.some(row => row.sourceId !== src.id)) throw new Error('导出行与所选数据源不匹配');
    const headers = kind === 'operations' ? ['工序ID', '批次', '名称', '工序', '工序状态', '应做数量', '已报数量', '待报数量',
      '计划开工', '计划完工', '首段实际开工', '整道实际完工', '最近作业结束', '开工偏差(分钟)', '整道完工偏差(分钟)',
      '计划日历跨度(h)', '整道实际跨度(h)', '已报有效工时(h)', '计划设备', '计划人员', '报工条数', '待补记录数', '偏差关注', '完整性', '计划缺口'] :
      kind === 'reports' ? ['工序ID', '记录ID', '报工编号', '批次', '名称', '工序', '本次数量', '实际开工', '本次结束', '本次有效工时(h)', '实际设备', '实际人员', '录入或修改时间', '修订次数', '待补字段', '备注'] :
        ['实际资源', '工序数', '涉及批次数', '报工条数', '已报有效工时(h)', '未报工时记录数'];
    if (scope && scope.source !== src.id) throw new Error('导出范围与数据来源不一致');
    const scopeFields = ['dateFrom', 'dateTo', 'batch', 'resourceType', 'resource', 'search', 'focus'];
    const scopeHeaders = scope ? ['范围开始日期', '范围结束日期', '范围批次', '范围资源类型', '范围关联资源', '范围搜索', '范围焦点', '完工允许延后(分钟)'] : [];
    const metadata = [src.label, src.provenance, src.context.version, new Date(src.model.state.clock).toISOString().slice(0, 16), kinds[kind],
      ...(scope ? [...scopeFields.map(key => scope[key]), 10] : [])];
    const data = [['数据源', '数据性质', '来源版本', '数据截至(墙上时间)', '报表', ...scopeHeaders, ...headers], ...rows.map(row => [...metadata, ...exportCells(kind, row)])];
    return { text: '\uFEFF' + data.map(line => line.map(csvCell).join(',')).join('\r\n') + '\r\n',
      count: rows.length, filename: kinds[kind] + '-' + src.label + '-' + new Date(src.model.state.clock).toISOString().slice(0, 10) + '.csv' };
  }
  function download(payload, host = window) {
    if (!payload.count) throw new Error('当前筛选没有可导出数据');
    if (!host.URL || typeof host.URL.createObjectURL !== 'function') throw new Error('当前环境不支持文件下载');
    const blob = new host.Blob([payload.text], { type: 'text/csv;charset=utf-8;' }), url = host.URL.createObjectURL(blob);
    const link = host.document.createElement('a');
    try { link.href = url; link.download = payload.filename; host.document.body.appendChild(link); link.click(); }
    finally { link.remove(); host.setTimeout(() => host.URL.revokeObjectURL(url), 1000); }
  }
  function integrityLabel(value) { return { unreported: '未报工', incomplete: '字段待补', complete: '字段齐全' }[value]; }
  window.APSReportWorkbench = { sources, source, snapshot, filterRows, metrics, reportRows, sortRows, paginate, csv, csvCell, download,
    anomalies, capabilities, kinds, number, time, delta, recordGaps, integrityLabel };
})();
