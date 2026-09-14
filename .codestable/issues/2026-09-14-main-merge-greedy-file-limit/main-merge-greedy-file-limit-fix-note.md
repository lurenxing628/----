---
doc_type: issue-fix
slug: main-merge-greedy-file-limit
status: fixed
created: 2026-09-14
summary: 收回 SGS 缓存接线造成的调度器文件行数增长，恢复架构门禁要求。
tags: [scheduler, architecture, quality-gate]
---

# main 合入前的 greedy 文件上限修复

## 失败现场

- 待合入提交：`196f91b729b87267844b3f2a9db481fab6bce029`。
- GitHub 运行：[34796872620](https://github.com/lurenxing628/----/actions/runs/34796872620)。前 14/19 步通过，第 15 步 `tests/gate_meta/test_architecture_fitness.py` 报告 `core/algorithms/greedy/scheduler.py: 503 lines`，超过 500 行上限。
- 两套 Pyright 均已通过，本次失败与上一轮类型错误无关。

## 根因与修复

`core/algorithms/greedy/scheduler.py` 在 `4f14ffbb` 前为 492 行；SGS 评分缓存接线新增统计、挂载和探针合同，使文件增长到 503 行。文件顶部仍保留逐条复述实现细节的长说明，形成了可以无损收敛的重复文本。

将顶部说明收敛为等义的模块职责概述，文件降为 497 行。没有修改导入格式、缓存启用条件、探针合同、调度流程、公开接口、门禁阈值或忽略清单。

## 验证边界

- `.venv/bin/python -m pytest -q tests/gate_meta/test_architecture_fitness.py`：**21 passed / 11.74s**。
- `.venv/bin/python -m pytest -q tests/algorithm/test_sgs_score_cache_equivalence.py`：**32 passed / 6.20s**。
- 两套 Pyright 配置均为 **0 errors, 0 warnings**。
- `core/algorithms/greedy/scheduler.py` 的 Ruff、Python 3.8.10 兼容语法扫描和 `git diff --check` 均通过。

这些是与本次修复直接相关的局部验证。按用户要求不在本地重跑数小时的完整门禁；提交推送后由 GitHub 必需门禁继续验证剩余步骤。
