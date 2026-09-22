'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm'), crypto = require('node:crypto');
const root = path.resolve(__dirname, '../..'), app = path.join(root, 'frontend/workbench/app');
const standalone = require.main === module, baselineRoot = standalone ? process.argv[2] : undefined, reportFile = standalone ? process.argv[3] : undefined;
const babel = require(path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'));
const { compile } = require('../../scripts/workbench/compile.cjs');
const sources = new Map(), syntax = new Map();
const hash = value => crypto.createHash('sha256').update(value).digest('hex'), evidence = { cases: [], baseline_sources: [] };
const dependencies = ['WorkbenchFormat.js', 'WorkbenchTerms.js', 'PlanGanttModel.js', 'DashboardTimelineModel.js', 'RunCandidateModel.js', 'FieldContract.js', 'ActualGanttModel.js'];
function read(name) {
  if (!sources.has(name)) {
    const code = fs.readFileSync(path.join(app, name), 'utf8'); sources.set(name, code);
    syntax.set(name, babel.transform(code, { filename: name, ast: true, code: false, sourceType: 'script', parserOpts: { plugins: ['jsx'] } }).ast);
  }
  return syntax.get(name);
}
function nodes(value, predicate, result = []) {
  if (!value || typeof value !== 'object') return result;
  if (predicate(value)) result.push(value);
  for (const [key, child] of Object.entries(value)) if (!['loc', 'tokens', 'comments'].includes(key)) {
    if (Array.isArray(child)) child.forEach(item => nodes(item, predicate, result)); else nodes(child, predicate, result);
  }
  return result;
}
function expression(name, predicate) {
  return nodes(read(name), node => node.type === 'JSXExpressionContainer').map(node => sources.get(name).slice(node.expression.start, node.expression.end)).filter(predicate);
}
const host = vm.createContext({ window: {}, Date });
for (const name of dependencies)
  vm.runInContext(fs.readFileSync(path.join(app, name), 'utf8'), host);
const real = host.window.WorkbenchFormat, calls = [];
host.window.WorkbenchFormat = { ...real, dateTime: (...args) => { calls.push(args[0]); return real.dateTime(...args); } };
const trial = nodes(read('TrialControls.jsx'), node => node.type === 'VariableDeclarator' && node.id.name === 'timeLabel')[0];
host.U = { timeLabel: vm.runInContext(sources.get('TrialControls.jsx').slice(trial.init.start, trial.init.end), host) };
const cases = [
  ['PlanGantt.jsx', 'PlanGanttModel', 'M.timeLabel(', ['2026-09-09', '23:59:59'], ['2026-09-10', '00:00:01'], ['tick.label.slice(0, 10)', 'tick.label.slice(11)']],
  ['DashboardTimeline.jsx', 'DashboardTimelineModel', 'M.timeLabel(', ['2026-09-09', '23:59:59'], ['2026-09-10', '00:00:01'], ['tick.label.slice(0, 10)', 'tick.label.slice(11)']],
  ['RunCandidateGantt.jsx', 'RunCandidateModel', 'M.timeLabel(', ['09-09', '23:59:59'], ['09-10', '00:00:01'], ['t.label.slice(5, 10)', 't.label.slice(11)']],
  ['ActualGanttWorkspace.jsx', 'ActualGanttModel', 'M.time(', ['2026-09-09', '23:59:59'], ['2026-09-10', '00:00:01'], ['tick.label.slice(0, 10)', 'tick.label.slice(11, 19)']],
  // The trial gantt now shares PlanGanttModel.ticks; its labels go through TrialControls.timeLabel (host.U below).
  ['TrialGantt.jsx', 'PlanGanttModel', 'U.timeLabel(', ['09-09', '23:59:59'], ['09-10', '00:00:01'], ['tick.label.slice(5, 10)', 'tick.label.slice(11)']],
];
// The formal-plan contract retains second precision; field/trial displays keep their existing compact whole-minute labels.
const wholeMinute = [['PlanGantt.jsx', 'PlanGanttModel', 'M.timeLabel(', '08:30:00'], ['ActualGanttWorkspace.jsx', 'ActualGanttModel', 'M.time(', '08:30'], ['TrialGantt.jsx', 'PlanGanttModel', 'U.timeLabel(', '08:30']];
function legacySource(name, expressions) {
  if (!baselineRoot) return;
  const file = path.join(baselineRoot, 'frontend/workbench/app', name), original = fs.readFileSync(file, 'utf8');
  expressions.forEach(code => assert(original.includes(code), 'Expression is present in the frozen source: ' + name));
  evidence.baseline_sources.push({ path: file, sha256: hash(original), expressions });
}
for (const [name, model, prefix, before, after, legacy] of cases) {
  const fragments = expression(name, code => code.startsWith(prefix) && code.includes('.slice('));
  legacySource(name, legacy);
  assert.equal(fragments.length, 2, name + ' has the two real tick text fragments'); host.M = host.window[model];
  for (const [stamp, expected] of [['2026-09-09T23:59:59', before], ['2026-09-10T00:00:01', after]]) {
    host.tick = host.t = { label: stamp }; const start = calls.length;
    const actual = fragments.map(code => vm.runInContext(code, host)), original = legacy.map(code => vm.runInContext(code, host));
    assert.deepEqual(actual, expected, name + ' factory-local tick precision'); assert.deepEqual(actual, original, 'Frozen full-second precision is retained');
    assert.deepEqual(calls.slice(start), [stamp, stamp], name + ' consumes the actual Format module');
    evidence.cases.push({ component: name, input: stamp, expected, actual, legacy_output: original, expressions: fragments, legacy_expressions: legacy });
  }
}
for (const [name, model, prefix, expected] of wholeMinute) {
  const fragments = expression(name, code => code.startsWith(prefix) && code.includes('.slice(')); host.M = host.window[model];
  host.tick = host.t = { label: '2026-09-10T08:30:00' };
  const actual = vm.runInContext(fragments[1], host);
  assert.equal(actual, expected, name + ' keeps its documented whole-minute precision');
  evidence.cases.push({ component: name, input: '2026-09-10T08:30:00', expected, actual, expressions: fragments });
}
const trialTicks = nodes(read('TrialGantt.jsx'), node => node.type === 'CallExpression' && node.callee.type === 'MemberExpression' && node.callee.property.name === 'ticks');
assert(trialTicks.some(node => sources.get('TrialGantt.jsx').slice(node.start, node.end).startsWith('window.PlanGanttModel.ticks(')), 'Trial ticks come from the shared plan gantt ladder');
const trialCss = fs.readFileSync(path.join(app, 'styles/32-process-trial.css'), 'utf8');
assert(/\.tt-tick\s+small\s*\{[^}]*display\s*:\s*block/.test(trialCss), 'Trial tick date and time are separated onto two visual lines');
const average = expression('ActualGanttWorkspace.jsx', code => code.startsWith("stats.average === null ? '暂无数据'")); assert.equal(average.length, 1);
// 词表把「未核实」改成「暂无数据」、把 m 改成分钟；数值语义仍与冻结源逐值对齐，只在比较前抹平这两处措辞。
const sameNumber = value => value.replace(/,/g, '').replace(' 分钟', 'm').replace('暂无数据', '未核实');
const legacyAverage = "stats.average === null ? '未核实' : (stats.average > 0 ? '+' : '') + Math.round(stats.average) + 'm'";
legacySource('ActualGanttWorkspace.jsx', [legacyAverage]);
for (const [value, expected] of [[null, '暂无数据'], [0, '0 分钟'], [-0, '0 分钟'], [.1, '+0 分钟'], [-.1, '0 分钟'], [.5, '+1 分钟'], [-.5, '0 分钟'], [1.5, '+2 分钟'], [-1.5, '-1 分钟'], [12345.6, '+12,346 分钟'], [-12345.6, '-12,346 分钟']]) {
  host.stats = { average: value }; const actual = vm.runInContext(average[0], host), original = vm.runInContext(legacyAverage, host);
  assert.equal(actual, expected, 'Original round/sign semantics with shared number grouping'); assert.equal(sameNumber(actual), original);
  evidence.cases.push({ component: 'ActualGanttWorkspace.jsx average', input: Object.is(value, -0) ? '-0' : value, expected, actual, legacy_output: original, expressions: average, legacy_expressions: [legacyAverage] });
}
for (const value of [NaN, Infinity, -Infinity]) {
  host.stats = { average: value }; assert.throws(() => vm.runInContext(average[0], host), error => error.name === 'TypeError');
  evidence.cases.push({ component: 'ActualGanttWorkspace.jsx average', input: String(value), expected: 'TypeError', actual: 'TypeError', expressions: average });
}
const product = Array.from(new Set(cases.map(row => row[0]).concat('TrialGantt.jsx')));
const built = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources: product.map(name => ({ path: name, code: sources.get(name) })), check_combined: true });
if (reportFile) {
  const directory = path.dirname(path.resolve(reportFile)); fs.mkdirSync(path.join(directory, 'compiled'), { recursive: true });
  evidence.sources = [...product, ...dependencies, 'TrialControls.jsx'].map(name => ({ path: 'frontend/workbench/app/' + name, sha256: hash(fs.readFileSync(path.join(app, name))) }));
  evidence.input_expected_sha256 = hash(JSON.stringify(evidence.cases.map(({ component, input, expected }) => ({ component, input, expected }))));
  evidence.passed = true; fs.writeFileSync(path.resolve(reportFile), JSON.stringify(evidence, null, 2));
  built.outputs.forEach(item => fs.writeFileSync(path.join(directory, 'compiled', item.path + '.js'), item.code));
  fs.writeFileSync(path.join(directory, 'compile.json'), JSON.stringify({ babel_version: built.babel_version, target: built.target, passed: true, outputs: built.outputs.map(item => ({ path: 'compiled/' + item.path + '.js', sha256: hash(item.code) })) }, null, 2));
}
console.log(JSON.stringify({ passed: true, tick_consumers: 5, cross_midnight: true, whole_minute: wholeMinute.length, average_cases: 11, rejected_nonfinite: 3, chrome_target: 109 }));
