(function () {
  'use strict';
  function CalibrationAdoptionAction({ detail, stale = false, onRefresh, adapter }) {
    const U = window.CalibrationAdoptionControls, s = window.CalibrationAdoptionState.useSession({ detail, stale, adapter });
    const label = s.saved ? s.saved.phase === 'committed' ? '查看采用回执' : s.saved.phase === 'pending' ? '核实原采纳请求' : '重新核对采用' : '预览采用';
    return <div className="plana calibration-adoption" data-calibration-adoption="true"><U.Styles />
      <U.Button icon={s.saved ? 'refresh-cw' : 'check'} aria-label={label} reason={!s.saved && (!detail || stale) ? '请先读取有效的所选模板和样本。' : ''}
        onClick={() => s.setOpen(true)} aria-expanded={s.open}>{label}</U.Button>
      {s.saved && !s.open && <span className="cad-inline">{s.saved.phase === 'committed' ? '采用与锁定回执已恢复。' : '原请求已保留，请先核实。'}</span>}
      {s.storageError && !s.open && <span className="cad-inline" role="alert">{s.storageError}<U.Button icon="refresh-cw" onClick={s.sync}>重读恢复记录</U.Button></span>}
      {s.open && <U.Dialog session={s} detail={detail} stale={stale} onRefresh={onRefresh} />}
    </div>;
  }
  window.CalibrationAdoptionAction = CalibrationAdoptionAction;
})();
