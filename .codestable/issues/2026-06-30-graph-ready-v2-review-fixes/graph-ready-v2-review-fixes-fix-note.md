---
doc_type: issue-fix
issue: 2026-06-30-graph-ready-v2-review-fixes
path: fast-track
fix_date: 2026-06-30
status: completed
severity: P1
tags:
  - scheduler
  - optimizer
  - graph-ready
  - candidate-generation
---

# GraphReady v2 候选生成审查问题修复记录

## 问题

对未提交的 GraphReady v2 候选生成改动做复核后,确认存在几类问题:

- 批次 `due_date` 业务上允许为空,但 v2 特征生成把空交期当成前置失败,导致生产候选池整池退回 v1。
- strict mode 没有传入 v2 profile 解析链路,未来如果 v2 前置失败被吞掉,外层严格模式拿不到错误。
- v2 跳过只写 candidate profile 摘要,没有 rejected attempt 和 candidate rejection 计数。
- 多个 v2 公式共享 `sacrifice_penalty` 首键,基准 ready 排序多样性不足。
- 内制工时、外协自然日和交期自然小时在 slack / pressure / ratio 里直接混用,缺少明确的追交预算口径。
- 容量扫描里有一条不可达的分钟级兜底分支。
- roadmap 指向的两个 feature 目录不存在,且 objective feature notes 曾删掉“不允许静默退化”合同。

## 修复

- `optimizer_graph_ready_v2_features.py`
  - 空交期改为合法 no-due 特征,不再抛 `graph_ready_v2_missing_due_date`。
  - no-due 工序设置低交期压力、低可救性、高牺牲惩罚,让交期型公式自然后置。
  - 非空但解析失败的交期一律报 `graph_ready_v2_bad_due_date`。
  - 新增 `due_budget_hours` 和 `remaining_due_burden_hours`;内制工序有日历时用**窗口产能小时(毛,未扣占用)**作为追交预算,外协继续用自然小时。(口径:刻意用毛而非净残余,经毛/净基准对比确认净无稳定收益,详见 `.codestable/compound/2026-06-30-due-budget-window-vs-residual/`。)
- `optimizer_graph_ready_profile_selection.py` / `optimizer_graph_ready.py`
  - strict mode 传入 v2 profile 解析链路。
  - 未来如 v2 pool 真被跳过,记录 rejected attempt 和 candidate rejection。
- `optimizer_graph_ready_candidates.py`
  - v2 排序归一化纳入 `due_budget_hours`、`remaining_due_burden_hours`。
  - 调整 ATC-like、saveability、graph_due_hybrid、bottleneck_due_gated 等公式首键,减少候选排序坍缩。
- `optimizer_public_search_report.py`
  - profile diagnostics 带出 v2 skip 状态和原因。
- `optimizer_graph_ready_v2_capacity.py`
  - 删除已证明不可达的分钟级兜底分支,保留 4000 次安全循环上限。
- CodeStable
  - 恢复 roadmap notes 中“不允许空交期导致 v2 静默退化成 v1 成功”的合同。
  - 补齐两个 roadmap done feature 的验收落档。
  - 更新 scheduler 架构文档,把 GraphReady v2 从未来合同改成当前生产候选池现状。

## 验证

- `python3 -m pytest tests/algorithm/test_optimizer_graph_ready_candidate_contract.py -q`
  - 结果: `58 passed`
- `python3 -m pytest tests/algorithm/test_optimizer_graph_ready_candidate_contract.py tests/algorithm/test_optimizer_candidate_profile_contract.py -q`
  - 结果: `82 passed`
- `python3 -m ruff check core/services/scheduler/run/optimizer_graph_ready_v2_features.py core/services/scheduler/run/optimizer_graph_ready_candidates.py core/services/scheduler/run/optimizer_graph_ready_profile_selection.py core/services/scheduler/run/optimizer_graph_ready.py core/services/scheduler/run/optimizer_graph_ready_v2_capacity.py core/services/scheduler/summary/optimizer_public_search_report.py tests/algorithm/test_optimizer_graph_ready_candidate_contract.py`
  - 结果: `All checks passed`

## 遗留边界

- 当前工作区在修复前已经有其它未提交改动,所以本记录不声明 clean-worktree proof。
- GraphReady v2 的 elite local repair 和全局 portfolio integration 仍是 roadmap 后续 in-progress 项,本次只修候选生成和审计合同。

## 复审追加清理(2026-06-30)

二次对抗复审发现:上一轮把空交期改成 per-op 占位降级后,`graph_ready_v2_missing_due_date` 已无任何产生点,导致整条 "v2-pool skip" 防御链变成不可达死代码(coverage 实测 `optimizer_graph_ready_profile_selection.py` 回退体 0 覆盖)。按"不过度防御、不静默兜底"原则清理:

- `optimizer_graph_ready_profile_selection.py`:删 `resolve_*` / `_metrics_for_profiles` 的 `strict_mode` 死参数、try/except 整池回退、`_is_v2_precondition_skip`、`_profile_summary_with_v2_skipped`;v2 特征异常直接上抛由 `run_graph_ready_candidates` 主链统一按 strict / feature-error 处理。
- `optimizer_graph_ready_v2_features.py`:删 `enrich_graph_ready_v2_metrics` / `_due_exclusive_datetime` / `_parse_due_day` 的穿透未消费 `strict_mode` 参数(空交期 per-op 降级、非空非法交期 `graph_ready_v2_bad_due_date` fail-loud 的行为不变)。
- `optimizer_graph_ready.py`:删 `_record_v2_pool_skip_if_any` 及其调用、resolve 调用处的 `strict_mode` 传参(主链 except 对 v2 feature 错误 fail-loud,其它可选图上下文错误仍按候选拒绝记录)。
- `optimizer_public_search_report.py`:删恒不产生的 `v2_status` / `v2_skip_reason` / `v2_skip_message` public 投影。
- 删对应测试 `test_graph_ready_v2_public_projection_keeps_skip_diagnostics_when_present`(测的是已移除的投影能力);保留 `assert "v2_status" not in graph_profile` 作为"正常路径不跳过"回归保护。

语义收敛为"v2 候选要么成功生成、要么 fail-loud",无中间 skip 态;`due_date` 合法可空的 per-op 降级行为不变。

验证:`python3 -m pytest tests/algorithm/` → `498 passed`;两个合同测试 `81 passed`(原 82,减去删掉的投影测试);`ruff check` 改动文件 `All checks passed`。工作区修复前已有其它未提交改动,不声明 clean-worktree proof。

## 对抗复核后追加修复(2026-06-30)

第三轮对抗复核确认前一版仍有几处生产可达问题,本次继续收口:

- `optimizer_graph_ready_v2_features.py`
  - `strict_mode` 重新传入 v2 特征层后又经复核收紧:空 `due_date` 仍按 no-due 占位继续生成候选;非空非法 `due_date` 与 strict 无关,一律抛 `graph_ready_v2_bad_due_date`。
  - merged 外协组按 `(batch_id, ext_group_id)` 只计一次 `ext_group_total_days`,组内工序共享 ready offset,后续工序只推进一次组总时长。
  - 容量特征新增 `resource_candidate_machine_count` / `effective_candidate_machine_count` / `bottleneck_machine_count`,避免无人员机器稀释瓶颈压力。
- `optimizer_graph_ready_v2_capacity.py`
  - `candidate_machine_count` 改为真实可用候选机器数;原始资源候选数单独写 `resource_candidate_machine_count`;全无可用人员时保留高容量压力,但可用候选机器数为 0。
- `optimizer_graph_ready_candidates.py` / `optimizer_candidate_fingerprint.py`
  - 删除 `due_budget_hours -> due_deadline_hours`、`remaining_due_burden_hours -> remaining_work_hours` 两条死回退,缺字段直接 fail-loud。
  - GraphReady 候选同时记录 `decision_batch_order` 与 `decoded_batch_order`;候选 `order` 改为正式排程结果推导顺序,未排批次按构造顺序追加。
  - 候选指纹优先使用 `decision_batch_order`,避免把展示用结果顺序误算成构造决策。
  - v2 rank01 归一化增加显式缓存:11 个 profile 无关排序值只算一次,`graph_bonus`、jitter 和最终 priority key 仍逐 profile 计算。
- `optimizer_graph_ready_profile_selection.py` / `optimizer_graph_ready.py`
  - `strict_mode` 从 GraphReady 主链传到 v2 profile 解析和特征 enrich 链路。
- CodeStable roadmap
  - 将“默认候选量控制在 20-60”改为“默认 GraphReady 候选 profile 为 19 个;若把 baseline 也算入 evaluated_candidates,常见展示为 20;配置上限仍为 60”。

新增/调整合同覆盖:

- 空交期不拖垮 GraphReady v2;非空坏交期在非严格和严格模式下都报错。
- merged 外协组 remaining work 与 ready offset 不重复计组总周期。
- 无人员机器不进入有效候选机器数,也不稀释瓶颈压力。
- v2 必需字段缺失不再静默回退。
- 缓存后的 v2 priority key 与未缓存路径完全一致。
- GraphReady 候选载荷分离构造顺序与正式结果顺序。

验证:

- `python3 -m pytest tests/algorithm/test_optimizer_graph_ready_candidate_contract.py -q`
  - 结果: `67 passed`
- `python3 -m pytest tests/algorithm/test_optimizer_graph_ready_candidate_contract.py tests/algorithm/test_optimizer_candidate_profile_contract.py -q`
  - 结果: `91 passed`
- `python3 -m pytest tests/algorithm/test_optimizer_public_summary_projection_contract.py tests/candidate/test_scheduler_candidate_runner_contract.py -q`
  - 结果: `23 passed`
- `python3 -m pytest tests/algorithm/test_optimizer_candidate_fingerprint_contract.py tests/algorithm/test_optimizer_business_neighborhood_registry_contract.py tests/algorithm/test_optimizer_vns_sa_local_search_contract.py -q`
  - 结果: `38 passed`
- `python3 -m pytest tests/algorithm/ -q`
  - 结果: `508 passed, 30 warnings`
- `python3 -m ruff check core/services/scheduler/run/optimizer_graph_ready_v2_features.py core/services/scheduler/run/optimizer_graph_ready_v2_capacity.py core/services/scheduler/run/optimizer_graph_ready_profile_selection.py core/services/scheduler/run/optimizer_graph_ready.py core/services/scheduler/run/optimizer_graph_ready_candidates.py core/services/scheduler/run/optimizer_candidate_fingerprint.py tests/algorithm/test_optimizer_graph_ready_candidate_contract.py`
  - 结果: `All checks passed`

遗留说明:本轮仍在既有 dirty worktree 上定点修复,不声明 clean-worktree proof。

## 五项优先级修复收口(2026-06-30)

对抗复核后确认五个优先级均需要收口。本轮按“生产合同优先,证明材料其次,人工脚本最后”的顺序修复:

- `optimizer_graph_ready_v2_features.py`:非空非法 `due_date` 与 `strict_mode` 无关,一律抛 `graph_ready_v2_bad_due_date`;空交期仍保留 no-due 占位,避免把合法空值和脏值混成一类。
- `optimizer_graph_ready_v2_capacity.py`:日历 `policy_for_datetime` 的旧接口兼容不再裸捕获所有 `TypeError`;只有确认旧接口不支持 `operator_id` 时才去掉参数重试,函数内部真实 `TypeError` 继续暴露。
- `optimizer_graph_ready.py`:GraphReady 内部候选策略配置错误(`graph_ready_candidate_policy` / `graph_ready_bad_candidate_policy`)在非严格模式下也 fail-loud,不再包装成普通候选 rejected。
- `optimizer_benchmark_ratchet.py`:轻量 ratchet 比较读取 actual/baseline 的 `dirty_worktree`,脏工作区证据返回 `failed` + `proof_binding_status=unbound_dirty_worktree`,不能再显示为通过。
- `benchmark_smtwt_localsearch.py` / `benchmark_optimizer_long_run.py`:人工 benchmark 脚本只要存在失败样本或 payload status failed,进程退出码即为非 0;`benchmark_optimizer_medium_gate.py` 继续复用子命令退出码判断。

新增/调整合同覆盖:

- 非空坏交期在非严格特征 enrich 和生产 GraphReady 候选链路都 fail-loud。
- 空交期仍保留 no-due 占位并后置,不误伤合法空值。
- 旧日历签名仍可运行,但日历函数内部 `TypeError` 不被静默重试吞掉。
- 非严格模式下 GraphReady 候选策略配置错直接抛错。
- dirty actual / dirty baseline 的轻量 ratchet 比较和 CLI 均失败。
- SMTWT 部分样本失败、long run payload failed 均返回非 0。

验证:

- `.venv/bin/python -m pytest tests/algorithm/test_optimizer_graph_ready_candidate_contract.py -q`
  - 结果: `70 passed`
- `.venv/bin/python -m pytest tests/algorithm/test_optimizer_benchmark_ratchet_gate.py -q`
  - 结果: `11 passed`
- `.venv/bin/python -m pytest tests/algorithm -q`
  - 结果: `516 passed`
- `.venv/bin/python -m ruff check core/services/scheduler/run/optimizer_graph_ready.py core/services/scheduler/run/optimizer_graph_ready_profile_selection.py core/services/scheduler/run/optimizer_graph_ready_v2_features.py core/services/scheduler/run/optimizer_graph_ready_v2_capacity.py tests/algorithm/test_optimizer_graph_ready_candidate_contract.py tests/_support/optimizer_benchmark_ratchet.py tests/_scripts_e2e/benchmark_optimizer_long_run.py tests/_scripts_e2e/benchmark_smtwt_localsearch.py tests/_scripts_e2e/benchmark_optimizer_medium_gate.py tests/algorithm/test_optimizer_benchmark_ratchet_gate.py`
  - 结果: `All checks passed`
- `git diff --check -- <本轮修复文件>`
  - 结果: 通过
- `.venv/bin/python scripts/run_quality_gate.py --allow-dirty-worktree`
  - 结果: 第 4/17 步 `python -m ruff check` 失败;失败点在既有 `.codestable/compound/2026-06-30-due-budget-window-vs-residual/scripts/` 实验脚本的 B009/F841/E702,不属于本轮五个优先级修复文件。

遗留说明:当前工作区在本轮开始前已经有大量未提交改动,上述验证只能声明为 dirty-worktree 上的局部回归证明,不能声明 clean-worktree proof。

## 对抗复审遗留全量收口(2026-06-30)

上一轮对抗复审继续暴露出几类证明口径和落档问题。本轮按“先修会误导结论的口径,再修可复现性和快照证据,最后跑门禁”的顺序收口:

- `tests/_support/optimizer_compare_algorithms.py`
  - `portfolio_all` 改为 `comparison_semantics=posthoc_upper_bound`,其 `time_budget_seconds` 记录来源算法预算总和,并保存来源算法和来源预算明细。
  - 普通算法对 `portfolio_all` 的比较标 `not_comparable` + `reference_is_posthoc_upper_bound`;`portfolio_all` 对普通算法的比较标 `not_comparable` + `actual_is_posthoc_upper_bound`。
  - 对应合同测试补充 `portfolio_all` 不能当同预算普通算法胜平负的断言。
- `tests/_support/optimizer_smtwt_compare_*.py`
  - SMTWT 比较脚本同步使用同一套 `posthoc_upper_bound` / `same_budget_algorithm` 语义,避免另一条 benchmark 链继续把 `portfolio_all` 写成普通平局。
  - pairwise summary 遇到 `portfolio_all` 时计入 `not_comparable`,不再计胜平负。
- `.codestable/roadmap/scheduler-global-optimizer/` 与历史 fix note
  - 路线图、items、下一轮提示词和历史 fix note 都改成:`portfolio_all` 是事后上界,只能报告差距、来源和是否贡献最优路径,不能纳入同预算普通胜负。
- `.codestable/compound/2026-06-30-due-budget-window-vs-residual/`
  - 实验脚本按自身目录定位仓库和 `baselines/fjsp/`,默认写回本目录 `data/`,不再写死本机临时 job 路径。
  - 修正新增脚本的 `ruff` 问题(B009/F841/E702),旧日志里的临时路径只作为历史运行位置说明。
- `tests/web_pages/test_batch_template_ops_due_date_validation.py`
  - 增加真实 Flask POST 路径回归:确认页面创建批次时把 `due_date` 传给服务层,服务层抛交期校验错误时页面能 flash 给用户。
- `.codestable/checkup/scripts/callgraph_extract.py`
  - 补相对导入模块别名 + 模块函数调用解析,例如 `from . import batch_template_ops` 后的 `batch_template_ops.probe_template_ops_readonly(...)` 现在会生成确定调用边。
  - 已刷新 `.codestable/checkup/latest/callgraph/`;`probe_template_ops_readonly` 当前 `fan_in=1`,不再在 `islands.json`。
- `.codestable/issues/2026-06-30-benchmark-parallel-workers/benchmark-parallel-workers-fix-note.md`
  - 补齐 YAML frontmatter。
- `.codestable/audits/2026-06-30-test-suite-redundancy/scripts/`
  - 这些未跟踪审计脚本已经出现在当前工作区,会被全仓库 `ruff` 扫到;本轮只做静态风格修正,不改审计结论。

验证:

- `.venv/bin/python -m pytest tests/algorithm/test_optimizer_compare_algorithms_contract.py tests/algorithm/test_optimizer_smtwt_compare_algorithms_contract.py tests/web_pages/test_batch_template_ops_due_date_validation.py -q`
  - 结果:`35 passed`
- `.venv/bin/python -m ruff check`
  - 结果:`All checks passed!`
- `git diff --check`
  - 结果:通过,无输出。
- `.venv/bin/python .codestable/checkup/scripts/callgraph_extract.py`
  - 结果:函数数 `6921`,确信边 `10440`,孤岛数从旧快照的 `371` 降为 `346`。
- `python3 -m tools.symbol_locator callers probe_template_ops_readonly --deep --json`
  - 结果:真实调用方为 `core/services/scheduler/batch_service.py:394`。
- `.venv/bin/python scripts/run_quality_gate.py --allow-dirty-worktree`
  - 结果:17/17 步通过,manifest 状态为 `passed_but_unbound`;因为当前工作区仍是 dirty,这只能作为 dirty-worktree 功能证明,不能当 clean proof。

## 子代理复审后继续收口(2026-06-30)

第二轮子代理复审又指出几处会继续误导下一轮结论的问题。本轮继续收口:

- `tests/_support/optimizer_compare_algorithms.py` / `tests/_support/optimizer_smtwt_compare_report.py`
  - 普通算法之间只有在 `time_budget_seconds` 完全一致时才允许计胜平负。
  - 缺时间预算、非法时间预算、时间预算不同,统一标为 `not_comparable`,并把实际预算和基准预算写入比较结果。
- `tests/_support/optimizer_compare_algorithms_report.py`
  - baseline 回归检查也开始核对时间预算。分数没退步但预算变长,不再算通过。
- `.codestable/checkup/scripts/callgraph_extract.py`
  - `functions.json` 同时输出总扇入/扇出、确信扇入/扇出、模糊扇入/扇出。
  - `islands.json` 按“确信边 + 模糊边 + 函数对象引用边”判断孤岛;环和桥接点仍只用确信调用边,避免把“函数被当参数传入”包装成真实调用。
  - `_default_runtime()` 这类把函数对象传入运行时容器的路径现在会落成 `function_reference` 边。
- `.codestable/architecture/service-scheduler.md`
  - 更新 scheduler 规模、根目录文件数、`run/` 文件数和行数。
  - 修正 batch 族描述:它不是 6 文件全孤立,而是围绕 `batch_service.py` 形成批次主数据簇;只是对 run/summary/graph 等排产执行族仍基本无反向耦合。
- `.codestable/roadmap/scheduler-global-optimizer/drafts/graph-ready-v2-next-agent-prompt.md`
  - 删除“当前分支 clean 且 HEAD=4fbe2331”的旧现场描述,改成接手时必须实跑 `git status --short` 和 `git rev-parse HEAD`。
- `.codestable/issues/2026-06-29-graph-ready-v2-hardening/graph-ready-v2-hardening-fix-note.md`
  - frontmatter 改为 `doc_type: issue-fix`,补 `issue` / `path` / `fix_date` / `tags`。
- `.codestable/roadmap/scheduler-global-optimizer/graph-ready-v2-comparison-baseline.json`
  - 用当前代码刷新 dirty baseline。`portfolio_all` 现在是 `posthoc_upper_bound`,预算为 6 秒来源预算总和,对普通算法的比较是 `not_comparable`。

验证:

- `.venv/bin/python .codestable/checkup/scripts/callgraph_extract.py`
  - 结果:函数数 `6921`,确信边 `10440`,总边 `26635`,孤岛数 `164`。
- 关键调用图抽查:
  - `BatchService.create_batch_from_template`: `fan_in=2`,不在 `islands.json`。
  - `BatchService.list_operations`: `fan_in=2`,不在 `islands.json`。
  - `_run_graph_ready_candidates`: `fan_in=1`,不在 `islands.json`。
  - `probe_template_ops_readonly`: `fan_in=2`,不在 `islands.json`。
- `.venv/bin/python -m pytest tests/algorithm/test_optimizer_compare_algorithms_contract.py tests/algorithm/test_optimizer_smtwt_compare_algorithms_contract.py tests/web_pages/test_batch_template_ops_due_date_validation.py -q`
  - 结果:`39 passed`
- `.venv/bin/python -m ruff check .codestable/checkup/scripts/callgraph_extract.py tests/_support/optimizer_compare_algorithms.py tests/_support/optimizer_compare_algorithms_report.py tests/_support/optimizer_smtwt_compare_report.py tests/algorithm/test_optimizer_compare_algorithms_contract.py tests/algorithm/test_optimizer_smtwt_compare_algorithms_contract.py`
  - 结果:`All checks passed!`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/_scripts_e2e/benchmark_optimizer_compare_algorithms.py --profiles greedy,local_search,grasp_ig,graph_ready_v1,graph_ready_v2_no_repair,graph_ready_v2_with_repair,portfolio_all --seeds 10 --workers 10 --update-baseline --allow-dirty-proof`
  - 结果:刷新 `.codestable/roadmap/scheduler-global-optimizer/graph-ready-v2-comparison-baseline.json`;`proof_binding_status=unbound_dirty_worktree`。
- `.venv/bin/python -m ruff check`
  - 结果:`All checks passed!`
- `git diff --check`
  - 结果:通过,无输出。
- `.venv/bin/python scripts/run_quality_gate.py --allow-dirty-worktree`
  - 结果:17/17 步通过,包含 4633 个测试收集、full-test-debt 分片检查和 250 个 required regression 目标核验;最终 manifest 状态为 `passed_but_unbound`,进程返回码为 2。

遗留说明:当前仍在 dirty worktree 上收口,因此只能声明 dirty functional proof,不能声明 clean proof。

## 第三轮子代理复审阻塞修复(2026-06-30)

第三轮盲审发现路线图正文和 `items.yaml` 状态冲突,会误导下一轮接手人。本轮修复:

- `.codestable/roadmap/scheduler-global-optimizer/scheduler-global-optimizer-roadmap.md`
  - 第 14-18 项状态已和 `items.yaml` 一致:`done`。
  - 第 19-21 项状态已和 `items.yaml` 一致:`in_progress`。
  - 备注同步写清楚:14-18 已落地的范围、19-21 仍未完整落地的原因,以及 `portfolio_all` 仍只能作为事后上界和 `not_comparable`。
  - 第四轮盲审又发现后半段重复的 `benchmark-reference-diagnostics-baseline` 仍是旧状态;已改为 `done` 并说明它已作为 GraphReady v2 前置量尺被消费。
  - 第五轮盲审又发现叙述段仍写“下一轮先做前置量尺/修改前基准”;已改为当前事实:GraphReady v2 前半段已推进到 item 18,下一步继续收口 item 19-21。
  - 第六轮定向复核发现路线图正文编号和 `items.yaml` 顺序错位;已按 YAML 顺序把 `benchmark-reference-diagnostics-baseline` 固定为 item 14, GraphReady v2 后续项固定为 item 15-21, ALNS 后续项固定为 item 22-28。
- `.codestable/roadmap/scheduler-global-optimizer/drafts/graph-ready-v2-next-agent-prompt.md`
  - 从“推进前置量尺和 GraphReady v2”改为“核验已完成 item 14-18,继续收口 item 19-21”。
  - 把 item 14-18 小节改成已完成合同 / 接手核验点,避免下一轮 agent 重复做已完成工作。
- `.codestable/architecture/service-scheduler.md`
  - 顺手修正 `run/` 小节旧计数:`optimizer_*` 从 15 更新为 36,`schedule_graph_*` 从 4 更新为 5。
  - 第四轮定向复核又指出 graph 小节仍写“3 个 `schedule_graph_*` 文件”;已改为当前 5 个 `schedule_graph_*` 文件,其中 4 个直接函数体内延迟 import graph 子包。
- `.codestable/issues/2026-06-30-benchmark-parallel-workers/benchmark-parallel-workers-fix-note.md`
  - 补充说明并行 benchmark 记录来自 dirty worktree 功能检查,不能当作 clean proof 或替代最新 HEAD 完整质量门禁。

验证:

- 路线图正文第 14-21 项状态探针:
  - 14-18: `done`
  - 19-21: `in_progress`
- 路线图正文 slug/status 和 `scheduler-global-optimizer-items.yaml` 全量对比:
  - 结果:`mismatches=[]`,`duplicate_slugs={}`。
- 对交接提示词和路线图正文搜索旧阶段指令:
  - 目标词包括“下一轮实现 v2 前”“先做这个前置量尺”“前置量尺通过后”“先完成 benchmark-reference-diagnostics-baseline”等。
  - 结果:无命中。
- 对 `.codestable/roadmap/scheduler-global-optimizer`、`.codestable/architecture/service-scheduler.md` 和 `.codestable/issues/2026-06-30-benchmark-parallel-workers/benchmark-parallel-workers-fix-note.md` 搜索旧现场 / 旧孤岛 / 旧计数话术:
  - 结果:无命中;本修复记录自身只作为历史删除说明引用这些旧词。
- `find core/services/scheduler/run -maxdepth 1 -type f -name 'schedule_graph_*.py' -print | sort`
  - 结果:当前 5 个 `schedule_graph_*` 文件。
- `git diff --check`
  - 结果:通过,无输出。

遗留说明:这次是文档一致性收口,尚未在这些最终文档改动后重跑完整质量门禁。

## 第七轮盲审阻塞修复(2026-06-30)

第七轮盲审发现多算法比较里还有两处证明链阻塞:缺失 `seed` 会被默认成 0,同一 ratchet key 的重复行会被后来的行覆盖;SMTWT 成对胜负统计也会把缺 `seed` 的结果按 seed 0 配对并算成赢。本轮修复:

- `tests/_support/optimizer_compare_algorithms_report.py`
  - `compare_to_algorithm_baseline()` 在建立 actual / baseline 索引前先校验 ratchet key。
  - `case_group`、`case_slug`、`algorithm_profile`、`algorithm_version`、`seed` 任一缺失或非法都会记录失败。
  - 同一 ratchet key 出现重复行时记录 `duplicate_actual_ratchet_key` / `duplicate_baseline_ratchet_key`,并且不再覆盖第一行。
- `tests/_support/optimizer_smtwt_compare_common.py`
  - `row_key()` 不再把缺 `seed` 默认成 0;缺 case slug、缺 seed、非法 seed 都返回不可配对。
- `tests/_support/optimizer_smtwt_compare_report.py`
  - `pairwise_vs()` 遇到 subject 缺 key、subject 重复 key、reference 重复 key 或 reference 缺失时,按 `not_comparable` 计数,不再算胜 / 平 / 负。
  - `mean_overdue_gap_delta` 只用真实配对成功的行计算,不可比行不再读取空 reference。
- `tests/algorithm/test_optimizer_compare_algorithms_contract.py`
  - 新增缺 `seed` 失败、重复 ratchet key 不覆盖退步行的回归测试。
- `tests/algorithm/test_optimizer_smtwt_compare_algorithms_contract.py`
  - 新增 SMTWT 缺 `seed` 不算赢、重复 reference key 不算赢的回归测试。
- `.codestable/roadmap/scheduler-global-optimizer/drafts/graph-ready-v2-next-agent-prompt.md`
  - 补充接手硬要求:缺 `seed`、非法 `seed`、缺 ratchet key 字段、重复 ratchet key 必须失败,不能默认 0 或覆盖。

验证:

- `.venv/bin/python -m pytest tests/algorithm/test_optimizer_compare_algorithms_contract.py tests/algorithm/test_optimizer_smtwt_compare_algorithms_contract.py -q`
  - 结果:`39 passed`
- `.venv/bin/python -m ruff check tests/_support/optimizer_compare_algorithms_report.py tests/_support/optimizer_smtwt_compare_common.py tests/_support/optimizer_smtwt_compare_report.py tests/algorithm/test_optimizer_compare_algorithms_contract.py tests/algorithm/test_optimizer_smtwt_compare_algorithms_contract.py`
  - 结果:`All checks passed!`
- 最小探针:
  - 缺 actual `seed`:返回 `failed`,失败原因包含 `missing_actual_seed` 和 `missing_actual_row`。
  - actual 重复 ratchet key 且第一行退步:返回 `failed`,失败原因包含 `duplicate_actual_ratchet_key` 和 `objective_score_regressed`。
  - SMTWT subject 缺 `seed`:pairwise 结果 `wins=0`,`not_comparable=1`。

遗留说明:第七轮修复后还需要重新跑一轮定向复审 + 盲审复审;当前仍是 dirty worktree,不能声明 clean proof。

## 第八轮盲审阻塞修复(2026-06-30)

第八轮盲审继续发现两处证明口径问题:SMTWT 成对统计已经把预算不一致标为 `not_comparable`,但仍用这些不可比行计算 `mean_overdue_gap_delta`;GraphReady v1 真实 SGS 样例没有 exact/oracle,却把 `gap_to_oracle_pct` 写成 `0.0`。本轮修复:

- `tests/_support/optimizer_smtwt_compare_report.py`
  - `pairwise_vs()` 的 `mean_overdue_gap_delta` 只使用真正可比的配对行。
  - 预算不一致、缺 key、重复 key、缺 reference 这类不可比行不再参与平均差距。
  - 差距计算不再用 `or 0` 把缺失 `overdue_gap_to_opt` 当成 0。
- `tests/_support/optimizer_graph_ready_benchmark.py`
  - `run_graph_ready_real_sgs_case()` 输出 `oracle_status=not_run`、`gap_to_oracle_pct=None`。
  - `run_graph_ready_flexible_machine_metric_case()` 同样输出 `oracle_status=not_run`、`gap_to_oracle_pct=None`。
- `tests/algorithm/test_optimizer_smtwt_compare_algorithms_contract.py`
  - 时间预算不一致的 pairwise 测试覆盖 `not_comparable`,不可比行不应参与差距计算。
  - 补 SMTWT subject 重复 key、reference 缺 key 的不可比回归。
- `tests/algorithm/test_optimizer_compare_algorithms_contract.py`
  - 补非法 `seed` 和 baseline 重复 ratchet key 的回归。
- `tests/algorithm/test_optimizer_graph_ready_candidate_contract.py`
  - 补 GraphReady v1 真实 SGS 样例 `oracle_status=not_run`、`gap_to_oracle_pct is None` 的回归。
- `.codestable/roadmap/scheduler-global-optimizer/benchmark-ratchet-baseline.json`
  - 已刷新:GraphReady 真实 SGS 和瓶颈指标样例均为 `oracle_status=not_run`、`gap_to_oracle_pct=null`;tiny exact case 仍保留真实 `gap_to_oracle_pct=0.0`。
- `.codestable/roadmap/scheduler-global-optimizer/graph-ready-v2-comparison-baseline.json`
  - 已刷新:10 条 `graph_ready_v1` 行均为 `oracle_status=not_run`、`gap_to_oracle_pct=null`;`proof_binding_status` 仍是 `unbound_dirty_worktree`。
- `.codestable/roadmap/scheduler-global-optimizer/drafts/graph-ready-v2-next-agent-prompt.md`
  - 补充交接硬要求:SMTWT pairwise 只在同 case、同 seed、同预算、唯一 subject、唯一 reference 时计算胜平负和平均差距;没有 exact/oracle 的 GraphReady 真实 SGS 样例不能写 gap 0。

验证:

- `.venv/bin/python -m pytest tests/algorithm/test_optimizer_compare_algorithms_contract.py tests/algorithm/test_optimizer_smtwt_compare_algorithms_contract.py tests/algorithm/test_optimizer_graph_ready_candidate_contract.py::test_graph_ready_candidates_run_real_sgs_weight_grid tests/algorithm/test_optimizer_graph_ready_candidate_contract.py::test_graph_ready_v2_runs_real_sgs_and_keeps_repair_attribution_separate tests/web_pages/test_batch_template_ops_due_date_validation.py -q`
  - 结果:`49 passed`
- `.venv/bin/python -m pytest tests/algorithm/test_optimizer_benchmark_ratchet_gate.py -q`
  - 结果:`11 passed`
- `.venv/bin/python -m ruff check tests/_support/optimizer_smtwt_compare_report.py tests/_support/optimizer_graph_ready_benchmark.py tests/algorithm/test_optimizer_compare_algorithms_contract.py tests/algorithm/test_optimizer_smtwt_compare_algorithms_contract.py tests/algorithm/test_optimizer_graph_ready_candidate_contract.py`
  - 结果:`All checks passed!`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/_scripts_e2e/benchmark_optimizer_ratchet.py --update-baseline`
  - 结果:刷新 `.codestable/roadmap/scheduler-global-optimizer/benchmark-ratchet-baseline.json`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/_scripts_e2e/benchmark_optimizer_compare_algorithms.py --profiles greedy,local_search,grasp_ig,graph_ready_v1,graph_ready_v2_no_repair,graph_ready_v2_with_repair,portfolio_all --seeds 10 --workers 10 --update-baseline --allow-dirty-proof`
  - 结果:刷新 `.codestable/roadmap/scheduler-global-optimizer/graph-ready-v2-comparison-baseline.json`;`proof_binding_status=unbound_dirty_worktree`。
- 基准文件探针:
  - `benchmark-ratchet-baseline.json`:GraphReady 真实 SGS 行 `oracle_status=not_run`,`gap_to_oracle_pct=None`。
  - `graph-ready-v2-comparison-baseline.json`:10 条 `graph_ready_v1` 行均 `oracle_status=not_run`,`gap_to_oracle_pct=None`。
  - 两份基准里仅 tiny exact case 保留真实 `gap_to_oracle_pct=0.0`。

遗留说明:第八轮修复后仍需重新跑双轨子代理复审;当前仍是 dirty worktree,不能声明 clean proof。

## 第九轮盲审阻塞修复(2026-06-30)

第九轮盲审发现 4 个“缺证据被当成 0”的证明口径问题。本轮继续收紧:

- `tests/_support/optimizer_benchmark_ratchet.py`
  - `_proof_case_row()` 不再用 `case.get("gap_to_oracle_pct") or 0.0`;缺失或非法 gap 会保留为 `None`,比较状态为 `not_comparable`。
  - `_float_metric_increase_failure()` 不再把缺失 metric 当 0;actual / baseline 缺失或非法时返回失败。
  - tiny exact case 仍可写真实 `oracle_status=proven_optimal` 和 `gap_to_oracle_pct=0.0`;GraphReady 中大样例仍是 `not_run/null`。
- `tests/_support/optimizer_compare_algorithms.py`
  - `portfolio_all` 来源行缺 `time_budget_seconds` 或预算非法时,记录 `invalid_time_budget_sources`,组合行状态变为 `failed`,不再把缺预算加成 0 后通过。
- `tests/_support/optimizer_smtwt_compare_report.py`
  - SMTWT 的 `portfolio_all` 同样校验来源预算,缺预算时组合行失败。
  - `overdue_gap_to_opt` 缺失时不再默认成 0,汇总不再把缺 gap 的 passed 行算作最优。
- `tests/_support/optimizer_compare_algorithms_report.py`
  - 汇总层只对 `improved/same/degraded` 且有真实 `primary_delta` 的行计算均值和最差值。
  - `not_comparable` 的 passed 行不再显示成 `0.0` 差距,而是 `null`。
- `tests/_support/optimizer_smtwt_compare_common.py`
  - `mean()` 跳过缺失、布尔值、非数和无限值;调用方不能再把“没有可比样本”解释成平均差距 0。
- `.codestable/roadmap/scheduler-global-optimizer/scheduler-global-optimizer-items.yaml`
  - item 12 备注改为:dirty baseline / dirty actual 下 `--check-baseline` 应失败并返回 `unbound_dirty_worktree`,不能写成通过证明。
- `.codestable/roadmap/scheduler-global-optimizer/scheduler-global-optimizer-roadmap.md`
  - 同步改掉“相对 dirty baseline 未退化”的误导说法。
- `.codestable/roadmap/scheduler-global-optimizer/drafts/graph-ready-v2-next-agent-prompt.md`
  - 删除旧提交号描述,改成当前 dirty / unbound 口径,并明确 dirty 下 `--check-baseline` 应失败。

新增回归:

- ratchet 缺 `gap_to_oracle_pct` 失败。
- GraphReady `portfolio_all` 缺来源预算失败。
- GraphReady 汇总层不可比 delta 不写成 0。
- SMTWT `portfolio_all` 缺来源预算失败。
- SMTWT 缺 `overdue_gap_to_opt` 不算最优。

验证:

- `.venv/bin/python -m pytest tests/algorithm/test_optimizer_benchmark_ratchet_gate.py tests/algorithm/test_optimizer_compare_algorithms_contract.py tests/algorithm/test_optimizer_smtwt_compare_algorithms_contract.py -q`
  - 结果:`59 passed`
- `.venv/bin/python -m ruff check tests/_support/optimizer_benchmark_ratchet.py tests/_support/optimizer_compare_algorithms.py tests/_support/optimizer_compare_algorithms_report.py tests/_support/optimizer_smtwt_compare_common.py tests/_support/optimizer_smtwt_compare_report.py tests/algorithm/test_optimizer_benchmark_ratchet_gate.py tests/algorithm/test_optimizer_compare_algorithms_contract.py tests/algorithm/test_optimizer_smtwt_compare_algorithms_contract.py`
  - 结果:`All checks passed!`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/_scripts_e2e/benchmark_optimizer_ratchet.py --update-baseline`
  - 结果:刷新 `.codestable/roadmap/scheduler-global-optimizer/benchmark-ratchet-baseline.json`;tiny exact 行有 `oracle_status=proven_optimal`,GraphReady 中大样例仍为 `not_run/null`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/_scripts_e2e/benchmark_optimizer_compare_algorithms.py --profiles greedy,local_search,grasp_ig,graph_ready_v1,graph_ready_v2_no_repair,graph_ready_v2_with_repair,portfolio_all --seeds 10 --workers 10 --update-baseline --allow-dirty-proof`
  - 结果:刷新 `.codestable/roadmap/scheduler-global-optimizer/graph-ready-v2-comparison-baseline.json`;`portfolio_all` 包含 `invalid_time_budget_sources=[]`,不可比 summary delta 为 `null`,证明状态仍是 `unbound_dirty_worktree`。
- 最小探针:
  - ratchet 缺 actual `gap_to_oracle_pct`:返回 `failed`,原因 `missing_or_invalid_actual_gap_to_oracle_pct`。
  - GraphReady `portfolio_all` 来源缺预算:返回 `failed`,并记录 `invalid_time_budget_sources`。
  - GraphReady 不可比 summary:均值 / 最差 primary delta 为 `null`。
  - SMTWT 缺 `overdue_gap_to_opt`:不算最优,`mean_overdue_gap_to_opt=null`。

遗留说明:第九轮修复后仍需重新跑双轨子代理复审;当前仍是 dirty worktree,不能声明 clean proof。

## 第十轮定向复审阻塞修复(2026-06-30)

第十轮定向子代理复审发现:SMTWT `pairwise_vs()` 虽然已经把预算不一致、缺 key、重复 key、缺 reference 标成 `not_comparable`,但当完全没有可比配对时,`mean_overdue_gap_delta` 仍通过公共 `mean()` 输出 `0.0`。这会把“不能比较”误导成“平均打平”。本轮修复:

- `tests/_support/optimizer_smtwt_compare_report.py`
  - `_pairwise_row()` 先计算真正可比配对的 gap delta。
  - 没有任何可比 gap delta 时,`mean_overdue_gap_delta` 返回 `None`,不再返回 `0.0`。
- `tests/algorithm/test_optimizer_smtwt_compare_algorithms_contract.py`
  - 预算不一致、缺 seed、subject 重复 key、reference 缺 key、reference 重复 key 这些全不可比 pairwise 场景,期望值统一改为 `mean_overdue_gap_delta is None`。

待复核:本轮修复后仍需重新跑定向测试、ruff、双轨子代理复审和质量门禁;当前仍是 dirty worktree,不能声明 clean proof。

## 第十一轮盲审阻塞修复(2026-06-30)

第十一轮盲审发现:GraphReady 算法对比汇总在“没有任何成功可比差距”的情况下,仍会把 `mean_primary_delta_vs_current_baseline` 和 `worst_primary_delta_vs_current_baseline` 输出为 `0.0`。这会把“没有可比较数据”误导成“平均打平”。本轮修复:

- `tests/_support/optimizer_compare_algorithms_report.py`
  - `summarize_comparison_rows()` 只有在存在真实 `improved/same/degraded` 且有 `primary_delta` 的行时才计算均值和最差值。
  - `deltas` 为空时,均值和最差值统一返回 `None`;真实可比较 delta 本身为 `0.0` 时才保留 `0.0`。
- `tests/algorithm/test_optimizer_compare_algorithms_contract.py`
  - 失败行即使带着 `comparison_to_current_baseline.status=improved`,也不会计胜场,均值和最差差距都应为 `None`。

待复核:本轮修复后仍需重新跑相关测试、ruff、双轨子代理复审和质量门禁;当前仍是 dirty worktree,不能声明 clean proof。
