# fusion-v2-quickwin-pack 验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-06-11
> 关联方案 doc：fusion-v2-quickwin-pack-design.md（status: approved）
> 实现提交：cd0c2c3e（分支 ci/install-networkx-win）

## 1. 接口契约核对

**接口示例逐项核对**：
- [x] format_public_datetime（web/viewmodels/scheduler_history_summary.py:209-213）："2026-05-05 10:00:00"→"2026年5月5日 10:00" / "debug raw garbage"→"时间记录异常" / None→"-"——由 test_dashboard_schedule_time_display.py 两条用例 + 既有单测（test_scheduler_candidate_plain_language.py:309）实证一致。

**名词层"现状 → 变化"逐项核对**：
- [x] style.css「V1 收编区」：已落 web_new_test/static/css/style.css 末段（@media 之前），含 11 类 + 伴生三件（盒模型不含 transition 行 / aps-spin keyframes / 六个 --aps-* 变量）+ 5 条暗色变体 + 下拉浅色/暗色适配。Codex 审核逐行对照 base.css 源（:344-373/:581-597/:149/:486/:718-730/:409-411/:773-811）确认无漏收无多收。
- [x] `latest_history_time_display` 新字段：dashboard.py:352 产出（helper :237-239 getattr 口径），双树 dashboard.html:137 消费。
- [x] dashboard.html:137 改动：双树同改，cmp exit 0。

**流程图核对**：
- [x] mermaid 图三条线（dashboard 格式化链 / V2 壳挂载链 / 收编区供给链）在代码均有落点：dashboard.py:237/:352、web_new_test base.html:114、style.css 收编区；build_workbench_navigation_links 注入点 render_bridge.py:88 未动（grep 确认）。

## 2. 行为与决策核对

**需求摘要逐项验证**：
- [x] 入口可见：默认 GET / 响应含 aps-workbench-nav 与「计划工作台」（test_default_ui_serves_plan_workbench_menu 实测 + 截图目检下拉展开 7 入口）。
- [x] 孤儿 CSS 救活：/scheduler/config 等页警示框配色+盒模型完整（双主题截图目检：亮色 warning 黄底左色条、暗色变体生效）。
- [x] 时间公开口径：正常值中文格式 / 脏值「时间记录异常」（页面级测试红绿对照）。

**明确不做逐项核对**（反向核对项全过）：
- [x] base.css 未删未改（提交 diff 0 行）。
- [x] render_bridge.py / ui_mode*.py / system_ui_mode.py / factory.py 零 diff（提交文件清单不含，逐文件 diff 0 行）。
- [x] V2 base.html 仅 +1 行挂载，<title> 块与 sidebar nav-item 区零 diff（git diff 实证）。
- [x] style.css 只增不改：diff 无删除行，.alert-* 区(:522-536)与既有 .flash-card 基类(:537)原样。
- [x] 未新增 Jinja filter/global；tools/ 门禁源零 diff。

**关键决策落地**：
- [x] 决策 1（nav 包裹）：base.html:114 `<nav class="top-header-workbench">`，门禁断言钉死结构。
- [x] 决策 2（浅色适配）：收编区 scoped 规则 + 暗色覆盖（截图实证暗色 header 下菜单字色正确——实现期发现暗色隐形问题并净修）。
- [x] 决策 3（:not(.alert) 隔离）：亮色三变体+暗色三变体+盒模型全部带 :not(.alert)（Codex 逐条核对）；双挂元素（V2 base:145、common_draft.js:128）零触碰。
- [x] 决策 4（伴生三件）：盒模型不含 transition 行（既有 0.2s 过渡保留）；keyframes 收编；六变量齐（含第二轮复审抓到的 --aps-radius）。
- [x] 决策 5（路由侧单点格式化）：helper + getattr，None 路径不抛错。
- [x] 决策 6（镜像同改）：cmp exit 0。

**流程级约束核对**：
- [x] 不包 try（纯函数已有测试钉死）；镜像 cmp 过；级联 :not 结构隔离；quickref 缓存失效已知为预期。

**挂载点反向核对（可卸载性）**：
- [x] M1 V2 壳挂载：base.html:114 一处，grep `top-header-workbench` 全仓仅 base.html+测试 2 处。
- [x] M2 收编区：style.css 注释明确分节，可整块定位删除。
- [x] M3 时间消费点：grep `latest_history_time_display` 恰 3 处（路由 1+双树模板 2）。
- [x] M4 门禁断言：test_workbench_nav_entry_contract.py 新增 2 条。
- [x] 反向 grep：本 feature 引用全部落在清单内，无清单外插桩。
- [x] 拔除沙盘：删 M1 一行→入口消失（测试转红）；删 M2 块→样式回裸奔；删 M3 三处+恢复旧行→回旧态；删 M4 两条→守卫消失。无残留。

## 3. 验收场景核对

- [x] S1 默认入口：pytest 实测 + 截图 ✓
- [x] S2 V1 不回归：旧断言 7 条过；V1 不加载 style.css 结构性零暴露 ✓
- [x] S3 三高频页样式：真实服务双主题截图目检（/tmp/aps_quickwin_shots/，本地留档不入 git）✓
- [x] S4 双挂零变化：选择器结构保证 + 截图佐证（暗色 config 页 flash 循环消息配色与改前 alert 口径一致）✓
- [x] S5 三态时间：正常/脏值页面级测试 + None 由 `{% if latest_history %}` 守卫 ✓
- [x] S6 镜像：cmp exit 0 ✓
- [x] S7 先红后绿：实现期先写断言跑红（2 failed 7 passed）再挂载跑绿（9 passed）；required 并行段 1716 passed + serial 段 221 passed ✓
- [x] S8 aps-spin：style.css 含 keyframes（grep=1）；DevTools 加类验证转动 ✓
- [x] S9 脏值播种：显式给 schedule_time 列，红绿对照实证 ✓

**浏览器肉眼验证**：真实服务 5613 端口，亮/暗双主题截图（首页、config、gantt、下拉展开态）目检通过。

## 4. 术语一致性

- `top-header-workbench`：全仓 2 处（挂载+测试断言）一致 ✓
- `latest_history_time_display`：3 处一致 ✓
- 「V1 收编区」：style.css 注释与 design 同名 ✓
- 禁用词核对：未引入 plan_role/scenario_id 等内部字段暴露（改动面无此类字段）✓

## 5. 架构归并

- [x] ARCHITECTURE.md「顶层计划工作台入口」条：已更新为双壳挂载（V2 top-header nav 包裹 + 收编区适配 + 门禁双壳断言）。
- [x] ARCHITECTURE.md「首页计划员值班台」条：已补时间公开口径单点格式化一句。
- [x] ui-gantt.md：本 feature 未触及甘特行为，无需更新。

## 6. requirement 回写

design frontmatter `requirement` 为空。本 feature 不新增用户能力——「计划工作台入口」能力本身在 2026-06-01-workbench-nav-entry feature 已落档（该 feature requirement 亦为空，能力记载在 ARCHITECTURE.md），本次只是把既有能力在默认界面接通 + 修存量样式/时间缺陷，属缺陷修复非新能力。结论：**无 requirement 回写**。

## 7. roadmap 回写

- [x] aps-frontend-fusion-items.yaml：fusion-v2-quickwin-pack `status: done`（validate-yaml 通过）。
- [x] 主文档第 5 节第 1 条：已标 ✅ done + 提交号。

## 8. attention.md 候选盘点

候选 1：「跑本地 dev 服务用 `app.run(use_reloader=False)`——reloader 在 `python -c` 启动方式下会因 argv 重放崩溃」。判据：下个 feature 起服务截图还会撞。
候选 2：「headless Chrome 截暗色主题：响应 HTML 落盘后在 <head> 预写 localStorage.setItem('aps_theme','dark') + <base> 指回服务」。判据：后续大量改版 feature 都要双主题截图。
（仅登记，落不落由用户定。）

## 9. 遗留

- 并行会话把 core/infrastructure/backup.py 推到 503 行，daily gate 的 test_file_size_limit 在工作区红——非本 feature 引入，归该会话收口。
- V2 下拉 hover 配色按浅色 header 适配，待 fusion-tokens-single-source（第 5 条）token 化后裸 hex 收编。
- 收编区整体是临时层：fusion-dual-track-retirement（第 2 条）转正搬家时随 style.css 一起成为唯一主样式；fusion-css-layer-split（第 7 条）拆层时收编区并入对应分层文件。
- 实现期顺手发现：V2 暗色下浅色适配会隐形（已净修，暗色覆盖规则随收编区落盘）。
