(function () {
  'use strict';
  const { Button } = window.ResourceControls;
  function ProcessFileButtons({ disabled, hoursOnly = false, routeOnly = false, onAction }) {
    return <>{(hoursOnly ? [['hours', '工时定额']] : routeOnly ? [['route', '工艺路线']] : [['route', '工艺路线'], ['hours', '工时定额']]).map(([kind, label]) => <React.Fragment key={kind}>
      <Button transfer="import" disabled={disabled} onClick={() => onAction(kind, 'import')}>{'导入' + label}</Button>
      <Button transfer="export" disabled={disabled} onClick={() => onAction(kind, 'export')}>{'导出' + label}</Button>
    </React.Fragment>)}</>;
  }
  window.ProcessFileButtons = ProcessFileButtons;
})();
