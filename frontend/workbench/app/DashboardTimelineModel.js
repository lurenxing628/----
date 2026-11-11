import PlanGanttModel from './PlanGanttModel.js';
import WorkbenchFormat from './WorkbenchFormat.js';
import WorkbenchTerms from './WorkbenchTerms.js';

const G = PlanGanttModel;

function prepare(data) {
  const stopRows = new Map(data.downtimes.map(row => [row.downtime_ref, row]));
  data.overlaps.forEach(row => row.source.downtimes.forEach(stop => {
    if (!stopRows.has(stop.downtime_ref)) stopRows.set(stop.downtime_ref, { ...stop, machine_ref: row.source.machine_ref, valid: true, recorded_at: null });
  }));
  const stops = Array.from(stopRows.values()).filter(row => row.valid).map(row => ({ ...row, startAt: G.instant(row.start), endAt: G.instant(row.end) }));
  const affected = new Set(stops.map(row => row.machine_ref)), windows = new Map();
  for (const row of stops) { if (!windows.has(row.machine_ref)) windows.set(row.machine_ref, []); windows.get(row.machine_ref).push(row); }
  const tasks = data.tasks.filter(row => row.source === 'internal' && row.machine_ref);
  const facts = G.prepareTasks({
    tasks, plan_span: { start: data.time_scope.range_start, end: data.time_scope.range_end },
    resources: data.resource_common.cohort.map(row => ({ ref: row.ref, label: row.label }))
  });
  return { facts, stops, affected, windows, risks: new Map(data.deliveries.map(row => [row.batch_ref, row.risk])) };
}

function groupPrepared(prepared, mode) {
  let facts = prepared.facts;
  if (mode === 'downtime') {
    let start = facts.start, end = facts.end;
    for (const stop of prepared.stops) { start = Math.min(start, stop.startAt); end = Math.max(end, stop.endAt); }
    facts = { ...facts, start, end, items: facts.items.filter(item => prepared.affected.has(item.task.machine_ref)) };
  }
  return { ...G.selectPrepared(G.groupPrepared(facts, 'machine')), windows: prepared.windows, risks: prepared.risks };
}

function layoutPrepared(prepared, width) {
  return { ...G.layoutPrepared(prepared, width), windows: prepared.windows, risks: prepared.risks };
}

function title(task, risk) {
  return [
    task.batch_id + ' · ' + task.sequence + ' ' + task.process_label,
    WorkbenchFormat.compactRange(task.start, task.end), '安排时长 ' + WorkbenchFormat.hours(task.span_hours),
    task.start === task.end ? '零工时工序，不占设备人员' : null,
    '设备：' + (task.machine_label || '名称未填写'),
    risk ? '批次交付：' + WorkbenchTerms.delivery_risks[risk] : null
  ].filter(Boolean).join('\n');
}

const instant = G.instant;
const wire = G.wire;
const visibleRows = G.visibleRows;
const visibleItems = G.visibleItems;
const number = (value, options) => WorkbenchFormat.number(value, options);
const timeLabel = value => WorkbenchFormat.compactDateTime(value);

const DashboardTimelineModel = {
  prepare, groupPrepared, layoutPrepared, title, instant, wire,
  visibleRows, visibleItems, number, timeLabel
};

export {
  DashboardTimelineModel, prepare, groupPrepared, layoutPrepared, title, instant, wire,
  visibleRows, visibleItems, number, timeLabel
};
export default DashboardTimelineModel;
