'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../../frontend/workbench/app/theme.js'), 'utf8');
const PRIMARY = 'aps_theme', PROTOTYPE = 'aps_kit_theme';
const results = [], failures = [];

function runtime(options = {}) {
  const store = new Map(Object.entries(options.stored || {}));
  const cookies = new Map(), attributes = new Map(), events = new Map();
  const writes = [], cookieWrites = [];
  const faults = {read: options.readError, write: options.writeError};
  function putCookie(text) {
    const entry = text.trim(), split = entry.indexOf('=');
    if (split > 0) cookies.set(entry.slice(0, split), entry.slice(split + 1));
  }
  (options.cookie || '').split(';').forEach(putCookie);
  const document = {
    documentElement: {setAttribute: (key, value) => attributes.set(key, value)},
    get cookie() { return [...cookies].map(([key, value]) => key + '=' + value).join('; '); },
    set cookie(value) { cookieWrites.push(value); putCookie(value.split(';')[0]); }
  };
  const context = vm.createContext({document, localStorage: {
    getItem(key) {
      if (faults.read === '*' || faults.read === key) throw new Error('Storage read denied');
      return store.has(key) ? store.get(key) : null;
    },
    setItem(key, value) {
      writes.push([key, value]);
      if (faults.write === '*' || faults.write === key) throw new Error('Storage write denied');
      store.set(key, String(value));
    }
  }, addEventListener(name, callback) {
    if (!events.has(name)) events.set(name, []);
    events.get(name).push(callback);
  }});
  context.window = context;
  vm.runInContext(source, context, {filename: 'frontend/workbench/app/theme.js', timeout: 1000});
  return {api: context.APSWorkbenchTheme, store, cookies, attributes, writes, cookieWrites, faults,
    emit(name, detail = {}) {
      (events.get(name) || []).slice().forEach(callback => callback({...detail, type: name}));
    }};
}

function themeIs(client, expected) {
  assert.equal(client.api.get().theme, expected);
  assert.equal(client.attributes.get('data-theme'), expected);
  assert.equal(typeof client.api.get().error, 'string');
}
function hasError(value) {
  assert.equal(typeof value.error, 'string');
  assert.ok(value.error.trim(), 'A failed preference operation must expose an error');
}
function check(name, run) {
  try { run(); results.push(name); }
  catch (error) { failures.push({name, error: error.stack || String(error)}); }
}

check('missing preferences default to light', () => {
  const client = runtime(); themeIs(client, 'light');
  assert.equal(client.api.get().error, '');
});
check('prototype-only preference migrates before cookie fallback', () => {
  const client = runtime({stored: {[PROTOTYPE]: 'dark'}, cookie: 'aps_theme=light'});
  themeIs(client, 'dark'); assert.equal(client.api.get().error, '');
});
check('canonical preference is read without a prototype key', () => {
  const client = runtime({stored: {[PRIMARY]: 'dark'}, cookie: 'aps_theme=light'});
  themeIs(client, 'dark'); assert.equal(client.api.get().error, '');
});
check('canonical preference wins a prototype conflict', () => {
  const client = runtime({stored: {[PRIMARY]: 'light', [PROTOTYPE]: 'dark'}, cookie: 'aps_theme=dark'});
  themeIs(client, 'light'); assert.equal(client.api.get().error, '');
});
check('cookie fallback accepts both legal themes', () => {
  for (const theme of ['dark', 'light']) {
    const client = runtime({cookie: 'other=value; aps_theme=' + theme + '; tail=value'});
    themeIs(client, theme); assert.equal(client.api.get().error, '');
  }
});
check('invalid canonical value uses a legal prototype fallback visibly', () => {
  const client = runtime({stored: {[PRIMARY]: 'sepia', [PROTOTYPE]: 'dark'}});
  themeIs(client, 'dark'); hasError(client.api.get());
});
check('invalid stored values use a legal cookie fallback visibly', () => {
  const client = runtime({stored: {[PRIMARY]: 'sepia', [PROTOTYPE]: 'blue'}, cookie: 'aps_theme=dark'});
  themeIs(client, 'dark'); hasError(client.api.get());
});
check('invalid values never become a document theme', () => {
  const client = runtime({stored: {[PRIMARY]: 'sepia', [PROTOTYPE]: 'blue'}, cookie: 'aps_theme=sepia'});
  themeIs(client, 'light'); hasError(client.api.get());
});
check('invalid set values are rejected without changing preferences', () => {
  const client = runtime({stored: {[PRIMARY]: 'dark'}});
  const before = [...client.store], writes = client.writes.length, cookies = client.cookieWrites.length;
  for (const value of ['sepia', 'Dark', '', null, undefined, true, 1, {}]) {
    assert.throws(() => client.api.set(value), error => typeof error.message === 'string' && !!error.message);
    themeIs(client, 'dark');
  }
  assert.deepEqual([...client.store], before);
  assert.equal(client.writes.length, writes); assert.equal(client.cookieWrites.length, cookies);
});
check('set persists canonical then prototype and cookie', () => {
  const client = runtime();
  for (const theme of ['dark', 'light']) {
    client.writes.length = 0; client.cookieWrites.length = 0;
    const result = client.api.set(theme);
    themeIs(client, theme); assert.equal(result.theme, theme); assert.equal(result.error, '');
    assert.deepEqual(client.writes.slice(0, 2), [[PRIMARY, theme], [PROTOTYPE, theme]]);
    assert.equal(client.store.get(PRIMARY), theme); assert.equal(client.store.get(PROTOTYPE), theme);
    assert.equal(client.cookies.get(PRIMARY), theme);
    assert.ok(client.cookieWrites.some(value => value.startsWith(PRIMARY + '=' + theme + ';')));
  }
});
check('storage observes a newer preference saved by the old page', () => {
  const client = runtime({stored: {[PRIMARY]: 'dark', [PROTOTYPE]: 'dark'}}), notices = [];
  client.api.subscribe(value => notices.push(value));
  client.store.set(PRIMARY, 'light'); client.emit('storage', {key: PRIMARY});
  themeIs(client, 'light'); assert.equal(notices.length, 1); assert.equal(notices[0].theme, 'light');
});
check('pageshow observes a newer preference saved by the old page', () => {
  const client = runtime({stored: {[PRIMARY]: 'dark', [PROTOTYPE]: 'dark'}}), notices = [];
  client.api.subscribe(value => notices.push(value));
  client.store.set(PRIMARY, 'light'); client.emit('pageshow');
  themeIs(client, 'light'); assert.equal(notices.length, 1); assert.equal(notices[0].theme, 'light');
});
check('window focus rechecks preferences without saving or changing business state', () => {
  const client = runtime({stored: {[PRIMARY]: 'dark'}}), notices = [];
  client.api.subscribe(value => notices.push(value)); client.store.set(PRIMARY, 'light'); client.emit('focus');
  themeIs(client, 'light'); assert.equal(notices.length, 1); assert.equal(client.writes.length, 0);
});
check('prototype storage events cannot override a canonical preference', () => {
  const client = runtime({stored: {[PRIMARY]: 'light', [PROTOTYPE]: 'light'}});
  client.store.set(PROTOTYPE, 'dark'); client.emit('storage', {key: PROTOTYPE});
  themeIs(client, 'light');
});
check('unrelated storage events do not notify theme subscribers', () => {
  const client = runtime(), notices = [];
  client.api.subscribe(value => notices.push(value)); client.emit('storage', {key: 'unrelated'});
  assert.equal(notices.length, 0); themeIs(client, 'light');
});
check('storage clear rechecks the cookie fallback', () => {
  const client = runtime({stored: {[PRIMARY]: 'light'}, cookie: 'aps_theme=dark'});
  client.store.clear(); client.emit('storage', {key: null}); themeIs(client, 'dark');
});
check('unsubscribe stops set and event notifications without removing other subscribers', () => {
  const client = runtime(), first = [], second = [];
  const unsubscribe = client.api.subscribe(value => first.push(value));
  client.api.subscribe(value => second.push(value)); client.api.set('dark');
  assert.equal(first.length, 1); assert.equal(second.length, 1);
  assert.equal(first[0].theme, 'dark'); assert.equal(first[0].error, '');
  unsubscribe(); unsubscribe(); client.api.set('light'); client.emit('storage', {key: PRIMARY}); client.emit('pageshow');
  assert.equal(first.length, 1); assert.equal(second.length, 4);
});
check('canonical storage read failures are visible on initialization', () => {
  const client = runtime({readError: PRIMARY});
  hasError(client.api.get()); assert.ok(['light', 'dark'].includes(client.api.get().theme));
  themeIs(client, client.api.get().theme);
});
check('prototype fallback storage read failures are visible on initialization', () => {
  const client = runtime({readError: PROTOTYPE});
  hasError(client.api.get()); assert.ok(['light', 'dark'].includes(client.api.get().theme));
  themeIs(client, client.api.get().theme);
});
check('storage and pageshow read failures notify subscribers explicitly', () => {
  for (const event of ['storage', 'pageshow']) {
    const client = runtime({stored: {[PRIMARY]: 'dark'}}), notices = [];
    client.api.subscribe(value => notices.push(value)); client.faults.read = '*';
    client.emit(event, {key: PRIMARY}); hasError(client.api.get());
    assert.equal(notices.length, 1); hasError(notices[0]);
  }
});
check('canonical storage write failure is not reported as saved', () => {
  const client = runtime({stored: {[PRIMARY]: 'light'}, writeError: PRIMARY}), notices = [];
  client.api.subscribe(value => notices.push(value)); client.writes.length = 0;
  const result = client.api.set('dark');
  themeIs(client, 'dark'); hasError(result); hasError(client.api.get());
  assert.equal(client.store.get(PRIMARY), 'light'); assert.equal(client.writes[0][0], PRIMARY);
  assert.equal(notices.length, 1); hasError(notices[0]);
});
check('prototype write failure preserves the already saved canonical preference and reports error', () => {
  const client = runtime({stored: {[PRIMARY]: 'light'}, writeError: PROTOTYPE}), notices = [];
  client.api.subscribe(value => notices.push(value)); client.writes.length = 0;
  const result = client.api.set('dark');
  themeIs(client, 'dark'); hasError(result); hasError(client.api.get());
  assert.equal(client.store.get(PRIMARY), 'dark');
  assert.deepEqual(client.writes.slice(0, 2), [[PRIMARY, 'dark'], [PROTOTYPE, 'dark']]);
  assert.equal(notices.length, 1); hasError(notices[0]);
});
check('a successful retry clears the earlier persistence error', () => {
  const client = runtime({writeError: '*'}); hasError(client.api.set('dark'));
  client.faults.write = null;
  const result = client.api.set('light'); themeIs(client, 'light');
  assert.equal(result.error, ''); assert.equal(client.api.get().error, '');
  assert.equal(client.store.get(PRIMARY), 'light'); assert.equal(client.store.get(PROTOTYPE), 'light');
  assert.equal(client.cookies.get(PRIMARY), 'light');
});

console.log(JSON.stringify({checks: results.length + failures.length, passed: results.length,
  failed: failures.length, failures, network: 'none', browser: false, production: false}));
if (failures.length) process.exitCode = 1;
