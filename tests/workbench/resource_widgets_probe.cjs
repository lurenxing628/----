/* Isolated component fixture, not production persistence evidence. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const { chromium } = require('playwright');
const root = path.resolve(__dirname, '../..');
const output = process.argv[2];
if (!output) throw new Error('Pass an artifact directory');
fs.mkdirSync(output, { recursive: true });
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json')));
const records = new Map(manifest.files.map(item => [item.path, item]));
const fixture = `
window.fixture = {bulk:[], rows: Array.from({length:50}, (_, index) => ({
  ref: String(index+1).padStart(48,'0'), business_code:'MAT-'+String(index+1).padStart(3,'0'),
  label:'Fixture material '+(index+1), status:index===10 ? null : 'active',
  fields:{spec:'Round',unit:'kg',stock_qty:index===10?null:index+1,remark:'Retained'},
  relationships:{},issues:[],write_context:null
}))};
function envelope(data) {return {ok:true,schema_version:1,data,meta:{source:'demo',time_basis:'factory_local',snapshot_ref:'fixture-snapshot',request_ref:'fixture-request',as_of:'2026-09-09T08:00:00'},warnings:[]};}
const adapter={
  summary: async()=>envelope({counts:{part:0,material:50,internal_op_types:0,machine:0,operator:0,external_op_types:0,supplier:0}}),
  list: async(kind,scope)=>{let rows=fixture.rows.filter(row=>!scope.query||row.business_code.includes(scope.query)||row.label.includes(scope.query));
    rows=rows.slice().sort((a,b)=>a.business_code.localeCompare(b.business_code)*(scope.direction==='desc'?-1:1));
    return envelope({entities:rows.slice((scope.page-1)*scope.size,scope.page*scope.size),page:{number:scope.page,size:scope.size,total:rows.length,pages:Math.max(1,Math.ceil(rows.length/scope.size)),sort:[{field:scope.sort,direction:scope.direction}]},create_context:null});},
  openBulk: async(kind,request)=>{fixture.bulk.push({kind,refs:request.refs.slice(),scope:request.scope});return {state:'cancelled'};}
};
ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(AppShell,{active:'process',title:'Resource component fixture',theme:document.documentElement.dataset.theme,showCapsule:false,onNav:()=>{}},React.createElement(ResourceWorkspace,{adapter,initialNode:'material'})));
`;
const html = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
  '<script src="/static/' + manifest.theme_script + '"></script>' +
  manifest.styles.map(item => '<link rel="stylesheet" href="/static/' + item + '">').join('') +
  '</head><body class="aps-workbench"><div id="root"></div>' +
  manifest.scripts.filter(item => !item.endsWith('/main.js')).map(item => '<script src="/static/' + item + '"></script>').join('') +
  '<script>' + fixture + '</script></body></html>';
const server = http.createServer((req, res) => {
  if (req.url === '/favicon.ico') { res.writeHead(204); res.end(); return; }
  if (req.url === '/') { res.setHeader('Content-Type', 'text/html;charset=utf-8'); res.end(html); return; }
  const name = new URL(req.url, 'http://fixture').pathname.slice('/static/'.length);
  if (!records.has(name)) { res.writeHead(404); res.end(); return; }
  res.setHeader('Content-Type', records.get(name).mime);
  res.end(fs.readFileSync(path.join(root, 'static', name)));
});

(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  let browser;
  const result = {scope:'isolated-component-fixture',data_source:'demo',build_id:manifest.build_id,cases:[],errors:[],external:[]};
  try {
    browser = await chromium.launch({executablePath:process.env.WORKBENCH_BROWSER,headless:true,args:['--disable-background-networking']});
    assert(browser.version().startsWith('109.'), 'Actual Chromium 109 required');
    result.browser = browser.version();
    const origin = 'http://127.0.0.1:' + server.address().port;
    for (const viewport of [{width:1920,height:1080},{width:1392,height:924}]) for (const theme of ['light','dark']) {
      const context = await browser.newContext({viewport});
      await context.addInitScript(value => {localStorage.setItem('aps_theme',value);localStorage.setItem('aps_kit_theme',value);},theme);
      const page = await context.newPage();
      page.on('pageerror',error=>result.errors.push(error.message));
      page.on('console',message=>{if(message.type()==='error')result.errors.push(message.text());});
      await page.route('**/*',route=>{if(!route.request().url().startsWith(origin+'/')){result.external.push(route.request().url());return route.abort();}return route.continue();});
      await page.goto(origin);
      assert(await page.evaluate(()=>{const form=new FormData();form.append('probe','value');return form.get('probe')==='value';}),'Chromium 109 has native FormData');
      await page.getByRole('checkbox',{name:'选择 MAT-001 Fixture material 1',exact:true}).waitFor();
      await page.evaluate(()=>document.fonts.ready);
      const selected = page.locator('[data-resource-selection-count]');
      await page.getByRole('checkbox',{name:'选择 MAT-001 Fixture material 1',exact:true}).check();
      await page.getByRole('checkbox',{name:'选择 MAT-002 Fixture material 2',exact:true}).check();
      assert.equal(await selected.innerText(),'2');
      await page.getByRole('button',{name:'下一页',exact:true}).click();
      await page.getByRole('checkbox',{name:'选择 MAT-021 Fixture material 21',exact:true}).waitFor();
      assert.equal(await selected.innerText(),'2');
      await page.getByRole('checkbox',{name:'全选当前页',exact:true}).check();
      assert.equal(await selected.innerText(),'22');
      await page.getByRole('checkbox',{name:'全选当前页',exact:true}).uncheck();
      assert.equal(await selected.innerText(),'2');
      await page.getByRole('searchbox',{name:'搜索编号或名称'}).fill('MAT-040');
      await page.getByRole('button',{name:'搜索',exact:true}).click();
      await page.getByRole('checkbox',{name:'选择 MAT-040 Fixture material 40',exact:true}).waitFor();
      assert.equal(await selected.innerText(),'2');
      assert(await page.getByText('含非当前页记录',{exact:true}).isVisible());
      await page.getByRole('button',{name:'批量删除',exact:true}).click();
      await page.waitForFunction(()=>fixture.bulk.length===1);
      const bulk=await page.evaluate(()=>fixture.bulk[0]);
      assert.deepEqual(bulk.refs,[String(1).padStart(48,'0'),String(2).padStart(48,'0')]);
      await page.getByRole('button',{name:'清除所有选择',exact:true}).click();
      assert.equal(await selected.count(),0);
      assert(await page.getByRole('button',{name:/^批量删除/}).isDisabled());
      const input = await page.evaluate(()=>{
        const original=fixture.rows[10], draft=APSResourceContract.draft('material',original);
        draft.label='Changed label';
        return APSResourceContract.input('material',draft,original);
      });
      assert.deepEqual(input,{label:'Changed label'});
      await page.evaluate(()=>window.scrollTo(0,0));
      const geometry=await page.evaluate(()=>({width:innerWidth,height:innerHeight,scroll:document.documentElement.scrollWidth,
        theme:document.documentElement.dataset.theme,controls:Array.from(document.querySelectorAll('.toolbar button,.toolbar input,.toolbar select')).map(node=>{const r=node.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width,height:r.height};})}));
      assert.equal(geometry.theme,theme);assert(geometry.scroll<=viewport.width+1);
      assert(geometry.controls.every(item=>item.width>0&&item.height>0&&item.right<=viewport.width+1));
      const screenshot = viewport.width+'x'+viewport.height+'-'+theme+'.png';
      await page.screenshot({path:path.join(output,screenshot)});
      result.cases.push({viewport,theme,selection_across_pages:true,hidden_selection_confirmed:true,unknown_fields_preserved:true,geometry,screenshot});
      await context.close();
    }
    assert.deepEqual(result.errors,[]);assert.deepEqual(result.external,[]);
  } finally {
    if(browser)await browser.close();
    await new Promise(resolve=>server.close(resolve));
    fs.writeFileSync(path.join(output,'component-result.json'),JSON.stringify(result,null,2)+'\n');
  }
  console.log(JSON.stringify({output,browser:result.browser,cases:result.cases.length,scope:result.scope,errors:result.errors,external:result.external}));
})().catch(error=>{console.error(error);process.exitCode=1;});
