(function () {
  'use strict';
  const C = window.APSResourceContract, P = window.APSProcessContract, E = window.ProcessStageEditor;
  const { Button, Modal } = window.ResourceControls;
  const build = () => ({ groups: [], discard_group_refs: [] });
  function input(draft) {
    return { groups: draft.groups.map(row => {
      if (!row.operation_refs.length || !row.supplier_ref || !Number.isFinite(Number(row.total_days)) || Number(row.total_days) <= 0)
        throw C.failure('每段请选择连续外协工序、供应商，并填写大于 0 的整段周期。');
      return { ref: row.ref, operation_refs: row.operation_refs, supplier_ref: row.supplier_ref, total_days: Number(row.total_days) };
    }), discard_group_refs: draft.discard_group_refs };
  }
  function ProcessGroupEditor({ adapter, result, command, disabled, onDirty, onClose }) {
    const model = E.useDraft({ result, adapter, stage: 'groups', build, reconcile: draft => draft, saved: 0, onDirty });
    const entity = model.base.data, draft = model.draft, operations = E.active(entity), paging = E.usePage(operations);
    const [editing, setEditing] = React.useState(null), [picker, setPicker] = React.useState(null), [discard, setDiscard] = React.useState(false);
    const [preview, setPreview] = React.useState(null), [checking, setChecking] = React.useState(false), serial = React.useRef(0), request = React.useRef(null), reviewRoot = React.useRef(null);
    const blocked = disabled || command.locked || command.phase === 'done', current = draft.groups.find(row => row.key === editing);
    const validPreview = preview && preview.draft === draft && preview.base === model.base && !model.review ? preview : null;
    const reason = model.review ? '请先核对最新资料。' : entity.workflow.route.state !== 'confirmed' ? '请先确认路线。'
      : P.reason(entity.capabilities, 'stage_confirm', typeof adapter.stagePreview === 'function' && typeof adapter.command === 'function')
        || (model.base.meta.source !== 'production' ? '请先读取可保存的工艺资料。' : '') || (!model.dirty ? '请先新增、修改或解除外协段。' : '');
    React.useEffect(() => () => { if (request.current) request.current.abort(); if (onDirty) onDirty('groups', false); }, []);
    React.useEffect(() => {
      if (!validPreview || !reviewRoot.current) return undefined;
      const frame = requestAnimationFrame(() => { if (reviewRoot.current) { reviewRoot.current.focus(); reviewRoot.current.scrollIntoView({ block: 'nearest' }); } });
      return () => cancelAnimationFrame(frame);
    }, [validPreview]);
    function edit(next) { if (request.current) request.current.abort(); setChecking(false); setPreview(null); model.edit(next); }
    function patch(values) { edit(old => ({ ...old, groups: old.groups.map(row => row.key === editing ? { ...row, ...values } : row) })); }
    function members(row) { return operations.filter(op => row.operation_refs.includes(op.ref)); }
    function start(group) {
      const row = group ? { key: group.ref, ref: group.ref, operation_refs: operations.filter(op => op.external_group_ref === group.ref).map(op => op.ref),
        supplier_ref: group.supplier_ref, supplier_label: group.supplier_label, total_days: group.total_days === null ? '' : String(group.total_days) }
        : { key: 'new-' + (++serial.current), ref: null, operation_refs: [], supplier_ref: null, supplier_label: null, total_days: '' };
      if (!draft.groups.some(item => item.key === row.key)) edit(old => ({ ...old, groups: old.groups.concat(row), discard_group_refs: old.discard_group_refs.filter(ref => ref !== row.ref) }));
      setEditing(row.key);
    }
    function remove(row) {
      edit(old => ({ ...old, groups: old.groups.filter(item => item.key !== row.key) }));
      if (editing === row.key) setEditing(null);
    }
    function detach(group) {
      edit(old => ({ groups: old.groups.filter(row => row.ref !== group.ref), discard_group_refs: old.discard_group_refs.includes(group.ref)
        ? old.discard_group_refs.filter(ref => ref !== group.ref) : old.discard_group_refs.concat(group.ref) }));
      if (editing === group.ref) setEditing(null);
    }
    function close() { if (!blocked) { if (model.dirty) setDiscard(true); else onClose(); } }
    async function check() {
      if (blocked || checking || reason) return;
      const controller = new AbortController(); request.current = controller; setChecking(true); model.setError(null);
      try {
        const body = input(draft), raw = await adapter.stagePreview(entity.ref, 'groups_confirm', body, model.base.meta.snapshot_ref, controller.signal);
        const response = P.stagePreview(raw, entity.ref, 'groups_confirm');
        if (!controller.signal.aborted) setPreview({ response, body, draft, base: model.base });
      } catch (error) { if (!controller.signal.aborted) model.setError(error); }
      finally { if (request.current === controller) { request.current = null; setChecking(false); } }
    }
    async function save() {
      if (blocked || !validPreview || reason) return;
      await command.submit('process', 'groups_confirm', entity.ref, validPreview.response.data.write_context, validPreview.body);
    }
    const editedRefs = new Set(draft.groups.map(row => row.ref).filter(Boolean)), removedRefs = new Set(draft.discard_group_refs);
    function label(fact) { return fact ? '工序 ' + (fact.sequences.join('、') || '无有效成员') + '；供应商 ' + (fact.supplier_label || fact.supplier_id || '未选') + '；' + (fact.merge_mode === 'merged' ? '整段 ' + E.value(fact.total_days) + ' 天' : '逐序周期') : '无'; }
    return ReactDOM.createPortal(<div className="plana process-detail" data-process-group-editor><Modal title="管理外协段" icon="chart-gantt" onClose={close} locked={blocked || checking} suspended={!!picker}
      footer={<><Button disabled={blocked || checking} onClick={close}>返回工时</Button><Button icon="search" disabled={blocked || checking} reason={reason} onClick={check}>预检外协段</Button>
        <Button className="btn primary" icon="check" disabled={blocked || checking || !validPreview} reason={reason} onClick={save}>确认保存外协段</Button></>}>
      <div className="modal-b scroll"><p>一段表示一次送出、一次回厂。只选路线中连续且属于同一家供应商的外协工序；两次送出请分别建段。整段周期只计算一次，修改后还需确认工时。</p>
        <p className="muted">拆分时先缩小原段的工序范围，再新增另一段；解除后各工序恢复原逐序周期，原来未填写的请补齐。未编辑的段及历史记录保留。</p>
        <div className="toolbar"><h3>已有外协段</h3><span className="tb-spacer" /><Button icon="plus" disabled={blocked || checking} onClick={() => start(null)}>新增外协段</Button></div>
        <div className="wb-table-frame"><table className="tbl wb-table" aria-label="已有外协段"><thead><tr><th scope="col">工序范围</th><th scope="col">供应商</th><th scope="col">周期</th><th scope="col">本次操作</th></tr></thead>
          <tbody>{entity.external_groups.map(row => <tr key={row.ref}><td>{row.start_sequence} 至 {row.end_sequence}</td><td>{row.supplier_label || '未选'}</td><td>{row.merge_mode === 'merged' ? E.value(row.total_days) + ' 天（整段）' : '逐序设置'}</td><td>
            <Button disabled={blocked || checking} onClick={() => start(row)}>{editedRefs.has(row.ref) ? '继续编辑' : '修改范围 / 供应商'}</Button>
            <Button disabled={blocked || checking} onClick={() => detach(row)}>{removedRefs.has(row.ref) ? '撤销解除' : '解除此段'}</Button>{removedRefs.has(row.ref) && <span role="status">保存时解除</span>}</td></tr>)}
            {!entity.external_groups.length && <tr><td colSpan={4}>尚无外协段，可选择工序新增。</td></tr>}</tbody></table></div>
        {!!draft.groups.length && <section><h3>本次新增 / 修改</h3>{draft.groups.map((row, index) => <div className="toolbar" key={row.key}><span>{row.ref ? '修改' : '新增'}外协段 · 工序 {members(row).map(op => op.sequence).join('、') || '待选择'} · {row.supplier_label || '待选供应商'} · {row.total_days || '待填'} 天</span>
          <Button disabled={blocked || checking} aria-label={'编辑本次第 ' + (index + 1) + ' 段'} onClick={() => setEditing(row.key)}>编辑</Button><Button disabled={blocked || checking} onClick={() => remove(row)}>撤销本次编辑</Button></div>)}</section>}
        {current && <section><h3>{current.ref ? '修改外协段' : '新外协段'}</h3><E.Search paging={paging} disabled={blocked || checking} />
          <div className="wb-table-frame"><table className="tbl wb-table wb-table--editable" aria-label="选择外协段工序"><thead><tr><th scope="col">加入此段</th><th scope="col">工序</th><th scope="col">归属 / 供应商</th></tr></thead>
            <tbody>{paging.rows.map(row => { const elsewhere = draft.groups.some(group => group.key !== current.key && group.operation_refs.includes(row.ref));
              const occupied = row.external_group_ref && row.external_group_ref !== current.ref && !editedRefs.has(row.external_group_ref) && !removedRefs.has(row.external_group_ref);
              return <tr key={row.ref}><td><label><input type="checkbox" aria-label={'外协段包含工序 ' + row.sequence} checked={current.operation_refs.includes(row.ref)} disabled={blocked || checking || row.source !== 'external' || elsewhere || !!occupied}
                onChange={event => patch({ operation_refs: event.target.checked ? current.operation_refs.concat(row.ref) : current.operation_refs.filter(ref => ref !== row.ref) })} />{row.source !== 'external' ? '自制工序' : elsewhere ? '已选入另一段' : occupied ? '先编辑或解除原段' : '选择'}</label></td><td>{row.sequence} · {row.label}</td><td>{P.sourceLabel(row.source)} · {row.source === 'internal' ? '不适用供应商' : row.supplier_label || '未选供应商'}</td></tr>; })}</tbody></table></div><E.Pager paging={paging} disabled={blocked || checking} />
          <div className="toolbar"><span>供应商：{current.supplier_label || '未选择'}</span><Button icon="search" disabled={blocked || checking || !current.operation_refs.length} onClick={() => { const rows = members(current); setPicker({ kind: 'supplier', source: 'external', sequence: rows[0].sequence,
            group: { start_sequence: rows[0].sequence, end_sequence: rows[rows.length - 1].sequence }, members: rows }); }}>选择整段供应商</Button>
            <label>整段周期（天）<input className="wt-in" type="number" step="any" min="0" aria-label="整段外协周期" value={current.total_days} disabled={blocked || checking} onChange={event => patch({ total_days: event.target.value })} /></label></div>
        </section>}
        <window.ResourceForms.Feedback command={command} /><E.Feedback model={model} disabled={blocked || checking} />
        {validPreview && <section role="status" ref={reviewRoot} tabIndex={-1}><h3>保存前核对</h3><div className="wb-table-frame"><table className="tbl wb-table" aria-label="外协段变更预检"><thead><tr><th scope="col">操作</th><th scope="col">保存前</th><th scope="col">保存后</th></tr></thead><tbody>
          {validPreview.response.data.changes.map((row, index) => <tr key={index}><td>{{ create: '新增段', update: '修改段', discard: '解除段' }[row.action]}</td><td>{label(row.before)}</td><td>{label(row.after)}</td></tr>)}
          {!validPreview.response.data.changes.length && <tr><td colSpan={3}>与已保存内容一致，无需改变现有段。</td></tr>}</tbody></table></div></section>}
        {discard && <section className="match-note is-block" role="alert"><p>本次外协段修改尚未保存。</p><Button disabled={blocked} onClick={() => setDiscard(false)}>继续编辑</Button><Button className="btn danger" disabled={blocked} onClick={onClose}>放弃段修改并返回</Button></section>}
      </div></Modal>{picker && <window.ProcessSourcePicker adapter={adapter} target={picker} disabled={blocked || checking} onClose={() => setPicker(null)} onSelect={row => {
        patch({ supplier_ref: row.ref, supplier_label: row.label, ...(!current.ref && !current.total_days && row.fields.default_days > 0 ? { total_days: String(row.fields.default_days) } : {}) }); setPicker(null);
      }} />}</div>, document.body);
  }
  window.ProcessGroupEditor = ProcessGroupEditor;
})();
