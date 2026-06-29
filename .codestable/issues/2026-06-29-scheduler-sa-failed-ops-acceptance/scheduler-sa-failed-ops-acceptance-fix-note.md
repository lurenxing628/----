---
doc_type: issue-fix
issue: 2026-06-29-scheduler-sa-failed-ops-acceptance
path: fast-track
fix_date: 2026-06-29
tags: [scheduler, optimizer, acceptance, simulated-annealing, failed-ops]
---

# 模拟退火接受准则失败工序零容忍修复记录

## 1. 问题描述

对抗审核发现,`simulated_annealing` 接受准则只按候选相对 current 的总分差计算概率,没有像 `threshold` 和 `record_to_record` 一样先拦截失败工序数变多的候选。

这会导致一个坏路径:如果候选 `score[0]` 的失败工序数比 current 多,它仍可能靠概率被接受为 current。当前默认生产入口还是 `improve_only`,最终 best 也有严格更好保护,所以它不会直接输出更差排程,但底层合同不完整。

## 2. 根因

`core/services/scheduler/run/optimizer_acceptance.py` 中:

- `threshold` 使用 `_failed_ops_worse(candidate_score, current_score)` 拦截失败工序数变多。
- `record_to_record` 使用 `_failed_ops_worse(candidate_score, best_score)` 拦截失败工序数超过 record。
- `simulated_annealing` 分支直接进入 `_simulated_annealing_decision`,没有失败工序数拦截。

## 3. 修复方案

给 `simulated_annealing` 增加与其 current-score 语义一致的失败工序数硬拦截:

- 候选 `failed_ops` 比 current 多时,直接返回 rejected。
- 拒绝原因写为 `failed_ops_worse`。
- 不抽随机数,避免报告看起来像概率拒绝。
- 失败工序数不变、只是目标值变差时,仍保留原模拟退火概率接受行为。

## 4. 改动文件清单

- `core/services/scheduler/run/optimizer_acceptance.py`
  - `_simulated_annealing_decision` 增加 `failed_ops_worse` 入参和硬拒绝分支。
  - `decide_acceptance` 在进入模拟退火前计算候选是否比 current 多失败工序。
- `tests/algorithm/test_optimizer_vns_sa_local_search_contract.py`
  - 把原模拟退火确定性测试改成“失败工序数相同但目标变差”的场景。
  - 新增“失败工序数变多时模拟退火必须拒绝”的回归测试。
- `.codestable/issues/2026-06-29-scheduler-sa-failed-ops-acceptance/scheduler-sa-failed-ops-acceptance-fix-note.md`
  - 记录本次快速修复闭环。

## 5. 验证结果

- `.venv/bin/python -m pytest tests/algorithm/test_optimizer_vns_sa_local_search_contract.py -q`
  - 结果:16 passed。
- `.venv/bin/python -m pytest tests/algorithm/test_optimizer_vns_sa_local_search_contract.py tests/algorithm/test_optimizer_search_report_contract.py tests/algorithm/test_optimizer_candidate_fingerprint_contract.py -q`
  - 结果:36 passed。
- `.venv/bin/python -m ruff check core/services/scheduler/run/optimizer_acceptance.py tests/algorithm/test_optimizer_vns_sa_local_search_contract.py`
  - 结果:All checks passed。
- `git diff --check -- core/services/scheduler/run/optimizer_acceptance.py tests/algorithm/test_optimizer_vns_sa_local_search_contract.py .codestable/issues/2026-06-29-scheduler-sa-failed-ops-acceptance/scheduler-sa-failed-ops-acceptance-fix-note.md`
  - 结果:passed。
- 行为验证小片段:
  - 输入:`simulated_annealing`,候选分数 `(1.0, 0.0, 0.0)`,current 分数 `(0.0, 100.0, 100.0)`。
  - 结果:`accepted=False`,原因 `failed_ops_worse`,未抽随机数。

## 6. 遗留事项

- 未跑整仓质量门禁。当前工作区本来就是 dirty,所以即使跑门禁也不能形成 clean-worktree proof。
- 未修改生产默认接受准则。当前默认仍是 `improve_only`;本次只修复底层 `simulated_annealing` 合同。
