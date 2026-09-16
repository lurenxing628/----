(function () {
  'use strict';
  const B = window.APSBatchContract, S = window.APSResourceSession;
  const { Button, ErrorBox, Issues } = window.ResourceControls;
  // Quotas are shown as entered (up to four decimals); a one-decimal summary would hide non-zero unit hours.
  const ENTERED_HOURS = { digits: 4, trim: true }, ENTERED_DAYS = { digits: 1, trim: true };
  function BatchDetail({ adapter, batchRef, revision, onBack, onEdit, onDelete, onOperation, onSync, disabled }) {
    const read = S.useQuery(async signal => B.detail(await adapter.detail('batch', batchRef, signal), batchRef), [adapter, batchRef, revision]);
    const entity = read.result && read.result.data;
    if (!entity) return <section className="batch-band"><Button icon="arrow-left" onClick={onBack} disabled={disabled}>返回列表</Button>
      {read.loading && <p role="status">正在读取批次详情…</p>}<ErrorBox error={read.error} />{read.error && <Button icon="refresh-cw" onClick={read.reload}>刷新详情</Button>}</section>;
    const reason = action => B.reason(entity.write_context, action, read.result.meta.source);
    const template = entity.template;
    return <div data-batch-detail={entity.ref}>
      <section className="batch-band"><div className="batch-section-head"><h2>批次详情 · {entity.business_code}</h2><div className="batch-section-actions">
        <Button icon="arrow-left" onClick={onBack} disabled={disabled}>返回列表</Button><Button icon="trash-2" aria-label="删除批次" disabled={disabled} reasonDisplay="tooltip" reason={reason('delete')} onClick={() => onDelete(entity)}>删除批次</Button></div></div>
        <dl className="batch-facts-grid"><div className="batch-fact-wide"><dt>图号 / 零件</dt><dd>{entity.relationships.part_no} · {entity.label}</dd></div><div><dt>数量</dt><dd>{window.WorkbenchFormat.number(entity.fields.quantity, { digits: 0 })}</dd></div>
          <div><dt>批次状态</dt><dd>{B.label('status', entity.status)}</dd></div><div><dt>工序进度</dt><dd>已完成 {entity.relationships.completed_count} / {entity.operations.length} 道</dd></div></dl>
        {entity.protected && <div className="batch-restriction" role="status"><p>已有排产、报工或执行状态记录，暂不能删除、替换或编辑工序。</p><details><summary>查看关联情况</summary>
          <p>计划及试调关联 {entity.relationships.plan_reference_count} 条 · 报工及执行记录 {entity.relationships.execution_reference_count} 条 · 批次状态 {B.label('status', entity.status)}</p></details></div>}
        {!entity.protected && reason('delete') && <p className="batch-restriction" role="status">{reason('delete')}</p>}<Issues issues={entity.issues} /></section>
      <section className="batch-band"><div className="batch-section-head"><h3>批次基础信息</h3><Button icon="square-pen" onClick={() => onEdit(entity)} disabled={disabled} reasonDisplay="tooltip" reason={reason('update')}>编辑基础信息</Button></div>
        <dl className="batch-facts-grid"><div><dt>交期</dt><dd>{window.WorkbenchFormat.date(entity.fields.due_date)}</dd></div><div><dt>优先级</dt><dd>{B.label('priority', entity.fields.priority)}</dd></div>
          <div><dt>齐套状态</dt><dd>{B.label('ready_status', entity.fields.ready_status)}</dd></div><div><dt>齐套日期</dt><dd>{window.WorkbenchFormat.date(entity.fields.ready_date)}</dd></div><div className="batch-fact-full"><dt>备注</dt><dd>{B.label('', entity.fields.remark)}</dd></div></dl>
        {entity.materials.count > 0 && <details><summary>物料齐套原记录 · {entity.materials.count} 项</summary><div className="wb-table-frame" data-sticky-head><table className="tbl wb-table" style={{ minWidth: 640 }} aria-label="批次物料齐套"><caption className="wb-visually-hidden">批次物料齐套</caption><thead><tr><th scope="col">物料</th><th scope="col">需求量</th><th scope="col">到料量</th><th scope="col">单位</th><th scope="col">齐套记录</th></tr></thead><tbody>
          {entity.materials.requirements.map(row => <tr key={row.material_ref}><td>{row.business_code} · {row.label}<Issues issues={row.issues} /></td><td>{window.WorkbenchFormat.number(row.required_quantity)}</td><td>{window.WorkbenchFormat.number(row.available_quantity)}</td><td>{row.unit || '未填写'}</td><td>{B.label('ready_status', row.ready_status)}</td></tr>)}
        </tbody></table></div></details>}</section>
      <section className="batch-band batch-template"><div className="batch-section-head"><h3>从工艺模板更新工序</h3></div>
        <dl className="batch-facts-grid"><div className="batch-fact-wide"><dt>来源工艺</dt><dd>{entity.relationships.part_no} · {entity.relationships.part_name}</dd></div><div><dt>有效工序</dt><dd>{template.operation_count} 道</dd></div>
          <div className="batch-fact-full"><dt>更新条件</dt><dd>{entity.protected ? '已有排产或执行记录，暂不能替换工序。' : template.complete ? '工艺资料齐全，可以预览本次更新。' : '请先补齐下列工艺资料。'}</dd></div></dl>
        <Issues issues={template.diagnostics} />
        <div className="batch-template-action"><Button icon="refresh-cw" aria-label="预览工序更新" disabled={disabled} reasonDisplay="tooltip" reason={reason('sync_confirm')} onClick={() => onSync(entity, read.result.meta.snapshot_ref)}>预览工序更新</Button>
          <span className="muted">先查看工序变化和设备、人员指定的清除情况，再确认更新。</span></div></section>
      <section className="batch-band"><h3>工序概况</h3><div className="batch-readiness"><span>工序总数：{entity.operations.length}</span>
        <span>自制：{entity.operations.filter(op => op.source === 'internal').length}</span><span>外协：{entity.operations.filter(op => op.source === 'external').length}</span>
        <span>已完工：{entity.relationships.completed_count}</span><span>待补齐：{entity.relationships.gap_count}</span></div></section>
      <section className="batch-band"><h3>批次工序</h3><div className="wb-table-frame" data-sticky-head data-sticky-actions><table className="tbl wb-table" style={{ minWidth: 1060 }} aria-label="批次工序"><caption className="wb-visually-hidden">批次工序</caption><thead><tr>
        {['工序编码', '工序', '工种', '归属', '资源补充', '完工', '操作'].map((name, index) => <th key={name} scope="col" className={index === 0 ? 'wb-col-key' : index === 6 ? 'wb-col-actions' : undefined} style={{ width: [160, 80, 130, 80, 330, 100, 130][index] }}>{name}</th>)}</tr></thead><tbody>
        {entity.operations.map(op => <tr key={op.ref}><td className="wb-col-key">{op.business_code}</td><td>{op.sequence}</td><td>{op.label}</td><td>{op.source === 'internal' ? '自制' : op.source === 'external' ? '外协' : '未归类'}</td>
          <td>{op.source === 'internal' ? <><div>{op.resources.machine ? op.resources.machine.label : '设备未选'} · {op.resources.operator ? op.resources.operator.label : '人员未选'}</div><div>换型 {window.WorkbenchFormat.hours(op.setup_hours, ENTERED_HOURS)} / 单件 {window.WorkbenchFormat.hours(op.unit_hours, ENTERED_HOURS)}</div></>
            : <><div>{op.resources.supplier ? op.resources.supplier.label : '供应商未选'}</div><div>{op.external_group && op.external_group.merge_mode === 'merged' ? '整组 ' + window.WorkbenchFormat.number(op.external_group.total_days, ENTERED_DAYS) : '本序 ' + window.WorkbenchFormat.number(op.external_days, ENTERED_DAYS)} 天</div></>}<Issues issues={op.issues} /></td>
          <td>{op.completed ? '已完工' : op.status === 'processing' ? '加工中' : op.status === 'skipped' ? '已跳过' : '未完工'}</td>
          <td className="wb-col-actions"><Button icon="square-pen" aria-label="补充资料" reasonDisplay="tooltip" onClick={() => onOperation(entity, op)} disabled={disabled || !op.editable} reason={reason('operation_update')}>补充资料</Button></td></tr>)}
        {!entity.operations.length && <tr><td colSpan={7}><window.WorkbenchControls.EmptyState kind="empty" title="尚未生成工序" /></td></tr>}
      </tbody></table></div></section>
    </div>;
  }
  window.BatchDetail = BatchDetail;
})();
