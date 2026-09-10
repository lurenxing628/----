---
doc_type: feature-design
status: implemented
feature: workbench-dashboard
created: 2026-09-10
summary: CR exclusive backend slice under approved workbench contracts 8.3
tags: [workbench, dashboard, sqlite]
---

# CR 接口交接

本批按已批准 roadmap D01-D08、workbench-contracts 第 2/3/4/8.3 节直接实施。
不改主线注册、schema.sql、version、frontend、build、旧预览及现有共享/计划/执行模块。

## 接口冻结

- `register_dashboard_routes(bp)` 由主线调用；前缀 `/api/workbench/v1`。
- GET `/dashboard`；GET `/dashboard/items/<item_ref>`；GET `/dashboard/items/<item_ref>/history`。
- POST `/dashboard/items/<item_ref>/transition`；POST `/dashboard/items/<item_ref>/reopen`。
- 写入沿用 `CommandInput`、`WorkbenchCommandService`、`workbench.command_receipt`。unknown 只查原 request_key，不新建请求重做。
- 参数 `category=all|delivery|actual|external|downtime|material|candidate`，`status=all|open|new|following|awaiting_verification|closed`，`query`，`sort=subject|category|status|deadline`，`direction=asc|desc`，`page>=1`，`size=1..100`，`snapshot_ref`，`source=production`。详情、历史和翻页必须带原列表快照及原筛选。
- QuerySuccess.data：`plan`、`as_of`、`categories`、`resource_pressure`、`candidate_catalog`、`items`、`page`、`scope`；详情为 `item`。条目字段 `item_ref/category/subject/source/source_state/risk/handling/allowed_transitions/write_context/navigation`。
- `risk.active=true|false|null` 与 `handling.status` 正交；类别 `state=loaded|no_data|no_official_plan|unavailable|not_connected`，`risk_count=null` 表示不能完整评估，`known_risk_count` 是确定风险数。`evaluation_gaps` 单列无法评估的来源引用和原因，不把它们造为报警。清单只包含已确认风险和已有处置历史的条目；来源消失/版本变化不能当成风险消除。
- `resource_pressure` 复用 `project_plan_calendar/project_plan_occupancy`，只认同一正式计划、日历、设备、人员及有效停机。占用小时不是有效加工工时，缺少可用产能时利用率为 null，不填写样板峰值。
- `candidate_catalog` 复用真实 `WorkbenchRunHistoryQueryService` 的有界目录页（20项，含 total/has_more），`selection=null`，按明确 run_ref 进入 `/scheduling/runs/<run_ref>/candidates`。其 kind 是 `directory_not_risk`，risk_count 不适用；不自动选候选、不把目录摘要当完整候选验证。
- `source` 带真实 `batch_ref/task_ref/operation_ref/plan_ref` 与可展示依据；历史 `source_snapshot` 带永久 snapshot_ref、工厂本地 as_of、原公开依据。此永久历史引用不等于可续读列表的短期 meta.snapshot_ref。私有原值保留 SQLite 类型，不外显数据库裸键。
- transition 必填 `target_status/remark`，其余合同字段省略表示不修改，null 表示明确清空（仍受状态必填规则校验）。非 new 需 owner/deadline/action；closed 需秒精度 completed_at、具体 completion_evidence 和 evidence_reference_text。`evidence_ref` 非空在本批明确拒绝，不把文字当文件。
- closed 的 allowed_transitions 为空，只给 reopen 能力；reopen 输入仅 `{reason}`，转 following，清空本轮完成字段，旧凭据永久在历史中。

## Schema Hook

`core.infrastructure.workbench_dashboard_schema` 提供 `objects()`、`contract_issues(conn)`、`install(conn)` 及具名别名。install 只允许调用方迁移事务；不 BEGIN/COMMIT、不修改版本、不修复部分安装。依赖已安装 metadata/plan identity 和 MachineDowntimes。

新表保存条目永久来源映射、处置状态、追加历史和停机永久引用。安装为已有来源建立映射，新来源由独占 DDL 的触发器建立映射；映射存在不代表报警。GET 严格只读，不分配引用。主线在独立测试迁移后注册，CR 不运行生产迁移。

DDL 冻结为 **21个对象：4表、1索引、16触发器**，含 UPDATE/DELETE 和 REPLACE 保留保护。`objects()` 按 `json.dumps(sort_keys=True,separators=(",",":"),ensure_ascii=True)` 编码为 ASCII 后，SHA-256 为 `623ec4c193f30535df5848acd335159471738924c5e0fc08a08629b796d03e03`。

当前主线 `CURRENT_SCHEMA_VERSION=28`。CO 保持9对象、指纹 `ecdbd579d6518bdf6c6f281705816865cf9cd6cae52a546f3ae51bc0d14757c3`。两套对象无重名，任意安装顺序与整笔回滚均有临时库测试；均由主线决定下一版（v29）统一安装/版本注册，不回改冻结v28。主线可先调用路由 hook，未安装 Dashboard DDL 的 GET/POST 均明确返回 `503/dashboard_unavailable/committed:false`，不自动建表。

## CY 前端独占顺序

DTO/路由名已交付冻结。CY 独占 `frontend/workbench/app/Dashboard*.js|jsx`，加载顺序为 `DashboardContract.js` → `DashboardSession.js` → `DashboardStyles.jsx` → `DashboardPanels.jsx` → `DashboardHistory.jsx` → `DashboardHandling.jsx` → `DashboardWorkspace.jsx`，依赖已有 ResourceControls/统一控件。CR 不编辑这些文件。

CY 同时独占 `tests/workbench/test_dashboard_widgets.py`、`dashboard_widgets_support.py`、`dashboard_widgets_probe.cjs`。CR 验证使用明确后端测试列表，不再用 `test_dashboard*.py` 通配符，也不让 Ruff 自动修复扫描这些前端测试。

CommandResult 沿既有 `result/receipt_ref/replayed/data`。`data` 固定为 `item_ref/handling/history_ref/risk/source/refresh_required`；没有新增 `confirmed`。回执必须核对原 item_ref 和真实 handling；unchanged 的 history_ref 为 null，不新增历史。unknown 只按原 request_key 查结果，不自动换键重做。

## 边界

实际外协发出/回厂另后续 slice：本批 external 明确 not_connected，数量 null，目标保留 `/api/workbench/v1/outsourcing/receipts` 但不可提交。现场回填入口指向已有统一 execution/tasks API，必须先从执行服务读取该 task 的 write_context，不能拿处置令牌报工；不建独立报工事实。非当前任务不允许此入口写入。

目录/来源上限：10000个当前计划工序、10000批次及处置清单条目；单来源原始事实50000行；响应及单历史证据8MiB，超过明确413。条目范围筛选/排序后分页；历史独立 `history_page`（仅 history 端点接受），同一列表快照绑定原筛选和 as_of。安装映射不是报警创建，没有任何 GET 写业务表或自动迁移。

执行偏差：唯一投影的待核实反馈、超过10分钟完工偏差、暂停/异常；有效工时超耗仅在完整逐次完成记录可核实时比较 `有效加工小时 / (当前批次工序unit_hours * 权威target_quantity) > 1.2`，不含准备/跨度工时。部分记录、旧完工缺工时明确未知，旧完整完工证据不变成未完成。

## 进度

1. 合同与 DTO/schema hook：已落地，独立安装/回滚/幂等测试通过。
2. 真实读投影、原子处置与路由：已实现，隔离 Blueprint 实测。
3. SQLite 复合/并发/旧值类型/rollback/ref 漂移：定向测试通过。`get_connection` 的 PARSE_DECLTYPES/COLNAMES 已用真实临时文件库覆盖 DATE/NULL/BLOB 的目录、详情和 transition；未装schema的GET/POST为503。此证明不等同于完整主线factory/Win7宿主证明。最终命令与原始结果见验收记录。
4. 主线注册、前端、最终整仓门禁、Win7：不在本批交付证据内。
