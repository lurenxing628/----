(function () {
  'use strict';
  function CalibrationAdoptionAction({ detail, stale = false, onRefresh, adapter }) {
    const U = window.CalibrationAdoptionControls, s = window.CalibrationAdoptionState.useSession({ detail, stale, adapter });
    const label = s.saved ? s.saved.phase === 'committed' ? '查看采用结果' : s.saved.phase === 'pending' ? '查询上次采用结果' : '重新核对采用' : '预检采用';
    return <div className="plana calibration-adoption" data-calibration-adoption="true"><U.Styles />
      <U.Button icon={s.saved ? 'refresh-cw' : 'check'} aria-label={label} reasonDisplay="tooltip" reason={!s.saved && (!detail || stale) ? '请先读取有效的所选模板和完工记录。' : ''}
        onClick={() => s.setOpen(true)} aria-expanded={s.open}>{label}</U.Button>
      {s.saved && !s.open && <span className="cad-inline">{s.saved.phase === 'committed' ? '采用与锁定结果已恢复。' : '上次操作已保留，请先查询结果。'}</span>}
      {s.storageError && !s.open && <span className="cad-inline" role="alert">{s.storageError}<U.Button icon="refresh-cw" onClick={s.sync}>刷新上次操作记录</U.Button></span>}
      {s.open && <U.Dialog session={s} detail={detail} stale={stale} onRefresh={onRefresh} />}
    </div>;
  }
  window.CalibrationAdoptionAction = CalibrationAdoptionAction;
})();
