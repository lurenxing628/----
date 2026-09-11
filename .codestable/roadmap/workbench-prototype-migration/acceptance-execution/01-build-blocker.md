# 完整构建阻断交接

- 2026-09-10 首次私有完整构建成功；随后主线新增 navigation/main/theme/build-order，按当前源哈希检查拒绝旧构建。原证据在 `/tmp/aps-final-e.0df81B/`。
- 19:23 提交钩子短暂 stash 的说明已收到。该时间窗口发生的读源漂移不判产品 bug；原失败仍保存。
- `HEAD=c00972784ccc129957f650836dd2a423792f7049`、dirty 恢复后的新目录 `/tmp/aps-final-e-postcommit.aHyPrN/` 重跑，构建仍返回 1：`Script dependency analysis failed: Unresolved script globals in workbench/app/WorkbenchNavigation.js: scrollX, scrollY`。
- 真实命令及输出：该目录 `build-command.json`。调用的是 `.venv/bin/python -B scripts/workbench/build.py --node /Users/lurenxing/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node --output-dir /tmp/aps-final-e-postcommit.aHyPrN/full-build/static/workbench`。
- 源码位置：`frontend/workbench/app/WorkbenchNavigation.js:35` 和 `:75` 已显式读取 `window.scrollX/window.scrollY`；须由 Main 核对构建全局声明合同，不在本分支修改入口/构建器或缩小检查集合。
- 本轮完整主入口 K/V 暂未运行，不使用历史组件测试或旧构建假报最新全站验收。B 合同测试已写入，未运行项保持未验证。
