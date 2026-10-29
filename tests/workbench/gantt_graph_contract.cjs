'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const root = path.resolve(__dirname, '../..'), window = {};
const context = vm.createContext({ window, Date, Number, Map, Set });
for (const file of ['WorkbenchFormat.js', 'WorkbenchTerms.js', 'FieldContract.js', 'PointContract.js', 'PointGanttModel.js', 'PlanGanttModel.js', 'GanttPresentation.js', 'RunCandidateModel.js', 'RunBaselineModel.js', 'GanttGraph.js'])
  vm.runInContext(fs.readFileSync(path.join(root, 'frontend/workbench/app', file), 'utf8'), context, { filename: file });
const G = window.GanttGraph, ref = n => n.toString(16).padStart(48, '0'), clone = value => JSON.parse(JSON.stringify(value));
const at = hour => '2026-10-12T' + String(hour).padStart(2, '0') + ':00:00';
const refs = values => Array.from(values).sort(), expected = values => values.map(ref).sort();
const edgesOf = value => Array.from(value.adjacency.values()).flat().sort((a, b) => a.order - b.order).map(item => item.edge);
const specs = [
  [1, null, 8, 9, 'common-start'], [2, 'A', 9, 10, 'piece-a-before'], [3, 'A', 10, 10, 'piece-a-point'],
  [4, 'A', 10, 11, 'piece-a-after'], [5, 'B', 9, 11, 'piece-b'], [6, null, 11, 12, 'common-end'],
  [7, 'A', 7, 8, 'other-batch']
];
const tasks = specs.map(([id, piece_id, start, end, process_label]) => ({
  task_ref: ref(id), operation_ref: ref(id + 20), plan_ref: ref(100), batch_id: id === 7 ? 'B2' : 'B1',
  piece_id, start: at(start), end: at(end), process_label, sequence: id * 10,
  machine_ref: ref(id === 7 ? 202 : 200), operator_ref: null, supplier_ref: null,
  ...(start === end ? { event_kind: 'point', duration_seconds: 0, occupies_resources: false } : {})
}));
const edge = (from, to, edge_type = 'process') => ({ from_task_ref: ref(from), to_task_ref: ref(to), edge_type });
const predecessors = new Map([[2, [1]], [3, [2]], [4, [3]], [6, [4, 5]], [5, [1]]]);
const graph = { state: 'available', reason: null, scope: 'full_plan', nodes: tasks.map((task, index) => ({ ...task,
  predecessor_operation_refs: (predecessors.get(index + 1) || []).map(id => ref(id + 20)) })),
  critical_task_refs: [7, 1, 2, 3, 4, 6].map(ref),
  critical_edges: [edge(7, 1, 'machine'), ...[[1, 2], [2, 3], [3, 4], [4, 6]].map(pair => edge(...pair))] };
const valid = (value, options = {}) => G.validate(value, { scope: 'full_plan', tasks, taskRef: 'task_ref',
  time: value => typeof value === 'string' && /^2026-10-12T\d{2}:00:00$/.test(value),
  sequence: Number.isInteger, processLabel: value => typeof value === 'string' && !!value.trim(), completeCount: tasks.length, ...options });

// The boundary accepts zero-duration tasks and a complete empty result, but rejects another source or incomplete identity.
assert(valid(graph));
assert(valid({ ...graph, nodes: [], critical_task_refs: [], critical_edges: [] }, { tasks: [], completeCount: 0 }));
assert(!valid({ ...graph, scope: 'full_candidate' }));
assert(!valid(graph, { completeCount: tasks.length + 1 }));
assert(valid(graph, { tasks: [tasks[2]], completeCount: undefined }), 'A range-filtered response retains the full graph');
const candidateTasks = tasks.map(task => ({ ...task, row_ref: task.task_ref }));
assert(valid({ ...graph, scope: 'full_candidate' }, { scope: 'full_candidate', tasks: candidateTasks, taskRef: 'row_ref' }));
for (const change of [
  value => { value.nodes[2].end = at(9); },
  value => { value.nodes[2].operation_ref = ref(999); },
  value => { value.nodes[1].predecessor_operation_refs = ['invalid']; },
  value => { value.nodes[1].predecessor_operation_refs = [value.nodes[1].operation_ref]; },
  value => { value.nodes[1].predecessor_operation_refs.push(value.nodes[1].predecessor_operation_refs[0]); },
  value => { value.edges = []; },
  value => { value.critical_edges[0].from_task_ref = ref(5); }
]) { const value = clone(graph); change(value); assert(!valid(value)); }
const unavailable = { state: 'unavailable', reason: '生成时未记录工艺关系', scope: 'full_plan', nodes: [], critical_task_refs: [], critical_edges: [] };
assert(valid(unavailable));
assert(!valid({ ...unavailable, reason: '' }));
assert(!valid({ ...unavailable, nodes: graph.nodes }));
const summaryGraph = { state: 'available', reason: null, scope: 'full_plan', nodes: [], node_count: tasks.length, nodes_complete: false, critical_task_refs: [], critical_edges: [] };
assert(valid(summaryGraph));
assert(!valid({ ...summaryGraph, node_count: 0 }));
assert(!valid({ ...summaryGraph, node_count: 10001 }));
assert(valid({ ...summaryGraph, node_count: 10001 }, { tasks: [tasks[0]], completeCount: undefined }));
assert(!valid({ ...summaryGraph, nodes: [graph.nodes[0]] }));
assert(!valid({ ...summaryGraph, scope: 'full_candidate' }, { scope: 'full_candidate' }));
assert(valid({ ...graph, node_count: graph.nodes.length, nodes_complete: true }));
assert(!valid({ ...graph, node_count: graph.nodes.length - 1, nodes_complete: true }));
assert(valid({ ...unavailable, node_count: 0, nodes_complete: false }));
assert(!valid({ ...unavailable, node_count: 1, nodes_complete: false }));
const largeGraph = { ...graph, nodes: Array.from({ length: 10001 }, (_, index) => index === 0 ? graph.nodes[0] : ({ ...graph.nodes[0], task_ref: ref(index + 1000), operation_ref: ref(index + 20000), predecessor_operation_refs: [] })), critical_task_refs: [], critical_edges: [] };
assert(valid(largeGraph, { tasks: [], completeCount: undefined }), 'The complete relation graph is independent of the 10000 visible-task limit');
assert(valid({ ...largeGraph, node_count: 10001, nodes_complete: true }, { tasks: [tasks[0]], completeCount: undefined }));
assert.equal(G.create(largeGraph).nodes.size, 10001);
const missingGraph = clone(graph); missingGraph.nodes[2].predecessor_operation_refs.push(ref(999));
assert(valid(missingGraph), 'An unarranged predecessor remains an explicit operation reference');
const missingIndex = G.create(missingGraph);
assert.equal(missingIndex.missingPredecessors.get(ref(3)), 1);
assert.deepEqual(refs(G.route(missingIndex, ref(3)).previous.get(ref(3)).map(node => node.task_ref)), expected([2]));
const { compile } = require('../../scripts/workbench/compile.cjs');
context.React = { createElement: (type, props, ...children) => ({ type, props: { ...props, children } }), useMemo: fn => fn() };
window.ResourceControls = { Button: 'button' };
vm.runInContext(compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'),
  sources: [{ path: 'GanttRouteList.jsx', code: fs.readFileSync(path.join(root, 'frontend/workbench/app/GanttRouteList.jsx'), 'utf8') }] }).outputs[0].code, context);
const createGraph = G.create; let detailGraphBuilds = 0;
G.create = value => { detailGraphBuilds++; return createGraph(value); };
const routeList = window.GanttRouteList({ index: missingIndex, targetRef: ref(3), loadedRefs: new Set([ref(3)]), onSelect() {} });
G.create = createGraph;
const routeText = value => Array.isArray(value) ? value.map(routeText).join('') : value && typeof value === 'object' ? routeText(value.props.children) : value == null || value === false ? '' : String(value);
assert.equal(detailGraphBuilds, 0, 'The route consumes the existing prepared index without rebuilding it');
assert(routeText(routeList).includes('所选工序有 1 道前序未在本计划安排。'));
const segmentedGraph = clone(graph); segmentedGraph.nodes.push({ ...segmentedGraph.nodes[0], task_ref: ref(8) });
const segmentedIndex = G.create(segmentedGraph);
assert.deepEqual(refs(G.route(segmentedIndex, ref(2)).previous.get(ref(2)).map(node => node.task_ref)), expected([8]), 'A predecessor resolves to its last saved arrangement, matching the shared producer');
const crossGraph = clone(graph); crossGraph.nodes[1].predecessor_operation_refs.push(ref(27));
const crossRoute = G.route(G.create(crossGraph), ref(2));
assert.deepEqual(refs(crossRoute.previous.get(ref(2)).map(node => node.task_ref)), expected([1]), 'A predecessor in another batch stays out of this batch route');
assert.equal(crossRoute.groups.reduce((sum, group) => sum + group.nodes.length, 0), crossRoute.count, 'A cross-batch predecessor does not strand its successor');

// Selecting a middle operation includes predecessors, successors and common operations without crossing to a sibling piece.
const index = G.create(graph), active = G.selection(index, { targetRef: ref(3) });
const fullRoute = G.route(index, ref(3));
const samePiece = G.selection(index, { targetRef: ref(4) }), sameBatchRoute = G.route(index, ref(1));
assert.strictEqual(samePiece.related, active.related);
assert.strictEqual(samePiece.adjacency, active.adjacency); assert.strictEqual(samePiece.critical, active.critical);
assert.strictEqual(sameBatchRoute.groups, fullRoute.groups); assert.strictEqual(sameBatchRoute.previous, fullRoute.previous);
assert.equal(samePiece.target.task_ref, ref(4)); assert.equal(sameBatchRoute.target.task_ref, ref(1));
assert.deepEqual(clone(fullRoute.groups.map(group => [group.pieceId, group.nodes.map(node => node.task_ref)])),
  [[null, [ref(1), ref(6)]], ['A', [ref(2), ref(3), ref(4)]], ['B', [ref(5)]]], 'The list keeps common operations and sibling branches distinct');
assert.deepEqual(refs(fullRoute.previous.get(ref(6)).map(node => node.task_ref)), expected([4, 5]), 'A common join shows both real branch predecessors');
assert.equal(fullRoute.count, 6); assert.equal(fullRoute.groups[0].nodes[1].process_label, 'common-end', 'Labels come from the complete frozen graph, including nodes outside loaded tasks');
const reversedSchedule = clone(graph);
Object.assign(reversedSchedule.nodes.find(node => node.task_ref === ref(2)), { start: at(11), end: at(12) });
Object.assign(reversedSchedule.nodes.find(node => node.task_ref === ref(4)), { start: at(7), end: at(8) });
assert.deepEqual(clone(G.route(G.create(reversedSchedule), ref(3)).groups.find(group => group.pieceId === 'A').nodes.map(node => node.task_ref)),
  [ref(2), ref(3), ref(4)], 'The route follows explicit dependencies even when the schedule runs in reverse order');
assert.deepEqual(refs(G.selection(index).critical), expected([7, 1, 2, 3, 4, 6]));
assert.deepEqual(refs(active.related), expected([1, 2, 3, 4, 6]));
assert.equal(active.target.task_ref, ref(3));
const activeEdges = edgesOf(active);
assert.equal(activeEdges.filter(item => item.kind === 'related').length, 4);
assert(activeEdges.every(item => item.kind === 'related'), 'Focus hides global edges instead of leaving unrelated lines');
assert.equal(edgesOf(G.selection(index)).length, 0, 'Global lines start off while critical marks remain');
assert(!activeEdges.some(item => item.from_task_ref === ref(5) || item.to_task_ref === ref(5)));
assert.equal(new Set(activeEdges.map(item => item.from_task_ref + ':' + item.to_task_ref + ':' + item.edge_type)).size, activeEdges.length,
  'A process edge shared by critical and related chains must be drawn once with the related style');
assert.deepEqual(refs(G.selection(index, { targetRef: ref(1) }).related), expected([1, 2, 3, 4, 5, 6]));
assert.deepEqual(refs(G.selection(index, { targetRef: ref(7) }).related), expected([7]));
const relatedOnly = G.selection(index, { enabled: false, targetRef: ref(3) });
assert.equal(relatedOnly.critical.size, 6); assert.equal(edgesOf(relatedOnly).length, 4);
assert.deepEqual(refs(relatedOnly.related), refs(active.related));

// One visible connection per task pair: the active process route replaces an overlapping resource dependency.
const resourceGraph = { ...graph, critical_edges: graph.critical_edges.map(item =>
  item.from_task_ref === ref(1) && item.to_task_ref === ref(2) ? { ...item, edge_type: 'machine' } : item) };
const resourceIndex = G.create(resourceGraph), pair = value => edgesOf(value).filter(item => item.from_task_ref === ref(1) && item.to_task_ref === ref(2));
assert.equal(pair(G.selection(resourceIndex, { enabled: true }))[0].edge_type, 'machine', 'The default critical connection keeps its resource dash style');
const highlightedPair = pair(G.selection(resourceIndex, { targetRef: ref(3) }));
assert.equal(highlightedPair.length, 1, 'Resource and process edges must not paint over each other');
assert.equal(highlightedPair[0].edge_type, 'process'); assert.equal(highlightedPair[0].kind, 'related');
assert.equal(resourceGraph.critical_edges.find(item => item.from_task_ref === ref(1)).edge_type, 'machine', 'Display selection must preserve the source graph');

const data = { tasks, gantt_graph: graph, resources: [{ ref: ref(200), label: 'Machine' }, { ref: ref(202), label: 'Other machine' }],
  plan_span: { start: at(7), end: at(12) }, task_span: { start: at(7), end: at(12) },
  projections: { calendar: { resources: [] }, occupancy: { resources: [] }, baseline: { state: 'unavailable', items: [] } } };
const occupancy = { resource_ref: ref(200), kind: 'machine', segments: [], utilization: 0.75, available_occupied_hours: 3, available_hours: 4 };
data.projections.occupancy.resources.push(occupancy);
assert.equal(window.PlanGanttModel.tone(tasks[0], new Map([['B1', 'on_time']])), 'primary', 'On-time tasks retain the normal pale-blue tone');
assert.equal(window.PlanGanttModel.tone(tasks[0], new Map([['B1', 'overdue']])), 'critical');
const candidateData = { gantt_graph: { ...graph, scope: 'full_candidate' }, task_span: data.task_span, unplanned_operations: [], tasks: candidateTasks.map(task => ({ ...task,
  batch_ref: ref(task.batch_id === 'B1' ? 300 : 301), batch_label: task.batch_id, machine: { ref: task.machine_ref, label: 'Machine' } })) };
// Same chain as RunCandidateGantt without a loaded baseline.
const candidateLayout = (value, mode, query, width = 1000, operationRefs = null) => {
  const M = window.RunCandidateModel, B = window.RunBaselineModel;
  const candidate = M.selectPrepared(M.groupPrepared(M.prepare(value), mode), query, operationRefs, null);
  return B.layoutPrepared(B.selectPrepared(candidate, B.groupPrepared(B.prepare(null), mode), query, operationRefs, false), width);
};
const width = 1000;
for (const candidate of [false, true]) {
  const layout = query => candidate ? candidateLayout(candidateData, 'machine', query, width)
    : window.PlanGanttModel.layoutPrepared(window.PlanGanttModel.selectPrepared(window.PlanGanttModel.groupPrepared(window.PlanGanttModel.prepare(data), 'machine'), query), width);
  const model = layout(''), options = { candidate }, viewport = { left: 0, top: 0, width, height: model.height };
  if (!candidate) assert.strictEqual(model.rows.find(row => row.id === ref(200)).occupancy, occupancy, 'Resource summary uses the existing occupancy projection');
  const positions = G.locations(model, options), locationIndex = G.locationIndex(positions);
  const indexed = () => G.paths(active, model, width, viewport, { locationIndex }), rendered = indexed();
  let positionScans = 0, criticalScans = 0, edgeScans = 0;
  const positionIterator = positions[Symbol.iterator], criticalIterator = active.critical[Symbol.iterator], adjacencyIterator = active.adjacency[Symbol.iterator];
  positions[Symbol.iterator] = function () { positionScans++; return positionIterator.call(this); };
  active.critical[Symbol.iterator] = function () { criticalScans++; return criticalIterator.call(this); };
  active.adjacency[Symbol.iterator] = function () { edgeScans++; return adjacencyIterator.call(this); };
  indexed(); G.paths(active, model, width, { ...viewport, top: 56, height: 56 }, { locationIndex });
  delete positions[Symbol.iterator]; delete active.critical[Symbol.iterator]; delete active.adjacency[Symbol.iterator];
  assert.equal(positionScans, 0); assert.equal(criticalScans, 0); assert.equal(edgeScans, 0);
  assert.equal(rendered.paths.length, 4); assert.equal(rendered.relatedVisible, 5); assert.equal(rendered.criticalVisible, 6);
  assert.equal(positions.get(ref(3)).start, positions.get(ref(3)).end, 'The zero-duration operation must keep its own coordinate');
  assert(rendered.paths.some(item => item.to_task_ref === ref(3)) && rendered.paths.some(item => item.from_task_ref === ref(3)),
    'The zero-duration operation retains both incoming and outgoing connectors');
  assert(rendered.paths.every(item => !/NaN|Infinity|undefined/.test(item.d)));

  const filtered = layout('piece-a'), filteredPaths = G.paths(active, filtered, width, { ...viewport, height: filtered.height }, { locationIndex: G.locationIndex(G.locations(filtered, options)) });
  assert.deepEqual(refs(active.related), expected([1, 2, 3, 4, 6]), 'Display filtering must not change semantic membership');
  assert.equal(filteredPaths.relatedVisible, 3); assert.equal(filteredPaths.paths.length, 2);
  assert(filteredPaths.paths.every(item => filteredPaths.visible.has(item.from_task_ref) && filteredPaths.visible.has(item.to_task_ref)));
  const pointRow = model.rows.find(row => row.items.some(item => item.task[candidate ? 'row_ref' : 'task_ref'] === ref(3)));
  const clipped = G.paths(active, model, width, { ...viewport, top: pointRow.top, height: pointRow.height }, { locationIndex });
  assert.equal(clipped.relatedVisible, 1); assert.equal(clipped.paths.length, 0, 'Offscreen endpoint rows must not leave dangling connectors');
}

// The original plan can reuse an operation/task identity, but must never replace the current endpoint coordinates.
const baselineItems = [{ operation_ref: tasks[3].operation_ref, change: 'moved',
  before: { ...tasks[3], start: at(7), end: at(8), machine_ref: ref(202) } }];
data.projections.baseline = { state: 'available', items: [], item_count: 1, items_complete: false };
const unloadedPlan = window.PlanGanttModel.prepare(data);
assert.equal(unloadedPlan.baselineLoaded, false);
assert.equal(unloadedPlan.before.length, 0);
const onDemandPlan = window.PlanGanttModel.prepare(data, baselineItems);
assert.equal(onDemandPlan.baselineLoaded, true);
assert.equal(onDemandPlan.before.length, 1);
data.projections.baseline = { state: 'available', items: baselineItems };
const comparison = window.PlanGanttModel.layoutPrepared(window.PlanGanttModel.selectPrepared(window.PlanGanttModel.groupPrepared(window.PlanGanttModel.prepare(data), 'machine'), '', false, true), width);
assert(comparison.rows.filter(row => row.before).every(row => row.occupancy === null), 'Baseline rows must not present current-plan utilization');
const current = G.locations(comparison).get(ref(4));
assert.equal(current.start, window.PlanGanttModel.instant(at(10))); assert.equal(current.end, window.PlanGanttModel.instant(at(11)));
const candidate = candidateLayout(candidateData, 'machine', '', width), before = G.locations(candidate, { candidate: true }).get(ref(4));
const baselineRow = { baseline: true, top: candidate.height, height: 26, items: [{ task: candidateData.tasks[3], start: 0, end: 1 }] };
assert.deepEqual(G.locations({ ...candidate, rows: [...candidate.rows, baselineRow] }, { candidate: true }).get(ref(4)), before);

// A short/zero time gap must not invent a backward loop. Only a genuinely reversed dependency may run left.
function connector({ gap, fromTop = 0, toTop = 56, candidate = false, point = false }) {
  const end = 200, next = end + gap, height = 56;
  const source = { task_ref: ref(801), row_ref: ref(801) }, target = { task_ref: ref(802), row_ref: ref(802) };
  const sourceItem = { task: source, start: point ? end : 100, end }, targetItem = { task: target, start: next, end: next + 100 };
  const rows = fromTop === toTop ? [{ top: fromTop, height, items: [sourceItem, targetItem] }]
    : [{ top: fromTop, height, point, items: [sourceItem] }, { top: toTop, height, items: [targetItem] }];
  const model = { start: 0, end: 500, rows, height: Math.max(fromTop, toTop) + height };
  const refs = new Set([source.task_ref, target.task_ref]);
  const edge = { from_task_ref: source.task_ref, to_task_ref: target.task_ref };
  const adjacency = new Map([[source.task_ref, [{ edge, order: 0 }]]]);
  return G.paths({ adjacency, critical: refs, related: refs },
    model, 500, { left: 0, top: 0, width: 500, height: model.height }, { locationIndex: G.locationIndex(G.locations(model, { candidate })) }).paths[0].d;
}
function route(path) { return path.split(' M')[0]; }
function horizontalSteps(path) {
  const start = /^M([^,]+),/.exec(route(path)), values = [Number(start[1])];
  for (const match of route(path).matchAll(/ H(-?[\d.]+)/g)) values.push(Number(match[1]));
  return values;
}
for (const candidate of [false, true]) {
  const height = 56;
  for (const gap of [0, 0.25, 8, 30]) for (const [fromTop, toTop] of [[0, 0], [0, height], [height, 0]]) {
    const path = connector({ gap, fromTop, toTop, candidate }), xs = horizontalSteps(path);
    assert(xs.every((value, i) => i === 0 || value >= xs[i - 1]), 'Forward dependencies must never backtrack horizontally: ' + path);
    if (fromTop === toTop) assert(!route(path).includes(' V'), 'One-row connectors stay at the shared seam');
    else if (gap === 0) assert(!route(path).includes(' H'), 'Equal-time handoffs connect vertically without a loop');
  }
  const down = connector({ gap: 0, toTop: height, candidate }), up = connector({ gap: 0, fromTop: height, toTop: 0, candidate });
  const lower = 47;
  assert.equal(route(down), 'M200,' + lower + ' V' + (height + 7), 'Downward links leave and enter the bar edges');
  assert.equal(route(up), 'M200,' + (height + 7) + ' V' + lower, 'Upward links leave and enter the bar edges');
  assert(down.endsWith(' L202.5,' + (height + 3)), 'Downward arrow points down');
  assert(up.endsWith(' L202.5,' + (lower + 4)), 'Upward arrow points up');
  const reversed = horizontalSteps(connector({ gap: -30, toTop: height, candidate }));
  assert(reversed.some((value, i) => i > 0 && value < reversed[i - 1]), 'Actual reversed timing remains visible');
  assert.equal(route(connector({ gap: 0, toTop: height, candidate, point: true })),
    'M200,34 V' + (height + 7), 'Zero-hour handoffs use the diamond edge');
}

// Shared presentation groups calendar dates without collapsing the overnight interval.
const P = window.GanttPresentation, start = Date.parse('2026-10-12T08:00:00Z'), end = Date.parse('2026-10-13T12:00:00Z');
const axis = P.axis({ start, end, width: 840, left: 0, viewport: 840 });
// Legal microsecond intervals must keep positive duration instead of collapsing into zero-hour points.
const epoch = window.PlanGanttModel.instant;
const microStart = epoch('2026-10-12T08:00:00.000001'), microEnd = epoch('2026-10-12T08:00:00.000002');
assert(microEnd > microStart, 'Distinct microseconds in the same millisecond retain their order');
const crossSecond = epoch('2026-10-12T08:00:01') - epoch('2026-10-12T08:00:00.999999');
assert(crossSecond > 0 && crossSecond < .002, 'The fractional milliseconds are added once across a second boundary');
const microAxis = P.axis({ start: microStart, end: microEnd, width: 640 });
assert(microAxis.bands.length > 0 && microAxis.bands.every(band => Number.isFinite(band.x) && Number.isFinite(band.width)), 'Short positive spans keep finite shared-axis coordinates');
assert.strictEqual(window.RunCandidateModel.instant, epoch, 'Candidates use the same factory-local coordinate parser');
assert.deepEqual(Array.from(axis.bands, band => band.label), ['10-12 周一', '10-13 周二']);
assert.equal(axis.bands[1].x, 480, 'Midnight remains sixteen real hours after the range start');
assert(axis.ticks.every(tick => /^\d{2}:\d{2}$/.test(tick.label)), 'Normal zoom omits seconds');
assert(P.axis({ start, end: start + 10000, width: 840 }).ticks.every(tick => /^\d{2}:\d{2}:\d{2}$/.test(tick.label)), 'Second-level zoom retains seconds');
assert.equal(P.taskLines({ sequence: 20, process: '车削', batch: 'B1', piece: '分件 A', resource: 'M1' }, 'machine', 50).primary, '车削');
assert.equal(P.taskLines({ sequence: 20, process: '车削', batch: 'B1', piece: '分件 A', resource: 'M1' }, 'batch', 150).secondary, 'M1 · 分件 A');
const changed = candidateLayout(candidateData, 'machine', '', width, new Set([tasks[3].operation_ref]));
assert.deepEqual(Array.from(changed.tasks, task => task.row_ref), [tasks[3].task_ref]);
assert.equal(changed.start, candidateLayout(candidateData, 'machine', '', width).start, 'Changed-only filtering preserves the full time range');

// Width changes consume prepared ordinary lanes and sort point inputs only once.
context.__normalSorts = 0; context.__baselineSorts = 0; context.__pointSorts = 0;
vm.runInContext(`const originalSort = Array.prototype.sort; Array.prototype.sort = function (compare) {
  const item = this[0], task = item && (item.task || item.segment);
  if (task) {
    if (window.PointContract.isPoint(task)) __pointSorts++;
    else if (item.segment) __baselineSorts++;
    else __normalSorts++;
  }
  return originalSort.call(this, compare);
};`, context);
const pointTask = { ...candidateData.tasks[2], row_ref: ref(900), task_ref: ref(900), operation_ref: ref(901),
  start: '2026-10-12T10:05:00', end: '2026-10-12T10:05:00' };
const candidateFacts = window.RunCandidateModel.prepare({ ...candidateData, tasks: [...candidateData.tasks, pointTask] });
const candidateGroups = window.RunCandidateModel.groupPrepared(candidateFacts, 'machine');
const preparedCandidate = window.RunCandidateModel.selectPrepared(candidateGroups, '', null, null);
const baseline = { comparisons: [{ operation_ref: candidateData.tasks[2].operation_ref, baseline_segments: [
  { ...candidateData.tasks[2], row_ref: ref(902), interval_comparable: true, start: at(0), end: at(0) },
  { ...pointTask, row_ref: ref(903), interval_comparable: true, start: '2026-10-12T00:05:00', end: '2026-10-12T00:05:00' },
  { ...candidateData.tasks[3], row_ref: ref(904), interval_comparable: true, start: at(1), end: at(2) }
] }] };
const baselineGroups = window.RunBaselineModel.groupPrepared(window.RunBaselineModel.prepare(baseline), 'machine');
const prepared = window.RunBaselineModel.selectPrepared(preparedCandidate, baselineGroups, '', null, true);
const sorts = [context.__normalSorts, context.__baselineSorts, context.__pointSorts], pointCalls = [], layoutTracks = window.PointGanttModel.layoutTracks;
window.PointGanttModel.layoutTracks = (...args) => { pointCalls.push({ start: args[1], end: args[2], width: args[3] }); return layoutTracks(...args); };
const compact = window.RunBaselineModel.layoutPrepared(prepared, 640), wide = window.RunBaselineModel.layoutPrepared(prepared, 10000);
assert.deepEqual([context.__normalSorts, context.__baselineSorts, context.__pointSorts], sorts);
assert.equal(pointCalls.length, 4, 'Each final width lays out current and baseline points once');
assert(pointCalls.every(call => call.start === prepared.start && call.end === prepared.end));
assert(compact.rows.filter(row => row.point).length > wide.rows.filter(row => row.point).length);
assert.deepEqual(clone(compact.rows.filter(row => !row.point && !row.baseline).map(row => row.items.map(item => [item.task.row_ref, item.start, item.end, item.overlap]))),
  clone(wide.rows.filter(row => !row.point && !row.baseline).map(row => row.items.map(item => [item.task.row_ref, item.start, item.end, item.overlap]))));
const preparedPlan = window.PlanGanttModel.selectPrepared(window.PlanGanttModel.groupPrepared(window.PlanGanttModel.prepare(data), 'machine'), 'piece-b', false, true), planSorts = [context.__normalSorts, context.__pointSorts];
const hiddenLanes = window.PlanGanttModel.layoutPrepared(preparedPlan, 640), hiddenWide = window.PlanGanttModel.layoutPrepared(preparedPlan, 10000);
assert.deepEqual([context.__normalSorts, context.__pointSorts], planSorts);
const shown = hiddenLanes.rows.find(row => !row.before && !row.point);
assert.equal(shown.track, 1); assert.equal(shown.subrow, 2); assert.equal(shown.trackCount, 2, 'Filtering keeps the full plan lane ordinals');
assert.deepEqual(clone(hiddenWide.rows.map(row => [row.key, row.track, row.trackCount, row.subrow])), clone(hiddenLanes.rows.map(row => [row.key, row.track, row.trackCount, row.subrow])));
window.PointGanttModel.layoutTracks = layoutTracks;
vm.runInContext('Array.prototype.sort = originalSort;', context);
console.log('Gantt graph contracts passed: source boundary, full piece routes, shared branches, zero duration, visibility and current-only geometry');
