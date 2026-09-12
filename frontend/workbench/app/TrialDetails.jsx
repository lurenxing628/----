(function () {
  'use strict';
  const U = window.TrialControls, C = window.TrialContract;
  const hoursBasis = value => ({ effective_processing_hours: '有效加工工时', calendar_days: '日历天', unknown: '工时依据不明' }[value] || '工时依据未识别');
  function References({ task }) {
    return <details className="tt-refs wb-ref"><summary>编号与原始依据</summary><dl>{[['任务', task.task_ref], ['行', task.row_ref], ['原任务', task.source_task_ref], ['原行', task.source_row_ref],
      ['工序', task.operation_ref], ['批次', task.batch_ref]].map(([label, ref]) => <React.Fragment key={label}><dt>{label}</dt><dd>{ref || '无（候选来源无正式任务引用）'}</dd></React.Fragment>)}</dl>
      <div>前序工序引用：{task.predecessor_operation_refs.join('、') || '无'}</div><div>原工时依据：<code>{task.hours.basis || '未记录'}</code></div></details>;
  }
  function Execution({ title, value }) {
    if (!value) return <div>{title}：未记录</div>;
    return <div><h4>{title}</h4><dl className="tt-facts">{[['目标量', value.target_quantity], ['已知完成量', value.known_completed_quantity],
      ['剩余量', value.remaining_quantity], ['执行状态', value.execution_state], ['数据质量', value.data_quality], ['目标依据', value.target_basis]].map(([label, v]) =>
        <React.Fragment key={label}><dt>{label}</dt><dd>{U.number(v)}</dd></React.Fragment>)}</dl></div>;
  }
  function Editor({ data, task, commands, onEditing, onRecheck, guardOwner, editorRevision }) {
    const [editing, setEditing] = React.useState(false), [form, setForm] = React.useState(null), [error, setError] = React.useState(null), [reviewed, setReviewed] = React.useState(false);
    const external = task.source === 'external';
    const initial = React.useRef(null);
    const dirty = editing && JSON.stringify(form) !== JSON.stringify(initial.current);
    window.WorkbenchGuards.useDirtyGuard({ owner: guardOwner, dirty, message: '试调工序的设备、人员或开工调整尚未保存。' });
    function close() { setEditing(false); onEditing(false); setError(null); }
    async function cancel() { if (!commands.busy && !commands.key && await window.WorkbenchGuards.confirmLeave({ owner: guardOwner })) close(); }
    function open() { const value = { machine_ref: external ? null : task.machine_ref, operator_ref: external ? null : task.operator_ref, start: task.start }; initial.current = value; setForm(value); setEditing(true); onEditing(true); setReviewed(true); }
    React.useEffect(() => { if (editing) setReviewed(false); }, [data]);
    React.useEffect(() => () => onEditing(false), []);
    React.useEffect(() => { close(); }, [editorRevision]);
    const editable = data.status === 'editing' && task.edit_context.can_change && data.write_context.capabilities['trial.change'] === true;
    async function submit(e) {
      e.preventDefault(); setError(null);
      const value = { ...form, start: form.start.length === 16 ? form.start + ':00' : form.start };
      try {
        C.check(C.time(value.start), '开工时间必须是有效的工厂本地时间。');
        C.check(external ? value.machine_ref === null && value.operator_ref === null : C.ref(value.machine_ref) && C.ref(value.operator_ref), '必须明确选择设备与人员。');
        const ok = await commands.execute({ action: 'change', draft_ref: data.draft_ref, input: { task_ref: task.task_ref, ...value } }, data.write_context.write_token);
        if (ok) close(); else setReviewed(false);
      } catch (error) { setError(error); }
    }
    return <><U.Issues rows={task.edit_context.blocked_reasons} />{!editing ? <U.Button icon="square-pen" disabled={!editable || commands.blocked} onClick={open}>调整此工序</U.Button> :
      <form onSubmit={submit} className="tt-editor"><h4>调整工序</h4>{['machine', 'operator'].map((kind, i) => <label key={kind}>{i ? '调整人员' : '调整设备'}
        <select aria-label={i ? '调整人员' : '调整设备'} value={form[kind + '_ref'] || ''} disabled={commands.busy || external} required={!external}
          onChange={e => setForm({ ...form, [kind + '_ref']: e.target.value || null })}>
          <option value="">{external ? '外协，无内部资源' : '请选择'}</option>{form[kind + '_ref'] && !data.resources[kind + 's'].some(r => r.ref === form[kind + '_ref']) && <option value={form[kind + '_ref']}>原资源（已不可读）</option>}
          {data.resources[kind + 's'].map(r => <option key={r.ref} value={r.ref} disabled={r.status !== 'active'}>{r.business_code} · {r.label || '名称未记录'}{r.status !== 'active' ? '（不可用）' : ''}</option>)}</select></label>)}
        <label>调整开工<input type="datetime-local" step="1" aria-label="调整开工" required value={form.start} disabled={commands.busy} onChange={e => setForm({ ...form, start: e.target.value })} /></label>
        <div className="tt-muted">原工时不变；完工由真实日历计算，前后序不自动移动。</div>
        {!external && !data.resources.authorizations.some(r => r.machine_ref === form.machine_ref && r.operator_ref === form.operator_ref) && <p className="tt-notice">当前设备与人员未登记操作授权，提交后以真实约束检查为准。</p>}
        <U.ErrorBox error={error} /><U.ErrorBox error={commands.error} />
        <label className="tt-check"><input type="checkbox" checked={reviewed} onChange={e => setReviewed(e.target.checked)} />已核对当前工序与保留输入</label>
        <div className="tt-tools"><U.Button icon="check" type="submit" disabled={!editable || !reviewed || commands.blocked}>保存调整</U.Button>
          <U.Button icon="x" disabled={commands.busy || !!commands.key} onClick={cancel}>取消编辑</U.Button><U.Button icon="refresh-cw" disabled={commands.busy || !!commands.key} onClick={onRecheck}>重读工序</U.Button></div>
      </form>}</>;
  }
  function Detail({ data, selected, commands, onSelect, onEditing, onRecheck, guardOwner, editorRevision }) {
    const task = data.tasks.find(t => t.task_ref === selected), name = window.TrialGantt.resourceNames(data);
    if (!task) return <aside className="tt-detail"><h3>工序详情</h3><div className="tt-empty">尚未选择工序</div></aside>;
    return <aside className="tt-detail" aria-label="工序详情"><div className="tt-heading"><h3>工序详情</h3><U.Button icon="x" aria-label="关闭工序详情" onClick={() => onSelect(null)} /></div>
      <h4>{task.batch_id} · {task.process_label}</h4><p>{task.part_no} · {task.part_name || '零件名称未记录'}</p>
      <Editor key={task.task_ref} {...{ data, task, commands, onEditing, onRecheck, guardOwner, editorRevision }} />
      <dl className="tt-facts">{[['分件', task.piece_id || '整批'], ['原目标量', U.number(task.quantity)], ['批次数量', U.number(task.batch_quantity)],
        ...(window.PointContract.isPoint(task) ? [['安排类型', '时间点'], ['本工序占用', '0 h · 不占用资源']] : []),
        ['优先级', { normal: '普通', urgent: '急件', critical: '特急' }[task.priority] || '未知'], ['交付截至日', task.due_date || '未记录'],
        ['来源', task.source === 'internal' ? '自制' : '外协'], ['当前设备', name(task.machine_ref)], ['当前人员', name(task.operator_ref)],
        ['当前开工', U.timeLabel(task.start)], ['当前完工', U.timeLabel(task.end)], ['原设备', name(task.original.machine_ref)], ['原人员', name(task.original.operator_ref)],
        ['原开工', U.timeLabel(task.original.start)], ['原完工', U.timeLabel(task.original.end)], ['原准备工时', U.number(task.hours.setup_hours)],
        ['原单件工时', U.number(task.hours.unit_hours)], ['原总工时', U.number(task.hours.total_hours)], ['工时依据', hoursBasis(task.hours.basis)],
        ...(task.source === 'external' ? [['原周期（天）', U.number(task.hours.days)]] : [])].map(([label, value]) =>
          <React.Fragment key={label}><dt>{label}</dt><dd>{value}</dd></React.Fragment>)}</dl>
      <div className="tt-tools">{task.predecessor_refs.map(ref => {
        const t = data.tasks.find(t => t.task_ref === ref);
        const piece = typeof t.piece_id === 'string' && t.piece_id.trim() ? '分件 ' + t.piece_id :
          t.piece_id === null && !t.data_gaps.some(g => g.field === 'piece_id') ? '共同工序' : '分件未记录';
        const label = '前序 ' + piece + ' · ' + t.process_label + ' ' + t.sequence;
        return <U.Button key={ref} icon="chevron-left" title={label} aria-label={label} onClick={() => onSelect(ref)}
          style={{ minWidth: 0, maxWidth: '100%', height: 'auto', whiteSpace: 'normal', textAlign: 'left' }}>
          <span style={{ minWidth: 0, overflowWrap: 'anywhere', wordBreak: 'break-word' }}>{label}</span></U.Button>;
      })}</div>
      <section><h4>工序约束</h4>{!task.issues.length && <p className="tt-muted">此工序未报告单项问题，仍须核对整体约束。</p>}<U.Issues rows={task.issues} onSelect={onSelect} /><U.Issues rows={task.data_gaps} /></section>
      <details><summary>执行依据</summary><Execution title="创建时执行投影" value={task.execution_at_creation} /><Execution title="本次读取执行投影" value={task.execution} /></details>
      <References task={task} />
    </aside>;
  }
  window.TrialDetails = Detail;
})();
