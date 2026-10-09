---
doc_type: issue-fix-note
issue: duplicate-notices
status: fixed
path: fast-track
date: 2026-10-10
summary: 统一前端提醒的展示归属，修复按钮与正文、页面与详情、错误与结果说明的重复展示
---

# 前端重复提醒修复

用户授权修复只读排查确认的四类重复提醒，并要求共同根因及同类入口一起处理、保留必要提醒、执行针对性验证。

## 根因与修改

1. **操作受限原因有多个展示者。** 继续使用 `ResourceControls.Button` 的 `reasonDisplay`：单个操作由按钮显示正文；同组其他按钮使用 tooltip 和可访问说明，不再额外显示一遍。删除表单中重复的段落；备份的共同限制在记录区显示一次，独立的恢复限制仍单独显示。系统按钮包装层尊重调用者的 `reasonDisplay`。
2. **值班台重复转发同一次读取错误。** 列表错误由列表区域负责，分析错误只表达分析部分自身的失败，并移除分析页签内的第二个错误框。保留原工作区已经存在的列表与分析合并读取改动。
3. **工时校准的页面和详情共同显示过期提醒。** 页面统一显示过期状态，详情保留具体读取失败和“刷新所选记录”操作。
4. **提交失败原因被再次拼进结果提示。** 错误框保留原始失败原因；值班台保存的操作状态负责结果说明，外协被拒后返回表单，只补充未生效及重新提交指引。未知结果仍保留“查询结果”和防止重复提交的提示。

没有新增全页面文本去重器；不同对象的警告、独立失败原因及字段错误保留。按钮禁用、查询结果、草稿及操作记录的处理方式保持原约定。

## 本轮范围

共修改 17 个前端源码文件：

- 共同说明：`ResourceControls.jsx`、`WorkbenchTerms.js`。
- 同类操作入口：`ResourceForms.jsx`、`ResourceCatalog.jsx`、`CalendarDayDialog.jsx`、`OperatorCalendarPanel.jsx`、`ResourceMaterialActions.jsx`、`ProcessFileActions.jsx`、`ProcessDetail.jsx`、`FieldEditor.jsx`、`ProcessGroupEditor.jsx`、`SystemMaintenanceControls.jsx`、`SystemMaintenanceRecords.jsx`。
- 页面及结果提醒：`DashboardWorkspace.jsx`、`CalibrationDetail.jsx`、`DashboardSession.js`、`OutsourcingSession.js`。
- 回归：新增 `tests/workbench/notice_ownership_contract.cjs`，加入现有 `test_ui_refinement_node_contracts.py`；复用现有当前产物 React 渲染工具。
- 运行产物：通过现有离线构建生成 `static/workbench/app/main.js`，目标仍为 Chrome 109。

修改前保留了本轮涉及文件的可恢复副本。原有后端、打包脚本、`DashboardContract.js`、测试支持工具及其他任务的未提交改动没有回退或夹带修改。

## 实际验证

- `python3 scripts/workbench/build.py` 成功，发布现有 10 项离线静态资源。
- 最后一次源码修正及重建后执行：
  `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/workbench/test_ui_refinement_node_contracts.py tests/app_runtime/test_frontend_offline_static_assets.py -q -rs`
  → **14 passed**。其中新增 Node 契约验证 16 处提醒只显示一次，并核对禁用状态、可访问说明、具体失败原因、未知结果恢复入口以及不含备份能力字段的日志查询。
- Playwright 使用当前静态资源、真实 React 和隔离的页面状态，检查报工、基础资料、外协段、值班台读取失败、校准过期、外协被拒、处置被拒共 **7 个场景**：目标正文均为 1 处；相关按钮保持禁用；隐藏说明实际受 CSS 裁剪；0 个页面运行错误。目视核对报工、外协段和校准页面。末次变动只限定备份能力字段的读取边界，上述 7 个场景的组件输入与实现未变，复用其有效浏览器结果。
- 当前混合工作区还完成一次日常门禁：实际选择全部 6 个 required 职责组、105 个目标，全仓 Ruff 通过，**299 passed / 18 skipped**。跳过项未计为通过。门禁运行期间补充了备份/日志边界修正，最终状态以上述重建后的 14 项针对性验证为准，未再次重复全部日常测试。
- 本轮源文件及测试的差异空白检查通过。符号定位工具已执行，未索引到 JSX `Button`，其定义和影响面通过现行源码引用与组件验证确认。

浏览器检查使用隔离状态和静态文件服务，没有连接业务数据库，也没有重新排产。未做业务数据端到端提交、Win7 实机验收、完整质量门禁或 clean-worktree proof，也未发布安装包。

## 提交范围

用户随后明确授权将当前工作区全部项目改动一并提交、推送。因此最终提交同时包含已有的值班台合并读取、静态资源打包、启动器和空闲系统维护改动；相关提交内容与推送门禁结果以 Git 记录为准。本机临时调试配置 `.claude/launch.json` 和运行输出 `logs/aps_launch_error.txt` 保留本地，不作为项目交付文件。
