# 旧批次组件测试依赖补齐

- 2026-09-11 01:18 +0800，按 Main 定向要求，仅调查并修复 `tests/workbench/test_batch_widgets.py::test_batch_components_chrome109`；没有停止或改动 Main 在途完整执行，也没有处理其 G05 缺规划事实文件的问题。
- 原树实际失败为 `TypeError: Cannot read properties of undefined (reading 'useSnapshot')`，栈在编译后的 `BatchWorkspace.jsx.js:134:33`；随后等待 `B001` 超时只是后果。产品源码 `frontend/workbench/app/BatchWorkspace.jsx:72` 调用 `window.WorkbenchPageContext.useSnapshot`，旧 probe 的文件清单没有加载该模块。
- 原失败目录：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-batch-widgets-_belqhr6`，`batch-result.json` SHA `ecd78bdd95b8c9c78a2c0b4218d4a1db485669d2d4ac0773398506029d5c37f5`。首场景失败和原始 pageerror 保留。
- 唯一代码修改：`tests/workbench/batch_widgets_probe.cjs:7` 在当前源码编译清单中增加 `WorkbenchPageContext.jsx`。与 C 的冻结副本逐行 diff 确认只有这一行差异；原 32 场景、40 图和全部动作、输入、断言均未删改。没有加入空 `useSnapshot` stub。
- 本次 trace 和重跑不要求 caption 或 `PlanProcessOrder` 依赖，不据测试名猜测这两项。加入的真实模块只依赖 React，缺少 Provider 时不记录上下文，这是该独立组件 fixture 的实际宿主边界。
- 修复后的 probe SHA `adb85b9f6b56daa0e5e8ff683deedd528d38fdc7a21ddc99962ca5651e0a91f2`；`WorkbenchPageContext.jsx` SHA `d801bb8d03453734f965cee4c3915279010b0391f5efc41c52dfe1dede066c9f`。
- 原树同一 pytest selector 重跑：`1 passed in 12.73s`；`node --check tests/workbench/batch_widgets_probe.cjs` exit 0。结果目录 `/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-batch-widgets-3my_xlvm`，`batch-result.json` SHA `3434843e84a3f86fd881a37679d92113c7081da19a861516ba96d5e4491b395a`。
- 实际结果：Chrome `109.0.5414.46`，32/32，40 图，14 个当前组件源码哈希由原 pytest 逐一核对，errors=[]、external=[]。`global_build=false`、`production_persistence_tested=false`，仍是独立 mock 组件证据，不能取代 C 的真实 67 场景联验或 Main 的 G05 固定源完整执行。
- 交给 Main/H 的机械输入只有这一个现有 probe 文件及其 SHA；原树很脏且该测试原已 untracked，C 未执行 Git 写操作，不宣称 clean-worktree proof。

```bash
env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m pytest -q -p no:cacheprovider tests/workbench/test_batch_widgets.py::test_batch_components_chrome109
```
