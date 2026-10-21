(function () {
  'use strict';
  const T = window.WorkbenchTerms, F = window.WorkbenchFormat;
  const amount = (value, suffix = '') => value == null ? '未记录' : (typeof value === 'string' ? F.integerText(value) : F.number(value, { digits: 3, trim: true })) + suffix;
  function hours(value, state) {
    if (value !== null) return amount(value, ' 小时');
    if (state === 'not_applicable') return '外协按周期';
    return '待确认';
  }
  function Standard({ value }) {
    return <details className="rd-effort-record"><summary>工序标准记录</summary><dl>
      <div><dt>标准准备</dt><dd>{amount(value.setup_standard_hours, ' 小时')}</dd></div><div><dt>{T.operation_effort_labels.unit_standard_hours}</dt><dd>{amount(value.unit_standard_hours, ' 小时')}</dd></div>
      <div><dt>{T.operation_effort_labels.standard_total_hours}</dt><dd>{value.state === 'not_applicable' ? '外协按周期' : amount(value.standard_total_hours, ' 小时')}</dd></div>
      <div><dt>记录数量 / 剩余数量</dt><dd>{amount(value.target_quantity)} / {amount(value.remaining_quantity)}</dd></div>
    </dl>{value.reason && <small>{value.reason.message}</small>}</details>;
  }
  function Source({ value, showHours = false }) {
    const source = value.evidence_source;
    const labels = { run: '排产记录', candidate: '候选记录', trial: '试调记录', scenario: '试调记录', official: '正式计划记录', admission_official: '正式计划记录', missing: '工时需求未保存' };
    return <details className="rd-effort-record"><summary>需求依据与数量</summary><dl>
      <div><dt>工时来源</dt><dd>{value.effort_basis ? T.effort_basis_labels[value.effort_basis] : '工时需求未保存'}</dd></div>
      <div><dt>{T.operation_effort_labels.requirement_role}</dt><dd>{T.effort_roles[value.requirement_role] || '安排方式未保存'}</dd></div>
      <div><dt>{T.operation_effort_labels.target_quantity}</dt><dd>{amount(value.target_quantity)} · {T.effort_quantity_bases[value.quantity_basis] || '数量依据未保存'}</dd></div>
      <div><dt>{T.operation_effort_labels.execution_target_quantity}</dt><dd>{amount(value.execution_target_quantity)} · {T.effort_quantity_bases[value.execution_quantity_basis] || '报工数量依据未记录'}</dd></div>
      <div><dt>{T.operation_effort_labels.remaining_quantity}</dt><dd>{amount(value.remaining_quantity)}</dd></div>
      <div><dt>保存来源</dt><dd>{source ? labels[source.kind] || '已保存来源' : '工时来源缺失'}{source && source.version != null && ' · 第 ' + source.version + ' 版'}</dd></div>
      {showHours && <div><dt>{T.operation_effort_labels.setup_state}</dt><dd>{T.setup_states[value.setup_state]}</dd></div>}
    </dl>{showHours && <><span>准备 {value.setup_standard_hours === null ? '—' : hours(value.setup_standard_hours, value.state)} · 加工 {value.processing_standard_hours === null ? '—' : hours(value.processing_standard_hours, value.state)}</span>
      <small>{T.operation_effort_labels.required_standard_hours} {value.required_standard_hours === null ? '—' : hours(value.required_standard_hours, value.state)}</small></>}{source && <window.WorkbenchReference entries={{ '源排产记录': source.run_ref, '源候选': source.candidate_ref, '源试调': source.scenario_ref, '源正式计划': source.plan_ref }} />}</details>;
  }
  function Effort({ value, absent = false, showStandard = true, showMachines = false }) {
    if (absent) return <span className="rc-muted">比较基准缺失</span>;
    if (!value) return <span className="rc-muted">这份记录未保存准备与加工工时。</span>;
    const C = window.RunCandidateControls;
    const keys = ['setup_standard_hours', 'processing_standard_hours', 'required_standard_hours'];
    const external = value.state === 'not_applicable', missing = !external && keys.some(key => value[key] === null), known = keys.filter(key => value[key] !== null);
    const notConstructed = value.data_gaps.some(gap => gap.code === 'runtime_requirement_not_constructed');
    const missingText = (known.length ? '部分工时需求' : '工时需求') + (notConstructed ? '未生成' : value.effort_basis === 'runtime_requirement_v1' ? '待确认' : '未保存');
    return <div className="rd-operation-effort"><strong>{T.preparation_allocations[value.allocation_state]}{missing && '，' + missingText + '。'}</strong>
      {!external && (missing ? known.length > 0 && <span>{known.map(key => T.operation_effort_labels[key] + ' ' + hours(value[key], value.state)).join(' · ')}</span> : <><span>准备 {hours(value.setup_standard_hours, value.state)} · 加工 {hours(value.processing_standard_hours, value.state)}</span>
        <small>{T.operation_effort_labels.required_standard_hours} {hours(value.required_standard_hours, value.state)}</small><small>{T.setup_states[value.setup_state]}</small></>)}
      {showMachines && <small>{value.machine_basis === 'admission_requirement' ? '所需设备' : value.machine_basis === 'saved_arrangement' ? '安排设备' : '设备'} {value.machines.length ? value.machines.map(row => row.label || T.name_missing).join(' / ') : '未记录'}</small>}
      {value.source === 'external' && <><span>{T.operation_effort_labels.external_cycle_days} {amount(value.external_cycle_days)}</span><small>外协组 {value.external_group_id || '未记录'} · {{ merged: '合并外协', separate: '分别外协' }[value.external_merge_mode] || value.external_merge_mode || '合并规则未记录'}</small></>}
      <Source value={value} showHours={missing || external} />{showStandard && <Standard value={value.standard} />}<C.Reasons rows={value.data_gaps} />
    </div>;
  }
  function Detail({ value, compact }) {
    const Tag = compact ? 'details' : 'section', Heading = compact ? 'summary' : 'h4';
    return <Tag className={compact ? 'wb-gantt-detail-section' : 'rd-effort-detail'}><Heading>准备与加工需求</Heading><div className={compact ? 'wb-gantt-detail-section-body' : undefined}><Effort value={value} /></div></Tag>;
  }
  window.RunOperationEffort = { Effort, Detail, Standard, hours, amount };
})();
