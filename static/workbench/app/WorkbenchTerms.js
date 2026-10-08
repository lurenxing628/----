(function () {
  'use strict';

  // 用户可见文案的前端词表与句式模板。词表决策：.codestable/compound/2026-09-13-decision-ui-copy-glossary.md
  const sentence = text => /[。！？；]$/.test(text) ? text : text + '。';
  window.WorkbenchTerms = Object.freeze({
    overdue_count: '预计超期批次',
    delay_hours: '超期时长',
    total_tardiness_hours: '总拖期',
    utilization: '利用率',
    candidate: '候选方案',
    official_plan: '正式计划',
    trial: '试调',
    trial_draft: '试调草稿',
    trial_scenario: '试调方案',
    hours_unit: '小时',
    handler: '经办人',
    recorder: '记录人',
    owner: '责任人',
    // 2026-09-21 全站收口：同一概念只留一个叫法，各工作区从这里取，不再各写一份。
    refresh_latest: '刷新最新资料',
    accept_latest: '已核对，继续编辑',
    personal_calendar: '个人日历',
    name_missing: '名称未填写',
    legacy_field_records: '历史现场记录',
    shared_operation: '共同工序',
    overdue: '超期',
    current_official: '当前正式',
    historical_official: '历史正式',
    baseline_plan: '排产时的正式计划',
    initial_plan: '初始计划',
    // 排产记录状态与候选方案状态：值班台、执行排产、排产记录、试调列表共用同一套叫法。
    run_statuses: Object.freeze({
      queued: '等待计算',
      running: '正在计算',
      complete: '计算完成',
      partial: '部分完成',
      failed: '计算失败',
      interrupted: '已中断'
    }),
    candidate_statuses: Object.freeze({
      completed: '已完成',
      partial: '部分完成',
      failed: '失败',
      skipped: '已跳过'
    }),
    // 齐套规则与拆批操作分开。旧 split 记录实际按整批齐套执行，不能据此声称已经拆批。
    material_strategies: Object.freeze({
      strict: '等整批物料齐套',
      stage: '按工序物料齐套',
      split: '等整批物料齐套（原分批开工入口）'
    }),
    material_descriptions: Object.freeze({
      strict: '这批全部用料到齐后，再安排工序开工。',
      stage: '每道工序只等本序和前序用料，不等后续用料。'
    }),
    material_strategy: (value, readyCheck) => readyCheck === false ? '未启用（齐套检查已关闭）' : value === null || readyCheck === null ? '未记录' : window.WorkbenchTerms.material_strategies[value || 'strict'] || '记录无效',
    // 不重排时段：排产检查、排产任务、排产记录、候选方案的回显用同一套说法。没有这一项的是旧记录，当时按交付设置。
    hold_window: (value, invalid) => value === undefined ? '未记录（按当时的交付设置）' : invalid ? '记录无效' : value === null ? '不设' : value.start.replace('T', ' ') + ' 至 ' + value.end.replace('T', ' '),
    // 报工执行状态：现场记录、实际甘特、报表、校准、排产候选、试调和值班台共用；与后端导出的“排产时报工状态”一致。
    execution_states: Object.freeze({
      unreported: '待报工',
      started: '已开工',
      partial: '部分完成',
      paused: '已暂停',
      exception: '异常',
      complete: '已完工'
    }),
    // 报工记录的数据完整性：与后端报表、实际甘特导出的叫法一致。complete 在这里是“完整”，不是执行状态的“已完工”。
    data_quality: Object.freeze({
      complete: '完整',
      incomplete: '不完整',
      legacy_incomplete: '历史资料不完整',
      invalid: '需复核'
    }),
    // 交付判断：计划详情、执行排产、值班台、试调共用；与正式计划导出一致。
    delivery_risks: Object.freeze({
      overdue: '预计超期',
      on_time: '预计按期',
      unknown: '暂无数据'
    }),
    // 页头身份标签允许 v3；句子里写“第 3 版”。
    plan_version: version => '正式 v' + version,
    download_started: name => '已交给浏览器下载：' + name,
    data_as_of: time => '数据截至 ' + time,
    // 逐次报工的动作名：现场、报表、校准三个工作区共用，不再各写一份。
    report_actions: Object.freeze({
      create: '新增',
      supplement: '补齐',
      correct: '更正'
    }),
    actions: Object.freeze({
      add: '新增',
      save: '保存',
      confirm: '确认',
      cancel: '取消',
      clear: '清除',
      import: '导入',
      export: '导出',
      download: '下载',
      refresh: '刷新',
      query_result: '查询结果',
      adopt: '采用'
    }),
    // 结果未知这一族提示只从这里取，各工作区不再自己写。
    outcomes: Object.freeze({
      pending: action => '上次' + action + '的结果还没查到，可能已经生效。请点「查询结果」，不要重复提交。',
      rejected: (action, reason) => '上次' + action + '没有生效：' + sentence(reason) + '填写内容已保留，改好后重新提交。',
      done: (action, next) => action + '已完成。' + (next ? sentence(next) : ''),
      unknown: action => action + '结果不确定，可能已经生效。请刷新后核对，不要重复提交。',
      stale: '数据已更新，请刷新后重试。刚才的选择已保留。',
      unavailable: '此功能尚未开通。',
      failure: '操作没有完成。请刷新重试；仍不行请联系维护人员，并告知下方编号。'
    })
  });
})();
