(function () {
  'use strict';
  const { Button, ErrorBox } = window.ResourceControls;
  function Segment({ label, value, choices, onChange, disabled }) {
    const id = React.useId();
    return <div className="pf-segment" role="radiogroup" aria-label={label}>{choices.map(([key, text, unavailable]) => <label key={String(key)} className={value === key ? 'selected' : ''}>
      <input type="radio" name={id} checked={value === key} disabled={disabled || unavailable} onChange={() => onChange(key)} /><span>{text}</span>
    </label>)}</div>;
  }
  function Rules({ value, onChange, disabled }) {
    return <section aria-labelledby="pf-rules-title"><h3 id="pf-rules-title">本次排产规则</h3><div className="pf-rows">
      <div className="pf-rule"><strong>齐套检查</strong><Segment label="齐套检查" value={value.ready_check} choices={[[true, '开启'], [false, '关闭']]} disabled={disabled} onChange={ready_check => onChange({ ready_check })} /></div>
      <div className="pf-rule"><strong>缺资源工序</strong><Segment label="缺资源工序" value={value.missing_resource_policy} choices={[["auto_assign", '自动分配'], ['exclude', '暂不排']]} disabled={disabled} onChange={missing_resource_policy => onChange({ missing_resource_policy })} /></div>
      <div className="pf-rule"><strong>已发生执行</strong><Segment label="已发生执行" value="preserve_actuals" choices={[["preserve_actuals", '保留事实'], ['reopen', '可重排', true]]} disabled={disabled} onChange={() => {}} /></div>
      <div className="pf-rule pf-note">本次参数，不改全局配置。工时、工种、外协资料仍为必填项；开工和完工事实不能解除保护。</div>
    </div></section>;
  }
  function Metrics({ counts }) {
    const items = [['selected_tasks', '范围内工序'], ['ready_tasks', '资料有效'], ['auto_assign_required', '自动分配待补'], ['skipped_tasks', '本次跳过'], ['blocked_tasks', '阻塞工序'], ['no_route_batches', '未生成工艺批次'], ['actual_fact_tasks', '已发生事实']];
    return <dl className="pf-metrics">{items.map(([key, label]) => <div key={key}><dt>{label}</dt><dd>{counts ? counts[key] : '未检查'}</dd></div>)}</dl>;
  }
  function Reasons({ data }) {
    const groups = new Map(), tasks = new Map(data.tasks.map(row => [row.operation_ref, row]));
    const batches = new Map(data.included_batches.concat(data.excluded_batches).map(row => [row.batch_ref, row.batch_id]));
    data.run_blocked_reasons.concat(data.warnings).forEach(item => {
      if (!groups.has(item.code)) groups.set(item.code, []);
      groups.get(item.code).push(item);
    });
    function summary(code, items) {
      const operations = new Set(items.map(item => item.operation_ref).filter(Boolean)).size;
      const messages = Array.from(new Set(items.map(item => item.message))).join('；');
      if (operations && code === 'operation_blocked') return operations + '道工序缺必填资料';
      if (operations && code === 'execution_review_required') return operations + '道工序已有执行记录待核对';
      if (code === 'route_not_generated') return new Set(items.map(item => item.batch_ref).filter(Boolean)).size + '批尚未生成工艺';
      return (operations ? operations + '道工序：' : '') + messages;
    }
    function objectLabel(item) {
      const task = tasks.get(item.operation_ref);
      if (task) return task.batch_id + ' · ' + task.sequence + ' ' + task.label + (task.piece_id ? ' · ' + task.piece_id : '');
      return item.batch_id || batches.get(item.batch_ref) || item.operation_ref || item.batch_ref || '';
    }
    return <div className="pf-alert"><div role="status">{Array.from(groups, ([code, items]) => <div key={code} data-reason-group={code}>{summary(code, items)}</div>)}</div>
      <details className="pf-reasons"><summary>原因与对应对象 · {data.run_blocked_reasons.length + data.warnings.length} 项</summary>
        <div className="pf-reason-list">{Array.from(groups, ([code, items]) => <div key={code}>{items.map((item, index) => <p key={index}
          data-reason-code={item.code} data-operation-ref={item.operation_ref} data-batch-ref={item.batch_ref}>
          {objectLabel(item) && <strong>{objectLabel(item)}： </strong>}{item.message}</p>)}</div>)}</div>
      </details></div>;
  }
  function Styles() {
    return <style>{`
      .plana.preflight-workspace {padding:0;max-width:none;width:100%;min-width:0;color:var(--ui-text);letter-spacing:0}
      .preflight-workspace * {box-sizing:border-box;letter-spacing:0}
      .preflight-workspace h2 {font-size:18px;line-height:1.5;margin:0}
      .preflight-workspace h3 {font-size:15px;line-height:1.5;margin:0 0 12px}
      .preflight-workspace .pf-heading,.preflight-workspace .pf-tools,.preflight-workspace .pf-window {display:flex;align-items:center;gap:10px;flex-wrap:wrap}
      .preflight-workspace .pf-heading {justify-content:space-between;padding-bottom:16px}
      .preflight-workspace .pf-window {padding:14px 0;border-top:1px solid var(--ui-border);border-bottom:1px solid var(--ui-border)}
      .preflight-workspace .pf-window label {display:flex;align-items:center;gap:8px}
      .preflight-workspace input[type=date] {width:156px;min-width:0}
      .preflight-workspace .pf-muted,.preflight-workspace .pf-note {color:var(--ui-info-muted);font-size:12px;line-height:1.7}
      .preflight-workspace .pf-metrics {margin:0;padding:18px 0;display:grid;grid-template-columns:repeat(7,minmax(0,1fr));border-bottom:1px solid var(--ui-border)}
      .preflight-workspace .pf-metrics>div {min-width:0;padding:0 14px;border-left:1px solid var(--ui-border)}
      .preflight-workspace .pf-metrics>div:first-child {border-left:0;padding-left:0}
      .preflight-workspace dt {font-size:12px;color:var(--ui-info-muted);overflow-wrap:anywhere}
      .preflight-workspace dd {margin:8px 0 0;font-size:20px;font-weight:600;font-variant-numeric:tabular-nums}
      .preflight-workspace .pf-body {display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:26px;padding:20px 0;border-bottom:1px solid var(--ui-border)}
      .preflight-workspace .pf-body>section {min-width:0}
      .preflight-workspace .pf-body>section+section {padding-left:26px;border-left:1px solid var(--ui-border)}
      .preflight-workspace .pf-rows {display:grid;grid-auto-rows:minmax(78px,auto)}
      .preflight-workspace .pf-rule,.preflight-workspace .pf-check {min-height:58px;display:grid;grid-template-columns:minmax(0,1fr) 200px;gap:10px;align-items:center;border-top:1px solid var(--ui-border);padding:9px 0}
      .preflight-workspace .pf-rule strong,.preflight-workspace .pf-check strong {font-size:13px}
      .preflight-workspace .pf-rule.pf-note {display:block}
      .preflight-workspace .pf-check {grid-template-columns:minmax(0,1fr) 110px}
      .preflight-workspace .pf-check p {margin:3px 0 0;font-size:12px;line-height:1.6;color:var(--ui-info-muted)}
      .preflight-workspace .pf-check>span {justify-self:end;max-width:110px;white-space:normal}
      .preflight-workspace .pf-segment {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));width:200px;min-height:32px;border:1px solid var(--ui-border);border-radius:5px;background:var(--ui-surface-muted)}
      .preflight-workspace .pf-segment label {position:relative;min-width:0;cursor:pointer}
      .preflight-workspace .pf-segment input {position:absolute;opacity:0!important;width:1px!important;height:1px!important;min-width:0;min-height:0;padding:0;margin:0;border:0}
      .preflight-workspace .pf-segment span {display:flex;align-items:center;justify-content:center;min-height:30px;padding:4px;font-size:12px;color:var(--ui-info-muted);border-radius:4px}
      .preflight-workspace .pf-segment .selected span {background:var(--ui-surface);color:var(--ui-text);box-shadow:0 1px 3px #0002;font-weight:600}
      .preflight-workspace .pf-segment input:focus-visible+span {outline:2px solid var(--ui-primary);outline-offset:2px}
      .preflight-workspace .pf-segment input:disabled+span {opacity:.5;cursor:not-allowed}
      .preflight-workspace .pf-picker {padding:16px 0;border-bottom:1px solid var(--ui-border);background:var(--ui-surface-muted)}
      .preflight-workspace .pf-picker-row {display:grid;grid-template-columns:22px minmax(110px,1fr) minmax(100px,2fr) 80px 90px;align-items:center;gap:12px;min-height:40px;border-top:1px solid var(--ui-border);padding:7px 10px;font-size:13px}
      .preflight-workspace .pf-picker-row>* {min-width:0;overflow-wrap:anywhere}
      .preflight-workspace .pf-picker-row input {width:15px;height:15px}
      .preflight-workspace .pf-picker-list {margin:12px 0;max-height:360px;overflow:auto}
      .preflight-workspace .pf-tools {padding:6px 0}
      .preflight-workspace .pf-tools input[type=search] {width:260px;max-width:100%;min-width:0}
      .preflight-workspace .pf-tools select {width:92px}
      .preflight-workspace .pf-detail {padding:14px 0;border-bottom:1px solid var(--ui-border)}
      .preflight-workspace .pf-detail summary {cursor:pointer;font-size:13px;font-weight:600}
      .preflight-workspace .pf-results {max-height:340px;overflow:auto;margin-top:12px}
      .preflight-workspace table {width:100%;table-layout:fixed}
      .preflight-workspace th,.preflight-workspace td {white-space:normal!important;overflow-wrap:anywhere;vertical-align:top}
      .preflight-workspace .pf-results p {margin:2px 0;font-size:12px;line-height:1.6}
      .preflight-workspace .pf-alert {padding:12px 14px;margin:14px 0;border-left:3px solid var(--ui-warning);background:var(--ui-surface-muted);font-size:13px;line-height:1.7;overflow-wrap:anywhere}
      .preflight-workspace .pf-reasons {margin-top:6px}.preflight-workspace .pf-reasons summary {cursor:pointer}
      .preflight-workspace .pf-reason-list {max-height:240px;overflow:auto;margin-top:8px}.preflight-workspace .pf-reason-list p {margin:4px 0}
      .preflight-workspace .pf-footer {display:flex;align-items:center;justify-content:space-between;gap:16px;padding:18px 0;flex-wrap:wrap}
      .preflight-workspace button {max-width:100%;white-space:normal}
      @media(max-width:1100px) {.preflight-workspace .pf-body{gap:18px}.preflight-workspace .pf-body>section+section{padding-left:18px}.preflight-workspace .pf-rule{grid-template-columns:minmax(0,1fr) 180px}.preflight-workspace .pf-segment{width:180px}}
      @media(max-width:760px) {.preflight-workspace .pf-body{grid-template-columns:minmax(0,1fr)}.preflight-workspace .pf-body>section+section{padding-left:0;border-left:0}.preflight-workspace .pf-metrics{grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.preflight-workspace .pf-picker-row{grid-template-columns:22px minmax(0,1fr) minmax(0,1fr)}.preflight-workspace .pf-picker-row>span:nth-last-child(-n+2){display:none}.preflight-workspace .pf-window label{flex-wrap:wrap}}
    `}</style>;
  }
  window.PreflightControls = { Button, ErrorBox, Rules, Metrics, Reasons, Styles };
})();
