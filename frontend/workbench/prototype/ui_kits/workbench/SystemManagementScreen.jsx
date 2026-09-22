// Host contract: theme + onToggleTheme (or onSetTheme). No backend adapter or production actions.
// Local Lucide 1.8.0 nodes; license: assets/lucide-LICENSE. No runtime package dependency.
const SM_TOOL_ICONS = {
  'refresh-cw': [['path', { d: 'M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8' }], ['path', { d: 'M21 3v5h-5' }], ['path', { d: 'M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16' }], ['path', { d: 'M8 16H3v5' }]],
  'rotate-ccw': [['path', { d: 'M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8' }], ['path', { d: 'M3 3v5h5' }]]
};
function SMIcon({ name }) {
  const nodes = SM_TOOL_ICONS[name] || (window.APSFieldReports && window.APSFieldReports.iconNodes && window.APSFieldReports.iconNodes[name]);
  if (!nodes) return null;
  return <svg className="sm-icon" data-sm-icon={name} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {nodes.map(([tag, attrs], index) => React.createElement(tag, { ...attrs, key: index }))}
  </svg>;
}
function SMStatus({ state }) {
  const [label, tone] = window.APSSystemWorkbench.STATES[state] || ['未知', 'neutral'];
  return <span className={'sm-status sm-tone-' + tone} data-state={state}>{label}</span>;
}
function SMUnavailable({ title, children }) {
  return <div className="sm-empty"><SMIcon name="folder-open" /><h4>{title}</h4><p>{children}</p></div>;
}
function SMExport({ disabled, onClick, children }) {
  const { TransferButton, ControlButton } = window.APSWorkbenchUI;
  const ready = window.APSFieldReports && window.APSFieldReports.iconNodes && window.APSFieldReports.iconNodes['file-output'];
  return ready ? <TransferButton className="sm-button" kind="export" disabled={disabled} onClick={onClick}>{children}</TransferButton> :
    <ControlButton className="sm-button" disabled title="缺少导出图标，暂时不能导出">{children}</ControlButton>;
}

function SystemManagementScreen({ theme, onToggleTheme, onSetTheme }) {
  const model = window.APSSystemWorkbench, { MetricStrip, Metric, ControlButton } = window.APSWorkbenchUI;
  const inspect = () => model.inspectEnvironment(window, { theme, onToggleTheme, onSetTheme });
  const [report, setReport] = React.useState(null), [notice, setNotice] = React.useState('');
  React.useEffect(() => { setReport(inspect()); }, [theme, onToggleTheme, onSetTheme]);
  const ready = report ? report.checks.filter(item => item.status === 'available').length : 0;
  const exportDiagnostic = () => {
    try {
      const current = inspect();
      model.download(window, '当前原型诊断.json', 'application/json;charset=utf-8', model.diagnosticJSON(current));
      setNotice('已生成当前原型诊断 JSON；是否保存以浏览器下载结果为准。');
    } catch (_) {
      setNotice('导出没有完成，本机数据没有任何改动。请用 Chrome 打开后重试。');
    }
  };
  return <div className="sm-workbench" data-source="prototype">
    <header className="sm-header"><div><h2>系统管理</h2><p>页面环境与本机维护入口</p></div><div className="sm-actions">
      <ControlButton className="sm-button sm-icon-button" size="sm" title="重新检查" aria-label="重新检查" onClick={() => { setReport(inspect()); setNotice('已重新检查当前页面依赖。'); }}><SMIcon name="refresh-cw" /></ControlButton>
      <SMExport disabled={!report} onClick={exportDiagnostic}>导出当前诊断 JSON</SMExport>
    </div></header>
    <p className="sm-source-note">此原型不读取本机数据库、备份或日志；正式页面只显示本机程序读到的数据。</p>
    <MetricStrip columns={4} className="sm-metrics"><Metric label="当前页面检查" value={report ? ready + ' / ' + report.checks.length : '待检查'} helper="仅页面依赖与资源" />
      <Metric label="本机数据读取" value="未连接" helper="未发起本机状态读取" /><Metric label="数据库状态" value="未知" helper="此原型不读取本机数据" /><Metric label="备份校验" value="未校验" helper="没有本机校验结果" /></MetricStrip>
    {notice && <p className="sm-notice" role="status">{notice}</p>}
    {!report ? <SMUnavailable title="页面环境尚未检查">请点「重新检查」。</SMUnavailable> : <section className="sm-section sm-environment">
      <div className="sm-section-head"><h3>页面环境自检</h3><span className="sm-meta">不代表数据库或备份健康</span></div>
      <div className="wb-table-shell wb-table-frame"><table className="wb-table sm-table sm-check-table"><caption className="wb-visually-hidden">当前页面环境检查</caption>
        <thead><tr><th scope="col">检查项</th><th scope="col">结果</th><th scope="col">检查范围</th></tr></thead>
        <tbody>{report.checks.map(item => <tr key={item.id}><th scope="row">{item.label}</th><td><SMStatus state={item.status} /></td><td>{item.detail}</td></tr>)}</tbody>
      </table></div>
    </section>}
  </div>;
}
window.SystemManagementScreen = SystemManagementScreen;
