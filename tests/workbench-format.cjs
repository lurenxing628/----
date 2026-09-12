'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { spawnSync } = require('node:child_process');
const root = path.resolve(__dirname, '..');
const context = vm.createContext({ window: {} });
vm.runInContext(fs.readFileSync(path.join(root, 'frontend/workbench/app/WorkbenchFormat.js'), 'utf8'), context);
const F = context.window.WorkbenchFormat;
const invalid = action => assert.throws(action, error => error.name === 'TypeError');

if (process.argv[2] === '--timezone') {
  assert.equal(F.dateTime('2026-09-12T08:03:09.123456'), '2026-09-12 08:03');
  assert.equal(F.dateTime('2026-09-12 08:03:09', { seconds: true }), '2026-09-12 08:03:09');
  const expected = { 'Asia/Shanghai': '2026-09-12 08:03:09', UTC: '2026-09-12 00:03:09', 'America/New_York': '2026-09-11 20:03:09' };
  assert.equal(F.instant('2026-09-12T00:03:09.123456Z', { seconds: true }), expected[process.env.TZ]);
  assert.equal(F.instant('2026-09-12T08:03:09+08:00', { seconds: true }), expected[process.env.TZ]);
  assert.equal(F.instant('2026-09-11T20:03:09-04:00', { seconds: true }), expected[process.env.TZ]);
  process.stdout.write('Timezone passed: ' + process.env.TZ + '\n');
} else {
  for (const empty of [null, undefined, '']) {
    for (const format of [F.date, F.dateTime, F.instant, F.number, F.integerText, F.percent, F.hours]) assert.equal(format(empty), '未知');
  }
  assert.equal(F.date('2024-02-29'), '2024-02-29');
  assert.equal(F.date('2024-02-29T23:59:59.123456'), '2024-02-29');
  assert.equal(F.dateTime('2000-02-29T08:03', { seconds: true }), '2000-02-29 08:03:00');
  assert.equal(F.dateTime('0001-01-01 00:00'), '0001-01-01 00:00');
  for (const value of ['2026-02-29', '1900-02-29', '2026-04-31', '2026-00-01', '2026-13-01', '2026-01-00',
    '0000-01-01', '2026-9-12', '2026/09/12', ' 2026-09-12', '2026-09-12 ', 0, false, {}, []]) invalid(() => F.date(value));
  for (const value of ['2026-09-12', '2026-09-12T24:00', '2026-09-12T08:60', '2026-09-12T08:00:60',
    '2026-09-12T08:00:00Z', '2026-09-12T08:00:00+08:00', '2026-09-12T08:00:00.1234567', '2026-09-12T08:00.1']) invalid(() => F.dateTime(value));
  for (const value of ['2026-09-12T08:00:00', '2026-02-29T08:00:00Z', '2026-09-12T24:00:00Z',
    '2026-09-12T08:00:00+24:00', '2026-09-12T08:00:00+08:60', '2026-09-12 08:00:00Z', '2026-09-12T08:00Z', 0]) invalid(() => F.instant(value));
  invalid(() => F.dateTime('2026-09-12T08:00', { seconds: 1 }));
  assert.equal(F.number(123456.25), '123,456.3');
  assert.equal(F.number(0), '0.0');
  assert.equal(F.number(-1234.5, { digits: 2 }), '-1,234.50');
  assert.equal(F.number(1234.5, { digits: 0 }), '1,235');
  assert.equal(F.integerText('0'), '0');
  assert.equal(F.integerText('123'), '123');
  assert.equal(F.integerText('1234'), '1,234');
  assert.equal(F.integerText('9007199254740993'), '9,007,199,254,740,993');
  assert.equal(F.integerText('123456789012345678901234567890'), '123,456,789,012,345,678,901,234,567,890');
  for (const value of ['01', '+1', '-1', '1.0', '1e10', ' 123', '123 ', 123, true, [], {}]) invalid(() => F.integerText(value));
  assert.equal(F.hours(3.25), '3.3 h');
  assert.equal(F.hours(-1.25, 2), '-1.25 h');
  // Negative zero and values that round to zero never read as a reduction.
  assert.equal(F.number(-0), '0.0');
  assert.equal(F.number(-0.04), '0.0');
  assert.equal(F.number(-0.06), '-0.1');
  assert.equal(F.hours(-0), '0.0 h');
  assert.equal(F.percent(-0), '0.0%');
  assert.equal(F.percent(-0.0004), '0.0%');
  // trim keeps entered precision (up to `digits` decimals) instead of padding a fixed one-decimal summary.
  assert.equal(F.number(12.5, { digits: 3, trim: true }), '12.5');
  assert.equal(F.number(2, { digits: 3, trim: true }), '2');
  assert.equal(F.number(0.0833, { digits: 3, trim: true }), '0.083');
  assert.equal(F.number(1234.5678, { digits: 3, trim: true }), '1,234.568');
  assert.equal(F.hours(0.05, { digits: 3, trim: true }), '0.05 h');
  assert.equal(F.hours(3.25, { digits: 2 }), '3.25 h');
  assert.equal(F.percent(0.5, { digits: 2 }), '50.00%');
  assert.equal(F.percent(0.5, { digits: 2, trim: true }), '50%');
  for (const options of [{ trim: 'yes' }, { digits: 21 }, null, 'x']) invalid(() => F.number(1, options));
  invalid(() => F.hours('1'));
  invalid(() => F.hours(1, { digits: 1.5 }));
  assert.equal(F.percent(0.873), '87.3%');
  assert.equal(F.percent(0), '0.0%');
  assert.equal(F.percent(1, 0), '100%');
  assert.equal(F.percent(1.2), '120.0%');
  assert.equal(F.percent(-0.125, 2), '-12.50%');
  const maxPercentDigits = '17976931348623157' + '0'.repeat(294);
  assert.equal(F.percent(Number.MAX_VALUE), maxPercentDigits.replace(/\B(?=(\d{3})+(?!\d))/g, ',') + '.0%');
  for (const value of ['12', false, true, NaN, Infinity, -Infinity, {}, []]) invalid(() => F.number(value));
  for (const digits of [-1, 21, 1.5, '2', null]) invalid(() => F.number(1, { digits }));
  for (const value of ['0.1', Infinity, NaN, false]) invalid(() => F.percent(value));
  for (const digits of [-1, 21, 1.5, '2', null]) invalid(() => F.percent(0.5, digits));
  assert(Object.isFrozen(F));
  for (const timezone of ['Asia/Shanghai', 'UTC', 'America/New_York']) {
    const result = spawnSync(process.execPath, [__filename, '--timezone'], { encoding: 'utf8', env: { ...process.env, TZ: timezone } });
    assert.equal(result.status, 0, result.stdout + result.stderr);
    process.stdout.write(result.stdout);
  }
  process.stdout.write('WorkbenchFormat contracts passed.\n');
}
