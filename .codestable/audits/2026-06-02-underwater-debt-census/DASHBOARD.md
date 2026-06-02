# 全项目水下语义债普查 · 最终仪表盘

> 两遍普查全 12 分区覆盖完成。Pass-1(10 分区 agent 自由取证 + 对抗验证)+ Pass-2(补 core-models/core-algorithms 两失败分区 + 图嫌疑核验)。
> 配套:`CROSS-CHECK.md`(两遍交叉检验)、`.codestable/checkup/latest/callgraph/`(5874 函数级调用图)。
> 日期 2026-06-02。只读普查,未改任何代码。

## 一句话结论

**全项目 61 条水下语义债,P1(写死假冒计算值)= 0 活例。** 唯一已知出血(execution_review)已被治理。债的形状是"整理到一半的房间"(P3 半截迁移 17 + P6 死代码 23 占 65%),不是"垃圾场"。**真正的存量高危不是债多,是 8 处"看着像债、实为救命护栏"的承重不对称——它们零本地注释,未来 LLM 以统一名义最容易误删。** 离屎山很远,且是结构性远(0 分层违规 + 全可测绘 = 爆炸半径可预测)。

## 病理分布(全 12 分区合并)

| 类 | 处数 | 性质 | 治理基调 |
|---|---|---|---|
| **P1** 写死假冒计算值 | **0** | 已绝迹 | — |
| **P2** 承重不对称无注释 | 4 | 全 load_bearing | **补"别动我"注释(最高杠杆)** |
| **P3** 半截迁移残渣 | 17 | 新路径胜出旧路径未清 | 删空壳/收口到已存在统一点 |
| **P4** 静默兜底死角 | 6 | 多为不可达防御,真吞 1 处(backup) | 改 raise / 补可观测 |
| **P5** 第N套私有实现 | 11 | 部分已语义漂移 | 收口到已存在统一点 |
| **P6** 死面包屑 | 23 | 纯死代码/死字段/死参数 | grep 实证后直删 |
| 合计 | **61** | | |

## 各分区健康(12/12)

| 分区 | 健康 | 主病 |
|---|---|---|
| scheduler-run | 偏干净 | P6 死面包屑(拆分残渣) |
| scheduler-dispatch | 轻残渣 | P5 派工 scope 双轨(team 轴承重) |
| scheduler-gantt | 偏干净 | P6 死方法 1 + 在途重复 1 |
| scheduler-exec-diag | 地基扎实 | P2 写侧 adopted 护栏无注释 + P6 死字段 |
| scheduler-plan-identity | 非重灾 | P5 default_plan_resolution_dict 私实现无 parity 测试 |
| scheduler-config-summary-graph | 非重灾 | P3 SP05 半截包拆分尾巴 |
| core-infra-shared | 基本干净 | P5 boolean_normalize 双实现(分层承重) |
| core-svc-domain | 基本干净 | P2 execution_review 护栏无注释 |
| data-repos | 结构干净 | P6 死读方法群(plan-role 迁移残渣) |
| web-all | 非重灾 | P2 路由层 adopted 护栏 + P6 plan_id 死面包屑 |
| **core-models**(Pass-2 补) | **健康** | **P3 双配置栈锁步同步(潜伏分叉)** + legacy 错误串桥 |
| **core-algorithms**(Pass-2 补) | **健康偏好** | P3/P6 三次重构的"新胜旧未清"尾巴 |

## ⭐ 承重不对称清单【防屎山核心资产 · 别动我】

> 对抗验证确认 load_bearing。共性:刻意和兄弟不一致(故意的护栏),但理由散在远处(schema CHECK/分层/UI 文案/导航),改动点本地零注释。**最高性价比的防屎山动作 = 给这 8 处补"我是故意的"注释。**

**A 族:execution_review 只复盘"正式采用方案"(4 处纵深防御,守同一不变量)**
1. `web/routes/reports_page_support.py:366,368` + `navigation_context.py:80-82` — 路由层硬钉 adopted/None
2. `core/services/report/execution_review.py:141,153` — 服务签名结构性拒收 plan_role/scenario_id
3. `core/services/report/execution_review.py:141`(core-svc-domain 重报)— 同上,源表层最后把关
4. `operation_execution_feedback_service.py:451-453`(+347-354)— 写侧消毒层,即便上游被绕过也绝不落非 adopted 身份

→ 必补注释:`# 计划和现场实际故意只复盘正式采用方案,与 overdue/utilization/downtime 三兄弟参数不对称是刻意的护栏;勿为"统一四报表签名"加 plan_role/scenario_id——会让模拟预览/旧版本冒充正式复盘`

**B 族:各自独立的承重不对称**
5. `schedule_payload_contract.py:50` 等三套正整数强制器(raise/→0/→None)— 按"落库闸门/解析错误文本/装配响应"刻意分化,裸合并会把"跳过坏行"变"抛错中断整页"
6. `resource_dispatch_service.py:63` + `schedule_plan_query_repo.py:447-463`(team 分支)— 派工 team 轴是收口点表达不了的第三维,统一会丢 team 致班组视图 500 或静默返回全量
7. `core/shared/boolean_normalize.py:33` — 不是冗余副本:core.models/algorithms 在下层只能调它,删了改指 core.services 会撞 AST 分层红线。该补的是绑定两套等价的契约测试
8. `core/services/common/number_utils.py:23`(verdict=depends)— 是有意的 delegation-facade(2026-06-01 KEEP/high 裁定),非半截迁移;薄壳化须先重写 monkeypatch 测试

## Pass-2 新增的潜伏 P3(core-models,Pass-1 漏报)

- **双 ScheduleConfigSnapshot 栈**(`schedule_config_runtime_*` 5 文件 ≈ `config/config_snapshot.py` 逐字节)— 算法层不能 import 服务层 → 另起一套中性投影,靠人工锁步同步(git 证据:b82c9a4d/ef244b9e 同时改两份)。**当前 27 字段未漂移属潜伏**:任一栈加字段忘同步,算法看到旧默认值而用户在配置页存的是新值,且回落静默(踩灵魂线)。collapse 方向:service 栈反过来复用 model 栈(services→models 是合法边)。**收敛前必须先补 parity 测试。**
- **legacy 错误串往返桥**(`scheduler_public_errors.py:62-103,218-290`)— 老路径发渲染好的中文串,下游用正则反解回 code,与结构化 make_public_error 两代并存。改任一中文文案会静默使正则失配。

## 图嫌疑核验(消偏差的机械补充)

调用图机械标记的 2 处 core-models "preview→render 泄漏嫌疑",人工核验**全是假阳性**,且揭示了出血的反面:

- `schedule_plan_identity.py:172` `EvidenceLink.to_dict` — **主动防冒充岗哨**:序列化前先 `self.validate()`,强制证据链接 scenario_id 必须与 plan_identity 逐字相符,否则抛错。与 execution_review 出血**正好相反方向**。
- `schedule_plan_resolution.py:64` — 忠实序列化器,is_scenario_preview/is_superseded 真值由上游 `build_plan_identity` 真实比较推导,如实带出不写死。

→ **方法论收获**:同一数据流形状(身份字段→to_dict),一个是病(execution_review 贴现行标签)、一个是药(validate 后拒绝冒充)。纯语法工具分不清,必须人核验语义。已知出血对照锚点:`execution_review.py:199,225`(导出文件名/汇总行标签写死"正式采用方案")。

## 屎山距离体检

**离屎山很远,结构性远。** 三硬指标:
1. **0 分层违规 + 全可测绘** = 爆炸半径可预测(屎山的反面)。每条债 grep 到 file:line、git 考古到引入提交。
2. **P1 = 0 活例** = 最强健康信号。灵魂线"坏数据不静默兜底"在主链落实如范本(fail-fast + DegradationCollector + EvidenceLink.validate)。
3. **债形状 = 半截迁移**(P3+P6 占 65%),被 SP05/契约测试钉死不会偷烂。"整理到一半"≠"腐烂"。

**唯一通向屎山的路**:LLM 以"统一/一致性/消除方言"名义抹掉 8 处承重不对称。风险中高,本项目唯一存量高危路径。

**免疫(按性价比)**:
1. 给 8 处补本地"别动我"注释(把散在远处的理由钉回执行现场)——对 LLM 协作者唯一有效的本地阻止信号。
2. 补缺失的承重回归:`GET /reports/execution-review?plan_role=非adopted&scenario_id=X` 断言服务端仍 adopted 且导出不含预览(当前最大测试盲区);boolean_normalize 两套等价契约;双配置栈 parity。
3. 把"承重不对称"登记进 SP05 式契约清单,任何抹平改动直接撞红线。

## 置信度标注

**充分(可直接行动)**:P1=0、第一档死代码 grep 实证、8 处承重护栏代码实证、图×agent 12 文件双重命中互证。
**需补证**:default_plan_resolution_dict 键集"今日 0 漂移"(无 parity 测试)、双配置栈"27 字段未漂移"(同理)、config/summary shim 是否有仓库外脚本消费(Win7 离线只能证树内)、`_normalize_critical_chain_result` 是 P5 真债还是在途中间态(git status 标 A 未提交,落手前问作者)。
**需 owner 裁断**:`_positive_int` 可空簇该收到哪(唯一"该收却无现成统一点"的债)、ready_queue 全量版是差分测试基准还是遗忘残渣、9 个 wrapper(roadmap 明示延期=暂不动)。
