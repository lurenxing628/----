'use strict';
const assert = require('node:assert/strict');
const {inspect, shot} = require('./detail008_prototype_support.cjs');

async function probeDetails(env, page, click, entry) {
  const records = new Map(env.report.record_graph.map(row => [row.code, row]));
  const testedEdges = new Set(), observedRoots = new Set();
  const close = async () => {
    await click(page.locator('.apsd-panel [data-apsd-close]'), ['close_unified_drawer']);
    await page.locator('.apsd-panel').waitFor({state: 'detached'});
  };
  const capture = async chain => {
    await page.locator('.apsd-panel.on').waitFor();
    const drawer = await page.locator('.apsd-panel').evaluate(node => ({
      code: node.querySelector('.apsd-code')?.textContent.trim(), text: node.innerText,
      links: [...node.querySelectorAll('[data-apsd-go]')].map(a => a.getAttribute('data-apsd-go')),
      foot: [...node.querySelectorAll('[data-apsd-act]')].map(a => a.getAttribute('data-apsd-act'))}));
    drawer.type = records.get(drawer.code)?.type || 'generic';
    drawer.chain = chain;
    env.report.drawers.push(drawer);
    if (['batch', 'plan', 'generic'].includes(drawer.type)) {
      env.report.found_target = {...drawer, screenshot: await shot(env, page, 'FOUND-target')};
      env.save();
      throw new Error('A real DETAIL-008 entry was found. Stop the unreachable decision.');
    }
    return drawer;
  };
  const root = async (locator, chain) => {
    await click(locator(), chain);
    let drawer = await capture(chain);
    observedRoots.add(drawer.code);
    if (!env.report.drawers.some(row => row !== drawer && row.type === drawer.type)) {
      drawer.screenshot = await shot(env, page, 'drawer-' + drawer.type);
    }
    for (const target of drawer.links) {
      const edge = drawer.code + '>' + target;
      if (testedEdges.has(edge)) continue;
      await click(page.locator('.apsd-panel [data-apsd-go="' + target + '"]'), [...chain, target]);
      const nested = await capture([...chain, target]);
      assert.equal(nested.code, target);
      assert.equal(nested.links.length, 0, 'New nested links require extending the bounded probe');
      testedEdges.add(edge);
      await close();
      await click(locator(), chain);
      drawer = await capture(chain);
    }
    await close();
  };
  await entry('calib');
  const parts = await page.locator('.calib-workbench a.bd-link').allTextContents();
  assert.equal(parts.length, 5);
  for (let index = 0; index < parts.length; index++) {
    await root(() => page.locator('.calib-workbench a.bd-link').nth(index), ['calib', 'row:' + index, parts[index]]);
  }
  await entry('process');
  for (const view of env.report.controls) {
    const node = view.native;
    const selector = '[data-node="' + node.node + '"]' + (node.sub ? '[data-sub="' + node.sub + '"]' : ':not([data-sub])');
    await click(page.locator('.plana ' + selector), ['process', node]);
    const links = view.controls.filter(row => row.tag === 'A' && row.class?.split(' ').includes('lnk') && row.known_type && !row.native_part_row);
    for (const link of links) {
      const locate = () => page.locator('#content a.lnk').filter({hasText: new RegExp('^' + link.text + '$')});
      await root(locate, ['process', node, link.text]);
    }
    if (links.length) {
      const locate = () => page.locator('#content tr').filter({has: page.locator('a.lnk', {hasText: links[0].text})})
        .locator('.rowact .mini:not(.danger)').first();
      await root(locate, ['process', node, 'row_action', links[0].text]);
    }
  }
  env.report.actual_roots = [...observedRoots].sort();
  env.report.actual_nested_edges = [...testedEdges].sort();
  const reachable = new Set(observedRoots);
  let changed = true;
  while (changed) {
    changed = false;
    for (const code of [...reachable]) for (const target of records.get(code).links) {
      if (!reachable.has(target)) { reachable.add(target); changed = true; }
    }
  }
  env.report.graph_closure = [...reachable].sort();
  env.report.incoming_target_edges = env.report.record_graph.flatMap(row => row.links
    .filter(code => ['batch', 'plan'].includes(records.get(code)?.type)).map(code => ({from: row.code, to: code})));
  assert.deepEqual(env.report.incoming_target_edges, []);
  env.report.alternative_details = [];
  await entry('batches');
  const batches = await page.locator('.batch-id-link').allTextContents();
  for (const code of batches) {
    await click(page.locator('.batch-id-link').filter({hasText: code}), ['batches', code]);
    const detail = await inspect(page);
    assert.equal(detail.drawer_count, 0);
    assert(await page.getByRole('button', {name: '\u2190 \u8fd4\u56de\u5217\u8868', exact: true}).isVisible());
    env.report.alternative_details.push({chain: ['batches', code], kind: 'current_batch_detail', ...detail,
      screenshot: await shot(env, page, 'current-batch-' + code)});
    await click(page.getByRole('button', {name: '\u2190 \u8fd4\u56de\u5217\u8868', exact: true}), ['batches', 'back']);
  }
  await entry('analysis');
  const schemes = await page.locator('input[name="scheme"]').evaluateAll(nodes => nodes.map(node => ({
    value: node.value, label: node.closest('label')?.innerText})));
  for (const scheme of schemes) {
    await click(page.locator('input[name="scheme"][value="' + scheme.value + '"]'), ['analysis', scheme]);
    const detail = await inspect(page);
    assert.equal(detail.drawer_count, 0);
    env.report.alternative_details.push({chain: ['analysis', scheme], kind: 'current_plan_selection', ...detail});
  }
  await click(page.getByRole('button', {name: '\u67e5\u770b\u6b64\u65b9\u6848\u7518\u7279', exact: true}), ['analysis', 'current_gantt']);
  await page.waitForURL(url => url.searchParams.get('view') === 'gantt');
  const tasks = await page.locator('.tr-bar[data-task]').evaluateAll(nodes => nodes.map(node => node.dataset.task));
  for (const task of tasks) {
    await click(page.locator('.tr-bar[data-task="' + task + '"]'), ['gantt', task]);
    assert.equal(await page.locator('.apsd-panel').count(), 0);
    const text = await page.locator('[aria-label="\u8ba1\u5212\u5de5\u5e8f\u8be6\u60c5"]').innerText();
    env.report.alternative_details.push({chain: ['gantt', task], kind: 'current_plan_operation', text, drawer_count: 0});
  }
  await shot(env, page, 'current-plan-operation');
  env.report.detail_clicks_complete = true;
}

async function probeCodeCollision(env, page, click, entry) {
  await entry('process');
  await click(page.locator('.plana [data-node="material"]'), ['process', 'material']);
  env.report.before_form = await inspect(page);
  await click(page.getByRole('button', {name: '\u65b0\u589e\u7269\u6599', exact: true}), ['process', 'material', 'add_material']);
  const form = page.getByRole('dialog').filter({hasText: '\u65b0\u589e\u7269\u6599'});
  await form.waitFor();
  env.report.visible_form = await inspect(page);
  const code = 'B202605-018', name = 'DETAIL008 reachability probe';
  for (const [key, value] of [['code', code], ['name', name]]) {
    await click(form.locator('input[data-k="' + key + '"]'), ['new_material', key]);
    env.report.steps.push({action: 'actual_keyboard_typing', field: key, value});
    await page.keyboard.type(value);
  }
  await click(form.getByRole('button', {name: '\u4fdd\u5b58\u5e76\u52a0\u5165\u5217\u8868', exact: true}),
    ['process', 'material', 'save_temporary_prototype_row', code]);
  await form.waitFor({state: 'detached'});
  env.report.after_save = await inspect(page);
  const row = page.locator('#content a.lnk').filter({hasText: new RegExp('^' + code + '$')});
  assert.equal(await row.count(), 1);
  await click(row, ['process', 'material', 'temporary_row_code', code]);
  await page.locator('.apsd-panel.on').waitFor();
  const drawer = await page.locator('.apsd-panel').evaluate(node => ({code: node.querySelector('.apsd-code').textContent.trim(),
    text: node.innerText, foot: [...node.querySelectorAll('[data-apsd-act]')].map(a => a.getAttribute('data-apsd-act'))}));
  drawer.type = await page.evaluate(code => window.APSDetail.RECORDS[code].type, code);
  assert.equal(drawer.code, code);
  assert.equal(drawer.type, 'batch');
  env.report.found_target = {...drawer, chain: ['process', 'material', 'add_material',
    {code, name}, 'save_and_add', 'click_code'], screenshot: await shot(env, page, 'FOUND-batch-through-native-form')};
  env.report.index_click_events = await page.evaluate(() => window.__detail008Clicks);
  assert(env.report.index_click_events.every(row => row.trusted));
  env.report.conclusion = 'detail008_batch_reachable_through_existing_native_form_code_collision';
  env.report.stop_unreachable_decision = true;
  env.report.mutation_scope = 'One temporary DOM row in an isolated original-prototype context; no source or production writes';
  env.save();
}

module.exports = {probeDetails, probeCodeCollision};
