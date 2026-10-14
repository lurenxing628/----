---
doc_type: issue-fix
issue: 2026-10-14-decision-workbench-review
status: resolved
path: fast-track
fix_date: 2026-10-14
related: [decision-workbench-review-instructions.md]
tags: [workbench, projection, runtime, quality-gate, layout]
---

# 工作台独立审查返修记录

基线：`efe047d3b3816db29f0718ba5999aeeb199669bf`。B1—B15 源码及正式静态资源已完成；主对话负责施工稿、产品取舍、独立验收和 Git。主对话已完成受影响真实 UI 的独立验收（parent accepted），按指令将修复状态记为 `resolved` 并冻结交接；完整门禁的 Windows 延期和 C 性能目标分别保留在下文。

## 修改结果

| 项目 | 最终行为 |
| --- | --- |
| B1 / B4 | 共同导出器支持“未设置交期”；完整范围包含末端零工时节点，显式半开范围排除终点，两个前端入口共用 `PlanGanttModel.scopeCaption`。 |
| B2 | 比较唯一范围沿当前 `issueBatchRef`；保留候选与时间选择，异步请求按签名隔离。正常库 DC-01→DC-02 实页与原 harness 通过。 |
| B3 | 跨夜班次保留原 `policy_date`，裁剪时段继续计算容量与占用；日历、详情及导出一致。 |
| B5 | 永久任务 ref 与 `current/before` 侧别一起保存；原安排沿 baseline 原件恢复。 |
| B6 | 全量缓存输入补实际 CJS、前端、编译依赖及 SQL/JSON/Windows 文本；collect 补实际台账依赖，pyc 保持复用。 |
| B7 | 交付、准备、未安排和历史共用 `facts/trial_origin.py` 的保存来源范围；全部安排行先进入上下文，范围外保留行可读。缺 runtime 保持未知；正式待料场景可保存、读回并预览采用，普通未安排仍拒绝；保存 JSON 原件保持。待料纯解析放 `facts/material_deferral_evidence.py`，四消费者直接使用，依赖循环解除。 |
| B8 / B9 / B11 | 切换 coverage 只取统计主体，前驱仍沿完整序列；资源取舍使用自身指标版本，reason 使用共同中文 message。同主体切换 `1→0、delta=-1、better`。 |
| B10 / B12 | 三份现行操作说明同步产物、缓存和下载检查；Chromium 清单与 x64 构建复制源一致。 |
| B13 | OS 非阻塞 mutation guard 贯通启动、发布、停止及退出；壳锁、DB 锁、契约分别保存原身份，每目录独立短期排他。主契约写原 state_dir，配置日志镜像沿原尽力写职责；旧退出保留替换后的新实例文件。入口 state 为必需参数，直接使用原 payload。空 guard 保留并排除产品包。 |
| B14 | 原生 pre-push 保留完整 stdin；按唯一 local_sha 在 detached worktree 执行目标源码，全部通过后写 aggregate cache。安装器保留原 pre-commit 链、保护用户 hook、支持重复安装；主对话已实际安装当前仓 hooks。 |
| B15 | 候选四/二/一列、蓝色选中；收益/代价独立等宽卡并按真实语义着色，摘要共用；无基准一条中性说明。页面详情、试调来源与问题编号展开占独立完整行。共同选中态覆盖 aria-current/data-selected 及冻结格/选中列标题；单行计划目录收至 83px，多行保留限高滚动。 |

B13 移动 cleanup handler 后，既有治理条目沿原 builder 重定位，保留 id、manual、legacy 和 source/status 等字段；原 CLI refresh/check 为 **76→76 条**，14 条更新。启动样本仅改为 131/133，其他源码原字节一致。快照和核对材料在 `evidence/decision-workbench-review/2026-10-14/ledger-repair/`。

## 实际验证

- B1/B4 相关 25 项、B3 既有夜班节点 3 项、B5 原甘特适配 2 项通过；B2 原异步 harness exit 0；B6 host 回归 6 项通过。
- B7 两组相关回归各 17 项通过，含重叠，数量未相加；原保存 JSON、读路径 total_changes 和旧档案语义核对通过。B8 相关切换/基准回归通过，主对话隔离复现原件为 `parent-b7-recheck.log`、`parent-b8-recheck.log`。
- B13 相关 13 项通过，最终定向 7 项通过；首次夹具库身份失配的原失败保留，修复后通过。原件在 `evidence/decision-stage-acceptance/stage-08/b13-runtime-lock/pytest-{first,repair,final,frozen}.log`；必需 state 类型修复后 Pyright 0 errors / 0 warnings，Ruff 和差异检查通过，见 `pyright-type-repair.log`。
- B14 真实临时 Git 回归 **6 passed，17.71s**；覆盖实际目标失败、双 ref、同 SHA 合并、缓存失效、HEAD/dirty 隔离、首次分支/删除、legacy stdin/退出码、临时文件清理、重复安装与冲突。当前仓安装原件为 `hook-install/install.log`，安装操作由主对话执行。
- 本批相对基线新增测试函数 **8**：B6 host 1、B13 4、B14 host 3；新增参数和删除函数均为 0。业务及纯布局沿有效原用例验证。
- B1—B6 当时日常门禁 **519 passed、20 skipped、0 failed，92.34s**，只对应当时范围；原件 `b1-b6-daily-gate.log`。
- 最终正式构建 exit 0：10 个文件、chrome109，见 `final-heading-ui-build.log`；此前构建保留在 `final-ui-build.log`。最终 CSS `1791979961`、JS `1791977112`，正常实例实际加载原件为 `ui-final-assets.json`。表头规则锚定 `body.aps-workbench`，覆盖带 important 的默认表头；纯 CSS 按实际影响复验，其他有效 UI 结果复用。
- 本批完整命令：`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --allow-dirty-worktree --long-gate-cache`。最终 attempt04 全量测试 **762 collected / 726 passed / 36 skipped / 0 failed / 0 collection errors，pytest exit 0**；full-test-debt proof passed，267.1s。门禁前 **16/17 步通过**；第 17 步 required_regressions 因 **15 项 Windows 启动器必需节点 setup:skipped** 返回 1，整体门禁 exit 2，保留 failed/deferred_by_user。最终长门禁 executed 9 / reused 0 / failed 1。原件 `final-dirty-gate-attempt04.log`，payload、总账及第 16/17 receipt 原字节保存在 `final-dirty-gate-proof/`。
- attempt01 缺 dirty 参数，入口 exit 2 / executed 0；attempt02 在 Pyright 暴露 Optional state，已修复；attempt03 在台账旧位置失败，已同步；四份 attempt 原日志全部保留。attempt04 在最后一行表头 CSS 返修前执行；其后仅改该选择器并正式构建，业务源码保持。按主对话明确范围复用全量/其他页面证据；最后表头实页复验通过，真实 pre-push 仍检查最终提交。

## 实页与原始导出

原件统一位于 `evidence/decision-workbench-review/2026-10-14/`。正常库未重排、采用或造样例；原进程统一冷启后，业务七表行数、原 run_ref 和四个 candidate_ref 保持，见 `normal-{before,after}-restart.json`。

- 正常实例 **http://127.0.0.1:59615** / PID **50528**；库 `/private/tmp/aps-decision-workbench-20261013/db/decision.sqlite`；instance_id `db3aa0a6a51f4a2089a04956930735f2`。最新公开健康、资产和身份交接为 `normal-final-handoff.json`，实例保持运行。
- 候选/收益/摘要/页面详情：`ui-comparison-no-baseline-after-1280.png`、`ui-tradeoffs-after-1280.png`、`ui-summary-after-1280.png`、`ui-page-details-after-1280.png`。标题 top 一致，摘要无裁剪，无基准说明只出现一次。
- 窄屏与键盘：`ui-comparison-after-560.png`、`ui-tradeoffs-after-560.png`；页面宽与 scrollWidth 均 560，radio ArrowRight/ArrowLeft 与 summary Space 实际通过。
- 最后返修：`ui-context-reference-expanded-final-1280.png` 中编号宽 934px / flex-basis 100%；`ui-plan-selected-final-1280.{png,json}` 中 row 和冻结首格均 rgb(239,246,255)，目录 83px。临时尺寸已恢复默认。
- 详细比较最终实页：`parent-ui-final/11b-selected-heading-final.{png,json}`，CSS1791979961 下选中表头与正文均 rgb(239,246,255)，表头文字 rgb(29,78,216)；未选中表头保持原浅灰，页面无横溢出。最后同类问题已通过。
- 试调实际来源使用既有单工序夹具的独立 TemporaryDirectory；主对话宽屏与 Space 开合通过，原件 `parent-ui-final/08-trial-details.{png,json}`。B 的 560 单列原件为 `ui-controlled/trial-details-560.{png,json}`。metadata 完整保存在 `ui-controlled/instance.json`；PID48561 已正常停止、临时根目录已移除，见 `ui-controlled/closed.json`。
- `export-fixed/` 下实际导出原字节：未指定交期 CSV/XLSX 各 1 行，状态“未设置交期”，预计完工 2026-09-09T08:45:00，截止/超期为空；完整末端点 CSV 8 行，包含 09:00 零工时节点；同一显式半开范围 CSV 7 行。主对话正常 UI 实际下载的 15 行 CSV 在 `parent-ui-final/07-plan-export.csv`。

## 文件清单与交接边界

下面目录内列出的名称共 76 个 B 实施文件；生成资源只有 `static/workbench/app/main.js` 和 `workbench.css`。主对话所有的路线图、items、stage-acceptance 与 `开发文档/README.md` 单独由主对话处理。

| 目录 | 文件 |
| --- | --- |
| 根目录 | `.gitignore`、`.pre-commit-config.yaml`、`README.md`、`DELIVERY_WIN7.md` |
| `core/services/workbench/facts/` | `changeovers.py`、`decision_baseline.py`、`decision_baseline_source.py`、`delivery_completeness.py`、`resource_projection.py`、`trial_scenario_archive.py`、新增 `trial_origin.py`、新增 `material_deferral_evidence.py` |
| `core/services/workbench/history/` | `conditions_source.py`、`metrics.py` |
| `core/services/workbench/plan/` | `export.py` |
| `core/services/workbench/run/` | `candidate_comparison.py`、`candidate_metrics.py`、`candidate_tradeoffs.py`、`decision_changeovers.py` |
| `core/services/workbench/trial/` | `preparation.py`、`projection.py`、`service.py` |
| `frontend/workbench/app/` | `DashboardCandidateComparisonAPI.js`、`DashboardCandidatePanels.jsx`、`DashboardCandidates.jsx`、`DashboardWorkspace.jsx`、`PlanExportUI.jsx`、`PlanGantt.jsx`、`PlanGanttModel.js`、`PlanWorkspace.jsx`、`TrialWorkspace.jsx` |
| `frontend/workbench/app/styles/` | `21-table-frame.css`、`32-process-trial.css`、`33-plan-gantt.css`、`36-analysis.css` |
| `frontend/workbench/prototype/ui_kits/workbench/` | `workbench-ui.css` |
| `packaging/win7/` | `offline-manifest.json` |
| `scripts/` | `portable_release.py`、`verify_decision_workbench.py` |
| `tests/app_runtime/` | `test_app_new_ui_create_app_smoke.py`、`test_launcher_startup.py`、`test_runtime_db_scope_lock.py` |
| `tests/gantt/` | `test_gantt_adapter_contract.py` |
| `tests/workbench/` | `runtime_reuse_contract.cjs`、`test_candidate_comparison_baseline.py`、`test_changeover_projection.py`、`test_decision_history_api.py`、`test_delivery_projection.py`、`test_delivery_trial_projection.py`、`test_gantt_graph.py`、`test_legacy_resource_projection.py`、`test_run_decision_resource_api.py`、`test_trial_effort_projection.py` |
| `tools/` | `git_hook_blocked_paths.py`、`git_hook_cache.py`、`git_hook_checks.py`、新增 `install_git_hooks.py`、新增 `native_pre_push.py`、`long_gate_manifest.py`、`quality_gate_shared.py` |
| `tools/host_tests/` | `test_gate_runner_and_hooks_content.py`、`test_long_gate_content.py` |
| `tools/wufenchang_demo/` | `builder.py` |
| `web/bootstrap/` | `entrypoint.py`、`launcher.py`、`launcher_cleanup_result.py`、`launcher_contracts.py`、`launcher_paths.py`、`launcher_runtime_lock.py`、`launcher_stop.py`、`launcher_stop_cleanup.py`、`workbench_run_lifecycle.py` |
| `开发文档/` | `系统速查表.md`、`技术债务治理台账.md` |

Windows / PowerShell / CMD / Win7 实际执行统一为 `deferred_by_user`；20,000 工序 4/6/8 候选的 2 秒目标交 C 收口。B 未执行 add/commit/push；当前 dirty 验证按上述范围交接，clean-worktree proof 与最终 Git 由主对话验收后处理。
