/* AZ current-source component harness. Frozen local assets; no Flask, DB or global build. */
'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), http = require('node:http');
const path = require('node:path'), crypto = require('node:crypto');
const { chromium } = require('playwright'), { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..');
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const variants = [1920, 1392].flatMap(width => ['light', 'dark'].map(theme => ({
  name: width + '-' + theme, theme, viewport: { width, height: width === 1920 ? 1080 : 924 }
})));
const appFiles = ['resource-contract.js', 'resource-session.js', 'ResourceControls.jsx', 'ResourceForms.jsx',
  'WorkbenchControlStyles.jsx', 'BatchContract.js', 'BatchControls.jsx', 'BatchFiles.jsx',
  'ProcessContract.js', 'ProcessStageEditor.jsx', 'ProcessSourceEditor.jsx'];
async function setup(kind) {
  const output = process.argv[2];
  assert(output, 'Pass a temporary artifact directory'); fs.mkdirSync(output, { recursive: true });
  const report = { scope: 'AZ-' + kind + '-component-mock', production_persistence_tested: false,
    win7_hardware_tested: false, cases: [], errors: [], external: [], screenshots: [] };
  const freeze = name => {
    const bytes = fs.readFileSync(path.join(root, name)), target = path.join(output, 'frozen', name);
    fs.mkdirSync(path.dirname(target), { recursive: true }); fs.writeFileSync(target, bytes);
    return bytes;
  };
  const manifestPath = 'static/workbench/asset-manifest.json', manifestBytes = freeze(manifestPath);
  const manifest = JSON.parse(manifestBytes);
  report.manifest = { path: manifestPath, sha256: sha(manifestBytes), build_id: manifest.build_id };
  const paths = appFiles.map(file => 'frontend/workbench/app/' + file).concat(['tests/workbench/az_contrast_modal_fixture.jsx']);
  const sources = paths.map(name => ({ path: name, code: freeze(name).toString('utf8') }));
  report.sources = sources.map(row => ({ path: row.path, sha256: sha(row.code) }));
  const babelPath = 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js';
  freeze(babelPath);
  // Extract the real private Steps and inline detail styles with Babel's AST, not a look-alike stylesheet.
  const detailPath = 'frontend/workbench/app/ProcessDetail.jsx', detail = freeze(detailPath).toString('utf8');
  const babel = require(path.join(output, 'frozen', babelPath));
  const ast = babel.transform(detail, { filename: detailPath, ast: true, code: false, parserOpts: { plugins: ['jsx'] } }).ast;
  const declarations = ast.program.body[0].expression.callee.body.body;
  const steps = declarations.find(node => node.type === 'FunctionDeclaration' && node.id.name === 'Steps');
  const styles = [];
  function visit(node) {
    if (!node || typeof node !== 'object') return;
    if (node.type === 'JSXElement' && node.openingElement.name.name === 'style') styles.push(node);
    Object.values(node).forEach(value => { if (Array.isArray(value)) value.forEach(visit); else if (value && typeof value === 'object') visit(value); });
  }
  visit(ast.program); assert(steps && styles.length === 1, 'ProcessDetail presentation extraction changed');
  report.presentation = { path: detailPath, sha256: sha(detail), extraction: 'Babel AST: Steps function and its exact inline style element' };
  sources.splice(sources.length - 1, 0, { path: 'az-extracted-process-presentation.jsx', code:
    '(function(){const {Button}=window.ResourceControls;' + detail.slice(steps.start, steps.end) +
    ';window.AZProcessSteps=Steps;window.AZProcessDetailStyles=()=>(' + detail.slice(styles[0].start, styles[0].end) + ');})();' });
  const built = compile({ babel_path: path.join(output, 'frozen', babelPath), sources, check_combined: true });
  report.compile = { target: built.target, babel: built.babel_version, global_build: false };
  const scripts = new Map(built.outputs.map((row, index) => {
    const name = '/fixture/' + index + '.js';
    fs.mkdirSync(path.join(output, 'compiled'), { recursive: true });
    fs.writeFileSync(path.join(output, 'compiled', index + '.js'), row.code);
    return [name, row.code];
  }));
  report.compiled = built.outputs.map(row => ({ path: row.path, sha256: sha(row.code) }));
  const assets = new Map(manifest.files.map(row => [row.path, { ...row, bytes: freeze('static/' + row.path) }]));
  report.assets = [...assets.values()].map(row => ({ path: 'static/' + row.path, sha256: sha(row.bytes), manifest_sha256: row.sha256 }));
  const orderPath = 'scripts/workbench/build-order.json', orderBytes = freeze(orderPath), styleOrder = JSON.parse(orderBytes).styles;
  assert(Array.isArray(styleOrder) && styleOrder.includes('00-tokens.css') && styleOrder.includes('10-shell.css'),
    'Current source harness requires the explicit maintained CSS layer');
  report.style_order = { path: orderPath, sha256: sha(orderBytes), styles: styleOrder };
  report.styles = styleOrder.map(name => {
    const source = 'frontend/workbench/app/styles/' + name, publicPath = 'workbench/app/styles/' + name;
    const bytes = freeze(source), formal = assets.get(publicPath);
    assets.set(publicPath, { path: publicPath, bytes, mime: 'text/css' });
    return { path: source, sha256: sha(bytes), public_path: publicPath, formal_sha256: formal ? sha(formal.bytes) : null };
  });
  const loadedStyles = manifest.styles.filter(name => !name.startsWith('workbench/app/styles/'))
    .concat(report.styles.map(row => row.public_path));
  const watch = ['schema.sql', 'frontend/workbench/app/main.jsx', 'scripts/workbench/build.py',
    'frontend/workbench/prototype/ui_kits/workbench/plana.css', 'frontend/workbench/app/ProcessDetail.jsx',
    'frontend/workbench/app/ProcessWorkspace.jsx', 'frontend/workbench/app/ProcessRouteEntry.jsx',
    'frontend/workbench/app/ResourceControls.jsx'];
  report.shared = watch.map(name => ({ path: name, before: sha(freeze(name)) }));
  const shared = manifest.scripts.filter(file => file.startsWith('workbench/vendor/') || file.startsWith('workbench/assets/foundation-'));
  const html = '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
    '<link rel="icon" href="/static/' + manifest.icon + '">' +
    loadedStyles.map(file => '<link rel="stylesheet" href="/static/' + file + '">').join('') +
    '</head><body class="aps-workbench"><div id="root"></div>' +
    shared.map(file => '<script src="/static/' + file + '"></script>').join('') +
    [...scripts.keys()].map(file => '<script src="' + file + '"></script>').join('') + '</body></html>';
  const server = http.createServer((req, res) => {
    const name = new URL(req.url, 'http://fixture').pathname;
    if (name === '/') { res.setHeader('Content-Type', 'text/html;charset=utf-8'); res.end(html); return; }
    if (scripts.has(name)) { res.setHeader('Content-Type', 'application/javascript'); res.end(scripts.get(name)); return; }
    const asset = name.startsWith('/static/') && assets.get(name.slice(8));
    if (!asset) { res.writeHead(404); res.end(); return; }
    res.setHeader('Content-Type', asset.mime); res.end(asset.bytes);
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const origin = 'http://127.0.0.1:' + server.address().port;
  let browser;
  try {
    assert(process.env.WORKBENCH_BROWSER, 'Set WORKBENCH_BROWSER to actual Chromium 109');
    browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true });
    report.browser = browser.version(); assert.match(report.browser, /^109\./);
  } catch (error) { await new Promise(resolve => server.close(resolve)); throw error; }
  return { output, report,
    async page(variant) {
      const page = await browser.newPage({ viewport: variant.viewport }); page.setDefaultTimeout(10000);
      page.on('pageerror', error => report.errors.push({ variant: variant.name, message: error.message }));
      page.on('console', message => { if (message.type() === 'error') report.errors.push({ variant: variant.name, message: message.text() }); });
      await page.route('**/*', route => {
        if (!route.request().url().startsWith(origin + '/')) { report.external.push(route.request().url()); return route.abort(); }
        return route.continue();
      });
      await page.goto(origin); await page.evaluate(theme => { document.documentElement.dataset.theme = theme; }, variant.theme);
      return page;
    },
    async shot(page, name) {
      const filename = name + '.png'; await page.screenshot({ path: path.join(output, filename), fullPage: false });
      report.screenshots.push(filename);
    },
    async close() {
      await browser.close(); await new Promise(resolve => server.close(resolve));
      report.shared.forEach(row => { row.after = sha(fs.readFileSync(path.join(root, row.path))); row.changed = row.before !== row.after; });
      report.source_drift = report.sources.concat(report.styles, [report.style_order])
        .filter(row => sha(fs.readFileSync(path.join(root, row.path))) !== row.sha256);
      report.stopped = true;
      fs.writeFileSync(path.join(output, kind + '-result.json'), JSON.stringify(report, null, 2));
      console.log(JSON.stringify({ output, browser: report.browser, cases: report.cases.length, errors: report.errors.length }));
    }
  };
}
async function settle(page) {
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise(resolve => requestAnimationFrame(resolve));
    await Promise.all(document.getAnimations().map(animation => animation.finished));
    await new Promise(resolve => requestAnimationFrame(resolve));
  });
}
module.exports = { setup, settle, variants, assert };
