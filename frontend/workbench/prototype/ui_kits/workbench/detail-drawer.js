// APS Workbench · 统一详情抽屉 + 轻提示
// One shared, framework-agnostic right-side drawer for every clickable code/record
// across the app (物料 / 零件 / 工种 / 设备 / 人员 / 供应商 / 批次 / 方案 …).
// Both plana-logic.js (light DOM) and the React screens call window.APSDetail.open(code).
// Styling uses the same --ui-* tokens as the rest of the kit so light/dark both work.
(function () {
  if (window.APSDetail) return;

  var GANTT_LOCATE_LABEL = '在甘特图中定位此批次';

  /* ---------------- one-time CSS ---------------- */
  var CSS = `
  .apsd-backdrop { position: fixed; inset: 0; background: rgb(15 23 42 / .42); z-index: 240; opacity: 0; transition: opacity .18s ease; }
  .apsd-backdrop.on { opacity: 1; }
  .apsd-panel { position: fixed; top: 50%; left: 50%; width: min(516px, 94vw); max-height: min(88vh, 860px); background: var(--ui-card-bg); border: 1px solid var(--ui-border); border-radius: var(--wb-radius-overlay); box-shadow: 0 32px 80px -28px rgb(15 23 42 / .55), 0 8px 24px -16px rgb(15 23 42 / .4); z-index: 241; display: flex; flex-direction: column; overflow: hidden; transform: translate(-50%, -48%) scale(.96); opacity: 0; transition: transform .22s cubic-bezier(.32,.72,0,1), opacity .18s ease; font-family: var(--font-family); color: var(--ui-text); }
  .apsd-panel.on { transform: translate(-50%, -50%) scale(1); opacity: 1; }
  @media (prefers-reduced-motion: reduce) { .apsd-backdrop, .apsd-panel { transition: none; } }

  .apsd-head { display: flex; align-items: flex-start; gap: 13px; padding: 20px 20px 16px; border-bottom: 1px solid var(--ui-border); }
  .apsd-ico { width: 40px; height: 40px; border-radius: var(--wb-radius-surface); background: var(--ui-primary-soft, var(--ui-surface-muted)); color: var(--ui-primary); display: grid; place-items: center; flex: none; }
  .apsd-htext { flex: 1; min-width: 0; }
  .apsd-kicker { font-size: 11.5px; font-weight: 600; letter-spacing: .03em; color: var(--ui-muted); }
  .apsd-code { font-size: 19px; font-weight: 700; line-height: 1.25; font-variant-numeric: tabular-nums; word-break: break-all; }
  .apsd-name { font-size: 13.5px; color: var(--ui-muted); margin-top: 2px; }
  .apsd-x { flex: none; width: 32px; height: 32px; border: 1px solid var(--ui-border); border-radius: var(--wb-radius-control); background: var(--ui-card-bg); color: var(--ui-muted); font-size: 17px; line-height: 1; cursor: pointer; display: grid; place-items: center; transition: background-color .15s, color .15s; }
  .apsd-x:hover { background: var(--ui-surface-muted); color: var(--ui-text); }

  .apsd-statusrow { display: flex; flex-wrap: wrap; gap: 8px; padding: 14px 20px 0; }
  .apsd-body { flex: 1; overflow-y: auto; padding: 16px 20px 22px; }
  .apsd-sec { margin-top: 18px; }
  .apsd-sec:first-child { margin-top: 8px; }
  .apsd-sec-t { font-size: 12px; font-weight: 700; letter-spacing: .04em; color: var(--ui-muted); text-transform: none; margin-bottom: 10px; }
  .apsd-rows { display: grid; grid-template-columns: 104px 1fr; gap: 9px 14px; }
  .apsd-rl { font-size: 13px; color: var(--ui-muted); }
  .apsd-rv { font-size: 13.5px; color: var(--ui-text); font-variant-numeric: tabular-nums; line-height: 1.5; }
  .apsd-rv .apsd-strong { font-weight: 700; }

  .apsd-pill { display: inline-flex; align-items: center; gap: 6px; padding: 3px 11px; border-radius: var(--wb-radius-control); font-size: 12px; font-weight: 700; border: 1px solid transparent; white-space: nowrap; }
  .apsd-pill .d { width: 6px; height: 6px; border-radius: 50%; flex: none; }
  .apsd-pill.ok { background: var(--ui-success-bg); border-color: var(--ui-success-border); color: var(--ui-success-text); } .apsd-pill.ok .d { background: var(--ui-success); }
  .apsd-pill.warn { background: var(--ui-warning-bg); border-color: var(--ui-warning-border); color: var(--ui-warning-text); } .apsd-pill.warn .d { background: var(--ui-warning); }
  .apsd-pill.danger { background: var(--ui-danger-bg); border-color: var(--ui-danger-border); color: var(--ui-danger-text); } .apsd-pill.danger .d { background: var(--ui-danger); }
  .apsd-pill.info { background: var(--ui-info-bg); border-color: var(--ui-info-border); color: var(--ui-info-text); } .apsd-pill.info .d { background: var(--ui-primary); }
  .apsd-pill.off { background: var(--ui-surface-muted); border-color: var(--ui-border); color: var(--ui-muted); } .apsd-pill.off .d { background: var(--ui-muted); }

  .apsd-chips { display: flex; flex-wrap: wrap; gap: 6px; }
  .apsd-chip { display: inline-flex; align-items: center; padding: 2px 9px; border-radius: var(--wb-radius-control); font-size: 12px; font-weight: 600; background: var(--ui-surface-muted); border: 1px solid var(--ui-border); color: var(--ui-text); }
  .apsd-chip.a { background: var(--ui-info-bg); border-color: var(--ui-info-border); color: var(--ui-info-text); }
  .apsd-link { color: var(--ui-primary); font-weight: 600; cursor: pointer; text-decoration: none; font-variant-numeric: tabular-nums; }
  .apsd-link:hover { text-decoration: underline; }

  .apsd-relrow { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 9px 0; border-bottom: 1px solid var(--ui-border); }
  .apsd-relrow:last-child { border-bottom: 0; }
  .apsd-relmeta { font-size: 12.5px; color: var(--ui-muted); }

  .apsd-mini { border: 1px solid var(--ui-border); border-radius: var(--wb-radius-surface); overflow: hidden; }
  .apsd-mini table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
  .apsd-mini th { text-align: left; font-weight: 600; color: var(--ui-muted); background: var(--ui-surface-muted); padding: 7px 10px; border-bottom: 1px solid var(--ui-border); white-space: nowrap; }
  .apsd-mini td { padding: 7px 10px; border-bottom: 1px solid var(--ui-border); color: var(--ui-text); }
  .apsd-mini tr:last-child td { border-bottom: 0; }
  .apsd-mini td.r, .apsd-mini th.r { text-align: right; font-variant-numeric: tabular-nums; }

  .apsd-note { font-size: 12.5px; color: var(--ui-muted); line-height: 1.65; background: var(--ui-surface-muted); border: 1px solid var(--ui-border); border-radius: var(--wb-radius-surface); padding: 11px 13px; }

  .apsd-meter { height: 8px; border-radius: var(--wb-radius-control); background: var(--ui-surface-muted); overflow: hidden; margin-top: 6px; }
  .apsd-meter i { display: block; height: 100%; border-radius: var(--wb-radius-control); background: var(--ui-primary); }
  .apsd-meter.warn i { background: var(--ui-warning); } .apsd-meter.danger i { background: var(--ui-danger); } .apsd-meter.ok i { background: var(--ui-success); }

  .apsd-foot { display: flex; gap: 10px; padding: 14px 20px; border-top: 1px solid var(--ui-border); background: var(--ui-surface-muted); }
  .apsd-btn { flex: 1; min-height: 38px; padding: 0 14px; border: 1px solid var(--ui-border); border-radius: var(--wb-radius-control); background: var(--ui-card-bg); color: var(--ui-text); font-family: inherit; font-size: 13.5px; font-weight: 600; cursor: pointer; transition: background-color .15s, border-color .15s; }
  .apsd-btn:hover { background: var(--ui-surface-muted); }
  .apsd-btn.primary { background: var(--ui-primary); border-color: var(--ui-primary); color: #fff; }
  .apsd-btn.primary:hover { filter: brightness(.96); background: var(--ui-primary); }

  .apsd-toast { position: fixed; left: 50%; bottom: 28px; transform: translate(-50%, 16px); z-index: 260; display: flex; align-items: center; gap: 9px; max-width: min(440px, 90vw); padding: 11px 16px; border-radius: var(--wb-radius-overlay); background: var(--ui-text); color: var(--ui-bg); font-family: var(--font-family); font-size: 13px; box-shadow: 0 12px 30px -10px rgb(15 23 42 / .5); opacity: 0; pointer-events: none; transition: opacity .2s ease, transform .2s ease; }
  .apsd-toast.on { opacity: 1; transform: translate(-50%, 0); }
  .apsd-toast .d { width: 7px; height: 7px; border-radius: 50%; background: var(--ui-success); flex: none; }
  `;
  var st = document.createElement('style');
  st.id = 'apsd-style';
  st.textContent = CSS;
  document.head.appendChild(st);

  /* ---------------- icons ---------------- */
  var ICO = {
    cube: '<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z"/><path d="M12 12l8-4.5M12 12v9M12 12L4 7.5"/>',
    route: '<circle cx="6" cy="6" r="2.4"/><circle cx="18" cy="18" r="2.4"/><path d="M8.4 6H15a3 3 0 010 6H9a3 3 0 000 6h6.6"/>',
    wrench: '<path d="M15 5.2a3.6 3.6 0 00-4.7 4.6L4 16.1 7.9 20l6.3-6.3A3.6 3.6 0 0018.8 9l-2.2 2.2-2-2L16.8 7z"/>',
    machine: '<path d="M3 20h18"/><path d="M5 20V9l5 3V9l5 3V6l4 2v12"/>',
    users: '<circle cx="9" cy="8" r="3"/><path d="M3 20c0-3.3 3-5 6-5s6 1.7 6 5"/><path d="M16 5.5a3 3 0 010 6M21.5 20c0-2.2-1.2-3.6-3.2-4.3"/>',
    truck: '<path d="M3 6h11v9H3z"/><path d="M14 9h3.5L21 12.2V15h-7z"/><circle cx="7" cy="18" r="1.9"/><circle cx="17" cy="18" r="1.9"/>',
    box: '<path d="M3 7l9-4 9 4v10l-9 4-9-4V7z"/><path d="M3 7l9 4 9-4M12 11v10"/>',
    chart: '<path d="M4 5v15h16"/><path d="M7 14l4-4 3 3 5-6"/>',
    scale: '<path d="M12 4v16M7 21h10"/><path d="M5 8h14M12 4l7 4M12 4L5 8"/><path d="M5 8l-2.6 5h5.2zM19 8l-2.6 5h5.2z"/>',
  };
  function svg(name) {
    return '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + (ICO[name] || ICO.box) + '</svg>';
  }

  /* ---------------- helpers ---------------- */
  function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
  function pill(tone, label) { return '<span class="apsd-pill ' + tone + '"><span class="d"></span>' + esc(label) + '</span>'; }
  function chips(arr, cls) { return '<span class="apsd-chips">' + (arr || []).map(function (x) { return '<span class="apsd-chip ' + (cls || '') + '">' + esc(x) + '</span>'; }).join('') + '</span>'; }
  function rows(pairs) {
    return '<div class="apsd-rows">' + pairs.filter(Boolean).map(function (p) {
      return '<div class="apsd-rl">' + esc(p[0]) + '</div><div class="apsd-rv">' + (p[1] == null ? '<span style="color:var(--ui-muted)">—</span>' : p[1]) + '</div>';
    }).join('') + '</div>';
  }
  function sec(title, html) { return '<div class="apsd-sec">' + (title ? '<div class="apsd-sec-t">' + esc(title) + '</div>' : '') + html + '</div>'; }
  function relList(items) {
    // items: {code, meta} -> clickable cross-links
    return '<div>' + items.map(function (it) {
      var right = it.meta ? '<span class="apsd-relmeta">' + esc(it.meta) + '</span>' : '';
      var left = RECORDS[it.code]
        ? '<a class="apsd-link" data-apsd-go="' + esc(it.code) + '">' + esc(it.label || it.code) + '</a>'
        : '<span class="apsd-strong">' + esc(it.label || it.code) + '</span>';
      return '<div class="apsd-relrow">' + left + right + '</div>';
    }).join('') + '</div>';
  }
  function miniTable(head, body) {
    return '<div class="apsd-mini"><table><thead><tr>' + head + '</tr></thead><tbody>' + body + '</tbody></table></div>';
  }

  /* ---------------- type config ---------------- */
  var TYPES = {
    material: { icon: 'cube', kicker: '物料主数据' },
    part:     { icon: 'route', kicker: '零件工艺' },
    op_int:   { icon: 'wrench', kicker: '自制工种 · 工时口径' },
    op_ext:   { icon: 'wrench', kicker: '外协工种 · 周期口径' },
    equip:    { icon: 'machine', kicker: '设备资源' },
    people:   { icon: 'users', kicker: '人员资源' },
    supplier: { icon: 'truck', kicker: '外协供应商' },
    batch:    { icon: 'box', kicker: '生产批次' },
    plan:     { icon: 'chart', kicker: '排产方案' },
    calib:    { icon: 'scale', kicker: '工时定额校准' },
  };

  /* ---------------- records ---------------- */
  // status: [tone, label]; body(rec) returns inner HTML; foot optional.
  function R(o) { RECORDS[o.code] = o; }
  var RECORDS = {};

  // —— 物料 ——
  [
    ['M-2001', '45# 圆钢 Ø120', ['ok', '启用'], 'Ø120 × 2000', '1,240 kg', 'kg', ['T-1008', 'T-1009']],
    ['M-2008', '6061 铝板 12mm', ['ok', '启用'], '1220 × 2440', '86 张', '张', ['T-1021']],
    ['M-2015', '40Cr 锻件毛坯', ['warn', '低库存'], 'Ø200 锻坯', '32 件', '件', ['T-1011']],
    ['M-2031', '不锈钢 304 棒', ['ok', '启用'], 'Ø60 × 3000', '410 kg', 'kg', []],
    ['M-2044', '紧固件套件 A', ['off', '停用'], 'M8 / M10 混装', '2,300 套', '套', []],
    ['WL-2201', '45# 钢棒料', ['ok', '已齐套'], 'Ø120 棒料', '齐套率 100%', 'kg', ['T-1008']],
    ['WL-2208', '铸铝件', ['warn', '待补料'], '铸铝毛坯', '齐套率 80%', '件', ['T-1009']],
    ['WL-2215', '密封圈', ['danger', '缺料'], '橡胶密封', '齐套率 60%', '件', ['T-1004']],
  ].forEach(function (m) {
    R({ type: 'material', code: m[0], name: m[1], status: m[2], body: function () {
      return rows([['规格', esc(m[3])], ['库存', '<span class="apsd-strong">' + esc(m[4]) + '</span>'], ['计量单位', esc(m[5])], ['状态', pill(m[2][0], m[2][1])]]) +
        (m[6].length ? sec('被以下零件引用', relList(m[6].map(function (c) { return { code: c, meta: (PARTNAME[c] || '') }; }))) : '') +
        sec('', '<div class="apsd-note">物料主数据；批次物料需求在「批次管理」里按批引用这里的主数据。低库存 / 缺料会影响批次齐套结果。</div>');
    }, foot: ['编辑物料', '调整库存'] });
  });

  // —— 零件 / 工艺 ——
  var PARTNAME = { 'T-1008': '回转壳体 A', 'T-1009': '回转壳体 B', 'T-1011': '端盖 C', 'T-1014': '法兰 D', 'T-1021': '支座 E', 'T-1006': '轴套 F', 'T-1004': '连接板 G', 'P-1042': '泵体 H', 'P-1008': '回转壳体 A', 'P-1009': '回转壳体 B', 'P-1011': '端盖 C' };
  var PART_ROUTE = {
    'T-1008': [['5', '数铣', '自制'], ['10', '钳工', '自制'], ['20', '数车', '自制'], ['30', '电镀', '外协'], ['35', '发黑', '外协'], ['40', '总检', '自制']],
    'T-1009': [['5', '数铣', '自制'], ['10', '钳工', '自制'], ['20', '数车', '自制'], ['30', '精磨', '自制'], ['40', '总检', '自制']],
    'T-1011': [['5', '数车', '自制'], ['10', '钻孔', '自制'], ['20', '热处理', '外协'], ['25', '喷涂', '外协'], ['30', '总检', '自制']],
    'T-1021': [['5', '数铣', '自制'], ['10', '数车', '自制'], ['20', '钻孔', '自制'], ['30', '发黑', '外协'], ['40', '总检', '自制'], ['45', '表处理', '自制']],
    'P-1042': [['20', '数铣', '自制'], ['30', '钳工', '自制'], ['50', '总检', '自制']],
  };
  [
    ['T-1008', ['ok', '已解析'], '42.5h', '自制 5 · 外协 2'],
    ['T-1009', ['ok', '已解析'], '38.0h', '自制 5'],
    ['T-1011', ['warn', '待复核'], '21.0h', '自制 3 · 外协 2'],
    ['T-1014', ['warn', '未解析'], '—', '待生成'],
    ['T-1021', ['ok', '已解析'], '36.0h', '自制 4 · 外协 1'],
    ['T-1006', ['ok', '已解析'], '28.0h', '自制 4'],
    ['T-1004', ['notice', '草稿'], '12.5h', '待生成'],
    ['P-1042', ['ok', '已解析'], '32.0h', '自制 3'],
  ].forEach(function (p) {
    var rt = PART_ROUTE[p[0]];
    R({ type: 'part', code: p[0], name: PARTNAME[p[0]] || '', status: p[1], body: function () {
      var info = rows([['名称', esc(PARTNAME[p[0]] || '—')], ['标准工时', '<span class="apsd-strong">' + esc(p[2]) + '</span>'], ['自制 / 外协', esc(p[3])], ['解析状态', pill(p[1][0], p[1][1])]]);
      var routeSec = rt ? sec('工艺路线 · ' + rt.length + ' 道工序', miniTable(
        '<th style="width:54px">工序</th><th>工种</th><th class="r" style="width:70px">归属</th>',
        rt.map(function (o) {
          var attr = o[2] === '外协' ? '<span class="apsd-chip a">外协</span>' : '<span class="apsd-chip">自制</span>';
          return '<tr><td class="r"><b>' + o[0] + '</b></td><td>' + esc(o[1]) + '</td><td class="r">' + attr + '</td></tr>';
        }).join('')
      )) : sec('', '<div class="apsd-note">该零件尚未导入工艺路线，按 ① 路线 → ② 归属 → ③ 工时 三步推进后即可参与排产。</div>');
      return info + routeSec;
    }, foot: ['打开工艺详情', '导出清单'] });
  });

  // —— 自制工种 ——
  [
    ['OT001', '数铣', '6', '14', '主力工序，设备充足', ['EQ-01'], ['P-101', 'P-133']],
    ['OT002', '数车', '5', '11', '—', ['EQ-04'], ['P-101', 'P-133']],
    ['OT003', '钳工', '3', '9', '瓶颈工序，人员偏紧', ['EQ-12'], ['P-126', 'P-133']],
    ['OT004', '精磨', '2', '6', '关键工序', ['EQ-09'], ['P-118']],
    ['OT006', '总检', '1', '4', '关键工序 · 必检', [], ['P-118']],
  ].forEach(function (o) {
    R({ type: 'op_int', code: o[0], name: o[1], status: ['info', '自制'], body: function () {
      return rows([['工种名称', '<span class="apsd-strong">' + esc(o[1]) + '</span>'], ['可用设备', esc(o[2]) + ' 台'], ['可用人员', esc(o[3]) + ' 人'], ['排产口径', '工时（换型 + 单件）'], ['产能备注', o[4] === '—' ? null : esc(o[4])]]) +
        (o[5].length ? sec('关联设备', relList(o[5].map(function (c) { return { code: c, meta: EQUIPNAME[c] || '' }; }))) : '') +
        (o[6].length ? sec('可承接人员', relList(o[6].map(function (c) { return { code: c, meta: PEOPLENAME[c] || '' }; }))) : '');
    }, foot: ['查看绑定', '编辑工种'] });
  });

  // —— 外协工种 ——
  [
    ['OT051', '电镀', '分别设置', '常用表面处理，多家供应商', ['S-01', 'S-07']],
    ['OT052', '发黑', '分别设置', '—', ['S-01']],
    ['OT053', '热处理', '合并设置', '需炉前确认整组周期', ['S-02']],
    ['OT054', '喷涂', '分别设置', '单一供应商', ['S-05']],
  ].forEach(function (o) {
    R({ type: 'op_ext', code: o[0], name: o[1], status: ['info', '外协'], body: function () {
      return rows([['工种名称', '<span class="apsd-strong">' + esc(o[1]) + '</span>'], ['周期策略', esc(o[2])], ['排产口径', '周期（天）'], ['备注', o[3] === '—' ? null : esc(o[3])]]) +
        (o[4].length ? sec('可承接供应商', relList(o[4].map(function (c) { return { code: c, meta: SUPNAME[c] || '' }; }))) : '');
    }, foot: ['查看供应商', '编辑工种'] });
  });

  // —— 设备 ——
  var EQUIPNAME = { 'EQ-01': '立式加工中心 VMC-850', 'EQ-04': '数控车床 CK-6150', 'EQ-09': '平面磨床 M7140', 'EQ-12': '钳工台 · 联合', 'M-03': '五轴加工中心', 'M-05': '卧式加工中心', 'M-07': '立式加工中心', 'M-12': '三坐标检测', 'M-18': '数控车床', 'M-21': '线切割' };
  [
    ['EQ-01', '立式加工中心 VMC-850', '数铣', '设备组 A', ['ok', '可用'], null, null],
    ['EQ-04', '数控车床 CK-6150', '数车', '设备组 A', ['ok', '可用'], null, null],
    ['EQ-09', '平面磨床 M7140', '精磨', '设备组 B', ['warn', '检修'], null, null],
    ['EQ-12', '钳工台 · 联合', '钳工', '设备组 C', ['ok', '可用'], null, null],
    ['M-03', '五轴加工中心', '精加工', '设备组 A', ['warn', '接近满载'], 12, 96],
    ['M-05', '卧式加工中心', '预加工', '设备组 A', ['warn', '接近满载'], 9, 89],
    ['M-07', '立式加工中心', '组装', '设备组 B', ['ok', '正常'], 7, 72],
    ['M-12', '三坐标检测', '检验', '设备组 C', ['ok', '正常'], 5, 58],
    ['M-18', '数控车床', '车加工', '设备组 A', ['off', '有余量'], 3, 34],
    ['M-21', '线切割', '特种加工', '设备组 D', ['danger', '停机维护'], 0, 0],
  ].forEach(function (e) {
    R({ type: 'equip', code: e[0], name: e[1], status: e[4], body: function () {
      var util = e[6] != null ? ('<div><span class="apsd-strong">' + e[6] + '%</span><div class="apsd-meter ' + (e[6] >= 90 ? 'danger' : e[6] >= 75 ? 'warn' : e[6] === 0 ? 'danger' : 'ok') + '"><i style="width:' + Math.max(e[6], 3) + '%"></i></div></div>') : null;
      return rows([
        ['设备名称', '<span class="apsd-strong">' + esc(e[1]) + '</span>'],
        ['绑定工序', '<span class="apsd-chip">' + esc(e[2]) + '</span>'],
        ['设备组', esc(e[3])],
        ['状态', pill(e[4][0], e[4][1])],
        e[5] != null ? ['本周任务', e[5] + ' 项'] : null,
        util ? ['本周利用率', util] : null
      ]) + sec('', '<div class="apsd-note">每台设备绑定一个自制工种，提供该工种的可用产能时段。利用率 ≥ 90% 视为接近满载，排产时优先避让。</div>');
    }, foot: ['查看甘特', '编辑设备'] });
  });

  // —— 人员 ——
  var PEOPLENAME = { 'P-101': '张伟', 'P-118': '李娜', 'P-126': '王强', 'P-133': '赵敏', 'P-021': '张三', 'P-024': '李四', 'P-030': '王五', 'P-033': '赵六' };
  [
    ['P-101', '张伟', ['数铣', '数车'], '白班', ['ok', '在岗'], '40h'],
    ['P-118', '李娜', ['精磨', '总检'], '白班', ['ok', '在岗'], '38h'],
    ['P-126', '王强', ['钳工'], '两班倒', ['warn', '请假'], '0h'],
    ['P-133', '赵敏', ['数车', '钻孔', '钳工'], '白班', ['ok', '在岗'], '42h'],
    ['P-021', '张三', ['精加工'], '一班', ['warn', '接近满载'], '42h'],
    ['P-024', '李四', ['组装'], '一班', ['ok', '有余量'], '31h'],
    ['P-030', '王五', ['检验'], '二班', ['ok', '正常'], '38h'],
    ['P-033', '赵六', ['车加工'], '二班', ['danger', '请假'], '0h'],
  ].forEach(function (p) {
    R({ type: 'people', code: p[0], name: p[1], status: p[4], body: function () {
      return rows([
        ['姓名', '<span class="apsd-strong">' + esc(p[1]) + '</span>'],
        ['技能工种', chips(p[2])],
        ['班次', esc(p[3])],
        ['本周排班', '<span class="apsd-strong">' + esc(p[5]) + '</span>'],
        ['状态', pill(p[4][0], p[4][1])]
      ]) + sec('', '<div class="apsd-note">人员按多技能矩阵参与排产，一人可覆盖多个自制工种。请假 / 异常状态会从当班产能中剔除。</div>');
    }, foot: ['查看排班', '编辑人员'] });
  });

  // —— 供应商 ——
  var SUPNAME = { 'S-01': '华表面处理', 'S-02': '金鼎热处理', 'S-05': '宏达喷涂', 'S-07': '精工电镀' };
  [
    ['S-01', '华表面处理', ['电镀', '发黑'], '3 天', ['ok', '启用']],
    ['S-02', '金鼎热处理', ['热处理'], '4 天', ['ok', '启用']],
    ['S-05', '宏达喷涂', ['喷涂'], '2 天', ['warn', '待复核']],
    ['S-07', '精工电镀', ['电镀'], '3 天', ['off', '停用']],
  ].forEach(function (s) {
    R({ type: 'supplier', code: s[0], name: s[1], status: s[4], body: function () {
      return rows([
        ['供应商', '<span class="apsd-strong">' + esc(s[1]) + '</span>'],
        ['可做外协工种', chips(s[2], 'a')],
        ['默认周期', '<span class="apsd-strong">' + esc(s[3]) + '</span>'],
        ['状态', pill(s[4][0], s[4][1])]
      ]) + sec('', '<div class="apsd-note">供应商绑定外协工种并给出默认周期（天）；连续外协工序可按整组周期计。待复核 / 停用的不参与排产。</div>');
    }, foot: ['查看承接工种', '编辑供应商'] });
  });

  // —— 批次 ——
  [
    ['B202605-018', 'T-1008', 12, '05-24 12:00', '30 / 60', ['danger', '超期'], 'M-03'],
    ['B202605-021', 'T-1009', 8, '05-25 08:00', '20 / 50', ['warn', '接近满载'], 'M-05'],
    ['B202605-019', 'T-1006', 6, '05-25 14:00', '40 / 50', ['ok', '正常'], 'M-07'],
    ['B202605-017', 'T-1004', 10, '05-26 10:00', '10 / 40', ['notice', '外协在途'], 'M-07'],
    ['B202605-024', 'T-1011', 4, '05-26 16:00', '待排', ['off', '待排'], 'M-03'],
    ['B202605-016', 'T-1006', 5, '05-24 09:00', '50 / 50', ['ok', '正常'], 'M-12'],
    ['B202605-013', 'T-1009', 7, '05-23 16:00', '50 / 50', ['ok', '正常'], 'M-12'],
  ].forEach(function (b) {
    var tone = b[5][0] === 'notice' ? 'info' : b[5][0];
    R({ type: 'batch', code: b[0], name: (PARTNAME[b[1]] || '') + ' · ' + b[2] + ' 件', status: [tone, b[5][1]], body: function () {
      return rows([
        ['图号', RECORDS[b[1]] ? '<a class="apsd-link" data-apsd-go="' + b[1] + '">' + b[1] + '</a> <span style="color:var(--ui-muted)">' + esc(PARTNAME[b[1]] || '') + '</span>' : esc(b[1])],
        ['数量', '<span class="apsd-strong">' + b[2] + ' 件</span>'],
        ['交期', esc(b[3])],
        ['工序进度', esc(b[4])],
        ['卡点资源', RECORDS[b[6]] ? '<a class="apsd-link" data-apsd-go="' + b[6] + '">' + b[6] + '</a>' : esc(b[6])],
        ['状态', pill(tone, b[5][1])]
      ]) + sec('执行时间线', miniTable(
        '<th>节点</th><th class="r" style="width:120px">时间</th>',
        '<tr><td>下料 / 备料</td><td class="r">05-22 08:00</td></tr><tr><td>预加工</td><td class="r">05-23 14:00</td></tr><tr><td>精加工（卡点）</td><td class="r" style="color:var(--ui-danger)">05-24 排队</td></tr><tr><td>计划完成</td><td class="r">05-24 18:00</td></tr>'
      )) + sec('', '<div class="apsd-note">批次沿工序链推进；卡点资源决定能否按期完成。点击图号 / 资源可继续巡检。</div>');
    }, foot: [GANTT_LOCATE_LABEL, '查看延期说明'] });
  });

  // —— 方案 ——
  [
    ['关键工序优先', ['ok', '已采用'], 0, 2, '18 小时', '5.8 天', 12, '把超期批次压到最低、总拖期更短；代价是 M-03 更忙、换型多 2 次。'],
    ['基准方案', ['off', '对照'], 0, 3, '24 小时', '5.6 天', 10, '系统默认算法的代表结果，作为对照基线。'],
    ['保交期优先', ['info', '备选'], 0, 2, '18 小时', '5.9 天', 13, '进一步压交期风险，但总工期略长、换型最多。'],
  ].forEach(function (p) {
    R({ type: 'plan', code: p[0], name: '排产方案', status: p[1], body: function () {
      return rows([
        ['方案标签', pill(p[1][0], p[1][1])],
        ['失败工序', p[2] + ' 道'],
        ['超期批次', '<span class="apsd-strong">' + p[3] + ' 个</span>'],
        ['总拖期', esc(p[4])],
        ['总工期', esc(p[5])],
        ['换型次数', p[6] + ' 次']
      ]) + sec('结论', '<div class="apsd-note">' + esc(p[7]) + '</div>');
    }, foot: ['查看甘特', '查看延期说明'] });
  });

  /* ---------------- render / open / close ---------------- */
  var cur = null;
  function buildPanel(rec) {
    var t = TYPES[rec.type] || { icon: 'box', kicker: '' };
    var statusPill = rec.status ? pill(rec.status[0], rec.status[1]) : '';
    var footItems = (rec.foot || []).filter(function (label) {
      // 从甘特图点开的批次卡：隐藏“定位此批次”（你本就在甘特图上）
      return !(label === GANTT_LOCATE_LABEL && cur && cur.from === 'gantt');
    });
    var foot = footItems.map(function (label, i) {
      return '<button class="apsd-btn' + (i === 0 ? ' primary' : '') + '" data-apsd-act="' + esc(label) + '">' + esc(label) + '</button>';
    }).join('');
    return '<div class="apsd-head">' +
        '<span class="apsd-ico">' + svg(t.icon) + '</span>' +
        '<div class="apsd-htext"><div class="apsd-kicker">' + esc(t.kicker) + '</div>' +
          '<div class="apsd-code">' + esc(rec.code) + '</div>' +
          (rec.name ? '<div class="apsd-name">' + esc(rec.name) + '</div>' : '') + '</div>' +
        '<button class="apsd-x" data-apsd-close aria-label="关闭">✕</button>' +
      '</div>' +
      (statusPill ? '<div class="apsd-statusrow">' + statusPill + '</div>' : '') +
      '<div class="apsd-body">' + rec.body() + '</div>' +
      (foot ? '<div class="apsd-foot">' + foot + '</div>' : '');
  }

  function close() {
    if (!cur) return;
    var c = cur; cur = null;
    c.panel.classList.remove('on');
    c.bg.classList.remove('on');
    document.removeEventListener('keydown', onKey);
    setTimeout(function () { if (c.bg.parentNode) c.bg.parentNode.removeChild(c.bg); if (c.panel.parentNode) c.panel.parentNode.removeChild(c.panel); }, 230);
  }
  function onKey(e) { if (e.key === 'Escape') close(); }

  function render(rec) {
    cur.panel.innerHTML = buildPanel(rec);
    cur.panel.querySelector('[data-apsd-close]').addEventListener('click', close);
    cur.panel.querySelectorAll('[data-apsd-go]').forEach(function (a) {
      a.addEventListener('click', function (e) { e.preventDefault(); var code = a.getAttribute('data-apsd-go'); if (RECORDS[code]) { cur.code = code; cur.from = null; render(RECORDS[code]); cur.panel.querySelector('.apsd-body').scrollTop = 0; } });
    });
    cur.panel.querySelectorAll('[data-apsd-act]').forEach(function (b) {
      b.addEventListener('click', function () {
        var act = b.getAttribute('data-apsd-act');
        if (act === GANTT_LOCATE_LABEL) {
          var batch = cur.code;
          close();
          if (window.APSFocusBatchInGantt) window.APSFocusBatchInGantt(batch);
          else toast(act + ' · 示例操作（演示界面）');
          return;
        }
        toast(act + ' · 示例操作（演示界面）');
      });
    });
  }

  function open(codeOrRec, typeHint, opts) {
    var rec = (typeof codeOrRec === 'string') ? RECORDS[codeOrRec] : codeOrRec;
    if (!rec) rec = genericRecord(codeOrRec, typeHint);
    if (!rec) return;
    var from = (opts && opts.from) || null;
    if (cur) { cur.code = rec.code; cur.from = from; render(rec); cur.panel.querySelector('.apsd-body').scrollTop = 0; return; }
    var bg = document.createElement('div'); bg.className = 'apsd-backdrop';
    var panel = document.createElement('aside'); panel.className = 'apsd-panel'; panel.setAttribute('role', 'dialog'); panel.setAttribute('aria-modal', 'true');
    document.body.appendChild(bg); document.body.appendChild(panel);
    cur = { bg: bg, panel: panel, code: rec.code, from: from };
    render(rec);
    bg.addEventListener('click', close);
    document.addEventListener('keydown', onKey);
    requestAnimationFrame(function () { bg.classList.add('on'); panel.classList.add('on'); });
  }

  // fallback for any code we don't have a rich record for
  function genericRecord(code, typeHint) {
    if (!code) return null;
    var type = typeHint || 'batch';
    return { type: type, code: String(code), name: '', status: null, body: function () {
      return rows([['编号', '<span class="apsd-strong">' + esc(code) + '</span>']]) +
        sec('', '<div class="apsd-note">该条目的明细在正式系统中按编号联动展示。当前为示例界面。</div>');
    }, foot: ['知道了'] };
  }

  /* ---------------- toast ---------------- */
  var _toastEl, _toastT;
  function toast(msg) {
    if (!_toastEl) { _toastEl = document.createElement('div'); _toastEl.className = 'apsd-toast'; document.body.appendChild(_toastEl); }
    _toastEl.innerHTML = '<span class="d"></span><span>' + esc(msg) + '</span>';
    _toastEl.classList.add('on');
    clearTimeout(_toastT);
    _toastT = setTimeout(function () { _toastEl.classList.remove('on'); }, 2600);
  }

  window.APSDetail = { open: open, close: close, toast: toast, has: function (c) { return !!RECORDS[c]; }, RECORDS: RECORDS };
})();
