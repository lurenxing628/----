---
doc_type: issue
date: 2026-10-10
status: in-progress
---

# Win7 大计划读取在 16 并发下超过 60 秒

## 问题与影响

Win7 SP1 x64 原生冻结程序在真实 100 批次、5000 工序、6 条分次报工样例上进行第一轮重度读取压力测试，完整全局分析和正式计划 workspace 大量超时。轻量健康检查和设备目录仍正常，说明不能用健康正常、单次读取或先前界面通过来核销并发大计划读取能力。第一轮压力结果为 **failed**，原失败、每次请求、进程采样和工具错误全部保留。

冻结源码是 `a4a6ad24452675305196c8889f18482c025447ad`；当时宿主 `9d4faa56743f9f9ab4af3e3740fcf14ea5bd198a` 仅改变债务台账行号/验证时间，运行内容相同。现有 clean 17 步/405 节点门禁属于这份修复前运行内容，不能覆盖正在修改的读取 CPU 路径。当前源码修复、原生 v3 重建、修后完整门禁及交付均未核销。

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

## 修复进展：源码稳定，原生复压仍待核销

当前修复源码涉及 **8 个生产文件、2 个新增测试文件**，已进入提交前稳定检查。沿既有 read-only snapshot/evidence 作用域复用同一 adoption audit 的**完整已验证证明**；数量投影消费同一次已经验证的 `GenerationFacts`，不再次完整恢复相同候选归档。同一计划的 ledger task mapping 只加载一次，两个私有字段仍保留独立 plain 副本；日期转换使用现有本地解析器，保留 fold、subclass、微秒及异常规则；精确 `str/bool/int/None` 类型只做原值快返回，float、date/blob/container/set/tuple、subclass 和不支持类型沿用原规则。

旧 baseline 与当前采用计划仍独立核验，不能将相同工序集合或同一次请求误当同一 plan_ref 的证明。schema、完整候选 manifest、准入/采用 receipt、既有 canonical 类型比较、64 MiB 归档限制、point witness、安排完整范围和永久引用证明全部保留；既有算法、token 与指纹规则不改。没有增加全局或持久缓存、后台刷新或跨读快照的陈旧证据复用。

当前定向验证分别记录，不累加为无重叠总数：

- 来源复用专项 **新增 9 项、既有 6 项通过**，覆盖同一 proof 的复用及不同 baseline/ref 的独立核验。
- CPU 等价专项 **94 节点通过**：原 22 个有业务意义的回归，加 72 个与优化前实现比较的存储类型 oracle。覆盖部分数量、当前/比较计划分开、坏匹配引用、重复工序/DTO、canonical int/float/bool/string 区别、与原归档不一致时的拒绝、日期/时区/fold、blob、非有限浮点和不支持类型的原异常。成功 canonical 文本与原 TypeError 文本一致。
- 既有 ledger/candidate/adoption/calendar 相关 **14 项通过**。此前测试夹具失败日志保留，没有修改产品保护来让测试通过。
- 首批 7 个生产模块的独立审查未发现阻断项；追加 primitive 快返回部分仍在补充独立审查，不能将首轮审查扩写成全部最终改动审查完成。

来源：[来源复用测试](../../../tests/workbench/test_adoption_source_read_reuse.py)、[CPU 等价测试](../../../tests/workbench/test_read_projection_cpu_equivalence.py)、[112 项执行日志](../../../output/pressure-cpu-profile-20261010/primitive-equivalence-tests.log)、[既有 14 项执行日志](../../../output/pressure-cpu-profile-20261010/related-tests.log)。这些是宿主定向验证，不代替修后完整 clean 门禁或原生 EXE 复压。

### 宿主 before/after 严格回放

优化前 clean `9d4faa56` 源码与优化后源码分别在独立进程、每版新的样例库副本上通过真实生产 factory/路由顺序回放。首轮 **4 routes × 3 次 × before/after = 24 个完整响应文件**均严格业务等价；只归一化生成的 `as_of/expires_at/request_ref/snapshot_ref/write_token` 值，同时保留字段存在性与原值类型，其余键/结构、标量类型、数组长度/顺序与业务 canonical 内容都相同。对应状态、`no-store` 和 wire 字节长度也一致。不能写成带动态生成值的原始 body 每字节相同。

primitive 追加改动后，analysis 和 merged 各再次读取 3 次，新增 6 份完整响应；与保留的 before 响应严格比较通过。`stable-comparison-v2.json` 单独保存，没有覆盖首轮比较和原完整响应；formal 没有第二版重跑证据。

| 路由 / 所属比较证据 | CPU median before → after（s） | 降幅 | 保留的输出合同 |
| --- | --- | --- | --- |
| formal-full / v1 | 8.265625 → 5.046875 | 38.94% | 原有完整范围 413 容量拒绝不变，wire 326 B |
| formal-scope-00，3003 tasks / v1 | 8.343750 → 5.218750 | 37.45% | 200，wire 7,799,551 B，完整本段范围 |
| full-global-analysis，5000 tasks / v2 | 5.015625 → 4.390625 | 12.46%（约 12.5%） | 200，wire 7,609,575 B |
| dashboard-merged / v2 | 5.796875 → 5.000000 | 13.75%（约 13.7%） | 200，wire 8,489,055 B |

这是合并源码改动的宿主串行诊断，不能归因于某一个快返回或单个模块。宿主样例有 **两版**已采用计划，需要保留两个来源独立证明；原生大型样例只有 **一版**正式采用。单次 scope、数据历史和机器环境不同，不能把宿主 37.45% 外推为 native 并发收益。v2 相对 v1 的增量只有 analysis 0.71%、merged 2.44%，有运行噪声；也不能据此宣称第一轮 160 次 timeout 已解决。

来源：[首轮严格比较](../../../output/pressure-cpu-profile-20261010/stable-comparison.json)、[追加 v2 比较](../../../output/pressure-cpu-profile-20261010/stable-comparison-v2.json)、[比较规则](../../../output/pressure-cpu-profile-20261010/compare_benchmark.py)、[完整诊断及修复进展](../../../output/pressure-cpu-profile-20261010/REPORT.md)。同目录 `stable-before/`、`stable-after/`、`stable-after-v2/` 的原响应、summary 和 profile 保留。

本问题不引入新的全局或持久缓存框架、后台刷新器、请求重试策略；不提高 60 s 请求预算、8 MiB 响应预算或其它既有容量限制。不能通过删除失败请求、降低原测量负载或改变 failure 统计制造通过。

第一轮压力后，原 v2 的低并发只读复核已恢复正常：16 个 HTTP 读取和导出步骤通过，5000 工序/6 报工保持、完整 CSV/XLSX 内容复核；[后置报告](../../../output/win7-complex-20261010/native-postpressure-http.json) 最大单次读取 7.248 s。该结果支持数据保持及空闲时可读，不改变第一轮压力 failed，也不是源码 CPU 修复后的原生重压通过。

仍为 pending：修后 clean/no-cache/no-resume 全门禁、原生 v3 冻结/普通冷启动与同规模同预算 600 s/16 并发复压、复压后 5000 工序和 6 报工/导出/界面检查、样例开关恢复、临时构建 Python 隔离后启动、最终包及桌面交付、main 合并和推送。完成真实核销前保持 **in-progress**，不得引用定向等价回放、修复前的 17/405 或工具夹具通过作为最终版本压力通过。

最终追加审查发现集合包含判断会触发自定义元类的 hash/eq，已改成严格类型身份判断；112 项类型和业务回归通过，独立复核无剩余阻断。[最终两接口语义回读](../../../output/pressure-cpu-profile-20261010/stable-comparison-v3-metaclass.json) 保留原业务值、键、类型和字节大小；此单次回读不提供新的性能增益结论。
