# 下一轮 Agent 执行提示词：GraphReady v2 生产级 repair、统一候选池与 clean comparative gate

本文是 2026-07-10 收口后的下一轮执行入口。它只描述**当前已经落地的事实、仍未完成的 roadmap item 和后续验收边界**，不要重复实现已经完成的合同、报告和长跑 harness。

---

## 0. 当前交接水位线

参考分支：

```text
feat/default-light-improve-sgs
```

本轮 GraphReady 业务代码水位线：

```text
2a5b7bbc test(scheduler): 锁定 GraphReady repair 仍为 benchmark-only
```

已按原子提交落地：

```text
f2ae8056 fix(scheduler): 统一 GraphReady v2 合同错误的 fail-loud 边界
9267bcdf fix(scheduler): 让 GraphReady 真正改进写入 acceptance 报告
3b2fe163 test(benchmark): 新增 GraphReady v2 专属长跑对比入口
2a5b7bbc test(scheduler): 锁定 GraphReady repair 仍为 benchmark-only
```

接手时必须重新运行：

```bash
git status --short --branch
git rev-parse HEAD
git log -10 --oneline
git rev-list --left-right --count HEAD...@{upstream}
```

不要假设上面的 hash 永远是最新 HEAD；它们是本轮已落地代码的可追溯锚点。

---

## 1. 解释器与交付边界

两类 Python 不能混：

1. **CodeStable / LimCode 本机维护、检索、体检工具**故意使用宿主 CPython 3.14，以获得更完整的工具/库支持和更好的本机执行效率。
2. **APS 产品代码、项目测试、打包和最终质量门禁**仍须兼容 Python 3.8 与 Win7 x64。

因此：

- `.limcode/skills/` 与 CodeStable 本机工具不要为了 APS 运行时降级到 Python 3.8 语法。
- `core/`、`web/`、`data/`、生产 scheduler、测试合同和打包入口不得使用 Python 3.9+ 专属语法。
- 宿主 Python 3.14 工具不得进入 APS 离线运行包。
- APS 验证继续使用 `.venv/bin/python`；跨平台子进程测试使用 `sys.executable`，不要写死 `.venv/bin/python`。

---

## 2. 启动必读

按顺序读取：

1. `AGENTS.md`
2. `.codestable/attention.md`
3. `.codestable/reference/system-overview.md`
4. `.codestable/roadmap/scheduler-global-optimizer/scheduler-global-optimizer-roadmap.md`
5. `.codestable/roadmap/scheduler-global-optimizer/scheduler-global-optimizer-items.yaml`
6. `.codestable/roadmap/scheduler-global-optimizer/graph-ready-v2-comparison-baseline.json`
7. `.codestable/roadmap/scheduler-global-optimizer/benchmark-ratchet-baseline.json`
8. 本文件列出的四个已落地 commit

修改函数前使用项目定位工具：

```bash
.venv/bin/python -m tools.symbol_locator whereis run_graph_ready_candidates
.venv/bin/python -m tools.symbol_locator callers run_graph_ready_candidates --deep
.venv/bin/python -m tools.symbol_locator callees run_graph_ready_candidates --deep
.venv/bin/python -m tools.symbol_locator whereis candidate_is_preferred
.venv/bin/python -m tools.symbol_locator callers candidate_is_preferred --deep
```

文本搜索可用 `rg`；本机没有 `rg` 时用 `grep -RIn`，不要把工具缺失包装成未发现引用。

---

## 3. 已完成，不要重复做

### 3.1 GraphReady v2 合同错误 fail-loud

已完成：

- 新增 `core/services/scheduler/run/optimizer_graph_ready_v2_contract.py`。
- 统一识别 v2 feature、formula、candidate policy 和已知 validation reason。
- 上下文解析、逐 profile 评估两处都在非 strict 下对 v2 合同错误直接上抛。
- 未知 formula 不再被吞成普通 candidate rejection。
- strict / non-strict 合同测试已经锁住。

继续修改时不得恢复：

- 大范围 `except Exception` 返回 incumbent；
- 非 strict 静默跳过非法 v2 formula；
- 把合同失败包装成普通 candidate_rejected。

### 3.2 accepted best 的 acceptance/report 口径

已完成：

- 新增 `optimizer_graph_ready_acceptance.py`。
- 只有 candidate score 严格优于 incumbent 才生成 `improve_only` acceptance event。
- `candidate_is_preferred()` 仍是唯一择优裁判；acceptance event 只记录报告事实。
- 同分 fingerprint/runtime/origin tie-break 可以替换 best，但不得标记 `report.improved=True`。
- same fingerprint 不生成 acceptance event。
- public 只展示 `acceptance_summary`；raw event、随机字段和 fingerprint 只进入 diagnostics。

后续 repair 必须复用这套口径，不得另造一套“repair accepted”裁判。

### 3.3 GraphReady v2 专属 long-run harness

已完成：

- 新增 `benchmark_git_state.py`。
- 新增 `optimizer_graph_ready_v2_long_run.py`。
- 新增 `benchmark_optimizer_graph_ready_v2_long_run.py`。
- 默认比较：greedy、local_search、GRASP/IG、GraphReady v1、GraphReady v2 no-repair、portfolio_all。
- 至少 10 seeds。
- 同 seed、同时间预算、有效同形 objective score 才进入普通胜平负。
- `portfolio_all` 固定是 `posthoc_upper_bound / not_comparable`。
- dirty evidence 固定是 `unbound_dirty_worktree`，不得冒充 clean proof。
- 子进程合同使用 `sys.executable`，兼容 Windows CI。

当前明确**没有**：

```text
.codestable/roadmap/scheduler-global-optimizer/graph-ready-v2-long-run-baseline.json
```

所以当前只有 harness，不得写成“clean ratchet baseline 已建立”或“item 21 已完成”。

### 3.4 benchmark-only repair 边界

已完成测试锁定：

- 生产 CandidateProfile 包含 `graph_ready_v2_no_repair`。
- 生产 CandidateProfile 不包含 `graph_ready_v2_with_repair`。
- 生产 CandidateProfile 不包含 `graph_ready_v2_repaired`。
- benchmark no-repair / with-repair 行都标 `repair_scope=benchmark_support_only_not_core`。
- item 19、20、21 继续保持 `in_progress`。

benchmark support 不是生产能力。不得因为 support helper 能跑 adjacent swap / single insert，就把 repair item 改成 done。

---

## 4. 当前 roadmap 状态

必须保持：

```text
graph-ready-v2-comparison-baseline-contract: done
graph-ready-v2-objective-feature-contract: done
graph-ready-v2-bottleneck-resource-score: done
graph-ready-v2-candidate-portfolio: done
graph-ready-v2-elite-local-repair: in_progress
graph-ready-v2-portfolio-integration: in_progress
graph-ready-v2-comparative-ratchet-gate: in_progress
```

后续按依赖推进：

```text
item 19 生产级 elite local repair
  -> item 20 接入统一生产候选池
    -> item 21 建立 clean comparative ratchet gate
```

不要跳过 item 19，直接把 benchmark with-repair 塞进 item 20。

---

## 5. 下一阶段 A：生产级 elite local repair

### 5.1 目标

只对 GraphReady v2 已经经过正式 SGS 解码的前 K 个精英候选生成轻量 repair 邻居；每个邻居仍必须重新经过正式 SGS、统一目标评分、指纹去重和 acceptance/report 链。

repair 只能改变候选决策输入，例如：

- batch order；
- graph priority；
- repair request；
- 邻域动作描述。

repair 不得直接写：

- `ScheduleResult`；
- `start_time` / `end_time`；
- 正式计划表；
- mutable 工序执行态；
- 绕过冻结、资格、前后置或资源约束的结果。

### 5.2 配置合同

以 roadmap 当前字段为准，不另造同义字段：

```text
graph_ready_optimization.elite_repair.enabled
graph_ready_optimization.elite_repair.top_k
graph_ready_optimization.elite_repair.max_neighbors_per_elite
graph_ready_optimization.elite_repair.time_budget_ms
graph_ready_optimization.elite_repair.neighbor_generators
graph_ready_optimization.elite_repair.pruning_strategy
```

候选生成器至少考虑：

```text
adjacent_swap
single_insert
tardy_boundary_move
```

边界：

- `top_k`、邻居上限和 repair 时间预算必须有系统钳制和报告字段。
- 超预算单独报告 `skipped_by_budget`，不能冒充 pruning。
- decision fingerprint 与 output fingerprint 都要去重。
- parent output、seen output 和同 fingerprint 邻居不得重复正式计为改进。

### 5.3 建议模块边界

优先新增独立模块：

```text
core/services/scheduler/run/optimizer_graph_ready_repair.py
```

职责建议：

- 选择 top-K elites；
- 生成确定性邻居描述；
- 执行 budget guard；
- 返回 repair candidate request 与 pruning/skip 统计；
- 不负责正式 SGS 解码和最终择优。

`optimizer_graph_ready.py` 只做阶段编排，不要继续膨胀成邻域实现仓库。

### 5.4 正式采纳链

每个 repair 邻居必须走：

```text
repair request
  -> schedule_fn
  -> GreedyScheduler.schedule
  -> SGS
  -> compute_metrics / objective_score
  -> CandidateFingerprint
  -> candidate_is_preferred
  -> improve_only acceptance event
  -> OptimizationSearchReportState
```

只有正式 objective score 严格更优、output fingerprint 非 parent/seen、acceptance 通过时，才能成为：

```text
graph_ready_v2_repaired
```

---

## 6. 下一阶段 B：接入统一生产候选池

item 20 只负责接入与统一择优，不负责实现 repair 本体。

需要核对的候选来源：

```text
greedy
local_search
grasp_ig
graph_ready_v1
graph_ready_v2_generated
graph_ready_v2_repaired
```

所有来源必须共享：

- 同一 objective；
- 同一 `candidate_is_preferred()`；
- 同一 output fingerprint 去重；
- 同一 SearchReport；
- 同一 public/diagnostics 脱敏边界。

禁止：

- 为 repaired candidate 新增特殊胜出捷径；
- 把 repair 命中率当成独立算法胜负；
- 把 `portfolio_all` 变成生产候选或同预算普通算法；
- 让 public 暴露 raw op/resource/node id、fingerprint 或完整 trace。

如果最终 best 来自 repaired candidate，public 可以说明“统一候选池采纳 GraphReady v2 修补候选”，但不能写“剪枝算法证明全局最优”。

---

## 7. 下一阶段 C：clean comparative ratchet gate

item 21 只能在 item 19、20 的生产链完成后收口。

### 7.1 当前 harness 命令

```bash
.venv/bin/python tests/_scripts_e2e/benchmark_optimizer_graph_ready_v2_long_run.py \
  --seeds 10 \
  --workers 1 \
  --no-write
```

当前没有版本化 baseline，`--check-baseline` 缺文件时失败是正确行为。

### 7.2 建立 baseline 的前提

必须同时满足：

- 最终业务 HEAD；
- clean worktree；
- 真实 production repair 已接线；
- 同 case、同 seed、同时间预算、同 objective；
- 全部算法行 status passed；
- proof_binding_status 为 `clean_worktree`；
- `portfolio_all` 仍为 posthoc/not_comparable；
- baseline 文件通过人工 review 后单独提交。

建议 baseline 单独提交：

```text
test(benchmark): 建立 GraphReady v2 clean long-run ratchet baseline
```

不得在 dirty worktree 下用 `--allow-dirty-proof` 生成 baseline 后宣称 clean gate。

### 7.3 必须报告

至少包括：

- wins / ties / losses / not_comparable；
- mean duplicate candidate rate；
- mean candidate rejection rate；
- repair evaluated / accepted / rejected；
- skipped_by_budget；
- pruned_by_rule；
- best origin；
- Git commit 与 proof binding；
- algorithm profile/version/seed ratchet key。

---

## 8. 下一阶段 D：反例夹具与防假证明

不要只继续扩充当前单一真实 SGS 样例。建议新增：

```text
tests/_support/optimizer_graph_ready_v2_cases.py
```

至少覆盖：

1. 内制日历产能与外协自然小时不能裸混。
2. 瓶颈很忙但 due 不紧时，不得压过主交期目标。
3. 可救短单与长尾牺牲边界。
4. micro perturbation 只允许平局扰动，不跨主交期分数。
5. repair 邻居必须重新走正式 SGS。
6. duplicate decision / duplicate output / parent output 分别计数。
7. budget skip 与 pruning 分开报告。
8. public / OperationLogs / size guard 不泄漏内部 id、fingerprint 和 trace。
9. production path 不依赖 benchmark override。
10. score shape、非法数字和 missing reference 不得变成 improved/degraded。

测试锁业务不变式，不要只锁某个 4 工序夹具的赢家顺序。

---

## 9. 推荐后续提交颗粒

### Commit A：repair 配置与纯邻域生成合同

```text
feat(scheduler): 定义 GraphReady v2 elite repair 配置与邻域请求
```

包含：

- 独立 repair 模块；
- 配置解析/钳制；
- 确定性邻居请求；
- 不接生产采纳链。

### Commit B：repair 正式 SGS 与 acceptance 接线

```text
feat(scheduler): 接入 GraphReady v2 repair 正式 SGS 采纳链
```

包含：

- top-K elite；
- 邻居正式解码；
- fingerprint；
- candidate_is_preferred；
- acceptance/report；
- repair origin。

### Commit C：统一候选池接入

```text
feat(scheduler): 将 GraphReady v2 repaired 候选接入统一择优池
```

### Commit D：反例和 public 边界

```text
test(scheduler): 补强 GraphReady v2 repair 反例与脱敏合同
```

### Commit E：clean ratchet baseline

```text
test(benchmark): 建立 GraphReady v2 clean long-run ratchet baseline
```

每个提交都要能独立回滚，测试与实现同批；不要把生产 repair、baseline JSON 和交接文档塞成一个巨型提交。

---

## 10. 验收命令

### 局部合同

```bash
.venv/bin/python -m pytest -p no:cacheprovider \
  tests/algorithm/test_optimizer_graph_ready_candidate_contract.py \
  tests/algorithm/test_optimizer_candidate_profile_contract.py \
  tests/algorithm/test_optimizer_candidate_fingerprint_contract.py \
  tests/algorithm/test_optimizer_compare_algorithms_contract.py \
  tests/algorithm/test_optimizer_graph_ready_v2_long_run_contract.py \
  -q
```

### long-run harness

```bash
.venv/bin/python tests/_scripts_e2e/benchmark_optimizer_graph_ready_v2_long_run.py \
  --seeds 10 \
  --workers 1 \
  --no-write
```

### 最终完整门禁

```bash
git status --porcelain
PYTHONDONTWRITEBYTECODE=1 \
PYTHONUTF8=1 \
PYTHONIOENCODING=utf-8 \
.venv/bin/python scripts/run_quality_gate.py \
  --require-clean-worktree \
  --long-gate-cache
```

只有最终 HEAD、干净 worktree、完整门禁通过，才能称为 clean-worktree proof。任何文档 amend 都会改变 HEAD，改变后必须重跑门禁。

---

## 11. 严禁事项

- 不要重复实现已经落地的 contract classifier、acceptance helper 或 v2 long-run harness。
- 不要把 benchmark with-repair 当成生产 repair。
- 不要把 `portfolio_all` 当成同预算算法胜利。
- 不要把 dirty evidence 写成 clean proof。
- 不要静默吞掉 v2 合同错误或非法 repair 配置。
- 不要直接修改 ScheduleResult 时间来伪造 repair。
- 不要把 skipped_by_budget 记成 pruned。
- 不要在 objective 不同或预算不同的行之间统计胜负。
- 不要在 public 投影泄漏 raw id、fingerprint 或 trace。
- 不要引入云服务、外部前端资源或新的 APS 运行时依赖。
- 不要用 Python 3.9+ 语法修改 APS 生产/测试代码。
- 不要把是否调用 Sub Agent 当成完成条件；用户要求单线程时由主线程完成并如实报告。

---

## 12. 最终交付必须说明

- 开始和结束时的分支、HEAD、工作区状态。
- 实际完成了哪个 roadmap item，哪些仍为 in_progress。
- 生产 repair 与 benchmark repair 的边界。
- 正式 SGS、fingerprint、candidate comparison、acceptance/report 的证据路径。
- 每类算法的可比/不可比原因。
- `portfolio_all` 是否保持 posthoc upper bound。
- 跑过的测试、benchmark 和质量门禁原命令。
- 哪些证据是 dirty/unbound，哪些是 clean proof。
- 是否生成或更新了版本化 baseline；没有就明确写“没有”。
- 所有未提交或未覆盖范围。

一句话目标：**在不破坏正式 SGS、统一择优、报告真实性和 Win7/Python 3.8 产品合同的前提下，把 GraphReady v2 从 no-repair 候选生成推进到可审计的生产级 elite repair、统一候选池和 clean comparative ratchet gate。**
