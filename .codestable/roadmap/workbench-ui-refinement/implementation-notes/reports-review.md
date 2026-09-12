# 报表、复盘与校准界面实施

## 设计与合同

- 只修改 Report*/Review*/Calibration* 的展示和交互；领域读写 API、快照校验、校准采用与锁定流程不变。
- 报表分页继续允许 10/20/50。校准接口允许 1–200，统一控件保留 10/20/50 及已恢复的合法当前档位，不能令原上下文失效。
- 仅当范围 summary.records 精确等于 0 才显示“暂无现场数据”横幅；数值 0 保留，null 是未知，部分缺失继续逐项明确提示。横幅适用的空实际值用可访问的破折号呈现。
- 工序与校准详情接入 WorkbenchDetailPanel；来源按键值/列表呈现，不直接打印 JSON，技术引用默认折叠且完整保留。
- 报表中心/执行复盘页签复用已有 go()，保留 scope/topic/returnTo。详情焦点和 Escape 交由共享面板，列表保留焦点恢复及表内滚动。
- 日期按字段语义使用 WorkbenchFormat；旧系统原存储时间不擅自转时区。新增样式位于 app/styles/37-reports.css。

## 验证清单

- [x] 新合同覆盖：无现场/部分缺失/零、结构化来源、合法分页档位、双页签上下文。
- [x] 针对报表、校准关联原合同执行并记录实际结果。
- [ ] 主线程统一构建、真实浏览器 1280 布局、暗色、键盘和详情验证。

## 实现

- `ReportEvidence.jsx` 提供来源键值/列表呈现、无现场状态、仅补充 caption/scope 的表格适配；保留既有 DataTable 的列拖宽，关键列/操作列在表内固定。
- `ReportWorkspace.jsx` 复用现有 go() 和 returnTo 切换报表/复盘页签；Home/End 与左右键切换后恢复页签焦点。同页返回来源仍可恢复原范围，只有点击当前页签时不重复导航。
- `ReportDetail.jsx`、`CalibrationDetail.jsx` 改用共享详情面板；技术编号默认折叠，报工数量与更正前后值完整保留。旧系统存储时间仍明确按原样声明。
- `ReportControls.jsx`、`CalibrationControls.jsx` 接入合法分页档位；空态、读取态统一。校准导出禁用理由已改为就地提示，并删除原有重复提示。
- `ReviewCharts.jsx`、`ReviewChartViews.jsx` 接入共享分页/空态与表格语义。三个组件的静态样式迁至 `styles/37-reports.css`。
- `CalibrationAdoptionControls.jsx` 的静态样式也迁入同一 CSS 文件，并使用统一层级与圆角 token；本域已无内嵌 `<style>`。页签保留 Alt/Ctrl/Meta 箭头的浏览器行为。
- 四份本域浏览器 harness 更新源文件接线，直接读取当前 CSS 并记录 SHA-256；`WORKBENCH_UI_NARROW_WIDTH=1280` 可重跑窄屏矩阵，默认仍保留 1392 基线。

## 已执行验证

- 报表读取/边界/执行台账读取与边界、校准完整性/路由/计算方法：123 passed（17.75 秒）。
- 报表 API + 原 mock 浏览器 + 真实 SQLite ledger 浏览器 + 新展示合同：4 passed（36.19 秒）；包含 1920/1392 明暗两色、24 张 mock 截图、36 张 ledger 截图、范围全部导出、修订前后值、caption/scope 与列拖宽保留断言。
- 校准 widgets + 新合同：2 passed（13.06 秒）；校准 lineage 及该文件其他原合同曾有完整 14 passed。
- 首轮 1280 矩阵：17 passed / 2 failed。报表 mock 的单横幅/0/部分缺失与页签 Home/End 焦点已通过；校准 widgets 通过。lineage 的浏览器动作全部通过，但测试运行中共享源发生修改导致最终 SHA 比对失败；ledger 的共享组件运行错误正在按完整堆栈核对。未放宽错误或源码绑定断言。
- 视觉检查额外发现共享 `22-shared-controls.css` 的 `.plana` 前缀没有覆盖报表/校准；共享 owner 已将通用范围修正为 `body.aps-workbench`，随后增补两列布局宽度和焦点的真实 DOM 断言并重跑。

## 本域最终复验

- 共享列表控件改为强依赖后，修正四份 harness 的源顺序为 `WorkbenchControlBridge` → `WorkbenchControls` → `WorkbenchListControls`；ledger 的初始化错误已消失。
- 最后一次真实 SQLite 浏览器复验：`WORKBENCH_UI_NARROW_WIDTH=1280` 下，`test_report_ledger_widgets.py`、`test_calibration_widgets.py`、`test_calibration_lineage_ui.py::test_chrome109_real_lineage_ui` **3 passed（83.90 秒）**。保留源 SHA 比对，零页面异常、全部范围导出、来源不改指与修订前后数据断言通过。
- `report_widgets_probe.cjs` 复用已留存的真实 SQLite 捕获 fixture，在当前源码和当前 CSS 下完成 **4 组 / 24 张截图，errors=[]、external=[]**。覆盖 1920×1080 与 1280×924 的明暗主题；新增真正 DOM 验证：右侧详情 320px 两列、打开/关闭焦点、caption/scope、列拖宽保留、单横幅及 0/未知/部分缺失区分、Home/End 页签焦点、Alt/Ctrl/Meta 箭头直通。该轮是捕获 DTO 的浏览器验证，不冒充新的 SQLite 采样。
- 最终独立 Node 展示合同通过，修改过的 tracked 源文件 `git diff --check` 通过。本域产品源码已冻结。

最终证据保存于 `/tmp/aps-wbui-implementation-20260912/reports-1280-final-v2`、`reports-ledger-1280-final`、`calibration-1280-final`、`calibration-lineage-1280-final`；每份 result JSON 包含浏览器版本、源哈希、截图与读写边界。1280×720、全应用最终 build_id 绑定、质量门禁由主线程统一收口；这些结果不是 clean-worktree proof。

状态：本域实现与针对性验收完成，待主线程统一终验。工作区原有调度优化暂存/未暂存内容，本任务不修改、不暂存、不提交。

## 冻结后的定点合同修复

复核确认 `StructuredFacts` 原先只按 `_ref/_refs/_snapshot` 字段名收纳引用，遗漏诊断 `code/rule/rule_code/diagnostic_code/request_key` 和原存储字段中的完整长十六进制引用。现在这些内容交给 `WorkbenchReference` 默认折叠；非业务字段中至少 32 位且完整匹配的十六进制字符串也收纳，包含嵌套列表。

业务批次号、工序号、名称、备注、数量和工时仍按原语义展示；包含引用的一整段业务说明不误收纳。传给折叠组件的值保持原类型与完整内容，引用列表中的 null、0 也不再被字符串拼接丢失。

仅修改 `ReportEvidence.jsx` 与独立展示合同探针。新增合同先复现 `code` 未收纳失败，再修正；最终 `.venv/bin/python -m pytest tests/workbench/test_ui_refinement_reports_review.py -q` 为 **1 passed（0.64 秒）**。按协调要求不重启全量浏览器；主线程最终构建需包含这次定点源变化。
