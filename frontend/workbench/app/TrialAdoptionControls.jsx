(function () {
  'use strict';
  const { Button, Modal } = window.ResourceControls;
  function Scope({ value, label, name }) {
    return <><dl className="ta-scope"><div><dt>{label}</dt><dd>{value.baseline.version === null ? '尚无正式计划' : '第 ' + value.baseline.version + ' 版'}</dd></div>
      <div><dt>采用完整范围</dt><dd>完整试调方案，共 {value.task_count} 道工序</dd></div>
      <div><dt>试调方案</dt><dd>{name || '未命名试调方案'}</dd></div></dl>
      <p className="ta-note">采用完整的试调方案，不受当前筛选或显示范围影响；会新增一版正式计划。旧版本和报工记录都会保留，可在计划列表查看和导出；如需恢复旧安排，需要重新排产并再采用一版。</p></>;
  }
  function Fields({ session: s }) {
    const id = React.useId(), frozen = !!s.saved, memoryHint = window.WorkbenchHandlerMemory.hint(s.draft.declared_operator);
    return <div className="ta-fields"><div className="field"><label htmlFor={id + '-reason'}>采用原因</label>
      <textarea id={id + '-reason'} rows={3} maxLength={1000} value={s.draft.reason} readOnly={frozen} disabled={s.busy}
        onChange={e => s.change({ ...s.draft, reason: e.target.value })} /></div>
      <div className="field"><label htmlFor={id + '-operator'}>{window.WorkbenchTerms.handler}</label><input id={id + '-operator'} maxLength={100} value={s.draft.declared_operator}
        readOnly={frozen} disabled={s.busy} onChange={e => s.change({ ...s.draft, declared_operator: e.target.value })} />
        <small>填写这次由谁经办，不是登录账号。{!frozen && memoryHint && ' ' + memoryHint}</small></div>
      {(!s.saved || s.saved.phase === 'rejected') && <label className="ta-consent"><input type="checkbox" checked={s.consent}
        disabled={s.busy || s.disabled || !s.preview || !s.preview.validation.can_adopt || !!s.storageError} onChange={e => s.setConsent(e.target.checked)} />
        <span>我已核对试调方案、试调草稿、正式计划和完整范围，确认正式采用。</span></label>}
      {frozen && <small>这次提交已绑定上面的试调方案和确认内容，改动后不能沿用。</small>}</div>;
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
        {other && <div className="ta-notice" role="status">上次操作属于另一个试调方案，请先查询那条记录的结果；不能用在当前试调方案上。</div>}
        {s.notice && <div className="ta-notice" role="status">{s.notice}</div>}
        {!pending && !s.result && (s.disabled || s.sourceError) && <div className="ta-notice" role="status">{s.sourceError || '试调方案正在读取，或还有操作没确认结果，暂时不能开始采用。'}</div>}
        {s.result && <div className="ta-result" role="status">已确认：这次生成正式计划第 {s.result.data.official_plan.version} 版，共 {s.result.data.row_count} 道工序。
          <p>这是提交时的结果，不代表现在的正式计划。最新情况请重新打开正式计划查看。</p>{s.result.replayed && <p>按同一个操作编号读到的是上次的结果，没有新增正式计划版本。</p>}</div>}
        {value.baseline && <Scope value={value} name={name} label={valid ? '这次预检核对的正式计划' : s.saved ? '上次提交核对的正式计划' : '试调方案保存时的正式计划'} />}
        {s.preview && !valid && <div className="ta-notice" role="status">{s.preview.validation.issues.map((v, i) => <div key={i}>{v.message}</div>)}</div>}
        {rejected && !s.preview && <p className="ta-note">上次提交被拒绝，没有采用。请重新预检并再次勾选确认，仍然用同一个操作编号和确认内容。</p>}
        {!s.result ? <Fields session={s} /> : <dl className="ta-scope"><div><dt>采用原因</dt><dd>{s.saved.input.reason}</dd></div><div><dt>经办人</dt><dd>{s.saved.input.declared_operator}</dd></div></dl>}
        <Records value={value} saved={s.saved} result={s.result} />
      </div></Modal>;
  }
  function Styles() {
    return null;
  }
  window.TrialAdoptionControls = { Button, Dialog, Styles };
})();
