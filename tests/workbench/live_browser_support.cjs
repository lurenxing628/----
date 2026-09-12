'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const API_PATH = '/api/workbench/v1/system/overview';
const pendingReads = new WeakMap();

class Recorder {
  constructor(root) {
    this.root = root;
    this.report = {schema_version:1, cases:[], assertions:0, screenshots:[], downloads:[],
      page_errors:[], console_errors:[], external_requests:[], failed_requests:[], http_errors:[],
      api_responses:[], injected_failures:[], first_render:[]};
  }
  ok(value, message) { this.report.assertions++; assert.ok(value, message); }
  equal(actual, expected, message) { this.report.assertions++; assert.deepEqual(actual, expected, message); }
  async shot(page, state, name) {
    const filename = String(this.report.screenshots.length + 1).padStart(3,'0') + '-' + state + '-' + name + '.png';
    const file = path.join(this.root,'screenshots',filename);
    await page.screenshot({path:file,fullPage:true,animations:'disabled',timeout:10000});
    this.report.screenshots.push(file);
    return file;
  }
  async run(page, state, name, action) {
    const row = {state,name,status:'passed'};
    try { await action(); }
    catch(error) { row.status='failed'; row.error=error.stack || String(error); }
    try { row.screenshot=await this.shot(page,state,name+(row.status==='failed'?'-FAILED':'')); }
    catch(error) { row.capture_error=error.message; row.status='failed'; }
    this.report.cases.push(row);
    console.log(state + ' / ' + name + ': ' + row.status);
    return row.status==='passed';
  }
  save() {
    this.report.summary = {cases:this.report.cases.length,
      passed:this.report.cases.filter(row=>row.status==='passed').length,
      failed:this.report.cases.filter(row=>row.status==='failed').length,
      assertions:this.report.assertions,screenshots:this.report.screenshots.length,
      real_api_responses:this.report.api_responses.filter(row=>row.source==='production').length,
      injected_failures:this.report.injected_failures.length};
    fs.writeFileSync(path.join(this.root,'probe-results.json'),JSON.stringify(this.report,null,2)+'\n');
    return this.report.summary;
  }
}

async function connected(page) {
  await page.waitForFunction(()=>Array.from(document.querySelectorAll('.wb-metric')).some(node=>
    node.querySelector('.wb-metric-label')?.textContent==='本机数据接入' &&
    node.querySelector('.wb-metric-value')?.textContent==='已连接'));
}

function trackReads(page) {
  const state = { requests: new Set(), lastEvent: Date.now() };
  pendingReads.set(page, state);
  page.on('request', request => {
    if (/^https?:/.test(request.url())) { state.requests.add(request); state.lastEvent = Date.now(); }
  });
  const done = request => { if (state.requests.delete(request)) state.lastEvent = Date.now(); };
  page.on('requestfinished', done); page.on('requestfailed', done);
}

async function settleReads(page) {
  // Track SPA follow-up reads too; callers still assert actual data and errors.
  const state = pendingReads.get(page), deadline = Date.now() + 12000;
  assert(state, 'Track browser requests before navigation');
  while (state.requests.size || Date.now() - state.lastEvent < 500) {
    assert(Date.now() < deadline, 'Reads did not finish: ' + Array.from(state.requests, request => request.url()).join(', '));
    await new Promise(resolve => setTimeout(resolve, 50));
  }
}

async function realRead(page, action, record, expected) {
  const wait = page.waitForResponse(response=>new URL(response.url()).pathname===API_PATH && response.request().method()==='GET');
  let response;
  try { await action(); response=await wait; }
  catch(error) { void wait.catch(()=>{}); throw error; }
  record.equal(response.status(),200,'Real backend request must succeed');
  const payload=await response.json();
  record.equal(payload.ok,true,'No successful API stubs are permitted');
  record.equal(payload.schema_version,1);
  record.equal(payload.meta.source,'production');
  record.equal(payload.meta.time_basis,'factory_local');
  record.ok(/^[0-9a-f]{32}$/.test(payload.meta.snapshot_ref),'Real snapshot identity');
  record.ok(/^[0-9a-f]{32}$/.test(payload.meta.request_ref),'Real request identity');
  record.ok(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/.test(payload.meta.as_of),'Factory-local timestamp');
  record.equal(payload.data.logs.operation_record_count,expected.operation_record_count,'Read the seeded SQLite records');
  record.equal(payload.data.backups.count,expected.backup_count,'Read the isolated backup directory');
  record.equal(payload.data.backups.files.map(row=>row.filename).sort(),expected.backup_names.slice().sort());
  record.equal(payload.data.config.values.auto_backup_interval_minutes,expected.backup_interval_minutes);
  record.equal(payload.data.config.writes_performed,false);
  record.equal(response.headers()['cache-control'],'no-store');
  record.report.api_responses.push({source:payload.meta.source,snapshot_ref:payload.meta.snapshot_ref,request_ref:payload.meta.request_ref,url:response.url()});
  await connected(page);
  await settleReads(page);
  return payload;
}

async function tab(page, id, record) {
  await page.locator('#sm-tab-'+id).click();
  await page.waitForFunction(id=>document.querySelector('#sm-tab-'+id)?.getAttribute('aria-selected')==='true',id);
  record.equal(await page.locator('#sm-tab-'+id).getAttribute('aria-selected'),'true');
  record.ok(await page.locator('#sm-panel-'+id).isVisible(),'Selected tab has a visible panel: '+id);
  if(await page.locator('.sm-workbench').getAttribute('data-source')==='current'){
    if(id==='backups'||id==='logs') await page.locator('#sm-panel-'+id+' .sm-record-table tbody tr').first().waitFor();
    if(id==='config') await page.locator('#sm-maintenance-auto_backup_interval_minutes').waitFor();
  }
  await settleReads(page);
}

async function layout(page, record) {
  const size=await page.evaluate(()=>({viewport:innerWidth,body:document.body.scrollWidth,document:document.documentElement.scrollWidth,
    mainRight:document.querySelector('.main-content')?.getBoundingClientRect().right}));
  record.ok(size.body<=size.viewport+1 && size.document<=size.viewport+1 && size.mainRight<=size.viewport+1,
    'No main-page horizontal overflow: '+JSON.stringify(size));
}

async function diagnostic(page, state, label, last, expected, record) {
  const wait=page.waitForEvent('download');
  await page.getByRole('button',{name:'导出诊断文件',exact:true}).click();
  const download=await wait;
  record.equal(download.suggestedFilename(),'aps-system-diagnostic.json');
  const file=path.join(record.root,'downloads',state+'-'+label+'.json');
  await download.saveAs(file);
  record.equal(await download.failure(),null);
  const raw=fs.readFileSync(file,'utf8'), value=JSON.parse(raw);
  record.equal(value.instance,expected.instance_label);
  record.equal(value.system.meta.snapshot_ref,last.meta.snapshot_ref,'Downloaded data matches the actual fetched snapshot');
  record.equal(value.system.data,last.data);
  record.equal(value.page_check.scope,'workbench-page');
  record.equal(value.page_check.checks.length,8);
  record.ok(value.page_check.checks.every(row=>row.status==='available'),'First-mount checks must be 8/8, not corrected only after a theme toggle');
  record.equal(value.page_check.checks.find(row=>row.id==='styles').status,'available');
  record.ok(!value.page_check.checks.find(row=>row.id==='model').detail.includes('尚未读取'),'No obsolete disconnected-model explanation');
  for(const key of ['service','database','backupHealth']) record.ok(!(key in value.page_check),'Page check does not claim backend state: '+key);
  record.ok(!raw.includes(expected.log_body_sentinel),'Diagnostic contains metadata, not log contents');
  record.report.downloads.push(file);
  return value;
}

module.exports={API_PATH,Recorder,connected,trackReads,settleReads,realRead,tab,layout,diagnostic};
