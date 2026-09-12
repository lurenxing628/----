/* Actual isolated Flask/SQLite + Chromium 109. The host adapter is test-local. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { chromium } = require('playwright');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), output = process.argv[2];
if (!output) throw new Error('Pass a fresh artifact directory');
fs.mkdirSync(output, { recursive: true });
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
const records = new Map(manifest.files.map(item => [item.path, { ...item, content: fs.readFileSync(path.join(root, 'static', item.path)) }]));
const files = ['resource-contract.js', 'resource-session.js', 'WorkbenchGuards.js', 'ResourceControls.jsx', 'WorkbenchGuardHost.jsx', 'ResourceForms.jsx',
  'WorkbenchControlBridge.js', 'WorkbenchControls.jsx', 'WorkbenchListControls.jsx', 'WorkbenchFormat.js', 'WorkbenchReferences.jsx',
  'CalendarContract.js', 'CalendarFields.jsx', 'CalendarDayDialog.jsx', 'CalendarRangeDialog.jsx', 'ResourceCalendar.jsx'];
const styleSources = ['00-tokens.css', '21-table-frame.css', '22-shared-controls.css', '31-batches-resources.css', '32-calendar-outsourcing.css'].map(name =>
  ({ name: 'styles/' + name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app/styles', name), 'utf8') }));
const compiled = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'),
  check_combined: true, sources: files.map(name => ({ path: name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8') })) });
fs.writeFileSync(path.join(output, 'source-hashes.json'), JSON.stringify(files.map(name => ({ name,
  sha256: require('node:crypto').createHash('sha256').update(fs.readFileSync(path.join(root, 'frontend/workbench/app', name))).digest('hex') })).concat(styleSources.map(item =>
  ({ name: item.name, sha256: require('node:crypto').createHash('sha256').update(item.code).digest('hex') }))), null, 2));
const python = String.raw`
import importlib, json, os, signal, sys, tempfile, threading
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(sys.argv[1]) / 'tests/workbench'))
from live_environment import create_root, environment, install_path_guard, write_json
root = create_root()
env = environment(root)
os.environ.clear(); os.environ.update(env)
os.chdir(str(root)); tempfile.tempdir = str(root / 'tmp')
sys.path.insert(0, sys.argv[1])
guard = install_path_guard(root)
app = importlib.import_module('app').app
from core.infrastructure.database import get_connection
from core.services.scheduler.calendar_service import CalendarService
from flask import request, jsonify
from werkzeug.serving import make_server
conn = get_connection(app.config['DATABASE_PATH'])
assert Path(app.config['DATABASE_PATH']).resolve() == root / 'db/aps-live.db'
conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('CAL-PROBE','Probe operator')")
conn.execute("INSERT INTO WorkbenchShiftProfiles(profile_id,name,anchor_date,cycle_days) VALUES ('CAL-PROBE','Probe shift','2026-09-01',1)")
conn.execute("INSERT INTO WorkbenchShiftPatternDays(profile_id,day_offset,is_rest,shift_start,shift_end) VALUES ('CAL-PROBE',0,0,'21:15','05:15')")
conn.execute("INSERT INTO WorkbenchOperatorProfiles(operator_id,shift_profile_id) VALUES ('CAL-PROBE','CAL-PROBE')")
conn.commit()
CalendarService(conn).upsert_operator_calendar('CAL-PROBE','2026-09-09',shift_start='23:15',shift_end='07:45',efficiency=.625,remark='Personal preserved')
protected = ['OperatorCalendar','WorkbenchShiftProfiles','WorkbenchShiftPatternDays','WorkbenchOperatorProfiles']
def rows(conn, table):
    return [dict(row) for row in conn.execute('SELECT * FROM ' + table)]
before = {table: rows(conn, table) for table in protected}; conn.close()
@app.route('/__calendar_probe/reset', methods=['POST'])
def reset():
    conn = get_connection(app.config['DATABASE_PATH'])
    conn.execute('DELETE FROM WorkCalendar'); conn.commit()
    CalendarService(conn).upsert('2026-09-09',shift_start='22:30',shift_end='06:30',efficiency=.875,allow_normal='no',allow_urgent='yes',remark='Original night')
    conn.close()
    return jsonify(ok=True)
@app.after_request
def journal(response):
    if request.path.startswith('/api/'):
        payload = response.get_json(silent=True) or {}
        row = {'method':request.method,'path':request.path,'status':response.status_code,'request':request.get_json(silent=True),
               'result':payload.get('result'),'source':payload.get('meta',{}).get('source')}
        with (root / 'requests.jsonl').open('a') as stream: stream.write(json.dumps(row) + '\n')
    return response
server = make_server('127.0.0.1',0,app,threaded=True)
stop = threading.Event()
signal.signal(signal.SIGTERM, lambda *_: stop.set())
signal.signal(signal.SIGINT, lambda *_: stop.set())
worker = threading.Thread(target=server.serve_forever,daemon=True); worker.start()
print('CALENDAR_READY ' + json.dumps({'root':str(root),'url':'http://127.0.0.1:'+str(server.server_port)}),flush=True)
stop.wait(); server.shutdown(); worker.join(); server.server_close()
conn = get_connection(app.config['DATABASE_PATH'])
after = {table:rows(conn,table) for table in protected}
result = {'stopped':not worker.is_alive(),'protected_unchanged':before==after,'guard':guard,
          'calendar_rows':rows(conn,'WorkCalendar'),'receipts':conn.execute('SELECT COUNT(*) FROM WorkbenchCommandReceipts').fetchone()[0]}
conn.close(); write_json(root / 'calendar-final.json',json.loads(json.dumps(result,default=str)))
print('CALENDAR_FINAL '+json.dumps(result,default=str),flush=True)
`;
const fixture = String.raw`
window.calendarProbe={commands:[],queries:[],committed:[],previews:[],source:'real-isolated-flask'};
const namespace='calendar';
const storageKey='calendar-widgets-pending-'+namespace;
async function readJSON(path,options) {
  const response=await fetch(path,options);
  const result=await response.json();
  if(!response.ok || result.ok===false)throw result;
  return result;
}
const adapter={
  query:async(path,scope,signal)=>{calendarProbe.queries.push({path,scope});return readJSON(path+'?'+new URLSearchParams(scope),{signal});},
  preview:async(path,body,signal)=>{calendarProbe.previews.push(body);return readJSON(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal});},
  command:async(kind,action,ref,body,signal)=>{calendarProbe.commands.push({kind,action,ref,body});
    return readJSON('/api/workbench/v1/calendar/'+(action==='confirm'?'range/confirm':action),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal});},
  lookup:async(key,signal)=>readJSON('/api/workbench/v1/commands/'+key,{signal}),
  readPending:()=>JSON.parse(localStorage.getItem(storageKey)||'null'),
  savePending:intent=>localStorage.setItem(storageKey,JSON.stringify(intent)),
  clearPending:()=>localStorage.removeItem(storageKey)
};
ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(AppShell,{active:'process',title:'Calendar fixture',theme:document.documentElement.dataset.theme,showCapsule:false,onNav:()=>{}},
  React.createElement('div',{className:'plana'},React.createElement(ResourceCalendar,{adapter,onCommitted:result=>calendarProbe.committed.push(result)}),React.createElement(WorkbenchGuardHost))));
`;
const html = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
  '<script src="/static/' + manifest.theme_script + '"></script>' + manifest.styles.map(item => '<link rel="stylesheet" href="/static/' + item + '">').join('') + '<style>' + styleSources.map(item => item.code).join('\n') + '</style>' +
  '</head><body class="aps-workbench"><div id="root"></div>' + manifest.scripts.filter(item => !item.endsWith('/main.js')).map(item => '<script src="/static/' + item + '"></script>').join('') +
  '<script src="/probe-components.js"></script><script>' + fixture + '</script></body></html>';
let backend;
const server = http.createServer((req, res) => {
  if (req.url.startsWith('/api/') || req.url.startsWith('/__calendar_probe/')) {
    const proxy = http.request(backend + req.url, { method: req.method, headers: { ...req.headers, host: new URL(backend).host } }, incoming => {
      res.writeHead(incoming.statusCode, incoming.headers); incoming.pipe(res);
    });
    proxy.on('error', error => { res.writeHead(502); res.end(error.message); }); req.pipe(proxy); return;
  }
  if (req.url === '/favicon.ico') { res.writeHead(204); res.end(); return; }
  if (req.url === '/') { res.setHeader('Content-Type', 'text/html;charset=utf-8'); res.end(html); return; }
  if (req.url === '/probe-components.js') { res.setHeader('Content-Type', 'application/javascript'); res.end(compiled.outputs.map(item => item.code).join('\n;\n')); return; }
  const name = new URL(req.url, 'http://fixture').pathname.slice('/static/'.length), record = records.get(name);
  if (!record) { res.writeHead(404); res.end(); return; }
  res.setHeader('Content-Type', record.mime); res.end(record.content);
});
async function startBackend() {
  const child = spawn(path.join(root, '.venv/bin/python'), ['-B', '-c', python, root], { cwd: root, env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' } });
  let log = '';
  const logfile = fs.createWriteStream(path.join(output, 'backend.log'));
  child.stdout.on('data', chunk => { log += chunk.toString(); logfile.write(chunk); });
  child.stderr.pipe(logfile, { end: false });
  const ready = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => { child.kill('SIGTERM'); reject(new Error('Backend startup timeout')); }, 60000);
    child.on('exit', code => { clearTimeout(timer); reject(new Error('Backend exit '+code+'\n'+log)); });
    child.stdout.on('data', () => { const match = log.match(/CALENDAR_READY (.+)\n/); if (match) { clearTimeout(timer); resolve(JSON.parse(match[1])); } });
  });
  return { child, ready, logfile };
}
async function monthJSON(page, year=2026, month=9) {
  const response = await page.request.get('/api/workbench/v1/calendar/month?year='+year+'&month='+month);
  assert.equal(response.status(),200,await response.text()); return (await response.json()).data;
}
async function changeOutside(page,date,fields) {
  const current = await monthJSON(page,Number(date.slice(0,4)),Number(date.slice(5,7)));
  const row = current.days.find(item=>item.date===date);
  const response = await page.request.post('/api/workbench/v1/calendar/upsert',{data:{request_key:require('node:crypto').randomUUID(),write_token:row.write_context.write_token,input:{date,fields}}});
  assert.equal(response.status(),200,await response.text());
}
async function done(page) {
  await page.getByText('已重新读取最新工作日历。',{exact:true}).waitFor();
  assert(await page.getByText(/服务器已确认提交。|服务器确认内容未变化。/).isVisible());
}
async function closeDialog(page) { await page.getByRole('dialog').getByRole('button',{name:'关闭',exact:true}).last().click(); await page.getByRole('dialog').waitFor({state:'hidden'}); }
async function openDay(page,date) { await page.getByRole('button',{name:new RegExp('^'+date+' ')}).click(); await page.getByRole('dialog').waitFor(); }
async function geometry(page,viewport) {
  const result = await page.evaluate(()=>({scrollWidth:document.documentElement.scrollWidth,theme:document.documentElement.dataset.theme,
    tables:Array.from(document.querySelectorAll('.calendar-range-dialog .wb-table-shell')).map(node=>({scroll:node.scrollWidth,client:node.clientWidth})),
    dialogs:Array.from(document.querySelectorAll('[role="dialog"]')).map(node=>{const r=node.getBoundingClientRect();return {x:r.x,y:r.y,right:r.right,bottom:r.bottom};}),
    cells:Array.from(document.querySelectorAll('.cal-cell:not(.empty)')).map(node=>{const r=node.getBoundingClientRect();return {width:r.width,height:r.height,scroll:node.scrollWidth,client:node.clientWidth};})}));
  assert(result.scrollWidth<=viewport.width+1); assert(result.cells.every(row=>row.width>0&&row.height>0&&row.scroll<=row.client+1));
  assert(result.tables.every(row=>row.scroll<=row.client+1));
  assert(result.dialogs.every(row=>row.x>=0&&row.y>=0&&row.right<=viewport.width+1&&row.bottom<=viewport.height+1)); return result;
}
(async()=>{
  let child, browser, logfile;
  const report={scope:'real-isolated-flask-calendar-components',host_adapter:'probe-local',cases:[],errors:[],external:[],http:[]};
  try {
    const started=await startBackend(); child=started.child; logfile=started.logfile; backend=started.ready.url; report.backend=started.ready;
    await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
    const origin='http://127.0.0.1:'+server.address().port;
    browser=await chromium.launch({executablePath:process.env.WORKBENCH_BROWSER,headless:true,args:['--disable-background-networking']});
    report.browser=browser.version();assert(report.browser.startsWith('109.'));
    for (const viewport of [{width:1920,height:1080},{width:1392,height:924}]) for(const theme of ['light','dark']) {
      const context=await browser.newContext({viewport,baseURL:origin});
      await context.addInitScript(value=>{localStorage.setItem('aps_theme',value);localStorage.setItem('aps_kit_theme',value);},theme);
      const page=await context.newPage(), id=viewport.width+'-'+theme;
      page.on('pageerror',error=>report.errors.push(error.message));
      page.on('response',response=>{if(response.status()>=400)report.http.push({url:response.url(),status:response.status()});});
      await page.route('**/*',route=>{if(!route.request().url().startsWith(origin+'/')){report.external.push(route.request().url());return route.abort();}return route.continue();});
      assert.equal((await page.request.post('/__calendar_probe/reset')).status(),200);
      await page.goto(origin);await page.getByRole('button',{name:/^2026-09-09 /}).waitFor();await page.evaluate(()=>document.fonts.ready);
      const boundaries=await page.evaluate(()=>({leap:APSCalendarContract.isDate('2000-02-29'),notLeap:APSCalendarContract.isDate('1900-02-29'),
        sunday:APSCalendarContract.rangeDates({start_date:'2027-01-03',end_date:'2027-01-03',scope:'weekday'}),
        century:APSCalendarContract.rangeDates({start_date:'0001-01-01',end_date:'0001-01-02',scope:'all'}),
        last:APSCalendarContract.rangeDates({start_date:'9999-12-31',end_date:'9999-12-31',scope:'all'})}));
      assert.deepEqual(boundaries,{leap:true,notLeap:false,sunday:[],century:['0001-01-01','0001-01-02'],last:['9999-12-31']});
      const initial=await geometry(page,viewport);assert.equal(initial.theme,theme);
      await page.screenshot({path:path.join(output,id+'-month.png'),animations:'disabled'});
      await page.getByRole('button',{name:/^2026-09-09 /}).focus();await page.keyboard.press('Enter');
      assert(await page.getByText(/^原始配置（只读）：.*22:30.*06:30/).isVisible());
      await page.getByLabel('备注',{exact:true}).fill('中文夜班备注 '+id);
      await page.screenshot({path:path.join(output,id+'-day.png'),animations:'disabled'});await geometry(page,viewport);
      await page.getByRole('button',{name:'保存配置',exact:true}).click();await done(page);
      let state=await monthJSON(page), night=state.days.find(row=>row.date==='2026-09-09');
      assert.equal(night.stored.shift_start,'22:30');assert.equal(night.stored.shift_end,'06:30');assert.equal(night.stored.efficiency,.875);
      assert.deepEqual(await page.evaluate(()=>calendarProbe.commands[0].body.input.fields),{note:'中文夜班备注 '+id});
      await closeDialog(page);await openDay(page,'2026-09-09');await page.getByRole('button',{name:'清除配置',exact:true}).click();
      await page.getByRole('button',{name:'确认清除，恢复默认',exact:true}).click();await done(page);await closeDialog(page);
      state=await monthJSON(page);assert.equal(state.days[8].calendar_ref,null);assert.equal(state.days[8].entity,null);
      await openDay(page,'2026-09-10');await page.getByLabel('可排工时（小时）').fill('9');await page.getByLabel('效率（%）').fill('90');
      await page.getByRole('group',{name:'允许普通件排产',exact:true}).getByRole('button',{name:'否',exact:true}).click();
      await page.getByRole('button',{name:'保存配置',exact:true}).click();await done(page);await closeDialog(page);
      state=await monthJSON(page);assert.equal(state.days[9].fields.hours,9);assert.equal(state.days[9].fields.eff,90);assert.equal(state.days[9].fields.allowNormal,'no');
      await openDay(page,'2026-09-10');await page.getByLabel('备注',{exact:true}).fill('保留草稿 '+id);
      await changeOutside(page,'2026-09-10',{eff:80,note:'Other write'});
      await page.getByRole('button',{name:'保存配置',exact:true}).click();await page.getByRole('alert').getByText('资料已变化，请重新读取并核对。',{exact:true}).waitFor();
      assert.equal(await page.getByLabel('备注',{exact:true}).inputValue(),'保留草稿 '+id);
      assert(await page.getByRole('button',{name:/^保存配置/}).isDisabled());
      await page.getByRole('button',{name:'重新读取最新资料',exact:true}).click();await page.getByRole('button',{name:'已核对，继续编辑',exact:true}).click();
      await page.getByRole('button',{name:'保存配置',exact:true}).click();await done(page);await closeDialog(page);
      state=await monthJSON(page);assert.equal(state.days[9].fields.hours,9);assert.equal(state.days[9].fields.eff,80);assert.equal(state.days[9].fields.note,'保留草稿 '+id);
      await openDay(page,'2026-09-10');await page.getByLabel('可排工时（小时）').fill('7');
      await page.getByRole('button',{name:'保存配置',exact:true}).click();await page.getByText(/保留的班次起止推导为 9 小时/).waitFor();
      assert.equal(await page.getByLabel('可排工时（小时）').inputValue(),'7');assert.equal((await monthJSON(page)).days[9].fields.hours,9);
      await page.getByRole('button',{name:'取消',exact:true}).click();await page.getByRole('button',{name:'放弃未保存内容并继续',exact:true}).click();
      await openDay(page,'2026-09-10');await page.getByLabel('效率（%）').fill('0');const before=await page.evaluate(()=>calendarProbe.commands.length);
      await page.getByRole('button',{name:'保存配置',exact:true}).click();await page.getByRole('alert').filter({hasText:'效率须大于'}).waitFor();
      assert.equal(await page.evaluate(()=>calendarProbe.commands.length),before);await page.getByRole('button',{name:'取消',exact:true}).click();await page.getByRole('button',{name:'放弃未保存内容并继续',exact:true}).click();
      await openDay(page,'2026-09-11');await page.getByRole('group',{name:'这一天是否排产',exact:true}).getByRole('button',{name:'休息日',exact:true}).click();
      assert(await page.getByLabel('可排工时（小时）').isDisabled());await page.getByRole('button',{name:'保存配置',exact:true}).click();await done(page);await closeDialog(page);
      state=await monthJSON(page);assert.equal(state.days[10].fields.type,'rest');assert.equal(state.days[10].fields.hours,0);assert.equal(state.days[10].fields.allowUrgent,'no');
      await openDay(page,'2026-09-12');await page.getByRole('group',{name:'这一天是否排产',exact:true}).getByRole('button',{name:'工作日',exact:true}).click();
      await page.getByLabel('可排工时（小时）').fill('6');await page.getByLabel('效率（%）').fill('110');
      await page.getByRole('group',{name:'允许普通件排产',exact:true}).getByRole('button',{name:'是',exact:true}).click();
      await page.getByRole('group',{name:'允许急件排产',exact:true}).getByRole('button',{name:'是',exact:true}).click();
      await page.getByRole('group',{name:'允许急件排产',exact:true}).getByRole('button',{name:'否',exact:true}).click();
      await page.getByRole('button',{name:'保存配置',exact:true}).click();await done(page);await closeDialog(page);
      state=await monthJSON(page);assert.equal(state.days[11].fields.hours,6);assert(Math.abs(state.days[11].fields.eff-110)<1e-10);
      assert.equal(state.days[11].fields.allowNormal,'yes');assert.equal(state.days[11].fields.allowUrgent,'no');assert.equal(state.stats.overrides,2);
      await openDay(page,'2026-09-12');assert.equal(await page.getByLabel('效率（%）').inputValue(),'110');await page.getByLabel('备注',{exact:true}).fill('Only note');
      await page.getByRole('button',{name:'保存配置',exact:true}).click();await done(page);
      assert.deepEqual(await page.evaluate(()=>calendarProbe.commands[calendarProbe.commands.length-1].body.input.fields),{note:'Only note'});await closeDialog(page);
      await page.getByRole('button',{name:'批量维护',exact:true}).click();
      await page.getByLabel('开始日期',{exact:false}).fill('2027-01-01');await page.getByLabel('结束日期',{exact:false}).fill('2028-01-01');
      await page.getByRole('button',{name:'预览全部日期',exact:true}).click();await page.getByText('全部命中 366 天',{exact:true}).waitFor();
      assert.equal(await page.getByLabel('预览页码').locator('option').count(),37);
      for(let number=1;number<=37;number++){await page.getByLabel('预览页码').selectOption(String(number));assert((await page.locator('.modal tbody tr').count())===(number===37?6:10));}
      assert(await page.getByRole('cell',{name:/^2028-01-01/}).isVisible());
      assert(await page.getByText('确认作用于全部 366 天，包含其他分页日期。',{exact:true}).isVisible());
      await page.screenshot({path:path.join(output,id+'-preview.png'),animations:'disabled'});await geometry(page,viewport);
      await changeOutside(page,'2027-01-01',{note:'Preserve range note'});
      await page.getByRole('button',{name:'确认全部 366 天',exact:true}).click();await page.getByText(/范围内日历已变化，请重新预览/).waitFor();
      await page.getByRole('button',{name:'重新预览',exact:true}).click();await page.getByText('全部命中 366 天',{exact:true}).waitFor();
      await page.getByRole('button',{name:'确认全部 366 天',exact:true}).click();await done(page);await closeDialog(page);
      assert.equal((await monthJSON(page,2027,1)).days[0].fields.note,'Preserve range note');
      assert((await monthJSON(page,2027,12)).days.every(row=>row.explicit));
      await page.getByRole('button',{name:'批量维护',exact:true}).click();await page.getByLabel('开始日期',{exact:false}).fill('2027-01-03');await page.getByLabel('结束日期',{exact:false}).fill('2027-01-03');
      await page.getByRole('button',{name:'仅周一至周五',exact:true}).click();await page.getByRole('button',{name:'预览全部日期',exact:true}).click();
      await page.getByText('全部命中 0 天',{exact:true}).waitFor();assert(await page.getByRole('button',{name:/^确认全部 0 天/}).isDisabled());
      await page.getByRole('button',{name:'返回修改范围',exact:true}).click();
      await page.getByLabel('开始日期',{exact:false}).fill('2027-01-01');await page.getByLabel('结束日期',{exact:false}).fill('2028-01-01');
      await page.getByRole('button',{name:'范围内每天',exact:true}).click();await page.getByRole('button',{name:'清除配置，恢复默认',exact:true}).click();
      await page.getByRole('button',{name:'预览全部日期',exact:true}).click();await page.getByText('全部命中 366 天',{exact:true}).waitFor();
      await page.getByRole('button',{name:'确认全部 366 天',exact:true}).click();await done(page);await closeDialog(page);
      assert((await monthJSON(page,2027,1)).days.every(row=>row.calendar_ref===null));
      if(theme==='light'&&viewport.width===1920){
        await openDay(page,'2026-09-10');await page.getByLabel('备注',{exact:true}).fill('Receipt uncertainty');
        await page.route('**/api/workbench/v1/commands/*',route=>route.abort('connectionfailed'));
        await page.route('**/api/workbench/v1/calendar/upsert',async route=>{await route.fetch();await route.abort('connectionfailed');});
        const commandCount=await page.evaluate(()=>calendarProbe.commands.length);
        await page.getByRole('button',{name:'保存配置',exact:true}).click();await page.getByText('结果待核实。请保留当前页面，不要重新新建或重复保存。',{exact:true}).waitFor();
        await page.keyboard.press('Escape');assert(await page.getByRole('dialog').isVisible());assert(await page.getByRole('button',{name:'取消',exact:true}).isDisabled());
        assert.equal(await page.evaluate(()=>calendarProbe.commands.length),commandCount+1);
        await page.reload();await page.getByRole('dialog',{name:'工作日历操作回执',exact:true}).waitFor();
        await page.getByText('结果待核实。请保留当前页面，不要重新新建或重复保存。',{exact:true}).waitFor();
        await page.unroute('**/api/workbench/v1/commands/*');await page.unroute('**/api/workbench/v1/calendar/upsert');
        await page.getByRole('button',{name:'查询原请求回执',exact:true}).click();await done(page);await closeDialog(page);
        assert.equal(await page.evaluate(()=>calendarProbe.commands.length),0);
        assert.equal((await monthJSON(page)).days[9].fields.note,'Receipt uncertainty');
      }
      await page.getByRole('button',{name:'上一月',exact:true}).click();await page.getByText('2026 年 8 月',{exact:true}).waitFor();
      await page.getByRole('button',{name:'今天',exact:true}).click();await page.getByRole('button',{name:/^2026-09-09 /}).waitFor();
      report.cases.push({viewport,theme,geometry:initial,full_366_day_preview:true,stale_preserves_draft_and_unedited_fields:true,night_fields_preserved:true,actual_commands:true});
      await context.close();
    }
    assert.deepEqual(report.errors,[]);assert.deepEqual(report.external,[]);assert(report.http.every(item=>item.status===409));
  } finally {
    if(browser)await browser.close();if(server.listening)await new Promise(resolve=>server.close(resolve));
    if(child&&child.exitCode===null){const stopped=new Promise(resolve=>child.once('exit',resolve));child.kill('SIGTERM');await stopped;}
    if(logfile)logfile.end();
    if(report.backend&&fs.existsSync(path.join(report.backend.root,'calendar-final.json'))){report.final=JSON.parse(fs.readFileSync(path.join(report.backend.root,'calendar-final.json')));}
    fs.writeFileSync(path.join(output,'calendar-result.json'),JSON.stringify(report,null,2)+'\n');
  }
  assert(report.final&&report.final.stopped);assert(report.final.protected_unchanged);assert.deepEqual(report.final.guard.violations,[]);
  console.log(JSON.stringify({output,backend:report.backend,browser:report.browser,cases:report.cases.length,scope:report.scope}));
})().catch(error=>{console.error(error);process.exitCode=1;});
