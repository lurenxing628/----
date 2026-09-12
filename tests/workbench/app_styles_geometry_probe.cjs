'use strict';
// Real browser validation of source CSS over the frozen imported CSS stack; no business writes.
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), http = require('node:http'), crypto = require('node:crypto');
const { chromium } = require('playwright');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), output = process.argv[2];
if (!output || path.resolve(output).startsWith(root + path.sep)) throw new Error('Pass an isolated artifact directory outside the repository');
fs.mkdirSync(output, { recursive: true });
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
const cssNames = ['00-tokens.css', '10-shell.css', '20-controls.css', '21-table-frame.css', '30-workspaces.css'];
const sources = cssNames.map(name => ({ name, source: 'frontend/workbench/app/styles/' + name,
  bytes: fs.readFileSync(path.join(root, 'frontend/workbench/app/styles', name)) }));
const jsx = 'frontend/workbench/app/WorkbenchControlStyles.jsx', jsxBytes = fs.readFileSync(path.join(root, jsx));
const shadows = 'frontend/workbench/app/WorkbenchScrollShadows.js', shadowBytes = fs.readFileSync(path.join(root, shadows));
const compiled = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'),
  sources: [{ path: jsx, code: jsxBytes.toString() }], check_combined: true }).outputs[0].code;
const records = new Map(manifest.files.map(item => [item.path, item]));
const groups = Array.from({ length: 6 }, (_, group) => '<div class="nav-group"><div class="nav-group-title">工作组 ' + (group + 1) + '</div>' +
  Array.from({ length: group < 2 ? 3 : 2 }, (_, item) => '<a class="nav-item" href="#"><span class="nav-label">工作入口 ' + group + '-' + item + '</span></a>').join('') + '</div>').join('');
const rows = Array.from({ length: 40 }, (_, row) => '<tr><td class="wb-col-key">批次 ' + row + '</td>' +
  Array.from({ length: 8 }, (_, cell) => '<td>加工资料 ' + row + '-' + cell + '</td>').join('') +
  '<td class="wb-col-actions"><button class="mini" onclick="window.lastAction=' + row + '">查看 / 编辑</button></td></tr>').join('');
const header = '<th class="wb-col-key" scope="col">批次号</th>' +
  Array.from({ length: 8 }, (_, cell) => '<th scope="col">列 ' + cell + '<button class="wb-th-action" aria-label="筛选列 ' + cell + '">筛选</button></th>').join('') +
  '<th class="wb-col-actions" scope="col">操作</th>';
const styles = manifest.styles.filter(name => name.startsWith('workbench/prototype/')).map(name => '<link rel="stylesheet" href="/static/' + name + '">').join('') +
  sources.map(item => '<link rel="stylesheet" href="/candidate/' + item.name + '">').join('');
const vendors = manifest.scripts.filter(name => name.startsWith('workbench/vendor/') || name.startsWith('workbench/assets/foundation-'));
const html = '<!doctype html><html lang="zh-CN" data-theme="light"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' + styles +
  '</head><body class="aps-workbench"><div class="app-container operations-shell"><aside class="sidebar"><div class="sidebar-header">APS 智能排产</div><nav class="sidebar-nav">' + groups +
  '</nav></aside><div class="main-content"><header class="top-header"><h2 class="top-title">批次管理</h2><div class="header-controls"><button class="hdr-pill">切换深色</button></div></header>' +
  '<main class="page-content"><div class="plana"><h2>表格与控件基座</h2><div class="toolbar"><button class="btn primary">新增批次</button><label><input id="hollow-radio" type="radio" name="sample"> 未选中</label>' +
  '<label><input id="filled-radio" type="radio" name="sample" checked> 已选中</label><input id="date" type="date" value="2026-09-12" aria-label="日期"></div>' +
  '<div class="wb-table-frame" data-sticky-head data-sticky-actions style="--wb-table-min:1500px"><table class="wb-table"><caption class="wb-visually-hidden">批次列表</caption><thead><tr>' + header +
  '</tr></thead><tbody>' + rows + '</tbody></table></div><div id="icons-root"></div></div></main></div></div>' +
  vendors.map(name => '<script src="/static/' + name + '"></script>').join('') + '<script src="/icons.js"></script>' +
  '<script>ReactDOM.createRoot(document.getElementById("icons-root")).render(React.createElement(WorkbenchControlStyles));</script>' +
  '<script src="/scroll-shadows.js"></script><script>WorkbenchScrollShadows.attach(document.querySelector(".main-content"));</script></body></html>';
const server = http.createServer((request, response) => {
  const pathname = new URL(request.url, 'http://fixture').pathname;
  if (pathname === '/favicon.ico') { response.writeHead(204); response.end(); return; }
  if (pathname === '/') { response.setHeader('Content-Type', 'text/html;charset=utf-8'); response.end(html); return; }
  if (pathname === '/icons.js') { response.setHeader('Content-Type', 'application/javascript'); response.end(compiled); return; }
  if (pathname === '/scroll-shadows.js') { response.setHeader('Content-Type', 'application/javascript'); response.end(shadowBytes); return; }
  const source = sources.find(item => pathname === '/candidate/' + item.name);
  if (source) { response.setHeader('Content-Type', 'text/css'); response.end(source.bytes); return; }
  const record = records.get(pathname.slice('/static/'.length));
  if (pathname.startsWith('/static/') && record) { response.setHeader('Content-Type', record.mime); response.end(fs.readFileSync(path.join(root, 'static', record.path))); return; }
  response.writeHead(404); response.end();
});
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const report = { scope: 'source-CSS-over-frozen-prototype-assets', build_id: manifest.build_id, source_hashes: sources.map(item => ({ path: item.source, sha256: hash(item.bytes) })),
  global_build: false, production_writes: false, cases: [], errors: [], external: [] };
report.source_hashes.push({ path: jsx, sha256: hash(jsxBytes) }, { path: shadows, sha256: hash(shadowBytes) });
let browser;
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const origin = 'http://127.0.0.1:' + server.address().port;
  try {
    browser = await chromium.launch({ headless: true, executablePath: process.env.WORKBENCH_BROWSER });
    report.browser = browser.version();
    for (const viewport of [{ width: 1280, height: 720 }, { width: 1366, height: 768 }, { width: 1920, height: 1080 }]) for (const theme of ['light', 'dark']) {
      const page = await browser.newPage({ viewport }), name = viewport.width + '-' + theme;
      page.on('pageerror', error => report.errors.push({ name, message: error.message }));
      page.on('request', request => { if (!request.url().startsWith(origin)) report.external.push(request.url()); });
      await page.goto(origin); await page.waitForFunction(() => document.body.dataset.workbenchControlIcons === 'ready');
      await page.evaluate(value => { document.documentElement.dataset.theme = value; }, theme);
      await page.evaluate(() => document.fonts.ready);
      const measure = () => page.evaluate(() => {
        const rect = selector => { const r = document.querySelector(selector).getBoundingClientRect(); return { left: r.left, right: r.right, top: r.top, bottom: r.bottom, height: r.height }; };
        const frame = document.querySelector('.wb-table-frame'), td = frame.querySelector('tbody td');
        return { frame: rect('.wb-table-frame'), head: rect('.wb-table thead th'), key: rect('.wb-table tbody .wb-col-key'), actions: rect('.wb-table tbody .wb-col-actions'),
          header: rect('.top-header'), lastNav: rect('.nav-group:last-child .nav-item:last-child'), pageWidth: document.documentElement.scrollWidth,
          font: getComputedStyle(td).fontSize, padding: getComputedStyle(td).padding, frameClient: frame.clientHeight, frameScroll: frame.scrollHeight,
          radioBg: getComputedStyle(document.querySelector('#hollow-radio')).backgroundColor, radioFill: getComputedStyle(document.querySelector('#hollow-radio'), '::before').visibility,
          radioRadius: getComputedStyle(document.querySelector('#hollow-radio')).borderRadius, dateIcon: getComputedStyle(document.querySelector('#date')).backgroundImage,
          buttonHeight: document.querySelector('.btn').getBoundingClientRect().height, text: getComputedStyle(document.body).color,
          overflows: frame.scrollWidth > frame.clientWidth + 1, overflowLeft: frame.hasAttribute('data-overflow-left'), overflowRight: frame.hasAttribute('data-overflow-right'),
          actionsShadow: getComputedStyle(frame.querySelector('tbody .wb-col-actions')).boxShadow, keyShadow: getComputedStyle(frame.querySelector('tbody .wb-col-key')).boxShadow,
          headWordBreak: getComputedStyle(frame.querySelector('thead th')).wordBreak };
      });
      const before = await measure();
      assert(before.pageWidth <= viewport.width, name + ' root overflow');
      assert(before.lastNav.bottom <= viewport.height, name + ' last nav clipped');
      assert.equal(before.header.height, 60); assert.equal(before.buttonHeight, 32);
      assert(before.actions.right <= before.frame.right && before.actions.left >= before.frame.left, name + ' actions inaccessible');
      assert(before.frameScroll > before.frameClient, name + ' must exercise vertical scroll');
      assert.equal(before.radioFill, 'hidden'); assert.equal(before.radioRadius, '50%');
      assert(before.dateIcon.startsWith('url("data:image/svg+xml,')); assert.notEqual(before.text, '');
      // Hidden columns announce themselves: the shadow follows the overflow flags and disappears at the scroll end.
      const layered = shadow => (shadow.match(/rgba?\(/g) || []).length >= 2;
      assert.equal(before.headWordBreak, 'keep-all', name + ' header labels must not break inside CJK words');
      assert.equal(before.overflowRight, before.overflows, name + ' right overflow flag before scrolling'); assert(!before.overflowLeft, name + ' no left overflow before scrolling');
      assert.equal(layered(before.actionsShadow), before.overflows, name + ' the covering column shadows only hidden cells'); assert(!layered(before.keyShadow), name + ' key column shadow before scrolling');
      await page.locator('.wb-table tbody tr:first-child button').click();
      assert.equal(await page.evaluate(() => window.lastAction), 0);
      await page.locator('.wb-table-frame').evaluate(frame => { frame.scrollTop = 250; frame.scrollLeft = 320; });
      const after = await measure();
      assert(Math.abs(after.head.top - before.head.top) <= 1, name + ' head did not stick');
      assert(Math.abs(after.key.left - before.key.left) <= 1, name + ' key did not stick');
      assert(Math.abs(after.actions.right - before.actions.right) <= 1, name + ' actions did not stick');
      let middle = null, end = null;
      if (before.overflows) {
        await page.waitForFunction(() => document.querySelector('.wb-table-frame').hasAttribute('data-overflow-left'));
        middle = await measure();
        assert(middle.overflowLeft && middle.overflowRight && layered(middle.actionsShadow) && layered(middle.keyShadow), name + ' both columns shadow mid-scroll');
        await page.locator('.wb-table-frame').evaluate(frame => { frame.scrollLeft = frame.scrollWidth; });
        await page.waitForFunction(() => !document.querySelector('.wb-table-frame').hasAttribute('data-overflow-right'));
        end = await measure();
        assert(end.overflowLeft && !layered(end.actionsShadow) && layered(end.keyShadow), name + ' shadow must leave the actions column at the scroll end');
        await page.locator('.wb-table-frame').evaluate(frame => { frame.scrollLeft = 320; });
      }
      const topmost = await page.evaluate(() => Array.from(document.querySelectorAll('.wb-table thead :is(.wb-col-key,.wb-col-actions)')).every(cell => {
        const r = cell.getBoundingClientRect(); return cell.contains(document.elementFromPoint(r.left + 5, r.top + 5));
      }));
      assert(topmost, name + ' scrolling cells paint over corner header');
      await page.evaluate(() => { document.documentElement.dataset.density = 'compact'; });
      const compact = await measure(); assert.equal(compact.font, before.font); assert.notEqual(compact.padding, before.padding);
      const layers = await page.evaluate(() => {
        const hidden = document.createElement('button'); hidden.className = 'btn primary'; hidden.hidden = true;
        document.body.appendChild(hidden); const hiddenDisplay = getComputedStyle(hidden).display; hidden.remove();
        const dialog = document.createElement('div'); dialog.className = 'plana';
        dialog.innerHTML = '<div class="modal-bg"><section class="modal">编辑器</section></div>'; document.body.appendChild(dialog);
        const ordinary = dialog.firstChild.contains(document.elementFromPoint(300, 20));
        const guard = document.createElement('div'); guard.className = 'plana wb-guard-host';
        guard.innerHTML = '<div class="modal-bg"><section class="modal">未保存草稿</section></div>'; document.body.appendChild(guard);
        const confirmation = guard.firstChild.contains(document.elementFromPoint(300, 20));
        guard.remove(); dialog.remove(); return { hiddenDisplay, ordinary, confirmation };
      });
      assert.equal(layers.hiddenDisplay, 'none'); assert(layers.ordinary, name + ' header above dialog'); assert(layers.confirmation, name + ' dialog above dirty guard');
      await page.screenshot({ path: path.join(output, name + '.png') });
      report.cases.push({ name, passed: true, before, after, middle, end, compact, layers }); await page.close();
    }
    assert.deepEqual(report.errors, []); assert.deepEqual(report.external, []);
  } finally {
    if (browser) await browser.close(); server.close();
    report.source_drift = report.source_hashes.filter(item => hash(fs.readFileSync(path.join(root, item.path))) !== item.sha256);
    fs.writeFileSync(path.join(output, 'app-styles-geometry.json'), JSON.stringify(report, null, 2));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
