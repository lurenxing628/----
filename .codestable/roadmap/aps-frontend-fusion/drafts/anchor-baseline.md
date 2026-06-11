# 改版基线三件套：锚点爆点清单 / 截图基线 / 打印介质回归清单

> **活文档**（fusion-anchor-baseline-prep 产出，2026-06-12）：每节附可重跑命令，开工前跑命令查活数据，不要信本档的冻结快照；
> EXPECTED_PAGE_SIGNALS（tests/app_runtime/ui_geometry_contract_data.py）是页面信号的**机器真相源**，本档只做导览。
> 用法：所有动 templates/ 或 static/ 的 feature，design 阶段先过一遍第一节对号入座；动打印相关再查第三节；改版前后跑第二节脚本留基线。

## 第一节：锚点爆点清单（六类高危锚）

### ① dashboard 超期卡正则锚（文案+DOM+类名三件套）

- **锚在哪**：`tests/web_pages/test_dashboard_overdue_count_tolerance.py:14-18`
  ```
  re.search(r"超期批次</div>\s*<div class=['\"]stat-card-value danger['\"]>\s*([^<]+)\s*</div>", html, re.S)
  ```
  同时钉死「超期批次」文案、相邻 div 结构、`stat-card-value danger` 类名三件事。
- **改它要动什么**：dashboard.html 的 stat-grid 区任何改动（删卡/换类名/改文案/调结构）都必须先迁此锚——roadmap 4.x 已点名「删 stat-grid 前必须先迁」；它是 required 测试，撞了直接门禁红。
- **缓存税**：dashboard.html 属 templates/**（见缓存税节）。
- **可重跑命令**：
  ```bash
  grep -n "stat-card-value danger" tests/web_pages/test_dashboard_overdue_count_tolerance.py templates/dashboard.html
  .venv/bin/python -m pytest -q tests/web_pages/test_dashboard_overdue_count_tolerance.py
  ```

### ② EXPECTED_PAGE_SIGNALS 20 页信号（机器真相源）

- **锚在哪**：`tests/app_runtime/ui_geometry_contract_data.py:45-178`——每页 `stable_texts`（中文文案）/`ids`（DOM id）/`diagnostic_texts`，reports 两页另有 `forbidden_texts`；页面清单 `UI_GEOMETRY_PAGE_PATHS`（:7-28，20 条 URL）。
- **消费方双档**：HTML 解析档 `tests/app_runtime/test_ui_geometry_html_contract.py`（required，registry 登记）+ 真浏览器档 `tests/app_runtime/test_ui_browser_geometry_smoke.py`（CI skip，本地/部署机 `APS_BROWSER_SMOKE_REQUIRED=1` 强制）。
- **改它要动什么**：改 20 页中任何一页的标题/栏目文案/关键控件 id → **只改 contract_data.py 这一处**（roadmap 4.9 钦定单点）；删页面/改 URL → 同步 UI_GEOMETRY_PAGE_PATHS。
- **可重跑命令**：
  ```bash
  .venv/bin/python -c "from tests.app_runtime.ui_geometry_contract_data import EXPECTED_PAGE_SIGNALS as S; print(len(S)); [print(k) for k in S]"
  .venv/bin/python -m pytest -q tests/app_runtime/test_ui_geometry_html_contract.py
  ```

### ③ test_frontend_ui_language_polish.py 文案依赖面（820 行 255 断言 + 双料指纹源）

- **锚在哪**：`tests/web_pages/test_frontend_ui_language_polish.py`——`_read()` 直读 28 个模板/静态文件做「期望整句 in + 禁词 not in」断言。依赖面：scheduler 5 页 + analysis 5 件套（:22-26）+ 8 个 excel_import 页 + gantt 6 个 JS（gantt_boot/render/decorations/popup/contract/help）+ system/logs.html + reports/utilization.html + scheduler_manual.md。
- **双料指纹源身份（这是它的特殊危险性）**：它在 `tools/quality_gate_shared.py` QUALITY_GATE_SOURCE_FILES 名单（改这个测试文件本身 → gate source proof sha256 变 → 长门禁缓存**全部作废**）+ py38 扫描 fail-on-hit 名单。
- **改它要动什么**：改上述 28 文件中任何文案 → 必须同步改本测试 → 缓存全废。**所以文案变更攒批合入**（roadmap items notes 纪律），不要一句一提交。
- **可重跑命令**：
  ```bash
  grep -n '_read("' tests/web_pages/test_frontend_ui_language_polish.py | grep -o '"[^"]*"' | sort -u
  .venv/bin/python -m pytest -q tests/web_pages/test_frontend_ui_language_polish.py
  ```

### ④ 全模板扫描测试（3 个，新增模板自动入辖）

- **锚在哪**：`tests/web_pages/test_template_no_inline_event_jinja.py`（禁 onclick= 等内联事件混 Jinja）、`tests/web_pages/test_template_urlfor_endpoints.py`（url_for 端点必须真实存在）、`tests/web_pages/test_ui_contract_component_tokens.py`（Jinja 实渲染 ui_macros 宏断言输出结构）。
- **改它要动什么**：新增任何模板自动被前两个扫到——内联事件/坏端点直接红；改 ui_macros.html 宏签名或输出结构撞第三个。
- **可重跑命令**：
  ```bash
  .venv/bin/python -m pytest -q tests/web_pages/test_template_no_inline_event_jinja.py tests/web_pages/test_template_urlfor_endpoints.py tests/web_pages/test_ui_contract_component_tokens.py
  ```

### ⑤ manual 系脚本的 CSS 正则断言

- **锚在哪**：仓库根 `verify_manual_styles.py`（11 处 `_check` 正则断言 ui_contract.css 的 manual 样式，含 `html[data-theme="dark"]` 暗色规则 + 实起 app 断言 manual-main-column 等结构）、`check_manual_layout.py`（浏览器自动化断言 `.manual-related-panel` min-width:0 等布局规则）。
- **改它要动什么**：改 ui_contract.css 中 manual-* 相关任何规则前先 grep 这两个脚本；它们是 long gate ENTRY_FULL_TEST_DEBT input_scopes 成员。
- **可重跑命令**：
  ```bash
  grep -n "_check\|re.search" verify_manual_styles.py | head -20
  .venv/bin/python verify_manual_styles.py
  ```

### ⑥ CDP 探针 JS DOM 硬锚（改壳必撞）

- **锚在哪**：`tests/ui_geometry_probe_page_eval.mjs` 三组硬编码——
  - :63-64 壳层判定：`document.querySelector('header nav, header.top-header, nav.sidebar-nav')` + `document.getElementById('apsThemeToggle')`（hasAppShell 信号，缺一即各页探针报无壳）；
  - :202-207 路径→必需控件 id 映射（/scheduler/ → runEnforceReady/runStrictMode 等 4 路径 7 控件）；
  - :232-235 三张系统表 id（systemLogsTable/pluginStatusTable/systemHistoryTable 多行渲染检查）。
  - 且被 `tests/app_runtime/test_ui_browser_geometry_smoke.py:131-136` 反向钉死（断言探针源码必须包含这些检查点——改探针也得同步改 smoke）。
- **改它要动什么**：改壳结构（header/sidebar/nav 元素或类名）、改主题按钮 id、改上述控件/表 id → page_eval.mjs 与 smoke 测试两处同步。
- **可重跑命令**：
  ```bash
  grep -n "top-header\|sidebar-nav\|apsThemeToggle" tests/ui_geometry_probe_page_eval.mjs tests/app_runtime/test_ui_browser_geometry_smoke.py
  .venv/bin/python -m pytest -q tests/app_runtime/test_ui_browser_geometry_smoke.py
  ```

### 缓存税说明（动模板/静态的固定开销）

- 机制：`tools/long_gate_fingerprint.py` 对 input_scopes 文件算指纹，diff 即缓存作废强制重跑。`templates/**/*.html` + `static/**` 是 **4 个 long gate entry** 的 input_scopes：startup-runtime-regressions、quickref-vs-routes（tools/long_gate_manifest.py:542-555——quickref 不是文案锚但吃这笔税）、debt-ledger-sync、full-test-debt。
- 即：**改任何模板 = 4 entry 缓存作废**；若同时改 language_polish 测试 = gate source proof 作废 = 全量重跑。攒批合入是唯一摊薄手段。
- 本档自己也在税里：roadmap/ 下 md 是 ENTRY_DEBT_LEDGER_SYNC input_scope，更新本档会作废该 entry 缓存（预期内，非异常）。
- CORE_BROWSER_SMOKE_PATHS（contract_data.py:30-33）现状**零消费方**——快速浏览器档接线归 fusion-frontend-gates，本档仅登记事实。

## 第二节：截图基线使用说明

- **采集**：`.venv/bin/python tests/_scripts_e2e/capture_ui_baseline.py`——复用几何探针管线（browser_support 造数 + make_server 起真实 app + CDP Page.captureScreenshot），遍历 FULL_UI_CONTRACT_PATHS 20 页 × 亮/暗双主题 ≈ 40 张 PNG。
- **产物**：`output/ui_baseline/<YYYYmmdd_HHMMSS>/<安全化路径>__<theme>.png` + `index.md`（路径↔文件名对照表）。**不入 git**（.gitignore + git hook 双重拉黑，纪律性产物目录）。
- **暗色口径**：截图前 `document.documentElement.setAttribute('data-theme','dark')` 后 await 两帧 rAF（common_theme.js 真实切换是双 rAF 延迟应用，不等会截到亮色残影）。
- **比对**：人工 A/B（改版前跑一次留时间戳目录，改版后再跑一次，并排翻图）。**没有像素 diff 门禁**——本机字体/抗锯齿/Chrome 版本差异会让自动 diff 假阳性失控。hex-migration 等「分批+逐批截图 A/B」流程消费的就是这套。
- **失败语义**：单页截图失败不中断（继续余页），最终退出码非 0 + 打印失败页清单——缺页必须被看见。

## 第三节：打印介质回归清单

规则源仅两处：`static/css/print.css`（97 行单 @media print 块，base.html 以 `media="print"` 全站挂载）+ `static/css/ui_contract.css:3484-3495`（隐藏 floating-manual-btn/toast/flash）。

**每页打印预览必查项**（Chrome Ctrl+P 或 headless `--print-to-pdf`）：

1. **侧栏不可见**：`.sidebar`（240px 深色渐变列）必须在 print.css 隐藏名单——2026-06-12 修复（此前 `header, nav` 元素级选择器盖不住 div.sidebar，打印出深色占位列）。回归断言：`tests/web_pages/test_print_css_contract.py`。
2. **A4 landscape 生效**：`@page { size: A4 landscape; margin: 15mm 10mm }`（print.css:90-93）。
3. **表格分页保护**：卡片 break-inside 避免跨页截断（print.css:41-45）；斑马纹/hover 清除（:62-65）。
4. **sticky 还原**：table-sticky 系 position:static（print.css:67-79），无悬浮阴影残留。
5. **链接黑色无下划线**：`a { color:#000 }` 且 `a[href]::after` 无 URL 注出（print.css:81-88）。

消费方提示：fusion-dispatch-print-sheet（第 31 条周派工单，一资源一页 page-break + 页眉版本时间）开工前先过本节；该 feature 会是全仓第一个 window.print 调用方（现状零调用）。

**可重跑命令**：
```bash
grep -n "sidebar\|@page" static/css/print.css
.venv/bin/python -m pytest -q tests/web_pages/test_print_css_contract.py
```
