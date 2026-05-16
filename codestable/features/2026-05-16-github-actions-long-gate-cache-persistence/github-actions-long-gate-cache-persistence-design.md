---
doc_type: feature-design
feature: 2026-05-16-github-actions-long-gate-cache-persistence
requirement:
roadmap: quality-gate-long-cache
roadmap_item: github-actions-long-gate-cache-persistence
status: approved
summary: 让 GitHub Actions 持久化 long gate cache 运行产物
tags: [quality-gate, ci, cache, github-actions]
---

# github-actions-long-gate-cache-persistence 设计方案

## 0. 术语约定

- long gate cache：完整质量门禁里给长耗时检查准备的成功缓存。它不是跳过门禁，而是先把旧成功结果拿回来，再由门禁重新核对命令、输入指纹、日志和输出文件。
- CI cache persistence：GitHub Actions 跨运行保存一小段本地运行产物。没有这一步，CI 每次都是新机器，上一轮 long gate success cache 不会留下来。
- proof：真正能说明本次通过的是 `python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache` 成功结束。cache hit 本身不是 proof。
- fork PR：来自别人 fork 的 pull request。它可以读取主仓库已有缓存帮助判断，但不能把自己的运行产物写回主仓库缓存。

## 1. 需求摘要

本次要实现 P6：让 `.github/workflows/quality.yml` 在 CI 里持久化 long gate cache。

成功标准：

- workflow 使用 pinned `actions/cache/restore` 和 pinned `actions/cache/save`。
- restore 放在完整质量门禁之前。
- save 放在完整质量门禁之后，并且只在完整质量门禁成功后执行。
- fork PR 不 save。
- CI 正式门禁命令保持 `python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache`。
- 缓存路径只包含已被忽略、long gate 复用需要的 `evidence/QualityGate/` 运行产物。
- 不缓存已跟踪的 `evidence/Conformance/quickref_vs_routes.md`。
- README、开发文档和 roadmap/items 说明：CI cache hit 不是 proof。

明确不做：

- 不改 Python 运行代码。
- 不改变 long gate enabled/planned entry。
- 不启用 `architecture_fitness` success cache。
- 不改变质量门禁命令。
- 不把 `evidence/Conformance/quickref_vs_routes.md` 放进 Actions cache。
- 不提交任何 `evidence/QualityGate/` 运行产物。

## 2. 设计方案

### 2.1 workflow 编排

CI 的顺序变成：

```text
checkout
setup python/node
install dependencies
validate chrome path
restore long gate cache
run python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache
save long gate cache when the gate succeeded and this is not a fork PR
upload evidence artifact
```

restore 要在门禁前，因为 `run_quality_gate.py` 会在启动时读取 `evidence/QualityGate/long_gate/results/*.success.json` 和对应日志、输出 proof。save 要在门禁成功后，因为失败运行不能污染下一轮成功缓存。

### 2.2 缓存路径

缓存只覆盖这些已忽略运行产物：

```text
evidence/QualityGate/long_gate/
evidence/QualityGate/collect_nodeids.json
evidence/QualityGate/current_full_test_debt.json
evidence/QualityGate/full_test_debt_summary.json
evidence/QualityGate/full_test_debt_node_cache.json
evidence/QualityGate/architecture_scan_cache.json
evidence/QualityGate/startup_runtime_regressions.json
evidence/QualityGate/required_regressions.json
evidence/QualityGate/debt_ledger_sync.json
evidence/QualityGate/ruff_check_full.json
evidence/QualityGate/pyright_gate_full.json
evidence/QualityGate/pyright_tools_full.json
```

不放 `evidence/Conformance/quickref_vs_routes.md`。这个文件当前是已跟踪文件，应由 checkout 得到，不能让 Actions cache 覆盖它。

### 2.3 key 策略

cache key 的可恢复前缀用 `quality-long-gate-${{ runner.os }}-py38-deps-${{ hashFiles(...) }}-tooling-${{ hashFiles(...) }}-`。`deps` 部分绑定 `requirements.txt` 和 `requirements-dev.txt`，`tooling` 部分绑定 workflow、pre-commit 配置、门禁脚本、`tools/**/*.py` 和 pyright 配置。这样系统、Python、依赖或门禁工具变化后，不会继续用旧前缀命中。

save 的精确 key 在这个前缀后继续加 `sha-${{ github.sha }}-run-${{ github.run_id }}-${{ github.run_attempt }}`。这样同一个前缀下可以恢复最近成功缓存，但每次保存仍按具体提交和运行编号落到独立 key。

这不会降低安全性，因为 long gate 自己还会重新校验 command、fingerprint、stdout/stderr 日志、输出 proof、schema、runner/tooling hash 和 repo identity。旧缓存拿回来后，如果任何证据不匹配，会自动重跑。

## 3. 验收契约

- S1：`.github/workflows/quality.yml` 有 pinned restore/save。
- S2：restore 在统一质量门禁前。
- S3：save 在统一质量门禁后，并且只在 success 后执行。
- S4：fork PR 不 save。
- S5：CI 命令仍是 `python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache`。
- S6：缓存路径只包含已忽略的 long gate 运行产物，不包含 `evidence/Conformance/quickref_vs_routes.md`。
- S7：restore 前缀包含 OS、Python 3.8、依赖 hash 和 tooling hash；save key 包含 `github.sha`。
- S8：README、开发文档、roadmap/items 明确 CI cache hit 不是 proof。
- S9：workflow 合同测试会解析 YAML，锁住 key、路径、fork save 条件和 CI 命令。

## 4. 回滚方式

如果 CI 缓存出现问题，回滚 `.github/workflows/quality.yml` 中两段 actions/cache 步骤即可。门禁命令本身没有变，所以回滚后 CI 仍会完整执行 `python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache`，只是无法跨运行复用 GitHub Actions 缓存。
