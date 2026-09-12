(function () {
  'use strict';
  const K = window.APSCalendarContract, S = window.APSResourceSession;
  const { Button, ErrorBox, Issues, Modal } = window.ResourceControls;
  const { RefreshResult, Policy } = window.CalendarFields;
  function ResourceCalendar({ adapter, onCommitted, initialContext, onNavigationReady, rememberEnabled = true }) {
    const [target] = React.useState(() => {
      if (initialContext == null) return { context: null };
      const parsed = window.ResourceWorkspace.navigation(initialContext);
      return parsed.context && parsed.context.kind !== 'calendar' ? { error: window.APSResourceContract.failure('日历导航类型不正确。') } : parsed;
    });
    const [month, setMonth] = React.useState(() => { const now = new Date(); return target.context
      ? { year: Number(target.context.month.slice(0, 4)), month: Number(target.context.month.slice(5, 7)) } : { year: now.getFullYear(), month: now.getMonth() + 1 }; });
    const [dialog, setDialog] = React.useState(null), [refreshState, setRefreshState] = React.useState({});
    const command = S.useCommand(adapter), handled = React.useRef(null), awaitingRefresh = React.useRef(false);
    const [deferred, setDeferred] = React.useState(() => !!target.context && command.phase !== 'idle');
    const [navigationError, setNavigationError] = React.useState(target.error || null), located = React.useRef(false), root = React.useRef(null);
    const request = S.useQuery(async signal => K.month(await adapter.query(K.path + '/month', month, signal), month.year, month.month), [adapter, month.year, month.month]);
    const result = request.result, data = result && result.data, source = result && result.meta.source;
    window.WorkbenchPageContext.useSnapshot({ source: 'production', kind: 'calendar', month: String(month.year).padStart(4, '0') + '-' + String(month.month).padStart(2, '0'),
      ...(dialog && dialog.mode === 'view' ? { date: dialog.day.date } : {}) },
      rememberEnabled && !!data && !request.loading && !request.error && !navigationError && !deferred && command.phase === 'idle'
      && source === 'production' && (!dialog || dialog.mode === 'view'));
    React.useEffect(() => { if (onNavigationReady) onNavigationReady(!dialog && command.phase === 'idle'); }, [dialog, command.phase, onNavigationReady]);
    React.useEffect(() => {
      if (!target.context || deferred || located.current || !data || command.phase !== 'idle') return;
      located.current = true;
      if (source !== 'production') { setNavigationError(window.APSResourceContract.failure('未取得指定月份的生产日历，未使用样例替代。')); return; }
      if (target.context.date) {
        const day = data.days.find(row => row.date === target.context.date);
        if (!day || !day.explicit) { setNavigationError(window.APSResourceContract.failure('原日期配置已不存在，未补建或打开默认规则作为原记录。')); return; }
        setDialog({ mode: 'view', day, source });
      }
    }, [data, source, command.phase, deferred, target]);
    function refresh() { awaitingRefresh.current = { previous: request.result }; setRefreshState({ loading: true }); request.reload(); }
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
      if (dialog || command.phase !== 'idle') { setNavigationError(window.APSResourceContract.failure('请先核实并关闭原日历操作结果，再继续导航。')); return; }
      setDeferred(false); setNavigationError(null);
    }
    const stats = [['work_days', '本月工作日', 'primary'], ['configured', '已配置日期', 'ok'], ['overrides', '调休 / 加班', 'warn'], ['weekend_rest', '周末休息', 'neutral']];
    return <section className="resource-calendar" aria-label="工作日历" ref={root}>
      <div className="crumb"><span>产能链</span><span className="sep">/</span><span>全局</span><span className="sep">/</span><span>工作日历</span></div>
      <div className="chead wb-page-heading"><div><h2>工作日历</h2><p className="cdesc">全局工作时间、效率与可排产范围</p></div></div>
      <div className="statline wb-metrics" style={{ '--wb-columns': 4 }}>{stats.map(([key, label, tone]) => <div key={key} className="stat wb-metric" data-tone={tone}>
        <span className="sl wb-metric-label">{label}</span><span className="sv wb-metric-value">{data ? data.stats[key] : '待读取'}</span></div>)}</div>
      <ErrorBox error={request.error} /><Issues issues={result && result.warnings || []} />
      <ErrorBox error={navigationError} />{deferred && <div role="status"><p>原日历请求优先处理，精确导航暂缓。</p><Button icon="arrow-right" onClick={continueNavigation}>继续原导航</Button></div>}
      <div className="cal-wrap" style={{ marginTop: 18 }}>
        <div className="cal-panel" style={{ minWidth: 0 }}>
          <div className="cal-top" style={{ flexWrap: 'wrap' }}>
            <Button className="cal-nav" icon="chevron-left" aria-label="上一月" disabled={blocked || request.loading || !data || !data.previous_month} onClick={() => setMonth(data.previous_month)} />
            <span className="cal-title">{month.year} 年 {month.month} 月</span>
            <Button className="cal-nav" icon="chevron-right" aria-label="下一月" disabled={blocked || request.loading || !data || !data.next_month} onClick={() => setMonth(data.next_month)} />
            <Button className="cal-nav cal-today-btn" title="回到本月" style={{ width: 'auto', padding: '0 10px', fontSize: 12, fontWeight: 600 }} disabled={blocked}
              onClick={() => { const now = new Date(); setMonth({ year: now.getFullYear(), month: now.getMonth() + 1 }); request.reload(); }}>今天</Button>
            <Button icon="refresh-cw" aria-label="重新读取月份" busy={request.loading} disabled={blocked} onClick={request.reload} />
            <span className="tb-spacer" style={{ flex: 1 }} /><Button icon="calendar-days" className="btn cal-batch" disabled={blocked || !data || request.loading}
              reason={source && source !== 'production' ? '当前不是生产数据，不能维护。' : ''} onClick={() => open({ mode: 'range' })}>批量维护</Button>
          </div>
          {request.loading && <window.WorkbenchControls.EmptyState kind="loading" title="正在读取工作日历…" />}
          {data && <div className="cal-grid">{['一', '二', '三', '四', '五', '六', '日'].map(day => <div className="cal-wd" key={day}>{day}</div>)}
            {data.cells.map((cell, index) => {
              if (!cell) return <div key={'empty-' + index} className="cal-cell empty" />;
              const row = data.days.find(day => day.date === cell.date), meta = K.tag(row);
              return <button key={row.date} type="button" className={'cal-cell ' + meta.tone + (row.is_today ? ' today' : '')}
                style={{ minWidth: 0, textAlign: 'left', color: 'inherit', fontFamily: 'inherit' }} disabled={blocked}
                data-calendar-date={row.date} aria-current={target.context && target.context.date === row.date ? 'date' : undefined}
                aria-label={row.date + ' ' + (row.explicit ? '单独配置' : '默认规则') + ' ' + meta.text} title={row.date + ' · ' + (row.explicit ? '单独配置' : '默认规则')}
                onClick={() => open({ mode: 'day', day: row, source })}><span className="d">{row.day}</span>
                <span className="tag" style={{ whiteSpace: 'normal', overflowWrap: 'anywhere' }}>{meta.text}</span></button>;
            })}</div>}
        </div>
        <div className="cal-panel cal-side"><h3>图例</h3><div className="cal-leg"><div><span className="sw cfg" />已配置工时</div>
          <div><span className="sw rest" />调休 / 加班</div><div><span className="sw we" />周末（默认非工作）</div></div>
          <h3>默认规则</h3><p>未单独配置的日期：周一至周五按 8 小时、效率 100%，普通件 / 急件均可排产；周末默认不排产。</p>
          <h3>规则来源</h3><p>本页维护全局日历。人员专属日历与班次仍单独生效，不会在此清除。</p>
          {data && <p>本机数据截至 {window.WorkbenchFormat.dateTime(data.as_of)}</p>}</div>
      </div>
      {dialog && dialog.mode === 'view' && <Modal title={dialog.day.date + ' · 日历详情'} icon="calendar-days" onClose={close}
        footer={<><Button onClick={close}>关闭</Button><Button icon="square-pen" onClick={() => open({ ...dialog, mode: 'day' })}>维护此日</Button></>}>
        <div className="modal-b form scroll"><Policy value={dialog.day} /><Issues issues={dialog.day.issues || []} /></div></Modal>}
      {dialog && dialog.mode === 'day' && <window.CalendarDayDialog adapter={adapter} day={dialog.day} source={dialog.source} command={command} onClose={close} refreshState={refreshState} onRefresh={refresh} />}
      {dialog && dialog.mode === 'range' && <window.CalendarRangeDialog adapter={adapter} month={month} source={source} command={command} onClose={close} refreshState={refreshState} onRefresh={refresh} />}
      {orphan && <Modal title="工作日历操作回执" icon="history" locked={command.locked} onClose={close} footer={<Button disabled={command.locked} onClick={close}>关闭</Button>}>
        <div className="modal-b form scroll">{command.intent ? <><p>{command.intent.action === 'confirm' ? '批量日历维护' : '日期配置维护'}</p>
          <window.WorkbenchReference entries={{ '请求编号': command.intent.request_key, '日期编号': command.intent.ref }} /></> : <p>本机待核实记录无法读取</p>}
          <window.ResourceForms.Feedback command={command} />{command.phase === 'done' && <RefreshResult state={refreshState} onRefresh={refresh} />}</div></Modal>}
    </section>;
  }
  window.ResourceCalendar = ResourceCalendar;
})();
