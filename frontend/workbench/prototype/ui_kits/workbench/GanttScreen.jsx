const RUN_SETTINGS = { start: '2026-05-23', end: '2026-05-29', picked: null, readyCheck: true, autoFill: true, lockStarted: true };
function PreflightCheck({ onNav }) {
  const { Panel } = window.APSDesignSystem_edbc5d, { ControlButton: Button, MetricStrip, Metric } = window.APSWorkbenchUI;
  const { StrictSeg, DateInput } = window.BD, batchApi = window.APSBatchDraft;
  const [settings, setSettings] = React.useState(() => ({ ...RUN_SETTINGS })), [ran, setRan] = React.useState(false), [expanded, setExpanded] = React.useState(false);
  const [, refresh] = React.useReducer(n => n + 1, 0);
  React.useEffect(() => batchApi.subscribe(() => { refresh(); setRan(false); }), []);
  const change = patch => { Object.assign(RUN_SETTINGS, patch); setSettings({ ...RUN_SETTINGS }); setRan(false); };
  const batches = batchApi.getBatches().filter(b => !['completed', 'cancelled'].includes(b.status));
  const result = window.APSPreflight.evaluate(batches, settings, batchApi);
  const unready = result.rows.filter(b => b.ready_status !== 'yes');
  const focus = (kind, ids) => onNav('batches', { focus: kind, batchIds: [...new Set(ids)], returnTo: 'run' });
  const toggle = id => { const ids = settings.picked || batches.map(b => b.batch_id); change({ picked: ids.includes(id) ? ids.filter(x => x !== id) : ids.concat(id) }); };
  return <Panel className="wb-page-panel pw-run" title="排产前检查" description="批次库样例 · 2026-05 · 不与 09 月方案试调样例混用">
    <div className="run-scope"><label>计划窗口</label><DateInput value={settings.start} onChange={value => change({ start: value })} /><span>至</span><DateInput value={settings.end} onChange={value => change({ end: value })} /><span className="muted">{result.rows.length} 批 · {result.operations} 道待排工序</span><Button size="sm" onClick={() => setExpanded(!expanded)}>{expanded ? '收起范围' : '选择批次'}</Button></div>
    {expanded && <div className="run-picker"><div className="pw-actions"><Button size="sm" onClick={() => change({ picked: null })}>全部待排</Button><Button size="sm" onClick={() => change({ picked: batches.filter(b => b.ready_status === 'yes').map(b => b.batch_id) })}>仅已齐套</Button><Button size="sm" onClick={() => change({ picked: [] })}>清空</Button></div>{batches.map(b => <label key={b.batch_id}><input type="checkbox" checked={!settings.picked || settings.picked.includes(b.batch_id)} onChange={() => toggle(b.batch_id)} /><strong>{b.batch_id}</strong><span>{window.BD.partName(b.part_no)}</span><span>{b.ops.length} 道工序</span><span className="muted">{b.ready_status === 'yes' ? '已齐套' : '未齐套'}</span></label>)}</div>}
    <MetricStrip><Metric label="范围内待排" value={result.operations} unit="道" helper={result.rows.length + ' 个选中批次'} /><Metric label="可进入排产" value={result.eligible} unit="道" helper={result.autoAssign + ' 道需自动分配；非排产结果'} /><Metric label="跳过工序" value={result.skipped.reduce((n, item) => n + item.count, 0)} unit="道" helper="未齐套或已设置缺资源暂不排" /><Metric label="需处理" value={result.invalid.length} unit="道" tone={result.invalid.length ? 'warning' : 'neutral'} helper="工时、工种或外协资料缺项" /></MetricStrip>
    <div className="run-body"><section className="run-rules" aria-labelledby="run-rules-title"><h3 id="run-rules-title">本次排产规则</h3><div className="run-rule-list">{[
      ['readyCheck', '齐套检查', '未齐套批次不进入本次排产。', '开启', '关闭'],
      ['autoFill', '缺资源工序', '自动分配仅处理设备 / 人员；暂不排只剔除缺资源工序。', '自动分配', '暂不排'],
      ['lockStarted', '已完成工序', '保留已有完成状态，不重新安排已完成工序。', '锁定', '可重排']
    ].map(([key, label, note, on, off]) => <div className="run-rule" data-rule={key} key={key}><div className="run-rule-copy"><strong>{label}</strong><p>{note}</p></div><StrictSeg checked={settings[key]} onChange={value => change({ [key]: value })} onText={on} offText={off} ariaLabel={label} /></div>)}</div><p className="pw-footnote">批次库未提供逐工序“已开工”字段，此处仅锁定已完成工序，不推断开工状态。</p></section>
      <section className="run-readiness" aria-labelledby="run-readiness-title"><h3 id="run-readiness-title">就绪检查</h3><div className="run-checks"><div className="run-check"><div><strong>设备 / 人员</strong><p>{result.missing.length} 道待补，{settings.autoFill ? '进入自动分配检查' : '本次跳过'}。</p></div><Button size="sm" disabled={!result.missing.length} onClick={() => focus('gaps', result.missing.map(r => r.batch))}>去补齐</Button></div>
      <div className="run-check"><div><strong>齐套状态</strong><p>{unready.length} 批未齐套，{settings.readyCheck ? '本次跳过' : '本次不校验齐套'}。</p></div><Button size="sm" disabled={!unready.length} onClick={() => focus('unready', unready.map(b => b.batch_id))}>查看批次</Button></div>
      <div className="run-check"><div><strong>工时 / 工艺 / 外协</strong><p>{result.invalid.length} 道需补资料，{result.noRoute.length} 批尚未生成工艺。</p></div><Button size="sm" disabled={!result.invalid.length && !result.noRoute.length} onClick={() => focus('gaps', result.invalid.map(r => r.batch).concat(result.noRoute.map(r => r.batch_id)))}>处理缺项</Button></div>
      <div className="run-check"><div><strong>日历与产能</strong><p>尚未调用引擎校验，不以页面就绪状态替代排产可行性。</p></div></div></div></section></div>
    {!!result.skipped.length && <details className="run-skipped"><summary>本次不排入 · {result.skipped.length} 项</summary>{result.skipped.map((r, i) => <div key={i}><span>{r.batch}</span><span>{r.reason}</span><span>{r.count} 道</span></div>)}</details>}
    {!!result.blocked.length && <div className="tr-error" role="alert">{result.blocked.map(text => <p key={text}>{text}</p>)}</div>}
    {ran && <div className="tr-notice" role="status">就绪检查完成：{result.included.length} 批 / {result.eligible} 道具备提交条件。原型未接排产引擎，未生成新方案、未写入计划。</div>}
    <div className="bd-form-footer"><span className="pw-footnote">修改批次资料后，检查结果会同步更新。</span><Button onClick={() => onNav('analysis')}>查看独立方案样例</Button><Button variant="primary" disabled={result.blocked.length > 0} onClick={() => setRan(true)}>开始排产检查</Button></div>
  </Panel>;
}
function GanttScreen({ mode, onNav, initialContext }) {
  return mode === 'run' ? <PreflightCheck onNav={onNav} /> : <GanttBoard onNav={onNav} initialContext={initialContext} />;
}
window.GanttScreen = GanttScreen;
