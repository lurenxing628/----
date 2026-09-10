---
doc_type: feature-design
feature: workbench-calibration-adoption
status: approved
summary: 实施已批准D05的模板校准采纳后端，主线另行注册下一版DDL及普通写入保护。
tags: [workbench, calibration, adoption]
---

# 依据与范围

沿用 roadmap/workbench-prototype-migration/workbench-contracts.md 第8.2和本轮明确授权，不重开设计审批。
现场未找到独立 decisions 文件及 calibration_statistics*.py；实际统计链为 CalibrationFacts ->
template_lineage_calibration -> calibration_method，保持近20个合格整道样本、至少5个、中位数原口径。
只新增CO独占文件；不修改v27/v28、schema.sql、main、registry、build、scheduler、既有读API或前端。

# 锁接口（供普通写入/Excel代理接线）

`data.repositories.workbench_calibration_adoption_repo.WorkbenchCalibrationAdoptionRepository(conn)`：

- `read_locks(template_operation_refs)`：输入永久模板工序ref的集合，输出`{ref: lock}`。
  lock包含`locked=True, adoption_ref, locked_unit_hours, locked_at, reason, application_operator,
  declared_operator, confirmed, method_version, sample_count, template_revision_after, request_key`。
- 合法完整schema下缺少该ref才表示未锁。缺表、部分DDL、锁审计不一致均明确失败；没有运行时补表。
- `require_unlocked(template_operation_refs)`：必须在调用方写事务中调用；有锁抛`calibration_quota_locked`。
- 公共接口已冻结：保护采纳的`unit_hours`，不是`setup_hours`或排程锁；批量读取最多10000个永久ref。
- 普通工时保存应在写事务重读并保护；Excel在同一事务先读锁，跳过锁项并返回数量/ref/原因，不先覆盖再标记。
- 锁绑定永久ref，不跟随图号/序号替换，不借用Schedule.lock_status。不提供未经批准的解锁/强制覆盖接口。
- 本slice只维护锁事实；普通写/导入的业务保护由另一代理接。完成前禁止启用生产采纳。

# DDL交接

`core.infrastructure.workbench_calibration_adoption_schema`提供`objects()/contract_issues(conn)/install(conn)`。
新增`WorkbenchCalibrationAdoptions`和`WorkbenchCalibrationQuotaLocks`，含唯一约束、延迟命令回执外键、
审计与锁不可update/delete/replace触发器及锁来源校验触发器。没有业务表ALTER、历史回填或自动安装。
按主线/CU补充的“原因/声明人/确认”合同，审计独立新增`declared_operator`和`confirmed=1`；本机身份仍是`application_operator`。
install要求调用方迁移事务，拒绝部分/未知DDL，调用方控制提交回滚。主线下一版统一注册，**不进入v27/v28**。

DDL已冻结为9个对象（2表、7触发器）。`objects()`经`json.dumps(sort_keys=True,separators=(",",":"),ensure_ascii=True)`
编码为ASCII后，SHA-256为`ecdbd579d6518bdf6c6f281705816865cf9cd6cae52a546f3ae51bc0d14757c3`。
此指纹替换未包含声明人/确认字段的旧`00ac16703eb5093d1b7a6a5de09d67374afce55cc0f22b157c005a702b10ffd1`；旧临时fixture应重建，install不会自动修补旧DDL。
主线已告知v28登记完成且只含additive索引；本采纳DDL仍留下一版，不回改v28。

# API交接

显式调用`register_calibration_adoption_routes(bp)`；配置`WORKBENCH_CALIBRATION_ADOPTION_ENABLED`默认false。
只有统一迁移、普通写/Excel保护接好后主线才打开。独立服务也默认关闭。

- `POST /api/workbench/v1/calibration/<suggestion_ref>/adopt-preview`，body为`{"input":{"reason":"...","declared_operator":"..."}}`。
  suggestion_ref即永久template_operation_ref。预览重读真实资料，不依赖旧列表token，不接受浏览器样本/建议值。
  返回建议、样本引用/修订证据、影响范围、锁、`validation.can_adopt`和现有write_context的15分钟令牌。
- `POST .../adopt`，body为`{"input":{"reason":"...","declared_operator":"...","confirm":true},"write_token":"...","request_key":"..."}`。
  原因与声明人绑定预览；用户看完预览后才显式确认。缺confirm字段400，false/非bool确认422 `confirmation_required`，不接受旧reason-only输入或confirmed别名。
  WorkbenchCommandService的BEGIN IMMEDIATE内重核真实来源/样本/旧值/修订/统计/锁。原因最多2000字、声明人最多100字，去首尾空白后绑定；本机身份不接受浏览器提供。
- `GET .../adopt/receipts/<request_key>`：只返回该对象及该动作的已提交回执。404不证明在途请求不会提交，重试保留原key。
  已提交同key/同intent重放在令牌检查之前，过期/服务关闭后仍可取原回执；改原因/对象拒绝。
  回执data独立包含`declared_operator`、`application_operator`和`confirmed:true`，改变声明人也属于请求内容冲突。

# 原子性与保留

只UPDATE目标PartOperations.unit_hours；不同值由原身份触发器推进修订，相同值不做无意义UPDATE但仍记录采纳与锁。
审计存原/新值、模板完整typed快照、原因、声明人、确认标记、本机操作者、时点、方法、样本ref/修订及选择证据。
审计、锁、回执失败整笔回滚。既有批次/计划/报工/旧事件/lineage原数据与SQLite类型不改。
后续真正复制模板使用新定额；不向既有批次同步，不重算已采用计划。
绑定目标所属零件的真实校准范围指纹：同零件其他候选漂移也保守要求重预览；生成时钟不进入写令牌哈希。

# 验证结果与边界

- 接口与DDL：已新增，待主线下一版注册。
- 仓库`.venv/bin/python`为Python 3.8.10。声明人/确认补充后的专项78 passed，13.50秒；最终完整组合201 passed，26.05秒。本目录`test-results.xml`保留JUnit原始结果，0 failure/0 error。
- 新增5个测试文件共78项：主合同12、来源漂移12、事务并发10、DDL12、HTTP32；另有123项回归复用原校准、lineage、write_context及commands合同。
- 定点Ruff覆盖6个新增产品文件、5个测试文件及独占support：All checks passed。
- 定点Pyright 1.1.406，`--pythonversion 3.8`覆盖6个产品文件：0 errors / 0 warnings。未升级工具或依赖。
- 真实临时文件SQLite：同key重放、异key抢同模板、持锁等待后重核、WAL读不到半写、四个写阶段故障、提交故障回滚、同key重试、重开连接查回执。
- 真实来源漂移：旧定额、模板改后改回、来源归属、实例改后改回、lineage撤回、报工更正/变未知、新样本、同号模板删除重建及旧执行原表漂移。
- 原数据保留：逐表typed快照（含NULL/integer/real/text/BLOB）、仅目标模板unit_hours及目标身份revision变化、既有批次/计划/执行/lineage不变、后续模板复制使用新值。
- 全量`scripts/run_quality_gate.py`未运行：当前为多人共用dirty worktree，完整门禁会写共享证明/清理输出，并含启动回归；不越过本轮独占路径及不运行用户实例的边界。以上仅为本轮局部验证，不是clean-worktree proof。
- 未做生产路由联合接入、UI验收、普通维护/Excel锁保护联合验证、下一版迁移注册、冻结包或Win7真机测试。5个新测试的主线registry登记由主线补，CO未编辑registry。
- 未运行生产库、用户预览、打包、stage或commit；工作区大量已有改动，不宣称clean proof。

最终组合命令（cwd为仓库根目录）：

```bash
.venv/bin/python -m pytest -q \
  tests/workbench/test_calibration_adoption.py \
  tests/workbench/test_calibration_adoption_drift.py \
  tests/workbench/test_calibration_adoption_transactions.py \
  tests/workbench/test_calibration_adoption_schema.py \
  tests/workbench/test_calibration_adoption_routes.py \
  tests/workbench/test_template_lineage_calibration.py \
  tests/workbench/test_calibration_method.py \
  tests/workbench/test_calibration_integrity.py \
  tests/workbench/test_calibration_routes.py \
  tests/workbench/test_write_context.py tests/workbench/test_commands.py \
  --junitxml=.codestable/features/2026-09-09-workbench-calibration-adoption/test-results.xml
```

# 独占文件与承重位置

- `core/models/workbench_calibration_adoption.py:12`：预览原因/声明人输入；`:24`：显式确认输入及严格字段合同。
- `core/services/workbench/calibration_adoption.py:40`：preview；`:54`：confirm；`:82`：receipt。复用现有命令及写上下文回调。
- `core/services/workbench/calibration_adoption_evidence.py:15`：事务内读取真实模板、源指纹、样本、统计与锁。
- `data/repositories/workbench_calibration_adoption_repo.py:32`：read_locks；`:66`：require_unlocked；`:73`：精确定额更新；`:91`：原子审计与锁。
- `core/infrastructure/workbench_calibration_adoption_schema.py:26`：objects；`:65`：contract_issues；`:72`：install。
- `web/routes/workbench/calibration_adoption.py:59`：显式路由注册hook，未接main。
- `tests/workbench/calibration_adoption_support.py:32`：独占临时SQLite/Flask fixture，受控本机操作者与时钟。
- `tests/workbench/test_calibration_adoption.py:27`：完整采用及后续模板使用；`:111`：原SQLite类型保留；`:127`：只改目标。
- `tests/workbench/test_calibration_adoption_drift.py:47`：事务重核真实漂移；`:105`：等待其他写事务后重核。
- `tests/workbench/test_calibration_adoption_transactions.py:18`：四阶段回滚；`:41`：双连接竞争；`:74`：半写隔离；`:152`：commit失败。
- `tests/workbench/test_calibration_adoption_schema.py:35`：安装/回滚；`:84`：不可覆盖审计与锁。
- `tests/workbench/test_calibration_adoption_routes.py:28`：真实HTTP/回执；`:81`：即使内部签发令牌，样本不足仍拒绝；`:104`：声明人校验；`:114`：显式确认；`:134`：声明人令牌绑定及独立回执字段。
- 本文及同目录`test-results.xml`为本轮独占交接和验证产物。所有新增内容未stage/commit。
