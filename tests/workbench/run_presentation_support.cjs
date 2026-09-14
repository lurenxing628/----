/* BY-only in-memory asset compilation and read-only proxy. No build/static writes. */
'use strict';
const UI = require('./run_ui_source.cjs');
const assert = require('node:assert/strict'), fs = require('node:fs'), http = require('node:http'), path = require('node:path'), crypto = require('node:crypto');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..');
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
function serve(backend, report, output) {
  const order = JSON.parse(fs.readFileSync(path.join(root, 'scripts/workbench/build-order.json')));
  const live = order.live;
  for (const name of ['RunBaselineAPI.js', 'RunBaselineModel.js', 'RunBaselineControls.jsx']) {
    assert(live.indexOf(name) > live.indexOf('RunCandidateControls.jsx') && live.indexOf(name) < live.indexOf('RunCandidateGantt.jsx'), 'Baseline dependency must be integrated in the real build order: ' + name);
  }
  const sources = [order.theme, ...live].map(name => ({ path: 'frontend/workbench/app/' + name,
    code: fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8') }));
  for (const source of sources) { const target = path.join(output, 'sources', source.path); fs.mkdirSync(path.dirname(target), { recursive: true }); fs.writeFileSync(target, source.code); }
  const compiled = compile({ babel_path: path.join(root, 'frontend/workbench/prototype', order.babel.path), sources, check_combined: true });
  report.sources = sources.map(row => ({ path: row.path, sha256: hash(row.code) }));
  const scripts = new Map(compiled.outputs.map((row, i) => ['/static/workbench/app/' + [order.theme, ...live][i].replace(/\.jsx$/, '.js'), row.code]));
  const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
  const assets = new Map(manifest.files.map(row => {
    const bytes = fs.readFileSync(path.join(root, 'static', row.path));
    assert.equal(hash(bytes), row.sha256, 'Concurrent build changed static asset: ' + row.path);
    return ['/static/' + row.path, { ...row, bytes }];
  }));
  report.style_build_id = manifest.build_id;
  report.compile = { global_build: false, target: 'chrome109', full_current_shell: true, sources: sources.length, build_order_sha256: hash(JSON.stringify(order)) };
  const boot = JSON.parse(fs.readFileSync(path.join(output, 'boot-fixture.json'), 'utf8'));
  report.boot = boot;
  const html = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
    '<link rel="icon" href="/static/' + manifest.icon + '"><script src="/static/' + manifest.theme_script + '"></script>' +
    manifest.styles.map(file => '<link rel="stylesheet" href="/static/' + file + '">').join('') + UI.styles(report, output) + '</head><body class="aps-workbench"><div id="root"></div>' +
    '<script id="workbench-boot" type="application/json">' + JSON.stringify(boot) + '</script>' +
    manifest.scripts.filter(file => !file.startsWith('workbench/app/')).concat(live.map(name => 'workbench/app/' + name.replace(/\.jsx$/, '.js')))
      .map(file => '<script src="/static/' + file + '"></script>').join('') + '</body></html>';
  return http.createServer((req, res) => {
    const pathname = new URL(req.url, 'http://fixture').pathname;
    if (pathname.startsWith('/api/') || pathname.startsWith('/fixture/')) {
      assert.equal(req.method, 'GET', 'Presentation probe must not write through HTTP');
      const upstream = http.request(backend + req.url, { method: req.method, headers: req.headers }, response => { res.writeHead(response.statusCode, response.headers); response.pipe(res); });
      upstream.on('error', error => { res.writeHead(502); res.end(error.message); }); req.pipe(upstream); return;
    }
    if (pathname === '/workbench') { res.setHeader('Content-Type', 'text/html;charset=utf-8'); res.end(html); return; }
    if (scripts.has(pathname)) { res.setHeader('Content-Type', 'application/javascript'); res.end(scripts.get(pathname)); return; }
    const asset = assets.get(pathname); if (!asset) { res.writeHead(404); res.end(); return; }
    res.setHeader('Content-Type', asset.mime); res.end(asset.bytes);
  });
}
async function layout(page) {
  return page.evaluate(() => {
    const rect = n => { const r = n.getBoundingClientRect(); return { x: r.x, y: r.y, width: r.width, height: r.height, bottom: r.bottom }; };
    const canvas = document.querySelector('[data-candidate-lane]'), scope = document.querySelector('.rc-scope');
    let painted = 0;
    if (canvas) { const data = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
      for (let i = 3; i < data.length; i += 4) if (data[i]) painted++; }
    const relevant = '[data-run-candidate-workspace], [data-run-history-workspace], [aria-label="这次排产记录"]';
    const body = document.querySelector(relevant), controls = [...body.querySelectorAll('button,select,input')].filter(n => n.getClientRects().length);
    const table = body.querySelector('table');
    return { viewport: { width: innerWidth, height: innerHeight }, scrollY, canvas: canvas && rect(canvas), painted,
      preview: body.querySelector('.rc-gantt') && rect(body.querySelector('.rc-gantt')),
      scope: scope && { borderLeft: getComputedStyle(scope).borderLeftWidth, background: getComputedStyle(scope).backgroundColor },
      body: rect(body), table: table && rect(table), rowHeights: table && [...table.tBodies[0].rows].map(n => rect(n).height),
      overflow: document.documentElement.scrollWidth > innerWidth,
      controlClipping: controls.filter(n => n.scrollWidth > n.clientWidth + 1).map(n => n.getAttribute('aria-label') || n.textContent),
      cellClipping: table && [...table.querySelectorAll('th,td')].filter(n => n.scrollWidth > n.clientWidth + 1).map(n => n.textContent),
      fontSize: getComputedStyle(body).fontSize,
      border: table && getComputedStyle(table.tBodies[0].rows[0].cells[0]).borderBottomWidth,
      defaultIds: [...body.querySelectorAll('td code')].filter(n => n.checkVisibility ? n.checkVisibility() : n.getBoundingClientRect().height > 0).length };
  });
}
async function contrast(page) {
  return page.evaluate(() => {
    const rgba = v => { const p = v.match(/[\d.]+/g).map(Number); return [...p.slice(0, 3), p.length > 3 ? p[3] : 1]; };
    const blend = (fg, bg) => fg.slice(0, 3).map((v, i) => v * fg[3] + bg[i] * (1 - fg[3]));
    const background = el => { const c = rgba(getComputedStyle(el).backgroundColor); return c[3] === 1 ? c.slice(0, 3) : blend(c, el.parentElement ? background(el.parentElement) : [255, 255, 255]); };
    const luminance = c => c.map(v => v / 255).map(v => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4).reduce((s, v, i) => s + v * [.2126, .7152, .0722][i], 0);
    const results = [], walker = document.createTreeWalker(document.querySelector('.page-content'), NodeFilter.SHOW_TEXT);
    let text;
    while ((text = walker.nextNode())) {
      const el = text.parentElement;
      if (!text.textContent.trim() || el.closest('style,script,svg,option,button:disabled,select')) continue;
      const range = document.createRange(); range.selectNodeContents(text);
      if (![...range.getClientRects()].some(r => r.width && r.height && r.bottom > 0 && r.top < innerHeight)) continue;
      const style = getComputedStyle(el), bg = background(el), fg = blend(rgba(style.color), bg), a = luminance(bg), b = luminance(fg);
      results.push({ text: text.textContent.trim().slice(0, 80), ratio: (Math.max(a, b) + .05) / (Math.min(a, b) + .05) });
    }
    return results;
  });
}
module.exports = { serve, layout, contrast };
