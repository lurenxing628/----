'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), crypto = require('node:crypto');
const {PNG} = require('pngjs');

const NAV = [
  ['process', '基础资料'], ['batches', '批次管理'], ['run', '执行排产'], ['analysis', '选择排产方案'],
  ['trial', '方案试调'], ['gantt', '设备 / 人员 / 批次甘特'], ['field', '现场记录'], ['fieldgantt', '现场实际甘特'],
  ['review', '执行复盘'], ['reports', '报表中心'], ['calib', '工时定额校准'], ['dashboard', '值班台'],
  ['basedata', '主数据总览'], ['system', '系统管理'],
];
const SIDEBAR = ['dashboard', 'process', 'basedata', 'batches', 'run', 'analysis', 'trial', 'field', 'fieldgantt', 'reports', 'calib', 'system']
  .map(view => NAV.find(row => row[0] === view));
const PARENT = {gantt: 'analysis', delay: 'analysis', review: 'reports'};
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
function write(file, value) { fs.writeFileSync(file, JSON.stringify(value, null, 2) + '\n'); }

class Record {
  constructor(root, ready) {
    this.root = root; this.ready = ready; this.pending = []; this.requestIndex = 0; this.pageIndex = 0; this.contextIndex = 0;
    this.assets = JSON.parse(fs.readFileSync(ready.assets.frozen_manifest));
    this.assetMap = new Map(this.assets.files.map(row => ['/static/' + row.path, row]));
    this.data = {scope: 'real Main shell; injected faults are separate, not business success evidence',
      expected: {first_views: 56, faults: 16, host_restarts: 4}, complete: false, cases: [], screenshots: [],
      normal_errors: [], fault_events: [], external_requests: [], api_responses: [], requests: [],
      served_assets: [], trusted_keys: [], input_states: [], scroll_actions: [], restoration_observations: [], assertions: 0};
    fs.mkdirSync(path.join(root, 'foundation-responses'));
  }
  save() { write(path.join(this.root, 'foundation-browser.json'), this.data); }
  equal(value, expected, message) { this.data.assertions++; assert.deepEqual(value, expected, message); }
  ok(value, message) { this.data.assertions++; assert.ok(value, message); }
  error(page, kind, detail) {
    const row = {state: page.foundationState, page_id: page.foundationPageId, phase: page.foundationPhase, kind, ...detail};
    (page.foundationPhase === 'normal' ? this.data.normal_errors : this.data.fault_events).push(row);
  }
  async context(browser, state, phase = 'normal') {
    const context = await browser.newContext({viewport: {width: state.width, height: state.height}, colorScheme: state.theme});
    context.foundationContextId = ++this.contextIndex;
    const metadata = source => ({state: state.id, page_id: source.page.foundationPageId, phase: source.page.foundationPhase});
    await context.exposeBinding('__foundationKey', (source, row) => this.data.trusted_keys.push({...metadata(source), ...row}));
    await context.exposeBinding('__foundationInput', (source, row) => this.data.input_states.push({...metadata(source), ...row}));
    await context.addInitScript(() => {
      document.addEventListener('keydown', event => {
        const target = event.target;
        if (target instanceof HTMLInputElement && target.type === 'search') {
          window.__foundationKey({key: event.key, trusted: event.isTrusted, label: target.getAttribute('aria-label'),
            value_before: target.value, selection_start: target.selectionStart, selection_end: target.selectionEnd});
        }
      }, true);
      document.addEventListener('input', event => {
        const target = event.target;
        if (!(target instanceof HTMLInputElement) || target.type !== 'search') return;
        const input = {data: event.data, input_type: event.inputType, trusted: event.isTrusted,
          value_at_event: target.value, label: target.getAttribute('aria-label')};
        requestAnimationFrame(() => window.__foundationInput({...input,
          query: history.state && history.state.workbench && history.state.workbench.context.query,
          original_connected: target.isConnected, original_focused: document.activeElement === target,
          gantt_count: document.querySelectorAll('[data-plan-gantt]').length,
          searchboxes: Array.from(document.querySelectorAll('input[type="search"]')).map(node => ({value: node.value,
            label: node.getAttribute('aria-label'), focused: node === document.activeElement,
            selection_start: node.selectionStart, selection_end: node.selectionEnd}))}));
      }, true);
    });
    return this.page(context, state, phase);
  }
  async page(context, state, phase = 'normal') {
    const page = await context.newPage();
    page.foundationPageId = ++this.pageIndex;
    page.foundationState = state.id; page.foundationPhase = phase; page.setDefaultTimeout(12000);
    await this.largeAssetCapture(context, page, state);
    await page.route('**/*', route => {
      const url = route.request().url();
      if (!url.startsWith(this.ready.url + '/') && !/^(data:|blob:)/.test(url)) {
        this.data.external_requests.push({state: state.id, page_id: page.foundationPageId, url}); return route.abort();
      }
      return route.continue();
    });
    page.on('pageerror', error => this.error(page, 'pageerror', {message: String(error)}));
    page.on('console', message => { if (message.type() === 'error') this.error(page, 'console', {message: message.text()}); });
    page.on('requestfailed', request => {
      const failure = request.failure();
      if (failure && failure.errorText === 'net::ERR_ABORTED' && request.method() === 'GET') {
        this.data.requests.push({state: state.id, page_id: page.foundationPageId, phase: page.foundationPhase, url: request.url(), method: 'GET', aborted_read: true});
      } else this.error(page, 'requestfailed', {url: request.url(), method: request.method(), failure});
    });
    page.on('response', response => {
      if (response.status() >= 400) this.error(page, 'http', {url: response.url(), status: response.status()});
    });
    page.on('requestfinished', request => {
      const phaseAtRequest = page.foundationPhase, index = ++this.requestIndex;
      this.pending.push((async () => {
        const response = await request.response();
        if (!response) throw new Error('Finished browser request has no response: ' + request.url());
        const url = new URL(request.url()), record = {state: state.id, page_id: page.foundationPageId, phase: phaseAtRequest,
          url: request.url(), method: request.method(), status: response.status(), request_body: request.postData()};
        this.data.requests.push(record);
        if (url.pathname.startsWith('/api/workbench/')) {
          const bytes = await response.body(), body = JSON.parse(bytes.toString('utf8'));
          const file = path.join(this.root, 'foundation-responses', String(index).padStart(5, '0') + '.json');
          fs.writeFileSync(file, bytes);
          this.data.api_responses.push({...record, file, sha256: hash(bytes), body});
        } else if (this.assetMap.has(url.pathname)) {
          if (this.assetMap.get(url.pathname).bytes >= 8 * 1024 * 1024) return;
          const bytes = await response.body(), actual = hash(bytes), expected = this.assetMap.get(url.pathname);
          if (phaseAtRequest === 'normal') this.equal(actual, expected.sha256, 'Browser must receive the actual private full-build asset');
          this.data.served_assets.push({...record, sha256: actual, expected_sha256: expected.sha256, bytes: bytes.length});
        }
      })().catch(error => this.error(page, 'capture', {url: request.url(), method: request.method(), message: String(error)})));
    });
    return {context, page, state};
  }
  async largeAssetCapture(context, page, state) {
    const cdp = await context.newCDPSession(page), large = new Map();
    cdp.on('Network.responseReceived', event => {
      const url = new URL(event.response.url), expected = this.assetMap.get(url.pathname);
      if (expected && expected.bytes >= 8 * 1024 * 1024) large.set(event.requestId, {url: event.response.url,
        status: event.response.status, expected, phase: page.foundationPhase});
    });
    cdp.on('Network.loadingFinished', event => {
      const row = large.get(event.requestId);
      if (!row) return;
      large.delete(event.requestId);
      this.pending.push((async () => {
        const body = await cdp.send('Network.getResponseBody', {requestId: event.requestId});
        const bytes = Buffer.from(body.body, body.base64Encoded ? 'base64' : 'utf8'), actual = hash(bytes);
        if (row.phase === 'normal') this.equal(actual, row.expected.sha256, 'Large actual browser resource must match the private build');
        this.data.served_assets.push({state: state.id, page_id: page.foundationPageId, phase: row.phase, url: row.url, method: 'GET', status: row.status,
          sha256: actual, expected_sha256: row.expected.sha256, bytes: bytes.length, body_capture: 'same browser response, CDP 32 MiB per-resource buffer'});
      })().catch(error => this.error(page, 'large-asset-capture', {url: row.url, message: String(error)})));
    });
    await cdp.send('Network.enable', {maxResourceBufferSize: 32 * 1024 * 1024, maxTotalBufferSize: 128 * 1024 * 1024});
  }
  async flush(page) {
    if (!page.isClosed()) await page.waitForLoadState('networkidle');
    await Promise.all(this.pending);
  }
  async shot(page, state, name, kind) {
    const directory = path.join(this.root, 'screenshots', state.id);
    fs.mkdirSync(directory, {recursive: true});
    const file = path.join(directory, name + '.png');
    const bytes = await page.screenshot({path: file, animations: 'disabled', fullPage: false});
    const png = PNG.sync.read(bytes), colors = new Set();
    let samples = 0, sum = 0, squares = 0;
    for (let y = kind === 'fault' ? 0 : 90; y < png.height - 12; y += 7) for (let x = kind === 'fault' ? 0 : 270; x < png.width - 12; x += 7) {
      const at = (y * png.width + x) * 4, value = (png.data[at] + png.data[at + 1] + png.data[at + 2]) / 3;
      colors.add([png.data[at], png.data[at + 1], png.data[at + 2]].join(',')); samples++; sum += value; squares += value * value;
    }
    const pixel = {distinct_colors: colors.size, samples, variance: squares / samples - (sum / samples) ** 2};
    this.ok(pixel.distinct_colors > 4 && pixel.variance > 0.1, 'Main viewport must not be a uniform blank image');
    fs.writeFileSync(path.join(directory, name + '.txt'), await page.locator('body').innerText());
    const row = {state: state.id, name, kind, file, sha256: hash(bytes), width: png.width, height: png.height, pixel};
    this.data.screenshots.push(row); this.save(); return row;
  }
  async run(page, state, kind, name, action) {
    const row = {state: state.id, page_id: page.foundationPageId, kind, name, status: 'passed'};
    try { row.detail = await action(); }
    catch (error) { row.status = 'failed'; row.error = String(error.stack || error); }
    try { row.screenshot = await this.shot(page, state, name + (row.status === 'failed' ? '-FAILED' : ''), kind); }
    catch (error) { row.status = 'failed'; row.screenshot_error = String(error); }
    this.data.cases.push(row); this.save(); console.log(JSON.stringify({state: state.id, kind, name, status: row.status, error: row.error}));
    return row.status === 'passed';
  }
}

async function settle(page, record) {
  await page.locator('#root[data-workbench-boot="ready"]').waitFor();
  await record.flush(page);
  await page.evaluate(async () => { await document.fonts.ready; await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))); });
}
async function shell(page, view, record) {
  const expected = NAV.find(row => row[0] === view);
  const title = view === 'delay' ? '交付风险' : expected[1], active = PARENT[view] || view;
  record.equal(await page.locator('.top-title').innerText(), title, 'Real main title');
  record.equal(await page.title(), title + ' · APS 智能排产', 'Browser document title follows actual route');
  const links = await page.locator('.sidebar-nav a.nav-item').evaluateAll(nodes => nodes.map(node => ({
    text: node.innerText.trim(), title: node.title, href: node.href, active: node.classList.contains('active'), current: node.getAttribute('aria-current')})));
  record.equal(links.map(row => row.text), SIDEBAR.map(row => row[1]), 'All 12 consolidated sidebar entries in approved order');
  record.equal(links.map(row => row.title), SIDEBAR.map(row => row[1]), 'All sidebar tooltips retain full titles');
  record.equal(links.filter(row => row.active).map(row => row.text), [NAV.find(row => row[0] === active)[1]]);
  record.equal(links.filter(row => row.current === 'page').map(row => row.text), [NAV.find(row => row[0] === active)[1]]);
  for (let index = 0; index < links.length; index++) {
    const url = new URL(links[index].href);
    record.equal(url.origin, record.ready.url);
    record.equal(url.pathname, SIDEBAR[index][0] === 'trial' ? '/workbench/trial' : '/workbench');
    if (SIDEBAR[index][0] !== 'trial') record.equal(url.searchParams.get('view'), SIDEBAR[index][0]);
  }
  if (['analysis', 'gantt', 'delay', 'reports', 'review'].includes(view)) {
    const tablist = page.getByRole('tablist', {name: active === 'analysis' ? '计划中心视图' : '统计分析视图', exact: true});
    record.equal(await tablist.getByRole('tab', {selected: true}).innerText(), title, 'The actual child route selects its corresponding tab');
  }
  record.equal(await page.locator('.wb-render-failure').count(), 0, 'Normal workspace must not be a render fallback');
  return {title, links};
}
async function navigate(page, view, record) {
  const parent = PARENT[view] || view, label = NAV.find(row => row[0] === parent)[1];
  await record.flush(page);
  let responseStart = record.data.api_responses.length;
  await page.locator('.sidebar-nav').getByRole('link', {name: label, exact: true}).click();
  await settle(page, record);
  if (parent !== view) {
    await page.locator(parent === 'analysis' ? '[data-plan-gantt]' : '.rw-workbench[data-ready="true"]').waitFor();
    await record.flush(page); responseStart = record.data.api_responses.length;
    const tabs = page.getByRole('tablist', {name: parent === 'analysis' ? '计划中心视图' : '统计分析视图', exact: true});
    await tabs.getByRole('tab', {name: view === 'delay' ? '交付风险' : NAV.find(row => row[0] === view)[1], exact: true}).click();
    await settle(page, record);
  }
  return {...await shell(page, view, record), mechanism: parent === view ? 'actual sidebar link click' : 'actual parent sidebar link and child tab clicks',
    sidebar_parent: parent, current_view_read_start: responseStart};
}
async function geometry(page, record) {
  const result = await page.evaluate(() => {
    const rect = node => { const r = node.getBoundingClientRect(); return {left: r.left, top: r.top, right: r.right, bottom: r.bottom, width: r.width, height: r.height}; };
    const nodes = ['.top-title', '.wb-current-plan', '.header-controls'].map(selector => ({selector, node: document.querySelector(selector)})).filter(row => row.node);
    const overlap = [];
    for (let a = 0; a < nodes.length; a++) for (let b = a + 1; b < nodes.length; b++) {
      const x = rect(nodes[a].node), y = rect(nodes[b].node);
      if (Math.min(x.right, y.right) - Math.max(x.left, y.left) > 2 && Math.min(x.bottom, y.bottom) - Math.max(x.top, y.top) > 2) overlap.push([nodes[a].selector, nodes[b].selector]);
    }
    const externalLinks = Array.from(document.querySelectorAll('a[href]')).map(node => node.href).filter(href => /^https?:/.test(href) && new URL(href).origin !== location.origin);
    return {viewport: {width: innerWidth, height: innerHeight}, bodyWidth: document.body.scrollWidth, documentWidth: document.documentElement.scrollWidth,
      sidebar: rect(document.querySelector('.sidebar')), main: rect(document.querySelector('.main-content')),
      header: nodes.map(row => ({selector: row.selector, rect: rect(row.node)})), overlap, externalLinks,
      textLength: document.querySelector('.page-content').innerText.trim().length};
  });
  record.ok(result.bodyWidth <= result.viewport.width + 2 && result.documentWidth <= result.viewport.width + 2, 'No global horizontal overflow');
  record.ok(result.sidebar.right <= result.main.left + 2, 'Sidebar must not cover main workspace');
  record.equal(result.overlap, [], 'Main title, real caption and controls must not overlap');
  record.equal(result.externalLinks, [], 'No external links in the offline shell');
  record.ok(result.textLength > 12, 'Workspace has meaningful visible content');
  return result;
}
module.exports = {NAV, SIDEBAR, Record, hash, write, settle, shell, navigate, geometry};
