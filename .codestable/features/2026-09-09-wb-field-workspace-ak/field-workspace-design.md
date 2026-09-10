---
doc_type: feature-design
feature: wb-field-workspace-ak
status: approved
summary: AK 现场记录整页、执行 API 与逐次十列 XLSX，消费 AJ 唯一执行台账
tags: [workbench, execution, field, xlsx]
---

# 范围与边界

- 依据本轮已批准全移植和 workbench-contracts.md 第 3、4、6 节实施，不另起任务，不调用子代理。
- AK 仅新增 `field_workspace*.py`、`field_report_files*.py`、`execution*.py`、九个 Field 前端文件、专属测试和此目录文档。
- AJ 独有 `ExecutionLedgerService` / `WorkbenchProductionReportService` 及执行 schema；主线负责迁移、共享 pending namespace、页面入口、资产接合与旧消费者保护。
- 不修改既有执行、排产、批次、报表、共享 transport/session/main/build/global __init__，不访问 productionDB，不 build/commit。

# 接口

1. `web.routes.workbench.execution.register_execution_routes(bp)` 注册 `/api/workbench/v1/execution`。
2. GET `/tasks`、`/tasks/<task_ref>` 返回统一 QuerySuccess；过滤先于分页，快照绑定完整原范围。
3. POST `/tasks/<task_ref>/reports`、`/reports/<report_ref>/supplement|correct` 接受 CommandInput，直接调用 AJ `execute` 拥有最外层事务。
4. 文件 GET `/files/template|export`，POST `/files/preview|confirm`；GET `/files/errors?preview_ref=...` 下载原预检问题清单。
5. 确认只接受 `{preview_ref}`，调用 AJ `execute_import`。已提交请求在读取过期 preview/bytes 前按 action、context、input_hash 回放；同键异预检拒绝。
6. `window.FieldWorkspace({onNavigate, initialContext, adapter?})`；正式 adapter 为 `FieldAPI.create()`，包装现有 base query/execute，pending namespace/kind 均为 execution。
7. task/report/revision 引用为 48 hex；preview 为 32 opaque `[A-Za-z0-9_-]{32}`，不限制为 hex。

# 数据流程

`GET -> 原计划永久身份 -> 真实计划任务 -> AJ project_operations -> 展示字段/范围 -> 分页`

`Excel bytes -> 包结构/十列解析 -> 当前范围唯一任务及资源映射 -> AJ preview_batch -> 原 bytes 保留 -> 显式确认 -> AJ execute_import -> 回执`

- 没有自建累计、状态或完工推断；未报工、已知零、数量未知、部分完工、合法旧 finish 都来自 AJ 投影。
- 对旧完工补齐必须明确 `legacy_fact_ref + reason`，不伪造 report_ref/event_id，也不将每次结束翻译为 finish。
- 文件报工号重复只补未知，已知冲突拒绝；无号输入按原 bytes SHA-256 和原行号生成稳定建议号。不会按开工时间或同批同序猜跨版本身份。
- 查询、预检、模板和导出不创建 schema、不补身份、不写业务表；测试用 PRAGMA query_only 强制验证。
- 导出全 scope 而非页面，逐次表严格十列、5000 行上限。CSV、旧执行反馈模板不混入本流程。
- XLSX 拒绝越列、重复/倒序物理行、重复/错位单元格、合并、公式和错误值；未知保持空白，零保持数值；支持 Excel 日期时间。
- API 私有快照经 `plain_plan_facts` 保留 BLOB/date 类型。实际公共旧字段由 AJ 处理不可展示诊断，不替换原始存储。

# 页面与导航

- 安静桌面表格、行内新增/补齐/更正、实际设备人员选择、数量步进/最大值、起止/有效工时/备注/原因/声明人、原值历史、逐次时间线、旧事件、文件弹窗。
- 页面根元素自带 `.plana`；本页主题映射使用真实 `--ui-*`，弹窗背景和定位不依赖 harness 额外父类。
- 失败不是空结果，未读取不显示零统计；未核实命令锁住本页写入、翻页、刷新、返回，刷新后查询原 request_key，不换请求重做。
- 接 AL 页面名 `fieldgantt`，task_ref 优先、entity_ref 兼容；初始 task_ref 可定位非第一页，严格绑定原 plan。
- 接收日期、计划重叠范围、设备/人员范围、batch_ids、query；operation_ref 仅作 task_ref 的辅助一致性核验。
- return_to 使用 `{view, context}`，不嵌套回来源链；本页 state 筛选只保存在返回上下文，不冒充实际甘特范围。

# 验收边界

- 专属 pytest + AJ 联合领域回归；Chrome 109，1920x1080/1392x924、浅深两色，键盘输入/控件点击，mock 与真实临时 Flask 分开标记。
- 浏览器源码仅测试进程内 JSX 编译，不修改交付静态资产；证据绑定源文件 SHA-256。
- 此包不能声称主线 v25、正式 bundle、旧调度消费者保护或 Win7 真机验收已完成。
