(function () {
  'use strict';
  const BASE = '/api/workbench/v1/dashboard', RECEIPTS = '/api/workbench/v1/commands/';
  const categories = { all: '全部风险', delivery: '交期风险', actual: '执行偏差', external: '外协回厂', downtime: '停机影响', material: '齐套缺口', candidate: '候选方案待确认' };
  const statuses = { new: '待分析', following: '跟进中', awaiting_verification: '待验证', closed: '已关闭' };
  const states = { loaded: '已读取', no_data: '无数据', no_official_plan: '无正式计划', unavailable: '暂无数据', not_connected: '尚未开通' };
  const fields = ['owner', 'deadline', 'action', 'remark', 'completed_at', 'completion_evidence', 'evidence_reference_text', 'evidence_ref'];
  const labels = { status: '处置状态', owner: '责任人', deadline: '责任期限', action: '处置行动', remark: '原因说明', completed_at: '完成时间', completion_evidence: '具体完成结果', evidence_reference_text: '凭据说明', evidence_ref: '已核验附件编号' };
  const object = v => v !== null && typeof v === 'object' && !Array.isArray(v);
  const ref = v => typeof v === 'string' && /^[a-f0-9]{48}$/.test(v);
  const text = v => typeof v === 'string' && v.length > 0;
  const count = v => Number.isSafeInteger(v) && v >= 0;
  const equal = (a, b) => canonical(a) === canonical(b);
  const rejected = new WeakSet();
  function canonical(v) { return JSON.stringify(v, (_, value) => object(value) ? Object.keys(value).sort().reduce((out, k) => { out[k] = value[k]; return out; }, {}) : value); }
  function check(ok, message = '值班台读到的数据不完整，请刷新后重试。') { if (!ok) throw new Error(message); }
  function scope(value = {}) {
    const q = { category: 'all', status: 'all', query: '', sort: 'subject', direction: 'asc', page: 1, size: 20, source: 'production', ...value };
    check(object(value) && Object.keys(q).every(k => ['category', 'status', 'query', 'sort', 'direction', 'page', 'size', 'source', 'snapshot_ref'].includes(k))
      && Object.prototype.hasOwnProperty.call(categories, q.category) && ['all', 'open', ...Object.keys(statuses)].includes(q.status)
      && typeof q.query === 'string' && q.query.length <= 200 && !q.query.includes('\0') && ['subject', 'category', 'status', 'deadline'].includes(q.sort)
      && ['asc', 'desc'].includes(q.direction) && count(q.page) && q.page >= 1 && q.page <= 100000 && count(q.size) && q.size >= 1 && q.size <= 100
      && q.source === 'production' && (q.snapshot_ref === undefined || text(q.snapshot_ref)), '值班台筛选条件无效，当前筛选没有变化。请重新选择筛选条件。');
    q.query = q.query.trim(); return q;
  }
  function handling(h) { check(object(h) && Object.prototype.hasOwnProperty.call(statuses, h.status) && fields.every(k => h[k] === null || typeof h[k] === 'string')); return h; }
  function baseHandling(h) { handling(h); return Object.fromEntries(['status', ...fields].map(k => [k, h[k]])); }
  function item(row) {
    check(object(row) && ref(row.item_ref) && Object.keys(categories).slice(1).includes(row.category) && text(row.subject)
      && object(row.source) && ['current', 'not_currently_evaluated'].includes(row.source_state) && object(row.risk)
      && [true, false, null].includes(row.risk.active) && text(row.risk.message) && text(row.risk.code) && Array.isArray(row.navigation));
    handling(row.handling);
    check(count(row.handling.history_count) && typeof row.handling.deadline_overdue === 'boolean' && Array.isArray(row.allowed_transitions)
      && new Set(row.allowed_transitions).size === row.allowed_transitions.length && row.allowed_transitions.every(s => Object.prototype.hasOwnProperty.call(statuses, s))
      && (row.handling.status !== 'closed' || row.allowed_transitions.length === 0));
    if (row.write_context !== null) check(object(row.write_context) && text(row.write_context.write_token) && object(row.write_context.capabilities) && Array.isArray(row.write_context.blocked_reasons));
    if (row.category === 'external') {
      check(row.source.kind === 'outsourcing_receipt' && ref(row.source.outsourcing_ref) && ['single', 'merged'].includes(row.source.target_kind)
        && row.source.time_basis === 'factory_local' && row.source.tracking_basis === 'manual_receipt_facts' && row.navigation.length === 1);
      if (row.source.receipt !== undefined) check(object(row.source.receipt) && row.source.receipt.outsourcing_ref === row.source.outsourcing_ref);
      const n = row.navigation[0]; check(object(n) && n.view === 'outsourcing' && object(n.context) && Object.keys(n.context).length === 1
        && n.context.outsourcing_ref === row.source.outsourcing_ref && n.query_target === '/api/workbench/v1/outsourcing/receipts/' + row.source.outsourcing_ref
        && n.enabled === (row.source_state === 'current'), '这条外协登记的跳转目标不对，页面没有跳转。请刷新后重试。');
    } else row.navigation.forEach(n => check(object(n) && ['gantt', 'fieldgantt', 'batches', 'analysis'].includes(n.view) && object(n.context) && typeof n.enabled === 'boolean'
      && Object.keys(n.context).every(k => ['plan_ref', 'batch_ref', 'task_ref', 'operation_ref'].includes(k) && ref(n.context[k]))));
    return row;
  }
  function envelope(v, q) {
    check(object(v) && v.ok === true && v.schema_version === 1 && object(v.meta) && v.meta.source === 'production'
      && v.meta.time_basis === 'factory_local' && text(v.meta.snapshot_ref) && text(v.meta.as_of) && Array.isArray(v.warnings) && object(v.data));
    const s = q && scope(q);
    if (s) {
      check(!s.snapshot_ref || s.snapshot_ref === v.meta.snapshot_ref, '数据已更新，请刷新后重试。刚才的选择已保留。');
      const expected = { kind: 'dashboard', ...s }; delete expected.page; delete expected.snapshot_ref;
      check(equal(v.data.scope, expected) && v.data.as_of === v.meta.as_of, '读到的数据和当前筛选不一致，请刷新后重试。');
    }
    return v.data;
  }
  function pagination(p, q) { check(object(p) && p.number === q.page && p.size === q.size && count(p.total) && p.pages === Math.max(1, Math.ceil(p.total / p.size))); }
  function external(s) {
    const connected = ['loaded', 'no_data'].includes(s.state), keys = ['receipt_count', 'current_receipt_count', 'awaiting_return_count', 'overdue_count', 'returned_count', 'awaiting_confirmation_count', 'unregistered_count', 'source_gap_count'];
    const legacyUnsupported = !Object.prototype.hasOwnProperty.call(s, 'handling_state') && !Object.prototype.hasOwnProperty.call(s, 'handling_issues')
      && s.handling_count === 0 && s.closed_count === 0;
    const explicitUnsupported = ['not_connected', 'unavailable'].includes(s.handling_state) && s.handling_count === null && s.closed_count === null
      && Array.isArray(s.handling_issues) && s.handling_issues.length > 0 && s.handling_issues.every(i => object(i) && text(i.code) && text(i.message));
    const supported = connected && s.handling_supported === true && count(s.handling_count) && s.handling_count <= s.receipt_count && count(s.closed_count) && s.closed_count <= s.handling_count
      && (s.handling_state === undefined || s.handling_state === 'loaded') && (s.handling_issues === undefined || Array.isArray(s.handling_issues) && s.handling_issues.length === 0);
    check(supported || s.handling_supported === false && (legacyUnsupported || explicitUnsupported), '外协处置统计读取失败，请刷新重试。');
    check(s.kind === 'outsourcing_receipts' && s.tracking_basis === 'manual_receipt_facts'
      && object(s.entry) && s.entry.view === 'outsourcing' && s.entry.target === '/api/workbench/v1/outsourcing/receipts' && s.entry.enabled === connected
      && keys.every(k => connected ? count(s[k]) : s[k] === null), '外协汇总数据读不完整，请刷新后重试。');
    if (connected) check(s.current_receipt_count <= s.receipt_count && s.awaiting_return_count + s.returned_count === s.current_receipt_count
      && s.overdue_count <= s.awaiting_return_count && s.awaiting_confirmation_count <= s.awaiting_return_count && s.known_risk_count <= s.awaiting_return_count
      && s.known_risk_count >= Math.max(s.overdue_count, s.awaiting_confirmation_count) && s.known_risk_count <= s.overdue_count + s.awaiting_confirmation_count
      && s.source_gap_count <= s.unknown_count && s.unregistered_count <= s.unknown_count);
    return s;
  }
  function catalog(v, query) {
    const q = scope(query), d = envelope(v, q);
    check(object(d.categories) && Array.isArray(d.items) && (d.plan === null || object(d.plan) && ref(d.plan.plan_ref) && d.plan.is_current_official === true));
    pagination(d.page, q); check(d.items.length === Math.min(q.size, Math.max(0, d.page.total - (q.page - 1) * q.size)));
    Object.keys(categories).slice(1).forEach(k => {
      const s = d.categories[k]; check(object(s) && Object.keys(states).includes(s.state) && (s.risk_count === null || count(s.risk_count))
        && count(s.known_risk_count) && count(s.unknown_count) && Array.isArray(s.issues) && Array.isArray(s.evaluation_gaps)
        && (s.risk_count === null || s.risk_count === s.known_risk_count && s.unknown_count === 0));
      if (['not_connected', 'unavailable', 'no_official_plan'].includes(s.state) || k === 'candidate') check(s.risk_count === null);
      s.evaluation_gaps.forEach(gap => {
        if (Object.prototype.hasOwnProperty.call(gap, 'operation')) check(object(gap.operation)
          && ['code', 'name'].every(field => gap.operation[field] === null || text(gap.operation[field])),
        '工序明细不完整，请刷新重试。');
      });
    });
    external(d.categories.external); check(d.categories.external.handling_supported || d.items.every(row => row.category !== 'external'), '外协风险处置尚未开通，这里不显示处置清单。');
    d.items.forEach(row => { item(row); check((q.category === 'all' || row.category === q.category) && (q.status === 'all' || q.status === 'open' && row.handling.status !== 'closed' || q.status === row.handling.status)); });
    check(new Set(d.items.map(r => r.item_ref)).size === d.items.length && object(d.resource_pressure) && object(d.candidate_catalog));
    const p = d.resource_pressure, c = d.candidate_catalog;
    check(p.resources === null || Array.isArray(p.resources));
    if (p.resources) { check(d.plan !== null && p.plan_ref === d.plan.plan_ref && object(p.time_scope) && text(p.time_scope.range_start) && text(p.time_scope.range_end)
      && p.time_scope.time_basis === 'factory_local' && p.time_scope.boundary === 'half_open'); p.resources.forEach(r => check(object(r) && ['machine', 'operator'].includes(r.kind)
      && ['arranged_hours', 'occupied_hours', 'available_hours', 'overlap_hours', 'outside_available_hours', 'utilization'].every(k => r[k] === null || typeof r[k] === 'number' && Number.isFinite(r[k]) && r[k] >= 0)
      && (r.utilization === null || r.utilization <= 1 && r.available_hours > 0) && Array.isArray(r.segments))); }
    check(['loaded', 'no_data', 'unavailable'].includes(c.state) && Array.isArray(c.runs));
    if (c.state !== 'unavailable') check(c.selection === null && count(c.run_count) && object(c.page) && c.runs.length <= 20 && typeof c.page.has_more === 'boolean');
    c.runs.forEach(r => check(ref(r.run_ref) && text(r.accepted_at) && count(r.candidate_count)));
    return v;
  }
  function detail(v, q, selected, historyPage) {
    const d = envelope(v, q); item(d.item); check(d.item.item_ref === selected, '详情内容和所选条目不一致，页面没有切换。请刷新后重试。');
    if (historyPage !== undefined) {
      check(object(d.history) && Array.isArray(d.history.items)); pagination(d.history.page, { page: historyPage, size: q.size });
      d.history.items.forEach(h => { check(ref(h.history_ref) && count(h.sequence) && ['transition', 'reopen'].includes(h.action) && text(h.receipt_ref)
        && text(h.local_operator) && text(h.recorded_at) && object(h.source_snapshot) && h.source_snapshot.snapshot_ref === h.history_ref
        && h.source_snapshot.source.item_ref === selected && h.source_snapshot.time_basis === 'factory_local'); handling(h.before); handling(h.after); });
    }
    return v;
  }
  function expected(intent) {
    const h = { ...intent.before };
    if (intent.action === 'reopen') { h.status = 'following'; h.remark = intent.input.reason; ['completed_at', 'completion_evidence', 'evidence_reference_text', 'evidence_ref'].forEach(k => { h[k] = null; }); }
    else { h.status = intent.input.target_status; fields.forEach(k => { if (Object.prototype.hasOwnProperty.call(intent.input, k)) h[k] = intent.input[k]; }); }
    return h;
  }
  function receipt(v, intent) {
    const d = v && v.data; check(v && v.ok === true && ['committed', 'unchanged'].includes(v.result) && /^[a-f0-9]{32}$/.test(v.receipt_ref)
      && typeof v.replayed === 'boolean' && Array.isArray(v.warnings) && object(d) && d.item_ref === intent.item_ref && d.refresh_required === true
      && equal(d.handling, expected(intent)) && equal(d.source, intent.source) && equal(d.risk, intent.risk)
      && (v.result === 'committed' ? ref(d.history_ref) : d.history_ref === null), '保存结果和这条处置对不上，结果还不确定。请点「查询结果」，不要重复提交。'); return v;
  }
  function resultTarget(intent) { return RECEIPTS + intent.request_key; }
  function failure(v, status, intent) {
    const e = v && v.error, valid = v && v.ok === false && [false, 'unknown'].includes(v.committed) && object(e) && text(e.code) && text(e.message) && Array.isArray(e.fields);
    const error = new Error(valid ? e.message : '读到的结果无法确认，上次提交可能已经生效。请点「查询结果」，不要重复提交。'); error.code = valid ? e.code : 'invalid_response'; error.fields = valid ? e.fields : [];
    if (valid && v.committed === false && [400, 404, 409, 422, 503].includes(status) && e.code !== 'request_key_conflict') rejected.add(error);
    if (valid && v.committed === 'unknown' && intent && e.result_target !== undefined) check(e.request_key === intent.request_key && e.result_target === resultTarget(intent), '返回的结果编号和上次提交对不上，这里没有读取其他结果。请点「查询结果」。');
    return error;
  }
  function create(fetcher = window.fetch.bind(window)) {
    async function request(url, body, signal, intent) {
      const controller = new AbortController(), abort = () => controller.abort(), timer = setTimeout(abort, 30000);
      if (signal) { signal.addEventListener('abort', abort, { once: true }); if (signal.aborted) abort(); }
      try {
        const r = await fetcher(url, { method: body === undefined ? 'GET' : 'POST', credentials: 'same-origin', cache: 'no-store', redirect: 'error', signal: controller.signal,
          ...(body === undefined ? {} : { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }) });
        check((r.headers.get('Content-Type') || '').split(';')[0].trim().toLowerCase() === 'application/json', '值班台读到的数据不完整，请刷新后重试。');
        const v = await r.json(); if (!r.ok || v.ok === false) throw failure(v, r.status, intent); check(r.status === 200); return v;
      } finally { clearTimeout(timer); if (signal) signal.removeEventListener('abort', abort); }
    }
    return {
      async list(q, signal) { return catalog(await request(BASE + '?' + new URLSearchParams(q), undefined, signal), q); },
      async detail(selected, q, historyPage, signal) { check(ref(selected)); const args = { ...q }; if (historyPage !== undefined) args.history_page = historyPage;
        return detail(await request(BASE + '/items/' + selected + (historyPage === undefined ? '' : '/history') + '?' + new URLSearchParams(args), undefined, signal), q, selected, historyPage); },
      async command(intent, token) { return receipt(await request(BASE + '/items/' + intent.item_ref + '/' + intent.action, { request_key: intent.request_key, write_token: token, input: intent.input }, undefined, intent), intent); },
      async lookup(intent, signal) { const v = await request(resultTarget(intent), undefined, signal, intent);
        if (v.state === 'not_recorded') { check(v.ok === true && v.receipt === null && v.may_be_in_flight === true); return null; }
        return receipt(v, intent); }
    };
  }
  window.DashboardContract = { categories, statuses, states, fields, labels, object, ref, text, equal, check, scope, item, baseHandling, catalog, detail, expected, receipt, create, external, isRejected: e => rejected.has(e) };
})();
