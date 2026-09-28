'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),Module=require('node:module');
const {execFileSync}=require('node:child_process');
const ready=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const {Probe: BaseProbe}=require('./final_master_process_support.cjs');
class Probe extends BaseProbe {
  async run(name, policy, action) {
    if(Array.isArray(ready.skip_cases)&&ready.skip_cases.includes(name)){
      this.serial++;this.report.prior_cases=(this.report.prior_cases||[]).concat({name,evidence:ready.previous_report,execution:'previously_passed'});this.save();return true;
    }
    const passed=await super.run(name,policy,action);
    assert(passed,'Stop after the first failed case; preserve its actual guest state: '+name);
    return passed;
  }
  oracle() {
    const output=execFileSync(process.execPath,[path.join(__dirname,'win7_snapshot_cli.cjs'),ready.win7_evidence_root,ready.win7_slot,path.join(this.root,'db/aps-live.db')],{encoding:'utf8',timeout:90000});
    this.report.guest_snapshots=(this.report.guest_snapshots||[]).concat(JSON.parse(output));
    return super.oracle();
  }
}
const supportPath=path.join(__dirname,'win7_process_runtime_support.cjs');
const support=new Module(supportPath,module);support.filename=supportPath;support.paths=module.paths;support.exports={Probe};support.loaded=true;Module._cache[supportPath]=support;
const originalPath=path.join(__dirname,'migrated_process_batch_probe.cjs');
const recoveryPath=path.join(__dirname,'final_master_process_recovery.cjs');
const recoverySource=fs.readFileSync(recoveryPath,'utf8').replaceAll('查询原请求回执','查询结果');
fs.writeFileSync(path.join(ready.root,'executed-recovery-probe.cjs'),recoverySource);
const recovery=new Module(recoveryPath,module);recovery.filename=recoveryPath;recovery.paths=module.paths;Module._cache[recoveryPath]=recovery;recovery._compile(recoverySource,recoveryPath);recovery.loaded=true;
let source=fs.readFileSync(originalPath,'utf8');
function replace(before,after){assert.equal(source.split(before).length,2,'Expected adapter anchor '+before);source=source.replace(before,after);}
replace("require('./migrated_process_batch_support.cjs')","require('./win7_process_runtime_support.cjs')");
replace("await chromium.launch({executablePath: process.env.WORKBENCH_BROWSER, headless: true})","await require('./win7_workflow_transport.cjs').connect(chromium,ready.win7_evidence_root)");
replace("require('./migrated_process_batch_recovery.cjs')","require('./final_master_process_recovery.cjs')");
replace("  await processArea().locator('tbody tr[data-process-ref]').first().waitFor();", "  await processArea().locator('tbody tr[data-process-ref]').first().waitFor();\n  await page.waitForFunction(()=>document.fonts.status==='loaded',null,{timeout:30000});");
const anchor="  await page.goto(ready.resource_url); await page.locator('.hb-tile').first().waitFor();";
if(source.includes(anchor))replace(anchor,"  await page.goto('about:blank');\n"+anchor);
const oldLabel="d.getByText(/文件导入已完成|已查到文件导入结果/)";
if(source.includes(oldLabel))replace(oldLabel,"d.getByText(kind === 'hours' ? '已查到文件导入结果；导入不代替工时阶段的人工确认。' : '文件导入已完成；工艺确认状态以刷新后的详情为准。', {exact: true})");
fs.writeFileSync(path.join(ready.root,'executed-process-probe.cjs'),source);
fs.writeFileSync(path.join(ready.root,'adaptation.json'),JSON.stringify({product:'Frozen d1307cb8 and guest Chrome109',
  oracle:'Before/after actual guest SQLite snapshots using sqlite3_backup with read-only source; host checks only the copied evidence',
  response_faults:'Existing final_master_process_recovery deliberately loses a real committed response; no mocked success',
  uploads:'Actual file bytes transferred to guest browser file inputs',states:process.env.AN_STATES},null,2));
const executed=new Module(originalPath,module);executed.filename=originalPath;executed.paths=module.paths;executed._compile(source,originalPath);
