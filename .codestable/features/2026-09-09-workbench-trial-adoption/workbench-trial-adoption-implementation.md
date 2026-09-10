---
doc_type: feature
status: implemented
created: 2026-09-10
feature: workbench-trial-adoption
summary: CQ 独占实施已保存完整试调场景的真实正式采用
tags: [workbench, trial, adoption]
---

# 范围与接点

- 本轮已批准整体移植的独占 slice；原范围不修改既有 trial/run_candidate/shared/schema/migration/main/UI/registry/build，不 stage/commit，不操作生产库或用户预览，不使用子代理。
- 真 host 测试发现 DATE converter 后，主线明确扩大 CQ 独占写集到 `trial_base.py`、`trial_facts.py` 与新增 `data/repositories/workbench_trial_raw_repo.py`，修复已在该范围内完成；不修改全局 get_connection。
- 新增 `WorkbenchTrialAdoptionService.preview(scenario_ref)`、`adopt(scenario_ref, write_token, request_key, value)`、`lookup(scenario_ref, request_key)`。
- `register_trial_adoption_routes(bp)`：POST `/api/workbench/v1/trial/scenarios/<scenario_ref>/adopt-preview`（空 JSON）；POST 同场景 `/adopt`（`write_token/request_key/input`）；GET 同场景 `/adoption-commands/<request_key>`。
- input 与真实 candidate adopt 相同：`confirm:true/reason/declared_operator`。本机实际操作者独立记录。
- 使用 `trial.scenario.adopt` 与 scenario_ref 做命令身份；审计与回执明确 scenario_ref/draft_ref，不伪造 candidate_ref。
- 复用现有 `WORKBENCH_CANDIDATE_ADOPTION_ENABLED` 真 host 合同、HTTP draining、原 `_RUN_SCHEDULE_LOCK` 与 `WorkbenchCommandService`。不增加独立启用开关。
- 主线已交付 `core.services.workbench.official_plan_persistence.persist_official_plan_in_tx` 中性持久化接点，现有 candidate wrapper 保持原合同；CQ 已接入，不复制 Schedule 写入实现。
- 不需要新增 DDL；冻结 v27 保持不变。主线已注册本路由；测试 registry 与完整交付由主线统一维护。
- UI 稳定合同见同目录 `workbench-trial-adoption-api.md`，不要求前端重写保存时的历史 validation。

# 验证原则

1. 读取原 scenario 快照、永久场景行和已关闭源 draft，校验全范围与永久来源一致。正式行只来自保存的场景安排，源 draft 仅补充未公开的原 SQLite 字段。
2. 当前基线必须仍等于原基线。执行、原工序、数量、工时、永久资源、日历、停机、资质、工艺链、固定与范围外占用重新验证。
3. 复用真实 scheduler 输入、payload、资源日历与执行持久化保护。完整范围才准入，未知证据明确拒绝；不保留永远 blocked 的占位实现。
4. confirm 在 BEGIN IMMEDIATE 和原全局 run 锁内重读，正式 version/ref/任务身份/审计/receipt 在一个事务内提交；旧正式、执行及 SQLite 原始类型保留。
5. 原 key 重放先于 token 校验；未知 ACK 只查询原 key，不声称未观察到回执等于不会提交。

# 实现与验证

- 已读取 AGENTS、attention、体系入口、合同第7节、试调交付记录与真实 candidate adoption 全链。
- symbol_locator 普通查询找到持久化调用方和 validation 依赖；deep SCIP 对新增未提交函数无结果，使用真实源码定点核对。后续普通查询因源码变化自动重建静态快照，出现过并行 JSON 读取冲突；未手动刷新 SCIP，也未改索引工具。
- 正式采用完整实现；场景/原关闭草稿/保存回执一致性、范围、实时事实和命令事务已连接。保存快照与场景任务不可重写；采用问题引用明确重绑到场景任务，不返回源草稿任务假链接。
- Python 3.8.10 下 CQ 专属 78 项通过；原试调包括1000/10000任务规模在内的56项回归通过。均为真实临时文件 SQLite，不使用生产数据。
- CQ 覆盖：plan/candidate来源的真实采用、完整保存安排与窄显示范围、两连接同key单次与异key竞争、7处持久化故障全部回滚、COMMIT前失败与ACK丢失、进程退出与冷恢复、过期token、原key回执、基线/执行/设备/人员/工艺/日历/锁定漂移、完整证据缺失、旧正式/执行/任务身份及BLOB类型保留。
- 真实 factory/launcher/root blueprint 测试通过：不开测试专用启用开关，完成run→trial→save→adopt；HTTP stopping拒绝新请求且等待在途场景采用结束，才停worker和释放原DB锁。仅替换socket server，不启动用户预览。
- Ruff、Python3.8 AST（20个本轮产品/测试文件）、产品复杂度/大小扫描通过，复杂度/大小新增违规均为0。
- v27 `objects()` 按冻结口径 SHA-256 仍为 `f025c779d645c7a39666681c0c285eddf119a172cb93e339809e44282b972164`，未改DDL。
- 完整门禁未跑：共享工作区仍有大量他人在途改动，主线负责共享evidence/registry、完整门禁与离线打包；本结果不是 clean-worktree proof。未做Win7实机/安装包运行验证。
- 分件场景沿用现有共用candidate采用的证明边界：piece_adoption_unsupported或其上游分件输入适配缺证据时明确阻断；不冒充已完成任意分件链的正式采用。已有完整非分件场景真实采用成功测试，不是全域永远blocked的占位实现。

# 生产连接修复

- 原因是生产 get_connection 开启 PARSE_DECLTYPES/PARSE_COLNAMES，试调 SELECT * 读出的 date 不能进入原值JSON；进一步核对发现共用候选输入还直接比较 date 与字符串。
- 新 raw repo 使用规范 quote 的 PRAGMA table_info 与一元 `+` 列表达式，不更改连接或全局转换器。使用合成列别名以避免旧字段名中的 `[DATE]` 再次触发 COLNAMES；结果按真实字段名映回，保持TEXT/BLOB/NULL/INTEGER/REAL。
- 试调完整plan SQL与范围门禁继续复用原实现；detail也取消Python converter，并以同一原批次的真实due_date替代显示SQL的CAST结果，防止BLOB/数值日期被字符串化。
- 坏交期继续允许保留冲突草稿，原值留在原表与草稿，validation明确blocker，comparison不得算按时；非法或不可无损表示的安排时间拒绝创建，不猜默认时间。
- `trial_adoption_input.py` 只把同一事务已读取的raw事实接给原 `_prepare/_projection_map` 与model/chain校验，复用现有全部执行/资源/日历/freeze builders；不绕开校验、不改共用候选行为，也不生成/替换场景安排。
- 已验证生产连接与普通连接的facts/hash一致，跨连接preview→create→save→adopt的token不漂移，有值的真实ready_date能够正式采用，非法日期保持原类型并明确阻断。

# 文件与收尾

- 新增产品8文件：`workbench_trial_adoption.py`模型，`trial_adoption.py/_input.py/_storage.py/_validation.py/_persistence.py`五服务，`workbench_trial_raw_repo.py`与采用路由。
- 授权修复既有产品2文件：`trial_base.py`、`trial_facts.py`。
- 新增8个 `test_trial_adoption*.py` 测试文件与2个独占support；新增本实现记录与API合同。
- CQ写集均未stage/commit；主线新增的中性持久化、根蓝图、v28/registry不属于CQ提交内容，也未被CQ覆盖。

```bash
.venv/bin/python -m pytest tests/workbench/test_trial_adoption*.py -q --tb=short
.venv/bin/python -m pytest tests/workbench/test_trial_lifecycle.py tests/workbench/test_trial_validation.py tests/workbench/test_trial_edges.py tests/workbench/test_trial_atomic.py tests/workbench/test_trial_api_schema.py tests/workbench/test_trial_scale.py tests/workbench/test_trial_catalog.py -q --tb=short
```
