(function () {
  'use strict';
  const { Icon, ErrorBox } = window.ResourceControls;
  function Button({ className = '', ...props }) {
    return <window.ResourceControls.Button {...props} className={'wb-action ' + className} />;
  }
  const names = { batch_label: '批次', planned_end: '计划完工', finish_deviation_minutes: '完工偏差', effective_processing_hours: '有效工时',
    event_time: '实际结束或事件时间', quantity_done: '本次数量或旧登记量', resource_label: '资源', events: '旧现场事件数', event_count: '旧现场事件数', data_quality: '完整性' };
  const focuses = [['all', '全部工序'], ['unreported', '暂无现场反馈'], ['unclosed', '到期未确认完成'], ['late_open', '超时未确认完成'],
    ['finish_late', '已确认晚完'], ['complete', '已确认整道完工'], ['data_gaps', '数据待补']];
  function Styles() {
    return <style>{`
      .rw-workbench {background:transparent;box-shadow:none;}
      .rw-workbench .rw-metrics {background:transparent!important;margin-top:12px;}
      .rw-workbench .wb-metric {background:transparent!important;}
      .rw-workbench .aw-scope-main {gap:10px 12px;}
      .rw-workbench .aw-scope-filters {gap:10px 12px;}
      .rw-workbench .rw-filters {gap:10px 16px;align-items:flex-end;}
      .rw-workbench .rw-filters label {gap:6px;white-space:nowrap;}
      .rw-workbench .rw-table-heading {border-top:1px solid var(--ui-border);padding:12px 0 8px;}
      .rw-workbench .rw-primary-table {max-height:max(240px,calc(100vh - 490px));overscroll-behavior:contain;}
      .rw-workbench .rw-primary-table th {position:sticky;top:0;z-index:1;background:var(--ui-surface-muted)!important;}
      .rw-workbench .rw-primary-table:focus-visible {outline:2px solid var(--ui-info-text);outline-offset:2px;}
      .rw-workbench .rw-cell-text {min-width:0;max-width:100%;}
      .rw-workbench .rw-cell-text > summary {cursor:pointer;display:flex;align-items:flex-start;gap:4px;color:inherit;}
      .rw-workbench .rw-cell-text > summary::-webkit-details-marker {display:none;}
      .rw-workbench .rw-cell-text > summary svg {width:14px;height:18px;flex:none;color:var(--ui-info-text);}
      .rw-workbench .rw-cell-text[open] > summary svg {transform:rotate(180deg);}
      .rw-workbench .rw-cell-preview {display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;overflow-wrap:anywhere;}
      .rw-workbench .rw-cell-text[open] .rw-cell-preview {-webkit-line-clamp:unset;display:block;}
      .rw-workbench .rw-catalog .rw-filters {justify-content:flex-start;}
      .rw-workbench .rw-catalog .rw-filters label {flex-direction:column;align-items:stretch;}
      .rw-workbench .rw-catalog .rw-filters input {width:168px;}
      .rw-workbench .rw-catalog .rw-filters select {max-width:240px;}
      @media(max-width:1450px) {
        .rw-workbench .aw-scope-main {grid-template-columns:140px repeat(2,minmax(150px,1fr)) minmax(150px,1fr) minmax(180px,1.2fr) auto;}
        .rw-workbench .rw-table {min-width:1100px;}
      }
      @media(max-width:1200px) {
        .rw-workbench .aw-scope-main {grid-template-columns:repeat(3,minmax(140px,1fr));}
        .rw-workbench .rw-primary-table {max-height:460px;}
      }
      @media(max-width:700px) {
        .rw-workbench .aw-scope-main {grid-template-columns:repeat(2,minmax(0,1fr));}
      }
    `}</style>;
  }
  function Scope({ value, onChange, choices = {}, busy }) {
    const [draft, setDraft] = React.useState(value), [more, setMore] = React.useState(false);
    React.useEffect(() => setDraft(value), [JSON.stringify(value)]);
    const set = patch => setDraft(old => ({ ...old, ...patch }));
    const options = kind => choices[kind] || [];
    function selectOptions(kind, selected) {
      const rows = options(kind).slice();
      if (selected && selected !== 'unassigned' && !rows.some(row => row.ref === selected)) rows.unshift({ ref: selected, label: '当前范围外的已选对象' });
      return rows.map(row => <option value={row.ref} key={row.ref}>{row.label}{row.available === false ? '（原资料不可用）' : ''}</option>);
    }
    return <form className="aw-scope" aria-label="执行分析筛选" onSubmit={event => { event.preventDefault(); onChange(window.ReportAPI.scope(draft)); }}>
      <div className="aw-scope-main">
        <label>数据来源<select aria-label="数据来源" value="production" disabled><option value="production">当前正式计划</option></select></label>
        <label>计划完工起日<input type="date" aria-label="计划完工起日" value={draft.plan_finish_date_from || ''} onChange={event => set({ plan_finish_date_from: event.target.value })} /></label>
        <label>计划完工止日<input type="date" aria-label="计划完工止日" value={draft.plan_finish_date_to || ''} onChange={event => set({ plan_finish_date_to: event.target.value })} /></label>
        <label>批次<select aria-label="批次筛选" value={draft.batch_ref || ''} onChange={event => set({ batch_ref: event.target.value })}><option value="">全部批次</option>{selectOptions('batch', draft.batch_ref)}</select></label>
        <label>搜索<input type="search" aria-label="搜索批次或工序" value={draft.query || ''} onChange={event => set({ query: event.target.value })} /></label>
        <div className="aw-scope-tools"><Button icon="search" type="submit" busy={busy} aria-label="查询范围" className="btn" />
          <Button icon="chevron-down" aria-label="更多筛选" aria-expanded={more} onClick={() => setMore(old => !old)} />
          <Button icon="x" aria-label="清除筛选" onClick={() => onChange({ source: 'production', ...(value.plan_ref ? { plan_ref: value.plan_ref } : {}) })} /></div>
      </div>
      <div className="aw-scope-filters" hidden={!more}>
        <label>资源类型<select aria-label="资源类型" value={draft.resource_type || ''} onChange={event => set({ resource_type: event.target.value, resource_ref: '' })}><option value="">全部资源</option><option value="machine">设备</option><option value="operator">人员</option></select></label>
        <label>关联资源<select aria-label="关联资源" value={draft.resource_ref || ''} disabled={!draft.resource_type} onChange={event => set({ resource_ref: event.target.value })}><option value="">全部对象</option><option value="unassigned">未填写</option>{selectOptions(draft.resource_type, draft.resource_ref)}</select></label>
        <label>分析范围<select aria-label="分析范围" value={draft.focus || 'all'} onChange={event => set({ focus: event.target.value })}>{focuses.map(([key, label]) => <option value={key} key={key}>{label}</option>)}</select></label>
      </div>
      <div className="aw-scope-summary"><ul>{Object.entries(value).filter(([key, item]) => !['source', 'plan_ref'].includes(key) && item && item !== 'all').map(([key, item]) =>
        <li key={key}><span>{key === 'query' ? item : key === 'focus' ? (focuses.find(row => row[0] === item) || [null, item])[1] : key.endsWith('_ref') ? Object.values(choices).flat().find(row => row.ref === item)?.label || '已选资源' : item === 'machine' ? '设备' : item === 'operator' ? '人员' : item}</span>
          <button type="button" aria-label={'清除 ' + key} onClick={() => { const next = { ...value }; delete next[key]; if (key === 'resource_type') delete next.resource_ref; if (key.startsWith('plan_finish_date')) { delete next.plan_finish_date_from; delete next.plan_finish_date_to; } onChange(next); }}><Icon name="x" /></button></li>)}</ul></div>
    </form>;
  }
  function Tabs({ topic, onChange }) {
    const labels = ['工序完成情况', '报工记录', '设备工时', '人员工时', '数据完整性'];
    return <div className="rw-tabs" role="tablist" aria-label="报表专题">{window.ReportAPI.topics.map((key, index) => <button key={key} id={'report-tab-' + key} type="button" role="tab"
      aria-selected={topic === key} aria-controls="report-topic-panel" tabIndex={topic === key ? 0 : -1} onClick={() => onChange(key)} onKeyDown={event => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault(); const next = event.key === 'Home' ? 0 : event.key === 'End' ? 4 : (index + (event.key === 'ArrowRight' ? 1 : -1) + 5) % 5;
        onChange(window.ReportAPI.topics[next]); document.getElementById('report-tab-' + window.ReportAPI.topics[next]).focus();
      }}>{labels[index]}</button>)}</div>;
  }
  function Page({ page, onChange, busy }) {
    return <div className="rw-pagination"><span aria-live="polite">共 {page.total} 项 · 第 {page.number} / {page.pages} 页</span>
      <label>每页<select aria-label="每页数量" value={page.size} disabled={busy} onChange={event => onChange({ page: 1, size: Number(event.target.value) })}>{[10, 20, 50].map(size => <option key={size} value={size}>{size}</option>)}</select></label>
      <div className="rw-actions" style={{ marginLeft: 0 }}><Button icon="chevron-left" aria-label="上一页" disabled={busy || page.number <= 1} onClick={() => onChange({ page: page.number - 1 })} />
      <Button icon="chevron-right" aria-label="下一页" disabled={busy || page.number >= page.pages} onClick={() => onChange({ page: page.number + 1 })} /></div></div>;
  }
  function Sort({ topic, state, onChange }) {
    return <><label>排序<select aria-label="排序字段" value={state.sort} onChange={event => onChange({ sort: event.target.value, page: 1 })}>{window.ReportAPI.sorts[topic].map(key => <option value={key} key={key}>{names[key]}</option>)}</select></label>
      <label>顺序<select aria-label="排序方向" value={state.direction} onChange={event => onChange({ direction: event.target.value, page: 1 })}><option value="asc">升序</option><option value="desc">降序</option></select></label></>;
  }
  function useRead(load, identity) {
    const [result, setResult] = React.useState(null), [error, setError] = React.useState(null), [busy, setBusy] = React.useState(true);
    React.useEffect(() => {
      const controller = new AbortController(); let active = true;
      setBusy(true); setError(null); setResult(null);
      Promise.resolve().then(() => load(controller.signal)).then(value => { if (active) setResult(value); }, failure => { if (active) setError(failure); }).finally(() => { if (active) setBusy(false); });
      return () => { active = false; controller.abort(); };
    }, [identity]);
    return { result, error, busy };
  }
  window.ReportControls = { Scope, Tabs, Page, Sort, useRead, Button, Icon, ErrorBox, Styles };
})();
