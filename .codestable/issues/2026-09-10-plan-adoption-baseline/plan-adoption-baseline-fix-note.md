---
doc_type: issue-fix
status: implemented
created: 2026-09-10
summary: DA 接入新正式采用的原始基线证据，不改共享正式写入与迁移
tags: [workbench, plan, baseline, adoption]
---

# 结论与范围

- 原因：`core/services/workbench/plan_baseline.py` 对非旧调整场景直接返回 `not_recorded`，未消费新正式采用已有的审计、receipt 和受理快照。
- 已接通 `candidate_adoption` 与 `trial_adoption`。真实 engine -> candidate -> 正式v1 -> trial -> 正式v2 测试通过；第二次直接采用 candidate 的正式版本也通过。
- DA 产品写集仅 `core/services/workbench/plan_baseline.py`、同目录四个 `plan_adoption_baseline*.py` helper，以及事先报告路径的 `frontend/workbench/app/PlanContract.js`、`PlanDetailsUI.jsx`。
- 未改 main、Scheduling、Trial、Dashboard、共享正式写入、schema/version/registry/build、主线 stage。未操作生产库或现有预览；测试使用独立临时 SQLite，浏览器用无服务端的独立页面。
- 未 stage、commit 或重建静态包。主线以后按原构建入口带入两份前端源文件即可，不需要 DA 的 DDL 或 schema29 接点。

# 可直接接入的合同

继续使用 `GET /api/workbench/v1/plans/<plan_ref>/workspace` 的 `data.projections.baseline`，不增加路由或请求参数。

- available DTO 结构不变：`state/reason_code/reason/basis/baseline_plan/comparison_scope/compared_fields/items/item_count/items_complete`。
- `basis` 支持原 `scenario_base`，新增 `candidate_adoption`、`trial_adoption`。新增两种 basis 只允许 selected `official` 对历史 `official`，baseline 不是当前正式，也不是 selected 本身。
- `baseline_plan.plan_ref` 是实际采用记录的原正式引用。选择正式v12但原基线为v1的跳号测试明确排除 version-1；产生v13后再读v12仍对v1。
- 任务严格按 `operation_ref` 对齐，两边 `task_ref` 各自独立。先校验全量基线/selected，再按任一侧与半开区间重叠保留整道任务；移出范围的另一侧时间不裁剪。
- 比较字段仍为 `start/end/machine_ref/operator_ref`。旧场景的旧语义不变；新来源 before 的工序标签使用捕获值，不拿当前同号标签填充。
- `PlanGanttModel.js` 无需修改；现有初始条与详情切换直接使用新 DTO。`PlanDetailsUI.jsx` 仅把新来源 before 的历史供应商显示为“未记录”。

unavailable 结构不变，新增以下 reason_code；详细缺项只保存在参与快照计算的 PRIVATE facts，不泄漏原表字段到 DTO：

| reason_code | 含义 |
| --- | --- |
| no_adoption_baseline | 记录明确证明采用时尚无正式计划，不是漏记，也不能以自身作为基线 |
| adoption_evidence_missing | 原库缺少必要表、采用字段、proof 字段或原命令回执 |
| adoption_source_archived | 原运行、candidate、trial 场景或源草稿已移除 |
| adoption_snapshot_invalid | 原快照损坏，或摘要、proof、receipt、完整任务绑定互不一致 |
| adoption_baseline_archived | 原正式历史或原 Schedule 行已移除 |
| adoption_reference_invalid | 原计划、工序、任务、资源、批次实例引用失效或被同号替换 |
| adoption_baseline_drift | 原基线全行/原 SQLite 类型与捕获记录不同 |
| adoption_plan_drift | selected 正式完整工序集合或安排与采用原来源不同 |

# 证据链与保留

1. 从所选正式的 ScheduleHistory 审计中读取 `source/request_key/baseline_ref/baseline_version/proof`，与不可变命令回执的 action/context/意图指纹/正式引用/version/来源引用/row_count 交叉核对。
2. candidate 复用 `AdmissionBaseline`、`GenerationFacts` 和原 candidate manifest 读取合同，核对受理事实 SHA-256、受理 baseline_hash、候选完整原件 hash；不重新执行 engine。
3. trial 复用 CQ 的 `load_saved_scenario`，核对关闭草稿、场景保存回执、scenario/admission/rows/execution/baseline hashes，再补校验持久场景行的真实 task_ref/source_row_ref。
4. 比较捕获时 ScheduleHistory 的正式基线与捕获时 Schedule 全行，校验原 `WorkbenchPlanSourceRefs` 与完整 `WorkbenchTaskRefs`。再读保留的原版本行，以保留 SQLite 类型的编码比较所有原字段；同内容 BLOB 改成 TEXT 也不可冒充相同。
5. 数据库原值读取使用一元 `+` 及合成列别名，绕开 DECLTYPES/COLNAMES 的转换，不改连接或全局 converter。普通连接和生产类型转换连接冷重开结果一致。
6. 全过程 SELECT-only、caller-owned transaction；不会补 meta、修身份、补快照、改 receipt 或延长旧计划身份。query_only、全库带类型快照和 total_changes 检查均覆盖。

# 已知证据边界

- Schedule 没有历史 supplier assignment 和 effective processing hours，不能以当前 supplier 或墙钟时长补成历史事实；沿用 RunBaseline 的证据边界，供应商 before=null，UI 为“未记录”。
- candidate 原输入没有另外独立记录的 input digest。本实现复用 RunBaseline 的输入/执行/工序交叉校验，但不声称补出了不存在的独立 input digest。
- trial adopt proof 的 `facts_hash` 是采用时事实，包含创建/保存引入的身份，不等于更早 admission.facts_hash。只校验各自已记录且可重现的 admission、baseline、execution、rows、scenario hashes；不拿现在的生产事实重算采用时事实或运行当前规则补证明。
- adoption receipt 没有逐个保存新正式 task_ref 的采用后快照。因此新正式任务核对完整当前永久绑定及采用来源安排；原 baseline task_ref 则逐个对照原捕获值。未声称拥有未记录的新正式 task_ref 历史独立摘要。
- 原保存的 source 被清理、基线原行丢失或类型漂移时明确 unavailable；不能只凭一条 baseline_ref 回读当前同号行就宣称历史完整。
- 现有 CSV/XLSX 格式仅导出 selected 任务，不含初始基线对照列。本轮验证导出任务/身份/范围与 workspace 一致，并在基线证据变化后拒绝旧 snapshot；没有暗改导出格式。

# 验证与剩余风险

- DA 测试：`.venv/bin/python -m pytest tests/workbench/test_plan_adoption_baseline*.py -q --tb=short`，最终 **56 passed in 24.80s**。覆盖两种真实采用、空正式基线、跳号及后续新版本、101任务全量与窄范围、缺证据/损坏/归档/同号重建、BLOB/TEXT 类型、跨页、两种导出、只读与重开。
- 最终计划侧回归：`test_plan_baseline.py test_plan_catalog.py test_plan_workspace_projections.py test_plan_export_api.py test_plan_transport.py`，使用 `-k 'not test_schema_error_propagates_not_a_fake_unavailable'`，**128 passed / 1 deselected in 78.90s**。排除项的原因和DA等价测试见下，不把 deselected 算通过。
- 真 Chrome109：actual SQLite DTO 输入当前 PlanContract/PlanGanttModel/PlanDetailsUI；1366 和390宽度，验证初始条模型保留、原/当前详情切换和历史供应商未知文本。临时编译仅在内存中，不重建已有预览资产；不是生产库或 Win7 实机证明。
- 最终 trial 浏览器证据目录：`/private/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/pytest-of-lurenxing/pytest-985/test_real_adoption_dto_in_chro1/da-browser/`；已目视检查390宽的窄范围截图，原/当前完整起止时间可见，无文字互相遮挡。
- Ruff、Python3.8.10 执行与 AST、产品大小/复杂度扫描通过，新增违规为0。
- 扩大回归一次结果：289 passed / 9 failed，失败不隐去。1项旧 `test_plan_baseline.py:240` 在 DROP TABLE WorkbenchEntityRefs 时被现有外键约束拦住，未进入产品调用；DA 增补 FK-off 的临时缺表等价测试。其余8项 CQ/场景UI保留断言要求 WorkbenchDashboardItems 完全不变，实际新任务身份触发 `wb_dashboard_task_insert` 追加项目；失败点在 `trial_adoption_support.py:65`、`trial_adoption_widgets_support.py:158`。未改这些共享测试或触发器。
- 全仓 import-cycle gate 仍报基线外2目录环/2文件环；定点扫描无 DA 文件参与的硬文件环、无显式硬文件环。未刷新或改基线。
- 完整 `scripts/run_quality_gate.py` 未运行：共享工作区大量在途修改，且会操作主线统一门禁产物。本轮不占用主线 stage/build；上述全部是 dirty-worktree 局部验证，不是 clean-worktree proof。
