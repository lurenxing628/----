(function () {
  'use strict';
  const { Icon, ErrorBox } = window.ResourceControls;
  function Button({ className = '', ...props }) {
    return <window.ResourceControls.Button {...props} className={'wb-action ' + className} />;
  }
  // 排序列名在渲染时才读词表里的「历史现场记录」，避免加载顺序依赖。
  const names = () => ({ batch_label: '批次', planned_end: '计划完工', finish_deviation_minutes: '完工偏差（分钟）', effective_processing_hours: '有效工时（小时）',
    event_time: '实际结束或记录时间', quantity_done: '本次数量或登记数量', resource_label: '资源', events: window.WorkbenchTerms.legacy_field_records + '数',
    event_count: window.WorkbenchTerms.legacy_field_records + '数', data_quality: '完整性' });
  // 「清除某个筛选」按钮的可读名字，不用内部键名。
  const scopeNames = { plan_finish_date_from: '计划完工起日', plan_finish_date_to: '计划完工止日', batch_ref: '批次',
    query: '搜索', resource_type: '资源类型', resource_ref: '关联资源', focus: '分析范围' };
  // 已选条件摘要里，找不到名称的编号按条件种类说明，不笼统写「已选资源」。
  const selectedFallback = { batch_ref: '已选批次', resource_ref: '已选资源' };
  const focuses = [['all', '全部工序'], ['unreported', '待报工'], ['unclosed', '到期未确认完成'], ['late_open', '超时未确认完成'],
    ['finish_late', '已确认晚完成'], ['complete', '已确认整道完工'], ['data_gaps', '数据待补']];
  function Scope({ value, onChange, choices = {}, busy }) {
    const [draft, setDraft] = React.useState(value), [more, setMore] = React.useState(false);
    React.useEffect(() => setDraft(value), [JSON.stringify(value)]);
    const set = patch => setDraft(old => ({ ...old, ...patch }));
    const options = kind => choices[kind] || [];
    function selectOptions(kind, selected) {
      const rows = options(kind).slice();
      if (selected && selected !== 'unassigned' && !rows.some(row => row.ref === selected)) rows.unshift({ ref: selected, label: '当前范围外的已选项' });
      return rows.map(row => <option value={row.ref} key={row.ref}>{row.label}{row.available === false ? '（原资料不可用）' : ''}</option>);
    }
    return <form className="aw-scope" aria-label="执行分析筛选" onSubmit={event => { event.preventDefault(); onChange(window.ReportAPI.scope(draft)); }}>
      <div className="aw-scope-main">
        <label>计划完工起日<input type="date" aria-label="计划完工起日" value={draft.plan_finish_date_from || ''} onChange={event => set({ plan_finish_date_from: event.target.value })} /></label>
        <label>计划完工止日<input type="date" aria-label="计划完工止日" value={draft.plan_finish_date_to || ''} onChange={event => set({ plan_finish_date_to: event.target.value })} /></label>
        <label>批次<select aria-label="批次筛选" value={draft.batch_ref || ''} onChange={event => set({ batch_ref: event.target.value })}><option value="">全部批次</option>{selectOptions('batch', draft.batch_ref)}</select></label>
        <label>搜索<input type="search" aria-label="搜索批次或工序" value={draft.query || ''} onChange={event => set({ query: event.target.value })} /></label>
        <div className="aw-scope-tools"><Button icon="search" type="submit" busy={busy} aria-label="查询范围" className="primary" />
          <Button icon="chevron-down" aria-label="更多筛选" aria-expanded={more} onClick={() => setMore(old => !old)} />
          <Button icon="x" aria-label="清除筛选" onClick={() => onChange({ source: 'production', ...(value.plan_ref ? { plan_ref: value.plan_ref } : {}) })} /></div>
      </div>
      <div className="aw-scope-filters" hidden={!more}>
        <label>资源类型<select aria-label="资源类型" value={draft.resource_type || ''} onChange={event => set({ resource_type: event.target.value, resource_ref: '' })}><option value="">全部资源</option><option value="machine">设备</option><option value="operator">人员</option></select></label>
        <label>关联资源<select aria-label="关联资源" value={draft.resource_ref || ''} disabled={!draft.resource_type} onChange={event => set({ resource_ref: event.target.value })}><option value="">全部关联资源</option><option value="unassigned">未填写</option>{selectOptions(draft.resource_type, draft.resource_ref)}</select></label>
        <label>分析范围<select aria-label="分析范围" value={draft.focus || 'all'} onChange={event => set({ focus: event.target.value })}>{focuses.map(([key, label]) => <option value={key} key={key}>{label}</option>)}</select></label>
      </div>
      <div className="aw-scope-summary"><ul>{Object.entries(value).filter(([key, item]) => !['source', 'plan_ref'].includes(key) && item && item !== 'all').map(([key, item]) =>
        <li key={key}><span>{key === 'query' ? item : key === 'focus' ? (focuses.find(row => row[0] === item) || [null, item])[1] : key.endsWith('_ref') ? item === 'unassigned' ? '未填写' : Object.values(choices).flat().find(row => row.ref === item)?.label || selectedFallback[key] || '已选条件' : item === 'machine' ? '设备' : item === 'operator' ? '人员' : item}</span>
          <button type="button" aria-label={'清除' + (scopeNames[key] || '筛选项')} onClick={() => { const next = { ...value }; delete next[key]; if (key === 'resource_type') delete next.resource_ref; if (key.startsWith('plan_finish_date')) { delete next.plan_finish_date_from; delete next.plan_finish_date_to; } onChange(next); }}><Icon name="x" /></button></li>)}</ul></div>
    </form>;
  }
  function Tabs({ topic, onChange }) {
    const labels = ['工序完成情况', '报工记录', '设备工时', '人员工时', '数据完整性'];
    return <div className="rw-tabs" role="tablist" aria-label="报表专题">{window.ReportAPI.topics.map((key, index) => <button key={key} id={'report-tab-' + key} type="button" role="tab"
      aria-selected={topic === key} aria-controls="report-topic-panel" tabIndex={topic === key ? 0 : -1} onClick={() => onChange(key)} onKeyDown={event => {
        if (event.altKey || event.ctrlKey || event.metaKey) return;
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault(); const next = event.key === 'Home' ? 0 : event.key === 'End' ? 4 : (index + (event.key === 'ArrowRight' ? 1 : -1) + 5) % 5;
        onChange(window.ReportAPI.topics[next]); document.getElementById('report-tab-' + window.ReportAPI.topics[next]).focus();
      }}>{labels[index]}</button>)}</div>;
  }
  function Page({ page, onChange, busy }) {
    return <window.WorkbenchListControls.Pager page={page.number} pages={page.pages} total={page.total} size={page.size}
      sizes={[10, 20, 50]} label="" busy={busy} onPage={number => onChange({ page: number })} onSize={size => onChange({ page: 1, size })} />;
  }
  function Sort({ topic, state, onChange }) {
    const labels = names();
    return <><label>排序<select aria-label="排序列" value={state.sort} onChange={event => onChange({ sort: event.target.value, page: 1 })}>{window.ReportAPI.sorts[topic].map(key => <option value={key} key={key}>{labels[key]}</option>)}</select></label>
      <label>顺序<select aria-label="排序方向" value={state.direction} onChange={event => onChange({ direction: event.target.value, page: 1 })}><option value="asc">升序</option><option value="desc">降序</option></select></label></>;
  }
  function useRead(load, identity) {
    const read = window.APSResourceSession.useQuery(load, [identity]);
    return { ...read, busy: read.loading };
  }
  window.ReportControls = { Scope, Tabs, Page, Sort, useRead, Button, Icon, ErrorBox };
})();
