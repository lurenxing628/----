'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const root = path.resolve(__dirname, '../..'), host = { window: {}, Date, Map, Set, Number, JSON, Object, Array, Infinity, Math };
vm.createContext(host);
for (const name of ['WorkbenchFormat.js', 'PointContract.js', 'PointGanttModel.js', 'ActualGanttModel.js']) vm.runInContext(fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8'), host);
const M = host.window.ActualGanttModel, ref = n => n.toString(16).padStart(48, '0');
const r = (n, start, end, machine = ref(2)) => ({ report_ref: ref(n), report_no: 'report ' + n, actual_start: start, actual_end: end,
  actual_machine_ref: machine, actual_operator_ref: ref(3), completed_quantity: null, effective_processing_hours: null, remark: '' });
const reports = [r(11, '2026-03-08T01:00:00', '2026-03-08T03:00:00'), r(12, '2026-03-08T02:00:00', '2026-03-08T04:00:00'),
  r(13, '2026-03-08T04:00:00', '2026-03-08T04:00:01'), r(14, '2026-03-08T05:00:00', null), r(15, '2026-03-08T05:00:00', null, ref(4))];
const task = { task_ref: ref(1), operation_ref: ref(6), plan_ref: ref(7), batch_id: '中文批次', sequence: 1, process_label: '跨夜工序',
  piece_id: null, quantity: null, batch_quantity: null, quantity_basis: 'unknown', quantity_reason: 'plan_target_not_recorded',
  machine_ref: ref(2), operator_ref: ref(3), start: '2026-03-07T22:00:00', end: '2026-03-08T06:00:00' };
const item = { task, execution: { reports, execution_state: 'partial', known_completed_quantity: 0, target_quantity: 10, remaining_quantity: null,
  remaining_plan: null, confirmed_finish: null, legacy_facts: [], completion_basis: null } };
const data = { items: [item], resources: [{ ref: ref(2), label: '计划机', business_code: 'M1' }, { ref: ref(4), label: '改换设备', business_code: 'M2' },
  { ref: ref(3), label: '操作人', business_code: 'O1' }], axis_span: { start: task.start, end: task.end } };
const view = { mode: 'machine', query: '', late: 'all', onlySelected: false, selected: null, collapsed: {} };
const original = JSON.stringify(data);
assert.equal(M.instant('2026-03-08T03:00:00') - M.instant('2026-03-08T01:00:00'), 7200000, 'Factory wall clock does not lose DST hours');
const tracks = M.tracks(reports), pointReport = row => !row.actual_end || row.actual_start === row.actual_end;
assert.equal(tracks.filter(lane => !pointReport(lane[0])).length, 2, 'Overlapping normal reports still require two tracks');
assert.equal(tracks.filter(lane => pointReport(lane[0])).length, reports.filter(pointReport).length, 'Report points own separate hit tracks');
assert.equal(tracks.reduce((n, t) => n + t.length, 0), 5);
for (const lane of tracks) {
  if (lane.some(pointReport)) assert.equal(lane.length, 1, 'Point targets never share report tracks');
  for (let i = 1; i < lane.length; i++) assert(M.instant(lane[i - 1].actual_end) <= M.instant(lane[i].actual_start), 'Normal report tracks remain nonoverlapping');
}
const model = M.layout(data, view, '2026-03-08T06:00:00'); assert.equal(model.groups.length, 2);
assert.ok(M.describe(item, model.labels).some(line => line.includes('计划应做：未知 件 · 批次：未知 件')));
assert.ok(M.describe(item, model.labels).some(line => line.includes('旧计划未记录原数量证据')));
const axisStart = M.instant(data.axis_span.start), axisEnd = M.instant(data.axis_span.end);
const pad = Math.max(60000, (axisEnd - axisStart) * .04);
assert.equal(axisEnd - axisStart, 8 * 3600000, 'Original business span remains eight hours');
assert.equal(model.start, axisStart - pad, 'Point display axis has left marker clearance');
assert.equal(model.end, axisEnd + pad, 'Point display axis has right marker clearance');
assert.equal(model.reportLocations.get(ref(15)).group.id, ref(4));
assert.equal(model.locations.get(ref(1)).baseline, true);
const allMarks = model.rows.filter(row => row.item).flatMap(row => M.marks(row));
assert.equal(allMarks.filter(m => m.kind === 'plan').length, 1); assert.equal(allMarks.filter(m => m.kind === 'point').length, 2);
assert.equal(allMarks.filter(m => m.kind === 'remaining').length, 0);
assert.equal(allMarks.find(m => m.key === ref(13)).end - allMarks.find(m => m.key === ref(13)).start, 1000, 'Narrow duration is never padded');
assert.equal(allMarks.find(m => m.kind === 'plan').y, 74, 'Baseline is below actual report');
assert.equal(allMarks.find(m => m.kind === 'plan').start, axisStart, 'Axis padding never widens a normal plan mark');
assert.equal(allMarks.find(m => m.kind === 'plan').end, axisEnd);
for (const row of model.rows.filter(row => row.item)) {
  const marks = M.marks(row);
  for (const point of marks.filter(mark => mark.kind === 'point')) {
    assert.equal(point.start, point.end, 'Report point has no fabricated duration');
    for (const other of marks.filter(mark => mark !== point)) {
      assert(point.y + point.height <= other.y || other.y + other.height <= point.y, 'Fixed point hitbox does not cover baseline or reports');
    }
  }
}
assert.equal(M.filter(data, { ...view, query: '改换设备' }, '2026-03-08T06:00:00').length, 1);
assert.equal(M.filter(data, { ...view, late: 'unclosed' }, '2026-03-08T06:00:00').length, 1);
assert.equal(M.number(null), '未知'); assert.equal(M.number(0), '0.00');
assert.equal(M.visibleRows(model.rows, 100000, 100010).length, 0);
assert.equal(Object.prototype.hasOwnProperty.call(model, 'conflicts'), false, 'Visual report overlap is not plan conflict evidence');
const legacy = { ...item, execution: { ...item.execution, execution_state: 'complete', completion_basis: 'legacy_finish_event', confirmed_finish: task.end, reports: [], legacy_facts: [{}] } };
const legacyLayout = M.layout({ ...data, items: [legacy] }, view, '2026-03-08T06:00:00');
assert.equal(legacyLayout.start, axisStart, 'Without points the display axis is not padded');
assert.equal(legacyLayout.end, axisEnd);
assert.equal(legacyLayout.rows.filter(row => row.kind === 'remaining').length, 0);
assert.ok(M.describe(legacy, model.labels).some(line => line.includes('旧完工事件确认完成')));
assert.equal(JSON.stringify(data), original, 'Layout, marks and display padding never mutate source DTOs');
console.log(JSON.stringify({ point_tracks: tracks.filter(lane => pointReport(lane[0])).length,
  original_span_ms: axisEnd - axisStart, display_padding_ms: pad, dto_unchanged: true, timezone: process.env.TZ || 'host' }));
