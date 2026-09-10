(function () {
  'use strict';
  // ResourceControls -> TrialAdoptionAPI -> TrialAdoptionState -> TrialAdoptionControls -> this file.
  // Main hook: renderAdoption(props); onAdopted receives the verified command receipt, not current-plan evidence.
  function Session(props) {
    const U = window.TrialAdoptionControls, s = window.TrialAdoptionState.useSession(props);
    const label = s.result ? '查看场景采用回执' : s.saved ? s.saved.phase === 'pending' ? '核实场景采用结果' : '重新核对场景采用' : '正式采用';
    const reason = s.saved ? '' : s.storageError || s.sourceError || (props.disabled ? '原场景正在读取或有待核实操作，新的采用已暂停。' : '');
    return <span className="plana trial-adoption-action" data-trial-adoption-action><U.Styles />
      <U.Button icon={s.saved ? 'refresh-cw' : 'check'} reason={reason} busy={s.busy && !s.saved} aria-expanded={s.open}
        onClick={() => { if (s.saved) s.setOpen(true); else s.inspect(); }}>{label}</U.Button>
      {!s.open && s.saved && <span className="ta-inline">{s.result ? '提交时的采用回执已恢复。' : '原场景请求已保留，请先核实。'}</span>}
      {!s.open && s.storageError && <span className="ta-inline" role="alert">{s.storageError}<U.Button icon="refresh-cw" onClick={s.sync}>重读恢复记录</U.Button></span>}
      {!s.open && !s.saved && s.notice && <span className="ta-inline" role="status">{s.notice}</span>}
      {s.open && <U.Dialog session={s} scenarioRef={props.scenarioRef} onNavigate={props.onNavigate} />}
    </span>;
  }
  window.TrialAdoptionAction = function TrialAdoptionAction(props) { return <Session key={props.scenarioRef || 'missing'} {...props} />; };
})();
