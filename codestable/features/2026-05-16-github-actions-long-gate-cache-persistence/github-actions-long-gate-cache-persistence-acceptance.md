---
doc_type: feature-acceptance
feature: 2026-05-16-github-actions-long-gate-cache-persistence
roadmap: quality-gate-long-cache
roadmap_item: github-actions-long-gate-cache-persistence
status: accepted
accepted_at: 2026-05-16
---

# github-actions-long-gate-cache-persistence 验收记录

## 1. 完成范围

- `.github/workflows/quality.yml` 已新增 pinned `actions/cache/restore` 和 pinned `actions/cache/save`。
- restore 在 `python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache` 之前。
- save 在完整质量门禁之后，且只在前面步骤成功时执行。
- fork PR 不保存缓存：`pull_request` 事件里只有 head repo 和当前 repo 相同时才 save。
- CI 正式门禁命令没有变化，仍是 `python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache`。
- 缓存路径只包含已忽略的 `evidence/QualityGate/` long gate 运行产物。
- 缓存路径没有包含已跟踪的 `evidence/Conformance/quickref_vs_routes.md`。
- README、开发文档、roadmap 和 items 已写清楚：CI cache hit 不是 proof。

## 2. 明确未做

- 没有修改 Python 运行代码。
- 没有新增或启用 long gate entry。
- 没有启用 `architecture_fitness` success cache。
- 没有改变 CI 质量门禁命令。
- 没有缓存 `evidence/Conformance/quickref_vs_routes.md`。
- 没有提交 `evidence/QualityGate/` 运行产物。

## 3. Proof 口径

- GitHub Actions cache hit 只代表旧运行产物被恢复，不代表本次门禁已经通过。
- 本次 CI 的通过证明仍然只能来自 `python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache` 成功结束。
- long gate 自己仍会重新校验 command、fingerprint、stdout/stderr 日志、输出 proof、schema、runner/tooling hash 和 repo identity；校验不完整就重跑。
- fork PR 不 save，可以避免外部 fork 的运行产物写回主仓库缓存。

## 4. 局部验证

这些验证只证明本次 YAML、文档和配置改动没有明显格式问题，不等同于完整 clean proof。

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python codestable/tools/validate-yaml.py --file codestable/roadmap/quality-gate-long-cache/quality-gate-long-cache-items.yaml`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python codestable/tools/validate-yaml.py --file codestable/features/2026-05-16-github-actions-long-gate-cache-persistence/github-actions-long-gate-cache-persistence-checklist.yaml`：通过。
- `ruby -e 'require "yaml"; YAML.load_file(".github/workflows/quality.yml"); puts "workflow yaml ok"'`：通过。
- `git diff --check`：通过。

## 5. 后续建议

- 建议在 GitHub Actions 上观察一次非 fork PR 或 main push：确认 restore 在门禁前执行、save 在门禁成功后执行。
- 建议再观察一次 fork PR：确认 workflow 可以跑门禁，但 save step 被跳过。
- 如果未来新增 long gate output proof 文件，需要同步 `.gitignore`、hook 文档和 workflow cache path。
