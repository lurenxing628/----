'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const context = vm.createContext({}); context.window = context;
vm.runInContext(fs.readFileSync(path.join(__dirname, '../../frontend/workbench/app/system-contract.js'), 'utf8'), context);
const validate = context.APSWorkbenchSystemContract.validate;
let checks = 0;
for (const fixture of input.valid) { assert.equal(validate(fixture), true); checks++; }
const bare = {};
for (const key of Object.keys(input.valid[0])) bare[key] = {state: 'available'};
for (const fixture of [null, [], {}, bare]) { assert.equal(validate(fixture), false); checks++; }
const mutations = [
  data => { data.database.state = 'healthy'; },
  data => { data.backups.message = null; },
  data => { data.backups.files = null; },
  data => { data.backups.files = [null]; },
  data => { data.backups.files = [{filename: 'x', modified_at: null, size_bytes: 1}]; },
  data => { data.backups.files = [{filename: 'x', modified_at: '2026-09-09', size_bytes: Infinity}]; },
  data => { data.backups.files_truncated = 'false'; },
  data => { data.logs.operation_record_count = -1; },
  data => { data.config.values = {}; },
  data => { data.config.values.auto_backup_enabled = true; },
  data => { data.config.defaulted_fields = null; },
  data => { data.config.dirty_fields = ['unknown_key']; },
  data => { data.config.dirty_fields = ['auto_backup_enabled']; data.config.dirty_reasons = {}; },
  data => { data.maintenance.jobs = undefined; },
  data => { data.maintenance.jobs = [null, null, null]; },
  data => { data.maintenance.jobs[1] = data.maintenance.jobs[0]; },
  data => { data.maintenance.jobs[0].result = {}; },
  data => { data.maintenance.jobs[0].last_run_time = 123; },
  data => { data.logs.error = {message: []}; }
];
for (const mutate of mutations) {
  const value = JSON.parse(JSON.stringify(input.valid[0])); mutate(value);
  assert.equal(validate(value), false, mutate.toString()); checks++;
}
console.log(JSON.stringify({checks, invalid: mutations.length + 4}));
