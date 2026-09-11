---
doc_type: feature-ff-note
feature: optimizer-quality-matrix
date: 2026-09-08
tags: [optimizer, quality-matrix, production-repair, real-sgs, dirty-evidence]
---

# 真实生产优化器质量矩阵

## 结论与边界

- 本专项只新增 8 个 Python 文件和本记录，未改旧 ratchet、旧 CLI/tests、旧基线、共享注册、产品代码或前端/启动/打包；未 commit，未启动代理。
- 最小覆盖就是完整的 8 cases：4 个正式 objective × tiny 8 工序 / medium_shift_pool 48 工序。没有新增另一套轻量框架。
- 固定生成的制造业形状 fixture 不是现场客户数据；实际执行的是生产 `run_graph_ready_candidates`、正式 elite repair、`GreedyScheduler` SGS 和 `CalendarService`。
- 只证明本组 fixture 的可行性与质量不退化，不声称全局最优、最优差距或 clean quality-gate proof。

## 文件

| 文件 | 职责 |
| --- | --- |
| `tests/_support/optimizer_quality_matrix.py` | 串行编排、正式优化器/SGS、真实 perf_counter 计时和解码计数 |
| `tests/_support/optimizer_quality_matrix_cases.py` | 固定输入、真实工序图指标、仅内存 SQLite 的 CalendarService 场景 |
| `tests/_support/optimizer_quality_matrix_schedule.py` | 全工序覆盖、身份、资源/前序/停机冲突、日历工时和重算目标分数 |
| `tests/_support/optimizer_quality_matrix_provenance.py` | 机器/运行时、Git HEAD/status/diff、实际源码摘要及前后来源绑定 |
| `tests/_support/optimizer_quality_matrix_compare.py` | 严格元数据、保存矩阵重验、完整目标向量和宽容 runtime 比较 |
| `tests/_support/optimizer_quality_matrix_io.py` | 诊断输出与 clean-only 正式基线更新；拒绝重复 JSON key/非有限数字 |
| `tests/_scripts_e2e/benchmark_optimizer_quality_matrix.py` | `run` / `compare` / `update-baseline` CLI |
| `tests/algorithm/test_optimizer_quality_matrix_contract.py` | 合同/真实调用/质量/runtime/来源 mutation 测试 |

## 固定合同

- 目标：`min_overdue`、`min_tardiness`、`min_weighted_tardiness`、`min_changeover`。比较生产 `failed_ops + objective_score` 的完整字典序向量，不只比较第一项。
- tiny 用真实 CalendarService 的 24 小时日历；medium 使用 08:00-16:00 班次、两段实际停机输入、3 台候选设备和交叉人员资源池，实际触发自动派工及跨班排程。
- 同 case 的 baseline 和 improved 复用相同 scheduler/calendar、工序/批次、资源池、停机、起始时刻及 SGS 参数。baseline 同样使用工序图前序约束。保存两份排程，读快照时重新校验并重算分数。
- 默认 seed=0；优化阶段墙钟预算 10 秒，baseline 另计；graph+repair 解码总上限 60；repair top_k=3、每 elite 最多 8 个邻居；workers 必须为 1。不接受 xdist worker 中的性能测量。
- 计时涵盖 baseline SGS、GraphReady 构造/正式 repair/SGS/评估，不含 fixture 初始化、来源采集和事后排程审计。不是模拟时钟，也不把单个最佳候选耗时当成整体优化耗时。
- runtime 默认门槛：`actual <= reference * 3 + 250ms`，分别比较 baseline、improve、合计三个时间。可调整 ratio/slack；比较要求同机器/运行时、同 seed/预算/config 和固定 case 全覆盖。
- 诊断可写到 `evidence/QualityGate/long_gate/optimizer_quality_matrix/` 或仓库外临时路径，不能占用保留的 `optimizer_quality_matrix*.json` 正式基线文件名前缀，也不能写仓库内其他目录。
- 正式更新只接受 status=passed、运行前后均 clean 且来源一致、当前 clean HEAD/源码/机器与快照相符、已知完整元数据的快照。已有正式矩阵还须通过退化比较。当前 dirty/changed 快照必拒绝，不伪造 clean。

## CLI 跑法

以下命令在 `/Users/lurenxing/GitHub/----` 执行。主线程应先暂停其他性能任务，再将 matrix 与 SGS paired measurement 顺序运行；本专项未实现或启动 SGS paired measurement，也不负责全机任务冻结。

最小命令（默认全部 8 cases、seed=0、10s/60 candidates）：

```bash
.venv/bin/python tests/_scripts_e2e/benchmark_optimizer_quality_matrix.py run
```

完整固定参数命令（全部 8 cases，不增加并行 worker）：

```bash
.venv/bin/python tests/_scripts_e2e/benchmark_optimizer_quality_matrix.py run \
  --seed 0 --time-budget-seconds 10 --max-candidates 60 \
  --repair-top-k 3 --repair-max-neighbors-per-elite 8 --workers 1 \
  --output evidence/QualityGate/long_gate/optimizer_quality_matrix/frozen-run-a.json
```

需要复测时，在前一条结束后用相同参数另存 `frozen-run-b.json`，不要并行运行。比较不同 seed 或预算会明确失败；不同配置应另建证据序列。

```bash
.venv/bin/python tests/_scripts_e2e/benchmark_optimizer_quality_matrix.py compare \
  --baseline evidence/QualityGate/long_gate/optimizer_quality_matrix/frozen-run-a.json \
  --actual evidence/QualityGate/long_gate/optimizer_quality_matrix/frozen-run-b.json \
  --runtime-ratio 3 --runtime-slack-ms 250 \
  --output evidence/QualityGate/long_gate/optimizer_quality_matrix/frozen-comparison.json

.venv/bin/python -m pytest -q tests/algorithm/test_optimizer_quality_matrix_contract.py
```

正式更新入口（仅示例，当前 dirty 禁止执行成功，且不指向任何旧基线）：

```bash
.venv/bin/python tests/_scripts_e2e/benchmark_optimizer_quality_matrix.py update-baseline \
  --snapshot evidence/QualityGate/long_gate/optimizer_quality_matrix/frozen-run-a.json \
  --baseline tests/fixtures/optimizer_quality_matrix_baseline.json
```

CLI 成功返回 0；比较/矩阵检查失败返回 1；配置、元数据、读写或基线提升拒绝返回 2。合同测试必须串行跑，不要用 `pytest -n auto`。必跑注册由主线程接入，本专项没有修改注册表。

## 已实跑证据

- Python **3.8.10**：最终新合同测试 **52 passed in 20.27s**；新增 Python 文件 Ruff 全过。测试包含四目标真实质量变差、1000 倍 runtime mutation、真实 sleep 延迟注入、缺 case/重复 case/改 seed/预算失配/未知元数据/假分数/排程冲突，以及 dirty 正式提升拒绝与基线文件保护。
- 最终 CLI 于 **2026-09-08 15:46:39 至 15:46:56（Asia/Shanghai）** 完成，8/8 cases passed；合计计量 runtime **17547.549ms**，**254 次真实 SGS 解码，126 次正式 repair 解码**。所有 case failed_ops=0，完整目标分数均不劣于各自 baseline。
- tiny 单 case 48.471-51.378ms；medium 单 case 4151.189-4720.558ms。机器：macOS arm64、10 CPU、CPython 3.8.10、SQLite 3.35.5、NetworkX 3.1。未做 Win7 目标机性能验证。
- 最终快照：`evidence/QualityGate/long_gate/optimizer_quality_matrix/2026-09-08-run-final.json`，SHA-256 `c1eacd8015c04e1ad82016db2fcc09f5b2d2c9b33118ca85e0e86c1f901e1e2f`。
- 对照快照：同目录 `2026-09-08-run-b.json`。保存比较：`2026-09-08-comparison-final.json`，status=passed、failures=[]、ratio=3、slack=250ms。
- HEAD 来源：`de96cd3f681bf4f3b1ca9183f347c56f3de8e73a`。最终测量前后 matrix/production 源码摘要一致，但整仓 tracked diff 在并行工作期间变化，所以最终快照正确标为 **unbound_source_changed**；run-b 为 **unbound_dirty_worktree**。这些不是冻结整机后的性能证明，主线程统一冻结后需要重新串行测量。
- 已实际调用 update-baseline，返回 **2**：`formal baseline requires a clean passed matrix run; dirty/changed evidence is diagnostic only`。`optimizer_quality_matrix_rejected_baseline.json` 未创建；没有正式基线更新。
- 全量 clean gate 未执行：当前大量 dirty 和并行改动，后续统一冻结/门禁由主线程统筹。本专项测试通过不能替代整仓 clean proof。

## 范围外检查交接

- 补跑现有 `test_optimizer_graph_ready_v2_elite_repair_contract.py` 和 `test_optimizer_graph_ready_v2_elite_repair_neighbors.py`：当时 **26 passed、4 failed in 2.16s**，未改这些文件。
- 失败节点：`test_remaining_profile_candidate_budget_blocks_repair`（repair_candidate_budget 实际 10，预期 0）、`test_no_v2_elites_due_to_profile_cap_is_explicit`（no_strict_improvement vs skipped_no_elite）、`test_global_deadline_blocks_all_repairs`（no_strict_improvement vs skipped_by_budget）、`test_disabled_repair_keeps_production_profile_search`（实际 9 calls，预期 19）。这是该时点 dirty 现场的记录，不假定后续主线程修改后仍是相同结果。
- 主线程随后告知已完成必跑注册、旧 ratchet 29 项及 A18 publiccompletion 17 项验证；这些没有在本专项重复执行，也不计入本专项 52 项结果。
- 专项排产计时进程均已结束，没有遗留后台性能任务。新增文件保持未提交，既有 dirty/staged 内容全部保留。

## 2026-09-08 来源稳定性定点修复

- 根因：`validate_snapshot` 原来只验证 `proof_binding` 标签与来源记录相符；混合源码/HEAD 的测量只要正确标成 `unbound_source_changed`，仍能进入质量/runtime 比较并通过。
- 定点修改：在元数据校验后，明确要求同一快照的 `source_before/after.source_sha256` 与 `head` 分别相等。不相等则报 `measured <field> changed during run; snapshot is diagnostic-only`。两个比较操作数都经过该检查，CLI compare 返回失败；正式基线入口同样拒绝。诊断保存接口不改，混合版本输出仍可保留用于调查。
- 放行边界：只变整仓 `status_porcelain` / `diff_sha256`，而测量源码摘要和 HEAD 稳定，仍保留 dirty 诊断比较资格；不要求全仓绝对不变。两个独立且各自稳定的测量之间可以具有不同源码摘要/HEAD，避免阻断正常跨版本比较。正式基线的 clean-only 条件没有放宽。
- 新增 9 项 mutation：源码/HEAD 变化分别放在 baseline 和 actual 侧（4项），仅 status、仅 diff、二者变化（3项），两次独立稳定测量的版本不同（2项）；同时覆盖诊断可保存、compare 失败退出码及正式提升拒绝。
- 红测复现 4 failed / 5 passed。该次 pytest 重载模块使最初的回放替换失效，实际触发一次既有矩阵 fixture（18.54s），已结束且没有生成新的正式基线或冻结性能证明。
- 修复后以 `2026-09-08-run-final.json` 为既有真实快照重放：新增 9 passed；相关校验/比较/生命周期共 58 passed、3个实时排程测试未运行，`GreedyScheduler.schedule` 已强制拦截且调用计数为 0。重放在 Python 3.8.10 进程内替换 runner 的 `build_quality_matrix`，未改变测试文件中正常全量运行使用真实矩阵的 fixture。Ruff 与定点 diff whitespace 检查通过。
- 本轮只改比较器、对应测试和本记录，未改生产代码、旧 ratchet、共享注册或旧基线，未提交。完整矩阵及冻结后的性能复测仍由主线程独立执行；本次重放结果不构成完整新性能测量或 clean proof。

## 主线程冻结复跑

- 2026-09-08 关闭全部 SubAgent 后，按 seed=0、预算10秒、候选60、top_k=3、邻域上限8、worker=1 串行跑两轮完整矩阵，每轮 8/8 case 通过。
- 保存为 `evidence/QualityGate/long_gate/optimizer_quality_matrix/frozen-run-a.json` 与 `frozen-run-b.json`；均为 `unbound_dirty_worktree`，运行前后测量源码稳定。
- `frozen-comparison.json` 比较通过，failures=[]，runtime_ratio=3、runtime_slack_ms=250。
- 最终全仓 5937 项通过，前述旧 repair 测试集成交接已完成。正式 tracked 基线没有更新，项目门禁仍被既有依赖基线差异阻塞，不能宣称 clean proof。
