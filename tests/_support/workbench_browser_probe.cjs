/* Real local React/Chromium contract probe. Inputs are declared by its Python caller. */
'use strict';
const fs = require('fs'), path = require('path'), crypto = require('crypto');
const { chromium } = require('playwright');
async function main() {
  const input = JSON.parse(fs.readFileSync(0, 'utf8'));
  const browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true });
  const result = { browser: browser.version(), inputs: [], requests: [], errors: [], external: [], value: null };
  try {
    if (!result.browser.startsWith('109.')) throw new Error('Chromium 109 is required');
    for (const name of input.inputs) {
      const file = path.resolve(input.root, name), data = fs.readFileSync(file);
      if (!file.startsWith(path.resolve(input.root) + path.sep)) throw new Error('Input escaped private source');
      result.inputs.push({ path: name, sha256: crypto.createHash('sha256').update(data).digest('hex'), bytes: data.length,
        mode: fs.statSync(file).mode & 0o777 });
    }
    const page = await browser.newPage({ viewport: { width: 1392, height: 924 } });
    page.on('pageerror', error => result.errors.push(error.message));
    page.on('request', request => result.requests.push({ method: request.method(), url: request.url() }));
    await page.route('**/*', route => {
      const url = new URL(route.request().url());
      if (input.url && url.origin === new URL(input.url).origin) return route.continue();
      if (!input.url && url.origin === 'http://127.0.0.1') return route.fulfill({ contentType: 'text/html',
        body: '<!doctype html><html lang="zh-CN"><body class="aps-workbench"><div id="root"></div></body></html>' });
      result.external.push(url.href); return route.abort();
    });
    if (input.url) {
      const response = await page.goto(input.url);
      if (response.status() !== 200) throw new Error('Canonical host status ' + response.status());
      await page.waitForSelector('#root[data-workbench-boot="ready"]');
    } else {
      await page.goto('http://127.0.0.1/workbench?view=dashboard');
      for (const name of input.inputs.slice(1)) await page.addScriptTag({ path: path.join(input.root, name) });
    }
    result.value = await page.evaluate(async ({ body, data }) => {
      const execute = new Function('data', 'expect', 'render', 'return (async () => {' + body + '})();');
      const expect = (value, message) => { if (!value) throw new Error(message || 'Contract assertion failed'); };
      const container = document.createElement('section'); document.body.appendChild(container);
      const root = ReactDOM.createRoot(container);
      const render = async element => { ReactDOM.flushSync(() => root.render(element)); await new Promise(resolve => setTimeout(resolve, 20));
        return container; };
      return await execute(data, expect, render);
    }, { body: input.body, data: input.data });
    await page.screenshot({ path: path.join(input.output, 'page.png'), fullPage: true });
    if (result.errors.length || result.external.length) throw new Error(JSON.stringify({ errors: result.errors, external: result.external }));
  } finally {
    fs.writeFileSync(path.join(input.output, 'result.json'), JSON.stringify(result, null, 2));
    await browser.close();
  }
}
main().catch(error => { console.error(error.stack); process.exitCode = 1; });
