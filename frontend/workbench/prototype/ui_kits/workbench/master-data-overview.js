(function () {
  'use strict';
  var DOMAINS = [
    { id: 'part', label: '零件' }, { id: 'route', label: '工艺路线' },
    { id: 'opType', label: '工种' }, { id: 'equipment', label: '设备' },
    { id: 'personnel', label: '人员' }, { id: 'material', label: '物料' },
    { id: 'supplier', label: '供应商' }, { id: 'calendar', label: '日历配置' }
  ];
  var STATUS = { attention: '待维护', checked: '已检查', inactive: '停用' };
  function text(value) { return value == null ? '' : String(value).trim(); }
  function missing(value) { return !text(value) || text(value) === '—'; }
  function number(value) {
    if (missing(value) || !['number', 'string'].includes(typeof value) || !/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(text(value))) return null;
    var n = Number(value); return Number.isFinite(n) ? n : null;
  }
  function cell(html) {
    var doc = new DOMParser().parseFromString('<body>' + (html || '') + '</body>', 'text/html');
    return { text: text(doc.body.textContent), chips: Array.from(doc.querySelectorAll('.chip')).map(function (c) { return text(c.textContent); }) };
  }
  function buildOverview(snapshot) {
    var entities = [], issues = [], byKey = new Map(), serial = 0;
    var loaded = !!snapshot && snapshot.schemaVersion === 1 && snapshot.source === 'native-session';
    var available = {}, lists = loaded ? snapshot.lists || {} : {};
    DOMAINS.forEach(function (d) { available[d.id] = false; });
    function add(domain, code, name, details, target) {
      var baseKey = domain + ':' + code, key = baseKey;
      while (byKey.has(key)) key = baseKey + ':' + (++serial);
      var e = { key: key, domain: domain, code: text(code), name: text(name), details: details || [],
        target: Object.assign({ domain: domain, code: code }, target), relations: [], issues: [], status: 'checked', fields: [] };
      entities.push(e); byKey.set(key, e); return e;
    }
    function issue(e, rule, title, evidence, action, stage) {
      var item = { key: e.key + '/' + rule, entityKey: e.key, domain: e.domain, code: e.code, name: e.name,
        title: title, evidence: evidence, action: action, status: 'attention', target: Object.assign({}, e.target, stage ? { stage: stage } : {}) };
      e.issues.push(item); issues.push(item); return item;
    }
    function field(e, label, value, valid) {
      e.fields.push({ label: label, filled: valid == null ? !missing(value) : valid });
    }
    function relate(a, b, label, reverse) {
      if (!a || !b || a.key === b.key) return;
      if (!a.relations.some(function (r) { return r.key === b.key && r.label === label; })) a.relations.push({ key: b.key, label: label });
      if (reverse) relate(b, a, reverse, null);
    }
    function tableRows(listKey, domain, detailLabels, values) {
      if (!Array.isArray(lists[listKey])) return [];
      available[domain] = true;
      return lists[listKey].map(function (row, index) {
        var cells = row.map(cell), get = function (i) { return cells[i] || { text: '', chips: [] }; };
        var code = get(0).text, e = add(domain, code || '(未编号 ' + (index + 1) + ')', get(1).text,
          detailLabels.map(function (label, i) { return [label, get(i + 2).text]; }),
          domain === 'opType' ? { chain: listKey === 'op_ext' ? 'external' : 'internal' } : {});
        e.listKey = listKey; e.cells = cells; e.registered = true;
        e.recordSource = snapshot.visibleList === listKey ? '当前表格视图，临时增删未写入源数组' : '当前会话源记录';
        field(e, '编号', code); field(e, '名称', e.name);
        if (missing(code) || missing(e.name)) issue(e, 'identity', '编号或名称未填写', '编号：' + (code || '未填') + '；名称：' + (e.name || '未填'), '补齐基本信息');
        if (values) values(e, get);
        return e;
      });
    }
    var opsInt = tableRows('op_int', 'opType', ['显示设备数（不作关联依据）', '显示人员数（不作关联依据）', '备注']);
    var opsExt = tableRows('op_ext', 'opType', ['周期策略', '备注']);
    var opTypes = opsInt.concat(opsExt), opMap = new Map();
    opTypes.forEach(function (e) {
      var key = e.target.chain + ':' + e.name, group = opMap.get(key) || [];
      group.push(e); opMap.set(key, group);
    });
    function bind(e, names, chain) {
      names.forEach(function (name) {
        var matches = opMap.get(chain + ':' + name) || [];
        if (matches.length === 1) relate(e, matches[0], '绑定工种', '关联' + DOMAINS.find(function (d) { return d.id === e.domain; }).label);
        else issue(e, 'op-' + name, matches.length ? '工种名称不唯一' : '绑定工种未建档', '工种：' + name + '；当前工种记录匹配 ' + matches.length + ' 条', '核对工种与绑定关系');
      });
    }
    var equipment = tableRows('equip', 'equipment', ['绑定工种', '设备组', '使用状态'], function (e, get) {
      e.nativeStatus = get(4).text;
      var names = get(2).chips; field(e, '绑定工种', names.join(''));
      if (!names.length) issue(e, 'unbound', '设备未绑定工种', '绑定工种为空', '绑定一个自制工种');
      if (Array.isArray(lists.op_int)) bind(e, names, 'internal');
      if (e.nativeStatus === '检修') issue(e, 'maintenance', '设备处于检修', '当前使用状态：检修', '核对检修与可用状态');
    });
    var people = tableRows('people', 'personnel', ['技能工种', '班次', '在岗状态'], function (e, get) {
      e.nativeStatus = get(4).text; var names = get(2).chips;
      field(e, '技能工种', names.join('')); field(e, '班次', get(3).text);
      if (!names.length) issue(e, 'skills', '人员未登记技能', '当前技能工种为空', '补齐人员技能');
      if (Array.isArray(lists.op_int)) bind(e, names, 'internal');
      if (e.nativeStatus === '请假') issue(e, 'absence', '人员处于请假状态', '当前在岗状态：请假', '核对人员可用状态');
      e.details.push(['人员设备操作关系', '未加载，技能名称不等于设备操作授权']);
    });
    tableRows('material', 'material', ['规格', '库存', '使用状态'], function (e, get) {
      e.nativeStatus = get(4).text; field(e, '规格', get(2).text); field(e, '库存', get(3).text);
      if (missing(get(2).text)) issue(e, 'spec', '物料规格未填写', '当前规格为空', '补齐规格');
      if (missing(get(3).text)) issue(e, 'stock', '库存未填写', '当前库存为空', '核对库存和单位');
      if (e.nativeStatus === '低库存') issue(e, 'stock-state', '物料标记为低库存', '来自物料状态；未加载批次需求，不能据此判断缺料', '核对库存与批次需求');
      e.details.push(['批次物料需求关联', '未加载']);
    });
    var suppliers = tableRows('supplier', 'supplier', ['外协工种', '默认周期', '使用状态'], function (e, get) {
      e.nativeStatus = get(4).text; var names = get(2).chips, lead = /^(\d+(?:\.\d+)?)\s*天$/.exec(get(3).text);
      field(e, '外协工种', names.join('')); field(e, '默认周期', get(3).text, !!lead && Number(lead[1]) > 0);
      if (!names.length) issue(e, 'op', '供应商未绑定外协工种', '外协工种为空', '补齐外协工种');
      if (Array.isArray(lists.op_ext)) bind(e, names, 'external');
      if (!lead || Number(lead[1]) <= 0) issue(e, 'days', '供应商默认周期待核对', '默认周期：' + (get(3).text || '未填'), '填写正数天数');
      if (e.nativeStatus === '待复核') issue(e, 'review', '供应商待复核', '当前使用状态：待复核', '确认供应商资料与启用状态');
    });
    if (loaded && Array.isArray(snapshot.pendingOpTypes)) snapshot.pendingOpTypes.forEach(function (p, i) {
      var e = add('opType', '待归类-' + (i + 1), p.name, [['来源', p.from]], { code: '', name: p.name, chain: 'internal' });
      e.registered = false; field(e, '名称', p.name); field(e, '工种建档', '', false);
      issue(e, 'classification', '工种待归类建档', p.from || '当前会话待归类记录', '确认自制或外协归属');
    });
    if (loaded && Array.isArray(snapshot.parts)) {
      available.part = available.route = true;
      snapshot.parts.forEach(function (p) {
        var operations = Array.isArray(p.operations) ? p.operations : [], meta = p.meta || {}, stage = p.stage || {};
        var part = add('part', p.code, meta.name, [['工序数', operations.length], ['路线', operations.length ? '已有路线' : '未录入']]);
        field(part, '图号', p.code); field(part, '名称', meta.name); field(part, '工艺路线', '', operations.length > 0);
        if (missing(p.code) || missing(meta.name)) issue(part, 'identity', '零件基本信息不完整', '图号或名称为空', '补齐零件信息');
        if (!operations.length) { issue(part, 'route', '零件未录入工艺路线', '工序清单为 0 条', '录入工艺路线', 'route'); return; }
        var route = add('route', p.code, (meta.name || p.code) + ' · 工艺路线', [['工序数', operations.length], ['归属确认', stage.attr === 'done' ? '已确认' : '待确认']], { partCode: p.code });
        relate(part, route, '工艺路线', '所属零件');
        field(route, '工序归属确认', '', stage.attr === 'done');
        if (stage.attr !== 'done') issue(route, 'classification', '工序归属待确认', '基础资料中的归属确认尚未完成', '确认工序归属', 'attr');
        operations.forEach(function (op, i) {
          var seq = '工序 ' + op.seq + ' ' + op.op, prefix = 'op-' + i;
          var chain = op.src === 'int' ? 'internal' : op.src === 'ext' ? 'external' : null;
          field(route, seq + '归属', '', !!chain);
          if (!chain) issue(route, prefix + '-source', '工序归属未明确', seq, '确认自制或外协归属', 'attr');
          var matches = opMap.get(chain + ':' + op.op) || [];
          if (chain && Array.isArray(lists[chain === 'internal' ? 'op_int' : 'op_ext'])) {
            field(route, seq + '工种建档', '', matches.length === 1);
            if (matches.length === 1) relate(route, matches[0], '工序使用工种', '引用路线');
            else issue(route, prefix + '-type', '工序工种建档待核对', seq + '；当前建档匹配 ' + matches.length + ' 条', '核对工种后确认工序归属', 'attr');
          }
          if (op.src === 'int') ['setup', 'unit'].forEach(function (key) {
            var label = key === 'setup' ? '换型工时' : '单件工时', n = number(op[key]);
            field(route, seq + label, op[key], n !== null && n >= 0);
            if (n === null || n < 0) issue(route, prefix + '-' + key, missing(op[key]) ? label + '未填写' : label + '数值异常', seq + '；' + label + '：' + (text(op[key]) || '未填'), stage.attr === 'done' ? '填写非负有限工时，0 合法' : '先确认归属，再补工时', stage.attr === 'done' ? 'hours' : 'attr');
          });
          route.details.push([seq, op.src === 'int' ? '自制 · 换型 ' + (text(op.setup) || '未填') + ' h / 单件 ' + (text(op.unit) || '未填') + ' h' : '外协 · ' + (text(op.ext) || '周期未填')]);
          if (op.src === 'ext') {
            if (missing(op.ext) || /待定/.test(op.ext)) issue(route, prefix + '-external', '外协周期待维护', seq + '；' + (op.ext || '周期未填'), '核对外协周期', 'hours');
            if (/待定供应商/.test(op.dev || '')) issue(route, prefix + '-supplier', '外协供应商待指定', seq + '；' + op.dev, '核对工序供应商', 'hours');
          }
        });
        route.details.push(['外协正式分组与供应商编号', '未加载；显示文字不作为正式绑定依据']);
      });
    }
    opTypes.forEach(function (op) {
      var external = op.target.chain === 'external', related = op.relations.map(function (r) { return byKey.get(r.key); });
      var resources = related.filter(function (r) { return r.domain === (external ? 'supplier' : 'equipment'); });
      var persons = related.filter(function (r) { return r.domain === 'personnel'; });
      op.details = external ? [['周期策略', op.details[0][1]], ['关联供应商', available.supplier ? resources.length : '未加载']] : [['关联设备', available.equipment ? resources.length : '未加载'], ['技能人员', available.personnel ? persons.length : '未加载']];
      if (external ? available.supplier : available.equipment) {
        field(op, external ? '供应商关联' : '设备关联', '', resources.length > 0);
        if (!resources.length) issue(op, 'resource', external ? '未找到关联供应商' : '未找到关联设备', '当前会话实际绑定记录为 0 条', external ? '维护供应商工种绑定' : '维护设备工种绑定');
      }
      if (!external && available.personnel) {
        field(op, '技能人员关联', '', persons.length > 0);
        if (!persons.length) issue(op, 'people', '未找到技能人员', '当前会话技能工种匹配为 0 条', '维护人员技能');
      }
    });
    if (loaded && snapshot.calendar && snapshot.calendar.cfg && typeof snapshot.calendar.cfg === 'object') {
      available.calendar = true;
      Object.keys(snapshot.calendar.cfg).sort().forEach(function (key) {
        var c = snapshot.calendar.cfg[key], parts = key.split('-'), date = parts[0] + '-' + String(Number(parts[1]) + 1).padStart(2, '0') + '-' + String(parts[2]).padStart(2, '0');
        var e = add('calendar', date, c.type === 'rest' ? '休息 / 调休' : '工作日配置', [['类型', c.type === 'rest' ? '休息' : '工作'], ['工时', c.hours == null ? '默认' : c.hours + ' h'], ['效率', c.eff == null ? '默认' : c.eff + '%'], ['备注', c.note || '无']]);
        field(e, '日历类型', '', c.type === 'rest' || c.type === 'work');
        if (c.type !== 'rest' && c.type !== 'work') issue(e, 'type', '日历类型异常', text(c.type), '核对日历类型');
        if (c.type === 'work') [['hours', '可用工时'], ['eff', '效率']].forEach(function (entry) {
          var n = number(c[entry[0]]), valid = c[entry[0]] == null || (n !== null && (entry[0] === 'eff' ? n > 0 : n >= 0));
          field(e, entry[1], c[entry[0]], valid);
          if (!valid) issue(e, entry[0], entry[1] + '数值异常', entry[1] + '：' + text(c[entry[0]]), '核对工时与效率');
        });
      });
    }
    var identities = new Map();
    entities.forEach(function (e) { var id = e.domain + ':' + e.code, same = identities.get(id) || []; same.push(e); identities.set(id, same); });
    identities.forEach(function (same) { if (same.length > 1) same.forEach(function (e) { issue(e, 'duplicate', '编号重复', '同域同编号 ' + same.length + ' 条', '核对编号唯一性'); }); });
    entities.forEach(function (e) {
      if (e.recordSource) e.details.push(['记录来源', e.recordSource]);
      e.status = e.nativeStatus === '停用' ? 'inactive' : e.issues.length ? 'attention' : 'checked';
      e.completeness = { filled: e.fields.filter(function (f) { return f.filled; }).length, total: e.fields.length };
      e.summary = e.issues.length ? e.issues[0].title + (e.issues.length > 1 ? ' 等 ' + e.issues.length + ' 项' : '') : '已检查字段未发现待维护项';
      delete e.cells;
    });
    return { loaded: loaded, sourceLabel: loaded ? '基础资料 · 当前会话' : '基础资料 · 未加载', sample: loaded && snapshot.sample === true,
      entities: entities, issues: issues, byKey: byKey,
      domains: DOMAINS.map(function (d) { var rows = entities.filter(function (e) { return e.domain === d.id; }); return Object.assign({}, d, { loaded: available[d.id], count: available[d.id] ? rows.length : null, attention: rows.filter(function (e) { return e.issues.length; }).length }); }),
      stats: { entities: entities.length, issues: issues.length, affected: entities.filter(function (e) { return e.issues.length; }).length, relations: entities.reduce(function (n, e) { return n + e.relations.length; }, 0) / 2,
        registeredOpTypes: opTypes.length, equipment: equipment.length, people: people.length, suppliers: suppliers.length }
    };
  }
  function query(overview, options) {
    options = options || {}; var q = text(options.search).toLowerCase(), view = options.view === 'issues' ? 'issues' : 'entities';
    var rows = overview[view].filter(function (r) {
      return (!options.domain || options.domain === 'all' || r.domain === options.domain) &&
        (!options.status || options.status === 'all' || (options.status === 'attention' ? (view === 'issues' || r.issues.length > 0) : r.status === options.status)) &&
        (!q || [r.code, r.name, r.title, r.evidence, r.summary].concat(r.details ? r.details.map(function (f) { return f.join(' '); }) : []).join(' ').toLowerCase().indexOf(q) >= 0);
    });
    var sort = options.sort || 'issues';
    rows.sort(function (a, b) {
      var diff = sort === 'issues' ? (b.issues ? b.issues.length : overview.byKey.get(b.entityKey).issues.length) - (a.issues ? a.issues.length : overview.byKey.get(a.entityKey).issues.length) :
        sort === 'relations' ? (b.relations || []).length - (a.relations || []).length :
        sort === 'name' ? a.name.localeCompare(b.name, 'zh-CN') : 0;
      return diff || a.code.localeCompare(b.code, 'zh-CN', { numeric: true }) || a.key.localeCompare(b.key);
    });
    var size = [20, 50, 100].indexOf(Number(options.pageSize)) >= 0 ? Number(options.pageSize) : 20;
    var pages = Math.max(1, Math.ceil(rows.length / size)), page = Math.max(1, Math.min(pages, Math.floor(Number(options.page) || 1)));
    return { all: rows, rows: rows.slice((page - 1) * size, page * size), total: rows.length, page: page, pages: pages, pageSize: size };
  }
  function toCSV(overview, options) {
    var result = query(overview, options), isIssue = options && options.view === 'issues';
    var rows = [isIssue ? ['数据域', '编号', '名称', '待维护项', '当前记录', '维护建议'] : ['数据域', '编号', '名称', '检查状态', '已填字段', '检查字段', '关联项数', '待维护项数']];
    result.all.forEach(function (r) { var label = DOMAINS.find(function (d) { return d.id === r.domain; }).label;
      rows.push(isIssue ? [label, r.code, r.name, r.title, r.evidence, r.action] : [label, r.code, r.name, STATUS[r.status], r.completeness.filled, r.completeness.total, r.relations.length, r.issues.length]);
    });
    return '\uFEFF' + rows.map(function (row) { return row.map(function (value) {
      var s = value == null ? '' : String(value); if (/^[\s]*[=+@-]/.test(s) || /^[\t\r\n]/.test(s)) s = "'" + s;
      return '"' + s.replace(/"/g, '""') + '"';
    }).join(','); }).join('\r\n') + '\r\n';
  }
  function downloadCSV(overview, options) {
    if (!overview.loaded) throw new Error('基础资料尚未加载，无法导出。');
    var blob = new Blob([toCSV(overview, options)], { type: 'text/csv;charset=utf-8' });
    if (!window.URL || !window.URL.createObjectURL) throw new Error('当前环境不支持文件下载。');
    var url = window.URL.createObjectURL(blob), a = document.createElement('a');
    a.href = url; a.download = options && options.view === 'issues' ? '主数据待维护项.csv' : '主数据实体.csv'; a.hidden = true;
    try { document.body.appendChild(a); a.click(); }
    finally { a.remove(); window.setTimeout(function () { window.URL.revokeObjectURL(url); }, 1000); }
    return { rows: query(overview, options).total, filename: a.download };
  }
  function createModel(options) {
    var readSnapshot = options && options.readSnapshot || function () {
      if (!window.APSPlanAData) return null;
      window.APSPlanAData.ensureSession();
      return window.APSPlanAData.getSnapshot();
    };
    return { read: function () { return buildOverview(readSnapshot()); } };
  }
  function navigate(target, onNav) {
    if (!window.APSPlanAData || typeof onNav !== 'function') throw new Error('基础资料导航尚未接入。');
    window.APSPlanAData.requestNavigation(target); onNav('process');
  }
  window.APSMasterDataOverview = { domains: DOMAINS, statusLabels: STATUS, createModel: createModel, buildOverview: buildOverview, query: query, toCSV: toCSV, downloadCSV: downloadCSV, navigate: navigate };
})();
