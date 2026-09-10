(function () {
  'use strict';
  const C = window.OutsourcingContract, KEY = 'aps_outsourcing_pending_v1', EVENT = KEY + '_changed';
  function originalInput(v) {
    const p = v.input, creating = Object.prototype.hasOwnProperty.call(p, 'target');
    const allowed = ['declared_operator', 'reason', creating ? 'target' : 'outsourcing_ref', ...C.fields];
    return Object.keys(p).every(k => allowed.includes(k)) && ['declared_operator', 'reason'].every(k => C.text(p[k]) && p[k] === p[k].trim() && !p[k].includes('\0'))
      && p.declared_operator.length <= 200 && p.reason.length <= 2000 && C.fields.every(k => creating || Object.prototype.hasOwnProperty.call(p, k) ? p[k] === v.after[k] : true)
      && (creating ? C.equal(p.target, C.target(v.target)) : C.ref(p.outsourcing_ref));
  }
  function valid(v) {
    try { return v && v.version === 1 && /^outsourcing-[a-f0-9]{48}$/.test(v.request_key) && ['pending', 'confirmed', 'rejected'].includes(v.phase)
      && C.object(v.input) && !!C.facts(v.after) && !!C.target(v.target, true) && originalInput(v) && !Object.prototype.hasOwnProperty.call(v, 'write_token')
      && (v.phase !== 'confirmed' || !!C.receipt(v.receipt, v)); } catch (_) { return false; }
  }
  function read() {
    let raw; try { raw = localStorage.getItem(KEY); } catch (_) { throw new Error('原外协请求记录不可读，不能开始新的登记。'); }
    if (raw === null) return null;
    let v; try { v = JSON.parse(raw); } catch (_) { throw new Error('原外协请求记录损坏，请保留现场。'); }
    C.check(valid(v), '原外协请求不完整，不能换请求重做。'); return v;
  }
  function save(v, previous) {
    C.check(C.equal(read(), previous), '原外协请求已在其他页面变化，未覆盖。'); C.check(v === null || valid(v));
    try { if (v === null) localStorage.removeItem(KEY); else localStorage.setItem(KEY, JSON.stringify(v)); }
    catch (_) { throw new Error('原外协请求无法持久保存，未开始登记。'); }
    C.check(C.equal(read(), v)); window.dispatchEvent(new Event(EVENT)); return v;
  }
  function useCommand(api) {
    const [initial] = React.useState(() => { try { return { saved: read() }; } catch (error) { return { saved: null, error }; } });
    const [saved, setSaved] = React.useState(initial.saved), [storageError, setStorageError] = React.useState(initial.error || null);
    const [error, setError] = React.useState(null), [notice, setNotice] = React.useState(''), [busy, setBusy] = React.useState(false);
    const active = React.useRef(saved), running = React.useRef(false), mounted = React.useRef(false); active.current = saved;
    function sync() { try { const v = read(); active.current = v; setSaved(v); setStorageError(null); } catch (e) { setStorageError(e); } }
    React.useEffect(() => {
      mounted.current = true; const changed = e => { if (!e.key || e.key === KEY) sync(); };
      window.addEventListener('storage', changed); window.addEventListener(EVENT, changed);
      return () => { mounted.current = false; window.removeEventListener('storage', changed); window.removeEventListener(EVENT, changed); };
    }, []);
    function accept(v, original) {
      C.receipt(v, original); save({ ...original, phase: 'confirmed', receipt: v }, original);
      if (mounted.current) { setError(null); setNotice('外协回执已确认。'); }
    }
    async function lookup() {
      if (running.current || !active.current || active.current.phase !== 'pending') return;
      const original = active.current; running.current = true; setBusy(true); setError(null);
      try { const v = await api.lookup(original); if (v) accept(v, original); else if (mounted.current) setNotice('尚未查到原回执，原请求仍可能完成；保留原 key，不重新提交。'); }
      catch (e) { if (mounted.current) setError(e); }
      finally { running.current = false; if (mounted.current) setBusy(false); }
    }
    React.useEffect(() => { if (initial.saved && initial.saved.phase === 'pending') lookup(); }, []);
    async function submit(preview) {
      if (running.current || storageError || active.current) return;
      running.current = true; setBusy(true); setError(null); setNotice(''); let original;
      try {
        C.check(navigator.locks && typeof navigator.locks.request === 'function', '浏览器请求锁不可用，不能开始登记。');
        await navigator.locks.request(KEY, { ifAvailable: true }, async lock => {
          C.check(lock && read() === null, '存在其他页面的原外协请求，请先核实。');
          const d = C.preview(preview, preview.data.input).data;
          original = { version: 1, phase: 'pending', request_key: 'outsourcing-' + Array.from(crypto.getRandomValues(new Uint8Array(24)), n => n.toString(16).padStart(2, '0')).join(''),
            input: d.input, after: d.after, target: d.target };
          save(original, null);
          try { accept(await api.command(original, d.write_context.write_token), original); }
          catch (e) {
            if (C.isRejected(e)) save({ ...original, phase: 'rejected' }, original);
            if (mounted.current) { setError(e); setNotice(C.isRejected(e) ? '本次明确未写入，请完成核实后刷新。' : '结果尚未确认，仅查询原请求。'); }
          }
        });
      } catch (e) { if (mounted.current) setStorageError(e); }
      finally { running.current = false; if (mounted.current) setBusy(false); }
      if (original && active.current && active.current.phase === 'pending') await lookup();
    }
    function finish() {
      if (running.current) return false;
      try { const v = read(); C.check(v && v.phase !== 'pending', '未知结果不能丢弃原请求。'); save(null, v); setError(null); setNotice(''); return true; }
      catch (e) { setStorageError(e); return false; }
    }
    return { saved, storageError, error, notice, busy, sync, submit, lookup, finish };
  }
  function useRead(load, deps, enabled = true) { return window.APSResourceSession.useQuery(load, deps, enabled); }
  function input(draft, selected, item, now) {
    const values = { sent: C.stamp(draft.sent), planned: C.stamp(draft.planned), returned: draft.returned ? C.stamp(draft.returned) : null, confirmedState: draft.confirmedState };
    C.facts(values, now);
    const p = { declared_operator: draft.declared_operator.trim(), reason: draft.reason.trim() };
    C.check(p.declared_operator && p.declared_operator.length <= 200 && !p.declared_operator.includes('\0') && p.reason && p.reason.length <= 2000 && !p.reason.includes('\0'), '请填写声明人和本次核实 / 更正原因。');
    if (item) { p.outsourcing_ref = item.outsourcing_ref; C.fields.forEach(k => { if (values[k] !== item[k]) p[k] = values[k]; }); }
    else {
      C.check(selected.length > 0 && selected.every(r => r.can_register && r.batch_ref === selected[0].batch_ref && r.supplier_ref === selected[0].supplier_ref), '请选择同一批次、同一供应商的真实可登记工序。');
      p.target = C.target({ kind: draft.kind, batch_ref: selected[0].batch_ref, supplier_ref: selected[0].supplier_ref, operation_refs: selected.map(r => r.operation_ref) }); Object.assign(p, values);
    }
    return p;
  }
  window.OutsourcingSession = { KEY, valid, read, save, useCommand, useRead, input };
})();
