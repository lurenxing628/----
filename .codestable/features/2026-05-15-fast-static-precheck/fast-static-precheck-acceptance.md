---
doc_type: feature-acceptance
feature: 2026-05-15-fast-static-precheck
roadmap: quality-gate-long-cache
roadmap_item: fast-static-precheck
status: accepted
accepted_at: 2026-05-15
---

# fast-static-precheck 验收记录

## 1. 完成范围

- 新增 `tools/fast_static_precheck.py`，提供 `main(argv=None) -> int` 和 `python -m tools.fast_static_precheck` 入口。
- 默认收集 staged、unstaged、untracked 的 `.py` 文件。
- 支持 `--base-ref REF`，但它只检查 `REF...HEAD` 的已提交差异，不混入 unstaged / untracked。
- 删除文件、非 Python 文件、不存在文件、目录、repo 外路径、运行产物路径和 ruff exclude 类路径不会传给 ruff。
- 路径通过 git `-z` 输出收集，ruff 命令使用 list args，不拼 shell 字符串。
- 局部 ruff 使用 `python -m ruff check --force-exclude -- <targets>`。
- pyright 默认跳过，并说明不是 `pyright_gate_full` / `pyright_tools_full`。
- `scripts/run_quality_gate.py --fast-precheck` 会在完整 command plan 前早退。
- `tools/git_hook_checks.py run-fast-static-precheck` 是独立手动入口，不改变 `run-quality-gate` 和 `run-final-quality-gate`。
- `tests/test_fast_static_precheck.py` 已加入正式 required 测试注册和 quality_gate 分组。

## 2. 明确未做

- 没有接入 `scripts/run_daily_quality_gate.py`；daily gate 当前仍按原口径运行。
- 没有启用 `ruff_check_full` success cache。
- 没有启用 `pyright_gate_full` / `pyright_tools_full` success cache。
- 没有启用 `architecture_fitness` success cache。
- 没有启用 `debt_ledger_sync` / `quickref_vs_routes` success cache。
- 没有写 long gate success cache。
- 没有写 full gate proof。
- 没有声明 clean-worktree full proof。
- 没有把局部 ruff 说成 `ruff_check_full`。
- 没有把 pyright skip 说成 full pyright gate。

## 3. 对抗审查

- 第一轮只读摸底 3 个 Agent 均确认：默认范围应为 staged / unstaged / untracked；局部 ruff 可做；pyright 默认跳过最安全；`--fast-precheck` 必须在完整门禁计划前早退；planned entry 不得启用。
- 第一轮实现后对抗审查发现 roadmap 主文档和 items 仍有 pyright 旧口径、checklist 已实现步骤未标 done、`tests/test_fast_static_precheck.py` 未进入正式注册；已全部修复。
- 第二轮对抗审查发现 roadmap 测试总表还残留“ruff/pyright 失败”说法；已改成“ruff 失败、pyright skip 文案”。
- 第二轮对抗审查发现 `normalize_repo_path()` 使用 `lstrip("./")` 会漏掉 `.limcode/...py` 这类顶层点目录 Python 文件；已改为只去掉字面量 `./`，并补 `.limcode/hooks/check_complexity.py` 测试。
- 最终只读复审确认上述阻塞已消除，可以进入验收。

## 4. 验收核对

- staged / unstaged / untracked 默认纳入：已由 `tests/test_fast_static_precheck.py` 覆盖。
- rename 取新路径：已由 `renamed_old.py -> renamed 新.py` 测试覆盖。
- 删除文件、非 Python 文件、不存在文件和目录跳过：已由目标过滤测试覆盖。
- 顶层点目录 Python 文件不再漏检：已由 `./.limcode/hooks/check_complexity.py` 测试覆盖。
- 无目标 Python 文件返回 0 且不跑 ruff：已由单测覆盖。
- ruff 失败返回失败并输出可复制复跑命令：已由单测覆盖。
- pyright 默认跳过，输出不是 `pyright_gate_full` / `pyright_tools_full`：已由单测和 CLI 实测覆盖。
- `run_quality_gate.py --fast-precheck` 早退，不写 manifest、receipt、summary 或 success cache：已由 `tests/test_run_quality_gate.py` 覆盖。
- hook daily/final 旧语义不变，新 fast precheck 是独立命令：已由 `tests/test_git_hook_checks.py` 覆盖。
- long gate planned entries 不被启用：已由 `tests/test_long_gate_manifest.py` 覆盖。

## 5. 验证结果

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_fast_static_precheck.py`：通过，7 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_run_quality_gate.py tests/test_git_hook_checks.py`：通过，88 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_long_gate_manifest.py tests/test_long_gate_cache.py tests/test_long_gate_cli_controls.py`：通过，104 passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check tools/fast_static_precheck.py scripts/run_quality_gate.py tools/git_hook_checks.py tools/quality_gate_shared.py tools/test_registry.py tests/test_fast_static_precheck.py tests/test_run_quality_gate.py tests/test_git_hook_checks.py tests/test_long_gate_manifest.py`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright tools/fast_static_precheck.py scripts/run_quality_gate.py tools/git_hook_checks.py tools/quality_gate_shared.py tools/test_registry.py tests/test_fast_static_precheck.py tests/test_run_quality_gate.py tests/test_git_hook_checks.py tests/test_long_gate_manifest.py`：通过，0 errors。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/quality-gate-long-cache/quality-gate-long-cache-items.yaml`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/features/2026-05-15-fast-static-precheck/fast-static-precheck-checklist.yaml`：通过。
- `git diff --check`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/git_hook_checks.py check-staged-artifacts`：通过。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --fast-precheck`：通过；它只跑局部 ruff，pyright 默认跳过，不是完整门禁 proof。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m tools.fast_static_precheck --print-targets`：通过；输出当前改动目标文件并完成局部 ruff。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --long-gate-cache-explain`：失败，Chrome headless preflight 报 `chrome_exited_before_devtools`，Chrome 版本输出为 `Google Chrome 148.0.7778.168`。这条命令只是 explain，不是 proof；失败不代表 fast precheck 功能失败，但也不能把 explain 当作已通过。

## 6. Proof 口径

- 未完成 clean-worktree full proof，不能宣称完整质量门禁通过。
- 本次验证只证明 NEXT-9 相关单测、入口测试、局部 ruff/pyright 静态检查和 YAML/diff 检查通过。
- `--fast-precheck` 是快速提前提醒，不是 final quality gate。
- `--long-gate-cache-explain` 不是 proof，且本次在本机 Chrome headless 预检处失败。

## 7. Roadmap 回写

- `.codestable/roadmap/quality-gate-long-cache/quality-gate-long-cache-items.yaml` 中 `fast-static-precheck` 已从 `in-progress` 改为 `done`。
- roadmap 主文档第 1、5、6 节已同步 NEXT-9 完成状态和真实边界。

## 8. AGENTS.md 候选

- 本 feature 未暴露需要写入 AGENTS.md 的新长期规则；已有项目约定已经覆盖“不要把快速预检说成 clean proof”和“质量门禁入口以 scripts/run_quality_gate.py 为准”。

## 9. 遗留

- 本机 Chrome headless 预检会在 `--long-gate-cache-explain` 中意外退出，需要另按 Chrome/浏览器环境 issue 排查。
- NEXT-10 的正式 ruff/pyright 全量缓存仍保持 planned，不能借 NEXT-9 的局部 ruff 结果替代。
