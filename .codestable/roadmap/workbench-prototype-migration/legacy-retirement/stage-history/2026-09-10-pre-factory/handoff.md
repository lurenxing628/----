# G 完成交接：旧GET转换与待应用退役补丁

- 已完成本轮授权代码：严格nav（含delay及无nav外层验证）、真实旧GET SELECT转换器和测试；dispatcher/新结果/print/manual/error为可应用patch，仍未挂载、未删资产。
- Main正在接pages/boot/JS；G未改这些现有文件。尚未收到17通过后的退役挂载许可，本交接不是全站17/退役18完成声明。

## 精确接口

- `web/routes/workbench/navigation_boot.py:178`：`read_navigation(view, request.args)`。唯一view/nav先验证，再决定无nav返回None；`WorkbenchNavigationInvalid`由Main以现有unavailable400+no-store呈现。
- `web/routes/workbench/legacy_navigation.py:156`：`resolve_legacy_get(conn, LegacyGetRequest(endpoint, tuple(args.items(multi=True)), path_values))`；非页面None，等价redirect，否则明确retired；`:53`提供`build_legacy_destination(decision)`。
- `legacy_page_contract.py:69`定义request，`:82`定义decision；固定51页，严禁前缀拦截。具体字段/身份/日期/不等价规则见`legacy-navigation-contract.md`。
- 待应用的`draft-payload/web/routes/workbench/legacy_dispatch.py`提供`install_legacy_retirement(app)`：所有blueprint注册后、服务开始前调用一次，已具体连接g.db/转换器/新呈现，不再需要Main补写converter。
- 17授权后先复核24个preimage，再应用patch并挂载；新presentation与全部新模板须一起应用。Main登记两份test及两份support，完成HTML/浏览器消费和最终候选门禁。

## 实际源码 SHA256

| 路径 | SHA256 |
| --- | --- |
| `web/routes/workbench/navigation_boot.py` | `405adefc94b0280fa6a187400d2277234d140bc349cb37d0ca6ef9cc529f785e` |
| `web/routes/workbench/legacy_page_contract.py` | `f738fd62bd10a7c3aaca974193641f3061b42f37297754598b179e198fc088ad` |
| `web/routes/workbench/legacy_navigation_plan.py` | `a8f822fa82bb681ab87dc361ee9eec2c34a5821861cf17cdbe1b9887a69b8bba` |
| `web/routes/workbench/legacy_navigation.py` | `ad4646bf3cb852e501b712a765793e3ff3e6416183f796d603799b0750ad85c1` |
| `tests/workbench/test_final_navigation_boot.py` | `8fcb2b8aa35e148a34376c10870e1ae26377a2ce290d70f048cf8a0586598af3` |
| `tests/workbench/final_navigation_support.py` | `cee7d9b907ceb66bab0a1a6d51baa6871dc3336231486e2d12ac9f8ce0ce9071` |
| `tests/workbench/test_final_legacy_navigation.py` | `905a653bda26d9e82a0ccd7d29a397ddea82712092e21d44393f2a3a65e0cb49` |
| `tests/workbench/final_legacy_navigation_support.py` | `d6480c3fb10e2b0a8a59566374b3b1adeec0206ed65c2b4eb3ae207c674248e3` |

以上8文件当前均untracked；不在退役patch内重复覆盖。逐函数行号及payload10文件的SHA见`verification.json`。

## 待应用补丁

- `candidate-review.patch`：24目标；14个旧Python renderer只替换模板字符串，其余10个新/错误呈现文件。当前24preimage均匹配，14个恢复字符串后的AST相等；不含factory/pages/JS/schema/service/asset删除。
- patch SHA256：`a6c1a20dce70b241046b09ecfcd349fd7c8dddb7a6f00ee0ea644d916fabd0e2`。
- index SHA256：`8e4fbad3b665f3e81be9fb6835df31ebaec2d90acc74b4f32a323cc0b29106fa`。
- `candidate-review.md` / `draft-payload/`可逐文件审阅；`draft-tests/candidate_sources.py`与`build_candidate_manifest.py`只在内存构造内容并输出，不写产品。
- 结果页保留原确认字段与24个POST回执，显示各自现有模板表头白名单；无generic raw context/data JSON。print保留原警示、范围和空白备注；manual保留原文、相关主题、锚点、下载且无旧JS依赖。

## 实际验证

- 产品专项联合：30passed（nav12 + 真实私有SQLite/ref旧GET18）；不靠mock converter证明身份。
- dispatcher/呈现样稿：15tests OK。私有候选HTTP：5tests OK；使用正常具体安装函数，真实人员XLSX预览不写库、旧基线拒绝、确认写入/重开回读，真实print/manual及原md下载字节一致。
- 113旧POST和39非页面GET注册函数身份未变；这不是113条完整业务交易都跑过。其余11组导入交易与浏览器确认仍由完整验收覆盖。
- 8实际文件Pyright：0errors/0warnings；全部实际与draft Python Ruff通过；无忽略/门禁降级/依赖升级。
- 命令、结果、hash及较早阶段历史证据均在`verification.json`；未跑整仓gate/浏览器/Win7/回退演练，不称clean proof。

## 保留与后续

- G没有stage/commit/reset/checkout、缓存清理或删除。当前记录HEAD=`830a58e69faaa64a39d7a238ba2a0a0cd5c9047c`，index空；其他dirty原样保留。
- planning206与原81清单hash未变；81矩阵未伪填B/K/V/P通过。生产库、原preview、源码归档恢复均未操作；仅私有临时SQLite测试写入并关闭。
- 剩余由Main接线/验收：规范boot前端消费与消息可见；17后应用/安装；候选资产排除及旧UI负向缺席、其余业务全链、最终整站/门禁、代码与D1新数据回退证明。
- 本轮没有任何G服务器、浏览器、构建或测试进程仍在运行。
