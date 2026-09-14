/* CN-only source harness. All business reads/writes are proxied to the real isolated Flask. */
'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), http = require('node:http'), path = require('node:path'), crypto = require('node:crypto');
const { chromium } = require('playwright'), { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), output = process.argv[2], backend = process.argv[3];
const exportOnly = process.argv[5] === 'exports';
const targetOnly = !exportOnly && process.env.TRIAL_WIDGET_TARGET_ONLY === '1';
const files = JSON.parse(process.argv[4]);
assert(Array.isArray(files) && files.length === new Set(files).size);
assert(files.includes('TrialContract.js') && files.indexOf('TrialContract.js') < files.indexOf('TrialExport.js'));
assert(files.indexOf('TrialExport.js') < files.indexOf('TrialControls.jsx'));
const styleSources = JSON.parse(fs.readFileSync(path.join(root, 'scripts/workbench/build-order.json'), 'utf8')).styles.map(name => {
  const file = 'frontend/workbench/app/styles/' + name; return { path: file, code: fs.readFileSync(path.join(root, file), 'utf8') };
});
const workspaceCSS = styleSources.map(row => row.code).join('\n');
const sources = files.map(name => ({ path: 'frontend/workbench/app/' + name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8') }));
const compiled = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true });
const scripts = new Map(compiled.outputs.map((row, i) => ['/source/' + files[i], row.code]));
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
const assets = new Map(manifest.files.map(row => ['/static/' + row.path, { ...row, bytes: fs.readFileSync(path.join(root, 'static', row.path)) }]));
const foundation = manifest.scripts.filter(file => file.startsWith('workbench/vendor/') || file.startsWith('workbench/assets/foundation-'));
const html = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
  '<script src="/static/' + manifest.theme_script + '"></script>' + manifest.styles.map(file => '<link rel="stylesheet" href="/static/' + file + '">').join('') +
  '<style>body{margin:0}#fixture-root{margin-left:208px;padding:16px 24px;min-height:100vh}.fixture-rail{position:fixed;inset:0 auto 0 0;width:208px;padding:24px;background:var(--sidebar-bg);border-right:1px solid var(--ui-border);color:var(--sidebar-text-strong)}</style>' +
  '</head><body class="aps-workbench"><aside class="fixture-rail">APS 智能排产<br>方案试调</aside><div id="fixture-root"></div>' +
  foundation.map(file => '<script src="/static/' + file + '"></script>').join('') + [...scripts.keys()].map(file => '<script src="' + file + '"></script>').join('') +
  '<script>window.nav=[];window.targetChanges=[];window.historySync=location.search.includes("history=1");let root;window.mountTrial=(initialTarget={})=>{if(root)root.unmount();root=ReactDOM.createRoot(document.getElementById("fixture-root"));root.render(React.createElement(React.Fragment,null,React.createElement(WorkbenchGuardHost),React.createElement(WorkbenchControlStyles),React.createElement(WorkbenchTrialWorkspace,{initialTarget,onNavigate:(...v)=>nav.push(v),onTargetChange:next=>{targetChanges.push(next);if(window.failTargetChange)throw Error("Fixture target callback failure");if(historySync)history.replaceState({trialTarget:next},"",location.href);}})));};mountTrial(historySync&&history.state?history.state.trialTarget:{});</script></body></html>';
let dropReply = false;
const server = http.createServer((req, res) => {
  const pathname = new URL(req.url, 'http://fixture').pathname;
  if (pathname === '/probe/drop-next-write-reply') { dropReply = true; res.end('{}'); return; }
  if (pathname.startsWith('/api/') || pathname.startsWith('/fixture/')) {
    const upstream = http.request(backend + req.url, { method: req.method, headers: req.headers }, response => {
      if (dropReply && req.method === 'POST' && /\/(change|save|discard)$/.test(pathname)) {
        dropReply = false; response.resume(); response.on('end', () => { res.setHeader('Content-Type', 'application/json'); res.end('{"ok":'); }); return;
      }
      res.writeHead(response.statusCode, response.headers); response.pipe(res);
    });
    upstream.on('error', () => { if (!res.headersSent) res.writeHead(502); res.end('CN isolated fixture unavailable'); }); req.pipe(upstream); return;
  }
  if (pathname === '/') { res.setHeader('Content-Type', 'text/html;charset=utf-8'); res.end(html.replace('</head>', '<style>' + workspaceCSS + '</style></head>')); return; }
  if (pathname === '/favicon.ico') { res.writeHead(204); res.end(); return; }
  if (scripts.has(pathname)) { res.setHeader('Content-Type', 'application/javascript'); res.end(scripts.get(pathname)); return; }
  const asset = assets.get(pathname); if (!asset) { res.writeHead(404); res.end(); return; } res.setHeader('Content-Type', asset.mime); res.end(asset.bytes);
});
const report = { browser: null, variants: [], checks: [], downloads: [], screenshots: [], errors: [], external: [], dialogs: [], layout: [], shortTasks: [],
  sources: sources.concat(styleSources).map(s => ({ path: s.path, sha256: crypto.createHash('sha256').update(s.code).digest('hex') })) };
let page, origin, variant, refs;
const button = name => page.getByRole('button', { name, exact: true });
const done = name => report.checks.push({ variant, name, passed: true });
const evidence = async () => (await page.request.get(origin + '/fixture/evidence')).json();
const control = action => page.request.post(origin + '/fixture/control', { data: { action } });
const state = () => page.evaluate(() => TrialAPI.pending());
async function shot(name) { const file = path.join(output, variant + '-' + name + '.png'); await page.screenshot({ path: file, fullPage: true, animations: 'disabled' }); report.screenshots.push(file); }
async function exportsFor(data, entry) {
  const expected = JSON.parse(JSON.stringify(data, (key, value) => key === 'write_context' ? undefined : value));
  const dto = path.join(output, variant + '-' + entry + '-dto.json'); fs.writeFileSync(dto, JSON.stringify(expected, null, 2));
  const before = await evidence();
  for (const name of ['导出对比', '导出原始数据']) {
    const pending = page.waitForEvent('download'); await button(name).click(); const download = await pending;
    const filename = download.suggestedFilename(), dest = path.join(output, variant + '-' + entry + '-' + filename);
    await download.saveAs(dest);
    const item = { variant, entry, button: name, filename, path: dest, dto, task_count: data.task_count };
    report.downloads.push(item);
    if (name === '导出对比') {
      assert.equal(filename, '方案试调对比.csv');
      const bytes = fs.readFileSync(dest); assert.deepEqual([...bytes.subarray(0, 3)], [239, 187, 191]);
      assert(!bytes.toString('utf8').includes('write_context')); assert(!bytes.toString('utf8').includes('write_token'));
    } else {
      assert.equal(filename, '试调原始数据.json');
      const downloaded = JSON.parse(fs.readFileSync(dest, 'utf8'));
      assert.equal(downloaded.task_count, data.task_count); assert.equal(downloaded.tasks.length, data.task_count);
      assert(!('write_context' in downloaded)); assert.deepEqual(downloaded, expected);
      item.complete_task_count = true; item.no_write_context = true;
    }
  }
  assert.deepEqual(await evidence(), before, 'Exports must not fetch, write, or replace the current snapshot');
  done(entry + '-actual-csv-and-complete-raw-json-downloads');
}
async function exportRoundTrip() {
  await reset(); await create(); await editor(); await fill();
  const changed = await saveChange(); await exportsFor(changed, 'editing');
  await button('保存试调方案').click(); await page.getByLabel('试调方案名称', { exact: true }).fill('CN 导出逐字段核对 ' + variant);
  await page.getByLabel('确认保存完整试调方案，冲突和未排工序一并保留').check();
  await button('确认保存试调方案').click(); await page.getByRole('dialog').waitFor({ state: 'hidden' }); await ready();
  const scenario = await active(); assert.equal(scenario.draft_ref, changed.draft_ref); assert.equal(scenario.status, 'saved');
  await exportsFor(scenario, 'saved');
}
async function active() {
  const host = page.locator('[data-trial-workspace]'), ref = await host.getAttribute('data-open-ref'), kind = await host.getAttribute('data-open-kind');
  assert(ref); const v = await (await page.request.get(origin + '/api/workbench/v1/trial/' + (kind === 'scenario' ? 'scenarios/' : 'drafts/') + ref)).json();
  assert(v.ok, JSON.stringify(v)); return v.data;
}
async function ready() { await page.locator('.tt-bar').first().waitFor(); await page.waitForFunction(() => !document.querySelector('[aria-label="刷新当前试调"]')?.disabled); }
async function reset() {
  refs = await (await page.request.post(origin + '/fixture/reset')).json();
  await page.goto(origin); await page.locator('[data-trial-ref]').first().waitFor();
}
async function create(kind = 'plan') {
  await button('新增试调').click();
  if (kind === 'candidate') {
    await page.getByRole('tab', { name: '排产候选', exact: true }).click();
    await page.locator('.tt-source-row button:not(:disabled)').first().click();
  }
  await page.locator('.tt-source-row input[type=radio]:not(:disabled)').first().check();
  await button('核对原来源').click();
  await page.getByLabel('确认基于此来源新增独立草稿，正式计划保持不变').check();
  assert.equal(await state(), null);
  const before = (await evidence()).drafts.length;
  await button('确认新增草稿').click(); await page.getByRole('dialog').waitFor({ state: 'hidden' }); await ready();
  const data = await active(), e = await evidence(); assert.equal(e.drafts.length, before + 1); assert.equal(data.task_count, kind === 'plan' ? 5 : 4);
  assert.equal(data.tasks.length, data.task_count); assert(data.tasks.every(t => e.rows.some(r => r.task_ref === t.task_ref && r.draft_ref === data.draft_ref)));
  assert.equal(await state(), null); return data;
}
async function editor(sequence = 1) {
  await selectTask('B1', sequence); await button('调整此工序').click();
}
function taskLabel(task) {
  return '选择工序 ' + task.batch_id + ' · ' + task.sequence + ' ' + task.process_label + ' · '
    + (task.piece_id === null ? '共同工序' : '分件 ' + task.piece_id);
}
async function selectTask(batch, sequence) {
  const tasks = (await active()).tasks.filter(task => task.batch_id === batch && task.sequence === sequence);
  assert.equal(tasks.length, 1, 'Fixture selection must identify one actual task');
  await button(taskLabel(tasks[0])).first().click();
}
async function fill(machine = 'M2', operator = 'O2', start = '2026-09-09T13:00:00') {
  await page.getByLabel('调整设备', { exact: true }).selectOption(refs.machines[machine]);
  await page.getByLabel('调整人员', { exact: true }).selectOption(refs.operators[operator]);
  await page.getByLabel('调整开工', { exact: true }).fill(start.endsWith(':00') ? start.slice(0, 16) : start);
}
async function saveChange() { await button('保存调整').click(); await page.getByLabel('调整开工', { exact: true }).waitFor({ state: 'hidden' }); await ready(); return active(); }
async function geometry(name) {
  await page.evaluate(async () => { await document.fonts.ready; await new Promise(resolve => requestAnimationFrame(resolve)); });
  await page.waitForFunction(() => document.getAnimations().every(animation => animation.playState !== 'running'
    || animation.effect.getTiming().iterations === Infinity));
  const result = await page.evaluate(() => {
    const visible = n => n.getClientRects().length, rect = n => { const r = n.getBoundingClientRect(); return { x: r.x, y: r.y, right: r.right, bottom: r.bottom, width: r.width, height: r.height }; };
    const bars = [...document.querySelectorAll('.tt-bar')].filter(visible), baselines = [...document.querySelectorAll('.tt-baseline')].filter(visible);
    const intersects = (a, b) => a.x < b.right - .01 && b.x < a.right - .01 && a.y < b.bottom - .01 && b.y < a.bottom - .01;
    const dialogs = [...document.querySelectorAll('[role=dialog]')];
    const dialog = dialogs[dialogs.length - 1];
    const rgb = value => (value.match(/[\d.]+/g) || []).map(Number).slice(0, 3);
    const luma = color => rgb(color).map(v => v / 255).map(v => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4).reduce((sum, v, i) => sum + v * [.2126, .7152, .0722][i], 0);
    const ratio = (a, b) => (Math.max(luma(a), luma(b)) + .05) / (Math.min(luma(a), luma(b)) + .05);
    const background = n => { for (let node = n; node; node = node.parentElement) { const c = getComputedStyle(node).backgroundColor; if (!['transparent', 'rgba(0, 0, 0, 0)'].includes(c)) return c; } return 'rgb(255, 255, 255)'; };
    const controls = [...document.querySelectorAll('.trial-workspace .btn:not(:disabled),.trial-modal-body input:not([type=checkbox]),.trial-workspace .tt-muted')].filter(visible);
    const host = document.querySelector('.plana.trial-workspace'), parent = host.parentElement, hostStyle = getComputedStyle(host), parentStyle = getComputedStyle(parent);
    return { overflow: document.documentElement.scrollWidth > innerWidth, bars: bars.length, shortBars: bars.filter(b => rect(b).width < 5).length,
      barGeometry: bars.map(b => ({ ref: b.dataset.taskRef, ...rect(b), trackWidth: rect(b.parentElement).width,
        track: rect(b.parentElement), baseline: b.parentElement.querySelector('.tt-baseline') ? rect(b.parentElement.querySelector('.tt-baseline')) : null, span: b.title })),
      rootWidth: rect(host).width, availableWidth: parent.clientWidth - parseFloat(parentStyle.paddingLeft) - parseFloat(parentStyle.paddingRight),
      rootPadding: [hostStyle.paddingTop, hostStyle.paddingRight, hostStyle.paddingBottom, hostStyle.paddingLeft], rootMaxWidth: hostStyle.maxWidth,
      minTextContrast: Math.min(...controls.map(n => ratio(getComputedStyle(n).color, background(n)))),
      lowTextContrast: controls.map(n => ({ text: n.textContent, className: n.className,
        foreground: getComputedStyle(n).color, background: background(n), ratio: ratio(getComputedStyle(n).color, background(n)) })).filter(row => row.ratio < 4.5),
      textInsideBars: bars.some(b => b.textContent.trim()), barOverlap: bars.some((b, i) => bars.slice(i + 1).some(a => intersects(rect(a), rect(b)))),
      baselineOverlap: bars.some(b => baselines.some(a => intersects(rect(a), rect(b)))),
      labelOverlap: bars.some(b => [...document.querySelectorAll('.tt-task-label')].some(a => intersects(rect(a), rect(b)))),
      dialog: dialog ? { ...rect(dialog), focusInside: dialog.contains(document.activeElement), viewport: { width: innerWidth, height: innerHeight } } : null,
      clippedControls: [...document.querySelectorAll('.trial-workspace button,.trial-modal-body button,.trial-modal-body input')].filter(n => visible(n) && !n.matches('.tt-bar,.tt-task-label') && n.scrollWidth > n.clientWidth + 2).map(n => n.textContent) };
  });
  assert.equal(result.overflow, false, JSON.stringify(result)); assert.equal(result.textInsideBars, false);
  assert(Math.abs(result.rootWidth - result.availableWidth) < 1); assert.equal(result.rootMaxWidth, 'none'); assert(result.rootPadding.every(p => p === '0px'));
  assert(result.minTextContrast >= 4.5, JSON.stringify(result));
  assert.equal(result.barOverlap, false); assert.equal(result.baselineOverlap, false); assert.equal(result.labelOverlap, false); assert.deepEqual(result.clippedControls, []);
  if (result.dialog) {
    const d = result.dialog; assert(d.x >= 0 && d.y >= 0 && d.right <= d.viewport.width + 1 && d.bottom <= d.viewport.height + 1); assert(d.focusInside);
    for (let i = 0; i < 10; i++) { await page.keyboard.press(i % 2 ? 'Tab' : 'Shift+Tab'); assert(await page.getByRole('dialog').evaluate(n => n.contains(document.activeElement))); }
  }
  report.layout.push({ variant, name, ...result }); return result;
}
async function shortTaskCoverage(draft, name, layout) {
  const tasks = draft.tasks.filter(t => t.batch_id === 'B1').sort((a, b) => a.sequence - b.sequence);
  assert.deepEqual(tasks.map(t => t.sequence), [1, 2, 3]); assert(layout.shortBars >= 2);
  const bars = tasks.map(t => layout.barGeometry.find(b => b.ref === t.task_ref)); assert(bars.every(Boolean));
  for (const b of bars) {
    assert(b.x >= b.track.x && b.right <= b.track.right && b.y >= b.track.y && b.bottom <= b.track.bottom);
    assert(b.baseline && b.bottom < b.baseline.y && b.baseline.bottom <= b.track.bottom);
  }
  const proof = { variant, name, tasks: [], boundaries: [] }; report.shortTasks.push(proof);
  for (let i = 1; i < tasks.length; i++) {
    const task = tasks[i], previous = tasks[i - 1], bar = bars[i], before = bars[i - 1];
    assert.equal(previous.end, task.start); assert(task.predecessor_refs.includes(previous.task_ref));
    assert.equal(task.machine_ref, previous.machine_ref); assert.equal(task.operator_ref, previous.operator_ref);
    assert.equal(Date.parse(task.end + 'Z') - Date.parse(task.start + 'Z'), 30000);
    assert.equal(task.hours.basis, 'effective_processing_hours'); assert.equal(task.quantity, 3);
    assert(Math.abs(task.hours.total_hours * 3600 - 30) < 1e-8); assert.equal(task.duration_reason, null);
    assert(bar.width > 0 && bar.width < 5, JSON.stringify(bar));
    const gap = bar.x - before.right; assert(Math.abs(gap) < .05, JSON.stringify({ before, bar, gap }));
    assert(before.track.bottom <= bar.track.y); assert(before.baseline.bottom < bar.y);
    const target = page.locator('.tt-bar[data-task-ref="' + task.task_ref + '"]');
    await target.scrollIntoViewIfNeeded();
    assert(await target.evaluate(n => { const r = n.getBoundingClientRect(); return document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2) === n; }));
    await target.click(); assert.equal(await target.getAttribute('aria-pressed'), 'true');
    assert.equal(await page.locator('.tt-task-label[aria-pressed=true]').getAttribute('aria-label'), taskLabel(task));
    proof.tasks.push({ ref: task.task_ref, start: task.start, end: task.end, seconds: 30, width: bar.width, real_hit_and_click: true });
    proof.boundaries.push({ predecessor: previous.task_ref, successor: task.task_ref, pixel_gap: gap, separate_rows: true });
  }
  done(name + '-real-short-task-boundaries-and-hit-targets');
}
async function basic() {
  await reset(); assert.equal(await page.locator('.tt-bar').count(), 0); done('mount-does-not-select-latest-draft');
  await page.getByLabel('列表每页数量').selectOption('10'); await button('列表下一页').click(); await page.locator('[data-trial-ref]').first().waitFor();
  let e = await evidence(); assert(e.journal.some(r => r.query.page === '2' && r.query.snapshot_ref)); done('bounded-directory-snapshot-pagination');
  const draft = await create(); assert.equal(draft.base.plan_ref, refs.plan_ref); assert.equal(draft.base_identity.kind, 'official');
  const layout = await geometry('gantt-original'); assert(layout.shortBars >= 2); await shot('original-gantt');
  await shortTaskCoverage(draft, 'gantt-original', layout);
  await page.getByRole('tab', { name: '人员', exact: true }).click(); await shortTaskCoverage(draft, 'person-gantt', await geometry('person-gantt'));
  await page.getByRole('tab', { name: '批次', exact: true }).click(); await shortTaskCoverage(draft, 'batch-gantt', await geometry('batch-gantt'));
  await page.getByRole('tab', { name: '设备', exact: true }).click();
  await button('放大甘特').click(); await button('缩小甘特').click();
  await selectTask('B2', 1); assert(await button('调整此工序').isDisabled());
  await editor(); await fill(); await geometry('editor'); await shot('editor');
  const changed = await saveChange(), task = changed.tasks.find(t => t.batch_id === 'B1' && t.sequence === 1), original = draft.tasks.find(t => t.task_ref === task.task_ref);
  assert.equal(task.start, '2026-09-09T13:00:00'); assert.equal(task.end, '2026-09-09T16:00:00'); assert.deepEqual(task.original, original.original);
  assert.equal(task.machine_ref, refs.machines.M2); assert.equal(task.operator_ref, refs.operators.O2);
  e = await evidence(); const stored = e.rows.find(r => r.task_ref === task.task_ref); assert.equal(stored.current.start, task.start); assert.equal(stored.current.end, task.end);
  assert(changed.validation.issues.some(r => r.code === 'precedence_violation')); assert.equal(changed.comparison.late_count, null); done('manual-real-change-refs-and-sqlite-match');
  const rejected = await page.evaluate(data => {
    const alterations = [d => d.tasks.pop(), d => d.tasks[1].task_ref = d.tasks[0].task_ref, d => d.tasks_complete = false,
      d => d.base.plan_ref = 'a'.repeat(48), d => delete d.capacity, d => delete d.comparison.late_count];
    return alterations.map(alter => { const copy = JSON.parse(JSON.stringify(data)); alter(copy); try { TrialContract.workspace(copy); return false; } catch (_) { return true; } });
  }, changed); assert(rejected.every(Boolean)); done('incomplete-or-wrong-identity-dto-rejected');
  await page.getByRole('tab', { name: '调整记录', exact: true }).click(); await page.getByRole('table', { name: '调整记录', exact: true }).waitFor();
  assert((await page.getByRole('table', { name: '调整记录', exact: true }).innerText()).includes('13:00:00'));
  await page.getByRole('tab', { name: '资源占用', exact: true }).click(); await page.getByRole('table', { name: '资源占用', exact: true }).waitFor(); await geometry('capacity'); await shot('capacity');
  await page.getByRole('tab', { name: '约束问题', exact: true }).click(); await page.getByText('此功能尚未开通：保存只留下试调方案，不会改变正式计划。', { exact: true }).first().waitFor();
  await page.getByRole('tab', { name: '完整任务', exact: true }).click(); assert.equal(await page.getByRole('table', { name: '完整任务明细' }).locator('tbody tr').count(), 5);
  await exportsFor(changed, 'editing'); done('complete-comparison-capacity-history-and-export');
  await button('保存试调方案').click(); assert(await button('确认保存试调方案').isDisabled()); await page.getByLabel('试调方案名称', { exact: true }).fill('现场手工试调 CN ' + variant);
  await page.getByLabel('确认保存完整试调方案，冲突和未排工序一并保留').check(); await geometry('save-confirm'); await shot('save-confirm');
  await button('确认保存试调方案').click(); await page.getByRole('dialog').waitFor({ state: 'hidden' }); await ready();
  const scenario = await active(); assert(scenario.scenario_ref); assert.equal(scenario.draft_ref, draft.draft_ref); assert.equal(scenario.status, 'saved');
  assert(scenario.tasks.every(t => !t.edit_context.can_change)); assert(scenario.tasks.every(t => !draft.tasks.some(old => old.task_ref === t.task_ref)));
  assert(await button('保存试调方案').isDisabled()); assert(await button('采用方案').isDisabled());
  assert.equal(await button('采用方案').getAttribute('data-wb-disabled-reason'), '此功能尚未开通。');
  await exportsFor(scenario, 'saved');
  e = await evidence(); assert(e.scenarios.some(s => s.scenario_ref === scenario.scenario_ref && s.name === scenario.name)); done('named-scenario-saved-readonly-and-adoption-blocked');
  await page.reload(); await page.getByRole('tab', { name: '试调方案', exact: true }).click();
  await page.locator('[data-trial-ref="' + scenario.scenario_ref + '"]').getByRole('button', { name: '打开', exact: true }).click(); await ready();
  assert.deepEqual((await active()).tasks, scenario.tasks); assert.equal(await state(), null); done('cold-page-catalog-reopens-original-scenario-without-cache');
}
async function candidateAndDiscard() {
  await reset(); const draft = await create('candidate'); assert.equal(draft.base.candidate_ref, refs.candidate_ref); assert(!draft.base.plan_ref);
  assert(draft.tasks.every(t => t.source_task_ref === null)); assert(draft.tasks.every(t => t.source_row_ref));
  await button('放弃草稿').click(); assert(await button('确认放弃').isDisabled()); await button('取消').click();
  assert.equal((await active()).status, 'editing'); await button('放弃草稿').click(); await page.getByLabel('确认放弃当前指定草稿').check(); await geometry('discard-confirm'); await shot('discard-confirm');
  await button('确认放弃').click(); await page.getByRole('dialog').waitFor({ state: 'hidden' }); await ready();
  const after = await active(); assert.equal(after.status, 'discarded'); assert.equal(after.task_count, draft.task_count); assert(await button('保存试调方案').isDisabled());
  const e = await evidence(); assert.equal(e.scenarios.length, 2); assert.equal(e.rows.filter(r => r.draft_ref === draft.draft_ref).length, draft.task_count);
  done('real-candidate-identity-and-confirmed-discard-retains-all-rows');
}
async function uncertain() {
  await reset(); await create(); await editor(); await fill();
  await page.request.post(origin + '/probe/drop-next-write-reply'); await button('保存调整').click();
  await page.getByRole('region', { name: '待确认的试调提交' }).waitFor(); const key = await state(); assert(/^trial-/.test(key));
  await page.getByText('上次提交的结果还没查到，可能已经生效。请点「查询结果」，不要重复提交。', { exact: true }).waitFor();
  await page.waitForFunction(async key => (await (await fetch('/fixture/evidence')).json()).receipts.some(r => r.request_key === key), key);
  const before = (await evidence()).journal.filter(r => r.request_key === key).length;
  await page.reload(); await page.getByRole('region', { name: '待确认的试调提交' }).waitFor(); assert(await button('新增试调').isDisabled()); await shot('unknown-restored');
  assert.equal(await state(), key); await button('查询结果').click(); await ready(); assert.equal(await state(), null);
  assert.equal((await evidence()).journal.filter(r => r.request_key === key).length, before); done('lost-real-commit-reply-reloaded-key-only-and-no-rewrite');
  await reset(); await create(); await editor(); await fill(); await control('pause'); await button('保存调整').click();
  await page.waitForFunction(async () => (await (await fetch('/fixture/evidence')).json()).started);
  const paused = await state(); await page.reload(); await button('查询结果').click(); await page.getByText('上次提交的结果还没查到，可能已经生效。请点「查询结果」，不要重复提交。', { exact: true }).waitFor();
  assert.equal(await state(), paused); assert(await button('新增试调').isDisabled()); await control('release');
  await page.waitForFunction(async key => (await (await fetch('/fixture/evidence')).json()).receipts.some(r => r.request_key === key), paused);
  await button('查询结果').click(); await ready(); assert.equal((await evidence()).journal.filter(r => r.request_key === paused).length, 1);
  done('not-observed-does-not-retry-inflight-command');
}
async function staleAndScope() {
  await reset(); await create(); await editor(); await fill(); await control('expire'); await button('保存调整').click();
  await page.getByRole('alert').first().waitFor(); assert.equal(await page.getByLabel('调整开工', { exact: true }).inputValue(), '2026-09-09T13:00');
  assert.equal(await state(), null); assert.equal((await evidence()).receipts.filter(r => r.action === 'trial.change').length, 0);
  await button('刷新工序').click(); await ready(); assert.equal(await page.getByLabel('调整开工', { exact: true }).inputValue(), '2026-09-09T13:00');
  await page.getByLabel('已核对当前工序与保留输入').check(); await saveChange(); done('expired-write-context-rejected-input-preserved-explicit-recheck');
  await reset(); await page.evaluate(ref => mountTrial({ base: { plan_ref: ref }, scope: { range_start: '2026-09-10T08:00:00', range_end: '2026-09-10T09:00:00' } }), refs.plan_ref);
  await button('核对原来源').click(); await page.getByLabel('确认基于此来源新增独立草稿，正式计划保持不变').check(); await button('确认新增草稿').click();
  await page.getByRole('dialog').waitFor({ state: 'hidden' }); await page.getByText('当前显示范围没有匹配工序', { exact: true }).waitFor(); assert.equal((await active()).task_count, 5);
  await page.getByLabel('原显示范围', { exact: true }).uncheck(); await ready(); assert.equal(await page.locator('.tt-bar').count(), 5); done('initial-target-display-scope-does-not-truncate-full-dto');
  await editor(); await fill();
  await page.evaluate(() => { window.originalSetItem = Storage.prototype.setItem; Storage.prototype.setItem = function(k, v) { if (k === TrialAPI.PENDING_KEY) throw Error('fixture storage full'); return originalSetItem.call(this, k, v); }; });
  const count = (await evidence()).receipts.length; await button('保存调整').click(); await page.getByText('存不下上次操作记录，这次没有提交。请重新打开页面。', { exact: true }).first().waitFor();
  assert.equal((await evidence()).receipts.length, count); await page.evaluate(() => { Storage.prototype.setItem = originalSetItem; });
  await button('取消编辑').click(); await page.getByRole('dialog', { name: '离开前确认', exact: true }).waitFor();
  await button('放弃未保存内容并继续').click(); await button('刷新试调内容和操作记录').click(); await ready(); done('storage-unavailable-fails-before-write');
  await control('drift'); await button('刷新当前试调').click(); await ready(); assert((await active()).validation.issues.some(i => i.code === 'trial_facts_changed'));
  await page.getByRole('tab', { name: '约束问题', exact: true }).click(); await page.getByText('建草稿之后现场数据变了；草稿里的工序和对比基准没变，不能按旧数据正式采用。', { exact: true }).first().waitFor(); done('live-facts-drift-keeps-original-base-and-reports-blocker');
  await page.evaluate(() => mountTrial({ draft_ref: 'invalid' })); await page.getByRole('alert').waitFor(); assert.equal(await page.locator('.tt-bar').count(), 0); done('invalid-initial-identity-does-not-fallback');
}
async function large() {
  refs = await (await page.request.post(origin + '/fixture/reset', { data: { large: true } })).json(); await page.goto(origin);
  await button('新增试调').click(); await page.locator('.tt-source-row input[type=radio]:not(:disabled)').first().check(); await button('核对原来源').click();
  await page.getByLabel('确认基于此来源新增独立草稿，正式计划保持不变').check(); await button('确认新增草稿').click();
  await page.getByRole('dialog').waitFor({ state: 'hidden' }); await ready();
  const data = await active(); assert.equal(data.task_count, 1000); assert.equal(data.tasks.length, 1000); assert.equal(await page.locator('.tt-bar').count(), 30);
  await page.getByLabel('甘特页码', { exact: true }).fill('34'); await button('跳转甘特页').click(); await selectTask('CN-LARGE', 1000);
  await button('调整此工序').click(); await page.getByLabel('调整开工', { exact: true }).fill('2026-09-09T13:00');
  const updated = await saveChange(); assert.equal(updated.task_count, 1000); const last = updated.tasks.find(t => t.sequence === 1000);
  assert.equal(last.task_ref, data.tasks.find(t => t.sequence === 1000).task_ref); assert.equal(last.end, '2026-09-09T13:00:01');
  await page.getByRole('tab', { name: '完整任务', exact: true }).click(); assert.equal(await page.getByRole('table', { name: '完整任务明细' }).locator('tbody tr').count(), 50);
  await page.getByLabel('完整任务明细页码', { exact: true }).fill('20'); await button('跳转完整任务明细页').click();
  assert((await page.getByRole('table', { name: '完整任务明细' }).innerText()).includes('连续短工序 1000'));
  const e = await evidence(); assert.equal(e.rows.filter(r => r.draft_ref === updated.draft_ref).length, 1000);
  await exportsFor(updated, '1000-tasks-last-page');
  await shot('1000-tasks'); done('1000-real-tasks-bounded-dom-last-page-edit-and-persistent-ref');
}
async function targetHistory() {
  await reset(); await page.goto(origin + '/?history=1');
  await page.evaluate(ref => { history.replaceState({ trialTarget: { base: { plan_ref: ref } } }, '', location.href); mountTrial(history.state.trialTarget); }, refs.plan_ref);
  await button('核对原来源').click(); await page.getByLabel('确认基于此来源新增独立草稿，正式计划保持不变').check(); await button('确认新增草稿').click();
  await page.getByRole('dialog').waitFor({ state: 'hidden' }); await ready(); const draft = await active();
  await selectTask('B1', 1);
  const details = await page.getByRole('complementary', { name: '工序详情', exact: true }).innerText();
  assert(details.includes('有效加工工时')); assert(!details.includes('effective_processing_hours')); done('hours-basis-is-plain-language-with-raw-code-collapsed');
  for (const width of [1920, 1392]) for (const theme of ['light', 'dark']) {
    await page.setViewportSize({ width, height: width === 1920 ? 1080 : 924 }); await page.evaluate(theme => { document.documentElement.dataset.theme = theme; }, theme);
    await geometry('root-width-' + width + '-' + theme); await shot('root-width-' + width + '-' + theme);
  }
  await page.setViewportSize({ width: 1392, height: 924 }); await page.evaluate(() => { document.documentElement.dataset.theme = 'dark'; });
  assert.deepEqual(await page.evaluate(() => history.state.trialTarget), { draft_ref: draft.draft_ref });
  const creates = (await evidence()).receipts.filter(r => r.action === 'trial.create').length;
  await page.reload(); await ready(); assert.equal((await active()).draft_ref, draft.draft_ref); assert.equal(await page.getByRole('dialog').count(), 0);
  assert.equal((await evidence()).receipts.filter(r => r.action === 'trial.create').length, creates);
  await page.locator('[data-trial-ref="' + refs.drafts[3] + '"]').getByRole('button', { name: '打开', exact: true }).click(); await ready();
  assert.deepEqual(await page.evaluate(() => history.state.trialTarget), { draft_ref: refs.drafts[3] }); await page.reload(); await ready();
  assert.equal((await active()).draft_ref, refs.drafts[3]); done('base-create-and-directory-open-replace-history-with-original-draft');
  await button('保存试调方案').click(); await page.getByLabel('试调方案名称', { exact: true }).fill('刷新后仍为原场景'); await page.getByLabel('确认保存完整试调方案，冲突和未排工序一并保留').check();
  await button('确认保存试调方案').click(); await page.getByRole('dialog').waitFor({ state: 'hidden' }); await ready(); const scenario = await active();
  assert.deepEqual(await page.evaluate(() => history.state.trialTarget), { scenario_ref: scenario.scenario_ref }); await page.reload(); await ready();
  assert.equal((await active()).scenario_ref, scenario.scenario_ref); done('saved-scenario-refresh-retains-exact-scenario-ref');
  await page.evaluate(() => { window.failTargetChange = true; }); await button('新增试调').click(); await button('核对原来源').click();
  await page.getByLabel('确认基于此来源新增独立草稿，正式计划保持不变').check(); await button('确认新增草稿').click(); await page.getByRole('dialog').waitFor({ state: 'hidden' }); await ready();
  await page.getByText('试调记录已定位，但页面地址没有更新成功。记录还在试调列表里，没有重复写入。', { exact: true }).waitFor();
  assert.equal(await state(), null); assert.equal((await evidence()).receipts.filter(r => r.action === 'trial.create').length, creates + 1); done('target-callback-failure-does-not-erase-commit-or-reissue');
}
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve)); let browser;
  if (process.env.TRIAL_WIDGET_PREVIEW === '1') {
    const ready = { url: 'http://127.0.0.1:' + server.address().port, backend, root: output, source_only: true, production_database: false };
    fs.writeFileSync(path.join(output, 'preview-ready.json'), JSON.stringify(ready, null, 2)); console.log(JSON.stringify(ready)); return;
  }
  try {
    browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true, args: ['--disable-background-networking'] });
    report.browser = browser.version(); assert(report.browser.startsWith('109.')); origin = 'http://127.0.0.1:' + server.address().port;
    for (const width of (targetOnly ? [1392] : [1920, 1392])) for (const theme of (targetOnly ? ['dark'] : ['light', 'dark'])) {
      variant = width + '-' + theme; const row = { variant, width, height: width === 1920 ? 1080 : 924, passed: false }; report.variants.push(row);
      const context = await browser.newContext({ viewport: { width, height: row.height }, timezoneId: 'America/New_York', acceptDownloads: true });
      await context.addInitScript(theme => { localStorage.setItem('aps_theme', theme); localStorage.setItem('aps_kit_theme', theme); }, theme);
      page = await context.newPage(); page.setDefaultTimeout(15000);
      page.on('pageerror', error => report.errors.push(error.message)); page.on('dialog', dialog => {
        if (dialog.type() === 'beforeunload') { report.nativeLeaveConfirmations = (report.nativeLeaveConfirmations || 0) + 1; dialog.accept(); }
        else { report.dialogs.push(dialog.type()); dialog.dismiss(); }
      });
      await page.route('**/*', route => { if (!route.request().url().startsWith(origin + '/')) { report.external.push(route.request().url()); return route.abort(); } return route.continue(); });
      try {
        if (exportOnly) { await exportRoundTrip(); if (width === 1392 && theme === 'dark') await large(); }
        else if (targetOnly) await targetHistory();
        else { await basic(); await candidateAndDiscard(); await uncertain(); await staleAndScope(); if (width === 1392 && theme === 'dark') { await large(); await targetHistory(); } }
        row.passed = true;
      }
      catch (error) { row.error = error.stack; await shot('FAILED'); }
      finally { await control('release'); await context.close(); }
    }
    assert.deepEqual(report.errors, []); assert.deepEqual(report.external, []); assert.deepEqual(report.dialogs, []);
    assert(report.variants.every(row => row.passed), JSON.stringify(report.variants.filter(row => !row.passed)));
    console.log(JSON.stringify({ browser: report.browser, checks: report.checks.length, variants: report.variants.length, output }));
  } finally { if (browser) await browser.close(); server.close(); fs.writeFileSync(path.join(output, 'trial-widgets.json'), JSON.stringify(report, null, 2)); }
})().catch(error => { console.error(error.stack); process.exitCode = 1; });
