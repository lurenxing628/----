# D 域当前缺口与失败回归

## 结论边界

- 本文记录本轮真实失败和当前未接入口；不修改冻结 planning，不将未测动作改成不适用。
- `evidence-matrix.json` 当前仍是历史四组合证据：同源 `64b6bfb181a1c4a04c2f3b218de1f8ad9c4a56b306fc3be19e0213899b0bfe77`，78 / 146 不同动作，不代表后续全部进度或最终完成。
- Main 已于 2026-09-10 22:19 解除以下 D 域产品文件冻结并授权修复；F/C/E 也在修改，不存在全局 source freeze。D 未改 Main shared navigation 或 G05 build-order。
- 115 动作的 94cb 构建与早期 b7b 预检证据均为历史记录，不覆盖当前进度。P003 已获 Main 批准、已实现并完成同一冻结源码的 12 项四组合测试；不是待审批阻断。当前 P003 回执见 `p003-implementation-note.md`，最小 Main V 索引见 `main-v-p003-minimum.md`。
- `evidence-matrix-p003.json` 原记录 124 / 146；剩余 22 ID 全保留。核对这 22 项中的 ANA-001 后发现旧 `WBP-ANA-001.metrics` 的测试只覆盖现有候选指标，没有覆盖冻结四指标中的“调整工序/换设备数”，因此另列证据范围不足，当前须验证 23 ID，不能继续把该一项当完整合同通过。历史 JSON 不抹除，差额见最小 V 索引和 `remaining-analysis-gaps.md`。

## D-P001：预检返回后丢批次与日期

- 状态：已按授权修复，原失败独立用例先通过，随后正式补齐 1920/1392 深浅四组合；各组 5 动作、77 表逐项不变通过，详见 fix-note。影响 `WBP-RUN-005.return-context`；检查结果失效，六个明确有型输入保留。
- 操作：在私有数据库选择 `Z-D-01`，日期 `2026-09-11` 至 `2026-09-23`；预检识别 1 个未齐套批次；点“查看批次”，批次页准确出现 `Z-D-01`；点“返回排产”。
- 实际：日期变为 `2026-09-10` 至 `2026-09-16`，已选批次由 1 变为 0。
- 证据根：`/private/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-workbench-live-2lbfh6at`。`final_planning_actions.json` 中 `preflight_return` 保存完整原始观察，前 15 个动作成功；`screenshots/final-planning-actions-preflight-return-context-viewport.png` 和同名 `.txt` / `.html` 保留现场。
- 构建与运行：Main `64b6bfb1...`，真实 factory/受管 worker/私有文件 SQLite，无业务 API mock；`page_errors`、`console_errors`、`capture_errors` 均为空。原命令的 JUnit：`/tmp/aps-final-d-browser-extra-preflight.xml`，`1 failed, 3 deselected in 12.22s`。
- 源码原因：`frontend/workbench/app/PreflightWorkspace.jsx:40` 起把输入仅存在局部 `value`，没有发布 `WorkbenchPageContext` 快照；`:65` 起向批次页传定位与 `return_to`，未保存输入。`BatchWorkspace.jsx:127` 返回 `run` 后只能恢复旧空 context，重新取默认日期与空批次。这不是 `WorkbenchNavigation` 应擅自推断的业务输入。
- 失败断言保留在 `final_planning_preflight_actions.cjs`，独立入口为 `test_final_planning_preflight_return.py`，没有 xfail/skip 或降低断言。新增逐字段断言：history context 与原 normalized_input 完全一致且只有六项；无 result/input_ref/write_context/token，返回只发生 GET，不自动重预检/运行。`PreflightWorkspace` 用既有 PageContext 发布有效输入，离页先 invalidate。

## D-P002：正式甘特缺少三个查看入口

- 状态：已按授权接入三个控件；1920/1392 深浅四组合的真实完整链已通过。截图仍待 Main V。
- 要求来自冻结 `WBP-GANTT-001`；`PlanGantt.jsx:79` 起仅有分组、初始基线、搜索及时间轴缩放/定位按钮。时间轴放大、适配不等于展开/收起工作区，不互相冒充。
- `PlanGanttModel.layout()` 以 `projections.baseline.items[*].change` 筛选；未知基线禁用并保留原因。展开使用实际固定视口甘特，时间 zoom 不变，按钮和 Escape 均可收起。展开图标使用当前离线 Lucide 集已有 `chart-gantt` / `x`，没有改共享图标库。
- 同一原失败集合还确认悬停事件次序问题：从底部任务切回首行时，浏览器先 mouseenter 后 scroll；原 effect 无条件清掉仍位于同一真实任务上的 tooltip。修复为滚动后按 elementFromPoint 核对 task_ref 和基线身份。原断言保留，诊断证据为 `aps-workbench-live-5t81hdhf/final_planning_hover-detail.json`，修复后真实 1392 深色完整链通过。

## D-P003：正式甘特详情已接入

- 状态：Main 已批准并登记 `PointContract.js -> PlanProcessOrder.js -> PlanContract.js`，G 已提供 shared parser；D 已完成冻结关系、前后序定位、详情“调整此工序”、真实草稿唯一映射和刷新验证。四组合 K/B/P 已执行，Main V 待独立检查；后续只补缺项，不重开审批或广域审查。
- 原缺口是 `WBP-GANTT-003.predecessors` 缺少前后序入口，`WBP-GANTT-004.trial-link` 只有禁用占位。旧描述属于修复前现场，不代表当前产品。
- 需区分整份计划来源、选中工序身份与创建后的新草稿任务身份；不能把正式 `task_ref` 冒充草稿 `task_ref`，也不能为定位而缩小完整场景采用范围。

## D-P004：试调打印缺 live 实现证据

- 状态：已按授权在真实 Trial Session 接入 scoped beforeprint/afterprint，卸载时移除监听并恢复未完成的临时主题。1392 深色原生打印已通过。
- 冻结 `WBP-TRIAL-011` 要求浏览器打印前转浅色、打印后恢复；不要求新造打印按钮。
- 原缺口：hooks 仅在 `frontend/workbench/prototype/ui_kits/workbench/trial-sample.js:248`、`:249`，旧样例不是真实 live 实现。现修复位于 `frontend/workbench/app/TrialWorkspace.jsx`。
- 验证不是合成事件或 emulateMedia：Chrome 109 原生 `Page.printToPDF` 触发 trusted beforeprint/afterprint，观察 light 后恢复原 dark；整个 localStorage 逐项保持。PDF 与事件见 `aps-workbench-live-2h9jvqyf/final_planning_actions.json.native_print`；没有新造打印按钮。

## 历史构建失败

- 后续新增控制流程在启动前严格校验失败：`ActualGanttWorkspace.jsx` 当前 SHA `b89e4862c051f82d96e050531fd892f9328885ef192465776c3599f8d1b206f4`，旧 `64b6...` manifest 为 `fc98d8da3b56cef575185eabb8a1558a45ffd09e6f991c691780aa79222902ee`。
- 对应私有根 `aps-workbench-live-8pwe71_2` 和 `/tmp/aps-final-d-browser-extra-controls.xml`；仅构建核对失败，尚未启动 host。此结果不是新增业务故障，也不抹去此前运行时源一致的四组合证据。
- 当前冻结完整构建为 `9f54333a9b8abe65cddfa918920607536199439739d4ea0603ef84a18d60a8dd`，223 产物、315 输入。后续只叠加测试到私有源码副本；不等待产品窗口，不改共享 capturer。
