# G 私有候选验收交接

- 已解决 H 指出的新增 SQL/Repository 越层和目录依赖环，完成新绑定快照的真实 factory 验证。Main checkout 仍未应用退役 patch、未挂载 dispatcher、未删旧资产；不是 17/18 或发布通过声明。
- 当前结论以 [factory-acceptance.md](factory-acceptance.md) 和 [factory-verification.json](factory-verification.json) 为准。早期 30+15+5 证据保存在 `stage-history/2026-09-10-pre-factory/` 和 `verification.json.previous_pre_factory_stage`，不能混用其旧 hash。
- V4已封存。随后批准的D-P003仅导航解析扩展另见 [精确schema与hash](../../../features/2026-09-10-trial-task-origin-navigation/trial-task-origin-navigation-ff-note.md)、`task-origin-overlay.json`/`.patch`；新增8项测试，当前局部回归51passed。它没有回填V4的factory通过结论，也未修改V4源码。

## 当前改动

- `core/services/workbench/legacy_navigation_queries.py` 是纯 SELECT 查询叶；web 只保留旧 URL/token/date 解析与 HTTP 决策。保留外层事务，缺身份不补建、不换对象，不导入 Flask/werkzeug/web。
- `core/services/report/date_input.py` 原样承接两个显式报表日期校验函数。旧 `web/routes/report_plan_preview.py` 兼容导出，两 web 调用方直接依赖 core；不是 lazy import 绕扫描。提取的 2 个函数及原 web 剩余 7 个函数 AST 均相等。
- 有效人员日历详情明确退役，缺人员仍 404；不误判为 400，也不跳到另一种日历。专项测试已锁住。
- 四个专项测试加两份 support 均在以下 13 文件清单。Main 当前 registry 已列四个测试，但位于 supplemental `workbench_browser` 组，不等于默认必跑或执行回执。G 未改 registry；最终门禁选择及新 core/旧 web 文件的源绑定由 Main 负责。

## 真实验收

| 组 | 本轮结果与边界 |
| --- | --- |
| 正常 pytest | 46 passed：nav 12、旧 GET 19、分层 4、日期配对 8、原架构适应度 3；正常 conftest，无 xfail/门禁绕过 |
| 源守卫 | 2 个负向测试通过；动态原目录/命名空间/插件别名回落、模式变化被拒绝 |
| 两种 import scanner | production 和 include-tests 均 exit 0，旧 baseline 字节不变；仍有 1 个基线内目录环，不是全仓零环 |
| 12 组导入 | candidate 12/12、baseline 12/12：真实 XLSX preview/confirm、拒绝、刷新、精确库回读/重开、原模板和导出检查 |
| 旧方法矩阵 | 每侧 51 页面及 39 非页面 GET/HEAD、113 实际空表单 POST；POST 状态/MIME/JSON、非页面状态/MIME无差异，零 5xx，GET 业务数据不变 |
| 报表/打印/手册 | candidate 26、baseline 24 次日期 HTTP；两角色真实打印含身份警示、批次、日期/范围、空白备注；原手册下载字节相等 |
| 真实消息链 | 设备修改 POST → 旧详情 GET → canonical；正常、坏 nav 400、实际缺资源 503 三条通过，已提交数据保留，消息刷新只消费一次 |
| 静态检查 | 13 实际文件 Pyright 0 errors/0 warnings；13 文件及全部 factory harness Python Ruff 通过 |

113 空表单请求不是 113 条完整交易验收；12 组导入也不是所有 mode/replace/引用冲突组合均已覆盖。HTTP/boot 中消息正确不等于浏览器已可见。

## 冻结来源

- 最终私有根：`/private/tmp/aps-g-retirement-candidate-u8YnDE`；`source/` 已真实应用原 patch，并在真实 `create_app` 后显式调用 `install_legacy_retirement`；`baseline/` 未应用/未安装。
- candidate：3927 文件，92,948,312 bytes，aggregate `e74e6dce3c8a196433692084dbdc4d94f3f9c4b79e952bc352c0e7ed8714b85b`。
- baseline：3919 文件，92,926,072 bytes，aggregate `a2920c5e43ab655f5b8e82897df3f4a8af3b25e8eeebc66d484afcd072b4240f`。
- V4 继承 V3 的 3918 个已冻结文件并逐字节/模式核对，补入正常 conftest 所需原治理台账，随后复核并实际应用全部 24 preimage/postimage。两种循环基线也在快照内。
- 所有运行前后源内容/模式相等，测试 harness 单独冻结并绑定 SHA。原源码/生产数据不作为运行时回落；显式复用 Main `.venv` 的标准依赖不等于从 Main 导入产品代码。
- CzTalo、FtCvUw、WQooWU 三轮旧目录及失败回执保留。完整范围、缺项修正和测试脚本 SHA 在 JSON，不能把声明范围的静态盘点夸大为所有未测动态路径的完备证明。

## V4 封存源码 SHA256

下表不包含后续D-P003两文件overlay；当前解析器/测试新hash以overlay记录为准。

| 路径 | SHA256 |
| --- | --- |
| `core/services/report/date_input.py` | `09cbdd505aeb05cdd07996288af073bc7e19c59a0ce749f15bcdf09bc565f0a0` |
| `core/services/workbench/legacy_navigation_queries.py` | `d29482a6953b5d4937feaafb5258b43114c2f2b70c58d5c6dcae30590564f429` |
| `web/routes/report_plan_preview.py` | `c61a6c21c6708ca3c944b4638310e8e7d48e5fb51088ed40e85de2dd6b9c528c` |
| `web/routes/workbench/navigation_boot.py` | `405adefc94b0280fa6a187400d2277234d140bc349cb37d0ca6ef9cc529f785e` |
| `web/routes/workbench/legacy_page_contract.py` | `f738fd62bd10a7c3aaca974193641f3061b42f37297754598b179e198fc088ad` |
| `web/routes/workbench/legacy_navigation.py` | `63f3f6c92d8a1e57d93902ca7f28eb728e91fe35b9e71075884b875c02ca67cf` |
| `web/routes/workbench/legacy_navigation_plan.py` | `4a75f6c88e78cb0189c9f0804c0ba9ed431fadfca4086ab4ab522a4d4c8abe00` |
| `tests/workbench/test_final_navigation_boot.py` | `8fcb2b8aa35e148a34376c10870e1ae26377a2ce290d70f048cf8a0586598af3` |
| `tests/workbench/final_navigation_support.py` | `cee7d9b907ceb66bab0a1a6d51baa6871dc3336231486e2d12ac9f8ce0ce9071` |
| `tests/workbench/test_final_legacy_navigation.py` | `efbf34f05ce8b834b6cfeaa5c6b93a6a45dac01b57bc1427875f3a49109d0c37` |
| `tests/workbench/final_legacy_navigation_support.py` | `d6480c3fb10e2b0a8a59566374b3b1adeec0206ed65c2b4eb3ae207c674248e3` |
| `tests/workbench/test_final_legacy_navigation_layering.py` | `6ebf323e625b987692379f939dee46f82699cb1156c14121161b66335e2917f7` |
| `tests/workbench/test_final_legacy_report_dates.py` | `9d09c6f6c96268346d0eefcaa6959622730a6a6142a48a1181c9b2ea1c0c94a8` |

V4封存时以上13文件与私有snapshot相同；后续仅导航解析器和对应测试按D-P003另作overlay变化。12个新增/未跟踪文件、1个已跟踪web文件修改及文档/harness未提交；V4封存时index为空。HEAD只读观察值为 `21134f739c192aca45cee9356d13138f1c658953`，证据绑定源hash，不冒充该HEAD的clean proof。

## Main/F 后续

- 完整 patch 仍为 24 目标，SHA `a6c1a20dce70b241046b09ecfcd349fd7c8dddb7a6f00ee0ea644d916fabd0e2`。它不重复覆盖以上实际源码，也不包含 factory/pages/JS/schema/资产删除。正式应用前再次检查全部 preimage，不能覆盖并行改动。
- F 可统一从 `factory-tests/source_binding.py capture/check` 入手；操作顺序及非 Python 事实源见 [factory-tests/README.md](factory-tests/README.md)。
- 当前快照构建自身产物 hash 正常，但 302 个源输入有 49 个漂移，不是匹配构建；浏览器验收继续待 F/Main 的完整匹配目录，不在旧 bundle 上宣称 nav、flash、17 或 18 通过。
- Main 的 pages/main.jsx/unavailable 原消息消费者已随源快照复用，G 未覆盖或另造 flash 存储。后续浏览器必须验证真实提交后可见及只消费一次。
- 17 授权后才由 Main 正式挂载/排除旧资产，并完成最终整站、Win7、全质量门禁和 D1 回退演练。本轮未操作生产库、原 preview 或 Main 构建；没有 G 服务器、浏览器、构建或测试进程在途。
