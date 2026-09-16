---
doc_type: issue-report
issue: 2026-09-16-ci-quality-gate-45min-timeout
status: open
severity: P1
created: 2026-09-16
source: 2026-09-16 PR #10 三次 CI 运行均在 45 分钟处被取消；回查 main 历史确认同因
tags: [ci, quality-gate, full-test-debt, timeout, branch-protection]
---

# CI 全量门禁在 45 分钟处被取消，main 的必需检查 quality-gate 自 6 月后再未通过

## 现象

- `.github/workflows/quality.yml` 的 `quality-gate` 作业 `timeout-minutes: 45`，在 windows-latest 上跑
  `python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache`（19 步）。
- main 分支保护要求该检查通过且 `enforce_admins: true`，管理员也不能绕过。
- PR #10（分支 `feat/2026-09-16-scheduler-workbench-batch`）第 3 次运行 35074640082：第 1–17 步全部通过，
  第 18 步 `tools/check_full_test_debt.py --sharded --shard-count 3` 于 08:47 启动，串行分片（2105 个 nodeid）
  单独先跑，到 09:20:57 作业超时被取消时仍未结束；三个并行分片根本没有开始。
- 回查 main：2026-09-14 的运行 34800856044（HEAD 84d717f6，本批之前）同样在第 18 步串行分片（2071 个 nodeid）处被取消。
  workflow 历史里最后一次成功是 2026-06-11（PR `ci/install-networkx-win`），当时全量测试只有 3912 个 nodeid，
  第 18 步在 CI 上耗时 619 秒。

## 规模对比

| 时点 | 测试文件 | test 函数 | 收集到的 nodeid | 串行分片 | CI 上全量测试耗时 |
|---|---:|---:|---:|---:|---|
| 2026-06-11 最后一次 CI 成功（48b7f291） | 554 | 3133 | 3912 | 1111 | 619 秒 |
| 2026-09-14 main（84d717f6，本批之前） | — | — | — | 2071 | 串行分片未跑完即超时 |
| 本批基线 7034b873 | 1222 | 7761 | — | — | — |
| 本批 HEAD 030eba6c | 1265 | 8070 | 17907 | 2102 | 串行分片 33 分钟未跑完即超时 |

本机 Mac 上 6 月同规模（4038 个 nodeid）全量测试 159 秒，CI Windows 跑同规模用了 619 秒，约 4 倍。
按此估算当前 17907 个 nodeid 在 CI 上至少要 50 分钟以上，串行分片还要单独先跑，45 分钟无论如何不够。

## 根因

1. 测试规模自 6 月起翻了三倍多，`timeout-minutes: 45` 没有随之调整；本批只贡献了约 4% 的增量（7761→8070 个 test 函数），
   问题在本批之前就已存在。
2. 分片模式的执行顺序是“串行分片先单独跑完，再并行跑三个分片”（`tools/collect_full_test_debt.py:_run_sharded_pytest`），
   串行分片本身就是关键路径。串行判定规则（`tools/full_test_debt_shards.py`）把整目录 `tests/scheduler_graph/`、
   全部 `test_long_gate*.py`、所有 nodeid 含 `runtime` / `evidence` 的用例都划进串行，共 2102 个，
   其中 114 个是第 17 步刚跑过的启动回归。
3. long gate cache 只在 push 到 main 且作业成功时保存；作业从未成功，缓存从未建立，每次都是全量冷跑。

## 影响

- 任何 PR 都无法满足 main 的必需检查，本批（PR #10）在本机所有能跑的门禁步骤都已通过却无法合并。
- CI 每次白跑 45 分钟后被取消，且不产出第 18、19 步的任何证据。

## 可选处理（待用户裁决）

1. 立即解阻：把 `timeout-minutes` 提到 180（GitHub 托管作业上限 360），先让 CI 把第 18、19 步跑完，拿到真实耗时与全量结果。
   公共仓库标准 runner 不计费，代价是每次 PR 检查 1.5–2 小时。
2. 结构改造（建议单开 cs-feat）：把第 18 步拆成 GitHub matrix 多作业——串行分片按文件组再拆、三个并行分片各一作业，
   最后由一个汇总作业合并 payload 并跑第 19 步，作业名保持 `quality-gate` 以满足分支保护。
   现有 `--worker-payload` / `--worker-nodeids-file` 工作模式可复用，但合并与 clean proof 逻辑需要新写。
3. 顺带收窄串行集合：复核 `*runtime*` / `*evidence*` 两条 nodeid 通配规则是否过宽，并去掉与第 17 步重复的启动回归。
4. 流程层面：分支保护是否继续要求 `quality-gate`，或临时放开 `enforce_admins`，由仓库所有者决定。

## 本轮已做

- 只读核实，未改 workflow、未改分支保护。
- PR #10 的分支已包含第 1–17 步在 CI 上全部通过的提交（030eba6c）。
