---
doc_type: issue
date: 2026-10-10
status: resolved
---

# Win7 大计划读取在 16 并发下超过 60 秒

## 问题与影响

Win7 SP1 x64 原生冻结程序在真实 100 批次、5000 工序、6 条分次报工样例上进行第一轮重度读取压力测试，完整全局分析和正式计划 workspace 大量超时。轻量健康检查和设备目录仍正常，说明不能用健康正常、单次读取或先前界面通过来核销并发大计划读取能力。第一轮压力结果为 **failed**，原失败、每次请求、进程采样和工具错误全部保留。

首压力的冻结源码是 `a4a6ad24452675305196c8889f18482c025447ad`；当时宿主 `9d4faa56743f9f9ab4af3e3740fcf14ea5bd198a` 仅改变债务台账行号/验证时间，运行内容相同。修复前clean17步/405节点门禁属于这份运行内容，不能覆盖后来的读取CPU改动；最终4f门禁及原生核销分别保存在下文，旧证明不改写成新版本。

本问题现已 **resolved**：修复源码 `4f850c75cfb4c2d4d975e7832958180cd6f82d54` 的完整 clean 门禁17/526普通通过；同一源码原生冻结v3在相同100/5000/6、600s/16worker/60s socket timeout/无重试条件下，实际 **279/279通过、timeout/failed/non_200/invalid_content均0**。压后任务/数量/报工/来源链及全列导出保持，样例停用与复用已核销。最终临时Python退役后的正常启动/停止、进程退出、VM原状态恢复及桌面交付也已完成；Git整合另由root实际执行并记录收据。完整范围见[原生验收审计](../../audits/2026-10-10-win7-complex-native-acceptance.md)。

## 实际复现及第一轮结果

来宾 4 logical processors、约 8 GiB RAM；冻结后端 5957，backend PID 564。测试程序在来宾直接发真实 loopback GET，16 个 worker 同时开始，持续发新请求 600 s，socket timeout 60 s，**没有重试**；结束时停止新请求，等待全部在途请求完成或失败。不是宿主串行 guest_rpc 桥接，也不是合成成功响应。

| 指标 | 实际结果 |
| --- | --- |
| run | `20261009T233236555-1212` |
| 实际总耗时（含最终 drain） | 657.451 s |
| 最大同时在途客户端请求 / 完成 worker | 16 / 16 |
| 全部请求 | 254 |
| 普通通过 / 失败 | 94 / 160 |
| timeout / invalid_content | 160 / 0 |
| health | 42 次，42 个 200；最大 0.140 s |
| machine-directory | 40 次，40 个 200；最大 0.858 s |
| full-global-analysis | 82 次，6 个 200，76 个 timeout |
| formal-scope-00 | 90 次，6 个 200，84 个 timeout |

160 次失败均没有收到 HTTP 状态（记录为 null / None），不能写成 160 个 HTTP 500、413 或服务器返回错误。原报告的 `non_200=160` 包含这种未收到状态的请求，保留原字段并说明含义。成功响应的完整性核对没有发现 invalid_content；这只核销成功收到的响应，不能把超时的完整性也记为通过。

这里的 60 s 是 urllib socket 操作 timeout，测试没有宣称它是绝对 wall-clock 总截止；657.451 s 包含最后一批请求 drain。16 个 worker 都已结束，失败请求没有删除、自动重试或重新归为通过。

原证据：[最终 HTTP 结果](../../../output/win7-complex-20261010/exchange/native-pressure/20261009T233236555-1212/http/result.json)、[原配置及精确内容基线](../../../output/win7-complex-20261010/exchange/native-pressure/20261009T233236555-1212/http/config.json)、同目录 `worker-00.jsonl` 至 `worker-15.jsonl`、[wrapper 状态](../../../output/win7-complex-20261010/exchange/native-pressure/20261009T233236555-1212/wrapper-state.json)。原结果 wrapper `stress_exit_code=1 / state=failed` 保留。

## 资源观测、身份纠正及推断边界

原生 WMI 44 次采样都指向实际 backend PID 564，其 process counter 为 93–100%，平均约 98.909%；在 4 logical processors 上，相当于一个核心量级的 CPU 持续占用。42 个合法的整机换算值约 24.799–25.399%、平均约 25.019%。原计算样本 index 1 出现不可能的 842.9009% 换算异常（48.9219 CPU 秒除以 1.451 s 采样间隔），原样保留，不能把它并入正常均值或声称后端真实超过机器全部 CPU。

后端 working set 峰值 313,176,064 B；原/纠正采样中可用物理内存最低仍分别约 5,661,680 / 5,645,168 KiB。这里没有内存耗尽、OOM 或进程崩溃的证据。**CPU 密集读取路径导致并发延迟是当前证据支持的推断；没有直接测量 GIL 等待，也没有证明某个单一线程机制是唯一原因。**

最初 WMI 把 venv launcher PID **3412** 标成 stress_client，实际发请求进程是其子进程 **1316**。纠正记录通过 progress 自报 PID、WMI 创建时间/路径和 `1316 → 3412 → 1212` 进程链确认身份；只从压力已运行 450.235 s 后覆盖实际 client，持续约 196.585 s。此前 launcher 样本不改名，不回填缺失的真实 client CPU/内存。后端 564 的原采样不受该客户端身份错误影响。

原证据：[硬件](../../../output/win7-complex-20261010/exchange/native-pressure/20261009T233236555-1212/hardware.json)、[原进程采样](../../../output/win7-complex-20261010/exchange/native-pressure/20261009T233236555-1212/process-samples.jsonl)、[实际客户端身份纠正](../../../output/win7-complex-20261010/exchange/native-pressure/20261009T233236555-1212/actual-client-20261009T234029292-5036/client-identity.json)、同纠正目录的 `process-samples.jsonl`。中途 [只读分析](../../../output/win7-complex-20261010/native-pressure-partial-readonly-analysis.json) 当时还是 running，不能替代最终 254 请求结果。

## 同运行源码的 CPU profile 映射

宿主在私有 ignored 目录使用真实 5000 工序已采用样例的独立库副本、正常生产 app factory/Flask 路由及现有持久证据做诊断，原样例和 VM 未改。四个 GET 各执行一次无 profile、一次 cProfile，共 8 次独立源码路由调用；不是统计意义的多轮 benchmark，也不是原生 HTTP 耗时。SQL trace 包括嵌套 PRAGMA 和独立归档 DDL 解析连接，不能全部解释为主库查询。

| 路由 | 结果 / 任务范围 | 无 profile wall / CPU s | cProfile CPU s |
| --- | --- | --- | --- |
| 全部正式 workspace | 413，原有容量拒绝，未暴露部分任务 | 8.472 / 8.297 | 11.359 |
| 合法半范围正式 workspace | 200，3003 任务 | 8.751 / 8.609 | 11.609 |
| 完整独立分析 | 200，5000 任务 | 5.270 / 5.094 | 7.359 |
| 合并值班台 | 200，分析含 5000 任务 | 6.057 / 5.875 | 8.750 |

无 profile 的 CPU 占 wall 约 97–98%，与原生负载下单核量级占用一致。cProfile 的额外开销不能当作产品实际耗时。

已定位的共有重复工作：正式范围读取的 `workspace_projections` 累计约 7.68–8.01 s；`build_plan_baseline` 约 6.61–6.72 s；3 次 `candidate_source` 累计约 5.84–5.94 s，3 次 `project_tasks` 约 5.89–5.92 s，重复恢复和校验 5000 工序的候选准入/归档及采用数量。当前计划与原 baseline 两个不同 plan_ref 的证明必须分开；需要减少的是同一读快照中相同当前采用来源的重复恢复，不能合并不同计划来源或跳过完整性复核。

完整分析另有已采用来源检查后再次恢复归档/数量的开销；执行 ledger 在比较计划与当前计划相同时重复加载同一 5000 task mapping；日期/日历投影存在反复解析、格式化后再解析。原 sorted stats/callers 证明这些具体调用，不是仅凭 CPU 百分比猜测热点。两个压力失败路径没有发现 5000 行逐项 SQL N+1；合并 dashboard 的外协来源 N+1 是较小独立热点，不能替代主要来源恢复成本的判断。最终 canonical 字节预算检查的成本更小，不以提高或移除预算解决。

原证据：[profile 报告](../../../output/pressure-cpu-profile-20261010/REPORT.md)、[机器可读 summary](../../../output/pressure-cpu-profile-20261010/summary.json)、[正式范围原 stats](../../../output/pressure-cpu-profile-20261010/formal-scope-00-stats.txt)、[全局分析原 stats](../../../output/pressure-cpu-profile-20261010/full-global-analysis-stats.txt)。同目录完整 `.prof`、`*-callers.json/txt`、各路由 baseline 和 `profile.log` 保留。

## 工具问题单独记录

- 首次 wrapper `20261009T232816616-2748` 在启动压力请求前，PowerShell 2 的 JavaScriptSerializer 直接序列化 WMI/PowerShell 对象，因 PSParameterizedProperty 循环引用失败。这是验收 helper 序列化错误，不是产品压力失败；原 [failure.txt](../../../output/win7-complex-20261010/exchange/native-pressure/20261009T232816616-2748/failure.txt) 保留，不能计入 254 次真实请求。
- WMI launcher/actual-client 身份错误属于量测工具口径，按上节纠正；不能因此抹掉真实 160 次大读取超时。
- UI 原扫描把只读 `POST /entities/batch/query` 按方法误判成业务写入。独立 [严格只读审查 v2](../../../output/win7-complex-20261010/native-app-ui-scan-strict-ro-audit-v2.json) 核对真实源码契约及唯一 request_id，纠正工具判断，原报告 false 保留。唯一 bootstrap 导航取消仍单列，不改成 200，也不把该问题写成产品业务写入 bug。

## 最终源码修复及等价验证

最终修复涉及 **8 个生产文件、2 个新增测试文件**，已作为4f源码提交、冻结并实测。沿既有 read-only snapshot/evidence 作用域复用同一 adoption audit 的**完整已验证证明**；数量投影消费同一次已经验证的 `GenerationFacts`，不再次完整恢复相同候选归档。同一计划的 ledger task mapping 只加载一次，两个私有字段仍保留独立 plain 副本；日期转换使用现有本地解析器，保留 fold、subclass、微秒及异常规则；精确 `str/bool/int/None` 类型只做原值快返回，float、date/blob/container/set/tuple、subclass 和不支持类型沿用原规则。

旧 baseline 与当前采用计划仍独立核验，不能将相同工序集合或同一次请求误当同一 plan_ref 的证明。schema、完整候选 manifest、准入/采用 receipt、既有 canonical 类型比较、64 MiB 归档限制、point witness、安排完整范围和永久引用证明全部保留；既有算法、token 与指纹规则不改。没有增加全局或持久缓存、后台刷新或跨读快照的陈旧证据复用。

当前定向验证分别记录，不累加为无重叠总数：

- 来源复用专项 **新增 9 项、既有 6 项通过**，覆盖同一 proof 的复用及不同 baseline/ref 的独立核验。
- CPU 等价专项最终 **112节点通过=22业务语义+72存储类型oracle+18 metadata**；原94只是中间阶段。覆盖部分数量、当前/比较计划分开、坏匹配引用、重复工序/DTO、canonical int/float/bool/string 区别、与原归档不一致时的拒绝、日期/时区/fold、blob、非有限浮点、不支持类型及自定义元类的原行为。成功canonical文本与原TypeError文本一致。
- 既有 ledger/candidate/adoption/calendar 相关 **14 项通过**。此前测试夹具失败日志保留，没有修改产品保护来让测试通过。
- 首批7模块及最终primitive的独立审查已完成，无剩余阻断；集合包含判断会触发自定义元类hash/eq的问题已改为严格类型身份判断。[最终两接口语义回读](../../../output/pressure-cpu-profile-20261010/stable-comparison-v3-metaclass.json) 保留原业务值、键、类型及字节大小，单次回读不提供新的性能增益结论。

来源：[来源复用测试](../../../tests/workbench/test_adoption_source_read_reuse.py)、[CPU 等价测试](../../../tests/workbench/test_read_projection_cpu_equivalence.py)、[CPU专项阶段日志](../../../output/pressure-cpu-profile-20261010/primitive-equivalence-tests.log)、[既有14项日志](../../../output/pressure-cpu-profile-20261010/related-tests.log)。最终112 CPU与9来源节点已在[4f完整526节点结果](../../../output/win7-complex-20261010/quality-gate-cpu-4f850c75-526-raw/current_full_test_debt.json) 实际执行，各setup/call/teardown普通passed；17steps、526nodes、1578reports无skip/xfail/error/new debt，所有receipt实际执行、无cache/resume。Win7独立源码另实测132=旧11+9+112，5个原始XML与2130源码CRC证明已归档；源码夹具与原生冻结HTTP分别核销，不互相替代。

### 宿主 before/after 严格回放

优化前 clean `9d4faa56` 源码与优化后源码分别在独立进程、每版新的样例库副本上通过真实生产 factory/路由顺序回放。首轮 **4 routes × 3 次 × before/after = 24 个完整响应文件**均严格业务等价；只归一化生成的 `as_of/expires_at/request_ref/snapshot_ref/write_token` 值，同时保留字段存在性与原值类型，其余键/结构、标量类型、数组长度/顺序与业务 canonical 内容都相同。对应状态、`no-store` 和 wire 字节长度也一致。不能写成带动态生成值的原始 body 每字节相同。

primitive 追加改动后，analysis 和 merged 各再次读取 3 次，新增 6 份完整响应；与保留的 before 响应严格比较通过。`stable-comparison-v2.json` 单独保存，没有覆盖首轮比较和原完整响应；formal 没有第二版重跑证据。

| 路由 / 所属比较证据 | CPU median before → after（s） | 降幅 | 保留的输出合同 |
| --- | --- | --- | --- |
| formal-full / v1 | 8.265625 → 5.046875 | 38.94% | 原有完整范围 413 容量拒绝不变，wire 326 B |
| formal-scope-00，3003 tasks / v1 | 8.343750 → 5.218750 | 37.45% | 200，wire 7,799,551 B，完整本段范围 |
| full-global-analysis，5000 tasks / v2 | 5.015625 → 4.390625 | 12.46%（约 12.5%） | 200，wire 7,609,575 B |
| dashboard-merged / v2 | 5.796875 → 5.000000 | 13.75%（约 13.7%） | 200，wire 8,489,055 B |

这是合并源码改动的宿主串行诊断，不能归因于某一个快返回或单个模块。宿主样例有 **两版**已采用计划，需要保留两个来源独立证明；原生大型样例只有 **一版**正式采用。单次scope、数据历史和机器环境不同，不能把宿主37.45%外推为native并发收益。v2相对v1增量analysis0.71%、merged2.44%有运行噪声；本问题关闭依据是下面真实原生同参数复压，不能仅凭这些宿主数值核销160次timeout。

来源：[首轮严格比较](../../../output/pressure-cpu-profile-20261010/stable-comparison.json)、[追加 v2 比较](../../../output/pressure-cpu-profile-20261010/stable-comparison-v2.json)、[比较规则](../../../output/pressure-cpu-profile-20261010/compare_benchmark.py)、[完整诊断及修复进展](../../../output/pressure-cpu-profile-20261010/REPORT.md)。同目录 `stable-before/`、`stable-after/`、`stable-after-v2/` 的原响应、summary 和 profile 保留。

本问题不引入新的全局或持久缓存框架、后台刷新器、请求重试策略；不提高 60 s 请求预算、8 MiB 响应预算或其它既有容量限制。不能通过删除失败请求、降低原测量负载或改变 failure 统计制造通过。

第一轮压力后，原 v2 的低并发只读复核已恢复正常：16 个 HTTP 读取和导出步骤通过，5000 工序/6 报工保持、完整 CSV/XLSX 内容复核；[后置报告](../../../output/win7-complex-20261010/native-postpressure-http.json) 最大单次读取 7.248 s。该结果支持数据保持及空闲时可读，不改变第一轮压力 failed，也不是源码 CPU 修复后的原生重压通过。

## 修复后真实原生同参数复压：通过

原生v3固定run **`20261010T005347844-2572`**，source4f、Win7 SP1 x64、4 logical processors/约8GiB；实际backend **3088**，launcher1916，真实HTTP client **4300** 经自报PID和父链一次核对。仅在相同原生样例100批次/5000工序/6条partial报工上发只读loopback GET，600s停止新请求、16并发、60s socket操作timeout、无重试，未提高响应或归档预算。

| 指标 | v3真实结果 |
| --- | --- |
| 总耗时 / 600s后在途drain | 653.613s / 53.613s |
| 请求 / 普通通过 | 279 / 279，全HTTP200 |
| failed / timeout / non_200 / invalid_content | 0 / 0 / 0 / 0 |
| health / machine-directory / full-global-analysis / formal-scope-00 | 45 / 43 / 95 / 96，全部访问 |
| 实际最大并发 / 完成worker | 16 / 16 |
| 最后发起 / 最后结束 | 596.642s / 653.363s |
| 最大HTTP wall耗时 / 对60s余量 | 58.266s / 1.734s |

279条原JSONL、16个worker序列与预定调度、真实I/O区间、内容validator和234条业务响应no-store由独立审查核对；没有600s后继续发请求、失败删除、重试或用镜像覆盖原请求。综合 **16项checks全部true**，[真实最终结果](../../../output/win7-complex-20261010/exchange/native-pressure/20261010T005347844-2572/http/result.json)、[综合独立审查](../../../output/win7-complex-20261010/native-pressure-v3-complete-readonly-audit.json)、[原请求独立审查v2](../../../output/win7-complex-20261010/exchange/native-pressure/20261010T005347844-2572/raw-audit-native_matrix_sources-v2.json)、[进程独立审查](../../../output/win7-complex-20261010/native-pressure-v3-process-readonly-audit.json) 分别保留。

v3共有37个backend WMI观测，weighted约25.010%整机/1.0004单核量级，working-set峰值272,089,088B，可用内存最低5,808,340KiB；实际client采样从核对后开始，首行缺失不回填，冷WMI格式化延迟与CPU原capture时间分开。该结果没有内存耗尽或崩溃，37个观测不证明任意长期负载无泄漏。最大请求距60s仅1.734s，结论限于此实测规模、环境及并发，不泛化到任意慢机或更高负载。

原v2的160次超时、PS2 prelaunch失败及WMI身份纠正仍保留。v3第一次独立raw auditor又产生48条方法误报：47条不同计时范围offset差及1条用四舍五入端点重建I/O峰值；原失败审查不改写，后续v2审查按真实原capture区间核销。它们不是失败HTTP请求，实际client原failure始终0。

## 复压后数据、导出、界面与样例启停：通过

[压后真实GET/导出](../../../output/win7-complex-20261010/native-v3-readonly/postpressure-http-export.json) 共16次、全部200/no-store，14份原JSON和2份原文件保存；7组业务检查passed，独立[16项压后审查](../../../output/win7-complex-20261010/native-pressure-v3-post-readonly-audit.json) 全部true。与本v3压前基线相比，5000唯一task的业务值/四个采用数量字段、全部执行事实、6条partial报工及342-node完整source chain一致；原scope/snapshot重开，CSV/XLSX各5000×32=160,000格原列内容核对，通过且无重复/遗漏。独立审查另逐格比较两个文件及五个核心字段；不能声称重新解析不存在的279份原HTTP body。桥接最大5.199520s（含base64准备），该串行复查不是再次并发测试。

实际Chrome109页面16入口/15视图/33截图，独立[96项v3 UI审查](../../../output/win7-complex-20261010/native-app-ui-v3-independent-audit-v2.json) 全passed；原strict仅把draft_ref与关联scenario_ref混淆的false保留。压力期间既有值班台局部操作842.9ms完成，新增request/API/WebSocket均0，未重新导航、刷新或发业务请求；不能借此宣称所有页面在压力下可重新加载。[压力中局部探针](../../../output/win7-complex-20261010/exchange/app-ui-results/native-app-ui-local-v3-20261010T010035564-4264/result.json) 和[压后新鲜可见截图](../../../output/win7-complex-20261010/environment/v3-postpressure-ui-fresh.png) 分开保存；后者中文、正式v1、100待排及真实未知/来源缺口提示可读，没有空白或加载占位。

SampleOff固定run `20261010T011208682-2580` 正常退出样例、回正式PID2516，4.736s；[正式控制实体复核](../../../output/win7-complex-20261010/native-v3-readonly/sentinel-off.json) 12GET全200，synthetic详情一致（新生成write_context单独排除）、正式仅1个material且batch/run/history/scenario均0。SampleOn固定复用run `20261010T011401854-2708` 7.171s重开已有样例PID1556，16 GET回读一致、原acceptance报告字节完全相同、无新注入；[复用结果](../../../output/win7-complex-20261010/native-v3-readonly/sample-on-reuse.json) 核对5000/6/342及数量、目录、历史引用保持，只允许资料汇总calendar.as_of时钟变化。不把所有新HTTP正文都描述为原始字节相同。此项关闭样例切换的数据保持验证，不替代最终用户目录安装。

最终docfix普通安装实际run `20261010T011909098-3312` 已149文件/首次无user-data/defaultoff/exit0；证据版本4、实际release-v3-docfix/compiled4f/docs404dc。另[最终普通冷启动及相对目录停止](../../../output/win7-complex-20261010/exchange/native-docfix-cold-dot-20261010T012504835-2968.json) 总8.368s、Start2.624s，新backend2936创建晚于CMD，系统PATH；真实START /WAIT执行`--runtime-stop . --stop-aps-chrome`并捕获ERRORLEVEL0、原PID退出/rootbackend0/5957free/marker保持，无kill/retry。这不等于强退役所有临时Python后已验证。

最终强退役固定run `20261010T012833250-1832` 已passed：四个owned临时目录buildenv/python38/test-tools/test-tools-v3移到可恢复retiredRoot，普通Start1.451s/系统PATH/新backend2784/5957、标准stop0。新鲜独立[退出后WMI](../../../output/win7-complex-20261010/exchange/native-final-state-20261010T013527843-4548.json)仅采集helper4548，完成helper1832 absent、owned APS/Chrome/Python0、sample formalOff；四条temporary_task_python_directory的实际字段 **directory_exists=false**，与原Move后源absent/目标present断言一致。固定[强退役证据](../../../output/win7-complex-20261010/exchange/native-retire-python-20261010T012833250-1832.json)及[独立28checks审查](../../../output/win7-complex-20261010/build-prep/final-retire-readonly-audit-20261010T014022510-73652.json)均通过，范围限本任务四目录及最终程序，不宣称全机所有Python被删除。

VM恢复固定run `20261010T013707772-57380` 已真实完成：仅移除本任务共享、九键恢复原值、两个原快照及VMSD原字节不变、soft suspended、旧应用/业务不改。首Apply因helper错误只接受running而实机返回on，在任何mutation前拒绝；原failed保留，最小on兼容修正后29offlinechecks通过，再执行真实恢复。来源：[成功state](../../../output/win7-complex-20261010/build-prep/host-restoration-evidence/20261010T013707772-57380/state.json)。

桌面交付已完成，程序内容和两ZIP完整回读通过；main整合/推送及版本核对以root实际执行的[Git同步收据](../../../output/win7-complex-20261010/final-git-sync.json)为准。新安装目录标签Version4只表示再次部署，编译源码仍4f；148个非README文件不变，不能把它记作native v4重编译。本问题关闭依据为真实同参数复压，全部交付范围及限制另见原生审计。
