---
doc_type: fix-note
date: 2026-09-10
status: completed
scope: R1-K
---

# R1-K 测试登记与共享影响面接合

本文件记录首批 579 冻结；随后获准的 SGS/L/SQLite support 增量及最终 581 计数见同目录 `round1-registry-final-increment.md`，两次验证与源哈希不混用。

## 冻结结论

- K 的代码与测试写集已冻结，第一轮本次登记完成；不等待 D/L，不进入下一轮。
- 当前为 **579 required / 85 supplemental / 33 required groups**，missing、duplicates、unknown 均为空；真实测试发现检查无漏登。
- 相对 FD 的 553/84/33，增加 25 个业务/依赖边界 required 文件、1 个 registry required 文件和 1 个真实浏览器 supplemental 文件。
- 306 个 required 文件仍 untracked，即原有 280 加本轮 26。没有修改 tracked 检查，也没有 git add、stage 或 commit。
- 多人已有大量 dirty；这只是源码哈希绑定的局部验证，不是全仓、最终 HEAD 或 clean-worktree proof。

## 修改范围与证据

- `tools/test_registry_groups_workbench.py:133`：D 的 execution/plan-read 依赖边界测试归入原有 `workbench_registry`；该组本来就覆盖真实 import scanner 的源码根目录，不扩大普通台账测试组。
- `:260` 起按已出现的具体文件登记 A/B/C/D/E/F/G/H/I/J/MAIN 测试；未按 `test_round1_*.py` 自动扩张 target。I 的 input/compute 分到 `workbench_run_compute`，models/candidates 分到 `workbench_run_jobs`；MAIN host/runtime 分到 `workbench_system`。
- `:47` 及各原台账 scope 补 `core/services/execution/**/*.py`。新六模块现在触发全部原有 20 个 required 和 13 个 supplemental 组，不再只有 2/0。
- `:38` 精确声明 `core/services/common/{plan_identity,plan_query,bounded_plan_query}.py`。新共享读取覆盖旧 scheduler 查询的全部 16 个 required / 13 个 supplemental 影响组；当前 required 共 22 个，包括真实 report、migration、outsourcing 及原有 common 组。
- `tools/test_registry_groups_misc.py:32` 和 `tools/test_registry_groups_scheduler.py:423`：补齐旧 batch/resource 与 analysis/report 两组对新共享 plan-read 模块的 scope。
- `tools/test_registry_groups_workbench.py:367`：覆盖新 canonical `core/services/system/backup_restore.py`、旧 `web/routes/system_backup_actions.py`、unit_excel 根及真实叶模块；entrypoint、system_actions、system_journal、host/runtime 由对应已有 scope 覆盖。`tools/test_registry_groups_misc.py:232` 保留旧 system UI 消费者对迁移实现的影响选择。
- `tools/test_registry_groups_workbench.py:889`：B 的真实 Chrome 文件工作流只登记为 supplemental；浏览器脚本、Python `-m` workbook probe、support、harness 仅作输入。没有把跳过或缓存元信息测试说成真实浏览器验收；K 未重跑 B 的 Chrome 流程。
- `tests/gate_meta/test_workbench_round1_registry_contract.py:47`：冻结旧 553/84 的每组归属与完整顺序哈希，只允许本次逐项声明的增量。`:84`/`:104` 锁新共享模块影响组，`:157` 锁真实 owner 和 required parent 的源变更指纹失效。
- `tests/gate_meta/workbench_round1_registry_support.py:3` 是独立的预期清单，不从生产 registry 反推期望；没有 test 定义，不是 pytest target。
- 原 `test_workbench_registry_contract.py` 和 `test_long_gate_manifest.py` 的严格顺序、唯一性、计数、required/supplemental 分离断言继续保留，只追加已审阅的具体新条目。新 piece evidence 文件遵循原 `*evidence*` serial 规则，未改分片规则或 perf 标记。
- `tools/test_registry.py`、`tools/test_registry_data.py` 的起步已有 dirty 原样保留。未写 MAIN 的 `tools/quality_gate_shared.py` startup 样本点或治理台账，未写全局配置、baseline、依赖、产品代码。

## 实际验证

全部 pytest 使用 `.venv/bin/python`、私有 basetemp/cache、`APS_DB_PATH=/tmp/aps-r1-k-XINZqC/private.db`、私有日志/备份/模板目录，以及私有 `PYTHONPYCACHEPREFIX`。没有生产库、全局 build、预览服务、全站 gate、5000 压测或 Win7 发布操作。

| 检查 | 实际结果 |
| --- | --- |
| 初次单项 registry | fixture 导入中报 `SchedulePlanResolution` 缺失，发生于 D 迁移中间状态；未改别域，后续真实导入恢复 |
| 第一趟三个 registry/manifest 文件 | 1015 passed / 6 failed；新 runtime 刚出现、两组 plan-read scope 未补，以及本次新预期中的 serial 和 probe 形式错误均保留原失败证据 |
| 修正后的增量定点 | 138 passed，24.98s，`/tmp/aps-r1-k-XINZqC/registry2.xml` |
| 最终八个 registry/cache/consumer 文件 | **1323 passed**，140.57s，无跳过，`/tmp/aps-r1-k-XINZqC/consumers.xml` |
| 短 integration 四文件 | **47 passed**，8.17s，无跳过，`/tmp/aps-r1-k-XINZqC/integration.xml` |
| MAIN 同文件 runtime 增量 | 最新 14 个 runtime 用例加真实测试发现检查，**15 passed**，1.70s，`/tmp/aps-r1-k-XINZqC/runtime-final.xml`；未改变登记文件数量 |
| Ruff | 七个本轮改动/新增 Python 文件全部通过 |
| 定点 Pyright | `--project pyrightconfig.tools.json` 显式三个 registry 文件：3 files / 0 error / 0 warning；两个新 meta 文件：2 files / 0 error / 0 warning，不是默认全仓检查 |
| Python 3.8 grammar | 九个 registry/meta 文件通过 |
| diff / 源冻结 | `git diff --check` 通过，冻结后的九个登记相关源文件 hash drift 为空 |

最终消费者命令在相同隔离环境下执行：

```bash
.venv/bin/python -m pytest -q -o cache_dir=/tmp/aps-r1-k-XINZqC/cache --basetemp=/tmp/aps-r1-k-XINZqC/consumers --junitxml=/tmp/aps-r1-k-XINZqC/consumers.xml tests/gate_meta/test_workbench_registry_contract.py tests/gate_meta/test_workbench_round1_registry_contract.py tests/gate_meta/test_long_gate_manifest.py tests/gate_meta/test_workbench_cache_environment.py tests/gate_meta/test_long_gate_required_regression_cache.py tests/gate_meta/test_long_gate_startup_regression_cache.py tests/gate_meta/test_quality_gate_registry_split_scope_contract.py tests/gate_meta/test_verify_required_regressions_from_full_test_debt.py
.venv/bin/python -m pytest -q -o cache_dir=/tmp/aps-r1-k-XINZqC/cache --basetemp=/tmp/aps-r1-k-XINZqC/integration --junitxml=/tmp/aps-r1-k-XINZqC/integration.xml tests/workbench/test_round1_host_boundaries.py tests/workbench/test_round1_runtime_observation.py tests/schedule/route_view/test_scheduler_plan_identity_evidence_contract.py tests/workbench/test_round1_report_export_contract.py
```

以上测试集合有重叠，不相加声称独立覆盖数。私有 cache 测试只证明缓存语义，不是执行了 full gate 或 Chrome 验收。

## 源绑定

`/tmp/aps-r1-k-XINZqC/handoff-freeze.json` 保留九个登记相关源、全部本次登记测试源的 SHA-256、coverage 和 staged patch hash；该 JSON 自身 SHA-256 为 `4f59583629f70ad50149737dfb9bfbd84c26054692743a1f3570b6d3cfd2605e`。

| 本轮写集 | 冻结 SHA-256 |
| --- | --- |
| `tools/test_registry_groups_workbench.py` | `7aff65d00d5b348c5c8897af3328a0a3212c911975322f281a780889f50a9f1c` |
| `tools/test_registry_groups_misc.py` | `d9e97e9ff32b57dd2c38ac018ce03983ce4181087b303ef60c5be677f84c0a5b` |
| `tools/test_registry_groups_scheduler.py` | `c8907d61f9386ab9a7a48d6d9d25f592690dc458276f0059c702ae19943ef3c6` |
| `tests/gate_meta/test_workbench_registry_contract.py` | `aca9bd44b5faa07351ec4f8aaa7260ed866a864a4d698ae8b06f786c9f68d420` |
| `tests/gate_meta/test_workbench_round1_registry_contract.py` | `4418a753351dda407913ae5fef8a6e19f141fc4d126c35ab7cc47fbdb47203fd` |
| `tests/gate_meta/workbench_round1_registry_support.py` | `d9998b67b75436fae8c980f3ea2654f2e45236c1b84ae082c08713d6003b66be` |
| `tests/gate_meta/test_long_gate_manifest.py` | `2cc41c1fee01c50fdc11d9339c794fabc834c2c601679e7fb9f6bac547ef81fb` |

required registry hash 为 `4b1a100eef623966f5addccded806ce739188c0095ebb9a51d052a0b9bfecce3`；group registry hash 为 `33d4710e08a10f8dfbbab66a5ada442036e37ae21dc16b9a76ed77d6b2be750d`。

MAIN 在 K 冻结后把 runtime 测试由 6 项扩到同文件 14 项，最新文件 SHA-256 为 `1ba860c93930ca7518bcec9eb8c96950dc201d6257eafdb29cfdbadd13e8e823`。本次最后的 `final-recheck.json` 明确记录该变化，不将早先 47 项 integration 冒充新增 8 项的证明；最新增量由单独的 15 项运行覆盖。startup_config、factory、entrypoint 三条路径均实际选择 `workbench_system` 和该 runtime target，且没有走 all-required fallback。K 的九个登记相关源文件仍无 drift。

唯一既有 staged 仍是 `tests/gate_meta/test_frozen_bundle_contract.py`，工作文件 SHA-256 `c7a02daca9a8bfd7c9f57dcb7374a1031534c8e067f8809a9902dbc650487b2b`，整个 staged patch SHA-256 `952a9e734f0c0d73d6c780090ac53a2854134b3523f0a552d3fe362f4f908b7d`，均未改变。

## 剩余边界

- 现有已完整出现的本轮测试均已登记，本次 K 已完成；D/L 若冻结后再新增测试，需要主线单独交回增量，不能把将来文件算入本次证明。
- 306 个 required untracked 是仍然真实存在的 tracked 契约阻断，不通过暂存或豁免消除。
- 未执行全部新业务测试、完整质量门禁、全站验收、5000 容量、Win7 真机/离线发布、旧 UI 下线；不对这些范围作通过声明。
