---
doc_type: feature-acceptance
feature: 2026-05-28-resource-dispatch-site-records
status: accepted
summary: 资源派工页现场记录、实际情况填写和 Excel 一键导入已完成
tags: [scheduler, resource-dispatch, shop-floor, excel-import]
accepted_at: 2026-05-28
---

# 资源派工现场记录验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-05-28
> 关联方案 doc：`.codestable/features/2026-05-28-resource-dispatch-site-records/resource-dispatch-site-records-design.md`

## 1. 接口契约核对

**接口示例逐项核对**

- [x] `POST /scheduler/resource-dispatch/execution/<op_id>/actual`：route 负责收参并组装 `ExecutionFeedbackContext`，`ResourceDispatchActualRecordService.record_actual_situation()` 负责检查和写入。实际支持用户填实际开工、实际完工、暂停时间、异常记录、反馈人和备注；反馈人可空。
- [x] `POST /scheduler/resource-dispatch/execution/import`：普通页面使用的一键导入入口。`ResourceDispatchActualRecordService.import_workbook()` 先读取 Excel，再复用导入检查；有错误返回 400 和行级错误，不写事件；无错误进入事务写入。
- [x] 兼容入口 `/import/preview` 和 `/import/confirm` 保留。普通页面不再把它们作为主流程；确认阶段仍重新检查并整批写入，避免旧入口绕开校验。
- [x] 模板下载 `/execution/actual-template`：由当前最新正式采用方案生成，Sheet 为 `任务反馈` 和 `暂停明细`，不暴露内部字段。

**名词层“现状 → 变化”逐项核对**

- [x] “现场反馈”页面口径改为“现场记录 / 填写实际情况 / 导入实际情况 Excel”：模板、前端脚本、ViewModel 输出和测试均已改到大白话。
- [x] 反馈人可空：页面不再强制填写；后端通过 `feedback_person()` 统一转成内部兜底值 `未填写反馈人`。
- [x] 暂停/继续从醒目实时按钮改为暂停时间段填写：页面主按钮只保留“填写实际情况”和“查看计划和实际”，暂停用开始、结束或时长表达。
- [x] Excel 导入使用“任务识别码”匹配当前正式计划任务，不要求用户填写 `op_id / schedule_id / state_revision / execution_snapshot_revision`。

**流程图核对**

- [x] 用户打开资源派工页、进入现场记录、单条填写、下载模板、上传 Excel、后端检查、错误不写、无错事务追加事件、刷新任务卡，这些节点都有实际落点。

## 2. 行为与决策核对

**需求摘要逐项验证**

- [x] 单条填写实际开工和实际完工使用用户填写时间，不再只取当前时间。
- [x] 异常记录支持异常时间、异常原因、严重程度和异常说明。
- [x] 暂停时间支持“开始 + 结束”和“开始 + 时长”，结束和时长冲突时报中文错误。
- [x] Excel 普通页面一键导入：用户少点一步；后端仍先检查整份文件，有错就直接报错并且一条都不写。
- [x] 页面没有普通提示“这些记录来自人工填写或 Excel 导入，不代表设备自动采集”。

**明确不做逐项核对**

- [x] 没有新增 MES/DNC 接入、设备采集、设备控制或异常后自动重排。
- [x] 没有静默覆盖旧开工、完工或异常事件；已有记录时返回重复/已记录提示。
- [x] 没有把内部字段放到普通页面和 Excel 模板里。

**关键决策落地**

- [x] 仍复用 `OperationExecutionEvents`，只追加事件，不新建 MES 表。
- [x] 暂停时间仍拆成 `pause` + `resume` 两条事件，复用现有状态读模型。
- [x] 单条填写和 Excel 导入都复用同一套任务计划校验，降低两套规则不一致的风险。
- [x] 普通页面改为一键导入；兼容预览/确认接口保留但不是页面主流程。

**挂载点反向核对**

- [x] 模板挂载点：`templates/scheduler/resource_dispatch.html`。
- [x] 前端交互挂载点：`static/js/resource_dispatch.js`。
- [x] 现场记录 route 挂载点：`web/routes/domains/scheduler/scheduler_resource_dispatch_execution_routes.py` 和 `scheduler_route_registrar.py`。
- [x] 查询 URL 挂载点：`scheduler_resource_dispatch.py` 与 `scheduler_resource_dispatch_query.py`。
- [x] service 挂载点：`resource_dispatch_actual_record_service.py`、`resource_dispatch_actual_excel.py`、`resource_dispatch_actual_import.py`、`resource_dispatch_actual_records.py`。
- [x] 反向 grep 已覆盖新增 URL、按钮文案、禁用词和导入相关函数；未发现清单外主挂载点。
- [x] 拔除沙盘：删除模板入口、JS 导入入口、execution routes 注册、actual service 文件后，本 feature 的用户可见能力会一起消失；残留只会是兼容旧执行反馈的已有能力。

## 3. 验收场景核对

- [x] 页面显示“现场记录 / 填写实际情况 / 导入实际情况 Excel / 下载填写模板 / 查看计划和实际”等大白话。
- [x] 页面不显示“执行事实补录 / 执行事件 / 事件底座 / 生产事实 / 事实台账 / 执行状态读模型”等抽象词。
- [x] 普通页面不显示“不代表设备自动采集”提示。
- [x] 反馈人为空时后端允许写入，并保存内部兜底值。
- [x] 手动指定实际开工、实际完工时间已由 route 回归测试覆盖。
- [x] 完工时间早于开工时间返回中文错误，不写完工事件。
- [x] 暂停开始 + 暂停结束、暂停开始 + 暂停时长、暂停结束和时长冲突、暂停重叠均已由回归测试覆盖。
- [x] Excel 模板不包含内部字段。
- [x] Excel 有错误时一键导入返回错误并不写 `OperationExecutionEvents`。
- [x] Excel 整批无错误时直接写入；浏览器当前页面已能看到真实导入后的开工记录。
- [x] 非最新正式采用方案仍不能写现场记录。
- [x] 前端浏览器验证：打开用户给定 URL 后，普通页面只看到“导入实际情况 Excel”，没有“预览导入 / 确认写入”；“查看计划和实际”记录区为纵向记录块，窄卡可读。

## 4. 术语一致性

- “现场记录 / 填写实际情况 / 导入实际情况 Excel / 下载填写模板 / 查看计划和实际 / 暂停时间 / 异常记录”已在页面和测试中锁住。
- 禁用词在普通页面模板和前端脚本中无命中；测试中只作为反向断言出现。
- “预览 / 确认”仅保留在兼容接口、测试和架构说明中；普通页面不再出现对应按钮和流程。

## 5. 架构归并

- [x] `.codestable/architecture/ARCHITECTURE.md` 已写入资源派工现场记录能力：单条填写、下载模板、一键导入、后端整批检查、有错不写、无错事务追加。
- [x] 架构文档已说明 route 拆分到 `scheduler_resource_dispatch_execution_routes.py`，业务编排拆到 `resource_dispatch_actual_*` service 文件。
- [x] 架构文档已保留系统边界：不做 MES/DNC、设备控制和自动重排；普通页面不暴露内部字段。

## 6. requirement 回写

- [x] `.codestable/requirements/shop-floor-execution-feedback.md` 已更新为当前能力：资源派工页采用现场记录口径，支持手填实际情况、暂停时间段、异常记录、反馈人可空和 Excel 一键导入。
- [x] 变更日志已追加 2026-05-28 的本次能力变更。

## 7. roadmap 回写

- [x] 本 feature 不是从 roadmap 条目起头，frontmatter 没有 `roadmap` / `roadmap_item`，因此跳过 roadmap 回写。

## 8. attention.md 候选盘点

- [x] 本 feature 未暴露必须补入 `.codestable/attention.md` 的新启动注意事项。现有 Win7、Python 3.8、离线静态资源约束已在 `AGENTS.md` 和项目文档里覆盖。

## 9. 遗留

- 后续可单独开 refactor：`static/js/resource_dispatch.js` 和 `static/css/ui_contract.css` 是历史大文件，仍超过 500 行；本次没有强拆前端文件，避免把现场记录功能和前端结构重构搅在一起。
- 后续可单独开纠错 feature：当前仍坚持只追加，不提供覆盖旧开工/完工记录的改错入口。
- 兼容预览/确认接口仍保留，方便旧调用方过渡；普通页面已经不用两步导入。
