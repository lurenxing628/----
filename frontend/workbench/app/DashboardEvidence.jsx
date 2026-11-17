import React from './shared/runtime/react.js';
import F from './WorkbenchFormat.js';
import T from './WorkbenchTerms.js';
import { Issues } from './ResourceControls.jsx';
import { WorkbenchReference } from './WorkbenchReferences.jsx';
import OutsourcingControls from './OutsourcingControls.jsx';
import { labels as receiptLabels } from './OutsourcingContract.js';

// 证据项分两张表，生产方见下方词表说明：labels 是正文可见的项；referenceLabels 是只进折叠编号区的项（编号、诊断依据、
// 内部码和外协回执原始记录），这些项的值照原样保留在编号区。处置历史保存的是当时的来源，可能带现在已不输出的项，
// 两张表都查不到时按“其他记录项”依次编号，不显示原键名。
const labels = {
  kind: '来源类型', evaluation: '交付评估', requirements: '物料需求',
  label: '名称', business_code: '业务编号', required_quantity: '需求量', available_quantity: '可用量', unit: '单位',
  ready_status: '齐套状态', due_date: '交期', planned_finish: T.arrangement_labels.planned_finish, delay_days: '预计超期天数',
  due_state: '交期状态', due_issue: '交期问题', completion_state: T.arrangement_labels.status, partial_planned_finish: T.arrangement_labels.partial_finish,
  operation_count: '全部工序', scheduled_operation_count: '已安排工序', unscheduled_operation_count: '未安排工序',
  deferred_operation_count: T.arrangement_labels.deferred, ordinary_unscheduled_operation_count: T.arrangement_labels.other_unplanned,
  schedule_complete: T.arrangement_labels.complete, is_overdue: '是否超期', delay_hours: '预计超期小时',
  planned_start: '正式安排开始', planned_end: '正式安排结束', first_actual_start: '首次实际开始', confirmed_finish: '确认完工时间',
  finish_deviation_minutes: '完工偏差（分钟）', overlap_hours: '停机重叠（小时）', delay_after_reschedule_hours: '重排后超期（小时）',
  execution_state: '执行状态', data_quality: '记录完整性', hours: '工时依据', effective_processing_hours: '有效加工小时',
  quota_processing_hours: '定额加工小时', overrun: '是否超耗', downtimes: '停机依据', reason: '原因', start: '开始', end: '结束',
  overlap_start: '重叠开始', overlap_end: '重叠结束', data_gaps: '数据缺口', message: '说明', receipt: '物流登记',
  quantity: '数量', risk: '风险判断', basis: '计算依据', setup_or_elapsed_hours_included: '是否包括准备或停留时间'
};
// 按所在层登记：来源本身（交付、齐套、执行、停机、外协），交付评估，物料需求，数据缺口，外协回执。
const referenceLabels = {
  plan_ref: '正式计划编号', batch_ref: '批次编号', task_ref: '安排编号', operation_ref: '工序编号', downtime_ref: '停机编号',
  machine_ref: '设备编号', supplier_ref: '供应商编号', material_ref: '物料编号', report_ref: '报工编号', report_refs: '全部报工编号',
  outsourcing_ref: '外协登记编号', latest_fact_ref: '最新登记编号', operation_refs: '登记工序编号', batch_id: '批次号',
  code: '检查规则', time_basis: '时间计算方式', due_boundary: '交期截止计算方式', stored_status: '批次状态', ready_date: '齐套日期',
  readiness_issues: '齐套问题', completion_basis: '完工依据', risk_codes: '风险类型', known_overlap_hours: '已知停机重叠（小时）',
  grouping_basis: '合并发出依据', part: '零件', batch: '批次', supplier: '供应商', operations: '外协工序',
  target_kind: '登记类型', tracking_basis: '跟踪依据',
  part_no: '图号', part_label: '零件名称', priority: '优先级', task_count: '已安排条数',
  delivery_deadline_exclusive: '交期截止时刻', completeness: '安排完整性', issues: '相关问题', fields: '缺填项',
  ...receiptLabels, target: '登记的批次与工序', state_label: '状态说明', confirmed_at: '确认时间',
  declared_operator: T.handler, local_operator: T.recorder, history_count: '登记次数', awaiting_return: '是否待回厂',
  overdue: '是否超时', source_state: '来源状态', execution: '报工衔接说明', can_preview: '可否预检'
};
// 证据里的受控取值按项登记词表，生产方是 core/services/workbench/dashboard 的 projection.py（交付、齐套）、downtime.py、execution.py
// 与 external_handling.py。同一个取值在不同项里意思不同：齐套的 partial 是“部分齐套”，报工的 partial 是“部分完成”；执行状态的
// complete 是“已完工”，记录完整性的 complete 是“完整”，所以只按项取词，不按取值猜。没登记的项是数字、日期、编号或自由文本
// （物料编号、名称、单位、停机原因、说明），照原值显示；登记过的项遇到词表外的值显示“其他取值”。
const fieldValues = {
  kind: { planned_delivery: '正式计划交付推算', batch_readiness: '批次齐套检查', outsourcing_receipt: '外协物流登记',
    registered_downtime_overlap: '已登记停机与正式安排重叠', execution_projection: '现场报工记录' },
  basis: { batch_material_requirements_not_stock: '按批次物料需求判断，不看库存', union_of_registered_downtime_intersections: '已登记有效停机与安排重叠时段合并计算',
    not_currently_evaluated: '现在没有评估', complete_report_processing_hours_vs_operation_unit_hours_times_target: '完整报工加工工时与单件定额乘以目标数量对照' },
  ready_status: T.ready_statuses, execution_state: T.execution_states, data_quality: T.data_quality, risk: T.delivery_risks,
  due_state: T.due_states, due_issue: T.due_issues, completion_state: T.delivery_completion_states
};
// Only diagnostics and opaque references fold into the reference summary. Business identifiers such as
// business_code or kind stay visible: 4.7 hides technical ids, not the information a planner acts on.
// 只有正文可见的项会进到这里判断：业务字段照常显示，其余项的值是完整十六进制引用时折进编号区。
const businessKey = key => /(?:_code|_quantity|_hours|_minutes|_days)$/.test(key)
  || ['kind', 'label', 'unit', 'reason', 'message', 'basis'].includes(key);

const referenceField = (key, item) => !businessKey(key) && typeof item === 'string' && /^[0-9a-f]{32,}$/i.test(item);
const own = (table, key) => Object.prototype.hasOwnProperty.call(table, key);

// 需求量、可用量等物料数量按批次详情的口径显示全部小数，0.004 不能读成 0.00；小时等其他计量值保留两位小数。
const quantityKey = key => typeof key === 'string' && /(?:^|_)quantity$/.test(key);

function display(value, key, context) {
  if (key === 'due_date' && context && context.due_state) return T.due_date(value, context.due_state, context.due_issue);
  if (context && context.due_state === 'unspecified' && ['is_overdue', 'delay_hours', 'delay_days'].includes(key)) return '不适用';
  if (key === 'due_issue' && value === null) return '无';
  if (value === null || value === undefined || value === '') return '未知';
  if (typeof value === 'boolean') return value ? '是' : '否';
  if (typeof value === 'number') return F.number(value, quantityKey(key) ? { digits: 20, trim: true } : { digits: Number.isInteger(value) ? 0 : 2 });
  if (/^\d{4}-\d\d-\d\d[T ]\d\d:\d\d/.test(value)) return F.dateTime(value);
  if (/^\d{4}-\d\d-\d\d$/.test(value)) return F.date(value);
  if (own(fieldValues, key)) return fieldValues[key][value] || '其他取值';
  return String(value);
}

const technical = item => item === null || item === undefined ? '' : typeof item === 'object' ? JSON.stringify(item) : String(item);

// field：这个值所在的项，按项取词和数量精度；列表里的每一项沿用列表所在的项。
function Structure({ value, title, field, context }) {
  if (Array.isArray(value)) return value.length ? <ol className="dy-source-list">{value.map((item, index) => <li key={index}><Structure value={item} field={field} context={context} /></li>)}</ol> : <span>无记录</span>;
  if (!value || typeof value !== 'object') return /[a-f0-9]{32,}/i.test(String(value)) ? <WorkbenchReference value={value} /> : <span>{display(value, field, context)}</span>;
  // Only keys in labels become visible facts. Opaque references, diagnostics and other keys fold into the
  // reference summary under their Chinese names, so a raw key never reads as a label on screen.
  const refs = {}, fields = [];
  let others = 0;
  Object.entries(value).forEach(([key, item]) => {
    if (own(labels, key) && !referenceField(key, item)) fields.push([key, item]);
    else refs[own(labels, key) ? labels[key] : own(referenceLabels, key) ? referenceLabels[key] : '其他记录项 ' + (++others)] = technical(item);
  });
  return <>{title && <h4>{title}</h4>}<dl className="dy-source-facts">{fields.map(([key, item]) => <div key={key}><dt>{labels[key]}</dt><dd><Structure value={item} field={key} context={value} /></dd></div>)}</dl>
    {Object.keys(refs).length > 0 && <WorkbenchReference entries={refs} />}</>;
}

function Evidence({ source }) {
  const e = source.evaluation;
  const timeline = Object.fromEntries(['planned_start', 'planned_end', 'first_actual_start', 'confirmed_finish', 'finish_deviation_minutes', 'overlap_hours', 'delay_after_reschedule_hours'].filter(key => own(source, key)).map(key => [key, source[key]]));
  return <><WorkbenchReference entries={{ [referenceLabels.plan_ref]: source.plan_ref, [referenceLabels.batch_ref]: source.batch_ref }} />
    {source.kind === 'outsourcing_receipt' && <><h4>物流登记记录</h4>{source.receipt ? <div className="outsourcing-live"><OutsourcingControls.Facts facts={source.receipt} /></div> : <div className="dy-note warning">物流登记读取失败，请刷新重试。</div>}</>}
    {source.requirements && <Structure title="物料需求" value={source.requirements} />}
    {e && <Structure title="交付评估" value={e} />}
    {source.execution_state && <div className="dy-note">执行状态：{display(source.execution_state, 'execution_state')} · {labels.data_quality}：{display(source.data_quality, 'data_quality')}</div>}
    {Object.keys(timeline).length > 0 && <Structure title="安排与执行时间" value={timeline} />}
    {source.hours && <Structure title="加工工时依据" value={source.hours} />}
    {source.downtimes && <Structure title="停机时段依据" value={source.downtimes} />}
    {source.data_gaps && <Issues issues={source.data_gaps} />}
    <details className="dy-evidence"><summary>完整来源依据</summary><Structure value={source} /></details></>;
}

const DashboardEvidence = { Evidence, Structure, display };

export { DashboardEvidence, Evidence, Structure, display };
export default DashboardEvidence;
