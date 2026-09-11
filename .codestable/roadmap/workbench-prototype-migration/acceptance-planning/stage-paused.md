# D 域阶段记录：等待独占容量窗口结束

> 历史快照，不是当前状态。Main/B 后续已结束 5000 独占窗口并允许继续功能验证；其后 D 获得候选交付投影、工作区 caption/context 和三处 key 的明确写授权。2026-09-10 22:19 Main 又解除 D-P001..004 产品文件冻结并授权修复，F/C/E 也已解冻，不存在全局 source freeze。本文保留当时证据，不用其中的未实现或暂停状态覆盖后续结果；最新状态见 open-findings.md 与 p001-p004-fix-note.md。

## 范围与结论

- 本域分母为 scheduling 25 + trial 12 = 37 能力族，拆为 `action-inventory.json` 中 146 个稳定动作。该文件只定义分母，不虚写通过状态。
- 冻结 `workbench-capabilities.json` 未改；SHA-256 为 `0cad8e05a5adbadacf0c2ecef1e56f38bb4c97e6948c1dc5a2fc847bcec1ffb2`。
- 收到 Main 独占容量窗口通知后暂停所有新测试、浏览器、构建、全树 hash/扫描；仅进行本域小范围编辑和记录。
- 本阶段不是 37 族完成、不是全站终验、不是完整门禁或 clean proof。

## 本轮真实运行

- 命令：`env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/tmp/aps-final-d-pycache .venv/bin/python -m pytest -q -s -o cache_dir=/tmp/aps-final-d-pytest-cache --basetemp=/tmp/aps-final-d-pytest-sixth tests/workbench/test_final_planning_browser.py -k '1920-light'`。
- 结果：`1 failed, 3 deselected in 14.10s`。失败为探针在全入口同时匹配外壳标题与工作区标题；已将选择器限定到 `[data-plan-workspace]`，暂停期没有重跑。
- 私有证据根：`/private/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-workbench-live-b_1thch3`。
- `final_planning_actions.json` 保留真实 HTTP 请求/响应、成功完成到该位置的 38 个 action ID、完整入口下载 hash、截图路径。不能把此前的部分成功当成整个测试通过。
- 本次使用实际完整 `main.jsx`、真实 production factory、受管 worker、schema 31 文件 SQLite；没有 API mock、单组件替身或浏览器合成业务请求。
- 实际已到：空范围拒绝进入运行、全选/清空/齐套选择、规则控件、日期弹窗、13 道完整工序预检、四候选、共同/分件数量及四个零工时时间点、首次采用 v5、正式甘特分组/搜索/初始基线/资源占用和日历。
- 尚未走到：试调编辑/约束冲突/取消/保存场景/二次采用、原回执恢复、新进程保持；其余 1920/dark、1392/light、1392/dark 未运行。
- `server-final.json` 确认 `http_stopped`、`runtime_shutdown_joined`、`exit_backup_complete_under_lock`、`launcher_locks_released`，`assets_unchanged=true`、`isolation_violations=[]`。PID 46690 经 `ps -p 46690 -o pid=,stat=,command=` 核对已不存在。浏览器在探针 finally 中 await close 后退出。
- 前五次开发探针失败也保留在各独立临时目录。原因均为探针假定空选按钮应 disabled、重复原因文本选择器、或选中状态等待时机；不得登记为产品缺陷。Main 提示的提交钩子短时 stash 不作为产品错误证据。

## 给主线的集成意见

- SH004：正式工作区已有真实 `PlanCatalogUI.Identity`、版本、范围、读取时间；候选显示非正式、受理时事实与范围；试调显示原来源、创建时正式基线和持久引用。不能据此声称空 `.cap-rich` 已显示全局本机来源。
- SH008：最新样本实际按 F4 打开日期弹窗、点击日历日、Escape 取消后核对值，再填写原范围。SH009：采用确认实际填写原因/声明人、Tab 焦点保持模态内、测量模态不超视口、取消后重开确认。截图仍须 Main V 审视。
- delay：`PlanDetailsUI.ProjectionTables` 已有真实 `data.projections.delivery_risks` 子表；后端以全批工序完整性判定交付，缺证据保持未知。最小接入是 enabled_views + main 路由至现有 PlanCenterWorkspace，正式计划复用 PlanWorkspace 风险表及原身份/scope，标题按 delay 区分，不复制算法/DTO。
- RunCandidateWorkspace 没有同等逐批交付风险子表；只有候选比较、任务/未安排和受理时基线。不能只改标题就宣告 DELAY-001..004 完成。
- 当时主入口通过 history.state 保存 plan/trial 上下文，URL 仅 view；同浏览器刷新与新浏览器打开 URL 不可混称。本域新进程恢复脚本设计为真实目录中重新选择原身份，再核对完整任务一致。Main 的导航改动完成后需用最新 fullbuild 再核对。

## 保留边界与下一步

- 本域没有 git add/commit/reset/checkout，没有触碰唯一原 staged 文件、两份源码备份、生产库、旧 preview 53144/PID 73298 或其私有根。
- 全部新增仅位于 `tests/workbench/final_planning*`、`tests/workbench/test_final_planning*` 和本目录，未改产品算法/runtime、共享 factory/host、DTO、构建入口或 global static。
- 等 B 通知恢复后先重跑单样本，把后半链闭合；随后最新源码四矩阵、源 hash 绑定、逐动作 B/K/P 台账和 Main V 待审截图。正式 5000 性能由 Main/B 独占安排，不由 D 发起。
