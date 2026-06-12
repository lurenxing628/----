# fusion-gantt-fix-pack 验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-06-13
> 关联方案 doc：fusion-gantt-fix-pack-design.md（approved，Codex 设计四轮——首轮 2 阻塞+3 建议全修；二轮 2 残留（术语表 change_view_mode 旧口径/验收场景 3 漏 page_manuals+ui-gantt:94 可检查项）+1 建议（prototype.call 零实例化）全采纳；三轮 1 阻塞（frontmatter 摘要残留旧方案）+1 建议（连带数量口径乱）全修；四轮 **CLEAN**。实现三轮——首轮 PASS-WITH-SUGGESTIONS（1 建议：文档旧文案反向守卫不全）；二轮 BLOCK（守卫漏「不能点击」「灰色入口」）；三轮 **CLEAN**）

## 1. 四件逐项核对

- [x] **①筛选精确匹配**：gantt.js 新增 `equalsI`（大小写不敏感全等，空值放行语义与 includesI 对齐，紧邻定义+导出）；gantt_render.js applyFilters 四点改 equalsI（machine/operator 两分支同改）+头部解构+缺失守卫；gantt.html aria-label「输入批次号关键词」→「选择批次号」。includesI 定义零 diff。
- [x] **②cc-outline 暗色**：aps_gantt.css dark 块（overdue 重申规则后）追加 `html[data-theme="dark"] .aps-cc-outline-outer { stroke: var(--ui-muted) }`；零新增裸 hex（注释 hex 不计——契约测试先剥注释再统计，Codex 核对 :47-53 确认）；inner #38bdf8 暗背景对比充分不补（目检确认）。
- [x] **③删死按钮整壳**：gantt.html :7 link+壳整删；aps_gantt_simulation.css 文件删除；HEX_FREEZE_ALLOWANCE 删行；三个文件九处文字连带全清（ui-gantt.md :21/:36/:83/:94、page_manuals :17/:175、scheduler_manual 三处——新口径「拖拽调整功能尚未开放」）；**实现期发现第十处连带**：test_frontend_ui_language_polish.py 正向锚点「灰色说明入口」过期→改「拖拽调整功能尚未开放」（Codex 实现审核确认处理正当）。查看模式说明保留（gantt_help.js:17+手册）。
- [x] **④boot 断言**：`collectZoomSpecMismatches(applyScale)` 纯函数挂 ns（missingDeps 检查段后）；`_zoomSpecsDriftDetected` 用 `Gantt.prototype.update_view_scale.call({options:{}}, mode)` 零实例化逐 9 级比对；vendor 缺失不在此报错（adapter 既有通道）；失配 _showEarlyError+reportClientError 后 **boot 整体 return**（loadAndRender 不导出、DOMContentLoaded 不绑定——fail-loud 不跛行，Codex 确认错误展示不会被覆盖）。

## 2. 验收场景核对

- [x] S1 筛选：JS contract 断言 B1 不匹配 B12/B100、大小写不敏感（b1 命中 B1）、machine/operator 双视图 id+名称等值同语义；浏览器 CDP 实测 B00 前缀筛 0 条/B001 筛 2 条。**已知语义收紧已明示**：URL 手输部分关键词不再模糊筛。
- [x] S2 暗色外圈：CSS 契约锁 dark 块选择器+token 值；浏览器实测 dark stroke `rgb(148,163,184)`（=--ui-muted #94a3b8）、light `rgb(51,65,85)` 不变；暗色截图留证（/tmp/fix14-dark-outline.png）。
- [x] S3 零残留：钉死范围 grep（templates/static/web/tests/.codestable/architecture）`ganttSimulationEntry|aps_gantt_simulation` 零命中；文件不存在断言；HEX 白名单零残留断言；三文件 × 六短语（灰色说明入口/灰色禁用按钮/灰色入口/不能点击/当前页面入口仍禁用/ganttSimulationEntry）反向守卫（实现二轮 BLOCK 补全）；合法文案「灰色不可编辑/灰色项」不误伤。
- [x] S4 boot 断言：node 直跑真 vendor 9 级全配（Month 43200/120 … One Minute 1/18）；红绿自证（桩 applyScale 全配空数组/篡改 Hour step_minutes=999 报 1 条失配含级名与值）；漂移仿真 fail-loud（假 Gantt 写错值→「时间粒度配置与渲染组件不一致」+loadAndRender 不导出）；真实页面 collectZoomSpecMismatches 空数组+ganttError 空。
- [x] S5 回归：tests/gantt 196 passed（含新 6 条）；tests/web_pages 411 passed；daily gate 绿（stash 隔离并行 WIP 后跑、跑完立即 pop）。

## 3. 明确不做反向核对

- [x] includesI 定义零 diff；ZOOM_SPECS/frappe-gantt.min.js 数值零 diff；gantt_zoom.js/gantt_chain_walk.js/gantt_popup.js/gantt_legend.js（#12/#13 段）零 diff；core/services/scheduler 零 diff。
- [x] 无新筛选 UI；Draft 模型/后端零 diff；并行 WIP 零接触（staged 核净）。

## 4. 术语一致性

「精确匹配（大小写不敏感全等）/两份真相 boot 断言（prototype.call 零实例化）/拖拽调整功能尚未开放」design、代码注释、测试 docstring、文档同口径。

## 5. 架构归并

- [x] ui-gantt.md 四处口径更新即本 feature 连带（:21 删壳说明/:36 删 CSS 行/:83 入口说法/:94 模型能力句）。
- [x] ARCHITECTURE.md 无需新段（bugfix 不改架构语义）。

## 6. requirement 回写

design frontmatter `requirement` 为空；纯 bugfix/守卫不新增用户能力语义。结论：**无 requirement 回写**。

## 7. roadmap 回写

- [x] items.yaml：fusion-gantt-fix-pack `status: done` + feature 回填。
- [x] 主文档第 14 条标 ✅ done。

## 8. attention.md 候选盘点

候选 1：「正向锁中文文案的守卫测试（如 test_frontend_ui_language_polish）在删功能时是隐性连带——删旧文案前先 grep tests/ 里的正向锚点」。（仅登记，落不落由用户定。）

## 9. 遗留

- 筛选 UX 重排（多选/搜索）归 #27 controls-rework。
- 裸 hex 迁移（aps_gantt.css 115 存量）归 #6 hex-migration。
