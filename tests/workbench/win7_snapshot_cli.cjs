'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const {channel,quote}=require('./win7_workflow_transport.cjs');
(async()=>{
  const [root,slot,destination]=process.argv.slice(2);
  assert(root&&slot&&destination);
  const id=crypto.randomUUID().replace(/-/g,'');
  await channel(root).job('& '+quote('C:\\APS-Workflows-20260927\\snapshot-helper\\Win7ReadOnlySnapshot.exe')+' '+quote(slot)+' '+quote(id)+'\nif($LASTEXITCODE -ne 0){throw "Consistent snapshot failed"}','snapshot');
  const copy=path.join(root,'exchange','snapshots',id+'.db');
  const digest=crypto.createHash('sha256').update(fs.readFileSync(copy)).digest('hex');
  assert.equal(digest,fs.readFileSync(copy+'.sha256','utf8').trim());
  fs.mkdirSync(path.dirname(destination),{recursive:true});fs.copyFileSync(copy,destination);
  console.log(JSON.stringify({id,slot,destination,sha256:digest,method:'sqlite3_backup with read-only source'}));
})().catch(error=>{console.error(error);process.exitCode=1});
