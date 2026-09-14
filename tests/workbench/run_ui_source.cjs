'use strict';
const fs = require('node:fs'), path = require('node:path'), crypto = require('node:crypto');
const root = path.resolve(__dirname, '../..');
function dependencies(files) {
  const result = ['WorkbenchFormat.js', 'WorkbenchTerms.js', 'WorkbenchHandlerMemory.js', 'WorkbenchReferences.jsx', 'RunPresentation.js',
    'resource-contract.js', 'ResourceControls.jsx', 'WorkbenchGuards.js', 'CalendarContract.js', 'WorkbenchControlBridge.js',
    'WorkbenchControlStyles.jsx', 'WorkbenchSelectMenu.jsx', 'WorkbenchDatePickerModel.js', 'WorkbenchDatePicker.jsx',
    'WorkbenchControls.jsx', 'WorkbenchNumberControls.jsx', 'WorkbenchListControls.jsx', ...files];
  return [...new Set(result)];
}
function styles(report, output) {
  const names = ['00-tokens.css', '20-controls.css', '21-table-frame.css', '22-shared-controls.css',
    ...(report.sources.some(row => /\/(?:PointGantt|PlanGantt)/.test(row.path)) ? ['33-plan-gantt.css'] : []), '34-run.css'];
  const rows = names.map(name => {
    const source = 'frontend/workbench/app/styles/' + name, code = fs.readFileSync(path.join(root, source), 'utf8');
    if (output) { const target = path.join(output, 'sources', source); fs.mkdirSync(path.dirname(target), { recursive: true }); fs.writeFileSync(target, code); }
    return { path: source, code, sha256: crypto.createHash('sha256').update(code).digest('hex') };
  });
  report.sources.push(...rows.map(({ path, sha256 }) => ({ path, sha256 })));
  return rows.map(row => '<style data-source="' + row.path + '">' + row.code + '</style>').join('');
}
async function reference(owner, value) {
  const detail = owner.locator('details.wb-ref').filter({ hasText: value }).first();
  await detail.evaluate(node => { node.open = true; });
  await detail.getByText(value, { exact: true }).waitFor();
}
function button(page, name) {
  const task = /^工序详情 ([0-9a-f]{48})$/.exec(name), candidate = /^查看候选 ([0-9a-f]{48})$/.exec(name), baseline = /^初始计划对照 ([0-9a-f]{48})$/.exec(name), run = /^查看运行 ([0-9a-f]{48})$/.exec(name);
  if (task) return page.locator('[data-candidate-task-list] [data-row-ref="' + task[1] + '"]').getByRole('button');
  if (candidate) return page.locator('[data-candidate-ref="' + candidate[1] + '"]').getByRole('button', { name: /^查看候选 / });
  if (baseline) return page.locator('[data-baseline-operation="' + baseline[1] + '"]').getByRole('button');
  if (run) return page.locator('[data-run-ref="' + run[1] + '"]').getByRole('button');
  return page.getByRole('button', { name: name === '正式采用' ? '采用方案' : name, exact: true });
}
module.exports = { dependencies, styles, reference, button };
