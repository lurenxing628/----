(function () {
  'use strict';
  const C = window.APSResourceContract;
  const { Button, Icon } = window.ResourceControls;
  const labels = { known: '已核实', recorded: '已登记', zero: '0 条记录', unknown: '未知', not_configured: '未配置', unavailable: '无法核实' };
  const weekdays = ['一', '二', '三', '四', '五', '六', '日'];
  const number = value => Number.isFinite(value) && value >= 0;
  const amount = value => window.WorkbenchFormat.number(value, { digits: 1 });
  const countLabels = { active: '启用', inactive: '停用', maintain: '检修', leave: '请假', pending_review: '待复核', unknown: '未知' };
  function processText(item, total, loading) {
    const unavailable = { lead: loading ? '工艺阶段待读取' : '工艺阶段无法核实', lines: [] };
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
    const facts = key === 'op_int' ? [['without_machines', '未绑设备'], ['available_operators', '匹配人员']] :
      key === 'op_ext' ? [['merge_mode_unset', '策略未设'], ['available_suppliers', '匹配供应商']] : [];
    facts.forEach(([field, label]) => { if (number(item.counts[field])) states.push(label + ' ' + item.counts[field]); });
    return states.join(' / ');
  }
  function dayText(day) {
    const origin = day.explicit ? '显式配置' : '服务默认（未配置）';
    if (!day.effective) return day.date + ' · ' + origin + ' · 无法核实：' + day.issues.map(issue => issue.message).join('；');
    const value = day.effective;
    return day.date + ' · ' + origin + '\n' + window.WorkbenchFormat.dateTime(value.window_start, { seconds: true }) + ' 至 ' + window.WorkbenchFormat.dateTime(value.window_end, { seconds: true }) +
      (value.crosses_midnight ? '（跨夜，归班次起始日）' : '') + '\n班次 ' + amount(value.hours) + ' h × 效率 ' + amount(value.efficiency * 100) +
      '%；有效 ' + amount(value.effective_hours) + ' h\n普通件 ' + (value.allow_normal ? '允许' : '不允许') +
      ' / 急件及特急件 ' + (value.allow_urgent ? '允许' : '不允许') +
      (value.rest_reason === 'priorities_disabled' ? '；两类均不许可，非0班次工时' : '') +
      (day.issues.length ? '\n' + day.issues.map(issue => issue.message).join('；') : '');
  }
  function CalendarSummary({ value, error, loading, node, disabled, onNode }) {
    const pending = loading ? '待读取' : '无法核实';
    const stats = value && value.stats, standard = value && value.standard_hours;
    const standardText = standard ? standard.status === 'known' ? amount(standard.value) + ' h' : labels[standard.status] : pending;
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
            {stats ? '本周显式 ' + stats.configured_days + ' 天 · 服务默认 ' + stats.default_days + ' 天' : error || pending}</span></span></span>
        <span className="hb-cal-stats">{[[standardText, '标准工时 / 日', standard && standard.message],
          [stats && stats.work_days != null ? stats.work_days + ' 天' : pending, '本周工作日', '有工时且至少允许普通件或急件的班次起始日'],
          [rest, '休息 / 无许可', stats && stats.known_rest_dates.join('、')]].map(([text, label, title]) =>
          <span className="hb-cs" key={label} style={{ minWidth: 0 }} title={title || undefined}><span className="hb-csv" style={{ fontSize: 12, whiteSpace: 'normal', letterSpacing: 0 }}>{text}</span><span className="hb-csl">{label}</span></span>)}</span>
        <span className="hb-cal-strip-cap" style={{ flexWrap: 'wrap' }}>{caption}</span>
        <span className="hb-cal-strip">{days.map(day => {
          const effective = day.effective, rest = effective && effective.is_rest;
          return <span className={'hb-seg' + (rest ? ' rest' : '')} key={day.date} data-calendar-date={day.date}
            data-calendar-source={day.source} data-calendar-status={day.status} title={value ? dayText(day) : error || pending}>
            <span className="hb-sl">{weekdays[day.weekday]}</span><span className="hb-sb" style={!effective ? { background: 'var(--ui-border)' } : {}}
              aria-label={value ? dayText(day) : weekdays[day.weekday] + ' ' + pending} />
            <span className="hb-sl">{effective ? rest ? effective.rest_reason === 'priorities_disabled' ? '禁排' : '休' : amount(effective.effective_hours) + 'h' : '?'}</span>
            <span className="hb-sl">{value ? day.explicit ? '显式' : '默认' : '?'}</span></span>;
        })}</span>
        {value && <span className="hb-cl2" title={value.basis} data-calendar-week-hours>
          本周有效 {stats.effective_hours == null ? '无法核实' : amount(stats.effective_hours) + ' h'} · 普通 {amount(stats.normal_effective_hours)} / 急件 {amount(stats.urgent_effective_hours)} h
          <br />工厂日期 {value.factory_today} · 班次起始日口径
          <br /><span title={holiday.basis + (holiday.issues.length ? '；' + holiday.issues.map(issue => issue.message).join('；') : '')}>
            假期录入默认效率：{holiday.status === 'known' ? amount(holiday.value * 100) + '%' : labels[holiday.status]}</span>
          {stats.unavailable_days > 0 && <><br />{stats.unavailable_days} 天无法核实</>}
        </span>}
      </span>
    </button>;
  }
  function ResourceRail({ node, counts, onNode, onNavigate, disabled }) {
    const summary = counts.summary || {}, value = summary.data || {}, readiness = value.readiness;
    const items = readiness && readiness.items || {};
    const process = processText(items.process, counts.process && counts.process.total, summary.loading);
    const tile = (key, tone) => {
      const item = items[key], count = counts[key], text = count && number(count.total) ? count.total + ' ' + C.nodes[key].unit : summary.loading ? '待读取' : '无法核实';
      const details = itemText(item, key), issues = item && item.issues || [];
      return <button type="button" className={'hb-tile ' + tone + (node === key ? ' on' : '')} key={key} disabled={disabled}
        data-rail-node={key} title={[C.nodes[key].label, details, ...issues.map(issue => issue.message), count && count.error].filter(Boolean).join('；')}
        aria-pressed={node === key} onClick={() => onNode(key)}>
        <span className={'hb-tico ' + tone}><Icon name={C.nodes[key].icon} /></span><span className="hb-tbody"><span className="hb-tname">{C.nodes[key].label}</span>
          <span className="hb-tmeta">{text}</span>{details && <span className="hb-tmeta">{details}</span>}
          {key === 'process' && <><span className="hb-tmeta" style={{ fontWeight: 600, whiteSpace: 'normal' }}>{process.lead}</span>
            {process.lines.map(line => <span className="hb-tmeta" key={line} style={{ whiteSpace: 'normal', overflowWrap: 'anywhere' }}>{line}</span>)}</>}
          {key !== 'process' && item && item.status === 'unavailable' && <span className="hb-tmeta">关联量无法核实</span>}
        </span></button>;
    };
    const lane = (label, tone, keys) => <div className={'hb-lane ' + (tone === 'int' ? 'intl' : 'extl')}>
      <div className="hb-lane-head"><span className="hb-lane-dot" /><span className="hb-lane-name">{label}</span><span className="hb-lane-meas">{tone === 'int' ? '工时口径' : '周期口径'}</span><span className="hb-lane-count">{keys.length} 项</span></div>
      <div className="hb-lane-row">{keys.map(key => tile(key, tone))}</div></div>;
    return <section className="rail" aria-label="产能链主线" aria-busy={!!summary.loading}>
      <div className="rail-bar"><span className="rail-cap">产能链主线</span><span className="rail-status muted">基础资料 · {summary.error ? '无法核实' : summary.loading ? '读取中' : '只读汇总'}</span></div>
      <div className="flow"><div className="hb-hub" style={{ width: '100%' }}>
        <div className="hb-block hero"><div className="hb-bhead"><span className="hb-bdot io" /><span className="hb-bname">数据输入</span><span className="hb-bmeas">2 源</span></div><div className="hb-bbody">{tile('process', 'io')}{tile('material', 'io')}</div></div>
        <div className="hb-flowarr"><Icon name="arrow-right" /></div>
        <div className="hb-block hero hb-ops"><div className="hb-bhead"><span className="hb-bdot fk" /><span className="hb-bname">工序 · 两条链</span><span className="hb-bnum">5 环节</span></div>
          <div className="hb-bbody">{lane('自制链', 'int', ['op_int', 'machine', 'operator'])}{lane('外协链', 'ext', ['op_ext', 'supplier'])}</div></div>
        <div className="hb-flowarr"><Icon name="arrow-right" /></div>
        <CalendarSummary value={value.calendar} loading={summary.loading} error={summary.error || value.calendar_error} node={node} disabled={disabled} onNode={onNode} />
      </div></div>
      <div className="rail-foot"><div className="hb-ready"><div className="hb-r-top" style={{ flexWrap: 'wrap' }}>
        <span className="hb-rl1">产能就绪度</span><span className="hb-rl2">{summary.loading ? '待读取' : summary.error ? '无法核实' : '未知'}</span>
        <span className="hb-r-tag" style={{ whiteSpace: 'normal', flexShrink: 1 }}>{summary.error || value.readiness_error || process.lead}</span><span className="hb-r-spacer" />
        <Button className="hb-r-next" icon="arrow-right" disabled={disabled} reason={typeof onNavigate !== 'function' ? '批次导航尚未接入。' : ''} onClick={() => onNavigate('batches')}>下一步 · 批次管理</Button>
      </div><div className="hb-cl2" style={{ padding: '0 18px 12px' }} role="status">{readiness ? readiness.message : '未获得整体就绪口径；未推定就绪率。'}</div>
      <div className="hb-r-floor" aria-label="整体就绪度未知" /></div></div>
    </section>;
  }
  window.ResourceRail = ResourceRail;
})();
