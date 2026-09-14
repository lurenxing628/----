/* Isolated custom date/time picker. No global input host, production API or Win7 hardware proof. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const crypto = require('node:crypto');
const { chromium } = require('playwright');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), output = process.argv[2];
if (!output) throw new Error('Pass an artifact directory');
fs.mkdirSync(output, { recursive: true });
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
const files = ['resource-contract.js', 'CalendarContract.js', 'ResourceControls.jsx', 'WorkbenchControlStyles.jsx', 'WorkbenchDatePickerModel.js', 'WorkbenchDatePicker.jsx'];
const sources = files.map(file => ({ path: 'frontend/workbench/app/' + file, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', file), 'utf8') }));
const compiled = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true });
const scripts = new Map(compiled.outputs.map((item, index) => ['/fixture/' + files[index] + '.js', item.code]));
const assets = new Map(manifest.files.map(item => [item.path, item]));
const fixtureCode = `
window.fixture={calls:[],closed:0,serial:0,escape:[],nativeUI:[]};
['showPicker','reportValidity'].forEach(method=>{HTMLInputElement.prototype[method]=function(){fixture.nativeUI.push(method);throw new Error('Native picker or bubble was invoked');};});
document.addEventListener('keydown',event=>{if(event.key==='Escape')fixture.escape.push({prevented:event.defaultPrevented});});
let fixtureRoot=ReactDOM.createRoot(document.getElementById('fixture-root'));
function Harness({spec}) {
 return React.createElement(React.Fragment,null,React.createElement(WorkbenchControlStyles),
 React.createElement('div',{className:'wb-control-popup',role:'dialog','aria-label':'日期时间组件夹具',style:{position:'relative',maxHeight:'none',width:320,maxWidth:'100%'}},
 React.createElement(WorkbenchDatePicker,{...spec,onCommit:value=>fixture.calls.push(value),onClose:()=>fixture.closed++})));
}
window.mountFixture=spec=>{fixture.calls=[];fixture.closed=0;fixture.escape=[];fixture.spec=spec;fixtureRoot.render(React.createElement(Harness,{spec,key:++fixture.serial}));};
window.updateFixture=spec=>{fixture.spec=spec;fixtureRoot.render(React.createElement(Harness,{spec,key:fixture.serial}));};
`;
const html = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
  '<link rel="icon" href="/static/' + manifest.icon + '"><script src="/static/' + manifest.theme_script + '"></script>' +
  manifest.styles.map(file => '<link rel="stylesheet" href="/static/' + file + '">').join('') +
  '</head><body class="aps-workbench"><main class="plana" style="padding:24px"><p>日期时间组件验证 · 无生产数据</p><div id="fixture-root"></div></main>' +
  manifest.scripts.filter(file => file.startsWith('workbench/vendor/') || file.startsWith('workbench/assets/foundation-')).map(file => '<script src="/static/' + file + '"></script>').join('') +
  Array.from(scripts.keys(), file => '<script src="' + file + '"></script>').join('') + '<script>' + fixtureCode + '</script></body></html>';
const server = http.createServer((req, res) => {
  const name = new URL(req.url, 'http://fixture').pathname;
  if (name === '/') { res.setHeader('Content-Type', 'text/html;charset=utf-8'); res.end(html); return; }
  if (scripts.has(name)) { res.setHeader('Content-Type', 'application/javascript'); res.end(scripts.get(name)); return; }
  const asset = assets.get(name.slice('/static/'.length));
  if (!name.startsWith('/static/') || !asset) { res.writeHead(404); res.end(); return; }
  res.setHeader('Content-Type', asset.mime); res.end(fs.readFileSync(path.join(root, 'static', asset.path)));
});
const result = { scope: 'isolated-date-time-component', global_host_tested: false, production_persistence_tested: false, win7_hardware_tested: false,
  probe_sha256: crypto.createHash('sha256').update(fs.readFileSync(__filename)).digest('hex'),
  sources: sources.map(item => ({ path: item.path, sha256: crypto.createHash('sha256').update(item.code).digest('hex') })), cases: [], errors: [], external: [], screenshots: [] };
let page, variant;
const button = name => page.getByRole('button', { name, exact: true });
const day = name => page.getByRole('gridcell', { name, exact: true });
const field = name => page.getByLabel(name, { exact: true });
async function mount(spec) { await page.evaluate(spec => mountFixture(spec), spec); await page.locator('[data-picker-type="' + spec.type + '"]').waitFor(); }
async function calls(expected) { assert.deepEqual(await page.evaluate(() => fixture.calls), expected); }
async function unavailable(name) { assert.equal(await day(name).getAttribute('aria-disabled'), 'true'); }
async function allowed(name) { assert.equal(await day(name).getAttribute('aria-disabled'), 'false'); }
async function pick(name) { await allowed(name); await day(name).click(); }
async function fillTime(hour, minute, second, fraction) {
  if (hour !== undefined) await field('时').fill(hour);
  if (minute !== undefined) await field('分').fill(minute);
  if (second !== undefined) await field('秒').fill(second);
  if (fraction !== undefined) await field('毫秒').fill(fraction);
}
async function openMonths() {
  assert.equal(await button('选择月份').locator('svg').count(), 1);
  await button('选择月份').click(); await page.locator('[data-picker-view="months"]').waitFor();
  assert.equal(await page.getByRole('gridcell').count(), 12); assert.equal(await button('返回日历').getAttribute('aria-expanded'), 'true');
  assert.equal(await button('返回日历').locator('svg').count(), 1);
}
async function dateView() { await page.locator('[data-picker-view="days"]').waitFor(); }
async function bounds() {
  return page.evaluate(() => Object.fromEntries(['.wb-control-popup', '.wb-picker-grid'].map(selector => {
    const rect = document.querySelector(selector).getBoundingClientRect();
    return [selector, { width: rect.width, height: rect.height }];
  })));
}
async function shot(name) {
  await page.evaluate(() => document.fonts.ready);
  const geometry = await page.evaluate(() => {
    const popup = document.querySelector('.wb-control-popup'), r = popup.getBoundingClientRect();
    return { viewport: [innerWidth, innerHeight], popup: { left: r.left, right: r.right, top: r.top, bottom: r.bottom },
      scroll: document.documentElement.scrollWidth,
      overflow: Array.from(popup.querySelectorAll('button,input')).filter(el => { const b = el.getBoundingClientRect(); return b.left < r.left - 1 || b.right > r.right + 1 || b.bottom > r.bottom + 1; }).map(el => el.outerHTML),
      clipped: Array.from(popup.querySelectorAll('button,label')).filter(el => el.scrollWidth > el.clientWidth + 1).map(el => el.textContent),
      native_controls: popup.querySelectorAll('select,input[type="date"],input[type="time"],input[type="month"],input[type="datetime-local"],input[type="number"]').length,
      icon_buttons: Array.from(popup.querySelectorAll('.wb-picker-nav')).map(el => ({ label: el.getAttribute('aria-label'), svg: !!el.querySelector('svg') })) };
  });
  assert(geometry.popup.left >= 0 && geometry.popup.right <= geometry.viewport[0] && geometry.popup.bottom <= geometry.viewport[1]);
  assert(geometry.scroll <= geometry.viewport[0]); assert.deepEqual(geometry.overflow, []); assert.deepEqual(geometry.clipped, []);
  assert.equal(geometry.native_controls, 0); assert(geometry.icon_buttons.every(item => item.svg && item.label));
  const file = variant + '-' + name + '.png'; await page.screenshot({ path: path.join(output, file) }); result.screenshots.push({ file, geometry });
}
async function run(name, task) {
  try { await task(); result.cases.push({ variant, name, passed: true }); }
  catch (error) { result.cases.push({ variant, name, passed: false, message: error.message }); await page.screenshot({ path: path.join(output, variant + '-' + name + '-failure.png') }); throw error; }
}
async function cases() {
  await run('empty-date-does-not-commit-today', async () => {
    await mount({ type: 'date', value: '' }); await calls([]); assert.equal(await page.locator('[role="gridcell"][aria-selected="true"]').count(), 0);
    const current = await page.evaluate(() => WorkbenchDatePickerModel.today()); await pick(current); await calls([current]); await shot('date');
  });
  await run('exactly-one-initial-focus-target', async () => {
    for (const [type, value, expected] of [['date', '2026-09-09', '2026-09-09'], ['month', '2026-09', '2026-09'], ['datetime-local', '2026-09-09T08:30', '2026-09-09'], ['time', '', null]]) {
      await mount({ type, value }); const target = page.locator('[data-picker-initial]'); assert.equal(await target.count(), 1);
      assert.equal(await target.getAttribute('data-date'), expected); await target.focus();
      if (type === 'time') { assert.equal(await field('时').inputValue(), ''); await page.keyboard.press('ArrowUp'); assert.equal(await field('时').inputValue(), '00'); }
      else { await page.keyboard.press('ArrowRight'); assert.equal(await page.locator(':focus').getAttribute('data-date'), type === 'month' ? '2026-10' : '2026-09-10'); }
      await calls([]);
    }
  });
  await run('empty-time-requires-explicit-fields-and-confirm', async () => {
    await mount({ type: 'time', value: '' }); assert.equal(await field('时').inputValue(), ''); assert.equal(await field('分').inputValue(), ''); assert(await button('确认').isDisabled());
    await fillTime('8'); assert(await button('确认').isDisabled()); await calls([]);
    await fillTime(undefined, '15'); assert(await button('确认').isEnabled()); await calls([]); await button('确认').click(); await calls(['08:15']); await shot('time');
  });
  await run('empty-datetime-date-first-requires-time', async () => {
    await mount({ type: 'datetime-local', value: '', min: '2026-09-01T00:00' }); await pick('2026-09-09'); await calls([]);
    assert(await button('确认').isDisabled()); assert.equal(await field('时').inputValue(), ''); assert.equal(await field('分').inputValue(), '');
    await fillTime('22', '30'); await button('确认').click(); await calls(['2026-09-09T22:30']); await shot('datetime');
  });
  await run('empty-datetime-time-first-never-guesses-date', async () => {
    await mount({ type: 'datetime-local', value: '' }); await fillTime('0', '0'); assert(await button('确认').isDisabled()); await calls([]);
    assert(await page.getByText('尚未选择日期', { exact: true }).isVisible()); await button('今天').click(); await calls([]); await button('确认').click();
    await calls([await page.evaluate(() => WorkbenchDatePickerModel.today() + 'T00:00')]);
  });
  await run('clear-cancel-and-escape-ownership', async () => {
    for (const [type, value] of [['date', '2026-09-09'], ['month', '2026-09'], ['time', '12:00'], ['datetime-local', '2026-09-09T12:00']]) {
      await mount({ type, value }); await button('取消').click(); await calls([]); assert.equal(await page.evaluate(() => fixture.closed), 1);
      await button('关闭日期时间选择').click(); assert.equal(await page.evaluate(() => fixture.closed), 2);
      await button('清除').click(); await calls(['']); await page.keyboard.press('Escape');
      assert.deepEqual(await page.evaluate(() => fixture.escape), [{ prevented: false }]);
    }
  });
  await run('gregorian-leap-days-and-low-years', async () => {
    for (const [year, leap] of [['0001', false], ['0004', true], ['0099', false], ['0100', false], ['1900', false], ['2000', true], ['2024', true], ['2100', false], ['9999', false]]) {
      await mount({ type: 'date', value: year + '-02-15' }); assert.equal(await day(year + '-02-29').count(), leap ? 1 : 0);
      const target = year + '-02-' + (leap ? '29' : '28'); await pick(target); await calls([target]);
    }
  });
  await run('year-domain-boundary-and-invalid-draft', async () => {
    await mount({ type: 'date', value: '0001-01-01' }); assert(await button('上个月').isDisabled());
    await day('0001-01-01').focus(); await page.keyboard.press('ArrowLeft'); assert.equal(await page.locator(':focus').getAttribute('data-date'), '0001-01-01');
    await field('年份').fill('0000'); await page.keyboard.press('Enter'); assert(await page.getByText('年份须为 1 至 9999。', { exact: true }).isVisible()); await calls([]);
    await field('年份').fill('99'); await page.keyboard.press('Enter'); assert.equal(await field('年份').inputValue(), '0099'); await pick('0099-01-02'); await calls(['0099-01-02']);
    await mount({ type: 'date', value: '9999-12-31' }); assert(await button('下个月').isDisabled()); await day('9999-12-31').focus(); await page.keyboard.press('ArrowRight');
    assert.equal(await page.locator(':focus').getAttribute('data-date'), '9999-12-31'); await page.keyboard.press('Enter'); await calls(['9999-12-31']);
  });
  await run('keyboard-grid-arrows-home-end-page-navigation', async () => {
    await mount({ type: 'date', value: '2024-02-29' }); await day('2024-02-29').focus();
    for (const [key, expected] of [['ArrowRight', '2024-03-01'], ['ArrowDown', '2024-03-08'], ['ArrowLeft', '2024-03-07'], ['ArrowUp', '2024-02-29'], ['Home', '2024-02-26'], ['End', '2024-03-03'], ['PageUp', '2024-02-03'], ['Shift+PageDown', '2025-02-03']]) {
      await page.keyboard.press(key); assert.equal(await page.locator(':focus').getAttribute('data-date'), expected);
    }
    await calls([]); await page.keyboard.press('Enter'); await calls(['2025-02-03']);
  });
  await run('date-min-max-step-and-disabled-keyboard', async () => {
    await mount({ type: 'date', value: '', min: '2026-09-08', max: '2026-09-12', step: '2' });
    for (const date of ['07', '09', '11', '13']) await unavailable('2026-09-' + date);
    for (const date of ['08', '10', '12']) await allowed('2026-09-' + date);
    await day('2026-09-08').focus(); await page.keyboard.press('ArrowRight'); await page.keyboard.press('Enter'); await calls([]);
    await page.keyboard.press('ArrowRight'); await page.keyboard.press('Enter'); await calls(['2026-09-10']); await shot('disabled-days');
  });
  await run('native-value-attribute-step-base', async () => {
    await mount({ type: 'date', value: '2026-09-09', step: '2' }); await unavailable('2026-09-10'); await pick('2026-09-11'); await calls(['2026-09-11']);
    await mount({ type: 'time', value: '08:03', step: '600' }); await fillTime('08', '10'); assert(await button('确认').isDisabled());
    await fillTime(undefined, '13'); await button('确认').click(); await calls(['08:13']);
  });
  await run('live-value-never-replaces-explicit-native-step-base', async () => {
    await mount({ type: 'time', value: '08:03', valueAttribute: '', step: '600' }); assert(await button('确认').isDisabled());
    await fillTime('08', '10'); await button('确认').click(); await calls(['08:10']);
    await mount({ type: 'date', value: '2026-09-10', valueAttribute: '2026-09-09', step: '2' });
    await unavailable('2026-09-10'); await pick('2026-09-11'); await calls(['2026-09-11']);
    await mount({ type: 'time', value: '', valueAttribute: '08:10:00.125', step: '1' });
    assert.equal(await field('毫秒').inputValue(), ''); await fillTime('08', '10', '00', '125'); await button('确认').click(); await calls(['08:10:00.125']);
  });
  await run('month-grid-constraints-and-shortcut', async () => {
    await mount({ type: 'month', value: '', min: '2026-03', max: '2027-08', step: '2' }); await unavailable('2026-04'); await pick('2026-05'); await calls(['2026-05']);
    await button('下一年').click(); await allowed('2027-07'); await unavailable('2027-08'); await unavailable('2027-09'); await shot('months');
    await mount({ type: 'month', value: '' }); await calls([]); await button('当前月份').click(); await calls([await page.evaluate(() => WorkbenchDatePickerModel.today().slice(0, 7))]);
  });
  await run('month-keyboard-year-crossing', async () => {
    await mount({ type: 'month', value: '0099-12' }); await day('0099-12').focus(); await page.keyboard.press('ArrowRight');
    assert.equal(await page.locator(':focus').getAttribute('data-date'), '0100-01'); await page.keyboard.press('ArrowDown');
    assert.equal(await page.locator(':focus').getAttribute('data-date'), '0100-04'); await page.keyboard.press('End');
    assert.equal(await page.locator(':focus').getAttribute('data-date'), '0100-06'); await page.keyboard.press('Home');
    assert.equal(await page.locator(':focus').getAttribute('data-date'), '0100-04'); await page.keyboard.press('Enter'); await calls(['0100-04']);
    await mount({ type: 'month', value: '9999-12' }); assert(await button('下一年').isDisabled());
  });
  await run('periodic-time-range-and-step', async () => {
    await mount({ type: 'time', value: '', min: '22:00', max: '06:00', step: '900' }); await fillTime('12', '00'); assert(await button('确认').isDisabled());
    await fillTime('23', '45'); await button('确认').click(); await calls(['23:45']); await fillTime('05', '30'); await button('确认').click(); await calls(['23:45', '05:30']);
    await mount({ type: 'time', value: '', min: '08:10', max: '10:00', step: '900' }); await fillTime('08', '15'); assert(await button('确认').isDisabled());
    await fillTime('08', '25'); await button('确认').click(); await calls(['08:25']);
  });
  await run('seconds-fractions-and-no-rounding', async () => {
    await mount({ type: 'time', value: '12:34:56.125', min: '00:00:00', step: '0.125' }); assert.equal(await field('毫秒').inputValue(), '125');
    await fillTime(undefined, undefined, undefined, '126'); assert(await button('确认').isDisabled()); await fillTime(undefined, undefined, undefined, '250');
    await button('确认').click(); await calls(['12:34:56.250']); await shot('fractional-time');
    await mount({ type: 'time', value: '08:30:45', step: '60' }); assert.equal(await field('秒').inputValue(), '45'); await button('确认').click(); await calls(['08:30:45']);
    await mount({ type: 'time', value: '', step: 'any' }); assert.equal(await field('秒').inputValue(), ''); assert.equal(await field('毫秒').inputValue(), '');
    await fillTime('1', '2', '3', '4'); await button('确认').click(); await calls(['01:02:03.004']);
  });
  await run('time-spinners-are-explicit-and-bounded', async () => {
    await mount({ type: 'time', value: '' }); await button('增加时').click(); assert.equal(await field('时').inputValue(), '00'); assert.equal(await field('分').inputValue(), '');
    assert(await button('减少时').isDisabled()); await button('减少分').click(); assert.equal(await field('分').inputValue(), '59'); assert(await button('增加分').isDisabled());
    await field('时').fill('23'); assert(await button('增加时').isDisabled()); await field('时').press('ArrowDown'); assert.equal(await field('时').inputValue(), '22');
    await fillTime('99', '00'); assert(await button('确认').isDisabled()); await fillTime('22', '59'); await field('分').press('Enter'); await calls(['22:59']);
  });
  await run('datetime-partial-day-and-multi-day-step', async () => {
    await mount({ type: 'datetime-local', value: '', min: '2026-09-09T12:15', max: '2026-09-11T08:45', step: '1800' });
    await unavailable('2026-09-08'); await allowed('2026-09-09'); await allowed('2026-09-11'); await unavailable('2026-09-12');
    await pick('2026-09-11'); await fillTime('09', '00'); assert(await button('确认').isDisabled()); await fillTime('08', '15'); await button('确认').click(); await calls(['2026-09-11T08:15']);
    await mount({ type: 'datetime-local', value: '', min: '2026-09-09T12:00', max: '2026-09-13T12:00', step: '172800' });
    for (const date of ['09', '11', '13']) await allowed('2026-09-' + date);
    for (const date of ['08', '10', '12', '14']) await unavailable('2026-09-' + date);
    await pick('2026-09-11'); await fillTime('12', '00'); await button('确认').click(); await calls(['2026-09-11T12:00']);
  });
  await run('malformed-bounds-follow-native-but-bad-values-never-commit', async () => {
    await mount({ type: 'date', value: '2026-09-09', min: 'garbage', max: '2026-02-30', step: '-1' }); await pick('2026-09-10'); await calls(['2026-09-10']);
    const values = await page.evaluate(() => {
      const M = WorkbenchDatePickerModel;
      return ['0000-01-01', '10000-01-01', '0099-02-29', '2026-02-30', '2026-09-09Z'].map(value => M.validate({ type: 'date' }, value).valid);
    }); assert.deepEqual(values, [false, false, false, false, false]);
    await mount({ type: 'datetime-local', value: '', min: '2026-09-09T12:30', step: 'ANY' }); await allowed('2026-09-09'); await unavailable('2026-09-08');
    await mount({ type: 'time', value: '08:30', step: 'Infinity' }); assert.equal(await field('秒').count(), 0); await button('确认').click(); await calls(['08:30']);
    await mount({ type: 'datetime-local', value: '', min: '2026-09-09T12:30', max: '2026-09-08T12:30' }); await unavailable('2026-09-09');
  });
  await run('unapplied-year-never-commits-stale-selection', async () => {
    await mount({ type: 'datetime-local', value: '2026-09-09T12:00' }); await field('年份').fill('0000'); assert(await button('确认').isDisabled());
    await field('时').press('Enter'); await calls([]); await field('年份').fill('2027'); assert(await button('确认').isDisabled());
    await button('下个月').click(); assert.equal(await field('年份').inputValue(), '2027'); assert.equal(await page.getByRole('grid').getAttribute('aria-label'), '2027 年 10 月');
    await pick('2027-10-09'); await button('确认').click(); await calls(['2027-10-09T12:00']);
  });
  await run('prop-changes-reset-draft-without-implicit-commit', async () => {
    await mount({ type: 'time', value: '08:00' }); await fillTime('09', '15');
    await page.evaluate(() => updateFixture({ type: 'datetime-local', value: '0001-01-02T03:04' })); await field('年份').waitFor();
    assert.equal(await field('年份').inputValue(), '0001'); assert.equal(await field('时').inputValue(), '03'); assert.equal(await field('分').inputValue(), '04'); await calls([]);
    await button('确认').click(); await calls(['0001-01-02T03:04']);
  });
  await run('native-step-and-day-availability-oracle', async () => {
    const mismatches = await page.evaluate(() => {
      const M = WorkbenchDatePickerModel, failures = [];
      for (const step of ['60', '900', '5400', '86400', '172800', 'any']) for (const value of ['', '2026-09-09T05:17']) {
        const props = { type: 'datetime-local', value, step, min: '2026-09-08T12:17', max: '2026-09-12T13:19' };
        for (let date = 7; date <= 13; date++) {
          const key = '2026-09-' + M.pad(date), native = M.nativeField(props);
          let expected = false;
          for (let minute = 0; minute < 1440 && !expected; minute++) { native.value = key + 'T' + M.pad(Math.floor(minute / 60)) + ':' + M.pad(minute % 60); expected = native.checkValidity(); }
          const actual = M.daySelectable(props, key); if (actual !== expected) failures.push({ props, key, actual, expected });
        }
      }
      return failures;
    }); assert.deepEqual(mismatches, []);
  });
  await run('weekday-and-domain-arithmetic', async () => {
    const mismatches = await page.evaluate(() => {
      const M = WorkbenchDatePickerModel, failures = [];
      for (const year of [1, 4, 99, 100, 400, 1600, 1900, 2000, 2026, 2400, 9999]) for (let month = 1; month <= 12; month++) {
        const key = M.dateKey(year, month, 1), reference = new Date(0);
        reference.setUTCFullYear(year, month - 1, 1); reference.setUTCHours(0, 0, 0, 0);
        const expected = (reference.getUTCDay() + 6) % 7;
        if (M.weekday(key) !== expected) failures.push({ key, expected, actual: M.weekday(key) });
      }
      return failures;
    }); assert.deepEqual(mismatches, []);
  });
  await run('no-native-picker-no-bubble-no-native-popup-descendants', async () => {
    await calls(await page.evaluate(() => fixture.calls)); assert.deepEqual(await page.evaluate(() => fixture.nativeUI), []);
    assert.equal(await page.locator('.wb-control-popup select,.wb-control-popup input:not([type="text"])').count(), 0);
  });
  await monthNavigationCases();
}
async function monthNavigationCases() {
  await run('date-month-title-browses-without-committing', async () => {
    await mount({ type: 'date', value: '2026-09-09' }); const before = await bounds(); await openMonths();
    assert.deepEqual(await bounds(), before); assert.equal(await page.locator(':focus').getAttribute('data-date'), '2026-09');
    assert.equal(await day('2026-09').getAttribute('aria-selected'), 'true'); assert.equal(await day('2026-09').getAttribute('data-view-month'), 'true');
    const current = await page.evaluate(() => WorkbenchDatePickerModel.today().slice(0, 7));
    if (current.startsWith('2026-')) assert.equal(await day(current).getAttribute('aria-current'), 'date');
    await calls([]); await shot('date-month-navigation'); await pick('2026-02'); await dateView(); await calls([]);
    assert.deepEqual(await bounds(), before); assert.equal(await page.locator(':focus').getAttribute('data-date'), '2026-02-09');
    assert.equal(await page.locator('[aria-selected="true"]').count(), 0); await openMonths();
    assert.equal(await day('2026-02').getAttribute('data-view-month'), 'true'); assert.equal(await day('2026-02').getAttribute('aria-selected'), 'false');
    assert.equal(await day('2026-09').getAttribute('aria-selected'), 'true'); await shot('viewed-selected-current-months');
    await button('返回日历').click(); await dateView(); await calls([]); await pick('2026-02-09'); await calls(['2026-02-09']);
  });
  await run('datetime-month-browse-retains-date-and-precise-time', async () => {
    const original = '2024-01-31T22:30:45.125';
    await mount({ type: 'datetime-local', value: original, step: 'any' }); const before = await bounds(); await openMonths();
    assert.deepEqual(await bounds(), before); await pick('2024-02'); await dateView(); await calls([]);
    assert.equal(await page.locator(':focus').getAttribute('data-date'), '2024-02-29');
    assert.equal(await field('时').inputValue(), '22'); assert.equal(await field('分').inputValue(), '30');
    assert.equal(await field('秒').inputValue(), '45'); assert.equal(await field('毫秒').inputValue(), '125');
    assert(await page.getByText('2024-01-31', { exact: true }).isVisible()); await button('确认').click(); await calls([original]);
    await mount({ type: 'datetime-local', value: original, step: 'any' }); await openMonths(); await pick('2024-02'); await pick('2024-02-29');
    await button('确认').click(); await calls(['2024-02-29T22:30:45.125']);
  });
  await run('empty-datetime-month-choice-never-fills-date-or-time', async () => {
    await mount({ type: 'datetime-local', value: '', min: '2024-01-01T00:00' }); await openMonths(); await pick('2024-02'); await dateView();
    assert.equal(await field('时').inputValue(), ''); assert.equal(await field('分').inputValue(), '');
    assert(await page.getByText('尚未选择日期', { exact: true }).isVisible()); assert(await button('确认').isDisabled()); await calls([]);
    await pick('2024-02-29'); assert(await button('确认').isDisabled()); await fillTime('22', '00'); await button('确认').click(); await calls(['2024-02-29T22:00']);
  });
  await run('date-month-keyboard-enter-is-navigation-only', async () => {
    await mount({ type: 'date', value: '2026-09-30' }); await button('选择月份').focus(); await page.keyboard.press('Enter');
    await page.locator('[data-picker-view="months"]').waitFor();
    for (const [key, expected] of [['ArrowRight', '2026-10'], ['ArrowLeft', '2026-09'], ['ArrowDown', '2026-12'], ['ArrowUp', '2026-09'], ['Home', '2026-07'], ['End', '2026-09'], ['PageUp', '2025-09'], ['PageDown', '2026-09'], ['ArrowDown', '2026-12'], ['ArrowRight', '2027-01']]) {
      await page.keyboard.press(key); assert.equal(await page.locator(':focus').getAttribute('data-date'), expected); await calls([]);
    }
    await page.keyboard.press('Enter'); await dateView(); assert.equal(await page.locator(':focus').getAttribute('data-date'), '2027-01-30'); await calls([]);
    await page.keyboard.press('Enter'); await calls(['2027-01-30']);
  });
  await run('month-view-year-navigation-and-domain-boundaries', async () => {
    await mount({ type: 'date', value: '2026-01-31' }); await field('年份').fill('0000'); await button('选择月份').click();
    assert(await page.locator('[data-picker-view="days"]').isVisible()); await calls([]);
    await field('年份').fill('0099'); await openMonths(); assert.equal(await field('年份').inputValue(), '0099');
    await pick('0099-02'); await dateView(); assert.equal(await page.locator(':focus').getAttribute('data-date'), '0099-02-28'); await calls([]);
    await mount({ type: 'date', value: '2024-02-29' }); await openMonths();
    assert.equal(await button('下个月').count(), 0); await button('下一年').click(); assert.equal(await field('年份').inputValue(), '2025');
    assert.equal(await page.getByRole('grid').getAttribute('aria-label'), '2025 年月份'); await pick('2025-02'); await dateView();
    assert.equal(await page.locator(':focus').getAttribute('data-date'), '2025-02-28'); assert.equal(await button('下一年').count(), 0); await calls([]);
    await mount({ type: 'date', value: '0001-01-31' }); await openMonths(); assert(await button('上一年').isDisabled());
    await page.locator('[data-picker-initial]').focus(); await page.keyboard.press('ArrowLeft'); assert.equal(await page.locator(':focus').getAttribute('data-date'), '0001-01');
    await field('年份').fill('0000'); await page.keyboard.press('Enter'); await day('0001-02').click(); await calls([]);
    assert(await page.locator('[data-picker-view="months"]').isVisible()); await field('年份').fill('99'); await page.keyboard.press('Enter');
    await pick('0099-02'); await dateView(); assert.equal(await page.locator(':focus').getAttribute('data-date'), '0099-02-28'); await calls([]);
    await mount({ type: 'datetime-local', value: '9999-12-31T23:59' }); await openMonths(); assert(await button('下一年').isDisabled());
    await page.locator('[data-picker-initial]').focus(); await page.keyboard.press('ArrowRight'); assert.equal(await page.locator(':focus').getAttribute('data-date'), '9999-12');
    await page.keyboard.press('Enter'); await dateView(); await calls([]); await button('确认').click(); await calls(['9999-12-31T23:59']);
    for (const [value, key, control] of [['0001-09-09', 'PageUp', '上一年'], ['9999-02-28', 'PageDown', '下一年']]) for (const type of ['date', 'month']) {
      await mount({ type, value: type === 'month' ? value.slice(0, 7) : value });
      if (type === 'date') await openMonths(); else await page.locator('[data-picker-initial]').focus();
      assert(await button(control).isDisabled()); await page.keyboard.press(key);
      assert.equal(await page.locator(':focus').getAttribute('data-date'), value.slice(0, 7)); await calls([]);
    }
  });
  await run('date-month-disabled-state-uses-date-step-not-month-step', async () => {
    await mount({ type: 'date', value: '', min: '2026-09-30', max: '2026-10-01', step: '2' }); await openMonths();
    await allowed('2026-09'); for (const key of ['2026-08', '2026-10', '2026-11']) await unavailable(key);
    await page.keyboard.press('ArrowRight'); await page.keyboard.press('Enter'); await calls([]); assert(await page.locator('[data-picker-view="months"]').isVisible());
    await shot('disabled-month-navigation'); await page.keyboard.press('ArrowLeft'); await page.keyboard.press('Enter'); await dateView(); await pick('2026-09-30'); await calls(['2026-09-30']);
    await mount({ type: 'date', value: '2026-02-01', valueAttribute: '2026-01-31', max: '2026-05-01', step: '60' }); await openMonths();
    await allowed('2026-01'); await unavailable('2026-02'); await unavailable('2026-03'); await allowed('2026-04'); await unavailable('2026-05');
    await pick('2026-04'); await dateView(); await calls([]); await pick('2026-04-01'); await calls(['2026-04-01']);
  });
  await run('year-spanning-step-and-leap-month-selection', async () => {
    await mount({ type: 'date', value: '2024-02-29', min: '2024-02-29', max: '2025-03-31', step: '366' }); await openMonths();
    await allowed('2024-02'); await unavailable('2024-03'); await button('下一年').click(); await unavailable('2025-02'); await allowed('2025-03');
    await pick('2025-03'); await dateView(); await calls([]); await pick('2025-03-01'); await calls(['2025-03-01']);
  });
  await run('datetime-month-availability-honors-time-and-fractions', async () => {
    await mount({ type: 'datetime-local', value: '', min: '2026-01-31T23:30', max: '2026-03-02T01:00', step: String(29 * 86400) }); await openMonths();
    await allowed('2026-01'); await unavailable('2026-02'); await allowed('2026-03'); await unavailable('2026-04'); await pick('2026-03'); await dateView();
    await calls([]); assert(await button('确认').isDisabled()); await pick('2026-03-01'); await fillTime('23', '30'); await button('确认').click(); await calls(['2026-03-01T23:30']);
    await mount({ type: 'datetime-local', value: '', min: '2026-02-28T23:59:59.999', max: '2026-03-01T00:00', step: 'any' }); await openMonths();
    await unavailable('2026-01'); await allowed('2026-02'); await allowed('2026-03'); await unavailable('2026-04'); await calls([]);
    assert.equal(await field('时').inputValue(), ''); assert.equal(await field('毫秒').inputValue(), ''); await shot('datetime-month-navigation');
  });
  await run('month-browse-back-escape-and-updated-spinner-enter', async () => {
    await mount({ type: 'datetime-local', value: '2026-01-31T08:00' }); await openMonths(); await button('下一年').click();
    await button('返回日历').click(); await dateView(); assert.equal(await field('年份').inputValue(), '2026'); await calls([]);
    await openMonths(); await button('增加时').focus(); await page.keyboard.press('Enter'); assert.equal(await field('时').inputValue(), '09'); await calls([]);
    assert(await page.locator('.wb-number-stepper').first().isVisible()); await page.keyboard.press('Escape');
    assert.deepEqual(await page.evaluate(() => fixture.escape), [{ prevented: false }]); assert.equal(await page.evaluate(() => fixture.closed), 0); await calls([]);
    await button('取消').click(); assert.equal(await page.evaluate(() => fixture.closed), 1); await calls([]);
  });
  await run('month-mode-is-not-native-month-field-and-resets-with-type', async () => {
    await mount({ type: 'date', value: '2026-09-09' }); await openMonths();
    await page.evaluate(() => updateFixture({ type: 'month', value: '2026-09', min: '2026-01', step: '2' }));
    assert.equal(await button('返回日历').count(), 0); await allowed('2026-11'); await unavailable('2026-10'); await pick('2026-11'); await calls(['2026-11']);
    await page.evaluate(() => updateFixture({ type: 'time', value: '' })); await field('时').waitFor();
    assert.equal(await page.getByRole('grid').count(), 0); assert.equal(await button('选择月份').count(), 0); assert.equal(await field('时').inputValue(), '');
  });
  await run('month-availability-independent-native-oracle', async () => {
    const mismatches = await page.evaluate(() => {
      const M = WorkbenchDatePickerModel, failures = [];
      const specs = [
        { type: 'date', value: '', min: '2026-01-31', max: '2026-11-30', step: '60' },
        { type: 'date', value: '2026-02-01', valueAttribute: '2026-01-31', step: '366' },
        { type: 'datetime-local', value: '', valueAttribute: '2026-01-31T05:17', step: String(31 * 86400) }
      ];
      for (const props of specs) for (let month = 1; month <= 12; month++) {
        const key = M.monthKey(2026, month), native = M.nativeField(props);
        let expected = false;
        for (let day = 1; day <= APSCalendarContract.monthDays(2026, month) && !expected; day++) {
          native.value = key + '-' + M.pad(day) + (props.type === 'datetime-local' ? 'T05:17' : ''); expected = native.checkValidity();
        }
        const actual = M.monthSelectable(props, key); if (expected !== actual) failures.push({ props, key, expected, actual });
      }
      return failures;
    }); assert.deepEqual(mismatches, []);
  });
}
(async () => {
  let browser;
  try {
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve)); const origin = 'http://127.0.0.1:' + server.address().port;
    browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true }); result.browser = await browser.version();
    assert(result.browser.startsWith('109.'), 'The test must use actual Chromium 109');
    for (const viewport of [{ width: 1920, height: 1080 }, { width: 1392, height: 924 }]) for (const theme of ['light', 'dark']) {
      variant = viewport.width + '-' + theme; const context = await browser.newContext({ viewport, timezoneId: 'Asia/Shanghai' }); page = await context.newPage();
      await page.addInitScript(theme => { localStorage.setItem('aps_theme', theme); }, theme);
      page.on('pageerror', error => result.errors.push({ variant, message: error.message }));
      page.on('console', event => { if (event.type() === 'error') result.errors.push({ variant, message: event.text() }); });
      page.on('request', request => { if (!request.url().startsWith(origin + '/') && !request.url().startsWith('data:')) result.external.push(request.url()); });
      await page.goto(origin); await page.evaluate(theme => document.documentElement.dataset.theme = theme, theme); await cases(); await context.close();
    }
    for (const timezoneId of ['America/New_York', 'Europe/Berlin']) {
      variant = timezoneId.replace('/', '-'); const context = await browser.newContext({ viewport: { width: 1920, height: 1080 }, timezoneId }); page = await context.newPage();
      await page.goto(origin); await run('local-datetime-no-timezone-or-dst-conversion', async () => {
        for (const value of ['2026-03-08T02:30', '2026-03-29T02:30', '0099-01-01T01:23', '9999-12-31T23:59']) {
          await mount({ type: 'datetime-local', value }); await button('确认').click(); await calls([value]);
        }
      }); await context.close();
    }
    assert.deepEqual(result.errors, []); assert.deepEqual(result.external, []);
  } finally {
    if (browser) await browser.close(); await new Promise(resolve => server.close(resolve)); fs.writeFileSync(path.join(output, 'date-picker-result.json'), JSON.stringify(result, null, 2) + '\n');
  }
  console.log(JSON.stringify({ output, browser: result.browser, cases: result.cases.length, screenshots: result.screenshots.length, errors: result.errors, external: result.external, scope: result.scope }));
})().catch(error => { console.error(error); process.exitCode = 1; });
