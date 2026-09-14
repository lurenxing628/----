---
doc_type: audit-remediation-plan
audit: 2026-09-13-frontend-ui-ux-review
created: 2026-09-13
reviewed: 2026-09-13
status: draft
---

# 前端 UI/UX 修改建议方案

配套报告：[index.md](index.md)。本方案只做「改什么、怎么改、怎么验证」的建议，实施时按阶段走 cs-issue / cs-refactor 流程，逐阶段交付。2026-09-13 复核后重写，删掉了会破坏构建、被门禁拦下或与既有裁决相反的条目。

## 目标与原则

1. **顺现有体系，不另起炉灶**：颜色只动令牌、组件复用已有模式（图例虚线边、EmptyState、WorkbenchDetailPanel），不引入新依赖、新框架。
2. **Win7 + Chrome 109 兼容不动**：不使用 Chrome 109 之后的 CSS / JS 能力；`ui-monospace`、容器查询之类不可依赖。
3. **不破坏既有优点**：令牌治理、双主题零特判、防呆确认链、诚实未知表达、工作区状态恢复、技术错误自动折叠。
4. **三条硬通道**：
   - 原型令牌与原型 CSS（`frontend/workbench/prototype/`）是 `前端设计/` 的 sha256 快照，改动只能改 `前端设计/` 再跑 `scripts/workbench/import_prototype.py --update`；直接改快照会让构建报 Snapshot hash mismatch。
   - 应用样式层（`frontend/workbench/app/styles/`）受 `tests/workbench/test_ui_refinement_style_gate.py` 约束：不写裸色、`!important` 只在 `20-controls.css`、z-index 只用 `--wb-z-*`。
   - 用户可见文案受 `tools/scan_ui_copy.py` + `tools/ui_copy_glossary.json` 约束，术语以 `.codestable/compound/2026-09-13-decision-ui-copy-glossary.md` 为准；要换词先回词表 update。
5. **每阶段独立可交付、独立可回滚**；样式改动过实机截图对比（1280 / 1366 / 1920 × 明暗），改源码后重建 `static/workbench`。

---

## 阶段 0 · Quick wins（预计 1 天内）

| # | 对应发现 | 改动点 | 改法 |
|---|---|---|---|
| 0.1 | finding-02 | `前端设计/tokens/dark.css` → `import_prototype.py --update` | 暗色 `--ui-table-row-hover-bg` 改 `--ui-surface-muted`（#162032）或更亮一档；浅色 hover 一并评估加深 |
| 0.2 | finding-03 | `frontend/workbench/app/styles/34-run.css:158` | 三个不存在的令牌换已定义组合（如 `--ui-info-text` / `--ui-info-bg` / `--ui-primary`）；在 `test_ui_refinement_style_gate.py` 补「`var()` 首参数必须已定义」扫描 |
| 0.3 | finding-05 | `20-controls.css:429` 附近 | `table.wb-table td` 加 `font-variant-numeric: var(--num-variant)`，一处覆盖全仓 |
| 0.4 | finding-13 | `frontend/workbench/app/PreflightControls.jsx:14` | 假单选组改纯文本「已开工工序：保留记录（不可修改）」 |
| 0.5 | P2-V1 | `00-tokens.css` | 定义 `--wb-shadow-color` 为已有令牌的别名（如 `var(--ui-border)`），或在 `前端设计/tokens/` 新增阴影令牌经快照导入；不得在 styles 层写 rgba 字面量 |
| 0.6 | finding-09 | 已完成（工作区，未提交） | 29 处可见位置已改 `WorkbenchTerms.outcomes.unavailable`，随遗留文案改动一起提交 |
| 0.7 | finding-10 | `PreflightWorkspace.jsx:90` | 页脚「预检不生成版本…」改「排产检查不生成版本…」 |

**验证**：0.1–0.3 截图对比；0.2 修后跑样式门禁；0.7 跑 `scan_ui_copy`。

## 阶段 1 · 术语与文案（预计 1 天）

先对照裁决，再动手；下表「依据」列写明每行与裁决的关系。

| 现文案 | 处理 | 依据 |
|---|---|---|
| 检查 / 排产检查 / 预检 | 不统一为「检查」；排产前那道叫「排产检查」，采用前那道叫「预检」。只改 PreflightWorkspace 页脚一词（0.7）。步骤条短标签「检查」是否作简称，交词表维护人确认 | 裁决 :28 / :92 / :93；`ui_copy_glossary.json:312,315-317` 已是门禁 |
| 采用方案 / 正式采用 | 词表补一行裁定按钮名；建议统一「采用方案」，与 `wbui-run-stepper` 一致。不引入「采用为正式计划」 | 裁决未覆盖 |
| 重叠拆轨 | 「时间重叠的安排分行显示」 | 未覆盖，可采纳；`RunCandidateGantt.jsx:110` |
| 不可评估 / 无法评估 | 统一「暂无数据」 | 裁决 B 表「没有值」行；`TrialControls.jsx:5`、`DashboardContract.js:6` |
| 原排产候选 | 「上次排产的候选方案」 | 裁决 :56 与候选行；`TrialControls.jsx:6` |
| 外协独立色 | 「外协工序用另一种颜色」+ 真色块图例 | 未覆盖，可采纳 |
| 完成确认 / 完成并刷新 | 统一收尾动词，词表补一行 | 未覆盖；`RunAdoptionControls.jsx:34`、`DashboardHandling.jsx:21` |
| 「请不要再操作，联系维护人员。」 | 不动。`DashboardSession.js:12-13` 改用 `WorkbenchTerms.outcomes.failure` 模板承载编号 | 裁决 :70 / :146 |
| 值班台跳转标签 | `DashboardPanels.jsx:4` 改读 boot.titles，与侧栏同名 | 裁决原则 2 + :102 |
| 「基础资料」vs「资料总览」 | 不动；如仍有歧义回词表 update，不自造「资料维护」 | 裁决 :102 |
| 「仅影响尚未模板使用…」语病 | 改「仅影响后续尚未使用该模板的计划，不会修改已有批次、历史计划和已执行记录。」；先定位到具体文件行 | 未覆盖 |
| 「返回排产」无条件显示 | 交互项，移到阶段 2（2.13） | P2-L5 |

另外三条策略性修改：

- **首现注释**：候选方案首现加注「还没生效的排产结果」、试调首现加注「模拟调整，不影响正式计划」、齐套括注「物料到齐」。注释文案需进词表。
- **经办人默认值**：记住上次经办人（`RunAdoptionAction.jsx:3`、`TrialAdoptionState.js:35,133`），复用 `TrialViewState.js:3-45` 的作用域化 + 版本化偏好模式；不要复用幂等台账那一类存储。后端只校验非空、≤100、无 NUL（`core/models/workbench_run_adoption.py:32-35`），恢复值仍过 trim 闸门。同时把 `TrialAdoptionControls.jsx:15-17` 的硬编码改回 `WorkbenchTerms.handler`。
- **长说明拆层**：`DashboardPanels.jsx:87` 一句话结论常驻 + 详情折叠；候选页已是折叠态，不动。

**验证**：`python3 -m tools.scan_ui_copy --paths frontend/workbench/app` 全量过；关键页截图走查。

## 阶段 2 · 交互修复（预计 3–5 天）

| # | 对应发现 | 改动 | 备注 |
|---|---|---|---|
| 2.1 | finding-01 + 14 + 16 | 甘特状态双通道编码：critical 加斜纹 / 加粗边、success 条内 ✓；候选甘特补色块图例组件；统一 critical 语义或给拆轨换纹理；现场实际甘特计划基线条改描边空心或加纹理 | 顺 `33-plan-gantt.css:19` 虚线语言扩展；色板若动走快照通道 |
| 2.2 | finding-04 | 现场时间线 planned 条换深一档令牌或描边空心底 | `35-field.css:15`，展开工序详情后截图复核 |
| 2.3 | finding-11 | 资料总览 focus 重置改「数据可能已更新」提示条 + 手动刷新；保留 page / selected / detail | `MasterOverviewWorkspace.jsx:53-55,65`；`aps:master-data-changed` 语义不动；补「切窗不丢位置」测试 |
| 2.4 | finding-12 | 工时 / 归属编辑器加「确认全部 N 道」跨页全选（带二次确认）；保存报错列出未确认工序页码并可一键定位 | 纯前端；服务端协议已是整零件粒度（`test_process_stage_api.py:143-157`）；归属侧沿用 `invalidate()` |
| 2.5 | finding-15 | 候选工作区行动区分组：导航类降为链接样式靠左，采用 / 试调靠右加分隔并标注「不影响正式计划」 | `RunCandidateWorkspace.jsx:109-114` |
| 2.6 | finding-06 | `.scheduling-navigation` 补第三个 pressed 页签「候选方案」；侧栏高亮按 context 加二级提示 | 不新增侧栏项 |
| 2.7 | finding-17 | 列筛选弹层只在锚点移出视口或祖先容器滚动超阈值时关闭；或关闭时暂存已勾选值 | `ResourceTableFilter.jsx:77-95,111`；补探针 |
| 2.8 | P2-I10 | Choice 控件搜索框默认可见；翻页改用 `WorkbenchListControls.Pager` | `ResourceControls.jsx:272-292` |
| 2.9 | P2-I13 | 工艺列表空态复用 EmptyState 四态，带清除筛选动作 | `ProcessWorkspace.jsx:53` |
| 2.10 | P2-I18 | 危险确认两级模型定型：删除类统一勾选确认、恢复类保留打字确认 | `ResourceForms.jsx:127,129`、`ResourceCatalogEditor.jsx:61`、`SystemMaintenanceControls.jsx:37-38` |
| 2.11 | P2-I3 | 采用确认补说明：「旧版本与报工记录都保留，可在计划列表查看和导出；如需恢复旧安排，需重新排产并再采用一版」 | 后端没有「重新启用上一版」能力：计划接口全 GET（`web/routes/workbench/plan_reads.py:127-130`），采用强制以当前正式计划为基线（`core/services/workbench/run_candidate_adoption_storage.py:83-93`）。不得写「可在计划版本里重新启用上一版」 |
| 2.12 | P2-I4 | 值班台「候选方案」类别卡或交付风险区加「去执行排产」入口，带当前范围上下文 | `DashboardPanels.jsx:4` 补 run 目标 |
| 2.13 | P2-L5 | 批次管理「返回排产」按来源显隐；侧栏直入时改「下一步 · 去排产」 | `BatchWorkspace.jsx:119,143` |

**验证**：每项针对性走查 + 截图；2.3 / 2.4 / 2.7 补合同或探针；相关 `tests/workbench/` 回归。

## 阶段 3 · 布局与组件级（预计 1–2 周）

| # | 对应发现 | 改动 |
|---|---|---|
| 3.1 | finding-07 + P2-L1 | 768 高屏的表格限高与嵌套滚动区数量重新评估；内嵌滚动区滚动位置纳入 `WorkbenchNavigation.js:92-104` 的 remember / restore |
| 3.2 | P2-I1 | 抽共用时间轴工具条组件：统一缩放上限、快捷键、命名；三处甘特迁移 |
| 3.3 | P2-L2 + P2-V11 | 原型死 CSS（4 条弹层 z-index 规则）与死令牌（`--leading-*`、`--num-variant` 若 0.3 不消费）清理，经 `前端设计/` 快照通道，挂 `wbui-prototype-css-cleanup` 漏项 |
| 3.4 | P2-V4 + P2-V5 | 密度令牌覆盖扩展到自绘表（作为 `wbui-table-density-noise` 的扩展提案）；控件高度 34px 五处回归 32 / 36 双档，保留 mini 30px 变体 |
| 3.5 | P2-V3 / V8 / V10 | 选中语言统一为 inset 主色条；禁用态统一实色或统一 opacity 一档；等宽字体栈统一为 `monospace` |
| 3.6 | P2-L4 / L6 / L8 | 值班台标签改读 boot.titles；是否升级为全局图标去重交用户拍板；`?view=trial` 入站容忍是否保留交用户拍板 |

原方案中的「排产记录升侧栏第 4 项」与「窄主区详情改覆盖式抽屉、复用 `field-reporting.css:86`」两项撤销：前者与 `wbui-view-tabs-merge` 的 12 项目标冲突，后者引用的原型抽屉 CSS 已无消费者，且 1366 下详情面板本就并排。

**验证**：1366×768 实机逐页走查；`tests/workbench/` 几何探针回归；截图基线对比。

## 阶段 4 · 需后端配合（单独排期）

| # | 对应发现 | 改动 |
|---|---|---|
| 4.1 | finding-08 | 进度口径为「已算完 X/Y 个候选方案」：计数点 `core/services/scheduler/run/schedule_candidate_runner.py:188-210`；后端返回体新增字段须与前端契约（`RunJobAPI.js:48-51` 键集白名单与 `progress === null`）、库表心跳列（`core/infrastructure/workbench_run_schema.py:12-26`，需放宽 CHECK）同一批改。前端先行部分：不确定进度条 + 显眼常驻「正常计算中，请勿关闭」 |

原 4.2「数据表正文 14px 评估」转为索引观察项 O1，改字号档要先推翻 `wbui-tokens-states` 的分档决定，不在本方案排期。

## 风险与注意

- **色板不轻动**：甘特 pastel 色板牵涉暗色镜像与多处消费，阶段 2.1 只加双通道不换色；换色需单独走查，且经快照通道。
- **门禁联动**：样式类改动过 `test_ui_refinement_style_gate.py`；文案类改动过 `scan_ui_copy` 并同步 `ui_copy_glossary.json`；原型改动过 `verify_snapshot`。
- **截图基线**：每阶段交付物附前后对比图，用 `browser-e696/` 同口径的整改后集合，不用 `baseline-current/`。
- **遗留未提交改动**：工作区现有一份 180 个前端文件的文案改动与本轮 finding-09 处置叠在一起，提交前先跑 `scan_ui_copy` 与相关探针。
- **不做的事**：不引入新 UI 框架 / 组件库、不改导航整体结构、不动暗色令牌映射机制、不顺手重构无关模块。
