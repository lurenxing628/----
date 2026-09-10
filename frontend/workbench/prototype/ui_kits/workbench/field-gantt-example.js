(function () {
  "use strict";
  const base = window.APSFieldReports.model;
  // 独立演示事实；只共享纯函数及标签表，不继承原状态或 getTask 闭包。
  const tasks = [
    {
      id: 'demo-a-10', batch: 'DEMO-01', name: '回转壳体', op: '10 下料', target: 12,
      machine: 'M-18', person: '刘七', planStart: '2026-09-07T08:00', planEnd: '2026-09-07T10:00', closed: true,
      reports: [
        { id: 'demo-a-10-r1', reportNo: 'DEMO-BG-20260907-0001', revision: 0, recorded: '2026-09-07T09:50',
          qty: 12, start: '2026-09-07T08:00', end: '2026-09-07T09:45', hours: 1.5,
          machine: 'M-18', person: '刘七', remark: '12 件下料完成，比原计划提前 15 分钟。' }
      ]
    },
    {
      id: 'demo-a-20', batch: 'DEMO-01', name: '回转壳体', op: '20 粗车', target: 12,
      machine: 'M-03', person: '张三', planStart: '2026-09-07T10:30', planEnd: '2026-09-07T13:00', closed: true,
      reports: [
        { id: 'demo-a-20-r1', reportNo: 'DEMO-BG-20260907-0002', revision: 0, recorded: '2026-09-07T12:05',
          qty: 5, start: '2026-09-07T10:40', end: '2026-09-07T12:00', hours: 1.1,
          machine: 'M-03', person: '张三', remark: '首段完成 5 件，12:00 至 12:40 停工换刀。' },
        { id: 'demo-a-20-r2', reportNo: 'DEMO-BG-20260907-0003', revision: 0, recorded: '2026-09-07T13:25',
          qty: 7, start: '2026-09-07T12:40', end: '2026-09-07T13:20', hours: 0.6,
          machine: 'M-05', person: '张三', remark: '换刀后张三转 M-05 完成剩余 7 件，整道延后 20 分钟。' }
      ]
    },
    {
      id: 'demo-a-30', batch: 'DEMO-01', name: '回转壳体', op: '30 精加工', target: 12,
      machine: 'M-05', person: '李四', planStart: '2026-09-08T08:00', planEnd: '2026-09-08T11:30', closed: false,
      reports: [
        { id: 'demo-a-30-r1', reportNo: 'DEMO-BG-20260908-0001', revision: 0, recorded: '2026-09-08T09:20',
          qty: 3, start: '2026-09-08T08:00', end: '2026-09-08T09:15', hours: 1,
          machine: 'M-05', person: '李四', remark: '完成 3 件后停工转机，09:15 至 10:00 无实际加工。' },
        { id: 'demo-a-30-r2', reportNo: 'DEMO-BG-20260908-0002', revision: 0, recorded: '2026-09-08T11:15',
          qty: 4, start: '2026-09-08T10:00', end: '2026-09-08T11:10', hours: 1,
          machine: 'M-07', person: '陈敏', remark: '转 M-07 由陈敏接手完成 4 件；剩余 5 件另列预设计划。' }
      ],
      remainingPlan: { start: '2026-09-08T13:00', end: '2026-09-08T15:00', machine: 'M-05', person: '李四' }
    },
    {
      id: 'demo-a-40', batch: 'DEMO-01', name: '回转壳体', op: '40 终检', target: 12,
      machine: 'M-12', person: '王五', planStart: '2026-09-09T08:00', planEnd: '2026-09-09T10:00', closed: false,
      reports: [],
      remainingPlan: { start: '2026-09-09T08:30', end: '2026-09-09T10:30', machine: 'M-12', person: '王五' }
    },
    {
      id: 'demo-b-10', batch: 'DEMO-02', name: '连接法兰', op: '10 下料', target: 8,
      machine: 'M-18', person: '刘七', planStart: '2026-09-07T10:30', planEnd: '2026-09-07T12:00', closed: true,
      reports: [
        { id: 'demo-b-10-r1', reportNo: 'DEMO-BG-20260907-0004', revision: 0, recorded: '2026-09-07T12:05',
          qty: 8, start: '2026-09-07T10:30', end: '2026-09-07T12:00', hours: 1.2,
          machine: 'M-18', person: '刘七', remark: '8 件全部完成，实际起止与原计划一致。' }
      ]
    },
    {
      id: 'demo-b-20', batch: 'DEMO-02', name: '连接法兰', op: '20 粗车', target: 8,
      machine: 'M-03', person: '张三', planStart: '2026-09-07T13:30', planEnd: '2026-09-07T16:00', closed: true,
      reports: [
        { id: 'demo-b-20-r1', reportNo: 'DEMO-BG-20260907-0005', revision: 0, recorded: '2026-09-07T15:05',
          qty: 3, start: '2026-09-07T13:50', end: '2026-09-07T15:00', hours: 1,
          machine: 'M-03', person: '张三', remark: '首段 3 件完成，15:00 停工检查夹具。' },
        { id: 'demo-b-20-r2', reportNo: 'DEMO-BG-20260907-0006', revision: 1, recorded: '2026-09-07T17:10',
          qty: 5, start: '2026-09-07T15:40', end: '2026-09-07T17:00', hours: 1,
          machine: 'M-05', person: '陈敏', remark: '停工 40 分钟后换机换人完成 5 件；工时已核正，整道延后 60 分钟。' }
      ]
    },
    {
      id: 'demo-b-30', batch: 'DEMO-02', name: '连接法兰', op: '30 钻孔', target: 8,
      machine: 'M-07', person: '赵六', planStart: '2026-09-08T08:00', planEnd: '2026-09-08T10:00', closed: false,
      reports: [
        { id: 'demo-b-30-r1', reportNo: 'DEMO-BG-20260908-0003', revision: 0, recorded: '2026-09-08T11:25',
          qty: null, start: '2026-09-08T11:20', end: '', hours: null,
          machine: 'M-07', person: '赵六', remark: 'M-07 转机作业结束后登记开工；本次结束、数量和工时尚未登记。' }
      ]
    },
    {
      id: 'demo-b-40', batch: 'DEMO-02', name: '连接法兰', op: '40 终检', target: 8,
      machine: 'M-12', person: '王五', planStart: '2026-09-09T10:30', planEnd: '2026-09-09T12:00', closed: false,
      reports: []
    },
    {
      id: 'demo-c-10', batch: 'DEMO-03', name: '支撑座', op: '10 下料', target: 16,
      machine: 'M-18', person: '陈敏', planStart: '2026-09-07T13:00', planEnd: '2026-09-07T15:00', closed: true,
      reports: [
        { id: 'demo-c-10-r1', reportNo: 'DEMO-BG-20260907-0007', revision: 0, recorded: '2026-09-07T15:15',
          qty: 16, start: '2026-09-07T13:05', end: '2026-09-07T15:10', hours: 1.7,
          machine: 'M-18', person: '陈敏', remark: '16 件完成，整道延后 10 分钟，保留轻微偏差边界样例。' }
      ]
    },
    {
      id: 'demo-c-20', batch: 'DEMO-03', name: '支撑座', op: '20 粗铣', target: 16,
      machine: 'M-03', person: '张三', planStart: '2026-09-08T08:00', planEnd: '2026-09-08T09:30', closed: true,
      reports: [
        { id: 'demo-c-20-r1', reportNo: 'DEMO-BG-20260908-0004', revision: 0, recorded: '2026-09-08T10:05',
          qty: 16, start: '2026-09-08T08:00', end: '2026-09-08T10:00', hours: 1.8,
          machine: 'M-03', person: '张三', remark: '16 件全部完成，整道延后 30 分钟。' }
      ]
    },
    {
      id: 'demo-c-30', batch: 'DEMO-03', name: '支撑座', op: '30 钻孔', target: 16,
      machine: 'M-07', person: '陈敏', planStart: '2026-09-08T13:30', planEnd: '2026-09-08T16:00', closed: false,
      reports: [],
      remainingPlan: { start: '2026-09-08T14:00', end: '2026-09-08T17:00', machine: 'M-07', person: '陈敏' }
    },
    {
      id: 'demo-c-40', batch: 'DEMO-03', name: '支撑座', op: '40 终检', target: 16,
      machine: 'M-12', person: '王五', planStart: '2026-09-09T13:00', planEnd: '2026-09-09T15:00', closed: false,
      reports: [],
      remainingPlan: { start: '2026-09-09T13:30', end: '2026-09-09T15:00', machine: 'M-12', person: '王五' }
    },
    {
      id: 'demo-d-10', batch: 'DEMO-04', name: '端盖', op: '10 下料', target: 10,
      machine: 'M-18', person: '刘七', planStart: '2026-09-07T15:30', planEnd: '2026-09-07T17:00', closed: true,
      reports: [
        { id: 'demo-d-10-r1', reportNo: 'DEMO-BG-20260907-0008', revision: 0, recorded: '2026-09-07T17:50',
          qty: 10, start: '2026-09-07T15:30', end: '2026-09-07T17:45', hours: 2,
          machine: 'M-18', person: '刘七', remark: '复核坯料后完成 10 件，整道延后 45 分钟。' }
      ]
    },
    {
      id: 'demo-d-20', batch: 'DEMO-04', name: '端盖', op: '20 精车', target: 10,
      machine: 'M-03', person: '赵六', planStart: '2026-09-08T10:30', planEnd: '2026-09-08T12:00', closed: false,
      reports: [
        { id: 'demo-d-20-r1', reportNo: 'DEMO-BG-20260908-0005', revision: 0, recorded: '2026-09-08T10:25',
          qty: 2, start: '2026-09-08T09:30', end: '2026-09-08T10:20', hours: 0.7,
          machine: 'M-05', person: '李四', remark: '提前利用 M-05 空档完成 2 件，与原计划设备、人员不同。' },
        { id: 'demo-d-20-r2', reportNo: 'DEMO-BG-20260908-0006', revision: 0, recorded: '2026-09-08T11:45',
          qty: 3, start: '2026-09-08T10:50', end: '2026-09-08T11:40', hours: 0.7,
          machine: 'M-05', person: '李四', remark: '10:20 至 10:50 停工测量；第二段完成 3 件，剩余 5 件待下午接续。' }
      ],
      remainingPlan: { start: '2026-09-08T15:30', end: '2026-09-08T17:00', machine: 'M-05', person: '张三' }
    },
    {
      id: 'demo-d-30', batch: 'DEMO-04', name: '端盖', op: '30 钻孔', target: 10,
      machine: 'M-07', person: '赵六', planStart: '2026-09-09T08:00', planEnd: '2026-09-09T11:00', closed: false,
      reports: []
    },
    {
      id: 'demo-d-40', batch: 'DEMO-04', name: '端盖', op: '40 终检', target: 10,
      machine: 'M-12', person: '王五', planStart: '2026-09-09T15:30', planEnd: '2026-09-09T18:00', closed: false,
      reports: []
    }
  ];

  window.APSFieldGanttExample = {
    context: { version: '演示', generated: '09-07 08:40', range: '09-07 ～ 09-09' },
    model: {
      tasks, state: { clock: base.ms('2026-09-08T12:00') },
      ms: base.ms, fmt: base.fmt, number: base.number, summary: base.summary, labels: base.labels
    },
    // 人工预设示例链，只解释原计划的工序/资源顺序，不是算法计算结果。
    criticalChain: {
      kind: 'preset-example',
      taskIds: ['demo-a-10', 'demo-a-20', 'demo-b-20', 'demo-b-30', 'demo-c-30', 'demo-c-40', 'demo-d-40'],
      edges: [
        { from: 'demo-a-10', to: 'demo-a-20', type: 'process', reason: 'DEMO-01 下料完成后，壳体坯料才能交给粗车工序。' },
        { from: 'demo-a-20', to: 'demo-b-20', type: 'resource', reason: 'M-03 和张三先加工 DEMO-01 壳体，再切换到 DEMO-02 法兰粗车。' },
        { from: 'demo-b-20', to: 'demo-b-30', type: 'process', reason: 'DEMO-02 法兰粗车形成定位基准后，才能进行后续钻孔。' },
        { from: 'demo-b-30', to: 'demo-c-30', type: 'resource', reason: 'M-07 原计划先完成 DEMO-02 法兰钻孔，再换装 DEMO-03 支撑座夹具。' },
        { from: 'demo-c-30', to: 'demo-c-40', type: 'process', reason: 'DEMO-03 支撑座钻孔完成后，终检才能核对孔位及尺寸。' },
        { from: 'demo-c-40', to: 'demo-d-40', type: 'resource', reason: 'M-12 和王五先检验 DEMO-03 支撑座，再检验 DEMO-04 端盖。' }
      ]
    }
  };
})();
