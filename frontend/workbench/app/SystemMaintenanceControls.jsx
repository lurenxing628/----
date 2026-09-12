(function () {
  'use strict';
  const A = window.SystemMaintenanceAPI;
  function Button({ children, icon, className = 'btn', ...props }) {
    const label = typeof children === 'string' ? children : props['aria-label'];
    return <window.ResourceControls.Button {...props} icon={icon === 'rotate-ccw' ? undefined : icon === 'save' ? 'check' : icon === 'trash-2' ? 'x' : icon}
      title={props.reason || props.title || label} aria-label={props['aria-label'] || (props.reason && label ? label + '：' + props.reason : undefined)}
      reasonDisplay={props.reason ? 'inline' : props.reasonDisplay} className={className + ' sm-button' + (children ? '' : ' sm-icon-button')}>{icon === 'rotate-ccw' && <SMIcon name="rotate-ccw" />}{children}</window.ResourceControls.Button>;
  }
  function Styles() {
    return null;
  }
  function ErrorBox({ error }) {
    return error ? <window.WorkbenchError error={error} /> : null;
  }
  function useRead(api, kind, input, revision, enabled = true) {
    const [state, setState] = React.useState({ data: null, error: null, loading: true });
    const signature = JSON.stringify(input);
    React.useEffect(() => {
      if (!enabled) { setState({ data: null, error: null, loading: false }); return; }
      const controller = new AbortController(); setState({ data: null, error: null, loading: true });
      api.read(kind, input, controller.signal).then(data => { if (!controller.signal.aborted) setState({ data, error: null, loading: false }); })
        .catch(error => { if (!controller.signal.aborted) setState({ data: null, error, loading: false }); });
      return () => controller.abort();
    }, [api, kind, signature, revision, enabled]);
    return state;
  }
  function Confirm({ action, row, reason, onClose, onConfirm }) {
    const [checked, setChecked] = React.useState(false), [typed, setTyped] = React.useState('');
    const destructive = action !== 'create', ready = !destructive || checked && (action !== 'restore' || typed === '恢复');
    return <window.ResourceControls.Modal title={A.actions[action]} icon={action === 'create' ? 'plus' : action === 'delete' ? 'x' : 'history'} onClose={onClose}
      footer={<><Button onClick={onClose}>取消</Button><Button icon="check" className="btn primary" reason={reason} disabled={!ready} onClick={onConfirm}>确认{action === 'create' ? '创建' : action === 'delete' ? '删除' : '恢复'}</Button></>}>
      <div className="modal-b form scroll" style={{ overflowWrap: 'anywhere' }}>
        {row && <p><strong>{row.filename}</strong><br />文件修改时间 {window.WorkbenchFormat.dateTime(row.time)} · {row.size_bytes} 字节<br />文件存在，尚无本次完整性校验证据。</p>}
        <p>{action === 'create' ? '创建本机数据库备份。结果以外置维护记录为准。' : action === 'delete' ? '仅删除此备份文件，删除后不能撤销。' : '将用所选备份替换当前数据库。恢复前保护副本、校验和失败回滚均由后端执行。'}</p>
        {action === 'restore' && <p className="sm-notice">一旦受理恢复，业务操作将停用。即使恢复成功或已回滚，也须关闭整个软件再启动；只刷新浏览器不算重启。</p>}
        {destructive && <label className="sm-inline-label"><input type="checkbox" checked={checked} onChange={event => setChecked(event.target.checked)} />我已核对所选文件与操作影响</label>}
        {action === 'restore' && <label className="field" style={{ marginTop: 16 }}><span>输入“恢复”确认</span><input value={typed} onChange={event => setTyped(event.target.value)} /></label>}
        {reason && <ErrorBox error={reason} />}
      </div>
    </window.ResourceControls.Modal>;
  }
  const labels = { accepted: '已受理', checking: '检查中', protecting: '创建保护副本', restoring: '恢复中', verifying: '校验中', rolling_back: '回滚中',
    succeeded: '已完成', failed: '操作失败', rolled_back: '恢复失败，已回滚', rollback_failed: '回滚失败，需人工核查', recovery_required: '需人工恢复核查' };
  function Outcome({ command }) {
    const { intent, result, error, busy, storageError } = command;
    if (!intent && !storageError) return null;
    const op = result && result.kind === 'file_operation' && result.operation;
    return <section className="sm-section sm-maintenance-outcome" aria-label="维护原请求结果" style={{ padding: '12px 20px', background: 'var(--ui-card-bg)', borderBottom: '1px solid var(--ui-border)', overflowWrap: 'anywhere' }}>
      <div className="sm-section-head"><h3>{intent ? intent.summary : '待核实记录不可用'}</h3><div className="sm-actions">
        {intent && !(result && result.kind === 'rejected') && <Button icon="refresh-cw" busy={busy} onClick={command.lookup}>核实原请求</Button>}
        {result && result.terminal && !command.suspended && <Button icon="check" disabled={busy} onClick={command.acknowledge}>确认结果</Button>}
      </div></div>
      {intent && <window.WorkbenchReference label="原请求编号" value={intent.request_key} />}
      <ErrorBox error={storageError || error} />
      {busy && <p role="status">正在等待维护结果，未重新提交。</p>}
      {op ? <div role="status"><p><strong className={op.state === 'succeeded' ? 'sm-tone-success' : 'sm-tone-warning'}>{labels[op.state]}</strong> · {op.message}</p>
        <window.WorkbenchReference label="维护记录与结果代码" entries={{ '维护编号': op.job_ref, '结果代码': op.code }} />
        <p>更新时间：{window.WorkbenchFormat.dateTime(op.updated_at)}<br />业务审计：{op.audit_persisted ? '已留存' : '未确认留存'}{op.replayed ? ' · 查询原结果' : ''}</p>
        {op.filename && <p>目标文件：{op.filename}</p>}{op.protection_filename && <p>保护副本：{op.protection_filename}</p>}
        <details className="sm-rules"><summary>维护阶段</summary>{op.history.map((step, index) => <p key={index}>{window.WorkbenchFormat.dateTime(step.time)} · {labels[step.state]}</p>)}</details>
      </div> : result && result.kind === 'config' ? <div role="status"><p>{result.command.result === 'committed' ? '八项维护配置已保存，事务和审计已留存。' : '配置没有变化，已留存无变更回执；未新增业务审计。'}</p>
        <window.WorkbenchReference label="配置回执" value={result.command.receipt_ref} />{result.command.replayed && <p>查询原结果</p>}</div> : result && result.kind === 'rejected' ? <p role="status">后端明确拒绝，本次未提交。核对错误后可确认结果。</p> : null}
      {intent && !(result && result.terminal) && <p className="sm-note">{result && result.kind === 'not_recorded' ? result.message : '原操作仍待核实。'} 查不到结果不代表未执行；不会更换请求键重做。{intent.action === 'restore' ? ' 恢复未核实前暂停读取其他数据库信息。' : ''}</p>}
    </section>;
  }
  function Preferences({ theme, onSetTheme, pageSize, onPageSize, compact, onCompact }) {
    return <section className="sm-section sm-preferences"><div className="sm-section-head"><h3>页面偏好</h3></div><div className="sm-session-settings">
      <fieldset className="sm-choice"><legend>主题</legend>{[['light', '浅色'], ['dark', '深色']].map(([value, label]) => <label key={value}>
        <input type="radio" name="system-maintenance-theme" checked={theme === value} disabled={typeof onSetTheme !== 'function'} onChange={() => onSetTheme(value)} />{label}</label>)}</fieldset>
      <label className="sm-inline-label">每页条数<select value={pageSize} onChange={event => onPageSize(Number(event.target.value))}>{[10, 25, 50].map(size => <option key={size} value={size}>{size} 条</option>)}</select></label>
      <label className="sm-inline-label" title="应用于全工作台表格"><input type="checkbox" checked={compact} onChange={event => onCompact(event.target.checked)} />紧凑行距</label>
    </div></section>;
  }
  window.SystemMaintenanceControls = { Button, Styles, ErrorBox, useRead, Confirm, Outcome, Preferences };
})();
