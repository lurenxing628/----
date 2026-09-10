'use strict';
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const http = require('node:http');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');

const sha = value => crypto.createHash('sha256').update(value).digest('hex');
const repo = path.resolve(__dirname, '../..');
const origin = path.join(repo, '\u524d\u7aef\u8bbe\u8ba1');
const roadmap = path.join(repo, '.codestable/roadmap/workbench-prototype-migration');
const json = (file, value) => fs.writeFileSync(file, JSON.stringify(value, null, 2) + '\n');

function snapshot(root, bytes = false) {
  const result = {};
  function visit(dir) {
    for (const item of fs.readdirSync(dir, {withFileTypes: true}).sort((a, b) => a.name.localeCompare(b.name))) {
      const file = path.join(dir, item.name);
      if (item.isDirectory()) visit(file);
      else if (item.isFile()) {
        const raw = fs.readFileSync(file), stat = fs.statSync(file);
        result[path.relative(root, file)] = {sha256: sha(raw), bytes: raw.length, mode: stat.mode & 0o777,
          ...(bytes ? {raw} : {})};
      } else throw new Error('Unsupported source entry: ' + file);
    }
  }
  visit(root);
  return result;
}

function frozenPlanning() {
  const files = snapshot(path.join(roadmap, 'acceptance-planning'));
  const raw = fs.readFileSync(path.join(roadmap, 'workbench-capabilities.json'));
  return {planning: files, capabilities: {sha256: sha(raw), bytes: raw.length}};
}

async function start() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'aps-detail008-prototype-'));
  fs.mkdirSync(path.join(root, 'screenshots'));
  const captured = snapshot(origin, true);
  const before = Object.fromEntries(Object.entries(captured).map(([file, row]) => [file,
    {sha256: row.sha256, bytes: row.bytes, mode: row.mode}]));
  const planningBefore = frozenPlanning();
  const report = {entry: 'original_prototype_only', origin, root, started: new Date().toISOString(),
    production_verification: 'not_run', manual_detail_open_calls: 0, entries: [], controls: [], drawers: [],
    steps: [], served: [], external: [], errors: [], screenshots: []};
  report.probe_sources = Object.fromEntries(['support', 'probe', 'links'].map(name => {
    const file = path.join(__dirname, 'detail008_prototype_' + name + '.cjs');
    const raw = fs.readFileSync(file);
    assert(!/APSDetail\s*\.\s*open\s*\(/.test(raw.toString()), 'Do not invoke the detail API in this probe');
    return [path.relative(repo, file), {sha256: sha(raw), bytes: raw.length}];
  }));
  json(path.join(root, 'source-before.json'), before);
  json(path.join(root, 'planning-before.json'), planningBefore);
  const mime = {'.html': 'text/html', '.jsx': 'text/plain', '.js': 'application/javascript', '.css': 'text/css',
    '.svg': 'image/svg+xml', '.png': 'image/png', '.woff2': 'font/woff2', '.woff': 'font/woff', '.json': 'application/json'};
  const server = http.createServer((request, response) => {
    const pathname = decodeURIComponent(new URL(request.url, 'http://127.0.0.1').pathname);
    const file = pathname.replace(/^\/+/, '');
    const row = captured[file];
    const status = !['GET', 'HEAD'].includes(request.method) ? 405 : row ? 200 : 404;
    report.served.push({method: request.method, path: file, status, sha256: row?.sha256});
    response.writeHead(status, {'Content-Type': mime[path.extname(file)] || 'application/octet-stream',
      'Cache-Control': 'no-store'});
    response.end(status === 200 && request.method === 'GET' ? row.raw : undefined);
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const base = 'http://127.0.0.1:' + server.address().port;
  report.base = base;
  console.log('DETAIL008_ROOT ' + root);
  return {root, base, report, captured,
    save() { json(path.join(root, 'reachability.json'), report); },
    async stop() {
      await new Promise(resolve => server.close(resolve));
      report.server_closed = true;
      const after = snapshot(origin), planningAfter = frozenPlanning();
      json(path.join(root, 'source-after.json'), after);
      json(path.join(root, 'planning-after.json'), planningAfter);
      report.source_changes = [...new Set([...Object.keys(before), ...Object.keys(after)])]
        .filter(key => JSON.stringify(before[key]) !== JSON.stringify(after[key]));
      report.planning_unchanged = JSON.stringify(planningBefore) === JSON.stringify(planningAfter);
      report.source_manifest_sha256 = sha(fs.readFileSync(path.join(root, 'source-before.json')));
      report.finished = new Date().toISOString();
      this.save();
      assert.deepEqual(report.source_changes, []);
      assert(report.planning_unchanged);
    }};
}

async function inspect(page) {
  return page.evaluate(() => {
    const visible = node => !!node.getClientRects().length && getComputedStyle(node).visibility !== 'hidden';
    const R = window.APSDetail?.RECORDS || {};
    const controls = [...document.querySelectorAll('a,button,[role="button"],summary,input,select,label')].filter(visible).map(node => ({
      tag: node.tagName, text: (node.innerText || node.textContent || '').trim(), label: node.getAttribute('aria-label'),
      title: node.getAttribute('title'), href: node.getAttribute('href'), class: node.className,
      data: {...node.dataset}, disabled: !!node.disabled, name: node.name, value: node.value, type: node.type,
      known_type: R[node.textContent.trim()]?.type || null,
      native_part_row: !!node.closest('tr[data-code]')}));
    return {url: location.href, title: document.querySelector('.top-title')?.innerText,
      heading: [...document.querySelectorAll('h1,h2,h3')].filter(visible).map(node => node.innerText),
      body: document.body.innerText, controls,
      drawer_count: document.querySelectorAll('.apsd-panel').length,
      scripts: [...document.scripts].filter(node => node.src).map(node => node.src)};
  });
}

async function shot(env, page, name) {
  await page.evaluate(() => document.fonts.ready);
  await page.locator('.apsd-panel,.apsd-backdrop').evaluateAll(async nodes => {
    for (const node of nodes) await Promise.all(node.getAnimations().map(animation => animation.finished));
  });
  const file = path.join(env.root, 'screenshots', name + '.png');
  await page.screenshot({path: file});
  env.report.screenshots.push({name, file});
  return file;
}

module.exports = {start, inspect, shot, sha, json};
