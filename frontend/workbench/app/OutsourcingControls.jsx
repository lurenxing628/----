(function () {
  'use strict';
  const C = window.OutsourcingContract, S = window.OutsourcingSession, { Button, ErrorBox, Issues, Modal } = window.ResourceControls;
  const value = v => v === null || v === undefined || v === '' ? '未填写' : typeof v === 'object' ? '原值格式待核实' : String(v);
  const when = v => v ? value(v).replace('T', ' ') : '未回厂';
  function Pager({ page, busy, onPage, onSize, label }) {
    return <div className="os-pager"><span>{page.total} 项 · 第 {page.number} / {Math.max(1, page.pages)} 页</span>
      {onSize && <label>每页<select aria-label={label + '每页数量'} value={page.size} disabled={busy} onChange={e => onSize(Number(e.target.value))}>
        {[2, 10, 20, 50, 100].concat(page.size).filter((v, i, a) => a.indexOf(v) === i).sort((a, b) => a - b).map(n => <option key={n}>{n}</option>)}</select></label>}
      <Button icon="chevron-left" aria-label={label + '上一页'} disabled={busy || page.number <= 1} onClick={() => onPage(page.number - 1)} />
      <Button icon="chevron-right" aria-label={label + '下一页'} disabled={busy || page.number >= page.pages} onClick={() => onPage(page.number + 1)} /></div>;
  }
  function Target({ target }) { return <section className="os-target" aria-label="本次外协成员"><div className="os-heading"><b>{value(target.batch.business_code)} · {value(target.batch.label)}</b>
    <span>{value(target.supplier.label)} · {target.kind === 'merged' ? '合并发出' : '单工序'} · {target.operations.length} 道工序</span></div>
    <div className="os-members">{target.operations.map(o => <span key={o.operation_ref}>{value(o.business_code)} · {value(o.label)}{o.piece !== null ? ' · 分件 ' + value(o.piece) : ''}</span>)}</div></section>; }
  function Facts({ facts, before }) { return <dl className="os-facts">{C.fields.map(k => <div key={k}><dt>{C.labels[k]}</dt><dd>
    {before && before[k] !== facts[k] && <del>{k === 'confirmedState' ? C.states[before[k]] : when(before[k])}</del>}
    <span>{k === 'confirmedState' ? C.states[facts[k]] : when(facts[k])}</span></dd></div>)}</dl>; }
  function TargetPicker({ api, mode, selected, onSelect, onMode, disabled, onOpen, batchRef }) {
    const [q, setQuery] = React.useState(() => ({ page: 1, size: 10, ...(batchRef ? { batch_ref: batchRef } : {}) }));
    const read = S.useRead(signal => api.read('targets', q, undefined, signal), [api, q]);
    const result = read.result, data = result && result.data;
    function change(patch, paging = false) { setQuery({ ...q, ...patch, page: paging ? patch.page : 1, ...(paging ? { snapshot_ref: result.meta.snapshot_ref } : {}) }); }
    function reset() { const next = { ...q, page: 1 }; delete next.snapshot_ref; setQuery(next); onSelect([]); }
    function choose(row, checked) { onSelect(mode === 'single' ? [row] : checked ? selected.concat(row) : selected.filter(r => r.operation_ref !== row.operation_ref)); }
    return <section aria-label="选择真实外协工序"><div className="os-heading"><div className="os-modes" role="radiogroup" aria-label="发出方式">
      {[['single', '单工序'], ['merged', '合并发出']].map(([k, label]) => <label key={k}><input type="radio" name="os-mode" value={k} checked={mode === k} disabled={disabled} onChange={() => { onSelect([]); onMode(k); }} />{label}</label>)}</div>
      <Button icon="refresh-cw" aria-label="明确刷新可登记工序" busy={read.loading} disabled={disabled} onClick={reset} /></div>
      <ErrorBox error={read.error} />{read.loading && <div className="os-empty" role="status">正在读取真实外协工序</div>}
      {data && <><div className="os-scroll os-pick-scroll"><table className="os-pick-table"><thead><tr><th>选择</th><th>工序 / 名称</th><th>批次 / 供应商</th><th>登记情况</th></tr></thead><tbody>
        {data.items.map((r, index) => { const chosen = selected.some(s => s.operation_ref === r.operation_ref), first = selected[0];
          const other = mode === 'merged' && first && (first.batch_ref !== r.batch_ref || first.supplier_ref !== r.supplier_ref);
          return <tr key={r.operation_ref || index} data-target-ref={r.operation_ref} data-selected={chosen}><td><input type={mode === 'single' ? 'radio' : 'checkbox'} name="os-member"
            aria-label={'选择工序 ' + value(r.business_code)} checked={chosen} disabled={disabled || !r.can_register || !!other || !chosen && selected.length >= 200}
            onChange={e => choose(r, e.target.checked)} /></td><td><b>{value(r.business_code)}</b><div>{value(r.label)}</div></td>
            <td>{r.batch ? (r.batch.business_code || '批次编号未知') + ' · ' + (r.batch.label || '批次名称未知') : '批次名称未知'}<div className="os-muted">{r.supplier && r.supplier.label || '供应商名称未知'}</div></td>
            <td>{r.outsourcing_ref ? <Button className="mini" icon="arrow-right" disabled={disabled} onClick={() => onOpen(r.outsourcing_ref)}>打开原登记</Button> : r.can_register ? other ? '不同批次 / 供应商' : '可登记' : '不可登记'}<Issues issues={r.issues} /></td></tr>; })}
      </tbody></table>{!data.items.length && <div className="os-empty">没有可读取的外协工序。</div>}</div>
      <Pager page={data.page} label="工序" busy={disabled || read.loading} onPage={page => change({ page }, true)} />
      <div className="os-selected" aria-label="已选择成员"><b>已选 {selected.length} 道</b>{selected.map(r => <span key={r.operation_ref}>{value(r.business_code)} · {value(r.label)}
        <Button className="mini" icon="x" aria-label={'移除工序 ' + value(r.business_code)} disabled={disabled} onClick={() => onSelect(selected.filter(s => s.operation_ref !== r.operation_ref))} /></span>)}</div></>}
    </section>;
  }
  function FormFields({ draft, update, disabled }) { return <div className="os-form">
    {['sent', 'planned', 'returned'].map(k => <label key={k}>{C.labels[k]}<input type="datetime-local" step="1" aria-label={C.labels[k]} value={draft[k]} disabled={disabled} onChange={e => update(k, e.target.value)} /></label>)}
    <label>确认状态<select aria-label="外协确认状态" value={draft.confirmedState} disabled={disabled} onChange={e => update('confirmedState', e.target.value)}>
      {Object.entries(C.states).map(([k, label]) => <option key={k} value={k}>{label}</option>)}</select></label>
    <label>声明人<input type="text" aria-label="外协声明人" maxLength={200} value={draft.declared_operator} disabled={disabled} onChange={e => update('declared_operator', e.target.value)} /></label>
    <div className="os-clear"><Button icon="x" disabled={disabled || !draft.returned} onClick={() => update('returned', '')}>清空实际回厂</Button></div>
    <label className="wide">本次核实 / 更正原因<textarea aria-label="外协核实原因" maxLength={2000} value={draft.reason} disabled={disabled} onChange={e => update('reason', e.target.value)} /></label>
  </div>; }
  function Pending({ command }) {
    const v = command.saved, done = v.phase === 'confirmed';
    return <><Target target={v.target} /><Facts facts={v.after} /><div className={'os-note ' + (done ? 'success' : 'warning')} role="status">
      {done ? '已确认：外协登记已保存，回厂不等于工序完工。' : v.phase === 'rejected' ? '本次明确未写入。' : '结果尚未确认，仅查询原请求。'}</div>
      <dl className="os-facts"><div><dt>原请求</dt><dd data-original-key>{v.request_key}</dd></div><div><dt>声明人</dt><dd>{v.input.declared_operator}</dd></div>
        <div><dt>核实原因</dt><dd>{v.input.reason}</dd></div>{done && <><div><dt>系统记录人</dt><dd>{v.receipt.data.local_operator}</dd></div><div><dt>确认时间</dt><dd>{when(v.receipt.data.confirmed_at)}</dd></div></>}</dl></>;
  }
  function Editor({ api, item, command, onClose, onFinish, onOpen, batchRef }) {
    const [draft, setDraft] = React.useState(() => ({ kind: 'single', sent: item ? item.sent : '', planned: item ? item.planned : '', returned: item && item.returned || '',
      confirmedState: item ? item.confirmedState : 'in_transit', declared_operator: '', reason: '' }));
    const [selected, setSelected] = React.useState([]), [preview, setPreview] = React.useState(null), [error, setError] = React.useState(null), [busy, setBusy] = React.useState(false);
    const alive = React.useRef(false), running = React.useRef(false);
    React.useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
    const locked = busy || command.busy, saved = command.saved;
    function update(k, v) { setDraft(d => ({ ...d, [k]: v })); setPreview(null); setError(null); }
    async function review() {
      if (running.current || saved || command.storageError) return;
      running.current = true; setBusy(true); setError(null);
      try { const p = S.input(draft, selected, item), result = await api.preview(p); if (alive.current) setPreview(result); }
      catch (e) { if (alive.current) setError(e); }
      finally { running.current = false; if (alive.current) setBusy(false); }
    }
    const footer = saved ? <>{saved.phase === 'pending' ? <Button icon="search" busy={command.busy} onClick={command.lookup}>查询原回执</Button> : <Button className="btn primary" icon="check" disabled={locked} onClick={onFinish}>完成核实并刷新</Button>}</> : <>
      <Button disabled={locked} onClick={onClose}>取消</Button>{preview ? <><Button icon="square-pen" disabled={locked} onClick={() => setPreview(null)}>返回修改</Button>
        <Button className="btn primary" icon="check" busy={locked} disabled={!!command.storageError} onClick={() => command.submit(preview)}>确认保存外协登记</Button></> :
        <Button className="btn primary" icon="search" busy={locked} disabled={!!command.storageError} onClick={review}>预览核对</Button>}</>;
    return <Modal title={saved ? '外协登记回执' : item ? '核实 / 更正外协登记' : '新建外协登记'} icon="truck" onClose={onClose} locked={locked} footer={footer}>
      <div className="os-dialog-body"><ErrorBox error={command.storageError || error || command.error} />
        {saved ? <Pending command={command} /> : preview ? <><Target target={preview.data.target} /><Facts facts={preview.data.after} before={preview.data.before} />
          <dl className="os-facts"><div><dt>声明人</dt><dd>{preview.data.input.declared_operator}</dd></div><div><dt>核实原因</dt><dd>{preview.data.input.reason}</dd></div></dl>
          <div className="os-note">{preview.data.execution.reason}</div><div className="os-muted">核对时点 {when(preview.meta.as_of)} · 工厂本地时间</div></> : <>
          {item ? <Target target={item.target} /> : <TargetPicker api={api} mode={draft.kind} selected={selected} onSelect={setSelected} onMode={v => update('kind', v)} disabled={locked} onOpen={onOpen} batchRef={batchRef} />}
          <FormFields draft={draft} update={update} disabled={locked} /></>}
        {command.notice && <div className="os-note" role="status">{command.notice}</div>}
      </div></Modal>;
  }
  window.OutsourcingControls = { value, when, Pager, Target, Facts, TargetPicker, FormFields, Pending, Editor };
})();
