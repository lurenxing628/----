'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const root = path.resolve(__dirname, '../..'), context = vm.createContext({ window: {}, Date });
vm.runInContext(fs.readFileSync(path.join(root, 'frontend/workbench/app/RunPresentation.js'), 'utf8'), context);
const P = context.window.RunPresentation;
assert.equal(P.step(null, null), 1);
assert.equal(P.step({ batch_refs: [] }, null), 1);
assert.equal(P.step({ batch_refs: ['batch'] }, null), 2);
assert.equal(P.step({ batch_refs: ['batch'] }, {}), 3);
assert.equal(P.step({ batch_refs: [] }, {}), 1);
assert.equal(P.stage({ stage: 'awaiting_reconciliation' }), '核对排产记录');
assert.equal(P.stage({ stage: 'unexpected' }), '排产阶段未知');
const run = { accepted_at: '2026-09-12T12:00:00', started_at: '2026-09-12T12:01:00', finished_at: '2026-09-12T13:02:03' };
assert.equal(P.elapsed(run), '1 小时 1 分钟 3 秒');
assert.equal(P.elapsed({ ...run, started_at: null }), '1 小时 2 分钟 3 秒');
assert.equal(P.elapsed({ ...run, finished_at: null }, new Date(2026, 8, 12, 12, 1, 35).getTime()), '35 秒');
assert.equal(P.elapsed({ ...run, finished_at: '2026-09-12T11:59:59' }), '未知');
assert.equal(P.elapsed({ ...run, accepted_at: 'bad', started_at: null }), '未知');
context.window.PlanGanttModel = {};
for (const name of ['WorkbenchFormat.js', 'WorkbenchTerms.js', 'RunCandidateModel.js']) {
  vm.runInContext(fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8'), context);
}
assert.equal(context.window.RunCandidateModel.number('9007199254740993'), '9,007,199,254,740,993');
assert.equal(context.window.RunCandidateModel.percent('9007199254740993'), '900,719,925,474,099,300%');
console.log('run UI step and elapsed contracts passed');
