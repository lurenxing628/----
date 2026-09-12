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
      if (!result || !result.data || !Array.isArray(result.data.parts) || !result.data.parts.every(row => B.ref(row.ref))) throw C.failure('图号目录未能正确读取。');
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
        reasonDisplay="inline" reason={B.reason(context, action, source)}>{entity ? '保存基础信息' : '创建批次'}</Button>}</>}>
      <form id={form} ref={formElement} className="modal-b form" onSubmit={submit} noValidate>
        <BaseFields value={value} setValue={next => { setValue(next); setError(null); }} entity={entity} disabled={locked} choices={choices.result && choices.result.data} error={currentError} errors={fieldErrors} />
        <ErrorBox error={error} excludePaths={paths} /><ErrorBox error={choices.error} /><window.ResourceForms.Feedback command={command} excludePaths={error ? [] : paths} />
        {command.phase !== 'done' && <Button icon="refresh-cw" disabled={locked} onClick={reload}>重新读取并核对</Button>}
        {review && <div className="batch-band"><Issues issues={[{ message: '最新资料已读回，未覆盖已填写内容。' }]} />
          {entity && <dl>{B.fields.map(key => <React.Fragment key={key}><dt>{B.fieldNames[key]}</dt><dd>{window.BatchControls.display(key, review.data.fields[key])}</dd></React.Fragment>)}</dl>}
          <Button onClick={acceptReview} disabled={locked}>采用最新资料继续编辑</Button></div>}
      </form>
    </Modal>;
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
    return <Modal title={action === 'sync_confirm' ? '确认刷新批次工序' : '确认批量' + ({ update: '修改', delete: '删除', copy: '复制' })[preview.action]} icon="check" locked={command.locked} onClose={onClose}
      footer={<><Button onClick={onClose} disabled={command.locked}>{command.phase === 'done' ? '关闭' : '取消'}</Button>{command.phase !== 'done' && <Button icon="check" className="btn primary" disabled={disabled || command.locked}
        onClick={() => command.submit('batch', action, subject, preview.write_context, { preview_ref: preview.preview_ref })}>确认变更</Button>}</>}>
      <div className="modal-b"><div className="batch-preview wb-table-frame" data-sticky-head><table className="tbl wb-table"><caption className="wb-visually-hidden">批次变更前后对照</caption><thead><tr><th scope="col">原记录</th><th scope="col">确认后</th></tr></thead><tbody>
        {action === 'bulk_confirm' ? preview.rows.map(row => <tr key={row.entity_ref}><td>{value(row.before)}</td><td>{value(row.after)}</td></tr>)
          : <tr><td>{preview.before.map(row => <div key={row.ref}>{row.sequence} · {row.label} · {B.label('status', row.status)}</div>)}</td>
            <td>{preview.after.map((row, index) => <div key={index}>{row.sequence} · {row.label} · 换型 {window.WorkbenchFormat.hours(row.setup_hours, ENTERED_HOURS)} / 单件 {window.WorkbenchFormat.hours(row.unit_hours, ENTERED_HOURS)} / 周期 {window.WorkbenchFormat.number(row.external_days, ENTERED_DAYS)}</div>)}</td></tr>}
      </tbody></table></div>{action === 'sync_confirm' && <p>刷新会替换现有工序及资源补充；缺失工时保留未填写，已有计划或执行引用时不能刷新。</p>}
        <Issues issues={preview.warnings || []} /><ErrorBox error={error} /><window.ResourceForms.Feedback command={command} /></div>
    </Modal>;
  }
  window.BatchForms = { BaseEditor, Preview };
})();
