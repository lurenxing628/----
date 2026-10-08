(function () {
  'use strict';
  const C = window.APSResourceContract;
  const { Button, Icon, MetricValue } = window.ResourceControls;
  const labels = { known: '已确认', recorded: '已登记', zero: '0 条记录', unknown: '未知', not_configured: '未填写', unavailable: '暂无数据' };
  const weekdays = ['一', '二', '三', '四', '五', '六', '日'];
  const number = value => Number.isFinite(value) && value >= 0;
  const amount = value => window.WorkbenchFormat.number(value, { digits: 1 });
  const integer = value => window.WorkbenchFormat.number(value, { digits: 0 });
  const hoursOrNone = value => value == null ? '暂无数据' : window.WorkbenchFormat.hours(value);
  const countLabels = { active: '启用', inactive: '停用', maintain: '停机', leave: '请假', pending_review: '待复核', unknown: '未知' };
  const chipOrder = ['process', 'material', 'op_int', 'machine', 'operator', 'op_ext', 'supplier'];
  // 首次展开；手动选择在同一页会话内跨节点保留，不因窗口尺寸改变而重置。
  const COLLAPSED_CHOICE_KEY = 'aps_resource_rail_collapsed';
  function readCollapsedChoice() {
    try {
      const value = sessionStorage.getItem(COLLAPSED_CHOICE_KEY);
      return { collapsed: value === 'true' ? true : value === 'false' ? false : null, error: '' };
    } catch (_) {
      return { collapsed: null, error: '无法读取产能链显示设置，当前已展开，仍可手动收起。' };
    }
  }
  function processText(item, total, loading) {
    const unavailable = { lead: '工艺阶段暂无数据', pending: '', lines: [] };
    if (loading || !item || item.status === 'unavailable') return unavailable;
    const counts = item.counts;
    const fields = ['total', 'route', 'source', 'hours', 'ready', 'legacy', 'managed', 'legacy_route_present',
      'route_confirmed', 'source_confirmed', 'hours_confirmed'];
    if (!counts || !fields.every(key => Number.isSafeInteger(counts[key]) && counts[key] >= 0) || counts.total !== total ||
        counts.route + counts.source + counts.hours + counts.ready !== total || counts.legacy + counts.managed !== total ||
        counts.legacy_route_present > Math.min(counts.legacy, counts.source) || counts.legacy - counts.legacy_route_present > counts.route ||
        counts.route_confirmed !== counts.source + counts.hours + counts.ready - counts.legacy_route_present ||
        counts.source_confirmed !== counts.hours + counts.ready || counts.hours_confirmed !== counts.ready ||
        item.status !== (total === 0 ? 'zero' : counts.ready === total ? 'ready' : 'pending')) return unavailable;
    if (total === 0) return { lead: '暂无零件', pending: '', lines: [] };
    return { lead: '已确认 ' + counts.ready + ' / ' + total + ' 项',
      pending: [['route', '待路线'], ['source', '待归属'], ['hours', '待工时']]
        .filter(([key]) => counts[key] > 0).map(([key, label]) => label + ' ' + counts[key]).join(' · '), lines: [
      '待路线 ' + counts.route + ' / 待归属 ' + counts.source + ' / 待工时 ' + counts.hours,
      '已确认：路线 ' + counts.route_confirmed + ' / 归属 ' + counts.source_confirmed + ' / 工时 ' + counts.hours_confirmed,
      ...(counts.legacy ? [counts.legacy + ' 项暂无确认记录，其中 ' + counts.legacy_route_present + ' 项已有路线资料'] : [])] };
  }
  function itemLines(item, key) {
    if (!item) return [];
    if (item.status === 'unavailable') return ['关联数量暂无数据'];
    const states = Object.keys(countLabels).filter(key => number(item.counts[key]) && item.counts[key] > 0)
      .map(key => countLabels[key] + ' ' + integer(item.counts[key]));
    const facts = key === 'op_int' ? [['without_machines', '未关联设备'], ['available_operators', '匹配人员']] :
      key === 'op_ext' ? [['merge_mode_unset', '周期规则未设'], ['available_suppliers', '匹配供应商']] : [];
    facts.forEach(([field, label]) => states.push(label + ' ' + (number(item.counts[field]) ? integer(item.counts[field]) : '未知')));
    return states;
  }
  const itemText = (item, key) => itemLines(item, key).join(' / ');
  function dayText(day) {
    const origin = day.explicit ? '单独设置' : '按默认（未单独设置）';
    if (!day.effective) return day.date + ' · ' + origin + ' · 暂无数据：' + day.issues.map(issue => issue.message).join('；');
    const value = day.effective;
    return day.date + ' · ' + origin + '\n' + window.WorkbenchFormat.dateTime(value.window_start, { seconds: true }) + ' 至 ' + window.WorkbenchFormat.dateTime(value.window_end, { seconds: true }) +
      (value.crosses_midnight ? '（跨夜，归班次起始日）' : '') + '\n班次 ' + window.WorkbenchFormat.hours(value.hours) + ' × 效率 ' + amount(value.efficiency * 100) +
      '%；有效 ' + window.WorkbenchFormat.hours(value.effective_hours) + '\n普通件 ' + (value.allow_normal ? '允许' : '不允许') +
      ' / 急件及特急件 ' + (value.allow_urgent ? '允许' : '不允许') +
      (value.rest_reason === 'priorities_disabled' ? '；普通件和急件都不许可，但班次工时不是 0' : '') +
      (day.issues.length ? '\n' + day.issues.map(issue => issue.message).join('；') : '');
  }
  function CalendarSummary({ value, error, loading, node, disabled, onNode }) {
    const stats = value && value.stats, standard = value && value.standard_hours;
    const standardText = standard ? standard.status === 'known' ? window.WorkbenchFormat.hours(standard.value) : labels[standard.status] : '暂无数据';
    const days = value ? value.days : weekdays.map((label, index) => ({ weekday: index, date: label, status: 'unavailable', issues: [] }));
    const source = stats ? stats.configured_days === 0 ? '本周全部按默认规则' : '单独设置 ' + integer(stats.configured_days) + ' 天 · 按默认 ' + integer(stats.default_days) + ' 天' : '来源暂无数据';
    const differentPriorities = stats && (stats.normal_effective_hours !== stats.effective_hours || stats.urgent_effective_hours !== stats.effective_hours);
    return <button type="button" className={'hb-block hero hb-cal-block' + (node === 'calendar' ? ' on' : '')} aria-label="工作日历 · 全局"
      style={{ font: 'inherit', color: 'inherit', textAlign: 'left' }} disabled={disabled} aria-pressed={node === 'calendar'} onClick={() => onNode('calendar')}>
      <span className="rail-calendar-summary">
        <span className="rail-calendar-heading">
          <span className="hb-bhead"><span className="hb-bdot cal" /><span className="hb-bname">工作日历</span><span className="hb-bmeas">自制 · 全局</span></span>
          <span className="rail-calendar-range"><MetricValue pending={loading}>{value ? value.week_start + ' 至 ' + value.week_end : '日期暂无数据'}</MetricValue></span>
        </span>
        <span className="rail-calendar-stats">
          <span className="rail-calendar-stat" data-calendar-week-hours><span className="rail-calendar-stat-label">本周有效</span>{' '}<span className="rail-calendar-stat-value"><MetricValue pending={loading}>{stats ? hoursOrNone(stats.effective_hours) : '暂无数据'}</MetricValue></span></span>
          <span className="rail-calendar-stat"><span className="rail-calendar-stat-label">工作日</span><span className="rail-calendar-stat-value"><MetricValue pending={loading}>{stats ? stats.work_days == null ? '未知' : integer(stats.work_days) + ' 天' : '暂无数据'}</MetricValue></span></span>
          <span className="rail-calendar-stat"><span className="rail-calendar-stat-label">休息 / 禁排</span><span className="rail-calendar-stat-value"><MetricValue pending={loading}>{stats ? stats.rest_days == null ? '未知' : integer(stats.rest_days) + ' 天' : '暂无数据'}</MetricValue></span></span>
        </span>
        {differentPriorities && <span className="rail-calendar-facts">普通件 {hoursOrNone(stats.normal_effective_hours)} · 急件 {hoursOrNone(stats.urgent_effective_hours)}</span>}
      </span>
      <span className="rail-calendar-week">
        <span className="rail-calendar-unit">每日有效工时（小时）</span>
        <span className="hb-cal-strip">{days.map(day => {
          const effective = day.effective, rest = effective && effective.is_rest;
          return <span className={'hb-seg' + (rest ? ' rest' : '') + (!loading && !effective ? ' unavailable' : '')} key={day.date} data-calendar-date={day.date}
            data-calendar-source={day.source} data-calendar-status={day.status} title={value ? dayText(day) : loading ? '正在读取工作日历' : error || '工作日历暂无数据'}>
            <span className="hb-sl">{weekdays[day.weekday]}</span>
            <span className="rail-day-value"><MetricValue pending={loading}>{effective ? rest ? effective.rest_reason === 'priorities_disabled' ? '禁排' : '休息' : amount(effective.effective_hours) : '未知'}</MetricValue></span>
          </span>;
        })}</span>
        <span className="rail-calendar-source"><MetricValue pending={loading}>{source} · 标准 {standardText} / 日</MetricValue></span>
      </span>
    </button>;
  }
  function ResourceRail({ node, counts, onNode, onNavigate, disabled }) {
    const summary = counts.summary || {}, value = summary.data || {}, readiness = value.readiness;
    const items = readiness && readiness.items || {};
    const process = processText(items.process, counts.process && counts.process.total, summary.loading);
    const [choice, setChoice] = React.useState(readCollapsedChoice);
    const compact = choice.collapsed === true;
    function toggle() {
      const next = !compact;
      let error = '';
      try { sessionStorage.setItem(COLLAPSED_CHOICE_KEY, String(next)); }
      catch (_) { error = '无法保存产能链显示设置，当前显示已切换；重新打开时可能恢复原设置。'; }
      setChoice({ collapsed: next, error });
    }
    const countText = key => { const item = counts[key]; return item && number(item.total) ? integer(item.total) + ' ' + C.nodes[key].unit : summary.loading ? '未读取' : '暂无数据'; };
    const notices = [...new Set([
      summary.error && C.message(summary.error), value.readiness_error, value.calendar_error,
      ...chipOrder.flatMap(key => (items[key] && items[key].issues || []).map(issue => C.nodes[key].label + '：' + issue.message)),
      ...(value.calendar ? [
        ...(value.calendar.stats.issues || []).map(issue => '工作日历：' + issue.message),
        ...value.calendar.days.flatMap(day => day.issues.map(issue => day.date + '：' + issue.message)),
        ...value.calendar.holiday_default_efficiency.issues.map(issue => '假期默认效率：' + issue.message)
      ] : [])
    ].filter(Boolean))];
    const tile = (key, tone) => {
      const item = items[key], text = countText(key), count = counts[key];
      const lines = itemLines(item, key), issues = item && item.issues || [];
      return <button type="button" className={'hb-tile ' + tone + (node === key ? ' on' : '')} key={key} disabled={disabled}
        data-rail-node={key} title={[C.nodes[key].label, ...lines, ...issues.map(issue => issue.message), count && count.error].filter(Boolean).join('；')}
        aria-pressed={node === key} onClick={() => onNode(key)}>
        <span className={'hb-tico ' + tone}><Icon name={C.nodes[key].icon} /></span><span className="hb-tbody">
          <span className="rail-tile-title"><span className="hb-tname">{C.nodes[key].label}</span><span className="hb-tmeta"><MetricValue pending={summary.loading}>{text}</MetricValue></span></span>
          {key === 'process' ? <><span className="hb-tmeta rail-process-progress"><MetricValue pending={summary.loading}>{process.lead}</MetricValue></span>
            {process.pending && <span className="hb-tmeta rail-pending">{process.pending}</span>}</> : lines.length > 0 && <span className="rail-tile-facts">{lines.map(line => <span className="hb-tmeta" key={line}><MetricValue pending={summary.loading}>{line}</MetricValue></span>)}</span>}
        </span></button>;
    };
    const lane = (label, tone, keys) => <div className={'hb-lane ' + (tone === 'int' ? 'intl' : 'extl')}>
      <div className="hb-lane-head"><span className="hb-lane-dot" /><span className="hb-lane-name">{label}</span><span className="hb-lane-meas">{tone === 'int' ? '按工时排产' : '按自然日周期'}</span></div>
      <div className={'hb-lane-row rail-resource-links' + (keys.length === 2 ? ' rail-resource-pair' : '')} data-resource-source={keys[0]} data-resource-targets={keys.slice(1).join(' ')}>
        <div className="rail-branch-source">{tile(keys[0], tone)}</div>
        <span className={'rail-branch-link' + (keys.length > 2 ? ' fork' : '')} aria-hidden="true"><Icon name="arrow-right" /></span>
        <div className="rail-branch-targets">{keys.slice(1).map(key => tile(key, tone))}</div>
      </div></div>;
    const chip = (key, label, icon) => <button type="button" key={key} className={node === key ? 'on' : ''} data-rail-node={key} aria-pressed={node === key}
      disabled={disabled} title={C.nodes[key] ? [C.nodes[key].label, itemText(items[key], key)].filter(Boolean).join('；') : label} onClick={() => onNode(key)}>
      <Icon name={icon} /><span>{label}</span>{key !== 'calendar' && <b><MetricValue pending={summary.loading}>{countText(key)}</MetricValue></b>}</button>;
    return <section className={'rail' + (compact ? ' rail-collapsed' : '')} data-collapsed={compact ? 'true' : 'false'} aria-label="产能链" aria-busy={!!summary.loading}>
      <div className="rail-bar"><span className="rail-cap">产能链</span>{summary.loading && <span className="rail-read-state" role="status">正在读取…</span>}
        <Button className="btn link rail-toggle" icon={compact ? 'chevron-down' : 'chevron-up'} aria-expanded={!compact} onClick={toggle}>{compact ? '展开产能链' : '收起产能链'}</Button></div>
      {choice.error && <p className="muted" role="alert">{choice.error}</p>}
      {notices.length > 0 && <ul className="rail-notices" role="alert">{notices.map(text => <li key={text}>{text}</li>)}</ul>}
      {compact && <div className="seg rail-compact" role="group" aria-label="产能链快捷切换">
        {chipOrder.map(key => chip(key, C.nodes[key].label, C.nodes[key].icon))}{chip('calendar', '工作日历', 'calendar-days')}</div>}
      {!compact && <><div className="flow"><div className="hb-hub" style={{ width: '100%' }}>
        <div className="hb-block hero rail-input"><div className="hb-bhead"><span className="hb-bdot io" /><span className="hb-bname">工艺与物料</span></div><div className="hb-bbody">{tile('process', 'io')}{tile('material', 'io')}</div></div>
        <div className="hb-flowarr" aria-hidden="true"><Icon name="arrow-right" /></div>
        <div className="hb-block hero hb-ops"><div className="hb-bhead"><span className="hb-bdot fk" /><span className="hb-bname">加工资源</span></div>
          <div className="hb-bbody">{lane('自制链', 'int', ['op_int', 'machine', 'operator'])}{lane('外协链', 'ext', ['op_ext', 'supplier'])}</div></div>
        <div className="hb-flowarr" aria-hidden="true"><Icon name="arrow-right" /></div>
        <CalendarSummary value={value.calendar} loading={summary.loading} error={summary.error ? C.message(summary.error) : value.calendar_error} node={node} disabled={disabled} onNode={onNode} />
      </div></div>
      <div className="rail-foot"><div className="hb-r-top">
        {(process.lines.length > 0 || value.calendar) && <details className="rail-details"><summary>确认记录与日历规则</summary><div className="rail-detail-content">
          {process.lines.length > 0 && <div><strong>工艺确认记录</strong>{process.lines.map(line => <p key={line}>{line}</p>)}</div>}
          {value.calendar && <div><strong>工作日历规则</strong><p>{value.calendar.basis}</p><p>工厂日期 {value.calendar.factory_today} · 按班次起始日统计</p>
            <p>假期录入默认效率：{value.calendar.holiday_default_efficiency.status === 'known' ? amount(value.calendar.holiday_default_efficiency.value * 100) + '%' : labels[value.calendar.holiday_default_efficiency.status]}。{value.calendar.holiday_default_efficiency.basis}</p></div>}
        </div></details>}
        <span className="hb-r-spacer" />
        <Button className="hb-r-next" icon="arrow-right" disabled={disabled} reason={typeof onNavigate !== 'function' ? '批次管理尚未开通。' : ''} onClick={() => onNavigate('batches')}>下一步 · 批次管理</Button>
      </div></div></>}
    </section>;
  }
  window.ResourceRail = ResourceRail;
})();
