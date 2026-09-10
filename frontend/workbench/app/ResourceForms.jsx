(function () {
  'use strict';
  const C = window.APSResourceContract;
  const { Button, ErrorBox, Issues, Status, Modal, Choice, Relation } = window.ResourceControls;
  const icons = { material: 'box', op_type: 'wrench', machine: 'machine', operator: 'users', supplier: 'truck' };
  function Feedback({ command }) {
    if (!command) return null;
    const phase = command.phase;
    return <>
      {['sending', 'checking'].includes(phase) && <p role="status">{phase === 'sending' ? '正在提交，请勿重复保存…' : '正在核实原请求的回执…'}</p>}
      {phase === 'pending' && <div role="status" className="match-note" style={{ display: 'block' }}>
        <p>结果待核实。请保留当前页面，不要重新新建或重复保存。</p>
        <Button icon="history" onClick={command.check}>查询原请求回执</Button>
      </div>}
      {phase === 'done' && <p role="status">{command.result.result === 'partial' ? '部分操作完成，请核对逐项结果。' : command.result.result === 'unchanged' ? '服务器确认内容未变化。' : '服务器已确认提交。'}</p>}
      <ErrorBox error={command.error} /><Issues issues={command.result && command.result.warnings || []} />
      {phase === 'done' && command.result.result === 'partial' && (Array.isArray(command.result.data.items) ? <ul>
        {command.result.data.items.map((item, index) => <li key={index}>{item.business_code || item.label || '第 ' + (index + 1) + ' 项'}：
          {({ committed: '已提交', unchanged: '未变化', failed: '失败', skipped: '未执行' })[item.result] || '结果待核实'}
          {item.error && item.error.message ? '；' + item.error.message : ''}</li>)}</ul> : <p role="alert">回执未附逐项明细，请在维护向导核实。未确认全部成功。</p>)}
    </>;
  }
  function LegacyFacts({ entity }) {
    if (!entity) return <div className="field full"><span className="fhint">新人员尚无设备操作授权；登记工种技能不会自动增加授权。</span></div>;
    const facts = entity.relationships.legacy_machine_authorizations;
    return <div className="field full"><label>既有设备授权（只读）</label>
      {Array.isArray(facts) ? facts.length ? <div className="chipline">{facts.map((item, index) => <span className="chip" key={item.ref || index} style={{ whiteSpace: 'normal' }}>
        {item.label || '设备名称未提供'}{item.status && item.status !== 'active' ? '（历史授权）' : ''}</span>)}</div> : <span className="fhint">无既有设备授权。</span> :
        Number.isSafeInteger(entity.relationships.machine_authorization_count) ? <span className="fhint">已登记 {entity.relationships.machine_authorization_count} 项设备授权；授权明细未提供。</span> :
          C.own(entity.relationships, 'machine_refs') ? <Relation entity={entity} field="machine_refs" /> : <span className="fhint">既有设备授权尚未读取，不能据技能推断。</span>}
      <span className="fhint">技能登记不改变既有设备授权。</span></div>;
  }
  function Field({ label, path, error, required, full, children }) {
    const id = React.useId(), errors = C.fieldErrors(error).filter(row => row.path === path || row.path === 'input.' + path);
    return <div className={'field' + (full ? ' full' : '') + (errors.length ? ' err' : '')} style={{ minWidth: 0 }}>
      <label htmlFor={id}>{label}{required && <span className="req" aria-hidden="true">*</span>}</label>
      {React.cloneElement(children, { id, 'aria-required': required || undefined, 'aria-invalid': errors.length ? true : undefined, 'aria-describedby': errors.length ? id + '-error' : undefined })}
      {errors.length > 0 && <span id={id + '-error'} style={{ color: 'var(--ui-danger-text)' }}>{errors.map(row => row.message).join(' ')}</span>}</div>;
  }
  function DetailStyles() {
    return <style>{`
      .plana .wb-resource-detail { color: var(--ui-text); padding: 20px; }
      .plana .wb-resource-identity { display: flex; align-items: flex-start; gap: 16px; padding-bottom: 16px; border-bottom: 1px solid var(--ui-border); }
      .plana .wb-resource-identity > div { flex: 1; min-width: 0; }
      .plana .wb-resource-identity .pill { flex: none; max-width: 42%; margin-top: 4px; }
      .plana .wb-resource-code { color: var(--ui-info-muted); font-size: 12px; overflow-wrap: anywhere; }
      .plana .wb-resource-identity h3 { margin: 4px 0 0; color: var(--ui-text); font-size: 17px; line-height: 1.5; font-weight: 600; overflow-wrap: anywhere; }
      .plana .wb-resource-facts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px 24px; margin: 0; padding: 16px 0; }
      .plana .wb-resource-fact { min-width: 0; }
      .plana .wb-resource-fact dt, .plana .wb-resource-remark dt { margin: 0 0 5px; color: var(--ui-info-muted); font-size: 12px; font-weight: 400; }
      .plana .wb-resource-fact dd, .plana .wb-resource-remark dd { margin: 0; color: var(--ui-text); font-size: 14px; text-align: left; overflow-wrap: anywhere; white-space: pre-wrap; font-variant-numeric: tabular-nums; }
      .plana .wb-resource-stock { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 8px; }
      .plana .wb-resource-stock strong { min-width: 0; max-width: 100%; font-size: 22px; line-height: 1.3; font-weight: 600; overflow-wrap: anywhere; }
      .plana .wb-resource-stock span { min-width: 0; color: var(--ui-info-muted); font-size: 13px; }
      .plana .wb-resource-remark { margin: 0; padding: 16px 0; border-top: 1px solid var(--ui-border); }
      .plana .wb-resource-links { padding: 16px 0; border-top: 1px solid var(--ui-border); }
      .plana .wb-resource-identity + .wb-resource-links { border-top: 0; }
      .plana .wb-resource-links .field > label { color: var(--ui-info-muted); font-size: 12px; font-weight: 400; }
      .plana .wb-resource-detail > .match-note { margin: 0 0 16px; }
      .plana .wb-resource-read-time { margin: 0; padding-top: 12px; border-top: 1px solid var(--ui-border); color: var(--ui-info-muted); font-size: 12px; overflow-wrap: anywhere; }
      .plana form.modal-b.form > .fgrid { margin-bottom: 16px; }
      .plana .wb-resource-review { margin-top: 16px; padding: 14px; border: 1px solid var(--ui-border); background: var(--ui-surface-muted); }
      .plana .wb-resource-review > p { margin: 0 0 12px; }
      .plana .wb-resource-review-identity { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 16px; }
      .plana .wb-resource-review-identity > strong { min-width: 0; flex: 1; overflow-wrap: anywhere; font-weight: 600; }
      .plana .wb-resource-review-identity > .pill { flex: none; max-width: 42%; }
      .plana .wb-resource-review .wb-resource-facts { padding-top: 0; }
      .plana .wb-resource-review .wb-resource-stock strong { font-size: 18px; }
      @media (max-width: 560px) { .plana .wb-resource-facts { grid-template-columns: minmax(0, 1fr); } }
    `}</style>;
  }
  function Remark({ kind, entity }) {
    return C.own(entity.fields, 'remark') ? <dl className="wb-resource-remark"><dt>{C.fieldLabels(kind, entity.fields.category).remark}</dt>
      <dd>{C.fieldValue(kind, 'remark', entity.fields.remark)}</dd></dl> : null;
  }
  function CurrentFields({ kind, entity, includeRemark = true }) {
    const labels = C.fieldLabels(kind, entity.fields.category);
    const stock = kind === 'material' && C.own(entity.fields, 'stock_qty');
    const keys = Object.keys(labels).filter(key => C.own(entity.fields, key) && key !== 'remark' && !(stock && key === 'unit'));
    return <>{keys.length > 0 && <dl className="wb-resource-facts">{keys.map(key => <div className="wb-resource-fact" key={key} data-field={key}><dt>{labels[key]}</dt>
      <dd>{stock && key === 'stock_qty' ? <span className="wb-resource-stock"><strong>{entity.fields.stock_qty == null ? '未知' : String(entity.fields.stock_qty)}</strong>
        <span>{entity.fields.unit || '单位未填写'}</span></span> : C.fieldValue(kind, key, entity.fields[key])}</dd></div>)}</dl>}
      {includeRemark && <Remark kind={kind} entity={entity} />}</>;
  }
  function StockFacts({ entity }) {
    return <><div className="field full"><label>物料</label><span style={{ overflowWrap: 'anywhere' }}>{entity.business_code} · {entity.label}</span></div>
      <div className="field full"><label>当前库存</label><span className="wb-resource-stock"><strong>{entity.fields.stock_qty == null ? '未知' : String(entity.fields.stock_qty)}</strong>
        <span>{entity.fields.unit || '单位未填写'}</span></span></div></>;
  }
  function ResourceForms({ adapter, kind, category, action = 'create', entity: initialEntity, acceptedEntity, writeContext, source, command,
    onClose, onReloadContext, refreshState = {}, onRefresh, contextError, contextReview, onAcceptContext, contextBusy, stockOnly = false }) {
    const [entity, setEntity] = React.useState(initialEntity);
    const [draft, setDraft] = React.useState(() => C.draft(kind, initialEntity, category));
    const [error, setError] = React.useState(null), [catalogBusy, setCatalogBusy] = React.useState(false);
    React.useLayoutEffect(() => {
      if (!acceptedEntity || acceptedEntity === entity) return;
      if (!entity || acceptedEntity.ref !== entity.ref) { setError(C.failure('最新资料与当前编辑的记录不一致，已填写的内容未被替换。')); return; }
      setDraft(value => C.rebaseDraft(kind, value, entity, acceptedEntity, category)); setEntity(acceptedEntity);
    }, [acceptedEntity, kind, category]);
    const formId = React.useId();
    const opCategory = draft.fields.category;
    const adjustingStock = stockOnly && kind === 'material' && action === 'update';
    const done = command.phase === 'done', disabled = command.locked || done || catalogBusy || contextBusy;
    const reason = typeof adapter.command !== 'function' ? '保存接口尚未接入。' : C.blocked(writeContext, kind, action, source);
    const currentError = error || command.error;
    function change(section, key, value) {
      setDraft(current => section ? { ...current, [section]: { ...current[section], [key]: value } } : { ...current, [key]: value }); setError(null);
    }
    async function submit(event) {
      event.preventDefault(); if (disabled || reason) return;
      try {
        const invalidNumbers = Array.from(event.currentTarget.elements).filter(element => element.type === 'number' && element.validity.badInput);
        if (invalidNumbers.length) throw C.failure('请核对表单中的数字。', invalidNumbers.map(element => ({ path: 'fields.' + element.name, message: '请输入有效数字，不能把无效内容作为未填写提交。' })));
        const inputDraft = adjustingStock ? C.draft(kind, entity, category) : draft;
        if (adjustingStock) inputDraft.fields.stock_qty = draft.fields.stock_qty;
        const input = action === 'delete' ? {} : C.input(kind, inputDraft, entity, category);
        setError(null); await command.submit(kind, action, entity ? entity.ref : null, writeContext, input, draft.fields.category);
      } catch (failure) { setError(failure); }
    }
    async function catalog(field, reload) {
      setCatalogBusy(true); setError(null);
      let opened = false;
      const completed = result => {
        setCatalogBusy(false);
        if (C.receipt(result) === 'terminal') { reload(); if (result.result === 'partial') setError(C.failure('目录维护仅部分完成，请在目录向导核对逐项结果。')); }
        else setError(C.failure('目录维护结果待核实，未视为保存成功。'));
      };
      try {
        const result = await adapter.openCatalog(field.kind, { refs: [], scope: { source }, onCommitted: completed, onClosed: () => setCatalogBusy(false) }, new AbortController().signal);
        if (result && result.state === 'opened') { opened = true; return; }
        if (result && result.state === 'cancelled') return;
        if (C.receipt(result) === 'terminal' && result.result !== 'partial') { reload(); return; }
        throw C.failure('目录维护未返回明确结果，未视为保存成功。');
      } catch (failure) { setError(failure); }
      finally { if (!opened) setCatalogBusy(false); }
    }
    const text = (key, label, options = {}) => <Field key={key} label={label} path={options.top ? key : 'fields.' + key} error={currentError} required={options.required} full={options.full}>
      {options.multiline ? <textarea name={key} value={draft.fields[key]} disabled={disabled} onChange={event => change('fields', key, event.target.value)} /> :
        <input name={key} value={options.top ? draft[key] : draft.fields[key]} disabled={disabled} readOnly={options.readOnly}
          type={options.number ? 'number' : 'text'} step={options.number ? 'any' : undefined} min={options.number ? 0 : undefined}
          style={options.number ? { textAlign: 'right', fontVariantNumeric: 'tabular-nums' } : undefined}
          onChange={event => change(options.top ? null : 'fields', key, event.target.value)} />}</Field>;
    const stateField = () => <Field label="状态" path="fields.status" error={currentError} required><select name="status" value={draft.fields.status} disabled={disabled} onChange={event => change('fields', 'status', event.target.value)}>
      <option value="" disabled>请选择状态</option>{C.statuses[kind].filter(row => row[0] !== 'unknown').map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      {!C.statuses[kind].some(row => row[0] === draft.fields.status && row[0] !== 'unknown') && draft.fields.status && <option value={draft.fields.status}>旧状态 / 原因未知（保持原值）</option>}</select></Field>;
    return <Modal title={adjustingStock ? '调整库存' : (action === 'create' ? '新增' : action === 'delete' ? '删除' : '编辑') + C.resourceName(kind, opCategory)} icon={icons[kind]} onClose={onClose} locked={command.locked || catalogBusy || contextBusy} suspended={catalogBusy}
      footer={<><Button onClick={onClose} reason={command.locked ? '结果未核实，暂不能关闭。' : contextBusy ? '正在读取最新资料。' : ''} disabled={catalogBusy}>{done ? '关闭' : '取消'}</Button>
        {!done && <Button form={formId} type="submit" icon={action === 'delete' ? 'minus' : 'check'} className={'btn primary wb-action wb-primary'} reason={reason} busy={disabled}>
          {action === 'delete' ? '确认删除' : '保存'}</Button>}</>}>
      <form id={formId} className="modal-b form scroll" onSubmit={submit} noValidate><DetailStyles />
        {action === 'delete' ? <p>确认删除 <b>{entity.business_code} · {entity.label}</b>？服务端会重新核对引用和删除条件。</p> : adjustingStock ? <div className="fgrid" style={{ marginBottom: 12 }}>
          <StockFacts entity={entity} />{text('stock_qty', '调整后库存' + (entity.fields.unit ? '（' + entity.fields.unit + '）' : '（单位未填写）'), { number: true, full: true })}
        </div> : <div className="fgrid">
          {text('business_code', C.codeLabel(kind), { top: true, required: action === 'create', readOnly: action !== 'create' })}
          {text('label', C.nameLabel(kind), { top: true, required: true })}
          {kind === 'material' && <>{text('spec', '规格')}{text('unit', '单位')}{text('stock_qty', '库存数量', { number: true })}</>}
          {kind === 'op_type' && <>
            {!['internal', 'external'].includes(entity ? entity.fields.category : category) && <Field label="归属" path="fields.category" error={currentError} required><select name="category" value={opCategory} disabled={disabled} onChange={event => change('fields', 'category', event.target.value)}>
              <option value="" disabled>请选择归属</option><option value="internal">自制</option><option value="external">外协</option>
              {opCategory && !['internal', 'external'].includes(opCategory) && <option value={opCategory}>原归属未识别（保持原值）</option>}</select></Field>}
            {opCategory === 'external' && <Field label="默认周期策略" path="fields.default_merge_mode" error={currentError}><select name="default_merge_mode" value={draft.fields.default_merge_mode} disabled={disabled} onChange={event => change('fields', 'default_merge_mode', event.target.value)}>
              <option value="">未设置</option><option value="separate">分别设置</option><option value="merged">合并设置</option>
              {!['', 'separate', 'merged'].includes(draft.fields.default_merge_mode) && <option value={draft.fields.default_merge_mode}>原周期策略未识别（保持原值）</option>}</select></Field>}</>}
          {(C.relations[kind] || []).map(field => <Choice key={field.key} adapter={adapter} field={field} value={draft.relationships[field.key]} original={entity}
            disabled={disabled} onChange={value => change('relationships', field.key, value)} onCatalog={catalog} catalogBusy={catalogBusy} />)}
          {kind === 'supplier' && text('default_days', '默认周期（天）', { number: true, required: true })}
          {C.statuses[kind] && stateField()}
          {entity && entity.fields.inactive_reason === 'unknown' && <div className="field full"><span className="fhint">当前停用原因未知，未认定为请假或待复核。</span></div>}
          {entity && C.own(entity.fields, 'legacy_status') && <div className="field full"><label>原始状态（只读）</label><span className="fhint">{entity.fields.legacy_status === 'inactive' ? '原停用状态，原因未登记' : '原状态：' + String(entity.fields.legacy_status)}</span></div>}
          {(kind === 'material' || kind === 'op_type') && text('remark', kind === 'op_type' && opCategory === 'internal' ? '产能备注' : '备注', { full: true, multiline: true })}
          {kind === 'operator' && <LegacyFacts entity={entity} />}
        </div>}
        <Issues issues={entity && entity.issues || []} />
        <ErrorBox error={error} /><Feedback command={command} /><ErrorBox error={contextError} />
        {reason && <p role="status">{reason}</p>}
        {!done && !command.locked && onReloadContext && <Button icon="refresh-cw" busy={contextBusy} disabled={catalogBusy} onClick={onReloadContext}>重新读取最新资料</Button>}
        {contextReview && !done && <div className="wb-resource-review" role="status">
          <p>最新资料已读取，已填写的内容保持不变。请核对后继续编辑。</p>
          {contextReview.data.ref ? <><div className="wb-resource-review-identity"><strong>{contextReview.data.business_code} · {contextReview.data.label}</strong>{kind !== 'op_type' && <Status kind={kind} entity={contextReview.data} />}</div>
            <CurrentFields kind={kind} entity={contextReview.data} />
            {(C.relations[kind] || []).map(field => <p key={field.key}>{field.label}：<Relation entity={contextReview.data} field={field.key} /></p>)}</> : <p>当前资料总数：{contextReview.data.page.total}</p>}
          <Button disabled={disabled} onClick={onAcceptContext}>已核对，继续编辑</Button></div>}
        {done && <><p role="status">{refreshState.loading ? '正在重读列表和详情…' : refreshState.done ? '已重新读取最新数据。' : '最新数据尚未确认。'}</p><ErrorBox error={refreshState.error} />
          <Issues issues={refreshState.detail && refreshState.detail.data.issues || []} />
          {refreshState.error && <Button icon="refresh-cw" onClick={onRefresh}>重新读取保存结果</Button>}</>}
      </form></Modal>;
  }
  function Detail({ adapter, kind, result, onClose, onEdit, onDelete, onAdjustStock, onRelated, onBack, busy, error, onRetry }) {
    const entity = result && result.data;
    return <Modal title={C.resourceName(kind, entity && entity.fields.category) + '详情'} icon={icons[kind]} onClose={onClose} footer={<>{onBack && <Button icon="chevron-left" onClick={onBack}>返回上一条详情</Button>}<Button onClick={onClose}>关闭</Button>
      {entity && <><Button icon="minus" reason={C.blocked(entity.write_context, kind, 'delete', result.meta.source)} onClick={onDelete}>删除</Button>
        {kind === 'material' && <Button icon="square-pen" reason={C.blocked(entity.write_context, kind, 'update', result.meta.source) || (typeof onAdjustStock !== 'function' ? '库存调整入口尚未接入。' : '')} onClick={onAdjustStock}>调整库存</Button>}
        <Button icon="square-pen" className="btn primary" reason={C.blocked(entity.write_context, kind, 'update', result.meta.source)} onClick={onEdit}>编辑</Button></>}</>}>
      <div className="modal-b scroll wb-resource-detail"><DetailStyles />{busy && <p role="status">正在读取详情…</p>}<ErrorBox error={error} />{error && <Button onClick={onRetry}>重新读取</Button>}
        {entity && <><div className="wb-resource-identity"><div><div className="wb-resource-code">{entity.business_code}</div><h3>{entity.label}</h3></div>{kind !== 'op_type' && <Status kind={kind} entity={entity} />}</div>
          <CurrentFields kind={kind} entity={entity} includeRemark={false} />{(kind === 'op_type' || (C.relations[kind] || []).length > 0) && <div className="wb-resource-links fgrid">
            {kind === 'op_type' && <div className="field"><label>排产口径</label><span>{entity.fields.category === 'internal' ? '工时（换型＋单件）' : entity.fields.category === 'external' ? '周期（天）' : '未明确'}</span></div>}
            {(C.relations[kind] || []).map(field => <div className="field" key={field.key}><label>{field.label}</label><Relation entity={entity} field={field.key}
              onOpen={!field.catalog && onRelated ? ref => onRelated(field.kind, ref, field.category) : undefined} /></div>)}
            {kind === 'operator' && <LegacyFacts entity={entity} />}</div>}<Remark kind={kind} entity={entity} /><Issues issues={entity.issues} />
          {kind === 'op_type' && ['internal', 'external'].includes(entity.fields.category) && <window.ResourceDetailRelations key={entity.ref + ':' + result.meta.snapshot_ref} adapter={adapter} entity={entity} onOpen={onRelated} />}
          <Issues issues={result.warnings} /><p className="wb-resource-read-time">读取时间：<time dateTime={result.meta.as_of}>{result.meta.as_of.replace('T', ' ')}</time></p></>}</div></Modal>;
  }
  ResourceForms.Detail = Detail;
  ResourceForms.Feedback = Feedback;
  window.ResourceForms = ResourceForms;
})();
