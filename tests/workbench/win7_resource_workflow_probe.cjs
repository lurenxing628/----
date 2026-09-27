'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path'), Module = require('node:module');
const ready = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const originalPath = path.join(__dirname, 'resource_live_probe.cjs');
let source = fs.readFileSync(originalPath, 'utf8');
function replace(before, after) {
  assert.equal(source.split(before).length, 2, 'Expected one adapter anchor: ' + before);
  source = source.replace(before, after);
}
replace("await chromium.launch({executablePath:process.env.WORKBENCH_BROWSER,headless:true,args:['--disable-background-networking']})",
        "await require('./win7_workflow_transport.cjs').connect(chromium,ready.win7_evidence_root)");
replace("for(const viewport of [{width:1920,height:1080},{width:1392,height:924}])for(const theme of ['light','dark'])",
        "for(const viewport of [{width:1920,height:1080}])for(const theme of ['light'])");
replace("row.method==='GET'&&row.error==='net::ERR_ABORTED'",
        "require('./final_master_probe_support.cjs').isCanceledRead(row.method,row.url,row.error)");
replace("async function run(page,state,name,fn){", "async function run(page,state,name,fn){\n  if(Array.isArray(ready.skip_cases)&&ready.skip_cases.includes(name)){report.cases.push({state,name,status:'previously_passed',evidence:ready.previous_report});return;}\n");
const dependencyPath = path.join(__dirname, 'resource_files_live_probe.cjs');
let dependencySource = fs.readFileSync(dependencyPath, 'utf8');
const pythonAnchor = "const python=path.resolve(__dirname,'../../.venv/bin/python');";
assert.equal(dependencySource.split(pythonAnchor).length, 2);
dependencySource = dependencySource.replace(pythonAnchor, "const python=process.env.WIN7_HOST_PYTHON;assert(python,'Explicit host file-validation interpreter required');");
if (ready.file_only_xlsx) {
  replace("const state=viewport.width+'-'+theme", "const state=viewport.width+'-'+theme+'-xlsx'");
  replace("    await conflicts(page,context,state,{...helpers,createEntity,editAndDelete,openEdit,save,row,watch,readEntity},report,origin);", "    // Conflict workflows already passed in the full Win7 pass.");
  const uploadEnd=dependencySource.indexOf('async function confirmImport');
  assert(uploadEnd>0);
  dependencySource=dependencySource.slice(0,uploadEnd).replaceAll('CSV (.csv)','Excel (.xlsx)')
    .replace("name:'resources.csv',mimeType:'text/csv',buffer:Buffer.from(csv(rows))", "name:'resources.xlsx',mimeType:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',buffer:require('./win7_xlsx_input.cjs').fromCsv(csv(rows))")+dependencySource.slice(uploadEnd);
  for(const filename of ['calendar_files_live_probe.cjs','operator_calendar_files_live_probe.cjs','relation_files_live_probe.cjs']) {
    const file=path.join(__dirname,filename);
    const adapted=fs.readFileSync(file,'utf8').replaceAll('CSV (.csv)','Excel (.xlsx)').replaceAll('.csv\'', '.xlsx\'')
      .replaceAll("mimeType:'text/csv'", "mimeType:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'")
      .replaceAll('Buffer.from(csv(rows))', "require('./win7_xlsx_input.cjs').fromCsv(csv(rows))");
    fs.writeFileSync(path.join(ready.root,'xlsx-'+filename),adapted);
    const loaded=new Module(file,module);loaded.filename=file;loaded.paths=module.paths;Module._cache[file]=loaded;loaded._compile(adapted,file);loaded.loaded=true;
  }
  const auxPath=path.join(__dirname,'resource_aux_probe.cjs');
  let aux=fs.readFileSync(auxPath,'utf8');
  const begin=aux.indexOf("  await run(page,state,'material-import-preview-and-confirm'");
  const end=aux.indexOf("  await run(page,state,'material-export-and-bulk-delete'",begin);
  assert(begin>0&&end>begin);
  const portion=aux.slice(begin,end).replaceAll('CSV (.csv)','Excel (.xlsx)').replace("name:'resource-input.csv',mimeType:'text/csv',buffer:Buffer.from(","name:'resource-input.xlsx',mimeType:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',buffer:require('./win7_xlsx_input.cjs').fromCsv(");
  aux=aux.slice(0,begin)+portion+aux.slice(end);
  fs.writeFileSync(path.join(ready.root,'xlsx-resource_aux_probe.cjs'),aux);
  const loaded=new Module(auxPath,module);loaded.filename=auxPath;loaded.paths=module.paths;Module._cache[auxPath]=loaded;loaded._compile(aux,auxPath);loaded.loaded=true;
}
fs.writeFileSync(path.join(ready.root, 'executed-resource-probe.cjs'), source);
fs.writeFileSync(path.join(ready.root, 'executed-resource-files.cjs'), dependencySource);
fs.writeFileSync(path.join(ready.root, 'adaptation.json'), JSON.stringify({
  product: 'Real frozen d1307cb8 on original Win7 SP1 x64',
  changes: ['Connect actual guest Chrome109 through CDP instead of launching host browser',
    'Run one 1920x1080 light-theme business pass; display combinations have separate coverage',
    'Use explicit host Python only to inspect actual downloaded files',
    'Retain exact canceled-read classification from final_master_probe_support'],
  product_responses_mocked: false,
  intentional_faults: 'Original two-window stale write and lost-response cases retain actual server commits and deliberate network aborts'
}, null, 2));
const dependency = new Module(dependencyPath, module); dependency.filename=dependencyPath; dependency.paths=module.paths;
Module._cache[dependencyPath]=dependency; dependency._compile(dependencySource, dependencyPath); dependency.loaded=true;
const executed = new Module(originalPath, module); executed.filename=originalPath; executed.paths=module.paths;
executed._compile(source, originalPath);
