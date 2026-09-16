---
doc_type: issue-fix-note
status: fixed
date: 2026-09-14
title: 补齐试调导航 SVG 并改名为试调排产方案
---

## 根因与修改

- `web/routes/workbench/navigation_metadata.py` 为 trial 配置 `square-pen`，前端导航校验也允许该名称，但原型 `AppShell.jsx` 的 Ico 图形表没有该项；实际页面仅渲染空 SVG。
- 在正式工作台 `frontend/workbench/app/main.jsx` 增加 NavigationIcon，为 square-pen 提供本地 SVG 路径，其余已支持图标继续交给 Ico；保留导入原型快照不变。
- 将导航元数据中的 trial 标题改为“试调排产方案”，同步菜单、提示文字和宿主页标题。
- 更新既有 `tests/workbench/final_foundation_live_probe.cjs` 的名称预期，并补充全部侧栏菜单必须包含 SVG 图形的检查。
- 执行正式离线构建，更新 `static/workbench/app/main.js` 和 `static/workbench/asset-manifest.json`，目标仍为 Chrome 109。

## 验证

- `.venv/bin/python scripts/workbench/build.py` 成功，build_id 为 `2d81253eb43d6c0821428d8b2322402f0aca3270c382fa59041c35c6ceb4fb53`。
- `.venv/bin/python -m pytest -q tests/workbench/test_final_navigation_host.py tests/workbench/test_ui_navigation_guard.py`：17 passed in 9.34s。
- 对修改的 Python 文件执行 ruff，通过；`git diff --check` 通过。
- 重启本地 production 服务并刷新内置浏览器，实际看到“试调排产方案”及方框铅笔图标；读取 SVG 确认含两个 path。独立打开 `/workbench/trial`，页面标题及顶部标题均为“试调排产方案”。
- 完整门禁尝试 `.venv/bin/python scripts/run_quality_gate.py --allow-dirty-worktree --long-gate-cache`，在执行检查前被活动 APS 实例拦截；没有完整门禁通过证明。为用户继续使用保留服务，未为门禁长时间停机。新增的全量浏览器探针断言未单独执行完整探针，实际页面检查及上述定向测试已执行。

## 工作区与范围

- 本轮为上述 5 个源码/构建/测试文件及本记录，均未提交。
- 保留前轮数据库修复记录、备份目录及运行锁；未修改排产算法或试调业务操作。
- 服务继续位于 `http://127.0.0.1:5000`。
