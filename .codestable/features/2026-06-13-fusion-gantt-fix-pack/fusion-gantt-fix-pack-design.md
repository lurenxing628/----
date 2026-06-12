---
doc_type: feature-design
feature: 2026-06-13-fusion-gantt-fix-pack
requirement:
roadmap: aps-frontend-fusion
roadmap_item: fusion-gantt-fix-pack
status: approved
summary: 甘特小修包四件（纯 bugfix/守卫）——①批次/资源筛选 includesI 过匹配改精确等值（B1 不再带出 B12，select option 全是完整 id，URL 部分关键词语义收紧为精确）；②暗色 cc-outline 外圈 #334155 与暗背景同色隐形——dark 块补覆盖；③删「模拟调整」死按钮整壳（含 aps_gantt_simulation.css 与手册三处连带）；④ZOOM_SPECS 与 frappe-gantt.min.js 双份真相 boot 启动期断言（Gantt.prototype.update_view_scale.call 零实例化逐 9 级比对 step_minutes/column_width，不一致走既有 fail-loud 早错通道）
tags: [frontend, gantt, bugfix, module-w]
---

# fusion-gantt-fix-pack design

## 0. 术语约定

| 术语 | 定义 | 防冲突结论 |
|---|---|---|
| 精确匹配 | 筛选值与 meta 字段全等（大小写不敏感保留——后端 id 只 strip 未统一大小写规范，不敏感是防御性宽容而非已证事实需求） | select option value 全是完整 id（collectFilterOptions 收集；URL fallback 追加 option 的 value 是原始值、「批次：」只是显示文字——equals 不受影响），select 路径天然精确；**已知语义收紧**：URL 手输部分关键词（gantt_batch=B1）从模糊筛一片变成只匹配恰好叫 B1 的批次——bugfix 口径，列入验收风险明示 |
| cc-outline 暗色补丁 | `.aps-cc-outline-outer` stroke #334155 在暗色背景（--ui-card-bg #1e293b/边框 #334155）下隐形 | 纯 CSS：dark 块内补覆盖（沿 #12 的「dark 重申压回」模式同块追加）；outline 节点由 gantt_outline.js 建、不内联颜色，JS 零改动 |
| 死按钮整壳 | `#ganttSimulationEntryShell`（查看模式徽标+说明文案+disabled 按钮）gantt.html:160-173 | 删整壳含专用 CSS 文件 aps_gantt_simulation.css 与 link；「当前为查看模式」说明条的口径文案在 gantt_help.js/手册仍保留（删的是死入口不是查看模式说明） |
| 双份真相 boot 断言 | ZOOM_SPECS（gantt_zoom.js 9 级 stepMinutes/columnWidthPx）与 min.js update_view_scale 硬编码表各一份，单边改动即静默漂移（装饰层几何读 min.js 值、范围守卫读 ZOOM_SPECS） | 启动期 `Gantt.prototype.update_view_scale.call({options:{}}, mode)` 逐 ZOOM_SPECS 9 级比对 options.step_minutes/column_width——**零实例化**（new Gantt 构造函数会跑一次完整 change_view_mode 渲染，prototype.call 连这一次都省掉；vendor 数值表藏在方法体内无法纯表 import，prototype.call 是最小读取面）；按 9 级单向核对（min.js 的 YEAR 模式不在 ZOOM_SPECS，不反向全等）；不一致走 gantt_boot 既有 missingDeps/_showEarlyError fail-loud 通道 |

## 1. 决策与约束

**需求摘要**（roadmap 第 14 条，模块 W，纯 bugfix/守卫跑测试即可验收；2026-06-11 用户拍板从七合一拆出）：①select 精确匹配修过匹配；②暗色 cc-outline 补丁；③删「模拟调整」死按钮；④ZOOM_SPECS 双份真相 boot 断言。依赖 #12 done（同甘特 JS 施工冲突解除）。

**复杂度档位**：Web 应用默认档位，无偏离。

**关键决策**：

1. **筛选精确匹配**：`applyFilters`（gantt_render.js:85-92）的批次/资源四个匹配点从 `includesI` 改 `equalsI`（大小写不敏感全等，新小 helper 落 gantt.js 紧邻 includesI）；machine/operator 两分支同改（结构不对称处顺手对齐但不重排逻辑）。`includesI` 本身保留（gantt_legend 等别处可能用）。同步修 gantt.html:206 过时 aria-label（「输入批次号关键词」→「选择批次号」）。
2. **cc-outline 暗色**：aps_gantt.css dark 块追加 `.aps-cc-outline-outer { stroke: var(--ui-muted) }`（亮色外圈 #334155 与暗色 --ui-border #334155 同色隐形；--ui-muted 暗色值是浅灰系在 #1e293b 背景上可辨，且零新增裸 hex）；inner #38bdf8（天蓝）在暗背景对比度充分，**不补**（目检确认项）。CSS 契约断言锁 dark 块 `.aps-cc-outline-outer` 选择器+token 值（沿 #12 锁值模式，不只测存在）。
3. **删死按钮整壳**：gantt.html:160-173 整壳删除 + :7 的 aps_gantt_simulation.css link 删除 + CSS 文件删除；连带同步**三个文件共九处文字**：ui-gantt.md 四处（:21/:36/:83/:94「当前页面入口仍禁用」口径过期）、page_manuals_scheduler_outputs.py 两处（:17/:175）、scheduler_manual.md 三处（:1214/:1216/:1236——「页面上有模拟调整灰色入口」旧说法全清）；另**test_css_token_source_contract.py 的 HEX_FREEZE_ALLOWANCE 字典删 aps_gantt_simulation.css 行**（删文件后白名单残留即 grep 命中）——「模拟调整入口」描述改为「拖拽调整功能尚未开放」口径（查看模式说明保留）。零残留验收命令钉死范围：`grep -rn ganttSimulationEntry\|aps_gantt_simulation --include='*.py' --include='*.js' --include='*.html' --include='*.md' --include='*.css' templates/ static/ web/ tests/ .codestable/architecture/`（排除历史审查档 review-*.md 与 .codestable/features|refactors 历史记录）。无测试阻力（原守卫已 DROP）。
4. **boot 断言**：守卫逻辑拆**纯函数** `collectZoomSpecMismatches(applyScale) -> string[]`（挂 ns 供测试直调——gantt_boot 现状只导出 loadAndRender，私有函数测试够不着）：**零实例化**——`Gantt.prototype.update_view_scale.call({options:{}}, spec.frappeViewMode)` 逐 ZOOM_SPECS 9 级在裸 options 对象上执行 vendor 写值（new Gantt 构造函数会跑一次完整 change_view_mode 渲染，prototype.call 连这一次都省；vendor 数值表藏在方法体内无法纯表 import，这是最小读取面），比对 `options.step_minutes === spec.stepMinutes && options.column_width === spec.columnWidthPx`；boot 启动期（依赖检查段后）调用一次，失配走 missingDeps 同款早错通道（_showEarlyError+reportClientError，不静默跛行）。
5. **测试**：①applyFilters 精确匹配单测（B1 不匹配 B12/大小写不敏感/资源两视图同语义——DOM shim 直调 ns.applyFilters）；②CSS 契约（dark 块含 cc-outline 覆盖断言——沿 #12 锁值模式）；③删按钮反向断言（gantt.html 零 ganttSimulationEntry/aps_gantt_simulation 引用）；④boot 断言红绿自证：`ns.collectZoomSpecMismatches` 纯函数直调——喂桩 applyScale 函数（按 mode 写 options 的最小桩）全配时返回空数组、篡改任一级 step_minutes 返回失配描述（零 Gantt 实例化）。

**明确不做**：不动 includesI 本身与其他消费方；不做筛选 UX 重排（多选/搜索框归 #27）；不开放模拟调整真功能（删死按钮≠开发功能，Draft 模型现状不动）；不改 ZOOM_SPECS 或 min.js 的任何数值（断言是守卫不是改值）；不动 #12/#13 刚落的执行着色/巡检段。

## 2. 名词与编排

### 2.1 名词层

**现状**：`includesI` substring 匹配（gantt.js:75-80），applyFilters 四点消费（gantt_render.js:85-92）；select option 由 collectFilterOptions 从 meta 收集完整 id（gantt.js:156-191），URL 回填 setSelectValueWithFallback 会为未知值追加 option（gantt.js:100-111）；cc-outline 双圈 stroke 写死 #334155/#38bdf8（aps_gantt.css:143-161），dark 块（:706-889）零覆盖；死按钮壳 gantt.html:160-173 + aps_gantt_simulation.css（gantt.html:7 link）+ 三个文件九处文字（ui-gantt.md 四 + page_manuals 两 + scheduler_manual 三）；ZOOM_SPECS 9 级（gantt_zoom.js:20-101）与 min.js update_view_scale 硬编码表两份真相，gantt_boot 已有 missingDeps fail-loud（:45-56）；现有测试：test_gantt_url_persistence（不测匹配语义）、test_gantt_zoom_contract（离线雏形非运行时守卫）。

**变化**：
- 修改 `static/js/gantt.js`：新增 `equalsI` helper。
- 修改 `static/js/gantt_render.js`：applyFilters 四点改 equalsI。
- 修改 `static/css/aps_gantt.css`：dark 块 cc-outline 覆盖段。
- 修改 `templates/scheduler/gantt.html`：删壳/删 link/aria-label 修正。
- 删除 `static/css/aps_gantt_simulation.css`。
- 修改 `static/js/gantt_boot.js`：`_assertZoomSpecsMatchVendor` + 启动期调用。
- 修改 `.codestable/architecture/ui-gantt.md` + `web/viewmodels/page_manuals_scheduler_outputs.py` + `static/docs/scheduler_manual.md`：死按钮文字连带。
- 测试：tests/gantt/ 新文件 test_gantt_fix_pack_contract.py（四件断言）。

### 2.2 编排层

四件互不相干的点修，无新流程图必要：①②③是点位修改；④是 boot 启动序列里插一步守卫（依赖检查 → **zoom 双份真相断言** → 数据加载）。

**流程级约束**：
- ④断言失败必须走 _showEarlyError 显式报错（与缺依赖同款），禁止 console.warn 静默跛行。
- ②零新增裸 hex；③删除后 grep 全仓 ganttSimulationEntry/aps_gantt_simulation 零残留。
- ①只改匹配语义不改数据流（option 填充/URL 回填链路零动）。

### 2.3 挂载点清单

1. `gantt_render.js` applyFilters 四点 — 修改
2. `aps_gantt.css` dark 块 cc-outline 段 — 修改
3. `gantt.html` 死按钮壳/link/aria-label — 修改；`aps_gantt_simulation.css` — 删除
4. `gantt_boot.js` 启动期断言 — 修改
5. 文档连带三个文件九处文字（ui-gantt.md :21/:36/:83/:94、page_manuals_scheduler_outputs.py :17/:175、scheduler_manual.md :1214/:1216/:1236） — 修改
6. `tests/gantt/test_gantt_fix_pack_contract.py` — 新文件

拔除推演：四件各自独立可回退；全回退=恢复 includesI 四点/删 dark 段/恢复壳与 CSS 文件/删断言函数与调用/恢复文档九处文字/删测试 → 完全回到现状。

### 2.4 推进策略

1. ①筛选精确匹配 + 单测 → 绿
2. ②cc-outline dark 段 + CSS 契约断言 → 绿 + 浏览器暗色目检
3. ③删壳与连带 + 反向断言 → 绿
4. ④boot 断言 + 红绿自证 → 绿 → 甘特全量回归 + daily gate

### 2.5 结构健康度与微重构

##### 评估
四件全是点修：gantt.js +6、gantt_render.js ±4、aps_gantt.css +10、gantt.html -14、gantt_boot.js +30、删一个 CSS 文件。无结构问题。compound 无冲突 convention。

##### 结论：不做

## 3. 验收契约

关键场景：
1. 筛选 B1：B1 命中、B12/B100 不命中；大小写混合 id 不漏（equalsI）；machine/operator 视图资源筛选同语义。**已知风险明示**：URL 手输部分关键词（gantt_batch=B1）不再模糊筛出 B1x 系列——bugfix 收紧，验收确认无现存用户依赖路径（书签/文档中无部分关键词 URL 先例）。
2. 暗色主题下关键工序外圈可见（目检+CSS 契约断言 dark 块含 .aps-cc-outline-outer）。
3. 钉死范围 grep（templates/static/web/tests/.codestable/architecture）零 ganttSimulationEntry/aps_gantt_simulation 残留；aps_gantt_simulation.css 文件不存在且 HEX_FREEZE_ALLOWANCE 字典同步删行；**九处文字连带逐项核查**：grep「模拟调整」在 page_manuals_scheduler_outputs.py（:17/:175 旧文案清）与 scheduler_manual.md（:1214/:1216/:1236 旧说法清）零「灰色入口/不能点击」残留、ui-gantt.md 四处（:21/:36/:83/:94「当前页面入口仍禁用」）口径更新；查看模式说明（gantt_help/手册）保留。
4. boot 断言：9 级全配时静默通过；collectZoomSpecMismatches 纯函数红绿自证（桩 applyScale 全配空数组/篡改报失配）；真实页面加载零报错（prototype.call 零实例化零渲染）。
5. 全甘特测试零回归（URL persistence 用完整值不受影响）；daily gate 绿。

明确不做的反向核对：
- includesI 定义零 diff；ZOOM_SPECS/min.js 数值零 diff；#12/#13 落的段零 diff。
- 无新筛选 UI；Draft 模型/后端零 diff。
- 并行 WIP 零接触。

## 4. 与项目级架构文档的关系

验收时归并：ui-gantt.md 死按钮四处删改（:21/:36/:83/:94）即本 feature 连带（验收核对）；ARCHITECTURE.md 甘特条目无需新段（bugfix 不改架构语义，boot 守卫在 ui-gantt.md 记）；roadmap 第 14 条回写 done。
