---
doc_type: architecture-proposal
status: approved
created: 2026-11-09
updated: 2026-11-09
roadmap: aps-architecture-consolidation
summary: 采用固定版本esbuild统一生产与vm.Context测试构建，剥离前端对后端受控DTO的重复重验并归位5类真实边界，彻底拔除prototype生产依赖与DOM事后修补，统一命令结算会话与7条回执查询消费。
---

# 工作台前端架构设计

本专题从属于[总设计](aps-architecture-consolidation-roadmap.md)，为已由主代理与审查通道对齐定稿的目标方案。
一次完成全量迁移、整体验收和发布，不建设旧新 API 兼容层、全局导出桥或两套生产构建。
下文的任务顺序是同一次实施内部的依赖顺序；任何部分未迁完，均不作为独立上线版本。

## 1. 推荐目标与保留约束

- 保留 React 18.3.1、现有工作台交互和领域功能，使用原生 ES module 表达源码依赖，由宿主固定版本的 `esbuild` 构建为本地生产产物。
- 生产业务模块不再读写 `window.XxxAPI/Contract/Workspace`；构建不再依赖手工 JavaScript 加载顺序。
- 页面仍由本机 Python 服务提供，Chrome109 执行，所有字体、图标、脚本和样式随包交付，运行时不访问 CDN。
- Node、`esbuild` 及构建依赖只存在于维护/构建宿主，目标 Win7 机器仍不需要 Python、Node 或包管理器。
- 剥离前端对本机后端受控 DTO 的事后全字段重验、分页公式重验与主线程 2 万行 diff 重算，同时严守引用展开、身份绑定、用户输入归一化与本机存储反序列化校验 5 类真实边界。
- 彻底拔除 `prototype/` 的生产构建依赖与 AST 声明切片，将实际使用的生产组件收口为 `frontend/workbench/` 一等源码，消除渲染后 `useLayoutEffect` 扫 DOM 补表格属性的补偿。
- 命令的确定/未知结论、跨页互斥、幂等键与本机结算保留（本机 `pending` 存储编码保持 0 变更）；同一 `storage + key` 由底层结算会话统一管理，不造带一串布尔开关的万能 `useCommand`。

## 2. 当前事实与主要维护负担

| 现场事实 | 具体位置 | 设计处理 |
| --- | --- | --- |
| `app` 有 245 个 JS/JSX 文件，都使用 `window`；比较页在一行取得六个全局依赖 | [RunDecisionComparison.jsx:3](../../../frontend/workbench/app/RunDecisionComparison.jsx#L3) | 所有生产调用者统一改为显式 import |
| API、图表和视图的次序由列表指定 | [build-order.json:192](../../../scripts/workbench/build-order.json#L192) | JS 次序交给模块依赖图，删除该顺序列表 |
| 构建器检查名单齐全，再逐文件读取、Babel 单文件编译、拼接 | [build.py:63](../../../scripts/workbench/build.py#L63)、[compile.cjs:33](../../../scripts/workbench/compile.cjs#L33) | 改用固定版本 `esbuild` 静态链接打包，缺导出/缺模块在构建时直接失败 |
| 25 个 `*Contract.js / *API.js` 对后端受控 DTO 做 `Reflect.ownKeys` 键数白名单、分页算术与 2 万行 diff 重验 | [PlanContract.js:10](../../../frontend/workbench/app/PlanContract.js#L10)、[PlanContract.js:216-225](../../../frontend/workbench/app/PlanContract.js#L216-L225) | 剥离对内部受控 DTO 的重复重验，将紧凑 `after` 引用展开归位到 `PlanGanttModel` |
| 生产构建通过 `ds-projection.cjs` 与 `selectDeclarations` 从 `prototype/` 切 AST 拼入 foundation | [ds-projection.cjs](../../../scripts/workbench/ds-projection.cjs)、[Table.jsx:239](../../../frontend/workbench/prototype/components/data/Table.jsx#L239) | 实际生产定义迁入 `frontend/workbench/` 一等源码，彻底断开 `prototype/` 生产编译依赖 |
| 传输、未确认意图存储和 UI 会话混在两个共享脚本中 | [transport.js:235](../../../frontend/workbench/app/transport.js#L235)、[resource-session.js:40](../../../frontend/workbench/app/resource-session.js#L40) | 按网络、底层结算会话、查询 Hook、领域协议四个实际职责分层 |
| 21 项 Node 契约测试与甘特 VM 宿主在 `vm.Context` 沙箱内从 `window` 取全局对象 | [test_ui_refinement_node_contracts.py:13](../../../tests/workbench/test_ui_refinement_node_contracts.py#L13)、[gantt_current_runtime.cjs:7](../../../tests/_support/gantt_current_runtime.cjs#L7) | 共用固定版本 `esbuild` 打包测试入口并在独立 `vm.createContext` 沙箱执行，支持模块级替身注入 |

## 3. 目标目录与依赖方向

```text
frontend/workbench/app/
  shell/              main.jsx、导航、启动 JSON、页面守卫、页面记忆
  shared/runtime/     react.js、theme.js、浏览器平台能力（inspectEnvironment 等）
  shared/network/     transport.js、envelope.js、fault.js、downloads.js
  shared/session/     query.js、command-session.js、pending-store.js
  shared/ui/          icons.jsx、Table.jsx、buttons.jsx、MetricStrip.jsx 等实际复用生产控件
  shared/contracts/   用户输入归一化、浏览器存储边界校验、点事件/时间区间与身份绑定原语
  domains/            resource、process、batch、run、plan、trial、field、report、calibration、dashboard、system
  styles/             生产样式入口、tokens、控件、领域样式
```

依赖方向为 `shell → domains → shared`；领域视图导入自己领域的 API/展示模型/输入合同；API 只向下依赖网络和共享原语，不反向导入 React 视图。
领域之间通过明确的导航目标、回调或真正共享的只读表示连接，不导入其他 Workspace 的内部状态。
共用甘特的几何计算、时间表示、选择控件下沉至 `shared`；候选、正式计划、实际记录各自的业务来源和权限仍由对应领域负责。
不建立汇总导出所有领域的总 `index.js`，不为每个原文件增加空转发层；实际调用方直接 import 所需命名导出。
模块初始化只创建纯常量/明确单例；DOM 监听、挂载与订阅从 `mountWorkbench()` 或 effect 启动，并返回释放函数。

## 4. 显式模块接口、React 运行时与 Node `vm.Context` 测试宿主合同

### 4.1 生产 React 运行时与首屏主题

所有 JSX 明确 `import React from '../../shared/runtime/react.js'`；`createRoot / createPortal` 从同一适配模块取得，避免第二份 React。第三方 vendor globals 仅允许在这一处读取：

```js
// shared/runtime/react.js；vendor scripts 先由静态资源清单加载。
const React = window.React;
const ReactDOM = window.ReactDOM;
export default React;
export const createRoot = ReactDOM.createRoot;
export const createPortal = ReactDOM.createPortal;
```

保留现有本地 React/ReactDOM vendor、许可证和版本固定检查（[`build.py:170`](../../../scripts/workbench/build.py#L170)）。入口在挂载前完成 vendor 可用性判断，失败时只显示已有“资源未完整加载”的启动错误，不联网下载替代品。适配文件不承担业务注册，不将领域对象重新挂到 `window`。

主题的首屏应用与设置接口分开：早执行的 `app/theme.js` 入口只根据当前偏好设置 `documentElement.dataset.theme`，不导出业务全局对象；主包导入 `shared/runtime/theme.js` 以读取、设置、订阅。保留现有 `aps_theme`、cookie 与未保存提示语义（[`theme.js:5`](../../../frontend/workbench/app/theme.js#L5)、[`theme.js:22`](../../../frontend/workbench/app/theme.js#L22)）；`window.APSWorkbenchTheme` 随所有调用者迁移一次删除。

### 4.2 Node 契约测试与 `vm.Context` 沙箱执行合同

Node 原生无法直接 `import` `.jsx` 源码，且现有契约测试依赖沙箱级浏览器全局隔离与 Hook/替身注入。为避免在生产包中留测试后门或出现“测试跑通、生产构建报错”的脱节，生产与测试执行合同统一如下：

1. **生产与测试共用固定版本 `esbuild`**：生产入口（`app/shell/main.jsx`、`app/theme.js`）与 21 项 Node 契约测试（[`tests/workbench/test_ui_refinement_node_contracts.py:13`](../../../tests/workbench/test_ui_refinement_node_contracts.py#L13)）及甘特 VM 宿主（[`tests/_support/gantt_current_runtime.cjs:7`](../../../tests/_support/gantt_current_runtime.cjs#L7)）统一使用宿主固定版本的 `esbuild`。
2. **测试入口经 `esbuild` 打包后在独立 `vm.createContext` 沙箱内执行**：每个测试入口显式 `import` 真实生产 ESM/JSX 源码，由 `esbuild` 内存打包后送入独立的 `vm.createContext` 沙箱运行，不靠 Node 原生直接导入 `.jsx`，也不从生产交付包的 `window` 全局读取业务符号。
3. **沙箱级模块实例与浏览器环境隔离**：每个测试沙箱拥有完全独立的模块实例与顶层状态，完整保留 `window / document / localStorage / sessionStorage / fetch / navigator.locks / matchMedia` 等沙箱环境隔离。
4. **构建期模块别名/插件注入测试替身（生产包 0 负担）**：
   - 测试构建支持通过 `esbuild` resolve 插件注入 `shared/runtime/react.js` 测试桩，直接承接 [`tests/workbench/storage_write_contract.cjs:69`](../../../tests/workbench/storage_write_contract.cjs#L69) 与 [`tests/_support/gantt_current_runtime.cjs:27`](../../../tests/_support/gantt_current_runtime.cjs#L27) 动态替换或拦截 `React` Hook 的测试行为，生产 `shared/runtime/react.js` 无需增加可变代理；
   - 同样通过测试构建注入 API、Session、Workspace 测试替身（如承接 [`tests/workbench/decision_comparison_contract.cjs:519`](../../../tests/workbench/decision_comparison_contract.cjs#L519) 的替身组装），彻底告别靠覆盖 `window.Xxx` 注入 mock 的旧模式。

## 5. 一套 `esbuild` 构建入口与离线静态资产硬契约

**构建工具裁决**：**采用宿主固定版本的 `esbuild`**，明确放弃“用仓内 Babel 自写静态模块链接器”方案——因为 Babel 单文件转译无法静态验证跨模块命名导出是否存在，无法满足“缺导出/写错导出名在构建期直接失败”的硬要求。

- 保持 `python scripts/workbench/build.py --node ... --output-dir ...` 作为宿主构建入口，内部调用固定版本的 `esbuild`（配置 `bundle: true`、`platform: 'browser'`、`format: 'iife'`、`target: 'chrome109'`、关闭代码分割 splitting）。
- 应用入口为 `app/shell/main.jsx`，首屏主题入口为 `app/theme.js`；其余生产 JS 均由这两个入口的静态 `import` 图解析获得。禁止远端 URL import、Node 内置模块混入浏览器产物或动态包搜索。
- 一次性删除 [`scripts/workbench/build-order.json`](../../../scripts/workbench/build-order.json) 的 JS `live / foundation / bootstrap` 顺序清单。
- 样式由唯一 `styles/index.css` 按确定的级联顺序导入 tokens、基础控件、布局和领域样式；复用现有本地 CSS 资源校验与打包流程（[`build.py:210`](../../../scripts/workbench/build.py#L210)）。
- **静态产物硬契约**：严格保持 `asset-manifest.json` 的 `schema_version=1`、`target=chrome109`，以及本地字体、tokens、inline CSS、logo、React/ReactDOM vendor 与 Lucide `LICENSE` 的离线自包含闭包（[`web/routes/workbench/assets.py:14`](../../../web/routes/workbench/assets.py#L14)、[`tests/app_runtime/test_frontend_offline_static_assets.py:145`](../../../tests/app_runtime/test_frontend_offline_static_assets.py#L145)）。`node_modules` 与 `esbuild` 二进制仅留在构建宿主，严禁进入 Win7 离线交付包。

## 6. 剥离受控 DTO 事后重复重验，守住 5 类真实边界

### 6.1 砍掉对本机后端受控 DTO 的重复校验（消除母题 F / G / E / D）

本机 Python 后端产出的 HTTP 响应 DTO 属于同一产品内部的受控结构，其字段形状、分页计数、SQL 排序筛选、基线差异与图拓扑均已由后端领域投影和契约测试保证。前端不再扮演“第二个后端校验器”，一次性砍掉 25 个 `*Contract.js / *API.js` 及会话层中的以下冗余重验：

1. **砍掉 `Reflect.ownKeys` 严格键数白名单与逐字段类型重检**：如 [`frontend/workbench/app/PlanContract.js:10`](../../../frontend/workbench/app/PlanContract.js#L10)、[`frontend/workbench/app/RunCandidateAPI.js:9`](../../../frontend/workbench/app/RunCandidateAPI.js#L9) 等对内部 DTO 逐层遍历键集合的防御代码。
2. **砍掉 12 处分页算术公式重验**：前端不再重算 `total_pages / offset / page_size` 等分页算术恒等式。
3. **砍掉展示文案与业务加总重验**：如 [`frontend/workbench/app/RunAdoptionAPI.js:61-67`](../../../frontend/workbench/app/RunAdoptionAPI.js#L61-L67)、[`frontend/workbench/app/PreflightContract.js:105-147`](../../../frontend/workbench/app/PreflightContract.js#L105-L147) 对后端已算好的汇总计数与状态文案做二次核验。
4. **砍掉主线程 2 万行基线 diff 重算**：删除 [`frontend/workbench/app/PlanContract.js:216-225`](../../../frontend/workbench/app/PlanContract.js#L216-L225) 在浏览器主线程对高达 2 万行计划基线重跑 diff 校验的热路径负担。
5. **砍掉前端全图闭包重验与 SQL 排序/筛选重验**：删除 [`frontend/workbench/app/GanttGraph.js:8-49`](../../../frontend/workbench/app/GanttGraph.js#L8-L49) 的全图闭包事后自检，以及 [`frontend/workbench/app/RunHistoryAPI.js:70-96`](../../../frontend/workbench/app/RunHistoryAPI.js#L70-L96) 用 JS 重新验证后端 SQL 排序顺序与筛选命中条件的重复扫描。
6. **砍掉 [`frontend/workbench/app/resource-session.js:148-175`](../../../frontend/workbench/app/resource-session.js#L148-L175) 仅服务坏 DTO 的深校验**：删除对 `calendarSummary / readinessSummary` 的防御性结构深检；合法的后端 `unavailable` 状态与周合计 `null` 直接由组件现有的“未知/暂无数据”分支自然渲染（由 [`tests/workbench/resource_rail_presentation_contract.cjs:110`](../../../tests/workbench/resource_rail_presentation_contract.cjs#L110) 锁定）。
7. **同步清理 `tests/workbench/*.cjs` 中的母题 D 篡改断言**：删除专门通过 `delete p.data.tasks[0][key]`、`.reverse()` 或往返回对象塞额外未知键来证明前端 DTO 重验“删不得”的人造篡改测试；完整保留快照错绑、身份绑定、分页装配、引用展开、零工时/点事件、合法 `unavailable` 渲染与真实交互断言。

### 6.2 必须保留并归位的 5 类真实职责（严禁误删）

在剥离冗余 DTO 重验的同时，以下 5 类承担真实数据装配、业务分流与外部/存储边界保护的职责必须 100% 保留并归位：

| 真实职责类别 | 具体定位与目标归位动作 | 保留原因（拷问 3 / 拷问 4） |
| --- | --- | --- |
| **1. 紧凑任务引用展开归位到 `PlanGanttModel`** | 后端 [`core/services/workbench/plan/baseline.py:177`](../../../core/services/workbench/plan/baseline.py#L177) 的范围内 `after` 仅传输紧凑 `{task_ref}`。原 [`frontend/workbench/app/PlanContract.js:209-215`](../../../frontend/workbench/app/PlanContract.js#L209-L215) 用 `verifiedTasks` `WeakMap` 在校验时原地改写 `row.after = matched` 供 [`frontend/workbench/app/PlanDetailsUI.jsx:67`](../../../frontend/workbench/app/PlanDetailsUI.jsx#L67) 读取。现改为在 [`frontend/workbench/app/PlanGanttModel.js:66`](../../../frontend/workbench/app/PlanGanttModel.js#L66) 中直接复用其已构建的 `taskIndex` 完成 `after` 引用展开，彻底删掉 `PlanContract` 的 `WeakMap`、重复索引与原地篡改。 | 真实的数据装配职责，删掉会导致计划详情前置工序信息丢失（母题 O） |
| **2. 真实业务分流与状态/编辑模型转换** | ① 保留 Dashboard 分析失败时仅局部关闭分析区域；② 保留 [`frontend/workbench/app/SystemMaintenanceAPI.js:67`](../../../frontend/workbench/app/SystemMaintenanceAPI.js#L67) 区分外置维护账本（journal）与普通信封并归一化 `terminal`；③ 保留 [`frontend/workbench/app/CalendarContract.js:78`](../../../frontend/workbench/app/CalendarContract.js#L78) 的 DTO→编辑草稿转换、效率百分比换算与差量提交构造；④ 保留 [`frontend/workbench/app/PointContract.js:5`](../../../frontend/workbench/app/PointContract.js#L5) 的零时长点事件与半开时间范围语义。 | 真实的视图模型转换、多态协议分流与时间几何语义 |
| **3. `bindResponse` 按接口真实身份范围绑定** | 候选 baseline 绑定独立快照；正式计划分块加载绑定首屏快照；报工定位绑定 `task_ref + operation_ref + page + scope`；内嵌 `resource_result` 保留内嵌信封、身份核对与局部失败处理。 | 防止并发请求、分块翻页或跨范围切换时张冠李戴（母题 N / O） |
| **4. 外部用户输入归一化（`input`）** | 用户表单输入、导入参数、筛选与分页查询入参的归一化与前置校验 100% 保留。 | 浏览器端首次接收外部用户输入的真实信任边界（拷问 3） |
| **5. 浏览器存储边界校验（`validIntent`）** | `localStorage / sessionStorage` 跨刷新反序列化 `pending` 意图时的 `validIntent` 校验 100% 保留。特别注意：像 [`frontend/workbench/app/RunAdoptionAPI.js:81`](../../../frontend/workbench/app/RunAdoptionAPI.js#L81) 的 `summary()` 同时被网络 preview 和本机存储 `validIntent` 调用，删网络端重复校验时严禁顺手删掉本机存储反序列化校验。 | 跨会话/跨页面持久化存储属于可能损坏或残留的外部边界（拷问 3） |

## 7. 一个实际字段变更应触及哪些位置

现有阶段耗时由 [`unified_process.py:36`](../../../core/services/workbench/facts/unified_process.py#L36) 汇总，[`:43`](../../../core/services/workbench/facts/unified_process.py#L43) 形成 `elapsed_ms`；[`decision_process.py:61`](../../../core/services/workbench/run/decision_process.py#L61) 对统一投影分页并透传，前端在 [`RunDecisionProcess.jsx:65`](../../../frontend/workbench/app/RunDecisionProcess.jsx#L65) 展示。

剥离前端对后端受控 DTO 的全字段白名单重验后，给阶段补一个由已存事实汇总的纯展示字段，**只需修改后端投影、前端展示模型/组件（如需要格式转换）和相关契约样本**——甚至无需再去前端手写一份字段键名白名单（原 [`RunDecisionAPI.js:388`](../../../frontend/workbench/app/RunDecisionAPI.js#L388)）。无需改路由转发、公共信封、请求会话、导航、浏览器存储或构建顺序。

## 8. 查询状态、页面状态与底层命令结算会话分层

### 8.1 查询状态与页面状态分离

`useQuery(load, deps, enabled)` 保留当前身份隔离和 `AbortController` 机制（[`resource-session.js:40`](../../../frontend/workbench/app/resource-session.js#L40)）。
目标接口为 `{status: 'idle'|'loading'|'ready'|'error', result, error, reload, reloadAndWait}`；查询身份包括实体、范围、筛选和快照，不能只按 URL 路径缓存。
新身份加载时 `result=null`，旧请求迟到不覆盖新身份；取消读取只影响 read，不改命令是否提交的判断。
筛选、排序、页长、查看目标和展开意图属于页面状态；统计、安排、交期和资源占用属于当前 DTO。
导航记忆归 shell 单一入口；保留 [`WorkbenchNavigation.js:202`](../../../frontend/workbench/app/WorkbenchNavigation.js#L202) 的滚动节流与 flush，不向各 Workspace 复制一套。

### 8.2 命令结算会话分层（拒绝带一串布尔开关的万能 `useCommand`）

不同领域的写操作具有真实的业务协议差异（例如：是否有预览确认流、排产任务的后台轮询、拒绝后是保留草稿供修改还是直接清除、重试是否沿用原 `request_key`）。若强行塞进一个带一串布尔配置开关的万能 `useCommand` Hook，只会制造新的伪可选分支与耦合（母题 A / J）。目标采用清晰的**双层架构**：

1. **底层命令结算会话（`shared/session/command-session.js` + `pending-store.js`）**：
   - 同一 `storage + key` 的**服务器权威结论、未刷盘结算状态（含欠着的 `beforeWrite` 附属写入）以及跨标签页 `storage` 事件监听**，统一由一个底层会话单例对象拥有；
   - React Hook 只负责订阅该底层会话对象的状态快照并在组件卸载时取消订阅，因此组件因路由切换或父级状态变化重挂载（remount）时，绝不会丢失已拿到的服务端终态或复活无效轮询。
2. **领域命令协议层（各领域 Session / Action）**：
   - 各页面的草稿、预览、二次确认，以及各业务协议特有的轮询、恢复、拒绝后保留还是清除本机记录、是否沿用 `request_key`，仍由各自领域协议模块直接表达。

## 9. 存储互斥边界与 7 条回执协议前后端同步消费

### 9.1 守住本机存储与跨页互斥边界

- **存储介质与编码不变**：资源命令继续使用 `sessionStorage`（[`frontend/workbench/app/resource-api.js:96`](../../../frontend/workbench/app/resource-api.js#L96)），排产、采用、校准、试调与系统维护等继续使用 `localStorage`；浏览器本机 `pending` 记录的 JSON 编码保持 0 变更。
- **保留“先持久化 intent，再发送网络请求”**：写不下新意图则直接阻断发送（[`frontend/workbench/app/resource-session.js:102`](../../../frontend/workbench/app/resource-session.js#L102)）；同一用户意图内 `request_key` 固定不变。
- **完整保留由 [`tests/workbench/storage_write_contract.cjs:81`](../../../tests/workbench/storage_write_contract.cjs#L81) 锁定的全部结算与容错语义**：
  - 完整保留 [`frontend/workbench/app/RunJobAPI.js:173`](../../../frontend/workbench/app/RunJobAPI.js#L173) 与 [`frontend/workbench/app/transport.js:264-344`](../../../frontend/workbench/app/transport.js#L264-L344) 的结算顺序：**先执行 `beforeWrite`（如写入 `RECENT` 最近结果），再清除 `PENDING` 记录**；
  - 纯只读入口 `read()` 只报告当前记录与内存未刷盘权威值，**严禁在 `read()` 中暗藏锁外写盘或补刷（`setItem / removeItem`）**；
  - 跨标签页继续使用同名 Web Locks 互斥，在锁内由 `flush()` 重放未完成的结算写入（含暂存的 `beforeWrite`）；
  - 当服务端已确认终态（成功回执或明确业务拒绝）但本机 `localStorage / sessionStorage` 写入或清除抛异常时，底层会话在内存中锁定终态并标记 `persistence: 'unflushed' | 'unavailable'`，后续 `finish / sync / lookup / refresh` 均遵循该权威终态，**绝不因本机存储异常把已知终态降级回 `pending`**。

### 9.2 同步全部回执协议消费者

与[数据专题 §6.2](data-and-runtime-design.md#62-全仓-7-条命令回执查询lookup链路统一收口)一次同步修改前端全部回执消费者：
- **覆盖范围**：全部领域 API、[`resource-contract.js`](../../../frontend/workbench/app/resource-contract.js) / [`resource-session.js`](../../../frontend/workbench/app/resource-session.js)、`Dashboard` / `Outsourcing` Contract、`TrialSession`、候选/试调/校准采用 `State / Action`、`RunJobPanel`、`SystemRestoreStatus`。
- **统一消费契约**：普通、采用、校准、试调命令查询统一消费 `{state: "recorded" | "not_observed", receipt, may_be_in_flight, resolution}`（采用链路含 `data_context_ref`）；排产任务受理查询消费 `{found, run, resolution, data_context_ref}`；系统维护查询消费统一回执或外部维护日志结果。
- **清理特判与错址**：
  - 删除 [`frontend/workbench/app/transport.js:153`](../../../frontend/workbench/app/transport.js#L153) 针对 HTTP 404 `receipt_not_found` 的特判兜底；
  - 同步修正 [`frontend/workbench/app/CalibrationAdoptionAPI.js:69`](../../../frontend/workbench/app/CalibrationAdoptionAPI.js#L69) 提交时 `expect` 回执地址与 [`web/routes/workbench/calibration_adoption.py:42`](../../../web/routes/workbench/calibration_adoption.py#L42) 的 `g.workbench_result_target`，使前端 `expect`、后端失败信封 `result_target` 与实际查询地址完全一致。

## 10. 组件生命周期与真实交互

`details`、工具栏、分页按钮和必要焦点锚点在查询加载期间保持同一组件身份，条件只控制内容体（[`RunDecisionProcess.jsx:168`](../../../frontend/workbench/app/RunDecisionProcess.jsx#L168)、[`:71`](../../../frontend/workbench/app/RunDecisionProcess.jsx#L71)）。
`key` 只表达真实业务身份变化，不使用 `loading / page / result` 对整个 Workspace 或需要保留开合的壳重新挂载。
同一记录的往返翻页保留用户展开/折叠；切换到另一业务对象时按产品语义重置，不把所有页面开合写入全局缓存。
焦点由触发操作的组件负责；首末页按钮禁用后移到仍可操作的同组按钮，取消/重试后可从当前控件继续。
打印媒体查询和下载是平台边界；Node `vm.Context` 沙箱模拟这些真实能力，不向产品代码注入无用兼容回退。

## 11. 彻底拔除 `prototype/` 生产依赖与 DOM 事后修补

当前生产构建通过 [`scripts/workbench/ds-projection.cjs`](../../../scripts/workbench/ds-projection.cjs) 和 [`scripts/workbench/compile.cjs`](../../../scripts/workbench/compile.cjs) 的 `selectDeclarations` 对 `frontend/workbench/prototype/` 做 AST 切片来拼凑生产基础组件。本次将实际使用的生产定义全部收口为 `frontend/workbench/app/` 下的一等源码，彻底断开生产构建对 `prototype/` 的依赖：

1. **图标收口**：将 5 处散落的图标定义统一合并入 `frontend/workbench/app/shared/ui/icons.jsx`。
2. **通用控件与工具函数迁入一等源码**：
   - 将实际使用的 `ControlButton / TransferButton`、`MetricStrip / Metric` 迁入 `shared/ui/`；
   - 将 [`frontend/workbench/app/TrialExport.js:26`](../../../frontend/workbench/app/TrialExport.js#L26) 依赖的 `csvCell`（完整保留双引号转义与公式前缀防注入转义）迁入共享导出工具模块；
   - 将 [`frontend/workbench/app/SystemLive.jsx:19`](../../../frontend/workbench/app/SystemLive.jsx#L19) 依赖的 `inspectEnvironment` 迁入 `shared/runtime/`。
3. **正式 `Table` 组件迁入 `shared/ui/Table.jsx` 并消除 DOM 事后修补**：
   - 从 [`frontend/workbench/prototype/components/data/Table.jsx:239`](../../../frontend/workbench/prototype/components/data/Table.jsx#L239) 迁入 `shared/ui/Table.jsx` 时，删除生产未使用的客户端排序与筛选弹窗代码，但**完整保留列宽拖拽手柄、百分比列宽、右对齐、自定义单元格渲染与横向滚动**；
   - 让 `Table` 组件在 JSX 中直接原生渲染 `<caption>`、`<th scope="col">` 和固定列 class，**彻底删除 [`frontend/workbench/app/ReportEvidence.jsx:45-60`](../../../frontend/workbench/app/ReportEvidence.jsx#L45-L60)（`TableFrame`）在 `useLayoutEffect` 里遍历 DOM 补写属性的事后修补逻辑（母题 J）**。
4. **清理 AST 切片工具与死组件**：删除 [`scripts/workbench/ds-projection.cjs`](../../../scripts/workbench/ds-projection.cjs)、[`scripts/workbench/compile.cjs`](../../../scripts/workbench/compile.cjs) 中的 `selectDeclarations` AST 切片逻辑，以及 `prototype/` 中其余 7 个 0 生产调用的死组件支线。

## 12. 当前文件到目标的完整迁移清单

| 当前实现 | 目标位置/动作 | 同一次实施必须清理 |
| --- | --- | --- |
| `main.jsx`、`WorkbenchNavigation.js`、`WorkbenchGuards.js` | `shell/`，显式挂载与释放 | 生产全局调用、隐藏自动注册 |
| `theme.js` 与主题全局 | `shared/runtime/theme.js` 与 `app/theme.js` 首屏入口 | `window.APSWorkbenchTheme` 导出与调用 |
| `transport.js` | `shared/network/transport.js`，存储部分移到 `shared/session/pending-store.js` | 原大对象导出、`transport.js:153` 的 404 `receipt_not_found` 特判 |
| `resource-session.js` | `shared/session/query.js`、`command-session.js` 与领域会话 | 删除 `resource-session.js:148-175` 仅服务坏 DTO 的 summary 深校验 |
| 25 个 `*Contract.js / *API.js` | 对应 `domains/<领域>/` 的 API、输入合同与展示模型 | 砍掉 `Reflect.ownKeys` 白名单、12 处分页公式重验、文案加总重验、2 万行 diff 重算、全图闭包与 SQL 排序重验；保留并归位 5 类真实边界 |
| `PlanContract.js:209-215` 与 `PlanGanttModel.js:66` | 在 `PlanGanttModel.js` 中直接用已有 `taskIndex` 展开 `after` 引用 | 删除 `PlanContract` 的 `verifiedTasks` `WeakMap`、重复索引与原地篡改 |
| `CalibrationAdoptionAPI.js:69` 及各采用/试调/排产/系统回执消费者 | 5 类数据库命令（普通、候选采用、试调采用、校准采用、试调编辑）统一消费 `{state: "recorded" \| "not_observed", receipt, may_be_in_flight, resolution}`；排产受理保持 `{found, run, resolution, data_context_ref}`；系统维护保持数据库回执或外部维护日志协议 | 同步修复 `CalibrationAdoptionAPI.js:69` 的 `expect` 与后端 `calibration_adoption.py:42` 的 `g.workbench_result_target`；删除旧 `committed` / 裸 `receipt` 分支与 404 特判 |
| `prototype/` 生产引用与 `ReportEvidence.jsx:45-60` | 迁入 `shared/ui/{icons,Table,buttons,MetricStrip}.jsx`、`csvCell`、`inspectEnvironment`；`Table` 原生输出无障碍与固定列属性 | 删除 `ds-projection.cjs`、`compile.cjs` `selectDeclarations`、7 个 0 调用死组件及 `TableFrame` 的 `useLayoutEffect` DOM 修补 |
| `build-order.json`、拼接型 `compile.cjs` | 固定版本 `esbuild` 打包，保持 `asset-manifest.json` 离线静态资产硬契约 | JS `live/pending/foundation/never-live` 顺序表 |
| 21 项 Node 契约测试与 `gantt_current_runtime.cjs` | 共用 `esbuild` 打包测试入口并在独立 `vm.createContext` 沙箱执行，支持注入 `react.js` 桩与业务替身 | 删除生产 `window` 导出路径，以及 `tests/workbench/*.cjs` 中 `delete task[key]` / `.reverse()` 等母题 D 篡改断言 |

## 13. 同一次实施的依赖顺序（严格遵循 `A3 -> A2`）

1. **（`A3`）** 引入宿主固定版本 `esbuild`，打通生产双入口（`app/shell/main.jsx`、`app/theme.js`）与 Node `vm.Context` 契约测试沙箱构建管道（含 `shared/runtime/react.js` 桩与替身注入），验证 `asset-manifest.json` 离线闭包契约。
2. **（`A3`）** 拔除 `prototype/` 生产依赖，将图标、`Table`（原生支持 `<caption>` / `<th scope="col">` / 拖拽列宽等）、按钮、指标条、`csvCell`、`inspectEnvironment` 收口为 `frontend/workbench/app/` 一等源码，删除 `ReportEvidence.jsx` 的 DOM 事后修补与 `ds-projection.cjs`。
3. **（`A3`，保持现有 HTTP 响应协议不变）** 重构共享网络、底层命令结算会话（`command-session.js` + `pending-store.js`）与查询 Hook，迁移全部领域模块与 shell 为显式 ESM `import/export`，剥离 25 个 `*Contract.js / *API.js` 对受控 DTO 的事后重复重验，将紧凑 `after` 引用展开归位到 `PlanGanttModel`，守住 5 类真实边界，并同步清理 `tests/workbench/*.cjs` 中的母题 D 断言。
4. **（`A3`）** 删除全部 `window.*` 业务导出、`build-order.json` 与旧拼接编译器，跑通 21 项 Node 契约测试与离线静态资产门禁。
5. **（`A2`，在 `A1`、`A3` 完成后同包原子切换）** 同步切换后端 7 条命令回执查询链路与前端回执消费者、协同修正 `CalibrationAdoptionAPI.js:69` 的 `expect` 地址与 `calibration_adoption.py:42` 的 `g.workbench_result_target`、删除 `transport.js:153` 的 404 特判并更新契约测试 fixture，完成端到端真实浏览器验收。

## 14. 验收与完成条件

- **构建与静态资产硬契约**：生产双入口由固定版本 `esbuild` 离线打包成功，任意缺 import / 缺命名导出在构建期直接报错失败；`asset-manifest.json` 保持 `schema_version=1`、`target=chrome109`，本地字体/tokens/inline CSS/logo/Lucide LICENSE 离线闭包完整通过 [`test_frontend_offline_static_assets.py:145`](../../../tests/app_runtime/test_frontend_offline_static_assets.py#L145)，Win7 运行包不含 Node 或 `esbuild` 二进制。
- **Node `vm.Context` 契约宿主**：21 项 Node 契约测试（[`test_ui_refinement_node_contracts.py:13`](../../../tests/workbench/test_ui_refinement_node_contracts.py#L13)）与甘特 VM 宿主（[`gantt_current_runtime.cjs:7`](../../../tests/_support/gantt_current_runtime.cjs#L7)）全部通过 `esbuild + vm.createContext` 沙箱执行真实生产 ESM/JSX 源码，沙箱存储/网络/锁隔离与 Hook/替身注入正常工作。
- **DTO 减负与 5 类真实边界**：25 个 `*Contract.js / *API.js` 的 `Reflect.ownKeys` 键白名单、分页算术重验、2 万行基线 diff 重算、全图闭包与 SQL 排序重验全部清零；`PlanGanttModel` 正确展开紧凑 `after` 引用，业务分流、`bindResponse` 身份绑定、外部用户输入归一化（`input`）与本机存储反序列化校验（`validIntent`）全部通过验证。
- **`prototype/` 断联与原生 `Table`**：`ds-projection.cjs` 与 AST 切片删除；`shared/ui/Table.jsx` 原生渲染 `<caption>`、`<th scope="col">` 并保留列宽拖拽手柄、百分比列宽、右对齐、自定义单元格与横向滚动，`ReportEvidence.jsx` 无 `useLayoutEffect` DOM 修补。
- **命令结算与 7 条回执消费**：同一 `storage + key` 由底层会话管理，[`storage_write_contract.cjs:81`](../../../tests/workbench/storage_write_contract.cjs#L81) 锁定的先写 `RECENT` 再清 `PENDING`、`read()` 不暗写、Web Locks 锁内 `flush()`、刷盘失败终态不退回 `pending` 全部保持；5 类数据库命令回执查询消费者统一对接 `{state: "recorded" | "not_observed", receipt, may_be_in_flight, resolution}`（采用链路含 `data_context_ref`），排产任务受理查询保持 `{found, run, resolution, data_context_ref}`，系统维护查询保持数据库回执或外部维护日志协议，无 404 `receipt_not_found` 特判，校准采用 `expect` 地址一致。
