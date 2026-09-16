(function () {
  'use strict';
  const C = window.OutsourcingContract, S = window.OutsourcingSession, { Button, ErrorBox, Issues, Modal, Field, focusFirstInvalid } = window.ResourceControls;
  const { EmptyState } = window.WorkbenchListControls;
  const formPaths = ['sent', 'planned', 'returned', 'confirmedState', 'declared_operator', 'reason'];
  const value = v => v === null || v === undefined || v === '' ? '未填写' : typeof v === 'object' ? '原值格式不对' : String(v);
  const when = v => window.WorkbenchFormat.dateTime(v, { seconds: true });
  function Pager({ page, busy, onPage, onSize, label }) {
    return <window.WorkbenchListControls.Pager page={page} sizes={[2, 10, 20, 50, 100].concat(page.size).filter((v, i, all) => all.indexOf(v) === i).sort((a, b) => a - b)}
      label={label} sizeLabel={label + '每页数量'} disabled={busy} onPage={onPage} onSize={onSize} />;
  }
  function Target({ target }) { return <section className="os-target" aria-label="本次外协成员"><div className="os-heading"><b>{value(target.batch.business_code)} · {value(target.batch.label)}</b>
    <span>{value(target.supplier.label)} · {target.kind === 'merged' ? '合并发出' : '单工序'} · {target.operations.length} 道工序</span></div>
    {target.part && <div className="os-muted">图号：{value(target.part.business_code)} · {value(target.part.label)}</div>}
    <div className="os-members">{target.operations.map(o => <span key={o.operation_ref}>{value(o.business_code)} · {value(o.label)}{o.piece !== null ? ' · 分件 ' + value(o.piece) : ''}</span>)}</div>
    {target.source_resolution && target.source_resolution.basis === 'current_relation' && <div className="os-muted">这批旧工序按本页列出的批次登记。</div>}</section>; }
  function Facts({ facts, before }) { return <dl className="os-facts">{C.fields.map(k => <div key={k}><dt>{C.labels[k]}</dt><dd>
    {before && before[k] !== facts[k] && <del>{k === 'confirmedState' ? C.states[before[k]] : k === 'returned' && before[k] === null ? '未回厂' : when(before[k])}</del>}
    <span>{k === 'confirmedState' ? C.states[facts[k]] : k === 'returned' && facts[k] === null ? '未回厂' : when(facts[k])}</span></dd></div>)}</dl>; }
  function TargetPicker({ api, mode, selected, onSelect, onMode, disabled, onOpen, batchRef }) {
    const [q, setQuery] = React.useState(() => ({ page: 1, size: 10, ...(batchRef ? { batch_ref: batchRef } : {}) }));
    const read = S.useRead(signal => api.read('targets', q, undefined, signal), [api, q]);
    const result = read.result, data = result && result.data;
    function change(patch, paging = false) { setQuery({ ...q, ...patch, page: paging ? patch.page : 1, ...(paging ? { snapshot_ref: result.meta.snapshot_ref } : {}) }); }
    function reset() { const next = { ...q, page: 1 }; delete next.snapshot_ref; setQuery(next); onSelect([]); }
    function choose(row, checked) { onSelect(mode === 'single' ? [row] : checked ? selected.concat(row) : selected.filter(r => r.operation_ref !== row.operation_ref)); }
    return <section aria-label="选择外协工序"><div className="os-heading"><div className="os-modes" role="radiogroup" aria-label="发出方式">
      {[['single', '单工序'], ['merged', '合并发出']].map(([k, label]) => <label key={k}><input type="radio" name="os-mode" value={k} checked={mode === k} disabled={disabled} onChange={() => { onSelect([]); onMode(k); }} />{label}</label>)}</div>
      <Button icon="refresh-cw" aria-label="刷新可登记工序" busy={read.loading} disabled={disabled} onClick={reset} /></div>
      <ErrorBox error={read.error} />{read.loading && <EmptyState kind="loading" title="正在读取外协工序" />}
      {data && <><div className="os-scroll os-pick-scroll wb-table-shell wb-table-frame" data-sticky-head data-sticky-actions><table className="os-pick-table wb-table"><caption className="wb-visually-hidden">可登记的外协工序</caption><thead><tr><th scope="col" className="wb-col-key">选择</th><th scope="col" className="wb-col-key os-operation-key">工序 / 名称</th><th scope="col">批次 / 供应商</th><th scope="col" className="wb-col-actions">登记情况</th></tr></thead><tbody>
        {data.items.map((r, index) => { const chosen = selected.some(s => s.operation_ref === r.operation_ref), first = selected[0];
          const other = mode === 'merged' && first && (first.batch_ref !== r.batch_ref || first.supplier_ref !== r.supplier_ref);
          return <tr key={r.operation_ref || index} data-target-ref={r.operation_ref} data-selected={chosen} aria-selected={chosen}><td className="wb-col-key"><input type={mode === 'single' ? 'radio' : 'checkbox'} name="os-member"
            aria-label={'选择工序 ' + value(r.business_code)} checked={chosen} disabled={disabled || !r.can_register || !!other || !chosen && selected.length >= 200}
            onChange={e => choose(r, e.target.checked)} /></td><td className="wb-col-key os-operation-key"><b>{value(r.business_code)}</b><div>{value(r.label)}</div></td>
            <td>{r.batch ? (r.batch.business_code || '编号未填写') + ' · ' + (r.batch.label || '名称未填写') : '批次未读取'}<div className="os-muted">{r.supplier && r.supplier.label || '供应商名称未填写'}</div></td>
            <td className="wb-col-actions">{r.outsourcing_ref ? <Button className="mini" icon="arrow-right" disabled={disabled} onClick={() => onOpen(r.outsourcing_ref)}>打开已有登记</Button> : r.can_register ? other ? '不同批次 / 供应商' : '可登记' : '不可登记'}<Issues issues={r.issues} /></td></tr>; })}
      </tbody></table></div>{!data.items.length && <EmptyState kind="empty" title="没有可读取的外协工序" hint="可刷新工序列表，或返回资源资料核对外协工艺。" />}
      <Pager page={data.page} label="工序" busy={disabled || read.loading} onPage={page => change({ page }, true)} />
      <div className="os-selected" aria-label="已选择成员"><b>已选 {selected.length} 道</b>{selected.map(r => <span key={r.operation_ref}>{value(r.business_code)} · {value(r.label)}
        <Button className="mini" icon="x" aria-label={'移除工序 ' + value(r.business_code)} disabled={disabled} onClick={() => onSelect(selected.filter(s => s.operation_ref !== r.operation_ref))} /></span>)}</div></>}
    </section>;
  }
  function FormFields({ draft, update, disabled, error }) { return <div className="os-form">
    {['sent', 'planned', 'returned'].map(k => <Field key={k} label={C.labels[k]} path={k} error={error} required={k !== 'returned'}><input type="datetime-local" step="1" aria-label={C.labels[k]} value={draft[k]} disabled={disabled} onChange={e => update(k, e.target.value)} /></Field>)}
    <Field label="确认状态" path="confirmedState" error={error} required><select aria-label="外协确认状态" value={draft.confirmedState} disabled={disabled} onChange={e => update('confirmedState', e.target.value)}>
      {Object.entries(C.states).map(([k, label]) => <option key={k} value={k}>{label}</option>)}</select></Field>
    <Field label="经办人" path="declared_operator" error={error} required><input type="text" aria-label="外协经办人" maxLength={200} value={draft.declared_operator} disabled={disabled} onChange={e => update('declared_operator', e.target.value)} /></Field>
    <div className="os-clear"><Button icon="x" disabled={disabled || !draft.returned} onClick={() => update('returned', '')}>清除实际回厂</Button></div>
    <Field label="本次核实 / 更正原因" path="reason" error={error} required full><textarea aria-label="外协核实原因" maxLength={2000} value={draft.reason} disabled={disabled} onChange={e => update('reason', e.target.value)} /></Field>
  </div>; }
  function Pending({ command }) {
    const v = command.saved, done = v.phase === 'confirmed';
    return <><Target target={v.target} /><Facts facts={v.after} /><div className={'os-note ' + (done ? 'success' : 'warning')} role="status">
      {done ? window.WorkbenchTerms.outcomes.done('外协登记') : v.phase === 'rejected' ? '上次外协登记没有生效，填写内容已保留。改好后重新提交。' : window.WorkbenchTerms.outcomes.pending('外协登记')}</div>
      <div data-original-key><window.WorkbenchReference entries={{ '操作编号': v.request_key }} /></div>
      <dl className="os-facts"><div><dt>经办人</dt><dd>{v.input.declared_operator}</dd></div>
        <div><dt>核实原因</dt><dd>{v.input.reason}</dd></div>{done && <><div><dt>记录人</dt><dd>{v.receipt.data.local_operator}</dd></div><div><dt>确认时间</dt><dd>{when(v.receipt.data.confirmed_at)}</dd></div></>}</dl></>;
  }
  function Editor({ api, item, command, onClose, onFinish, onOpen, batchRef }) {
    const [draft, setDraft] = React.useState(() => ({ kind: 'single', sent: item ? item.sent : '', planned: item ? item.planned : '', returned: item && item.returned || '',
      confirmedState: item ? item.confirmedState : 'in_transit', declared_operator: '', reason: '' }));
    const [selected, setSelected] = React.useState([]), [preview, setPreview] = React.useState(null), [error, setError] = React.useState(null), [busy, setBusy] = React.useState(false);
    const alive = React.useRef(false), running = React.useRef(false), formRef = React.useRef(null), errorRef = React.useRef(null), initialDraft = React.useRef(JSON.stringify(draft)), editorId = React.useId();
    React.useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
    const locked = busy || command.busy, saved = command.saved;
    const guardOwner = window.WorkbenchGuards.useDirtyGuard({ owner: 'outsourcing-' + editorId,
      dirty: !saved && (selected.length > 0 || JSON.stringify(draft) !== initialDraft.current), locked: command.busy, message: '外协登记有尚未保存的填写内容。' });
    async function close() { if (!locked && await window.WorkbenchGuards.confirmLeave({ owner: guardOwner })) onClose(); }
    async function openExisting(ref) { if (!locked && await window.WorkbenchGuards.confirmLeave({ owner: guardOwner })) onOpen(ref); }
    React.useEffect(() => {
      if (error && !focusFirstInvalid(formRef.current) && errorRef.current) errorRef.current.focus();
    }, [error]);
    function update(k, v) { setDraft(d => ({ ...d, [k]: v })); setPreview(null); setError(null); }
    async function review() {
      if (running.current || saved || command.storageError) return;
      running.current = true; setBusy(true); setError(null);
      try { const p = S.input(draft, selected, item), result = await api.preview(p); if (alive.current) setPreview(result); }
      catch (e) { if (alive.current) setError(e); }
      finally { running.current = false; if (alive.current) setBusy(false); }
    }
    const footer = saved ? <>{saved.phase === 'pending' ? <Button icon="search" busy={command.busy} onClick={command.lookup}>查询结果</Button> : <Button className="btn primary" icon="check" disabled={locked} onClick={onFinish}>完成</Button>}</> : <>
      <Button disabled={locked} onClick={close}>取消</Button>{preview ? <><Button icon="square-pen" disabled={locked} onClick={() => setPreview(null)}>返回修改</Button>
        <Button className="btn primary" icon="check" busy={locked} disabled={!!command.storageError} onClick={() => command.submit(preview)}>确认保存外协登记</Button></> :
        <Button className="btn primary" icon="search" busy={locked} disabled={!!command.storageError} onClick={review}>预检核对</Button>}</>;
    return <Modal title={saved ? '外协登记结果' : item ? '核实 / 更正外协登记' : '新增外协登记'} icon="truck" onClose={onClose} guardOwner={guardOwner} locked={locked} footer={footer}>
      <div className="os-dialog-body" ref={formRef}><div tabIndex={-1} ref={errorRef}><ErrorBox error={command.storageError || error || command.error} excludePaths={saved || preview ? [] : formPaths} /></div>
        {saved ? <Pending command={command} /> : preview ? <><Target target={preview.data.target} /><Facts facts={preview.data.after} before={preview.data.before} />
          <dl className="os-facts"><div><dt>经办人</dt><dd>{preview.data.input.declared_operator}</dd></div><div><dt>核实原因</dt><dd>{preview.data.input.reason}</dd></div></dl>
          <div className="os-note">{preview.data.execution.reason}</div><div className="os-muted">核对时点 {when(preview.meta.as_of)}</div></> : <>
          {item ? <Target target={item.target} /> : <TargetPicker api={api} mode={draft.kind} selected={selected} onSelect={setSelected} onMode={v => update('kind', v)} disabled={locked} onOpen={openExisting} batchRef={batchRef} />}
          <FormFields draft={draft} update={update} disabled={locked} error={error} /></>}
        {command.notice && <div className="os-note" role="status">{command.notice}</div>}
      </div></Modal>;
  }
  window.OutsourcingControls = { value, when, Pager, Target, Facts, TargetPicker, FormFields, Pending, Editor };
})();
