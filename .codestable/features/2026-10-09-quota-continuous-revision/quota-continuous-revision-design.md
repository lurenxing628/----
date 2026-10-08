---
doc_type: feature-design
feature: quota-continuous-revision
status: approved
summary: 取消工时定额永久锁定，共用现有模板工时写入及版本规则，保留采用历史和批次快照。
roadmap: demand-hours-integration
roadmap_item: quota-continuous-revision
tags: [workbench, calibration, quota, migration]
---

# 0. 依据与术语

2026-10-09 用户明确授权实施路线图第 22 至 26 条，取消永久锁定的决定取代旧校准采用设计。当前定额是 `PartOperations` 的工时；采用记录是解释历史决定的追加事实，不是未来修改的锁。

# 1. 决策与边界

同一道模板允许人工保存、Excel/CSV 导入和再次采用合格校准建议，不要求解锁或删除重建。继续使用模板引用、版本及事务；不建第二套定额库或审批。新建批次使用当前值，已有批次和历史计划保留当时值，更新沿用原批次规则。实际工种变化清空不适用的旧工时。当前版本至少 5 条、最近最多 20 条合格整道样本的中位数算法不变；样本不足不限制人工修订。

范围只含 `quota-continuous-revision`。独立试算、需求草稿、转批次及汇总导出已取消；BOM 与装配仍为未来需求。Win7 x64、Python 3.8、离线、单机不变。

# 2. 名词与编排

旧 `ProcessQuotaProtection` 及所有锁查询、导入跳过、再采用拒绝和工种替换阻断退役。现有入口使用 `ProcessTemplateHours.current` 读取有效模板，`revise(ref, values, expected_revision=...)` 在调用方事务中保存真正变化的工时，并由现有触发器推进版本。例如单件工时从 3 改为 4.5，提交版本与当前一致才写入，旧批次不更新。

普通保存：`PartService.update_internal_hours` 和工作台 `apply_hours`；文件：`ProcessHoursFileOperations`；校准：`adopt_checked_quota`，均调用同一 `revise`。工种替换沿用工作台路线、归属更新中清空工时的行为，去掉旧锁特判。旧路线重建接口的工时保留必须同时匹配序号与实际工种，模板 Model 保留 NULL 未知工时，不把清空值转成 0。

v39 从旧采用表完整复制历史行，去掉模板引用 UNIQUE，保留采用编号、请求号唯一及历史行不可篡改规则；锁表及触发器退役。v29 使用冻结历史 DDL，新库使用当前 DDL。预检改用 `latest_adoption` 展示上次采用并绑定预检版本；即使本次建议与原值相同，另一笔采用也会使旧预检过期。新回执不再宣称锁定，旧回执原文仍可读取。

工时导入已保留解析内容与逐行预检结果，并在写事务中重读现状、比较完整预检；原文件 SHA256 不提供额外责任，本次从工艺文件共同入口和界面合同中删除。原请求、来源版本及事务规则继续承担各自职责。

# 3. 验收契约

- 精确旧锁结构迁移保留全部历史行和旧值，迁移失败完整回滚。
- 人工保存、工作台保存、CSV 和 XLSX 导入能够连续修订同一引用并推进版本。
- 按新模板版本补足样本后可再次采用，两笔采用历史都保留；样本不足时人工仍可修改。
- 实际工种替换不再被历史采用阻断，清空旧换型与单件工时。
- 旧批次、排程行及历史计划原样保留，新批次取得最新定额。
- 重复提交、竞争写入、存储失败仍按原事务与回执协议处理。
- 已采用模板在前端可再次预检和确认；新、旧回执均可读取，界面没有永久锁提示或跳过统计。

# 4. 当前说明与验证入口

架构归并到 `.codestable/architecture/workbench-shell.md`，需求更新 `workbench-production-workflows`，数据模型和字段字典分别同步到开发文档与系统速查表。用户手册更新当前流程，旧采用设计保留历史正文并加替代说明。结果、验证边界和路线图状态见同目录 acceptance。

行为回归：`tests/workbench/test_quota_continuous_revision.py`，复用 `test_calibration_adoption_transactions.py` 和 `test_schema_parity.py`；前端：`tests/workbench/quota_revision_contract.cjs`。业务用例使用临时 SQLite，不写用户实际数据库。
