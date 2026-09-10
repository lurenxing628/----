'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '../../..');
const BASE = '.codestable/roadmap/workbench-prototype-migration';
const INVENTORY = BASE + '/drafts/prototype-capability-inventory.md';
const ASSESSMENTS = [
  BASE + '/drafts/operations-backend-assessment.md',
  BASE + '/drafts/scheduling-backend-assessment.md',
];
const WORKSTREAMS = ['foundation', 'master-data', 'batches', 'scheduling', 'trial',
  'execution', 'analytics', 'calibration', 'dashboard', 'system'];
const FITS = ['reuse', 'adapt', 'new', 'mixed', 'unknown'];
const SCOPES = ['in_scope', 'needs_reachability_decision'];
const VERIFICATION = ['backend', 'browser_input', 'visual', 'persistence'];
const KIT = '前端设计/ui_kits/workbench/';
const REACHABILITY = 'WBP-DETAIL-008';
const DEMO_DECISIONS = ['WBP-FG-001', 'WBP-SCOPE-001', 'WBP-SYS-001',
  'WBP-TRIAL-009', 'WBP-SYS-017', 'WBP-FIELD-008'];

function nonempty(value, label) {
  assert.equal(typeof value, 'string', label + ': expected string');
  assert.ok(value.trim(), label + ': must not be empty');
}

function parseInventory(text) {
  let section = '';
  const rows = [];
  text.split('\n').forEach((line, index) => {
    if (line.startsWith('## ')) section = line.slice(3);
    if (!/^\| WBP-/.test(line)) return;
    const cells = line.split('|').slice(1, -1).map(cell => cell.trim());
    assert.equal(cells.length, 5, 'inventory columns at line ' + (index + 1));
    rows.push({ id: cells[0], title: cells[1], behavior: cells[2],
      requirements: cells[3], references: cells[4], line: index + 1, section });
  });
  assert.equal(rows.length, 206, 'inventory must contain the agreed 206 families');
  assert.equal(new Set(rows.map(row => row.id)).size, rows.length, 'duplicate inventory ID');
  return rows;
}

function prototypeRefs(text) {
  return [...text.matchAll(/`([^`\n]+\.(?:jsx|js|html|css|cjs)):(\d+)`/g)]
    .map(match => ({ path: match[1].startsWith('前端设计/') ? match[1] : KIT + match[1],
      line: Number(match[2]) }));
}

function countBy(caps, key, values) {
  const result = Object.fromEntries(values.map(value => [value, 0]));
  caps.forEach(cap => { result[cap[key]] = (result[cap[key]] || 0) + 1; });
  return result;
}

function summarize(caps) {
  const prefixes = [...new Set(caps.map(cap => cap.id.split('-')[1]))].sort();
  return {
    exact_count: caps.length,
    by_workstream: countBy(caps, 'workstream', WORKSTREAMS),
    by_scope: countBy(caps, 'scope', SCOPES),
    by_backend_fit: countBy(caps, 'backend_fit', FITS),
    by_capability_family: Object.fromEntries(prefixes.map(prefix =>
      [prefix, caps.filter(cap => cap.id.split('-')[1] === prefix).length])),
    requires_decision_count: caps.filter(cap => cap.requires_decision).length,
    needs_reachability_decision_count: caps.filter(cap => cap.needs_reachability_decision).length,
    implementation_status: { not_started: caps.filter(cap => cap.implementation_status === 'not_started').length },
    verification: Object.fromEntries(VERIFICATION.map(key =>
      [key, { not_run: caps.filter(cap => cap.verification[key] === 'not_run').length }])),
  };
}

function validatePlan(plan, options = {}) {
  const root = options.repoRoot || ROOT;
  const cache = new Map();
  function read(relative) {
    nonempty(relative, 'reference path');
    assert.ok(!path.isAbsolute(relative) && !relative.split(/[\\/]/).includes('..'),
      'reference must be repository-relative: ' + relative);
    if (!cache.has(relative)) cache.set(relative, fs.readFileSync(path.join(root, relative), 'utf8'));
    return cache.get(relative);
  }
  function checkRef(ref, label, allowBlank = false) {
    assert.ok(ref && typeof ref === 'object', label + ': reference required');
    const lines = read(ref.path).split('\n');
    assert.ok(Number.isInteger(ref.line) && ref.line > 0 && ref.line <= lines.length,
      label + ': invalid line ' + ref.path + ':' + ref.line);
    assert.ok(allowBlank || lines[ref.line - 1].trim(),
      label + ': blank evidence line ' + ref.path + ':' + ref.line);
    return lines;
  }
  assert.equal(plan.schema_version, 1, 'schema_version');
  assert.equal(plan.phase, 'planning', 'this validator checks the planning baseline only');
  assert.equal(plan.source_inventory.path, INVENTORY, 'source_inventory.path');
  const inventory = parseInventory(read(INVENTORY));
  const byId = new Map(inventory.map(row => [row.id, row]));
  assert.ok(Array.isArray(plan.backend_assessments), 'backend_assessments required');
  assert.deepEqual(plan.backend_assessments.map(item => item.path).sort(), ASSESSMENTS.slice().sort(),
    'exactly the two existing backend assessments are required');
  ASSESSMENTS.forEach(read);
  assert.ok(Array.isArray(plan.capabilities), 'capabilities must be an array');
  const caps = plan.capabilities;
  const ids = caps.map(cap => cap.id);
  assert.equal(new Set(ids).size, ids.length, 'duplicate capability ID');
  assert.deepEqual(ids.slice().sort(), [...byId.keys()].sort(), 'capability/inventory ID mismatch');

  caps.forEach(cap => {
    const label = cap.id;
    const original = byId.get(cap.id);
    assert.equal(cap.title, original.title, label + ': merged controls/fields were changed');
    assert.equal(cap.prototype_behavior, original.behavior, label + ': prototype behavior was changed');
    const source = cap.prototype_source;
    assert.ok(source && typeof source === 'object', label + ': prototype_source required');
    assert.equal(source.inventory.path, INVENTORY, label + ': wrong inventory');
    assert.equal(source.inventory.line, original.line, label + ': wrong inventory row');
    assert.equal(source.inventory.section, original.section, label + ': wrong inventory section');
    checkRef(source.inventory, label);
    assert.deepEqual(source.code_references, prototypeRefs(original.references), label + ': prototype refs differ');
    source.code_references.forEach(ref => {
      const lines = checkRef(ref, label, true);
      if (lines[ref.line - 1].trim()) return;
      const note = (source.reference_notes || []).find(item =>
        item.path === ref.path && item.line === ref.line);
      assert.ok(note, label + ': original blank anchor requires an explicit note');
      assert.equal(note.kind, 'blank_original_anchor', label + ': reference note kind');
      nonempty(note.note, label + ': reference note');
      assert.equal(note.nearby_anchor.path, ref.path, label + ': nearby anchor path');
      assert.equal(note.nearby_anchor.line, ref.line + 1, label + ': nearby anchor line');
      checkRef(note.nearby_anchor, label);
    });
    assert.ok(SCOPES.includes(cap.scope), label + ': scope must retain the capability');
    assert.equal(cap.needs_reachability_decision, cap.id === REACHABILITY, label + ': reachability marker');
    assert.equal(cap.scope, cap.id === REACHABILITY ? 'needs_reachability_decision' : 'in_scope', label + ': scope');
    assert.ok(WORKSTREAMS.includes(cap.workstream), label + ': invalid workstream');
    assert.ok(FITS.includes(cap.backend_fit), label + ': invalid backend_fit');
    nonempty(cap.backend_fit_rationale, label + ': backend_fit_rationale');
    assert.equal(typeof cap.requires_decision, 'boolean', label + ': requires_decision');
    assert.ok(Array.isArray(cap.decision_reasons), label + ': decision_reasons');
    cap.decision_reasons.forEach(reason => nonempty(reason, label + ': decision reason'));
    assert.equal(cap.requires_decision, cap.decision_reasons.length > 0, label + ': decision flag/reasons mismatch');
    if (DEMO_DECISIONS.includes(cap.id) || cap.id === REACHABILITY) {
      assert.equal(cap.requires_decision, true, label + ': demo/reachability decision must remain explicit');
    }
    assert.equal(cap.implementation_status, 'not_started', label + ': not a migrated implementation');
    assert.deepEqual(Object.keys(cap.verification).sort(), VERIFICATION.slice().sort(), label + ': verification fields');
    VERIFICATION.forEach(key => assert.equal(cap.verification[key], 'not_run', label + ': prior prototype checks are not migration proof'));
    assert.ok(Array.isArray(cap.required_actions) && cap.required_actions.length > 0, label + ': required_actions');
    assert.equal(cap.required_actions[0].description, original.title, label + ': merged action fields were lost');
    assert.equal(cap.required_actions[0].backend_requirements, original.requirements, label + ': original requirements were lost');
    cap.required_actions.forEach(action => {
      assert.equal(action.action_id, null, label + ': atomic action IDs are not defined yet');
      assert.equal(action.needs_action_id_breakdown, true, label + ': must split actions in the next phase');
      nonempty(action.description, label + ': action description');
      nonempty(action.backend_requirements, label + ': action backend requirements');
    });
    assert.ok(Array.isArray(cap.backend_evidence) && cap.backend_evidence.length > 0, label + ': backend_evidence');
    let keyPaths = 0;
    cap.backend_evidence.forEach(evidence => {
      const ref = evidence.assessment;
      assert.ok(ref && ASSESSMENTS.includes(ref.path), label + ': unapproved assessment source');
      const lines = checkRef(ref, label);
      nonempty(ref.section, label + ': assessment section');
      assert.equal(lines[ref.line - 1].replace(/^#{2,3} /, ''), ref.section, label + ': assessment heading mismatch');
      const headingDepth = lines[ref.line - 1].match(/^#{2,3} /)[0].trim().length;
      let end = ref.line;
      while (end < lines.length) {
        const heading = lines[end].match(/^(#{1,6}) /);
        if (heading && heading[1].length <= headingDepth) break;
        end++;
      }
      const sectionText = lines.slice(ref.line - 1, end).join('\n');
      nonempty(evidence.note, label + ': evidence note');
      assert.ok(Array.isArray(evidence.key_paths), label + ': key_paths required');
      evidence.key_paths.forEach(keyRef => {
        assert.ok(/^(core|web|data|templates|static)\//.test(keyRef.path), label + ': not a real product path');
        checkRef(keyRef, label);
        assert.ok(sectionText.includes('`' + keyRef.path + ':' + keyRef.line + '`'),
          label + ': path not cited by the specified assessment section');
        keyPaths++;
      });
      if (!evidence.key_paths.length) nonempty(evidence.no_key_paths_reason, label + ': missing-path explanation');
    });
    if (cap.backend_fit !== 'unknown') assert.ok(keyPaths > 0, label + ': no key product-path evidence');
  });
  const summary = summarize(caps);
  assert.deepEqual(plan.summary, summary, 'summary is not an exact count of capabilities');
  return { valid: true, ...summary, evidence_files_read: cache.size,
    proof_scope: 'planning schema, source coverage and evidence references only; no backend/browser/persistence proof' };
}

function selfTest(plan) {
  const tests = [
    ['missing ID', p => p.capabilities.pop()],
    ['duplicate ID', p => { p.capabilities[1].id = p.capabilities[0].id; }],
    ['extra ID', p => p.capabilities.push({ ...p.capabilities[0], id: 'WBP-EXTRA-001' })],
    ['lost merged fields', p => { p.capabilities[0].required_actions[0].description = 'shortened'; }],
    ['wrong prototype behavior', p => { p.capabilities[0].prototype_behavior = 'implemented'; }],
    ['lost original-anchor note', p => {
      delete p.capabilities.find(c => c.id === 'WBP-PROC-007').prototype_source.reference_notes;
    }],
    ['silent exclusion', p => { p.capabilities[0].scope = 'excluded'; }],
    ['lost reachability marker', p => { p.capabilities.find(c => c.id === REACHABILITY).needs_reachability_decision = false; }],
    ['lost demo decision', p => { p.capabilities.find(c => c.id === 'WBP-TRIAL-009').requires_decision = false; }],
    ['false implementation', p => { p.capabilities[0].implementation_status = 'done'; }],
    ['false browser proof', p => { p.capabilities[0].verification.browser_input = 'passed'; }],
    ['missing evidence', p => { p.capabilities[0].backend_evidence = []; }],
    ['wrong evidence line', p => { p.capabilities[0].backend_evidence[0].assessment.line = 0; }],
    ['wrong summary', p => { p.summary.exact_count--; }],
  ];
  tests.forEach(([name, mutate]) => {
    const copy = JSON.parse(JSON.stringify(plan));
    mutate(copy);
    assert.throws(() => validatePlan(copy), undefined, name + ': invalid fixture was accepted');
  });
  assert.throws(() => JSON.parse('{invalid json'), SyntaxError);
  return { negative_cases_rejected: tests.length + 1, fixture_files_written: 0 };
}

if (require.main === module) {
  try {
    const args = process.argv.slice(2);
    assert.ok(args.length === 0 || args.length === 1 && args[0] === '--self-test',
      'Usage: node validate-plan.cjs [--self-test]');
    const plan = JSON.parse(fs.readFileSync(path.join(__dirname, 'workbench-capabilities.json'), 'utf8'));
    const result = validatePlan(plan);
    if (args[0] === '--self-test') result.self_test = selfTest(plan);
    process.stdout.write(JSON.stringify(result, null, 2) + '\n');
  } catch (error) {
    process.stderr.write('Capability plan validation failed: ' + error.message + '\n');
    process.exitCode = 1;
  }
}

module.exports = { validatePlan, parseInventory, prototypeRefs, summarize };
