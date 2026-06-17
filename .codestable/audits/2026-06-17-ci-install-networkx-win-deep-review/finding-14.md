# Finding 14：full-test-debt long gate 缓存没有钉住真实 Chrome 运行时身份

- 优先级：P1 阻塞
- 结论：full-test-debt 会强制跑浏览器 smoke，但 long gate 缓存指纹只看部分环境变量，没有再记录 Chrome 二进制、版本和 headless 预检结果。Chrome 变了但路径字符串没变时，缓存可能误复用旧结果。

## 根因

门禁命令把 `REQUIRED_BROWSER_ENV_OVERLAY` 注入 full-test-debt，说明这一步依赖真实浏览器环境。缓存指纹却在本分支移除了历史的 `chrome_executable_resolution`、`chrome_version`、`chrome_executable_identity`、`chrome_headless_preflight`，只剩 `APS_CHROME_PATH` 等字面环境值。

大白话说：测试实际看的是“这台机器上的 Chrome 能不能跑”，缓存却主要记“环境变量长什么样”。如果 Chrome 被替换、损坏、版本变化，但变量没变，缓存可能还当成同一个环境。

## 调用链

- `scripts/run_quality_gate.py`
- `tools/quality_gate_shared.py::build_quality_gate_command_plan()`
- full-test-debt 命令注入浏览器 smoke 环境
- `tools/long_gate_manifest.py` 决定这条长门禁缓存要采集哪些运行时 key
- `tools/long_gate_fingerprint.py` 计算 key 的值

## 证据

- `tools/quality_gate_shared.py:705-710`：full-test-debt 命令带 `env_overlay=dict(REQUIRED_BROWSER_ENV_OVERLAY)`。
- `tools/long_gate_manifest.py:775-798`：full-test-debt 的 env keys 包含 `APS_BROWSER_SMOKE_REQUIRED`、`APS_CHROME_PATH`、Node 信息，但没有 Chrome 版本、真实路径和 headless 预检。
- `tools/long_gate_fingerprint.py:484-506`：运行时指纹分支覆盖 Python、pytest、platform、Node 等，没有 Chrome 身份分支。
- `git diff d4589d77..313f6528 -- tools/long_gate_manifest.py` 显示本分支删除了 `chrome_executable_resolution`、`chrome_version`、`chrome_executable_identity`、`chrome_headless_preflight`。

## 影响

- long gate cache 可能把浏览器相关测试的旧结果当作新环境证明。
- 这会削弱 full-test-debt proof，尤其是 Windows/本地浏览器 smoke 这类强依赖机器环境的检查。

## 建议

- full-test-debt 的缓存指纹恢复 Chrome 真实路径、版本、二进制身份和 headless 预检。
- 或者对强依赖浏览器的 full-test-debt 禁用 long gate cache，只允许真实重跑。
- 增加 gate meta 测试，证明 Chrome 运行时变化会让 full-test-debt 缓存失效。
