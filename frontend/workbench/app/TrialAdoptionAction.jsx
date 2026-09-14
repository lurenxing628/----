(function () {
  'use strict';
  // ResourceControls -> TrialAdoptionAPI -> TrialAdoptionState -> TrialAdoptionControls -> this file.
  // Main hook: renderAdoption(props); onAdopted receives the verified command receipt, not current-plan evidence.
  function Session(props) {
    const U = window.TrialAdoptionControls, s = window.TrialAdoptionState.useSession(props);
    const label = s.result ? '查看采用结果' : s.saved ? s.saved.phase === 'pending' ? '查询采用结果' : '重新核对采用' : '采用方案';
    const reason = s.saved ? '' : s.storageError || s.sourceError || (props.disabled ? '试调方案正在读取，或还有操作没确认结果，暂时不能开始采用。' : '');
    return <span className="plana trial-adoption-action" data-trial-adoption-action><U.Styles />
      <U.Button icon={s.saved ? 'refresh-cw' : 'check'} reason={reason} busy={s.busy && !s.saved} aria-expanded={s.open}
        onClick={() => { if (s.saved) s.setOpen(true); else s.inspect(); }}>{label}</U.Button>
      {!s.open && s.saved && <span className="ta-inline">{s.result ? '提交时的采用结果已恢复。' : '上次的采用操作还在，请先查询结果。'}</span>}
      {!s.open && s.storageError && <span className="ta-inline" role="alert">{s.storageError}<U.Button icon="refresh-cw" onClick={s.sync}>刷新上次操作记录</U.Button></span>}
      {!s.open && !s.saved && s.notice && <span className="ta-inline" role="status">{s.notice}</span>}
      {s.open && <U.Dialog session={s} scenarioRef={props.scenarioRef} onNavigate={props.onNavigate} name={props.data && props.data.name} />}
    </span>;
  }
  window.TrialAdoptionAction = function TrialAdoptionAction(props) { return <Session key={props.scenarioRef || 'missing'} {...props} />; };
})();
