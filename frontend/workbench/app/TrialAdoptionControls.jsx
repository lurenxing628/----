(function () {
  'use strict';
  const { Button, Modal } = window.ResourceControls;
  function Scope({ value, label, name }) {
    return <><dl className="ta-scope"><div><dt>{label}</dt><dd>{value.baseline.version === null ? '尚无正式计划' : '第 ' + value.baseline.version + ' 版'}</dd></div>
      <div><dt>采用完整范围</dt><dd>完整试调方案，共 {value.task_count} 道工序</dd></div>
      <div><dt>试调方案</dt><dd>{name || '未命名试调方案'}</dd></div></dl>
      <p className="ta-note">将完整试调方案采用为新一版正式计划，保留历史版本。恢复旧安排需重新排产并采用。</p></>;
  }
  function Fields({ session: s }) {
    const id = React.useId(), frozen = !!s.saved, memoryHint = window.WorkbenchHandlerMemory.hint(s.draft.declared_operator);
    return <div className="ta-fields"><div className="field"><label htmlFor={id + '-reason'}>采用原因</label>
      <textarea id={id + '-reason'} rows={3} maxLength={1000} value={s.draft.reason} readOnly={frozen} disabled={s.busy}
        onChange={e => s.change({ ...s.draft, reason: e.target.value })} /></div>
      <div className="field"><label htmlFor={id + '-operator'}>{window.WorkbenchTerms.handler}</label><input id={id + '-operator'} maxLength={100} value={s.draft.declared_operator}
        readOnly={frozen} disabled={s.busy} onChange={e => s.change({ ...s.draft, declared_operator: e.target.value })} />
        {!frozen && memoryHint && <small>{memoryHint}</small>}</div>
      {(!s.saved || s.saved.phase === 'rejected') && <label className="ta-consent"><input type="checkbox" checked={s.consent}
        disabled={s.busy || s.disabled || !s.preview || !s.preview.validation.can_adopt || !!s.storageError} onChange={e => s.setConsent(e.target.checked)} />
        <span>确认将完整试调方案正式采用。</span></label>}
      {frozen && <small>已提交的内容暂不可修改。</small>}</div>;
  }
  function Records({ value, saved, result }) {
    return <details className="ta-records wb-ref"><summary>编号与保存记录</summary><div>试调方案编号：{value.scenario_ref}</div>
      {value.draft_ref && <div>试调草稿编号：{value.draft_ref}</div>}{value.baseline && value.baseline.plan_ref && <div>当时的正式计划编号：{value.baseline.plan_ref}</div>}
      {saved && <div>操作编号：{saved.request_key}</div>}{result && <><div>结果编号：{result.receipt_ref}</div><div>新正式计划编号：{result.data.official_plan.plan_ref}</div></>}</details>;
  }
  function Dialog({ session: s, scenarioRef, onNavigate, name }) {
    const pending = s.saved && s.saved.phase === 'pending', rejected = s.saved && s.saved.phase === 'rejected', valid = s.preview && s.preview.validation.can_adopt;
    const value = valid ? s.preview : s.saved ? s.saved.preview : s.original || { scenario_ref: scenarioRef || '未指定' };
    const other = s.saved && s.saved.scenario_ref !== scenarioRef;
    const blocked = s.disabled || !!s.sourceError || !!s.storageError || !!other;
    const canConfirm = valid && s.consent && s.draft.reason.trim() && s.draft.declared_operator.trim() && !pending && !blocked;
    return <Modal title={s.result ? '试调方案采用结果' : pending ? '查询上次采用结果' : '确认正式采用试调方案'} icon="check" onClose={s.close}
      footer={<><Button onClick={s.close}>{pending ? '关闭并保留这次操作' : s.result ? '关闭' : '取消'}</Button>
        {rejected && <Button disabled={s.busy || !!s.storageError} onClick={s.finish}>结束本次未采用</Button>}
        {s.result ? <><Button icon="refresh-cw" busy={s.busy} disabled={!!s.storageError} onClick={s.lookup}>查询结果</Button>
          <Button icon="check" disabled={s.busy || !!s.storageError} onClick={s.finish}>完成</Button><Button icon="arrow-right" className="btn primary"
            reason={typeof onNavigate === 'function' ? '' : window.WorkbenchTerms.outcomes.unavailable} onClick={() => onNavigate('analysis', { plan_ref: s.result.data.official_plan.plan_ref })}>进入正式计划</Button></>
          : pending ? <Button icon="refresh-cw" busy={s.busy} disabled={!!s.storageError} onClick={s.lookup}>查询结果</Button>
            : <><Button icon="refresh-cw" busy={s.busy} disabled={blocked} onClick={s.inspect}>重新预检</Button>
              <Button icon="check" className="btn primary" busy={s.busy} disabled={!canConfirm} onClick={s.submit}>确认正式采用</Button></>}</>}>
      <div className="modal-body ta-body">
        {(s.storageError || s.error) && <div className="ta-notice" role="alert">{s.storageError || s.error}</div>}
        {s.storageError && <Button icon="refresh-cw" disabled={s.busy} onClick={s.sync}>刷新上次操作记录</Button>}
        {other && <div className="ta-notice" role="status">另一个试调方案的采用结果待确认，请先查询结果。</div>}
        {s.notice && <div className="ta-notice" role="status">{s.notice}</div>}
        {!pending && !s.result && (s.disabled || s.sourceError) && <div className="ta-notice" role="status">{s.sourceError || '试调方案正在读取，或还有操作没确认结果，暂时不能开始采用。'}</div>}
        {s.result && <div className="ta-result" role="status">已确认：这次生成正式计划第 {s.result.data.official_plan.version} 版，共 {s.result.data.row_count} 道工序。
          <p>当前正式计划可在计划列表查看。</p>{s.result.replayed && <p>已查询到上次采用结果。</p>}</div>}
        {value.baseline && <Scope value={value} name={name} label={valid ? '这次预检核对的正式计划' : s.saved ? '上次提交核对的正式计划' : '试调方案保存时的正式计划'} />}
        {s.preview && !valid && <div className="ta-notice" role="status">{s.preview.validation.issues.map((v, i) => <div key={i}>{v.message}</div>)}</div>}
        {rejected && !s.preview && <p className="ta-note">上次采用未通过，请重新检查并确认。</p>}
        {!s.result ? <Fields session={s} /> : <dl className="ta-scope"><div><dt>采用原因</dt><dd>{s.saved.input.reason}</dd></div><div><dt>经办人</dt><dd>{s.saved.input.declared_operator}</dd></div></dl>}
        <Records value={value} saved={s.saved} result={s.result} />
      </div></Modal>;
  }
  function Styles() {
    return null;
  }
  window.TrialAdoptionControls = { Button, Dialog, Styles };
})();
