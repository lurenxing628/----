---
doc_type: issue-fix
issue: chrome-headless-preflight-exit
status: fixed
severity: medium
root_cause_type: process-cleanup
tags:
  - quality-gate
  - chrome
  - long-gate-cache
  - browser-smoke
---

# Chrome headless 预检意外退出修复记录

## 1. 问题描述

本地跑 `scripts/run_quality_gate.py --long-gate-cache-explain` 时，Chrome 侧会出现“意外退出”类报错。之前只看命令返回码不够，因为命令可能已经拿到 DevTools 端口并返回成功，但 macOS 仍会把被强杀的 Chrome 展示成崩溃弹窗。

## 2. 诊断方法

本次没有只重复跑完整门禁，而是拆成三层小测试：

- 先直接运行 `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome --version`，确认 Chrome 可执行文件本身能启动并打印版本。
- 再用和 long gate 指纹预检完全相同的参数启动 headless Chrome，确认它能写出 `DevToolsActivePort`，说明 Chrome 不是一启动就坏。
- 最后单独复现清理动作：Chrome 已经正常启动后调用当前 `_kill_process_tree()`，进程返回码为 `-9`。这说明用户看到的“意外退出”不是前面启动失败，而是收尾时被 `SIGKILL` 强杀。

## 3. 根因

根因是 Chrome 预检和真浏览器 smoke 的正常收尾路径用了过硬的退出方式：

- `tools/long_gate_fingerprint.py::_chrome_headless_preflight()` 在 `finally` 中直接调用 `_kill_process_tree()`。
- macOS 下 `_kill_process_tree()` 对整个进程组发送 `SIGKILL`。
- `tests/regression_ui_browser_geometry_smoke.py` 生成的 Node 探针脚本也在 `finally` 里直接 `chrome.kill("SIGKILL")`。

这类强杀适合超时兜底，不适合成功路径。成功路径用强杀会让 Chrome 主进程或子进程像崩溃一样退出，用户侧就会看到“Chrome 意外退出”。

## 4. 修复方案

- 新增温和退出 helper：先发 `SIGTERM` / `process.terminate()`，等待进程正常结束；只有超时不退出时才回退到原来的强杀。
- long gate Chrome headless 预检成功或失败收尾时，改用温和退出 helper。
- 真浏览器 geometry smoke 里的 Node 脚本先 `SIGTERM` 等待 Chrome 退出，只有没退出才 `SIGKILL`。
- Python 侧 Node 探针超时清理也先走温和退出，再按原逻辑兜底强杀。

## 5. 改动文件

- `tools/long_gate_fingerprint.py`
- `tests/regression_ui_browser_geometry_smoke.py`
- `tests/test_long_gate_fingerprint.py`
- `tests/test_ui_browser_geometry_env.py`
- `tools/test_registry.py`

## 6. 验证结果

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_long_gate_fingerprint.py tests/test_ui_browser_geometry_env.py`
  - 结果：`12 passed`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --long-gate-cache-explain`
  - 结果：通过。
  - 说明：这只是缓存决策 explain，不是 quality gate proof。
- 手动 Chrome 退出探针：
  - 改前同类探针强杀后返回码是 `-9`。
  - 改后温和退出返回码是 `0`。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_ui_browser_geometry_smoke.py::test_ui_pages_do_not_create_body_level_overflow_in_real_browser --tb=short -p no:cacheprovider`
  - 结果：`1 passed`

## 7. 未做事项

- 没有改 Chrome 版本，也没有改用户本机 Chrome 安装路径。
- 没有把 `--long-gate-cache-explain` 当作完整门禁证明。
- 未运行 clean-worktree full proof，不能宣称完整质量门禁通过。
