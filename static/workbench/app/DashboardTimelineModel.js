(function () {
  'use strict';

  const G = window.PlanGanttModel;
  function layout(data, mode, width) {
    const stops = data.downtimes.filter(row => row.valid),
      affected = new Set(stops.map(row => row.machine_ref));
    const tasks = data.tasks.filter(row => row.source === 'internal' && row.machine_ref && (mode !== 'downtime' || affected.has(row.machine_ref)));
    let start = data.time_scope.range_start,
      end = data.time_scope.range_end;
    if (mode === 'downtime') for (const stop of stops) {
      if (stop.start < start) start = stop.start;
      if (stop.end > end) end = stop.end;
    }
    const model = G.layout({
      tasks,
      plan_span: {
        start,
        end
      },
      resources: data.resources.map(row => ({
        ref: row.resource_ref,
        label: row.label
      })),
      projections: {
        calendar: {
          resources: []
        },
        occupancy: {
          resources: []
        },
        baseline: {
          state: 'unavailable'
        }
      }
    }, 'machine', '', false, width);
    const windows = new Map();
    for (const row of stops) {
      if (!windows.has(row.machine_ref)) windows.set(row.machine_ref, []);
      windows.get(row.machine_ref).push(row);
    }
    return {
      ...model,
      windows
    };
  }
  function title(task) {
    return [task.batch_id + ' · ' + task.sequence + ' ' + task.process_label, window.WorkbenchFormat.dateTime(task.start) + ' 至 ' + window.WorkbenchFormat.dateTime(task.end), '计划时长 ' + window.WorkbenchFormat.hours(task.span_hours), task.start === task.end ? '零工时工序，不占设备人员' : null, '设备：' + (task.machine_label || '名称未填写')].filter(Boolean).join('\n');
  }
  window.DashboardTimelineModel = {
    layout,
    title,
    instant: G.instant,
    wire: G.wire,
    ticks: G.ticks,
    visibleRows: G.visibleRows,
    visibleItems: G.visibleItems,
    number: value => window.WorkbenchFormat.number(value),
    timeLabel: value => window.WorkbenchFormat.dateTime(value)
  };
})();
