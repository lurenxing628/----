# 排产算法深度研究 · 问题清单全集（2026-07-20）

> 来源：算法深度研究 workflow（runId wf_db8f9dd8-b33，10 领域研究员+对抗评审）。
> 综合档案：`.codestable/research/2026-07-20-algo-deep-research/index.md`。
> 行号以 2026-07-20 工作区为准（当日 A 批修复已改动的文件可能有小幅漂移，以内容定位）。
> 标注说明：【评审确认】=经可行性对抗评审员亲验；【评审修正后确认】=问题成立但口径被收窄/修正，正文附修正；【未经对抗评审】=研究员直报（含 resource-model 等评审断流领域，以及评审标题改写后未能自动匹配者）。

**共 57 条有效问题：高 12 / 中 30 / 低 15；另 1 条被评审否决（附录）。**

---

## 一、高严重度（high）（12 条）

### 1. 【评审确认】saveability/sacrifice_penalty/due_pressure 不含机器竞争,负载场景下整池饱和失去区分度

- **严重度**：高
- **位置**：`core/services/scheduler/run/optimizer_graph_ready_v2_features.py:324-347(特征定义), 95-103(只用本批 remaining)`
- **领域**：GraphReadyV2 特征工程与权重 profile 族(optimizer_graph_ready* / sgs 图评分键)
- **证据**：特征只比较『本批自身剩余工时 vs 本批交期窗口』,不含同池竞争工作量。wt40 实例实测(/tmp/exp3):40 个工序 saveability 全部=1.0、sacrifice_penalty 全部=0.0(distinct=1),导致 saveability/sacrifice 主导的公式全部塌缩为 due_pressure 单特征排序。单机 40 job 总工时≈48000h、单批自身 due 窗口>>自身工时是典型负载形态,生产多批共享机台同理。v2『目标感知』族的核心特征在最需要区分的场景里没有信号。

### 2. 【评审确认】19 个 profile 固定枚举序 v1 在前、无解码前排序去重,高价值 profile 排在第 12/17 位,紧预算下可能永远轮不到

- **严重度**：高
- **位置**：`core/services/scheduler/run/optimizer_graph_ready_profiles.py:180-194(枚举序); core/services/scheduler/run/optimizer_graph_ready.py:256-301(先解码后指纹去重,289)`
- **领域**：GraphReadyV2 特征工程与权重 profile 族(optimizer_graph_ready* / sgs 图评分键)
- **证据**：实测唯一稳定赢家 v2_spt(20/25 wins)与 v2_sacrifice_long(24/25 wins, 7 sole wins)分别排在枚举第 12、17 位,而前 9 个 v1 profile 在 SMTWT 上互相逐位一致(8 个 always-identical)。指纹去重发生在完整 SGS 解码之后(evaluate→mark_candidate_evaluated),重复排序照样花一次全量解码。默认 time_budget=5s(schedule_config_runtime_fields.py:92)与局搜共享 deadline(schedule_optimizer.py:279),n=40 单机每解码约 61ms,生产上百工序+auto_assign 探测时每解码更贵,图相既可能吃光预算饿死局搜,也可能在到达 due-aware 公式前被截断。

### 3. 【评审确认】SGS 每轮全量重评分+全池探针：现实规模单跑成本直接吞掉 improve 全预算

- **严重度**：高
- **位置**：`core/algorithms/greedy/dispatch/sgs.py:252-291 + core/algorithms/greedy/auto_assign.py:247-305`
- **领域**：SGS 主循环与评分架构（sgs.py / sgs_scoring.py / sgs_graph.py / batch_order.py / auto_assign.py 探针链）
- **证据**：实测（/tmp/sgs_probe_experiment.py，合成实例+连续日历、.venv py3.8）：固定资源 500 工序单次 SGS 2.5-3.7s、25,774 次 estimate_internal_slot（51.5 次/工序）；auto-assign 500 工序 13.9-30.9s、412,192 次（824 次/工序，其中 92% 是评分期探针全池对扫）；auto-assign 1000 工序单跑 118.6s。同实验测得 84-92% 的重评分 key 与上一轮完全相同（读集失效规则'同批∪机台池含被占机∪人员池含被占人'在两类实例上 0 违例），即绝大多数评分是纯重复劳动。而 improve 默认 time_budget_seconds=5（core/models/schedule_config_runtime_fields.py:92），deadline=起点+预算（core/services/scheduler/run/schedule_optimizer.py:279），每个局搜邻居=一整次 SGS（optimizer_local_search_candidate_eval.py:36-53）→ 现实规模下 improve 一个邻居都评不完即触发 time_budget，退化为 greedy。这直击已知'达最优率~18%/邻域浅'的预算饥饿根源。cProfile（固定 500 工序）：_score_candidates 占 dispatch 总时长 97%，estimate_internal_slot 累计 77%。与 #53（仅 meta 重解析）、debt-recheck-ultra U01-U10、full-defect-sweep D 系及 A 批清单核对均无重叠。

### 4. 【评审确认】唯一自动化质量回归门禁被脏 baseline 永久锁红，且门禁测试把脏状态锁死为合同

- **严重度**：高
- **位置**：`tests/_support/optimizer_benchmark_ratchet.py:146-152; tests/algorithm/test_optimizer_benchmark_ratchet_gate.py:41-50; .codestable/roadmap/scheduler-global-optimizer/benchmark-ratchet-baseline.json(dirty_worktree=true, 2026-06-30)`
- **领域**：基准与实验体系（算法质量回归门禁、基准覆盖面、性能基准固化）
- **证据**：实测 .venv/bin/python tests/_scripts_e2e/benchmark_optimizer_ratchet.py --check-baseline → status=failed, failures=[dirty_actual_worktree, dirty_baseline_worktree]，即使工作区干净也必红（baseline 自身 dirty）。门禁测试 test_light_benchmark_ratchet_rejects_tracked_dirty_baseline 断言比对必须失败且 reason 含 dirty_baseline_worktree——在干净工作区重生成 baseline 会让该测试三个断言全挂，修复动作本身触发门禁红。且该测试只查 dirty reason 存在，其余质量回退 reason 混在 failures 里被无视。自 2026-06-30 baseline 冻结以来 core/algorithms+run 已有 6 个 commit 加当前 A 批大改，全部无 ratchet 绑定。

### 5. 【评审确认】中门禁三族基准全部只防 crash 不防质量倒退，'改进不倒退'在中等规模上无锁

- **严重度**：高
- **位置**：`tests/_scripts_e2e/benchmark_smtwt_localsearch.py:135-165(仅 had_failed_samples 返 1); tests/_scripts_e2e/benchmark_fjsp.py:66-69(仅 valid 检查); tests/_scripts_e2e/benchmark_sgs_large_resource_pool.py:139-151(仅有效性)`
- **领域**：基准与实验体系（算法质量回归门禁、基准覆盖面、性能基准固化）
- **证据**：SMTWT 250 实例的 gap/改进数只 print 到 stdout，无阈值无 baseline 比对；实测当前 sgs 局搜 gap 6.82，若倒退回 batch_order 水平 10.78 门禁依旧绿。medium_gate 的 coverage 字段自述为 'non-degradation shape'，实际连 shape 都只是退出码。全套实测仅 43s（10 workers），成本不是不锁的理由。

### 6. 【未经对抗评审】GraphReadyV2 组合在生产规模下被预算饿死：≥500 工序时 10 个 v2 目标感知公式一个都轮不到，而实验中赢家恰恰全是 v2

- **严重度**：高
- **位置**：`core/services/scheduler/run/optimizer_graph_ready_profiles.py:180-194（v1 9 个排前、v2 10 个排尾）；core/services/scheduler/run/optimizer_graph_ready.py:257-259（固定顺序循环+候选间 deadline 检查）；core/services/scheduler/config/config_field_spec.py:284（默认预算 5 秒）`
- **领域**：文献对照与算法选型（SGS+优先规则+局搜 vs 最新实践、CP-SAT 适用边界、轻量 learning-to-dispatch）
- **证据**：实验（/tmp/aps_algo_exp1_profile_coverage.py，合成多机链式算例，仅给图相位完整 5s——生产里 multi_start 还会先烧掉 12 次解码，实际更糟）：500 工序 5s 内只评估 5/19 个 profile（全是 v1），1000 工序 1/19（仅 balanced），2000 工序 1/19 且 wall=30s。无预算限制对照（exp4）：各规模赢家均为 v2 公式（v2_edd/v2_min_slack/v2_seeded_micro_perturbation），500 工序 v2_min_slack 得 overdue=50 vs 5s 预算下只能拿到 57（差 12%）。即生产默认配置下，GraphReadyV2 的'目标感知组合'在中大型算例上事实性失效

### 7. 【未经对抗评审】SGS 解码超线性(≈N^2.3)：每派工一步全量重评分所有 ready 候选，评分占解码 96%，同时导致预算语义失真（5s 预算实际跑 30s）

- **严重度**：高
- **位置**：`core/algorithms/greedy/dispatch/sgs.py:199-247（while 循环每轮 _collect_candidates→_score_candidates 全量）；core/algorithms/greedy/dispatch/sgs_scoring.py:214-226（每候选每步重新估算槽位）；core/algorithm_runtime/internal_slot.py:279-330（每次估算重建 SegmentOverlapIndex、0-hop 线性扫时间轴）`
- **领域**：文献对照与算法选型（SGS+优先规则+局搜 vs 最新实践、CP-SAT 适用边界、轻量 learning-to-dispatch）
- **证据**：cProfile（/tmp/aps_algo_exp2_profile_decode.py，500 工序图模式解码 2.15s）：500 步×~90 候选=45,050 次 _score_candidate 占 2.06s(96%)，其中 estimate_internal_slot 1.09s(53%)、_candidate_meta 0.45s（内含 45,150 次 strptime 重解析交期 0.30s=14%，即已登记 #53 的量化确认）。相邻两步之间只有 1 台机/1 个人/1 个批次的状态变化，其余候选评分不变却被重算。规模扫描：24ms@100→14.5s@2000（≈N^2.3）。连锁后果：单次解码不可中断+deadline 只在候选间检查（optimizer_graph_ready.py:304-315），2000 工序时 5s 预算实际 wall=30s，预算合同（'时间到不再开始新排法'）在大算例上等于失效

### 8. 【评审修正后确认】生产 GraphReadyV2 路径上迭代搜索整体短路:改进全靠 9 个一次性 profile 解码

- **严重度**：高
- **位置**：`core/services/scheduler/run/optimizer_local_search.py:298-300;core/services/scheduler/run/optimizer_grasp_ig_candidates.py:427-429`
- **领域**：局部搜索 / GRASP-IG(optimizer_local_search*、optimizer_neighborhood_*、optimizer_grasp_ig_*、optimizer_vns、optimizer_acceptance、optimizer_graph_ready 候选相位)
- **证据**：两处对 graph_ready_context is not None 无条件 return best 并记 'graph_ready_uses_graph_candidate_phase';生产默认 graph_analysis_mode=on(记忆:GraphReadyV2 是生产默认),因此 VNS/邻域/shake/GRASP/IG 全部只在遗留 batch_order 路径生效。图相位本身(optimizer_graph_ready.py:262-301)是单趟 for 循环、每个 profile 一次完整解码,无任何围绕 incumbent 的迭代改进。这可能是 by-design 的相位分工,但结果是生产路径改进能力=9 个一次性候选,与已知'达最优率~18%'直接相关。
- **评审修正**：亲验属实。optimizer_local_search.py:298-300 与 optimizer_grasp_ig_candidates.py:427-429 两处均在 graph_ready_context 非 None 时无条件记 'graph_ready_uses_graph_candidate_phase' 并 return best;optimizer_graph_ready.py:255-301 是单趟 for profile 循环、每 profile 一次完整解码、无迭代。生产默认 graph_analysis_mode=on,故生产路径确无迭代式改进搜索。保留 adjusted 而非 confirmed 仅因两点:(1) 行号与代码处于 A 批并发修复中(_run_weight_profiles 内已出现 _candidate_should_replace_best/_accept_candidate/append_graph_trace 等新痕迹,可能是修复中间态),结论需以集成后为准;(2) '相位分工 by-design' 的可能性报告自己也承认,建议对照 graph_ready 相位的设计文档/ADR 确认这是分工决策还是遗漏,再定 severity=high。

### 9. 【评审确认】追踪中的 ratchet 基线自身 dirty_worktree=True,质量棘轮永远无法 pass,且必跑测试硬编码断言它 failed——棘轮形同虚设

- **严重度**：高
- **位置**：`.codestable/roadmap/scheduler-global-optimizer/benchmark-ratchet-baseline.json(dirty_worktree=true);tests/algorithm/test_optimizer_benchmark_ratchet_gate.py:44-55(test_light_benchmark_ratchet_rejects_tracked_dirty_baseline 断言 comparison status==failed,reason==dirty_baseline_worktree);tests/_support/optimizer_benchmark_ratchet.py:146-160(_worktree_proof_failures)`
- **领域**：基准与实验体系(算法质量基准 / 回归棘轮 / 性能基准)
- **证据**：python3 读基线 json 实测 dirty_worktree=True(基线 commit e3ed32c,由 2fae3625 提交)。任何 --check-baseline 都因 unbound_dirty_worktree 失败;唯一的必跑测试把这个失败当预期,即干净工作区也拿不到 passing 的算法质量棘轮证明。

### 10. 【未经对抗评审】生产默认 improve 路径(local_search/grasp_ig/graph v2)在 SMTWT 250 实例上无任何质量回归门禁;SMTWT 对比 evidence 只跑 2 个实例且无 check-baseline

- **严重度**：高
- **位置**：`tests/_support/optimizer_smtwt_compare_algorithms.py:127-129(limit_per_size 截断);evidence/QualityGate/long_gate/optimizer_benchmark/optimizer_smtwt_compare_algorithms.json(limit_per_size=1,只 2 case);tests/_scripts_e2e/benchmark_smtwt_localsearch.py:165(return 1 if had_failed_samples——只在样本抛异常时 fail,gap 变大不 fail)`
- **领域**：基准与实验体系(算法质量基准 / 回归棘轮 / 性能基准)
- **证据**：ratchet 基线只有 3 个 case 且全是 tiny/graph_ready 单 case;对比基线 70 行全部同一 case_slug(graph-ready-weight-grid-real-sgs)。已 vendored 的 250 实例+Moore-Hodgson oracle 完全没进任何门禁;实测跑了一下 loaders+grading 路径存在且可用,缺的只是基线+check 接线。

### 11. 【评审确认】A14 外部组缓存重建在真实调用边界失效:operations 参数不含被冻结工序

- **严重度**：高
- **位置**：`core/algorithms/greedy/external_groups.py:50-78;调用方 core/services/scheduler/run/schedule_optimizer.py:152、optimizer_local_search_candidate_eval.py:39、optimizer_graph_ready_candidates.py:76、optimizer_grasp_ig_candidates.py:68、schedule_optimizer_steps.py:68/106/337 全部传 operations=algo_ops_to_schedule`
- **领域**：增量排产:seed 续排、freeze_window 冻结、batch_order_override
- **证据**：_merged_group_key_by_op_id(operations)(external_groups.py:50-61)只能给 operations 里出现的 op_id 建组键,而 _seed_blocks_by_group(:64-78)按 seed.op_id 查这张表;生产链路所有 schedule() 调用传的都是已剔除固定集的 algo_ops_to_schedule(schedule_input_runtime_support.py:29-30),被种的 merged 组成员不在 operations 里→查表恒 miss→重建恒空转,且没有任何计数/告警暴露这次空转。冻结按批 seq 前缀切割,merged 组跨界时部分成员被冻部分待排是完全可能的,即 A14 要修的场景在集成后依旧复现。并发修复中,以集成后为准;但当前形态必须改数据源(传全量 operations 或单独传组键映射)才有效。

### 12. 【评审确认】SGS 评分跨轮零复用导致准二次墙:1200 工序在制品规模下不可用(>300s 未跑完)

- **严重度**：高
- **位置**：`core/algorithms/greedy/auto_assign.py:255 (_choose_best_pair) + core/algorithms/greedy/dispatch/sgs.py:250 (_score_candidates)`
- **领域**：端到端性能画像(SGS 派工主链路 + 优化器候选评估)
- **证据**：cProfile 实测:200ops=7.5s、400ops=17.6s、1200ops/120批>300s(被杀);estimate_internal_slot 调用 70 万次/400ops(85 次/auto_assign 尝试×全配对,每轮重估同一批候选)。同一候选工序在未中选前每轮都被对所有机-人对重新 estimate,而时间轴每轮只有 1 机 1 人变化。已用 memo 原型验证 90.9% 的调用是重复计算(/tmp/aps_memo_experiment.py,输出逐结果比对一致)

## 二、中严重度（med）（30 条）

### 13. 【评审确认】v2_atc_like 与 v2_critical_ratio 代数等价,CR 族 5 个 profile 实际是同一个排序

- **严重度**：中
- **位置**：`core/services/scheduler/run/optimizer_graph_ready_candidates.py:291-305; core/services/scheduler/run/optimizer_graph_ready_v2_features.py:324-339`
- **领域**：GraphReadyV2 特征工程与权重 profile 族(optimizer_graph_ready* / sgs 图评分键)
- **证据**：atc_like 主键 -due_pressure=-(remaining/due),critical_ratio 主键 due/remaining——对所有未过期未收紧(remaining<due)工序是同一全序(x 与 1/x 取负的单调恒等),差异只在 clamp/逾期区。实验 /tmp/exp3_v2_feature_ties.py:wt40 实例上 critical_ratio/atc_like/saveability/bottleneck_due_gated/micro_perturbation 五个公式 induced order 逐位一致;/tmp/exp1_profile_wins.py 40 实例上五者排程 35/40 完全相同,mean gap 16.0-16.2 全部劣于 baseline 11.55。5/19 的解码预算买同一个(且更差的)候选。

### 14. 【评审修正后确认】slack/due_pressure 口径错位:窗口从『本工序就绪时刻』起算,剩余工时却用『整批总量』,上游工时被双计

- **严重度**：中
- **位置**：`core/services/scheduler/run/optimizer_graph_ready_v2_features.py:62(capacity_start_dt=start+ready_offset), 95-97(slack=due_budget-整批 remaining)`
- **领域**：GraphReadyV2 特征工程与权重 profile 族(optimizer_graph_ready* / sgs 图评分键)
- **证据**：例:批内 A(10h)→B(10h),交期 100h。B 的容量窗口从 t=10 起算约 90h,但 remaining 用整批 20h,slack=70;而 B 就绪时真实剩余只有 10h,真 slack=80。深链批次的下游工序被系统性高估紧迫度,跨批比较时深链批被结构性偏置。纯代码推导,未做端到端量化(证据强度:代码级确认,量化不足)。
- **评审修正**：口径错位机制代码级确认:capacity_start_dt=start+ready_offset(features.py:62 区域,ready_offset 按批内上游工时累加),而 remaining_hours=_remaining_hours_by_batch 的整批总量(:95-97 区域),slack=due_budget-remaining(:112),窗口起点与剩余工时基准确实不一致,B 工序上游 10h 被双计的推导正确。但两点修正:1) 字段被同时写成 remaining_due_burden_hours(:126 区域),'整批负担'可能是有意的保守语义(把上游占用视为该工序的交期负担),是设计选择还是 bug 需要语义裁决,不能直接定缺陷;2) 报告自己承认无量化,危害方向(系统性高估深链批紧迫度)依赖跨批比较场景,单机同批场景影响为零。降级为机制确认、定性与量级待证。

### 15. 【评审确认】v1 加权和原始尺度混算,critical_path 权重是死旋钮;v2_graph_due_hybrid 的 graph_bonus 继承同一问题

- **严重度**：中
- **位置**：`core/services/scheduler/run/optimizer_graph_ready_candidates.py:142-162(_metric_bonus 原始尺度), 196(graph_bonus 用 raw 权重); optimizer_graph_ready_profiles.py:33-43`
- **领域**：GraphReadyV2 特征工程与权重 profile 族(optimizer_graph_ready* / sgs 图评分键)
- **证据**：is_on_critical_path 是 0/1×权重≤4 的平坦加分,而 downstream_hours 可达数百、bottleneck_score 数百,同权重直接相加。实验 /tmp/exp2_v1_scale_imbalance.py(300 工序、生产尺度):把 critical_path_first 的 cp 权重 4→0 只改变 0.225% 的成对排序决策;『critical_path_first』与『balanced』的差异(Kendall 0.10)几乎全部来自瓶颈权重减半而非其命名的关键路径强调。9 个 v1 profile 名义语义与实际排序行为脱节。

### 16. 【评审确认】v2_seeded_micro_perturbation 的 jitter 排在连续特征之后,几乎永不触发,种子多样性为零

- **严重度**：中
- **位置**：`core/services/scheduler/run/optimizer_graph_ready_candidates.py:302-305`
- **领域**：GraphReadyV2 特征工程与权重 profile 族(optimizer_graph_ready* / sgs 图评分键)
- **证据**：jitter 位于 (sacrifice_penalty, -due_pressure, jitter, ...) 第三位,due_pressure 是连续特征(wt40 实测 40/40 distinct),仅精确同值才轮到 jitter。实测该 profile 与 v2_critical_ratio 排程 35/40 完全一致——注释宣称的『同分候选间提供多样性』在跨批场景基本不发生,不同 seed 产生相同候选。

### 17. 【未经对抗评审】生产图模式 58%-78% 的候选全量解码可在解码前判定为必然重复，但全部照付全价；固定评估顺序还把互相重复的 v1 网格和 multi_start 排在 v2 组合之前，deadline 截断时最先砍掉最有价值候选

- **严重度**：中
- **位置**：`core/services/scheduler/run/optimizer_graph_ready.py:256-301（_run_weight_profiles 逐 profile 全解码、:257-259 deadline 截断）+ optimizer_graph_ready_profiles.py:180-194（v1 在前 v2 在后的固定顺序）+ schedule_optimizer.py:319-371（multi_start 12 次解码先于图阶段）`
- **领域**：评估函数与目标体系（evaluation.py / objective.py / candidate_eval 链 / best_metrics 流转）
- **证据**：已入库证据的重复输出率：portfolio 83%-85%、graph_ready_v2 58%-70%、v1 40%-80%（evidence/QualityGate/long_gate/optimizer_benchmark/optimizer_smtwt_compare_algorithms.json rows、optimizer_long_run.json aggregate mean_duplicate_candidate_rate=0.7、.codestable/roadmap/scheduler-global-optimizer/graph-ready-v2-comparison-baseline.json rows evaluated/distinct 字段）。/tmp/rank_map_real_smtwt.py 实验（真实 wt40/wt50 图上下文，与证据同族构造）：9 个 v1 profile 只诱导 2 个不同优先键弱序（78% 解码可预判跳过），19 个生产组合 profile 只有 8 个弱序（58% 可跳）；图结构更丰富的 tiny-4op 基准 v1 仍有 33% 可跳（/tmp/rank_map_dedup_experiment.py）。每次重复解码已付全价（/tmp/eval_cost_experiment.py 实测 wt40 sgs 解码 51ms/次、metrics 0.26ms、指纹 0.34ms）。可预判性的依据：per-op 优先键是静态 map（sgs.py:343-350），弱序（含并列类）相同则任意 ready 子集 argmin 相同 ⇒ 解码必然相同；循环内其余入参全同，graph_ready_profile 参数在 core/algorithms 全域无消费（解码惰性，已 grep 核实）。该浪费被证据体系量测但从未立案为问题（audits/roadmap 均查过）。

### 18. 【评审确认】winner 槽位被独立推导 4 次：探针、评分复算、放置重探针、放置终算

- **严重度**：中
- **位置**：`core/algorithms/greedy/dispatch/sgs_scoring.py:189-201 + core/algorithms/greedy/internal_operation.py:122-135`
- **领域**：SGS 主循环与评分架构（sgs.py / sgs_scoring.py / sgs_graph.py / batch_order.py / auto_assign.py 探针链）
- **证据**：auto-assign 候选评分先在 _choose_best_pair（auto_assign.py:247-305）里对最优对算过 estimate_internal_slot，_estimate_scoring_slot（sgs_scoring.py:351-382）随即对同一对同一状态原样重算一次——实测 500 工序 auto-assign 单跑该重算 25,262 次，占全部估算 6.1%，全部为纯重复；被选中的 winner 进 _dispatch_selected→_schedule_op 后，_resolve_internal_resources（internal_operation.py:122-135）又重跑一次全池 auto-assign（实测 7,500 次估算，1.8%）+ 放置终算 500 次。评分与放置的一致性目前靠'确定性重算必然一致'隐式成立，等价契约已有测试锁（tests/algorithm/test_internal_slot_estimator_consistency.py 首行 docstring：估算与落地完全一致），说明直通传递不改行为且有现成测试护栏。

### 19. 【未经对抗评审】冻结前缀完整性检查不感知执行事实种子/滞后报工：在制批次系统性丢冻结，strict 模式整趟中止（已实测复现）

- **严重度**：中
- **位置**：`core/services/scheduler/run/freeze_window.py:380-389（missing prefix 降级）+ :127-128（strict 抛 ValidationError）+ core/services/scheduler/run/schedule_input_collector.py:319-325（仅剔除 COMPLETED，PROCESSING/PAUSED 留在 reschedulable）+ core/services/scheduler/run/schedule_input_runtime_support.py:146-160（冻结先算、执行种子后合并）`
- **领域**：增量排产（seed 续排 / freeze_window 冻结 / batch_order_override / 部分重排正确性边界）
- **证据**：冻结 prefix 取 reschedulable 中 seq<=max_seq 的全部工序（freeze_window_prefixes.py:28-29），但 schedule_map 只装载与窗口重叠的上一版行（data/repositories/schedule_repo.py:71-80 重叠语义）。前道工序上一版计划行完全落在 start_dt 之前且未报完工（报工滞后、或未用报工模块、或 PROCESSING 已由执行种子钉住），prefix 即缺行→该批整批降级失冻。/tmp/freeze_past_prefix_repro.py 用真实 build_freeze_window_seed 复现：seq1 计划行 D-2~D-1、seq2 在窗内 → frozen=[]、freeze_state=degraded、警告只说'冻结窗口资料不完整'；对照组（seq1 已完工移除）frozen=[2] 正常；strict_mode=True 整趟 ValidationError 中止。其中'前道已 PROCESSING 被执行种子钉住'形态冻结后道本是可行的（前道位置已被执行种子固定），却被当资料不完整拒绝——冻结最想保护的在制批次恰恰最容易丢冻结。与 A15（disabled reason 断档）、驳回清单#2（日志缺版本号）均非同一缺陷。注：freeze_window.py 在本轮 A 批工兵并发修改中，以集成后代码为准（本复现基于当前工作区）。

### 20. 【未经对抗评审】部分批次重排的资源视界只有本次选中批次：未选批次的已采纳计划与在制执行事实完全不可见，可静默双订机台/人员

- **严重度**：中
- **位置**：`core/services/scheduler/run/schedule_input_collector.py:151-168（只装载所选批次工序）+ :306-318（执行事实只查所选工序的上一版行）+ core/services/scheduler/resource_pool_builder.py:223-277（downtime_map 只含维护停机）+ core/services/scheduler/run/schedule_persistence.py:290-297（新版本只写本次 payload 行）`
- **领域**：增量排产（seed 续排 / freeze_window 冻结 / batch_order_override / 部分重排正确性边界）
- **证据**：web/routes/domains/scheduler/scheduler_run.py:44 允许任意批次子集提交排产。算法收到的占用信息=种子（仅所选批次）+维护停机，未选批次哪怕正在某机台上加工（有 PROCESSING 执行事实），本次排产也感知不到——新计划可把所选批次排上同一机台同一时段，零警告零留痕。同时新版本 Schedule 行只覆盖所选批次，未选批次从最新版本视图消失（plan 解析按 version+role，schedule_plan_query_service.py:98，无跨版本按批合并）。要么现场同时执行两版计划互相冲突，要么未选批次计划事实作废。在 .codestable 需求/审计（含 2026-07-20 A01-A18）中未找到该语义的 by-design 裁决；若产品预期是'每次全选活动批次'，也没有任何守卫或提示强制这一预期。

### 21. 【评审确认】ratchet CLI --update-baseline 无脏工作区拒写防护，与 compare_algorithms 不对称

- **严重度**：中
- **位置**：`tests/_scripts_e2e/benchmark_optimizer_ratchet.py:52-54 对比 tests/_scripts_e2e/benchmark_optimizer_compare_algorithms.py:65-73`
- **领域**：基准与实验体系（算法质量回归门禁、基准覆盖面、性能基准固化）
- **证据**：compare_algorithms 在 dirty worktree 且无 --allow-dirty-proof 时拒绝写 baseline 并返 1；ratchet CLI 直接 write_baseline 无任何检查，也没有 --allow-dirty-proof 参数（build_arg_parser 只有 tier/baseline/update/check 四项，:34-40）。当前锁死门禁的脏 baseline 正是从这个通道写出的。

### 22. 【评审确认】质量基准族对 4 个业务目标只覆盖 min_overdue，其余 3 目标零基准且已有可测退化

- **严重度**：中
- **位置**：`core/models/objective.py:18-46(4 objectives); grep tests/_scripts_e2e+tests/_support 基准代码仅 min_overdue（min_tardiness/min_changeover 只出现在 e2e 冒烟参数里）`
- **领域**：基准与实验体系（算法质量回归门禁、基准覆盖面、性能基准固化）
- **证据**：实验：用现有 build_tiny_case_reference 构造 6 工序 min_changeover 案例，oracle 5ms 证明最优 2 次换型，当前 greedy/SGS 解出 4 次，gap_to_oracle_pct=100%——该退化在现有任何基准/门禁下不可见。vendored 的 wtopt40/50 加权最优值明确不用于评分（optimizer_benchmark_loaders.py:9-12 注释），min_weighted_tardiness 无任何量尺。

### 23. 【评审修正后确认】场景覆盖缺口：所有质量基准都在连续日历/无停机/无冻结/无资源池下跑；RCPSP 数据 vendored 两年式闲置

- **严重度**：中
- **位置**：`core/services/scheduler/run/optimizer_proof_oracle.py(_ContinuousCalendar); tests/_support/optimizer_fjsp_runner.py:96(seed_calendar_24h); tests/_support/optimizer_benchmark_loaders.py:79-81('not run through APS'); tests/_data/optimizer_benchmarks/rcpsp/`
- **领域**：基准与实验体系（算法质量回归门禁、基准覆盖面、性能基准固化）
- **证据**：全部基准 downtime_map={}、freeze_window_enabled=no、resource_pool=None（唯一带 300 候选对资源池的大池基准只排 1 个工序、只验有效性）。班次日历/停机时间轴/冻结窗/机人配对这些生产默认特征对解质量的影响没有任何基准量测；j30 实例+published optima+关键路径下界 loader 全部就绪但零执行。
- **评审修正**：前半段全部核实：oracle 用 _ContinuousCalendar(optimizer_proof_oracle.py:35-46)、freeze_window_enabled='no'(:328)；graph_ready 基准 downtime_map={}(optimizer_graph_ready_benchmark.py:222)、resource_pool=None(:228)；FJSP seed_calendar_24h(optimizer_fjsp_runner.py:95)；大池基准确实只排 1 个工序(benchmark_sgs_large_resource_pool.py:178-192)。修正后半段口径：(1)'两年式闲置'夸大——RCPSP 数据 2026-06 才 vendored，闲置数周而非数年；(2)不跑进 APS 是 loader 文档化的主动决定而非遗忘(optimizer_benchmark_loaders.py:76-81 'do not fold into the single-capacity APS model, so these are not run through APS'，并引 roadmap 4.2/102/274 可比性 caveat)；(3)实际只 vendored 3 个 .sm 实例(j301_1/j301_2/j3013_5)+480 条 optima，不是可直接开跑的完整 j30 集。场景盲区本身(med)成立。

### 24. 【未经对抗评审】评分 probe 结果丢弃导致同一轮内配对探测+槽位估算被执行两到三遍

- **严重度**：中
- **位置**：`core/algorithms/greedy/dispatch/sgs_scoring.py:214-226 + core/algorithms/greedy/auto_assign.py:255-321 + core/algorithms/greedy/internal_operation.py:123-199`
- **领域**：资源模型：auto_assign 机人配对、internal_slot 槽位估算、downtime 时间轴、双资源占用
- **证据**：sgs_scoring.py:171-226 先 probe_only 全配对探测、选中后对同一 pair 再调 estimate_internal_slot；sgs.py:215-247 评分与放置之间 run_state 无任何变异（record_dispatch_success 在放置后才调），internal_operation.py:123-136 却对全部 P 对重新探测、:185 再重估。/tmp/bench_slot.py 实测：250op/50批/6pair 规模全程约 46375 次 estimate 调用，其中放置层重探 1750 次 + 每轮选中 pair 重估约 1250 次为纯重复，且集中在 timeline 最长的后期轮次。与已知'后端重复劳动8HIGH'清单可能部分重叠，需对照去重；A03/A10 并发修复中，以集成后为准。

### 25. 【未经对抗评审】SegmentOverlapIndex 每次 estimate 调用重建，惰性物化在调用间永不复用，首扫恒 O(T)

- **严重度**：中
- **位置**：`core/algorithm_runtime/internal_slot.py:299-303 + core/algorithm_runtime/downtime.py:57-68`
- **领域**：资源模型：auto_assign 机人配对、internal_slot 槽位估算、downtime 时间轴、双资源占用
- **证据**：internal_slot.py:299-303 每次调用新建 3 个 SegmentOverlapIndex；downtime.py:57-68 惰性物化要同一对象第 2 次 shift_end 才构建前缀数组，而索引对象活不过单次 estimate——0-hop（最常见路径）每次 O(T) 线性扫。实测单次估算 49.1us@T=10、224.0us@T=50、896.5us@T=200，随时间轴线性恶化；SGS 全程内层成本实为 O(轮数×B×P×T)。

### 26. 【未经对抗评审】生产默认（图模式）完全没有改进搜索：local_search/grasp_ig 双双跳过，图相位又只有组合枚举没有邻域，整套 VNS/邻域/restart 机器在默认路径上是死代码

- **严重度**：中
- **位置**：`core/services/scheduler/run/optimizer_local_search.py:298-300（graph_ready_uses_graph_candidate_phase 跳过）；core/services/scheduler/run/optimizer_grasp_ig_candidates.py:427-429（同理跳过）；core/services/scheduler/run/optimizer_graph_ready.py:225-301（相位内无任何邻域/改进步）；GRAPH_READY_LOCAL_SEARCH_ORIGIN 常量预留未用（optimizer_graph_ready_profiles.py:12，仅被 optimizer_graph_ready.py:21,484 re-export）`
- **领域**：文献对照与算法选型（SGS+优先规则+局搜 vs 最新实践、CP-SAT 适用边界、轻量 learning-to-dispatch）
- **证据**：与已知 item9-13 修复史不同——那修的是非图 batch_order 路径的局搜；图路径是整段缺失。'repair'仅存在于基准测试代码（tests/_support/optimizer_smtwt_compare_graph.py:154-199），未进生产。实验 exp3：在组合最优解上用同一机制加一段 op 级前拉插入局搜，100 工序时加权拖期 13→4（-69%，18 次评估/0.7s）、500 工序 6241→6229（预算被解码慢卡住，见问题2）。gate 里的 SMTWT 对比也显示 with_repair 与 no_repair 打平（evidence/QualityGate/long_gate/optimizer_benchmark/optimizer_smtwt_compare_algorithms.json：仅 size=40、2 seeds、16 邻居的浅 repair，区分度不足）

### 27. 【未经对抗评审】图评分开启时 batch_order 类作用器被结构性架空：multi_start 12 次解码近乎重复烧预算，CP-SAT warmstart（若启用）输出的批次顺序也只剩深层 tie-break 作用

- **严重度**：中
- **位置**：`core/algorithms/greedy/dispatch/sgs_scoring.py:77-78（graph key 插在派工键主项前）；core/algorithm_contracts/dispatch_rules.py:87-95（batch_order 是第 5 位 tie-break）；core/services/scheduler/run/schedule_optimizer.py:319-346 + optimizer_config.py:47-51 + schedule_optimizer_steps.py:282-285（图模式 multi_start 仍跑 4 策略×3 规则=12 次解码，彼此只差 graph key 之后的尾部键位）；core/services/scheduler/run/schedule_graph_dispatch_context.py:254-256 + schedule_graph_score_projection.py:188-194（生产 base context 在 score 请求开启时带 score_enabled=True 的统一 graph key）`
- **领域**：文献对照与算法选型（SGS+优先规则+局搜 vs 最新实践、CP-SAT 适用边界、轻量 learning-to-dispatch）
- **证据**：v2 公式键含 per-op jitter（optimizer_graph_ready_candidates.py:264-271）几乎不产生平局，batch_order/dispatch_rule 差异极难穿透 graph key。后果：500 工序时 multi_start 的 12 次近重复解码≈5.5s，先于图相位耗尽 5s 预算（加重问题1）；ortools_bottleneck.py:77-231 的单机序列解在图模式评估（schedule_optimizer_steps.py:217-236 传入 graph context）时作用点同样被架空。与已立案 item6/7/8（作用点错位）同根但为新站点。限定：score_enabled=False（未配置图评分权重）时 multi_start 仍有真实差异；且相关文件在 A 批并发修复中，以集成后代码为准

### 28. 【未经对抗评审】利用率报表分母仍用 midnight 采样 capacity_hours，跨午夜班次工时错归属

- **严重度**：中
- **位置**：`core/services/report/report_engine.py:386（缺陷函数本体 core/services/report/calculations.py:66-78）`
- **领域**：日历引擎与算法交互（calendar_engine × SGS/auto-assign/internal_slot × 报表容量口径）
- **证据**：实验（/tmp/cal_capacity2.py，真实 CalendarEngine+内存 SQLite）：周一夜班 20:00→06:00(10h)+周二白班 8h，capacity_hours 返回 20.0（应 18.0）——每日 00:00 采样经 _policy_for_datetime 跨午夜归属规则（calendar_engine.py:226-232）落到前一日夜班策略，前一日班时重复计入、当日班时丢失。该缺陷在代码内已是明知：_sched_display_utils.py:120-122、week_plan_daily_summary.py:4、gantt_resource_load.py:4-9 三处消费方均注释'midnight 采样在跨午夜班次错归属，4.6 红线'并改用 capacity_hours_at_noon 绕行，唯 ReportEngine.utilization 未迁移（symbol_locator callers 确认为仅剩调用方）。2026-07-19 blindspot-sweep 只立案了 cap_hours<=0 降级缺口（index.md:90-91），未覆盖此错归属；roadmap capability-mining.md:195 还要求未来功能'与报表 capacity_hours 同源分母'，会扩散缺陷。修法现成：迁移到 capacity_hours_at_noon 同源 helper。

### 29. 【未经对抗评审】齐套检查开启时 ready_date 用全局日历预推进批次进度，丢失 OperatorCalendar 覆盖日的产能

- **严重度**：中
- **位置**：`core/algorithms/greedy/scheduler.py:398-403（_initialize_ready_progress，经 :379-380 readiness_gate 门控）`
- **领域**：日历引擎与算法交互（calendar_engine × SGS/auto-assign/internal_slot × 报表容量口径）
- **证据**：实验（真实引擎端到端）：O1 有周日 2026-01-11 的 OperatorCalendar 覆盖（该特性有回归测试 tests/calendar_maintenance/test_operator_calendar_override_allows_work_on_global_holiday.py 锁住），批次 ready_date=周日、readiness_gate_enabled=True → 工序实排周一 08:00 而非周日 08:00，白丢一个操作员工作日；引擎直证：全局 adjust(周日00:00)→周一08:00，O1 维度 adjust→周日08:00。根因：ready_date 是物料就绪日期而非作业事件，此处却按全局日历（无 operator_id）+批次优先级门控调整后写入 batch_progress；下游 estimate_internal_slot 本来就会按操作员日历再 adjust（internal_slot.py:305-306），预调整只会单向推迟。触发面：enforce_ready 开（默认 no，schedule_input_collector.py:123-139,376）+操作员在全局停排日有覆盖。修复需同时裁决外协工序语义：首道外协的 add_calendar_days 从 prev_end 起算（sgs_scoring.py:276/283），去掉预调整会把外协起点从'下一工作时刻'改回'ready 日 00:00'，属行为变更需一并定案。注：scheduler.py 在 A 批并发修复名单内，此结论基于当前工作区状态实测。

### 30. 【评审确认】IG 重建是随机重插而非贪婪重插,且 GRASP/IG 无迭代循环(名实不符)

- **严重度**：中
- **位置**：`core/services/scheduler/run/optimizer_grasp_ig_specs.py:41-53,75-101`
- **领域**：局部搜索 / GRASP-IG(optimizer_local_search*、optimizer_neighborhood_*、optimizer_grasp_ig_*、optimizer_vns、optimizer_acceptance、optimizer_graph_ready 候选相位)
- **证据**：_ig_order 删除后 `insert_at = rnd.randrange(len(order)+1)` 随机插回;经典 IG(Ruiz & Stützle 2007)要求 NEH 式贪婪 best-insertion。build_grasp_ig_candidate_specs 对每个 restart_index 只产一个 spec、评估一次,没有 accept-and-iterate 主循环。/tmp 实验(20 作业 5 机置换流水车间、总延误、12 实例、同等迭代预算):贪婪重插 12/12 全胜,平均总延误 4665.8 vs 随机重插 5827.3(约 -20%)。注:同等'完整解码次数'预算下贪婪反而更贵(每迭代评估 n-d+1 个插入位),说明该修复必须与增量/廉价评估配套才划算。

### 31. 【评审确认】批次序邻域步长被钉死在 2 个槽位,无 swap/任意位置 insert/块交换

- **严重度**：中
- **位置**：`core/services/scheduler/run/optimizer_neighborhood_moves.py:338-340`
- **领域**：局部搜索 / GRASP-IG(optimizer_local_search*、optimizer_neighborhood_*、optimizer_grasp_ig_*、optimizer_vns、optimizer_acceptance、optimizer_graph_ready 候选相位)
- **证据**：_pull_batch_earlier 统一 `out.insert(max(index - 2, 0), item)`,critical_chain/tardy_window/bottleneck_machine/time_window 四个邻域全部共用;整个算子集没有两批次 swap、没有插入到任意位置、没有 tardy 批次对交换。与已知'邻域浅卡局部最优'是同一根因的具体量化(步长=2),此处作为证据补强而非全新发现。

### 32. 【评审确认】性能基准只记录不棘轮:runtime_ms 在基线里但不参与比较;大资源池性能脚本无耗时基线

- **严重度**：中
- **位置**：`tests/_support/optimizer_benchmark_ratchet.py:110-124(_row_failures 只比 gap_to_oracle_pct/failed_ops,容差 0.0);tests/_scripts_e2e/benchmark_sgs_large_resource_pool.py:1(只断言 scheduled_ops>0/failed_ops=0/result_count 匹配,耗时只写报告)`
- **领域**：基准与实验体系(算法质量基准 / 回归棘轮 / 性能基准)
- **证据**：基线 json 里 runtime_ms=109 等字段存在但 compare_to_baseline 的 _row_failures 不读它。算法核心改动(如本次 A 批改 sgs.py/internal_slot.py)造成 2 倍变慢不会被任何门禁拦下。

### 33. 【未经对抗评审】RCPSP j30 资源受限基准数据与 loader/optima 已 vendored 但完全无人使用,多机资源受限场景零外部参照

- **严重度**：中
- **位置**：`tests/_data/optimizer_benchmarks/rcpsp/(j301_1.sm 等);tests/_support/optimizer_benchmark_loaders.py:176-250(load_rcpsp_instance/load_rcpsp_optima/rcpsp_critical_path_lower_bound);grep 全 tests/ 仅 loader 单测引用`
- **领域**：基准与实验体系(算法质量基准 / 回归棘轮 / 性能基准)
- **证据**：除 test_optimizer_benchmark_loaders.py 的形状测试外,没有任何 case builder/grading/e2e 脚本消费 RCPSP。多目标方面,grading 只锁 overdue_count 第一分量,weighted tardiness/total_tardiness/makespan/changeover 四个 tie-breaker 分量无外部参照。

### 34. 【评审确认】medium gate(三家族编排)未接入任何强制流水线,只被契约测试验证'计划存在'

- **严重度**：中
- **位置**：`tests/_scripts_e2e/benchmark_optimizer_medium_gate.py:50-62(三家族:FJSP smoke/SMTWT localsearch/SGS 大资源池);grep scripts/run_quality_gate.py、run_daily_quality_gate.py 无 benchmark 引用`
- **领域**：基准与实验体系(算法质量基准 / 回归棘轮 / 性能基准)
- **证据**：benchmark_optimizer_medium_gate.py --run 已经能一键跑三家族并汇总 returncode,但质量门禁入口从不调用它;长跑/中跑基准全靠人记得手工跑,evidence 目录 git-ignored,跑完不留可追踪痕迹。

### 35. 【评审确认】槽位估算的效率单点近似与 v2 容量核算的分段效率口径不一致,跨效率日工序两套结果互相矛盾

- **严重度**：中
- **位置**：`core/algorithm_runtime/internal_slot.py:233-237 vs core/services/scheduler/run/optimizer_graph_ready_v2_capacity.py:359-364`
- **领域**：日历引擎与算法交互(calendar_engine × SGS/槽位估算/v2容量)
- **证据**：实测(/tmp/cal_eff.py):周一 eff=1.0、周二 eff=0.5、各 8h 班,12h 工序单点近似 end=周二 12:00,分段精确 end=周二 16:00,偏差 4h。槽位估算只用 start_time 的效率(internal_slot.py:233 'calendar.get_efficiency(start_time...)'),而 v2 容量按段乘每日效率(capacity:363 'total += _wall_hours * _policy_efficiency')。批评家已注记疑似 by-design,故仅记 med:只要日历配置了逐日效率差异,graph-ready 容量特征与实际放置结果会系统性不一致

### 36. 【评审确认】CP-SAT 预热写死 num_search_workers=8,与 Win7 低端机(2-4核)和秒级预算错配

- **严重度**：中
- **位置**：`core/algorithms/ortools_bottleneck.py:194`
- **领域**：文献对照与算法选型(SGS+优先规则+局搜 / OR-Tools 适用边界)
- **证据**：solver.parameters.num_search_workers = 8 无条件设置,而调用方 time_limit 只有 max(1, min(cfg, remaining)) 秒(默认 cfg=5,core/models/schedule_config_runtime_fields.py:85)。低端 Win7 目标机上 8 worker 对一个小模型(<=200 job 单机)只会带来线程竞争和不可复现结果(多 worker CP-SAT 不保证确定性),与'可复现'约束冲突;arXiv:1909.08247 也显示多核收益主要体现在大实例,小实例反而开销。未按 os.cpu_count() 封顶、未暴露配置项。

### 37. 【评审确认】瓶颈工种判定只看工时总和,不除以该工种的并行机台数,多机工种会被误判为瓶颈

- **严重度**：中
- **位置**：`core/algorithms/ortools_bottleneck.py:121`
- **领域**：文献对照与算法选型(SGS+优先规则+局搜 / OR-Tools 适用边界)
- **证据**：load_by_type[ot] 累加工时后直接 max(:121),而 resource_pool 里同一 op_type 可能有多台机/多人;10台机工种总工时100h 的实际瓶颈度低于1台机工种50h。误判会使整个 warm-start 顺序围绕错误资源优化。resource_pool 已传入 scheduler 侧但该函数签名没接(:77-85 参数无 resource_pool)。

### 38. 【评审确认】非前缀 seed(乱序报工)下未种前道被静默排到已固定后道之后,时间序违反工艺序且零留痕

- **严重度**：中
- **位置**：`core/algorithm_runtime/run_state.py:82-90(advance_batch 取 max seed end);core/algorithms/greedy/dispatch/batch_order.py 无固定后继校验;sgs_graph.py:438 冲突留痕只覆盖前道失败分支`
- **领域**：增量排产:seed 续排、freeze_window 冻结、batch_order_override
- **证据**：实测(/tmp/seed_inversion.py,GreedyScheduler batch_order 模式):seq2 固定 09:00-10:00,seq1 被排到 10:00-11:00,前道整段落在后道之后,failure_details 为空、无 warning。机理:batch_progress 对同批 seed 取 max(end)(run_state.py:82-90),未种前道以推进后的 prev_end 为起点;batch_order.py 全文无任何对固定后继的时间序校验;sgs_graph.py 的 graph_fixed_successor_order_conflict 只在失败阻塞传播撞固定集时触发(:336-369、:438)。A02 修的是失败分支,成功但倒置的分支双模式都静默。

### 39. 【评审确认】seed 占用与机台停机(保养)零校验:冻结工序撞上新增 downtime 双占用静默

- **严重度**：中
- **位置**：`core/algorithms/greedy/scheduler.py:366(_prepare_run_state 不收 machine_downtimes)、:425-435;core/services/scheduler/run/schedule_input_runtime_support.py:74-111`
- **领域**：增量排产:seed 续排、freeze_window 冻结、batch_order_override
- **证据**：_prepare_run_state(scheduler.py:366-395)签名不含 machine_downtimes;_freeze_seed_resources(:425-435)只往机台/人员时间轴 occupy,不与停机段比对;downtime 在更外层 _load_runtime_resource_inputs(schedule_input_runtime_support.py:74-111)独立加载。场景:上一版排好的冻结工序,之后新录了该机的保养计划,重排后两者在时间轴上双占用,新版计划把这工序标在保养时段,无任何 degradation/warning。属'不静默'原则缺口。

### 40. 【未经对抗评审】graph-ready 权重网格为重复解码结果付全价 SGS:实测 6/10 候选输出与已见相同

- **严重度**：中
- **位置**：`core/services/scheduler/run/optimizer_graph_ready.py:412-434(_candidate_should_replace_best 在解码后才判 same_as_seen)`
- **领域**：评估函数与目标体系(evaluation.py / objective.py 四目标 / candidate_eval 链 / best_metrics 流转)
- **证据**：/tmp/exp_eval_dup.py 实测(40批/3机/73工序,默认 profile 网格):evaluated_candidates=10,same_fingerprint=6(60% 解码预算白跑),schedule_fn 占墙钟 99.2%。生产 graph_analysis_mode=on 下局搜/GRASP-IG 跳过,该网格就是 improve 模式的几乎全部评估开销。注:本文件 A08 工兵并发修复中,以集成后为准,但评估结构(先解码后判重)是合同层设计,短期不会变。

### 41. 【评审确认】_pair_rank 对 pool 中已是 int 的值逐次 parse_required_int 严格校验,单次排产 63 万次

- **严重度**：中
- **位置**：`core/algorithms/greedy/auto_assign.py:410-421 (_pair_rank) + auto_assign.py:162 (_coerce_resource_pool 只拷结构不解析值)`
- **领域**：端到端性能画像(SGS 派工主链路 + 优化器候选评估)
- **证据**：cProfile 200-op run:parse_required_int 630,600 次调用 tottime 0.19s+callee _parse_finite_int 0.22s,合计约占 6%;pair_rank 字典内容在一次排产内不可变,完全可在 _coerce_resource_pool 时一次性解析

### 42. 【评审确认】每次 estimate 新建 3 个 SegmentOverlapIndex,惰性物化重复 62 万次/次排产

- **严重度**：中
- **位置**：`core/algorithm_runtime/internal_slot.py:183-201 (_slot_segments) + downtime.py:70 (_materialize)`
- **领域**：端到端性能画像(SGS 派工主链路 + 优化器候选评估)
- **证据**：cProfile 200-op run:_materialize 624,807 次/0.48s;而一轮内不同候选访问的是同一批时间轴对象。缓存原型实测整体提速 11%(/tmp/aps_index_cache_experiment.py 9.4s→8.3s)。注意 internal_slot.py 正被 A 批并发修复,行号以集成后为准

## 三、低严重度（low）（15 条）

### 43. 【评审确认】ATC 的 exp 在远交期候选上下溢为 -0.0，远松弛候选间 ATC/WSPT 判别力全部丢失、集体并列

- **严重度**：低
- **位置**：`core/algorithm_contracts/dispatch_rules.py:81`
- **领域**：派工规则库（dispatch_rules / build_dispatch_key / 规则×图key 组合）
- **证据**：真实 build_dispatch_key 实测（/tmp/dispatch_rules_experiment.py Part C，avg_p=1h、k=2 内置）：slack≈1400h 时 primary=-8.9e-306 仍可判别；slack≈1500h vs 1600h → 两者 primary 均为 -0.0 并列；slack≈1500h vs 3000h（相差 62 天）同样并列。下溢阈值 ≈ 745·k·avg_p 小时（avg_p=1h 时约 62 天，avg_p=5h 时约 310 天）。并列后落到 tie-break（changeover→pr_rank→time_left），方向近似 EDD 尚可，但 w/p（WSPT）分量与松弛差异全部失效，且换型偏好压过优先级。触发需数月外的远交期＋小均值工时，量级受限

### 44. 【评审确认】CR/ATC 的 p 量纲混用：外协候选用日历墙钟小时、自制候选用工作小时，ATC 系统性把外协队首批次压到最后

- **严重度**：低
- **位置**：`core/algorithms/greedy/dispatch/sgs_scoring.py:121 + core/algorithm_contracts/dispatch_rules.py:76,81`
- **领域**：派工规则库（dispatch_rules / build_dispatch_key / 规则×图key 组合）
- **证据**：sgs_scoring.py:121 外协 proc_hours=(est_end-est_start) 墙钟秒/3600（含夜间/周末，ext_days=5 → p=120h）；自制走 estimate.total_hours 工作小时（同文件:209）；avg_proc_hours 只取自制样本（sgs.py:158-166 filter source==INTERNAL）。ATC=w/p：同优先级同松弛下，p=120h 外协 vs p=4h 自制指数相差 30 倍，外协队首批次在 SGS 循环里恒最后被派——其后继自制工序进入候选集更晚、订机台槽位更靠后；CR=time_left/p 则反向（外协更早）。三条规则对同一外协候选方向互相矛盾。机制链确定（外协不占机台、派发顺序只通过候选可见性影响后继订槽），端到端量级未实测，如实声明

### 45. 【评审确认】sgs+slack/cr 下批次加急（critical/urgent）对派工顺序几乎零作用：优先级只在第 3 位 tie-break，且排在换型偏好之后

- **严重度**：低
- **位置**：`core/algorithm_contracts/dispatch_rules.py:85-91（w 仅 :81 ATC 分支使用；pr_rank 位于 changeover 之后）`
- **领域**：派工规则库（dispatch_rules / build_dispatch_key / 规则×图key 组合）
- **证据**：真实 build_dispatch_key 实测（/tmp/dispatch_rules_flip2.py，0.5h 网格工时+日粒度交期，4000 随机对）：把候选升级为 critical 能改变胜者的比例 slack=0.1%、cr=0.1%（primary 并列率仅 0.3-0.4% 封顶）、atc=6.3%。即用户选智能派工+默认 slack 规则时，'加急'静默失效——只剩目标函数第二比较键 weighted_tardiness（objective.py:19-25）与死 tie-break batch_order 兜底；graph 特征层也零 priority 引用（optimizer_graph_ready_v2_features.py grep 零命中）。docstring(:47) 已写明 tie-break 次序（换型优先于优先级），属文档化设计，但对用户是无告警的语义缺口；与 item6/7/8（batch_order 作用点错位）和 A06（CR 负松弛反转）分属不同点位，未见既有登记

### 46. 【评审确认】容量口径 due_budget 被 30 天窗口帽静默饱和,日历可用时 >30 天交期的批次失去紧迫度区分

- **严重度**：低
- **位置**：`core/services/scheduler/run/optimizer_graph_ready_v2_capacity.py:12, 93-95; optimizer_graph_ready_v2_features.py:301-303`
- **领域**：GraphReadyV2 特征工程与权重 profile 族(optimizer_graph_ready* / sgs 图评分键)
- **证据**：_residual_capacity_window_end=min(due, start+30d);_uses_calendar_capacity_budget 为真时 due_budget_hours=residual_capacity_window_hours,即所有就绪偏移后 30 天以外到期的批次拿到同一个饱和预算,min_slack/critical_ratio/due_pressure 对它们退化为只按 remaining 排序,且 due_budget_basis 无饱和标记。wall_clock 分支(无日历)不受影响,故 SMTWT 实验未触发;代码级确认。

### 47. 【未经对抗评审】非图模式局搜迭代上限按 20 次解码/秒的写死假设换算，且把 skip-seen/noop 轮计入迭代——实测 10 秒预算只用 0.1 秒、只做 8-13 次真实解码就以 iteration_limit 停机

- **严重度**：低
- **位置**：`core/services/scheduler/run/optimizer_candidate_profile.py:49-53（ITERATIONS_PER_SECOND=20、ITERATION_FLOOR=200）+ :87-88（换算公式）+ optimizer_local_search.py:203-216（HEAD，迭代含未解码轮）+ optimizer_local_search_round.py:220（should_skip_seen 跳轮仍计入 it）`
- **领域**：评估函数与目标体系（evaluation.py / objective.py / candidate_eval 链 / best_metrics 流转）
- **证据**：/tmp/eval_cost_experiment.py（HEAD 快照实测）：wt40×3 实例 batch_order 模式 10s 预算 → evals=8/9/13、wall=0.1s、停止原因 iteration_limit(200=floor)，~95% 迭代轮无真实解码；batch_order 解码实测 3.3ms/次，与 20 次/秒隐含的 50ms/次差 15 倍。sgs 模式 3s 预算 wall=0.5s evals=10（该模式邻域只有派工规则，与已知 item6/7/8 邻域浅史相邻，但『迭代记账把预算废掉』这一维未见立案，已对照 2026-07-20-algo-core-sweep index 与 roadmap）。附注：实验中还目击工作树 A01 修复中间态（reset_current_to_best 签名已改、_restart_after_stall 调用一度不匹配，随后工兵重写至 425 行版），并发修复中，以集成后为准。

### 48. 【未经对抗评审】A14 修复的生产残留缺口：种子契约不携带外协组键，冻结主链路上组缓存依旧无法重建（修复自身已声明为已知缺口）

- **严重度**：低
- **位置**：`core/algorithms/greedy/external_groups.py:11-84（工作区新增 rebuild_external_group_cache_from_seeds，组键只能从 operations 解出）+ core/services/scheduler/run/schedule_input_runtime_support.py:29-30（冻结/执行固定工序被剔出 algo_ops_to_schedule）+ core/services/scheduler/run/freeze_window.py:247-260（种子 dict 无 ext_group_id/ext_merge_mode）`
- **领域**：增量排产（seed 续排 / freeze_window 冻结 / batch_order_override / 部分重排正确性边界）
- **证据**：并发中的 A14 修复在 GreedyScheduler._prepare_run_state 调 rebuild_external_group_cache_from_seeds(seed_results, operations)，但生产路径 operations=algo_ops_to_schedule 已剔除全部被种工序，种子 op_id 在 group_key_by_op_id 中必然查不到→静默 return，A14 原始触发场景（冻结把 merged 组切开→批次凭空多一个组周期）在生产上仍未闭环。修复作者已知晓并用测试锁定该跳过行为（tests/algorithm/test_seed_external_group_cache_rebuild.py:130-133：'生产冻结主链路会把已冻结工序从 operations 里剔除…属服务层种子契约缺组信息的已知缺口'）。并发修复中，以集成后为准；此条是给残留面立账，防止 A14 被登记为'已修'后缺口失踪。

### 49. 【未经对抗评审】冻结/执行种子与本次停机输入无重叠校验：新增维护窗与被钉工序冲突零留痕

- **严重度**：低
- **位置**：`core/algorithms/greedy/scheduler.py:414-424（_freeze_seed_resources 只占用不校验）+ core/services/scheduler/run/freeze_window.py:426-481（种子构建全程不接触 downtime）+ core/services/scheduler/run/schedule_payload_contract.py:347（持久化前校验亦无停机交叉检查）`
- **领域**：增量排产（seed 续排 / freeze_window 冻结 / batch_order_override / 部分重排正确性边界）
- **证据**：全仓 grep 无任何 seed/frozen×downtime 交叉校验代码。用户新增机台维护窗后重排，冻结窗内被钉工序若与新维护窗重叠，会原样写入新版本（带 frozen 标记），运行摘要/警告/algo_stats 全程零留痕；唯一发现渠道是用户另行手跑停机影响报表（core/services/report/downtime_impact.py，事后、非联动）。冻结语义'近期计划不动'可辩护，但按项目'能进业务审计链的要留下可查原因'原则，排产运行时至少应有 warning+计数。种子区间与停机区间都已在手（downtime_map、seed_sr_list），一次 O(S·logD) 扫描即可。

### 50. 【评审确认】性能基准无固化：计时只打印，产物全部 gitignore，无任何跨版本比较

- **严重度**：低
- **位置**：`tests/_scripts_e2e/benchmark_sgs_large_resource_pool.py:117-125(elapsed/estimate_calls 只写进 ignored 报告); .gitignore:112(/evidence/* 全忽略); ratchet 行 runtime_ms 恒 0(tests/_support/optimizer_benchmark_ratchet.py:91)`
- **领域**：基准与实验体系（算法质量回归门禁、基准覆盖面、性能基准固化）
- **证据**：实测大池基准 0.15s 输出 elapsed=0.011s/estimate_calls=601，但无阈值无 baseline；2026-07-19 审计 D13 的 O(V²)→Kahn 修复（58-120x 提速）靠一次性 /tmp 微基准坐实，修完护栏即消失；另一条 sgs_graph.py O(V²) 疑点被降级为'待实测'正是因为没有常驻 perf 量尺。memory 教训'性能要实跑 ground-truth'没有制度化载体。

### 51. 【未经对抗评审】槽位估算只取起点时刻效率代表全程，跨效率变化时段的长工序工时失真

- **严重度**：低
- **位置**：`core/algorithm_runtime/internal_slot.py:232-240 + core/services/scheduler/calendar_engine.py:242-243`
- **领域**：资源模型：auto_assign 机人配对、internal_slot 槽位估算、downtime 时间轴、双资源占用
- **证据**：_estimate_attempt 仅在 earliest 处 calendar.get_efficiency 取一次效率并除全程工时（internal_slot.py:233-234），add_working_hours 按等效平效率推进；若 DayPolicy 效率按日/班变化（calendar_engine.py:242-243 支持 per-operator policy），跨效率变化的长工序结束时刻与逐段积分语义有偏差。因放置复用同一估算故内部自洽，属近似而非不一致；实际数据是否按日变效率证据不足，定 low。

### 52. 【未经对抗评审】机台/人员负载均衡信号在配对评分中被 end_time 完全压制

- **严重度**：低
- **位置**：`core/algorithms/greedy/auto_assign.py:403-405`
- **领域**：资源模型：auto_assign 机人配对、internal_slot 槽位估算、downtime 时间轴、双资源占用
- **证据**：score=(end_time, changeover_penalty, load_penalty, pair_rank, mid, oid)（auto_assign.py:404-405），end_time 不同则 load_penalty 永远不生效；_sort_machine_candidates/_sort_operator_candidates 的 busy_hours 排序只决定探测顺序不改变最终选择（best 比较仍看 score）。多机等价池下负载自然向最早完工机台集中，但是否造成可观测的完工恶化无实测数据，定 low。

### 53. 【评审确认】add_working_hours 对已被 adjust 过的起点重复执行一次完整 adjust(冗余调用,量级百万次)

- **严重度**：低
- **位置**：`core/services/scheduler/calendar_engine.py:306(被 core/algorithm_runtime/internal_slot.py:307 前置 adjust 后再次触发)`
- **领域**：日历引擎与算法交互(calendar_engine × SGS/槽位估算/v2容量)
- **证据**：estimate_internal_slot 先在 :307 调 _adjust_slot_start,随后 _estimate_attempt→add_working_hours 在 engine 内部 :306 又 adjust 同一起点(idempotent 白跑一个循环+约2次 policy 查询)。实测 adjust 总调用 1,078,956 次 ≈ estimate 尝试数 1,046,097 + 外部少量,其中约 104.6 万次是 add_hours 内部的冗余 adjust,占 add_hours 16us 均耗中约 5us

### 54. 【评审确认】跨午夜归属判定在'空窗时段'返回今日 policy 的隐式语义缺乏注释与测试钉住

- **严重度**：低
- **位置**：`core/services/scheduler/calendar_engine.py:227-234`
- **领域**：日历引擎与算法交互(calendar_engine × SGS/槽位估算/v2容量)
- **证据**：_policy_for_datetime 对 dt 落在'今日班次开始前且不在昨日跨午夜窗内'的空隙(如凌晨 03:00)静默返回 p_today,调用方(adjust/add_hours)随后按'不在窗内'处理;该 fallback 语义只在 docstring 隐含,未见针对性测试(tests/calendar_maintenance 仅覆盖跨午夜正例),后续改动易破坏。证据强度:静态阅读,未跑失败用例

### 55. 【评审确认】max_jobs=200 截断后被排除批次仅用交期+优先级粗排追加尾部,大批量池场景预热质量陡降

- **严重度**：低
- **位置**：`core/algorithms/ortools_bottleneck.py:148-154,214-223`
- **领域**：文献对照与算法选型(SGS+优先规则+局搜 / OR-Tools 适用边界)
- **证据**：超出 max_jobs 的批次不参与 CP-SAT 求解,rest.sort 只用 (due, -weight, bid) 三键排序后直接 append。若生产池常年>200 批,预热序列的后半段等价于 EDD 静态排序,与 SGS 的 per-op 评分产生目标错位;该截断事件不打日志(只在 :225-229 记一条总数),降级链不可见。

### 56. 【评审确认】overdue_count 与 tardiness 在 due_exclusive 边界口径割裂:完工恰等于交期次日 0 点时超期数+1 但拖期+0 小时

- **严重度**：低
- **位置**：`core/algorithms/evaluation.py:261-266(_record_tardiness_if_overdue)`
- **领域**：评估函数与目标体系(evaluation.py / objective.py 四目标 / candidate_eval 链 / best_metrics 流转)
- **证据**：finish_time < due_exclusive 才不超期,finish == due_exclusive 时 delta_hours=0,overdue_count+=1 而 tardiness_hours+=0.0。字典序 score 下该批次恶化第 1/2 键(overdue_count/weighted_tardiness 对 weighted 也加 0)却不恶化第 3 键,与 A06(负松弛语义)/A12(目标比较键)挂起的决策直接相关,不宜顺手改。

### 57. 【未经对抗评审】runtime_ms 只在 graph-ready 候选上设置,局搜/GRASP-IG 候选缺失导致 tie-break 跨 origin 不一致

- **严重度**：低
- **位置**：`core/services/scheduler/run/optimizer_local_search_candidate_eval.py:56-72 与 optimizer_grasp_ig_candidates.py:85-105(载荷无 runtime_ms) vs optimizer_candidate_comparison.py:45-57(缺失按 1e9 最劣)`
- **领域**：评估函数与目标体系(evaluation.py / objective.py 四目标 / candidate_eval 链 / best_metrics 流转)
- **证据**：graph-ready 候选在 optimizer_graph_ready_candidates.py:66-107 按合同计时;另两条路径候选 runtime_ms 缺省→同分 tie 时非图候选被系统性视为'未知/最慢',runtime 维度实际只在图候选内部生效。candidate_runtime_ms 注释明说不能用 or 0 折 0,说明该语义被刻意设计过,但三条评估路径只有一条遵守。

---

## 附录：被评审否决的问题（1 条，留档防重复提报）

- **last_end_by_machine 是只写状态:core 内无读取方**
  - 位置：`core/algorithm_runtime/runtime_state.py:26-58;core/algorithm_runtime/internal_slot.py:144-150`
  - 否决理由：事实错误。runtime_state.py:41 `prev_end = last_end_by_machine.get(machine_id)` 就是读取方,且 :47/:56 的写入以该读取为守卫——这正是 A16 修复的本体:last_end 是决定 last_op_type 是否允许覆盖的守卫键,删掉或忽视它,A16 防的'gap 回填把 (end,type) 快照改成自相矛盾状态'即刻回归。报告 grep 时把 :41 这处读取漏掉(可能只当'函数透传'扫过),把 A16 刚建立的 load-bearing 状态误判为只写死状态。'误导性状态'结论不成立。

## 处置状态

- 本清单 57 条均**未修、未登账本**，等用户拍板（与 D/B/A 批同纪律）。
- 与 A 批已修复项的关系：A14 残留缺口（清单 #11/#48 两条）是 A 批修复时工兵自己声明的已知缺口；A03 修复后的跨调用复用问题（清单 #25/#42）是修复后新暴露的性能层。
- 高严重度三条主线：SGS 评分性能墙（#3/#7/#12）、基准棘轮形同虚设（#4/#5/#9/#10）、图模式生产路径预算饿死+搜索短路（#1/#2/#6/#8）。