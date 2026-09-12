---
doc_type: feature-acceptance
feature: 2026-09-12-algorithm-capability-efficiency
roadmap: scheduler-global-optimizer
roadmap_item: optimizer-quality-efficiency-20260912
status: implemented-validated
created: 2026-09-12
last_reviewed: 2026-09-13
summary: 算法实施及定向验证完成；最终20+8例完整比较和native20通过，1000工序基本持平，两次5000工序容量通过；按用户要求收敛验证，最终整仓门禁未完成。
tags: [scheduler, optimizer, quality, performance, python38, win7]
---

# 算法能力与效率统一验收

## 1. 结论、范围和验证约定

A–K 的实施及本轮定向验证已完成。最终冻结算法的旧新20例完整比较、核心8例历史比较及native20均通过；之前的完整入口与tiny次级回退已修复，原失败回执继续保留。1000工序四方案旧新中位数为10.815770459/10.744741417秒，约下降0.66%，应视为基本持平。两次正式5000工序四方案分别89.381380042和89.475103292秒，均低于原180秒阈值，完整结果与数据保留通过。

**最终整仓门禁未完成。** 最后一次主仓命令仅在guard预检因8个已有未跟踪测试文件退出，长测试没有启动；已通过`git add -N`纳入可见范围，文件字节和实际暂存内容未改变。按用户最新要求收敛验证，不再追加或重跑一小时整仓门禁。本记录表示实施完成及定向验证完成，不称full-gate或clean-worktree proof。

用户先要求全面研究算法，再授权全部已报告项目实施。事实源见[本轮A–K清单](../../roadmap/scheduler-global-optimizer/2026-09-12-quality-efficiency.md)。起始HEAD为`afc0551ed15ac0d8aceca63f1d950ebe8f9b0e8b`，业务实验使用独立临时样例；已完成的UI工作保留，不自动提交、安装或发布。

用户已明确整机无法保证100%无其他负载。进程背景采样和driver的`contended`标记作为实验环境限定；单次其他pytest进程样本不再被用于否决整轮产品或容量结果。180秒硬阈值、真实质量回退、完整payload和数据保留仍按实际结果验收，不因此放宽。

## 2. A-K 实现与逐项处置

| 编号 | 当前实现或处置 | 实现入口与子记录 | 本次完成状态 |
| --- | --- | --- | --- |
| A | 统一预算/反馈分配和安全去重；每个候选家族先保留代表，按实际 decode 成本预留搜索机会，在原 top_k 内按不同parent计槽，同parent的basis变体共享每次8项邻域预算，不扩大总预算/候选上限 | `optimizer_search_budget.py`、`optimizer_graph_ready_budget.py`、`optimizer_graph_ready_predecode.py`、repair；[预算验收](../2026-09-12-optimizer-budget-efficiency/optimizer-budget-efficiency-acceptance.md) | 共享parent修复后20+8例完整比较通过；本项实施完成 |
| B | 真实插入邻居与全合格组合剥夺提示；exact `SimpleNamespace` 直接读取当前 `id/op_type_name`，不缓存可变字段；一般对象和回调时序保留 | `resource_quality.py`、`resource_demand.py`、`run_state.py`、`auto_assign.py`；[资源质量验收](../2026-09-12-gap-resource-quality/gap-resource-quality-acceptance.md) | 134项及碰撞差分通过；最终20例质量比较通过 |
| C | 原生成功评分/估时/日期复用；自动分配且无固定机人组合时跳过无收益 cache，使用普通占用时间轴；首次导入构造、提前 getter 读取和自定义 metaclass 不能被当作原生证书 | `owned_timeline.py`、`native_snapshot.py`、`sgs_estimate_reuse.py`、`dispatch/sgs_reuse.py`；[SGS 执行记录](../../refactors/2026-09-12-sgs-incremental-scoring/sgs-incremental-scoring-apply-notes.md) | 边界验证及最终native20通过；1000工序总体基本持平 |
| D | 默认3轮、封顶8轮的真实SGS修补；批次/工序/合格资源邻域交错，保留已接受选择、旧elite及top_k，维持原轮数/时间/候选边界 | `optimizer_graph_ready_repair*.py`、`optimizer_graph_ready_operation_neighbors.py`；[图邻域执行记录](../2026-09-12-graph-search-neighborhoods/graph-search-neighborhoods-ff-note.md) | 同parent basis共用top_k槽及每次8项预算；tiny回退已修复 |
| E | `batch_workload_v1` 基础排序与 `operation_successor_v1` 增强排序显式并存；后继工量/piece/日历释放语义保留，基础启发仅保存在明确子行，两者共用正式SGS/评分 | `optimizer_graph_ready_feature_basis.py`、profiles/workload/v2_features；[目标特征验收](../2026-09-12-objective-aware-graph-features/objective-aware-graph-features-acceptance.md) | 199项局部与最终完整入口比较通过 |
| F | 比较/长跑计入初始解、全部搜索和正式 repair 的真实总耗时；独立算法状态；schema 2/source/machine 合同；真实矩阵整文件串行分片 | `optimizer_compare_algorithms*`、`optimizer_smtwt_compare*`、`optimizer_benchmark_ratchet*`、`full_test_debt_shards.py`；[量尺修复记录](../../issues/2026-09-12-optimizer-benchmark-trust/optimizer-benchmark-trust-fix-note.md) | 量尺修复及同版本对照完成；旧不兼容基线继续显式拒绝 |
| G | 5场景×4目标完整候选比较、完整向量/可行性和限定域tiny oracle；两种计数模式及基线生命周期明确区分 | `optimizer_end_to_end_*`、`optimizer_exact_oracle.py`；[完整入口实施记录](../2026-09-12-optimizer-end-to-end-quality/optimizer-end-to-end-quality-implementation.md) | 最终旧新20例完整比较、核心8例及native20通过 |
| H | 同一私有只读快照内 prepare→compute 消除第二次完整指纹；独立 prepared 调用仍全量校验 stale。选中 payload 缓存已测量后拒绝，原校验保留 | `core/services/workbench/run_compute.py`、`run_worker.py`；[快照执行记录](../../refactors/2026-09-12-run-snapshot-reuse/run-snapshot-reuse-apply-notes.md) | 一次事实指纹及两次正式容量的数据保留通过；payload缓存有据拒绝 |
| I | 单后继图线性精确计数，一般 DAG 分量位集合去重；联合评分一次合法化；同 comparison 权重无关模板复用且返回容器隔离 | `graph/impact_counts.py`、`graph/scoring.py`、`schedule_graph_cached_projection.py`；[图准备执行记录](../../refactors/2026-09-12-graph-preparation-efficiency/graph-preparation-efficiency-apply-notes.md) | 精确计数/投影隔离合同及最终集成通过 |
| J | 原生恒定工作窗内，跨设备/人员/停机延伸连续占用闭包；真实空隙、工作窗、abort、自定义对象继续限制快路径 | `core/algorithm_runtime/busy_block_skip.py`、`downtime.py`；[忙段闭包记录](../../refactors/2026-09-12-busy-union-closure/design-and-validation.md) | 忙段边界与最终容量验证通过 |
| K | 公共预算聚合字段投影、新测试显式注册、矩阵串行分片和统一验收归并 | `contracts/optimizer_budget_projection.py`、`tools/test_registry_algorithm_efficiency.py`、本记录、[架构 §10](../../architecture/service-scheduler.md#10-算法能力与效率合同2026-09-12-增补) | 实施与定向验收完成；最终整仓门禁未完成，按用户要求停止追加 |

上述算法改动保持 Python 3.8、Win7 x64、离线单机约束。没有增加依赖、新运行时、设备班次模型或顺序相关 setup 时长模型；冻结、piece、资格、日历效率和原错误合同不能为优化让步。

## 3. 已运行的模块验证

以下是各模块记录的实际结果，作用域互有重叠，**不得相加成全仓测试总数**。本次文档归并没有重新运行测试；最终整合以 §5 绑定源码的回执为准。

| 范围 | 已运行结果 | 关键锁定合同 | 证据 |
| --- | --- | --- | --- |
| A 预算/家族覆盖 | 共享parent最终156 passed in 15.94s；此前家族覆盖160项保留，各轮不相加 | 家族首代表、真实成本预留、basis top_k、原预算/候选/轮次不放宽 | [a-shared-parent-resume2-delivery.json](/private/tmp/aps-algorithm-implementation-20260912/a-shared-parent-resume2-delivery.json) |
| B 资源质量/即时字段 | 134 passed in 0.64s；碰撞差分子集12 passed in 0.45s（包含在扩展测试文件中，不另合计） | 当前字段读取不缓存mutable值；12组真实碰撞键/回调/首错与旧路径一致 | 资源质量验收；[comparison.json](/private/tmp/aps-algorithm-implementation-20260912/b-native-operation-type/comparison.json) 的48工序payload相同，profile时间不作原生提速证据 |
| C SGS/证书边界 | 无收益快路初验218 passed in 8.75s；首次导入/回调最终68 passed in 2.88s；与历史545项有重叠 | 原afc与修复后均6次评分、9次getter，修复后0 cache hit且完整payload相同；原构造/访问/首错时序保持 | [c-boundary-final-checks.json](/private/tmp/aps-algorithm-implementation-20260912/c-shift-pool-cpu-1yoPEE/c-boundary-final-checks.json)、[c-preimport-fixed-comparison.json](/private/tmp/aps-algorithm-implementation-20260912/c-shift-pool-cpu-1yoPEE/c-preimport-fixed-comparison.json) |
| D 图修补 | 初版联合 94 passed in 14.24s；保留旧 elite 后最终局部回执 36 passed in 11.18s（未单独归档 stdout）；类型/图合同 64 passed in 2.83s；范围重叠不相加 | 真实 SGS、DAG/资格/seed、多轮、无改善终止、解码前 deadline、旧 elite 保留与延期/预算计数 | 图邻域执行记录“统一整合后的收敛”；`typed-graph-contracts.log` |
| E 目标特征/basis | 本次199 passed in 5.88s | 基础整批与增强后继排序显式共存，四目标、piece菱形、外协/seed、日历及坏字段边界 | [e-final-source-manifest.json](/private/tmp/aps-algorithm-implementation-20260912/e-final-source-manifest.json) |
| F 量尺和分片 | 173 passed, 1 deselected in 7.08s | 真总耗时、算法状态隔离、正式基线提升拒绝 dirty、整模块串行与同 fixture | 量尺修复记录“验证”；既有真实十seed smoke的最终全仓回执未取得 |
| G 完整入口/独立 oracle | oracle 31 passed；矩阵其余 27 passed；最终夹具/未 patch 原生计数 2 项定点通过；snapshot 67 passed | 四候选真实入口、正式四目标向量、审计反例、两种计数模式、生命周期与有限域最优 | 完整入口实施记录验证表；定点复验存在重叠，不另作总数 |
| H 快照 | 163 passed in 10.10s；早期真实进程 2 passed, 4 deselected in 3.49s；修正隔离树旧 hook 后两项真实进程合同 2 passed in 10.94s | 一次指纹、独立 prepared stale、query_only、原库并发写、重启/恢复/锁与数据保留；原完整inflight浏览器用例未取得最终全仓门禁回执 | `final-tests.xml`、`process-tests.xml`、`workbench-restore-contracts-20260912.stdout.log`；范围重叠不相加 |
| I 图准备 | scheduler_graph（排除既有大性能文件）380 passed in 2.17s；950 组旧新评分/异常对照一致 | 1024 个五节点 DAG 对拍、6000 节点链、菱形去重、复制隔离、精确大整数 | 图准备执行记录“验证” |
| J 忙段闭包 | 主线程已完成 112 项局部回归；独立 120 组旧新结果对照一致 | 微小空隙、日历边界、重叠索引、动态输入和错误时机 | 忙段子记录已回填命令、有限证据及边界 |
| K 注册/截止/公开投影 | 历史定点结果保留；C边界测试显式纳入第28个算法注册，主仓623 required、隔离树同步口径616 | 旧582 required/85 supplemental 的owner与顺序hash不变，UI注册原样保留 | [registry-c28-receipt.json](/private/tmp/aps-algorithm-implementation-20260912/registry-replacements/gate-e-contract-fixes/registry-c28-receipt.json)；不等于最终全门禁 |

上述新切片的限定路径 Ruff、Python 3.8/Pyright及官方结构检查通过；[resume1-product-structure.json](/private/tmp/aps-algorithm-implementation-20260912/resume1-product-structure.json) 对主线程59个产品文件的 complexity/oversize 均为 `[]`。这些是局部/结构证据，不等于最终主仓全门禁或Win7实机验证。

## 4. 历史局部收益和适用边界

| 场景/测量 | 已有结果 | 能支持的结论 |
| --- | --- | --- |
| 真实插空换型微例 | 同一 09–10 时隙，强制原机 M1 为 4 次换型，自动 M2 为 2 次；种子不动 | 修正机器尾工种不能代表插入邻居的选择问题 |
| 真实稀缺机人微例 | A 可两组资源、B 仅一组，各 1 小时；强制占稀缺组合 2 小时，自动分配 1 小时 | 合法组合并列时保留稀缺组合可改善该实例工期 |
| B 中性比较单解码微例 | 同一当前源码内对照是否强制完整认证，各 3 次交替运行的中位数为 0.136300→0.113252 秒；另各 1 次 profile 仅作调用量分析；全部 8 次均为 48 行、零失败、相同完整 payload SHA-256 | 在该 48 工序微例减少无分差比较的认证成本；原始数据见 [b-neutral-decode.json](/private/tmp/aps-algorithm-implementation-20260912/b-neutral-decode.json)，不代表旧版本整体提速或容量验收 |
| SGS cProfile 调用量 | 10 个独立工序评分 55→10；30 个 465→30，结果等价 | 减少已认证固定资源候选的重复评分；调用量不是端到端提速比例 |
| SGS 1000 工序探索 | 专用机人、共享机人启用/禁用 cache 的全部产品 payload 哈希一致；初版三组共享资源约 1.4→5.2 秒的方案被拒绝并保留原回执 | 必须同时评估证书成本，最终采用资源独占门槛；最终同版本结果见§5，不混用历史计时 |
| 五档权重、38 个待排节点 | 图分析/健康/ready/资源匹配各 1 次；指标合法化 570→190，五档 key 仍不同 | 仅去除权重无关准备和重复合法化，不改变各候选评分 |
| 连续只读 prepare→compute | 完整指纹 2 次→1 次；独立 prepared 接口仍 2 次，完整候选结果相同 | 消除可证明重复扫描；历史行越多成本可能不同，不据此编造总提速 |
| 多轮图修补受控时钟 | 固定 40 工序实例 1 轮与 3 轮超期数均 5，后者继续降低拖期分量 | 证明多轮能到达进一步改善；不证明同墙钟预算普遍更好 |

所有本节测量都不承诺全输入加速、全规模质量提升或最坏运行时间。无改善候选是合法结果，不能改夹具或刷新基线来掩盖退化。


## 5. 最终冻结版本和定向验收

稳定证据已归档：[README](../../../evidence/algorithm-capability-efficiency/2026-09-13-final/README.md)、[summary.json](../../../evidence/algorithm-capability-efficiency/2026-09-13-final/summary.json)、[证据清单与哈希](../../../evidence/algorithm-capability-efficiency/2026-09-13-final/evidence-manifest.json)及[41份原始回执](../../../evidence/algorithm-capability-efficiency/2026-09-13-final/raw-evidence.zip)。下列临时回执在原始归档中留有对应内容，结论以稳定汇总为准。

### 5.1 来源与公开边界

- [source-equivalence-resume2.json](/private/tmp/aps-algorithm-implementation-20260912/source-equivalence-resume2.json)绑定193个明确算法/共享验证路径和841个core文件；主仓、validation及formal-resume2的core逐字节一致，映射SHA-256为`ff2e5b4527ba144b9e37dc3eb74de04cbe0238c8610d8c7b983d4400156d5ec0`。这不等于三棵整树一致，也不构成clean proof。
- 核心、旧新20例及native20各自source前后一致。旧新性能对照采用相同量尺、输入、预算和显式uncounted模式，不向旧产品回填计数器，不patch解码入口；native计数另行验证。已完成的UI及共享注册变化保留，当前主仓623 required、隔离算法口径616，历史582/85的owner和顺序hash不变。
- 所有实际回执位于`/private/tmp/aps-algorithm-implementation-20260912/`。最终依据是resume2/resume2b，早期c/g/final-e/resume1与v3结果只作历史，不互换源码绑定。

### 5.2 当前结果

| 验收项 | 实际结果 | 证据与边界 |
| --- | --- | --- |
| 完整入口旧新20例 | 两侧各20/20，完整质量比较passed、failures=[] | [end-to-end-resume2-compare.json](/private/tmp/aps-algorithm-implementation-20260912/end-to-end-resume2-compare.json)；原1秒内部/5秒外部预算及阈值不变 |
| 核心8例历史比较 | 8/8，完整字典序和三段耗时比较passed、failures=[]；tiny向量恢复`[0,4,2,12,12,26]` | [current-core-resume2-compare.json](/private/tmp/aps-algorithm-implementation-20260912/current-core-resume2-compare.json)；历史clean基线未重写 |
| native20 | 20/20，原生计数与可行性通过，source前后一致 | [end-to-end-native-resume2.json](/private/tmp/aps-algorithm-implementation-20260912/end-to-end-native-resume2.json)；限定tiny oracle不升级为一般最优证明 |
| 普通1000工序×4方案 | 三组旧新交替，旧中位10.815770459秒，新10.744741417秒，约-0.66%；基本持平 | `native-old/new-1000-resume2-a/b/c/result.json`；六次完整payload同`d47139632920b7b1313ff44bcd8f37d4349ea600f33408a0444ee107b084a1d9`，输入/源码不变；含prepare的计算入口，不是HTTP容量提速比例 |
| 1000工序、5秒improve预算 | 旧9.000100625秒、新5.104897417秒；两边均partial、2完成/2跳过/0失败，完整两候选payload一致 | 稳定summary的improve5_1000；单组观察，表明本例超预算耗时缩短，不推导普遍提速 |
| 正式5000工序×4方案 | resume2为89.381380042秒；同冻结源resume2b重复89.475103292秒；两次`complete/formal_capacity_passed=true` | [resume2](/private/tmp/aps-algorithm-implementation-20260912/formal-5000-resume2/result.json)、[resume2b](/private/tmp/aps-algorithm-implementation-20260912/formal-5000-resume2b/result.json)；均4×5000、20000任务落库、72张非运行表保留、重启旧行保留及GET零写入，原180秒阈值不变 |

首次容量driver因1次背景pytest样本标记`contended`，重复运行driver为passed且记录0次命中。按用户明确的验收口径，这保留为环境说明，不推翻实际89秒左右、完整四方案、持久化和重启保留通过的结果；不再追求零干扰重测，也不把单机合成场景外推为全部业务规模或Win7实机的保证。

### 5.3 测试与最终门禁边界

- 最终共享parent修复156项通过；此前隔离联合182项通过、59个产品文件官方复杂度/体量扫描均为空。A/B/C/E各模块的不同批次测试有重叠，不能相加为全仓总数。
- 历史门禁E前17步通过，第18步中断：16979 collected、39781阶段报告中13243 call通过/8失败/8跳过。原8失败及定点处置已保存，后续局部通过不把E改成完整门禁。算法/图/候选三前缀2729 collected，2728 call通过及1个当时历史质量失败，无skip/missing；也不另加到模块测试总数。
- 最后一次主仓尝试使用Python3.8/Chromium109和`--allow-dirty-worktree --no-long-gate-cache --no-resume`，仅guard预检退出；长测试未运行。见[invocation](/private/tmp/aps-algorithm-implementation-20260912/full-gate-main-final-invocation.json)、[预检处置回执](/private/tmp/aps-algorithm-implementation-20260912/main-final-preflight-closure/receipt.json)。8个已知测试只添加intent-to-add，文件字节不变，无实际暂存内容；这是测试可见性处置，不是产品缺陷。
- 用户明确要求停止扩大验证，本轮不再重跑整仓门禁。最终整仓门禁未完成，不声称clean/full proof；历史局部失败、旧性能慢化和不可迁移基线原样保留。

## 6. 明确拒绝的实验与保留限制

**H 选中 payload 缓存没有实施。** [测量原始记录](../../refactors/2026-09-12-run-snapshot-reuse/payload-cache-study.json) 绑定了既有 5000 工序历史 profile 和修改前 `run_compute.py` 相同字节。该 profile 总 self time 为 164.248633584 秒，全部 5 次 `build_validated_schedule_payload` 累计仅 0.292056041 秒，小于 0.18%；仅消除选中候选的一次调用上界更小。结果/输入可变，且两次校验间存在摘要生成，仅凭对象 identity 缓存不安全；完整内容证书会新增扫描及验证面。测得的上界不支持这项复杂缓存，故保留所有原校验。该历史 profile 中一次完整事实指纹为 0.102125042 秒，也不是本轮入口提速结果。

**C 保留失败性能实验。** `native-comparison.json` 中共享资源的大幅慢化促使收紧门槛；最终版本另存 `native-comparison-final.json`，中间收敛版本为 `native-comparison-selected.json`。它们绑定的源版本不同，不能挑选最快数字拼成一组正式旧新对照。极轻工序仍存在固定认证开销。

**F 旧基线不可直接复用。** 旧 ratchet 和旧 GraphReady v2 比较基线保持原字节；新协议实际返回 `baseline_migration_required` 或 `missing_baseline`。重新建立 schema 2 正式基线要求最终 clean 源码上的真实串行运行，不通过更换 schema/dirty 标签、放宽阈值或 `--allow-dirty-proof` 绕过。历史核心矩阵的独立 clean 参考与这些旧入口分开记账。

**G 完整入口与独立 oracle 的证明域有限。** G 从准备好的排产输入进入 `run_candidate_comparison`，计入整个候选比较，采用 `score_only`；不覆盖此前业务采集/工艺展开或此后的持久化，也不据此声明默认 `balanced` 已验证。20 例矩阵覆盖宽并行、班次/共享/稀缺资源、冻结、就绪与外协等合成输入，piece 的完整入口接线仍依赖既有专门合同，不把该矩阵标成已覆盖全部 piece 业务流程。独立 oracle 仅限 1–6 道工序、单一固定机人、全部 release=0、连续可用日历、无停机及顺序相关 setup；独立枚举拓扑顺序并计算四目标的完整字典序向量。非零释放等域外输入拒绝，不能声称一般 APS、piece/DAG 大实例或完整优化器达到全局最优。

**H 观察口径发生局部变化。** `final_capacity_observation.py` 的 engine v1 包含独立 prepared 新鲜度扫描，v2 从 prepare 后的私有计算续体开始；不能用两个 engine 值直接计算同口径提速。正式准入→终态总耗时仍可比较，180 秒验收门槛保持不变。

## 7. 收尾状态

本轮已报告的A–K均有实现、适用验证或明确实验处置；H选中payload缓存因可测收益上界过小且需新增可变输入证明而拒绝，原校验保留。前期c的六项回退、后续三项完整入口回退及resume1的tiny次级回退均保留原记录，最终以resume2的20+8通过收口，没有刷新基线掩盖退化。

实施与定向验收完成；最终整仓门禁按用户要求不再追加，明确保持未完成。已完成UI和所有未提交现场保留，没有Git提交、安装、发布或依赖升级。架构只归并当前合同，不刷新历史规模/SCC数字，不把旧clean proof移用到本轮。
