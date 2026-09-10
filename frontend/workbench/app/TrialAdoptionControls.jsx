(function () {
  'use strict';
  const { Button, Modal } = window.ResourceControls;
  function Scope({ value, label }) {
    return <><dl className="ta-scope"><div><dt>{label}</dt><dd>{value.baseline.version === null ? '尚无正式计划' : 'v' + value.baseline.version}</dd></div>
      <div><dt>采用完整范围</dt><dd>完整场景，共 {value.task_count} 道工序</dd></div>
      <div><dt>原场景</dt><dd>场景 · {value.scenario_ref.slice(-8)}</dd></div><div><dt>原草稿</dt><dd>草稿 · {value.draft_ref.slice(-8)}</dd></div></dl>
      <p className="ta-note">采用完整已存场景，不限当前筛选或显示范围；新增正式版本，保留原场景、旧正式计划和已有执行记录。</p></>;
  }
  function Fields({ session: s }) {
    const id = React.useId(), frozen = !!s.saved;
    return <div className="ta-fields"><div className="field"><label htmlFor={id + '-reason'}>采用原因</label>
      <textarea id={id + '-reason'} rows={3} maxLength={1000} value={s.draft.reason} readOnly={frozen} disabled={s.busy}
        onChange={e => s.change({ ...s.draft, reason: e.target.value })} /></div>
      <div className="field"><label htmlFor={id + '-operator'}>声明人</label><input id={id + '-operator'} maxLength={100} value={s.draft.declared_operator}
        readOnly={frozen} disabled={s.busy} onChange={e => s.change({ ...s.draft, declared_operator: e.target.value })} />
        <small>业务声明，不代表登录或认证身份。</small></div>
      {(!s.saved || s.saved.phase === 'rejected') && <label className="ta-consent"><input type="checkbox" checked={s.consent}
        disabled={s.busy || s.disabled || !s.preview || !s.preview.validation.can_adopt || !!s.storageError} onChange={e => s.setConsent(e.target.checked)} />
        <span>我已核对原场景、原草稿、正式基线及完整范围，确认正式采用。</span></label>}
      {frozen && <small>原 key 已绑定以上场景及确认内容，不可修改后复用。</small>}</div>;
  }
  function Records({ value, saved, result }) {
    return <details className="ta-records"><summary>原身份与回执记录</summary><div>原场景编号：{value.scenario_ref}</div>
      {value.draft_ref && <div>原草稿编号：{value.draft_ref}</div>}{value.baseline && value.baseline.plan_ref && <div>原正式基线编号：{value.baseline.plan_ref}</div>}
      {saved && <div>原请求编号：{saved.request_key}</div>}{result && <><div>回执编号：{result.receipt_ref}</div><div>新正式方案编号：{result.data.official_plan.plan_ref}</div></>}</details>;
  }
  function Dialog({ session: s, scenarioRef, onNavigate }) {
    const pending = s.saved && s.saved.phase === 'pending', rejected = s.saved && s.saved.phase === 'rejected', valid = s.preview && s.preview.validation.can_adopt;
    const value = valid ? s.preview : s.saved ? s.saved.preview : s.original || { scenario_ref: scenarioRef || '未指定' };
    const other = s.saved && s.saved.scenario_ref !== scenarioRef;
    const blocked = s.disabled || !!s.sourceError || !!s.storageError || !!other;
    const canConfirm = valid && s.consent && s.draft.reason.trim() && s.draft.declared_operator.trim() && !pending && !blocked;
    return <Modal title={s.result ? '场景正式采用回执' : pending ? '核实原场景采用请求' : '确认场景正式采用'} icon="check" onClose={s.close}
      footer={<><Button onClick={s.close}>{pending ? '关闭并保留请求' : s.result ? '关闭' : '取消'}</Button>
        {rejected && <Button disabled={s.busy || !!s.storageError} onClick={s.finish}>结束本次未采用</Button>}
        {s.result ? <><Button icon="refresh-cw" busy={s.busy} disabled={!!s.storageError} onClick={s.lookup}>查询原请求</Button>
          <Button icon="check" disabled={s.busy || !!s.storageError} onClick={s.finish}>完成核实</Button><Button icon="arrow-right" className="btn primary"
            reason={typeof onNavigate === 'function' ? '' : '正式方案导航尚未接入。'} onClick={() => onNavigate('analysis', { plan_ref: s.result.data.official_plan.plan_ref })}>进入正式方案</Button></>
          : pending ? <Button icon="refresh-cw" busy={s.busy} disabled={!!s.storageError} onClick={s.lookup}>查询原请求</Button>
            : <><Button icon="refresh-cw" busy={s.busy} disabled={blocked} onClick={s.inspect}>重新预览</Button>
              <Button icon="check" className="btn primary" busy={s.busy} disabled={!canConfirm} onClick={s.submit}>确认正式采用</Button></>}</>}>
      <div className="modal-body ta-body">
        {(s.storageError || s.error) && <div className="ta-notice" role="alert">{s.storageError || s.error}</div>}
        {s.storageError && <Button icon="refresh-cw" disabled={s.busy} onClick={s.sync}>重读恢复记录</Button>}
        {other && <div className="ta-notice" role="status">原请求属于另一场景，请先核实该原记录；不能用于当前场景。</div>}
        {s.notice && <div className="ta-notice" role="status">{s.notice}</div>}
        {!pending && !s.result && (s.disabled || s.sourceError) && <div className="ta-notice" role="status">{s.sourceError || '原场景正在读取或有待核实操作，新的采用已暂停。'}</div>}
        {s.result && <div className="ta-result" role="status">已核实：本次生成正式版本 v{s.result.data.official_plan.version}，共 {s.result.data.row_count} 道工序。
          <p>这是提交时的回执版本，不代表当前正式版本。当前状态以重新打开的正式方案为准。</p>{s.result.replayed && <p>已按原 key 读取原回执，未新增正式版本。</p>}</div>}
        {value.baseline && <Scope value={value} label={valid ? '本次预览核对的正式基线' : s.saved ? '原请求核对的正式基线' : '原场景保存时的正式基线'} />}
        {s.preview && !valid && <div className="ta-notice" role="status">{s.preview.validation.issues.map((v, i) => <div key={i}>{v.message}</div>)}</div>}
        {rejected && !s.preview && <p className="ta-note">上次已明确拒绝，未执行采用；须重新预览并再次勾选，仍使用原 key 与原确认内容。</p>}
        {!s.result ? <Fields session={s} /> : <dl className="ta-scope"><div><dt>采用原因</dt><dd>{s.saved.input.reason}</dd></div><div><dt>声明人</dt><dd>{s.saved.input.declared_operator}</dd></div></dl>}
        <Records value={value} saved={s.saved} result={s.result} />
      </div></Modal>;
  }
  function Styles() {
    return <style>{`
      .plana.trial-adoption-action{display:inline-flex;align-items:center;gap:8px;flex-wrap:wrap;max-width:100%;width:auto;padding:0;min-width:0;color:var(--ui-text);letter-spacing:0}
      .trial-adoption-action *{box-sizing:border-box;letter-spacing:0}.trial-adoption-action .modal-bg{z-index:1100}
      .trial-adoption-action .modal.lg{width:760px;max-width:calc(100vw - 48px);max-height:calc(100vh - 48px);display:flex;flex-direction:column;min-width:0;color:var(--ui-text);background:var(--ui-card-bg)}
      .trial-adoption-action .modal-head,.trial-adoption-action .modal-f{flex-shrink:0}.trial-adoption-action .modal-f{gap:8px;padding:14px 20px}
      .trial-adoption-action .ta-body{padding:16px 22px;overflow:auto;min-height:0;max-height:65vh;font-size:13px;line-height:1.7;color:var(--ui-text)}
      .trial-adoption-action .ta-scope{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px 20px;padding:12px 0;margin:0;border-bottom:1px solid var(--ui-border)}
      .trial-adoption-action dt,.trial-adoption-action small,.trial-adoption-action .ta-note{color:var(--ui-info-muted);font-size:12px}
      .trial-adoption-action dd{margin:3px 0 0;overflow-wrap:anywhere;color:var(--ui-text)}.trial-adoption-action .ta-fields{display:grid;gap:12px;padding:12px 0}
      .trial-adoption-action .field{min-width:0;margin:0;display:grid;gap:5px}.trial-adoption-action .field label{color:var(--ui-text)}
      .trial-adoption-action .field input,.trial-adoption-action textarea{width:100%;min-width:0;color:var(--ui-text);background:var(--ui-card-bg);font:inherit;border:1px solid var(--ui-border);border-radius:4px;padding:8px 10px}
      .trial-adoption-action textarea{resize:vertical;min-height:84px;max-height:220px}.trial-adoption-action .ta-consent{display:flex;gap:9px;align-items:flex-start;color:var(--ui-text);line-height:1.7}
      .trial-adoption-action .ta-consent input{flex:none;width:16px;height:16px;margin-top:4px;accent-color:var(--ui-info-text)}
      .trial-adoption-action .ta-notice{padding:10px 12px;margin:8px 0;border-left:3px solid var(--ui-warning);background:var(--ui-surface-muted);overflow-wrap:anywhere}
      .trial-adoption-action .ta-records{padding-top:10px;color:var(--ui-info-muted);font-size:12px;overflow-wrap:anywhere}.trial-adoption-action .ta-result{color:var(--ui-success-text);padding:10px 0}
      .trial-adoption-action .ta-result p{color:var(--ui-info-muted);font-size:12px;margin:4px 0}.trial-adoption-action button{white-space:normal;max-width:100%}
      .trial-adoption-action .ta-inline{font-size:12px;color:var(--ui-info-muted);max-width:460px;overflow-wrap:anywhere}
      @media(max-width:600px){.trial-adoption-action .ta-body{padding:12px}.trial-adoption-action .ta-scope{grid-template-columns:1fr}.trial-adoption-action .modal-f{padding:12px}}
    `}</style>;
  }
  window.TrialAdoptionControls = { Button, Dialog, Styles };
})();
