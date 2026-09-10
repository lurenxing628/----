'use strict';
const assert = require('node:assert/strict');
const { run } = require('./final_execution_browser_support.cjs');

async function exercise(p, phase) {
  const { page, ready } = p, seed = ready.expected.final_e;
  const initial = await p.read(() => page.locator('.sidebar a[href$="?view=fieldgantt"]').click(), '/actual-gantt');
  const chain = initial.data.critical_chain;
  assert.equal(chain.state, 'available'); assert.equal(chain.plan_ref, seed.plan_ref);
  assert.deepEqual(chain.task_refs, seed.task_refs.slice(0, 4));
  assert.deepEqual(chain.edges.map(edge => edge.edge_type), ['process', 'machine', 'operator']);
  assert.deepEqual(chain.edges.map(edge => edge.gap_minutes), [0, 30, 30]);
  assert.equal(chain.snapshot_ref, initial.meta.snapshot_ref); p.report.chain = chain;
  await page.getByRole('checkbox', { name: '关键链', exact: true }).check();
  const strip = page.getByLabel('所选计划关键链', { exact: true });
  await strip.locator('[data-chain-node]').first().waitFor();
  if (phase === 'restart') {
    await p.step(['WBP-FG-011', 'WBP-FG-012'], 'new-process-recomputes-original-plan-and-engine-evidence', async () => {
      assert.equal(await strip.getAttribute('data-chain-context'), 'global');
      assert.equal(await strip.locator('[data-chain-node]').count(), 4);
      await p.shot('chain-physical-restart');
    });
    return;
  }
  await p.step(['WBP-FG-011.A001', 'WBP-FG-011.A004', 'WBP-FG-011.A005'], 'real-engine-global-three-reasons-solid-dashed-and-independent-toggle', async () => {
    const reasons = await strip.locator('[data-chain-edge-reason]').allTextContents();
    assert(reasons[0].includes('工艺前驱') && reasons[0].includes('0 分钟'));
    assert(reasons[1].includes('设备') && reasons[1].includes('30 分钟'));
    assert(reasons[2].includes('人员') && reasons[2].includes('30 分钟'));
    const lines = page.getByRole('img', { name: '当前计划关键链连线', exact: true });
    await lines.waitFor();
    const types = new Set();
    for (const key of ['Home', 'End']) {
      await page.getByLabel('分次报工甘特', { exact: true }).focus(); await page.keyboard.press(key);
      await page.mouse.move(10, 10);
      await page.waitForFunction(() => !!document.querySelector('.fg-chain-lines path'));
      const paths = await lines.locator('path').evaluateAll(nodes => nodes.map(node => ({ type: node.dataset.chainEdge,
        dash: node.getAttribute('stroke-dasharray'), stroke: getComputedStyle(node).stroke, d: node.getAttribute('d') })));
      for (const path of paths) { types.add(path.type); assert(path.stroke !== 'none' && !path.d.includes('NaN'));
        assert.equal(path.dash, path.type === 'process' ? null : '4 3'); }
      await p.shot('chain-lines-' + key);
    }
    assert(types.has('process') && types.has('operator'));
    await page.getByRole('checkbox', { name: '关键链连线', exact: true }).uncheck();
    await lines.waitFor({ state: 'detached' }); assert.equal(await strip.locator('[data-chain-node]').count(), 4);
    await page.getByRole('checkbox', { name: '关键链连线', exact: true }).check(); await lines.waitFor();
    await page.getByRole('checkbox', { name: '关键链', exact: true }).uncheck(); await strip.waitFor({ state: 'detached' });
    await page.getByRole('checkbox', { name: '关键链', exact: true }).check(); await strip.waitFor();
  });
  await p.step(['WBP-FG-011.A002'], 'non-global-task-has-real-related-chain-not-no-association', async () => {
    await page.getByLabel('搜索现场甘特', { exact: true }).fill('CHAIN-B4');
    const target = page.locator('[data-task-row="' + seed.task_refs[4] + '"] .fg-task-select').first();
    await target.waitFor();
    const response = await p.read(() => target.hover(), '/actual-gantt/chain');
    const related = response.data.critical_chain;
    assert.equal(related.target_task_ref, seed.task_refs[4]); assert.deepEqual(related.task_refs, [seed.task_refs[4]]);
    assert.equal(related.mode, 'related'); assert.equal(related.plan_task_count, 5);
    assert.equal(related.snapshot_ref, chain.snapshot_ref); assert.notEqual(related.engine_evidence_ref, chain.engine_evidence_ref);
    await page.waitForFunction(ref => document.querySelector('.fg-chain-strip')?.dataset.chainTarget === ref, seed.task_refs[4]);
    assert.equal(await strip.locator('[data-chain-node]').count(), 1);
    p.report.independent_related = response; await p.shot('independent-task-related-chain');
  });
  await p.step(['WBP-FG-011.A002', 'WBP-FG-011.A003', 'WBP-FG-012'], 'resource-group-target-backtrace-retains-other-resource-predecessor', async () => {
    await page.getByLabel('搜索现场甘特', { exact: true }).fill('Second lathe');
    const group = page.locator('.fg-group-row .fg-resource-label'); await group.waitFor();
    const response = await p.read(() => group.hover(), '/actual-gantt/chain');
    const related = response.data.critical_chain;
    assert.equal(related.target_task_ref, seed.task_refs[2]); assert.deepEqual(related.task_refs, seed.task_refs.slice(0, 3));
    assert.equal(related.plan_task_count, 5); assert.equal(related.snapshot_ref, chain.snapshot_ref);
    await page.waitForFunction(ref => document.querySelector('.fg-chain-strip')?.dataset.chainTarget === ref, seed.task_refs[2]);
    assert(await strip.locator('[data-chain-node="' + seed.task_refs[0] + '"]').isDisabled());
    assert((await strip.innerText()).includes('筛选内 2 / 3 个节点'));
    p.report.resource_related = response; await p.shot('resource-full-input-related-chain');
    await page.getByLabel('搜索现场甘特', { exact: true }).fill('');
    await page.mouse.move(10, 10);
    await strip.locator('[data-chain-node="' + seed.task_refs[2] + '"]').click();
    await page.getByRole('button', { name: '定位选中工序', exact: true }).click();
    const selected = page.locator('[data-task-row="' + seed.task_refs[2] + '"].is-selected').first(); await selected.waitFor();
    await p.shot('chain-node-precise-task-selection');
  });
}
run('chain', exercise, { once: true });
