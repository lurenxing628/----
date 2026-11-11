'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { compile } = require('../scripts/workbench/compile.cjs');
const source = compile({
  sources: [{ path: 'WorkbenchDensity.js', code: fs.readFileSync(path.join(__dirname, '../frontend/workbench/app/WorkbenchDensity.js'), 'utf8') }],
  check_combined: false,
}).outputs[0].code;
function host(saved = null, denied = false) {
  const events = {}, attributes = {}, storage = { value: saved, denied };
  const context = {
    window: {
      addEventListener(name, callback) { events[name] = callback; },
      removeEventListener(name, callback) { if (events[name] === callback) delete events[name]; }
    },
    document: { documentElement: { setAttribute(name, value) { attributes[name] = value; } } },
    localStorage: {
      getItem(key) { assert.equal(key, 'aps_density'); if (storage.denied) throw new Error('unavailable'); return storage.value; },
      setItem(key, value) { assert.equal(key, 'aps_density'); if (storage.denied) throw new Error('unavailable'); storage.value = value; }
    }
  };
  vm.runInNewContext(source, context);
  return { api: context.__wbRuntime.getModule('WorkbenchDensity.js'), storage, attributes, events };
}
const empty = host();
assert.deepEqual(empty.events, {}, 'Module evaluation must not attach global listeners');
assert.deepEqual(empty.attributes, {}, 'Module evaluation must not eagerly read storage');
assert.equal(empty.api.get().density, 'comfortable');
assert.equal(empty.attributes['data-density'], 'comfortable');
const saved = host('compact');
assert.equal(saved.api.get().density, 'compact');
assert.equal(saved.attributes['data-density'], 'compact');
const observed = [], unsubscribe = saved.api.subscribe(value => observed.push(value));
assert.equal(typeof saved.events.storage, 'function');
assert.equal(typeof saved.events.pageshow, 'function');
saved.api.set('comfortable');
assert.equal(saved.storage.value, 'comfortable');
assert.equal(observed[0].density, 'comfortable');
unsubscribe();
assert.deepEqual(saved.events, {}, 'Unsubscribing the last listener must remove global listeners');
saved.api.set('compact'); assert.equal(observed.length, 1);
assert.throws(() => saved.api.set('dense'), /只能/);
assert.equal(saved.api.get().density, 'compact');
const invalid = host('dense');
assert.equal(invalid.api.get().density, 'comfortable'); assert.match(invalid.api.get().error, /无效/);
const denied = host(null, true);
assert.match(denied.api.get().error, /无法读取/);
denied.api.set('compact');
assert.equal(denied.attributes['data-density'], 'compact'); assert.match(denied.api.get().error, /未保存/);
const stopDenied = denied.api.subscribe(() => {});
denied.events.pageshow();
assert.equal(denied.api.get().density, 'compact'); assert.match(denied.api.get().error, /无法读取/);
stopDenied();
assert.deepEqual(denied.events, {});
const stopSaved = saved.api.subscribe(() => {});
saved.storage.value = 'comfortable'; saved.events.storage({ key: 'unrelated' });
assert.equal(saved.api.get().density, 'compact');
saved.events.storage({ key: 'aps_density' }); assert.equal(saved.api.get().density, 'comfortable');
stopSaved();
assert.deepEqual(saved.events, {});
const snapshot = saved.api.get(); snapshot.density = 'compact';
assert.equal(saved.api.get().density, 'comfortable');
const quiet = host('compact'), notices = [], stopQuiet = quiet.api.subscribe(value => notices.push(value));
quiet.events.pageshow(); assert.equal(notices.length, 0, 'pageshow with an unchanged preference must not notify');
quiet.storage.value = 'comfortable'; quiet.events.pageshow(); assert.equal(notices.length, 1); assert.equal(notices[0].density, 'comfortable');
stopQuiet();
assert.deepEqual(quiet.events, {});
console.log('workbench density preference contract passed');
