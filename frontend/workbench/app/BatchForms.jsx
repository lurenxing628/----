(function () {
  'use strict';
  const B = window.APSBatchContract, C = window.APSResourceContract, S = window.APSResourceSession;
  const { Button, Modal, ErrorBox, Issues } = window.ResourceControls;
  const { BaseFields } = window.BatchControls;
  // The confirmation table shows quotas as entered (up to four decimals), never as a one-decimal summary.
  const ENTERED_HOURS = { digits: 4, trim: true }, ENTERED_DAYS = { digits: 1, trim: true };
  function BaseEditor({ adapter, entity: original, createContext, source, command, onClose, onCommitted, disabled = false }) {
    const [entity, setEntity] = React.useState(original), [value, setValue] = React.useState(() => B.draft(original));
    const [context, setContext] = React.useState(original ? original.write_context : createContext);
    const [review, setReview] = React.useState(null), [error, setError] = React.useState(null), [loading, setLoading] = React.useState(false);
    const form = React.useId(), action = entity ? 'update' : 'create', seen = React.useRef(null);
    const formElement = React.useRef(null), [submitted, setSubmitted] = React.useState(false);
    const paths = ['business_code', 'part_ref', ...B.fields.map(key => 'fields.' + key)];
    const currentError = error || command.error;
    const fieldErrors = [...(submitted ? B.inputErrors(value, entity) : []), ...C.fieldErrors(currentError)];
    const guardOwner = window.WorkbenchGuards.useDirtyGuard({ dirty: command.phase !== 'done' && JSON.stringify(value) !== JSON.stringify(B.draft(entity)),
      locked: command.locked, message: '批次资料尚未保存，离开会丢失本次填写。' });
    React.useEffect(() => { if (currentError) window.ResourceControls.focusFirstInvalid(formElement.current); }, [currentError]);
    async function close(detail) {
      if (command.locked) return;
      if (detail && detail.guardConfirmed === true && detail.guardOwner === guardOwner || await window.WorkbenchGuards.confirmLeave({ owner: guardOwner })) onClose();
    }
    const choices = S.useQuery(async signal => {
      const result = await adapter.choices(signal);
      if (!result || !result.data || !Array.isArray(result.data.parts) || !result.data.parts.every(row => B.ref(row.ref))) throw C.failure('图号列表没有读到，请刷新后重试。');
      return result;
    }, [adapter], !entity);
    React.useEffect(() => {
      if (command.phase !== 'done' || seen.current === command.result.receipt_ref) return;
      try { B.receipt(command.result, action, entity && entity.ref); seen.current = command.result.receipt_ref; onCommitted(command.result); }
      catch (error) { setError(error); }
    }, [command.phase, command.result]);
    const locked = disabled || command.locked || command.phase === 'done' || loading;
    async function reload() {
      setLoading(true); setError(null);
      try { setReview(entity ? B.detail(await adapter.detail('batch', entity.ref), entity.ref) : B.list(await adapter.list('batch', { page: 1, size: 20, sort: 'business_code', direction: 'asc' }), { page: 1, size: 20, sort: 'business_code', direction: 'asc' })); }
      catch (error) { setError(error); } finally { setLoading(false); }
    }
    function acceptReview() {
      if (entity) {
        const next = review.data, previous = B.draft(entity), fresh = B.draft(next);
        setValue(current => Object.fromEntries(Object.keys(current).map(key => [key, current[key] === previous[key] ? fresh[key] : current[key]])));
        setEntity(next); setContext(next.write_context);
      } else setContext(review.data.create_context);
      setReview(null); setError(null); command.reset();
    }
    async function submit(event) {
      event.preventDefault(); if (locked || review || B.reason(context, action, source)) return;
      setSubmitted(true);
      try { const payload = B.input(value, entity); if (!Object.keys(payload.fields).length) throw C.failure('没有需要保存的变更。'); setError(null); await command.submit('batch', action, entity ? entity.ref : null, context, payload); }
      catch (error) { setError(error); }
    }
    return <Modal title={entity ? '编辑批次基础信息' : '新增批次'} icon="box" guardOwner={guardOwner} locked={command.locked} onClose={close} footer={<>
      <Button onClick={close} disabled={command.locked}>{command.phase === 'done' ? '关闭' : '取消'}</Button>
      {command.phase !== 'done' && <Button type="submit" form={form} icon="check" className="btn primary" disabled={locked || !!review || !entity && !choices.result}
        reasonDisplay="inline" reason={B.reason(context, action, source)}>{entity ? '保存基础信息' : '确认新增'}</Button>}</>}>
      <form id={form} ref={formElement} className="modal-b form" onSubmit={submit} noValidate>
        <BaseFields value={value} setValue={next => { setValue(next); setError(null); }} entity={entity} disabled={locked} choices={choices.result && choices.result.data} error={currentError} errors={fieldErrors} />
        <ErrorBox error={error} excludePaths={paths} /><ErrorBox error={choices.error} /><window.ResourceForms.Feedback command={command} excludePaths={error ? [] : paths} />
        {command.phase !== 'done' && <Button icon="refresh-cw" disabled={locked} onClick={reload}>刷新并核对</Button>}
        {review && <div className="batch-band"><Issues issues={[{ message: '已读到最新资料，您填写的内容没有被覆盖。' }]} />
          {entity && <dl>{B.fields.map(key => <React.Fragment key={key}><dt>{B.fieldNames[key]}</dt><dd>{window.BatchControls.display(key, review.data.fields[key])}</dd></React.Fragment>)}</dl>}
          <Button onClick={acceptReview} disabled={locked}>采用最新资料</Button></div>}
      </form>
    </Modal>;
  }
  function SyncPreview({ preview }) {
    const changeNames = { added: '新增', removed: '删除', updated: '修改', unchanged: '内容不变' };
    const operation = row => row ? <><div>{row.label} · {row.source === 'external' ? '外协' : '自制'}</div>
      {row.source === 'internal' ? <div>换型 {window.WorkbenchFormat.hours(row.setup_hours, ENTERED_HOURS)} / 单件 {window.WorkbenchFormat.hours(row.unit_hours, ENTERED_HOURS)}</div>
        : <><div>{row.external_group && row.external_group.merge_mode === 'merged' ? '整组周期 ' + window.WorkbenchFormat.number(row.external_group.total_days, ENTERED_DAYS) : '本序周期 ' + window.WorkbenchFormat.number(row.external_days, ENTERED_DAYS)} 天</div>
          <div>供应商：{(row.supplier || row.resources && row.resources.supplier || {}).label || '未填写'}</div></>}</> : '—';
    return <><div className="batch-sync-summary">{Object.entries(changeNames).map(([key, label]) => <span key={key}>{label} <b>{preview.change_counts[key]}</b> 道</span>)}</div>
      <div className="batch-preview wb-table-frame" data-sticky-head><table className="tbl wb-table batch-sync-table" aria-label="工序更新前后对照"><caption className="wb-visually-hidden">工序更新前后对照</caption>
        <thead><tr><th scope="col" style={{ width: 90 }}>工序 / 变化</th><th scope="col">当前批次工序</th><th scope="col">更新后</th></tr></thead><tbody>
          {preview.changes.map((row, index) => <tr key={index}><td><div>{row.sequence}{row.piece_id ? ' · ' + row.piece_id : ''}</div><div>{changeNames[row.change]}</div></td><td>{operation(row.before)}</td><td>{operation(row.after)}</td></tr>)}
        </tbody></table></div>
      <div className="batch-sync-resources"><h3>设备和人员指定</h3>{preview.cleared_resources.length ? <><p>以下 {preview.cleared_resources.length} 道工序的指定将被清除，更新后可重新指定。</p>
        <ul>{preview.cleared_resources.map(row => <li key={row.operation_ref}>{row.business_code}：{[row.machine && '设备 ' + row.machine.label, row.operator && '人员 ' + row.operator.label].filter(Boolean).join('；')}</li>)}</ul></>
        : <p>当前工序没有设备或人员指定，无需清除。</p>}</div>
      <p>确认后，将用上表中的工艺工序替换本批次现有工序。</p></>;
  }
  function Preview({ preview, command, onClose, onCommitted, disabled }) {
    const seen = React.useRef(null), [error, setError] = React.useState(null);
    const action = preview.operation.split('.')[1], subject = action === 'bulk_confirm' ? preview.preview_ref : preview.entity_ref;
    React.useEffect(() => {
      if (command.phase !== 'done' || seen.current === command.result.receipt_ref) return;
      try { B.receipt(command.result, action, subject); seen.current = command.result.receipt_ref; onCommitted(command.result); }
      catch (error) { setError(error); }
    }, [command.phase, command.result]);
    const value = row => row ? <><div>{[row.business_code, row.relationships.part_no, ...B.fields.map(key => window.BatchControls.display(key, row.fields[key]))].join(' · ')}</div>
      {row.operations.map((op, index) => <div key={index}>{op.business_code} · {op.sequence} · {op.label} · {op.source === 'external' ? '外协' : '自制'} ·
        {Object.values(op.resources).filter(Boolean).map(resource => resource.label).join(' / ')} · 换型 {window.WorkbenchFormat.hours(op.setup_hours, ENTERED_HOURS)} / 单件 {window.WorkbenchFormat.hours(op.unit_hours, ENTERED_HOURS)} / 周期 {window.WorkbenchFormat.number(op.external_days, ENTERED_DAYS)} · {B.label('status', op.status)}</div>)}
      <div>物料需求 {row.relationships.material_requirement_count} 项</div></> : '删除';
    const deleting = action === 'bulk_confirm' && preview.action === 'delete';
    return <Modal title={action === 'sync_confirm' ? '确认更新批次工序' : '确认批量' + ({ update: '修改', delete: '删除', copy: '复制' })[preview.action]} icon={deleting ? 'trash-2' : 'check'} locked={command.locked} onClose={onClose}
      footer={<><Button onClick={onClose} disabled={command.locked}>{command.phase === 'done' ? '关闭' : '取消'}</Button>{command.phase !== 'done' && <Button icon={deleting ? 'trash-2' : 'check'} className="btn primary" disabled={disabled || command.locked}
        onClick={() => command.submit('batch', action, subject, preview.write_context, { preview_ref: preview.preview_ref })}>{action === 'sync_confirm' ? '确认更新工序' : deleting ? '确认删除' : '确认变更'}</Button>}</>}>
      <div className="modal-b">{action === 'sync_confirm' ? <SyncPreview preview={preview} /> : <div className="batch-preview wb-table-frame" data-sticky-head><table className="tbl wb-table"><caption className="wb-visually-hidden">批次变更前后对照</caption><thead><tr><th scope="col">原记录</th><th scope="col">确认后</th></tr></thead><tbody>
        {preview.rows.map(row => <tr key={row.entity_ref}><td>{value(row.before)}</td><td>{value(row.after)}</td></tr>)}
      </tbody></table></div>}
        <Issues issues={preview.warnings || []} /><ErrorBox error={error} /><window.ResourceForms.Feedback command={command} action={deleting ? 'delete' : 'save'} /></div>
    </Modal>;
  }
  window.BatchForms = { BaseEditor, Preview };
})();
