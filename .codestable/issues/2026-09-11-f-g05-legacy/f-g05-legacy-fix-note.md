# F/Ohm：G05 四组旧测试回归

## 当前交接

- 三组已关闭且 Main 已核对合并；已19 PASS 不重跑。[6 文件交接包](/private/tmp/aps-F-G05-legacy.VjixJO/overlay-threefix-1/manifest.json)，SHA-256 `3e1d730758a1572eb915d26413f11880f335511c25cc12e100ec9e440383bec2`。随后获授权的 Batch 单文件修复已回写，[产品与2份新测试交接包](/private/tmp/aps-F-G05-legacy.VjixJO/overlay-batch-return-1/manifest.json)，SHA-256 `2a8cdfb684771a81dbe67272054ab7c5a53f3a93ef9c59bba4ae20b7ce1525d7`；45项合同检查通过，浏览器验证等待新静态 Batch。
- 错发 H/James 的四项任务未修改文件、未建副本、未启动测试。F 只处理 live browser、dashboard external handling、dashboard widgets、DU system restore。
- 正式固定输入：[Main 公共 manifest](/private/tmp/aps-G05-failure-baseline-NEJgZ8/manifest.json)，SHA-256 `ac34f31052f6593d4c4127f33fa4d027d4d14ac034a401d48dfaae48f03db859`。4898 文件、103665475 bytes；不再读取 Main live private。
- F 原样源 `/private/tmp/aps-F-G05-legacy.VjixJO/source-public`；独立验证树 `/private/tmp/aps-F-G05-legacy.VjixJO/candidate-public`。初始化时两份逐文件 SHA/bytes/mode 与公共 manifest 一致；六测试封装时复核公共源和 F 原样源仍全量一致，当时验证树仅有6个测试差异、产品差异为0；后续单独授权的 Batch 差异另包记录。[F 清单](/private/tmp/aps-F-G05-legacy.VjixJO/source-manifest-public.json) SHA-256 `8aba075e90ccf8c47b6b40ca36a50885852984c90fab37918f5c538e5ec926f7`。
- 原 G05 log/XML/JSON 和 live probe 失败记录已留在 `/private/tmp/aps-F-G05-legacy.VjixJO/original-failures/`，精确哈希在 F 清单。切换公共基准前建立的 `source-g05/candidate` 未用于测试或修改，保留为过渡记录，不作为修复依据。
- 初始 8 个指定测试文件及 5 个相关 helper 的原树 SHA 与 G05 相同；实施前再次检查。已回写6个自有测试文件，以及后来单独授权的 `BatchWorkspace.jsx` 和2份新合同测试；回写后 SHA 与各自验证副本一致。未覆盖并发修改，未改 C 其他文件或 `batch_widgets_probe.cjs`。

## 已确认产品阻塞

- `test_dashboard_widgets.py` 的 `navigateAndReturn` 第129行超时在“批次资料”落点，不是慢响应。失败 `dashboard-ui.json` 的 `failure_text` 是“批次来源引用或返回入口不正确。”
- 固定 G05 `frontend/workbench/app/DashboardWorkspace.jsx:45` 生成 `{ return_to: { view: 'dashboard', context: current } }`，第47行补 `entity_ref`；`BatchWorkspace.jsx:13-14` 的 `sourceContext` 却只接受 `return_to` 字符串 `run/dashboard`。真实 `main.jsx:143` 直接把上下文交给 `BatchWorkspace`，没有 fixture 专属适配。
- 已按 Main 授权仅改 `BatchWorkspace.jsx`：严格验证信封，原样保留内部 `context`，新第134行按 `onNav(view, context)` 返回；旧字符串继续单参数调用，未知目标、错误类型及额外信封字段拒绝。Dashboard 自行验证内部内容，Batch 无新增组件依赖。新合同测试45/45通过；没有改发送端、后端、路由或静态资产。
- 原 `test_dashboard_widgets.py` 仅运行一次，结果1 FAIL /1 PASS /35.21s：probe 第9行局部编译名单不含 Batch，第33行仍加载基线 `static/workbench/app/BatchWorkspace.js`（SHA `274c22fca9fca53c95ccf5939a54b637d8e7dd594527266bcad7503e805fa224`），所以仍出现旧 DOM 报错。这不是新 JSX 的浏览器验证。宿主已停；未自行第二次执行。待 Main 统一静态重建后单跑该项，或另行允许 probe 的局部编译依赖修正。

## 已关闭三组

- live：补真实 runtime、restore host、launcher locks 与 `WorkbenchRequestHandler`；复用正式计划夹具，更新旧控件合同，等待实际读取完成再切页。`seed_fixture` 与 `runtime_tools` 逐字 SHA 不变。`livefix6.xml` 为1 PASS /93.74s，内部60/60、1185断言、188次请求逐次数据库不变，浏览器/HTTP/网络错误均0，运行时与锁正常释放。
- external：unknown 对象的旧 disabled 断言改为 R14 的真实原因确认框；核对原因、原对象、取消后仍保留原详情且不导航、不写入。无跳过或成功桩。
- DU：原 proxy 的 `response.destroy()` 在真实200后引发 Chromium同键POST传输重试，第二次503覆盖 `report.operation`。改为真实200完成后在浏览器拦截层丢ACK，仍严格要求一个业务POST、同键回执、备份/数据保留和只读结果。external + DU 的既有 `twofix.xml` 为18 PASS /115.29s；两文件 SHA 不变，复用该次证据，不据此宣称全量通过。

原始 G05 口径仍为24 FAIL /2178 PASS /10 SKIP。上述仅为固定基线上的定点证据，不是最终 HEAD 或 clean-worktree proof。产品变化只有单独授权的 Batch 文件；未改 registry、静态资产或原库，未做 Git 写入或新完整矩阵；最终统一门禁等待 Main 冻结窗口。
