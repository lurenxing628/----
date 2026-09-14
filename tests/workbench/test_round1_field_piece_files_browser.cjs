'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path');
const { spawnSync } = require('node:child_process'), { chromium } = require('playwright');
const H = require('./field_workspace_probe_harness.cjs');
const [upstream, output, width, height, theme] = process.argv.slice(2);
assert(upstream && output && !path.resolve(output).startsWith(H.root + '/'));
const report = { scope: 'R1-B real file component workflow only', errors: [], screenshots: [], downloads: [], requests: [] };
let page;

function workbook(action, source, destination) {
  const args = ['-m', 'tests.workbench.round1_field_piece_files_probe', action, source];
  if (destination) args.push(destination);
  const result = spawnSync(process.env.WORKBENCH_PYTHON, args, { cwd: H.root, encoding: 'utf8', env: process.env });
  assert.equal(result.status, 0, result.stdout + result.stderr);
}

async function shot(name) {
  const target = path.join(output, name + '.png');
  await page.screenshot({ path: target, animations: 'disabled' });
  report.screenshots.push(target);
  const geometry = await page.evaluate(() => {
    const dialog = document.querySelector('[role=dialog]');
    const box = dialog && dialog.getBoundingClientRect();
    const note = dialog && dialog.querySelector('.field-note');
    return { width: innerWidth, height: innerHeight, scroll: document.documentElement.scrollWidth,
      box: box && { left: box.left, right: box.right, top: box.top, bottom: box.bottom },
      noteFits: !note || note.scrollWidth <= note.clientWidth + 1 };
  });
  assert(geometry.scroll <= geometry.width + 1 && geometry.noteFits, JSON.stringify(geometry));
  if (geometry.box) assert(geometry.box.left >= 0 && geometry.box.right <= geometry.width + 1 &&
    geometry.box.top >= 0 && geometry.box.bottom <= geometry.height + 1, JSON.stringify(geometry));
}

async function download(label, filename) {
  const pending = page.waitForEvent('download');
  await page.getByRole('button', { name: label, exact: true }).click();
  const file = await pending, target = path.join(output, filename);
  await file.saveAs(target);
  assert.equal(await file.failure(), null);
  report.downloads.push(target);
  return target;
}

async function main() {
  let browser, server;
  try {
    server = H.createServer(upstream, report);
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true });
    report.browser = browser.version();
    assert.match(report.browser, /^109\./);
    page = await browser.newPage({ viewport: { width: Number(width), height: Number(height) } });
    page.setDefaultTimeout(15000);
    page.on('pageerror', error => report.errors.push(error.message));
    page.on('response', response => {
      if (response.url().includes('/api/')) report.requests.push({ url: response.url(), status: response.status() });
    });
    await page.goto('http://127.0.0.1:' + server.address().port + '/?theme=' + theme);
    await page.locator('[data-field-task]').first().waitFor();
    assert.equal(await page.locator('[data-field-task]').count(), 4);
    await page.getByRole('button', { name: '报工文件', exact: true }).click();
    await page.getByRole('dialog', { name: '报工文件', exact: true }).waitFor();
    assert.match(await page.getByRole('dialog').innerText(), /任务编号.*已预填.*不可修改/);
    const source = await download('下载模板', 'downloaded-template.xlsx');
    const filled = path.join(output, 'filled-template.xlsx');
    workbook('fill', source, filled);
    await shot('template');
    await page.getByLabel('报工 XLSX 文件', { exact: true }).setInputFiles(filled);
    await page.getByRole('button', { name: '预检文件', exact: true }).click();
    await page.getByText('预检通过，尚未写入报工。', { exact: true }).waitFor();
    await shot('preview');
    await page.getByRole('button', { name: '确认导入', exact: true }).click();
    await page.getByRole('button', { name: '刷新已确认结果', exact: true }).click();
    await page.getByRole('dialog').waitFor({ state: 'detached' });
    await page.locator('[data-field-task]').first().waitFor();
    await shot('refreshed');
    await page.getByRole('button', { name: '报工文件', exact: true }).click();
    const exported = await download('导出当前范围', 'exported.xlsx');
    workbook('verify', exported);
    await page.getByLabel('报工 XLSX 文件', { exact: true }).setInputFiles(filled);
    await page.getByRole('button', { name: '预检文件', exact: true }).click();
    await page.getByText('预检通过，尚未写入报工。', { exact: true }).waitFor();
    assert.equal(await page.getByRole('table', { name: '文件逐行预检' }).getByText('重复', { exact: true }).count(), 3);
    await shot('duplicate');
    await page.getByRole('button', { name: '确认导入', exact: true }).click();
    await page.getByRole('button', { name: '刷新已确认结果', exact: true }).click();
    await page.getByRole('dialog').waitFor({ state: 'detached' });
    assert.deepEqual(report.errors, []);
    report.completed = true;
  } catch (error) {
    report.error = error.stack;
    if (page) await page.screenshot({ path: path.join(output, 'failed.png') });
    process.exitCode = 1;
  } finally {
    if (browser) await browser.close();
    if (server) await new Promise(resolve => server.close(resolve));
    fs.writeFileSync(path.join(output, 'round1-field-browser.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify({ completed: report.completed, error: report.error, output }));
  }
}
main();
