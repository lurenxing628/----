'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), crypto = require('node:crypto');

async function candidateDownloadFailure(page, report, h, flush) {
  await h.action(['WBP-ANA-005.download-failure'], async () => {
    const before = report.failed_requests.length;
    let downloads = 0;
    const observed = () => { downloads++; };
    page.on('download', observed);
    try {
      await page.context().setOffline(true);
      assert.equal(await page.evaluate(() => navigator.onLine), false);
      await h.button('CSV').click();
      const error = page.locator('[data-run-candidate-workspace] [role="alert"]').first();
      await error.waitFor(); await flush();
      assert((await error.innerText()).length > 0);
      assert.equal(downloads, 0);
      assert.equal(await page.getByText(/^已下载 13 条记录/).count(), 0);
      const failed = report.failed_requests.slice(before);
      assert.equal(failed.length, 1);
      const request = failed[0];
      assert.equal(request.method, 'GET');
      assert(new URL(request.url).pathname.endsWith('/candidates/' + report.candidate.candidate.candidate_ref + '/export'));
      assert.equal(request.failure.errorText, 'net::ERR_INTERNET_DISCONNECTED');
      report.network_faults = (report.network_faults || []).concat({ url: request.url, method: request.method,
        error: request.failure.errorText, source: 'Chromium context offline, original fetch and API unchanged' });
      await h.shot('candidate-real-network-export-failure');
    } finally { await page.context().setOffline(false); page.off('download', observed); }
    assert.equal(await page.evaluate(() => navigator.onLine), true);
    const waiting = page.waitForEvent('download'); await h.button('CSV').click(); const file = await waiting;
    assert.equal(await file.failure(), null);
    const target = path.join(path.dirname(report.candidate_download.path), 'offline-retry-' + file.suggestedFilename());
    await file.saveAs(target);
    const bytes = fs.readFileSync(target);
    assert.deepEqual(bytes, fs.readFileSync(report.candidate_download.path));
    report.downloads.push(target);
    report.candidate_download_retry = { path: target, sha256: crypto.createHash('sha256').update(bytes).digest('hex'),
      candidate_ref: report.candidate.candidate.candidate_ref, identical_to_original: true, explicit_retry: true };
    await h.shot('candidate-export-explicit-retry');
  });
}
module.exports = { candidateDownloadFailure };
