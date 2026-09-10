'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), crypto = require('node:crypto');
const {Probe} = require('./final_master_process_support.cjs');
const root = path.resolve(process.argv[2]);
const read = name => JSON.parse(fs.readFileSync(path.join(root, name), 'utf8'));
const digest = name => crypto.createHash('sha256').update(fs.readFileSync(path.join(root, name))).digest('hex');
const originalHash = digest('an-process-batch-report.json'), original = read('an-process-batch-report.json');
assert.equal(original.summary.cases, 67);
assert.equal(original.summary.failed, 8);
assert.equal(original.oracles.length, original.cases.length);
const probe = Object.create(Probe.prototype);
probe.root = root;
probe.report = {mutation_policy: original.mutation_policy};
const cases = [];
for (const entry of original.cases) {
  assert(!entry.error && !entry.runtime_errors, 'Cannot reclassify an actual browser failure: ' + entry.id);
  if (!entry.passed) assert(entry.oracle_error.includes('template_lineage_corrupt'));
  const oracle = original.oracles.find(row => row.id === entry.id);
  assert(oracle && oracle.policy === entry.policy);
  probe.currentCase = entry.id;
  probe.lastAfter = read('oracle-' + entry.id + '-after.json');
  const before = read('oracle-' + entry.id + '-before.json');
  assert.deepEqual(JSON.parse(JSON.stringify(probe.diff(before, probe.lastAfter))), oracle.changes);
  probe.validate(oracle.changes, oracle.policy);
  cases.push({id: entry.id, passed: true, original_passed: entry.passed, browser_rerun: false,
    before_sha256: digest('oracle-' + entry.id + '-before.json'), after_sha256: digest('oracle-' + entry.id + '-after.json')});
}
assert.equal(digest('an-process-batch-report.json'), originalHash);
fs.writeFileSync(path.join(root, 'final-master-process-revalidation.json'), JSON.stringify({
  kind: 'original_browser_snapshots_revalidated', original_report_sha256: originalHash,
  cases, tracking_preservation: probe.report.tracking_preservation || [],
  summary: {cases: cases.length, failed: 0, browser_rerun: false, corrected_oracle_failures: 8}
}, null, 2) + '\n');
console.log(JSON.stringify({cases: cases.length, failed: 0, browser_rerun: false}));
