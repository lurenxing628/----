(function () {
  'use strict';
  const C = window.APSResourceContract;
  const { Button, Icon } = window.ResourceControls;
  const labels = { known: '已确认', recorded: '已登记', zero: '0 条记录', unknown: '未知', not_configured: '未填写', unavailable: '暂无数据' };
  const weekdays = ['一', '二', '三', '四', '五', '六', '日'];
  const number = value => Number.isFinite(value) && value >= 0;
  const amount = value => window.WorkbenchFormat.number(value, { digits: 1 });
  const countLabels = { active: '启用', inactive: '停用', maintain: '停机', leave: '请假', pending_review: '待复核', unknown: '未知' };
  const chipOrder = ['process', 'material', 'op_int', 'machine', 'operator', 'op_ext', 'supplier'];
  function shortScreenMedia() {
    // 阈值来自样式令牌，与 10-shell.css 里的 @media (max-height) 保持同一数值；令牌缺失说明样式没加载，直接报错。
    const value = getComputedStyle(document.documentElement).getPropertyValue('--wb-short-screen-max').trim();
    if (!value) throw new Error('样式令牌 --wb-short-screen-max 缺失，无法判断矮屏布局。');
    return window.matchMedia('(max-height: ' + value + ')');
  }
  function useShortScreen() {
    const media = React.useMemo(shortScreenMedia, []);
    const [short, setShort] = React.useState(media.matches);
    React.useEffect(() => {
      const sync = () => setShort(media.matches);
      media.addEventListener('change', sync);
      return () => media.removeEventListener('change', sync);
    }, [media]);
    return short;
  }
  function processText(item, total, loading) {
    const unavailable = { lead: loading ? '工艺阶段未读取' : '工艺阶段暂无数据', lines: [] };
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
    if (total === 0) return { lead: '暂无零件', lines: [] };
    return { lead: '工艺已确认 ' + counts.ready + ' / ' + total + ' 项', lines: [
      '待路线 ' + counts.route + ' / 待归属 ' + counts.source + ' / 待工时 ' + counts.hours,
      '已确认：路线 ' + counts.route_confirmed + ' / 归属 ' + counts.source_confirmed + ' / 工时 ' + counts.hours_confirmed,
      ...(counts.legacy ? ['存量 ' + counts.legacy + ' 项未确认；含路线资料 ' + counts.legacy_route_present + ' 项'] : [])] };
  }
  function itemText(item, key) {
    if (!item) return '';
    const states = Object.keys(countLabels).filter(key => number(item.counts[key]) && item.counts[key] > 0)
      .map(key => countLabels[key] + ' ' + item.counts[key]);
    const facts = key === 'op_int' ? [['without_machines', '未关联设备'], ['available_operators', '匹配人员']] :
      key === 'op_ext' ? [['merge_mode_unset', '周期规则未设'], ['available_suppliers', '匹配供应商']] : [];
    facts.forEach(([field, label]) => { if (number(item.counts[field])) states.push(label + ' ' + item.counts[field]); });
    return states.join(' / ');
  }
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
    const pending = loading ? '未读取' : '暂无数据';
    const stats = value && value.stats, standard = value && value.standard_hours;
    const standardText = standard ? standard.status === 'known' ? window.WorkbenchFormat.hours(standard.value) : labels[standard.status] : pending;
    const days = value ? value.days : weekdays.map((label, index) => ({ weekday: index, date: label, status: 'unavailable', issues: [] }));
    const rest = stats && stats.rest_days != null ? stats.rest_days + ' 天' : pending;
    const holiday = value && value.holiday_default_efficiency;
    const caption = value ? value.week_start + ' 至 ' + value.week_end : '本周排班 · ' + pending;
    return <button type="button" className={'hb-block hero hb-cal-block' + (node === 'calendar' ? ' on' : '')}
      style={{ font: 'inherit', color: 'inherit', textAlign: 'left' }} disabled={disabled} aria-pressed={node === 'calendar'} onClick={() => onNode('calendar')}>
      <span className="hb-bhead"><span className="hb-bdot cal" /><span className="hb-bname">工作日历</span><span className="hb-bmeas">全局</span></span>
      <span className="hb-bbody">
        <span className="hb-cal-top"><span className="hb-cal-ico"><Icon name="calendar-days" /></span><span className="hb-cal-lead">
          <span className="hb-cl1">工时 / 调休 / 加班</span><span className="hb-cl2" title={value ? value.basis : error}>
            {stats ? '本周单独设置 ' + stats.configured_days + ' 天 · 按默认 ' + stats.default_days + ' 天' : error || pending}</span></span></span>
        <span className="hb-cal-stats">{[[standardText, '标准工时 / 日', standard && standard.message],
          [stats && stats.work_days != null ? stats.work_days + ' 天' : pending, '本周工作日', '有工时且至少允许普通件或急件的班次起始日'],
          [rest, '休息 / 不许排产', stats && stats.known_rest_dates.join('、')]].map(([text, label, title]) =>
          <span className="hb-cs" key={label} style={{ minWidth: 0 }} title={title || undefined}><span className="hb-csv" style={{ fontSize: 12, whiteSpace: 'normal', letterSpacing: 0 }}>{text}</span><span className="hb-csl">{label}</span></span>)}</span>
        <span className="hb-cal-strip-cap" style={{ flexWrap: 'wrap' }}>{caption}</span>
        <span className="hb-cal-strip">{days.map(day => {
          const effective = day.effective, rest = effective && effective.is_rest;
          return <span className={'hb-seg' + (rest ? ' rest' : '')} key={day.date} data-calendar-date={day.date}
            data-calendar-source={day.source} data-calendar-status={day.status} title={value ? dayText(day) : error || pending}>
            <span className="hb-sl">{weekdays[day.weekday]}</span><span className="hb-sb" style={!effective ? { background: 'var(--ui-border)' } : {}}
              aria-label={value ? dayText(day) : weekdays[day.weekday] + ' ' + pending} />
            <span className="hb-sl">{effective ? rest ? effective.rest_reason === 'priorities_disabled' ? '禁排' : '休' : window.WorkbenchFormat.hours(effective.effective_hours) : '?'}</span>
            <span className="hb-sl">{value ? day.explicit ? '单独' : '默认' : '?'}</span></span>;
        })}</span>
        {value && <span className="hb-cl2" title={value.basis} data-calendar-week-hours>
          本周有效 {stats.effective_hours == null ? '暂无数据' : window.WorkbenchFormat.hours(stats.effective_hours)} · 普通 {amount(stats.normal_effective_hours)} / 急件 {window.WorkbenchFormat.hours(stats.urgent_effective_hours)}
          <br />工厂日期 {value.factory_today} · 按班次起始日统计
          <br /><span title={holiday.basis + (holiday.issues.length ? '；' + holiday.issues.map(issue => issue.message).join('；') : '')}>
            假期录入默认效率：{holiday.status === 'known' ? amount(holiday.value * 100) + '%' : labels[holiday.status]}</span>
          {stats.unavailable_days > 0 && <><br />{stats.unavailable_days} 天暂无数据</>}
        </span>}
      </span>
    </button>;
  }
  function ResourceRail({ node, counts, onNode, onNavigate, disabled }) {
    const summary = counts.summary || {}, value = summary.data || {}, readiness = value.readiness;
    const items = readiness && readiness.items || {};
    const process = processText(items.process, counts.process && counts.process.total, summary.loading);
    const short = useShortScreen();
    // 矮屏且已进入某个节点时默认收起成一行快捷切换，把高度留给下方列表；节点之间切换尊重用户当前的展开 / 收起选择。
    const [collapsed, setCollapsed] = React.useState(short && !!node);
    const previous = React.useRef({ node, short });
    React.useEffect(() => {
      const was = previous.current; previous.current = { node, short };
      if (short !== was.short || !node || !was.node) setCollapsed(short && !!node);
    }, [node, short]);
    const compact = short && !!node && collapsed;
    const countText = key => { const count = counts[key]; return count && number(count.total) ? count.total + ' ' + C.nodes[key].unit : summary.loading ? '未读取' : '暂无数据'; };
    const tile = (key, tone) => {
      const item = items[key], text = countText(key), count = counts[key];
      const details = itemText(item, key), issues = item && item.issues || [];
      return <button type="button" className={'hb-tile ' + tone + (node === key ? ' on' : '')} key={key} disabled={disabled}
        data-rail-node={key} title={[C.nodes[key].label, details, ...issues.map(issue => issue.message), count && count.error].filter(Boolean).join('；')}
        aria-pressed={node === key} onClick={() => onNode(key)}>
        <span className={'hb-tico ' + tone}><Icon name={C.nodes[key].icon} /></span><span className="hb-tbody"><span className="hb-tname">{C.nodes[key].label}</span>
          <span className="hb-tmeta">{text}</span>{details && <span className="hb-tmeta">{details}</span>}
          {key === 'process' && <><span className="hb-tmeta" style={{ fontWeight: 600, whiteSpace: 'normal' }}>{process.lead}</span>
            {process.lines.map(line => <span className="hb-tmeta" key={line} style={{ whiteSpace: 'normal', overflowWrap: 'anywhere' }}>{line}</span>)}</>}
          {key !== 'process' && item && item.status === 'unavailable' && <span className="hb-tmeta">关联数量暂无数据</span>}
        </span></button>;
    };
    const lane = (label, tone, keys) => <div className={'hb-lane ' + (tone === 'int' ? 'intl' : 'extl')}>
      <div className="hb-lane-head"><span className="hb-lane-dot" /><span className="hb-lane-name">{label}</span><span className="hb-lane-meas">{tone === 'int' ? '按工时排产' : '按周期排产'}</span><span className="hb-lane-count">{keys.length} 项</span></div>
      <div className="hb-lane-row">{keys.map(key => tile(key, tone))}</div></div>;
    const chip = (key, label, icon) => <button type="button" key={key} className={node === key ? 'on' : ''} data-rail-node={key} aria-pressed={node === key}
      disabled={disabled} title={C.nodes[key] ? [C.nodes[key].label, itemText(items[key], key)].filter(Boolean).join('；') : label} onClick={() => onNode(key)}>
      <Icon name={icon} /><span>{label}</span>{key !== 'calendar' && <b>{countText(key)}</b>}</button>;
    return <section className={'rail' + (compact ? ' rail-collapsed' : '')} aria-label="产能链" aria-busy={!!summary.loading}>
      <div className="rail-bar"><span className="rail-cap">产能链</span><span className="rail-status muted">基础资料 · {summary.error ? '暂无数据' : summary.loading ? '读取中' : '只读汇总'}</span>
        {short && !!node && <Button className="btn link rail-toggle" icon={compact ? 'chevron-down' : 'chevron-up'} aria-expanded={!compact} onClick={() => setCollapsed(!collapsed)}>{compact ? '展开产能链' : '收起产能链'}</Button>}</div>
      {compact && <div className="seg rail-compact" role="group" aria-label="产能链快捷切换">
        {chipOrder.map(key => chip(key, C.nodes[key].label, C.nodes[key].icon))}{chip('calendar', '工作日历', 'calendar-days')}</div>}
      {!compact && <><div className="flow"><div className="hb-hub" style={{ width: '100%' }}>
        <div className="hb-block hero"><div className="hb-bhead"><span className="hb-bdot io" /><span className="hb-bname">数据输入</span><span className="hb-bmeas">2 源</span></div><div className="hb-bbody">{tile('process', 'io')}{tile('material', 'io')}</div></div>
        <div className="hb-flowarr"><Icon name="arrow-right" /></div>
        <div className="hb-block hero hb-ops"><div className="hb-bhead"><span className="hb-bdot fk" /><span className="hb-bname">工序 · 两条链</span><span className="hb-bnum">5 环节</span></div>
          <div className="hb-bbody">{lane('自制链', 'int', ['op_int', 'machine', 'operator'])}{lane('外协链', 'ext', ['op_ext', 'supplier'])}</div></div>
        <div className="hb-flowarr"><Icon name="arrow-right" /></div>
        <CalendarSummary value={value.calendar} loading={summary.loading} error={summary.error || value.calendar_error} node={node} disabled={disabled} onNode={onNode} />
      </div></div>
      <div className="rail-foot"><div className="hb-ready"><div className="hb-r-top" style={{ flexWrap: 'wrap' }}>
        <span className="hb-rl1">产能就绪度</span><span className="hb-rl2">{summary.loading ? '未读取' : '暂无数据'}</span>
        <span className="hb-r-tag" style={{ whiteSpace: 'normal', flexShrink: 1 }}>{summary.error || value.readiness_error || process.lead}</span><span className="hb-r-spacer" />
        <Button className="hb-r-next" icon="arrow-right" disabled={disabled} reason={typeof onNavigate !== 'function' ? '批次管理尚未开通。' : ''} onClick={() => onNavigate('batches')}>下一步 · 批次管理</Button>
      </div><div className="hb-cl2" style={{ padding: '0 18px 12px' }} role="status">{readiness ? readiness.message : '系统没有给出整体就绪度，不做推算。'}</div>
      <div className="hb-r-floor" aria-label="整体就绪度暂无数据" /></div></div></>}
    </section>;
  }
  window.ResourceRail = ResourceRail;
})();
