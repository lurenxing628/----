(function () {
  'use strict';
  // 排产任务一律走共同优化（run_options 由 RunJobAPI 校验为 unified_search_v1），计算阶段直接按共同优化表述。
  const stages = { queued: '等待计算', computing: '正在共同优化方案', awaiting_reconciliation: '核对排产记录', finished: '排产已结束' };
  function step(input, checked) { return !input || !input.batch_refs.length ? 1 : checked ? 3 : 2; }
  function elapsed(run, now = Date.now()) {
    const start = run.started_at || run.accepted_at, finish = run.finished_at;
    function local(value) {
      if (typeof value !== 'string' || !value) return null;
      const normalized = window.WorkbenchDatePickerModel.factoryTime(value), [main, paddedFraction = ''] = normalized.split('.');
      const fields = main.split(/[-T:]/).map(Number);
      // UTC supplies an ordinal for naive factory fields, without applying the browser's timezone or DST.
      return { whole: Date.UTC(fields[0], fields[1] - 1, fields[2], fields[3], fields[4], fields[5]),
        fraction: Number(paddedFraction) / 1000000, precision: (value.split('.')[1] || '').length };
    }
    const begin = local(start);
    const end = finish ? local(finish) : Number.isFinite(now)
      ? { whole: Math.floor(now / 1000) * 1000 + 28800000, fraction: now % 1000 / 1000, precision: 3 } : null;
    if (!begin || !end || !Number.isFinite(begin.whole) || !Number.isFinite(end.whole)) return '未记录';
    const elapsed = (end.whole - begin.whole) / 1000 + end.fraction - begin.fraction;
    if (elapsed < 0) return '时间记录待核对';
    const precision = Math.min(begin.precision, end.precision);
    if (elapsed < 1 && !precision) return finish
      ? begin.whole === end.whole ? '起止记录在同一秒（记录精确到秒）' : '起止记录相差不足 1 秒（记录精确到秒）'
      : '不到 1 秒（起始记录精确到秒）';
    const seconds = precision ? Number(elapsed.toFixed(precision)) : Math.floor(elapsed);
    const hours = Math.floor(seconds / 3600), minutes = Math.floor(seconds % 3600 / 60);
    return (hours ? hours + ' 小时 ' : '') + (minutes || hours ? minutes + ' 分钟 ' : '')
      + window.WorkbenchFormat.number(seconds - hours * 3600 - minutes * 60, { digits: precision, trim: true }) + ' 秒';
  }
  function stage(run) {
    return stages[run.stage];
  }
  window.RunPresentation = { step, stage, elapsed };
})();
