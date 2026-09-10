(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.APSBatchDraft = factory();
}(typeof window === "object" ? window : this, function () {
  "use strict";

  var PRIORITY = { normal: "普通", urgent: "急件", critical: "特急" };
  var READY = { yes: "齐套", partial: "部分齐套", no: "未齐套" };
  var STATUS = { pending: "待排", scheduled: "已排", processing: "加工中", completed: "已完成", cancelled: "已取消" };
  var FIELDS = { batch_id: "批次号", part_no: "图号", quantity: "数量", due_date: "交期", ready_date: "齐套日期", priority: "优先级", ready_status: "齐套", status: "状态", remark: "备注" };
  var OP_FIELDS = { op_code: "工序编码", op_type: "工种", source: "归属", machine: "设备", operator: "人员", setup: "换型工时", unit: "单件工时", supplier: "供应商", ext_days: "外协周期", group: "外协组", mode: "组模式", total: "整组周期", done: "完工" };
  var MACHINE_OPERATORS = { "M-03": ["P-021"], "M-05": ["P-021", "P-024"], "M-07": ["P-024"], "M-12": ["P-030"], "M-18": ["P-033"] };
  function clone(value) {
    if (!value || typeof value !== "object") return value;
    if (Array.isArray(value)) return value.map(clone);
    var out = {}; Object.keys(value).forEach(function (key) { out[key] = clone(value[key]); }); return out;
  }
  function text(value) { return value == null ? "" : String(value).trim(); }
  function number(value, positive, integer) {
    if (typeof value !== "string" && typeof value !== "number") return false;
    if (!/^\d+(?:\.\d+)?$/.test(text(value))) return false;
    var n = Number(value);
    return isFinite(n) && n <= Number.MAX_SAFE_INTEGER && (positive ? n > 0 : n >= 0) && (!integer || Math.floor(n) === n);
  }
  function validDate(value) {
    if (value === "") return true;
    if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
    var y = Number(value.slice(0, 4)), m = Number(value.slice(5, 7)), d = Number(value.slice(8, 10));
    var leap = y % 4 === 0 && (y % 100 !== 0 || y % 400 === 0);
    return y >= 1 && m >= 1 && m <= 12 && d >= 1 && d <= [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1];
  }
  function validateBatch(batch, rows, parts, currentId) {
    var errors = {};
    if (!text(batch.batch_id) || ["__proto__", "constructor", "prototype"].indexOf(text(batch.batch_id)) >= 0) errors.batch_id = "请填写有效批次号。";
    else if ((rows || []).some(function (b) { return b.batch_id !== currentId && b.batch_id === text(batch.batch_id); })) errors.batch_id = "批次号已存在。";
    if (!text(batch.part_no) || (parts && !parts.some(function (p) { return p.part_no === batch.part_no; }))) errors.part_no = "请选择已登记的图号。";
    if (!number(batch.quantity, true, true)) errors.quantity = "数量必须是大于 0 的整数。";
    ["due_date", "ready_date"].forEach(function (key) { if (!validDate(batch[key])) errors[key] = "请输入真实日期，格式为 YYYY-MM-DD。"; });
    if (!Object.prototype.hasOwnProperty.call(PRIORITY, batch.priority)) errors.priority = "请选择有效优先级。";
    if (!Object.prototype.hasOwnProperty.call(READY, batch.ready_status)) errors.ready_status = "请选择有效齐套状态。";
    return errors;
  }
  function opErrors(op) {
    var errors = {};
    if (!text(op.op_type)) errors.op_type = "缺少工种。";
    if (op.source === "internal") {
      if (!MACHINE_OPERATORS[op.machine]) errors.machine = "请选择有效设备。";
      if (!op.operator || !MACHINE_OPERATORS[op.machine] || MACHINE_OPERATORS[op.machine].indexOf(op.operator) < 0) errors.operator = "人员与设备不匹配或未填写。";
      if (!number(op.setup, false)) errors.setup = "换型工时必须是非负数，不能留空。";
      if (!number(op.unit, false)) errors.unit = "单件工时必须是非负数，不能留空。";
    } else if (op.source === "external") {
      if (["华表面处理", "金鼎热处理"].indexOf(op.supplier) < 0) errors.supplier = "请选择有效供应商。";
      var ownPeriod = text(op.ext_days) !== "";
      if (ownPeriod ? !number(op.ext_days, true) : !(op.mode === "merged" && text(op.group) && number(op.total, true))) errors.ext_days = "外协周期必须大于 0；合并组可使用有效整组周期。";
    } else errors.source = "工序归属未确认。";
    return errors;
  }
  function gapCount(ops) { return ops.filter(function (op) { return Object.keys(opErrors(op)).length > 0; }).length; }
  function preflight(rows) {
    return rows.map(function (b) {
      return { id: b.batch_id, part: b.part_no, due: validDate(b.due_date) && b.due_date ? b.due_date.slice(5) : "", ops: b.ops.length, gaps: gapCount(b.ops), ready: b.ready_status === "yes", tag: b.priority === "normal" ? "" : PRIORITY[b.priority] };
    });
  }
  function matchesFocus(batch, context) {
    if (!context) return true;
    if (Array.isArray(context.batchIds) && context.batchIds.indexOf(batch.batch_id) < 0) return false;
    if (context.focus === "gaps") return !batch.ops.length || gapCount(batch.ops) > 0;
    if (context.focus === "unready") return batch.ready_status !== "yes";
    return true;
  }
  function query(rows, filters, partName) {
    filters = filters || {};
    var result = rows.filter(function (b) {
      return matchesFocus(b, filters.location) && (!filters.status || b.status === filters.status) && (!filters.ready || b.ready_status === filters.ready) &&
        (!text(filters.search) || (b.batch_id + " " + b.part_no + " " + (partName ? partName(b.part_no) : "")).toLowerCase().indexOf(text(filters.search).toLowerCase()) >= 0) &&
        Object.keys(filters.columns || {}).every(function (key) { return filters.columns[key].indexOf(String(b[key])) >= 0; });
    });
    if (filters.sort) {
      var s = filters.sort;
      result.sort(function (a, b) { var x = a[s.key], y = b[s.key]; return (x === y ? 0 : x > y ? 1 : -1) * (s.dir === "desc" ? -1 : 1); });
    }
    return result;
  }
  function toggleVisible(selection, rows, checked) {
    var next = clone(selection);
    rows.forEach(function (row) { if (checked) next[row.batch_id] = true; else delete next[row.batch_id]; });
    return next;
  }
  function display(key, value) {
    if (value == null || value === "") return "（空）";
    if (key === "priority") return PRIORITY[value] || String(value);
    if (key === "ready_status") return READY[value] || String(value);
    if (key === "status") return STATUS[value] || String(value);
    if (key === "done") return value ? "已完工" : "未完工";
    return String(value);
  }
  function changes(before, after, all) {
    var fields = [];
    function add(key, label, oldValue, newValue) {
      if (all || oldValue !== newValue) fields.push({ key: key, label: label, before: display(key, oldValue), after: after ? display(key, newValue) : "删除" });
    }
    Object.keys(FIELDS).forEach(function (key) { add(key, FIELDS[key], before[key], after && after[key]); });
    (before.ops || []).forEach(function (op, i) {
      var next = after && after.ops[i];
      Object.keys(OP_FIELDS).forEach(function (key) {
        if (Object.prototype.hasOwnProperty.call(op, key) || next && Object.prototype.hasOwnProperty.call(next, key)) add(key, "工序 " + op.seq + " · " + OP_FIELDS[key], op[key], next && next[key]);
      });
    });
    return fields;
  }
  function createSession(seed) {
    var rows = seed ? clone(seed) : null, drafts = {}, listeners = [], revision = 0, pending = null;
    function requireRows() { if (!rows) throw new Error("批次 seed 尚未初始化：请先加载 BaseBatches.jsx。"); return rows; }
    function emit() { listeners.slice().forEach(function (fn) { fn(); }); }
    function replaceBatches(next) {
      var previous = requireRows();
      var ids = {};
      next.forEach(function (b) {
        var errs = validateBatch(b, [], null);
        if (ids[b.batch_id] || Object.keys(errs).length || !Array.isArray(b.ops)) throw new Error(Object.values(errs).join(" ") || "批次号重复或工序格式无效。");
        ids[b.batch_id] = true;
      });
      previous.forEach(function (b) {
        var current = next.find(function (item) { return item.batch_id === b.batch_id; });
        var key = "base:" + b.batch_id;
        if (current && drafts[key]) Object.keys(drafts[key]).forEach(function (field) {
          if (String(drafts[key][field]) === String(b[field])) drafts[key][field] = current[field];
        });
        if (!current) {
          Object.keys(drafts).forEach(function (name) {
            if (name === key || name === "strict:" + b.batch_id || name.indexOf("op:" + b.batch_id + ":") === 0) delete drafts[name];
          });
          ["selection", "expanded"].forEach(function (name) { if (drafts[name]) delete drafts[name][b.batch_id]; });
        }
      });
      rows = clone(next); revision++; emit();
    }
    function previewBulk(kind, selected, patch) {
      var current = requireRows(), ids = selected.filter(function (id, i) { return selected.indexOf(id) === i; });
      pending = null;
      if (!ids.length) return { error: "请先勾选要操作的批次。" };
      if (ids.some(function (id) { return !current.some(function (b) { return b.batch_id === id; }); })) return { error: "所选批次已变化，请重新选择。" };
      if (["modify", "copy", "delete"].indexOf(kind) < 0) return { error: "不支持的批量操作。" };
      var change = {}, used = current.map(function (b) { return b.batch_id; });
      Object.keys(patch || {}).forEach(function (key) { if (["priority", "due_date", "remark"].indexOf(key) >= 0 && text(patch[key])) change[key] = text(patch[key]); });
      if (kind === "modify" && !Object.keys(change).length) return { error: "请至少填写一个要修改的字段。" };
      var result = [], error = "";
      ids.forEach(function (id) {
        var before = current.find(function (b) { return b.batch_id === id; }), after = clone(before);
        if (kind === "modify") Object.assign(after, change);
        if (kind === "copy") {
          var match = id.match(/(\d+)$/), serial = match ? Number(match[1]) : 0;
          var candidate;
          do {
            serial++;
            if (!Number.isSafeInteger(serial)) { error = "复制编号超出范围，请手工新增批次。"; return; }
            candidate = match ? id.slice(0, match.index) + String(serial).padStart(match[1].length, "0") : id + "-copy-" + serial;
          } while (used.indexOf(candidate) >= 0);
          used.push(candidate); after.batch_id = candidate; after.status = "pending";
          after.ops = after.ops.map(function (op) { return Object.assign({}, op, { op_code: candidate + "-" + String(op.seq).padStart(2, "0"), done: false }); });
        }
        if (kind === "delete") after = null;
        if (after) {
          var errs = validateBatch(after, current, null, kind === "copy" ? null : id);
          if (Object.keys(errs).length) error = id + "：" + Object.values(errs).join(" ");
        }
        var fields = changes(before, after, kind !== "modify");
        if (fields.length) result.push({ id: id, part: before.part_no, before: clone(before), after: after, fields: fields });
      });
      if (error || !result.length) return { error: error || "所填字段与当前值相同，没有需要修改的记录。" };
      pending = { kind: kind, revision: revision, rows: result };
      return { preview: clone(pending) };
    }
    function confirmBulk(preview) {
      if (!pending || JSON.stringify(preview) !== JSON.stringify(pending) || pending.revision !== revision) return { error: "数据或预览已变化，请重新预览后确认。" };
      var p = pending, next = requireRows().map(clone);
      for (var i = 0; i < p.rows.length; i++) {
        var entry = p.rows[i];
        if (entry.after) {
          var errs = validateBatch(entry.after, next, null, p.kind === "copy" ? null : entry.id);
          if (Object.keys(errs).length) return { error: Object.values(errs).join(" ") };
        }
        if (p.kind === "delete") next = next.filter(function (b) { return b.batch_id !== entry.id; });
        else if (p.kind === "copy") next.push(clone(entry.after));
        else next = next.map(function (b) { return b.batch_id === entry.id ? clone(entry.after) : b; });
      }
      pending = null; replaceBatches(next); return { count: p.rows.length };
    }
    return {
      initialize: function (seedRows) { if (!rows) rows = clone(seedRows); },
      getBatches: function () { return clone(requireRows()); }, replaceBatches: replaceBatches,
      preflightRows: function () { return preflight(requireRows()); },
      subscribe: function (fn) { listeners.push(fn); return function () { listeners = listeners.filter(function (x) { return x !== fn; }); }; },
      getDraft: function (key, initial) { return clone(Object.prototype.hasOwnProperty.call(drafts, key) ? drafts[key] : initial); },
      setDraft: function (key, value) { drafts[key] = clone(value); emit(); },
      clearDraft: function (key) { delete drafts[key]; emit(); },
      previewBulk: previewBulk, confirmBulk: confirmBulk, cancelBulk: function () { pending = null; },
      query: query, matchesFocus: matchesFocus, toggleVisible: toggleVisible,
      validateBatch: validateBatch, opErrors: opErrors, gapCount: gapCount, validDate: validDate,
      display: display, machineOperators: MACHINE_OPERATORS
    };
  }
  return Object.assign(createSession(), { createSession: createSession });
}));
