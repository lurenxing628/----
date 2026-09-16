(function () {
  'use strict';

  const BASE = '/api/workbench/v1/outsourcing',
    COMMANDS = '/api/workbench/v1/commands/';
  const states = {
    in_transit: '在途',
    returned: '已回厂',
    awaiting_confirmation: '待确认'
  };
  const fields = ['sent', 'planned', 'returned', 'confirmedState'];
  const labels = {
    sent: '实际发出',
    planned: '计划回厂',
    returned: '实际回厂',
    confirmedState: '确认状态'
  };
  const object = v => v !== null && typeof v === 'object' && !Array.isArray(v);
  const ref = v => typeof v === 'string' && /^[a-f0-9]{48}$/.test(v);
  const text = v => typeof v === 'string' && v.length > 0;
  const count = v => Number.isSafeInteger(v) && v >= 0;
  const rejected = new WeakSet();
  function check(ok, message = '外协读到的数据不完整，请刷新后重试。') {
    if (!ok) throw new Error(message);
  }
  function canonical(v) {
    return JSON.stringify(v, (_, x) => object(x) ? Object.keys(x).sort().reduce((r, k) => {
      r[k] = x[k];
      return r;
    }, {}) : x);
  }
  const equal = (a, b) => canonical(a) === canonical(b);
  function time(v) {
    if (typeof v !== 'string' || !/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d$/.test(v)) return false;
    const n = v.match(/\d+/g).map(Number),
      date = new Date(0);
    date.setUTCFullYear(n[0], n[1] - 1, n[2]);
    date.setUTCHours(n[3], n[4], n[5], 0);
    return n[0] > 0 && date.toISOString().slice(0, 19) === v;
  }
  function stamp(v) {
    const s = typeof v === 'string' && v.length === 16 ? v + ':00' : v;
    check(time(s), '请按 2026-09-13 08:30 这样填写日期和时间。');
    return s;
  }
  function facts(v, now) {
    check(object(v) && fields.every(k => Object.prototype.hasOwnProperty.call(v, k)) && time(v.sent) && time(v.planned) && (v.returned === null || time(v.returned)) && Object.prototype.hasOwnProperty.call(states, v.confirmedState));
    check(v.planned >= v.sent && (v.returned === null || v.returned >= v.sent), '计划回厂和实际回厂不能早于实际发出。');
    check(v.confirmedState === 'returned' === (v.returned !== null), '已回厂状态和实际回厂时间要一起填。还没回厂就点「清除实际回厂」。');
    if (now) check(v.sent <= now && (v.returned === null || v.returned <= now), '实际发出和实际回厂不能填未来时间，以系统的工厂时间为准。');
    return Object.fromEntries(fields.map(k => [k, v[k]]));
  }
  function target(t, publicData = false) {
    check(object(t) && ['single', 'merged'].includes(t.kind) && ref(t.batch_ref) && ref(t.supplier_ref) && Array.isArray(t.operation_refs) && t.operation_refs.length >= 1 && t.operation_refs.length <= 200 && t.operation_refs.every(ref) && new Set(t.operation_refs).size === t.operation_refs.length && t.kind === 'single' === (t.operation_refs.length === 1), '单工序要选 1 道，合并发出至少选 2 道，而且不能重复。');
    if (publicData) {
      check(t.grouping_basis === 'explicit_receipt_membership' && object(t.batch) && t.batch.ref === t.batch_ref && object(t.supplier) && t.supplier.ref === t.supplier_ref && Array.isArray(t.operations) && t.operations.length === t.operation_refs.length && equal(t.operations.map(o => o.operation_ref).sort(), t.operation_refs.slice().sort()));
      if (t.part !== undefined) {
        check(object(t.part) && ref(t.part.ref));
        entityLabel(t.part, t.part.ref);
      }
      if (t.source_resolution !== undefined) resolution(t.source_resolution);
    }
    return {
      kind: t.kind,
      batch_ref: t.batch_ref,
      supplier_ref: t.supplier_ref,
      operation_refs: t.operation_refs.slice().sort()
    };
  }
  function boundary(e, t) {
    check(object(e) && e.automatically_reported === false && equal(e.operation_refs.slice().sort(), t.operation_refs.slice().sort()) && e.service === 'WorkbenchProductionReportService' && text(e.reason), '回厂登记数据无效，请刷新重试。');
  }
  function entityLabel(entity, expected) {
    check(entity === null || object(entity) && entity.ref === expected && ref(expected) && ['business_code', 'label'].every(k => entity[k] === null || text(entity[k]) && entity[k].trim().length > 0), '外协工序的名称和编号对不上，这里不显示猜测的名称。请刷新后重试。');
  }
  function resolution(v) {
    check(object(v) && ['birth_record', 'current_relation', 'registration_confirmation'].includes(v.basis) && (v.basis === 'registration_confirmation' ? ref(v.confirmation_ref) : v.confirmation_ref === null));
  }
  function row(v) {
    check(object(v) && ref(v.outsourcing_ref) && ref(v.latest_fact_ref) && count(v.history_count) && v.history_count >= 1 && typeof v.can_preview === 'boolean' && ['current', 'identity_drift', 'source_unavailable'].includes(v.source_state) && Array.isArray(v.issues) && v.tracking_basis === 'manual_receipt_facts' && time(v.confirmed_at) && text(v.declared_operator) && text(v.local_operator) && text(v.reason));
    facts(v);
    target(v.target, true);
    boundary(v.execution, v.target);
    check(v.awaiting_return === (v.returned === null) && typeof v.overdue === 'boolean');
    return v;
  }
  function query(kind, value = {}) {
    const allowed = ['page', 'size', 'snapshot_ref'].concat(['targets', 'receipts'].includes(kind) ? ['batch_ref'] : []).concat(kind === 'receipts' ? ['status'] : []);
    const q = {
      page: 1,
      size: 10,
      ...value
    };
    check(object(value) && Object.keys(q).every(k => allowed.includes(k)) && Number.isSafeInteger(q.page) && q.page >= 1 && q.page <= 1000000 && Number.isSafeInteger(q.size) && q.size >= 1 && q.size <= 100 && (q.batch_ref === undefined || ref(q.batch_ref)) && (q.status === undefined || ['all', 'awaiting', 'overdue', 'returned'].includes(q.status)) && (q.snapshot_ref === undefined || text(q.snapshot_ref)) && (q.page === 1 || text(q.snapshot_ref)), '外协的筛选或翻页条件无效，当前范围没有变化。请重新选择。');
    return q;
  }
  function envelope(v, q, preview = false) {
    check(object(v) && v.ok === true && v.schema_version === 1 && object(v.meta) && v.meta.source === 'production' && v.meta.time_basis === 'factory_local' && time(v.meta.as_of) && (preview ? v.meta.snapshot_ref === null : text(v.meta.snapshot_ref)) && Array.isArray(v.warnings) && object(v.data));
    if (q && q.snapshot_ref) check(q.snapshot_ref === v.meta.snapshot_ref, '数据已更新，请刷新后重试。刚才的选择已保留。');
    return v.data;
  }
  function page(p, rows, q) {
    check(object(p) && p.number === q.page && p.size === q.size && count(p.total) && p.pages === Math.ceil(p.total / p.size) && Array.isArray(rows) && rows.length === Math.min(p.size, Math.max(0, p.total - (p.number - 1) * p.size)), '读到的页码和数量与当前范围不一致，请刷新后重试。');
  }
  function catalog(v, kind, q, selected) {
    const d = envelope(v, q);
    if (kind === 'targets') {
      check(d.grouping_basis === 'explicit_receipt_membership' && d.dates_inferred === false);
      page(d.page, d.items, q);
      d.items.forEach(r => {
        check(object(r) && ['operation_ref', 'batch_ref', 'supplier_ref', 'outsourcing_ref'].every(k => r[k] === null || ref(r[k])) && typeof r.can_register === 'boolean' && Array.isArray(r.issues) && (!r.can_register || r.outsourcing_ref === null && [r.operation_ref, r.batch_ref, r.supplier_ref].every(ref)) && (!q.batch_ref || r.batch_ref === q.batch_ref));
        entityLabel(r.batch, r.batch_ref);
        entityLabel(r.supplier, r.supplier_ref);
        if (r.part !== undefined && r.part !== null) {
          check(object(r.part) && ref(r.part.ref));
          entityLabel(r.part, r.part.ref);
        }
        if (r.source_resolution !== undefined && r.source_resolution !== null) resolution(r.source_resolution);
      });
      check(new Set(d.items.filter(r => r.operation_ref).map(r => r.operation_ref)).size === d.items.filter(r => r.operation_ref).length);
    } else if (kind === 'receipts') {
      check(d.as_of === v.meta.as_of && d.tracking_basis === 'manual_receipt_facts');
      page(d.page, d.items, q);
      d.items.forEach(r => {
        row(r);
        check(!q.batch_ref || r.target.batch_ref === q.batch_ref);
        check(r.overdue === (r.returned === null && r.planned < v.meta.as_of));
        check(!q.status || q.status === 'all' || q.status === 'returned' && !r.awaiting_return || q.status === 'awaiting' && r.awaiting_return || q.status === 'overdue' && r.overdue);
      });
      check(new Set(d.items.map(r => r.outsourcing_ref)).size === d.items.length);
    } else {
      row(d.item);
      check(d.item.outsourcing_ref === selected, '详情或历史和所选登记对不上，页面没有切换。请刷新后重试。');
      if (kind === 'history') {
        check(object(d.history));
        page(d.history.page, d.history.items, q);
        d.history.items.forEach(h => {
          check(ref(h.fact_ref) && (h.previous_fact_ref === null || ref(h.previous_fact_ref)) && time(h.confirmed_at) && text(h.declared_operator) && text(h.local_operator) && text(h.reason));
          facts(h.after);
          if (h.before !== null) facts(h.before);
        });
        check(d.history.page.total === d.item.history_count && (q.page !== 1 || d.history.items[0].fact_ref === d.item.latest_fact_ref));
        check(new Set(d.history.items.map(h => h.fact_ref)).size === d.history.items.length);
        if (q.page === 1) check(equal(d.history.items[0].after, facts(d.item)));
        d.history.items.forEach((h, i, rows) => {
          if (i + 1 < rows.length) check(h.previous_fact_ref === rows[i + 1].fact_ref && equal(h.before, rows[i + 1].after));
        });
      }
    }
    return v;
  }
  function preview(v, input) {
    const d = envelope(v, null, true);
    target(d.target, true);
    facts(d.after, v.meta.as_of);
    boundary(d.execution, d.target);
    check(equal(d.input, input) && d.outsourcing_ref === (input.outsourcing_ref || null) && d.can_confirm === true && object(d.write_context) && text(d.write_context.write_token) && d.write_context.capabilities.confirm === true);
    if (input.target) check(d.before === null && equal(target(d.target), input.target));else facts(d.before);
    check(equal(d.after, {
      ...(d.before || {}),
      ...Object.fromEntries(fields.filter(k => Object.prototype.hasOwnProperty.call(input, k)).map(k => [k, input[k]]))
    }));
    return v;
  }
  function receipt(v, intent) {
    const d = v && v.data;
    check(v && v.ok === true && v.result === 'committed' && /^[a-f0-9]{32}$/.test(v.receipt_ref) && typeof v.replayed === 'boolean' && Array.isArray(v.warnings) && object(d) && ref(d.outsourcing_ref) && ref(d.fact_ref) && (!intent.input.outsourcing_ref || d.outsourcing_ref === intent.input.outsourcing_ref) && equal(facts(d), intent.after) && equal(d.target, intent.target) && d.declared_operator === intent.input.declared_operator && d.reason === intent.input.reason && text(d.local_operator) && time(d.confirmed_at) && d.refresh_required === true, '保存结果和这条外协登记对不上，结果还不确定。请点「查询结果」，不要重复提交。');
    boundary(d.execution, d.target);
    return v;
  }
  function failure(v, status, intent) {
    const e = v && v.error,
      valid = v && v.ok === false && [false, 'unknown'].includes(v.committed) && object(e) && text(e.code) && text(e.message) && Array.isArray(e.fields);
    const error = new Error(valid ? e.message : '读到的结果无法确认，上次提交可能已经生效。请点「查询结果」，不要重复提交。');
    error.code = valid ? e.code : 'invalid_response';
    error.fields = valid ? e.fields : [];
    if (valid && v.committed === false && [400, 404, 409, 422, 503].includes(status) && e.code !== 'request_key_conflict') rejected.add(error);
    if (valid && v.committed === 'unknown' && intent && e.result_target !== undefined) check(e.request_key === intent.request_key && e.result_target === COMMANDS + intent.request_key, '返回的结果编号和上次提交对不上，这里没有读取其他结果。请点「查询结果」。');
    return error;
  }
  function create(fetcher = window.fetch.bind(window)) {
    async function request(url, body, signal, intent) {
      const controller = new AbortController(),
        abort = () => controller.abort(),
        timer = setTimeout(abort, 30000);
      if (signal) {
        signal.addEventListener('abort', abort, {
          once: true
        });
        if (signal.aborted) abort();
      }
      try {
        const r = await fetcher(url, {
          method: body === undefined ? 'GET' : 'POST',
          credentials: 'same-origin',
          cache: 'no-store',
          redirect: 'error',
          signal: controller.signal,
          ...(body === undefined ? {} : {
            headers: {
              'Content-Type': 'application/json'
            },
            body: JSON.stringify(body)
          })
        });
        check((r.headers.get('Content-Type') || '').split(';')[0].trim().toLowerCase() === 'application/json', '外协读到的数据不完整，请刷新后重试。');
        const v = await r.json();
        if (!r.ok || v.ok === false) throw failure(v, r.status, intent);
        check(r.status === 200);
        return v;
      } finally {
        clearTimeout(timer);
        if (signal) signal.removeEventListener('abort', abort);
      }
    }
    return {
      async read(kind, args = {}, selected, signal) {
        const q = query(kind, args);
        check(['targets', 'receipts', 'detail', 'history'].includes(kind));
        if (['detail', 'history'].includes(kind)) check(ref(selected));
        const path = ['targets', 'receipts'].includes(kind) ? '/' + kind : '/receipts/' + selected + (kind === 'history' ? '/history' : '');
        return catalog(await request(BASE + path + '?' + new URLSearchParams(q), undefined, signal), kind, q, selected);
      },
      async preview(input, signal) {
        return preview(await request(BASE + '/receipts/preview', {
          input
        }, signal), input);
      },
      async command(intent, token) {
        return receipt(await request(BASE + '/receipts', {
          input: intent.input,
          request_key: intent.request_key,
          write_token: token
        }, undefined, intent), intent);
      },
      async lookup(intent) {
        const v = await request(COMMANDS + intent.request_key, undefined, undefined, intent);
        if (v.state === 'not_recorded') {
          check(v.ok === true && v.receipt === null && v.may_be_in_flight === true);
          return null;
        }
        return receipt(v, intent);
      }
    };
  }
  window.OutsourcingContract = {
    states,
    fields,
    labels,
    object,
    ref,
    text,
    check,
    equal,
    time,
    stamp,
    facts,
    target,
    row,
    query,
    catalog,
    preview,
    receipt,
    create,
    isRejected: e => rejected.has(e)
  };
})();
