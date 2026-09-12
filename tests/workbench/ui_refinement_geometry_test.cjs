'use strict';

// Real Chromium negative controls for the evidence collector, with no product/server dependencies.
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');
const { measure, measureTable, measureGantt } = require('./ui_refinement_geometry.cjs');
const BASE_CSS = `
* { box-sizing: border-box; }
body { margin: 0; font: 14px/20px Arial, sans-serif; }
.sidebar-nav { position: fixed; left: 16px; top: 16px; width: 140px; }
.sidebar-nav a { display: block; height: 32px; padding: 6px; color: black; }
main { margin: 80px 20px 0 200px; width: 760px; }
.mo-tools { width: 300px; }
.mo-tools label { display: block; white-space: nowrap; }
.dy-metrics { display: flex; gap: 12px; margin-top: 16px; }
.dy-metric { width: 160px; height: 64px; padding: 8px; background: lightgray; }
.dy-metric strong,.dy-metric small { display: block; }
.wb-col-actions.fixture-action { position: fixed; left: 240px; top: 220px; width: 140px; height: 32px; }
.fixture-action button { width: 100%; height: 100%; }
.blocker { position: fixed; z-index: 100; background: silver; }
.wb-table-frame { width: 620px; height: 180px; overflow: auto; isolation: isolate; }
table { width: 1100px; border-collapse: separate; border-spacing: 0; table-layout: fixed; }
th,td { height: 32px; padding: 3px 6px; text-align: left; background: white; }
thead th { position: sticky; top: 0; z-index: 3; }
th:last-child,td:last-child { width: 140px; }
.wb-col-actions { position: sticky; right: 0; z-index: 2; }
thead .wb-col-actions { z-index: 4; }
td button { width: 90px; height: 24px; }
`;
const NAV = '<nav class="sidebar-nav"><a class="nav-item" href="#batch">批次管理</a></nav>';
const NORMAL = '<div class="mo-tools"><label>当前正式计划</label></div>' +
  '<div class="dy-metrics"><div class="dy-metric"><strong>120</strong><small>待排工序</small></div>' +
  '<div class="dy-metric"><strong>80</strong><small>已排工序</small></div></div>' +
  '<div class="wb-col-actions fixture-action"><button>查看工序</button></div>';
const LONG_LABEL = '工序筛选条件与设备人员显示范围需要完整显示';
const REFERENCE = 'abcdef0123456789abcdef0123456789';
const SIZES = [{ width: 1366, height: 768 }, { width: 1280, height: 720 }];

function table(rows = 24) {
  return '<div class="batch-list-table wb-table-frame"><table><thead><tr>' +
    '<th>批次</th><th>图号</th><th class="wb-col-actions">操作</th></tr></thead><tbody>' +
    Array.from({ length: rows }, (_, index) => '<tr><td>批次 ' + (index + 1) + '</td><td>零件编号</td>' +
      '<td class="wb-col-actions"><button>查看 ' + (index + 1) + '</button></td></tr>').join('') +
    '</tbody></table></div>';
}

function check(result, id) {
  const entry = result.checks.find(row => row.id === id);
  assert(entry, 'Missing required measurement ' + id);
  return entry;
}

async function run(output) {
  assert(process.env.WORKBENCH_BROWSER, 'WORKBENCH_BROWSER must identify the installed Chromium 109');
  fs.mkdirSync(output, { recursive: true });
  const report = { browser: null, errors: [], cases: [], sources: [], production_data_tested: false };
  for (const name of ['ui_refinement_geometry.cjs', 'ui_refinement_geometry_test.cjs']) {
    const bytes = fs.readFileSync(path.join(__dirname, name));
    report.sources.push({ file: 'tests/workbench/' + name, sha256: crypto.createHash('sha256').update(bytes).digest('hex') });
  }
  const browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true });
  try {
    report.browser = browser.version();
    assert(report.browser.startsWith('109.'), 'This contract needs real Chromium 109');
    for (const viewport of SIZES) {
      const context = await browser.newContext({ viewport });
      const page = await context.newPage();
      page.on('pageerror', error => report.errors.push(error.message));
      await page.route('**/*', route => { report.errors.push('Unexpected request: ' + route.request().url()); return route.abort(); });
      async function sample(name, css, content, probe, verify) {
        const item = { id: viewport.width + '-' + name, name, viewport, passed: false };
        try {
          await page.setContent('<!doctype html><html lang="zh-CN" data-theme="light"><head><style>' + BASE_CSS + css +
            '</style></head><body>' + NAV + '<main>' + content + '</main></body></html>');
          await page.evaluate(() => document.fonts.ready);
          await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
          item.measurement = await page.evaluate(probe, 'fixture');
          verify(item.measurement);
          item.passed = true;
        } catch (error) { item.error = error.message; }
        item.screenshot = item.id + '.png';
        await page.screenshot({ path: path.join(output, item.screenshot) });
        report.cases.push(item);
      }
      await sample('visible-baseline', '', NORMAL, measure, result => {
        for (const id of ['G2', 'G4', 'G5', 'G6', 'L1', 'L2', 'L3']) assert.equal(check(result, id).ok, true, id);
      });
      for (const [name, css] of [
        ['label-parent-clipping', '.mo-tools{width:100px;overflow:hidden}.mo-tools label{width:350px}'],
        ['label-self-clipping', '.mo-tools label{width:100px;overflow:hidden}'],
      ]) {
        await sample(name, css, '<div class="mo-tools"><label>' + LONG_LABEL + '</label></div>', measure, result => {
          assert.equal(check(result, 'G4').ok, true, 'Root stays within viewport');
          assert.equal(check(result, 'L1').ok, false, 'Local text clipping must still fail');
          assert(check(result, 'L1').detail.clipped.length > 0);
        });
      }
      await sample('overlapping-metrics', '.dy-metric:nth-child(2){margin-left:-90px}', NORMAL, measure, result => {
        assert.equal(check(result, 'G4').ok, true);
        assert.equal(check(result, 'L2').ok, false);
        assert(check(result, 'L2').detail.overlaps.length > 0);
      });
      for (const [name, css, blockedName] of [
        ['sidebar-occlusion', '.blocker{left:12px;top:12px;width:148px;height:44px}', '批次管理'],
        ['action-occlusion', '.blocker{left:238px;top:218px;width:144px;height:36px}', '查看工序'],
      ]) {
        await sample(name, css, NORMAL + '<div class="blocker">遮挡层</div>', measure, result => {
          assert.equal(check(result, 'L3').ok, false);
          assert(check(result, 'L3').detail.blocked.some(row => row.name === blockedName));
        });
      }
      await sample('visible-internal-reference', '', '<p>' + REFERENCE + '</p>', measure, result => {
        assert.equal(check(result, 'G6').ok, false);
        assert.equal(check(result, 'G6').detail.references.length, 1);
      });
      await sample('collapsed-internal-reference', '', '<details class="wb-ref"><summary>查看诊断标识</summary><p>' +
        REFERENCE + '</p></details>', measure, result => assert.equal(check(result, 'G6').ok, true));
      await sample('fully-clipped-row-actions-are-not-click-targets', '',
        '<div style="height:20px;overflow:hidden"><div class="wb-col-actions" style="margin-top:50px"><button>卷出滚动框的操作</button></div></div>',
        measure, result => assert.equal(check(result, 'L3').ok, true));
      await sample('bounded-table', '', table(), measureTable, result => {
        assert.equal(result.ok, true, JSON.stringify(result.detail));
        assert(result.detail.scrollTop > 0 && result.detail.scrollLeft > 0, 'Both internal scroll axes must be exercised');
        assert(Math.abs(result.detail.headTop - result.detail.frameTop) <= 3);
        assert.equal(result.detail.actionHit, true, 'A visible row action must remain reachable after scrolling');
      });
      for (const [name, css, markup] of [
        ['offset-sticky-header', 'thead th{top:60px}', table()],
        ['natural-height-table', '.wb-table-frame{height:auto}', table(10)],
        ['non-sticky-header', 'thead th{position:static}', table()],
        ['table-without-horizontal-scroll', 'table{width:100%}', table()],
      ]) {
        await sample(name, css, markup, measureTable, result => assert.equal(result.ok, false, JSON.stringify(result.detail)));
      }
      const gantt = '<div class="plan-gantt"><div data-plan-task style="width:500px;height:32px">第一条工序</div></div>';
      await sample('visible-gantt-row', '', gantt, measureGantt, result => assert.equal(result.ok, true));
      await sample('gantt-row-below-viewport', '.plan-gantt{position:absolute;top:1000px}', gantt, measureGantt,
        result => assert.equal(result.ok, false));
      await sample('gantt-row-locally-clipped', '.plan-gantt{height:4px;overflow:hidden}', gantt, measureGantt,
        result => assert.equal(result.ok, false, 'Four visible pixels cannot prove a readable first row'));
      await sample('gantt-row-partially-below-viewport', '.plan-gantt{position:absolute;bottom:-12px}', gantt, measureGantt,
        result => assert.equal(result.ok, false, 'A partially visible task bar is not a usable first row'));
      await sample('gantt-row-mostly-visible-but-clipped', '.plan-gantt{height:24px;overflow:hidden}', gantt, measureGantt,
        result => assert.equal(result.ok, false, 'Twenty-four visible pixels do not prove the complete task bar'));
      await context.close();
    }
    assert.deepEqual(report.errors, []);
  } finally {
    await browser.close();
    fs.writeFileSync(path.join(output, 'geometry-contract-results.json'), JSON.stringify(report, null, 2));
  }
  const failed = report.cases.filter(row => !row.passed);
  console.log(JSON.stringify({ output, browser: report.browser, cases: report.cases.length,
    failed: failed.map(row => ({ id: row.id, error: row.error, measurement: row.measurement })) }));
  assert.equal(failed.length, 0, 'Geometry probe misclassified isolated positive/negative controls');
  return report;
}

if (require.main === module) {
  if (process.argv.length !== 3) throw new Error('Usage: node ui_refinement_geometry_test.cjs <output-dir>');
  run(path.resolve(process.argv[2])).catch(error => { console.error(error); process.exitCode = 1; });
}
module.exports = { run };
