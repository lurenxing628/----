// APS Workbench · 基础资料（流程主线 · 方案A）native logic
// Ported from PlanAEmbed.html — runs in the page's own light DOM (no iframe),
// so every node inside is real and individually selectable/annotatable.
// window.APSPlanAInit(root, onNav): paints the page shell into `root` (a .plana
// element React renders empty), then wires the rail + content + modals. Modals
// and the toast are appended INTO `root` so their .plana-scoped CSS applies.
// Theme is handled globally by the app (html[data-theme]); the embed's own theme
// toggle / postMessage plumbing was dropped.

(function () {
var session = null, pendingNavigation = null;
window.APSPlanAData = {
  ensureSession: function () {
    if (!session) {
      var detachedRoot = document.createElement('div'); detachedRoot.className = 'plana';
      window.APSPlanAInit(detachedRoot);
    }
    return !!session;
  },
  getSnapshot: function () { return session ? session.getSnapshot() : null; },
  requestNavigation: function (target) {
    if (!target || ['part', 'route', 'opType', 'equipment', 'personnel', 'material', 'supplier', 'calendar'].indexOf(target.domain) < 0) {
      throw new Error('未知的基础资料定位目标');
    }
    pendingNavigation = JSON.parse(JSON.stringify(target));
  },
  applyNavigation: function () {
    if (!session || !session.isAttached() || !pendingNavigation) return false;
    var target = pendingNavigation;
    pendingNavigation = null;
    return session.navigate(target);
  }
};
window.APSPlanAInit = function (root, onNav) {
  if (!root) return;
  if (session) { session.attach(root, onNav); return session; }
  root.innerHTML = "<section class=\"rail\" aria-label=\"产能链主线\"><div class=\"rail-bar\"><span class=\"rail-cap\">产能链主线</span><span class=\"rail-hint\">点击任一环节进入维护</span><span class=\"rail-status\" id=\"railStatus\"></span></div><div class=\"flow\" id=\"flow\"></div><div class=\"rail-foot\" id=\"railFoot\"></div></section><section class=\"content\" id=\"content\"></section>";

/* ---------------- icons ---------------- */
var IP = {
  box: '<path d="M3 7l9-4 9 4v10l-9 4-9-4V7z"/><path d="M3 7l9 4 9-4M12 11v10"/>',
  database: '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.6 3.6 3 8 3s8-1.4 8-3V5"/><path d="M4 12c0 1.6 3.6 3 8 3s8-1.4 8-3"/>',
  play: '<circle cx="12" cy="12" r="9"/><path d="M10 8.5l6 3.5-6 3.5v-7z"/>',
  home: '<path d="M3 11l9-7 9 7"/><path d="M5 10v10h14V10"/>',
  gantt: '<path d="M4 7h10M4 12h15M4 17h7"/>',
  chart: '<path d="M4 5v15h16"/><path d="M7 14l4-4 3 3 5-6"/>',
  users: '<circle cx="9" cy="8" r="3"/><path d="M3 20c0-3.3 3-5 6-5s6 1.7 6 5"/><path d="M16 5.5a3 3 0 010 6M21.5 20c0-2.2-1.2-3.6-3.2-4.3"/>',
  clipboard: '<rect x="6" y="4" width="12" height="17" rx="2"/><path d="M9.5 4V3.2h5V4"/><path d="M9 10.5h6M9 14.5h4"/>',
  file: '<path d="M7 3h7l5 5v13H7z"/><path d="M14 3v5h5"/><path d="M10 13h6M10 17h6"/>',
  grid: '<rect x="4" y="4" width="7" height="7" rx="1.2"/><rect x="13" y="4" width="7" height="7" rx="1.2"/><rect x="4" y="13" width="7" height="7" rx="1.2"/><rect x="13" y="13" width="7" height="7" rx="1.2"/>',
  settings: '<path d="M4 7h9M18 7h2M4 17h2M11 17h9"/><circle cx="15" cy="7" r="2.2"/><circle cx="8" cy="17" r="2.2"/>',
  calendar: '<rect x="4" y="5" width="16" height="16" rx="2.5"/><path d="M4 10h16M8 3v4M16 3v4"/>',
  cube: '<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z"/><path d="M12 12l8-4.5M12 12v9M12 12L4 7.5"/>',
  route: '<circle cx="6" cy="6" r="2.4"/><circle cx="18" cy="18" r="2.4"/><path d="M8.4 6H15a3 3 0 010 6H9a3 3 0 000 6h6.6"/>',
  wrench: '<path d="M15 5.2a3.6 3.6 0 00-4.7 4.6L4 16.1 7.9 20l6.3-6.3A3.6 3.6 0 0018.8 9l-2.2 2.2-2-2L16.8 7z"/>',
  machine: '<path d="M3 20h18"/><path d="M5 20V9l5 3V9l5 3V6l4 2v12"/>',
  truck: '<path d="M3 6h11v9H3z"/><path d="M14 9h3.5L21 12.2V15h-7z"/><circle cx="7" cy="18" r="1.9"/><circle cx="17" cy="18" r="1.9"/>',
  import: '<path d="M12 3v11M8 10l4 4 4-4M5 20h14"/>',
  export: '<path d="M12 14V3M8 7l4-4 4 4M5 20h14"/>',
};
function svg(name, cls) {
  return '<svg class="' + (cls || '') + '" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + (IP[name] || '') + '</svg>';
}

/* ---------------- sidebar ---------------- */
var NAV_GROUPS = [
  { title: "① 数据准备", items: [ { id: "process", label: "基础资料", icon: "database" }, { id: "batches", label: "批次管理", icon: "box" } ] },
  { title: "② 执行排产", items: [ { id: "run", label: "执行排产", icon: "play" } ] },
  { title: "③ 看结果", items: [ { id: "dashboard", label: "值班台（首页）", icon: "home" }, { id: "gantt", label: "设备 / 人员甘特", icon: "gantt" }, { id: "analysis", label: "排产分析 · 周计划", icon: "chart" } ] },
  { title: "④ 现场", items: [ { id: "field", label: "现场记录", icon: "clipboard" } ] },
  { title: "⑤ 统计分析", items: [ { id: "reports", label: "执行复盘 · 报表中心", icon: "file" }, { id: "calib", label: "工时定额校准", icon: "scale" } ] },
  { title: "基础数据 · 系统", items: [ { id: "basedata", label: "主数据总览", icon: "grid" }, { id: "system", label: "系统管理", icon: "settings" } ] },
];


/* ---------------- rail model ---------------- */
var CHAINS = {
  internal: { name: '自制链', meas: '工时口径', tone: 'int', icon: 'machine', subs: [ { id: 'op', name: '自制工种', n: 8, unit: '个', icon: 'wrench' }, { id: 'eq', name: '设备', n: 14, unit: '台', icon: 'machine' }, { id: 'pp', name: '人员', n: 23, unit: '人', icon: 'users' } ] },
  external: { name: '外协链', meas: '周期口径', tone: 'ext', icon: 'truck', subs: [ { id: 'op', name: '外协工种', n: 4, unit: '个', icon: 'wrench' }, { id: 'sup', name: '供应商', n: 6, unit: '家', icon: 'truck' } ] },
};
var state = { node: 'process', sub: { internal: 'op', external: 'op' }, openPart: null, opView: 'full', stageFilter: 'all', openStage: null };
var partModal = null; // { code, repaint, close } — 零件工艺详情以弹出卡片呈现

/* ---------------- calendar model ---------------- */
/* cfg keyed "Y-M-D" (M 0-indexed). record: { type:'work'|'rest', hours, eff, prio, note } */
var calState = {
  y: 2026, m: 5,
  cfg: {
    '2026-5-2':  { type: 'work', hours: 8, eff: 100, prio: '普通' },
    '2026-5-4':  { type: 'work', hours: 8, eff: 100, allowNormal: 'yes', allowUrgent: 'yes' },
    '2026-5-9':  { type: 'work', hours: 8, eff: 100, allowNormal: 'yes', allowUrgent: 'yes' },
    '2026-5-11': { type: 'work', hours: 8, eff: 100, allowNormal: 'yes', allowUrgent: 'yes' },
    '2026-5-16': { type: 'work', hours: 8, eff: 100, allowNormal: 'yes', allowUrgent: 'yes' },
    '2026-5-18': { type: 'work', hours: 8, eff: 100, allowNormal: 'yes', allowUrgent: 'yes' },
    '2026-5-23': { type: 'work', hours: 8, eff: 100, allowNormal: 'yes', allowUrgent: 'yes' },
    '2026-5-25': { type: 'work', hours: 8, eff: 100, allowNormal: 'yes', allowUrgent: 'yes' },
    '2026-5-6':  { type: 'work', hours: 4, eff: 100, allowNormal: 'no', allowUrgent: 'yes', note: '周末仅急件加班' },
    '2026-5-19': { type: 'rest', note: '调休' }
  }
};
var MONTH_ZH = ['一', '二', '三', '四', '五', '六', '七', '八', '九', '十', '十一', '十二'];
function calKey(d) { return calState.y + '-' + calState.m + '-' + d; }
function calDayMeta(d) {
  var dow = new Date(calState.y, calState.m, d).getDay();
  var weekend = dow === 0 || dow === 6;
  var c = calState.cfg[calKey(d)];
  var cls = '', tag = '', working = !weekend;
  if (c) {
    if (c.type === 'work') {
      var an = c.allowNormal !== 'no';   // default 允许
      var au = c.allowUrgent !== 'no';
      if (!an && !au) {                  // 两项都不允许 = 这天不排产
        working = false;
        cls = weekend ? 'we' : 'rest';
        tag = '停排';
      } else {
        working = true;
        if (weekend) { cls = 'rest'; tag = '加班'; }
        else { cls = 'cfg'; tag = (c.hours != null ? c.hours : 8) + 'h'; }
        if (an && !au) tag += ' 普';      // 仅普通件
        else if (!an && au) tag += ' 急';  // 仅急件
      }
    } else { // rest
      working = false;
      if (weekend) { cls = 'we'; tag = '休'; }
      else { cls = 'rest'; tag = '调休'; }
    }
  } else if (weekend) { cls = 'we'; tag = '休'; }
  return { dow: dow, weekend: weekend, cfg: c, cls: cls, tag: tag, working: working };
}
function calStats() {
  var dim = new Date(calState.y, calState.m + 1, 0).getDate();
  var workDays = 0, configured = 0, overrides = 0, weekendRest = 0;
  for (var d = 1; d <= dim; d++) {
    var meta = calDayMeta(d);
    if (meta.working) workDays++;
    if (meta.cfg && meta.cfg.type === 'work') configured++;
    if (meta.cls === 'rest') overrides++;
    if (meta.cls === 'we') weekendRest++;
  }
  return { workDays: workDays, configured: configured, overrides: overrides, weekendRest: weekendRest };
}

function renderRail() {
  var f = document.getElementById('flow');
  // 中心枢纽（方案 3）：数据输入 → 工序(两条链) → 工作日历，箭头串联。
  var ARROW = '<svg viewBox="0 0 24 24" width="30" height="30" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h13M13 6l6 6-6 6"/></svg>';
  var ARROW15 = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h13M13 6l6 6-6 6"/></svg>';
  var CAL_ICO = '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + IP.calendar + '</svg>';
  var CHECK = '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 12.5l5 5 11-11"/></svg>';

  function ioTile(d) {
    var on = state.node === d.node;
    return '<button class="hb-tile io' + (on ? ' on' : '') + '" data-node="' + d.node + '">' +
      (d.warn ? '<span class="hb-nstat warn"></span>' : '') +
      '<span class="hb-tico io">' + svg(d.icon) + '</span>' +
      '<span class="hb-tbody"><span class="hb-tname">' + d.name + '</span>' +
      '<span class="hb-tmeta">' + d.meta + '</span></span></button>';
  }
  function laneBlock(laneId) {
    var c = CHAINS[laneId];
    var tone = laneId === 'internal' ? 'int' : 'ext';
    var cls = laneId === 'internal' ? 'intl' : 'extl';
    var tiles = c.subs.map(function (s) {
      var on = state.node === laneId && state.sub[laneId] === s.id;
      return '<button class="hb-tile ' + tone + (on ? ' on' : '') + '" data-node="' + laneId + '" data-sub="' + s.id + '">' +
        '<span class="hb-tico ' + tone + '">' + svg(s.icon) + '</span>' +
        '<span class="hb-tbody"><span class="hb-tname">' + s.name + '</span>' +
        '<span class="hb-tmeta">' + s.n + ' ' + s.unit + '</span></span></button>';
    }).join('');
    return '<div class="hb-lane ' + cls + '">' +
      '<div class="hb-lane-head"><span class="hb-lane-dot"></span><span class="hb-lane-name">' + c.name + '</span>' +
      '<span class="hb-lane-meas">' + c.meas + '</span>' +
      '<span class="hb-lane-count">' + c.subs.length + ' 项</span></div>' +
      '<div class="hb-lane-row">' + tiles + '</div></div>';
  }

  var blkData = '<div class="hb-block hero">' +
    '<div class="hb-bhead"><span class="hb-bdot io"></span><span class="hb-bname">数据输入</span><span class="hb-bmeas">2 源</span></div>' +
    '<div class="hb-bbody">' +
      ioTile({ node: 'process', icon: 'database', name: '工艺', meta: '12 模板 · 1 待解析', warn: true }) +
      ioTile({ node: 'material', icon: 'cube', name: '物料', meta: '86 条主数据' }) +
    '</div></div>';

  var blkOps = '<div class="hb-block hero hb-ops">' +
    '<div class="hb-bhead"><span class="hb-bdot fk"></span><span class="hb-bname">工序 · 两条链</span><span class="hb-bnum">5 环节</span></div>' +
    '<div class="hb-bbody">' + laneBlock('internal') + laneBlock('external') + '</div></div>';

  var WEEK = [['一'], ['二'], ['三'], ['四'], ['五'], ['六', 'rest'], ['日', 'rest']];
  var strip = WEEK.map(function (d) {
    return '<span class="hb-seg ' + (d[1] || '') + '"><span class="hb-sl">' + d[0] + '</span><span class="hb-sb"></span></span>';
  }).join('');
  var blkCal = '<div class="hb-block hero hb-cal-block' + (state.node === 'calendar' ? ' on' : '') + '" data-node="calendar" role="button" tabindex="0">' +
    '<div class="hb-bhead"><span class="hb-bdot cal"></span><span class="hb-bname">工作日历</span><span class="hb-bmeas">全局</span></div>' +
    '<div class="hb-bbody">' +
      '<div class="hb-cal-top"><span class="hb-cal-ico">' + CAL_ICO + '</span>' +
      '<span class="hb-cal-lead"><span class="hb-cl1">工时 / 调休 / 加班</span><span class="hb-cl2">统一作用于上方两条链口径</span></span></div>' +
      '<div class="hb-cal-stats">' +
        '<span class="hb-cs"><span class="hb-csv">8 h</span><span class="hb-csl">标准工时 / 日</span></span>' +
        '<span class="hb-cs"><span class="hb-csv">5 天</span><span class="hb-csl">本周工作日</span></span>' +
        '<span class="hb-cs"><span class="hb-csv">六 · 日</span><span class="hb-csl">休息 / 调休</span></span>' +
      '</div>' +
      '<div class="hb-cal-strip-cap"><span>本周排班</span>' +
        '<span class="hb-csc-key"><span class="hb-csc-dot work"></span>工作</span>' +
        '<span class="hb-csc-key"><span class="hb-csc-dot rest"></span>休息</span></div>' +
      '<div class="hb-cal-strip">' + strip + '</div>' +
    '</div></div>';

  f.innerHTML = '<div class="hb-hub">' +
    blkData + '<div class="hb-flowarr">' + ARROW + '</div>' +
    blkOps + '<div class="hb-flowarr">' + ARROW + '</div>' +
    blkCal + '</div>';

  // ---- 状态徽标（标题右侧）----
  var st = document.getElementById('railStatus');
  if (st) st.innerHTML = '<span class="rail-pill warn">1 项待处理</span>';

  // ---- 页脚：产能就绪度 + 下一步 ----
  var foot = document.getElementById('railFoot');
  if (foot) {
    foot.innerHTML =
      '<div class="hb-ready">' +
        '<div class="hb-r-top">' +
          '<span class="hb-r-ico">' + CHECK + '</span>' +
          '<span class="hb-rl1">产能就绪度</span>' +
          '<span class="hb-rl2">4 / 5 项就绪</span>' +
          '<span class="hb-r-tag">工艺路线 1 项待解析</span>' +
          '<span class="hb-r-spacer"></span>' +
          '<button class="hb-r-next" data-go="batches">下一步 · 批次管理 ' + ARROW15 + '</button>' +
        '</div>' +
        '<div class="hb-r-floor"><i style="width:80%"></i></div>' +
      '</div>';
    var nx = foot.querySelector('[data-go]');
    if (nx) nx.addEventListener('click', function (e) { e.stopPropagation(); if (onNav) onNav('batches'); });
  }

  // ---- 环节点击 ----
  var scope = document.querySelector('.rail') || f;
  scope.querySelectorAll('[data-node]').forEach(function (el) {
    el.addEventListener('click', function () {
      var nd = el.getAttribute('data-node');
      var sub = el.getAttribute('data-sub');
      state.node = nd;
      if (sub) state.sub[nd] = sub;
      render();
    });
    if (el.getAttribute('role') === 'button') {
      el.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); el.click(); }
      });
    }
  });
}

/* ---------------- table helper ---------------- */
function table(cols, rows) {
  var head = '<th class="cbx"><input type="checkbox" class="ck-all" aria-label="全选"></th>' +
    cols.map(function (c) { return '<th class="' + (c.r ? 'r' : '') + (c.act ? ' actcol' : '') + '"' + (c.w ? ' style="width:' + c.w + 'px"' : '') + '>' + c.t + '</th>'; }).join('');
  var body = rows.map(function (r) {
    return '<tr><td class="cbx"><input type="checkbox" class="ck-row"></td>' + r.map(function (cell, i) { return '<td class="' + (cols[i].r ? 'r' : '') + (cols[i].act ? ' actcol' : '') + '">' + cell + '</td>'; }).join('') + '</tr>';
  }).join('');
  return '<div class="card wb-table-frame"><div class="card-scroll wb-table-shell"><table class="tbl wb-table"><thead><tr>' + head + '</tr></thead><tbody>' + body + '</tbody></table></div></div>';
}
function actBtns(extra) { return '<div class="rowact"><button class="mini">' + (extra || '查看/编辑') + '</button><button class="mini danger">删除</button></div>'; }
function pager(total) {
  return '<div class="pager"><span>共 <b class="pgtotal" style="font-variant-numeric:tabular-nums">' + total + '</b> 条</span><span class="grow"></span>' +
    '<button class="pg">‹</button><span>第 1 / 1 页</span><button class="pg">›</button></div>';
}
function statline(items) {
  return '<div class="statline wb-metrics" style="--wb-columns:' + items.length + '">' + items.map(function (s) {
    var tone = s.tone === 'anchor' ? 'primary' : (s.tone || 'neutral');
    return '<div class="stat wb-metric ' + (s.tone || '') + '" data-tone="' + tone + '"><span class="sl wb-metric-label">' + s.l + '</span><span class="sv wb-metric-value">' + s.v + '</span></div>';
  }).join('') + '</div>';
}
function toolbar(ph, primary, icon, entity) {
  return '<div class="toolbar"><div class="search"><span class="ic">' + svg(icon || 'route').replace('width="18" height="18"', 'width="15" height="15"') + '</span>' +
    '<input placeholder="' + ph + '"></div><div class="tb-spacer"></div><div class="wb-actions">' +
    '<span class="selcount" hidden>已选 <b class="selN">0</b> 项</span>' +
    '<button class="linkbtn clear-sel" hidden>取消</button>' +
    '<button class="btn danger batch-del"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M5 7h14M10 7V5h4v2M7 7l1 13h8l1-13"/></svg>批量删除</button>' +
    '<span class="tb-div"></span>' +
    '<button class="btn io-btn io-imp wb-action wb-transfer" data-wb-transfer="import" data-entity="' + (entity || '') + '" data-mode="imp">' + window.APSWorkbenchUI.iconMarkup('import') + '导入</button>' +
    '<button class="btn io-btn io-exp wb-action wb-transfer" data-wb-transfer="export" data-entity="' + (entity || '') + '" data-mode="exp">' + window.APSWorkbenchUI.iconMarkup('export') + '导出</button>' +
    '<button class="btn primary add-btn wb-action wb-primary" data-entity="' + (entity || '') + '"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>' + primary + '</button></div></div>';
}

/* ---------------- datasets ---------------- */
var PARTS = [
  ['<a class="lnk">T-1008</a>', '回转壳体 A', '<span class="route" title="5数铣 10钳 20数车 30外协电镀 35外协发黑 40总检">5数铣 10钳 20数车 30外协电镀 35外协发黑 40总检</span>', '<span class="chipline"><span class="chip b">自制 5</span><span class="chip a">外协 2</span></span>', '<span class="pill ok"><span class="dot"></span>已解析</span>', actBtns()],
  ['<a class="lnk">T-1009</a>', '回转壳体 B', '<span class="route">5数铣 10钳 20数车 30精磨 40总检</span>', '<span class="chipline"><span class="chip b">自制 5</span></span>', '<span class="pill ok"><span class="dot"></span>已解析</span>', actBtns()],
  ['<a class="lnk">T-1011</a>', '端盖 C', '<span class="route">5数车 10钻孔 20外协热处理 25外协喷涂 30总检</span>', '<span class="chipline"><span class="chip b">自制 3</span><span class="chip a">外协 2</span></span>', '<span class="pill ok"><span class="dot"></span>已解析</span>', actBtns()],
  ['<a class="lnk">T-1014</a>', '法兰 D', '<span class="muted">—</span>', '<span class="muted" style="font-size:12px">待生成</span>', '<span class="pill warn"><span class="dot"></span>未解析</span>', actBtns()],
  ['<a class="lnk">T-1021</a>', '支座 E', '<span class="route">5数铣 10数车 20钻孔 30外协发黑 40总检 45表处理</span>', '<span class="chipline"><span class="chip b">自制 4</span><span class="chip a">外协 1</span></span>', '<span class="pill ok"><span class="dot"></span>已解析</span>', actBtns()],
];
var MATERIALS = [
  ['<a class="lnk">M-2001</a>', '45# 圆钢 Ø120', 'Ø120 × 2000', '1,240 kg', '<span class="pill ok"><span class="dot"></span>启用</span>', actBtns()],
  ['<a class="lnk">M-2008</a>', '6061 铝板 12mm', '1220 × 2440', '86 张', '<span class="pill ok"><span class="dot"></span>启用</span>', actBtns()],
  ['<a class="lnk">M-2015</a>', '40Cr 锻件毛坯', 'Ø200 锻坯', '32 件', '<span class="pill warn"><span class="dot"></span>低库存</span>', actBtns()],
  ['<a class="lnk">M-2031</a>', '不锈钢 304 棒', 'Ø60 × 3000', '410 kg', '<span class="pill ok"><span class="dot"></span>启用</span>', actBtns()],
  ['<a class="lnk">M-2044</a>', '紧固件套件 A', 'M8 / M10 混装', '2,300 套', '<span class="pill off"><span class="dot"></span>停用</span>', actBtns()],
];
var OP_INT = [
  ['<a class="lnk">OT001</a>', '数铣', '6', '14', '主力工序，设备充足', actBtns('查看绑定')],
  ['<a class="lnk">OT002</a>', '数车', '5', '11', '<span class="muted">—</span>', actBtns('查看绑定')],
  ['<a class="lnk">OT003</a>', '钳工', '3', '9', '瓶颈工序，人员偏紧', actBtns('查看绑定')],
  ['<a class="lnk">OT004</a>', '精磨', '2', '6', '关键工序', actBtns('查看绑定')],
  ['<a class="lnk">OT006</a>', '总检', '1', '4', '关键工序 · 必检', actBtns('查看绑定')],
];
var EQUIP = [
  ['<a class="lnk">EQ-01</a>', '立式加工中心 VMC-850', '<span class="chip b">数铣</span>', '设备组 A', '<span class="pill ok"><span class="dot"></span>可用</span>', actBtns()],
  ['<a class="lnk">EQ-04</a>', '数控车床 CK-6150', '<span class="chip b">数车</span>', '设备组 A', '<span class="pill ok"><span class="dot"></span>可用</span>', actBtns()],
  ['<a class="lnk">EQ-09</a>', '平面磨床 M7140', '<span class="chip b">精磨</span>', '设备组 B', '<span class="pill warn"><span class="dot"></span>检修</span>', actBtns()],
  ['<a class="lnk">EQ-12</a>', '钳工台 ·联合', '<span class="chip b">钳工</span>', '设备组 C', '<span class="pill ok"><span class="dot"></span>可用</span>', actBtns()],
];
var PEOPLE = [
  ['<a class="lnk">P-101</a>', '张伟', '<span class="chipline"><span class="chip b">数铣</span><span class="chip b">数车</span></span>', '白班', '<span class="pill ok"><span class="dot"></span>在岗</span>', actBtns()],
  ['<a class="lnk">P-118</a>', '李娜', '<span class="chipline"><span class="chip b">精磨</span><span class="chip b">总检</span></span>', '白班', '<span class="pill ok"><span class="dot"></span>在岗</span>', actBtns()],
  ['<a class="lnk">P-126</a>', '王强', '<span class="chipline"><span class="chip b">钳工</span></span>', '两班倒', '<span class="pill warn"><span class="dot"></span>请假</span>', actBtns()],
  ['<a class="lnk">P-133</a>', '赵敏', '<span class="chipline"><span class="chip b">数车</span><span class="chip b">钻孔</span><span class="chip b">钳工</span></span>', '白班', '<span class="pill ok"><span class="dot"></span>在岗</span>', actBtns()],
];
var OP_EXT = [
  ['<a class="lnk">OT051</a>', '电镀', '分别设置', '常用表面处理，多家供应商', actBtns('查看供应商')],
  ['<a class="lnk">OT052</a>', '发黑', '分别设置', '<span class="muted">—</span>', actBtns('查看供应商')],
  ['<a class="lnk">OT053</a>', '热处理', '合并设置', '需炉前确认整组周期', actBtns('查看供应商')],
  ['<a class="lnk">OT054</a>', '喷涂', '分别设置', '单一供应商', actBtns('查看供应商')],
];
var SUPPLIERS = [
  ['<a class="lnk">S-01</a>', '华表面处理', '<span class="chipline"><span class="chip a">电镀</span><span class="chip a">发黑</span></span>', '3 天', '<span class="pill ok"><span class="dot"></span>启用</span>', actBtns()],
  ['<a class="lnk">S-02</a>', '金鼎热处理', '<span class="chipline"><span class="chip a">热处理</span></span>', '4 天', '<span class="pill ok"><span class="dot"></span>启用</span>', actBtns()],
  ['<a class="lnk">S-05</a>', '宏达喷涂', '<span class="chipline"><span class="chip a">喷涂</span></span>', '2 天', '<span class="pill warn"><span class="dot"></span>待复核</span>', actBtns()],
  ['<a class="lnk">S-07</a>', '精工电镀', '<span class="chipline"><span class="chip a">电镀</span></span>', '3 天', '<span class="pill off"><span class="dot"></span>停用</span>', actBtns()],
];

/* ---------------- content views ---------------- */
function crumb(parts) {
  return '<div class="crumb">' + parts.map(function (p, i) {
    var last = i === parts.length - 1;
    return (i ? '<span class="sep">›</span>' : '') + '<span class="' + (last ? 'cur' : '') + '">' + p + '</span>';
  }).join('') + '</div>';
}
function chead(title, desc) { return '<div class="chead wb-page-heading"><div><h2>' + title + '</h2><p class="cdesc">' + desc + '</p></div></div>'; }
function subtabsFor(chainId) {
  var c = CHAINS[chainId];
  return '<div class="subtabs">' + c.subs.map(function (s) {
    var on = state.sub[chainId] === s.id;
    return '<button class="subtab' + (on ? ' on' : '') + '" data-chain="' + chainId + '" data-sub="' + s.id + '">' + s.name + ' <span class="cnt">' + s.n + '</span></button>';
  }).join('') + '</div>';
}

/* ---- 工艺 part detail · 工时录入（工序清单 换型/单件两列） ---- */
var PART_META = {
  'T-1008': { name: '回转壳体 A', parsed: true },
  'T-1009': { name: '回转壳体 B', parsed: true },
  'T-1011': { name: '端盖 C', parsed: true },
  'T-1014': { name: '法兰 D', parsed: false },
  'T-1021': { name: '支座 E', parsed: true },
};
var PART_OPS = {
  'T-1008': [
    { seq: 5,  op: '数铣', dev: 'M-03 加工中心',     src: 'int', setup: '30', unit: '11.8' },
    { seq: 10, op: '钳工', dev: '钳工台',            src: 'int', setup: '0',  unit: '' },
    { seq: 20, op: '数车', dev: 'CK-6150 数控车',    src: 'int', setup: '15', unit: '2.0' },
    { seq: 30, op: '电镀', dev: '华表面处理（外协）', src: 'ext', ext: '周期 3 天（外协链维护）' },
    { seq: 35, op: '发黑', dev: '华表面处理（外协）', src: 'ext', ext: '周期 2 天（外协链维护）' },
    { seq: 40, op: '总检', dev: '检测台',            src: 'int', setup: '0',  unit: '0', bad: true },
  ],
  'T-1009': [
    { seq: 5,  op: '数铣', dev: 'M-01 加工中心', src: 'int', setup: '30', unit: '9.4' },
    { seq: 10, op: '钳工', dev: '钳工台',        src: 'int', setup: '0',  unit: '1.2' },
    { seq: 20, op: '数车', dev: 'CK-6150',       src: 'int', setup: '15', unit: '2.4' },
    { seq: 30, op: '精磨', dev: 'M7140 平磨',    src: 'int', setup: '20', unit: '3.1' },
    { seq: 40, op: '总检', dev: '检测台',        src: 'int', setup: '0',  unit: '0.6' },
  ],
  'T-1011': [
    { seq: 5,  op: '数车',   dev: 'CK-6150',           src: 'int', setup: '15', unit: '1.8' },
    { seq: 10, op: '钻孔',   dev: 'Z-3050 摇臂钻',      src: 'int', setup: '10', unit: '' },
    { seq: 20, op: '热处理', dev: '金鼎热处理（外协）',  src: 'ext', ext: '整组周期 6 天（合并设置）' },
    { seq: 25, op: '喷涂',   dev: '外协 · 待定供应商',   src: 'ext', ext: '整组周期 6 天（合并设置）' },
    { seq: 30, op: '总检',   dev: '检测台',            src: 'int', setup: '0',  unit: '0.5' },
  ],
  'T-1021': [
    { seq: 5,  op: '数铣',   dev: 'M-03 加工中心',     src: 'int', setup: '30', unit: '8.0' },
    { seq: 10, op: '数车',   dev: 'CK-6150',          src: 'int', setup: '15', unit: '2.2' },
    { seq: 20, op: '钻孔',   dev: 'Z-3050 摇臂钻',     src: 'int', setup: '10', unit: '1.1' },
    { seq: 30, op: '发黑',   dev: '华表面处理（外协）', src: 'ext', ext: '周期 2 天（外协链维护）' },
    { seq: 40, op: '总检',   dev: '检测台',           src: 'int', setup: '0',  unit: '0.4' },
    { seq: 45, op: '表处理', dev: '表处理工位',        src: 'int', setup: '5',  unit: '0.9' },
  ],
};

var PART_CODES = ['T-1008', 'T-1009', 'T-1011', 'T-1014', 'T-1021'];
function partHoursSummary(code) {
  var meta = PART_META[code];
  var ops = PART_OPS[code] || [];
  var internal = ops.filter(function (o) { return o.src === 'int'; });
  if (!meta || !meta.parsed || !internal.length) return null;
  var filled = internal.filter(function (o) { return o.unit !== '' && Number(o.unit) !== 0; }).length;
  var missing = internal.filter(function (o) { return o.unit === ''; }).length;
  var bad = internal.filter(function (o) { return o.unit !== '' && Number(o.unit) === 0; }).length;
  var sumUnit = internal.reduce(function (a, o) { return a + (o.unit !== '' ? (Number(o.unit) || 0) : 0); }, 0);
  var sumSetup = internal.reduce(function (a, o) { return a + (o.setup !== '' ? (Number(o.setup) || 0) : 0); }, 0);
  return { total: internal.length, filled: filled, missing: missing, bad: bad, sumUnit: sumUnit, sumSetup: sumSetup };
}
function hoursCell(code) {
  var s = partHoursSummary(code);
  if (!s) return '<span class="muted">—</span>';
  var pill, todo;
  if (s.missing) { pill = '<span class="pill warn"><span class="dot"></span>缺 ' + s.missing + ' 项</span>'; todo = '去填 →'; }
  else if (s.bad) { pill = '<span class="pill danger"><span class="dot"></span>异常 ' + s.bad + '</span>'; todo = '复核 →'; }
  else { pill = '<span class="pill ok"><span class="dot"></span>已填 ' + s.filled + '/' + s.total + '</span>'; todo = '查看 →'; }
  return '<div class="wt-sum">' +
    '<div class="wt-sum-top">' + pill + '<a class="lnk wt-go">' + todo + '</a></div>' +
    '<div class="wt-sum-h">单件合计 <b>' + s.sumUnit.toFixed(1) + '</b> h · 换型 ' + s.sumSetup.toFixed(1) + ' h</div>' +
    '</div>';
}
function partRows() {
  return PARTS.map(function (r, i) {
    var row = r.slice();
    row.splice(5, 0, hoursCell(PART_CODES[i]));
    return row;
  });
}

/* ===== 工艺三步流程：阶段模型 + 列表管线 + 详情 stepper + 归属分拣 + 已就绪 ===== */
var CHK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>';
var LCK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>';
var ARR = '<span class="pp-arr"></span>';

/* 每个零件三步进度：route/attr/hours = done|pending|partial|locked|todo */
var PART_STAGE = {
  'T-1008': { route: 'done', attr: 'pending', hours: 'locked' },
  'T-1009': { route: 'done', attr: 'done',    hours: 'done' },
  'T-1011': { route: 'done', attr: 'done',    hours: 'partial' },
  'T-1014': { route: 'todo', attr: 'locked',  hours: 'locked' },
  'T-1021': { route: 'done', attr: 'done',    hours: 'done' },
};
function partStageOf(code) { return PART_STAGE[code] || { route: 'todo', attr: 'locked', hours: 'locked' }; }

/* ---- 工种库（识别用）+ 路线引入的「待归类·待建」工种 ---- */
var KNOWN_INT = ['数铣', '数车', '钳工', '精磨', '钻孔', '总检'];
var KNOWN_EXT = ['电镀', '发黑', '热处理', '喷涂'];
function classifyOp(name) {
  name = (name || '').trim();
  if (!name) return 'empty';
  if (KNOWN_INT.indexOf(name) >= 0) return 'int';
  if (KNOWN_EXT.indexOf(name) >= 0) return 'ext';
  return 'unknown';
}
/* 在路线里出现、但工种库还没有的工种：自制 / 外协未定，挂在两条链的「待归类」区 */
var PENDING_OPTYPES = [
  { name: '表处理', from: 'T-1014 法兰 D' },
  { name: '标印', from: 'T-1014 法兰 D' }
];
function pendingHas(name) { return PENDING_OPTYPES.some(function (p) { return p.name === name; }); }
function addPending(name, from) { if (!pendingHas(name) && classifyOp(name) === 'unknown') PENDING_OPTYPES.push({ name: name, from: from }); }

/* 整条文本 → 工序行：支持「5数铣 10钳 20数车」「5数铣10钳…」「换行 / 逗号分隔」等写法（模块级，新增零件与手工新建路线共用） */
function parseRouteText(text) {
  function clean(s) { return (s || '').replace(/^(外协|自制)/, '').trim(); }
  var out = [];
  if (!text) return out;
  var norm = text.replace(/[，,、;；\n\r\t]+/g, ' ').replace(/([^\d\s])(\d)/g, '$1 $2');
  var toks = norm.split(/\s+/).filter(Boolean);
  var autoSeq = 0, pendSeq = null;
  toks.forEach(function (t) {
    var dm = t.match(/^(\d+)(.*)$/);
    if (dm) {
      if (dm[2]) { out.push({ seq: dm[1], op: clean(dm[2]) }); pendSeq = null; }
      else { pendSeq = dm[1]; }
    } else {
      var op = clean(t);
      if (!op) return;
      if (pendSeq !== null) { out.push({ seq: pendSeq, op: op }); pendSeq = null; }
      else { autoSeq += 10; out.push({ seq: String(autoSeq), op: op }); }
    }
  });
  return out;
}

var UP_SVG = window.APSWorkbenchUI.iconMarkup('import');
var PEN_SVG = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20h4L18.5 9.5a2 2 0 0 0-3-3L5 17v3z"/><path d="M13.5 6.5l3 3"/></svg>';

/* 归属分拣的逐工序建议（自动只"建议"，人确认才作数） */
var PART_SORT = {
  'T-1008': [
    { seq: 5,  op: '数铣', sug: 'int', conf: 'hi', basis: '命中 <b>"数铣"→自制</b> · 与本图号历史一致' },
    { seq: 10, op: '钳工', sug: 'int', conf: 'hi', basis: '命中 <b>"钳工"→自制</b> · 与本图号历史一致' },
    { seq: 20, op: '数车', sug: 'int', conf: 'hi', basis: '命中 <b>"数车"→自制</b> · 与本图号历史一致' },
    { seq: 40, op: '总检', sug: 'int', conf: 'hi', basis: '命中 <b>"总检"→自制</b> · 与本图号历史一致' },
    { seq: 30, op: '电镀', sug: 'ext', conf: 'lo', basis: '命中关键词 <b>"电镀"→外协</b>，但本厂 2025 年曾自制过此序 · 与历史冲突', attn: true },
    { seq: 35, op: '发黑', sug: null,  conf: 'none', basis: '<b>无规则命中</b>："发黑"不在规则库 → 不替你猜，请人工指定', attn: 'bad' },
  ],
};
function deriveSort(code) {
  return (PART_OPS[code] || []).map(function (o) {
    return { seq: o.seq, op: o.op, sug: o.src, conf: 'hi', basis: '命中 <b>"' + o.op + '"→' + (o.src === 'int' ? '自制' : '外协') + '</b> · 与本图号历史一致' };
  });
}
function sortList(code) { return PART_SORT[code] || deriveSort(code); }

function hoursStateAfter(code) {
  var s = partHoursSummary(code);
  if (!s) return 'done';
  return (s.missing || s.bad) ? 'partial' : 'done';
}
function stageBucket(code) {
  var s = partStageOf(code);
  if (s.route !== 'done') return 'route';
  if (s.attr !== 'done') return 'sort';
  if (s.hours !== 'done') return 'hours';
  return 'ready';
}
function effStage(code) {
  if (state.openStage) return state.openStage;
  var b = stageBucket(code);
  return b === 'sort' ? 'attr' : b;
}

/* 列表行内三段管线 */
function pp(label, st) {
  var ico = st === 'done' ? CHK : (st === 'lock' ? LCK : '');
  return '<span class="pp ' + st + '">' + ico + label + '</span>';
}
function pipelineCell(code) {
  var s = partStageOf(code);
  var r = s.route === 'done' ? pp('路线', 'done') : pp('路线 · 待导入', 'warn');
  var a;
  if (s.route !== 'done') a = pp('归属', 'todo');
  else if (s.attr === 'done') a = pp('归属', 'done');
  else {
    var sl = sortList(code);
    var attnN = sl.filter(function (o) { return o.attn; }).length;
    a = pp('归属 · 待分拣 ' + attnN + ' / 共 ' + sl.length, 'warn');
  }
  var h;
  if (s.hours === 'locked' || s.attr !== 'done') h = pp('工时', 'lock');
  else if (s.hours === 'done') h = pp('工时', 'done');
  else { var sum = partHoursSummary(code); var miss = sum ? (sum.missing + sum.bad) : 0; var tot = sum ? sum.total : 0; h = pp('工时 · 缺 ' + miss + ' / 共 ' + tot, 'warn'); }
  return '<div class="pipe">' + r + ARR + a + ARR + h + '</div>';
}
function nextActionCell(code) {
  var b = stageBucket(code);
  if (b === 'route') return '<button class="lnk pl-route-menu" data-code="' + code + '">录入路线 ▾</button>';
  if (b === 'sort')  return '<a class="lnk pl-act">去分拣 →</a>';
  if (b === 'hours') return '<a class="lnk pl-act">填工时 →</a>';
  return '<span class="muted" style="font-size:12.5px">已就绪</span>';
}

/* 详情 stepper */
function stepperHtml(code, eff) {
  var s = partStageOf(code);
  var routeC = s.route === 'done' ? 'done' : 'active';
  var attrC  = s.route !== 'done' ? 'lock' : (s.attr === 'done' ? 'done' : 'active');
  var hoursC = s.attr !== 'done' ? 'lock' : (s.hours === 'done' ? 'done' : 'active');
  if (eff === 'route') routeC = 'active';
  if (eff === 'attr')  attrC = 'active';
  if (eff === 'hours') hoursC = 'active';
  var ops = (PART_OPS[code] || []);
  var intN = ops.filter(function (o) { return o.src === 'int'; }).length;
  var extN = ops.filter(function (o) { return o.src === 'ext'; }).length;
  var sum = partHoursSummary(code);
  var routeSub = s.route === 'done' ? ('已导入 · ' + ops.length + ' 道工序') : '待导入路线';
  var attrSub  = s.route !== 'done' ? '待路线完成' : (s.attr === 'done' ? ('自制 ' + intN + ' · 外协 ' + extN + ' · 已确认') : '进行中 · 待分拣');
  var hoursSub = s.attr !== 'done' ? '待归属确认后解锁' : (s.hours === 'done' ? (intN + ' 道自制序全填') : ('缺 ' + (sum ? (sum.missing + sum.bad) : 0) + ' 项'));
  function node(c, num, title, sub, reopen) {
    var ico = c === 'done' ? CHK : (c === 'lock' ? LCK : num);
    var edit = (c === 'done' && reopen) ? '<span class="stp-edit" data-reopen="' + reopen + '">重新打开</span>' : '';
    return '<div class="stp ' + c + '"><div class="stp-n">' + ico + '</div><div class="stp-b"><span class="stp-t">' + title + edit + '</span><span class="stp-s">' + sub + '</span></div></div>';
  }
  return '<div class="stepper">' +
    node(routeC, '1', '① 工艺路线', routeSub, null) +
    node(attrC,  '2', '② 工序归属', attrSub, 'attr') +
    node(hoursC, '3', '③ 工时定额', hoursSub, 'hours') +
    '</div>';
}

var GATE_NOTE = '<div class="gate-note">' + LCK + '<span><b>闸门：</b>③ 工时定额在本页「待确认 / 待定」清零前保持锁定。归属判错 = 整道工序走错链（自制漏排产能、外协空等填工时），所以必须人工确认才放行。</span></div>';

function sortRowHtml(o, preStaged) {
  var attnCls = preStaged ? ' staged' : (o.attn === 'bad' ? ' attn-bad' : (o.attn ? ' attn' : ''));
  var seg = '<span class="segm"><button data-attr="int"' + (o.sug === 'int' ? ' class="on int"' : '') + '>自制</button><button data-attr="ext"' + (o.sug === 'ext' ? ' class="on ext"' : '') + '>外协</button></span>';
  var sug = o.sug ? '<span class="sug">建议</span>' : '';
  var conf = o.conf === 'hi' ? '<div class="conf hi" style="margin-top:5px">置信高</div>'
    : (o.conf === 'lo' ? '<div class="conf lo" style="margin-top:5px">置信中 · 请复核</div>'
      : '<div class="conf none" style="margin-top:5px">无建议 · 需人工</div>');
  var pill = preStaged ? '<span class="pill info"><span class="dot"></span>建议 · 已采纳</span>'
    : (o.attn === 'bad' ? '<span class="pill danger"><span class="dot"></span>待定 · 需人工</span>' : '<span class="pill warn"><span class="dot"></span>待确认</span>');
  return '<tr class="sort-row' + attnCls + '" data-conf="' + o.conf + '">' +
    '<td class="num"><b>' + o.seq + '</b> ' + o.op + '</td>' +
    '<td>' + o.op + '</td>' +
    '<td><div class="attr-cell">' + seg + sug + '</div></td>' +
    '<td><div class="basis">' + o.basis + '</div>' + conf + '</td>' +
    '<td><span class="attr-status">' + pill + '</span></td></tr>';
}
function sortBody(code) {
  var list = sortList(code);
  var attn = list.filter(function (o) { return o.attn; });
  var hi = list.filter(function (o) { return !o.attn; });
  var total = list.length;
  var rows = attn.map(function (o) { return sortRowHtml(o, false); }).join('');
  if (hi.length) rows += '<tr class="grp-row"><td colspan="5">高置信 · ' + hi.length + ' 道工序已默认采纳（关键词明确命中，且与本图号历史一致）· 可点行内按钮改动</td></tr>' + hi.map(function (o) { return sortRowHtml(o, true); }).join('');
  return GATE_NOTE +
    '<div class="statline wb-metrics" style="--wb-columns:3">' +
      '<div class="stat anchor wb-metric" data-tone="primary"><span class="sl wb-metric-label">工序</span><span class="sv wb-metric-value">' + total + '</span></div>' +
      '<div class="stat ok wb-metric" data-tone="ok"><span class="sl wb-metric-label">已选定</span><span class="sv sort-confirmed wb-metric-value">' + hi.length + '</span></div>' +
      '<div class="stat warn wb-metric" data-tone="warn"><span class="sl wb-metric-label">待办</span><span class="sv sort-todo wb-metric-value">' + (total - hi.length) + '</span></div>' +
    '</div>' +
    '<div class="toolbar"><div class="search"><span class="ic">' + svg('route').replace('width="18" height="18"', 'width="15" height="15"') + '</span>' +
      '<input placeholder="搜索工序、工种…"></div><div class="tb-spacer"></div></div>' +
    '<div class="card wb-table-frame"><div class="card-scroll wb-table-shell"><table class="tbl wb-table" style="min-width:1020px;table-layout:auto"><thead><tr>' +
      '<th style="width:150px">工序</th><th style="width:96px">工种</th><th style="width:200px">归属 <small style="font-weight:500;color:var(--ui-muted)">建议 → 确认</small></th><th>判断依据 / 置信</th><th style="width:118px">状态</th>' +
      '</tr></thead><tbody>' + rows + '</tbody></table></div></div>' +
    '<div class="pd-foot sticky"><div class="muted">确认后写入工序归属并留痕（确认人 / 时间 / 依据）。下次重导路线时，<b>已人工确认的不被自动判断覆盖</b>。</div>' +
      '<button class="btn primary sort-finish"' + (total - hi.length > 0 ? ' disabled' : '') + '>' + (total - hi.length > 0 ? ('完成归属 · 解锁工时（还剩 ' + (total - hi.length) + '）') : ('完成归属 · 解锁工时（' + total + ' 道）')) + '</button></div>';
}

function readyBody(code) {
  var ops = PART_OPS[code] || [];
  var sum = partHoursSummary(code) || { sumUnit: 0, sumSetup: 0 };
  var rows = ops.map(function (o) {
    var attr = o.src === 'ext' ? '<span class="chip a">外协</span>' : '<span class="chip b">自制</span>';
    if (o.src === 'ext') return '<tr><td class="num"><b>' + o.seq + '</b> ' + o.op + '</td><td>' + o.op + '</td><td class="muted">' + o.dev + '</td><td>' + attr + '</td><td class="r wt-col" colspan="2" style="text-align:center"><span class="muted" style="font-size:12px">外协工序无工时 · ' + o.ext + '</span></td></tr>';
    var unitCell = '<span class="wt-val">' + o.unit + '</span>';
    return '<tr><td class="num"><b>' + o.seq + '</b> ' + o.op + '</td><td>' + o.op + '</td><td class="muted">' + o.dev + '</td><td>' + attr + '</td><td class="r wt-col"><span class="wt-val">' + o.setup + '</span></td><td class="r wt-col">' + unitCell + '</td></tr>';
  }).join('');
  var intN = ops.filter(function (o) { return o.src === 'int'; }).length;
  var extN = ops.filter(function (o) { return o.src === 'ext'; }).length;
  return '<div class="ready-note"><div class="rn-ico">' + CHK + '</div><div><div class="rn-t">已就绪 · 可参与排产</div><div class="rn-s">路线 / 归属 / 工时三项齐备，本零件已纳入下次执行排产的可调度池。</div></div><div class="rn-act"><button class="btn ready-export wb-action wb-transfer" data-wb-transfer="export">' + window.APSWorkbenchUI.iconMarkup('export') + '导出工序清单</button></div></div>' +
    '<div class="card wb-table-frame"><div class="card-scroll wb-table-shell"><table class="tbl op-tbl wb-table" style="min-width:720px;table-layout:auto"><thead><tr><th style="width:120px">工序</th><th style="width:90px">工种</th><th>设备 / 资源</th><th style="width:84px">归属</th><th class="r wt-col" style="width:124px">换型工时<small>定额·h</small></th><th class="r wt-col" style="width:124px">单件工时<small>定额·h</small></th></tr></thead><tbody>' + rows + '</tbody></table></div></div>' +
    '<div class="pd-foot"><div class="wt-sum"><div class="wt-sum-top"><span class="muted" style="font-size:12.5px">汇总</span></div><div class="wt-sum-h">自制 <b>' + intN + '</b> 序 · 外协 <b>' + extN + '</b> 序 · 换型合计 <b>' + sum.sumSetup.toFixed(1) + ' h</b> · 单件合计 <b>' + sum.sumUnit.toFixed(1) + ' h</b></div></div><button class="btn ready-edit">编辑（重新打开某步）</button></div>';
}

var IMPORT_PROMPT = '<div class="card" style="padding:34px;text-align:center"><div class="muted" style="margin-bottom:16px;line-height:1.7">该零件还没有工艺路线。可<b>导入</b>工艺室给的路线，也可<b>手工逐行新建</b>；完成后再进行<b>工序归属</b>与<b>工时定额</b>两步。</div><div style="display:flex;gap:10px;justify-content:center"><button class="btn primary pd-manual-route wb-action wb-primary">' + PEN_SVG + '手工新建路线</button><button class="btn pd-import-route wb-action wb-transfer" data-wb-transfer="import">' + UP_SVG + '导入工艺路线</button></div></div>';

function hoursBody(code) {
  var ops = PART_OPS[code] || [];
  var focus = false;
  var internal = ops.filter(function (o) { return o.src === 'int'; });
  var filled = internal.filter(function (o) { return o.unit !== '' && Number(o.unit) !== 0; }).length;
  var missing = internal.filter(function (o) { return o.unit === ''; }).length;
  var bad = internal.filter(function (o) { return o.unit !== '' && Number(o.unit) === 0; }).length;
  var rows = ops.map(function (o) { return opRow(o, focus); }).join('');
  var minw = focus ? 640 : 880;
  return statline([
      { v: ops.length, l: '工序', tone: 'anchor' },
      { v: filled, l: '已填', tone: 'ok' },
      { v: missing, l: '缺工时', tone: 'warn' },
      { v: bad, l: '异常', tone: 'danger' }
    ]) +
    '<div class="toolbar"><div class="search"><span class="ic">' + svg('route').replace('width="18" height="18"', 'width="15" height="15"') + '</span>' +
      '<input placeholder="搜索工序、工种…"></div><div class="tb-spacer"></div><div class="wb-actions">' + impButtons(true) + '</div></div>' +
    '<div class="match-note">⚠ 上次工时导入：匹配 <b>312 / 320</b> · <b>8 条未匹配</b>（图号 + 工序在路线中不存在）<a class="lnk" style="margin-left:auto">查看未匹配 →</a></div>' +
    '<div class="card wb-table-frame"><div class="card-scroll wb-table-shell"><table class="tbl op-tbl wb-table" style="min-width:' + minw + 'px;table-layout:auto"><thead><tr>' + opTableHead(focus) + '</tr></thead><tbody>' + rows + '</tbody></table></div></div>' +
    '<div class="pd-foot"><span class="muted">填好换型 / 单件工时后点保存；外协工序无需填写，缺工时或单件为 0 会标黄 / 标红提示。</span><button class="btn primary pd-save"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l4 4 10-10"/></svg>保存工时</button></div>' +
    '<div class="pager"><span class="grow"></span><span class="muted">' + code + ' · 共 ' + ops.length + ' 道工序</span></div>';
}

function headDescFor(stage) {
  if (stage === 'route') return '导入工艺路线后，按 <b>① 路线 → ② 归属 → ③ 工时</b> 三步推进。';
  if (stage === 'attr') return '逐道工序确认走 <b class="bi">自制</b> 还是 <b class="be">外协</b>。系统按工序名给<b>建议</b>，确认才作数；外协工序不进工时、走周期。';
  if (stage === 'hours') return '右侧两列填 <b class="be">定额室</b> 的换型 / 单件工时；外协工序无需填写。';
  return '三步齐备的只读汇总，可参与排产。任一步需修改点 stepper 上「重新打开」。';
}

function processListToolbar() {
  return '<div class="toolbar"><div class="search"><span class="ic">' + svg('route').replace('width="18" height="18"', 'width="15" height="15"') + '</span>' +
    '<input placeholder="搜索图号、名称、路线…"></div><div class="tb-spacer"></div><div class="wb-actions">' + impButtons(false) +
    '<span class="tb-div"></span>' + expButtons() +
    '<button class="btn primary add-btn wb-action wb-primary" data-entity="part"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>新增零件</button></div></div>';
}
function statlineProcess(counts) {
  return '<div class="statline wb-metrics" style="--wb-columns:4">' +
    '<div class="stat anchor wb-metric" data-tone="primary"><span class="sl wb-metric-label">零件总数</span><span class="sv wb-metric-value">' + PART_CODES.length + '</span></div>' +
    '<div class="stat warn wb-metric" data-tone="warn"><span class="sl wb-metric-label">待分拣</span><span class="sv wb-metric-value">' + counts.sort + '</span></div>' +
    '<div class="stat warn wb-metric" data-tone="warn"><span class="sl wb-metric-label">待填工时</span><span class="sv wb-metric-value">' + counts.hours + '</span></div>' +
    '<div class="stat ok wb-metric" data-tone="ok"><span class="sl wb-metric-label">已就绪</span><span class="sv wb-metric-value">' + counts.ready + '</span></div>' +
    '</div>';
}

function impButtons(primaryHours) {  var up = window.APSWorkbenchUI.iconMarkup('import');
  return '<button class="btn imp-route wb-action wb-transfer" data-wb-transfer="import">' + up + '导入工艺路线</button>' +
    '<button class="btn wb-action wb-transfer ' + (primaryHours ? 'primary wb-primary ' : '') + 'imp-hours" data-wb-transfer="import">' + up + '导入工时定额</button>';
}

function expButtons() {  var dn = window.APSWorkbenchUI.iconMarkup('export');
  return '<button class="btn io-btn io-exp wb-action wb-transfer" data-wb-transfer="export" data-entity="route" data-mode="exp">' + dn + '导出工艺路线</button>' +
    '<button class="btn io-btn io-exp wb-action wb-transfer" data-wb-transfer="export" data-entity="hours" data-mode="exp">' + dn + '导出工时定额</button>';
}

function processToolbar() {
  return '<div class="toolbar"><div class="search"><span class="ic">' + svg('route').replace('width="18" height="18"', 'width="15" height="15"') + '</span>' +
    '<input placeholder="搜索图号、名称、路线…"></div><div class="tb-spacer"></div><div class="wb-actions">' +
    '<span class="selcount" hidden>已选 <b class="selN">0</b> 项</span>' +
    '<button class="linkbtn clear-sel" hidden>取消</button>' +
    '<button class="btn danger batch-del"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M5 7h14M10 7V5h4v2M7 7l1 13h8l1-13"/></svg>批量删除</button>' +
    '<span class="tb-div"></span>' + impButtons(false) +
    '<button class="btn primary add-btn wb-action wb-primary" data-entity="part"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>新增零件</button></div></div>';
}

function opTableHead(focus) {
  if (focus) return '<th style="width:120px">工序</th><th style="width:90px">工种</th>' +
    '<th class="wt-col" style="width:150px">换型工时<small>定额·h</small></th>' +
    '<th class="wt-col">单件工时<small>定额·h</small></th>';
  return '<th style="width:120px">工序</th><th style="width:90px">工种</th>' +
    '<th>设备 / 资源</th><th style="width:84px">归属</th>' +
    '<th class="wt-col" style="width:140px">换型工时<small>定额·h</small></th>' +
    '<th class="wt-col" style="width:190px">单件工时<small>定额·h</small></th>';
}
function opRow(o, focus) {
  var seqCell = '<td class="num"><b>' + o.seq + '</b> ' + o.op + '</td><td>' + o.op + '</td>';
  if (o.src === 'ext') {
    var lead = seqCell + (focus ? '' : '<td class="muted">' + o.dev + '</td><td><span class="chip a">外协</span></td>');
    return '<tr>' + lead + '<td class="wt-col" colspan="2" style="text-align:center"><span class="muted" style="font-size:12px">外协工序无工时 · ' + o.ext + '</span></td></tr>';
  }
  var mid = focus ? '' : '<td class="muted">' + o.dev + '</td><td><span class="chip b">自制</span></td>';
  var isEmpty = o.unit === '';
  var isBad = !isEmpty && Number(o.unit) === 0;
  var setup = '<td class="wt-col"><input class="wt-in" data-seq="' + o.seq + '" data-field="setup" value="' + o.setup + '"></td>';
  var unitCls = isBad ? 'wt-in bad' : (isEmpty ? 'wt-in empty' : 'wt-in');
  var marker = isBad ? '<span class="prov bad-note">单件为 0 · 请复核</span>' : '';
  var unit = '<td class="wt-col"><div class="wt-cell">' + marker + '<input class="' + unitCls + '" data-seq="' + o.seq + '" data-field="unit" value="' + o.unit + '"' + (isEmpty ? ' placeholder="待填"' : '') + '></div></td>';
  return '<tr>' + seqCell + mid + setup + unit + '</tr>';
}

function viewPartDetail(code) {
  var meta = PART_META[code] || { name: code, parsed: false };
  var stage = effStage(code);
  var crumbLast = stage === 'attr' ? '工序归属' : (stage === 'hours' ? '工时' : (stage === 'ready' ? '汇总' : '路线'));
  var head =
    '<button class="linkbtn pd-back" style="margin-bottom:10px">← 返回零件列表</button>' +
    crumb(['产能链', '输入', '工艺', code, crumbLast]) +
    '<div class="chead wb-page-heading"><div><h2>' + code + ' ' + meta.name + '</h2><p class="cdesc">' + headDescFor(stage) + '</p></div></div>' +
    stepperHtml(code, stage);
  var body;
  if (stage === 'route') body = IMPORT_PROMPT;
  else if (stage === 'attr') body = sortBody(code);
  else if (stage === 'hours') body = hoursBody(code);
  else body = readyBody(code);
  return head + body;
}

function partBodyFor(code, stage) {
  if (stage === 'route') return IMPORT_PROMPT;
  if (stage === 'attr') return sortBody(code);
  if (stage === 'hours') return hoursBody(code);
  return readyBody(code);
}

/* 零件工艺详情 · 弹出卡片（替代整页下钻） */
function openPartModal(code) {
  state.openPart = code;
  state.opView = 'full';
  state.openStage = null;
  var bg = document.createElement('div');
  bg.className = 'modal-bg';
  function close() {
    if (bg.parentNode) bg.parentNode.removeChild(bg);
    document.removeEventListener('keydown', onKey);
    partModal = null;
    state.openPart = null;
    state.openStage = null;
  }
  function onKey(e) { if (e.key === 'Escape') close(); }
  bg.addEventListener('click', function (e) { if (e.target === bg) close(); });
  function repaint() {
    var meta = PART_META[code] || { name: code };
    var stage = effStage(code);
    bg.innerHTML = '<div class="modal xl pd-modal" role="dialog" aria-modal="true">' +
      modalHead('route', code + ' ' + (meta.name || ''), headDescFor(stage)) +
      '<div class="modal-b scroll pd-modal-b">' +
        stepperHtml(code, stage) +
        partBodyFor(code, stage) +
      '</div></div>';
    bg.querySelectorAll('[data-close]').forEach(function (b) { b.addEventListener('click', close); });
    var modalEl = bg.querySelector('.pd-modal');
    wirePartModal(code, modalEl, stage);
  }
  partModal = { code: code, repaint: repaint, close: close };
  document.addEventListener('keydown', onKey);
  repaint();
  root.appendChild(bg);
}

function wirePartModal(code, scope, stage) {
  scope.querySelectorAll('.stp-edit[data-reopen]').forEach(function (e) {
    e.addEventListener('click', function () { state.openStage = e.getAttribute('data-reopen'); render(); });
  });
  if (stage === 'route') {
    var pir = scope.querySelector('.pd-import-route');
    if (pir) pir.addEventListener('click', function () { showImportExport('route', 'imp'); });
    var pmr = scope.querySelector('.pd-manual-route');
    if (pmr) pmr.addEventListener('click', function () { showRouteEntry(code); });
  } else if (stage === 'attr') {
    wireSort(code, scope);
  } else if (stage === 'hours') {
    wireHours(code, scope);
  } else {
    var re = scope.querySelector('.ready-edit');
    if (re) re.addEventListener('click', function () { state.openStage = 'attr'; render(); });
    var rx = scope.querySelector('.ready-export');
    if (rx) rx.addEventListener('click', function () { showFlash('已导出 ' + code + ' 工序清单（示例）。'); });
  }
}

function viewProcess() {
  var filter = state.stageFilter || 'all';
  var counts = { route: 0, sort: 0, hours: 0, ready: 0 };
  PART_CODES.forEach(function (c) { counts[stageBucket(c)]++; });
  var tabs = [
    { id: 'all', label: '全部', n: PART_CODES.length },
    { id: 'route', label: '待导入路线', n: counts.route },
    { id: 'sort', label: '待分拣', n: counts.sort },
    { id: 'hours', label: '待填工时', n: counts.hours },
    { id: 'ready', label: '已就绪', n: counts.ready }
  ];
  var subtabs = '<div class="subtabs">' + tabs.map(function (t) { return '<button class="subtab' + (filter === t.id ? ' on' : '') + '" data-stage="' + t.id + '">' + t.label + ' <span class="cnt">' + t.n + '</span></button>'; }).join('') + '</div>';
  var visible = PART_CODES.filter(function (c) { return filter === 'all' || stageBucket(c) === filter; });
  var rows = visible.map(function (c) {
    var meta = PART_META[c] || { name: c };
    var ops = (PART_OPS[c] || []).length;
    var opsCell = ops ? '<span class="num">' + ops + '</span>' : '<span class="muted">—</span>';
    return '<tr data-code="' + c + '"><td><a class="lnk">' + c + '</a> <span class="pl-name">' + (meta.name || '') + '</span></td><td class="r">' + opsCell + '</td><td>' + pipelineCell(c) + '</td><td>' + nextActionCell(c) + '</td></tr>';
  }).join('');
  if (!rows) rows = '<tr><td colspan="4" style="text-align:center;padding:28px" class="muted">该阶段暂无零件。</td></tr>';
  var tableHtml = '<div class="card wb-table-frame"><div class="card-scroll wb-table-shell"><table class="tbl wb-table" style="min-width:920px;table-layout:auto"><thead><tr><th style="width:230px">图号 / 零件</th><th class="r" style="width:70px">工序数量</th><th>进度</th><th style="width:130px">下一步</th></tr></thead><tbody>' + rows + '</tbody></table></div></div>';
  return crumb(['产能链', '输入', '工艺']) +
    chead('零件工艺', '每个零件按 <b>① 导入路线 → ② 工序归属（自制 / 外协）→ ③ 工时定额</b> 三步推进；后一步在前一步完成前锁定。工序归属由系统按工序名给<b>建议</b>，需人工确认才放行。') +
    statlineProcess(counts) +
    (PENDING_OPTYPES.length ? '<div class="match-note">⚠ 本批路线有 <b>' + PENDING_OPTYPES.length + '</b> 个工种未识别，已登记到工种库「待归类 · 待建」<a class="lnk go-pending" style="margin-left:auto">去工种库 →</a></div>' : '') +
    subtabs +
    processListToolbar() +
    tableHtml +
    pager(PART_CODES.length);
}
function viewMaterial() {
  return crumb(['产能链', '输入', '物料']) +
    chead('物料 · 物料主数据', '维护物料编号、规格、库存与状态；批次物料需求在「批次管理」里按批引用这里的主数据。') +
    statline([
      { v: 86, l: '物料主数据', tone: 'anchor' },
      { v: 78, l: '启用', tone: 'ok' },
      { v: 5, l: '低库存', tone: 'warn' },
      { v: 3, l: '停用' }
    ]) +
    toolbar('搜索物料编号、名称…', '新增物料', 'cube', 'material') +
    table([{ t: '物料编号', w: 120 }, { t: '名称', w: 180 }, { t: '规格' }, { t: '库存', w: 120, r: true }, { t: '状态', w: 110 }, { t: '操作', w: 190, act: true }], MATERIALS) +
    pager(86);
}
function viewCalendar() {
  var s = calStats();
  return crumb(['产能链', '全局', '工作日历']) +
    chead('工作日历', '设置排产用的工作时间、效率与可排产优先级；未配置的日期按默认规则处理，可在此配置调休或加班。') +
    statline([
      { v: s.workDays, l: '本月工作日', tone: 'anchor' },
      { v: s.configured, l: '已配工时', tone: 'ok' },
      { v: s.overrides, l: '调休 / 加班', tone: 'warn' },
      { v: s.weekendRest, l: '周末休息' }
    ]) +
    '<div style="margin-top:18px" class="cal-wrap">' +
      '<div class="cal-panel">' +
        '<div class="cal-top"><button class="cal-nav" data-dir="-1" aria-label="上一月">‹</button><span class="cal-title">' + calState.y + ' 年 ' + (calState.m + 1) + ' 月</span><button class="cal-nav" data-dir="1" aria-label="下一月">›</button><button class="cal-nav cal-today-btn" title="回到本月" style="width:auto;padding:0 10px;font-size:12px;font-weight:600">今天</button><span class="tb-spacer" style="flex:1"></span><button class="btn cal-batch">批量维护</button></div>' +
        calGrid() +
      '</div>' +
      '<div class="cal-panel cal-side">' +
        '<h3>图例</h3>' +
        '<div class="cal-leg">' +
          '<div><span class="sw cfg"></span> 已配置工时</div>' +
          '<div><span class="sw rest"></span> 调休 / 加班</div>' +
          '<div><span class="sw we"></span> 周末（默认非工作）</div>' +
        '</div>' +
        '<h3>默认规则</h3>' +
        '<p>未单独配置的日期：工作日按 8 小时、效率 100% 排产，普通件 / 急件都允许；周末默认不排产。点任一日期可单独覆盖工时、效率，或单独关掉普通件 / 急件（如只留急件加班）。</p>' +
      '</div>' +
    '</div>';
}
function calGrid() {
  var wd = ['一', '二', '三', '四', '五', '六', '日'];
  var html = '<div class="cal-grid">' + wd.map(function (d) { return '<div class="cal-wd">' + d + '</div>'; }).join('');
  var first = new Date(calState.y, calState.m, 1).getDay();   // 0=Sun
  var lead = (first + 6) % 7;                                  // Monday-first offset
  var dim = new Date(calState.y, calState.m + 1, 0).getDate();
  var now = new Date();
  for (var i = 0; i < lead; i++) html += '<div class="cal-cell empty"></div>';
  for (var d = 1; d <= dim; d++) {
    var meta = calDayMeta(d);
    var cls = 'cal-cell' + (meta.cls ? ' ' + meta.cls : '');
    if (now.getFullYear() === calState.y && now.getMonth() === calState.m && now.getDate() === d) cls += ' today';
    html += '<div class="' + cls + '" data-d="' + d + '" role="button" tabindex="0"><span class="d">' + d + '</span><span class="tag">' + meta.tag + '</span></div>';
  }
  return html + '</div>';
}
/* ---------------- calendar interactions ---------------- */
function wireCalendar() {
  var root = document.getElementById('content');
  root.querySelectorAll('.cal-nav[data-dir]').forEach(function (b) {
    b.addEventListener('click', function () {
      calState.m += parseInt(b.getAttribute('data-dir'), 10);
      if (calState.m < 0) { calState.m = 11; calState.y--; }
      else if (calState.m > 11) { calState.m = 0; calState.y++; }
      renderContent();
    });
  });
  var todayBtn = root.querySelector('.cal-today-btn');
  if (todayBtn) todayBtn.addEventListener('click', function () {
    var n = new Date(); calState.y = n.getFullYear(); calState.m = n.getMonth(); renderContent();
  });
  root.querySelectorAll('.cal-cell[data-d]').forEach(function (cell) {
    var open = function () { openDayModal(parseInt(cell.getAttribute('data-d'), 10)); };
    cell.addEventListener('click', open);
    cell.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); } });
  });
  var batch = root.querySelector('.cal-batch');
  if (batch) batch.addEventListener('click', showCalBatchModal);
}
function openDayModal(d) {
  var dow = new Date(calState.y, calState.m, d).getDay();
  var weekend = dow === 0 || dow === 6;
  var wdZh = ['日', '一', '二', '三', '四', '五', '六'][dow];
  var rec = calState.cfg[calKey(d)];
  var type = rec ? rec.type : (weekend ? 'rest' : 'work');
  var typeLabel = type === 'work' ? '工作日' : '休息日';
  var hours = rec && rec.hours != null ? rec.hours : 8;
  var eff = rec && rec.eff != null ? rec.eff : 100;
  var allowNormal = rec && rec.allowNormal === 'no' ? '否' : '是';
  var allowUrgent = rec && rec.allowUrgent === 'no' ? '否' : '是';
  var note = (rec && rec.note) || '';
  var seg = function (name, val, opts) {
    return '<div class="seg" data-seg="' + name + '">' + opts.map(function (o) {
      return '<button type="button" class="' + (o === val ? 'on' : '') + '" data-v="' + o + '">' + o + '</button>';
    }).join('') + '</div>';
  };
  var m = openModal('<div class="modal lg" role="dialog" aria-modal="true">' +
    modalHead('calendar', calState.m + 1 + ' 月 ' + d + ' 日 · 周' + wdZh, '设置这一天的工作时间、效率与可排产范围' + (weekend ? ' · 默认周末不排产' : '')) +
    '<div class="modal-b form">' +
      '<div class="field full"><label>这一天是否排产</label>' + seg('type', typeLabel, ['工作日', '休息日']) +
        '<span class="fhint">休息日不参与排产；工作日按下方工时与效率计算可用产能。</span></div>' +
      '<div class="fgrid cal-work-fields">' +
        '<div class="field"><label>可排工时（小时）</label><input class="cal-hours" type="number" min="0" max="24" step="0.5" value="' + hours + '"></div>' +
        '<div class="field"><label>效率（%）</label><input class="cal-eff" type="number" min="0" max="200" step="5" value="' + eff + '"></div>' +
        '<div class="field"><label>允许普通件排产</label>' + seg('allowNormal', allowNormal, ['是', '否']) + '</div>' +
        '<div class="field"><label>允许急件排产</label>' + seg('allowUrgent', allowUrgent, ['是', '否']) + '</div>' +
        '<div class="field full"><span class="fhint">两项相互独立、默认都为「是」；可单独关掉某一类，例如只留急件加班。两项都为「否」则这天不排产。</span></div>' +
      '</div>' +
      '<div class="field full"><label>备注</label><input class="cal-note" placeholder="如 节前加班 / 设备检修调休" value="' + note.replace(/"/g, '&quot;') + '"></div>' +
    '</div>' +
    '<div class="modal-f">' +
      '<button class="btn" data-close>取消</button>' +
      (rec ? '<button class="btn cal-clear">清除配置</button>' : '') +
      '<button class="btn primary cal-save">保存配置</button>' +
    '</div></div>');

  // segmented controls
  m.bg.querySelectorAll('.seg').forEach(function (s) {
    s.querySelectorAll('button').forEach(function (b) {
      b.addEventListener('click', function () {
        s.querySelectorAll('button').forEach(function (x) { x.classList.toggle('on', x === b); });
        if (s.getAttribute('data-seg') === 'type') syncType();
      });
    });
  });
  function curType() { return m.bg.querySelector('.seg[data-seg="type"] button.on').getAttribute('data-v'); }
  function syncType() {
    var work = curType() === '工作日';
    var fields = m.bg.querySelector('.cal-work-fields');
    fields.style.opacity = work ? '' : '.45';
    fields.style.pointerEvents = work ? '' : 'none';
  }
  syncType();

  if (rec) m.bg.querySelector('.cal-clear').addEventListener('click', function () {
    delete calState.cfg[calKey(d)];
    m.close();
    renderContent();
    showFlash('已清除 ' + (calState.m + 1) + ' 月 ' + d + ' 日 的配置，恢复默认规则。');
  });
  m.bg.querySelector('.cal-save').addEventListener('click', function () {
    var work = curType() === '工作日';
    var noteV = (m.bg.querySelector('.cal-note').value || '').trim();
    if (work) {
      var an = m.bg.querySelector('.seg[data-seg="allowNormal"] button.on').getAttribute('data-v');
      var au = m.bg.querySelector('.seg[data-seg="allowUrgent"] button.on').getAttribute('data-v');
      calState.cfg[calKey(d)] = {
        type: 'work',
        hours: Number(m.bg.querySelector('.cal-hours').value) || 0,
        eff: Number(m.bg.querySelector('.cal-eff').value) || 0,
        allowNormal: an === '否' ? 'no' : 'yes',
        allowUrgent: au === '否' ? 'no' : 'yes',
        note: noteV
      };
    } else {
      calState.cfg[calKey(d)] = { type: 'rest', note: noteV };
    }
    m.close();
    renderContent();
    showFlash('已保存 ' + (calState.m + 1) + ' 月 ' + d + ' 日 的工作日历（示例数据，刷新后恢复）。');
  });
}
function showCalBatchModal() {
  var m = openModal('<div class="modal lg" role="dialog" aria-modal="true">' +
    modalHead('calendar', '批量维护工作日历', '对一段日期范围统一设置工时、效率或调休 / 加班。') +
    '<div class="modal-b form">' +
      '<div class="fgrid">' +
        '<div class="field"><label>开始日期<span class="req">*</span></label><input class="cb-from" type="date" value="' + calState.y + '-' + String(calState.m + 1).padStart(2, '0') + '-01"></div>' +
        '<div class="field"><label>结束日期<span class="req">*</span></label><input class="cb-to" type="date" value="' + calState.y + '-' + String(calState.m + 1).padStart(2, '0') + '-07"></div>' +
      '</div>' +
      '<div class="field full"><label>应用到</label><div class="seg" data-seg="scope"><button type="button" class="on" data-v="all">范围内每天</button><button type="button" data-v="weekday">仅工作日</button><button type="button" data-v="weekend">仅周末</button></div></div>' +
      '<div class="field full"><label>设置类型</label><div class="seg" data-seg="type"><button type="button" class="on" data-v="工作日">工作日</button><button type="button" data-v="休息日">休息日</button></div></div>' +
      '<div class="fgrid cb-work">' +
        '<div class="field"><label>可排工时（小时）</label><input class="cb-hours" type="number" min="0" max="24" step="0.5" value="8"></div>' +
        '<div class="field"><label>效率（%）</label><input class="cb-eff" type="number" min="0" max="200" step="5" value="100"></div>' +
        '<div class="field"><label>允许普通件排产</label><div class="seg" data-seg="allowNormal"><button type="button" class="on" data-v="是">是</button><button type="button" data-v="否">否</button></div></div>' +
        '<div class="field"><label>允许急件排产</label><div class="seg" data-seg="allowUrgent"><button type="button" class="on" data-v="是">是</button><button type="button" data-v="否">否</button></div></div>' +
      '</div>' +
    '</div>' +
    '<div class="modal-f"><button class="btn" data-close>取消</button><button class="btn primary cb-apply">应用到所选范围</button></div></div>');
  if (window.APSDatePicker) APSDatePicker.enhanceAll(m.bg);
  m.bg.querySelectorAll('.seg').forEach(function (s) {
    s.querySelectorAll('button').forEach(function (b) {
      b.addEventListener('click', function () {
        s.querySelectorAll('button').forEach(function (x) { x.classList.toggle('on', x === b); });
        if (s.getAttribute('data-seg') === 'type') {
          var work = m.bg.querySelector('.seg[data-seg="type"] button.on').getAttribute('data-v') === '工作日';
          var w = m.bg.querySelector('.cb-work');
          w.style.opacity = work ? '' : '.45'; w.style.pointerEvents = work ? '' : 'none';
        }
      });
    });
  });
  m.bg.querySelector('.cb-apply').addEventListener('click', function () {
    var from = m.bg.querySelector('.cb-from').value, to = m.bg.querySelector('.cb-to').value;
    if (!from || !to || from > to) { showFlash('请选择正确的开始 / 结束日期。'); return; }
    var scope = m.bg.querySelector('.seg[data-seg="scope"] button.on').getAttribute('data-v');
    var work = m.bg.querySelector('.seg[data-seg="type"] button.on').getAttribute('data-v') === '工作日';
    var hours = Number(m.bg.querySelector('.cb-hours').value) || 0;
    var eff = Number(m.bg.querySelector('.cb-eff').value) || 0;
    var an = m.bg.querySelector('.seg[data-seg="allowNormal"] button.on').getAttribute('data-v') === '否' ? 'no' : 'yes';
    var au = m.bg.querySelector('.seg[data-seg="allowUrgent"] button.on').getAttribute('data-v') === '否' ? 'no' : 'yes';
    var start = new Date(from), end = new Date(to), n = 0;
    for (var dt = new Date(start); dt <= end; dt.setDate(dt.getDate() + 1)) {
      var dow = dt.getDay(), weekend = dow === 0 || dow === 6;
      if (scope === 'weekday' && weekend) continue;
      if (scope === 'weekend' && !weekend) continue;
      var key = dt.getFullYear() + '-' + dt.getMonth() + '-' + dt.getDate();
      calState.cfg[key] = work ? { type: 'work', hours: hours, eff: eff, allowNormal: an, allowUrgent: au, note: '批量设置' } : { type: 'rest', note: '批量设置' };
      n++;
    }
    m.close();
    renderContent();
    showFlash('已批量' + (work ? '设置工时' : '设为休息') + ' ' + n + ' 天（示例数据，刷新后恢复）。');
  });
}
var SUBDESC = {
  internal: {
    op: '自制链 · 按 <b class="bi">工时口径</b>（换型 + 单件小时）排产。维护工序所需的自制工种，下接<b>设备</b>（绑 1 个工种）与<b>人员</b>（多技能矩阵）。',
    eq: '自制链 · <b class="bi">工时口径</b>。每台设备绑定一个自制工种，提供该工种的可用产能时段。',
    pp: '自制链 · <b class="bi">工时口径</b>。人员按多技能矩阵参与排产，一人可覆盖多个自制工种。'
  },
  external: {
    op: '外协链 · 按 <b class="be">周期口径</b>（天）排产。维护外协工序工种，由供应商承接；连续外协工序可按整组周期计。',
    sup: '外协链 · <b class="be">周期口径</b>。供应商绑定外协工种并给出默认周期（天）。'
  }
};
function viewChain(chainId) {
  var c = CHAINS[chainId], sub = state.sub[chainId];
  var subObj = c.subs.filter(function (s) { return s.id === sub; })[0];
  var tagCls = chainId === 'internal' ? 'tag-int' : 'tag-ext';
  var head = crumb(['产能链', '<span class="' + tagCls + '">' + c.name + ' · ' + c.meas + '</span>', subObj.name]);
  var desc = SUBDESC[chainId][sub];
  var stats, body;
  if (chainId === 'internal') {
    if (sub === 'op') { stats = statline([{ v: 8, l: '自制工种', tone: 'anchor' }, { v: 14, l: '关联设备' }, { v: 23, l: '可用人员', tone: 'ok' }, { v: 1, l: '未绑设备', tone: 'warn' }]); body = toolbar('搜索自制工种…', '新增工种', 'wrench', 'op_int') + table([{ t: '工种编号', w: 120 }, { t: '名称', w: 130 }, { t: '可用设备', w: 100, r: true }, { t: '可用人员', w: 100, r: true }, { t: '产能备注' }, { t: '操作', w: 190, act: true }], OP_INT) + pager(8); }
    else if (sub === 'eq') { stats = statline([{ v: 14, l: '设备总数', tone: 'anchor' }, { v: 12, l: '可用', tone: 'ok' }, { v: 2, l: '检修', tone: 'warn' }, { v: 3, l: '设备组' }]); body = toolbar('搜索设备…', '新增设备', 'machine', 'equip') + table([{ t: '设备编号', w: 110 }, { t: '名称' }, { t: '绑定工种', w: 120 }, { t: '设备组', w: 110 }, { t: '状态', w: 110 }, { t: '操作', w: 190, act: true }], EQUIP) + pager(14); }
    else { stats = statline([{ v: 23, l: '人员总数', tone: 'anchor' }, { v: 20, l: '在岗', tone: 'ok' }, { v: 3, l: '请假 / 异常', tone: 'warn' }, { v: 41, l: '技能认证' }]); body = toolbar('搜索人员…', '新增人员', 'users', 'people') + table([{ t: '工号', w: 100 }, { t: '姓名', w: 110 }, { t: '技能工种' }, { t: '班次', w: 100 }, { t: '状态', w: 110 }, { t: '操作', w: 190, act: true }], PEOPLE) + pager(23); }
  } else {
    if (sub === 'op') { stats = statline([{ v: 4, l: '外协工种', tone: 'anchor' }, { v: 6, l: '可用供应商', tone: 'ok' }, { v: 1, l: '合并设置' }, { v: 3, l: '分别设置' }]); body = toolbar('搜索外协工种…', '新增外协工种', 'wrench', 'op_ext') + table([{ t: '工种编号', w: 120 }, { t: '名称', w: 150 }, { t: '默认周期策略', w: 150 }, { t: '备注' }, { t: '操作', w: 190, act: true }], OP_EXT) + pager(4); }
    else { stats = statline([{ v: 6, l: '供应商总数', tone: 'anchor' }, { v: 4, l: '启用', tone: 'ok' }, { v: 1, l: '待复核', tone: 'warn' }, { v: 1, l: '停用' }]); body = toolbar('搜索供应商…', '新增供应商', 'truck', 'supplier') + table([{ t: '编号', w: 90 }, { t: '供应商', w: 160 }, { t: '可做外协工种' }, { t: '默认周期', w: 110, r: true }, { t: '状态', w: 110 }, { t: '操作', w: 190, act: true }], SUPPLIERS) + pager(6); }
  }
  return head + chead(subObj.name, desc) + stats + (sub === 'op' ? pendingCard() : '') + body;
}

function pendingCard() {
  if (!PENDING_OPTYPES.length) return '';
  var rows = PENDING_OPTYPES.map(function (p, i) {
    return '<tr data-pi="' + i + '"><td><b>' + p.name + '</b></td>' +
      '<td><span class="pill warn"><span class="dot"></span>待归类</span></td>' +
      '<td class="muted" style="font-size:12px">路线引入 · ' + p.from + '</td>' +
      '<td class="r"><div class="rowact" style="justify-content:flex-end"><button class="mini pend-int" data-pi="' + i + '">建为自制</button><button class="mini pend-ext" data-pi="' + i + '">建为外协</button></div></td></tr>';
  }).join('');
  return '<div class="pend-card"><div class="pend-head"><span class="pill warn"><span class="dot"></span>待归类工种 · 由路线引入</span>' +
    '<span class="muted" style="font-size:12px">这些工种在路线里出现、但工种库里还没有。建库时选自制 / 外协，归位后对应工序自动可排产。</span></div>' +
    '<div class="card wb-table-frame"><div class="card-scroll wb-table-shell"><table class="tbl wb-table"><thead><tr><th style="width:160px">工种名</th><th style="width:110px">状态</th><th>来源</th><th class="r" style="width:210px">建库</th></tr></thead><tbody>' + rows + '</tbody></table></div></div></div>';
}

function renderContent() {
  var el = document.getElementById('content');
  if (state.node === 'process') el.innerHTML = viewProcess();
  else if (state.node === 'material') el.innerHTML = viewMaterial();
  else if (state.node === 'calendar') el.innerHTML = viewCalendar();
  else el.innerHTML = viewChain(state.node);

  el.querySelectorAll('.subtab[data-chain]').forEach(function (b) {
    b.addEventListener('click', function () { state.sub[b.getAttribute('data-chain')] = b.getAttribute('data-sub'); render(); });
  });
  wireList();
  wireToolbar();
  document.querySelectorAll('#content .pend-int, #content .pend-ext').forEach(function (b) {
    b.addEventListener('click', function () {
      var i = +b.getAttribute('data-pi');
      var p = PENDING_OPTYPES[i];
      if (!p) return;
      var asInt = b.classList.contains('pend-int');
      if (asInt) KNOWN_INT.push(p.name); else KNOWN_EXT.push(p.name);
      PENDING_OPTYPES.splice(i, 1);
      showFlash('已建为' + (asInt ? '自制' : '外协') + '工种「' + p.name + '」·引用它的工序已转可排产。');
      render();
    });
  });
  if (state.node === 'process') wireProcess();
  if (state.node === 'calendar') wireCalendar();
  window.dispatchEvent(new Event('aps:master-data-changed'));
}

/* new / import-export buttons */
function wireToolbar() {
  var add = document.querySelector('#content .add-btn');
  if (add) add.addEventListener('click', function () { var en = add.getAttribute('data-entity'); if (en === 'part') showAddPartModal(); else showFormModal(en); });
  document.querySelectorAll('#content .io-btn').forEach(function (io) {
    io.addEventListener('click', function () { showImportExport(io.getAttribute('data-entity'), io.getAttribute('data-mode')); });
  });
}

/* 工艺：双导入按钮 + 零件下钻 + 三步 stepper + 归属分拣 */
function wireProcess() {
  var ir = document.querySelector('#content .imp-route');
  if (ir) ir.addEventListener('click', function () { showImportExport('route', 'imp'); });
  var ih = document.querySelector('#content .imp-hours');
  if (ih) ih.addEventListener('click', function () { showImportExport('hours', 'imp'); });

  document.querySelectorAll('#content .subtab[data-stage]').forEach(function (b) {
    b.addEventListener('click', function () { state.stageFilter = b.getAttribute('data-stage'); render(); });
  });
  var gp = document.querySelector('#content .go-pending');
  if (gp) gp.addEventListener('click', function () { state.node = 'internal'; state.sub.internal = 'op'; render(); });
  document.querySelectorAll('#content .tbl tbody tr[data-code]').forEach(function (tr) {
    var code = tr.getAttribute('data-code');
    var open = function (e) { if (e) e.preventDefault(); openPartModal(code); };
    var lnk = tr.querySelector('.lnk'); if (lnk) lnk.addEventListener('click', open);
    var act = tr.querySelector('.pl-act'); if (act) act.addEventListener('click', open);
    var menu = tr.querySelector('.pl-route-menu');
    if (menu) menu.addEventListener('click', function (e) {
      e.preventDefault(); e.stopPropagation();
      openMenu(menu, [
        { icon: UP_SVG, transfer: 'import', label: '导入工艺路线', onClick: function () { showImportExport('route', 'imp'); } },
        { icon: PEN_SVG, label: '手工新建路线', onClick: function () { showRouteEntry(code); } }
      ]);
    });
  });
}

function wireHours(code, scope) {
  scope = scope || document.getElementById('content');
  scope.querySelectorAll('.subtab[data-opview]').forEach(function (b) {
    b.addEventListener('click', function () { state.opView = b.getAttribute('data-opview'); render(); });
  });
  scope.querySelectorAll('.wt-in[data-field="unit"]').forEach(function (inp) {
    inp.addEventListener('input', function () {
      var v = inp.value.trim();
      inp.classList.toggle('empty', v === '');
      inp.classList.toggle('bad', v !== '' && Number(v) === 0);
    });
  });
  var save = scope.querySelector('.pd-save');
  if (save) save.addEventListener('click', function () {
    var ops = PART_OPS[code] || [];
    scope.querySelectorAll('.wt-in').forEach(function (inp) {
      var seq = Number(inp.getAttribute('data-seq')), f = inp.getAttribute('data-field');
      var op = ops.find(function (o) { return o.seq === seq; });
      if (op) op[f] = inp.value.trim();
    });
    var s = partStageOf(code); s.hours = hoursStateAfter(code);
    render();
    showFlash('已保存 ' + code + ' 的工序工时（示例数据，刷新后恢复）。');
  });
}

function wireSort(code, scope) {
  var content = scope || document.getElementById('content');
  var rows = [].slice.call(content.querySelectorAll('.sort-row'));
  var total = rows.length;
  var confEl = content.querySelector('.sort-confirmed');
  var todoEl = content.querySelector('.sort-todo');
  var finish = content.querySelector('.sort-finish');
  function refresh() {
    var c = rows.filter(function (r) { return r.classList.contains('staged'); }).length;
    if (confEl) confEl.textContent = c;
    if (todoEl) todoEl.textContent = total - c;
    if (finish) { finish.disabled = c < total; finish.textContent = c < total ? ('完成归属 · 解锁工时（还剩 ' + (total - c) + '）') : ('完成归属 · 解锁工时（' + total + ' 道）'); }
  }
  function stage(tr) {
    tr.classList.add('staged'); tr.classList.remove('attn', 'attn-bad');
    var st = tr.querySelector('.attr-status'); if (st) st.innerHTML = '<span class="pill info"><span class="dot"></span>已选 · 待提交</span>';
    refresh();
  }
  rows.forEach(function (tr) {
    tr.querySelectorAll('.segm button').forEach(function (b) {
      b.addEventListener('click', function () {
        tr.querySelectorAll('.segm button').forEach(function (x) { x.classList.remove('on', 'int', 'ext'); });
        b.classList.add('on'); b.classList.add(b.getAttribute('data-attr') === 'int' ? 'int' : 'ext');
        stage(tr);
      });
    });
  });
  if (finish) finish.addEventListener('click', function () {
    if (finish.disabled) return;
    var s = partStageOf(code);
    s.attr = 'done';
    if (s.hours === 'locked') s.hours = hoursStateAfter(code);
    state.openStage = null;
    render();
    showFlash(code + ' 工序归属已确认，工时录入已解锁（示例）。');
  });
  refresh();
}

/* selection + batch delete (toolbar-contextual) */
var currentUpd = null;
function wireList() {
  var all = document.querySelector('#content .ck-all');
  if (!all) return;
  var selgrp = null;
  var del = document.querySelector('#content .batch-del');
  var selN = document.querySelector('#content .selN');
  var selcount = document.querySelector('#content .selcount');
  var clear = document.querySelector('#content .clear-sel');
  var pgt = document.querySelector('#content .pgtotal');
  function rowsNow() { return [].slice.call(document.querySelectorAll('#content .ck-row')); }
  function upd() {
    var rows = rowsNow();
    var sel = rows.filter(function (r) { return r.checked; });
    var has = sel.length > 0;
    selN.textContent = sel.length;
    if (selcount) selcount.hidden = !has;
    if (clear) clear.hidden = !has;
    all.checked = rows.length > 0 && sel.length === rows.length;
    all.indeterminate = has && sel.length < rows.length;
  }
  all.addEventListener('change', function () { rowsNow().forEach(function (r) { r.checked = all.checked; }); upd(); });
  rowsNow().forEach(function (r) { r.addEventListener('change', upd); });
  currentUpd = upd;
  if (clear) clear.addEventListener('click', function () { rowsNow().forEach(function (r) { r.checked = false; }); upd(); });
  if (del) del.addEventListener('click', function () {
    var sel = rowsNow().filter(function (r) { return r.checked; });
    if (!sel.length) {
      showConfirm({ title: '请先选择要删除的行', body: '在列表左侧勾选一个或多个行后，再点击「批量删除」。你也可以勾选表头复选框全选。', ok: '知道了', info: true });
      return;
    }
    showConfirm({
      title: '批量删除所选 ' + sel.length + ' 项？',
      body: '若所选项目存在引用（被<b>工序 / 批次 / 资源</b>引用），对应行将删除失败并提示。确认继续吗？',
      ok: '确认删除 ' + sel.length + ' 项',
      onOk: function () {
        sel.forEach(function (r) { var tr = r.closest('tr'); if (tr) tr.parentNode.removeChild(tr); });
        if (pgt) { var n = parseInt((pgt.textContent || '0').replace(/[^0-9]/g, ''), 10) || 0; pgt.textContent = Math.max(0, n - sel.length); }
        upd();
        showFlash('已删除 ' + sel.length + ' 项（示例数据，刷新或切换后恢复）。');
      }
    });
  });
  upd();
}

function showConfirm(o) {
  var bg = document.createElement('div');
  bg.className = 'modal-bg';
  var foot = o.info
    ? '<button class="btn primary ok">' + (o.ok || '知道了') + '</button>'
    : '<button class="btn cancel">取消</button><button class="btn dangerfill ok">' + (o.ok || '确认') + '</button>';
  bg.innerHTML = '<div class="modal" role="dialog" aria-modal="true">' +
    '<div class="modal-h">' + o.title + '</div>' +
    '<div class="modal-b">' + o.body + '</div>' +
    '<div class="modal-f">' + foot + '</div></div>';
  function close() { if (bg.parentNode) bg.parentNode.removeChild(bg); document.removeEventListener('keydown', onKey); }
  function onKey(e) { if (e.key === 'Escape') close(); }
  bg.addEventListener('click', function (e) { if (e.target === bg) close(); });
  var cancel = bg.querySelector('.cancel');
  if (cancel) cancel.addEventListener('click', close);
  bg.querySelector('.ok').addEventListener('click', function () { close(); if (o.onOk) o.onOk(); });
  document.addEventListener('keydown', onKey);
  root.appendChild(bg);
}

/* ---------------- generic modal shell ---------------- */
function openModal(html) {
  var bg = document.createElement('div');
  bg.className = 'modal-bg';
  bg.innerHTML = html;
  function close() { if (bg.parentNode) bg.parentNode.removeChild(bg); document.removeEventListener('keydown', onKey); }
  function onKey(e) { if (e.key === 'Escape') close(); }
  bg.addEventListener('click', function (e) { if (e.target === bg) close(); });
  document.addEventListener('keydown', onKey);
  root.appendChild(bg);
  bg.querySelectorAll('[data-close]').forEach(function (b) { b.addEventListener('click', close); });
  return { bg: bg, close: close };
}
function modalHead(icon, title, sub) {
  return '<div class="modal-head"><span class="modal-ico">' + svg(icon) + '</span>' +
    '<div><div class="modal-h2">' + title + '</div><div class="modal-hs">' + sub + '</div></div>' +
    '<button class="modal-x" data-close aria-label="关闭">✕</button></div>';
}

/* ---------------- 轻量下拉菜单 ---------------- */
function closeMenu() { var m = root.querySelector('.pl-menu'); if (m) m.parentNode.removeChild(m); document.removeEventListener('mousedown', _menuOut); }
function _menuOut(e) { var m = root.querySelector('.pl-menu'); if (m && !m.contains(e.target)) closeMenu(); }
function openMenu(anchor, items) {
  closeMenu();
  var m = document.createElement('div');
  m.className = 'pl-menu';
  m.innerHTML = items.map(function (it, i) { return '<button class="pl-menu-item' + (it.transfer ? ' wb-transfer' : '') + '" data-i="' + i + '"' + (it.transfer ? ' data-wb-transfer="' + it.transfer + '"' : '') + '><span class="pl-menu-ic">' + it.icon + '</span><span>' + it.label + '</span></button>'; }).join('');
  root.appendChild(m);
  var r = anchor.getBoundingClientRect();
  m.style.top = (r.bottom + 6) + 'px';
  m.style.left = Math.max(8, Math.min(r.left, window.innerWidth - 230)) + 'px';
  m.querySelectorAll('.pl-menu-item').forEach(function (b) {
    b.addEventListener('click', function () { var i = +b.getAttribute('data-i'); closeMenu(); items[i].onClick(); });
  });
  setTimeout(function () { document.addEventListener('mousedown', _menuOut); }, 0);
}

/* ---------------- 手工新建工艺路线 ---------------- */
function showRouteEntry(code) {
  var meta = PART_META[code] || { name: '' };
  var opts = KNOWN_INT.concat(KNOWN_EXT);
  var dataList = '<datalist id="re-oplist">' + opts.map(function (o) { return '<option value="' + o + '">' + (KNOWN_INT.indexOf(o) >= 0 ? '自制' : '外协') + '</option>'; }).join('') + '</datalist>';
  var rows = [{ seq: '5', op: '' }, { seq: '10', op: '' }, { seq: '20', op: '' }];

  function attrCellHtml(op) {
    var k = classifyOp(op);
    if (k === 'int') return '<span class="chip b">自制</span>';
    if (k === 'ext') return '<span class="chip a">外协</span>';
    if (k === 'unknown') return '<span class="pill warn"><span class="dot"></span>未识别 · 待归类</span>';
    return '<span class="muted">—</span>';
  }
  function rowHtml(r, i) {
    return '<tr data-i="' + i + '">' +
      '<td class="r"><input class="wt-in re-seq" style="width:62px;text-align:right" value="' + r.seq + '"></td>' +
      '<td><input class="wt-in re-op" list="re-oplist" placeholder="选择或输入工种" style="width:172px" value="' + r.op + '"></td>' +
      '<td class="re-attr">' + attrCellHtml(r.op) + '</td>' +
      '<td class="r"><button class="mini danger re-del" data-i="' + i + '" aria-label="删除">删除</button></td></tr>';
  }
  function tableHtml() {
    return dataList + '<div class="card wb-table-frame"><div class="card-scroll wb-table-shell"><table class="tbl re-tbl wb-table" style="min-width:470px"><thead><tr><th class="r" style="width:78px">工序号</th><th style="width:192px">工种</th><th style="width:150px">归属</th><th class="r" style="width:70px">操作</th></tr></thead><tbody class="re-body">' + rows.map(rowHtml).join('') + '</tbody></table></div></div>' +
      '<button class="mini re-add" style="margin-top:10px">+ 添加工序</button>';
  }
  function summaryHtml() {
    var named = rows.filter(function (r) { return r.op.trim(); });
    var names = [];
    named.forEach(function (r) { if (classifyOp(r.op) === 'unknown') { var n = r.op.trim(); if (names.indexOf(n) < 0) names.push(n); } });
    if (!named.length) return '<div class="iohint">至少录入一道工序。</div>';
    if (!names.length) return '<div class="re-ok">✓ ' + named.length + ' 道工序，工种全部识别，保存后可直接进入下一步。</div>';
    return '<div class="match-note">⚠ ' + named.length + ' 道工序中 <b>' + names.length + ' 个工种未识别</b>（' + names.join('、') + '）。保存照常，未识别工种将登记到工种库「待归类 · 待建」，补建后这些工序自动转可排产。</div>';
  }

  function serializeRows() {
    return rows.filter(function (r) { return r.op.trim(); })
      .map(function (r) { return r.seq + ' ' + r.op.trim(); }).join('   ');
  }
  function previewHtml() {
    var named = rows.filter(function (r) { return r.op.trim(); });
    if (!named.length) return '<div class="iohint">按上面的格式整条粘贴或输入，系统会在这里按工序号自动拆行预览，并标出每道工序的归属。</div>';
    return '<div class="seclabel" style="margin:14px 2px 9px">解析预览 · ' + named.length + ' 道工序</div>' +
      '<div class="card wb-table-frame"><div class="card-scroll wb-table-shell"><table class="tbl re-tbl wb-table" style="min-width:380px"><thead><tr><th class="r" style="width:78px">工序号</th><th style="width:188px">工种</th><th style="width:160px">归属</th></tr></thead><tbody>' +
      named.map(function (r) { return '<tr><td class="r">' + (r.seq || '—') + '</td><td>' + r.op.trim() + '</td><td class="re-attr">' + attrCellHtml(r.op) + '</td></tr>'; }).join('') +
      '</tbody></table></div></div>';
  }
  function textPaneHtml() {
    return '<div class="field full" style="margin:0">' +
        '<label>路线文字</label>' +
        '<textarea class="re-text" placeholder="如：5数铣10钳工20数车30外协电镀40总检" style="min-height:104px;line-height:1.7"></textarea>' +
        '<span class="fhint">工序号与工种可直接连写、不用空格（如 <b>5数铣10钳工20数车</b>），系统按工序号自动拆行；也兼容空格 / 逗号 / 换行分隔，或直接粘贴工艺卡文字。带「外协」前缀或库内外协工种自动归到外协链；库里没有的工种保存后登记为「待归类 · 待建」。</span>' +
      '</div>' +
      '<div class="re-prev" style="margin-top:6px"></div>';
  }

  var m = openModal('<div class="modal lg re-modal" role="dialog" aria-modal="true">' +
    modalHead('route', '手工新建工艺路线' + (code ? (' · ' + code + ' ' + (meta.name || '')) : ''), '整条录入：直接粘贴 / 输入一整条路线文字，按工序号自动拆行；也可切到逐行表格逐道编辑。工种优先匹配库内，库里没有的可直接写。') +
    '<div class="modal-b scroll">' +
      '<div class="seg re-mode" data-seg="mode" style="margin:2px 0 16px">' +
        '<button type="button" class="on" data-v="text">整条录入</button>' +
        '<button type="button" data-v="table">逐行表格</button>' +
      '</div>' +
      '<div class="re-pane-text">' + textPaneHtml() + '</div>' +
      '<div class="re-pane-table" style="display:none">' + tableHtml() + '</div>' +
      '<div class="re-sum">' + summaryHtml() + '</div>' +
    '</div>' +
    '<div class="modal-f wb-actions"><button class="btn" data-close>取消</button><button class="btn primary re-save wb-action wb-primary">保存路线</button></div></div>');

  var mode = 'text';
  function refreshSum() { m.bg.querySelector('.re-sum').innerHTML = summaryHtml(); }
  function renderPreview() { var p = m.bg.querySelector('.re-prev'); if (p) p.innerHTML = previewHtml(); }
  function rebuild() { m.bg.querySelector('.re-pane-table').innerHTML = tableHtml(); refreshSum(); wireTable(); }
  function wireTable() {
    m.bg.querySelectorAll('.re-op').forEach(function (inp) {
      inp.addEventListener('input', function () {
        var i = +inp.closest('tr').getAttribute('data-i');
        rows[i].op = inp.value;
        inp.closest('tr').querySelector('.re-attr').innerHTML = attrCellHtml(inp.value);
        refreshSum();
      });
    });
    m.bg.querySelectorAll('.re-seq').forEach(function (inp) {
      inp.addEventListener('input', function () { rows[+inp.closest('tr').getAttribute('data-i')].seq = inp.value; });
    });
    m.bg.querySelectorAll('.re-del').forEach(function (b) {
      b.addEventListener('click', function () { rows.splice(+b.getAttribute('data-i'), 1); if (!rows.length) rows.push({ seq: '5', op: '' }); rebuild(); });
    });
    var add = m.bg.querySelector('.re-add');
    if (add) add.addEventListener('click', function () {
      var last = rows.length ? parseInt(rows[rows.length - 1].seq, 10) : 0;
      var nx = (isNaN(last) ? rows.length * 10 : last) + 10;
      rows.push({ seq: String(nx), op: '' });
      rebuild();
    });
  }
  function wireText() {
    var ta = m.bg.querySelector('.re-text');
    if (!ta) return;
    ta.value = serializeRows();
    ta.addEventListener('input', function () {
      rows = parseRouteText(ta.value);
      renderPreview();
      refreshSum();
    });
    renderPreview();
  }
  m.bg.querySelectorAll('.re-mode button').forEach(function (b) {
    b.addEventListener('click', function () {
      var v = b.getAttribute('data-v');
      if (v === mode) return;
      mode = v;
      m.bg.querySelectorAll('.re-mode button').forEach(function (x) { x.classList.toggle('on', x === b); });
      m.bg.querySelector('.re-pane-text').style.display = v === 'text' ? '' : 'none';
      m.bg.querySelector('.re-pane-table').style.display = v === 'table' ? '' : 'none';
      if (v === 'table') { rebuild(); }
      else { var ta = m.bg.querySelector('.re-text'); if (ta) ta.value = serializeRows(); renderPreview(); }
      refreshSum();
    });
  });
  wireTable();
  wireText();

  m.bg.querySelector('.re-save').addEventListener('click', function () {
    var named = rows.filter(function (r) { return r.op.trim(); });
    if (!named.length) { showFlash('请至少录入一道工序。'); return; }
    var unk = [];
    named.forEach(function (r) { if (classifyOp(r.op) === 'unknown') { var n = r.op.trim(); if (unk.indexOf(n) < 0) unk.push(n); } });
    if (code) {
      PART_OPS[code] = named.map(function (r) {
        var k = classifyOp(r.op);
        return { seq: r.seq, op: r.op.trim(), dev: '—', src: k === 'ext' ? 'ext' : 'int', setup: '', unit: '', ext: k === 'ext' ? '外协' : '' };
      });
      PART_STAGE[code] = PART_STAGE[code] || {};
      PART_STAGE[code].route = 'done';
      if (PART_STAGE[code].attr === 'locked' || !PART_STAGE[code].attr) PART_STAGE[code].attr = 'pending';
      if (!PART_STAGE[code].hours) PART_STAGE[code].hours = 'locked';
      var pm = PART_META[code] || (PART_META[code] = { name: meta.name || code });
      pm.parsed = true;
    }
    unk.forEach(function (n) { addPending(n, code ? (code + ' ' + (meta.name || '')) : '手工录入'); });
    m.close();
    var msg = '已保存' + (code ? (' ' + code) : '') + '路线 · ' + named.length + ' 道工序';
    if (unk.length) msg += '；' + unk.length + ' 个工种未识别，已登记到工种库待建';
    showFlash(msg + '。');
    if (state.openPart === code) state.openStage = null;
    render();
  });
}

/* ---------------- 新增 / 编辑 表单 ---------------- */
var FORMS = {
  part: { title: '新增零件', icon: 'route', sub: '工艺零件模板，保存后加入列表。', cols: 6, fields: [
    { k: 'code', l: '图号', ph: '如 T-1024', req: true, w: 'half' },
    { k: 'name', l: '名称', ph: '如 回转壳体 F', req: true, w: 'half' },
    { k: 'route', l: '路线文字', ph: '如 5数铣 10钳 20数车 30外协电镀 40总检', type: 'textarea', full: true, hint: '每道工序在解析后按归属自动分流到自制 / 外协两条链。' } ] },
  material: { title: '新增物料', icon: 'cube', sub: '物料主数据，供批次按主数据引用。', cols: 6, fields: [
    { k: 'code', l: '物料编号', ph: '如 M-2050', req: true, w: 'half' },
    { k: 'name', l: '名称', ph: '如 45# 圆钢', req: true, w: 'half' },
    { k: 'spec', l: '规格', ph: '如 Ø120 × 2000', w: 'half' },
    { k: 'stock', l: '库存', ph: '如 1,200 kg', w: 'half' },
    { k: 'status', l: '状态', type: 'select', opts: ['启用', '低库存', '停用'], w: 'half' } ] },
  op_int: { title: '新增自制工种', icon: 'wrench', sub: '自制链工种，按工时口径排产。', cols: 6, fields: [
    { k: 'code', l: '工种编号', ph: '如 OT007', req: true, w: 'half' },
    { k: 'name', l: '名称', ph: '如 钻孔', req: true, w: 'half' },
    { k: 'note', l: '产能备注', ph: '如 瓶颈工序，人员偏紧', type: 'textarea', full: true } ] },
  equip: { title: '新增设备', icon: 'machine', sub: '每台设备绑定一个自制工种。', cols: 6, fields: [
    { k: 'code', l: '设备编号', ph: '如 EQ-15', req: true, w: 'half' },
    { k: 'name', l: '名称', ph: '如 立式加工中心 VMC-650', req: true, w: 'half' },
    { k: 'op', l: '绑定工种', type: 'select', opts: ['数铣', '数车', '钳工', '精磨', '总检'], w: 'half', hint: '一台设备只绑定一个工种。' },
    { k: 'group', l: '设备组', type: 'select', opts: ['设备组 A', '设备组 B', '设备组 C'], w: 'half' },
    { k: 'status', l: '状态', type: 'select', opts: ['可用', '检修'], w: 'half' } ] },
  people: { title: '新增人员', icon: 'users', sub: '人员按多技能矩阵参与排产。', cols: 6, fields: [
    { k: 'code', l: '工号', ph: '如 P-140', req: true, w: 'half' },
    { k: 'name', l: '姓名', ph: '如 孙明', req: true, w: 'half' },
    { k: 'skills', l: '技能工种', type: 'chips', opts: ['数铣', '数车', '钳工', '精磨', '钻孔', '总检'], full: true, hint: '可多选，构成多技能矩阵。' },
    { k: 'shift', l: '班次', type: 'select', opts: ['白班', '两班倒', '夜班'], w: 'half' },
    { k: 'status', l: '状态', type: 'select', opts: ['在岗', '请假'], w: 'half' } ] },
  op_ext: { title: '新增外协工种', icon: 'wrench', sub: '外协链工种，按周期口径排产。', cols: 5, fields: [
    { k: 'code', l: '工种编号', ph: '如 OT055', req: true, w: 'half' },
    { k: 'name', l: '名称', ph: '如 阳极氧化', req: true, w: 'half' },
    { k: 'policy', l: '默认周期策略', type: 'select', opts: ['分别设置', '合并设置'], w: 'half', hint: '合并设置：连续外协工序按整组周期计。' },
    { k: 'note', l: '备注', ph: '如 需炉前确认整组周期', type: 'textarea', full: true } ] },
  supplier: { title: '新增供应商', icon: 'truck', sub: '供应商绑外协工种并给默认周期。', cols: 6, fields: [
    { k: 'code', l: '编号', ph: '如 S-09', req: true, w: 'half' },
    { k: 'name', l: '供应商', ph: '如 华表面处理', req: true, w: 'half' },
    { k: 'ops', l: '可做外协工种', type: 'chips', opts: ['电镀', '发黑', '热处理', '喷涂'], full: true },
    { k: 'lead', l: '默认周期', ph: '如 3 天', w: 'half' },
    { k: 'status', l: '状态', type: 'select', opts: ['启用', '待复核', '停用'], w: 'half' } ] },
};
function fieldHtml(f) {
  var inner;
  if (f.type === 'textarea') inner = '<textarea data-k="' + f.k + '" placeholder="' + (f.ph || '') + '"></textarea>';
  else if (f.type === 'select') { var car = '<span class="selcar"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg></span>'; var ck = '<span class="ck"><svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5L19 7"/></svg></span>'; inner = '<div class="selbox" data-k="' + f.k + '" data-val="' + f.opts[0] + '"><button type="button" class="selbtn"><span class="selval">' + f.opts[0] + '</span>' + car + '</button><div class="selpop">' + f.opts.map(function (o, i) { return '<div class="selopt' + (i === 0 ? ' on' : '') + '" data-v="' + o + '">' + o + ck + '</div>'; }).join('') + '</div></div>'; }
  else if (f.type === 'chips') inner = '<div class="fchips" data-k="' + f.k + '">' + f.opts.map(function (o) { return '<span class="fchip" data-v="' + o + '">' + o + '</span>'; }).join('') + '</div>';
  else inner = '<input data-k="' + f.k + '" placeholder="' + (f.ph || '') + '">';
  return '<div class="field' + (f.full ? ' full' : '') + '">' +
    '<label>' + f.l + (f.req ? '<span class="req">*</span>' : '') + '</label>' + inner +
    (f.hint ? '<span class="fhint">' + f.hint + '</span>' : '') + '</div>';
}
function pillFor(s) {
  var map = { '启用': 'ok', '已解析': 'ok', '可用': 'ok', '在岗': 'ok', '低库存': 'warn', '检修': 'warn', '请假': 'warn', '待复核': 'warn', '待解析': 'warn', '未解析': 'warn', '停用': 'off' };
  return '<span class="pill ' + (map[s] || 'info') + '"><span class="dot"></span>' + s + '</span>';
}
function chipsOf(arr, cls) { return arr && arr.length ? '<span class="chipline">' + arr.map(function (x) { return '<span class="chip ' + cls + '">' + x + '</span>'; }).join('') + '</span>' : '<span class="muted">—</span>'; }
function buildRow(entity, v) {
  var lnk = '<a class="lnk">' + (v.code || '—') + '</a>';
  if (entity === 'part') return [lnk, v.name || '—', '<span class="route">' + (v.route || '—') + '</span>', '<span class="muted" style="font-size:12px">待生成</span>', pillFor(v.status || '待解析'), actBtns()];
  if (entity === 'material') return [lnk, v.name || '—', v.spec || '<span class="muted">—</span>', v.stock || '<span class="muted">—</span>', pillFor(v.status || '启用'), actBtns()];
  if (entity === 'op_int') return [lnk, v.name || '—', '0', '0', v.note || '<span class="muted">—</span>', actBtns('查看绑定')];
  if (entity === 'equip') return [lnk, v.name || '—', v.op ? '<span class="chip b">' + v.op + '</span>' : '<span class="muted">—</span>', v.group || '—', pillFor(v.status || '可用'), actBtns()];
  if (entity === 'people') return [lnk, v.name || '—', chipsOf(v.skills, 'b'), v.shift || '白班', pillFor(v.status || '在岗'), actBtns()];
  if (entity === 'op_ext') return [lnk, v.name || '—', v.policy || '分别设置', v.note || '<span class="muted">—</span>', actBtns('查看供应商')];
  if (entity === 'supplier') return [lnk, v.name || '—', chipsOf(v.ops, 'a'), v.lead || '—', pillFor(v.status || '启用'), actBtns()];
  return [];
}
function addRowToTable(cells) {
  var tbody = document.querySelector('#content tbody');
  if (!tbody) return;
  var ths = [].slice.call(document.querySelectorAll('#content thead th')).slice(1);
  var tr = document.createElement('tr');
  var html = '<td class="cbx"><input type="checkbox" class="ck-row"></td>';
  cells.forEach(function (c, i) {
    var th = ths[i];
    var cls = th && th.classList.contains('r') ? 'r' : (th && th.classList.contains('actcol') ? 'actcol' : '');
    html += '<td class="' + cls + '">' + c + '</td>';
  });
  tr.innerHTML = html;
  tr.style.animation = 'fade .2s ease';
  tbody.insertBefore(tr, tbody.firstChild);
  var ck = tr.querySelector('.ck-row');
  if (ck) ck.addEventListener('change', function () { if (currentUpd) currentUpd(); });
  var pgt = document.querySelector('#content .pgtotal');
  if (pgt) { var n = parseInt((pgt.textContent || '0').replace(/[^0-9]/g, ''), 10) || 0; pgt.textContent = n + 1; }
  if (currentUpd) currentUpd();
}
function closeAllSel(root) {
  (root || document).querySelectorAll('.selbox.open').forEach(function (x) {
    x.classList.remove('open');
    var p = x.querySelector('.selpop');
    if (p) { p.style.position = ''; p.style.left = ''; p.style.top = ''; p.style.bottom = ''; p.style.width = ''; }
  });
}
function openSel(box) {
  box.classList.add('open');
  var pop = box.querySelector('.selpop');
  var r = box.querySelector('.selbtn').getBoundingClientRect();
  var ph = Math.min(pop.scrollHeight, 220);
  pop.style.position = 'fixed';
  pop.style.left = r.left + 'px';
  pop.style.width = r.width + 'px';
  if (window.innerHeight - r.bottom < ph + 16) { pop.style.top = ''; pop.style.bottom = (window.innerHeight - r.top + 5) + 'px'; }
  else { pop.style.bottom = ''; pop.style.top = (r.bottom + 5) + 'px'; }
}
/* ---------------- 新增零件 · 一次填完（路线 + 归属 + 工时） ---------------- */
function showAddPartModal() {
  var rows = []; // {seq, op, src, setup, unit}
  function sugOf(op) { var k = classifyOp(op); return k === 'ext' ? 'ext' : (k === 'int' ? 'int' : null); }

  function reparse(text) {
    var snap = {};
    rows.forEach(function (r) { snap[r.seq + '|' + r.op] = r; });
    rows = parseRouteText(text).map(function (p) {
      var prev = snap[p.seq + '|' + p.op];
      if (prev) return prev;
      var s = sugOf(p.op);
      return { seq: p.seq, op: p.op, src: s === 'ext' ? 'ext' : 'int', setup: '', unit: '' };
    });
  }
  function stats() {
    var intRows = rows.filter(function (r) { return r.src === 'int'; });
    var missing = intRows.filter(function (r) { return r.unit === '' || Number(r.unit) === 0; }).length;
    var unk = [];
    rows.forEach(function (r) { if (classifyOp(r.op) === 'unknown' && unk.indexOf(r.op) < 0) unk.push(r.op); });
    return { total: rows.length, intN: intRows.length, extN: rows.length - intRows.length, missing: missing, unk: unk };
  }
  function summaryHtml() {
    if (!rows.length) return '';
    var s = stats();
    var line = '<div class="statline wb-metrics" style="--wb-columns:4;margin-top:2px">' +
      '<div class="stat anchor wb-metric" data-tone="primary"><span class="sl wb-metric-label">工序</span><span class="sv wb-metric-value">' + s.total + '</span></div>' +
      '<div class="stat wb-metric" data-tone="neutral"><span class="sl wb-metric-label">自制</span><span class="sv ap-intn wb-metric-value">' + s.intN + '</span></div>' +
      '<div class="stat wb-metric" data-tone="neutral"><span class="sl wb-metric-label">外协</span><span class="sv ap-extn wb-metric-value">' + s.extN + '</span></div>' +
      '<div class="stat wb-metric ' + (s.missing ? 'warn' : 'ok') + '" data-tone="' + (s.missing ? 'warn' : 'ok') + '"><span class="sl wb-metric-label">缺工时</span><span class="sv ap-miss wb-metric-value">' + s.missing + '</span></div>' +
      '</div>';
    var note = s.unk.length
      ? '<div class="match-note" style="margin-top:10px">⚠ <b>' + s.unk.length + ' 个工种未识别</b>（' + s.unk.join('、') + '）：已默认归到自制，可在「归属」列改；保存后登记到工种库「待归类 · 待建」。</div>'
      : (s.missing ? '<div class="iohint" style="margin-top:10px">自制工序的换型 / 单件工时现在就能填；留空则该零件保存后停在 <b>「待填工时」</b>，仍可稍后补。</div>'
        : '<div class="re-ok" style="margin-top:10px">✓ 路线、归属、工时已齐备，保存后<b>直接就绪</b>，可参与排产。</div>');
    return line + note;
  }
  function rowHtml(r, i) {
    var sug = sugOf(r.op);
    var seg = '<span class="segm ap-seg" data-i="' + i + '"><button type="button" data-attr="int"' + (r.src === 'int' ? ' class="on int"' : '') + '>自制</button><button type="button" data-attr="ext"' + (r.src === 'ext' ? ' class="on ext"' : '') + '>外协</button></span>';
    var tag = sug ? '<span class="sug">建议 ' + (sug === 'int' ? '自制' : '外协') + '</span>' : '<span class="conf none" style="margin-left:7px">未识别 · 请指定</span>';
    var wt;
    if (r.src === 'ext') wt = '<td class="wt-col" colspan="2" style="text-align:center"><span class="muted" style="font-size:12px">外协工序无工时 · 走周期</span></td>';
    else wt = '<td class="r wt-col"><input class="wt-in ap-setup" data-i="' + i + '" inputmode="decimal" placeholder="0" style="width:74px;text-align:right" value="' + r.setup + '"></td>' +
      '<td class="r wt-col"><input class="wt-in ap-unit" data-i="' + i + '" inputmode="decimal" placeholder="必填" style="width:74px;text-align:right" value="' + r.unit + '"></td>';
    return '<tr data-i="' + i + '">' +
      '<td class="num"><b>' + r.seq + '</b></td>' +
      '<td>' + r.op + '</td>' +
      '<td><div class="attr-cell">' + seg + tag + '</div></td>' + wt + '</tr>';
  }
  function tableHtml() {
    if (!rows.length) return '<div class="iohint">在上面整条输入路线（如 <b>5数铣10钳20数车30外协电镀40总检</b>），系统按工序号自动拆行，并为每道工序给出<b>自制 / 外协</b>建议；自制工序可直接填工时。</div>';
    return '<div class="seclabel" style="margin:16px 2px 9px">工序明细 · 归属与工时 <small style="font-weight:500;color:var(--ui-muted)">建议 → 确认，自制填工时</small></div>' +
      '<div class="card wb-table-frame"><div class="card-scroll wb-table-shell"><table class="tbl op-tbl wb-table" style="min-width:560px;table-layout:auto"><thead><tr>' +
        '<th class="num" style="width:64px">工序号</th><th style="width:120px">工种</th><th style="width:210px">归属</th>' +
        '<th class="r wt-col" style="width:118px">换型工时<small>定额·h</small></th><th class="r wt-col" style="width:118px">单件工时<small>定额·h</small></th>' +
      '</tr></thead><tbody>' + rows.map(rowHtml).join('') + '</tbody></table></div></div>';
  }

  var m = openModal('<div class="modal lg" role="dialog" aria-modal="true">' +
    modalHead('route', '新增零件', '一处填完<b>图号 / 名称 + 路线 + 归属 + 工时</b>，保存即按完成度落到对应阶段，无需再逐步操作。') +
    '<div class="modal-b form scroll">' +
      '<div class="fgrid">' +
        '<div class="field"><label>图号<span class="req">*</span></label><input class="ap-code" placeholder="如 T-1024"></div>' +
        '<div class="field"><label>名称<span class="req">*</span></label><input class="ap-name" placeholder="如 回转壳体 F"></div>' +
        '<div class="field full"><label>路线文字<span class="req">*</span></label><textarea class="ap-route" placeholder="如：5数铣10钳20数车30外协电镀40总检" style="min-height:88px;line-height:1.7"></textarea>' +
          '<span class="fhint">工序号与工种可直接连写、不用空格，系统按工序号自动拆行；也兼容空格 / 逗号 / 换行。带「外协」前缀或库内外协工种自动归到外协链。</span></div>' +
      '</div>' +
      '<div class="ap-parsed"></div>' +
      '<div class="ap-sum"></div>' +
    '</div>' +
    '<div class="modal-f wb-actions"><button class="btn" data-close>取消</button><button class="btn primary ap-save wb-action wb-primary"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l4 4 10-10"/></svg>保存并加入列表</button></div></div>');

  function wireRows() {
    m.bg.querySelectorAll('.ap-seg button').forEach(function (b) {
      b.addEventListener('click', function () {
        var i = +b.closest('.ap-seg').getAttribute('data-i');
        rows[i].src = b.getAttribute('data-attr');
        renderParsed();
      });
    });
    m.bg.querySelectorAll('.ap-setup').forEach(function (inp) {
      inp.addEventListener('input', function () { rows[+inp.getAttribute('data-i')].setup = inp.value.trim(); });
    });
    m.bg.querySelectorAll('.ap-unit').forEach(function (inp) {
      inp.addEventListener('input', function () { rows[+inp.getAttribute('data-i')].unit = inp.value.trim(); refreshSum(); });
    });
  }
  function refreshSum() {
    var s = stats(), sum = m.bg.querySelector('.ap-sum');
    var iN = sum.querySelector('.ap-intn'), eN = sum.querySelector('.ap-extn'), mS = sum.querySelector('.ap-miss');
    if (iN) iN.textContent = s.intN;
    if (eN) eN.textContent = s.extN;
    if (mS) { mS.textContent = s.missing; var st = mS.closest('.stat'); if (st) { st.classList.toggle('warn', !!s.missing); st.classList.toggle('ok', !s.missing); st.setAttribute('data-tone', s.missing ? 'warn' : 'ok'); } }
  }
  function renderParsed() {
    m.bg.querySelector('.ap-parsed').innerHTML = tableHtml();
    m.bg.querySelector('.ap-sum').innerHTML = summaryHtml();
    wireRows();
  }

  var ta = m.bg.querySelector('.ap-route');
  ta.addEventListener('input', function () { reparse(ta.value); ta.closest('.field').classList.remove('err'); renderParsed(); });
  renderParsed();

  m.bg.querySelector('.ap-save').addEventListener('click', function () {
    var codeEl = m.bg.querySelector('.ap-code'), nameEl = m.bg.querySelector('.ap-name');
    var code = (codeEl.value || '').trim(), name = (nameEl.value || '').trim(), bad = null;
    [[codeEl, code], [nameEl, name]].forEach(function (p) { p[0].closest('.field').classList.toggle('err', !p[1]); if (!p[1] && !bad) bad = p[0]; });
    if (bad) { bad.focus(); showFlash('请先填写图号与名称。'); return; }
    if (!rows.length) { ta.closest('.field').classList.add('err'); ta.focus(); showFlash('请先录入工艺路线。'); return; }
    if (PART_META[code]) { codeEl.closest('.field').classList.add('err'); codeEl.focus(); showFlash('图号 ' + code + ' 已存在。'); return; }

    var ops = rows.map(function (r) {
      var ext = r.src === 'ext';
      return { seq: r.seq, op: r.op, dev: ext ? '外协 · 待定供应商' : '—', src: r.src, setup: ext ? '' : (r.setup || '0'), unit: ext ? '' : r.unit, ext: ext ? '外协 · 待定周期' : '' };
    });
    rows.forEach(function (r) { if (classifyOp(r.op) === 'unknown') addPending(r.op, code + ' ' + name); });
    var intRows = ops.filter(function (o) { return o.src === 'int'; });
    var allFilled = intRows.length > 0 && intRows.every(function (o) { return o.unit !== '' && Number(o.unit) !== 0; });

    PART_META[code] = { name: name, parsed: true };
    PART_OPS[code] = ops;
    PART_STAGE[code] = { route: 'done', attr: 'done', hours: allFilled ? 'done' : 'pending' };
    PART_CODES.unshift(code);
    state.stageFilter = 'all';

    m.close();
    render();
    showFlash('已新增「' + code + ' ' + name + '」· ' + ops.length + ' 道工序，' + (allFilled ? '三步齐备，已就绪' : '待补工时') + '（示例数据，刷新后恢复）。');
  });

  var f = m.bg.querySelector('.ap-code');
  if (f) f.focus();
}

function showFormModal(entity) {  var cfg = FORMS[entity];
  if (!cfg) return;
  var grid = '<div class="fgrid">' + cfg.fields.map(fieldHtml).join('') + '</div>';
  var m = openModal('<div class="modal lg" role="dialog" aria-modal="true">' +
    modalHead(cfg.icon, cfg.title, cfg.sub) +
    '<div class="modal-b form">' + grid + '</div>' +
    '<div class="modal-f wb-actions"><button class="btn" data-close>取消</button><button class="btn primary save wb-action wb-primary">保存并加入列表</button></div></div>');
  m.bg.querySelectorAll('.fchip').forEach(function (c) {
    c.addEventListener('click', function () { c.classList.toggle('on'); });
  });
  m.bg.querySelectorAll('.selbox').forEach(function (box) {
    box.querySelector('.selbtn').addEventListener('click', function (e) {
      e.stopPropagation();
      var wasOpen = box.classList.contains('open');
      closeAllSel(m.bg);
      if (!wasOpen) openSel(box);
    });
    box.querySelectorAll('.selopt').forEach(function (opt) {
      opt.addEventListener('click', function (e) {
        e.stopPropagation();
        var v = opt.getAttribute('data-v');
        box.setAttribute('data-val', v);
        box.querySelector('.selval').textContent = v;
        box.querySelectorAll('.selopt').forEach(function (o) { o.classList.toggle('on', o === opt); });
        closeAllSel(m.bg);
      });
    });
  });
  m.bg.querySelector('.modal-b').addEventListener('click', function () { closeAllSel(m.bg); });
  m.bg.querySelector('.save').addEventListener('click', function () {
    var vals = {}, bad = null;
    cfg.fields.forEach(function (f) {
      var wrap, val;
      if (f.type === 'chips') { wrap = m.bg.querySelector('[data-k="' + f.k + '"]'); val = [].slice.call(wrap.querySelectorAll('.fchip.on')).map(function (x) { return x.getAttribute('data-v'); }); }
      else if (f.type === 'select') { val = m.bg.querySelector('[data-k="' + f.k + '"]').getAttribute('data-val'); }
      else { var elx = m.bg.querySelector('[data-k="' + f.k + '"]'); val = (elx.value || '').trim(); if (f.req && !val) { if (!bad) bad = elx; elx.closest('.field').classList.add('err'); } else { elx.closest('.field').classList.remove('err'); } }
      vals[f.k] = val;
    });
    if (bad) { bad.focus(); showFlash('请先填写带 * 的必填项。'); return; }
    addRowToTable(buildRow(entity, vals));
    m.close();
    showFlash('已新增「' + (vals.name || vals.code) + '」（示例数据，刷新后恢复）。');
  });
  var first = m.bg.querySelector('input, textarea, select');
  if (first) first.focus();
}

/* ---------------- 批量导入 / 导出 ---------------- */
var IO_LABEL = { part: '零件工艺', material: '物料', op_int: '自制工种', equip: '设备', people: '人员', op_ext: '外协工种', supplier: '供应商', route: '工艺路线（工艺室）', hours: '工时定额（定额室）' };
function showImportExport(entity, mode) {
  mode = mode === 'exp' ? 'exp' : 'imp';
  var label = IO_LABEL[entity] || '数据';
  var isImp = mode === 'imp';
  var body = isImp ?
    '<div class="iopane on" data-pane="imp">' +
      '<div class="tmpl-row"><span class="tmpl-ico"><svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M7 3h7l5 5v13H7z"/><path d="M14 3v5h5"/><path d="M9.5 13l1.8 1.8L15 11"/></svg></span>' +
        '<div><div class="tmpl-t">' + label + '导入模板.xlsx</div><div class="tmpl-s">含字段说明与示例行，按模板填写后上传</div></div>' +
        '<button class="mini dl-tmpl wb-action wb-transfer" data-wb-transfer="template">' + window.APSWorkbenchUI.iconMarkup('template') + '下载模板</button></div>' +
      '<div class="drop" id="io-drop"><div class="di"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 16V4M7 9l5-5 5 5"/><path d="M5 16v4h14v-4"/></svg></div>' +
        '<div class="dt">点击选择文件，或拖拽到此处</div><div class="ds">支持 .xlsx / .csv，单次最多 2,000 行</div></div>' +
      '<div class="iohint">导入采用<b>「按编号增量更新」</b>：编号已存在则更新，不存在则新增。被引用项的关键字段变更会二次确认。</div>' +
    '</div>'
  :
    '<div class="iopane on" data-pane="exp">' +
      '<div class="seclabel">导出范围</div>' +
      '<div class="iorow on" data-scope="cur"><span class="radio"></span><div><div class="iotitle">当前筛选结果</div><div class="iosub">按当前搜索 / 子页范围导出</div></div><span class="iotag">本页</span></div>' +
      '<div class="iorow" data-scope="all"><span class="radio"></span><div><div class="iotitle">全部 ' + label + '</div><div class="iosub">忽略筛选，导出整张表</div></div></div>' +
      '<div class="seclabel" style="margin-top:14px">文件格式</div>' +
      '<div class="seg"><button class="on" data-fmt="xlsx">Excel (.xlsx)</button><button data-fmt="csv">CSV (.csv)</button></div>' +
    '</div>';
  var m = openModal('<div class="modal' + (isImp ? ' lg' : '') + '" role="dialog" aria-modal="true">' +
    modalHead(isImp ? 'import' : 'export',
      (isImp ? '批量导入 · ' : '批量导出 · ') + label,
      isImp ? ('从 Excel / CSV 成批导入' + label + '数据。') : ('把' + label + '导出为 Excel / CSV 文件。')) +
    '<div class="modal-b scroll">' + body + '</div>' +
    '<div class="modal-f wb-actions"><button class="btn" data-close>取消</button><button class="btn primary io-do wb-action wb-transfer wb-primary" data-wb-transfer="' + (isImp ? 'import' : 'export') + '">' + window.APSWorkbenchUI.iconMarkup(isImp ? 'import' : 'export') + (isImp ? '确认导入' : '导出文件') + '</button></div></div>');
  if (isImp) {
    m.bg.querySelector('.dl-tmpl').addEventListener('click', function (e) { e.stopPropagation(); showFlash('已下载「' + label + '导入模板.xlsx」（示例）。'); });
    var drop = m.bg.querySelector('#io-drop');
    drop.addEventListener('click', function () {
      drop.classList.add('has');
      drop.querySelector('.dt').innerHTML = '<b>' + label + '_示例.xlsx</b> · 128 行待导入';
      drop.querySelector('.ds').textContent = '校验通过：可导入 126 行，2 行编号冲突将更新';
    });
  } else {
    m.bg.querySelectorAll('.iorow').forEach(function (r) {
      r.addEventListener('click', function () { m.bg.querySelectorAll('.iorow').forEach(function (x) { x.classList.toggle('on', x === r); }); });
    });
    m.bg.querySelectorAll('.seg button').forEach(function (b) {
      b.addEventListener('click', function () { m.bg.querySelectorAll('.seg button').forEach(function (x) { x.classList.toggle('on', x === b); }); });
    });
  }
  m.bg.querySelector('.io-do').addEventListener('click', function () {
    m.close();
    if (isImp) showFlash('已导入 ' + label + ' 126 行 · 更新 2 行（示例）。');
    else { var fmt = m.bg.querySelector('.seg button.on').getAttribute('data-fmt'); showFlash('已导出 ' + label + ' 列表（.' + fmt + '，示例）。'); }
  });
}

var _toastT;
function showFlash(msg) {
  var t = document.getElementById('toast');
  if (!t) { t = document.createElement('div'); t.id = 'toast'; t.className = 'toast'; root.appendChild(t); }
  t.innerHTML = '<span class="tdot"></span><span>' + msg + '</span>';
  t.classList.add('on');
  clearTimeout(_toastT);
  _toastT = setTimeout(function () { t.classList.remove('on'); }, 2800);
  window.dispatchEvent(new Event('aps:master-data-changed'));
}

function render() { renderRail(); renderContent(); if (partModal) partModal.repaint(); }

// The native prototype owns both closure data and temporary table-only edits.
// Move its existing subtree on remount; never re-seed or turn display totals into records.
function getSessionSnapshot() {
  var lists = { material: MATERIALS, op_int: OP_INT, equip: EQUIP, people: PEOPLE, op_ext: OP_EXT, supplier: SUPPLIERS };
  var visible = state.node === 'material' ? 'material' :
    state.node === 'internal' ? { op: 'op_int', eq: 'equip', pp: 'people' }[state.sub.internal] :
    state.node === 'external' ? { op: 'op_ext', sup: 'supplier' }[state.sub.external] : null;
  var tables = [].slice.call(root.querySelectorAll('#content table.tbl'));
  var activeTable = tables.filter(function (t) { return !t.closest('.pend-card'); })[0];
  if (visible && activeTable) {
    lists[visible] = [].slice.call(activeTable.querySelectorAll('tbody tr')).map(function (tr) {
      return [].slice.call(tr.cells).slice(1).map(function (cell) { return cell.innerHTML; });
    });
  }
  return JSON.parse(JSON.stringify({
    schemaVersion: 1, source: 'native-session', sample: true,
    parts: PART_CODES.map(function (code) {
      return { code: code, meta: PART_META[code], operations: PART_OPS[code] || [], stage: partStageOf(code) };
    }),
    lists: lists, calendar: calState, pendingOpTypes: PENDING_OPTYPES,
    knownOpTypes: { internal: KNOWN_INT, external: KNOWN_EXT }, visibleList: visible,
    visibleListIsTemporary: !!visible
  }));
}
function navigateSession(target) {
  if (!root.isConnected) return false;
  if (partModal) partModal.close();
  root.querySelectorAll('.modal-bg').forEach(function (bg) {
    var close = bg.querySelector('[data-close], .cancel'); if (close) close.click();
  });
  root.querySelectorAll('[data-md-located]').forEach(function (el) { el.removeAttribute('data-md-located'); el.removeAttribute('aria-current'); el.classList.remove('md-native-located'); });
  var domain = target.domain;
  if (domain === 'part' || domain === 'route') {
    var code = target.partCode || target.code;
    state.node = 'process'; state.stageFilter = 'all'; render();
    if (!PART_META[code]) { showFlash('未找到零件「' + code + '」，记录可能已变化。'); return false; }
    openPartModal(code);
    var stages = partStageOf(code);
    var allowedStage = target.stage === 'route' || target.stage === 'attr' && stages.route === 'done' ||
      target.stage === 'hours' && stages.route === 'done' && stages.attr === 'done' ||
      target.stage === 'ready' && stageBucket(code) === 'ready';
    if (allowedStage) {
      state.openStage = target.stage; partModal.repaint();
    }
    return true;
  }
  var next = domain === 'material' ? ['material'] : domain === 'calendar' ? ['calendar'] :
    domain === 'equipment' ? ['internal', 'eq'] : domain === 'personnel' ? ['internal', 'pp'] :
    domain === 'supplier' ? ['external', 'sup'] : [target.chain === 'external' ? 'external' : 'internal', 'op'];
  var changed = state.node !== next[0] || (next[1] && state.sub[next[0]] !== next[1]);
  state.node = next[0]; if (next[1]) state.sub[next[0]] = next[1];
  if (domain === 'calendar') {
    var date = /^(\d{4})-(\d{2})-(\d{2})$/.exec(target.code || '');
    if (!date) { showFlash('未找到对应日历日期。'); return false; }
    calState.y = +date[1]; calState.m = +date[2] - 1;
    render(); openDayModal(+date[3]); return true;
  }
  if (changed) render();
  var found = [].slice.call(root.querySelectorAll('#content tbody tr')).find(function (tr) {
    var label = tr.querySelector('.lnk') || tr.querySelector('b');
    return label && label.textContent.trim() === (target.code || target.name);
  });
  if (!found) { showFlash('未找到「' + (target.code || target.name) + '」，记录可能已变化。'); return false; }
  found.setAttribute('data-md-located', 'true'); found.setAttribute('aria-current', 'true'); found.classList.add('md-native-located'); found.tabIndex = -1;
  found.focus(); if (found.scrollIntoView) found.scrollIntoView({ block: 'center' });
  return true;
}
var hasRendered = false;
session = {
  getSnapshot: getSessionSnapshot, navigate: navigateSession, isAttached: function () { return root.isConnected; },
  attach: function (nextRoot, nextNav) {
    if (root !== nextRoot) { while (root.firstChild) nextRoot.appendChild(root.firstChild); root = nextRoot; }
    onNav = nextNav;
    if (!hasRendered && root.isConnected) { hasRendered = true; render(); }
    window.APSPlanAData.applyNavigation();
  }
};
if (root.isConnected) { hasRendered = true; render(); }

/* ---- 统一详情：表格内编号 / 行内「查看」按钮 → 详情抽屉；「删除」→ 确认 ---- */
var contentEl = root.querySelector('#content') || document.getElementById('content');
if (contentEl && window.APSDetail) {
  contentEl.addEventListener('click', function (e) {
    // 编号链接（排除工艺零件列表，那里点编号进三步详情）
    var lnk = e.target.closest('a.lnk');
    if (lnk && !e.target.closest('tr[data-code]')) {
      var code = (lnk.textContent || '').trim();
      if (window.APSDetail.has(code)) { e.preventDefault(); e.stopPropagation(); window.APSDetail.open(code); return; }
    }
    // 行内操作按钮
    var mini = e.target.closest('.rowact .mini');
    if (mini) {
      var tr = mini.closest('tr');
      var lk = tr && tr.querySelector('.lnk');
      var rc = lk ? (lk.textContent || '').trim() : '';
      if (mini.classList.contains('danger')) {
        if (rc) {
          e.preventDefault();
          showConfirm({ title: '删除「' + rc + '」？', body: '若该项被<b>工序 / 批次 / 资源</b>引用，将删除失败并提示。确认继续吗？', ok: '确认删除', onOk: function () { if (tr && tr.parentNode) tr.parentNode.removeChild(tr); if (currentUpd) currentUpd(); showFlash('已删除「' + rc + '」（示例数据，刷新后恢复）。'); } });
        }
        return;
      }
      if (rc && window.APSDetail.has(rc)) { e.preventDefault(); e.stopPropagation(); window.APSDetail.open(rc); }
    }
  });
}

window.APSPlanAData.applyNavigation();
return session;
};
})();
