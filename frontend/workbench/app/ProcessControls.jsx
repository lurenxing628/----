(function () {
  'use strict';
  const { Button } = window.ResourceControls, P = window.APSProcessContract;
  function ProcessFileButtons({ capabilities, disabled, hoursOnly = false, routeOnly = false, onAction }) {
    return <>{(hoursOnly ? [['hours', '工时定额']] : routeOnly ? [['route', '工艺路线']] : [['route', '工艺路线'], ['hours', '工时定额']]).map(([kind, label]) => <React.Fragment key={kind}>
      <Button transfer="import" reason={P.reason(capabilities, 'import', typeof onAction === 'function')} disabled={disabled} onClick={() => onAction(kind, 'import')}>{'导入' + label}</Button>
      <Button transfer="export" reason={P.reason(capabilities, 'export', typeof onAction === 'function')} disabled={disabled} onClick={() => onAction(kind, 'export')}>{'导出' + label}</Button>
    </React.Fragment>)}</>;
  }
  window.ProcessFileButtons = ProcessFileButtons;
})();
