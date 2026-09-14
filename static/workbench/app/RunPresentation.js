(function () {
  'use strict';

  const stages = {
    queued: '等待计算',
    computing: '正在计算',
    awaiting_reconciliation: '核对排产记录',
    finished: '计算已结束'
  };
  function step(input, checked) {
    return !input || !input.batch_refs.length ? 1 : checked ? 3 : 2;
  }
  function elapsed(run, now = Date.now()) {
    const start = run.started_at || run.accepted_at,
      finish = run.finished_at;
    function local(value) {
      if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/.test(value)) return NaN;
      const date = value.slice(0, 10).split('-').map(Number),
        time = value.slice(11).split(':').map(Number);
      return new Date(date[0], date[1] - 1, date[2], time[0], time[1], time[2]).getTime();
    }
    const begin = local(start),
      end = finish ? local(finish) : now;
    if (!Number.isFinite(begin) || !Number.isFinite(end) || end < begin) return '未知';
    const seconds = Math.floor((end - begin) / 1000),
      hours = Math.floor(seconds / 3600),
      minutes = Math.floor(seconds % 3600 / 60);
    return (hours ? hours + ' 小时 ' : '') + (minutes || hours ? minutes + ' 分钟 ' : '') + seconds % 60 + ' 秒';
  }
  function stage(run) {
    return stages[run.stage] || '排产阶段未知';
  }
  window.RunPresentation = {
    step,
    stage,
    elapsed
  };
})();
