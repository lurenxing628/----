"""DU: load-order and fail-closed JS contracts without a build or a browser."""

import subprocess
from pathlib import Path

from tests.workbench.test_live_browser import runtime_tools


def test_du_restore_status_first_load_and_actual_api_method_contract():
    node, _, _ = runtime_tools()
    root = Path(__file__).resolve().parents[2]
    source = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const window={};
const context=vm.createContext({window,AbortController,setTimeout,clearTimeout});
for(const name of ['SystemRestoreStatus.js','SystemMaintenanceAPI.js'])
  new vm.Script(fs.readFileSync('frontend/workbench/app/'+name,'utf8')).runInContext(context);
const R=window.SystemRestoreStatus,A=window.SystemMaintenanceAPI;
const host={state:'ready',request_key:null,restart_required:false,automatic_resume:false,operations_available:true,
  result_source:'external_maintenance_journal',references:'reload_from_database_after_process_restart'};
const value={ok:true,schema_version:1,data:{kind:'restore_host',host},warnings:[],meta:{source:'production',
  result_source:'external_maintenance_journal',request_ref:'a'.repeat(32),time_basis:'factory_local'}};
const requests=[];
const api=A.create(async(url,options)=>{requests.push({url,options});return {ok:true,headers:{get:()=> 'application/json'},json:async()=>value};});
assert.equal(typeof api.host,'function');assert.equal(typeof api.lookupReference,'function');
assert.equal('host' in A.pending({getItem:()=>null}),false);
assert.equal(R.referencePath('a'.repeat(32),'request'),'/results/'+'a'.repeat(32));
assert.equal(R.referencePath('a'.repeat(32),'job'),'/jobs/'+'a'.repeat(32));
for(const ref of ['bad','../../workbench','x?write=yes'])assert.throws(()=>R.referencePath(ref));
for(const mutation of [{restart_required:true},{automatic_resume:true},{state:'unknown'},{result_source:'database'}])
  assert.throws(()=>R.validateHost({...host,...mutation}));
assert.throws(()=>R.validateHost({...host,state:'recovery_required',restart_required:true}));
for(const meta of [{...value.meta,source:'sample'},{...value.meta,result_source:'database'},{...value.meta,request_ref:null}])
  assert.throws(()=>R.envelope({...value,meta}));
const op={action:'restore',state:'succeeded',terminal:true,database_origin:'selected_backup',restart_required:true,
  result_source:'external_maintenance_journal',restart_scope:'restoring_process',references_require_reload:true,
  target_sha256:'b'.repeat(64),protection_sha256:'c'.repeat(64),database_after_sha256:'d'.repeat(64),request_key:'system-'+'e'.repeat(48)};
R.operation(op);
for(const mutation of [{database_origin:'unconfirmed'},{restart_scope:'browser'},{target_sha256:null,protection_sha256:'bad'},{references_require_reload:false}])
  assert.throws(()=>R.operation({...op,...mutation}));
const stopped={...host,state:'restart_required',restart_required:true,operations_available:false,request_key:op.request_key};
assert(R.describe(stopped,op).guidance.includes('请关闭整个 APS 软件后重新启动'));
assert(R.describe({...stopped,state:'recovery_required'},op).uncertain);
assert(R.describe({...stopped,request_key:'different-request-key'},op).uncertain);
assert(!R.describe(host,null).title.includes('已核实'));
assert.equal(R.describe(null,null).title,'无法读取维护状态');
assert(R.describe(null,null).guidance.includes('当前页面已暂停业务读写'));
assert(R.describe(stopped,null).title.includes('系统已暂停'));
assert(R.describe(null,op).uncertain);
(async()=>{assert.deepEqual(await api.host(),host);assert.equal(requests.length,1);
assert(requests[0].url.endsWith('/restore-host'));assert.equal(requests[0].options.cache,'no-store');
console.log('DU restore API binding, load order, references, metadata and restart contracts passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
'''
    completed = subprocess.run([node, "-e", source], cwd=str(root), capture_output=True, text=True, timeout=20)
    assert completed.returncode == 0, completed.stdout + completed.stderr
