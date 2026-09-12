(function () {
  'use strict';
  const { Icon, ErrorBox, Modal, Issues } = window.ResourceControls;
  const iconAliases = { 'arrow-left': 'chevron-left', 'file-spreadsheet': 'file-input', 'file-plus': 'plus', info: 'history', 'chevron-up': 'fold-vertical' };
  function Button({ icon, ...props }) { return <window.ResourceControls.Button {...props} icon={iconAliases[icon] || icon} />; }
  function Styles() { return null; }
  function State({ value }) { return <span className={'field-state ' + value}>{window.FieldContract.states[value] || '未读取'}</span>; }
  function Feedback({ command, onDone, excludePaths = [] }) {
    return <div aria-live="polite"><ErrorBox error={command.error} excludePaths={excludePaths} />
      {command.locked && <div className="field-note">{command.phase === 'sending' ? '正在保存，请保留当前页面。' : '结果待核实，已保留原请求。'} <Button icon="refresh-cw" disabled={command.phase !== 'pending'} onClick={command.check}>核实原请求</Button></div>}
      {command.phase === 'done' && <div className="field-note">{command.result.result === 'unchanged' ? '内容未变化。' : '已保存。'} <Button icon="check" onClick={onDone}>重读已确认结果</Button></div>}
    </div>;
  }
  window.FieldControls = { Styles, Button, Icon, ErrorBox, Modal, Issues, State, Feedback };
})();
