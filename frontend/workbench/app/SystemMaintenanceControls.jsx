(function () {
  'use strict';
  const A = window.SystemMaintenanceAPI;
  // 恢复各阶段的叫法只在 SystemRestoreStatus.labels 维护一份；后端 web/bootstrap/workbench_system_restore_view.py 与之逐字对齐。
  const labels = window.SystemRestoreStatus.labels;
  function Button({ children, icon, className = 'btn', ...props }) {
    const label = typeof children === 'string' ? children : props['aria-label'];
    return <window.ResourceControls.Button {...props} icon={icon === 'rotate-ccw' ? undefined : icon === 'save' ? 'check' : icon}
      title={props.reason || props.title || label} aria-label={props['aria-label'] || (props.reason && label ? label + '：' + props.reason : undefined)}
      reasonDisplay={props.reason ? 'inline' : props.reasonDisplay} className={className + ' sm-button' + (children ? '' : ' sm-icon-button')}>{icon === 'rotate-ccw' && <SMIcon name="rotate-ccw" />}{children}</window.ResourceControls.Button>;
  }
  function ErrorBox({ error }) {
    return error ? <window.WorkbenchError error={error} /> : null;
  }
  function useRead(api, kind, input, revision, enabled = true) {
    const signature = JSON.stringify(input);
    const query = window.APSResourceSession.useQuery(signal => api.read(kind, input, signal), [api, kind, signature, revision], enabled);
    return { data: query.result, error: query.error, loading: query.loading };
  }
  function Confirm({ action, row, reason, onClose, onConfirm }) {
    const [checked, setChecked] = React.useState(false), [typed, setTyped] = React.useState('');
    const destructive = action !== 'create', ready = !destructive || checked && (action !== 'restore' || typed === '恢复');
    return <window.ResourceControls.Modal title={A.actions[action]} icon={action === 'create' ? 'plus' : action === 'delete' ? 'trash-2' : 'history'} onClose={onClose}
      footer={<><Button onClick={onClose}>取消</Button><Button icon={action === 'delete' ? 'trash-2' : 'check'} className={'btn ' + (action === 'delete' ? 'danger' : 'primary')} reason={reason} disabled={!ready} onClick={onConfirm}>确认{action === 'create' ? '新增' : action === 'delete' ? '删除' : '恢复'}</Button></>}>
      <div className="modal-b form scroll sm-wrap-anywhere">
        {row && <p><strong>{row.filename}</strong><br />文件修改时间 {window.WorkbenchFormat.dateTime(row.time)} · {row.size_bytes} 字节<br />文件存在，本次还没有做完整性检查。</p>}
        <p>{action === 'create' ? '备份当前数据库。' : action === 'delete' ? '仅删除此备份文件，删除后不能撤销。' : '将用所选备份替换当前数据库。系统会先生成保护副本；完整性检查不通过时自动还原。'}</p>
        {action === 'restore' && <p className="sm-notice">一旦提交恢复，业务操作会停用。无论恢复成功还是已还原，都要关闭整个软件再启动；只刷新浏览器不算重启。</p>}
        {destructive && <label className="sm-inline-label"><input type="checkbox" checked={checked} onChange={event => setChecked(event.target.checked)} />我已核对所选文件与操作影响</label>}
        {action === 'restore' && <label className="field sm-field-gap"><span>输入「恢复」确认</span><input value={typed} onChange={event => setTyped(event.target.value)} /></label>}
        {reason && <ErrorBox error={reason} />}
      </div>
    </window.ResourceControls.Modal>;
  }
  // 系统拒绝提交时，按这次要做的事说清楚什么没有发生。
  const rejectedText = { create: '系统拒绝了这次提交，没有新增备份。', delete: '系统拒绝了这次提交，没有删除备份。',
    restore: '系统拒绝了这次提交，没有开始恢复。', config: '系统拒绝了这次提交，配置没有改动。' };
  function Outcome({ command }) {
    const { intent, result, error, busy, storageError } = command;
    if (!intent && !storageError) return null;
    const op = result && result.kind === 'file_operation' && result.operation;
    return <section className="sm-section sm-maintenance-outcome" aria-label="上次维护操作的结果">
      <div className="sm-section-head"><h3>{intent ? intent.summary : '上次操作记录不可用'}</h3><div className="sm-actions">
        {intent && !(result && result.kind === 'rejected') && <Button icon="refresh-cw" busy={busy} onClick={command.lookup}>{window.WorkbenchTerms.actions.query_result}</Button>}
        {result && result.terminal && !command.suspended && <Button icon="check" disabled={busy} onClick={command.acknowledge}>确认结果</Button>}
      </div></div>
      {intent && <window.WorkbenchReference label="操作编号" value={intent.request_key} />}
      <ErrorBox error={storageError || error} />
      {busy && <p role="status">正在等待维护结果，没有重新提交。</p>}
      {op ? <div role="status"><p><strong className={op.state === 'succeeded' ? 'sm-tone-success' : 'sm-tone-warning'}>{labels[op.state]}</strong> · {op.message}</p>
        <window.WorkbenchReference label="维护记录与结果代码" entries={{ '维护编号': op.job_ref, '结果代码': op.code }} />
        <p>更新时间：{window.WorkbenchFormat.dateTime(op.updated_at)}<br />操作记录：{op.audit_persisted ? '已留存' : '未确认留存'}{op.replayed ? ' · 查询上次结果' : ''}</p>
        {op.filename && <p>目标文件：{op.filename}</p>}{op.protection_filename && <p>保护副本：{op.protection_filename}</p>}
        <details className="sm-rules"><summary>维护阶段</summary>{op.history.map((step, index) => <p key={index}>{window.WorkbenchFormat.dateTime(step.time)} · {labels[step.state]}</p>)}</details>
      </div> : result && result.kind === 'config' ? <div role="status"><p>{result.command.result === 'committed' ? '八项维护配置已保存，操作记录已留存。' : '配置没有变化，没有写入新的操作记录。'}</p>
        <window.WorkbenchReference label="保存结果编号" value={result.command.receipt_ref} />{result.command.replayed && <p>查询上次结果</p>}</div> : result && result.kind === 'rejected' ? <p role="status">{rejectedText[intent && intent.action] || rejectedText.config}请按上面的提示改好后重新提交。</p> : null}
      {intent && !(result && result.terminal) && <p className="sm-note">{result && result.kind === 'not_recorded' ? result.message : '上次操作还没有确认结果。'}请点「查询结果」，勿重复提交。{intent.action === 'restore' ? '确认恢复结果前，业务操作暂停。' : ''}</p>}
    </section>;
  }
  // 叫法与顶栏一致：顶栏是「切换深色 / 切换浅色」和「紧凑表格」。
  function Preferences({ theme, onSetTheme, pageSize, onPageSize, compact, onCompact }) {
    return <section className="sm-section sm-preferences"><div className="sm-section-head"><h3>页面偏好</h3></div><div className="sm-session-settings">
      <fieldset className="sm-choice"><legend>切换深色或浅色</legend>{[['light', '浅色'], ['dark', '深色']].map(([value, label]) => <label key={value}>
        <input type="radio" name="system-maintenance-theme" checked={theme === value} disabled={typeof onSetTheme !== 'function'} onChange={() => onSetTheme(value)} />{label}</label>)}</fieldset>
      <label className="sm-inline-label">每页条数<select value={pageSize} onChange={event => onPageSize(Number(event.target.value))}>{[10, 25, 50].map(size => <option key={size} value={size}>{size} 条</option>)}</select></label>
      <label className="sm-inline-label" title="应用于全工作台表格"><input type="checkbox" checked={compact} onChange={event => onCompact(event.target.checked)} />紧凑表格</label>
    </div></section>;
  }
  window.SystemMaintenanceControls = { Button, ErrorBox, useRead, Confirm, Outcome, Preferences };
})();
