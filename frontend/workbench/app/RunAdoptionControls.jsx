(function () {
  'use strict';
  const { Button, Modal } = window.ResourceControls;
  function Scope({ value, saved }) {
    return <><dl className="ra-scope"><div><dt>{saved ? '上次提交时核对的正式计划' : '当前正式计划（本次预检）'}</dt><dd>{value.baseline.version === null ? '尚无正式计划' : 'v' + value.baseline.version}</dd></div>
      <div><dt>目标候选方案</dt><dd>当前核对的完整候选方案<window.WorkbenchReference value={value.candidate_ref} /></dd></div><div><dt>采用工序</dt><dd>{value.task_count} 道</dd></div>
      <div><dt>采用范围</dt><dd>完整候选方案及全部当前正式安排</dd></div></dl>
      <p className="ra-note">采用会新增一版正式计划；不是只采用当前筛选出的工序。旧版本和报工记录都会保留，可在计划列表查看和导出；如需恢复旧安排，需要重新排产并再采用一版。</p></>;
  }
  function Records({ value, intent, result }) {
    return <details className="ra-records wb-ref"><summary>编号</summary>
      <div>候选方案编号：{value.candidate_ref}</div>{value.run_ref && <div>排产编号：{value.run_ref}</div>}
      {value.baseline && value.baseline.plan_ref && <div>原正式计划编号：{value.baseline.plan_ref}</div>}
      {intent && <div>操作编号：{intent.request_key}</div>}{result && <><div>结果编号：{result.receipt_ref}</div><div>新正式计划编号：{result.data.official_plan.plan_ref}</div></>}
    </details>;
  }
  function Fields({ draft, onChange, consent, onConsent, readOnly, busy }) {
    const id = React.useId(), memoryHint = window.WorkbenchHandlerMemory.hint(draft.declared_operator);
    return <div className="ra-fields"><div className="field"><label htmlFor={id + '-reason'}>采用原因</label>
      <textarea id={id + '-reason'} rows={3} maxLength={1000} value={draft.reason} readOnly={readOnly} disabled={busy}
        onChange={e => onChange({ ...draft, reason: e.target.value })} /></div>
      <div className="field"><label htmlFor={id + '-operator'}>{window.WorkbenchTerms.handler}</label><input id={id + '-operator'} maxLength={100} value={draft.declared_operator}
        readOnly={readOnly} disabled={busy} onChange={e => onChange({ ...draft, declared_operator: e.target.value })} />
        <small>填写这次由谁经办，不是登录账号。{!readOnly && memoryHint && ' ' + memoryHint}</small></div>
      {!readOnly && <label className="ra-consent"><input type="checkbox" checked={consent} disabled={busy} onChange={e => onConsent(e.target.checked)} />
        <span>我已核对正式计划、目标候选方案和完整范围，确认正式采用。</span></label>}</div>;
  }
  function Dialog({ value, intent, result, preview, draft, consent, busy, error, storageError, notice, onReadStorage, onChange, onConsent, onClose, onPreview, onConfirm, onLookup, onFinish, onCancelRejected, onNavigate }) {
    const pending = intent && intent.phase === 'pending' && !result, valid = preview && preview.validation.can_adopt === true;
    const canConfirm = valid && consent && draft.reason.trim() && draft.declared_operator.trim() && !pending && !storageError;
    return <Modal title={result ? '正式采用结果' : pending ? '查询上次采用结果' : '确认正式采用'} icon="check" onClose={onClose}
      footer={<><Button onClick={onClose}>{pending ? '关闭并保留上次操作' : result ? '关闭' : '取消'}</Button>
        {intent && intent.phase === 'rejected' && <Button disabled={busy || !!storageError} onClick={onCancelRejected}>结束本次未采用</Button>}
        {result ? <><Button icon="check" onClick={onFinish}>完成</Button><Button icon="arrow-right" className="btn primary"
          reason={typeof onNavigate === 'function' ? '' : window.WorkbenchTerms.outcomes.unavailable} onClick={() => onNavigate('analysis', { plan_ref: result.data.official_plan.plan_ref })}>进入正式计划</Button></>
          : pending ? <Button icon="refresh-cw" busy={busy} onClick={onLookup}>{window.WorkbenchTerms.actions.query_result}</Button>
            : <><Button icon="refresh-cw" busy={busy} disabled={!!storageError} onClick={onPreview}>重新预检</Button><Button icon="check" className="btn primary" busy={busy}
              disabled={!canConfirm} onClick={onConfirm}>确认正式采用</Button></>}</>}>
      <div className="modal-body ra-body">
        {error && <div className="ra-notice" role="alert">{error}</div>}{notice && <div className="ra-notice" role="status">{notice}</div>}
        {storageError && <Button icon="refresh-cw" disabled={busy} onClick={onReadStorage}>刷新上次操作记录</Button>}
        {result && <div className="ra-result" role="status">已确认：本次生成第 {result.data.official_plan.version} 版正式计划，共 {result.data.row_count} 道工序。
          <p>这是提交时的结果；当前状态请重新打开正式计划核对。</p></div>}
        {value.baseline && <Scope value={value} saved={!!intent && !valid} />}
        {preview && !valid && <div className="ra-notice" role="status">{preview.validation.issues.map((item, index) => <div key={index}>{item.message}</div>)}</div>}
        {!result && <Fields draft={draft} onChange={onChange} consent={consent} onConsent={onConsent} readOnly={!!pending} busy={busy} />}
        {result && <dl className="ra-scope"><div><dt>采用原因</dt><dd>{draft.reason}</dd></div><div><dt>{window.WorkbenchTerms.handler}</dt><dd>{draft.declared_operator}</dd></div></dl>}
        <Records value={value} intent={intent} result={result} />
      </div></Modal>;
  }
  function Styles() {
    return null;
  }
  window.RunAdoptionControls = { Button, Dialog, Styles };
})();
