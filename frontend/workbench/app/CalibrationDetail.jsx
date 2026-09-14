(function () {
  'use strict';
  const { Button, ErrorBox, Page, text, hours, writeReason } = window.CalibrationControls;
  const fields = [['actual_start', '实际开工'], ['actual_end', '本次结束'], ['completed_quantity', '完成数量'], ['effective_processing_hours', '有效加工工时（小时）'], ['remark', '备注']];
  function Refs({ rows }) {
    // 编号、版本号一律进折叠的「编号」区，正文只留人看得懂的内容。
    const visible = rows.filter(([label]) => !/(编号|版本)$/.test(label));
    const refs = Object.fromEntries(rows.filter(([label]) => /(编号|版本)$/.test(label)));
    return <><dl className="ca-refs">{visible.map(([label, value]) => <React.Fragment key={label}><dt>{label}</dt><dd>{['实际开工', '本次结束', '登记时间', '生成时间', '数据截至'].includes(label) && value ? window.WorkbenchFormat.dateTime(value, { seconds: true }) : text(value)}</dd></React.Fragment>)}</dl>
      {!!Object.keys(refs).length && <window.WorkbenchReference entries={refs} />}</>;
  }
  function Report({ report }) {
    return <details><summary>报工 · {report.actual_end ? window.WorkbenchFormat.dateTime(report.actual_end) : '结束时间未知'} · 数量 {text(report.completed_quantity)} · {hours(report.effective_processing_hours, '工时未知')}</summary>
      <Refs rows={[["单号", report.report_no], ["记录编号", report.report_ref], ["记录人", report.local_operator], ["经办人", report.declared_operator],
        ["登记时间", report.recorded_at], ["原计划记录编号", report.recorded_against_plan_ref], ["原任务记录编号", report.recorded_against_task_ref], ["当前版本编号", report.revision_ref]]} />
      <Refs rows={fields.map(([key, label]) => [label, report[key]])} /><window.WorkbenchReference entries={{ '设备编号': report.actual_machine_ref, '人员编号': report.actual_operator_ref, '报工来源': report.source }} />
      <h4>登记与更正记录（{report.correction_history.length} 条）</h4>
      {report.correction_history.map(revision => <details key={revision.revision_ref}><summary>{window.WorkbenchTerms.report_actions[revision.action] || revision.action} · {window.WorkbenchFormat.dateTime(revision.recorded_at)}</summary>
        <Refs rows={[["更正原因", revision.reason || '无'], ["记录人", revision.local_operator], ["经办人", revision.declared_operator], ["版本编号", revision.revision_ref], ["结果编号", revision.receipt_ref]]} />
        <div className="ca-table-scroll wb-table-frame"><table className="ca-table" aria-label="更正前后值"><caption className="wb-visually-hidden">逐次报工更正前后的值</caption><thead><tr><th scope="col">项目</th><th scope="col">更正前</th><th scope="col">更正后</th></tr></thead><tbody>{fields.map(([key, label]) =>
          <tr key={key}><th scope="row">{label}</th><td>{revision.before === null ? '新增，无原值' : text(revision.before && revision.before[key])}</td><td>{text(revision.after && revision.after[key])}</td></tr>)}</tbody></table></div>
        <window.WorkbenchReference entries={{ '原设备编号': revision.before && revision.before.actual_machine_ref, '新设备编号': revision.after && revision.after.actual_machine_ref,
          '原人员编号': revision.before && revision.before.actual_operator_ref, '新人员编号': revision.after && revision.after.actual_operator_ref }} />
      </details>)}
    </details>;
  }
  function Sample({ sample, opened, onOpen }) {
    const state = sample.selected ? '可用记录' : sample.template_operation_ref === null ? '未关联核对' : '已关联但剔除';
    return <details className="ca-evidence ca-sample" open={opened} data-sample-ref={sample.sample_ref} onToggle={event => {
      if (event.target === event.currentTarget && event.currentTarget.open !== opened) onOpen(event.currentTarget.open ? sample.sample_ref : null);
    }}><summary>{state} · {sample.batch_code} · {sample.confirmed_finish ? window.WorkbenchFormat.dateTime(sample.confirmed_finish) : '完工时间未知'} · 已知数量 {text(sample.completed_quantity)}
      {sample.unknown_record_count > 0 && ' · ' + sample.unknown_record_count + ' 条数量未知'} · {hours(sample.effective_processing_hours, '工时未知')}</summary>
      {opened && <><Refs rows={[["批次", sample.batch_code], ["工序单号", sample.operation_code], ["完工记录编号", sample.execution_operation_ref], ["来源模板编号", sample.template_operation_ref],
        ["来源模板版本", sample.template_revision], ["来源证据编号", sample.lineage_evidence_ref], ["记录版本", sample.sample_revision]]} />
        <p>单件工时：{hours(sample.unit_hours, '未知')}；数量未知记录 {sample.unknown_record_count} 条。</p>
        <ul>{sample.exclusion_reasons.map((reason, index) => <li key={reason.code + ':' + index}>{reason.message}</li>)}</ul>
        <h4>逐次报工（{sample.reports.length} 条）</h4>{sample.reports.map(report => <Report key={report.report_ref} report={report} />)}
        <h4>历史现场记录（{sample.legacy_facts.length} 条）</h4>{sample.legacy_facts.map((fact, index) => <details key={fact.legacy_fact_ref || index}><summary>历史现场记录 {index + 1}</summary><window.ReportEvidence.StructuredFacts value={fact} /></details>)}
        {!!sample.data_gaps.length && <><h4>数据缺口</h4><ul>{sample.data_gaps.map((gap, index) => <li key={index}>{gap.message || <window.ReportEvidence.StructuredFacts value={gap} />}</li>)}</ul></>}
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
      {!samples.length && <window.WorkbenchListControls.EmptyState kind="empty" title="暂无记录" />}
      {samples.slice((paging.page - 1) * paging.size, paging.page * paging.size).map(sample => <Sample key={sample.sample_ref} sample={sample} opened={sampleRef === sample.sample_ref} onOpen={onSample} />)}
      {samples.length > 10 && <Page label={label} page={{ number: paging.page, size: paging.size, total: samples.length, total_pages: Math.ceil(samples.length / paging.size) }} onChange={patch => setPaging(old => ({ ...old, ...patch }))} />}
    </section>;
  }
  function Detail({ result, busy, error, selected, sampleRef, onSample, onClose, onRefresh, stale }) {
    const data = result && result.data, row = data && data.suggestion;
    const groups = React.useMemo(() => data ? [
      ['可用记录', 'selected', data.suggestion.sample_refs.map(ref => data.samples.find(sample => sample.sample_ref === ref))],
      ['已关联但剔除', 'excluded', data.samples.filter(sample => sample.template_operation_ref !== null && !sample.selected)],
      ['同零件未关联核对', 'unbound', data.samples.filter(sample => sample.template_operation_ref === null)]
    ] : [], [data]);
    const actions = <div className="ca-actions">
        {!window.CalibrationAdoptionAction && <><Button icon="check" reason={writeReason}>采用</Button><Button icon="lock" reason={writeReason}>锁定</Button></>}
        </div>;
    return <window.WorkbenchDetailPanel className="ca-detail" detailKey={selected} title={row ? row.part_no + ' · ' + row.sequence + ' ' + row.operation_label : '已选校准记录'}
      subtitle="校准详情" actions={actions} onClose={onClose}>
      {!row && <Refs rows={[["已选记录编号", selected], ["已选完工记录编号", sampleRef]]} />}
      <ErrorBox error={error} />{stale && <p className="ca-note">数据已更新，请点「刷新所选记录」后重试。已选记录和完工记录来源已保留，不会自动换到其他记录。</p>}
      {(error || stale) && <Button icon="refresh-cw" onClick={onRefresh}>刷新所选记录</Button>}
      {busy && <window.WorkbenchListControls.EmptyState kind="loading" title="正在读取完工记录来源" />}
      {row && <><dl className="ca-facts"><div><dt>原定额</dt><dd>{hours(row.old_unit_hours)} / 件</dd></div><div><dt>建议定额</dt><dd>{hours(row.suggested_unit_hours, '暂无建议')}</dd></div>
        <div><dt>可用记录数</dt><dd>{row.sample_count} 条</dd></div><div><dt>核对记录总数</dt><dd>{row.candidate_count} 条</dd></div></dl>
        {row.suggested_unit_hours === null && <p className="ca-note">同模板、同版本的可用完工记录不足 5 条，暂无建议。</p>}
        <details className="ca-evidence"><summary>定额记录与计算依据</summary>
          <Refs rows={[["模板工序编号", row.template_operation_ref], ["模板版本", row.template_revision], ["模板数据版本", row.template_snapshot], ["零件记录编号", row.part_ref],
            ["计算方法编号", row.method_version], ["生成时间", row.generated_at], ["数据截至", row.as_of], ["数据版本编号", row.snapshot_ref]]} />
          <p>取最近 20 条来源与版本已确认的整道完工记录，至少 5 条才生成中位数建议。原定额为 0 或未填写时都不算相对偏差。</p>
          <ul>{row.exclusion_reasons.map((reason, index) => <li key={reason.code + ':' + index}>{reason.message}（{reason.count} 条记录）</li>)}</ul>
        </details>
        <h3>完工记录与来源核对</h3>
        {sampleRef && !data.samples.some(sample => sample.sample_ref === sampleRef) && <><p className="ca-note">原来选中的完工记录已不在结果里，没有改选其他来源。</p><window.WorkbenchReference value={sampleRef} label="原选完工记录编号" /></>}
        {groups.map(([label, kind, samples]) => <SampleGroup key={selected + kind} label={label} kind={kind} samples={samples} sampleRef={sampleRef} onSample={onSample} />)}
      </>}
    </window.WorkbenchDetailPanel>;
  }
  window.CalibrationDetail = Detail;
})();
