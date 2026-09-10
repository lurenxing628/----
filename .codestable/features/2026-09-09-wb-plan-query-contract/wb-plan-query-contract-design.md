---
doc_type: feature-design
feature: wb-plan-query-contract
status: approved
created: 2026-09-09
summary: 将既有计划身份及明细投影接为工作台统一只读合同
tags: [workbench, plans, readonly]
roadmap: workbench-prototype-migration
roadmap_item: wb-plan-query-contract
approval_basis: 总体方案已获批准，本项按其既定范围展开
---

# 计划查询合同

## 0. 术语

沿用PlanIdentity、Scope、永久plan_ref/operation_ref/task_ref；这些引用不等于旧进程内token。版本、请求角色、实际来源、当前正式和完整性分别表达。候选与正式共用排程明细，不会因此获得正式身份或写入资格。

## 1. 目标与限制

范围是完整计划目录、公开身份、甘特任务/基线/日历/占用与交付风险的统一真实查询，不固定两日日班、不静默换latest。保留旧服务的身份/执行保护，缺摘要、坏关系、缺明细都必须明确。

明确不做：本项不生成候选、不采用、不试调保存、不新增报工事实；不会因为有一个私有目录函数就开放尚未接通的页面。当前目录读取是一个计算节点，不是已完成的公共API。

## 2. 现状与编排

现有 SchedulePlanQueryService/PlanIdentity 负责真实角色和正式资格，旧甘特/超期服务负责明细及时间/风险。新增工作台查询依次：

```text
读取真实目录 -> 解析指定永久plan_ref与Scope
  -> 一致读取快照 -> 任务/基线/日历/风险投影
  -> 脱离内部ID的公开DTO -> 工作台及同范围导出
```

`workbench_plan_catalog.py` 当前返回冻结的私有 PlanCatalogEntry，包括locator、kind、完整性、不可看原因及既有身份模型；不得直接序列化到API。已有历史去重与latest规则保持，最新partial/failed不倒退到旧success。

场景published不冒充active预览，其发布版本只供后续显式导航。坏明细与坏摘要仍在目录中以不可看原因表达。DB/schema错误上抛，不写默认值或引用。

永久计划/任务引用和读快照另行接入持久层。交互接口必须先限制范围/分页，不能直接把全历史、全明细检查路径挂到每次下拉或刷新；完整目录函数可以供显式全量用途，性能必须按真实范围验证。

2026-09-09已补`workbench_plan_page.py`私有有界入口：历史按版本降序seek，场景按内部场景编号BINARY升序seek，默认20、最大50，SQL只取本页加一个lookahead；不计算全量total、不使用OFFSET。冻结页模型与普通实体的Page不同，不直接公开内部游标；后续公开API须包装为不透明上下文。明细校验只处理选中计划及对应场景基线，仍受单个巨大计划规模影响，不能称为固定时延。

原目录43项、分页46项及既有身份10项验证通过，并进入本批1124项联合回归。实测1万个版本/50万正式明细、2000场景/4万场景明细：20版本首段和深段均约43ms、102次SQL；50版本约106ms、252次SQL；20场景约44ms、162次SQL。原始输出在`output/workbench-migration/verification/resources-l20nLi/scale-output.log`；此为本机ARM64/Python3.8.10/SQLite3.35.5成绩，不代表Win7真机。公开引用、计划投影、API、UI仍未接入。

## 3. 验收契约

- 空库、当前/历史正式、代表候选、active/published等身份不混淆，坏数据不冒充健康。
- 所有公开payload使用永久引用；任务严格属于指定计划，执行工序引用跨版本稳定。
- 甘特、详情、风险、基线、日历和导出共享Scope及读快照，缺失目标不静默退回最新。
- 支持真实夜班/跨夜与稀疏范围，完整和缺项状态可追溯，不按原型常数补全。
- 合理分页与复杂规模验证，双尺寸双主题浏览器逐项点击及目视；查询不改正式计划或执行事实。

## 4. 架构关系

与workbench-shell、service-scheduler、ui-gantt衔接。私有目录节点不能替代整个feature验收；完成后再回写需求和本项done。
