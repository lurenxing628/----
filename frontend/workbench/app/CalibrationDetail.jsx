(function () {
  'use strict';
  const { Button, ErrorBox, Page, text, hours, writeReason } = window.CalibrationControls;
  const fields = [['actual_start', '实际开工'], ['actual_end', '本次结束'], ['completed_quantity', '完成数量'], ['effective_processing_hours', '有效加工小时'],
    ['actual_machine_ref', '设备记录编号'], ['actual_operator_ref', '人员记录编号'], ['remark', '备注']];
  function Refs({ rows }) { return <dl className="ca-refs">{rows.map(([label, value]) => <React.Fragment key={label}><dt>{label}</dt><dd>{text(value)}</dd></React.Fragment>)}</dl>; }
  function Report({ report }) {
    return <details><summary>报工 · {report.actual_end || '结束时间未知'} · 数量 {text(report.completed_quantity)} · {hours(report.effective_processing_hours, '工时未知')}</summary>
      <Refs rows={[["单号", report.report_no], ["记录编号", report.report_ref], ["来源", report.source], ["登记人员", report.local_operator], ["声明人员", report.declared_operator],
        ["登记时间", report.recorded_at], ["原计划记录编号", report.recorded_against_plan_ref], ["原任务记录编号", report.recorded_against_task_ref], ["当前修订编号", report.revision_ref]]} />
      <Refs rows={fields.map(([key, label]) => [label, report[key]])} />
      <h4>登记与更正记录（{report.correction_history.length} 条）</h4>
      {report.correction_history.map(revision => <details key={revision.revision_ref}><summary>{({ create: '首次登记', supplement: '补录', correct: '更正' })[revision.action] || revision.action} · {revision.recorded_at}</summary>
        <Refs rows={[["更正原因", revision.reason || '无'], ["登记人员", revision.local_operator], ["声明人员", revision.declared_operator], ["修订编号", revision.revision_ref], ["回执编号", revision.receipt_ref]]} />
        <table className="ca-table" aria-label="更正前后值"><thead><tr><th>项目</th><th>更正前</th><th>更正后</th></tr></thead><tbody>{fields.map(([key, label]) =>
          <tr key={key}><td>{label}</td><td>{revision.before === null ? '首次登记，无前值' : text(revision.before && revision.before[key])}</td><td>{text(revision.after && revision.after[key])}</td></tr>)}</tbody></table>
      </details>)}
    </details>;
  }
  function Sample({ sample, opened, onOpen }) {
    const state = sample.selected ? '有效样本' : sample.template_operation_ref === null ? '未关联核对' : '已关联但剔除';
    return <details className="ca-evidence ca-sample" open={opened} data-sample-ref={sample.sample_ref} onToggle={event => {
      if (event.target === event.currentTarget && event.currentTarget.open !== opened) onOpen(event.currentTarget.open ? sample.sample_ref : null);
    }}><summary>{state} · {sample.batch_code} · {sample.confirmed_finish || '完工时间未知'} · 已知数量 {text(sample.completed_quantity)}
      {sample.unknown_record_count > 0 && ' · ' + sample.unknown_record_count + ' 条数量未知'} · {hours(sample.effective_processing_hours, '工时未知')}</summary>
      {opened && <><Refs rows={[["批次", sample.batch_code], ["工序单号", sample.operation_code], ["实例记录编号", sample.execution_operation_ref], ["来源模板编号", sample.template_operation_ref],
        ["来源模板修订", sample.template_revision], ["来源证据编号", sample.lineage_evidence_ref], ["样本修订", sample.sample_revision]]} />
        <p>单件工时：{hours(sample.unit_hours, '未知')}；数量未知记录 {sample.unknown_record_count} 条。</p>
        <ul>{sample.exclusion_reasons.map((reason, index) => <li key={reason.code + ':' + index}>{reason.message}</li>)}</ul>
        <h4>逐次报工（{sample.reports.length} 条）</h4>{sample.reports.map(report => <Report key={report.report_ref} report={report} />)}
        <h4>旧现场事实（{sample.legacy_facts.length} 条）</h4>{sample.legacy_facts.map((fact, index) => <details key={fact.legacy_fact_ref || index}><summary>旧现场记录 {index + 1}</summary><pre>{JSON.stringify(fact, null, 2)}</pre></details>)}
        {!!sample.data_gaps.length && <><h4>数据缺口</h4><ul>{sample.data_gaps.map((gap, index) => <li key={index}>{gap.message || JSON.stringify(gap)}</li>)}</ul></>}
      </>}
    </details>;
  }
  function SampleGroup({ label, kind, samples, sampleRef, onSample }) {
    const [paging, setPaging] = React.useState({ page: 1, size: 10 });
    React.useEffect(() => {
      const index = samples.findIndex(sample => sample.sample_ref === sampleRef);
      setPaging(old => ({ ...old, page: index >= 0 ? Math.floor(index / old.size) + 1 : Math.min(old.page, Math.max(1, Math.ceil(samples.length / old.size))) }));
    }, [samples, sampleRef]);
    return <section className="ca-sample-group" aria-label={label} data-sample-group={kind}><h4>{label}（{samples.length}）</h4>
      {!samples.length && <p className="ca-muted">暂无记录。</p>}
      {samples.slice((paging.page - 1) * paging.size, paging.page * paging.size).map(sample => <Sample key={sample.sample_ref} sample={sample} opened={sampleRef === sample.sample_ref} onOpen={onSample} />)}
      {samples.length > 10 && <Page label={label} page={{ number: paging.page, size: paging.size, total: samples.length, total_pages: Math.ceil(samples.length / paging.size) }} onChange={patch => setPaging(old => ({ ...old, ...patch }))} />}
    </section>;
  }
  function Detail({ result, busy, error, selected, sampleRef, onSample, onClose, onRefresh, stale }) {
    const data = result && result.data, row = data && data.suggestion, root = React.useRef(null);
    const groups = React.useMemo(() => data ? [
      ['有效样本', 'selected', data.suggestion.sample_refs.map(ref => data.samples.find(sample => sample.sample_ref === ref))],
      ['已关联但剔除', 'excluded', data.samples.filter(sample => sample.template_operation_ref !== null && !sample.selected)],
      ['同零件未关联核对', 'unbound', data.samples.filter(sample => sample.template_operation_ref === null)]
    ] : [], [data]);
    React.useEffect(() => {
      const previous = document.activeElement; root.current.focus({ preventScroll: true }); root.current.scrollIntoView({ block: 'start' });
      return () => { if (previous && previous.isConnected) previous.focus({ preventScroll: true }); };
    }, [selected]);
    return <section className="ca-detail" aria-label="校准详情" tabIndex={-1} ref={root} onKeyDown={event => {
      if (event.key === 'Escape' && !event.defaultPrevented) { event.stopPropagation(); onClose(); }
    }}>
      <div className="ca-heading"><h3>{row ? row.part_no + ' · ' + row.sequence + ' ' + row.operation_label : '已选校准记录'}</h3><div className="ca-actions">
        {!window.CalibrationAdoptionAction && <><Button icon="check" reason={writeReason}>采用</Button><Button icon="lock" reason={writeReason}>锁定</Button></>}
        <Button icon="x" aria-label="关闭校准详情" onClick={onClose} /></div></div>
      {!row && <Refs rows={[["已选记录编号", selected], ["已选实例编号", sampleRef]]} />}
      <ErrorBox error={error} />{stale && <p className="ca-note">前后快照不一致，请明确刷新。已选记录和样本来源保留，不会自动换到其他记录。</p>}
      {(error || stale) && <Button icon="refresh-cw" onClick={onRefresh}>刷新所选记录</Button>}
      {busy && <p role="status">正在读取样本来源...</p>}
      {row && <><dl className="ca-facts"><div><dt>原定额</dt><dd>{hours(row.old_unit_hours)} / 件</dd></div><div><dt>建议定额</dt><dd>{hours(row.suggested_unit_hours, '暂无建议')}</dd></div>
        <div><dt>有效样本</dt><dd>{row.sample_count} 个</dd></div><div><dt>核对实例总数</dt><dd>{row.candidate_count} 个</dd></div></dl>
        {row.suggested_unit_hours === null && <p className="ca-note">同模板、同修订有效样本不足 5 个，暂无建议。</p>}
        <details className="ca-evidence"><summary>定额记录与计算依据</summary>
          <Refs rows={[["模板工序编号", row.template_operation_ref], ["模板修订", row.template_revision], ["模板快照", row.template_snapshot], ["零件记录编号", row.part_ref],
            ["计算方法", row.method_version], ["生成时间", row.generated_at], ["数据截至", row.as_of], ["范围快照", row.snapshot_ref]]} />
          <p>取最近 20 个来源与修订已确认的整道完工实例，至少 5 个才生成中位数建议。原定额为 0 和未提供时均不计算相对偏差。</p>
          <ul>{row.exclusion_reasons.map((reason, index) => <li key={reason.code + ':' + index}>{reason.message}（{reason.count} 个实例）</li>)}</ul>
        </details>
        <h3>样本与来源核对</h3>
        {sampleRef && !data.samples.some(sample => sample.sample_ref === sampleRef) && <p className="ca-note">原选实例已不在返回结果中，未选择其他来源。记录编号：{sampleRef}</p>}
        {groups.map(([label, kind, samples]) => <SampleGroup key={selected + kind} label={label} kind={kind} samples={samples} sampleRef={sampleRef} onSample={onSample} />)}
      </>}
    </section>;
  }
  window.CalibrationDetail = Detail;
})();
