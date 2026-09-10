---
doc_type: feature-design
feature: wb-batch-workflow
status: approved
created: 2026-09-09
summary: 在既有总体授权内移植批次页面，使用真实批次及永久引用和统一命令回执
tags: [workbench, batch, sqlite]
approval_basis: 本轮用户授权整体移植并继续整个页面；workbench-prototype-migration 总体方案已批准
---

# 范围与依据

按 WBP-BATCH-001..017 分块交付。原型事实源是
`frontend/workbench/prototype/ui_kits/workbench/BaseBatches.jsx`，不是旧管理页。
新增表单只建待排批次，工序在详情明确同步。固定批次号及图号，不新增手改状态、排产配置、分组编辑等旧高级选项。

# 领域边界

- CRUD 复用 `BatchService`；普通写入由 `WorkbenchCommandService` 持有最外层事务并写 receipt。
- 读 raw SQLite 行保留 null/0 和原字段；part/batch 使用 WorkbenchEntityRefs，operation 使用 WorkbenchPlanIdentityRepository。
- 原 `batch_template_ops._build_batch_op_payload` 将 null 工时转 0；本适配器的显式同步复制原字段，不调用该有损投影，不解析路线或自动填工时。同步调用既有 managed 模板 ready 闸门。
- 合并外协组依 `operation_edit_service._resolve_external_ext_days_value` 禁止逐道周期写入；整组模式/周期只读。不照搬原型相冲突的逐道周期规则。
- 有正式/候选/试调/执行引用、已有执行状态的工序不可删除或重建；数量改变也不能破坏这些事实。物料需求随批次删除的影响必须预览，不默默删掉。
- 工序进度来自实际逐序状态；不能从前序完成推断已开工，也不能把部分完成称整批完成。齐套显示与 BatchMaterials 到料事实分开，不以库存推算或自动覆盖。

# 接口与编排

读取 -> 绑定快照及动作能力 -> 预览（批量/同步）-> 用户确认 -> 事务内重新验证 -> 领域写入与 receipt 原子提交 -> 重读。

- GET `/api/workbench/v1/entities/batch`：query/status/ready_status/page/size/sort/direction；字段列筛选由同前缀 POST query 提供。
- GET `/api/workbench/v1/entities/batch/<ref>`：四区详情、工序、齐套原记录及上下文。
- POST 同前缀 `create` / `<ref>/update` / `<ref>/delete`，input 白名单；例如 update `{"fields":{"quantity":12,"due_date":null}}`，省略不修改。
- 同前缀批量/同步 preview -> confirm；预览绑定明确 refs、输入和全量当前依赖事实，不在 GET/preview 中写业务表。
- 前端 `APSBatchAPI.create()`、`BatchWorkspace` 为独立入口；只导出 `register_batch_routes(bp)`，主代理负责全局挂载、main/build 及验收。

# 验收与限制

真实临时 SQLite 覆盖所有表保留、原子性、幂等、stale、动作权限、日期/数量/null/0、删除引用及模板 ready。
组件测试从当前源码局部编译，Chrome109 + mock，只证明组件；不启动生产库、不构建发布资产、不提交、不 spawn。
三种 XLSX 导入及文件下载仍在范围；未交付项在 checklist 保持未完成。无关模块不重构，走现有 Python3.8/Win7 离线档位。
