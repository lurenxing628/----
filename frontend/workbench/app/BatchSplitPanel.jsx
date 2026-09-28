(function () {
  'use strict';
  const { Button, Modal, ErrorBox, Field } = window.ResourceControls;
  const B = window.APSBatchContract;
  function BatchSplitPanel({ refs, day, onCommitted }) {
    const adapter = React.useMemo(() => window.APSBatchAPI.create(), []);
    const command = window.APSResourceSession.useCommand(adapter);
    const [preview, setPreview] = React.useState(null), [error, setError] = React.useState(null), [busy, setBusy] = React.useState(false);
    const [quantity, setQuantity] = React.useState(''), seen = React.useRef(null), serial = React.useRef(0);
    const owner = window.WorkbenchGuards.useDirtyGuard({ dirty: false, locked: command.locked, message: '拆分正在确认，请先核对保存结果。' });
    React.useEffect(() => { serial.current++; setPreview(null); }, [JSON.stringify(refs), day]);
    React.useEffect(() => () => { serial.current++; }, []);
    React.useEffect(() => {
      if (command.phase !== 'done' || seen.current === command.result.receipt_ref || command.intent.action !== 'split_confirm') return;
      try {
        const result = B.receipt(command.result, 'split_confirm', command.intent.ref);
        if (!B.ref(result.data.child_ref)) throw window.APSResourceContract.failure('未读到拆分子批，请刷新批次核对。');
        seen.current = result.receipt_ref; setPreview(null); setQuantity(''); onCommitted(result.data.child_ref, command.intent.ref);
      } catch (e) { setError(e); }
    }, [command.phase, command.result]);
    async function inspect() {
      if (refs.length !== 1 || command.locked || busy) return;
      const id = ++serial.current; setBusy(true); setError(null);
      try {
        command.reset();
        const count = quantity.trim() ? Number(quantity) : null;
        if (count !== null && (!Number.isSafeInteger(count) || count <= 0)) throw window.APSResourceContract.failure('请填写正整数数量，留空则按当前物料可做数量预览。');
        const detail = await adapter.detail('batch', refs[0]), input = { as_of_date: day, quantity: count };
        B.detail(detail, refs[0]);
        const response = await adapter.preview('split', refs[0], input, null, detail.meta.snapshot_ref);
        const data = B.preview(response, 'split', refs[0], input);
        if (id === serial.current) setPreview(data);
      } catch (e) { if (id === serial.current) setError(e); }
      finally { setBusy(false); }
    }
    return <section aria-label="分批开工预览">
      <div className="toolbar"><Field label="本次先做数量（可留空）"><input inputMode="numeric" aria-label="本次先做数量" value={quantity} disabled={busy || command.locked}
        onChange={e => { setQuantity(e.target.value); setPreview(null); }} /></Field>
        <Button busy={busy} disabled={command.locked || refs.length !== 1} onClick={inspect}>预览可开工数量</Button></div>
      <p>一次选择一个批次预览；按排产开始日期 {day} 前的到料计算。确认后才保存为两个批次，并选中可开工子批。需求量按件数比例分配，设备换型和外协周期在每个子批分别计算。</p>
      {refs.length !== 1 && <p>请先选择一个要拆分的待排批次。</p>}
      <ErrorBox error={error} /><window.ResourceForms.Feedback command={command} />
      {preview && ReactDOM.createPortal(<div className="plana"><Modal title="确认分批开工" icon="box" guardOwner={owner} locked={command.locked} onClose={() => { if (!command.locked) setPreview(null); }}
        footer={<><Button disabled={command.locked} onClick={() => setPreview(null)}>取消</Button><Button className="btn primary" disabled={command.locked}
          onClick={() => command.submit('batch', 'split_confirm', preview.entity_ref, preview.write_context, { preview_ref: preview.preview_ref })}>确认拆分并选择可开工子批</Button></>}>
        <div className="modal-b"><p>{preview.source_code} 原有 {preview.original_quantity} 件：{preview.child_code} 先做 {preview.quantity} 件，原批保留 {preview.remaining_quantity} 件。</p>
          <div className="wb-table-frame"><table className="tbl wb-table" aria-label="拆分物料分配"><thead><tr><th>物料</th><th>子批需求</th><th>剩余需求</th><th>子批到料</th><th>剩余到料</th></tr></thead><tbody>
            {preview.materials.map((row, i) => <tr key={i}><td>{row.business_code} · {row.label}</td><td>{row.child_required}</td><td>{row.source_required}</td><td>{row.child_available + row.child_arrivals.reduce((n, a) => n + a.quantity, 0)}</td><td>{row.source_available + row.source_arrivals.reduce((n, a) => n + a.quantity, 0)}</td></tr>)}</tbody></table></div>
          <p>到料分配包含后续到料，按各自日期可用。取消不会改动批次；确认后仍需检查并开始计算。</p><window.ResourceForms.Feedback command={command} />
        </div></Modal></div>, document.body)}
    </section>;
  }
  window.BatchSplitPanel = BatchSplitPanel;
})();
