'use strict';
const assert = require('node:assert/strict');

async function analysisMetrics(page, report, h, flush) {
  await page.locator('[data-candidate-analysis]').waitFor(); await flush();
  const data = h.last((_data, row) => row.url.endsWith('/analysis'));
  assert.equal(data.candidate_ref, report.candidate.candidate.candidate_ref);
  assert.equal(data.run_ref, report.candidate.candidate.run_ref);
  assert.deepEqual(data.operations.operation_refs.slice().sort(), report.candidate.tasks.map(row => row.operation_ref).sort());
  const section = page.getByRole('region', { name: '完整候选比较摘要', exact: true });
  const labels = { overdue_count: '预计超期批次', total_tardiness_hours: '总拖期（小时）', changed_operation_count: '调整工序', machine_change_count: '换设备数' };
  assert.equal(await section.locator('[data-analysis-metric]').count(), 4);
  for (const [key, label] of Object.entries(labels)) {
    const metric = data.metrics[key], cell = section.locator('[data-analysis-metric="' + key + '"]');
    assert((await cell.innerText()).includes(label));
    if (metric.value === null) {
      assert(metric.reason && metric.unknown_count > 0);
      assert((await cell.innerText()).includes('已知小计 ' + metric.known_subtotal));
      assert((await cell.innerText()).includes('待确认 ' + metric.unknown_count + ' / ' + metric.total_count));
      await cell.getByText('依据不足', { exact: true }).click();
      assert((await cell.innerText()).includes(metric.reason.message));
    } else assert((await cell.locator('dd').innerText()).includes(String(metric.value)));
  }
  assert.equal(data.basis.recommendation, null);
  assert.equal(data.basis.scope, 'full_candidate_and_full_admission_baseline');
  assert.equal(data.basis.current_entities_consulted, false);
  assert(Object.values(data.metrics).some(metric => metric.value === null), 'This legacy fixture must expose missing whole-baseline evidence');
  const scopeText = await page.getByLabel('候选变化与取舍', { exact: true }).innerText();
  assert(scopeText.includes('调整工序：') && scopeText.includes('换设备：'), scopeText);
  assert(!scopeText.includes('优化收益'), 'The scope block states saved-arrangement changes only');
  await section.scrollIntoViewIfNeeded(); await h.shot('candidate-four-metrics-and-unknown');
  return data;
}

async function cancelAnalysisRead(page, report, h, flush, expected) {
  const start = report.requests.length, session = await page.context().newCDPSession(page);
  try {
    await session.send('Network.enable');
    await session.send('Network.emulateNetworkConditions', { offline: false, latency: 800, downloadThroughput: -1, uploadThroughput: -1 });
    await h.button('刷新候选方案').click();
    await h.button('取消候选比较读取').click();
    await page.getByText('候选比较读取已取消。', { exact: true }).waitFor(); await flush();
    assert.equal(await page.locator('[data-candidate-analysis]').count(), 0);
    assert(report.requests.slice(start).every(row => row.method === 'GET'));
    report.analysis_cancel = { physical_fault: 'Chromium network latency 800ms; no response replacement',
      candidate_ref: expected.candidate_ref, prior_result_hidden: true, requests: report.requests.slice(start) };
    await h.shot('candidate-analysis-read-cancelled');
  } finally {
    await session.send('Network.emulateNetworkConditions', { offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1 });
    await session.detach();
  }
  await h.button('刷新候选比较').click();
  await page.locator('[data-candidate-analysis]').waitFor(); await flush();
  assert.deepEqual(h.last((_data, row) => row.url.endsWith('/analysis')), expected);
}

async function candidateAnalysis(page, report, h, flush) {
  const { action, button, shot, last } = h;
  await action(['WBP-ANA-001.metrics', 'WBP-ANA-001.unavailable', 'WBP-ANA-001.tradeoffs'], async () => {
    report.candidate_analysis = await analysisMetrics(page, report, h, flush);
    await cancelAnalysisRead(page, report, h, flush, report.candidate_analysis);
  });
  await action(['WBP-ANA-003.delivery', 'WBP-ANA-003.batch-gantt'], async () => {
    const start = report.requests.length, data = report.candidate_analysis;
    await page.getByRole('tablist', { name: '候选明细类别', exact: true }).getByRole('tab', { name: '交付风险', exact: true }).click();
    const table = page.getByRole('table', { name: '候选批次交付对照', exact: true }); await table.waitFor();
    for (const batch of data.batches) {
      const row = table.locator('[data-analysis-batch="' + batch.batch_ref + '"]'), cells = row.getByRole('cell');
      assert((await cells.nth(0).innerText()).includes(batch.batch_id));
      assert.equal(await cells.nth(1).innerText(), batch.after.due_date || '未记录');
      for (const [index, side] of [[2, 'before'], [3, 'after']]) {
        const expected = batch[side].planned_finish;
        assert((await cells.nth(index).innerText()).includes(expected ? expected.slice(0, 16).replace('T', ' ') : '暂无数据'));
      }
      assert((await cells.nth(4).innerText()).includes(batch.delay_delta_hours === null ? '未知' : batch.delay_delta_hours === 0 ? '不变' : batch.delay_delta_hours > 0 ? '增加' : '减少'));
    }
    await table.scrollIntoViewIfNeeded(); await shot('candidate-batch-before-after');
    const batch = data.batches.find(row => row.batch_id === 'B1');
    await button('查看批次甘特 B1', table).click();
    await page.getByRole('heading', { name: '候选甘特', exact: true }).waitFor(); await flush();
    const shown = last(value => value.candidate && value.tasks);
    assert.equal(shown.candidate.candidate_ref, data.candidate_ref); assert.equal(shown.batch_ref, batch.batch_ref);
    assert.equal(shown.time_scope.range_start, null); assert.equal(shown.time_scope.range_end, null);
    assert.deepEqual(shown.tasks, report.candidate.tasks.filter(task => task.batch_ref === batch.batch_ref));
    assert.deepEqual(last((_data, row) => row.url.endsWith('/analysis')), data);
    await h.caption(data.candidate_ref, '候选方案'); await shot('candidate-batch-exact-gantt');
    await page.reload(); await page.getByRole('heading', { name: '候选甘特', exact: true }).waitFor(); await flush();
    const refreshed = last(value => value.candidate && value.tasks);
    assert.equal(refreshed.batch_ref, batch.batch_ref); assert.deepEqual(refreshed.tasks, shown.tasks);
    assert.equal(refreshed.candidate.candidate_ref, data.candidate_ref);
    report.analysis_gantt_recovery = { candidate_ref: data.candidate_ref, batch_ref: batch.batch_ref, read_view: 'gantt', actual_reload: true };
    await page.goBack(); await page.getByRole('table', { name: '候选批次交付对照', exact: true }).waitFor(); await flush();
    await page.reload(); await page.getByRole('table', { name: '候选批次交付对照', exact: true }).waitFor(); await flush();
    assert.deepEqual(last((_data, row) => row.url.endsWith('/analysis')), data);
    assert.equal(await page.getByRole('tablist', { name: '候选明细类别', exact: true }).getByRole('tab', { name: '交付风险', exact: true }).getAttribute('aria-selected'), 'true');
    report.analysis_delivery_recovery = { candidate_ref: data.candidate_ref, batch_refs: data.batch_refs, tab: 'delivery', actual_reload: true };
    await shot('candidate-batch-tab-refreshed');
    await page.getByRole('tab', { name: '采用记录', exact: true }).click();
    await page.getByText('这个候选方案还没有采用记录。', { exact: true }).waitFor(); await flush();
    assert.deepEqual(last((_data, row) => row.url.endsWith('/adoptions')).items, []);
    await shot('candidate-adoption-history-empty');
    await page.getByRole('tab', { name: '任务安排', exact: true }).click();
    assert(report.requests.slice(start).every(row => row.method === 'GET'));
  });
}

async function candidateHistory(page, report, h, flush) {
  await h.action(['WBP-ANA-003.history'], async () => {
    const start = report.requests.length;
    await page.goBack(); await page.locator('[data-run-candidate-workspace]').waitFor();
    await page.getByRole('tab', { name: '采用记录', exact: true }).click();
    await page.getByRole('table', { name: '候选采用记录', exact: true }).waitFor(); await flush();
    const data = h.last((_data, row) => row.url.endsWith('/adoptions'));
    assert.equal(data.candidate_ref, report.candidate.candidate.candidate_ref); assert.equal(data.total, 1);
    const item = data.items[0], committed = report.responses.find(row => row.url.endsWith('/adopt') && row.body.ok === true);
    assert(committed); assert.equal(item.receipt_ref, committed.body.receipt_ref);
    assert.equal(item.official_plan.plan_ref, report.first_official.plan.plan_ref);
    assert.equal(item.official_plan.version, 5); assert.equal(item.row_count, report.first_official.tasks.length);
    assert.equal(item.can_open, true); assert.deepEqual(item.evidence_gaps, []);
    assert.equal(item.adoption.reason, '任务D真实全入口验收，保留原身份与完整范围');
    await h.shot('candidate-adoption-history-original');
    await page.reload(); await page.getByRole('table', { name: '候选采用记录', exact: true }).waitFor(); await flush();
    assert.deepEqual(h.last((_data, row) => row.url.endsWith('/adoptions')), data);
    assert.equal(await page.getByRole('tab', { name: '采用记录', exact: true }).getAttribute('aria-selected'), 'true');
    report.candidate_adoption_history = data;
    report.analysis_history_recovery = { candidate_ref: data.candidate_ref, receipt_ref: item.receipt_ref, tab: 'history', actual_reload: true };
    await h.shot('candidate-adoption-history-refreshed');
    await h.button('打开原采用计划 v5').click(); await page.locator('[data-plan-workspace] .plan-main').waitFor(); await flush();
    assert.deepEqual(h.last(value => value.plan && value.tasks).tasks, report.first_official.tasks);
    assert.equal(h.last(value => value.plan && value.tasks).plan.plan_ref, item.official_plan.plan_ref);
    assert(report.requests.slice(start).every(row => row.method === 'GET'));
  });
}

async function restartCandidateAnalysis(page, original, report, h, flush) {
  await h.action(['WBP-ANA-001.metrics', 'WBP-ANA-003.history'], async () => {
    const ref = original.candidate.candidate.candidate_ref, run = original.candidate.candidate.run_ref;
    await h.button('排产记录', page.locator('.scheduling-navigation')).click();
    const runRow = page.getByRole('table', { name: '排产记录', exact: true }).locator('[data-run-ref="' + run + '"]');
    await runRow.waitFor(); assert.equal(await runRow.count(), 1);
    await runRow.getByRole('button', { name: /^查看 .* 提交的排产记录$/ }).click();
    const candidateRow = page.getByRole('table', { name: '候选比较', exact: true }).locator('[data-candidate-ref="' + ref + '"]');
    await candidateRow.waitFor(); assert.equal(await candidateRow.count(), 1);
    await h.button('查看候选 ' + original.candidate.candidate.label, candidateRow).click(); await page.locator('[data-candidate-analysis]').waitFor(); await flush();
    assert.deepEqual(h.last((_data, row) => row.url.endsWith('/analysis')), original.candidate_analysis);
    await h.shot('new-process-candidate-analysis');
    await page.getByRole('tab', { name: '采用记录', exact: true }).click();
    await page.getByRole('table', { name: '候选采用记录', exact: true }).waitFor(); await flush();
    assert.deepEqual(h.last((_data, row) => row.url.endsWith('/adoptions')), original.candidate_adoption_history);
    report.reopened_candidate_analysis = { candidate_ref: ref, run_ref: run, receipt_ref: original.candidate_adoption_history.items[0].receipt_ref };
    await h.shot('new-process-original-candidate-history');
    await h.button('打开原采用计划 v5').click(); await page.locator('[data-plan-workspace] .plan-main').waitFor(); await flush();
    assert.deepEqual(h.last(value => value.plan && value.tasks).tasks, original.first_official.tasks);
    assert.equal(h.last(value => value.plan && value.tasks).plan.plan_ref, original.first_official.plan.plan_ref);
    await h.caption(original.first_official.plan.plan_ref, '历史正式');
    assert(report.requests.every(row => row.method === 'GET'));
  });
}
module.exports = { candidateAnalysis, candidateHistory, restartCandidateAnalysis };
