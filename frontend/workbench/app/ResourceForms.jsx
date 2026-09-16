(function () {
  'use strict';
  const C = window.APSResourceContract;
  const { Button, ErrorBox, Issues, Status, Modal, Choice, Relation, Field, focusFirstInvalid } = window.ResourceControls;
  const icons = { material: 'box', op_type: 'wrench', machine: 'machine', operator: 'users', supplier: 'truck' };
  function Feedback({ command, action, excludePaths = [] }) {
    if (!command) return null;
    const phase = command.phase, intent = command.intent || {}, operation = action || intent.action;
    const bulkDelete = operation === 'confirm' && ['material_bulk', 'op_type_bulk', 'machine_bulk', 'operator_bulk', 'supplier_bulk', 'process_bulk'].includes(intent.kind);
    const batchAction = command.result && command.result.data && command.result.data.action;
    const verb = intent.kind === 'calendar' && operation === 'delete' ? '清除日历配置'
      : operation === 'delete' || bulkDelete ? '删除' : operation === 'unlink' ? '解除关联'
        : intent.kind === 'batch' && operation === 'bulk_confirm' ? ['delete', 'update', 'copy'].includes(batchAction) ? ({ delete: '删除', update: '保存', copy: '复制' })[batchAction] : '批次操作'
          : operation === 'machine_permissions' ? '设备关联保存' : operation === 'import' ? '导入' : '保存';
    return <>
      {['sending', 'checking'].includes(phase) && <p role="status">{phase === 'sending' ? '正在提交' + verb + '，请勿重复操作…' : '正在查询上次' + verb + '的结果…'}</p>}
      {phase === 'pending' && <div role="status" className="match-note" style={{ display: 'block' }}>
        <p>{window.WorkbenchTerms.outcomes.pending(verb)}</p>
        <Button icon="history" onClick={command.check}>{window.WorkbenchTerms.actions.query_result}</Button>
      </div>}
      {phase === 'done' && <p role="status">{command.result.result === 'partial' ? '部分' + verb + '已完成，请核对逐项结果。' : command.result.result === 'unchanged' ? '内容没有变化，已确认。' : window.WorkbenchTerms.outcomes.done(verb)}</p>}
      <ErrorBox error={command.error} excludePaths={excludePaths} /><Issues issues={command.result && command.result.warnings || []} />
      {phase === 'done' && command.result.result === 'partial' && (Array.isArray(command.result.data.items) ? <ul>
        {command.result.data.items.map((item, index) => <li key={index}>{item.business_code || item.label || '第 ' + (index + 1) + ' 项'}：
          {({ committed: '已提交', unchanged: '未变化', failed: '失败', skipped: '未执行' })[item.result] || '结果未确认'}
          {item.error && item.error.message ? '；' + item.error.message : ''}</li>)}</ul> : <p role="alert">结果里没有逐项明细，请在维护向导里核对。没有当成全部成功。</p>)}
    </>;
  }
  function LegacyFacts({ entity }) {
    if (!entity) return <div className="field full"><span className="fhint">请在人员详情中设置可操作设备。</span></div>;
    const permissions = entity.relationships.machine_permissions;
    if (Array.isArray(permissions)) return <div className="field full"><label>可操作设备</label>
      {permissions.length ? <div className="chipline">{permissions.map(item => <span className="chip" key={item.machine_ref} style={{ whiteSpace: 'normal' }}>
        {item.business_code} · {item.label}{item.is_primary === 'yes' ? '（主操）' : ''}</span>)}</div> : <span className="fhint">尚未设置可操作设备。</span>}
      <span className="fhint">在人员详情中点“编辑可操作设备”维护设备关联。</span></div>;
    const facts = entity.relationships.legacy_machine_authorizations;
    return <div className="field full"><label>既有设备授权（只读）</label>
      {Array.isArray(facts) ? facts.length ? <div className="chipline">{facts.map((item, index) => <span className="chip" key={item.ref || index} style={{ whiteSpace: 'normal' }}>
        {item.label || '设备名称未填写'}{item.status && item.status !== 'active' ? '（历史授权）' : ''}</span>)}</div> : <span className="fhint">无既有设备授权。</span> :
        Number.isSafeInteger(entity.relationships.machine_authorization_count) ? <span className="fhint">已登记 {entity.relationships.machine_authorization_count} 项设备授权，明细未读取。</span> :
          C.own(entity.relationships, 'machine_refs') ? <Relation entity={entity} field="machine_refs" /> : <span className="fhint">设备授权尚未读取。</span>}
      <span className="fhint">技能登记不改变既有设备授权。</span></div>;
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
    onClose, onReloadContext, refreshState = {}, onRefresh, contextError, contextReview, contextBusy, stockOnly = false }) {
    const [entity, setEntity] = React.useState(initialEntity);
    const [draft, setDraft] = React.useState(() => C.draft(kind, initialEntity, category));
    const baseline = React.useRef(JSON.stringify(C.draft(kind, initialEntity, category))), form = React.useRef(null);
    const [error, setError] = React.useState(null), [catalogBusy, setCatalogBusy] = React.useState(false);
    const [deleteChecked, setDeleteChecked] = React.useState(false);
    React.useLayoutEffect(() => {
      if (!acceptedEntity || acceptedEntity === entity) return;
      if (!entity || acceptedEntity.ref !== entity.ref) { setError(C.failure('最新资料和正在编辑的记录不一致，已填写的内容没有被替换。')); return; }
      baseline.current = JSON.stringify(C.draft(kind, acceptedEntity, category));
      setDraft(value => C.rebaseDraft(kind, value, entity, acceptedEntity, category)); setEntity(acceptedEntity);
    }, [acceptedEntity, kind, category]);
    const formId = React.useId();
    const opCategory = draft.fields.category;
    const adjustingStock = stockOnly && kind === 'material' && action === 'update';
    const done = command.phase === 'done', disabled = command.locked || done || catalogBusy || contextBusy;
    const reason = typeof adapter.command !== 'function' ? '保存功能尚未开通。' : C.blocked(writeContext, kind, action, source);
    // Deleting basic data takes the checkbox confirmation used for backup deletion; the unchecked state is the button's own reason, not a bare sentence.
    const confirmReason = action === 'delete' && !deleteChecked ? '请先勾选已核对要删除的资料及其关联关系。' : '';
    const currentError = error || command.error;
    const guardOwner = window.WorkbenchGuards.useDirtyGuard({ dirty: action !== 'delete' && !done && JSON.stringify(draft) !== baseline.current,
      // Only a pending command locks the draft guard; catalog or context busy states are UI state, not an unverified request.
      message: '基础资料里有尚未保存的填写内容。', locked: command.locked });
    React.useEffect(() => { if (currentError) focusFirstInvalid(form.current); }, [currentError]);
    const fieldPaths = action === 'delete' ? [] : adjustingStock ? ['fields.stock_qty'] : ['business_code', 'label',
      ...(kind === 'material' ? ['fields.spec', 'fields.unit', 'fields.stock_qty', 'fields.remark'] : []),
      ...(kind === 'op_type' ? ['fields.remark', ...(!['internal', 'external'].includes(entity ? entity.fields.category : category) ? ['fields.category'] : []),
        ...(opCategory === 'external' ? ['fields.default_merge_mode'] : [])] : []),
      ...(kind === 'supplier' ? ['fields.default_days'] : []), ...(C.statuses[kind] ? ['fields.status'] : []),
      ...(C.relations[kind] || []).flatMap(field => [field.key, 'relationships.' + field.key])];
    async function close(detail) {
      if (command.locked || catalogBusy || contextBusy) return;
      if (!(detail && detail.guardConfirmed === true && detail.guardOwner === guardOwner) && !await window.WorkbenchGuards.confirmLeave({ owner: guardOwner })) return;
      onClose();
    }
    function change(section, key, value) {
      setDraft(current => section ? { ...current, [section]: { ...current[section], [key]: value } } : { ...current, [key]: value }); setError(null);
    }
    async function submit(event) {
      event.preventDefault(); if (disabled || reason || confirmReason) return;
      try {
        const invalidNumbers = Array.from(event.currentTarget.elements).filter(element => element.type === 'number' && element.validity.badInput);
        if (invalidNumbers.length) throw C.failure('请核对标红的数字。', invalidNumbers.map(element => ({ path: 'fields.' + element.name, message: '请输入有效数字。' })));
        const inputDraft = adjustingStock ? C.draft(kind, entity, category) : draft;
        if (adjustingStock) inputDraft.fields.stock_qty = draft.fields.stock_qty;
        const input = action === 'delete' ? {} : C.input(kind, inputDraft, entity, category);
        setError(null); await command.submit(kind, action, entity ? entity.ref : null, writeContext, input, draft.fields.category);
      } catch (failure) { setError(failure); }
    }
    async function catalog(field, reload) {
      setCatalogBusy(true); setError(null);
      let opened = false;
      const refreshParent = () => { reload(); if (onReloadContext) onReloadContext(); };
      const completed = result => {
        setCatalogBusy(false);
        if (C.receipt(result) === 'terminal') { refreshParent(); if (result.result === 'partial') setError(C.failure(field.label + '只完成了一部分，请点「维护' + field.label + '」核对逐项结果。')); }
        else setError(C.failure(field.label + '的维护结果还没确认，没有当成保存成功。'));
      };
      try {
        const result = await adapter.openCatalog(field.kind, { refs: [], scope: { source }, onCommitted: completed, onClosed: () => setCatalogBusy(false) }, new AbortController().signal);
        if (result && result.state === 'opened') { opened = true; return; }
        if (result && result.state === 'cancelled') return;
        if (C.receipt(result) === 'terminal' && result.result !== 'partial') { refreshParent(); return; }
        throw C.failure(field.label + '维护没有返回明确结果，没有当成保存成功。');
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
    return <Modal title={adjustingStock ? '调整库存' : (action === 'create' ? '新增' : action === 'delete' ? '删除' : '编辑') + C.resourceName(kind, opCategory)} icon={action === 'delete' ? 'trash-2' : icons[kind]} onClose={close} guardOwner={guardOwner} locked={command.locked || catalogBusy || contextBusy} suspended={catalogBusy}
      footer={<><Button onClick={close} reason={command.locked ? '结果还没确认，暂时不能关闭。' : contextBusy ? '正在读取最新资料。' : ''} disabled={catalogBusy}>{done ? '关闭' : '取消'}</Button>
        {!done && <Button form={formId} type="submit" icon={action === 'delete' ? 'trash-2' : 'check'} className={'btn primary wb-action wb-primary'} reason={reason || confirmReason} busy={disabled}>
          {action === 'delete' ? '确认删除' : '保存'}</Button>}</>}>
      <form id={formId} ref={form} className="modal-b form scroll" onSubmit={submit} noValidate>
        {action === 'delete' ? <><p>确认删除 <b>{entity.business_code} · {entity.label}</b>？系统会再次核对关联关系和删除条件。</p>
          <label className="rm-check"><input type="checkbox" checked={deleteChecked} disabled={disabled} onChange={event => setDeleteChecked(event.target.checked)} />我已核对要删除的资料及其关联关系</label></> : adjustingStock ? <div className="fgrid" style={{ marginBottom: 12 }}>
          <StockFacts entity={entity} />{text('stock_qty', '调整后库存' + (entity.fields.unit ? '（' + entity.fields.unit + '）' : '（单位未填写）'), { number: true, full: true })}
        </div> : <div className="fgrid">
          {text('business_code', C.codeLabel(kind), { top: true, required: action === 'create', readOnly: action !== 'create' })}
          {text('label', C.nameLabel(kind), { top: true, required: true })}
          {kind === 'material' && <>{text('spec', '规格')}{text('unit', '单位')}{text('stock_qty', '库存数量', { number: true })}</>}
          {kind === 'op_type' && <>
            {!['internal', 'external'].includes(entity ? entity.fields.category : category) && <Field label="归属" path="fields.category" error={currentError} required><select name="category" value={opCategory} disabled={disabled} onChange={event => change('fields', 'category', event.target.value)}>
              <option value="" disabled>请选择归属</option><option value="internal">自制</option><option value="external">外协</option>
              {opCategory && !['internal', 'external'].includes(opCategory) && <option value={opCategory}>原归属未识别（保持原值）</option>}</select></Field>}
            {opCategory === 'external' && <Field label="默认周期规则" path="fields.default_merge_mode" error={currentError}><select name="default_merge_mode" value={draft.fields.default_merge_mode} disabled={disabled} onChange={event => change('fields', 'default_merge_mode', event.target.value)}>
              <option value="">未填写</option><option value="separate">分别设置</option><option value="merged">合并设置</option>
              {!['', 'separate', 'merged'].includes(draft.fields.default_merge_mode) && <option value={draft.fields.default_merge_mode}>原周期规则未识别（保持原值）</option>}</select></Field>}</>}
          {(C.relations[kind] || []).map(field => <Choice key={field.key} adapter={adapter} field={field} value={draft.relationships[field.key]} original={entity}
            disabled={disabled} error={currentError} onChange={value => change('relationships', field.key, value)} onCatalog={catalog} catalogBusy={catalogBusy} />)}
          {kind === 'supplier' && text('default_days', '默认周期（天）', { number: true, required: true })}
          {C.statuses[kind] && stateField()}
          {entity && entity.fields.inactive_reason === 'unknown' && <div className="field full"><span className="fhint">当前停用原因未知，没有当成请假或待复核。</span></div>}
          {entity && C.own(entity.fields, 'legacy_status') && <div className="field full"><label>原始状态（只读）</label><span className="fhint">{entity.fields.legacy_status === 'inactive' ? '原停用状态，原因未登记' : '原状态：' + String(entity.fields.legacy_status)}</span></div>}
          {(kind === 'material' || kind === 'op_type') && text('remark', kind === 'op_type' && opCategory === 'internal' ? '产能备注' : '备注', { full: true, multiline: true })}
          {kind === 'operator' && <LegacyFacts entity={entity} />}
        </div>}
        <Issues issues={entity && entity.issues || []} />
        <ErrorBox error={error} excludePaths={fieldPaths} /><Feedback command={command} action={action} excludePaths={error ? [] : fieldPaths} /><ErrorBox error={contextError} />
        {reason && <p role="status">{reason}</p>}
        {!done && !command.locked && onReloadContext && <Button icon="refresh-cw" busy={contextBusy} disabled={catalogBusy} onClick={onReloadContext}>刷新最新资料</Button>}
        {contextReview && !done && <div className="wb-resource-review" role="status">
          <p>最新资料已刷新。你修改的内容已保留，未修改的项已更新；下方显示当前已保存的资料。</p>
          {contextReview.data.ref ? <><div className="wb-resource-review-identity"><strong>{contextReview.data.business_code} · {contextReview.data.label}</strong>{kind !== 'op_type' && <Status kind={kind} entity={contextReview.data} />}</div>
            <CurrentFields kind={kind} entity={contextReview.data} />
            {(C.relations[kind] || []).map(field => <p key={field.key}>{field.label}：<Relation entity={contextReview.data} field={field.key} /></p>)}</> : <p>当前资料总数：{contextReview.data.page.total}</p>}
          </div>}
        {done && <><p role="status">{refreshState.loading ? '正在刷新列表和详情…' : refreshState.done ? '已刷新到最新数据。' : '最新数据还没确认。请点「刷新保存结果」。'}</p><ErrorBox error={refreshState.error} />
          <Issues issues={refreshState.detail && refreshState.detail.data.issues || []} />
          {refreshState.error && <Button icon="refresh-cw" onClick={onRefresh}>刷新保存结果</Button>}</>}
      </form></Modal>;
  }
  function Detail({ adapter, kind, result, onClose, onEdit, onDelete, onAdjustStock, onMachinePermissions, onRelated, onBack, busy, error, onRetry }) {
    const entity = result && result.data;
    return <Modal title={C.resourceName(kind, entity && entity.fields.category) + '详情'} icon={icons[kind]} onClose={onClose} footer={<>{onBack && <Button icon="chevron-left" onClick={onBack}>返回上一条详情</Button>}<Button onClick={onClose}>关闭</Button>
      {entity && <><Button icon="trash-2" reason={C.blocked(entity.write_context, kind, 'delete', result.meta.source)} onClick={onDelete}>删除</Button>
        {kind === 'material' && <Button icon="square-pen" reason={C.blocked(entity.write_context, kind, 'update', result.meta.source) || (typeof onAdjustStock !== 'function' ? '调整库存尚未开通。' : '')} onClick={onAdjustStock}>调整库存</Button>}
        <Button icon="square-pen" className="btn primary" reason={C.blocked(entity.write_context, kind, 'update', result.meta.source)} onClick={onEdit}>编辑</Button></>}</>}>
      <div className="modal-b scroll wb-resource-detail">{busy && <p role="status">正在读取详情…</p>}<ErrorBox error={error} />{error && <Button onClick={onRetry}>刷新</Button>}
        {entity && <><div className="wb-resource-identity"><div><div className="wb-resource-code">{entity.business_code}</div><h3>{entity.label}</h3></div>{kind !== 'op_type' && <Status kind={kind} entity={entity} />}</div>
          <CurrentFields kind={kind} entity={entity} includeRemark={false} />{(kind === 'op_type' || (C.relations[kind] || []).length > 0) && <div className="wb-resource-links fgrid">
            {kind === 'op_type' && <div className="field"><label>排产方式</label><span>{entity.fields.category === 'internal' ? '工时（换型＋单件）' : entity.fields.category === 'external' ? '周期（天）' : '未明确'}</span></div>}
            {(C.relations[kind] || []).map(field => <div className="field" key={field.key}><label>{field.label}</label><Relation entity={entity} field={field.key}
              onOpen={!field.catalog && onRelated ? ref => onRelated(field.kind, ref, field.category) : undefined} /></div>)}
            {kind === 'operator' && <LegacyFacts entity={entity} />}</div>}<Remark kind={kind} entity={entity} /><Issues issues={entity.issues} />
          {kind === 'operator' && <Button icon="machine" reason={C.blocked(entity.write_context, kind, 'update', result.meta.source)
            || (typeof onMachinePermissions !== 'function' ? '设备关联编辑未连接。' : '')} onClick={onMachinePermissions}>编辑可操作设备</Button>}
          {kind === 'op_type' && ['internal', 'external'].includes(entity.fields.category) && <window.ResourceDetailRelations key={entity.ref + ':' + result.meta.snapshot_ref} adapter={adapter} entity={entity} onOpen={onRelated} />}
          <Issues issues={result.warnings} /><p className="wb-resource-read-time">读取时间：<time dateTime={result.meta.as_of}>{window.WorkbenchFormat.dateTime(result.meta.as_of)}</time></p></>}</div></Modal>;
  }
  ResourceForms.Detail = Detail;
  ResourceForms.Feedback = Feedback;
  window.ResourceForms = ResourceForms;
})();
