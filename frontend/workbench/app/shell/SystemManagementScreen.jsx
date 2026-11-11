import React from '../shared/runtime/react.js';
import { STATES } from '../shared/runtime/environment.js';
import { SM_TOOL_ICONS, SMIcon } from '../shared/ui/icons.jsx';
import { TransferButton } from '../shared/ui/Button.jsx';

function SMStatus({ state }) {
  const [label, tone] = STATES[state];
  return <span className={'sm-status sm-tone-' + tone} data-state={state}>{label}</span>;
}

function SMUnavailable({ title, children }) {
  return <div className="sm-empty"><SMIcon name="folder-open" /><h4>{title}</h4><p>{children}</p></div>;
}

function SMExport({ disabled, onClick, children }) {
  return <TransferButton className="sm-button" kind="export" disabled={disabled} onClick={onClick}>{children}</TransferButton>;
}

const SystemManagementScreen = { SM_TOOL_ICONS, SMIcon, SMStatus, SMUnavailable, SMExport };
export { SM_TOOL_ICONS, SMIcon, SMStatus, SMUnavailable, SMExport, SystemManagementScreen };
export default SystemManagementScreen;
