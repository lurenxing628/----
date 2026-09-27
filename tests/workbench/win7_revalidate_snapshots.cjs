'use strict';
const fs=require('node:fs'),path=require('node:path');
process.env.PYTHONIOENCODING='utf-8';process.env.PYTHONUTF8='1';
const {Probe}=require('./final_master_process_support.cjs');
const file=process.argv[2],bindings=JSON.parse(fs.readFileSync(file,'utf8'));
const report={source:file,checks:[],passed:false};
try{
 for(const item of bindings){
  const before=JSON.parse(fs.readFileSync(path.join(item.root,'before.json'),'utf8'));
  const after=JSON.parse(fs.readFileSync(path.join(item.root,'after.json'),'utf8'));
  const probe=new Probe({root:item.root,assets:{build_id:'d1307cb8-real-Win7'}});
  probe.currentCase=item.case;probe.lastAfter=after;probe.validate(probe.diff(before,after),item.policy);
  report.checks.push({case:item.case,passed:true,bindings:item.snapshots,tracking:probe.report.tracking_preservation||[]});
 }
 report.passed=true;
}catch(error){report.error=error.stack;console.error(error);process.exitCode=1;}
fs.writeFileSync(path.join(path.dirname(file),'verification.json'),JSON.stringify(report,null,2));
console.log(JSON.stringify({passed:report.passed,cases:report.checks.length}));
