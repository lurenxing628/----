(function () {
  'use strict';
  const C = window.OutsourcingContract, S = window.OutsourcingSession, P = window.OutsourcingControls, { Button, ErrorBox, Issues } = window.ResourceControls;
  const { EmptyState } = window.WorkbenchListControls;
  function Records({ api, selected, revision, onEdit, onClose, blocked }) {
    const [q, setQuery] = React.useState({ page: 1, size: 10 });
    const read = S.useRead(signal => api.read('history', q, selected, signal), [api, q, selected, revision]);
    const result = read.result, data = result && result.data, item = data && data.item;
    function reload() { const next = { ...q, page: 1 }; delete next.snapshot_ref; setQuery(next); }
    function change(patch, paging = false) { const next = { ...q, ...patch, page: paging ? patch.page : 1 }; delete next.snapshot_ref;
      if (paging) next.snapshot_ref = result.meta.snapshot_ref; setQuery(next); }
    return <section className="os-detail" aria-label="外协登记与历史"><div className="os-heading"><h4>登记详情与核实历史</h4><div className="os-tools">
      <Button icon="refresh-cw" aria-label="明确刷新原登记历史" busy={read.loading} onClick={reload} /><Button icon="x" aria-label="收起外协详情" onClick={onClose} /></div></div>
      <ErrorBox error={read.error} />{read.loading && <EmptyState kind="loading" title="正在读取原登记和同一快照历史" />}
      {item && <div data-outsourcing-detail={item.outsourcing_ref}><P.Target target={item.target} /><Issues issues={item.issues} /><P.Facts facts={item} />
        <div className="os-heading"><span className="os-muted">数据截至 {P.when(result.meta.as_of)} · 工厂本地时间</span>
          <Button icon="square-pen" disabled={blocked} reason={!item.can_preview ? '原来源已变化，历史保留，不能改绑新对象。' : ''} onClick={() => onEdit(item)}>核实 / 更正登记</Button></div>
        {data.history.items.map((h, i) => <details className="os-history" key={h.fact_ref} data-fact-ref={h.fact_ref}>
          <summary>第 {data.history.page.total - (q.page - 1) * q.size - i} 次 · {P.when(h.confirmed_at)} · {h.declared_operator} · {C.states[h.after.confirmedState]}</summary>
          <P.Facts facts={h.after} before={h.before} /><p>{h.reason}</p><div className="os-muted">系统记录人 {h.local_operator}</div><window.WorkbenchReference entries={{ '历史编号': h.fact_ref }} />
        </details>)}
        <P.Pager page={data.history.page} label="外协历史" busy={read.loading} onPage={page => change({ page }, true)} onSize={size => change({ size })} />
      </div>}
    </section>;
  }
  function Content({ batchRef, outsourcingRef, onUpdated }) {
    const api = React.useMemo(() => C.create(), []), command = S.useCommand(api);
    const [q, setQuery] = React.useState(() => ({ page: 1, size: 10, status: 'all', ...(batchRef ? { batch_ref: batchRef } : {}) }));
    const [selected, setSelected] = React.useState(outsourcingRef || null), [dialog, setDialog] = React.useState(null), [revision, refresh] = React.useReducer(n => n + 1, 0);
    const read = S.useRead(signal => api.read('receipts', q, undefined, signal), [api, q, revision]);
    const result = read.result, data = result && result.data, blocked = command.busy || !!command.saved || !!command.storageError;
    function change(patch, paging = false) { const next = { ...q, ...patch, page: paging ? patch.page : 1 }; delete next.snapshot_ref;
      if (paging) next.snapshot_ref = result.meta.snapshot_ref; setQuery(next); }
    function reload() { change({}); refresh(); }
    function open(ref) { setSelected(ref); setDialog(null); }
    function finish() {
      const ref = command.saved && command.saved.phase === 'confirmed' && command.saved.receipt.data.outsourcing_ref;
      if (command.finish()) { setDialog(null); if (ref) setSelected(ref); reload(); if (typeof onUpdated === 'function') onUpdated(); }
    }
    return <section className="outsourcing-live" aria-label="真实外协登记" data-outsourcing-workspace data-ready={!!data}><window.OutsourcingStyles />
      <div className="os-heading"><h3>外协发出与回厂登记</h3><div className="os-tools"><label>登记筛选<select aria-label="外协登记筛选" value={q.status} disabled={read.loading} onChange={e => change({ status: e.target.value })}>
        {[['all', '全部登记'], ['awaiting', '待回厂'], ['overdue', '超期未回'], ['returned', '已回厂']].map(([k, label]) => <option key={k} value={k}>{label}</option>)}</select></label>
        <Button icon="refresh-cw" aria-label="明确刷新外协登记" busy={read.loading} disabled={command.busy} onClick={reload} />
        <Button className="btn primary" icon="plus" disabled={blocked} onClick={() => setDialog({ item: null })}>新建外协登记</Button></div></div>
      <ErrorBox error={command.storageError} />{command.storageError && <Button icon="refresh-cw" onClick={command.sync}>重读原外协请求记录</Button>}
      {command.saved && <div className="os-note warning"><div className="os-heading"><span>{command.saved.phase === 'pending' ? '存在未核实的原外协请求，不可换 key 重做。' : '原外协回执待完成核实。'}</span>
        <Button icon="history" onClick={() => setDialog({ item: null })}>{command.saved.phase === 'confirmed' ? '查看已确认外协回执' : '核实原外协请求'}</Button></div></div>}
      <ErrorBox error={read.error} />{read.loading && <EmptyState kind="loading" title="正在读取外协真实登记" />}
      {data && <><div className="os-muted">数据截至 {P.when(result.meta.as_of)} · 工厂本地时间</div><div className="os-scroll os-register-scroll wb-table-shell wb-table-frame" data-sticky-head data-sticky-actions><table className="os-table wb-table"><caption className="wb-visually-hidden">外协发出与回厂登记</caption><thead><tr>
        <th scope="col" className="wb-col-key">批次 / 成员</th><th scope="col">供应商 / 状态</th><th scope="col">实际发出</th><th scope="col">计划 / 实际回厂</th><th scope="col" className="wb-col-actions">操作</th></tr></thead><tbody>{data.items.map(r => <tr key={r.outsourcing_ref} data-outsourcing-ref={r.outsourcing_ref} data-selected={selected === r.outsourcing_ref} aria-selected={selected === r.outsourcing_ref}>
          <td className="wb-col-key"><b>{P.value(r.target.batch.business_code)} · {P.value(r.target.batch.label)}</b><div className="os-muted">{r.target.kind === 'merged' ? '合并发出' : '单工序'} · {r.target.operations.map(o => P.value(o.business_code)).join('、')}</div></td>
          <td>{P.value(r.target.supplier.label)}<div><span className={'os-state ' + (r.overdue ? 'danger' : !r.awaiting_return ? 'success' : r.confirmedState === 'awaiting_confirmation' ? 'warning' : '')}>{r.overdue ? '超期未回 · ' : ''}{C.states[r.confirmedState]}</span></div></td>
          <td>{P.when(r.sent)}</td><td>{P.when(r.planned)}<div className="os-muted">{r.returned === null ? '未回厂' : P.when(r.returned)}</div></td>
          <td className="wb-col-actions"><Button className="mini" icon="search" aria-label={'查看外协登记 ' + r.target.operations.map(o => P.value(o.business_code)).join('、')} onClick={() => open(r.outsourcing_ref)}>详情</Button></td></tr>)}</tbody></table></div>
        {!data.items.length && <EmptyState kind={q.status === 'all' ? 'empty' : 'filtered'} title={data.page.total ? '当前页没有登记' : '当前筛选没有外协登记'}
          hint="可以调整筛选查看已有登记，也可在有真实外协工序时新建登记。"
          action={q.status !== 'all' ? <Button disabled={read.loading} onClick={() => change({ status: 'all' })}>查看全部登记</Button> : undefined} />}
        <P.Pager page={data.page} label="外协登记" busy={read.loading} onPage={page => change({ page }, true)} onSize={size => change({ size })} /></>}
      {selected && <Records key={selected + ':' + revision} api={api} selected={selected} revision={revision} onEdit={item => setDialog({ item })} onClose={() => setSelected(null)} blocked={blocked} />}
      {dialog && <P.Editor key={command.saved ? command.saved.request_key : dialog.item ? dialog.item.latest_fact_ref : 'create'} api={api} item={dialog.item} batchRef={batchRef}
        command={command} onClose={() => setDialog(null)} onFinish={finish} onOpen={open} />}
    </section>;
  }
  function OutsourcingWorkspace({ batchRef, outsourcingRef, onUpdated }) {
    if (batchRef !== undefined && !C.ref(batchRef) || outsourcingRef !== undefined && !C.ref(outsourcingRef)) return <ErrorBox error={new Error('外协登记上下文不是有效的原对象引用。')} />;
    return <Content key={(batchRef || '') + ':' + (outsourcingRef || '')} batchRef={batchRef} outsourcingRef={outsourcingRef} onUpdated={onUpdated} />;
  }
  window.OutsourcingWorkspace = OutsourcingWorkspace;
})();
