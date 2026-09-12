'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../frontend/workbench/app/WorkbenchDensity.js'), 'utf8');
function host(saved = null, denied = false) {
  const events = {}, attributes = {}, storage = { value: saved, denied };
  const context = {
    window: { addEventListener(name, callback) { events[name] = callback; } },
    document: { documentElement: { setAttribute(name, value) { attributes[name] = value; } } },
    localStorage: {
      getItem(key) { assert.equal(key, 'aps_density'); if (storage.denied) throw new Error('unavailable'); return storage.value; },
      setItem(key, value) { assert.equal(key, 'aps_density'); if (storage.denied) throw new Error('unavailable'); storage.value = value; }
    }
  };
  vm.runInNewContext(source, context);
  return { api: context.window.WorkbenchDensity, storage, attributes, events };
}
const empty = host();
assert.equal(empty.api.get().density, 'comfortable');
assert.equal(empty.attributes['data-density'], 'comfortable');
const saved = host('compact');
assert.equal(saved.api.get().density, 'compact');
assert.equal(saved.attributes['data-density'], 'compact');
const observed = [], unsubscribe = saved.api.subscribe(value => observed.push(value));
saved.api.set('comfortable');
assert.equal(saved.storage.value, 'comfortable');
assert.equal(observed[0].density, 'comfortable');
unsubscribe(); saved.api.set('compact'); assert.equal(observed.length, 1);
assert.throws(() => saved.api.set('dense'), /只能/);
assert.equal(saved.api.get().density, 'compact');
const invalid = host('dense');
assert.equal(invalid.api.get().density, 'comfortable'); assert.match(invalid.api.get().error, /无效/);
const denied = host(null, true);
assert.match(denied.api.get().error, /无法读取/);
denied.api.set('compact');
assert.equal(denied.attributes['data-density'], 'compact'); assert.match(denied.api.get().error, /未保存/);
denied.events.pageshow();
assert.equal(denied.api.get().density, 'compact'); assert.match(denied.api.get().error, /无法读取/);
saved.storage.value = 'comfortable'; saved.events.storage({ key: 'unrelated' });
assert.equal(saved.api.get().density, 'compact');
saved.events.storage({ key: 'aps_density' }); assert.equal(saved.api.get().density, 'comfortable');
const snapshot = saved.api.get(); snapshot.density = 'compact';
assert.equal(saved.api.get().density, 'comfortable');
console.log('workbench density preference contract passed');
