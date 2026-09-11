# 排产算法深度研究综合报告（2026-07-20，wf_db8f9dd8-b33）

## 方法与覆盖

10 领域研究员深读+实验（SGS 主循环、GraphReadyV2 特征、局搜/GRASP-IG、评估函数、派工规则、资源模型、增量排产、端到端性能画像、基准体系、日历引擎、文献对照），每领域配一个可行性对抗评审员。研究员 10/10 交卷（perf-architecture 经两次断流后补跑成功），评审员 9/10 交卷（resource-model 评审断流，其领域报告已交但未经对抗评审，问题/机会标注『未评审』）。综合报告尾段断流空产出，由主会话按评审定案整合。

## 一、算法体系现状速写（整合各领域 how_it_works）

### dispatch-rules
规则库仅 3 条枚举 SLACK/CR/ATC（core/algorithm_contracts/dispatch_rules.py:19-21）。build_dispatch_key(:41-95) 产出"越小越优"元组：(primary, changeover, pr_rank, time_left, batch_order, seq, op_id)；ATC 内置 k=2.0(:80)、w=优先级权重 1/2/3(priority_constants.py:12)、ATC 对负松弛有 max(slack,0) 钳位(:81) 而 CR 没有（即 A06，等决策）。avg_proc_hours 是全局静态自制工时均值（sgs.py:147-168）；外协候选 p 用日历墙钟小时（sgs_scoring.py:121）。规则只在 sgs 派工路径生效（batch_order.py 零引用）；出厂默认 dispatch_mode=batch_order、rule=slack（config_field_spec.py:168,190）。评分链：_dispatch_key 前缀超窗罚分（sgs_scoring.py:71）；图模式下 graph_key 插在罚分与规则 primary 之间（sgs_scoring.py:74-75、sgs.py:344-350）——v1 profile 图 key=(-bonus,rank) 在 bonus 平局时规则接管；v2 公式 key 尾带 per-op jitter（optimizer_graph_ready_candidates.py:289-310），实际把规则 primary 完全挡死。生产默认 graph=on 时 optimizer 强制全部图候选走 sgs（schedule_optimizer.py:251-253），bas

### graph-v2
生产默认 improve+graph_on 走 PROFILE_GRAPH_READY(optimizer_candidate_profile.py:300-301),GRASP/IG 整相跳过(optimizer_grasp_ig_candidates.py:427-429)。图相按固定顺序枚举 19 个 profile(非任务描述的 5 个):9 个 v1 原始加权和 + 10 个 v2 目标感知公式(optimizer_graph_ready_profiles.py:180-194);每个 profile 生成一份静态 graph_priority_key_by_op_id,整趟 SGS 完整解码一次再与 incumbent 比分(optimizer_graph_ready.py:256-301),与后续局搜共享同一个默认 5 秒 deadline(schedule_optimizer.py:279;schedule_config_runtime_fields.py:92)。v1 键=(-raw 加权和, critical_path_rank);v2 先 enrich 出 due/remaining/容量特征(optimizer_graph_ready_v2_features.py:57-145),做 rank01 百分位归一(严格保序,故对字典序公式的选择结果是 no-op),再按 formula_slug 组装字典序 tuple(optimizer_graph_ready_candidates.py:269-310)。SGS 中 graph key 插在 score_penalty 之后、动态派工键(slack/ATC/CR, dispatch_rules.py:75-95)之前(sgs_scoring.py:74-75),静态 profile 排序全面压制动态估

### objective-eval
四目标是字典序键链(core/models/objective.py:18-46)，score=(failed_ops,)+objective_score(core/algorithms/evaluation.py:345)，五个评估点各自拼装；候选比较用元组严格<(optimizer_candidate_comparison.py:87-105)，平手落 fingerprint_changed→runtime_ms→origin(runtime 语义缺陷已立案)。每候选=整趟 SGS 重解码+compute_metrics+输出指纹；实测 wt40：解码 51ms/次占 98%+，compute_metrics 0.26ms、指纹 0.34ms 均<1%——评估侧微优化无意义，解码次数是唯一杠杆。去重全是事后的(output_fingerprint same_as_seen 付完解码才知道)；局搜另有 move 级 seen_hashes 但 restart 重置(实测重复评估率 0%，非热点)。生产默认(graph on+improve)：multi_start 12 次解码→图组合 19 个 profile 各 1 次解码；局搜(optimizer_local_search.py:179-181)与 GRASP-IG(optimizer_grasp_ig_candidates.py:427-429)均跳过——候选集固定、与默认 5s 预算(config_field_spec.py:284)脱钩，预算只作截断。best_metrics 随获胜候选 dict 流转到 OptimizationOutcome→summary(A18 已立案)。注：optimizer_local_search*/optimizer_graph_ready* 正被 A 批工兵并发修改，本文行号以

### sgs-core
SGS 主循环（core/algorithms/greedy/dispatch/sgs.py:201-249）每轮三步：收集就绪候选（非图模式=每批次首个未排工序；图模式=Kahn 前沿，sgs_graph.py:313-337）→ 全量评分所有候选（sgs.py:252-291）→ min() 取最优派工。评分 key=(窗口罚,)+图 key+规则 key（slack/cr/atc，dispatch_rules.py:41-95），tie-break 硬编码固定序：换型>优先级>剩余时间>批序>seq>op_id，op_id 收尾保证 key 唯一、min 与候选序无关。内部候选评分链：meta 逐次重解析（#53 已登记）→ 资源解析（固定资源直通；auto-assign 走全池机×人探针 auto_assign.py:247-305，每对各跑一次 estimate_internal_slot）→ 再对探针选中对重跑一次估算（sgs_scoring.py:189-201）。放置复用 batch_order 的 _schedule_op（batch_order.py:162-202），winner 再次全池 auto-assign+终算。batch_order 旧路径按全局序线性放置、不评分；两路失败语义为已测试锁定的有意不对称：SGS 缺资源整趟 ValidationError fail-loud（tests/algorithm/test_dispatch_blocking_consistency.py、tests/schedule/route_view/test_scheduler_missing_resource_message.py），batch_order 按批失败留痕继续跑（internal_operation.py:116-119）。生产默认 improv

### incremental
增量排产=“种子钉住+其余全量重排”。服务层 collect_schedule_run_input 只装载所选批次的工序，种子来自两路：(1) freeze_window 按批取 [start,start+days) 与上一版重叠的行，要求 seq 前缀完整才整批冻结（freeze_window.py:363-405），缺行即降级（strict 直接抛）；(2) 执行事实 PROCESSING/PAUSED/COMPLETED 构造执行种子（guardrails，PROCESSING 末端=实际开工+计划时长），两路按 op_id 合并、冲突即中止（schedule_input_runtime_support.py:326-351）。frozen∪execution_fixed 从 algo_ops_to_schedule 剔除；图模式把 frozen∪seed 全部作 fixed_op_ids（schedule_graph_dispatch_context.py:236-252）。算法层 GreedyScheduler 注入种子时重建：机/人时间轴占用、busy_hours、last_end/last_op_type（op_type 空则跳过）、batch_progress（每批 max(end) 标量）、外协组缓存（A14 修复并发落地中）。优化器所有阶段（多起点/GRASP-IG/图 profile/局搜）每个候选都携带同一 seed_sr_list 完整重跑 schedule()；图模式下局搜与 GRASP-IG 整体跳过（optimizer_local_search.py:179-181、optimizer_grasp_ig_candidates.py:427-428）。实测（/tmp/seed_incremental_bench.py，SGS）：全量 500/1

### benchmark-tooling
基准体系分三层。轻层：optimizer_proof_harness 用穷举精确 oracle（节点上限 5 万）证明 tiny 案例最优，但 build_default_tiny_cases 只有 1 个 2 工序单机案例（core/services/scheduler/run/optimizer_proof_cases.py:43）；轻层 ratchet 快照=tiny proof+4 工序 graph-ready 真实 SGS 案例+瓶颈指标案例，与 tracked baseline（.codestable/roadmap/scheduler-global-optimizer/benchmark-ratchet-baseline.json）比对，由 tests/algorithm/test_optimizer_benchmark_ratchet_gate.py 进门禁。中层：benchmark_optimizer_medium_gate 跑三族——SMTWT 250 实例（tests/_data/optimizer_benchmarks/smtwt/wt40+wt50，对 Moore-Hodgson 精确最优比 overdue_count，实测 10 workers 41s，sgs 局搜 gap 16.16→6.82）、FJSP mk01 折叠冒烟（1.3s）、SGS 大资源池有效性（0.15s）——但三者退出码都只防 crash/无效解，不防质量倒退。长层：compare_algorithms 7 算法档对比、long_run 多 seed，产物全写进 gitignore 的 evidence 目录。两个 tracked baseline 均为 dirty_worktree=true（2026-06-30），ratchet 比对因此永久红。RCPSP j30 数据已

### resource-model
机人配对（core/algorithms/greedy/auto_assign.py）：op 未固定机/人时，`_resolve_machine_candidates` 按 op_type→机台池取候选，`_choose_best_pair`（:255-321）对全部 机×人 组合逐一调 `estimate_internal_slot` 打分，score=(end_time, changeover, load_penalty, pair_rank, mid, oid) 取最小，best[0] 作为后续 pair 的 abort_after 剪枝。槽位估算（core/algorithm_runtime/internal_slot.py:279-350）：起点效率除总工时→calendar.add_working_hours 算 end→避让循环用 SegmentOverlapIndex（core/algorithm_runtime/downtime.py:23-83，起点升序+前缀最大end，bisect O(log n)，但索引每次 estimate 调用新建，0-hop 首扫恒 O(T)）。占用（downtime.py:11-20）bisect.insort 维持有序，机/人双时间轴同步写入（internal_operation.py:87-88）。SGS 主循环（sgs.py:199-247）每轮对每批首未排 op 全量重评分；auto_assign 路径每候选 = P 次 pair 估算 + 选中 pair 再估 1 次（sgs_scoring.py:214-226），放置时 `_resolve_internal_resources` 在状态未变下又全量重探 + 重估（internal_operation.py:123-199）。实测（/tmp/bench_slot.

### literature-fit
生产默认(improve+graph_analysis_mode=on)流水线：optimize_schedule(schedule_optimizer.py:211) 依次跑 ①ortools warmstart(默认关,optimizer_config.py:144)、②multi_start(4策略×sgs×3规则=12次全解码,schedule_optimizer_steps.py:373)、③GraphReadyV2 组合=19个固定顺序 profile(9个v1权重+10个v2目标感知公式,optimizer_graph_ready_profiles.py:180-194)逐个全解码取优、④local_search 与 grasp_ig 在图模式下整段跳过(optimizer_local_search.py:298-300, optimizer_grasp_ig_candidates.py:427-429)。每个候选=一次完整 SGS 解码：_run_sgs_loop(sgs.py:180)每步收集全部 ready 候选并全量重评分(估算槽位+派工键)，图模式下 graph_priority_key 插在派工键主项之前(sgs_scoring.py:77)。预算默认5秒(config_field_spec.py:284)，只在候选间检查 deadline，单次解码不可中断。实测(合成算例、连续日历、固定机/人)：解码耗时 100/250/500/1000/2000 工序=24ms/165ms/462ms/3.3s/14.5s(≈N^2.3)，评分阶段占解码96%。注意：sgs.py/sgs_graph.py/optimizer_* 正被 A 批修复工兵并发修改，本报告行号以研究时点为准，集成后需复核。

### calendar-interplay
CalendarEngine（core/services/scheduler/calendar_engine.py）按"日期键"推导 DayPolicy：每天单一班窗（shift_start+shift_hours 或 shift_end 推导，支持跨午夜归属 :211-234），normal/urgent 门控，效率必须>0；(operator_id,date) 级 DayPolicy 缓存已存在（:87-88，实测命中率 99.99%）。算法消费四个 API：adjust_to_working_time/add_working_hours 均为逐日 while 走窗（:255-276/:310-344），get_efficiency 单点取值，add_calendar_days 纯自然日（外协用，sgs_scoring.py:276/283）。机台无日历维度——machine_id 参数全被忽略且无任何调用方传入（机台停机走 downtime 时间轴，by-design）。调用密度由 SGS 评分×auto-assign 撑爆：每轮每候选跑一次 auto-assign 探测（机×人对逐一 estimate_internal_slot，auto_assign.py:281-313），每次 estimate 平均 5.4 次避让 attempt，每 attempt 1 次 get_efficiency+add_working_hours（internal_slot.py:231-239,306,321,339）。实测（160 工序、6机×8人池、sgs+auto 单趟）：add_working_hours 40.9 万次、adjust 113 万次、_policy_for_datetime 257 万次，仅 256 个去重 (op,date) 键；入参级重复率 adjust

### local-search
编排顺序(schedule_optimizer.py:347-411):先跑 run_heuristic_candidate_phases(图 profile 相位 → GRASP-IG 相位),再跑 run_local_search。生产路径(graph_ready_context 非空,GraphReadyV2 默认 on)下:图相位对至多 9 个固定权重 profile 各做一次完整 SGS 解码取最优(optimizer_graph_ready.py:_run_weight_profiles 225-301,单趟、无迭代);GRASP-IG 相位与局部搜索相位被无条件跳过(optimizer_grasp_ig_candidates.py:427-429、optimizer_local_search.py:298-300,跳过原因 "graph_ready_uses_graph_candidate_phase")。即生产路径没有任何迭代式改进搜索。遗留 batch_order 路径下:局部搜索是 VNS 循环(optimizer_local_search.py:322-410),每轮 round-robin 选一个邻域产生**唯一一个**候选(optimizer_neighborhood_registry.choose_neighborhood_move),接受准则默认 improve_only(纯爬山),no_improve≥restart_after(derive_iteration_limits,it_limit/8,钳 [50,800])后做 restart shake(随机交换/重插 3-8 次,optimizer_local_search.py:32-46)并用一次真实解码对齐 current。邻域算子集(optimizer_neighborhood_mo

### perf-architecture
排产主链路:scheduler.py:70 schedule → sgs.py:49 dispatch_sgs → _run_sgs_loop(sgs.py:180) 每轮从就绪队列取候选(每批一个头工序),逐候选调 _score_candidate(sgs.py:292)→ sgs_scoring._score_internal_candidate → auto_assign._choose_best_pair(auto_assign.py:255) 对 machine_candidates×operator_candidates 全配对,每对调 estimate_internal_slot(internal_slot.py:279) 做日历工时累加+时间轴避让 hop;选中最优对后 commit,occupy_resource(downtime.py:11) 用 bisect.insort 把段插进机/人时间轴,进入下一轮。关键复杂度:轮数=工序数 N,每轮候选数≈就绪批数 B,每候选评估配对数=M(机)×O(人)。estimate 结果**跨轮零复用**,总成本 O(N×B×M×O)。实测(darwin arm64 .venv,2026-07-20 快照,注意 sgs/internal_slot/auto_assign 等文件 A 批修复并发中,数字以集成后为准):200 ops/40 批/20机×4人=7.5s(3990 万函数调用,estimate_internal_slot 35.5 万次≈1770 次/op);400 ops=17.6s(estimate 70 万次);1200 ops/120 批基线>300s 跑不完。热点:cumtime 95% 在 _choose_best_pair 内,estimate_internal_slot cumtime 15.

## 二、新发现问题清单（评审 confirmed，按严重度排）

1. [problem] ATC 的 exp 在远交期候选上下溢为 -0.0，远松弛候选间 ATC/WSPT 判别力全部丢失、集体并列（派工规则库（dispatch_rules / build_dispatch_key / 规则×图key 组合））
   评审：亲验实跑 /tmp/dispatch_rules_experiment.py Part C（调仓库真实 build_dispatch_key）逐数复现：slack≈1400h primary=-8.932e-306 可判别；1500 vs 1600h 均为 -0.0 并列；1500 vs 3000h（差 62 天）同样并列。代码亲读：core/algorithm_contracts/dispatch_rules.py:81 exp(-max(slack,0)/(k·avg_p)) 无下溢防护，:59-66 的 _safe_positive/isfinite 只守输入 p/avg_p 不守 exp 结果，:57-58 注释声称防 -0.0 传播但实际防不到此处。下溢阈值 745·k·avg_p 数学成立（exp 双精度下溢点 ≈-745.13）。并列后落 tie-break（:89-90 c

2. [problem] CR/ATC 的 p 量纲混用：外协候选用日历墙钟小时、自制候选用工作小时，ATC 系统性把外协队首批次压到最后（派工规则库（dispatch_rules / build_dispatch_key / 规则×图key 组合））
   评审：三处代码事实亲验属实（行号因 A 批并发修复略有漂移，报告已预声明）：外协 p=墙钟小时——sgs_scoring.py:124 proc_hours=(est_end-est_start)/3600，窗口来自 :276/:283 ctx.calendar.add_calendar_days（含夜间/周末）；自制 p=工作小时——:234 estimate.total_hours；avg_proc_hours 仅取自制样本——sgs.py:157 filter source==INTERNAL。外协/自制候选确在同一池比 key（sgs.py:310-339 同一 score() 分派、_pick_best_candidate 取 min）。方向推导正确：ATC=w/p 大 p 压后、CR=time_left/p 大 p 提前、slack 无视 p，三规则互相矛盾成立。'恒最后'仅在其自设

3. [problem] sgs+slack/cr 下批次加急（critical/urgent）对派工顺序几乎零作用：优先级只在第 3 位 tie-break，且排在换型偏好之后（派工规则库（dispatch_rules / build_dispatch_key / 规则×图key 组合））
   评审：结构性事实亲读属实：w 仅在 ATC 分支使用（dispatch_rules.py:51 定义、:81 唯一消费点），pr_rank 位于 changeover 之后第 3 位（:89-90），docstring :47 确已文档化该次序。实验亲跑双份复现：连续工时版 flip 率 slack=0.0%/cr=0.0%/atc=5.9%（/tmp/dispatch_rules_experiment.py Part D），0.5h 网格+日粒度交期版 slack=0.1%/cr=0.1%/atc=6.3%、primary 并列率 0.3-0.4%（/tmp/dispatch_rules_flip2.py）——与报告数字一致。旁证亲核：optimizer_graph_ready_v2_features.py grep priority 零命中；min_overdue 前两键 overdue_c

4. [opportunity] ATC primary 改 log 形式：-(ln w - ln p - max(slack,0)/(k·avg_p))，消灭 exp 下溢并列（派工规则库（dispatch_rules / build_dispatch_key / 规则×图key 组合））
   评审：数学亲验：primary_new=-ln(atc)，-ln 与 -atc 同为 atc 的严格减函数，非下溢区严格保序成立；log 参数安全性亲读代码确认——p>0、avg_p>0 由 dispatch_rules.py:59-73 _safe_positive+回退链保证，w∈{1,2,3}（priority_constants.py:12），math.log 无定义域风险，py3.8/Win7 无兼容问题。测试风险声明亲核属实：全仓测试 grep 无对 primary 绝对值的 golden 断言，仅 tests/resource_dispatch/test_dispatch_rules_nonfinite_proc_hours_safe.py:47 断言 isfinite（log 形式对合法输入仍有限，兼容）、其余为相对序断言。与 A06 同文件（A06 定案在 :75-77 CR 

5. [problem] 唯一自动化质量回归门禁被脏 baseline 永久锁红，且门禁测试把脏状态锁死为合同（基准与实验体系（算法质量回归门禁、基准覆盖面、性能基准固化））
   评审：亲验全链：baseline JSON dirty_worktree=true(benchmark-ratchet-baseline.json:164, 2026-06-30)；比对代码 tests/_support/optimizer_benchmark_ratchet.py:146-152 对 dirty baseline 必加 failure；实跑 .venv/bin/python tests/_scripts_e2e/benchmark_optimizer_ratchet.py --check-baseline → status=failed, failures=[dirty_actual_worktree, dirty_baseline_worktree]，与报告一致。锁死测试 test_optimizer_benchmark_ratchet_gate.py:41-50 断言比对必

6. [problem] 中门禁三族基准全部只防 crash 不防质量倒退，'改进不倒退'在中等规模上无锁（基准与实验体系（算法质量回归门禁、基准覆盖面、性能基准固化））
   评审：逐文件核实：benchmark_smtwt_localsearch.py:165 仅 'return 1 if had_failed_samples else 0'，gap 只 print(:148-163)；benchmark_fjsp.py:66-69 仅 valid 计数判退出码；benchmark_sgs_large_resource_pool.py:139-151 仅 scheduled_ops>0/failed_ops=0/result_count 三项有效性。medium_gate 的 coverage 字段自述 'non-degradation shape'(benchmark_optimizer_medium_gate.py:56)确与实际不符。本人实跑全套 SMTWT 250 实例(10 workers,~40s)：sgs gap 16.16→6.82、improved

7. [problem] ratchet CLI --update-baseline 无脏工作区拒写防护，与 compare_algorithms 不对称（基准与实验体系（算法质量回归门禁、基准覆盖面、性能基准固化））
   评审：benchmark_optimizer_ratchet.py:34-40 parser 仅 tier/baseline/update-baseline/check-baseline 四项、:52-54 直接 write_baseline 无任何检查；对照 benchmark_optimizer_compare_algorithms.py:43-47 有 --allow-dirty-proof、:65-73 dirty 时拒写返 1。write_baseline 本体(optimizer_benchmark_ratchet.py:68-70)也无防护。当前脏 baseline 由该通道写出成立：该文件唯一写入方即此 CLI，git 历史(898f0214/2fae3625)提交的就是 dirty_worktree=true 快照。

8. [problem] 质量基准族对 4 个业务目标只覆盖 min_overdue，其余 3 目标零基准且已有可测退化（基准与实验体系（算法质量回归门禁、基准覆盖面、性能基准固化））
   评审：core/models/objective.py:18-46 四目标属实；grep tests/_scripts_e2e+_support：min_tardiness/min_changeover/min_weighted_tardiness 只出现在 run_synthetic_case.py:621、run_browser_extreme_stress_case.py:503 等 e2e 冒烟参数里，无任何对最优参照的质量基准；loaders 注释(optimizer_benchmark_loaders.py:8-24)明确 weighted 最优值不用于评分。研究员的 changeover 退化实验类独立复现成功：/tmp 自构 6 工序(3A/3B 交错交期单机)min_changeover 案例，oracle 33ms proven_optimal 换型 1 次，greedy 实

9. [problem] 性能基准无固化：计时只打印，产物全部 gitignore，无任何跨版本比较（基准与实验体系（算法质量回归门禁、基准覆盖面、性能基准固化））
   评审：benchmark_sgs_large_resource_pool.py:116-125 elapsed/estimate_calls 进结果 dict，:281-283 写进报告，报告路径 :289-296 落 evidence/QualityGate/long_gate/，.gitignore '/evidence/*' 全忽略；ratchet 行 runtime_ms 硬编码 0(optimizer_benchmark_ratchet.py:91)、time_budget_seconds 0(:84)。审计佐证核实：2026-07-19-full-defect-sweep/index.md:228 D13 '微基准坐实(V=2000 55ms/V=5000 345ms)后改 Kahn，修后 58-120x 提速'为一次性 /tmp 实测；:191 另一条 sgs_graph O(V²

10. [opportunity] 解锁 ratchet 门禁：干净工作区重生成两个 tracked baseline + 重写锁死测试 + ratchet CLI 补脏拒写/--allow-dirty-proof 对称语义（基准与实验体系（算法质量回归门禁、基准覆盖面、性能基准固化））
   评审：机制完备性亲验：compare_to_baseline 的不劣化比较/候选计数/proof binding 全已实现(optimizer_benchmark_ratchet.py:43-59,107-238)；'亚秒级'实测成立(/usr/bin/time 整个 CLI 含 python 启动 real 0.20s)；两个 tracked baseline 均 dirty_worktree=true 核实(ratchet baseline:164、comparison baseline:27)；同文件 test_benchmark_ratchet_blocks_dirty_*(:53-72)确有可套用的合成 fixture 写法；roadmap item21 状态 in_progress 核实(roadmap.md:1058)。effort=S、risk(等 A 批集成+干净工作区)诚实，

11. [opportunity] 中门禁质量 ratchet：SMTWT 250 实例 gap 阈值化 + 确定性迭代预算替代 1s wall-clock（基准与实验体系（算法质量回归门禁、基准覆盖面、性能基准固化））
   评审：数字稳定性亲验：本人独立重跑全套(10 workers,~40s)得 sgs 16.16→6.82、improved 209/250(83.6%)、batch_order 15.40→10.78，与研究员报告逐位一致——同机跨 run 近乎确定，阈值(≤7.5/≥195)留有余量合理。预算公式核实：derive_iteration_limits(optimizer_candidate_profile.py:87)常量 FLOOR=200/CEILING=5000/PER_SECOND=20(:49-53)，budget=1 → max(200,min(5000,20))=200 属实；TIME_BUDGET=1 wall deadline 在 benchmark_smtwt_localsearch.py:50,:80。--tier choices 仅 ('light',)(benchmar

12. [opportunity] 扩 tiny oracle 案例族：从 1 个 2 工序案例扩到 ~10 个 ≤9 工序案例，覆盖 DAG/双机/三个未测目标/优先级混合（基准与实验体系（算法质量回归门禁、基准覆盖面、性能基准固化））
   评审：关键前提全部亲验：build_default_tiny_cases 确仅 1 个 2 工序单机案例(optimizer_proof_cases.py:43-77)；run_optimizer_proof_harness 支持传自定义 cases(optimizer_proof_harness.py:43-48)；oracle 能力实测——6 工序 min_changeover 案例 build_tiny_case_reference 全程 33-37ms 即 proven_optimal，且立刻暴露 greedy 3 vs 最优 1(gap 200%)的目标盲区，印证'新案例必然暴露非最优、必须用 ratchet 语义而非 require_optimal'这条 risk 是诚实且必要的(当前 ratchet 快照在 optimizer_benchmark_ratchet.py:26 写死 

13. [opportunity] 性能基准固化：大池基准扩成规模系列，estimate_calls 等确定性计数严格 ratchet + 耗时宽容差告警（基准与实验体系（算法质量回归门禁、基准覆盖面、性能基准固化））
   评审：基础设施核实：estimate_calls 计数机制已实现(benchmark_sgs_large_resource_pool.py:92-106 mock 包装四处 import 点)；比较机制可复用(optimizer_benchmark_ratchet.py 的 _int_metric_* 族)；现有案例确实只排 1 个工序、无法压出复杂度信号。D13/sgs_graph 两次教训引用核实(audits/2026-07-19-full-defect-sweep/index.md:228,:191)。一处口径修正写入采纳前提：计数通道对 D13 这类'函数内字典全扫'型 O(V²) 回归是盲的——那段环检测不调 estimate_internal_slot，计数零变化；能抓住 58-120x 量级回归的其实是宽容差 wall-time 告警通道(固定开发机上 1.5-2x 容差足以红 

14. [problem] IG 重建是随机重插而非贪婪重插,且 GRASP/IG 无迭代循环(名实不符)（局部搜索 / GRASP-IG(optimizer_local_search*、optimizer_grasp_ig_*、optimizer_neighborhood_*、optimizer_vns、optimizer_acceptance、optimizer_graph_ready 候选相位)）
   评审：亲验属实。optimizer_grasp_ig_specs.py:41-53 _ig_order 删除后 `insert_at = rnd.randrange(len(order)+1)` 确为随机插回,无 best-insertion;_grasp_order(31-38)是对 base_order 前 rcl_size=3 个位置随机 pop 的位置型洗牌,不评估贪婪函数值;build_grasp_ig_candidate_specs 每个 restart_index 只产一个 spec、无 accept-and-iterate 循环。名实不符成立。/tmp 实验(-20% 总延误、12/12 胜)无法复核原始脚本,但方向与 Ruiz & Stützle 2007 一致,且报告自己诚实标注了'等解码次数预算下贪婪反而更贵'这一反直觉点,证据链完整。注意该相位当前在生产路径被跳过,实际危

15. [problem] 批次序邻域步长被钉死在 2 个槽位,无 swap/任意位置 insert/块交换（局部搜索 / GRASP-IG(optimizer_local_search*、optimizer_grasp_ig_*、optimizer_neighborhood_*、optimizer_vns、optimizer_acceptance、optimizer_graph_ready 候选相位)）
   评审：亲验属实。optimizer_neighborhood_moves.py:338-340 `out.insert(max(index - 2, 0), item)` 步长钉死为 2,且 grep 确认 critical_chain/tardy_window/bottleneck_machine/time_window 四邻域(119/137/154/228 行)全部共用 _pull_batch_earlier;算子集中确无 swap/任意位置 insert。报告自己定位为'已知邻域浅根因的量化补强而非全新发现',定性诚实,不构成重复报发现。severity=med 合理。

16. [opportunity] 图路径补一层围绕 incumbent 的迭代搜索(profile 权重扰动重启)（局部搜索 / GRASP-IG(optimizer_local_search*、optimizer_grasp_ig_*、optimizer_neighborhood_*、optimizer_vns、optimizer_acceptance、optimizer_graph_ready 候选相位)）
   评审：思路成立且是 problems#1 的对症最小侵入解:权重空间 ILS 不动 SGS 解码器,jitter_seed 确定性机制已存在可复用。effort=M 与'必须走 GraphReadyWeightProfile 校验、等 A 批集成后动手'的风险声明诚实。两处保留:(1) '文献依据(talon 权重扰动之于 ATC 调参)'写得含糊,未给具体文献,支撑偏弱;(2) expected_gain 拿遗留路径 gap 16→6.8 类比图路径是跨路径外推,报告自己标了'需实测',可接受但验收时必须落 250 实例基准数据才算数。无新依赖、不违反 Win7/py3.8。

17. [opportunity] IG 改贪婪重插 + 真迭代主循环(与机会#2 配套)（局部搜索 / GRASP-IG(optimizer_local_search*、optimizer_grasp_ig_*、optimizer_neighborhood_*、optimizer_vns、optimizer_acceptance、optimizer_graph_ready 候选相位)）
   评审：与 problems#2 证据链一致,Ruiz & Stützle 2007 文献引用真实恰当(IG for PFSP 确实依赖贪婪重插+增量评估)。风险声明诚实:'必须落在 #2 之后或用 destruction_size+候选位封顶''生产路径被跳过、需先解 problems#1'两点都是真约束,无夸大。expected_gain 的 -20% 明确标注是合成基准、真实基准需实测,符合证据纪律。无依赖/兼容性冲突。

18. [opportunity] 邻域扩容 + best-of-neighborhood:swap、任意位置 insert、tardy 批次对交换（局部搜索 / GRASP-IG(optimizer_local_search*、optimizer_grasp_ig_*、optimizer_neighborhood_*、optimizer_vns、optimizer_acceptance、optimizer_graph_ready 候选相位)）
   评审：与 problems#3 直接对应,insert-to-best + swap 是 PFSP 局搜标配,文献方向正确。风险声明诚实:best-of-neighborhood 翻倍解码次数需配 #2、VnsState 语义要扩展、sgs.py 并发冲突已标注。'把达最优率从 ~18% 再抬一截'有(需实测)限定,可接受。唯一小瑕疵:'item9-13 修复史部分收益来自邻域修复'与 memory 记录一致但属历史类比,非新证据——不影响结论。effort=M 合理。

19. [opportunity] 邻域自适应选择:按近期成功率加权替代 round-robin（局部搜索 / GRASP-IG(optimizer_local_search*、optimizer_grasp_ig_*、optimizer_neighborhood_*、optimizer_vns、optimizer_acceptance、optimizer_graph_ready 候选相位)）
   评审：成立。亲验 optimizer_local_search.py 走 round-robin choose_neighborhood_move,VnsState 已有 noop/fallback/improved 计数可作 AOS 原料;确定性有 rng_factory 播种 rnd 保障,报告也要求纳入 search_report 留痕,符合审计链纪律。'AOS 相对均匀选择 5-15%'是文献常见区间但未给具体出处,属弱引用,可接受为方向性依据。effort=S 诚实,无约束冲突。建议排在 #7 之后做(接受准则变化会改变各邻域成功率口径,先定口径再自适应)。

20. [opportunity] 接受准则默认从 improve_only 换 record_to_record/threshold,或随进度自适应（局部搜索 / GRASP-IG(optimizer_local_search*、optimizer_grasp_ig_*、optimizer_neighborhood_*、optimizer_vns、optimizer_acceptance、optimizer_graph_ready 候选相位)）
   评审：亲验属实:optimizer_candidate_profile.py:288 默认 acceptance='improve_only',optimizer_acceptance.py:11-16 四种准则均已在 ALLOWED_ACCEPTANCES 白名单且经校验,即代码已备好只是默认没切。报告正确识别了两个前置:(1) A13(接受准则量纲)正在等语义决策,threshold 量纲与 score 元组分量匹配问题必须先裁决;(2) restart 后 current 已被真实解码对齐,接受差解的三元组一致性前提具备。effort=S(在 A13 落地后)合理。无夸大,依赖关系标注清楚,是与现有决策项衔接最干净的一条。

21. [problem] A14 外部组缓存重建在真实调用边界失效:operations 参数不含被冻结工序（增量排产:seed 续排、freeze_window 冻结、batch_order_override）
   评审：代码核实成立。external_groups.py:50-61 _merged_group_key_by_op_id 只遍历传入的 operations 建组键;scheduler.py:385-391 把 schedule() 收到的 operations 直接传给 rebuild_external_group_cache_from_seeds;而全部生产调用方(schedule_optimizer.py:152、optimizer_local_search_candidate_eval.py:39、optimizer_graph_ready_candidates.py:76、optimizer_grasp_ig_candidates.py:68、schedule_optimizer_steps.py:68/106/337)传的都是 schedule_input_runtime_supp

22. [problem] 非前缀 seed(乱序报工)下未种前道被静默排到已固定后道之后,时间序违反工艺序且零留痕（增量排产:seed 续排、freeze_window 冻结、batch_order_override）
   评审：机理核实成立:run_state.py:82-90 advance_batch 对同批 seed 取 max(end),prev_end(:79-80)直接返回该推进值作为未种工序起点;batch_order.py 全文 grep 无 fixed/seed/conflict 相关校验;graph_fixed_successor_order_conflict 的留痕点(run_state.py:152)只在失败阻塞传播分支触发,成功但倒置分支双模式静默。未亲跑其实验(/tmp/seed_inversion.py 非仓内产物),但机制链条每一环均在代码中坐实,实验结论与代码行为一致,且属'不静默'原则真实缺口。med 合理(非前缀 seed 即乱序报工场景,非常态但合法输入)。

23. [problem] seed 占用与机台停机(保养)零校验:冻结工序撞上新增 downtime 双占用静默（增量排产:seed 续排、freeze_window 冻结、batch_order_override）
   评审：核实成立。scheduler.py:366-378 _prepare_run_state 签名确无 machine_downtimes;:425-435 _freeze_seed_resources 只做 occupy_resource 不比对停机段;downtime 在 schedule_input_runtime_support.py:74-111 _load_runtime_resource_inputs 独立加载,两条路径无交汇。'上一版冻结工序 + 新增保养计划→时间轴双占用零告警'场景成立,违反不静默原则。med 合理:后果是计划与保养冲突要人工发现,不丢数据但误导执行。注意 scheduler.py 本身在并发修复中,修法(比对放 _prepare_run_state 还是更外层)需与集成后结构对齐。

24. [problem] 机会-seed 边界机台末态(换型链)从上一版窗口前尾部初始化（增量排产:seed 续排、freeze_window 冻结、batch_order_override）
   评审：核实成立:run_state.py:199-221 的 last 状态仅由本次 seed 经 update_machine_last_state(seed_mode=True) 重建,无任何加载 start_dt 之前机台尾工序的路径;internal_slot.py:144-150 _changeover_penalty 在 last_type 缺失时返回 0,冻结窗后每机台首道工序换型惩罚恒 0 属实,auto_assign 同丢该先验。修法(补查上一版窗口前最后一行以 seed_mode 注入)与 A16 同守卫语义兼容,freeze_meta 降级留痕框架可复用,只读上一版风险低,py3.8/SQLite 无兼容问题。expected_gain 未给虚构数字(只说'从恒 0 变为贴近现场'+可 harness 量化),诚实。注意 freeze_window.py 在并发修复清单内,

25. [problem] graph-ready 权重网格为重复解码结果付全价 SGS（评估函数与目标体系(evaluation.py / objective.py / candidate_eval 链 / best_metrics 流转)）
   评审：代码结构亲验属实:optimizer_graph_ready.py:419-422 指纹判重发生在 schedule_fn 解码之后,same_as_seen 只省 best 更新不省解码;生产 graph_analysis_mode=on 下局搜/GRASP-IG 在 optimizer_local_search.py:299-301 与 optimizer_grasp_ig_candidates.py:427-429 整段跳过,该网格确为 improve 模式主要评估开销。60% 重复率来自研究员单实例实测,结构上与'SGS 粗粒度解码'解释自洽,可信但不可外推为通用比例。severity med 合理。注意:指纹判重以 search_report_state 非 None 为前提,该路径在生产编排中恒有,无额外漏洞。

26. [problem] overdue_count 与 tardiness 在 due_exclusive 边界口径割裂（评估函数与目标体系(evaluation.py / objective.py / candidate_eval 链 / best_metrics 流转)）
   评审：evaluation.py:261-266 亲验:finish == due_exclusive 时 overdue_count+=1 且 delta_hours=0,确实出现'超期+1 批、拖期+0 小时'。属边界 measure-zero 情形,且与 A06/A12 挂起决策直接相关,研究员'不宜顺手改'的克制正确。severity low 恰当——它更像字典序下第二/三键排序的一个已记录怪癖,不是错误计算。

27. [problem] runtime_ms 只在 graph-ready 候选上设置,tie-break 跨 origin 不一致（评估函数与目标体系(evaluation.py / objective.py / candidate_eval 链 / best_metrics 流转)）
   评审：grep 亲验:runtime_ms 仅 optimizer_graph_ready_candidates.py:107/408 写入;optimizer_candidate_comparison.py:45-57 缺失按 1e9 最劣处理,注释明示该语义被刻意设计但只图候选遵守。后果是同分 tie 时局搜/GRASP-IG 候选在 runtime 维度系统性垫底——鉴于生产 graph 模式下另两阶段整段跳过,实际影响面小,severity low 合理;若未来 graph mode off 场景回暖则升级为 med。

28. [opportunity] 解码前按 graph_priority_key 映射哈希精确去重（评估函数与目标体系(evaluation.py / objective.py / candidate_eval 链 / best_metrics 流转)）
   评审：context_for_profile(optimizer_graph_ready_candidates.py:111-132)证实 key 映射是 (metrics, profile) 的确定函数,SGS 解码对相同 (key 映射, seed, rule, context) 确定产出同排程,预去重无损。研究员自己给出的风险(哈希键漏解码输入)与缓解(测试锁'同 key 必同结果'合同)正确且必要——当前 decode 输入还含 downtime_map/seed_sr_list/readiness_gate 等,哈希构造必须枚举全。~11% 是保守实测下限,effort S 属实。与机会 1 可叠加且应先做(S 先于 M)。

29. [opportunity] 反模式备案:不为 compute_metrics/指纹做缓存（评估函数与目标体系(evaluation.py / objective.py / candidate_eval 链 / best_metrics 流转)）
   评审：compute_metrics(evaluation.py:132)确为单遍 O(n)+每机排序,相对 SGS 全量解码可忽略,成本结构与代码阅读一致(0.2%/0.3% 数字来自实测,方向无疑)。纯 cs-learn 文档沉淀零风险,能防止后续工兵重复立案,确认。

30. [opportunity] search_report 加同分 plateau 计数为 A13 决策供数据（评估函数与目标体系(evaluation.py / objective.py / candidate_eval 链 / best_metrics 流转)）
   评审：字典序纯键序(objective.py:17-44)与 score 首位 failed_ops 属实,'首键打平时后键严格更优才算改进'的比较语义与 candidate_is_preferred 严格小于一致。在 A13(接受准则量纲)挂起期间只加观测计数、不改行为,完全符合'语义决策前不动接受准则'的纪律,且产出正是决策最缺的本仓库分布数据。effort S、风险极低,确认。

31. [problem] 追踪中的 ratchet 基线自身 dirty_worktree=True,质量棘轮永远无法 pass,且必跑测试硬编码断言它 failed——棘轮形同虚设（基准与实验体系(算法质量基准 / 回归棘轮 / 性能基准)）
   评审：亲验属实:baseline json 顶层 dirty_worktree=true(git_commit e3ed32c,generated 2026-06-30);optimizer_benchmark_ratchet.py:146-160 _worktree_proof_failures 对 dirty baseline 产生 dirty_baseline_worktree failure;必跑测试 test_optimizer_benchmark_ratchet_gate.py:44-55 断言 comparison status==failed、proof_binding_status==unbound_dirty_worktree。危害链成立:任何干净工作区也拿不到 passing 证明,棘轮只剩机制自测价值。

32. [problem] 性能基准只记录不棘轮:runtime_ms 在基线里但不参与比较;大资源池性能脚本无耗时基线（基准与实验体系(算法质量基准 / 回归棘轮 / 性能基准)）
   评审：亲验属实:_row_failures(optimizer_benchmark_ratchet.py:106-124)只比 gap_to_oracle_pct/failed_ops 容差 0;_graph_ready_row_failures(:189)比 objective_score/best_origin/status 也不读 runtime_ms;benchmark_sgs_large_resource_pool.py 只断言 scheduled_ops>0/failed_ops=0/result_count 匹配,elapsed 只写报告。A 批正在改 sgs.py/internal_slot.py,2 倍变慢确实无门禁拦截。

33. [problem] RCPSP j30 数据与 loader/optima 已 vendored 但完全无人使用,多机资源受限零外部参照（基准与实验体系(算法质量基准 / 回归棘轮 / 性能基准)）
   评审：亲验属实:grep tests/ 下 rcpsp 仅命中 optimizer_benchmark_loaders.py 与其形状单测 test_optimizer_benchmark_loaders.py;tests/_data/optimizer_benchmarks/rcpsp/ 三实例+j30opt 就位无人消费;grading 只锁 overdue_count 第一分量,四个 tie-breaker 分量无外部参照的判断与 loader docstring 口径一致。

34. [problem] medium gate 三家族编排未接入任何强制流水线,只被契约测试验证计划存在（基准与实验体系(算法质量基准 / 回归棘轮 / 性能基准)）
   评审：亲验属实:grep scripts/run_quality_gate.py、run_daily_quality_gate.py、tools/long_gate_manifest.py 均无 benchmark 引用;medium gate 仅被 test_optimizer_benchmark_ratchet_gate.py:250 的契约测试验证 command_plan;evidence 目录确为 git-ignored。说'未接入任何强制流水线'准确。

35. [opportunity] 把 runtime_ms 纳入 ratchet 比较或为大资源池性能脚本建宽松耗时棘轮（基准与实验体系(算法质量基准 / 回归棘轮 / 性能基准)）
   评审：建议锁相对比率或 estimate_internal_slot 确定性调用次数是诚实且工程上正确的(大资源池脚本已 mock 包裹估算器计数,基础设施现成);无实验数字属合理定性;risk 栏对绝对耗时误报与干净基线前置的披露诚实;无依赖/兼容性冲突。本批机会类中证据与风险披露最平衡的一条。

36. [opportunity] 把 medium gate --run 接进 long-gate 清单(非 daily)（基准与实验体系(算法质量基准 / 回归棘轮 / 性能基准)）
   评审：接入成本确实极低(medium gate --run 现成、long_gate_candidate 机制现成),分层进 long-gate 而非 daily 与 memory 中门禁分层约定一致;expected_gain 为机制性收益无数字属合理;risk 栏诚实(时长上升、需 A 批后跑通)。

37. [opportunity] 落地 RCPSP j30 资源受限基准:补 case builder+grading（基准与实验体系(算法质量基准 / 回归棘轮 / 性能基准)）
   评审：数据/LB 函数确实 vendored 且零消费,补多机资源受限外部参照的结构性盲区判断成立;risk 栏对 RCPSP→APS 语义映射失真与 CP-LB 松下界的披露诚实,'排在 O1-O4 之后'的优先级自觉也对。effort=L 与 expected_gain 均为定性无实验,属探索性机会,按此口径接受。

38. [problem] v2_atc_like 与 v2_critical_ratio 代数等价,CR 族 5 个 profile 实际是同一个排序（GraphReadyV2 特征工程与权重 profile 族(optimizer_graph_ready* / sgs 图评分键)）
   评审：代数核实成立:due_pressure=max(0,min(1,remaining/due))(features.py:371-375),critical_ratio=due/remaining(:384-388);未逾期未收紧区间(remaining<due)critical_ratio>1 且与 due_pressure 严格互为倒数单调,取负后全序相同;rank01 保序,两公式次级键(sacrifice_penalty/processing_rank/jitter)完全相同,故正常区 induced order 必一致,差异只在 clamp 饱和区与逾期分支(atc_like 的 due<=0 给 1+逾期天数,CR 给负值)。报告'差异只在 clamp/逾期区'表述精确。补充一个报告没说的强化点:clamp 使 remaining>=due 时 due_pressure 全部=1

39. [problem] saveability/sacrifice_penalty/due_pressure 不含机器竞争,负载场景下整池饱和失去区分度（GraphReadyV2 特征工程与权重 profile 族(optimizer_graph_ready* / sgs 图评分键)）
   评审：代码机制确认:saveability=min(1,due/remaining)(:378-381)在 due>=remaining 时恒=1.0;sacrifice_penalty 在 remaining<0.7*due 时恒=0(:391-396);两者输入只有本批 remaining 与 due,确实无同池竞争项(enrich 段 :95-119)。这是 clamp 数学保证的塌缩,不是偶发——只要交期窗口>本批剩余工时(负载不重时的常态)就整池饱和。'生产多批共享机台同理'是外推,但单机 40 工序全 1.0 的实测与 clamp 机制互证。saturation 后 saveability/sacrifice 主导的公式(saveability/sacrifice_long 的主键)确实退化为 due_pressure/processing_rank 排序,P1 的冗余链进一步放大。

40. [problem] 19 个 profile 固定枚举序 v1 在前、无解码前排序去重,高价值 profile 排在第 12/17 位,紧预算下可能永远轮不到（GraphReadyV2 特征工程与权重 profile 族(optimizer_graph_ready* / sgs 图评分键)）
   评审：枚举序核实:v1 9 个(profiles.py:33-43)+v2 10 个(:180-194),v2_spt 第 12、v2_sacrifice_long 第 17 位正确。去重位置核实:_candidate_should_replace_best 内的 mark_candidate_evaluated(optimizer_graph_ready.py:412-424)在 _evaluate_profile(:260)完整解码之后,先解码后去重属实。图相与局搜共享 deadline 的循环结构(:256-258 先查 deadline)属实。两点保留:1) 报告未核实生产 max_weight_profiles 默认上限是否放满 19 个,若有截断问题更严重;2) '可能吃光预算饿死局搜'的相对量级依赖生产单解码耗时,61ms 是小基准数字,大实例方向成立但程度未证。核心指控(赢家排尾

41. [problem] v1 加权和原始尺度混算,critical_path 权重是死旋钮;v2_graph_due_hybrid 的 graph_bonus 继承同一问题（GraphReadyV2 特征工程与权重 profile 族(optimizer_graph_ready* / sgs 图评分键)）
   评审：尺度混算代码级确认:_metric_bonus 把 is_on_critical_path 的 0/1×权重(v1 权重表 critical_path∈[0,4],profiles.py:33-43)与 downstream_critical_minutes/60×权重(candidates.py:142-162,生产尺度下游小时可达数百)和 bottleneck_machine_score×权重直接相加,无归一。critical_path 平坦加 2-4 分对总量数百分的 bonus 确为死旋钮,'critical_path_first 与 balanced 的差异主要来自瓶颈权重减半'从权重表可直接读出(cp 2→4 但 bottleneck 1→0.5)。v2_graph_due_hybrid 的 graph_bonus 用 raw 权重再做 rank01(:196 区域),继承同一

42. [problem] v2_seeded_micro_perturbation 的 jitter 排在连续特征之后,几乎永不触发,种子多样性为零（GraphReadyV2 特征工程与权重 profile 族(optimizer_graph_ready* / sgs 图评分键)）
   评审：键结构核实:micro_perturbation 返回 (sacrifice_penalty, -due_pressure, jitter, processing_rank)(candidates.py:302-305),jitter 第三位。sacrifice_penalty 是 {0,1,2} 附近的离散值(长尾 0/1 + 1-saveability),due_pressure 是连续值——jitter 要触发需要前两位同时精确相等,跨批场景 due_pressure 连续故概率极低,与实测 35/40 与 critical_ratio 一致互证。注释宣称的'同分候选间多样性'只在同批同 sacrifice 档且 due_pressure 也相同的罕见并列下发生,种子多样性名存实亡。代码级确认。

43. [problem] 容量口径 due_budget 被 30 天窗口帽静默饱和,日历可用时 >30 天交期的批次失去紧迫度区分（GraphReadyV2 特征工程与权重 profile 族(optimizer_graph_ready* / sgs 图评分键)）
   评审：代码级确认:_RESIDUAL_CAPACITY_MAX_WINDOW_DAYS=30(capacity.py:12),_residual_capacity_window_end=min(due, start+30d)(:93-95);日历分支 due_budget_hours=residual_capacity_window_hours(features.py _deadline_budget_hours :333-350),故 >30 天交期的内部工序拿到同一个 30 天饱和预算,min_slack/CR/due_pressure 对它们退化为只按 remaining 排序。due_budget_basis 只有 'calendar_capacity_hours'/'wall_clock_hours'/'no_due_placeholder' 三值,确无饱和标记(:353-362)。w

44. [opportunity] 解码前按『induced 排序结构』去重 profile,重复排序不再花全量 SGS 解码（GraphReadyV2 特征工程与权重 profile 族(optimizer_graph_ready* / sgs 图评分键)）
   评审：前提核实:解码确定性成立(同一静态 graph key 全序+同一 SGS),现状确为先解码后指纹去重(optimizer_graph_ready.py:289, 412-424),循环顶按 key 映射 tie-group 序列去重可跳过必然相同的候选,O(N logN) 纯字典序比较,无行为风险。19→约 7 的收益与其 6.9 个不同排程的实测自洽。两点补充(不否决):1) 去重键必须含 jitter 等全部 tuple 分量,否则 micro_perturbation 会被误并;2) 与 A02/A04 并发改 sgs.py 的冲突提示诚实,集成后实施正确。effort S、风险极低属实。

45. [opportunity] 静态图键与动态派工键融合:引入真正时间依赖的 ATC 公式(v3)（GraphReadyV2 特征工程与权重 profile 族(optimizer_graph_ready* / sgs 图评分键)）
   评审：现状核实:graph key 确实整体插在 score_penalty 之后、动态派工键之前(sgs_scoring.py:74-75 with_graph_priority_key 拼 base_key[:1]+graph_key+base_key[1:]),静态 profile 一旦选定即压制含 est_start 的动态 slack/ATC/CR,属实。ATC/BATC 文献方向(Vepsalainen&Morton 1987)是排产领域公认结论,引用恰当。报告诚实:无收益数字('量化需 A/B')、自挂 A06/A12/A13 语义裁决之后、承认单机实验中动态/静态 slack 简并。effort M 合理(改评分语义+回归)。无约束冲突。这是方向性 confirmed 而非收益 confirmed,报告措辞本身也如此,故维持 confirmed。

46. [opportunity] 拥挤感知的 saveability/due_pressure:用瓶颈窗口内竞争工作量修正本批口径（GraphReadyV2 特征工程与权重 profile 族(optimizer_graph_ready* / sgs 图评分键)）
   评审：对症:P2 的饱和机制代码级确认,修正方向(用候选机台集合 due 窗口内竞争工时/residual capacity 作系数)所需输入(duration_by_op_id、candidate_machine_ids、residual_capacity_hours)确已在 enrich 流程内存在(features.py:126-140 区域的 capacity dict 与 duration 汇总),无新数据依赖、无新依赖。报告诚实标注 clamp 阈值(0.70 长尾)需重调、特征合同测试需同步、收益需基准复测,无量化吹嘘。effort M、O(N×M) 聚合成本评估合理。Win7/py3.8/离线兼容。

47. [opportunity] 用 rank01 加权和公式族替代纯字典序,打开连续可自适应的 profile 空间(基础设施已就位但闲置)（GraphReadyV2 特征工程与权重 profile 族(optimizer_graph_ready* / sgs 图评分键)）
   评审：关键洞察代码级确认:rank01 是严格保序变换(_rank01_by_op_id,candidates.py:243-256),而 10 个 v2 公式全部消费 *_rank01 字段做字典序 tuple(:269-305),归一对选择结果确为 no-op;唯一跨特征聚合 graph_bonus 在 raw 尺度(:196 区域)继承 P5 失衡——两处指控都重读属实。rank01 恰好提供 [0,1] 可比尺度,w·rank 加权族+坐标扰动是『profile 参数自适应』的合理落点,且能顺带治 P6 死 jitter(rank+ε·jitter 真扰动)。jitter 已是确定性整数散列(_seeded_jitter :258-266),锁定种子可复现;新 formula_slug 走现有 ValidationError 合同、老公式不动,回退安全。'连续权重空间可继续下探 2.85

48. [problem] 槽位估算的效率单点近似与 v2 容量核算的分段效率口径不一致,跨效率日工序两套结果互相矛盾（日历引擎与算法交互(calendar_engine × SGS/槽位估算/v2容量)）
   评审：代码与实验双双证实。internal_slot.py _estimate_attempt 用 _resolve_efficiency(start_time=earliest) 取起点单点效率、总工时除以该值后交给 add_working_hours 按墙钟工时推进;而 optimizer_graph_ready_v2_capacity.py _calendar_capacity_hours 的累计行是 total += _wall_hours(cursor, segment_end) * _policy_efficiency(policy)(:359-364),按段乘效率。/tmp/cal_eff.py 复跑复现:周一 eff=1.0/周二 eff=0.5 下 12h 工序单点近似 end=12:00 vs 分段精确 16:00,差 4h。两口径系统性不一致属实,severity med 

49. [problem] add_working_hours 对已被 adjust 过的起点重复执行一次完整 adjust(冗余调用,量级百万次)（日历引擎与算法交互(calendar_engine × SGS/槽位估算/v2容量)）
   评审：确认。estimate_internal_slot 先 _adjust_slot_start(internal_slot.py:307 附近),随后 _estimate_attempt→add_working_hours 内部 calendar_engine.py:305 又对同一起点 adjust 一次;对已 adjusted 起点 adjust 是幂等白跑。实测计数吻合:adjust 总 1,078,956 ≈ add_hours 内部 1,046,097 + 外部约 3.3 万,即约 104.6 万次冗余。severity low 恰当——本机实测 adjust 单次仅 2.1us(窗内快速返回),冗余部分绝对耗时有限。

50. [problem] 跨午夜归属判定在'空窗时段'返回今日 policy 的隐式语义缺乏注释与测试钉住（日历引擎与算法交互(calendar_engine × SGS/槽位估算/v2容量)）
   评审：代码事实确认:_policy_for_datetime(calendar_engine.py:211-234)对 dt < start_today 且不在昨日跨午夜窗内的空窗时段,穿过 if 块落到末尾 return p_today,该 fallback 语义仅在 docstring 的跨午夜约定中隐含,无注释显式说明。severity low 合理:调用方 adjust/add_hours 随后按不在窗内处理,行为自洽,风险是后续改动无人钉住该语义。研究员自承仅静态阅读未跑失败用例,诚实。

51. [opportunity] 统一效率口径:要么槽位估算也做分段效率积分,要么 v2 容量改用同一近似并在文档钉住'单点近似是 by-design'（日历引擎与算法交互(calendar_engine × SGS/槽位估算/v2容量)）
   评审：问题基础已亲验(4h 分歧复现)。研究员正确地把它定性为语义决策而非纯工程,与 A06/A12/A13 的处理方式一致(走 cs-decide 立案),没有越权拍板;两个方向(分段积分/钉住单点 by-design)的取舍与风险(改变既有排产结果需回归基线)都写清楚了。与机会1的耦合(累计表存 eff 加权工时则分段积分零额外循环)是正确洞察。effort M 合理。

52. [problem] CP-SAT 预热写死 num_search_workers=8,与 Win7 低端机(2-4核)和秒级预算错配（文献对照与算法选型(SGS+优先规则+局搜 / OR-Tools 适用边界)）
   评审：亲验属实:core/algorithms/ortools_bottleneck.py:194 无条件 num_search_workers=8(仅 try/except 兜底参数设置失败),无 os.cpu_count() 封顶、无配置项;默认预算确为 5s(core/models/schedule_config_runtime_fields.py:85 default=5)。多 worker CP-SAT 非确定性属实,与'可复现'约束冲突。修正点:危害链有边界——ortools_enabled 默认 "no"(同文件:80),该预热默认不启用,且 Win7 上 ortools 本身已被 SPIKE 判高风险,实际暴露面是'显式开启预热的用户',severity med 偏上限,按 low-med 落地更准。

53. [problem] 瓶颈工种判定只看工时总和,不除以该工种的并行机台数,多机工种会被误判为瓶颈（文献对照与算法选型(SGS+优先规则+局搜 / OR-Tools 适用边界)）
   评审：亲验属实:ortools_bottleneck.py:121 直接 max(load_by_type) 按工时总和选瓶颈,函数签名(:77-85)确无 resource_pool 参数;而调用侧 schedule_optimizer_steps.py:97/135/231/348/452 多处 resource_pool 已在手,改造可行。多机工种被高估瓶颈度的机制成立,且 warm-start 整条链围绕该工种建模,误判会放大。不影响主流程(可选预热),severity med 合理。

54. [problem] max_jobs=200 截断后被排除批次仅用交期+优先级粗排追加尾部,大批量池场景预热质量陡降（文献对照与算法选型(SGS+优先规则+局搜 / OR-Tools 适用边界)）
   评审：亲验属实::148-154 超 max_jobs 截断,:214-222 rest.sort 用 (due_min, -weight, bid) 三键后 append;日志(:225-229)只记 jobs/total_batches 总数,截断事件本身无独立审计记录,'降级链不可见'的指控成立。与 SGS per-op 评分的目标错位推断合理但未经实测,severity low 恰当。

55. [opportunity] OR-Tools 预热从'单一瓶颈工种'扩展为 top-k 瓶颈分解+AddHint 现任职解,按需串行求 2-3 个工种（文献对照与算法选型(SGS+优先规则+局搜 / OR-Tools 适用边界)）
   评审：成立且与 problem#1/#2 形成闭环修复:top-k 归一化直接消除已确认的瓶颈误判,AddHint 在 ortools 9.x(py3.8 封顶 9.8.3296)API 可用属实,arXiv:2403.16766 的 ~40% 求解时间下降有文献出处。worker 数改 min(os.cpu_count(), cfg) 与 problem#1 是同一处,应合并落地。修正点:ortools_bottleneck.py 不在 A 批并发修复清单内,落地无冲突;但所有收益以'用户显式开启可选预热'为前提,实际覆盖面受 ortools_enabled 默认 off 限制,expected_gain 的可达性需打折说明。

56. [opportunity] 用已完成排产历史做超轻量'规则选择器',替代 learning-to-dispatch 的重模型路线（文献对照与算法选型(SGS+优先规则+局搜 / OR-Tools 适用边界)）
   评审：成立:algorithm selection(Rice 框架)路线对单机离线 py3.8 现实,拒绝 learning-to-dispatch 重模型的判断正确;两侧数据基础属实——v2_features 已是实例特征、algo_stats 已记录 run 级规则与目标值,'差的只是离线拟合+查表'的差距评估准确。2-6% 标注了'文献典型值'属诚实外推,非编造;对 item6/7/8 作用点错位'把调旋钮变成选实例适配组合'的根治方向论述与已有裁决不冲突。effort L、样本偏差风险、与 GraphReadyV2 profile 族职责边界的提示均诚实。落地建议作为独立增强排在 FBI 之后。

57. [problem] SGS 每轮全量重评分+全池探针:现实规模单跑成本直接吞掉 improve 全预算（SGS 主循环与评分架构(sgs.py / sgs_scoring.py / sgs_graph.py / batch_order.py / auto_assign.py 探针链)）
   评审：亲验复核:重跑 /tmp/sgs_probe_experiment.py(.venv py3.8,并发修复中间态代码),固定 500 ops=25,774 次 estimate_internal_slot(51.5/工序)、auto-assign 500 ops=412,320 次(824.6/工序,其中 aa_pair_estimate_scoring 379,050 占 92%)、auto-assign 500 ops 墙钟 14.2s(报告口径 13.9-30.9s,量级一致);重评分 key 重复率 88.6-92.6%,失效规则违例 0,与报告数字吻合(微小漂移系并发修复所致)。预算链核实:time_budget_seconds 默认 5(core/models/schedule_config_runtime_fields.py:92)、deadline=起点+预算(schedu

58. [problem] winner 槽位被独立推导 4 次:探针、评分复算、放置重探针、放置终算（SGS 主循环与评分架构(sgs.py / sgs_scoring.py / sgs_graph.py / batch_order.py / auto_assign.py 探针链)）
   评审：四段推导逐点核实成立:评分期 _choose_best_pair 全池探针(auto_assign.py:253-305,probe_only=True 只读已核 auto_assign.py:97-101)→ _estimate_scoring_slot 对选中同对重算(sgs_scoring.py,实测 scoring_final_estimate=25,270 次)→ 放置 _resolve_internal_resources 再跑全池 auto-assign(internal_operation.py:122-135,实测 aa_pair_estimate_placement=7,500)→ placement_final_estimate=500。等价契约护栏 tests/algorithm/test_internal_slot_estimator_consistency.py

59. [opportunity] SGS 增量评分缓存:op 级 key 缓存 + 读集失效规则（SGS 主循环与评分架构(sgs.py / sgs_scoring.py / sgs_graph.py / batch_order.py / auto_assign.py 探针链)）
   评审：机制亲验成立:评分读集=批次 prev_end/机台 timeline·busy_hours·last_op_type/人员 timeline·busy_hours,失效规则'同批∪机台池∪人员池'在实测两类实例 0 违例(88-92% key 本就逐轮不变,缓存命中 76-79% 与冗余率自洽)。byte-identical 原型存在(/tmp/sgs_cache_prototype.py),ready_queue 差分 oracle 先例属实。风险披露诚实(失败事件清缓存未在含失败实例验证、图模式需专项差分、ValidationError 不缓存)、明确等 A 批集成后落地,不冲突。收益数字全部有实测支撑,非拍脑袋。effort M 合理。纯 dict/set,py3.8/Win7/离线/零依赖全合规。

60. [opportunity] pair 级槽位估算缓存:按资源版本号精确失效（SGS 主循环与评分架构(sgs.py / sgs_scoring.py / sgs_graph.py / batch_order.py / auto_assign.py 探针链)）
   评审：92% 探针占比与 824 次/工序的实测基数复核一致;版本号失效(pair 命中 82-85% vs op 级 33-34%)与实测失效模式自洽。风险披露尤其诚实:核实 auto_assign.py:303 确以 abort_after=best[0] 做剪枝,缓存复用必须关闭该剪枝否则估算依赖扫描顺序——这是本机会最容易翻车的点,研究员主动点破且实测净赢。InternalSlotEstimate frozen、内存量级、失败清空、A15/A18 并发依赖声明均如实。预期 3.8×@500/4.5×@1000 有原型实测,可信。

61. [opportunity] winner 结果直通:探针估算随候选传递,收敛四段重算（SGS 主循环与评分架构(sgs.py / sgs_scoring.py / sgs_graph.py / batch_order.py / auto_assign.py 探针链)）
   评审：与 P2 修复对应,四段收敛为一段的结构面清晰;algo_stats 计数语义风险(internal_auto_assign_attempt/success/failed 在放置时计数、有测试锁)核实属实——跳过重探针必须显式补计,这是本机会唯一实质风险,研究员已点名。effort S 合理,~8% 估算量节省与 P2 实测口径(6.1%+1.8%)一致,主要收益实为消灭评分/放置双路漂移面,定位诚实。

62. [opportunity] #53 修法建议:候选静态 meta 预计算（SGS 主循环与评分架构(sgs.py / sgs_scoring.py / sgs_graph.py / batch_order.py / auto_assign.py 探针链)）
   评审：#53 系已登记问题,此处仅给修法,定位正确。_candidate_meta 中 priority/due_date/seq/op_id 静态、仅 prev_end 动态的判断与代码相符;_group_sgs_ops 预计算点合理。strict/非 strict 日期解析语义分叉(sgs_scoring.py:34-35)的风险提示必要且准确。10% 为 cProfile 实测占比,effort S、风险极低,成立。注:O1 落地后本项收益被覆盖,研究员已自行声明该关系。

63. [opportunity] 小项:图模式候选每轮 sort_key 排序是无效功（SGS 主循环与评分架构(sgs.py / sgs_scoring.py / sgs_graph.py / batch_order.py / auto_assign.py 探针链)）
   评审：事实核实:sgs_graph.py:319 每轮 sorted(ready_op_ids, key=sort_key) 存在;评分 key 以 op_id 收尾必唯一(dispatch_rules.py:94),min() 与输入序无关,排序对排程结果确零影响(仅影响 ValidationError 抛出顺序)。研究员对收益(<2%)和定位(不值得单动、O1 落地顺带收编)的判断克制且诚实,报错工序顺序漂移的风险提示也正确。成立。

64. [problem] SGS 评分跨轮零复用导致准二次墙:1200 工序在制品规模下不可用(>300s 未跑完)（端到端性能画像(SGS 派工主链路 + 优化器候选评估)）
   评审：代码事实核实:auto_assign.py:255 _choose_best_pair 全配对调 estimate_internal_slot(internal_slot.py:279),sgs.py 每轮重估,跨轮零复用成立。本机复跑实验确认准二次 scaling:200ops≈7.5-9.7s、400ops≈9.7s(桩日历下 memo 基线),报告口径与实测一致;1200ops>300s 未复跑(成本过高),但 200→400 的超线性增长(2.35x/2x)与 memo 实验 90.9% 重复率足以支撑 high severity。downtime.py:19 occupy_resource 确实只 insort,佐证'时间轴只增、每轮仅 1 机 1 人变化'的论断。

65. [problem] _pair_rank 对 pool 中已是 int 的值逐次 parse_required_int 严格校验,单次排产 63 万次（端到端性能画像(SGS 派工主链路 + 优化器候选评估)）
   评审：auto_assign.py:410-421 确认 _pair_rank 对 pool 中已校验过的值逐次 parse_required_int;pair_rank 内容排产内不可变。63 万次/~5-6% 占比未独立复跑 profile,但与机会1实验同场景下 estimate 35.5 万次×配对数的量级自洽,且修复方向(预解析)风险低。注意:根治不能简单挪进 _coerce_resource_pool(见机会2修正)。

66. [problem] 每次 estimate 新建 3 个 SegmentOverlapIndex,惰性物化重复 62 万次/次排产（端到端性能画像(SGS 派工主链路 + 优化器候选评估)）
   评审：internal_slot.py:183-201 _slot_segments 每次 estimate 新建 3 个 SegmentOverlapIndex,downtime.py:70 _materialize 惰性物化,事实成立。复跑 /tmp/aps_index_cache_experiment.py:9.65s→8.54s(11.5%),与报告 11% 一致;schedule 结果一致。62 万次物化未独立计数,由 11% 提速间接佐证。

67. [opportunity] SGS 跨轮 estimate memo:按 (op.id, machine, operator, prev_end, base_time, 时间轴len版本, end_dt, last_op_type) 缓存 estimate,abort_after 移到用点判断（端到端性能画像(SGS 派工主链路 + 优化器候选评估)）
   评审：本机复跑 memo 实验完全复现:400ops 9.7s→2.8s(3.4x)、命中率 90.9%、schedule 逐字段与基线一致、确定性成立。语义等价性核实:internal_slot.py:212-222 _abort_after_result 只依赖 earliest,避让循环 earliest 单调右移(:320-348),abort_after=None 算一次+用点比较 start_time 等价成立;abort 结果携带的 efficiency_fallback_used 可从缓存的成功结果带出。风险评级诚实(键含时间轴 len 版本、op.id、等 A 批集成)。补充两点报告未写明:缓存 dict 需挂 ScheduleRunState 生命周期防跨排产泄漏;内存上界未估算(1200ops 键量约 ops×M×O 去重后 ~misses 数,量级可控但应写明)。1200

68. [opportunity] SegmentOverlapIndex 按轮复用:以时间轴对象身份+len 为键缓存索引(或把索引挂到 ScheduleRunState 的时间轴旁)（端到端性能画像(SGS 派工主链路 + 优化器候选评估)）
   评审：复跑实验确认单独 ~11.5%(9.65→8.54s)、结果一致。'索引绝不修改输入'与 downtime.py 只读契约一致;id() 裸键风险提醒正确。与 memo 叠加后收益缩到 miss 路径的判断合理(memo 命中时根本不建索引)。effort S、风险低-中诚实。注意 internal_slot.py A 批并发修复中。

69. [opportunity] 优化器候选评估并行化:不推荐走多进程,优先吃 memo 红利（端到端性能画像(SGS 派工主链路 + 优化器候选评估)）
   评审：论证链全部核实:calendar_engine.py:81 CalendarEngine.__init__ 持有 sqlite conn,GreedyScheduler 经日历不可 pickle 成立;Win7+py3.8 冻结 exe 下 multiprocessing 只能 spawn+freeze_support 的约束正确;tests/_support/benchmark_parallel.py 确实存在但仅是测试脚本,不能佐证生产可行;'并行改变候选选取顺序破坏可复现合同'是关键论点,与 APS 可复现/可追溯原则直接冲突。结论'不做、优先吃 memo 红利'判断正确且与机会1形成合理优先级。effort L/风险高评级诚实。

## 三、评审 adjusted（按修正后口径）

1. [opportunity] 把 dispatch_rule 纳入候选族：新增 sgs+atc 候选（或随 sgs 默认化把默认规则切 atc），由 balanced 选择护栏择优（派工规则库（dispatch_rules / build_dispatch_key / 规则×图key 组合））
   修正：方向证据扎实：实验亲跑逐数复现（加权拖期 slack 919.3 vs atc_k2 365.0 即 -60%；超期数 17.0 vs 9.3 即 -45%；EDD 605.7/CR 630.0 居中；k=2 逐格 gap 最大 +3.9% 否定 k 标定；maxlate 恶化 39.7→61.4h 的风险披露也复核属实），与文献共识（Vepsalainen & Morton 1987 ATC 为加权拖期最强单遍规则）一致。架构前提亲核属实：候选枚举 schedule_candidate_specs.py:59-90、balanced 护栏与 baseline 兜底见审计驳回#4 记录（断裂环2 引 schedule_candidate_selection.py:44-100 等）、time_budget 默认 5s（config_field_spec.py:284）、驳回#4 断裂环1 

2. [opportunity] 新增 priority-aware 规则值（如 'wslack'：slack/w 或 slack-β·(w-1)·avg_p），让'加急'在智能派工下生效（派工规则库（dispatch_rules / build_dispatch_key / 规则×图key 组合））
   修正：问题基础（problems#3）已确认，自我降级为'ATC 落地后观察项'的定位诚实，6.3% flip 率作参照上限有实验依据。但必须修正一处未标注的设计缺陷：候选形态 slack/w 在负松弛区语义反转——过期候选 slack<0 时除以 w=3 使 critical 批 -10h→-3.33，反而排在 normal 批 -5h 之后，即'加急越高越不急'，与 A06 定案的 CR 负松弛病灶（dispatch_rules.py:75-77 除法在负区反转，A06 审计记录明证同类机制）完全同族；仓库正为此等语义决策，再引入同病灶形态不可接受。只有加法形态 slack-β·(w-1)·avg_p 在负区安全，落地时应直接排除除法形态而非'标定二选一'。另补一处遗漏触点：新枚举值需同步进优化器 sgs_dispatch_rule 邻域的合法规则清单（schedule_optimizer_

3. [problem] 场景覆盖缺口：所有质量基准都在连续日历/无停机/无冻结/无资源池下跑；RCPSP 数据 vendored 两年式闲置（基准与实验体系（算法质量回归门禁、基准覆盖面、性能基准固化））
   修正：前半段全部核实：oracle 用 _ContinuousCalendar(optimizer_proof_oracle.py:35-46)、freeze_window_enabled='no'(:328)；graph_ready 基准 downtime_map={}(optimizer_graph_ready_benchmark.py:222)、resource_pool=None(:228)；FJSP seed_calendar_24h(optimizer_fjsp_runner.py:95)；大池基准确实只排 1 个工序(benchmark_sgs_large_resource_pool.py:178-192)。修正后半段口径：(1)'两年式闲置'夸大——RCPSP 数据 2026-06 才 vendored，闲置数周而非数年；(2)不跑进 APS 是 loader 文档化的主动决定而

4. [opportunity] RCPSP j30 折叠跑通：把 renewable capacity 折成 k 台同型机资源池，建第一个资源受限+DAG 质量基准（基准与实验体系（算法质量回归门禁、基准覆盖面、性能基准固化））
   修正：实验修正三处：(1)规模口径错——j30 实例是 30 个真实活动(32 jobs 含源汇，实测 j301_1/j301_2/j3013_5 均 real_activities=30)，'120 活动量级'是 PSPLIB j120 集，本仓未 vendored；(2)仓内只 vendored 3 个 .sm 实例(+480 条 optima)，'跑通 j30'先要补数据；(3)致命的是 demand 剖面：实测 j301_1 有 27/30、j301_2 有 28/30 活动 demand>1，j3013_5 全部 30 个活动跨多资源——'筛选 demand≤1 可精确折叠的实例'在现有数据上近乎筛出空集；而忽略 demand 量级把 capacity=12 折成 12 台机是放松约束(真实并发度约 2-3)，放松模型可解出优于 published optimum 的 makespan

5. [problem] 生产 GraphReadyV2 路径上迭代搜索整体短路:改进全靠 9 个一次性 profile 解码（局部搜索 / GRASP-IG(optimizer_local_search*、optimizer_grasp_ig_*、optimizer_neighborhood_*、optimizer_vns、optimizer_acceptance、optimizer_graph_ready 候选相位)）
   修正：亲验属实。optimizer_local_search.py:298-300 与 optimizer_grasp_ig_candidates.py:427-429 两处均在 graph_ready_context 非 None 时无条件记 'graph_ready_uses_graph_candidate_phase' 并 return best;optimizer_graph_ready.py:255-301 是单趟 for profile 循环、每 profile 一次完整解码、无迭代。生产默认 graph_analysis_mode=on,故生产路径确无迭代式改进搜索。保留 adjusted 而非 confirmed 仅因两点:(1) 行号与代码处于 A 批并发修复中(_run_weight_profiles 内已出现 _candidate_should_replace_best/_

6. [opportunity] 增量后缀评估:批次序改动只重排受影响后缀（局部搜索 / GRASP-IG(optimizer_local_search*、optimizer_grasp_ig_*、optimizer_neighborhood_*、optimizer_vns、optimizer_acceptance、optimizer_graph_ready 候选相位)）
   修正：方向正确且是解锁 #3/#4 的前提,报告对'等解码次数下贪婪重插反而亏'的成本结构分析是本报告最有价值的洞察。但需调整两点:(1) 'k 之前排程不变'在图就绪 SGS 下并非显然——前后缀边界除批次序外还受优先级图/资源可用状态约束,换装/setup 跨边界状态传递报告已在 risk 中承认,但 rationale 里'前 k 批次 results 作为 seed_results'表述过于轻描淡写,实际 seed 注入路径(A14 正在改 external_group_cache)是当前并发热点,冲突风险比报告写的更高;(2) '有效候选数放大 5-20 倍'无实验无文献出处,纯估计,应降级为'待实测'。effort=L 诚实。

7. [opportunity] 评估剪枝:解码前用免解码下界剪掉必劣候选（局部搜索 / GRASP-IG(optimizer_local_search*、optimizer_grasp_ig_*、optimizer_neighborhood_*、optimizer_vns、optimizer_acceptance、optimizer_graph_ready 候选相位)）
   修正：思路合法但收益数字不合格:'剪掉 20-50% 必劣解码'无任何实验或具体文献支撑,是纯经验拍数,应删除或标为'完全待实测'。另有两点报告自己已部分承认但需强化:(1) 多目标 score 元组(failed_ops 字典序优先)使'下界不劣于 incumbent 上界'的剪枝条件设计远比单度量复杂,界设计错误会直接破坏可复现合同;(2) 本仓库 internal_slot 是槽位估算件,能否构成真下界未论证,'可复用作界的原料'是推测。effort=M 在真下界证明面前偏乐观。建议降级为'先做可复现性安全的单度量宽松界+对拍验证'。

8. [problem] 机会-真正的增量重排:受影响子集重优化 + 稳定性(anti-nervousness)目标（增量排产:seed 续排、freeze_window 冻结、batch_order_override）
   修正：方向有文献与实测双支撑且诚实:Vieira et al. rescheduling survey 确把 stability/nervousness 列为重排核心目标;报告自带负面实测(seed 重放 1.8ms/趟 vs 全量 1348ms)排除了 seed 缓存伪机会,没有虚构收益数字;目标可比性风险(failed_ops+objective 须在全量 results 上算)点得准。修正点:(1) effort L 偏乐观——'受影响闭包推导'(变更工序+同机台冲突+同批后继+资源传播)在图就绪+外协组+冻结三层机制下边界条件多,且 schedule_optimizer.py/optimizer_local_search* 正是 A 批并发修复热点,落地排期须在集成后;(2) 稳定性惩罚 Σ|new_start-old_start| 与 A12(目标比较键)/A13(接受准则量纲)两条待

9. [problem] 机会-局搜/GRASP 邻域移动域剔除全冻结批次（增量排产:seed 续排、freeze_window 冻结、batch_order_override）
   修正：机制核实成立:_build_order(schedule_optimizer.py:266-274)对全部批次排序不剔全冻结批;全冻结批工序全由 seed 钉死,交换其位置不改变任何 dispatch 输入,fingerprint 去重后确为纯浪费评估;scheduler.py:321-325 override 补尾机制证实部分覆盖安全,move 域限'至少含 1 道未冻结工序的批次'语义无损;mutable_scope 报告字段(optimizer_local_search_candidate_eval.py:70)已存在。修正:expected_gain '1.2-2x'无实验无文献,纯按全冻结批占比推算,应降级为'方向性收益,幅度待 optimizer_proof_harness 实测';另 optimizer_neighborhood_registry.py 与 A 批局搜修复并发

10. [opportunity] graph-ready 网格连续 same-output 早停（评估函数与目标体系(evaluation.py / objective.py / candidate_eval 链 / best_metrics 流转)）
   修正：机制可行:_run_weight_profiles(optimizer_graph_ready.py:257-302)循环内已有 deadline 早退与指纹判重基础设施,加连续 K 次 same-output 计数是低风险增量,与局搜 seen_hashes 节流思想一致。但 expected_gain 的 40-50% 来自单一 40 批实例,且收益强依赖 profile 排序(改进 profile 若排在后部,K=3 可能误杀)——修正口径:收益区间为'单实例实测 40-50%,多实例待验证',落地前须跑 profile 顺序敏感性实验并至少 3 种规模实例复核;另早停只在与 deadline 不冲突时才有净收益(deadline 兜底已存在)。effort M 与'A08 集成后落地'的前置声明诚实。

11. [problem] 生产默认 improve 路径在 SMTWT 250 实例上无质量回归门禁;对比 evidence 只跑 2 实例且无 check-baseline（基准与实验体系(算法质量基准 / 回归棘轮 / 性能基准)）
   修正：事实全部属实但 severity 建议降为 med-high:基线确实只有 3 case 且 graph_ready 单 case 行;evidence/.../optimizer_smtwt_compare_algorithms.json 实测 limit_per_size=1 共 14 行(7 profile×2 size,即每 size 仅 1 实例);benchmark_smtwt_localsearch.py:165 只在 had_failed_samples 时 return 1,gap 倒退不 fail;对比基线实测 172KB 全部同属 graph-ready-weight-grid-real-sgs 单 slug。说'零门禁'成立,但 scheduler 组必跑测试里 ratchet 机制测试仍在跑,250 实例的 loaders/grading 也随时可接,属'未接线'

12. [opportunity] 重建干净 ratchet 基线并把 --check-baseline 变成真实可 pass 的门禁步骤（基准与实验体系(算法质量基准 / 回归棘轮 / 性能基准)）
   修正：rationale 与代码事实吻合且脚手架现成,但 expected_gain 无实验数字(属'恢复既有拦截力'的定性收益,非量化增益);risk 栏诚实(必须先 A 批集成+干净 HEAD)。另注意:_graph_ready_row_failures 把 best_origin=='baseline' 当 failure,重建基线后 A 批引入的候选来源变化可能直接触发 failed,重建时机必须等 A 批定稿。约束合规。

13. [opportunity] 给生产默认 improve 路径建 SMTWT n=40/50 质量棘轮(固定子集+Moore-Hodgson oracle)（基准与实验体系(算法质量基准 / 回归棘轮 / 性能基准)）
   修正：组件确实全部 vendored(smtwt_overdue_case、parallel_map_ordered、Moore-Hodgson oracle),Moore-Hodgson 精确解成本为零的说法有 loader 支撑。但 expected_gain 引用 items 9-13 的 16→6.8 是历史修复量级而非本机会的预测收益,严格说无新实验依据;且 overdue_count 分量只反映 grading 第一分量,与生产 improve 的多分量目标不完全对齐,risk 栏未提这一口径偏差。方向正确、收益数字降级。

14. [opportunity] SMTWT 对比 evidence 从 limit_per_size=1 提升到固定子集并固化 tracked 对比基线（基准与实验体系(算法质量基准 / 回归棘轮 / 性能基准)）
   修正：照搬 graph-ready-v2-comparison-baseline 模式方向对,但两处需修正:(a) 该基线实测 172KB 而非'70 行',且全部行同属单 case_slug,本身覆盖力单薄,不是值得照搬的强范式;(b) limit_per_size=1 是 evidence 跑法选择而非脚本默认(脚本 default=None),把样本提大只改调用参数即可,工作量比 M 小;expected_gain 无量化依据。risk 栏对 weighted SMTWT 不可比口径的提醒诚实。

15. [problem] slack/due_pressure 口径错位:窗口从『本工序就绪时刻』起算,剩余工时却用『整批总量』,上游工时被双计（GraphReadyV2 特征工程与权重 profile 族(optimizer_graph_ready* / sgs 图评分键)）
   修正：口径错位机制代码级确认:capacity_start_dt=start+ready_offset(features.py:62 区域,ready_offset 按批内上游工时累加),而 remaining_hours=_remaining_hours_by_batch 的整批总量(:95-97 区域),slack=due_budget-remaining(:112),窗口起点与剩余工时基准确实不一致,B 工序上游 10h 被双计的推导正确。但两点修正:1) 字段被同时写成 remaining_due_burden_hours(:126 区域),'整批负担'可能是有意的保守语义(把上游占用视为该工序的交期负担),是设计选择还是 bug 需要语义裁决,不能直接定缺陷;2) 报告自己承认无量化,危害方向(系统性高估深链批紧迫度)依赖跨批比较场景,单机同批场景影响为零。降级为机制确认、定性与量级待

16. [opportunity] 组合精简+重排:due-aware 公式前置,删掉代数冗余的 atc_like,v1 族收缩到 2-3 个代表（GraphReadyV2 特征工程与权重 profile 族(optimizer_graph_ready* / sgs 图评分键)）
   修正：核心事实(三赢家组合=全 19 组合、赢家排第 11/12/17 位、9 个 v1 近冗余)与其 wt40 实验自洽,重排 due-aware 前置、atc_like/CR 二选一的方向由 P1/P3 代码事实独立支撑,低风险。修正点:1) '同预算下有效候选密度 6 倍''gap 16.5→2.85'全部来自单一单机无前置基准(SMTWT/wt40),v1 图特征在该形态天然退化,外推到 precedence 丰富的生产形态证据不足——报告自己已承认需 JSP 基准复测,故 expected_gain 应标注'单基准实测,待 JSP 复核';2) 删 v1 收缩到 2-3 个代表在复核前只能重排不能删;3) 未核实 max_weight_profiles 生产截断值,若默认放不满 19 个,重排收益比所述更大。降为 adjusted:方向 confirmed,收益数字降级为待复核。

17. [opportunity] v2 容量 enrich 的日历策略记忆化:(日期,操作员) 粒度缓存 policy 查询（GraphReadyV2 特征工程与权重 profile 族(optimizer_graph_ready* / sgs 图评分键)）
   修正：逐日 walk 与机×员双层遍历结构属实(capacity.py:109-133, 324-367),同一 enrich 内 (日期,操作员,priority) 的 policy 查询确实重复。但三处需修正:1) '从秒级降到近常数'夸大——memo 只省 policy_for_datetime 查询本身,分段 overlap、max 聚合等仍在,且每 op 的 ready_offset 起点不同导致窗口不同,收益是常数因子而非数量级;2) 正确性依赖 policy 日粒度假设,报告已自知(walk 按 _next_calendar_day 步进可作旁证)但未验证 policy_for_datetime 是否日内班次级,若为班次级则日粒度 memo 会算错容量,这是 blocker 级前置确认而非附带风险;3) A15/A17 并发改 downtime/calendar,集成后实施的提示正

18. [opportunity] 按 (operator_id) 预计算扁平化'累计工时时间表',把 add_working_hours/adjust 从逐日循环降为二分查找+一次算术（日历引擎与算法交互(calendar_engine × SGS/槽位估算/v2容量)）
   修正：方向与证据成立,数字微调。实测瓶颈属实:日历占整趟 69.8%(我机复跑),policy 缓存命中 6,636,545/未命中 480,瓶颈确为逐日 datetime 循环而非 DB。累计工时物化表用 bisect+算术替代逐日循环是纯标准库方案,符合 py3.8/Win7/离线/零新依赖。但 expected_gain 40-55% 偏乐观:日历 25.1s 中含 get_eff 2.7s 与 adjust 5.6s,物化表主要吃掉 add_hours 的 16.8s,adjust 仍需保留入口语义,乐观估计整趟提速约 35-45%;且收益数字基于 SGS+slack 基准,生产默认 improve 路径未实测。risk 写得诚实(跨午夜/priority 跳日/shift_end/缓存生命周期都点了),对照测试要求正确。

19. [opportunity] 槽位估算单次尝试只取一次 DayPolicy:get_efficiency 与 add_working_hours 内部重复 policy 查询合并,并消除冗余 adjust（日历引擎与算法交互(calendar_engine × SGS/槽位估算/v2容量)）
   修正：机制确认但收益下调。冗余 adjust(约 104.6 万次)与 get_eff/add_hours 内重复 policy_for_datetime 属实;'已调整起点+已取 policy'的内部通道不改对外契约、语义不变,向后兼容要求正确(internal_slot 被 core/algorithms/greedy/auto_assign.py 与 internal_operation.py 使用——注意报告写的 dispatch/ 路径有误)。但 expected_gain 20-25% 偏乐观:研究员把 adjust 总耗时 5.6s 的大头算作可消除,本机实测 adjust 均耗仅 2.1us、总 2.3s,可消除的真实大头是 get_eff 的 policy 查询;实际整趟提速更可能 10-15%。且与机会1重叠——物化表落地后本条大部分被吸收,建议作为机会1的过渡步骤或并入。并

20. [opportunity] v2 残余容量逐日 policy 循环接入同一物化表,消除按段×按日的重复窗口解析（日历引擎与算法交互(calendar_engine × SGS/槽位估算/v2容量)）
   修正：代码事实确认:_calendar_capacity_hours(optimizer_graph_ready_v2_capacity.py:322-367)逐日 cursor 推进、每日 policy_for_datetime,4000 日 guard(:343)证实长区间逐日循环是已知痛点;接同一物化表后按段×按日解析可消除。expected_gain 明确标注'未单独实测',用主路径 69% 占比做旁证并自我降级,诚实。effort S 与'保持 _wall_hours×efficiency 分段语义不变'的约束正确;并发修复提示符合实际(该文件在 A 批修复清单中)。依赖机会1落地,单独看收益不确定,故为 adjusted 而非无条件 confirmed。

21. [opportunity] 给每次 SGS 构造加 forward-backward justification(FBI)后处理——文献中性价比最高的单点改进（文献对照与算法选型(SGS+优先规则+局搜 / OR-Tools 适用边界)）
   修正：方向成立:grep 全仓确认无 forward-backward/justification 任何实现,FBI 是 RCPSP 文献中证据最强的单点改进,Kolisch&Hartmann 的 3-8% 数字有出处。但需修正两点:1) 'FBI 只是再调两次 dispatch_sgs' 过于轻巧——本仓 SGS 深度耦合工作日历/停机时间轴(calendar_engine/downtime),反向趟需要时间镜像的可排程性计算,在日历不对称下不是简单重跑,effort M 偏乐观,实接近 M+;2) 3-8% 是 makespan 目标上的文献值,本仓目标是加权拖期+batch_order 空间,收益属外推,落地前必须用仓内 SMTWT 实例实测(可与已知 gap 6.8 的基线对比)。与 A 批并发修复(sgs.py/sgs_scoring.py)冲突的判断正确,必须等集成。

22. [opportunity] 把 GRASP 构造阶段的规则采样升级为'带偏随机化优先规则采样'(biased-randomized),替代纯组合枚举（文献对照与算法选型(SGS+优先规则+局搜 / OR-Tools 适用边界)）
   修正：基线描述有误,需修正:本仓 GRASP-IG 不是'纯组合枚举'——optimizer_grasp_ig_specs.py:46 用 rnd.sample 做随机化破坏-重建,:76/:88 用 rng_factory(seed 体系)注入多样性,随机化构造已存在。因此'biased-randomized 替代纯枚举'的真实增量是'在评分键上加保序扰动'这一窄点,2-5% 收益缺乏对本仓现状的对照依据(文献对照的是确定性多起点,不是已有随机化 IG),应降级为'待实测'。机制本身与 A13 正交、可复现性有 seed 体系支撑、无兼容问题,这些判断成立。

23. [opportunity] CP-SAT 窗口化 LNS 修复:冻结前缀不动,只对滑动关键窗内的批次做单机/双机 CP-SAT 重优化（文献对照与算法选型(SGS+优先规则+局搜 / OR-Tools 适用边界)）
   修正：分解式思路(启发式选邻域+精确修邻域)本身务实,复用 critical_chain/bottleneck_machine 邻域识别与 freeze_window 冻结边界的架构判断正确,'回写 batch_order 保持单一事实源'的约束意识好。但:1) '关键链 tardiness 改善 30-50% 集中在窗口内'无任何文献或实验支撑,属编造数字,应删除;2) '30-80 批窗口 1-3s 近最优'是单机加权拖期的经验外推,本仓窗内还带日历/停机约束,需实测;3) effort L + 与 freeze_window 并发修复冲突的判断诚实。综合:方向保留,收益数字降级为未知。

24. [opportunity] tie-break 体系显式化:平局序做成 profile 可配向量（SGS 主循环与评分架构(sgs.py / sgs_scoring.py / sgs_graph.py / batch_order.py / auto_assign.py 探针链)）
   修正：事实层核实属实:build_dispatch_key(dispatch_rules.py:41-95)中 SLACK/CR 主键确不含优先级权重(w 仅 ATC 用),tie-break 序为 changeover>pr_rank>time_left>batch_order>seq>op_id。但'未见任何文档声明为有意设计'略夸大——dispatch_rules.py 顶部 docstring 明写了 tie-break 顺序('优先避免换型 -> 更高优先级...'),即行为有文档记录;缺的是业务语义裁决(为何换型压过优先级)与测试声明,而非完全无文档。修正后成立:这是与 A06/A12/A13 同性质的语义决策项,研究员主张先立案再 A/B 走 ratchet 门禁(test_optimizer_benchmark_ratchet_gate.py 核实存在),路径正确,未直改、不违反

25. [opportunity] pair_rank 在资源池构建时一次性解析为 int,运行期纯 dict.get（端到端性能画像(SGS 派工主链路 + 优化器候选评估)）
   修正：方向对但落点选错,预期收益按当前写法不成立:_coerce_resource_pool 在 auto_assign.py:108 被 _choose_best_pair 的每次 attempt 调用(每候选评估一次),把 pair_rank 解析挪进这里只是把 63 万次 parse 平移(每次 attempt 解析全表 M×O≈80 项,与查 80 次同量级),净收益≈0。要拿到 ~5% 必须做跨 attempt 缓存:以 resource_pool 对象身份(id+弱引用或挂 ScheduleRunState)缓存已解析 pool,或把解析上提到 dispatch_sgs 入口处一次。effort 应从 S 上调到 S+/M-,风险仍低(报错时机提前是唯一行为差)。auto_assign*.py 并发修复中。

## 四、优化机会全景（评审 confirmed，按性价比分层）

1. ATC primary 改 log 形式：-(ln w - ln p - max(slack,0)/(k·avg_p))，消灭 exp 下溢并列（派工规则库（dispatch_rules / build_dispatch_key / 规则×图key 组合））
   理由：数学亲验：primary_new=-ln(atc)，-ln 与 -atc 同为 atc 的严格减函数，非下溢区严格保序成立；log 参数安全性亲读代码确认——p>0、avg_p>0 由 dispatch_rules.py:59-73 _safe_positive+回退链保证，w∈{1,2,3}（priority_constants.py:12），math.log 无定义域风险，py3.8/Win7 无兼容问题。测试风险声明亲核属实：全仓测试 grep 无对 primary 绝对值的 golden 断言，仅 tests/resource_dispatch/test_dispatch_rules_nonfinite_proc_hours_safe.py:47 断言 isfinite（log 形式对合法输入仍有限，兼容）、其余为相对序断言。与 A06 同文件（A06 定案在 :75-77 CR 

2. 解锁 ratchet 门禁：干净工作区重生成两个 tracked baseline + 重写锁死测试 + ratchet CLI 补脏拒写/--allow-dirty-proof 对称语义（基准与实验体系（算法质量回归门禁、基准覆盖面、性能基准固化））
   理由：机制完备性亲验：compare_to_baseline 的不劣化比较/候选计数/proof binding 全已实现(optimizer_benchmark_ratchet.py:43-59,107-238)；'亚秒级'实测成立(/usr/bin/time 整个 CLI 含 python 启动 real 0.20s)；两个 tracked baseline 均 dirty_worktree=true 核实(ratchet baseline:164、comparison baseline:27)；同文件 test_benchmark_ratchet_blocks_dirty_*(:53-72)确有可套用的合成 fixture 写法；roadmap item21 状态 in_progress 核实(roadmap.md:1058)。effort=S、risk(等 A 批集成+干净工作区)诚实，

3. 中门禁质量 ratchet：SMTWT 250 实例 gap 阈值化 + 确定性迭代预算替代 1s wall-clock（基准与实验体系（算法质量回归门禁、基准覆盖面、性能基准固化））
   理由：数字稳定性亲验：本人独立重跑全套(10 workers,~40s)得 sgs 16.16→6.82、improved 209/250(83.6%)、batch_order 15.40→10.78，与研究员报告逐位一致——同机跨 run 近乎确定，阈值(≤7.5/≥195)留有余量合理。预算公式核实：derive_iteration_limits(optimizer_candidate_profile.py:87)常量 FLOOR=200/CEILING=5000/PER_SECOND=20(:49-53)，budget=1 → max(200,min(5000,20))=200 属实；TIME_BUDGET=1 wall deadline 在 benchmark_smtwt_localsearch.py:50,:80。--tier choices 仅 ('light',)(benchmar

4. 扩 tiny oracle 案例族：从 1 个 2 工序案例扩到 ~10 个 ≤9 工序案例，覆盖 DAG/双机/三个未测目标/优先级混合（基准与实验体系（算法质量回归门禁、基准覆盖面、性能基准固化））
   理由：关键前提全部亲验：build_default_tiny_cases 确仅 1 个 2 工序单机案例(optimizer_proof_cases.py:43-77)；run_optimizer_proof_harness 支持传自定义 cases(optimizer_proof_harness.py:43-48)；oracle 能力实测——6 工序 min_changeover 案例 build_tiny_case_reference 全程 33-37ms 即 proven_optimal，且立刻暴露 greedy 3 vs 最优 1(gap 200%)的目标盲区，印证'新案例必然暴露非最优、必须用 ratchet 语义而非 require_optimal'这条 risk 是诚实且必要的(当前 ratchet 快照在 optimizer_benchmark_ratchet.py:26 写死 

5. 性能基准固化：大池基准扩成规模系列，estimate_calls 等确定性计数严格 ratchet + 耗时宽容差告警（基准与实验体系（算法质量回归门禁、基准覆盖面、性能基准固化））
   理由：基础设施核实：estimate_calls 计数机制已实现(benchmark_sgs_large_resource_pool.py:92-106 mock 包装四处 import 点)；比较机制可复用(optimizer_benchmark_ratchet.py 的 _int_metric_* 族)；现有案例确实只排 1 个工序、无法压出复杂度信号。D13/sgs_graph 两次教训引用核实(audits/2026-07-19-full-defect-sweep/index.md:228,:191)。一处口径修正写入采纳前提：计数通道对 D13 这类'函数内字典全扫'型 O(V²) 回归是盲的——那段环检测不调 estimate_internal_slot，计数零变化；能抓住 58-120x 量级回归的其实是宽容差 wall-time 告警通道(固定开发机上 1.5-2x 容差足以红 

6. 图路径补一层围绕 incumbent 的迭代搜索(profile 权重扰动重启)（局部搜索 / GRASP-IG(optimizer_local_search*、optimizer_grasp_ig_*、optimizer_neighborhood_*、optimizer_vns、optimizer_acceptance、optimizer_graph_ready 候选相位)）
   理由：思路成立且是 problems#1 的对症最小侵入解:权重空间 ILS 不动 SGS 解码器,jitter_seed 确定性机制已存在可复用。effort=M 与'必须走 GraphReadyWeightProfile 校验、等 A 批集成后动手'的风险声明诚实。两处保留:(1) '文献依据(talon 权重扰动之于 ATC 调参)'写得含糊,未给具体文献,支撑偏弱;(2) expected_gain 拿遗留路径 gap 16→6.8 类比图路径是跨路径外推,报告自己标了'需实测',可接受但验收时必须落 250 实例基准数据才算数。无新依赖、不违反 Win7/py3.8。

7. IG 改贪婪重插 + 真迭代主循环(与机会#2 配套)（局部搜索 / GRASP-IG(optimizer_local_search*、optimizer_grasp_ig_*、optimizer_neighborhood_*、optimizer_vns、optimizer_acceptance、optimizer_graph_ready 候选相位)）
   理由：与 problems#2 证据链一致,Ruiz & Stützle 2007 文献引用真实恰当(IG for PFSP 确实依赖贪婪重插+增量评估)。风险声明诚实:'必须落在 #2 之后或用 destruction_size+候选位封顶''生产路径被跳过、需先解 problems#1'两点都是真约束,无夸大。expected_gain 的 -20% 明确标注是合成基准、真实基准需实测,符合证据纪律。无依赖/兼容性冲突。

8. 邻域扩容 + best-of-neighborhood:swap、任意位置 insert、tardy 批次对交换（局部搜索 / GRASP-IG(optimizer_local_search*、optimizer_grasp_ig_*、optimizer_neighborhood_*、optimizer_vns、optimizer_acceptance、optimizer_graph_ready 候选相位)）
   理由：与 problems#3 直接对应,insert-to-best + swap 是 PFSP 局搜标配,文献方向正确。风险声明诚实:best-of-neighborhood 翻倍解码次数需配 #2、VnsState 语义要扩展、sgs.py 并发冲突已标注。'把达最优率从 ~18% 再抬一截'有(需实测)限定,可接受。唯一小瑕疵:'item9-13 修复史部分收益来自邻域修复'与 memory 记录一致但属历史类比,非新证据——不影响结论。effort=M 合理。

9. 邻域自适应选择:按近期成功率加权替代 round-robin（局部搜索 / GRASP-IG(optimizer_local_search*、optimizer_grasp_ig_*、optimizer_neighborhood_*、optimizer_vns、optimizer_acceptance、optimizer_graph_ready 候选相位)）
   理由：成立。亲验 optimizer_local_search.py 走 round-robin choose_neighborhood_move,VnsState 已有 noop/fallback/improved 计数可作 AOS 原料;确定性有 rng_factory 播种 rnd 保障,报告也要求纳入 search_report 留痕,符合审计链纪律。'AOS 相对均匀选择 5-15%'是文献常见区间但未给具体出处,属弱引用,可接受为方向性依据。effort=S 诚实,无约束冲突。建议排在 #7 之后做(接受准则变化会改变各邻域成功率口径,先定口径再自适应)。

10. 接受准则默认从 improve_only 换 record_to_record/threshold,或随进度自适应（局部搜索 / GRASP-IG(optimizer_local_search*、optimizer_grasp_ig_*、optimizer_neighborhood_*、optimizer_vns、optimizer_acceptance、optimizer_graph_ready 候选相位)）
   理由：亲验属实:optimizer_candidate_profile.py:288 默认 acceptance='improve_only',optimizer_acceptance.py:11-16 四种准则均已在 ALLOWED_ACCEPTANCES 白名单且经校验,即代码已备好只是默认没切。报告正确识别了两个前置:(1) A13(接受准则量纲)正在等语义决策,threshold 量纲与 score 元组分量匹配问题必须先裁决;(2) restart 后 current 已被真实解码对齐,接受差解的三元组一致性前提具备。effort=S(在 A13 落地后)合理。无夸大,依赖关系标注清楚,是与现有决策项衔接最干净的一条。

11. 解码前按 graph_priority_key 映射哈希精确去重（评估函数与目标体系(evaluation.py / objective.py / candidate_eval 链 / best_metrics 流转)）
   理由：context_for_profile(optimizer_graph_ready_candidates.py:111-132)证实 key 映射是 (metrics, profile) 的确定函数,SGS 解码对相同 (key 映射, seed, rule, context) 确定产出同排程,预去重无损。研究员自己给出的风险(哈希键漏解码输入)与缓解(测试锁'同 key 必同结果'合同)正确且必要——当前 decode 输入还含 downtime_map/seed_sr_list/readiness_gate 等,哈希构造必须枚举全。~11% 是保守实测下限,effort S 属实。与机会 1 可叠加且应先做(S 先于 M)。

12. 反模式备案:不为 compute_metrics/指纹做缓存（评估函数与目标体系(evaluation.py / objective.py / candidate_eval 链 / best_metrics 流转)）
   理由：compute_metrics(evaluation.py:132)确为单遍 O(n)+每机排序,相对 SGS 全量解码可忽略,成本结构与代码阅读一致(0.2%/0.3% 数字来自实测,方向无疑)。纯 cs-learn 文档沉淀零风险,能防止后续工兵重复立案,确认。

13. search_report 加同分 plateau 计数为 A13 决策供数据（评估函数与目标体系(evaluation.py / objective.py / candidate_eval 链 / best_metrics 流转)）
   理由：字典序纯键序(objective.py:17-44)与 score 首位 failed_ops 属实,'首键打平时后键严格更优才算改进'的比较语义与 candidate_is_preferred 严格小于一致。在 A13(接受准则量纲)挂起期间只加观测计数、不改行为,完全符合'语义决策前不动接受准则'的纪律,且产出正是决策最缺的本仓库分布数据。effort S、风险极低,确认。

14. 把 runtime_ms 纳入 ratchet 比较或为大资源池性能脚本建宽松耗时棘轮（基准与实验体系(算法质量基准 / 回归棘轮 / 性能基准)）
   理由：建议锁相对比率或 estimate_internal_slot 确定性调用次数是诚实且工程上正确的(大资源池脚本已 mock 包裹估算器计数,基础设施现成);无实验数字属合理定性;risk 栏对绝对耗时误报与干净基线前置的披露诚实;无依赖/兼容性冲突。本批机会类中证据与风险披露最平衡的一条。

15. 把 medium gate --run 接进 long-gate 清单(非 daily)（基准与实验体系(算法质量基准 / 回归棘轮 / 性能基准)）
   理由：接入成本确实极低(medium gate --run 现成、long_gate_candidate 机制现成),分层进 long-gate 而非 daily 与 memory 中门禁分层约定一致;expected_gain 为机制性收益无数字属合理;risk 栏诚实(时长上升、需 A 批后跑通)。

16. 落地 RCPSP j30 资源受限基准:补 case builder+grading（基准与实验体系(算法质量基准 / 回归棘轮 / 性能基准)）
   理由：数据/LB 函数确实 vendored 且零消费,补多机资源受限外部参照的结构性盲区判断成立;risk 栏对 RCPSP→APS 语义映射失真与 CP-LB 松下界的披露诚实,'排在 O1-O4 之后'的优先级自觉也对。effort=L 与 expected_gain 均为定性无实验,属探索性机会,按此口径接受。

17. 解码前按『induced 排序结构』去重 profile,重复排序不再花全量 SGS 解码（GraphReadyV2 特征工程与权重 profile 族(optimizer_graph_ready* / sgs 图评分键)）
   理由：前提核实:解码确定性成立(同一静态 graph key 全序+同一 SGS),现状确为先解码后指纹去重(optimizer_graph_ready.py:289, 412-424),循环顶按 key 映射 tie-group 序列去重可跳过必然相同的候选,O(N logN) 纯字典序比较,无行为风险。19→约 7 的收益与其 6.9 个不同排程的实测自洽。两点补充(不否决):1) 去重键必须含 jitter 等全部 tuple 分量,否则 micro_perturbation 会被误并;2) 与 A02/A04 并发改 sgs.py 的冲突提示诚实,集成后实施正确。effort S、风险极低属实。

18. 静态图键与动态派工键融合:引入真正时间依赖的 ATC 公式(v3)（GraphReadyV2 特征工程与权重 profile 族(optimizer_graph_ready* / sgs 图评分键)）
   理由：现状核实:graph key 确实整体插在 score_penalty 之后、动态派工键之前(sgs_scoring.py:74-75 with_graph_priority_key 拼 base_key[:1]+graph_key+base_key[1:]),静态 profile 一旦选定即压制含 est_start 的动态 slack/ATC/CR,属实。ATC/BATC 文献方向(Vepsalainen&Morton 1987)是排产领域公认结论,引用恰当。报告诚实:无收益数字('量化需 A/B')、自挂 A06/A12/A13 语义裁决之后、承认单机实验中动态/静态 slack 简并。effort M 合理(改评分语义+回归)。无约束冲突。这是方向性 confirmed 而非收益 confirmed,报告措辞本身也如此,故维持 confirmed。

19. 拥挤感知的 saveability/due_pressure:用瓶颈窗口内竞争工作量修正本批口径（GraphReadyV2 特征工程与权重 profile 族(optimizer_graph_ready* / sgs 图评分键)）
   理由：对症:P2 的饱和机制代码级确认,修正方向(用候选机台集合 due 窗口内竞争工时/residual capacity 作系数)所需输入(duration_by_op_id、candidate_machine_ids、residual_capacity_hours)确已在 enrich 流程内存在(features.py:126-140 区域的 capacity dict 与 duration 汇总),无新数据依赖、无新依赖。报告诚实标注 clamp 阈值(0.70 长尾)需重调、特征合同测试需同步、收益需基准复测,无量化吹嘘。effort M、O(N×M) 聚合成本评估合理。Win7/py3.8/离线兼容。

20. 用 rank01 加权和公式族替代纯字典序,打开连续可自适应的 profile 空间(基础设施已就位但闲置)（GraphReadyV2 特征工程与权重 profile 族(optimizer_graph_ready* / sgs 图评分键)）
   理由：关键洞察代码级确认:rank01 是严格保序变换(_rank01_by_op_id,candidates.py:243-256),而 10 个 v2 公式全部消费 *_rank01 字段做字典序 tuple(:269-305),归一对选择结果确为 no-op;唯一跨特征聚合 graph_bonus 在 raw 尺度(:196 区域)继承 P5 失衡——两处指控都重读属实。rank01 恰好提供 [0,1] 可比尺度,w·rank 加权族+坐标扰动是『profile 参数自适应』的合理落点,且能顺带治 P6 死 jitter(rank+ε·jitter 真扰动)。jitter 已是确定性整数散列(_seeded_jitter :258-266),锁定种子可复现;新 formula_slug 走现有 ValidationError 合同、老公式不动,回退安全。'连续权重空间可继续下探 2.85

21. 统一效率口径:要么槽位估算也做分段效率积分,要么 v2 容量改用同一近似并在文档钉住'单点近似是 by-design'（日历引擎与算法交互(calendar_engine × SGS/槽位估算/v2容量)）
   理由：问题基础已亲验(4h 分歧复现)。研究员正确地把它定性为语义决策而非纯工程,与 A06/A12/A13 的处理方式一致(走 cs-decide 立案),没有越权拍板;两个方向(分段积分/钉住单点 by-design)的取舍与风险(改变既有排产结果需回归基线)都写清楚了。与机会1的耦合(累计表存 eff 加权工时则分段积分零额外循环)是正确洞察。effort M 合理。

22. OR-Tools 预热从'单一瓶颈工种'扩展为 top-k 瓶颈分解+AddHint 现任职解,按需串行求 2-3 个工种（文献对照与算法选型(SGS+优先规则+局搜 / OR-Tools 适用边界)）
   理由：成立且与 problem#1/#2 形成闭环修复:top-k 归一化直接消除已确认的瓶颈误判,AddHint 在 ortools 9.x(py3.8 封顶 9.8.3296)API 可用属实,arXiv:2403.16766 的 ~40% 求解时间下降有文献出处。worker 数改 min(os.cpu_count(), cfg) 与 problem#1 是同一处,应合并落地。修正点:ortools_bottleneck.py 不在 A 批并发修复清单内,落地无冲突;但所有收益以'用户显式开启可选预热'为前提,实际覆盖面受 ortools_enabled 默认 off 限制,expected_gain 的可达性需打折说明。

23. 用已完成排产历史做超轻量'规则选择器',替代 learning-to-dispatch 的重模型路线（文献对照与算法选型(SGS+优先规则+局搜 / OR-Tools 适用边界)）
   理由：成立:algorithm selection(Rice 框架)路线对单机离线 py3.8 现实,拒绝 learning-to-dispatch 重模型的判断正确;两侧数据基础属实——v2_features 已是实例特征、algo_stats 已记录 run 级规则与目标值,'差的只是离线拟合+查表'的差距评估准确。2-6% 标注了'文献典型值'属诚实外推,非编造;对 item6/7/8 作用点错位'把调旋钮变成选实例适配组合'的根治方向论述与已有裁决不冲突。effort L、样本偏差风险、与 GraphReadyV2 profile 族职责边界的提示均诚实。落地建议作为独立增强排在 FBI 之后。

24. SGS 增量评分缓存:op 级 key 缓存 + 读集失效规则（SGS 主循环与评分架构(sgs.py / sgs_scoring.py / sgs_graph.py / batch_order.py / auto_assign.py 探针链)）
   理由：机制亲验成立:评分读集=批次 prev_end/机台 timeline·busy_hours·last_op_type/人员 timeline·busy_hours,失效规则'同批∪机台池∪人员池'在实测两类实例 0 违例(88-92% key 本就逐轮不变,缓存命中 76-79% 与冗余率自洽)。byte-identical 原型存在(/tmp/sgs_cache_prototype.py),ready_queue 差分 oracle 先例属实。风险披露诚实(失败事件清缓存未在含失败实例验证、图模式需专项差分、ValidationError 不缓存)、明确等 A 批集成后落地,不冲突。收益数字全部有实测支撑,非拍脑袋。effort M 合理。纯 dict/set,py3.8/Win7/离线/零依赖全合规。

25. pair 级槽位估算缓存:按资源版本号精确失效（SGS 主循环与评分架构(sgs.py / sgs_scoring.py / sgs_graph.py / batch_order.py / auto_assign.py 探针链)）
   理由：92% 探针占比与 824 次/工序的实测基数复核一致;版本号失效(pair 命中 82-85% vs op 级 33-34%)与实测失效模式自洽。风险披露尤其诚实:核实 auto_assign.py:303 确以 abort_after=best[0] 做剪枝,缓存复用必须关闭该剪枝否则估算依赖扫描顺序——这是本机会最容易翻车的点,研究员主动点破且实测净赢。InternalSlotEstimate frozen、内存量级、失败清空、A15/A18 并发依赖声明均如实。预期 3.8×@500/4.5×@1000 有原型实测,可信。

26. winner 结果直通:探针估算随候选传递,收敛四段重算（SGS 主循环与评分架构(sgs.py / sgs_scoring.py / sgs_graph.py / batch_order.py / auto_assign.py 探针链)）
   理由：与 P2 修复对应,四段收敛为一段的结构面清晰;algo_stats 计数语义风险(internal_auto_assign_attempt/success/failed 在放置时计数、有测试锁)核实属实——跳过重探针必须显式补计,这是本机会唯一实质风险,研究员已点名。effort S 合理,~8% 估算量节省与 P2 实测口径(6.1%+1.8%)一致,主要收益实为消灭评分/放置双路漂移面,定位诚实。

27. #53 修法建议:候选静态 meta 预计算（SGS 主循环与评分架构(sgs.py / sgs_scoring.py / sgs_graph.py / batch_order.py / auto_assign.py 探针链)）
   理由：#53 系已登记问题,此处仅给修法,定位正确。_candidate_meta 中 priority/due_date/seq/op_id 静态、仅 prev_end 动态的判断与代码相符;_group_sgs_ops 预计算点合理。strict/非 strict 日期解析语义分叉(sgs_scoring.py:34-35)的风险提示必要且准确。10% 为 cProfile 实测占比,effort S、风险极低,成立。注:O1 落地后本项收益被覆盖,研究员已自行声明该关系。

28. 小项:图模式候选每轮 sort_key 排序是无效功（SGS 主循环与评分架构(sgs.py / sgs_scoring.py / sgs_graph.py / batch_order.py / auto_assign.py 探针链)）
   理由：事实核实:sgs_graph.py:319 每轮 sorted(ready_op_ids, key=sort_key) 存在;评分 key 以 op_id 收尾必唯一(dispatch_rules.py:94),min() 与输入序无关,排序对排程结果确零影响(仅影响 ValidationError 抛出顺序)。研究员对收益(<2%)和定位(不值得单动、O1 落地顺带收编)的判断克制且诚实,报错工序顺序漂移的风险提示也正确。成立。

29. SGS 跨轮 estimate memo:按 (op.id, machine, operator, prev_end, base_time, 时间轴len版本, end_dt, last_op_type) 缓存 estimate,abort_after 移到用点判断（端到端性能画像(SGS 派工主链路 + 优化器候选评估)）
   理由：本机复跑 memo 实验完全复现:400ops 9.7s→2.8s(3.4x)、命中率 90.9%、schedule 逐字段与基线一致、确定性成立。语义等价性核实:internal_slot.py:212-222 _abort_after_result 只依赖 earliest,避让循环 earliest 单调右移(:320-348),abort_after=None 算一次+用点比较 start_time 等价成立;abort 结果携带的 efficiency_fallback_used 可从缓存的成功结果带出。风险评级诚实(键含时间轴 len 版本、op.id、等 A 批集成)。补充两点报告未写明:缓存 dict 需挂 ScheduleRunState 生命周期防跨排产泄漏;内存上界未估算(1200ops 键量约 ops×M×O 去重后 ~misses 数,量级可控但应写明)。1200

30. SegmentOverlapIndex 按轮复用:以时间轴对象身份+len 为键缓存索引(或把索引挂到 ScheduleRunState 的时间轴旁)（端到端性能画像(SGS 派工主链路 + 优化器候选评估)）
   理由：复跑实验确认单独 ~11.5%(9.65→8.54s)、结果一致。'索引绝不修改输入'与 downtime.py 只读契约一致;id() 裸键风险提醒正确。与 memo 叠加后收益缩到 miss 路径的判断合理(memo 命中时根本不建索引)。effort S、风险低-中诚实。注意 internal_slot.py A 批并发修复中。

31. 优化器候选评估并行化:不推荐走多进程,优先吃 memo 红利（端到端性能画像(SGS 派工主链路 + 优化器候选评估)）
   理由：论证链全部核实:calendar_engine.py:81 CalendarEngine.__init__ 持有 sqlite conn,GreedyScheduler 经日历不可 pickle 成立;Win7+py3.8 冻结 exe 下 multiprocessing 只能 spawn+freeze_support 的约束正确;tests/_support/benchmark_parallel.py 确实存在但仅是测试脚本,不能佐证生产可行;'并行改变候选选取顺序破坏可复现合同'是关键论点,与 APS 可复现/可追溯原则直接冲突。结论'不做、优先吃 memo 红利'判断正确且与机会1形成合理优先级。effort L/风险高评级诚实。

## 五、被评审否决（一行一条，防重复提）

1. last_end_by_machine 是只写状态:core 内无读取方（增量排产:seed 续排、freeze_window 冻结、batch_order_override）：事实错误。runtime_state.py:41 `prev_end = last_end_by_machine.get(machine_id)` 就是读取方,且 :47/:56 的写入以该读取为守卫——这正是 A16 修复的本体:last_end 是决定 last_op_type 是否允许覆盖的守卫键,删掉或忽视它,A16 防的'gap 回填把 (end,type) 快照改成自相矛盾状态'即刻回

2. DayPolicy.work_window 的 datetime 对缓存进 DayPolicy 构建时一次算好（端到端性能画像(SGS 派工主链路 + 优化器候选评估)）：前提过时:calendar_engine.py:60-68 DayPolicy.work_window 已用 _window_start/_window_end 做记忆化,'每次重建两个 datetime'不成立;_policy_cache 也已按 (op_id, date_str) 缓存 DayPolicy(:169-178),建议的'构建时预存 start/end'大部分已实现。残余可优化点仅

## 六、建议落地顺序

结合当前 A 批修复与 A06/A12/A13 待决策，建议：
1. **先做**：A 批修复已落地的 A02/A04/A09/A03/A10/A05/A11/A07/A14/A15/A16/A17/A18/A01/A08 之外，本报告新增的高性价比优化机会（见第四节，评审 confirmed 且 effort=S 的）。
2. **再做**：A06/A12/A13 语义决策拍板后按选项落地；本报告中 adjusted 的口径修正项。
3. **长期**：benchmark-tooling 领域提出的算法质量回归门禁（需先补齐基准覆盖面，离线约束下）；local-search 领域提出的关键路径导向邻域/块移动（需 SMTWT 基准对比验证）。

## 运行档案

- Workflow：runId wf_db8f9dd8-b33；journal 见会话目录 subagents/workflows/wf_db8f9dd8-b33/journal.jsonl。
- 用量：22 agents / 1.04M subagent tokens / 412 tool uses / 58.6 分钟；2 个研究员（perf-architecture 两次断流后补跑成功、dispatch-rules 断流）、1 个评审员（resource-model 断流）经补跑/主会话整合。
- 问题清单规模：38 条评审 confirmed 问题（按严重度排）、25 条 adjusted、2 条 rejected；resource-model 领域报告已交但未经对抗评审（标注『未评审』）。
