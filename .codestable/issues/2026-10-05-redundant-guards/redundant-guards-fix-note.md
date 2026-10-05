---
doc_type: issue-fix-note
issue: 2026-10-05-redundant-guards
created: 2026-10-05
status: fixed
verification: targeted-passed-with-existing-gate-debt
scope: 全项目冗余保护和重复动作的已确认根因
---

# 冗余保护与重复动作修复记录

## 结果与授权

用户在全面引用链复核后授权“留档，然后该修的修，修的过程中注意是否确实冗余”。实施前先保存 [72 组审计及处置](../../audits/2026-10-05-redundant-guards/index.md)，再修复真实入口上的同事实重复处理和业务误拦。初始可行动不是自动删除保护的依据；实施中继续检查消费者、事务、输入变化及公开契约。

开始时 main 工作区干净。本轮没有 commit、push、发布、生产库写入、样例生成或真实重新排产。新增源模型只保存服务器持有的文件解析事实，没有新增摘要字段、证明清单或跨请求数据库事实缓存。兼容 Python 3.8；开发与测试运行于项目 Python 3.8.10。

## 已完成的源头修复

| 范围 | 最终实现及真实收益 | 保留的职责 |
|---|---|---|
| 试调、run 档案 | 看板四表从新试调事实排除；新 run 不读取和递归复制 trial/dashboard/log 非输入内容。旧档案在比较时投影同一输入范围，不改历史字节或摘要。 | 完整 schema、未知扩展、业务事实、正式历史、容量限制、真实业务变化拒绝。 |
| 候选准备、准入、比较 | 连续组合计算省去无人消费的 fullhash；一次准入预检同时提供校验及 freshness；comparison 的 GenerationFacts/AdmissionBaseline 各一次；分件固定事实仅同 query_only snapshot 共用。 | 独立 prepared 捕获并重核；每个候选的 payload/可行性；正式采用的当前事实重核。 |
| 试调编码及比较 | 一次 lossless 编码供容量和已有 digest；两边 hash 比较局部改为同规范内容比较。 | True/1、1/1.0、-0.0/0.0、BLOB 等原类型语义；写后权威 head/revision 回读。 |
| 维护、恢复、现场台账 | 静态请求轻量核宿主状态，health 两层共用当次状态；journal 一次有容量约束的 validated capture 供 pending/ready/集合；真实 cohort 复用同次 schema/clock/facts。 | 停止或归属不确定时拒绝准入、业务入口检查、日志坏值诊断、下一快照新鲜读取。 |
| 执行持久化、配置、计划、报表 | 每个最终 guard 内 snapshot/revisions 共用当前事实；配置同一时点 raw/normalized 一次读取；最新版本标量查询、报表传已有 resolution、catalog 共用 history/roles。 | 版本分配前及落库前两个独立 guard 时点；写前/写后不同事实；非法配置报错优先级。 |
| 物料、外协看板、工艺、指标 | 物料 DTO 带完整 m.* 状态；summary/handling 共用来源；workflow 从已捕获 raw 表投影；人员资格共用原解释入口，固定人机按 distinct pair 查授权。 | 未知列、坏值及身份漂移诊断、逐工序工种资格、最终写 stale/replay。 |
| 日历、定额及业务写入 | 内部 checked 写入口消费同命令 guard 事实；主操更新和覆盖导入排除当前目标，最终只写一次；外协组写最终成员，周期改变不重绑；拆分数量/最终状态合写；配置只写实际变动键。 | 公开独立入口检查、其他主操清理、组迁移约束、父批 revision、review 重置、审计与事务回滚。 |
| 六类普通文件导入 | material/resource/process/calendar/operator-calendar/relation 预检保留 PreparedImportSource；预检加确认解析及原摘要各一次。 | 确认重新读 DB、完整 proposal 比较、format/mode/operation/scope/target_ref 绑定、raw bytes 独立调用。 |
| 报工文件导入 | 文件 SHA 五次收为两次；确认传入同份 digest；write stamp 未变时不再第二次准备完整模拟。 | stamp 变则重算、同连接限制、replay 先行；提交时产生正式 48hex ref、当前 actor/时间和稳定 BG-X 编号。 |
| 排产优化器 | 重复 ID 检查线性化；同候选 decision/output digest 显式传递，免重复 seen set 复制。 | parent/seen 上下文各自重判；可行性、严格改善、去重和未验证 checkpoint 边界；无全部历史候选缓存。 |
| 前端及静态构建 | 保存后一次列表刷新、日历汇总共用、candidate_ref 决定分析读取；共同 API 响应边界；Babel 编译、分析、复制及来源记录使用同份已验证 bytes；相同 vendor/payload 免写。 | 注入 API 严格检查、UI 特有归属、跨 tab 偏好写后读回、live 输入变化检查、原子发布和 marker 最后写入。 |
| 宿主门禁、离线交付 | long-gate 同判定阶段共享文件/metadata，命令后新鲜捕获；同次架构 raw scan/AST 共用；impact 去除 focused 交集；同 HEAD 有据缓存结果免重复 replay；download 首次材料一次验证、dist launcher 来源统一、原绝对路径检查修正。 | 环境/输入/receipt/log/output 不匹配照常执行；STRUCTURAL_ONLY 非通过；NetworkX 三种职责、7za t+x、既有追溯摘要。 |

实施再次确认保留项：3.2/3.3/3.4 启动合同及具名索引、1.2/1.3/1.4/6.1 现存令牌作用域、5.3 父批修改语义、7.3 资源热更新、7.6 偏好同步、9.2/9.3 离线材料检查、10.1–10.8 的有实际消费者或兼容职责。旧事件写服务、模板批次 probe、RouteParser 没有被当作当前生产热路径扩改。逐组判断在审计索引的最终处置列。

## 实施复核

- 新旧试调均在看板处置后可采用；设备事实改变仍拒绝。旧档案原文与 digest 保持。
- 每个持久化 guard 的事实只读一次，但中间版本分配和摘要阶段可改变事实，所以两时点检查都保留。
- 导入解析缓存只保存源文件事实；诊断用深拷贝，每次确认重建当前 DB proposal。服务端 source 被替换、DB 隐藏字段变化、同编号重建、过期令牌仍原子拒绝。
- 报工模拟初版曾使用不符合公开形状的 preview 临时 ID，复核后恢复原 48hex 预览形状；正式写入仍重新分配永久 ID 和提交时间。
- 独立交叉只读检查优化器生成→评估→接受→报告链，未找到同候选摘要传递漏 parent/seen 判断或新增无界候选持有。导入交叉检查发现 material 留存类型仍写 bytes，已同步类型和说明。
- 留档阶段发现 selftest 预先决定整计划的缓存复用可能在前置命令执行后失效，已改成按实际使用的步骤惰性裁定，执行后清空当前 phase；真实输入/proof 改变回归通过。
- 本轮新增函数触发的复杂度已按职责拆分，没有新增豁免。启动异常 handler 真迁移及测试样本行只更新实际定位，没有改变日志、失败状态或退出码。

## 实际验证

下表按批次记录，存在交集，不相加冒充独立测试总量。前序通过只代表对应代码状态；后续行为变化有相应最新定点补验。

| 范围 | 实际结果 |
|---|---|
| run/trial、候选读取/analysis/档案/采用、分件、准入 | 当前两批 126 passed、262 passed；Ruff、范围 diff check 通过。 |
| 外协看板和外协登记 | 222 passed，含真实 SQLite trace 单次 header/latest/source 和目标标签读取。 |
| scheduler/config/report/optimizer | 163、101、6、154 passed；新增配置/授权/指纹契约所在批次 105 个成功用例，新 guard 错误次数断言已纠正并补验。 |
| material/resource/process/calendar/config 主域 | 前序 509、194 passed；最新资格/配置/主操/外协组 126 passed，覆盖导入 25 passed。 |
| execution、identity、restore | 前序 166、236、83 passed（有交集）；复杂度整理后 159 passed；公开预览/正式引用补验 2 passed。13 产品文件 scoped Pyright 0 errors。 |
| 主代理 HTTP 接线 | 228 passed、3 个内部 bytes 假设失败；适配为 source 保留和内容替换拒绝后，相关 19 passed。另 6 个真实 HTTP/读取次数/journal pending 用例全部通过。 |
| 主代理静态检查 | 14 产品文件 scoped Pyright 0 errors / 0 warnings；相关 Ruff、全 diff check 通过。第一次 daily 6 个 import 排序失败已修，后续进入全 Ruff 与 impact pytest。 |
| 前端/构建与浏览器 | 资产 23 passed；Chrome109 Plan 51、Actual 19、Candidate 241 checks（4 variants / 24 downloads）；资源保存 3 场景；opt-in 资产 9 passed。JSON 原证据已留档，errors/external 均为 0。 |
| 门禁工具与离线脚本 | 最后阶段失效/receipt 绑定等 3 passed，现有 selftest 元数据 22 passed；工具 Pyright 0 errors / 0 warnings，Inno 共用脚本 29 routines passed；此前相关批次各自保留，不累计。 |
| 统一 daily | 全仓 Ruff 通过；parallel impact 11836 passed / 34 failed / 1 skipped；补齐 serial 975 passed / 7 failed，focused 初次 6 passed / 1 failed。失败分流、修复与定点复验完成；最终 focused 7 passed，架构/边界复核 32 passed / 3 failed，剩余均为下面确认的 HEAD 既有治理项。整体门禁未通过。 |

原始统一门禁输出保存在 `evidence/2026-10-05-redundant-guards/`；第一次 Ruff 失败为 `daily-first-ruff.log`。统一架构检查已确认 HEAD 原有 entrypoint 问题：`_serve_created_app` 复杂度 17、监听失败的第二个可观察异常分支未登记，；另外 `_preferred_listen_port` 的旧符号登记已按相同 handler 实际迁移。该文件本轮未改；不新增豁免掩盖它们。最终影响按 daily 实际失败交付。

## 最终失败收束

| 剩余检查 | 实际证据与处置 |
|---|---|
| private import ratchet | `web/bootstrap/runtime_server.py:13` 从 launcher_network 导入 `_candidate_ports`，当前文件逐字等于 HEAD，基线无登记。本轮新定额跨模块入口已改为有共享职责的公开名字。 |
| exception ledger | `web/bootstrap/entrypoint.py:300` 监听失败分支已记录错误并 return 16，第二个 observable_degrade handler 缺少登记；原代码逐字等于 HEAD，未增加豁免。 |
| complexity threshold | `web/bootstrap/entrypoint.py:270` `_serve_created_app` 在 HEAD 实测 17，高于 15；本轮新增复杂度及超长 service 已按职责拆分。 |

这三项属于现存启动结构/登记治理，未发现需要按冗余保护删除的依据；本轮保留原失败处理和接口范围。没有把它们记为通过，也没有重刷基线消除告警。最终失败原文见 `evidence/2026-10-05-redundant-guards/architecture-final.log`。

最后 source/fixture 收束的有效定点补验：物料表格/列筛选/导出 79 passed，规模夹具签名更新后 1 passed；报告窗口 6 passed；piece admission 1 passed；CSS 4 passed；浏览器环境 34 passed；多轮 repair 17 passed；定额共享入口 35 passed；主操归一化 25 passed；真实 fixture 路径与 dead-path 11 passed。既有已通过结果按相关代码状态复用，没有再重跑整个 11836 用例。

日志复用接线的最后复核发现容量检查必须在 JSON 解析前，因此统一 bounded capture：2001 个真实临时 malformed JSON 文件在零解析前拒绝 413；系统维护 API 37 passed、接线后备份创建/删除/重放 1 passed，最后 6 个 HTTP/journal 接线用例全部通过。全仓 Ruff 及新增接线/归一化 scoped Pyright 均通过。

## 文档与交付边界

同步 `service-scheduler.md` 的组合计算/独立 prepared 新鲜度职责及开发 README 的 gate 复用合同；保存初始裁决和最终处置，不改写历史验收归属。没有运行真实 Windows 7 安装、真实库迁移、目标机交付或完整最终 clean gate。保留当前未提交工作区供审阅。


第一次 impact 失败根因分流：物料表格 caller 与测试 helper 签名 11 项；报告新 resolution 参数 6 项；piece admission 测试替身 1 项；CSS builder 测试替身 4 项；Node/Chrome 环境 11 项；private import 检查 1 项（本轮定额共享入口已改公开名，HEAD 既有 runtime_server 私有导入单独保留）。后续只复验这些变化及门禁未执行的 serial/focused 阶段，复用已有效的通过结果。


最终工作区有 226 条本轮变更（包含生成的 static 与 5 个新源/测试文件），无 staged 内容，未提交。审计、issue 和原始 evidence 已实际写入现行目录；其中被现有忽略规则覆盖的本地留档未改变忽略规则。
