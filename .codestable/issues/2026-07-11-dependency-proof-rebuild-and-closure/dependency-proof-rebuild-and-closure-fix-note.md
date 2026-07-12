---
doc_type: issue-fix-note
issue: 2026-07-11-dependency-proof-rebuild-and-closure
status: fixed_locally_clean_proof_pending
fixed_at: 2026-07-11
root_cause: 第 7、8 项冻结工具后，正式调用图快照、双循环基线、总哈希和事实文档仍分属旧工具阶段
related: [dependency-proof-rebuild-and-closure-report.md, dependency-proof-rebuild-and-closure-analysis.md]
roadmap: dependency-cycle-governance
roadmap_item: dependency-proof-rebuild-and-closure
tags: [callgraph, import-cycle, baseline, hashes, reproducibility]
---

# 依赖治理终态证据重建修复记录

## 1. 本项边界

本项只重建依赖治理证据，不修改业务代码，也不实施 scheduler A1：

- 冻结第 7、8 项最终工具代码。
- 调用图先写两个独立临时目录，核对文件集合和逐文件 SHA256。
- 生产与含测试循环扫描分别写临时 JSON 和候选 v2 基线，人工核对 SCC、圈内边和 unresolved。
- 差异解释通过后，才刷新正式调用图快照和双基线。
- 最后重建 `.codestable/checkup/baseline.json` 数字与 artifact SHA，并同步事实文档。
- 起点 HEAD 为 `cd6cdf43798e3c6321370e4fceb7150bbe4cef3c`，起点已有 45 条工作区状态记录。
- 全程未调用 subagent，未提交、未推送、未创建 PR。

## 2. 调用图确定性与差异核对

### 2.1 独立双跑

连续输出到：

- `/tmp/aps-dependency-proof-20260711/callgraph-a`
- `/tmp/aps-dependency-proof-20260711/callgraph-b`

两边都恰好包含同一组 10 个 JSON，逐文件 SHA256 完全一致：

| 文件 | SHA256 |
|---|---|
| `articulation_points.json` | `d0a73950942d53bcb2dfce256b89abde9e4c57378b3eb55a74db52f2b5a7663d` |
| `cycles.json` | `d666d885059e5feda385910af99471a4cbb9cac481f220a0d311683567c5b16b` |
| `dataflow_nodes.json` | `31c6e48a48096db05c777ed38b6883b858a3b913e91398797882acc6304f2084` |
| `dynamic_unresolved.json` | `7cc51f7b35257c8dbe54734f9b8dd234cc5fd52933c35c926d7a52d348ac21b0` |
| `edges.json` | `ba3b403f85ddecd59e29a990bc99f3501fdcdaf0e0d26aa1e38ba09b8424a1cf` |
| `functions.json` | `aa0433ff222201968b550ec58164f23ea67b8fef478a9a09be04205f59e0025f` |
| `high_fan_in.json` | `848810e47b88f75903c22582d6bc281fd3b1f214b683125bd2ec0c9d5ad26de8` |
| `islands.json` | `30fca84abdd73a0d78bc924aa9c7f8483b7572f145f0479c65cab5dccb16b6e2` |
| `risk_dataflow.json` | `c7be5b6365f4590d453c51606874ba034b24b39d2f60e64ead97e6830f53d023` |
| `summary.json` | `c3ebef9a0654405f7a1b53e3eb1984cba8254c257b5b12d4fd62c70cd26f851c` |

最终机器结果：

- callable：7329，其中嵌套 def/lambda 316；
- 输出边：25772；
- 确信边：10152；
- ambiguous 边：15620；
- typed 边：0；
- 受限确信简单循环：8；
- island：193；
- parse errors：0。

### 2.2 旧快照到最终快照的解释

第 9 项覆盖前的正式 `summary.json` 已是另一个中间口径：7329 callable、25385 输出边、11331 确信边、14054 模糊边、1179 typed 边；README / `baseline.json` 又停留在更早的 7314/25299/11320/13979/1198。

最终边集核对结果：

- 旧 2692 条 `attr` 关系全部保留。
- 旧 1179 条 typed 关系中，977 条在最终图里保守降为 ambiguous `attr`，202 条因接收者来源不可从调用语法证明而删除。
- 最终另得到 589 条不属于旧 attr/typed 集合的 ambiguous attr 关系，与三元调用点保留和取消 typed 先验合并后的解析结果一致；最终 attr 共 4258 条，净增 387 条输出边。
- `cycles.json` 前后逐字节一致，仍是 8 条已知真实受限简单循环；没有用 KISS 收敛误删真实递归记录。
- `dataflow_nodes.json`、`dynamic_unresolved.json` 和 `cycles.json` 不变；其余图派生文件按最终边集重算。

核对通过后，正式 `.codestable/checkup/latest/callgraph/` 已由 `callgraph-a` 受控覆盖；覆盖后 10 个 SHA 与上表完全一致。

## 3. 双 scope 循环扫描核对

### 3.1 候选基线与正式基线

分别生成：

- `import-production-candidate-baseline.json`
- `import-with-tests-candidate-baseline.json`

结构化比较与逐字节比较结果都是零差异：

| scope | 候选/正式 SHA256 | 目录 SCC | 父包感知 hard 文件 SCC | unresolved | 相对正式基线变化 |
|---|---|---:|---:|---:|---|
| production | `9bced631cba0f75bfaba6255ca057cea141b3d77a6adbac50d98a85ec3e66016` | 6 | 9 | 6 | SCC、成员、圈内边、unresolved 均 0 增删 |
| production-and-tests | `c92c2bb6ca785e31dfd8f6a222234217f5b26520f8aab97c3691a4a1632b4a41` | 7 | 9 | 44 | SCC、成员、圈内边、unresolved 均 0 增删 |

这意味着 alias 重绑定修复没有改变仓库现有真实圈或现有 unresolved 身份；本次双基线“刷新”是用正式 CLI 重写并确认相同内容，不是把未知变化基线化。

### 3.2 生产 SCC 与圈内边

6 个生产 hard 目录 SCC 的成员和圈内规范化模块边数：

| 成员 | 圈内边 |
|---|---:|
| `. / web/bootstrap / web/routes / web/routes/domains/scheduler` | 41 |
| `core/algorithms / core/algorithms/greedy / core/algorithms/greedy/dispatch` | 42 |
| `core/infrastructure / core/infrastructure/migrations / core/models / core/shared` | 28 |
| `core/plugins / core/services/common` | 2 |
| `core/services/report / core/services/report/exporters` | 3 |
| `core/services/scheduler / config / run / summary` | 49 |

9 个父包感知 hard 文件 SCC 的圈内边数依次为 94、45、53、2、4、33、23、4、2；纯显式 hard 文件 SCC 仍为 0。生产父包感知/纯显式 runtime 文件 SCC 仍为 14/5。

A1 的 49 条起点边没有漂移，结构债没有清零；本项不把“相对基线无新增”写成“无环”。

### 3.3 unresolved 逐项解释

生产 6 个站点全部是已有、函数内动态装载：

1. `core/plugins/manager.py:176` — `spec_from_file_location(module_name)`；
2. `core/services/scheduler/__init__.py:39` — `module_name`；
3. `core/services/scheduler/config/__init__.py:22` — `module_name`；
4. `core/services/scheduler/schedule_orchestrator.py:13` — `_TARGET_MODULE`；
5. `data/repositories/__init__.py:110` — `module_name`；
6. `web/routes/domains/scheduler/scheduler_route_registrar.py:31` — f-string 目标。

含测试比生产多 38 个，全部 `context=lazy` 且全部位于 `tests/`：

- `spec_from_file_location('regression_gantt_critical_outline_sync')`：13；
- `spec_from_file_location(module_name)`：5；
- `old_name` / `new_name`：各 4；
- `__import__(module_name)`：2；
- `module_name`：2；
- `spec_from_file_location('run_complex_case_and_export_gantt')`：2；
- 固定名 `aps_run_full_selftest`、`aps_synthetic_case_helpers`、`benchmark_optimizer_proof_harness_script`、`post_change_check_contract`、`test_callgraph_extract`：各 1；
- 变量 `name`：1。

这些合计 38，均是测试装载器或路径拓扑合同，没有混入生产未解析目标。含测试额外 hard 目录 SCC 恰好是既有 `tests/gantt / tests/operation_execution / tests/resource_dispatch / tests/web_pages` 四目录组，11 条圈内边与正式基线完全相同。

### 3.4 聚合数字变化

最终 production：

- 模块 750；
- `hard=8809 / cond=4 / lazy=257 / typeonly=135`；
- 父包初始化边 6654；
- parse errors 0。

相对首次文档的 749/8807/6653，新增模块是拆出的 `tools/import_cycle_graph.py`；`from tools import import_cycle_graph as _graph` 在扫描语义下明确解析到 `tools` 和 `tools.import_cycle_graph` 两个目标，因此模块 +1、hard 边 +2、父包初始化边 +1，未形成新 SCC。

最终 production-and-tests：模块 1443、`hard=13517 / cond=4 / lazy=5017 / typeonly=135`、父包初始化边 13138、parse errors 0。

## 4. 正式证据与文档重建

已重建：

- `.codestable/checkup/latest/callgraph/` 的 10 个 JSON；
- `.codestable/checkup/import_cycles_production_baseline.json`；
- `.codestable/checkup/import_cycles_with_tests_baseline.json`；
- `.codestable/checkup/baseline.json`；
- `.codestable/checkup/README.md`；
- scheduler 架构入口与循环依赖/模块架构两份审计；
- 2026-07-10 工具 issue、第 7/8 项 issue 的后续事实说明；
- dependency-cycle-governance roadmap 与 items YAML。

`baseline.json.artifact_sha256` 现绑定 25 个正式 artifact：四个调用图脚本、四个循环扫描工具、dead-code 工具、codemap 两项、完整 10 个调用图 JSON、dead-code 基线和双循环基线。逐项复算全部匹配；已删除的 `callgraph_type_index.py` 不再出现，`clean_worktree_proof` 仍为 `false`。

## 5. 提交前局部验证

已通过：

- 194 项定向回归：`194 passed in 9.97s`；
- 生产正式循环门禁：返回 0，quiet 模式无输出；
- 含测试正式循环门禁：返回 0，quiet 模式无输出；
- Ruff：19 个现存改动/新增 Python 文件全部通过；
- Pyright tools：`0 errors, 0 warnings, 0 informations`；
- Python 3.8.10 兼容扫描：19 个现存 Python 文件、0 发现；
- CodeStable roadmap YAML 和已更新 frontmatter：通过；
- baseline 25 项 artifact SHA 与机器计数自检：通过。

第一次候选 clean HEAD `9417bde3506d9eb3fc82e3f93337078880e2b41d` 完整门禁运行到第 11/19 步时，防回潮门禁发现三份新测试缺模块 docstring。前 10 步（工具版本、全仓 Ruff、双 scope 循环门禁、4712 项收集、YAML、Python 3.8 扫描和 quickref）均通过，但整次结果仍按失败处理，没有包装成 clean proof。

根因修复只替换三份测试第 1 行无必要的 `from __future__ import annotations` 为模块 docstring；三文件均使用 Python 3.8 可直接求值的 `typing.Dict/List/Tuple` 注解，不依赖 postponed annotations。这个写法不增加或删除物理行，因此既有 `test_callgraph_receiver_resolution.py:24` unresolved 身份不漂移。修后：

- 失败的 anti-regression gate 单独重跑通过；
- 194 项定向回归再次 `194 passed in 9.73s`；
- 三文件 Ruff 与 Python 3.8.10 扫描通过；
- 双 scope 正式循环门禁通过；
- 重新生成的双候选基线与正式文件仍逐字节一致，SHA 仍为 `9bced6...` / `c92c2b...`。

完整脏工作区门禁另行尝试：

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py \
  --allow-dirty-worktree --no-long-gate-cache --no-resume
```

结果为退出码 2，按正式 guard preflight 阻断：`tests/gate_meta/test_callgraph_receiver_resolution.py`、`test_import_cycle_scanner.py`、`test_import_cycle_baseline.py` 仍是 untracked required guard tests。失败总账已写到本机忽略目录 `evidence/QualityGate/quality_gate_manifest.json`，后续步骤没有启动。没有绕过或临时修改 Git index；这正是“必须先提交，再跑 clean HEAD 门禁”的预期硬边界，不能包装成完整门禁通过。

命令包装说明：

- Ruff 第一次把已删除的 `callgraph_type_index.py` 也作为路径传入，因此只报 `E902 file not found`；过滤不存在文件后，同一 19 个现存目标全部通过。
- `.venv/bin/pyright` 的 shebang 仍指向仓库搬迁前路径，直接启动失败；使用当前 `.venv/bin/python -m pyright -p pyrightconfig.tools.json` 后正式配置通过。这是本机 wrapper 路径问题，不是类型错误。
- CodeStable YAML 第一次误用位置参数，工具明确返回参数错误；按 `--file` / `--yaml-only` 真实接口重跑后通过。

## 6. 尚未闭环的唯一硬条件

当前仍是脏工作区，且用户尚未授权提交。因此本项只能标记为 `fixed_locally_clean_proof_pending`：

- 不能声称 clean-worktree proof；
- roadmap 第 9 项保持 `in_progress`；
- `scheduler-a1-decoupling` 继续保持 `planned`，不得启动；
- 只有用户明确授权提交本批治理改动，并在提交后的干净最终 HEAD 上运行完整 `scripts/run_quality_gate.py --require-clean-worktree` 成功，才能把本 issue 和 roadmap 第 9 项改为 completed。
