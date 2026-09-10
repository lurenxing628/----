(function () {
  'use strict';
  const sample = window.APSFieldGanttExample, tasks = [];
  // 十个独立生产单元复用场景结构；资源身份隔离，避免复制后产生假重叠。
  for (let cell = 1; cell <= 10; cell++) {
    const prefix = 'U' + String(cell).padStart(2, '0') + '-';
    sample.model.tasks.forEach((source) => {
      const t = JSON.parse(JSON.stringify(source));
      t.id = prefix + t.id; t.batch = prefix + t.batch;
      t.machine = prefix + t.machine; t.person = prefix + t.person;
      t.reports.forEach((r) => {
        r.id = prefix + r.id; r.reportNo = prefix + r.reportNo;
        r.machine = prefix + r.machine; r.person = prefix + r.person;
      });
      if (t.remainingPlan) {
        t.remainingPlan.machine = prefix + t.remainingPlan.machine;
        t.remainingPlan.person = prefix + t.remainingPlan.person;
      }
      tasks.push(t);
    });
  }
  window.APSFieldGanttDensityExample = {
    context: { ...sample.context, version: '密集演示' },
    model: { ...sample.model, tasks, state: { ...sample.model.state } },
    criticalChain: {
      kind: 'preset-example',
      taskIds: sample.criticalChain.taskIds.map((id) => 'U01-' + id),
      edges: sample.criticalChain.edges.map((edge) => ({ ...edge, from: 'U01-' + edge.from, to: 'U01-' + edge.to,
        reason: 'U01 单元预设关系：' + edge.reason }))
    }
  };
})();
