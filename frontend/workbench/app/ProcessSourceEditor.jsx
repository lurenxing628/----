(function () {
  'use strict';
  const C = window.APSResourceContract, P = window.APSProcessContract, S = window.APSResourceSession;
  const E = window.ProcessStageEditor, { Button, Modal, ErrorBox, Issues } = window.ResourceControls;
  function build(entity) {
    return Object.fromEntries(E.active(entity).map(row => [row.ref, { ref: row.ref, source: row.source, op_type_ref: row.op_type_ref,
      op_type_label: row.op_type_label, supplier_ref: row.supplier_ref, supplier_label: row.supplier_label,
      confirmed: !!(row.confirmation && row.confirmation.source.state === 'confirmed') }]));
  }
  function reconcile(draft, before, after) {
    const next = build(after), original = build(before), old = new Map(before.operations.map(row => [row.ref, row]));
    const oldGroups = new Map(before.external_groups.map(row => [row.ref, row])), newGroups = new Map(after.external_groups.map(row => [row.ref, row]));
    E.active(after).forEach(row => {
      const current = draft[row.ref], previous = original[row.ref], fresh = next[row.ref];
      fresh.confirmed = false;
      if (!current || !previous) return;
      if (current.source !== previous.source) fresh.source = current.source;
      [['op_type_ref', 'op_type_label'], ['supplier_ref', 'supplier_label']].forEach(([ref, label]) => {
        if (current[ref] === previous[ref]) return;
        if (current[ref] !== fresh[ref]) fresh[label] = current[label];
        fresh[ref] = current[ref];
      });
      fresh.confirmed = E.same(old.get(row.ref), row) && E.same(oldGroups.get(row.external_group_ref), newGroups.get(row.external_group_ref)) && current.confirmed;
    });
    return next;
  }
  function input(entity, draft) {
    const operations = E.active(entity).map(row => {
      const current = draft[row.ref];
      if (!current.confirmed || !['internal', 'external'].includes(current.source) || !current.op_type_ref || current.source === 'external' && !current.supplier_ref)
        throw C.failure('请逐序核对归属、绑定真实工种及外协供应商，并明确勾选确认。', [{ path: 'operations.' + row.sequence, message: '工序 ' + row.sequence + ' 尚未完整确认。' }]);
      return { ref: row.ref, source: current.source, op_type_ref: current.op_type_ref, supplier_ref: current.source === 'internal' ? null : current.supplier_ref, confirmed: true };
    });
    if (!operations.length) throw C.failure('尚无有效工序，不能确认归属。');
    return { operations, discard_group_refs: [] };
  }
  function Picker({ adapter, target, onSelect, onClose, disabled }) {
    const [search, setSearch] = React.useState(''), [scope, setScope] = React.useState({ query: '', page: 1, size: 50 });
    const read = S.useQuery(async signal => {
      if (typeof adapter.choices !== 'function') throw C.failure('关系选项读取接口尚未接入。');
      return C.query(await adapter.choices(target.kind, { ...scope, ...(target.kind === 'op_type' ? { category: target.source } : {}) }, signal), 'choices');
    }, [adapter, target.kind, target.source, scope]);
    const data = read.result && read.result.data, title = target.kind === 'op_type' ? P.sourceLabel(target.source) + '工种' : '供应商';
    return <Modal title={'选择' + title + ' · 工序 ' + target.sequence} icon="search" onClose={onClose} locked={disabled} footer={<Button onClick={onClose} disabled={disabled}>取消</Button>}>
      <div className="modal-b scroll"><form className="toolbar" onSubmit={event => { event.preventDefault(); setScope({ query: search, page: 1, size: 50 }); }}>
        <label className="search"><input type="search" aria-label={'搜索' + title} value={search} onChange={event => setSearch(event.target.value)} disabled={disabled} /></label><Button type="submit" icon="search" disabled={disabled}>搜索</Button></form>
        <ErrorBox error={read.error} />{read.error && <Button icon="refresh-cw" onClick={() => setScope({ query: search, page: 1, size: 50 })}>重读选项</Button>}
        {read.loading && <p role="status">正在读取选项…</p>}
        {data && <><Issues issues={read.result.warnings} /><div className="wb-table-frame"><table className="tbl wb-table" aria-label={title + '选项'} style={{ width: '100%', tableLayout: 'fixed' }}><caption className="wb-visually-hidden">{title + '选项'}</caption><thead><tr><th scope="col">编号</th><th scope="col">名称</th><th scope="col">选择</th></tr></thead>
          <tbody>{data.entities.map(row => <tr key={row.ref}><td>{row.business_code}</td><td>{row.label}</td><td><Button icon="check" disabled={disabled || !(row.status === 'active' || target.kind === 'op_type' && row.status === null) || target.kind === 'op_type' && row.fields.category !== target.source}
            aria-label={'选用 ' + row.label} onClick={() => onSelect(row)}>选用</Button></td></tr>)}{!data.entities.length && <tr><td colSpan={3}>没有匹配选项。</td></tr>}</tbody></table></div>
          <window.ResourceTables.Pager page={data.page} disabled={disabled || read.loading} onPage={page => setScope(current => ({ ...current, page, snapshot_ref: read.result.meta.snapshot_ref }))}
            onSize={size => setScope(current => ({ ...current, size, page: 1, snapshot_ref: undefined }))} /></>}
      </div></Modal>;
  }
  function ProcessSourceEditor({ adapter, result, command, disabled, saved, onDirty, onOverlay, onResourceCommitted }) {
    const model = E.useDraft({ result, adapter, stage: 'source', build, reconcile, saved, onDirty });
    const entity = model.base.data, draft = model.draft, rows = entity.operations, paging = E.usePage(rows);
    const [picker, setPicker] = React.useState(null), [create, setCreate] = React.useState(null);
    const [preflightResult, setPreview] = React.useState(null), [discarded, setDiscarded] = React.useState([]), [checking, setChecking] = React.useState(false);
    const preview = preflightResult && preflightResult.base === model.base && preflightResult.draft === draft ? preflightResult : null;
    const request = React.useRef(null);
    const blocked = disabled || command.locked || command.phase === 'done';
    const stageReason = E.reason(model, adapter, 'source'), editBlocked = blocked || entity.workflow.route.state !== 'confirmed' || entity.capabilities.stage_confirm !== true;
    function invalidate() { if (request.current) request.current.abort(); request.current = null; setChecking(false); setPreview(null); setDiscarded([]); }
    React.useEffect(() => { invalidate(); }, [model.draft, model.base, model.review, disabled, command.error]);
    React.useEffect(() => () => { if (request.current) request.current.abort(); }, []);
    function change(ref, patch) { invalidate(); model.edit(current => ({ ...current, [ref]: { ...current[ref], ...patch } })); }
    function openPicker(row, kind) { setPicker({ ...row, kind, source: draft[row.ref].source }); onOverlay(true); }
    function closePicker() { setPicker(null); onOverlay(false); }
    function choose(row) {
      change(picker.ref, picker.kind === 'op_type' ? { op_type_ref: row.ref, op_type_label: row.label, confirmed: false } : { supplier_ref: row.ref, supplier_label: row.label, confirmed: false }); closePicker();
    }
    async function preflight() {
      if (blocked || stageReason || checking) return;
      invalidate(); model.setError(null);
      const controller = new AbortController(); request.current = controller;
      try {
        if (typeof adapter.stagePreview !== 'function' || typeof P.stagePreview !== 'function') throw C.failure('归属检查接口尚未接入。');
        const body = input(entity, draft); setChecking(true);
        const response = P.stagePreview(await adapter.stagePreview(entity.ref, 'source_confirm', body, model.base.meta.snapshot_ref, controller.signal), entity.ref, 'source_confirm');
        if (!controller.signal.aborted && request.current === controller) { setPreview({ response, body, base: model.base, draft }); setChecking(false); }
      } catch (error) { if (!controller.signal.aborted && request.current === controller) { model.setError(error); setChecking(false); } }
      finally { if (request.current === controller) request.current = null; }
    }
    const affected = preview ? preview.response.data.affected_groups : [], acknowledgement = affected.every(row => discarded.includes(row.ref));
    const displayGroups = Array.from(new Map(entity.external_groups.concat(affected).map(row => [row.ref, row])).values());
    const saveReason = stageReason || (!preview ? '请先检查当前归属。' : !acknowledgement ? '请明确勾选解除所有受影响的外协组。' : C.blocked(preview.response.data.write_context, 'process', 'source_confirm', preview.response.meta.source));
    async function save() {
      if (blocked || saveReason) return;
      await command.submit('process', 'source_confirm', entity.ref, preview.response.data.write_context, { ...preview.body, discard_group_refs: discarded });
    }
    const confirmed = Object.values(draft).filter(row => row.confirmed).length;
    return <section data-process-source-editor><div className="toolbar"><E.Search paging={paging} disabled={blocked} /><span>有效工序 {E.active(entity).length} · 已核对 {confirmed}</span><span className="tb-spacer" />
      <Button icon="plus" disabled={editBlocked} reason={!adapter.resourceAdapter || !window.ProcessOpTypeCreate ? '工种独立建档尚未接入。' : ''}
        onClick={() => { invalidate(); setCreate({}); onOverlay(true); }}>待建工种</Button></div>
      <div className="toolbar"><label><input type="checkbox" aria-label="确认本页已核对工序" disabled={editBlocked || !paging.rows.some(row => row.status === 'active')}
        checked={paging.rows.some(row => row.status === 'active') && paging.rows.filter(row => row.status === 'active').every(row => draft[row.ref].confirmed)}
        onChange={event => { const checked = event.target.checked; invalidate(); model.edit(current => { const next = { ...current }; paging.rows.filter(row => row.status === 'active').forEach(row => { next[row.ref] = { ...next[row.ref], confirmed: checked }; }); return next; }); }} />确认本页已核对工序</label></div>
      <div className="wb-table-frame"><div className="card-scroll wb-table-shell"><table className="tbl wb-table" aria-label="工序归属明细" style={{ minWidth: 950, tableLayout: 'fixed' }}><caption className="wb-visually-hidden">{"工序归属明细"}</caption>
        <thead><tr><th scope="col" style={{ width: 150 }}>工序</th><th scope="col" style={{ width: 160 }}>工种</th><th scope="col" style={{ width: 160 }}>归属</th><th scope="col" style={{ width: 190 }}>供应商</th><th scope="col">核对 / 确认记录</th></tr></thead><tbody>{paging.rows.map(row => {
          const current = draft[row.ref] || row, inactive = row.status !== 'active', cycle = current.source === row.source && P.groupCycle(row, entity.external_groups);
          return <tr key={row.ref}><td><b>{row.sequence}</b> {row.label}{cycle && <div className="muted" data-process-cycle-group={row.external_group_ref}>{cycle}</div>}</td><td>{current.op_type_label || '未绑定工种'}<div><Button icon="search" aria-label={'选择工序 ' + row.sequence + ' 工种'} disabled={editBlocked || inactive || !current.source} onClick={() => openPicker(row, 'op_type')} /></div></td>
            <td><span className="segm" role="group" aria-label={'工序 ' + row.sequence + ' 归属'}>{['internal', 'external'].map(source => <Button key={source} className={current.source === source ? 'on ' + (source === 'internal' ? 'int' : 'ext') : ''}
              aria-pressed={current.source === source} disabled={editBlocked || inactive} onClick={() => { if (source !== current.source) change(row.ref, { source, op_type_ref: null, op_type_label: null, supplier_ref: null, supplier_label: null, confirmed: false }); }}>{P.sourceLabel(source)}</Button>)}</span>{!current.source && <div>未归类</div>}</td>
            <td>{current.source === 'internal' ? '不适用' : <>{current.supplier_label || '未绑定供应商'}<div><Button icon="search" aria-label={'选择工序 ' + row.sequence + ' 供应商'} disabled={editBlocked || inactive || current.source !== 'external'} onClick={() => openPicker(row, 'supplier')} />
              {current.supplier_ref && <Button icon="x" aria-label={'清除工序 ' + row.sequence + ' 供应商'} disabled={editBlocked || inactive} onClick={() => change(row.ref, { supplier_ref: null, supplier_label: null, confirmed: false })} />}</div></>}</td>
            <td>{inactive ? '已停用工序' : <label><input type="checkbox" aria-label={'确认工序 ' + row.sequence + ' 归属'} checked={!!current.confirmed} disabled={editBlocked} onChange={event => change(row.ref, { confirmed: event.target.checked })} />已核对</label>}
              <div className="muted"><E.Confirmation record={row.confirmation && row.confirmation.source} /></div><Issues issues={row.issues} /></td></tr>;
        })}{!paging.rows.length && <tr><td colSpan={5}>{rows.length ? '没有匹配的工序。' : '尚无工序记录。'}</td></tr>}</tbody></table></div></div><E.Pager paging={paging} disabled={blocked} />
      <E.Groups rows={displayGroups} affected={affected.map(row => row.ref)} discarded={discarded} onDiscard={preview ? setDiscarded : undefined} disabled={blocked} />
      {preview && <><Issues issues={preview.response.warnings} /><p role="status">当前归属已检查；受影响外协组 {affected.length} 个，尚未提交。</p></>}
      <E.Feedback model={model} disabled={blocked || checking} />
      <div className="pd-foot"><span className="muted">现有归属仅作建议；仅提交有效工序，不修改已有批次。</span><Button icon="search" busy={checking} disabled={blocked} reason={stageReason} onClick={preflight}>检查归属</Button>
        <Button icon="check" className="btn primary" disabled={blocked} reason={saveReason} onClick={save}>完成归属 · 解锁工时</Button></div>
      {picker && ReactDOM.createPortal(<div className="plana process-detail"><Picker adapter={adapter} target={picker} onSelect={choose} onClose={closePicker} disabled={blocked} /></div>, document.body)}
      {create && ReactDOM.createPortal(<div className="plana process-detail"><window.ProcessOpTypeCreate adapter={adapter.resourceAdapter} onClose={() => { setCreate(null); onOverlay(false); }} onCommitted={receipt => { invalidate(); model.reload(); if (onResourceCommitted) onResourceCommitted(receipt); }} /></div>, document.body)}
    </section>;
  }
  window.ProcessSourceEditor = ProcessSourceEditor;
})();
