# 第8阶段共同事实依赖方向修复

日期：2026-10-14。主对话亲自核对失败原件、基线、导入和调用点后确定本稿；原实施对话按稿写代码、验证及交接。属于本轮完整门禁实际失败的根因修复，原UI与其他独立交接继续。

## 1. 已确认事实

`full-gate/attempt02-v4/receipts/05_python-m-tools-scan_import_cycles-fail-on-new-cy.json`报告两个目录SCC。两份现行production／production-and-tests基线的`hard_dir_cycles`都为空。`tools/import_cycle_baseline.py:_baseline_supersets`已允许旧SCC缩小；`_new_edges`对全新圈不另列圈内新增边，所以日志中的0条圈内新增边不能用来接受这两组新环。

主对话与独立只读复核确认以下反向导入：

- `common/plan_query.py:29`向`scheduler/dispatch_task_ids.py`读取共同任务身份，连接成10目录环。任务身份文件只有标准库依赖，职责属于计划原件身份。
- `workbench/facts`向`plan/run`共7条：`decision_baseline.py:14-15`，`decision_baseline_source.py:7-9`，`common_completed_delivery.py:5`，`run_policy.py:8`。这些事实、投影与校验已同时供多个入口使用。
- `workbench/execution/actual_gantt.py:11`向`report/review_values.py`读取共同偏差计算；report已有对execution的正常读取，形成另一条返向。

修后方向应为`run/report → execution/plan/facts`、`execution → plan/facts`、`plan → facts`，共同事实不再反向依赖工作区编排。保留当前基线和扫描器，保持已有7组文件初始化环的原验收口径。

## 2. 直接搬移共同职责

以下每行搬移完整实现，修改实际导入，不改变公式、异常、未知值、校验顺序、编号、事务或返回形状；旧产品文件删除，不保留仅用于转发的兼容壳。

| 当前文件（相对core/services） | 最终文件 | 共同职责与消费者 |
| --- | --- | --- |
| `scheduler/dispatch_task_ids.py` | `common/plan_task_identity.py` | 完整原计划行的身份与公开任务编号；common计划查询、scheduler资源／甘特、workbench实际甘特及现有resource_dispatch测试统一引用。 |
| `workbench/plan/delivery_projection.py` | `workbench/facts/delivery_projection.py` | 真实任务区间、批次完成性、交期原值和共同汇总；plan、run、trial及common_completed_delivery同用。 |
| `workbench/plan/delivery_completeness.py` | `workbench/facts/delivery_completeness.py` | 保存的缺料／缺排证据及旧来源补读；保留已有CandidateStore、scenario和异常处理。 |
| `workbench/plan/adoption_baseline_values.py` | `workbench/facts/adoption_baseline_values.py` | 采用原件读取／类型与缺项判断、同一异常类和原因字典。 |
| `workbench/plan/adoption_baseline_sources.py` | `workbench/facts/adoption_baseline_sources.py` | 冻结候选／试调来源、采用工序原件读取及现有verified_read；与上一行共同下沉。 |
| `workbench/run/history_projection.py` | `workbench/facts/run_history_projection.py` | 原运行目录的保存记录校验、公开摘要与失败原因；run/history、worker、facts/run_policy及bootstrap读取同一实现。 |
| `workbench/report/review_values.py` | `workbench/facts/execution_values.py` | 工厂时间、分钟差及共同执行偏差；report/review_*、actual_gantt和dashboard/execution同用。 |

相对导入随所属文件更新。尤其保留`AdoptionBaselineUnavailable`为同一个类，现有捕获与测试monkeypatch必须指向新实际模块；`hour_totals`沿原转口，不另写一套计算。`plan/projection.py`等已有局部导入只改目标，不因本次修复额外改变其执行时机。

## 3. 候选源从工作区服务中提取

新增`core/services/workbench/facts/candidate_read_source.py`，只承接目前`run/candidates.py`已有的下列内容：

1. 完整`CandidateReadSource` dataclass及原`snapshot_identity`、两个cached_property，字段、默认值和生命周期保持。
2. `candidate_manifest(store, run_ref)`：搬入原`WorkbenchRunCandidateQueryService._load`函数体，依次run、receipt、candidates、validate_manifest、dispositions，返回原四项；只将`self.store`替换为形参`store`。
3. `read_candidate_source(store, candidate_ref)`：搬入原`_source`函数体，调用同一`candidate_manifest`；保留原run归属、candidate定位、capture、GenerationFacts、raw_tasks数量校验、tasks_projection、unplanned_projection及原DTO构造顺序。

`WorkbenchRunCandidateQueryService`继续拥有原store、目录分页和workspace业务DTO；catalog直接调用`candidate_manifest(self.store, ...)`，workspace直接调用`read_candidate_source(self.store, ...)`。原`_load`／`_source`移除，不新建继承层、第二份source状态、通用reader框架或重试。

原调用`reader._source`的`run/candidate_analysis.py`、`candidate_comparison.py`、`candidate_baseline.py`及3个现有测试文件中的4处调用，改调用共同函数并传现有store；原`store.snapshot()`／read_evidence_scope边界、读取次数和reader其他作用保留，非本项同名`_source`不改。`facts/decision_baseline_source.py`直接创建本次resolver的CandidateStore并调用该共同函数，保留原`sources`按永久身份缓存的请求生命周期，不再构造上层QueryService。`history/reading.py`只更新dataclass导入，其已存在的run／candidate缓存与读取逻辑保持。

不得把采用专用`load_adoption_candidate`代替通用候选读取：采用完整性前提与历史／候选查看不同。不得为去环把新反向导入藏入函数或把事实复制到调用方。

## 4. 引用与资料范围

使用现有symbol_locator和实际rg引用清单核对调用面；主对话已查询assign_task_ids、archived_deferred_operation_evidence、read_adoption_operation_facts、execution_deviation、scope_summary及_source，静态工具未覆盖tests的部分已用实际导入补查。同步当前活跃的产品／测试／工具引用，以及开发文档系统速查表中确有的模块位置。历史报告、冻结源码、SQL、数据库、原门禁manifest与旧导出原件保持原样；不要全仓替换历史材料。

第1次9项Ruff修复仅导入排序，之前计算与性能证据仍有效。本次同样要求搬移保持业务函数体；用已有attempt02原内容核对搬移对应关系即可，不增加哈希、摘要清单或来源校验框架。

## 5. 必要验证与收尾

- 对本次明确路径检查导入与Python3.8语法／Ruff；现有production和with-tests两次循环门禁应实际无新增目录环／文件环／圈内边／未解析项。若仍有新环，先给具体边回主对话定改法，不刷新基线。
- 原完整dirty Gate本来包含全部保留pytest，包括任务身份、交付、采用来源、历史、实际甘特和候选接口用例。这次直接由后续完整门禁统一验证这些相关用例，不先重复一套局部矩阵，不为纯搬移新增测试函数或测试文件。现有测试只更新真实导入和已移除私有方法的调用位置，断言保留。
- 保留attempt01/02失败原件；本次来源冻结后继续原`--allow-dirty-worktree --no-resume --no-long-gate-cache`完整门禁，记录真实manifest状态，不能仅凭exit2认定通过。
- 同代码业务函数、SQL和数据范围保持时，先前20k受控性能与原值比较继续复用；本项不重开受控服务、不重新排产、不跑大HTTP矩阵。后续主对话逐函数核对后决定是否有证据失效。
- 正常只读验收实例在搬移前保持在跑；源码冻结后为加载最终模块做一次同库正常重启，核对原实例身份和新资产，然后仅检查受影响的候选／正式来源／历史入口能正常读。已完成图形、布局和导出数值证据按未变范围复用。
- 在本feature的现有交接中记录具体文件搬移、来源与行为保持、实际扫描／完整门禁结果及剩余状态，供主对话亲验。主对话维护本稿与stage-acceptance；Git仍由主对话统一执行。
