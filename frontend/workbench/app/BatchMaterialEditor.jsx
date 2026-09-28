(function () {
  'use strict';
  const B = window.APSBatchContract, C = window.APSResourceContract, S = window.APSResourceSession;
  const { Button, Modal, ErrorBox } = window.ResourceControls;
  const toRows = entity => entity.materials.requirements.map(row => ({ ...row, operation_ref: row.operation_ref || null, arrivals: row.arrivals || [],
    required_quantity: row.required_quantity == null ? '' : String(row.required_quantity),
    available_quantity: row.available_quantity == null ? '' : String(row.available_quantity) }));
  function BatchMaterialEditor({ adapter, entity: initial, command, onCommitted, onClose, disabled }) {
    const [entity, setEntity] = React.useState(initial), [rows, setRows] = React.useState(() => toRows(initial));
    const [removed, setRemoved] = React.useState([]), [error, setError] = React.useState(null), [review, setReview] = React.useState(null);
    const [scope, setScope] = React.useState({ query: '', page: 1 }), [selected, setSelected] = React.useState('');
    const form = React.useId(), done = command.phase === 'done', locked = disabled || command.locked || done;
    const seen = React.useRef(null), changed = JSON.stringify(rows) !== JSON.stringify(toRows(entity)) || removed.length > 0;
    const owner = window.WorkbenchGuards.useDirtyGuard({ dirty: !done && !!changed, locked: command.locked, message: '物料需求有尚未保存的修改。' });
    const choices = S.useQuery(signal => adapter.materialChoices(scope, signal), [adapter, scope]);
    const data = choices.result && choices.result.data;
    React.useEffect(() => {
      if (!done || seen.current === command.result.receipt_ref) return;
      try { B.receipt(command.result, 'materials_update', entity.ref); seen.current = command.result.receipt_ref; onCommitted(command.result); }
      catch (e) { setError(e); }
    }, [done, command.result]);
    async function close(detail) {
      if (command.locked) return;
      if (detail && detail.guardConfirmed && detail.guardOwner === owner || await window.WorkbenchGuards.confirmLeave({ owner })) onClose();
    }
    function add() {
      const item = data && data.entities.find(row => row.ref === selected);
      if (!item) return;
      setRows(rows.concat({ row_key: null, material_ref: item.ref, business_code: item.business_code, label: item.label,
        unit: item.fields.unit, required_quantity: '', available_quantity: '0', operation_ref: null, arrivals: [] })); setSelected('');
    }
    function patch(index, change) { setRows(old => old.map((row, i) => i === index ? { ...row, ...change } : row)); }
    async function save(event) {
      event.preventDefault(); if (locked || review) return;
      try {
        const input = rows.map(row => {
          const values = [row.required_quantity, row.available_quantity].map(value => {
            if (!String(value).trim() || !Number.isFinite(Number(value))) throw C.failure('请填写有效的需求量和到料量，未到料请填 0。');
            return Number(value);
          });
          if (values[0] <= 0 || values[1] < 0) throw C.failure('需求量必须大于 0，到料量不能小于 0。');
          const arrivals = row.arrivals.map(item => {
            const quantity = Number(item.quantity);
            if (!item.arrival_date || !Number.isFinite(quantity) || quantity <= 0) throw C.failure('请填写每次到料日期和大于 0 的数量。');
            return { arrival_date: item.arrival_date, quantity };
          });
          return { row_key: row.row_key, material_ref: row.material_ref, required_quantity: values[0], available_quantity: values[1], operation_ref: row.operation_ref, arrivals };
        });
        setError(null); await command.submit('batch', 'materials_update', entity.ref, entity.write_context, { rows: input, removed_keys: removed });
      } catch (e) { setError(e); }
    }
    async function reload() {
      try { setReview(B.detail(await adapter.detail('batch', entity.ref), entity.ref).data); setError(null); }
      catch (e) { setError(e); }
    }
    function accept() {
      setEntity(review); setRows(toRows(review)); setRemoved([]); setReview(null); setError(null); command.reset();
    }
    return <Modal title={'物料需求 · ' + entity.business_code} icon="box" onClose={close} guardOwner={owner} locked={command.locked}
      footer={<><Button onClick={close} disabled={command.locked}>{done ? '关闭' : '取消'}</Button>{!done && <Button form={form} type="submit" className="btn primary" disabled={locked || !!review}>核对并保存需求</Button>}</>}>
      <form id={form} className="modal-b form" onSubmit={save}>
        <p>已有到料量与下方逐次到料分别累计，请勿重复登记。选择使用工序后，前面的工序可按本次排产选项先开工；未选工序的物料必须在开工前齐套。</p>
        <div className="toolbar"><input aria-label="搜索物料" value={scope.query} disabled={locked} onChange={e => setScope({ query: e.target.value, page: 1 })} />
          <select aria-label="选择物料" value={selected} disabled={locked || choices.loading} onChange={e => setSelected(e.target.value)}><option value="">请选择物料</option>
            {data && data.entities.map(row => <option key={row.ref} value={row.ref}>{row.business_code} · {row.label}</option>)}</select>
          <Button onClick={add} disabled={locked || !selected}>新增物料</Button></div>
        {data && <window.WorkbenchControls.Pager page={data.page} sizes={[20]} unit="条物料" label="物料选择" disabled={locked || choices.loading}
          onPage={page => setScope({ ...scope, page, snapshot_ref: choices.result.meta.snapshot_ref })} />}
        <div className="wb-table-frame"><table className="tbl wb-table" aria-label="维护批次物料需求"><thead><tr><th>物料</th><th>需求量</th><th>已有到料量</th><th>单位</th><th>操作</th></tr></thead><tbody>
          {rows.map((row, index) => <React.Fragment key={row.row_key || row.material_ref + index}><tr><td>{row.business_code} · {row.label}</td>
            {['required_quantity', 'available_quantity'].map((key, column) => <td key={key}><input aria-label={row.business_code + (column ? '到料量' : '需求量')} inputMode="decimal" value={row[key]} disabled={locked}
              onChange={e => setRows(rows.map((item, i) => i === index ? { ...item, [key]: e.target.value } : item))} /></td>)}
            <td>{row.unit || '未填写'}</td><td><Button disabled={locked} onClick={() => { setRows(rows.filter((_, i) => i !== index)); if (row.row_key) setRemoved(removed.concat(row.row_key)); }}>移除需求</Button></td></tr><tr><td colSpan="5"><div className="fgrid">
            <window.ResourceControls.Field label={row.business_code + '使用工序'}><select aria-label={row.business_code + '使用工序'} value={row.operation_ref || ''} disabled={locked}
              onChange={e => patch(index, { operation_ref: e.target.value || null })}><option value="">开工前用料</option>
              {entity.operations.filter(op => !op.piece_id).map(op => <option key={op.ref} value={op.ref}>{op.sequence} · {op.label}</option>)}</select></window.ResourceControls.Field>
            <div><strong>分次到料（按填写日期可用）</strong>{row.arrivals.map((item, n) => <div className="toolbar" key={n}>
              <input type="date" aria-label={row.business_code + '第' + (n + 1) + '次到料日期'} value={item.arrival_date} disabled={locked}
                onChange={e => patch(index, { arrivals: row.arrivals.map((a, j) => j === n ? { ...a, arrival_date: e.target.value } : a) })} />
              <input inputMode="decimal" aria-label={row.business_code + '第' + (n + 1) + '次到料数量'} value={item.quantity} disabled={locked}
                onChange={e => patch(index, { arrivals: row.arrivals.map((a, j) => j === n ? { ...a, quantity: e.target.value } : a) })} />
              <Button disabled={locked} onClick={() => patch(index, { arrivals: row.arrivals.filter((_, j) => j !== n) })}>移除到料</Button></div>)}
              <Button disabled={locked || row.arrivals.length >= 200} onClick={() => patch(index, { arrivals: row.arrivals.concat({ arrival_date: '', quantity: '' }) })}>新增一次到料</Button></div>
          </div></td></tr></React.Fragment>)}
        </tbody></table></div>
        {!rows.length && <p>当前没有物料需求。保存后保持未齐套；没有用料要求的批次可在基础信息中明确确认齐套。</p>}
        {removed.length > 0 && <p role="status">本次将移除 {removed.length} 条已有需求，请核对后保存。</p>}
        <ErrorBox error={error || choices.error} /><window.ResourceForms.Feedback command={command} />
        {!done && <Button onClick={reload} disabled={locked}>{window.WorkbenchTerms.refresh_latest}</Button>}
        {review && <div role="status"><p>已读到最新资料。采用后会放弃本次未保存的修改，并重新核对物料需求。</p><Button onClick={accept}>采用最新资料并重新填写</Button></div>}
      </form>
    </Modal>;
  }
  window.BatchMaterialEditor = BatchMaterialEditor;
})();
