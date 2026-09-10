'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path');
const {execFileSync} = require('node:child_process');
const {contrast} = require('./migrated_process_batch_visual.cjs');
class Probe {
  constructor(ready) {
    this.ready = ready; this.root = ready.root; this.serial = 0;
    this.report = {schema_version: 1, build_id: ready.assets.build_id, assets: ready.assets, cases: [], steps: [], screenshots: [], downloads: [], network: [], pageerrors: [], console: [], external: [], failed_requests: [], http_errors: [], oracles: []};
    this.report.mutation_policy = {
      business_rows: 'Only AN-* Parts, PartOperations, Batches, BatchOperations and OpTypes; PROC-001 sequence 10 unit_hours only',
      protected: 'All other business rows, all schema, ExternalGroups, old batch operations, plans, execution, backups and templates unchanged',
      receipt_columns_append_only: ['request_key', 'input_hash', 'receipt_ref', 'action', 'outcome_json', 'context_ref', 'committed_at_utc'],
      entity_ref_updates: ['revision', 'active'], process_confirmation_owners: 'AN-* and PROC-001 only',
      plan_source_refs: 'operation kind, alternate_key AN-B-*, additions or active only',
      plan_identity_clock: 'singleton=1, revision only; +4 for 3 operation inserts and 1 update; +6 for 3 copied inserts and deletes',
      cancel_noop: 'No business mutations; read/cancel prohibits receipts; actual noop command permits append-only receipt',
    };
  }
  json(name, value) { fs.writeFileSync(path.join(this.root, name), JSON.stringify(value, null, 2) + '\n'); }
  oracle() { return JSON.parse(execFileSync(process.env.AN_PYTHON, [path.join(__dirname, 'migrated_process_batch_oracle.py'), 'snapshot', this.root], {maxBuffer: 50 * 1024 * 1024})); }
  attach(page, state) {
    this.page = page; this.state = state;
    page.on('pageerror', e => {
      const row = {state, case: this.currentCase, at: new Date().toISOString(), last_step: this.report.steps[this.report.steps.length - 1], message: e.stack};
      const first = !this.report.pageerrors.some(error => error.case === row.case);
      this.report.pageerrors.push(row); console.error('AN_RUNTIME_ERROR ' + row.case + ' ' + e.message);
      if (first) this.errorCapture = (this.errorCapture || Promise.resolve()).then(async () => {
        row.dialogs = await page.locator('[role="dialog"]').evaluateAll(nodes => nodes.map(n => ({title: n.getAttribute('aria-label') || n.querySelector('.modal-h2')?.textContent,
          visibility: getComputedStyle(n).visibility, ariaModal: n.getAttribute('aria-modal'), activeInside: n.contains(document.activeElement),
          hiddenAncestors: !!n.closest('[hidden]'), rect: n.getBoundingClientRect().toJSON()})));
        row.screenshot = path.join(this.root, 'screenshots', 'runtime-error-' + row.case + '.png');
        await page.screenshot({path: row.screenshot}); this.save();
      }).catch(error => { row.capture_error = error.message; });
    });
    page.on('dialog', async d => { this.step('native-dialog-accept', d.type(), d.message()); await d.accept(); });
    page.on('console', e => { if (e.type() === 'error') this.report.console.push({state, case: this.currentCase, intentional_network_fault: !!this.intentionalNetworkFault, message: e.text()}); });
    page.on('requestfailed', r => this.report.failed_requests.push({state, case: this.currentCase, url: r.url(), error: r.failure(), intentional_network_fault: !!this.intentionalNetworkFault}));
    page.on('request', r => {
      if (!r.url().startsWith(this.ready.url + '/') && !/^(data:|blob:)/.test(r.url())) this.report.external.push({state, url: r.url()});
      if (r.url().startsWith(this.ready.url + '/api/')) {
        const body = r.postDataBuffer();
        this.report.network.push({state, event: 'request', method: r.method(), url: r.url(), post: r.headers()['content-type']?.includes('json') ? r.postData() : undefined, upload_bytes: body?.length});
      }
    });
    page.on('response', async r => {
      if (r.status() >= 400) this.report.http_errors.push({state, case: this.currentCase, url: r.url(), status: r.status()});
      if (!r.url().startsWith(this.ready.url + '/api/')) return;
      let payload; try { if (r.headers()['content-type']?.includes('json')) payload = await r.json(); } catch (_) {}
      this.report.network.push({state, event: 'response', status: r.status(), method: r.request().method(), url: r.url(), payload});
    });
    page.setDefaultTimeout(15000);
  }
  step(action, selector, value) { this.report.steps.push({state: this.state, at: new Date().toISOString(), action, selector, value}); }
  async click(locator) { this.step('click', String(locator)); await locator.click(); }
  async type(locator, value) { this.step('click+ControlOrMeta+A+Backspace+pressSequentially', String(locator), String(value)); await locator.click(); await locator.press('ControlOrMeta+A'); await locator.press('Backspace'); if (String(value)) await locator.pressSequentially(String(value)); }
  async select(locator, label) { await this.click(locator); const menu = this.page.getByRole('listbox'); await menu.waitFor(); await this.click(menu.getByRole('option', {name: label, exact: true})); }
  async response(suffix, action, status = 200) {
    if (suffix === '/entities/batch') suffix += '/query';
    const wait = this.page.waitForResponse(r => new URL(r.url()).pathname.endsWith(suffix));
    const [r] = await Promise.all([wait, action()]); assert.equal(r.status(), status, await r.text()); return r.json();
  }
  async shot(name) {
    await this.page.waitForFunction(() => !document.getAnimations().some(a => a.playState === 'running' && a.effect?.getTiming().iterations !== Infinity));
    const key = String(this.report.screenshots.length + 1).padStart(3, '0') + '-' + this.state + '-' + name;
    const file = path.join(this.root, 'screenshots', key + '.png');
    const geometry = await this.page.evaluate(() => ({width: innerWidth, height: innerHeight, body: document.body.scrollWidth,
      scroll: document.documentElement.scrollWidth, dialogs: Array.from(document.querySelectorAll('.modal-bg,[data-wb-table-filter]')).filter(n => n.getClientRects().length && !n.closest('[aria-hidden="true"]')).map(n => ({position: getComputedStyle(n).position, rect: n.getBoundingClientRect().toJSON(), wrapper: !!n.closest('.plana')}))}));
    await this.page.screenshot({path: file});
    const measured = await contrast(this.page); this.json('contrast-' + key + '.json', measured);
    this.report.screenshots.push({file, geometry, contrast: {checked: measured.checked, minimum: measured.minimum, failures: measured.failures}});
    assert(geometry.body <= geometry.width + 1 && geometry.scroll <= geometry.width + 1, 'page overflow: ' + JSON.stringify(geometry));
    for (const d of geometry.dialogs) { assert.equal(d.position, 'fixed'); assert(d.rect.left >= -1 && d.rect.top >= -1 && d.rect.right <= geometry.width + 1 && d.rect.bottom <= geometry.height + 1); }
    return file;
  }
  async download(name, action) {
    const pending = this.page.waitForEvent('download'); await action(); const item = await pending;
    const file = path.join(this.root, 'downloads', this.state + '-' + name + path.extname(item.suggestedFilename()));
    await item.saveAs(file); assert.equal(await item.failure(), null);
    const value = JSON.parse(execFileSync(process.env.AN_PYTHON, [path.join(__dirname, 'migrated_process_batch_oracle.py'), 'download', file], {maxBuffer: 15 * 1024 * 1024}));
    this.report.downloads.push(value); assert(value.bytes > 0); return value;
  }
  diff(before, after) {
    assert.deepEqual(after.schema, before.schema); assert.equal(after.integrity, 'ok'); assert.deepEqual(after.foreign_keys, []);
    const result = [];
    for (const table of Object.keys(before.tables)) {
      const old = new Map(before.tables[table].map(r => [r.__oracle_rowid__, r])), fresh = new Map(after.tables[table].map(r => [r.__oracle_rowid__, r]));
      for (const id of new Set([...old.keys(), ...fresh.keys()])) {
        const a = old.get(id), b = fresh.get(id); if (JSON.stringify(a) === JSON.stringify(b)) continue;
        result.push({table, id, before: a, after: b, columns: a && b ? Object.keys(a).filter(k => a[k] !== b[k]) : Object.keys(a || b)});
      }
    }
    return result;
  }
  validate(changes, policy) {
    for (const c of changes) {
      if (c.table === 'WorkbenchEntityRefs') {
        assert(c.after, 'Entity refs cannot disappear');
        if (c.before) { assert.equal(policy, 'write', 'Read/cancel/noop cannot revise old identity'); assert(c.columns.every(k => ['revision', 'active'].includes(k))); }
        continue;
      }
      if (c.table === 'sqlite_sequence') {
        assert.notEqual(policy, 'read'); assert(['PartOperations', 'BatchOperations'].includes((c.after || c.before).name));
        assert(c.after && (!c.before || c.after.seq >= c.before.seq)); continue;
      }
      if (policy === 'read') assert.fail('Read/cancel changed ' + c.table + ': ' + JSON.stringify(c));
      if (c.table === 'WorkbenchCommandReceipts') {
        assert(!c.before && c.after, 'Receipts append only');
        assert(c.columns.every(k => k === '__oracle_rowid__' || this.report.mutation_policy.receipt_columns_append_only.includes(k))); continue;
      }
      if (policy === 'noop') assert.fail('Noop changed ' + c.table);
      if (c.table === 'WorkbenchPlanIdentityClock') {
        assert(c.before && c.after && c.after.singleton === 1); assert.deepEqual(c.columns, ['revision']);
        const delta = this.currentCase.includes('batch-base-sync-operation') ? 4 : this.currentCase.includes('batch-crosspage-copy-delete-persist') ? 6 : 0;
        assert(delta > 0); assert.equal(c.after.revision - c.before.revision, delta); continue;
      }
      if (c.table === 'WorkbenchPlanSourceRefs') {
        const row = c.after || c.before; assert.equal(row.kind, 'operation'); assert(row.alternate_key.startsWith('AN-B-'));
        assert(c.after); if (c.before) assert.deepEqual(c.columns, ['active']); continue;
      }
      if (['WorkbenchProcessWorkflow', 'WorkbenchProcessOperationConfirmations'].includes(c.table)) {
        const ref = (c.after || c.before).part_ref;
        const identity = this.lastAfter.tables.WorkbenchEntityRefs.find(r => r.ref === ref);
        assert(identity && (identity.entity_key.startsWith('AN-') || identity.entity_key === 'PROC-001')); continue;
      }
      const row = c.after || c.before, owner = c.table.startsWith('Batch') ? row.batch_id : row.part_no || row.op_type_id;
      if (String(owner).startsWith('AN-')) continue;
      if (c.table === 'PartOperations' && owner === 'PROC-001') {
        assert(c.before && c.after && c.after.seq === 10); assert(c.columns.every(k => ['unit_hours'].includes(k)), JSON.stringify(c)); continue;
      }
      assert.fail('Out-of-scope mutation: ' + JSON.stringify(c));
    }
  }
  async run(name, policy, fn) {
    const id = String(++this.serial).padStart(3, '0') + '-' + this.state + '-' + name;
    this.currentCase = id;
    const before = this.oracle(); this.json('oracle-' + id + '-before.json', before);
    const errorsBefore = this.report.pageerrors.length;
    console.log('AN_START ' + id); const entry = {id, policy, passed: false};
    try { await fn(); entry.screenshot = await this.shot(name); entry.passed = true; }
    catch (e) { entry.error = e.stack; console.error('AN_PROBE_FAILURE ' + id + '\n' + e.stack); this.json('failure-' + id + '.json', {error: e.stack, text: await this.page.locator('body').innerText()}); try { await this.shot(name + '-FAILED'); } catch (_) {} }
    finally {
      const after = this.oracle(); this.json('oracle-' + id + '-after.json', after);
      this.lastAfter = after;
      const changes = this.diff(before, after); this.report.oracles.push({id, policy, changes});
      try { this.validate(changes, policy); } catch (e) { entry.passed = false; entry.oracle_error = e.stack; console.error(e.stack); }
      if (this.errorCapture) await this.errorCapture;
      if (this.report.pageerrors.length > errorsBefore) { entry.passed = false; entry.runtime_errors = this.report.pageerrors.length - errorsBefore; }
      this.report.cases.push(entry); this.save(); console.log('AN_RESULT ' + id + ' ' + (entry.passed ? 'PASS' : 'FAIL'));
    }
    if (!entry.passed && this.recover) await this.recover();
    return entry.passed;
  }
  save() { this.report.summary = {cases: this.report.cases.length, failed: this.report.cases.filter(c => !c.passed).length, steps: this.report.steps.length, screenshots: this.report.screenshots.length, downloads: this.report.downloads.length}; this.json('an-process-batch-report.json', this.report); }
}
module.exports = {Probe};
