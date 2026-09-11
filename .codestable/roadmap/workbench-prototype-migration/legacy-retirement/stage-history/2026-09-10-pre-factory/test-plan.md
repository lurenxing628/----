# 退役测试计划与旧合同迁移

- 本计划不是完整执行结果。G 已执行 nav 解析、真实私有 SQLite 的旧 GET 转换、候选 dispatcher/呈现及5项私有 HTTP 联验；HTTP 包含一组真实人员导入预检/过期拒绝/确认写入回读、真实打印、手册原文下载。其余业务链、浏览器 B/K/V/P、candidate 全站及回退演练仍 not_run。
- Main 已报告正式容量窗口通过：5000×4=20000 rows，admission_to_terminal=122.728285375s，runtime=121.342296s，1472 inputs 前后 hash 一致，重启 refs/payload/业务保留。G 没有重跑或独立替代该证据；17 全站仍未通过，不能应用退役。
- 以下以最终 candidate 实际内容为对象。禁止 TESTING/环境开关/特殊 query 让旧 UI 回来；不改门禁阈值、基线或删原业务断言来消红。

## 1. 必须覆盖的分母

| 维度 | 分母/范围 | 最小证据 |
| --- | --- | --- |
| 原能力 | planning 206 族不改写 | 复用前逐源 hash 核对；原型 passed 不抵迁移 |
| 旧选项 | LEG-001..081 全部 | options 矩阵每 ID 的 B/K/V/P 状态、源 hash、用例/截图/回读位置；不适用逐条写原因且保留行 |
| 页面 GET | 51 条实际规则 | 35 条条件重定向、14 条新说明、2 条新打印/手册；每条正例、非法参数、原合法但不等价参数 |
| 保留 GET | 39 条非页面规则 | 数据/下载/健康原状态、MIME/Disposition/内容、错误返回；不被 HTML 410 拦截 |
| 保留 POST | 113 条规则 | 原解析、前置校验、事务、确认/取消、失败/部分结果及原返回语义；至少 24 条导入 POST 检查新呈现 |
| 新接口/资源 | 152 workbench 规则 + static | 所有必要资源仍在最终 manifest 中，真实哈希/依赖/许可证；新请求不加载被移除资源 |
| 候选资源 | 68 旧模板、9 CSS、45 JS、2 SVG 的逐文件处置 | 不是一次全部删除；先完成打印、回执等依赖替换。2 文档、错误与恢复能力保留 |

## 2. 动作级 B/K/V/P

| 用例组 | B 真实后端 | K 浏览器输入/点击 | V Main 目视 | P 刷新/重启 |
| --- | --- | --- | --- | --- |
| 等价旧 GET | 隔离真实 fixture 解析 version/role/scenario/范围，映射已存在永久 ref；读取不补建、不换对象 | 从地址栏输入旧书签，点击新页目标/导出，检查目标 API 真正收到相同身份与范围 | 标题、选中对象、范围、非正式警示、结果/导出一致 | 复制新规范 URL、新标签、刷新、同版本重启后同 ref；缺失/失效明确错误 |
| 不等价旧 GET | 只读快照与 SQL trace 证明未执行写命令；保留下载仍真实可用 | 输入带不支持的合法条件，确认新说明列出具体原因及 LEG ID，不静默跳空列表 | 新风格，不含旧控件/导航/iframe；说明不声称未验证数据已迁移 | 同 URL 重开仍说明；不落到默认最新版 |
| 12 组旧导入 | 真实 XLSX/预检基线/已存数据，preview→confirm→回读；过期基线、引用冲突、行失败/事务失败全部保留原断言 | 向原 preview 提交文件，实际勾选确认并提交原 confirm；检查 mode/raw_rows_json/preview_baseline/filename/strict/auto_generate 原值不丢 | 逐行结果、真实失败/警告、replace 全量影响；不出现旧表格壳/旧脚本 | 刷新前后不自动重发未知交易；核对审计/行数/修订，重启后业务保留 |
| 打印/帮助/错误 | 原打印查询/身份警示、手册下载字节、通用错误字段/日志链保留 | 点击打印、切换人机/合法 day、下载原手册，故意触发 400/404/500 | 打印 thead 重复版本/范围/警示、空白备注、无伪造现场状态；错误页无旧外壳 | 冷启动/资源缺失/无 JS 仍有可读错误与恢复诊断；不存在版本不改查其他版本 |
| 新旧数据保留 | 旧/新增字段、引用、历史、执行事件、更正链、配置和外置 journal 分开做精确集合/值对照 | 新 UI 真操作后再从只读接口核对；不以按钮出现代替提交 | 结果、未知态、部分结果无误导 | 按 minimum-design 的 R1..R4 演练代码回退与 D1 数据保护 |

纯控件退役的 B 不伪造“点击原按钮成功”：检查父入口无副作用及对应后端/存量数据仍保留。已退控件不能再次作为可执行旧 UI 渲染到浏览器。当前 81 行均 not_run，没有以 N/A 缩分母。

## 3. 旧测试合同如何改

以下是下一步测试改造清单，G 本轮未修改这些旧测试。只改已批准退役的 UI 形状断言；原业务/错误/数据保护断言继续存在，必要时迁到对应真实新入口用例。

| 现有测试/依据 | 保留的合同 | 后续退役证明 |
| --- | --- | --- |
| `tests/app_runtime/test_validate_dist_static_payload.py:57`、`validate_dist_exe.py:41` | 包内资源非空且 HTTP 得到真实字节，缺/空载荷必须失败 | 旧 style.css/common.js 锚点换最终新 manifest/入口闭包；额外验证被移除资源在 candidate 不存在且 HTTP 不可取。不能夹带旧文件保旧断言 |
| `tests/web_pages/test_template_urlfor_endpoints.py:76` | 最终模板的所有 URL endpoint 真实注册 | 新模板扫描不漏，旧 endpoint 保留但响应类别改变；另加显式逐 route/method 分类完整性，不能仅剩空模板目录让扫描绿 |
| `tests/app_runtime/test_frontend_offline_static_assets.py:178` | 无外链脚本/样式/字体/图片 | 按最终新闭包继续同标准扫描，保留 UTF-8/缺文件失败；不是减少扫描范围 |
| `tests/gantt/test_gantt_url_persistence.py:1` | 版本/范围/资源不能错位或丢失 | 旧 gantt_* 控件代码断言逐项对应 LEG-035..041 的明确退役；转为旧 URL 精确映射/不等价说明及新组件真实消费，禁止仅看 Location 中字符串 |
| `tests/gantt/test_gantt_zoom_contract.py` 等旧 JS/DOM 合同 | 属于数据/时间边界的断言仍保留到领域/新图 | 仅缩放/旧 selector 合同改为对应 LEG 的不可达证明及不改排程；每条有旧断言→新断言去向，不直接删除整组 |
| `tests/web_pages/test_aps_workbench_context_propagation_contract.py` | 请求/有效身份、日期和范围跨入口保持 | 新规范 nav + 原下载 query 的逐字段断言；历史/候选不自动变 current adopted |
| `tests/scheduler_analysis/test_report_context_filters_contract.py` | report/export 同一计划、日期和资源语义 | HTML 外壳改为等价目录或明确退役，但旧导出真实字段/范围断言不降低；不能把事件日期改为计划完工日期 |
| `tests/web_pages/test_week_plan_print_page.py:47` | 页眉、分组、列、非正式警示、day 400、空态、版本 404 | 原查询断言保留，加载新模板；新增无旧 CSS/JS、打印跨页仍有警示。保留打印功能，不改为 410 |
| `tests/config/test_config_manual_markdown.py:1`、`test_scheduler_config_manual_url_normalization.py` | 原文下载、允许返回地址、锚点、不可读错误/noscript | candidate 已提供无旧JS依赖的手册呈现、兼容章节锚点、原文/相关主题；私有真实 GET/下载通过。Main 对新 DOM 更新合同，不删除原下载和内容断言 |
| `tests/web_pages/test_system_runtime_logs_page.py`、诊断包测试 | 文件/日志来源、过滤边界、读取失败不能假空、ZIP 内容 | 请求目标可迁到新读取接口，但失败注入与内容断言全部保留；日志原 GET 重定向后仍能看到错误结果，不只测 302 |
| 旧 Excel preview/confirm 及业务引用/rollback 测试 | mode 特定语义、真实预检基线、防漂移、事务、逐项结果、原字段保留 | 将旧 selector 改为新确认表单合同，仍从真实 preview 提交原 confirm 并查库；不注入旧 renderer 后门，也不将所有 POST 410 |
| `tests/schedule/route_view/test_scheduler_route_registration_contract.py:128` | 显式注册、幂等、导入边界与 routes 存在 | route 仍在，加入页面 handler 的新响应与其他 methods 原 handler 身份不变；不删除 scheduler 整体 |
| `tests/gate_meta/test_frozen_bundle_contract.py` | frozen import anchor 合同 | 不动其源/断言；已由 Main 的 c0097278 提交，不因 G 文档/退役反向改写 |

## 4. 已有样稿与未执行的真实测试

- `draft-tests/test_dispatch_samples.py` 已有15个单元测试：51 endpoint 清单原子安装、GET/HEAD、重复 query、POST 不被410、非页面接口不被包装、确认字段、打印警示/列、错误、手册章节/无脚本内容、24结果endpoint模板字段白名单。此组不含数据库/浏览器。
- `draft-tests/test_candidate_http.py` 另有5项：正常显式调用 `install_legacy_retirement(app)`，核对113 POST及39非页面GET的原函数；真实旧GET/说明页无写库；真实人员XLSX预览、过期基线拒绝、确认/重开回读；真实打印；真实手册GET与原md下载字节相等。仅私有候选 fixture，不是实际生产挂载或完整12组导入验收。
- `candidate-review-index.json` 对 13 个 Python renderer 文件验证了“恢复模板字符串后 AST 完全相等”；这只证明 patch 不改其他解析/事务/参数代码，不能替代后续运行测试。
- 真正应用后至少新增/登记 `test_legacy_retirement_routes.py`、`test_legacy_retirement_context.py`、`test_legacy_retirement_posts.py`、`test_legacy_retirement_assets.py` 和保留/回退测试。它们是待建用例，不是本轮已跑命令。
- 本轮实际新增的产品单测是 `tests/workbench/test_final_navigation_boot.py`，support 是 `final_navigation_support.py`，请 Main 按实际消费者登记到门禁；G 不改共享 registry。

## 5. 运行顺序

1. 定点 parser/dispatcher/template 单测可先跑；用私有 pycache、DB、日志、锁、浏览器 profile、临时构建目录。
2. Main 接好规范 boot 后，以真实 private app 做 HTTP + 浏览器输入/点击/主线截图审视/刷新重启；显式坏 nav 必须 HTML 400，不能用旧 history 填补。
3. 17 全站通过后 Main 再应用退役 patch，重建全新 candidate；先验 24 条导入 POST、print/manual/error，再移除旧模板/资源。
4. 最终正式性能只由 Main 安排独占窗口，不自行并跑。后改若影响容量路径按 Main 判定重跑，不改旧 PASS 的源绑定。
5. Main 最终以 `.venv/bin/python scripts/run_quality_gate.py` 运行完整门禁，绑定最终 HEAD/源和 candidate hash。dirty 验证不称 clean-worktree proof；记录未完成项，不靠基线刷新遮掩。
