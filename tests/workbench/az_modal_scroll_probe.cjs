'use strict';
const H = require('./az_contrast_modal_harness.cjs'), { assert } = H;
async function geometry(page) {
  return page.evaluate(() => {
    const rect = node => { const r = node.getBoundingClientRect(); return { top: r.top, bottom: r.bottom, left: r.left, right: r.right, width: r.width, height: r.height }; };
    const body = document.querySelector('.modal-b'), footer = document.querySelector('.modal-f');
    const buttons = [...footer.querySelectorAll('button')].map(node => {
      const r = rect(node), x = (r.left + r.right) / 2, y = (r.top + r.bottom) / 2;
      return { text: node.textContent, disabled: node.disabled, rect: r,
        inViewport: r.top >= 0 && r.bottom <= innerHeight && r.left >= 0 && r.right <= innerWidth,
        hit: node.contains(document.elementFromPoint(x, y)), x, y };
    });
    return { dialog: rect(document.querySelector('.modal')), header: rect(document.querySelector('.modal-head')),
      body: { ...rect(body), scrollTop: body.scrollTop, clientHeight: body.clientHeight, scrollHeight: body.scrollHeight },
      footer: rect(footer), buttons, documentScroll: scrollY, width: innerWidth, height: innerHeight,
      overflow: document.documentElement.scrollWidth > innerWidth,
      lastRow: rect([...body.querySelectorAll('h3')].find(node => node.textContent === '将删除的全部批次').parentElement.lastElementChild) };
  });
}
async function mouseClick(page, selector) {
  const position = await page.locator(selector).evaluate(node => {
    const r = node.getBoundingClientRect(), x = (r.left + r.right) / 2, y = (r.top + r.bottom) / 2;
    return { x, y, visible: r.top >= 0 && r.bottom <= innerHeight && node.contains(document.elementFromPoint(x, y)) };
  });
  assert(position.visible, 'Button must already be visible and hit-testable: ' + selector);
  await page.mouse.click(position.x, position.y);
}
(async () => {
  const h = await H.setup('modal_scroll');
  try {
    for (const variant of H.variants) {
      const page = await h.page(variant);
      for (const action of ['cancel', 'confirm', 'rejected']) {
        const row = { variant: variant.name, action, passed: false, wheel: [] }; h.report.cases.push(row);
        await page.evaluate(rejected => azMount('batch', { rejected }), action === 'rejected');
        await page.getByRole('dialog').waitFor(); await H.settle(page);
        // Form setup is outside the reachability proof; no footer locator click is ever used.
        await page.getByLabel('导入模式').selectOption('replace');
        await page.getByLabel('选择 Excel 文件').setInputFiles({ name: 'az-replace.xlsx', mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', buffer: Buffer.from('AZ explicit component mock; no parser or persistence assertion') });
        await H.settle(page); await mouseClick(page, '.modal-f button[data-wb-transfer="import"]');
        await page.getByRole('table', { name: '批次导入预览' }).waitFor(); await H.settle(page);
        row.before = await geometry(page); await h.shot(page, variant.name + '-' + action + '-before');
        // Use the visible body gutter, outside the nested table's horizontal/vertical scrollbar.
        const b = row.before.body;
        await page.mouse.move(b.right - 24, Math.min(b.bottom - 16, variant.viewport.height - 50));
        for (let index = 0; index < 24; index++) {
          await page.mouse.wheel(0, 420); await page.waitForTimeout(50);
          const sample = await geometry(page); row.wheel.push(sample);
          if (sample.body.scrollTop > 0 && sample.body.scrollTop + sample.body.clientHeight >= sample.body.scrollHeight - 1) break;
        }
        row.after = await geometry(page); await h.shot(page, variant.name + '-' + action + '-after-wheel');
        const g = row.after;
        assert(g.body.scrollTop > 0, 'Ordinary wheel did not scroll the long modal body');
        assert(g.body.scrollTop + g.body.clientHeight >= g.body.scrollHeight - 1, 'Wheel did not reach the body bottom');
        assert(g.lastRow.top >= g.body.top && g.lastRow.bottom <= g.body.bottom, 'Last deletion row is hidden');
        assert(g.header.bottom <= g.body.top + 1 && g.body.bottom <= g.footer.top + 1, 'Header/body/footer overlap');
        assert(g.header.top >= 0 && g.footer.bottom <= g.height && !g.overflow, 'Dialog is clipped');
        assert.equal(g.header.top, row.before.header.top); assert.equal(g.footer.top, row.before.footer.top);
        assert.equal(g.documentScroll, row.before.documentScroll);
        g.buttons.forEach(button => assert(button.inViewport && button.hit, 'Footer unreachable: ' + button.text));
        const target = action === 'confirm' ? g.buttons[1] : g.buttons[0];
        assert.equal(g.buttons[1].disabled, action === 'rejected');
        await page.mouse.click(target.x, target.y);
        await page.waitForFunction(confirm => confirm ? az.submissions.length === 1 : az.cancelled === 1, action === 'confirm');
        row.outcome = await page.evaluate(() => ({ submissions: az.submissions, cancelled: az.cancelled, previews: az.previews }));
        assert.equal(row.outcome.submissions.length, action === 'confirm' ? 1 : 0);
        if (action === 'confirm') assert.equal(row.outcome.submissions[0][1], 'import_confirm');
        row.passed = true;
      }
      await page.close();
    }
    assert.deepEqual(h.report.errors, []); assert.deepEqual(h.report.external, []);
  } finally { await h.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
