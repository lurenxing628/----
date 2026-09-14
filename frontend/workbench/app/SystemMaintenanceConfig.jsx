(function () {
  'use strict';
  const A = window.SystemMaintenanceAPI, C = window.SystemMaintenanceControls;
  function Config({ api, revision, command, active = true, ...preferences }) {
    const [refresh, reload] = React.useReducer(value => value + 1, 0), [draft, setDraft] = React.useState(null), [validated, setValidated] = React.useState(false);
    const [base, setBase] = React.useState(null), [replace, setReplace] = React.useState(false);
    const request = C.useRead(api, 'config', {}, revision + ':' + refresh, active), incoming = request.data && request.data.data;
    const validation = A.normalize(draft || {}), changed = base && draft && A.fields.some(field => String(draft[field.key]) !== String(base.values[field.key]));
    React.useEffect(() => {
      // A receipt or revision alone cannot settle a draft; all eight read-back values must match.
      const matchesDraft = incoming && draft && A.fields.every(field => String(draft[field.key]) === String(incoming.values[field.key]));
      if (incoming && (!changed || matchesDraft)) { setBase(incoming); setDraft({ ...incoming.values }); setValidated(false); }
    }, [incoming]);
    const ready = incoming && base === incoming && !request.loading && !request.error;
    const reason = command.locked ? '上次维护操作还没有确认结果。请先点「查询结果」。' : !ready ? '请先点「刷新配置」读取正式配置。' : '';
    function refreshNow() { setReplace(false); setBase(null); setDraft(null); reload(); }
    return <div className="sm-configuration" style={{ maxWidth: 'none' }}>
      <C.Preferences {...preferences} />
      <section className="sm-section sm-maintenance-config"><div className="sm-section-head"><h3>本机自动维护配置</h3><C.Button icon="refresh-cw" aria-label="刷新配置" busy={request.loading}
        onClick={() => changed ? setReplace(true) : refreshNow()} /></div>
        <C.ErrorBox error={request.error} />{request.loading && <p className="sm-note" role="status">正在读取八项维护配置…</p>}
        {incoming && base && incoming !== base && changed && <div className="sm-notice" role="status">已读到新的配置数据，你填的内容没有被覆盖。请核对变化后再保存。
          <details><summary>最新已存配置</summary>{A.fields.map(field => <p key={field.key}>{field.label}：{String(incoming.values[field.key])}{incoming.dirty_fields.includes(field.key) ? ' · ' + incoming.dirty_reasons[field.key] : ''}</p>)}</details>
          <C.Button icon="check" disabled={command.locked} onClick={() => setBase(incoming)}>核对后沿用草稿</C.Button></div>}
        {draft && base && <form className="sm-config-form" noValidate onSubmit={event => { event.preventDefault(); setValidated(true);
          if (validation.valid && !reason) command.execute('config', base.write_context.write_token, validation.values);
        }}><div className="sm-config-groups">{[['backup', '备份规则'], ['logs', '操作日志规则']].map(([group, label]) => <fieldset className="sm-config-group" key={group}><legend>{label}</legend>
          {A.fields.filter(field => field.group === group).map(field => <div className="sm-config-row" key={field.key} style={{ gridTemplateColumns: 'minmax(140px, 1fr) minmax(140px, 1fr)' }}>
            <label htmlFor={'sm-maintenance-' + field.key}>{field.label}</label><div>
              {field.switch ? <label className="sm-draft-checkbox"><input id={'sm-maintenance-' + field.key} type="checkbox" checked={draft[field.key] === 'yes'} disabled={!!reason}
                onChange={event => setDraft({ ...draft, [field.key]: event.target.checked ? 'yes' : 'no' })} /><span>{draft[field.key] === 'yes' ? '启用' : '关闭'}</span></label> : <div className="sm-number">
                <input id={'sm-maintenance-' + field.key} type="number" min={1} max={field.max} step={1} value={draft[field.key]} disabled={!!reason} aria-invalid={validated && !!validation.errors[field.key]}
                  aria-describedby={'sm-maintenance-help-' + field.key} onChange={event => setDraft({ ...draft, [field.key]: event.target.value })} /><span>{field.unit}</span></div>}
              <small id={'sm-maintenance-help-' + field.key} className={validated && validation.errors[field.key] ? 'sm-error' : 'sm-meta'}>{validated && validation.errors[field.key] || (field.switch ? '正式配置' : '1 至 ' + field.max + ' ' + field.unit)}</small>
              {base.dirty_fields.includes(field.key) ? <small className="sm-error">旧配置异常：{base.dirty_reasons[field.key]}{base.stored_values[field.key] !== null ? ' · 原值：' + base.stored_values[field.key] : ''}</small>
                : base.defaulted_fields.includes(field.key) ? <small className="sm-meta">默认值，尚未保存</small> : <small className="sm-meta">已存值：{field.switch ? base.values[field.key] === 'yes' ? '启用' : '关闭' : base.values[field.key]}</small>}
            </div>
          </div>)}
        </fieldset>)}</div>
          <div className="sm-form-footer"><span className="sm-meta">{changed ? '有未保存修改' : base.dirty_fields.length || base.defaulted_fields.length ? '含异常或默认项，还需核对后保存' : '当前值已读取'}</span><div className="sm-actions">
            <C.Button icon="rotate-ccw" disabled={!!reason || !changed} onClick={() => setReplace(true)}>放弃草稿</C.Button><C.Button icon="save" type="submit" className="btn primary" reason={reason}>保存维护配置</C.Button>
          </div></div>{validated && !validation.valid && <p className="sm-error" role="alert">有几项填得不对，配置没有保存。请修正标红的项。</p>}
        </form>}
        <details className="sm-rules sm-config-help"><summary>生效范围与自动维护规则</summary><p>打开页面时系统才会检查一次自动维护，检查间隔不保证在指定时刻执行。清理操作日志不会清除运行日志文件。</p><p>主题、每页条数、紧凑行距属于页面偏好，不写入业务配置。</p></details>
      </section>
      {replace && <window.ResourceControls.Modal title="放弃当前草稿并刷新？" icon="history" onClose={() => setReplace(false)}
        footer={<><C.Button onClick={() => setReplace(false)}>保留草稿</C.Button><C.Button icon="refresh-cw" onClick={refreshNow}>放弃并刷新</C.Button></>}><div className="modal-b form"><p>未保存修改将被丢弃，不会写入业务配置。</p></div></window.ResourceControls.Modal>}
    </div>;
  }
  window.SystemMaintenanceConfig = Config;
})();
