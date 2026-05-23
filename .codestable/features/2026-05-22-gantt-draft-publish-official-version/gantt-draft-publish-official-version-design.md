# 甘特图 Scenario 正式采用设计

## 背景

上一阶段已经能把 Draft 保存成 Scenario，并在只读甘特图里用 `scenario_id` 预览。Scenario 仍然只是模拟方案，不会改变正式排产。

本阶段补后端正式采用合同：用户确认采用某个 Scenario 后，系统生成一个新的正式排产版本。旧版本仍然保留，历史页、甘特图、周计划、资源排班和报表继续按版本读取。

## 范围

- 新增 `GanttAdjustmentPublishService`。
- 新增 `POST /scheduler/gantt/adjustments/publish-scenario`。
- 给 `ScheduleAdjustmentScenario` 增加发布审计字段。
- 发布成功后写：
  - `ScheduleVersionSeq`
  - `Schedule`
  - `ScheduleHistory`
  - `ScheduleAdjustmentScenario.status=published`
  - `ScheduleAdjustmentDraft.status=published`
  - `OperationLogs`

## 合同

- 必须输入二次确认文本：`正式采用`。
- 必须填写原因。
- 只允许 `active` Scenario 发布。
- 来源 Draft 必须是 `saved_scenario`。
- 发布前重新校验 Draft；有阻塞问题时拒绝发布。
- Scenario 明细必须和重新校验后的排程明细一致。
- Scenario 的 `base_version` 必须还是当前最新正式版本。
- 发布只追加新版本，不原地修改旧版本。
- 发布不写 `ScheduleCandidate*`。
- 发布人来自服务端可信上下文；当前没有登录权限体系时使用服务端 Web 操作者口径 `web`，接口不接受客户端自报 `published_by`。
- 操作日志是发布事务的一部分；日志写入失败时整次发布回滚。

## 暂不做

- 不在只读甘特图页面开放正式采用按钮。
- 不伪造用户权限系统，也不接受客户端自报发布人。
- 不把 Scenario 自动套到周计划、资源排班或报表的预览入口。
