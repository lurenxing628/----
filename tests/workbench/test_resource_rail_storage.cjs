'use strict';
// Compile only these components into memory; use real React and Chromium on an isolated HTTP origin, without a DB.
const assert = require('node:assert/strict'), fs = require('node:fs'), http = require('node:http'), path = require('node:path');
const { chromium } = require('playwright');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), preferenceKey = 'aps_resource_rail_collapsed';
const names = ['ResourceControls.jsx', 'ResourceRail.jsx', 'WorkbenchBoundary.jsx'];
const compiled = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'),
  sources: names.map(name => ({ path: name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8') })) }).outputs;
const files = new Map([
  ['/react.js', fs.readFileSync(path.join(root, 'static/workbench/vendor/react-18.3.1.production.min.js'), 'utf8')],
  ['/react-dom.js', fs.readFileSync(path.join(root, 'static/workbench/vendor/react-dom-18.3.1.production.min.js'), 'utf8')],
  ['/format.js', fs.readFileSync(path.join(root, 'frontend/workbench/app/WorkbenchFormat.js'), 'utf8')],
  ['/components.js', compiled.map(item => item.code).join('\n')],
]);
const fixture = `
window.APSResourceContract = {nodes: Object.fromEntries(['process','material','op_int','machine','operator','op_ext','supplier'].map(key => [key,{label:key,icon:'box',unit:'项'}]))};
window.Ico = () => React.createElement('span');
window.APSWorkbenchUI = {Icon: window.Ico};
window.remountRail = () => {
  if (window.railRoot) ReactDOM.flushSync(() => window.railRoot.unmount());
  window.railRoot = ReactDOM.createRoot(document.getElementById('root'));
  ReactDOM.flushSync(() => window.railRoot.render(React.createElement(window.WorkbenchBoundary, null,
    React.createElement(window.ResourceRail, {counts:{},node:'process',onNode:()=>{},onNavigate:()=>{}}))));
};
`;
const html = '<!doctype html><html><head><meta charset="utf-8"><style>:root{--wb-short-screen-max:820px}</style></head>' +
  '<body class="aps-workbench"><div id="root"></div><script src="/react.js"></script><script src="/react-dom.js"></script>' +
  '<script src="/format.js"></script><script>' + fixture + '</script><script src="/components.js"></script><script>remountRail()</script></body></html>';
const server = http.createServer((req, res) => {
  if (req.url === '/') { res.setHeader('Content-Type', 'text/html; charset=utf-8'); res.end(html); }
  else if (req.url === '/favicon.ico') { res.writeHead(204); res.end(); }
  else if (files.has(req.url)) { res.setHeader('Content-Type', 'application/javascript'); res.end(files.get(req.url)); }
  else { res.writeHead(404); res.end(); }
});

(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const origin = 'http://127.0.0.1:' + server.address().port;
  const browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true, args: ['--disable-background-networking'] });
  const report = {browser: browser.version(), cases: [], errors: [], external: [], database: false, global_build: false};
  try {
    assert(report.browser.startsWith('109.'), 'Actual Chromium 109 is required');
    for (const mode of ['normal', 'read-denied', 'write-quota', 'write-denied']) {
      const context = await browser.newContext({ viewport: {width: 1280, height: 720} });
      try {
        await context.addInitScript(({mode, key}) => {
          const nativeStorage = window.sessionStorage, write = nativeStorage.setItem.bind(nativeStorage);
          window.storageFault = mode;
          if (mode.startsWith('write-')) write(key, 'false');
          Object.defineProperty(window, 'sessionStorage', {configurable: true, get() {
            if (window.storageFault === 'read-denied') throw new DOMException('Storage access denied', 'SecurityError');
            return nativeStorage;
          }});
          Storage.prototype.setItem = function(name, value) {
            if (this === nativeStorage && name === key && window.storageFault.startsWith('write-'))
              throw new DOMException('Storage write rejected', window.storageFault === 'write-quota' ? 'QuotaExceededError' : 'SecurityError');
            return write(name, value);
          };
        }, {mode, key: preferenceKey});
        const page = await context.newPage();
        page.on('pageerror', error => report.errors.push(mode + ': ' + error.message));
        page.on('console', message => { if (message.type() === 'error') report.errors.push(mode + ': ' + message.text()); });
        await page.route('**/*', route => {
          if (!route.request().url().startsWith(origin + '/')) { report.external.push(route.request().url()); return route.abort(); }
          return route.continue();
        });
        await page.goto(origin);
        const rail = page.locator('.rail'), alert = page.getByRole('alert');
        assert.equal(await rail.count(), 1, mode + ': storage failure must not replace the resource workspace with its error boundary');
        if (mode.startsWith('write-')) {
          assert.equal(await rail.getAttribute('data-collapsed'), 'false', mode + ': existing saved preference must be read');
          await page.getByRole('button', {name:'收起产能链'}).click();
          assert.equal(await rail.getAttribute('data-collapsed'), 'true', mode + ': failed persistence must not prevent collapse');
          assert(await alert.isVisible()); assert.match(await alert.innerText(), /无法保存.*当前显示已切换/);
          assert.equal(await page.evaluate(key => sessionStorage.getItem(key), preferenceKey), 'false', 'A failed write must not be reported as persisted');
          await page.getByRole('button', {name:'展开产能链'}).click();
          assert.equal(await rail.getAttribute('data-collapsed'), 'false', mode + ': repeated toggles remain usable');
          assert(await alert.isVisible());
        } else {
          assert.equal(await rail.getAttribute('data-collapsed'), 'true', mode + ': short screens without a readable choice start collapsed');
          if (mode === 'read-denied') { assert(await alert.isVisible()); assert.match(await alert.innerText(), /无法读取.*仍可展开或收起/); }
          else assert.equal(await alert.count(), 0);
          await page.getByRole('button', {name:'展开产能链'}).click();
          assert.equal(await rail.getAttribute('data-collapsed'), 'false', mode + ': expand is usable');
          if (mode === 'read-denied') { assert(await alert.isVisible()); assert.match(await alert.innerText(), /无法保存.*当前显示已切换/); }
        }
        // Once persistence recovers, a new user choice is saved and its old failure message disappears.
        await page.evaluate(() => { window.storageFault = 'normal'; });
        await page.getByRole('button', {name:'收起产能链'}).click();
        assert.equal(await rail.getAttribute('data-collapsed'), 'true');
        assert.equal(await alert.count(), 0);
        assert.equal(await page.evaluate(key => sessionStorage.getItem(key), preferenceKey), 'true');
        await page.evaluate(() => remountRail());
        assert.equal(await rail.getAttribute('data-collapsed'), 'true', 'A remount restores the successfully saved choice');
        await page.getByRole('button', {name:'展开产能链'}).click();
        await page.evaluate(() => remountRail());
        assert.equal(await rail.getAttribute('data-collapsed'), 'false', 'An explicit expanded choice survives remounts');
        assert.equal(await alert.count(), 0);
        report.cases.push(mode);
      } finally { await context.close(); }
    }
    assert.deepEqual(report.errors, []); assert.deepEqual(report.external, []);
    process.stdout.write(JSON.stringify(report) + '\n');
  } finally { await browser.close(); await new Promise(resolve => server.close(resolve)); }
})().catch(error => { console.error(error); process.exitCode = 1; });
