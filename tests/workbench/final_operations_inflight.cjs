'use strict';
const fs = require('node:fs'), path = require('node:path');
async function waitFile(root, name) {
  const until = Date.now() + 10000;
  while (!fs.existsSync(path.join(root, name))) {
    if (Date.now() >= until) throw new Error('Real process marker not observed: ' + name);
    await new Promise(resolve => setTimeout(resolve, 20));
  }
}
async function begin(h) {
  const root = path.dirname(h.config.database);
  await waitFile(root, 'worker-entered');
  const response = h.page.context().request.get(h.config.origin + '/api/workbench/v1/dp-held-response');
  await waitFile(root, 'http-entered');
  return { root, response };
}
async function release(h, held) {
  const { page, assert, mark, shot, config, report } = h;
  await page.locator('[data-restore-maintenance=warm]').waitFor();
  await mark('WBP-SYS-009.drain', async () => {
    assert(await page.evaluate(() => document.getElementById('root').inert));
    assert.equal(fs.existsSync(path.join(held.root, 'http-finalized')), false);
    assert.equal(fs.existsSync(path.join(held.root, 'worker-computed')), false);
    assert.equal(fs.readdirSync(config.backup_dir).some(name => name.endsWith('before_restore.db')), false);
    await shot('restore-waits-for-inflight-http-and-real-worker');
    fs.writeFileSync(path.join(held.root, 'http-release'), 'release actual HTTP response');
    const response = await held.response; assert.equal(response.status(), 200); assert.equal(await response.text(), 'first\nlast\n');
    await waitFile(held.root, 'http-finalized'); await waitFile(held.root, 'worker-stopping');
    assert.equal(fs.existsSync(path.join(held.root, 'worker-computed')), false);
    assert.equal(fs.readdirSync(config.backup_dir).some(name => name.endsWith('before_restore.db')), false);
    fs.writeFileSync(path.join(held.root, 'worker-release'), 'release actual candidate computation');
    report.inflight_order = ['http_admitted', 'worker_computing', 'restore_readonly', 'http_finalized', 'worker_join_requested', 'worker_released'];
  });
}
module.exports = { begin, release };
