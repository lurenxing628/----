# F：13 项范围内缺项的已批准补全方案

## 当前结论

- Main 已核对冻结能力范围：以下 13 项原本缺少的产品承诺已补全并通过实际完整入口验证，不是等价替代、待用户选择或 N/A。旧 `needs_main_mapping_decision` 判断已撤回，228 动作分母不变。
- Main 已批准 A/B/C 全部最小写集并释放现有产品集成。13 项完整验证见 `F13-copy-matrix4-results.xml`（14 PASS），在途排空与恢复后新数据保留见 `F13-inflight1-results.xml`（1 PASS）。F 已执行操作并留证，不交给 Main 手跑。
- 后单独批准的 R14 两动作、Dashboard/System 同页新 PID 恢复修复不并入这 13 项，见 `navigation-recovery-fix.md`；最终 delta 21 PASS。228 动作 K 已收齐；Main 只对已核对的 28 张旧图签可见布局，新 delta 与动作全状态 V 未代签。
- Python 3.8 原 106 项后台/接口回归通过；新增 delta 定向回归 23 项通过，Ruff/Pyright 通过。H 指出的三个复杂度阻塞已按职责拆分，原函数复杂度为 12/6/6，新增叶均不超过 15。未提高阈值或忽略告警。
- Main 已批准在完整私有源码副本做中间联验：使用 `git ls-files --cached --others --exclude-standard` 清单，排除业务数据库/输出/缓存，逐文件校验 SHA-256、字节和模式，包含测试必读台账与冻结能力清单；原 venv 仅提供解释器和第三方依赖。已增加 repo-owned loaded-module 绝对路径及清单核验；原树后续修改不覆盖该固定副本的结果。这不是最终 HEAD 或 clean-worktree proof。
- 早期 `69ab1c53713a21acffe9810a3311ddf79538d4adeb1f86955ef272c0463372d8` 及后续失败均保留为历史。当前交接绑定完整 source18/build16，详见 `b-shared-source.json`；旧 source10 的 14 项与 source11 的在途证明各自保持独立绑定，不冒充 source18 全量回放或最终 HEAD。Dashboard build-order 连续块已交还 Main，F 不再写该文件。

## 13 项清单

| 动作 ID | 缺项 | 最小补全 |
| --- | --- | --- |
| WBP-DASH-001.metric-pressure | 顶部资源压力数值和入口 | 按真实资源、明确时间窗、实际日历可用时段投影压力及阈值计数；点击进入同页关联资源分析，不用风险条目数代替。 |
| WBP-DASH-001.metric-pending | 待排批次总数和入口 | 从真实待排批次池计数，与齐套风险数分开；点击进入本页待排批次表。 |
| WBP-DASH-001.category-select | 异常类别下拉 | 与侧栏共用同一类别状态和切换函数，保留键盘操作与只读导航上下文。 |
| WBP-DASH-007.hover-resource | 资源任务时段条和悬浮详情 | 同页绘制真实任务条，悬浮/键盘聚焦显示批次、工序、实际日期起止与跨度；没有固定 08:00-16:00 样例轴。 |
| WBP-DASH-007.select-batch | 按批次联动时间轴与影响表 | 同一永久 batch_ref 驱动任务条和影响批次表高亮；补齐同族 affected-batches / compare-navigation，不只增加颜色。 |
| WBP-DASH-011.downtime-bar | 检修窗口条 | 同一设备、同一时间轴显示有效停机窗口，保留重叠依据和真实登记时间。 |
| WBP-DASH-011.plan-task-bar | 检修轴上的原计划任务条 | 与停机条叠放真实当前正式安排，点击批次联动交集表；交集小时不冒充最终延期。 |
| WBP-DASH-013.candidate-radio | 候选方案单选 | 本页从同一 run 的持久候选目录生成单选项；至少三份真实候选验收，真实目录多于三份不裁掉，多种状态不伪装成完成。 |
| WBP-DASH-013.benefits-costs | 整体收益、代价和差额 | 同受理范围、同时间窗比较交付、换型、真实设备压力；不能拿平均利用率替代峰值，也不能拿安排跨度替代有效工时。 |
| WBP-DASH-013.per-batch-change | 逐批原方案/所选方案交付变化 | 以受理时永久批次集合为共同集合，展示初始正式基线与所选候选的完成、拖期及差额，保留未排/不完整批次。 |
| WBP-DASH-013.summary-dialog | 方案摘要弹窗 | 本页打开同一已验证比较结果的摘要，含交付、拖期、换型、换设备工序数；关闭/ESC 返回原选择，不触发采用。 |
| WBP-SYS-006.type-restore | 本机恢复事件筛选 | 读取外置维护 journal 的真实 restore 事件，展示原 request_key/job_ref、阶段与终态，不能伪造为可下载备份文件。 |
| WBP-SYS-006.type-cleanup | 本机清理事件筛选 | 读取真实 system/cleanup、logs_cleanup 审计；SystemJobState 仅作为明确标注的最近结果补充，不伪造全历史。 |

## A. 值班台只读分析

1. 新增 dashboard 专属只读分析投影及 GET 路由，保留既有风险条目/处置合同。以当前正式 plan_ref、真实时间范围和来源 fingerprint 绑定快照；计划已改变、引用失效或事实不完整时明确拒绝/显示未知。
2. 复用 `DashboardFacts.load()` 已在同一读取事务获得的正式任务、批次、停机及资源日历事实。`project_plan_calendar()` / `project_plan_occupancy()` 已有实际时间窗、可用容量、区间并集和交叠口径；新增投影只补任务/批次映射、日粒度压力与可视化所需字段，不改共享日历/排程算法。
3. `待排批次` 使用批次域的 pending 状态池，不拿 `material.risk_count` 充数。表中显示原型承诺的数量、交期、齐套状态、齐套日期；约束有真实来源才显示值，未选定排产输入时明确未选定。
4. 压力计数沿 >=90% 阈值，但分母必须是相同自然日/裁剪时间窗内的真实可用时段；没有有效可用量的资源不进入零值，也不假定 20 小时产能。峰值为范围内日粒度峰值，标明该口径；全部实际设备可见，不硬编码 M-03/M-08。
5. 新时间轴组件复用现有 PlanGanttModel 的本地时间解析/刻度/可见区间基础，不改 PlanGantt 或 PlanWorkspace。批次永久引用联动；零时长点、夜班跨日、窗口边界、滚动和键盘聚焦单独锁测试。

代码依据：
- `core/services/workbench/dashboard_facts.py:42` load，`:75` 正式任务投影及资源压力。
- `core/services/workbench/dashboard_catalogs.py:10` 复用日历/占用；`core/services/workbench/plan_occupancy.py:46` 资源区间及可用量，`:86` 同范围检查。
- `core/services/workbench/dashboard_downtime.py:28` 真实交集，`:39` 正式任务与停机来源。
- `frontend/workbench/app/DashboardPanels.jsx:13` 当前指标、`:73` 当前数值表，尚无所需时间轴；原型 `frontend/workbench/prototype/ui_kits/workbench/dashboard-views.js:27` / `:59`。

## B. 同 run 持久候选对照

1. 本页明确选择 run，再调用 `RunCandidateAPI.catalog(run_ref)`。每个单选项使用原 candidate_ref / 原 label，不使用 Plan 候选 ID，不借用样例，不给真实候选强贴“优先急件”等未被结果证明的名称。
2. 每次选择调用 `RunCandidateAPI.workspace(candidate_ref, commonRange)` 和 `RunBaselineAPI.read(workspace.data)`。后者自己持有基线快照，不传递 workspace snapshot token。所有候选共用同一 range 和受理时批次集合；切换需取消旧请求，错误/旧响应不能覆盖当前选择。
3. 原方案明确是该 run 的“受理时正式基线”，不是此刻可能已变化的当前正式计划。按 operation_ref / batch_ref 对照，保留 baseline_only、unscheduled、not_comparable 和已执行影响，不按行号/显示名称拼接。
4. 现有 API 有逐工序对照与候选交付，但缺完整的同范围收益汇总。新增 dashboard 专属只读 comparison endpoint/service，复用同一持久 capture、`GenerationFacts` / `AdmissionBaseline` 校验、已有交付投影和换型规则，补同范围基线/候选交付、换型、日粒度资源峰值及换设备工序数。它不改现有 RunCandidate/RunBaseline 公共 DTO；其输出必须回绑 candidate_ref、run_ref、baseline_ref、共同范围和 capture digest，由本页与两个既有 API 的结果交叉核对。
5. 候选全局 artifact metrics 不当作 range 统计。交付以共同选中批次的完整工序判断，不把被时间窗裁掉的工序当作完工；资源占用只在共同 range 内计算。日历/停机取受理时归档，不查现在的同号设备；缺历史容量或基线就显示具体原因和 null，控件仍可见，不能用未知掩盖尚未实现的正常路径。
6. 汇总表、逐批表、摘要弹窗使用同一已验证比较对象，不各算一套数字；摘要显示可核对的换设备工序及对应永久引用，不执行采用/发布。

代码依据：
- `frontend/workbench/app/RunCandidateAPI.js:67` 范围合同，`:106` 候选交付合同；`web/routes/workbench/run_candidates.py:59` 工作区读取。
- `frontend/workbench/app/RunBaselineAPI.js:21` 从 workspace 取得同范围且禁止复用其快照；`core/services/workbench/run_candidate_baseline.py:358` 校验归档并对照，`:385` 返回受理时基线、范围和永久引用。
- `core/services/workbench/run_candidate_delivery.py:93` 完整批次交付；`core/services/workbench/run_candidate_projection.py:102` artifact 全局指标；`core/algorithms/evaluation.py:137` 现有换型/指标规则。
- `core/services/workbench/run_jobs_facts.py:14` 已归档非运行记账表，包含当时日历/停机事实；`core/services/workbench/run_candidate_facts.py:104` capture SHA-256 核验。

## C. 本机维护事件筛选

1. 备份恢复记录集合扩展为明确区分的 `backup_file` / `restore_event` / `cleanup_event`；筛选、搜索、日期、状态、分页和快照一致。备份文件与事件不可共享含义模糊的状态。
2. restore 复用 `SystemMaintenanceJournal.records()` / `public()` 的已校验外置记录，保留成功/已回滚/回滚失败/待核实等原状态，不新造恢复过程，也不打开恢复后被禁用的业务数据库。
3. cleanup 优先读 `OperationLogs(module='system', action IN ('cleanup','logs_cleanup'))` 的真实审计，明确读取窗口。最近状态补充来自 `SystemJobState` 的结构化结果，并标明“最近结果，非完整历史”；按可证明身份去重，不能按近似时间误合并。
4. 只有 `backup_file` 继续提供现有 download/restore/delete 能力与 opaque backup_ref；事件行只读详情、原回执和阶段。保留已实现备份下载的原文件校验及旧 HTML 路由。坏 journal / 缺失审计必须显示读取失败或范围缺口，不能转成成功/空记录。

代码依据：
- `core/services/workbench/system_journal.py:80` records、`:133` public。
- `core/services/system/maintenance/cleanup_task.py:235` 备份清理审计、`:340` 日志清理审计；`data/repositories/system_job_state_repo.py:20` 最近状态集合。
- `frontend/workbench/app/SystemMaintenanceRecords.jsx:5` 当前类型缺 restore/cleanup；`:38` 当前详情仅区分文件/日志。

## 请求批准的最小写集

- 修改现有本域前端：`DashboardWorkspace.jsx`、`DashboardPanels.jsx`、`DashboardStyles.jsx`；`SystemMaintenanceAPI.js`、`SystemMaintenanceRecords.jsx`。
- 新增本域前端叶模块：`DashboardAnalysisAPI.js`、`DashboardTimelineModel.js`、`DashboardTimeline.jsx`、`DashboardCandidates.jsx`、`DashboardCandidateComparisonAPI.js`。全部位于 `frontend/workbench/app/`，视大小门禁按同职责继续拆叶，不塞回大文件。
- 新增本域后端叶模块：`core/services/workbench/dashboard_analysis.py`、`dashboard_candidate_comparison.py`、`dashboard_candidate_metrics.py`、`system_maintenance_records.py`；新增路由叶 `web/routes/workbench/dashboard_analysis.py`。不改共享查询、算法、恢复和事务实现。
- 修改仅注册/集合及严格域合同：`web/routes/workbench/dashboard.py`、`web/routes/workbench/system_reads.py`、`core/models/workbench_system.py`。事件/文件 discriminator 对应下载读取路径必须定向回归；既有 `system_backup_export.py` 原下载能力不降级。
- 测试和本目录仍归 F；Main 已明确委托 F 临时拥有 `scripts/workbench/build-order.json` 内 Dashboard 连续 block，仅登记已存在的本域叶，交回前 Main 不写此 block。其他 block 不在 F 写集。RunCandidateAPI/RunBaselineAPI、PlanWorkspace、schema、host、worker、排空、恢复事务、自动清理执行器均不在产品写集。

## 验证与停止边界

- Python 3.8 单元/接口：同范围、跨日、真实压力、pending 与缺料分离、永久引用/过期快照、三份及以上真候选、无基线/不完整候选、四种不同对照状态、同 batch_id 删除重建后仍取归档、坏 journal、事件不可获得文件动作能力。
- 主入口新进程：真实 managed worker 生成至少三份不同永久引用的持久候选；安排可以相同，真实差额为零照实展示，不制造差异。逐项点选/悬浮/键盘/联动/弹窗/筛选，核对真实 SQLite/capture/journal，四视口主题、F5/后退/进程重启。保留 228 动作逐项 BKVP 和此前失败，不用分域组件测试冒充完整入口。
- 最终包由 Main 重建后严格核对全部 inputs/files，再做四组正常及八组恢复重跑；F 不降低核对，也不替 Main 声称 V 或 clean-worktree proof。
- 发现缺少真正所需的持久事实，先给明确证据；不通过新假数据、静默默认、裁掉候选/批次或把缺控件标 N/A 来收尾。
