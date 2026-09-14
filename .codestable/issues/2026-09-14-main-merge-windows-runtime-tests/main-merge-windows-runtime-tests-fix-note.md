---
doc_type: issue-fix
slug: main-merge-windows-runtime-tests
status: fixed
created: 2026-09-14
summary: 修正 Windows 门禁中的新 UI 冷启动等待窗和数据库路径大小写断言。
tags: [windows, runtime, tests, quality-gate]
---

# main 合入前的 Windows 运行时测试修复

## 失败现场

- 待合入提交：`fa22665231bf5a7d132a131e9a1598cc60b06f31`。
- GitHub 运行：[34797742858](https://github.com/lurenxing628/----/actions/runs/34797742858)。前 16/19 步通过，第 17 步的 114 个启动与运行时回归中 **112 passed, 2 failed**。
- `test_startup_host_portfile_new_ui` 在 Windows runner 冷启动时 15 秒内未读到运行时契约；同一测试在 macOS 隔离 worktree 中通过。
- `test_real_stop_cli_reports_not_exited_after_token_acceptance` 将生产合同中的全小写 Windows 数据库路径与 `Path` 保留大小写的字符串直接比较。

## 根因与修复

1. 新 UI 真实启动测试验证的是契约最终可用，不包含 15 秒启动性能合同。Windows runner 的冷导入、空库建表和插件启动可能超过原等待窗；仅将首次运行时契约等待上限调整为 45 秒，后续端口、健康检查和清理界限不变。
2. 生产端 `_normalize_db_path_for_runtime` 明确使用 `os.path.normcase(os.path.abspath(...))` 生成数据库身份，仓库其他运行时合同测试也按该规则断言。stop-draining 测试改为比较同样的规范化绝对路径，仍要求目录和文件名完全一致。

未修改产品启动流程、运行时合同生成、进程停止逻辑、Windows 兼容目标、门禁项目或通过标准。

## 验证边界

修复前，在隔离 worktree 中运行远端第 17 步同一组 114 个测试，结果为 **114 passed / 40.75s**；两个失败均不能在 macOS 重现。修复后再次运行同一组测试，结果为 **114 passed / 40.63s**；两份修改测试的 Ruff、Python 3.8.10 兼容语法扫描和 `git diff --check` 也通过。

按用户要求不在本地重跑完整质量门禁；提交推送后由 GitHub Windows 必需门禁验证 Windows 专属行为，远端门禁通过前不视为可合并证明。
