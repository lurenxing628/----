(function () {
  'use strict';
  const C = window.APSResourceContract, P = window.APSProcessContract, S = window.APSResourceSession;
  const E = window.ProcessStageEditor, { Button, Modal, ErrorBox, Issues } = window.ResourceControls;
  function build(entity) {
    return Object.fromEntries(E.active(entity).map(row => [row.ref, { ref: row.ref, source: row.source, op_type_ref: row.op_type_ref,
      op_type_label: row.op_type_label, supplier_ref: row.supplier_ref, supplier_label: row.supplier_label }]));
  }
  function reconcile(draft, before, after) {
    const next = build(after), original = build(before);
    E.active(after).forEach(row => {
      const current = draft[row.ref], previous = original[row.ref], fresh = next[row.ref];
      if (!current || !previous) return;
      if (current.source !== previous.source) fresh.source = current.source;
      [['op_type_ref', 'op_type_label'], ['supplier_ref', 'supplier_label']].forEach(([ref, label]) => {
        if (current[ref] === previous[ref]) return;
        if (current[ref] !== fresh[ref]) fresh[label] = current[label];
        fresh[ref] = current[ref];
      });
    });
    return next;
  }
  const complete = row => ['internal', 'external'].includes(row.source) && !!row.op_type_ref && (row.source === 'internal' || !!row.supplier_ref);
  function input(entity, draft, pageSize) {
    const operations = E.active(entity).map(row => {
      const current = draft[row.ref];
      if (!complete(current)) {
        const error = C.failure('工序 ' + row.sequence + ' 请补齐归属、工种和外协供应商。', [{ path: 'operations.' + row.sequence, message: '工序 ' + row.sequence + ' 资料未填完整。' }]);
        error.locate_page = Math.floor(entity.operations.indexOf(row) / pageSize) + 1; throw error;
      }
      return { ref: row.ref, source: current.source, op_type_ref: current.op_type_ref, supplier_ref: current.source === 'internal' ? null : current.supplier_ref, confirmed: true };
    });
    if (!operations.length) throw C.failure('尚无有效工序，不能确认归属。');
    return { operations, discard_group_refs: [] };
  }
  function Picker({ adapter, target, onSelect, onClose, disabled }) {
    const [search, setSearch] = React.useState(''), [scope, setScope] = React.useState({ query: '', page: 1, size: 50 });
    const read = S.useQuery(async signal => {
      if (typeof adapter.choices !== 'function') throw C.failure('dependency not wired: window.APSProcessAPI.choices');
      return C.query(await adapter.choices(target.kind, { ...scope, ...(target.kind === 'op_type' ? { category: target.source } : {}) }, signal), 'choices');
    }, [adapter, target.kind, target.source, scope]);
    const data = read.result && read.result.data, title = target.kind === 'op_type' ? P.sourceLabel(target.source) + '工种' : '供应商';
    return <Modal title={'选择' + title + ' · 工序 ' + target.sequence} icon="search" onClose={onClose} locked={disabled} footer={<Button onClick={onClose} disabled={disabled}>取消</Button>}>
      <div className="modal-b scroll"><form className="toolbar" onSubmit={event => { event.preventDefault(); setScope({ query: search, page: 1, size: 50 }); }}>
        <label className="search"><window.ResourceControls.Icon name="search" /><input type="search" aria-label={'搜索' + title} value={search} onChange={event => setSearch(event.target.value)} disabled={disabled} /></label><Button type="submit" icon="search" disabled={disabled}>搜索</Button></form>
        <ErrorBox error={read.error} />{read.error && <Button icon="refresh-cw" onClick={() => setScope({ query: search, page: 1, size: 50 })}>刷新选项</Button>}
        {read.loading && <p role="status">正在读取选项…</p>}
        {data && <><Issues issues={read.result.warnings} /><div className="wb-table-frame"><table className="tbl wb-table" aria-label={title + '选项'} style={{ width: '100%', tableLayout: 'fixed' }}><caption className="wb-visually-hidden">{title + '选项'}</caption><thead><tr><th scope="col">编号</th><th scope="col">名称</th><th scope="col">选择</th></tr></thead>
          <tbody>{data.entities.map(row => <tr key={row.ref}><td>{row.business_code}</td><td>{row.label}</td><td><Button icon="check" disabled={disabled || !(row.status === 'active' || target.kind === 'op_type' && row.status === null) || target.kind === 'op_type' && row.fields.category !== target.source}
            aria-label={'采用 ' + row.label} onClick={() => onSelect(row)}>采用</Button></td></tr>)}{!data.entities.length && <tr><td colSpan={3}>没有匹配选项。</td></tr>}</tbody></table></div>
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
      change(picker.ref, picker.kind === 'op_type' ? { op_type_ref: row.ref, op_type_label: row.label } : { supplier_ref: row.ref, supplier_label: row.label }); closePicker();
    }
    async function preflight(commit = false) {
      if (blocked || stageReason || checking) return;
      invalidate(); model.setError(null);
      const controller = new AbortController(); request.current = controller;
      try {
        if (typeof adapter.stagePreview !== 'function' || typeof P.stagePreview !== 'function') throw C.failure('dependency not wired: window.APSProcessAPI.stagePreview');
        const body = input(entity, draft, paging.page.size); setChecking(true);
        const response = P.stagePreview(await adapter.stagePreview(entity.ref, 'source_confirm', body, model.base.meta.snapshot_ref, controller.signal), entity.ref, 'source_confirm');
        if (!controller.signal.aborted && request.current === controller) {
          setPreview({ response, body, base: model.base, draft }); setChecking(false);
          if (commit && !response.data.affected_groups.length) await command.submit('process', 'source_confirm', entity.ref, response.data.write_context, body);
        }
      } catch (error) { if (!controller.signal.aborted && request.current === controller) { model.setError(error); setChecking(false); } }
      finally { if (request.current === controller) request.current = null; }
    }
    const affected = preview ? preview.response.data.affected_groups : [], acknowledgement = affected.every(row => discarded.includes(row.ref));
    const displayGroups = Array.from(new Map(entity.external_groups.concat(affected).map(row => [row.ref, row])).values());
    const saveReason = stageReason || (preview && (!acknowledgement ? '请确认解除下方受影响的外协组。' : C.blocked(preview.response.data.write_context, 'process', 'source_confirm', preview.response.meta.source)));
    async function save() {
      if (blocked || checking || saveReason) return;
      if (!preview) { await preflight(true); return; }
      await command.submit('process', 'source_confirm', entity.ref, preview.response.data.write_context, { ...preview.body, discard_group_refs: discarded });
    }
    const active = E.active(entity);
    return <section data-process-source-editor><div className="toolbar"><E.Search paging={paging} disabled={blocked} /><span>共 {active.length} 道有效工序</span><span className="tb-spacer" />
      <Button icon="plus" disabled={editBlocked} reason={!adapter.resourceAdapter || !window.ProcessOpTypeCreate ? window.WorkbenchTerms.outcomes.unavailable : ''}
        onClick={() => { invalidate(); setCreate({}); onOverlay(true); }}>新增工种</Button></div>
      <div className="wb-table-frame"><table className="tbl wb-table wb-table--editable" aria-label="归属明细" style={{ minWidth: 950, tableLayout: 'fixed' }}><caption className="wb-visually-hidden">{"归属明细"}</caption>
        <thead><tr><th scope="col" style={{ width: 150 }}>工序</th><th scope="col" style={{ width: 160 }}>工种</th><th scope="col" style={{ width: 160 }}>归属</th><th scope="col" style={{ width: 190 }}>供应商</th><th scope="col">保存记录</th></tr></thead><tbody>{paging.rows.map(row => {
          const current = draft[row.ref] || row, inactive = row.status !== 'active', cycle = current.source === row.source && P.groupCycle(row, entity.external_groups);
          return <tr key={row.ref}><td><b>{row.sequence}</b> {row.label}{cycle && <div className="muted" data-process-cycle-group={row.external_group_ref}>{cycle}</div>}</td><td>{current.op_type_label || '未选工种'}<div><Button icon="search" aria-label={'选择工序 ' + row.sequence + ' 工种'} disabled={editBlocked || inactive || !current.source} onClick={() => openPicker(row, 'op_type')} /></div></td>
            <td><span className="segm" role="group" aria-label={'工序 ' + row.sequence + ' 归属'}>{['internal', 'external'].map(source => <Button key={source} className={current.source === source ? 'on ' + (source === 'internal' ? 'int' : 'ext') : ''}
              aria-pressed={current.source === source} disabled={editBlocked || inactive} onClick={() => { if (source !== current.source) change(row.ref, { source, op_type_ref: null, op_type_label: null, supplier_ref: null, supplier_label: null }); }}>{P.sourceLabel(source)}</Button>)}</span>{!current.source && <div>未归类</div>}</td>
            <td>{current.source === 'internal' ? '不适用' : <>{current.supplier_label || '未选供应商'}<div><Button icon="search" aria-label={'选择工序 ' + row.sequence + ' 供应商'} disabled={editBlocked || inactive || current.source !== 'external'} onClick={() => openPicker(row, 'supplier')} />
              {current.supplier_ref && <Button icon="x" aria-label={'清除工序 ' + row.sequence + ' 供应商'} disabled={editBlocked || inactive} onClick={() => change(row.ref, { supplier_ref: null, supplier_label: null })} />}</div></>}</td>
            <td>{inactive ? '已停用工序' : <div className="muted"><E.Confirmation record={row.confirmation && row.confirmation.source} /></div>}<Issues issues={row.issues} /></td></tr>;
        })}{!paging.rows.length && <tr><td colSpan={5}>{rows.length ? '没有匹配的工序。' : '尚无工序记录。'}</td></tr>}</tbody></table></div><E.Pager paging={paging} disabled={blocked} />
      <E.Groups rows={displayGroups} affected={affected.map(row => row.ref)} discarded={discarded} onDiscard={preview ? setDiscarded : undefined} disabled={blocked} />
      {preview && affected.length > 0 && <><Issues issues={preview.response.warnings} /><p role="status">本次修改将解除 {affected.length} 个外协组，请确认下方列出的变化。</p></>}
      <E.Feedback model={model} disabled={blocked || checking} paging={paging} />
      <div className="pd-foot"><span className="muted">保存全部 {active.length} 道有效工序，包含其他页和筛选隐藏的工序。</span>
        <Button icon="check" className="btn primary" busy={checking} disabled={blocked} reason={saveReason} onClick={save}>保存归属并继续</Button></div>
      {picker && ReactDOM.createPortal(<div className="plana process-detail"><Picker adapter={adapter} target={picker} onSelect={choose} onClose={closePicker} disabled={blocked} /></div>, document.body)}
      {create && ReactDOM.createPortal(<div className="plana process-detail"><window.ProcessOpTypeCreate adapter={adapter.resourceAdapter} onClose={() => { setCreate(null); onOverlay(false); }} onCommitted={receipt => { invalidate(); model.reload(); if (onResourceCommitted) onResourceCommitted(receipt); }} /></div>, document.body)}
    </section>;
  }
  window.ProcessSourceEditor = ProcessSourceEditor;
})();
