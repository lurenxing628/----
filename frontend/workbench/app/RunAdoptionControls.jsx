(function () {
  'use strict';
  const { Button, Modal } = window.ResourceControls;
  function Scope({ value, saved }) {
    return <><dl className="ra-scope"><div><dt>{saved ? '原请求核对的正式版本' : '当前正式版本（本次预览）'}</dt><dd>{value.baseline.version === null ? '尚无正式计划' : 'v' + value.baseline.version}</dd></div>
      <div><dt>目标候选</dt><dd>当前核对的完整候选<window.WorkbenchReference value={value.candidate_ref} /></dd></div><div><dt>采用工序</dt><dd>{value.task_count} 道</dd></div>
      <div><dt>采用范围</dt><dd>完整候选及全部当前正式安排</dd></div></dl>
      <p className="ra-note">采用会新增正式版本，保留旧版本和已有执行记录；不是只采用当前筛选出的工序。</p></>;
  }
  function Records({ value, intent, result }) {
    return <details className="ra-records wb-ref"><summary>记录信息</summary>
      <div>候选编号：{value.candidate_ref}</div>{value.run_ref && <div>运行编号：{value.run_ref}</div>}
      {value.baseline && value.baseline.plan_ref && <div>原正式方案编号：{value.baseline.plan_ref}</div>}
      {intent && <div>请求编号：{intent.request_key}</div>}{result && <><div>回执编号：{result.receipt_ref}</div><div>新正式方案编号：{result.data.official_plan.plan_ref}</div></>}
    </details>;
  }
  function Fields({ draft, onChange, consent, onConsent, readOnly, busy }) {
    const id = React.useId();
    return <div className="ra-fields"><div className="field"><label htmlFor={id + '-reason'}>采用原因</label>
      <textarea id={id + '-reason'} rows={3} maxLength={1000} value={draft.reason} readOnly={readOnly} disabled={busy}
        onChange={e => onChange({ ...draft, reason: e.target.value })} /></div>
      <div className="field"><label htmlFor={id + '-operator'}>声明人</label><input id={id + '-operator'} maxLength={100} value={draft.declared_operator}
        readOnly={readOnly} disabled={busy} onChange={e => onChange({ ...draft, declared_operator: e.target.value })} />
        <small>记录本次业务声明，不代表登录或认证身份。</small></div>
      {!readOnly && <label className="ra-consent"><input type="checkbox" checked={consent} disabled={busy} onChange={e => onConsent(e.target.checked)} />
        <span>我已核对正式版本、目标候选和完整范围，确认正式采用。</span></label>}</div>;
  }
  function Dialog({ value, intent, result, preview, draft, consent, busy, error, storageError, notice, onReadStorage, onChange, onConsent, onClose, onPreview, onConfirm, onLookup, onFinish, onCancelRejected, onNavigate }) {
    const pending = intent && intent.phase === 'pending' && !result, valid = preview && preview.validation.can_adopt === true;
    const canConfirm = valid && consent && draft.reason.trim() && draft.declared_operator.trim() && !pending && !storageError;
    return <Modal title={result ? '正式采用回执' : pending ? '核实原采用请求' : '确认正式采用'} icon="check" onClose={onClose}
      footer={<><Button onClick={onClose}>{pending ? '关闭并保留请求' : result ? '关闭' : '取消'}</Button>
        {intent && intent.phase === 'rejected' && <Button disabled={busy || !!storageError} onClick={onCancelRejected}>结束本次未采用</Button>}
        {result ? <><Button icon="check" onClick={onFinish}>完成核实</Button><Button icon="arrow-right" className="btn primary"
          reason={typeof onNavigate === 'function' ? '' : '正式方案页面尚未接入。'} onClick={() => onNavigate('analysis', { plan_ref: result.data.official_plan.plan_ref })}>进入正式方案</Button></>
          : pending ? <Button icon="refresh-cw" busy={busy} onClick={onLookup}>查询原请求</Button>
            : <><Button icon="refresh-cw" busy={busy} disabled={!!storageError} onClick={onPreview}>重新预览</Button><Button icon="check" className="btn primary" busy={busy}
              disabled={!canConfirm} onClick={onConfirm}>确认正式采用</Button></>}</>}>
      <div className="modal-body ra-body">
        {error && <div className="ra-notice" role="alert">{error}</div>}{notice && <div className="ra-notice" role="status">{notice}</div>}
        {storageError && <Button icon="refresh-cw" disabled={busy} onClick={onReadStorage}>重读恢复记录</Button>}
        {result && <div className="ra-result" role="status">已核实：本次生成正式版本 v{result.data.official_plan.version}，共 {result.data.row_count} 道工序。
          <p>这是提交时的回执；当前正式状态以重新打开的正式方案为准。</p></div>}
        {value.baseline && <Scope value={value} saved={!!intent && !valid} />}
        {preview && !valid && <div className="ra-notice" role="status">{preview.validation.issues.map((item, index) => <div key={index}>{item.message}</div>)}</div>}
        {!result && <Fields draft={draft} onChange={onChange} consent={consent} onConsent={onConsent} readOnly={!!pending} busy={busy} />}
        {result && <dl className="ra-scope"><div><dt>采用原因</dt><dd>{draft.reason}</dd></div><div><dt>声明人</dt><dd>{draft.declared_operator}</dd></div></dl>}
        <Records value={value} intent={intent} result={result} />
      </div></Modal>;
  }
  function Styles() {
    return null;
  }
  window.RunAdoptionControls = { Button, Dialog, Styles };
})();
