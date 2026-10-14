(function () {
  'use strict';
  const { Button, Modal } = window.ResourceControls, A = window.RunJobAPI;
  const labels = window.WorkbenchTerms.run_statuses;
  function Progress({ run }) {
    const [now, setNow] = React.useState(Date.now);
    React.useEffect(() => {
      if (run.finished_at) return undefined;
      const timer = setInterval(() => { if (!document.hidden) setNow(Date.now()); }, 1000);
      return () => clearInterval(timer);
    }, [run.run_ref, run.finished_at]);
    const progress = run.progress, computing = !A.terminal(run) && !run.recovery_required;
    const percent = progress && progress.total > 0 ? Math.round(progress.done / progress.total * 100) : null;
    return <div className="rj-progress" data-run-progress><p><strong>{window.RunPresentation.stage(run)}</strong><span>{run.started_at ? '处理用时' : run.finished_at ? '提交后用时' : '已等待'} {window.RunPresentation.elapsed(run, now)}</span>
      {progress && <span data-run-progress-count>已算完 {progress.done} / {progress.total} 个候选方案</span>}</p>
      {computing && <div className={'rj-bar' + (percent === null ? ' rj-bar-indeterminate' : '')} role="progressbar" aria-label="排产计算进度"
        aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent === null ? undefined : percent} aria-valuetext={percent === null ? '正在计算，进度未知' : '已算完 ' + progress.done + ' / ' + progress.total + ' 个候选方案'}>
        <i className="rj-bar-fill" style={percent === null ? undefined : { width: percent + '%' }} /></div>}
    </div>;
  }
  function Status({ run }) {
    return <span className={'pill ' + (run.state === 'complete' ? 'ok' : ['failed', 'partial', 'interrupted'].includes(run.state) ? 'warn' : 'off')} data-run-state={run.state} data-run-stage={run.stage}>
      <span className="dot" />{run.recovery_required ? '等待核对排产记录' : labels[run.state]}</span>;
  }
  // 不重排时段：本次没填时按交付设置，有同一次排产检查的结果就把推算出的时段一并写出来。
  function holdText(value, effective) {
    const T = window.WorkbenchTerms;
    if (value.hold_window === undefined && effective && effective.hold_window_source === 'default') return '按交付设置：' + T.hold_window(effective.hold_window);
    return T.hold_window(value.hold_window);
  }
  function Scope({ preview, effective, operationCount }) {
    const value = preview.normalized_input;
    return <dl className="rj-scope"><div><dt>本次范围</dt><dd>{value.batch_refs.length} 批{operationCount !== undefined && ' · ' + operationCount + ' 道工序'}</dd></div>
      <div><dt>排产日期</dt><dd>{value.start_date} 至 {value.end_date}</dd></div>
      <div><dt>物料齐套规则</dt><dd>{window.WorkbenchTerms.material_strategy(value.material_strategy, value.ready_check)}</dd></div><div><dt>齐套检查</dt><dd>{value.ready_check ? '开启' : '关闭'}</dd></div>
      <div><dt>缺资源工序</dt><dd>{value.missing_resource_policy === 'auto_assign' ? '自动分配' : '暂不排'}</dd></div>
      <div><dt>不重排时段</dt><dd data-hold-window>{holdText(value, effective)}</dd></div>
      <div><dt>已有报工</dt><dd>保留已开工和已完工的记录</dd></div></dl>;
  }
  function Reasons({ rows }) {
    const groups = new Map();
    rows.forEach(row => { const id = row.code + '\n' + row.message, group = groups.get(id); if (group) group.count += 1; else groups.set(id, { ...row, count: 1 }); });
    return <div className="rj-notice" role="status">{Array.from(groups.values()).slice(0, 20).map((row, index) => <div key={index}>
      {['run_worker_not_connected', 'run_schema_unavailable', 'execution_ledger_unavailable'].includes(row.code) ? A.message(row) : row.message}{row.count > 1 ? '（' + row.count + ' 项）' : ''}
      <window.WorkbenchReference entries={A.details(row)} />
    </div>)}{groups.size > 20 && <div>另有 {groups.size - 20} 类原因，请返回排产检查核对。</div>}</div>;
  }
  function BatchNames({ rows }) {
    const [page, setPage] = React.useState(1), pages = Math.max(1, Math.ceil(rows.length / 20));
    return <div className="rj-batch-names"><ol start={(page - 1) * 20 + 1}>{rows.slice((page - 1) * 20, page * 20).map(row => <li key={row.batch_ref}>
      <strong>{row.batch_id || '批次名称未保存'}</strong>{(row.part_no || row.part_label) && <span>{[row.part_no, row.part_label].filter(Boolean).join(' · ')}</span>}
    </li>)}</ol>{rows.length > 20 && <window.WorkbenchListControls.Pager page={page} pages={pages} total={rows.length} size={20} unit="批" label="批次" onPage={setPage} />}</div>;
  }
  function BusinessScope({ value }) {
    return <dl className="rj-business-scope"><div><dt>本次范围</dt><dd>{value.batch_count === null ? '批次数未保存' : value.batch_count + ' 批'} · {value.operation_count === null ? '工序数未保存' : value.operation_count + ' 道工序'}</dd></div>
      <div><dt>排产日期</dt><dd>{value.start_date && value.end_date ? window.WorkbenchFormat.date(value.start_date) + ' 至 ' + window.WorkbenchFormat.date(value.end_date) : '日期范围未保存'}</dd></div>
      <div><dt>排产目标</dt><dd>{value.objective_label || '目标说明未保存'}</dd></div></dl>;
  }
  function Confirmation({ preview, effective, batches = [], operationCount, busy, onConfirm, onClose }) {
    const [page, setPage] = React.useState(1), values = preview.normalized_input.batch_refs, pages = Math.max(1, Math.ceil(values.length / 20));
    const labels = new Map(batches.map(row => [row.batch_ref, row]));
    return <Modal title="确认本次候选排产" icon="play" onClose={onClose} locked={busy} footer={<>
      <Button onClick={onClose} disabled={busy}>取消</Button><Button icon="play" className="btn primary" busy={busy} onClick={onConfirm}>确认开始排产</Button></>}>
      <div className="modal-body run-job-panel rj-confirm"><Scope preview={preview} effective={effective} operationCount={operationCount} />
        <p className="rj-muted">计算完成后可比较候选方案，再选择是否采用为正式计划。</p>
        <h3>本次选中的批次</h3><ol className="rj-confirm-batches" start={(page - 1) * 20 + 1}>
          {values.slice((page - 1) * 20, page * 20).map(value => { const row = labels.get(value); return <li key={value}>{row ? row.batch_id : '批次名称未记录，请返回排产检查核对。'}</li>; })}</ol>
        {values.length > 20 && <window.WorkbenchListControls.Pager page={page} pages={pages} total={values.length} size={20} unit="批" label="批次" onPage={setPage} />}
        {!!preview.warnings.length && <Reasons rows={preview.warnings} />}</div>
    </Modal>;
  }
  function Record({ run, paused, retryPaused, retryHint = '可点「查询结果」再次核对原记录。', lastChecked, resolution, checking, verified, api, actions, navigation, title = '本次排产', onNavigate }) {
    const replaced = resolution === 'context_replaced';
    const queryLabel = checking ? '正在查询结果' : replaced ? '数据库已恢复' : resolution === 'lookup_failed' ? '查询失败' : '暂未查到这次排产记录';
    const saved = run && run.result_persisted && run.candidates.some(row => row.status === 'completed');
    const canOpen = typeof onNavigate === 'function' || typeof api.openCandidate === 'function';
    return <section aria-label="本次排产记录" className="rj-record"><div className="rj-heading rj-business-heading"><h2>{title}</h2>{run ? <Status run={run} /> : <span role="status" data-query-state={checking ? 'querying' : resolution}>{queryLabel}</span>}
      <div className="rj-business-actions">{navigation}{actions}</div></div>
      {replaced && <p className="rj-muted" role="status">数据库已恢复，上次排产结果不在当前数据中。请重新检查当前批次后开始排产。</p>}
      {run && !verified && <p className="rj-muted">下面是上次查到的结果，这次查询还没确认。</p>}
      {run && <><BusinessScope value={run.scope_summary} /><Progress run={run} />
        {run.recovery_required && <p className="rj-notice">正在核对上次的排产记录，结果还没确认，没有重新计算。</p>}
        {run.error && <div className="rj-notice" role="alert">{A.failure(run.error)}</div>}
        <div className="rj-tools">{saved && canOpen && <Button icon="chart" disabled={!verified} onClick={() => typeof onNavigate === 'function' ? onNavigate('run', { run_ref: run.run_ref }) : api.openCandidate({ run_ref: run.run_ref })}>查看本次排产结果</Button>}
          {A.terminal(run) && !saved && typeof onNavigate === 'function' && <Button icon="arrow-left" onClick={() => onNavigate('run', {})}>返回排产检查</Button>}</div>
        <details className="rj-record-details"><summary>排产记录详情</summary><dl className="rj-scope">
          {[['提交时间', run.accepted_at], ['开始处理', run.started_at], ['结束时间', run.finished_at]].filter(([, value]) => value).map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{window.WorkbenchFormat.dateTime(value, { seconds: true, fractions: true })}</dd></div>)}
          <div><dt>保存的目标</dt><dd>{run.scope_summary.objective_label || run.scope_summary.objective || '未保存'}</dd></div>
        </dl>{run.scope_summary.batches.length > 0 && <BatchNames rows={run.scope_summary.batches} />}
          {run.scope_summary.data_gaps.map((row, index) => <p className="rj-muted" key={index}>{row.message}</p>)}
          {lastChecked && <p className="rj-muted">最近查询：{window.WorkbenchFormat.instant(new Date(lastChecked).toISOString(), { seconds: true })}</p>}
        </details></>}
      {!replaced && <p className="rj-muted rj-query-summary" role="status">
        {retryPaused ? <span>已暂停自动查询。{retryHint}</span> : !A.terminal(run) && <span>{paused ? '页面已切走，返回后继续查询。' : checking ? '正在读取排产记录。' : '等待下次查询。'}</span>}
      </p>}
    </section>;
  }
  window.RunJobControls = { Button, Confirmation, Scope, Reasons, Record, Status, BusinessScope };
})();
