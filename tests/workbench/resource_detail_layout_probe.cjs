'use strict';
// Actual Chromium 109, built components and in-memory records. No backend or database proof.
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const { chromium } = require('playwright');
const root = path.resolve(__dirname, '../..');
if (!process.argv[2]) throw new Error('Pass a temporary screenshot/report directory');
const output = path.resolve(process.argv[2]);
assert(output !== root && !output.startsWith(root + path.sep), 'Artifacts must stay outside the checkout');
fs.mkdirSync(output, { recursive: true });
const report = { scope: 'read-only-component-mock', data_source: 'in-memory-fixture',
  simulates_production_envelopes: true, production_persistence_tested: false, win7_hardware_tested: false,
  cases: [], assertions: 0, screenshots: [], errors: [], external: [], unexpected_requests: [], writes: 0 };
const hash = data => crypto.createHash('sha256').update(data).digest('hex');
const ref = n => n.toString(16).padStart(48, '0');
const AS_OF = '2026-09-09T08:00:00';
const make = (kind, fields, relationships = {}, extra = {}) => ({ kind, ref: ref(100),
  business_code: kind.toUpperCase() + '-001', label: '布局夹具名称', status: kind === 'op_type' ? null : 'active',
  fields, relationships, issues: [], write_context: null, ...extra });
const material = (name, fields, extra = {}) => ({ name, entity: make('material', fields, {}, extra),
  facts: ['spec', 'stock_qty'], expected: { spec: fields.spec == null || fields.spec === '' ? '未填写' : fields.spec } });
const typical = { remark: '按炉号区分，领用前核对规格。', stock_qty: 1234.875, unit: 'kg', spec: '45 钢 / 直径 30 mm' };
const details = [
  material('material-typical-shuffled', typical),
  material('material-zero', { unit: '件', remark: '', stock_qty: 0, spec: '零库存规格' }),
  material('material-unknown', { stock_qty: null, remark: null, spec: null, unit: null }, { status: 'unknown' }),
  material('material-long-identity-spec-unit-remark', {
    unit: '特殊计量单位'.repeat(10), remark: '第一行说明，换行必须保留。\n' + '长备注用于检查完整显示和自动换行。'.repeat(12),
    stock_qty: 9007199254740991, spec: 'SPEC-' + 'S355JR-1200x2400x16-'.repeat(7)
  }, { business_code: 'MAT-LONG-' + 'A0123456789'.repeat(15), label: '高强度轴承用圆钢材料名称'.repeat(7), status: 'unknown' }),
  material('material-reordered-same-content', { spec: typical.spec, unit: typical.unit, stock_qty: typical.stock_qty, remark: typical.remark }),
  { name: 'machine-legacy-fields-and-relations', entity: make('machine', {
    remark: '设备旧备注', inactive_reason: 'unknown', legacy_status: 'inactive', status: 'inactive', category: '旧设备分类'
  }, { op_type_ref: ref(1), op_type: { ref: ref(1), label: '精加工工种' }, group_ref: ref(2), group: { ref: ref(2), label: '旧设备组' } }, { status: 'unknown' }),
  facts: ['category', 'status', 'legacy_status', 'inactive_reason'],
  expected: { category: '旧设备分类', status: '停用', legacy_status: '原停用状态，原因未登记', inactive_reason: '未知' },
  texts: ['绑定工种', '精加工工种', '设备组', '旧设备组', '原始状态（只读）'] },
  { name: 'operator-legacy-fields-and-authorizations', entity: make('operator', {
    remark: '人员旧备注', inactive_reason: 'unknown', legacy_status: 'inactive'
  }, { skill_refs: [ref(1), ref(3)], skills: [{ ref: ref(1), label: '精加工技能' }, { ref: ref(3), label: '装配技能' }],
    shift_profile_ref: ref(4), shift_profile: { ref: ref(4), label: '旧早班' },
    legacy_machine_authorizations: [{ ref: ref(5), label: '旧设备授权甲', status: 'inactive' }, { ref: ref(6), label: '旧设备授权乙', status: 'active' }]
  }, { status: 'unknown' }), facts: ['legacy_status', 'inactive_reason'],
  expected: { legacy_status: '原停用状态，原因未登记', inactive_reason: '未知' },
  texts: ['技能工种', '精加工技能', '装配技能', '班次', '旧早班', '既有设备授权（只读）', '旧设备授权甲（历史授权）', '旧设备授权乙', '技能登记不改变既有设备授权。'] },
  { name: 'internal-op-type-capacity-and-relations', entity: make('op_type', { remark: '旧产能说明', category: 'internal' }, {},
    { availability: { basis: 'enabled_authorized_matching', machines: 1, operators: 1 } }), facts: ['category'], expected: { category: '自制' },
  texts: ['产能备注', '排产方式', '工时（换型＋单件）', '工种绑定', '技能与设备授权'], relations: ['machines', 'operators'] },
  { name: 'external-op-type-policy-and-suppliers', entity: make('op_type', { default_merge_mode: 'merged', remark: '外协旧备注', category: 'external' }),
  facts: ['category', 'default_merge_mode'], expected: { category: '外协', default_merge_mode: '合并设置' },
  texts: ['默认周期规则', '排产方式', '周期（天）', '旧单工种关联'], relations: ['suppliers'] },
  { name: 'supplier-legacy-fields-and-relations', entity: make('supplier', {
    default_days: 2.75, remark: '供应商旧备注', inactive_reason: 'unknown', legacy_status: 'inactive'
  }, { op_type_refs: [ref(7), ref(8)], op_types: [{ ref: ref(7), label: '旧热处理关联', legacy: true }, { ref: ref(8), label: '表面处理关联' }] }, { status: 'unknown' }),
  facts: ['legacy_status', 'inactive_reason', 'default_days'], expected: { legacy_status: '原停用状态，原因未登记', inactive_reason: '未知', default_days: '2.75' },
  texts: ['可做外协工种', '旧热处理关联', '表面处理关联', '默认周期（天）', '原始状态（只读）'] }
];
const fixture = `
const h = React.createElement;
const envelope = data => ({ok:true,schema_version:1,data,meta:{source:'production',time_basis:'factory_local',snapshot_ref:'layout-fixture',request_ref:'memory-only',as_of:${JSON.stringify(AS_OF)}},warnings:[]});
window.layoutFixture = {writes:0,reads:[],reloads:0,accepted:0};
function rejectWrite(){layoutFixture.writes++;throw new Error('Read-only layout fixture must not submit');}
const adapter = {command:rejectWrite,relations:async(parent,scope)=>{
  layoutFixture.reads.push(scope.relation);
  const kinds={machines:'machine',operators:'operator',suppliers:'supplier'};
  const labels={machines:'工种绑定',operators:'技能与设备授权',suppliers:'旧单工种关联'};
  const item={kind:kinds[scope.relation],ref:'f'.repeat(48),business_code:'REL-001',label:'只读关联夹具',status:'active',
    fields:{relation_source_label:labels[scope.relation],matching_machine_authorization_count:1,qualification_matches:true},relationships:{},issues:[],write_context:null};
  return envelope({parent_ref:parent,parent_kind:'op_type',relation:scope.relation,basis:{code:'recorded_associations',message:'内存登记关联，不代表当前时段可排。'},
    entities:[item],page:{number:scope.page,size:scope.size,total:1,pages:1,sort:[{field:'business_code',direction:'asc'}]}});
}};
function CreateReview({kind}){
  const [review,setReview]=React.useState(null);
  return h(ResourceForms,{adapter,kind,category:kind==='op_type'?'internal':undefined,action:'create',source:'production',
    writeContext:null,command:{phase:'idle',locked:false,submit:rejectWrite},onClose:()=>{},contextReview:review,
    onReloadContext:()=>{layoutFixture.reloads++;setReview(envelope({entities:[],page:{number:1,size:20,total:7,pages:1,sort:[]},create_context:null}));},
    onAcceptContext:()=>{layoutFixture.accepted++;setReview(null);}});
}
let fixtureRoot;
window.mountLayout = spec => {
  if(fixtureRoot)fixtureRoot.unmount();
  layoutFixture.reads=[];layoutFixture.reloads=0;layoutFixture.accepted=0;
  fixtureRoot=ReactDOM.createRoot(document.getElementById('fixture-root'));
  fixtureRoot.render(spec.create?h(CreateReview,{kind:spec.kind}):h(ResourceForms.Detail,{adapter,kind:spec.entity.kind,
    result:envelope(spec.entity),onClose:()=>{},onEdit:rejectWrite,onDelete:rejectWrite,onAdjustStock:rejectWrite,onRelated:()=>{}}));
};
ReactDOM.createRoot(document.getElementById('controls-root')).render(h(React.Fragment,null,h(WorkbenchGuardHost),h(WorkbenchControlStyles),h(WorkbenchControls),h(WorkbenchNumberControls)));
`;

function prepareAssets() {
  const manifestBytes = fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json'));
  const manifest = JSON.parse(manifestBytes);
  assert.equal(manifest.target, 'chrome109');
  report.build_id = manifest.build_id;
  if (process.env.WORKBENCH_EXPECT_BUILD) assert.equal(manifest.build_id, process.env.WORKBENCH_EXPECT_BUILD, 'Unexpected build ID');
  report.manifest_sha256 = hash(manifestBytes);
  const required = ['resource-contract.js', 'resource-session.js', 'WorkbenchFormat.js', 'WorkbenchTerms.js', 'WorkbenchReferences.jsx', 'WorkbenchGuards.js', 'ResourceControls.jsx', 'WorkbenchGuardHost.jsx', 'WorkbenchListControls.jsx', 'ResourceForms.jsx', 'ResourceDetailRelations.jsx'];
  for (const name of required) {
    const input = manifest.inputs.find(item => item.path === 'frontend/workbench/app/' + name);
    assert(input, 'Missing source provenance: ' + name);
    assert.equal(hash(fs.readFileSync(path.join(root, input.path))), input.sha256, 'Stale build; ask the main task to rebuild: ' + name);
  }
  const assets = new Map();
  for (const item of manifest.files) {
    const bytes = fs.readFileSync(path.join(root, 'static', item.path));
    assert.equal(hash(bytes), item.sha256, 'Asset changed during snapshot: ' + item.path);
    assert.equal(bytes.length, item.bytes, 'Asset size differs: ' + item.path);
    assets.set('/static/' + item.path, { bytes, mime: item.mime });
  }
  assert.equal(hash(fs.readFileSync(path.join(root, 'static/workbench/asset-manifest.json'))), report.manifest_sha256, 'Build changed during snapshot');
  report.asset_count = assets.size;
  const components = new Set(required.map(name => name.replace(/\.jsx$/, '.js')).concat([
    'WorkbenchControlBridge.js', 'WorkbenchControlStyles.js', 'WorkbenchSelectMenu.js', 'WorkbenchDatePickerModel.js',
    'WorkbenchDatePicker.js', 'WorkbenchControls.js', 'WorkbenchNumberControls.js', 'CalendarContract.js'
  ]).map(name => 'workbench/app/' + name));
  const scripts = manifest.scripts.filter(name => name.startsWith('workbench/vendor/') || name.startsWith('workbench/assets/foundation-') || components.has(name));
  for (const component of components) assert(scripts.includes(component), 'Required built component missing: ' + component);
  const html = '<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
    '<link rel="icon" href="/static/' + manifest.icon + '"><script src="/static/' + manifest.theme_script + '"></script>' +
    manifest.styles.map(name => '<link rel="stylesheet" href="/static/' + name + '">').join('') +
    '</head><body class="aps-workbench"><main class="plana"><div id="controls-root"></div><div id="fixture-root"></div></main>' +
    scripts.map(name => '<script src="/static/' + name + '"></script>').join('') + '<script>' + fixture + '</script></body></html>';
  return http.createServer((req, res) => {
    if (req.method !== 'GET') { report.unexpected_requests.push({ method: req.method, url: req.url }); res.writeHead(405); res.end(); return; }
    if (req.url === '/') { res.setHeader('Content-Type', 'text/html;charset=utf-8'); res.end(html); return; }
    const asset = assets.get(new URL(req.url, 'http://fixture').pathname);
    if (!asset) { report.unexpected_requests.push({ method: req.method, url: req.url }); res.writeHead(404); res.end(); return; }
    res.setHeader('Content-Type', asset.mime); res.end(asset.bytes);
  });
}

// Measure rendered text, not only scrollWidth: hidden overflow must not produce a false pass.
function measure() {
  const dialog = document.querySelector('[role="dialog"]'), body = dialog.querySelector('.modal-b');
  const rect = node => {
    if (!node) return null;
    const r = node.getBoundingClientRect();
    return { left: r.left, right: r.right, top: r.top, bottom: r.bottom, width: r.width, height: r.height };
  };
  const rgba = value => { const values = value.match(/[\d.]+/g).map(Number); return values.length === 3 ? values.concat(1) : values; };
  const blend = (front, back) => front.slice(0, 3).map((v, i) => v * front[3] + back[i] * (1 - front[3]));
  const background = node => {
    const color = rgba(getComputedStyle(node).backgroundColor);
    return color[3] === 1 ? color.slice(0, 3) : blend(color, node.parentElement ? background(node.parentElement) : [255, 255, 255]);
  };
  const luminance = color => color.map(v => v / 255).map(v => v <= .04045 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4))
    .reduce((sum, v, i) => sum + v * [.2126, .7152, .0722][i], 0);
  const text = [], clipped = [], walker = document.createTreeWalker(dialog, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const node = walker.currentNode, parent = node.parentElement;
    if (!node.textContent.trim() || parent.closest('style,script,svg,option,button:disabled') || !parent.getClientRects().length) continue;
    const style = getComputedStyle(parent);
    if (style.visibility !== 'visible' || style.display === 'none') continue;
    const bg = background(parent), fg = blend(rgba(style.color), bg), a = luminance(bg), b = luminance(fg);
    text.push({ text: node.textContent.trim(), primary: !parent.closest('[aria-hidden="true"]'),
      contrast: (Math.max(a, b) + .05) / (Math.min(a, b) + .05) });
    const owner = parent.closest('.wb-resource-fact,.wb-resource-identity>div,.wb-resource-remark,.wb-resource-review,.field,button,.modal-head,.wb-resource-read-time,.wb-resource-relation-content') || body;
    const bounds = rect(owner), range = document.createRange(); range.selectNodeContents(node);
    for (const line of Array.from(range.getClientRects())) {
      if (line.left < bounds.left - 1 || line.right > bounds.right + 1) clipped.push({ text: node.textContent, bounds, left: line.left, right: line.right });
    }
  }
  const selectors = '.modal-b,.modal-f,.modal-head,.wb-resource-identity,.wb-resource-code,h3,.wb-resource-facts,.wb-resource-fact,dt,dd,.wb-resource-stock,.wb-resource-stock>*,.wb-resource-remark,.wb-resource-links,.wb-resource-links .field,.wb-resource-read-time,.wb-resource-review,button';
  const overflow = Array.from(dialog.querySelectorAll(selectors)).filter(node => node.clientWidth > 0 && node.scrollWidth > node.clientWidth + 1)
    .map(node => ({ selector: node.className || node.tagName, text: node.textContent, width: node.clientWidth, scroll: node.scrollWidth }));
  const identity = dialog.querySelector('.wb-resource-identity'), stock = dialog.querySelector('.wb-resource-stock');
  const bodyStyle = getComputedStyle(body), dialogStyle = getComputedStyle(dialog);
  return { theme: document.documentElement.dataset.theme, viewport: [innerWidth, innerHeight], documentWidth: document.documentElement.scrollWidth,
    dialog: rect(dialog), border: [parseFloat(dialogStyle.borderLeftWidth), parseFloat(dialogStyle.borderRightWidth)], body: rect(body),
    content: { left: rect(body).left + body.clientLeft + parseFloat(bodyStyle.paddingLeft), right: rect(body).left + body.clientLeft + body.clientWidth - parseFloat(bodyStyle.paddingRight) },
    footer: rect(dialog.querySelector('.modal-f')), identity: rect(identity), title: rect(dialog.querySelector('.wb-resource-identity h3')),
    identityText: identity && rect(identity.firstElementChild), status: rect(dialog.querySelector('.wb-resource-identity .pill')),
    factsBox: rect(dialog.querySelector('.wb-resource-facts')), facts: Array.from(dialog.querySelectorAll('.wb-resource-fact')).map(node => ({
      field: node.dataset.field, value: node.querySelector('dd').textContent, box: rect(node), label: rect(node.querySelector('dt')),
      valueBox: rect(node.querySelector('dd')), align: getComputedStyle(node.querySelector('dd')).textAlign })),
    stock: stock && { box: rect(stock), quantity: rect(stock.querySelector('strong')), unit: rect(stock.querySelector('span')),
      value: stock.querySelector('strong').textContent, unitText: stock.querySelector('span').textContent,
      sameGroup: stock.querySelector('strong').parentElement === stock && stock.querySelector('span').parentElement === stock },
    remark: rect(dialog.querySelector('.wb-resource-remark')), readTime: rect(dialog.querySelector('.wb-resource-read-time')),
    overflow, clipped, text };
}

let current;
function check(name, fn) {
  const assertion = { name, passed: false }; current.assertions.push(assertion); report.assertions++;
  try { fn(); assertion.passed = true; } catch (error) { assertion.error = error.message; throw error; }
}
const near = (a, b) => Math.abs(a - b) <= 1;
const contains = (parent, child) => child.left >= parent.left - 1 && child.right <= parent.right + 1 && child.top >= parent.top - 1 && child.bottom <= parent.bottom + 1;
const disjoint = (a, b) => a.right <= b.left + 1 || b.right <= a.left + 1 || a.bottom <= b.top + 1 || b.bottom <= a.top + 1;
async function shot(page, name) {
  await settled(page);
  const file = path.join(output, current.state + '-' + current.name + '-' + name + '.png');
  await page.screenshot({ path: file });
  report.screenshots.push(file); current.screenshots.push(file);
}
async function settled(page) {
  await page.evaluate(async () => {
    await document.fonts.ready;
    await Promise.all(document.getAnimations().map(animation => animation.finished));
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
}
async function commonLayout(page) {
  await settled(page);
  const geometry = await page.evaluate(measure); current.geometry = geometry;
  check('requested-theme-applied', () => assert.equal(geometry.theme, current.theme));
  check('dialog-contained-in-viewport', () => assert(contains({ left: 0, right: current.viewport.width, top: 0, bottom: current.viewport.height }, geometry.dialog)));
  check('no-document-horizontal-overflow', () => assert(geometry.documentWidth <= current.viewport.width + 1));
  check('no-element-horizontal-overflow', () => assert.deepEqual(geometry.overflow, []));
  check('rendered-text-not-clipped', () => assert.deepEqual(geometry.clipped, []));
  check('primary-text-theme-contrast', () => {
    const primary = geometry.text.filter(item => item.primary);
    assert(primary.length >= 5, 'Text audit must not be empty');
    assert.deepEqual(primary.filter(item => item.contrast < 4.5), []);
  });
  check('footer-spans-dialog-inner-width', () => {
    assert(near(geometry.footer.left, geometry.dialog.left + geometry.border[0]));
    assert(near(geometry.footer.right, geometry.dialog.right - geometry.border[1]));
  });
  check('footer-contained-and-after-body', () => {
    assert(contains(geometry.dialog, geometry.footer)); assert(geometry.footer.top >= geometry.body.bottom - 1);
  });
  return geometry;
}
async function visibleText(page, text) {
  const target = page.getByRole('dialog').getByText(text, { exact: true });
  await target.scrollIntoViewIfNeeded();
  const visible = await target.evaluate(node => {
    const r = node.getBoundingClientRect(), body = node.closest('.modal-b').getBoundingClientRect();
    return r.width > 0 && r.height > 0 && r.bottom > body.top && r.top < body.bottom;
  });
  check('text-reachable-by-scroll: ' + text, () => assert(visible));
}
async function detailCase(page, spec) {
  await page.evaluate(spec => mountLayout(spec), spec);
  await page.locator('.wb-resource-identity h3').waitFor();
  if (spec.relations) await page.waitForFunction(count => document.querySelectorAll('.wb-resource-relation').length === count, spec.relations.length);
  const dialog = page.getByRole('dialog'), entity = spec.entity;
  if (spec.name.endsWith('shuffled')) check('fixture-fields-are-not-canonical-insertion-order',
    () => assert.notDeepEqual(Object.keys(entity.fields), ['spec', 'unit', 'stock_qty', 'remark']));
  const g = await commonLayout(page);
  check('canonical-fact-order-independent-of-input', () => assert.deepEqual(g.facts.map(item => item.field), spec.facts));
  for (const [field, value] of Object.entries(spec.expected)) check('field-value: ' + field, () => assert.equal(g.facts.find(item => item.field === field).value, value));
  const identity = await dialog.locator('.wb-resource-code').textContent(), title = await dialog.locator('.wb-resource-identity h3').textContent();
  check('identity-text-preserved', () => { assert.equal(identity, entity.business_code); assert.equal(title, entity.label); });
  check('identity-title-status-do-not-overlap', () => {
    assert(contains(g.identity, g.title));
    if (entity.kind === 'op_type') assert.equal(g.status, null);
    else { assert(g.status); assert(contains(g.identity, g.status)); assert(disjoint(g.identityText, g.status)); }
  });
  check('fact-labels-and-values-left-aligned', () => {
    for (const fact of g.facts) { assert.equal(fact.align, 'left'); assert(near(fact.box.left, fact.label.left)); assert(near(fact.box.left, fact.valueBox.left)); }
  });
  const remark = await dialog.locator('.wb-resource-remark dd').textContent();
  check('remark-content-preserved', () => assert.equal(remark, entity.fields.remark == null || entity.fields.remark === '' ? '未填写' : entity.fields.remark));
  check('remark-full-width-after-facts', () => {
    assert(near(g.remark.left, g.content.left) && near(g.remark.right, g.content.right));
    assert(g.remark.top >= g.factsBox.bottom - 1);
  });
  const time = await dialog.locator('.wb-resource-read-time time').getAttribute('datetime');
  check('read-time-after-remark-and-full-width', () => {
    assert.equal(time, AS_OF); assert(g.readTime.top >= g.remark.bottom - 1);
    assert(near(g.readTime.left, g.content.left) && near(g.readTime.right, g.content.right));
  });
  if (entity.kind === 'material') {
    const specFact = g.facts[0], stockFact = g.facts[1];
    check('spec-and-stock-in-two-ordered-columns', () => { assert(near(specFact.box.top, stockFact.box.top)); assert(specFact.box.right < stockFact.box.left); });
    check('stock-quantity-and-unit-one-group', () => {
      assert(g.stock.sameGroup); assert.equal(g.stock.value, entity.fields.stock_qty == null ? '未知' : String(entity.fields.stock_qty));
      assert.equal(g.stock.unitText, entity.fields.unit || '单位未填写'); assert(!g.facts.some(item => item.field === 'unit'));
    });
    check('stock-group-left-aligned-and-contained', () => {
      assert(near(g.stock.box.left, stockFact.box.left) && near(g.stock.quantity.left, stockFact.box.left));
      assert(contains(g.stock.box, g.stock.quantity) && contains(g.stock.box, g.stock.unit)); assert(disjoint(g.stock.quantity, g.stock.unit));
      if (!spec.name.includes('-long-')) {
        assert(g.stock.unit.left >= g.stock.quantity.right); assert(g.stock.unit.left - g.stock.quantity.right <= 12);
        assert(g.stock.unit.top < g.stock.quantity.bottom && g.stock.unit.bottom > g.stock.quantity.top);
      }
    });
  }
  const editInputs = await dialog.locator('input:not([type="search"]),textarea,select').count();
  check('readonly-detail-does-not-render-form-fields', () => assert.equal(editInputs, 0));
  await shot(page, 'top');
  for (const text of spec.texts || []) await visibleText(page, text);
  await dialog.locator('.wb-resource-read-time').scrollIntoViewIfNeeded(); await settled(page); await shot(page, 'tail');
  const reads = await page.evaluate(() => layoutFixture.reads.slice().sort());
  check('only-expected-in-memory-relation-reads', () => assert.deepEqual(reads, (spec.relations || []).slice().sort()));
}
async function reviewCase(page, kind) {
  await page.evaluate(kind => mountLayout({ create: true, kind }), kind);
  const dialog = page.getByRole('dialog'); await dialog.locator('input[name="business_code"]').waitFor();
  const values = { business_code: 'DRAFT-109', label: '输入内容应保留', ...(kind === 'material' ? { spec: 'DRAFT-SPEC', unit: 'kg', stock_qty: '0' } : { remark: '已填写产能备注\n第二行保留' }) };
  for (const [name, value] of Object.entries(values)) await dialog.locator('[name="' + name + '"]').fill(value);
  const draft = () => dialog.locator('input[name],textarea[name],select[name]').evaluateAll(nodes => Object.fromEntries(nodes.map(node => [node.name, node.value])));
  const before = await draft();
  await dialog.getByRole('button', { name: '刷新最新资料', exact: true }).click();
  const review = dialog.locator('.wb-resource-review'); await review.waitFor();
  await review.getByText('最新资料已读取，已填写的内容保持不变。请核对后继续编辑。', { exact: true }).waitFor();
  await review.getByText('当前资料总数：7', { exact: true }).waitFor();
  const accept = review.getByRole('button', { name: '已核对，继续编辑', exact: true });
  await accept.scrollIntoViewIfNeeded(); await commonLayout(page);
  const usable = await accept.evaluate(node => {
    const r = node.getBoundingClientRect(), body = node.closest('.modal-b').getBoundingClientRect();
    const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
    return !node.disabled && r.top >= body.top && r.bottom <= body.bottom && (hit === node || node.contains(hit));
  });
  check('new-review-button-visible-uncovered-and-enabled', () => assert(usable));
  const during = await draft(); check('reload-and-review-preserve-all-inputs', () => assert.deepEqual(during, before));
  await shot(page, 'review'); await accept.click(); await review.waitFor({ state: 'detached' });
  const after = await draft(); check('accept-review-preserves-all-inputs', () => assert.deepEqual(after, before));
  current.draft = { before, during, after };
  const events = await page.evaluate(() => ({ reloads: layoutFixture.reloads, accepted: layoutFixture.accepted, writes: layoutFixture.writes }));
  check('review-callbacks-once-without-submit', () => assert.deepEqual(events, { reloads: 1, accepted: 1, writes: 0 }));
  await dialog.locator('input[name="business_code"]').scrollIntoViewIfNeeded(); await shot(page, 'retained-inputs');
}
async function runCase(page, state, name, fn) {
  current = { ...state, name, passed: false, assertions: [], screenshots: [] }; report.cases.push(current);
  try {
    await fn();
    const writes = await page.evaluate(() => layoutFixture.writes); report.writes += writes;
    check('no-fixture-write-attempts', () => assert.equal(writes, 0)); current.passed = true;
  } catch (error) {
    current.error = error.stack;
    try { await shot(page, 'FAILED'); } catch (captureError) { current.screenshot_error = captureError.message; }
  }
  console.log(current.state + ' / ' + name + ': ' + (current.passed ? 'passed' : 'FAILED'));
}
async function main() {
  let browser, server;
  try {
    server = prepareAssets();
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    const origin = 'http://127.0.0.1:' + server.address().port;
    assert(process.env.WORKBENCH_BROWSER, 'Set WORKBENCH_BROWSER to actual Chromium 109');
    browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true, args: ['--disable-background-networking'] });
    report.browser = browser.version(); assert.match(report.browser, /^109\./);
    for (const viewport of [{ width: 1920, height: 1080 }, { width: 1392, height: 924 }]) for (const theme of ['light', 'dark']) {
      const state = { state: viewport.width + 'x' + viewport.height + '-' + theme, viewport, theme };
      const context = await browser.newContext({ viewport });
      try {
        await context.addInitScript(theme => { localStorage.setItem('aps_theme', theme); localStorage.setItem('aps_kit_theme', theme); }, theme);
        const page = await context.newPage(); page.setDefaultTimeout(6000);
        page.on('pageerror', error => report.errors.push({ state: state.state, message: error.message }));
        page.on('console', message => { if (message.type() === 'error') report.errors.push({ state: state.state, message: message.text() }); });
        await page.route('**/*', route => {
          if (!route.request().url().startsWith(origin + '/')) { report.external.push(route.request().url()); return route.abort(); }
          return route.continue();
        });
        await page.goto(origin, { waitUntil: 'load' });
        await page.waitForFunction(() => typeof window.mountLayout === 'function');
        for (const spec of details) await runCase(page, state, spec.name, () => detailCase(page, spec));
        for (const kind of ['material', 'op_type']) await runCase(page, state, 'create-' + kind + '-review-keeps-input', () => reviewCase(page, kind));
      } finally { await context.close(); }
    }
    assert.deepEqual(report.errors, []); assert.deepEqual(report.external, []); assert.deepEqual(report.unexpected_requests, []);
    assert(report.cases.length === 48 && report.cases.every(item => item.passed), 'See failed cases in resource-detail-layout-result.json');
  } catch (error) { report.runner_error = error.stack; process.exitCode = 1; }
  finally {
    if (browser) await browser.close();
    if (server && server.listening) await new Promise(resolve => server.close(resolve));
    report.summary = { cases: report.cases.length, assertions: report.assertions, failed: report.cases.filter(item => !item.passed).length, screenshots: report.screenshots.length };
    fs.writeFileSync(path.join(output, 'resource-detail-layout-result.json'), JSON.stringify(report, null, 2) + '\n');
  }
  console.log(JSON.stringify({ output, browser: report.browser, build_id: report.build_id, ...report.summary }));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
