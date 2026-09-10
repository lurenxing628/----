---
doc_type: explore
status: draft
created: 2026-09-09
scope: win7-runtime-and-current-prototype
evidence: current-worktree-and-macos-chromium109
win7_machine_verified: false
runtime_changes: false
---

# Win7 单机与样板兼容性评估

## 1. 结论

当前样板没有出现必须放弃现有布局、配色或交互的浏览器兼容阻塞。主代理已实际运行 Chromium 109.0.5414.46，15 个入口、浅深两种主题、1920×1080 与 1392×924 共 60 个初始状态正常渲染，没有页面 JavaScript 错误、外网资源请求或整页横向溢出；方案跨页工作流、维护整行导航、复杂与密集现场甘特的现有测试亦通过。

这不是 Win7 真机证明，也不是迁移后真实后端、高数据量性能或所有业务功能验收。当前测试环境为 macOS arm64，使用真正的 109 内核，不是修改新版浏览器的 User-Agent。没有运行生产 app、访问真实数据库、改动原型或切换旧页面。

建议沿用仓库现有 Chrome 109 单机运行方式，保留样板视觉与交互，只做有证据的兼容与交付处理。不能因为 Win7 较旧就改回旧样式，也不能因为页面能打开就把当前开发用 HTML 原封不动当正式包。

## 2. 官方版本边界

以下是主要官方浏览器的最后支持分支，不是所有社区移植内核的理论上限。不同浏览器的版本数字不可横向比较，115 不等于比 Chromium 109 多六代能力。

| 运行时 | Win7 官方最后支持分支 | 证据 |
| --- | --- | --- |
| Google Chrome | 109；该主版本发布于 2023-01-10 | S1 |
| Microsoft Edge | 109 | S2、S3 |
| Microsoft WebView2 Runtime | 109；换成 WebView2 外壳不能绕过同样的内核边界 | S3 |
| Mozilla Firefox | 115 / 115 ESR 分支；116 系统要求已为 Windows 10 或更新版本 | S4、S5 |

“曾支持、现在仍能启动”和“仍获得维护更新”是不同结论。Microsoft 明确说明 Win7 上 Edge/WebView2 109 不再获得新功能、后续安全更新与缺陷修复。Firefox 115 ESR 的当前补丁号、未来延长日期不是本评估的已核实内容，不作承诺。该软件继续只服务本机、离线交付，不以旧内核浏览外部网站作为产品工作流。

官方资料于本轮实际读取。常规 web 搜索接口没有返回可用正文，改用网页读取工具获取上述官方站点内容；未使用社区博客替代官方支持政策。

- S1 Google, *Chrome browser system requirements*: `https://support.google.com/chrome/a/answer/7100626?hl=en`
- S2 Microsoft Learn, *Microsoft Edge Supported Operating Systems*, Recent changes: `https://learn.microsoft.com/en-us/deployedge/microsoft-edge-supported-operating-systems`
- S3 Microsoft Edge Team, *Microsoft Edge and WebView2 ending support for Windows 7 and Windows 8/8.1*, 2022-12-09，2023-01-17 更新: `https://blogs.windows.com/msedgedev/2022/12/09/microsoft-edge-and-webview2-ending-support-for-windows-7-and-windows-8-8-1/`
- S4 Mozilla, *Firefox 115.0 Release Notes*, 2023-07-04: `https://www.mozilla.org/en-US/firefox/115.0/releasenotes/`
- S5 Mozilla, *Firefox 116.0 System Requirements*: `https://www.mozilla.org/en-US/firefox/116.0/system-requirements/`
- S6 Microsoft Playwright v1.29.2 browser manifest，Chromium revision 1041 对应 109.0.5414.46: `https://raw.githubusercontent.com/microsoft/playwright/v1.29.2/packages/playwright-core/browsers.json`
- S7 Chrome Developers, *New in Chrome 111*, 2023-03-07，新增颜色功能: `https://developer.chrome.com/blog/new-in-chrome-111/`

## 3. 仓库和当前样板证据

本段相对路径均以 `/Users/lurenxing/GitHub/----/` 为根。

- `assets/启动_排产系统_Chrome.bat:62` 已设置机器级/用户级 `APS\Chrome109` 路径，并使用隔离的 `Chrome109Profile`；`:113` 起解析显式环境配置和注册表/默认路径。不是这次评估新引入浏览器运行时。
- `前端设计/ui_kits/workbench/index.html:305` 加载本地 React 18.3.1、ReactDOM 18.3.1 和 Babel 7.29.0；`:346` 起由浏览器处理 `text/babel` JSX。React 版本本身不是 Win7 的操作系统上限，真正需要验证的是浏览器及页面实际使用的能力。
- 两个入口及其脚本、样式和 CSS import 共清点 99 个文件；本次冒烟和现场甘特测试阻断 HTTP(S) 后仍可打开文件页面。并未把未加载的旧设计备选 HTML 当作当前入口能力。
- `前端设计/ui_kits/workbench/ProcessNative.jsx:2` 明确当前基础资料是实际 DOM 挂载，不是 iframe 假接入。
- `前端设计/tokens/typography.css:15` 有本地 TTF 的 `@font-face`；`:25` 字体栈含 Segoe UI / Microsoft YaHei。`前端设计/styles.css` 的“No @font-face”旧注释不符合当前实际内容，评估以字体文件源码为准。Windows 与 macOS 的字体优先级及绘制仍需真机核对。
- 现有生产 Python 环境本轮核实为 3.8.10、Flask 2.3.3；没有安装或升级后端依赖。兼容这个页面不要求目标 Win7 机安装 Node.js，不要求升级 Python，也不意味着需要改成云服务。

## 4. 内核能力与关注项

真实 109 `CSS.supports`/运行时探测结果：

| 功能 | 本轮结果 | 对本样板的含义 |
| --- | --- | --- |
| CSS Grid、gap、sticky、aspect-ratio | 支持 | 当前布局、工具区、固定列不需要改成旧式页面 |
| ResizeObserver、structuredClone、Array.at、Array.findLast | 存在 | 当前大小计算和常用 JS 能力无入口运行阻塞 |
| 原生 dialog.showModal、crypto.randomUUID | 存在 | 仍需按实际使用场景验收；本轮方案采用弹窗已走通 |
| `color-mix()` | 不支持 | 颜色应预先计算为同样的 RGB/RGBA 或主题 token，不改变设计色值 |
| `text-wrap: pretty` | 不支持 | 必须用宽度、行高和常规换行保证文字排版，不能依赖该增强功能 |
| Array.toSorted | 不存在 | 本次指定高版本 API 静态扫描未发现第一方加载代码调用它，不因此虚构功能故障 |

不兼容声明的实际影响不能仅凭关键词判断：

- `basedata.css:128` 的 `.bd-selbar` 使用 `color-mix()`；当前批次页又被后加载的 `batch-workbench.css:131` 明确覆盖为透明背景，因此它不是已确认的批量区底色故障。
- `gantt-board.css:84`、`:123`、`:124` 残留通用 `.gb-days/.gb-track/.gb-today` 的 `color-mix()`；当前方案甘特使用 `.tr-*`，现场甘特使用 `.fg-*`，60 个初始状态未匹配上述三个旧节点。不能将未使用旧样式列为当前甘特网格失效。
- `index.html:148`、`:152`、`:168` 有 3 处 `text-wrap: pretty` 旧分析样式，需在最终资源裁剪时确认可达性。该声明被忽略不等于文字全部不显示。

正式接入时应移除未用声明，或在保持相同视觉的前提下替换真正需要的声明，并建立 Chrome 109 检查。上述替换尚未实施。

## 5. 本轮实际验证

测试运行时：从 S6 对应 Playwright 官方 CDN 下载 mac-arm64 Chromium revision 1041。下载和启动目录只在 `/tmp/aps-chromium109-assessment/`，未替换用户浏览器、生产运行时或用户浏览器 profile。

成功下载来源：`https://playwright-akamai.azureedge.net/builds/chromium/1041/chromium-mac-arm64.zip`

ZIP SHA-256：`309715c55f6d13ffbeef969cb3969ec792f2146c2dab95147439c633beb5d006`

| 测试 | 结果 | 范围/限制 |
| --- | --- | --- |
| `runtime-probe.cjs` | 60/60 状态通过；0 pageerror、0 外网请求 | 14 个 index view + trial，1920×1080/1392×924，浅/深；页面渲染与宽度检查，不是全部控件验收 |
| 原型 `tests/workbench-workflow-browser.cjs`，强制 109 启动 | 247 检查通过，56 截图 | 候选选择、甘特/交付跨页、输入确认人/说明并采用样例、刷新、trial 往返、资源切换、搜索、排产检查批次选择；只在隔离 localStorage 上操作 |
| 原型 `tests/system-maintenance-navigation.cjs`，强制 109 | 1510 检查通过 | 1920/1392/390，双主题、双数据源；整行图标/文字/空白/箭头点击、Tab/Enter/Space；导航不修改数据或触发维护动作 |
| 原型 `tests/field-gantt-surfaces-browser.cjs`，强制 109 | 1186 检查、72 状态、56 截图通过 | 当前/复杂/密集数据，设备/人员/批次，展开/折叠，双主题双桌面尺寸；包含像素采样与离线资源检查 |

主代理实际打开检查了 1920 下基础资料、现场甘特、报表浅色图，以及系统管理、试调深色图；未宣称人工看完所有生成截图。现有浏览器测试通过 Playwright 真实点击/键盘/输入操作，但不冒充最终迁移后“所有控件逐个手输点击”的完整人工验收。

原始证据：

- `/tmp/aps-chromium109-assessment/runtime-probe.cjs`
- `/tmp/aps-chromium109-assessment/force-browser.cjs`
- `/tmp/aps-chromium109-assessment/runtime-probe.json`
- `/tmp/aps-chromium109-assessment/maintenance/measurements.json`
- `/tmp/aps-chromium109-assessment/field-surfaces/measurements.json`
- `/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-workflow-qa-1iNiul/`

临时目录并非正式归档或备份承诺。进入实施前应连同源码基线和哈希整理为版本化验收证据。

## 6. 后续方案要求

1. 保留当前 Flask 后端、Python 3.8、单机数据库、本机 Chrome 109 启动方式和离线资源边界。不要为了新版 WebView2 / Electron 或浏览器而抬高 Win7 基线。
2. 外观不降级。对齐当前布局、主题色、表格密度、工具条、甘特条几何和弹窗交互；兼容替换用同色值、同尺寸、同动作验收，不恢复旧页面样式。
3. 当前开发 HTML 不能直接成为正式 payload。Babel 文件为 3,137,752 bytes，ReactDOM 开发文件为 1,080,227 bytes，且有浏览器运行时 JSX 编译。若保留 React 组件，应在开发/打包端提前编译到 109 目标、使用生产资源并随包交付；目标机不安装 Node。是否新增构建流程须与原有 Flask/Jinja 架构约束一并形成明确决定，本次浏览器检查没有批准 SPA 迁移。
4. 后端接入、真实数据量和浏览器兼容是三道不同关卡。大表/甘特必须按目标机 CPU、内存和数据量独立评估分页、按范围查询及必要的虚拟化，不能用这批小样例的渲染时间作性能承诺。
5. 在 Win7 SP1 x64 上验收正式安装包启动、离线资源、字体和输入法、100%/125%/150% DPI、下载/导入、打印、显卡/软件渲染、重启恢复及高复杂度数据。Mac 109 测试不能替代这些结果。
6. 只有实际遇到无法在 109 解决的组件问题，才将对应实现改用现有 Flask/Jinja + HTML/CSS/普通 JS 等效复刻。Jinja 只改变 HTML 生成方式，不会自动让不支持的 CSS/API 变兼容；不能把换模板技术当作浏览器兼容修复。

本评估支持“有条件保留样板并做兼容交付”，不支持“现在即可下线旧页面”。旧页备份、真实接口/业务差异、全功能手动验收、压测和最终切换继续由总迁移方案单独管理。
