'use strict';
const fs = require('node:fs'), path = require('node:path'), http = require('node:http'), crypto = require('node:crypto'), assert = require('node:assert/strict');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), base = '/api/workbench/v1/master-overview';
const names = ['MasterOverviewContract.js', 'MasterOverviewAPI.js', 'MasterOverviewStyles.jsx', 'MasterOverviewTable.jsx', 'MasterOverviewDetail.jsx', 'MasterOverviewWorkspace.jsx'];
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const defaults = { view: 'issues', domain: 'all', status: 'all', query: '', sort: 'issue_count', direction: 'desc', size: 20, column_filters: {} };
const clone = value => JSON.parse(JSON.stringify(value));
const canonical = value => Array.isArray(value) ? '[' + value.map(canonical).join(',') + ']' : value && typeof value === 'object'
  ? '{' + Object.keys(value).sort().map(key => JSON.stringify(key) + ':' + canonical(value[key])).join(',') + '}' : JSON.stringify(value);
const snapshot = scope => 'mock-scope-' + hash(canonical(scope));
const labels = { part: '零件', route: '工艺路线', opType: '工种', equipment: '设备', personnel: '人员', material: '物料', supplier: '供应商', calendar: '日历配置' };
const statuses = { attention: '待维护', checked: '已检查', inactive: '停用', unknown: '无法核实' };
function match(fixture, scope) {
  const rows = fixture[scope.view].filter(row => (scope.domain === 'all' || scope.domain === row.domain)
    && (scope.status === 'all' || (scope.status === 'attention' ? row.issue_count > 0 : scope.status === row.status))
    && (!scope.query || [row.business_code, row.label, row.summary, row.evidence, row.title].some(text => text && text.toLowerCase().includes(scope.query.toLowerCase())))
    && Object.entries(scope.column_filters).every(([key, value]) => String(key === 'domain' ? labels[row.domain] : key === 'status' ? statuses[row.status] : row[key] === null ? '未知' : row[key]).includes(value)));
  rows.sort((a, b) => a.business_code.localeCompare(b.business_code) || a.key.localeCompare(b.key));
  rows.sort((a, b) => { const av = a[scope.sort], bv = b[scope.sort]; if (av === null || bv === null) return av === bv ? 0 : av === null ? 1 : -1;
    const diff = typeof av === 'number' ? av - bv : String(av).localeCompare(String(bv)); return scope.direction === 'asc' ? diff : -diff; });
  return rows;
}
const brief = row => Object.fromEntries(Object.entries(row).filter(([key]) => !['fields', 'relations', 'issues'].includes(key)));
const envelope = (data, token) => ({ ok: true, schema_version: 1, data, meta: { source: 'production', time_basis: 'factory_local', snapshot_ref: token, as_of: '2026-09-10T00:10:00', request_ref: 'fixture-request' }, warnings: [] });
function pageResult(fixture, scope, page, spec) {
  const rows = spec.empty ? [] : match(fixture, scope), total = rows.length, overview = clone(fixture.overview);
  if (spec.gaps) { const calendar = overview.domains[7]; overview.stats.entities -= calendar.count; calendar.loaded = false; calendar.count = calendar.attention = calendar.unknown = null;
    overview.complete = false; overview.stats.relations = null; overview.gaps = [{ source: 'WorkCalendar', code: 'source_unavailable', message: 'WorkCalendar来源未加载，相关数量或检查结果未知。' }]; }
  return { scope, rows: rows.slice((page - 1) * scope.size, page * scope.size).map(brief), overview,
    page: { number: page, size: scope.size, total: spec.badCount ? total + 999 : total, pages: Math.max(1, Math.ceil(total / scope.size)) } };
}
function setup(report, output) {
  const fixture = JSON.parse(fs.readFileSync(path.join(output, 'fixture.json'))), files = ['WorkbenchPageContext.jsx', 'resource-contract.js', 'ResourceControls.jsx', 'transport.js'].concat(names);
  const sources = files.map(name => ({ path: 'frontend/workbench/app/' + name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8') }));
  const built = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true });
  report.target = built.target; report.global_build = false;
  report.sources = sources.map(row => ({ path: row.path, sha256: hash(row.code) }));
  const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json'))), assets = new Map();
  report.style_build_id = manifest.build_id;
  for (const item of manifest.files) { const bytes = fs.readFileSync(path.join(root, 'static', item.path)); assert.equal(hash(bytes), item.sha256, 'Concurrent shared build; retry after it settles'); assets.set('/static/' + item.path, { bytes, mime: item.mime }); }
  const compiled = built.outputs.map((item, index) => { const url = '/fixture/' + files[index] + '.js'; assets.set(url, { bytes: item.code, mime: 'application/javascript' }); return url; });
  const shared = manifest.scripts.filter(file => file.startsWith('workbench/vendor/') || file.startsWith('workbench/assets/foundation-'));
  const scripts = shared.map(file => '/static/' + file).concat(compiled).map(url => '<script src="' + url + '"></script>').join('');
  const css = manifest.styles.map(file => '<link rel="stylesheet" href="/static/' + file + '">').join('');
  const harness = `let mounted; window.mountOverview = function(spec) { if(mounted)mounted.unmount(); window.fixtureState={navigations:[],spec}; document.documentElement.dataset.theme=spec.theme || 'light';
    mounted=ReactDOM.createRoot(document.getElementById('root')); const onNavigate=spec.noNavigation ? undefined : (view,context)=>{fixtureState.navigations.push({view,context});if(spec.navigationFailure)throw new Error('目标实体已不存在，未按同号替代。');};
    mounted.render(React.createElement(AppShell,{active:'basedata',theme:spec.theme||'light',operations:true,showCapsule:false,title:'主数据总览',onNav:()=>{}},React.createElement(MasterOverviewWorkspace,{onNavigate,initialContext:spec.initialContext})));};`;
  const html = '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' + css + '</head><body class="aps-workbench"><div id="root"></div>' + scripts + '<script>' + harness + '</script></body></html>';
  const state = { spec: {}, requests: [] };
  async function handle(req, res) {
    const url = new URL(req.url, 'http://localhost');
    if (url.pathname === '/') { res.setHeader('Content-Type', 'text/html;charset=utf-8'); res.end(html); return; }
    if (url.pathname === '/favicon.ico') { res.writeHead(204); res.end(); return; }
    if (url.pathname.startsWith(base)) {
      const scope = { ...defaults, ...JSON.parse(url.searchParams.get('scope') || '{}') }, token = url.searchParams.get('snapshot_ref');
      const request = { method: req.method, path: url.pathname, scope: clone(scope), token }; state.requests.push(request); report.requests.push(request);
      const spec = state.spec;
      const send = (value, status = 200) => { res.writeHead(status, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' }); res.end(JSON.stringify(value)); };
      const failure = message => send({ ok: false, committed: false, error: { code: 'snapshot_stale', message } }, 409);
      if (spec.delay && url.pathname === base) await new Promise(resolve => setTimeout(resolve, spec.delay));
      if (spec.failure) { failure('本机读取失败，未使用样例替代。'); return; }
      if (spec.stale && token || token && token !== snapshot(scope)) { failure('筛选范围或数据已经变化，请明确刷新后再继续。'); return; }
      if (url.pathname === base) { send(envelope(pageResult(fixture, scope, Number(url.searchParams.get('page') || 1), spec), snapshot(scope))); return; }
      if (url.pathname.endsWith('/export')) {
        const rows = match(fixture, scope); const csv = '\ufeff"编号","名称"\r\n' + rows.map(row => [row.business_code, row.label].map(value => '"' + value.replace(/"/g, '""') + '"').join(',')).join('\r\n');
        res.writeHead(200, { 'Content-Type': 'text/csv;charset=utf-8', 'X-Workbench-Snapshot-Ref': spec.badExport ? 'wrong-snapshot' : token, 'X-Workbench-Row-Count': String(rows.length) }); res.end(csv); return;
      }
      const [, mode, domain, ref] = url.pathname.slice(base.length).split('/'), entity = fixture.entities.find(row => row.ref === ref && row.domain === domain);
      if (!entity) { send({ ok: false, committed: false, error: { code: 'entity_not_found', message: '目标实体已不存在，未按同号替代。' } }, 404); return; }
      if (mode === 'locate') {
        const next = { ...defaults, view: 'entities', domain, sort: 'business_code', direction: 'asc', size: scope.size }, rows = match(fixture, next);
        const data = pageResult(fixture, next, Math.floor(rows.findIndex(row => row.ref === ref) / next.size) + 1, spec); data.selected = { domain, entity_ref: ref };
        send(envelope(data, snapshot(next))); return;
      }
      const section = url.searchParams.get('section'), page = Number(url.searchParams.get('detail_page') || 1), rows = entity[section];
      const data = { scope, entity: brief(entity), section, rows: rows.slice((page - 1) * 10, page * 10), counts: Object.fromEntries(['issues', 'relations', 'fields'].map(key => [key, entity[key].length])),
        page: { number: page, size: 10, total: rows.length, pages: Math.max(1, Math.ceil(rows.length / 10)) } };
      if (spec.wrongDetail) data.entity.ref = 'f'.repeat(48);
      send(envelope(data, snapshot(scope))); return;
    }
    const item = assets.get(url.pathname); if (item) { res.setHeader('Content-Type', item.mime); res.end(item.bytes); return; }
    report.unexpected.push(req.url); res.writeHead(404); res.end();
  }
  return { server: http.createServer((req, res) => handle(req, res).catch(error => { report.errors.push(error.stack); res.writeHead(500); res.end(); })), state, fixture };
}
module.exports = { setup, root, names };
