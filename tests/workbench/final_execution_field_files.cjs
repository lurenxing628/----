'use strict';
const assert = require('node:assert/strict'), path = require('node:path');
const { execFileSync } = require('node:child_process');

async function files(p) {
  const { page, ready } = p;
  let template;
  await p.step(['WBP-FIELD-015', 'WBP-FIELD-017'], 'main-field-download-template-and-three-sheet-saved-export', async () => {
    await page.getByRole('button', { name: '报工文件', exact: true }).click();
    await page.getByRole('dialog', { name: '报工文件', exact: true }).waitFor();
    await page.getByText('XLSX · 13 列 · 任务编号、工序范围、单件编号已预填，不可修改 · 兼容旧 10 列', { exact: true }).waitFor();
    template = await p.download(() => page.getByRole('button', { name: '下载模板', exact: true }).click(), 'template');
    await p.download(() => page.getByRole('button', { name: '导出当前范围', exact: true }).click(), 'saved-records');
    await p.shot('file-modal');
    await page.getByRole('button', { name: '取消', exact: true }).click();
  });
  await p.step(['WBP-FIELD-016.A002', 'WBP-FIELD-016.A003', 'WBP-FIELD-016.A004', 'WBP-FIELD-016.A005'], 'ten-rejected-physical-rows-problem-download-and-cancel', async () => {
    const rejected = path.join(ready.root, 'downloads', 'ten-invalid-from-real-download.xlsx');
    execFileSync(process.env.WORKBENCH_PYTHON, ['-B', '-m', 'tests.workbench.final_execution_fileedit', template, rejected, '--mode', 'rejected'],
      { cwd: path.resolve(__dirname, '../..'), env: process.env, stdio: 'pipe' });
    await page.getByRole('button', { name: '报工文件', exact: true }).click();
    const chooser = page.waitForEvent('filechooser');
    await page.getByRole('button', { name: '选择 Excel 文件', exact: true }).click();
    await (await chooser).setFiles(rejected);
    await page.getByText(path.basename(rejected), { exact: true }).waitFor();
    const result = await p.read(() => page.getByRole('button', { name: '预检文件', exact: true }).click(), '/files/preview');
    assert.equal(result.data.can_confirm, false); assert.equal(result.data.summary.rejected, 10);
    assert.equal(result.data.summary.changed, 0);
    const confirm = page.getByRole('button', { name: '确认导入', exact: true });
    assert(await confirm.isDisabled());
    const reason = await confirm.getAttribute('aria-describedby');
    assert(reason);
    assert.equal(await page.locator('[id="' + reason + '"]').innerText(), '文件存在问题，未写入任何报工。');
    const lines = await page.getByRole('table', { name: '文件逐行预检', exact: true }).locator('tbody tr td:first-child').allTextContents();
    assert.deepEqual(lines.map(Number), Array.from({ length: 10 }, (_, index) => index + 2));
    await p.download(() => page.getByRole('button', { name: '下载问题清单', exact: true }).click(), 'rejected-rows');
    await p.shot('ten-rejected-rows');
    const again = await p.read(() => page.getByRole('button', { name: '重新预检原文件', exact: true }).click(), '/files/preview');
    assert.deepEqual(again.data.rows, result.data.rows);
    await page.getByRole('button', { name: '取消', exact: true }).click();
  });
  await p.step(['WBP-FIELD-015', 'WBP-FIELD-016'], 'real-upload-preview-confirm-two-explicit-pieces-and-reimport', async () => {
    const edited = path.join(ready.root, 'downloads', 'filled-from-real-download.xlsx');
    execFileSync(process.env.WORKBENCH_PYTHON, ['-B', '-m', 'tests.workbench.final_execution_fileedit', template, edited],
      { cwd: path.resolve(__dirname, '../..'), env: process.env, stdio: 'pipe' });
    for (const round of ['first', 'duplicate']) {
      await page.getByRole('button', { name: '报工文件', exact: true }).click();
      await page.getByLabel('报工 XLSX 文件', { exact: true }).setInputFiles(edited);
      const preview = await p.read(() => page.getByRole('button', { name: '预检文件', exact: true }).click(), '/files/preview');
      assert.equal(preview.data.can_confirm, true);
      assert.equal(preview.data.summary[round === 'first' ? 'changed' : 'unchanged'], 2);
      await p.shot('file-' + round + '-preview');
      const committed = await p.read(() => page.getByRole('button', { name: '确认导入', exact: true }).click(), '/files/confirm');
      p.report.file_commits = [...(p.report.file_commits || []), committed];
      await page.getByRole('button', { name: '刷新已确认结果', exact: true }).click();
      await page.getByRole('dialog', { name: '报工文件', exact: true }).waitFor({ state: 'hidden' });
      await page.locator('[data-field-task]').first().waitFor();
    }
  });
}
module.exports = { files };
