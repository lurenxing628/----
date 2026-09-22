(function () {
  'use strict';
  const K = window.APSCalendarContract, S = window.APSResourceSession;
  const { Button, ErrorBox, Issues, Modal } = window.ResourceControls;
  const { RefreshResult, Policy } = window.CalendarFields;
  const statusLabels = { not_configured: '未填写', unknown: '未知', unavailable: '暂无数据' };
  // 默认规则只写班表汇总里真实读到的值：没有的项写“未填写 / 暂无数据”，不再把 8 小时、周末休息这类假设写死在图例里。
  function DefaultRules({ value }) {
    const standard = value.standard_hours, holiday = value.holiday_default_efficiency;
    const standardText = standard.status === 'known' ? window.WorkbenchFormat.hours(standard.value) : standard.message || statusLabels[standard.status] || '暂无数据';
    const holidayText = holiday.status === 'known' ? window.WorkbenchFormat.number(holiday.value * 100, { digits: 1, trim: true }) + '%' : statusLabels[holiday.status] || '暂无数据';
    return <><p>未单独设置的日期按默认规则排产。标准工时 / 日：{standardText}；假期录入默认效率：{holidayText}。</p><p className="muted">{value.basis}</p></>;
  }
  function ResourceCalendar({ adapter, onCommitted, initialContext, onNavigationReady, onOpenFile, rememberEnabled = true }) {
    const [target] = React.useState(() => {
      if (initialContext == null) return { context: null };
      const parsed = window.ResourceWorkspace.navigation(initialContext);
      return parsed.context && parsed.context.kind !== 'calendar' ? { error: window.APSResourceContract.failure('工作日历定位类型不正确。') } : parsed;
    });
    const [month, setMonth] = React.useState(() => { const now = new Date(); return target.context
      ? { year: Number(target.context.month.slice(0, 4)), month: Number(target.context.month.slice(5, 7)) } : { year: now.getFullYear(), month: now.getMonth() + 1 }; });
    const [dialog, setDialog] = React.useState(null), [refreshState, setRefreshState] = React.useState({});
    const command = S.useCommand(adapter), handled = React.useRef(null), awaitingRefresh = React.useRef(false);
    const [deferred, setDeferred] = React.useState(() => !!target.context && command.phase !== 'idle');
    const [navigationError, setNavigationError] = React.useState(target.error || null), located = React.useRef(false), root = React.useRef(null);
    const request = S.useQuery(async signal => K.month(await adapter.query(K.path + '/month', month, signal), month.year, month.month), [adapter, month.year, month.month]);
    const result = request.result, data = result && result.data, source = result && result.meta.source;
    // 刷新本月时继续显示同月数据并标 aria-busy；翻月时不把旧月网格放到新标题下。
    const last = React.useRef(null); if (result) last.current = result;
    const previous = last.current && last.current.data;
    const view = data || (request.loading && previous && previous.year === month.year && previous.month === month.month ? previous : null);
    const [summaryRevision, bumpSummary] = React.useReducer(value => value + 1, 0);
    const summary = S.useSummary(adapter, summaryRevision), rules = summary.result && summary.result.data;
    window.WorkbenchPageContext.useSnapshot({ source: 'production', kind: 'calendar', month: String(month.year).padStart(4, '0') + '-' + String(month.month).padStart(2, '0'),
      ...(dialog && dialog.mode === 'view' ? { date: dialog.day.date } : {}) },
      rememberEnabled && !!data && !request.loading && !request.error && !navigationError && !deferred && command.phase === 'idle'
      && source === 'production' && (!dialog || dialog.mode === 'view'));
    React.useEffect(() => { if (onNavigationReady) onNavigationReady(!dialog && command.phase === 'idle'); }, [dialog, command.phase, onNavigationReady]);
    React.useEffect(() => {
      if (!target.context || deferred || located.current || !data || command.phase !== 'idle') return;
      located.current = true;
      if (source !== 'production') { setNavigationError(window.APSResourceContract.failure('本月日历读取失败，请重新打开工作日历。')); return; }
      if (target.context.date) {
        const day = data.days.find(row => row.date === target.context.date);
        if (!day || !day.explicit) { setNavigationError(window.APSResourceContract.failure('这一天的单独设置已经不存在了，没有新增，也没有用默认规则代替。')); return; }
        setDialog({ mode: 'view', day, source });
      }
    }, [data, source, command.phase, deferred, target]);
    function refresh() { awaitingRefresh.current = { previous: request.result }; setRefreshState({ loading: true }); request.reload(); bumpSummary(); }
    React.useEffect(() => {
      if (command.phase !== 'done' || handled.current === command.result.receipt_ref) return;
      handled.current = command.result.receipt_ref; refresh();
      if (typeof onCommitted === 'function') onCommitted(command.result);
    }, [command.phase, command.result]);
    React.useEffect(() => {
      if (!awaitingRefresh.current || request.loading) return;
      if (request.error) { awaitingRefresh.current = false; setRefreshState({ error: request.error }); }
      else if (request.result && request.result !== awaitingRefresh.current.previous) { awaitingRefresh.current = false; setRefreshState({ done: true }); }
    }, [request.loading, request.result, request.error]);
    const orphan = !dialog && (command.locked || command.phase === 'done' || command.phase === 'rejected');
    const blocked = command.locked || command.phase === 'done';
    function open(next) { if (blocked || !command.reset()) return; setRefreshState({}); setDialog(next); }
    function close() { if (!command.reset()) return; setDialog(null); }
    function continueNavigation() {
      if (dialog || command.phase !== 'idle') { setNavigationError(window.APSResourceContract.failure('请先确认并关闭上次工作日历操作的结果，再继续跳转。')); return; }
      setDeferred(false); setNavigationError(null);
    }
    const stats = [['work_days', '本月工作日', 'primary'], ['configured', '已单独设置', 'ok'], ['overrides', '调休 / 加班', 'warn'], ['weekend_rest', '周末休息', 'neutral']];
    return <section className="resource-calendar" aria-label="工作日历" ref={root}>
      <div className="crumb"><span>产能链</span><span className="sep">/</span><span>全局</span><span className="sep">/</span><span>工作日历</span></div>
      <div className="chead wb-page-heading"><div><h2>工作日历</h2><p className="cdesc">全局工作时间、效率与可排产范围</p></div></div>
      <div className="statline wb-metrics" style={{ '--wb-columns': 4 }}>{stats.map(([key, label, tone]) => <div key={key} className="stat wb-metric" data-tone={tone}>
        <span className="sl wb-metric-label">{label}</span><span className="sv wb-metric-value">{view ? window.WorkbenchFormat.number(view.stats[key], { digits: 0 }) : '未读取'}</span></div>)}</div>
      <ErrorBox error={request.error} /><Issues issues={result && result.warnings || []} />
      <ErrorBox error={navigationError} />{deferred && <div role="status"><p>上次工作日历操作还没处理完，暂时没有跳转。</p><Button icon="arrow-right" onClick={continueNavigation}>继续跳转</Button></div>}
      <div className="cal-wrap" style={{ marginTop: 18 }}>
        <div className="cal-panel" style={{ minWidth: 0 }}>
          <div className="cal-top" style={{ flexWrap: 'wrap' }}>
            <Button className="cal-nav" icon="chevron-left" aria-label="上一月" disabled={blocked || request.loading || !data || !data.previous_month} onClick={() => setMonth(data.previous_month)} />
            <span className="cal-title">{month.year} 年 {month.month} 月</span>
            <Button className="cal-nav" icon="chevron-right" aria-label="下一月" disabled={blocked || request.loading || !data || !data.next_month} onClick={() => setMonth(data.next_month)} />
            <Button className="cal-nav cal-today-btn" title="回到本月" style={{ width: 'auto', padding: '0 10px', fontSize: 12, fontWeight: 600 }} disabled={blocked}
              onClick={() => { const now = new Date(); setMonth({ year: now.getFullYear(), month: now.getMonth() + 1 }); request.reload(); }}>本月</Button>
            <Button icon="refresh-cw" aria-label="刷新本月" busy={request.loading} disabled={blocked} onClick={request.reload} />
            <span className="tb-spacer" style={{ flex: 1 }} />
            <Button icon="file-input" transfer="import" disabled={blocked || !data || request.loading}
              reason={typeof onOpenFile !== 'function' ? '日历文件导入尚未开通。' : source && source !== 'production' ? '当前不是生产数据，不能导入。' : ''}
              onClick={() => onOpenFile('import', { source, month })}>导入日历</Button>
            <Button icon="file-output" transfer="export" disabled={blocked || !data || request.loading}
              reason={typeof onOpenFile !== 'function' ? '日历文件导出尚未开通。' : ''}
              onClick={() => onOpenFile('export', { source, month })}>导出日历</Button>
            <Button icon="calendar-days" className="btn cal-batch" disabled={blocked || !data || request.loading}
              reason={source && source !== 'production' ? '当前不是生产数据，不能维护。' : ''} onClick={() => open({ mode: 'range' })}>批量维护</Button>
          </div>
          {request.loading && !view && <window.WorkbenchControls.EmptyState kind="loading" title="正在读取工作日历…" />}
          {request.loading && view && <p role="status" className="muted">正在刷新工作日历…</p>}
          {view && <div className="cal-grid" aria-busy={request.loading}>{['一', '二', '三', '四', '五', '六', '日'].map(day => <div className="cal-wd" key={day}>{day}</div>)}
            {view.cells.map((cell, index) => {
              if (!cell) return <div key={'empty-' + index} className="cal-cell empty" />;
              const row = view.days.find(day => day.date === cell.date), meta = K.tag(row);
              return <button key={row.date} type="button" className={'cal-cell ' + meta.tone + (row.is_today ? ' today' : '')}
                style={{ minWidth: 0, textAlign: 'left', color: 'inherit', fontFamily: 'inherit' }} disabled={blocked || request.loading}
                data-calendar-date={row.date} aria-current={target.context && target.context.date === row.date ? 'date' : undefined}
                aria-label={row.date + ' ' + (row.explicit ? '单独设置' : '默认规则') + ' ' + meta.text} title={row.date + ' · ' + (row.explicit ? '单独设置' : '默认规则')}
                onClick={() => open({ mode: 'day', day: row, source })}><span className="d">{row.day}</span>
                <span className="tag" style={{ whiteSpace: 'normal', overflowWrap: 'anywhere' }}>{meta.text}</span></button>;
            })}</div>}
        </div>
        <div className="cal-panel cal-side"><h3>图例</h3><div className="cal-leg"><div><span className="sw cfg" />已单独设置工时</div>
          <div><span className="sw rest" />调休 / 加班</div><div><span className="sw we" />周末（默认非工作）</div></div>
          <h3>默认规则</h3>
          {rules && rules.calendar ? <DefaultRules value={rules.calendar} /> : summary.loading ? <p role="status">正在读取默认规则…</p>
            : <p>默认规则暂无数据{rules && rules.calendar_error ? '：' + rules.calendar_error : ''}</p>}
          <ErrorBox error={summary.error} />
          <h3>规则来源</h3><p>本页维护全局工作日历；{window.WorkbenchTerms.personal_calendar}和班次单独设置。</p>
          {view && <p>{window.WorkbenchTerms.data_as_of(window.WorkbenchFormat.dateTime(view.as_of))}</p>}</div>
      </div>
      {dialog && dialog.mode === 'view' && <Modal title={dialog.day.date + ' · 日历详情'} icon="calendar-days" onClose={close}
        footer={<><Button onClick={close}>关闭</Button><Button icon="square-pen" onClick={() => open({ ...dialog, mode: 'day' })}>维护此日</Button></>}>
        <div className="modal-b form scroll"><Policy value={dialog.day} /><Issues issues={dialog.day.issues || []} /></div></Modal>}
      {dialog && dialog.mode === 'day' && <window.CalendarDayDialog adapter={adapter} day={dialog.day} source={dialog.source} command={command} onClose={close} refreshState={refreshState} onRefresh={refresh} />}
      {dialog && dialog.mode === 'range' && <window.CalendarRangeDialog adapter={adapter} month={month} source={source} command={command} onClose={close} refreshState={refreshState} onRefresh={refresh} />}
      {orphan && <Modal title="工作日历操作结果" icon="history" locked={command.locked} onClose={close} footer={<Button disabled={command.locked} onClick={close}>关闭</Button>}>
        <div className="modal-b form scroll">{command.intent ? <><p>{command.intent.action === 'confirm' ? '批量维护工作日历' : '维护单日设置'}</p>
          <window.WorkbenchReference entries={{ '操作编号': command.intent.request_key, '日期编号': command.intent.ref }} /></> : <p>读不到上次操作记录</p>}
          <window.ResourceForms.Feedback command={command} />{command.phase === 'done' && <RefreshResult state={refreshState} onRefresh={refresh} />}</div></Modal>}
    </section>;
  }
  window.ResourceCalendar = ResourceCalendar;
})();
