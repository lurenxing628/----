(function () {
  'use strict';
  const B = window.APSBatchContract, S = window.APSResourceSession;
  const { Button, ErrorBox, Issues } = window.ResourceControls;
  function BatchDetail({ adapter, batchRef, revision, onBack, onEdit, onDelete, onOperation, onSync, disabled }) {
    const read = S.useQuery(async signal => B.detail(await adapter.detail('batch', batchRef, signal), batchRef), [adapter, batchRef, revision]);
    const [strict, setStrict] = React.useState(false), entity = read.result && read.result.data;
    if (!entity) return <section className="batch-band"><Button icon="arrow-left" onClick={onBack} disabled={disabled}>返回列表</Button>
      {read.loading && <p role="status">正在读取批次详情…</p>}<ErrorBox error={read.error} />{read.error && <Button icon="refresh-cw" onClick={read.reload}>重试读取详情</Button>}</section>;
    const reason = action => B.reason(entity.write_context, action, read.result.meta.source);
    return <div data-batch-detail={entity.ref}>
      <section className="batch-band"><div className="toolbar"><h2>批次详情 · {entity.business_code}</h2><span className="tb-spacer" />
        <Button icon="arrow-left" onClick={onBack} disabled={disabled}>返回列表</Button><Button icon="x" disabled={disabled} reason={reason('delete')} onClick={() => onDelete(entity)}>删除批次</Button></div>
        <div className="batch-readiness"><span>图号：{entity.relationships.part_no} · {entity.label}</span><span>数量：{B.label('', entity.fields.quantity)}</span>
          <span>状态：{B.label('status', entity.status)}</span><span>工序全部完成：{entity.all_operations_complete ? '是' : '否'}</span></div><Issues issues={entity.issues} /></section>
      <section className="batch-band"><div className="toolbar"><h3>① 批次基础信息</h3><span className="tb-spacer" /><Button icon="square-pen" onClick={() => onEdit(entity)} disabled={disabled} reason={reason('update')}>编辑基础信息</Button></div>
        <div className="batch-readiness"><span>交期：{B.label('', entity.fields.due_date)}</span><span>优先级：{B.label('priority', entity.fields.priority)}</span>
          <span>齐套显示：{B.label('ready_status', entity.fields.ready_status)}</span><span>齐套日期：{B.label('', entity.fields.ready_date)}</span><span>备注：{B.label('', entity.fields.remark)}</span></div>
        {entity.materials.count > 0 && <details><summary>物料齐套原记录 · {entity.materials.count} 项</summary><div className="card-scroll"><table className="tbl" style={{ minWidth: 640 }} aria-label="批次物料齐套"><thead><tr><th>物料</th><th>需求量</th><th>到料量</th><th>单位</th><th>齐套记录</th></tr></thead><tbody>
          {entity.materials.requirements.map(row => <tr key={row.material_ref}><td>{row.business_code} · {row.label}<Issues issues={row.issues} /></td><td>{B.label('', row.required_quantity)}</td><td>{B.label('', row.available_quantity)}</td><td>{row.unit || '未填写'}</td><td>{B.label('ready_status', row.ready_status)}</td></tr>)}
        </tbody></table></div></details>}</section>
      <section className="batch-band"><h3>② 按工艺模板同步工序</h3><label><input type="checkbox" checked={strict} disabled={disabled} onChange={event => setStrict(event.target.checked)} />资料不完整时停止刷新</label>
        <p>当前模板：{entity.template.origin === 'managed' ? entity.template.ready ? '已确认就绪' : '尚未完成三阶段确认' : '存量模板'}。</p>
        <Button icon="refresh-cw" disabled={disabled} reason={reason('sync_confirm')} onClick={() => onSync(entity, strict, read.result.meta.snapshot_ref)}>按最新工艺模板刷新本批次工序</Button></section>
      <section className="batch-band"><h3>③ 工序概况</h3><div className="batch-readiness"><span>工序总数：{entity.operations.length}</span>
        <span>自制：{entity.operations.filter(op => op.source === 'internal').length}</span><span>外协：{entity.operations.filter(op => op.source === 'external').length}</span>
        <span>已完工：{entity.relationships.completed_count}</span><span>待补齐：{entity.relationships.gap_count}</span></div></section>
      <section className="batch-band"><h3>④ 批次工序</h3><div className="card-scroll wb-table-frame"><table className="tbl" style={{ minWidth: 1060 }} aria-label="批次工序"><thead><tr>
        {['工序编码', '工序', '工种', '归属', '资源补充', '完工', '操作'].map((name, index) => <th key={name} style={{ width: [160, 80, 130, 80, 330, 100, 130][index] }}>{name}</th>)}</tr></thead><tbody>
        {entity.operations.map(op => <tr key={op.ref}><td>{op.business_code}</td><td>{op.sequence}</td><td>{op.label}</td><td>{op.source === 'internal' ? '自制' : op.source === 'external' ? '外协' : '未归类'}</td>
          <td>{op.source === 'internal' ? <><div>{op.resources.machine ? op.resources.machine.label : '设备未选'} · {op.resources.operator ? op.resources.operator.label : '人员未选'}</div><div>换型 {B.label('', op.setup_hours)} / 单件 {B.label('', op.unit_hours)} 小时</div></>
            : <><div>{op.resources.supplier ? op.resources.supplier.label : '供应商未选'}</div><div>{op.external_group && op.external_group.merge_mode === 'merged' ? '整组 ' + B.label('', op.external_group.total_days) : '本序 ' + B.label('', op.external_days)} 天</div></>}<Issues issues={op.issues} /></td>
          <td>{op.completed ? '已完工' : op.status === 'processing' ? '加工中' : op.status === 'skipped' ? '已跳过' : '未完工'}</td>
          <td><Button icon="square-pen" onClick={() => onOperation(entity, op)} disabled={disabled || !op.editable} reason={reason('operation_update')}>补充资料</Button></td></tr>)}
        {!entity.operations.length && <tr><td colSpan={7}>尚未生成工序</td></tr>}
      </tbody></table></div></section>
    </div>;
  }
  window.BatchDetail = BatchDetail;
})();
