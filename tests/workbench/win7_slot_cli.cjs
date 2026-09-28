'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const {channel,quote}=require('./win7_workflow_transport.cjs');
(async()=>{
 const [root,mode,current,target,fixture]=process.argv.slice(2);
 const allowed=['functional-d1307cb8','browser-d1307cb8','installed-d1307cb8','pressure1000-d1307cb8','pressure5000-d1307cb8'];
 assert(root&&['switch','restart','stop'].includes(mode)&&allowed.includes(current));
 if(mode==='switch')assert(allowed.includes(target)&&target!==current);
 const helper='\\\\vmware-host\\Shared Folders\\APSWorkflows20260927\\target-acceptance-d1307cb8.ps1';
 const call=(action,slot,args='')=>'& powershell.exe -NoProfile -ExecutionPolicy Bypass -File '+quote(helper)+' -Mode '+action+' -Slot '+slot+' '+args+'\nif($LASTEXITCODE -ne 0){throw '+quote(action+' failed for '+slot)+'}';
 const commands=[call('Stop',current),call('ExportDb',current)];
 if(mode==='switch'&&fixture){
  assert(/^[a-zA-Z0-9_-]+\.db$/.test(fixture));
  const hash=crypto.createHash('sha256').update(fs.readFileSync(path.join(root,'exchange/test-fixtures',fixture))).digest('hex');
  commands.push(call('ImportDb',target,'-FixtureName '+fixture+' -ExpectedDbSha256 '+hash));
 }
 if(mode!=='stop'){
  const next=mode==='restart'?current:target;
  commands.push(call('Start',next),call('StartChrome',next));
 }
 const result=await channel(root).job(commands.join('\n'),mode+'-'+current,240000);
 console.log(result.log);
})().catch(error=>{console.error(error);process.exitCode=1});
