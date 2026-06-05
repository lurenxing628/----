# 交接提示词 · 80 条水下语义债「修复前依赖分析与安全批次计划」(只出计划,不改代码)

> 把本文件整篇作为提示词交给下一个 Agent。

---

## 〇、你的任务(一句话)

在**当前工作区**上,产出一份**颗粒度到每一条债、可直接照着执行**的修复计划:理清 80 条水下语义债之间的相互勾连、爆炸半径、安全修复顺序、每批的前置安全网与门禁,确保将来有人照此修复时**不会连环炸**。

**铁律:本轮只读生产代码、只产出计划文档,绝不修改任何 `.py` 实现。** 交付物是 `.md`/`.json` 计划,不是任何代码 diff。用 **workflow(工作流)** 分相推进,颗粒度要细,**质量优先、不限时**。

---

## 一、最硬的四条红线(违反即整份作废)

1. **只读不改**:`core/ web/ data/` 下任何 `.py` 一律只读。你交付的是计划,不是改动。
2. **不准从零重造**:本项目已有一份做得很深的 fix-plan(见 §三)。你的活是 **继承 + 在当前代码上验证 + 加深 + 针对漂移重新校准**,不是重新发明轮子。凡你的判断与已有分析冲突,要么用当前代码证据明确推翻并说明理由,要么继承它——不许默默另起一套。
3. **承重护栏神圣**:11 条 `load_bearing` 护栏(见 §五)在计划里**只能**安排"补『我是故意的』注释 + 绑契约/parity 测试",**绝不能**出现删除/统一/合并/透传它们的步骤。
4. **不替 owner 拍板**:19 条须人裁断项(见 §六)在计划里标注"待 owner 裁断,暂不分配执行批次/暂不给终态修法",不得自作主张。

---

## 二、为什么这一步至关重要(背景)

这 80 条债**不是孤立的**:已机械算出 **146 条干扰边**,其中 **133 条是"同文件"**(两债落在同一物理文件,改一处会顶掉另一处的行号/逻辑)、**13 条是"同收口点"**(收口到同一符号,顺序敏感)。它们聚成一个 **67 债的巨型连通块 C01**(几乎含全部 LB + 绝大多数 R 债)。**盲目逐条修 = 连环炸**。最危险的炸法不是"改错了",而是**把看着像重复、实为承重护栏的不对称"以统一名义"抹掉——删了不报错、测试照样绿,直到坏数据流到不该去的地方**。所以必须先有这份依赖/爆炸半径/安全排序计划。

---

## 三、已有产物(开工前必须全部读完,这是你的地基)

**fix-plan 主干**(`/Users/lurenxing/Documents/GitHub/----/.codestable/audits/2026-06-02-underwater-debt-census/fix-plan/`):
- `MASTER-PLAN.md` — 16 批有序修复总计划、依赖 DAG、5 红线、7 退出自检、verdict=可发布。
- `phase1/PHASE1-MATRIX.md` + `phase1/_matrix_raw.json`(键:`ordering_dag`/`contradictions`/`cross_debt_edges`/`load_bearing_chapter`/`summary`)。
- `phase1/_phase1_blast.json` — 承重护栏逐条**爆炸半径**(9 字段:`co_change_within_group`/`contract_topology_tests`/`prod_consumers`/`test_consumers`/`downstream_effect`/`fix_invalidation_risk`/`lb_colocation_danger`/`location_status`/`planned_fix_class`)。
- `phase1/groups/` — 8 个爆炸半径分组。
- `phase2/_phase2_index.json` + `phase2/units/*.json` — 逐桶/逐债**修法**(B01a-LB-CORE / B02-IDENTITY / B05-INT-FLOAT / B07-RESOURCE …)。
- `phase0/_truth.json`(80 债真相 + 每条 `adv_precondition`)、`phase0/_all_debts_full.json`、`phase0/_bucket_packs.json`、`phase0/PHASE0-TRUTH.md`。
- `phase3/_audit_raw.json`、`phase3/_master_raw.json` — 对抗核查。

**干扰/家庭数据**(`/Users/lurenxing/Documents/GitHub/----/docs/_panorama_data/`):
- `debt_interference.json`(`meta`/`clusters`/`edges`[146]/`deb_primary_file`[80]/`deb_files`)。
- `debt_families.json`(`primary_collisions` 18 个碰撞文件)、`debt_buckets.json`(17 桶)。
- `debt_status_2026-06-05.json` — **逐条当前状态(6 已修/3 在途/70 待修/1 误标)+ 取证 evidence**(从当前工作区核出)。
- `structure_2026-06-05.json` — 当前结构指标(6107 函数/566 文件/0 分层违规)。

**审计正文**:`/Users/lurenxing/Documents/GitHub/----/.codestable/audits/2026-06-02-underwater-debt-census/report-sections/90-load-bearing.md`(承重护栏清单,防屎山核心)、`99-appendix.md`(附录 C 未决裁断 10 条)。

**继承要点**(已确认成立,直接用):16 批 DAG 无环;承重先落(Batch-1 全=注释+测试,零逻辑改动);facade 最后(晚于收敛);P5 收口到已存在点;唯一批准新建模块=**R09**(`core/shared` 新建 `parse_optional_positive_int`,坏值→None,语义与 `parse_finite_int` 的 raise 相反,故不能复用既有 sink)。

---

## 四、当前现实:基线已漂移,务必重新校准(关键!)

- fix-plan 的复核基线 = 提交 **`b08162cd`**;但**工作区已改 88 个生产文件(+5188/−1612)**。
- **所有 `location` 行号都是旧的**:evidence 描述对、行号错。**每条债落地前必须按符号名 `grep` 回盘,不许信 `location` 行号**。实测漂移:LB01 `347-354/451-453`→实际 `369-372/455`(+20);R44 `:28-29`→`:36`(+8);R42 `:86`→`:78`(−8)。
- **6 已修 / 3 在途**(全来自一次 resource-dispatch 执行车道重构,集中在 B01/B06/B11):
  - LB03/LB06/R56/R57/R07/R16 已修;LB02/LB05/R15 在途(契约测试已绑,注释/收口未完)。
  - 这次重构把 **adopted-only 不变量下沉为 v19 迁移的 DB CHECK 约束**(`effective_plan_role='adopted'`/`source_table='schedule'`)+ 新建 `core/models/operation_execution_scope.py` 集中 raise 校验 → **LB01/LB02 等代码层护栏注释的"前置紧迫性"下降(schema 已兜底)**。计划要重新评估这些前置是否还必须先落。
- **执行重构本身引入了新债/新不对称(必须纳入扫描,别只盯旧 80 条)**:
  - **R09 加重**:`_positive_int` 现被拷到**第 4 处**(`web/routes/domains/scheduler/scheduler_resource_dispatch_execution_context.py:28`),收口反而更远。
  - 新增约 **12 处宽 `except`,其中 ≥4 处 `return None`**(疑似新的 P4 静默兜底,例如 `execution_fact_provider.py:85` R15 未收口残留),计划须确认其余几处不是新埋的灵魂线违背。
- **你的计划针对**:剩余 **70 待修 + 3 在途收尾**,把已修 6 条作为"前置已完成"重算 DAG;同时把"执行新引入的债"补进清单。

---

## 五、防全炸核心 · 11 条承重护栏不可碰清单(逐条:守什么 / 禁什么 / 为什么改它会静默炸)

**A 族 · execution_review「只复盘正式采用方案」(4 层纵深防御,守同一条不变量,任一层都非冗余)**
- **LB06**(web 路由层):守"复盘页只能用正式采用方案取数";禁把 `"adopted",None` 改成从 request 读、禁删 is_execution_review 强制分支;炸=预览/对比方案经 `?plan_role=&scenario_id=` 冒充正式复盘、照常渲染绿。
- **LB02 == LB05**(服务签名层 `execution_review.py`):守"方法故意不收 plan_role/scenario_id,恒 ROLE_ADOPTED";禁为"统一四张报表签名"补形参并透传;炸=取数源切到 scenario 预览表,模拟明细以"正式现场复盘"身份导出。
- **LB01**(写侧反馈 `operation_execution_feedback_service`):守"现场反馈只能挂当前正式采用方案";禁把写死常量改透传 context、禁删硬拒分支;炸=现场事实写到候选/scenario 上,下游重排护栏基于污染事实决策。
- **R56/R57**(`navigation_context.py`,b08162cd 新接缝,**最脆弱**):守"导航/fallback 不信任未经 PlanIdentity 解析的 raw role/scenario";禁删/弱化字面量匹配分支、禁把 fallback 当等价快路径;炸=改路由名即静默失效 / raw 身份直通。
- **R58**(`scheduler_navigation_publish.py`):守"can_write_feedback 仅 formal_adopted 可写";禁用原始值 `context.update` 覆盖已 gate 的值。
- **R54 / N1**(承重字段散 3~4 抄,**比单处无注释更危险**):守"放行护栏依赖的 plan-guard 字段集单一来源";禁继续手维多份 key 列表;炸=漏拷一键护栏静默失效。

**B 族 · 各自独立的承重不对称**
- **LB04**(`boolean_normalize.py` 双实现):守"core/shared 提供下层可调的归一";禁以"统一到矩阵"删它/让 core.models 改指 core.services(越层+导入环,击穿 0 分层违规);唯一合法消重=上层 matrix 反向 delegate 到下层。
- **LB07**(双 `ScheduleConfigSnapshot` 栈,model↔service):守"两栈 27 字段逐字段同步";禁单边加字段;炸=算法用旧默认值、配置页存新值,静默分叉污染排产。收敛前必须先补 parity 测试。
- **LB08**(`scheduler_public_errors.py` legacy 错误串往返桥):守"正则把中文串反解回 code";禁改 `auto_assign_resource_errors` 发出的中文文案而不同步正则;炸=改一字静默失配,错误降级为通用文案。
- **LB03**(`schedule_plan_identity_builder.py`,已 fail-closed 治理,`adv_refuted=true`):真护栏是 `result_status='simulated'`(原子同写),不是此处 summary 解析;**禁把 `except: return False` 改 raise**;炸=`latest_executable_official_version` 全量扫历史,一条 legacy/NULL 坏行让整链崩=可用性放大事故。

> **最易被误修引爆的"像重复 / 该统一"实为护栏**:LB04(看似冗余 boolean)、LB07(看似该收敛的双配置栈)、R54/N1(看似该 DRY 的多份字段表)、A 族 LB01/02/05/06(看似该对齐的报表签名/参数方言)。共性=**刻意与兄弟不一致 + 理由散在远处(schema CHECK/分层规则/UI 文案/合同测试)+ 本地零注释**。计划里任何"DRY/统一/合并/对齐签名"步骤,只要落在这些上,一律改写为"补注释+绑测试"。

---

## 六、须人裁断、计划里"只标不修"的(19 条,附录 C 的 10 类 + 误标)

不得替 owner 拍板,标注"待裁、暂不分配执行批次":
1. **R09** 是否值得新建 `parse_optional_positive_int` 收口点。
2. **R22** `default_plan_resolution_dict` 键集"侥幸对齐"——收口前先补 parity 测试。
3. **LB07** 双配置栈"27 字段未漂移"靠手工比对——收敛前先补 parity 测试。
4. **R26** config/summary 5 个 shim——Win7 离线只能证树内,删除前须人工确认无树外脚本消费。
5. **R11** `_normalize_critical_chain_result` git 标 `A` 未提交——落手前必须问在途作者。
6. **R29** `number_utils.py` 是有意 delegation-facade 还是半截迁移(KEEP/owner pending)——薄壳化须先重写 monkeypatch 测试。**注:R29 当前被误标 `not_applicable`,实为 owner-pending 待裁,应纠正为 planned/待裁**。
7. **R52** ready_queue 全量版——needs_adversarial 仍开放。
8. **R14** 延期诊断三件套——本分支 `aps-three-gap-directions` roadmap 在途契约,勿动。
9. **R43** 9 个 `scheduler_*.py` wrapper——roadmap 明示延期,动即抢跑。
10. **LB08/R8** legacy 错误串桥——改文案会静默失配正则,收敛前同步检查。
> 另含 R55/R03/R71/R72/R41/R19/R69/R40/R32/R34/R08 等设计意图或落点未定项(见 `_matrix_raw.json` 与 MASTER-PLAN 的 owner 列表)。

---

## 七、建议的工作流设计(细颗粒、对抗式、质量优先)

> 用 workflow 分相;子 agent 写长文用"先 Write 小骨架,再逐段 Edit"、**返回别强制 schema**(防 StructuredOutput 掉线);本环境**只有 OPUS**——别传 `agentType:'Explore'` 或 `model:'haiku'`(会 404 全失败);产物落 **gitignored 目录或不要 `git add`**(本机有并行进程会 `git stash` 卷走 staged 改动)。

**分析单元 = 单条债(最细)。Phase A 一条债一个专属 agent,不许按桶打包(按桶=一个 context 塞 15 条=每条都浅)。每一层产出都必须经独立对抗审核,绝不一遍过、绝不自评自过。** agent 预算(并发上限约 10–14,排队跑完;总量低于 1000 上限):

**Layer 1 · 逐债档案 + 独立核验**
- **A1 构建 ≈ 76**:待修 70 + 在途 3 = 73 个 dossier agent(各管 1 条:当前代码 grep 回盘真实 file:line + 读 phase2 修法 + phase1 爆炸半径 + 调用图追调用者 → 产出 §八 12 字段档案)+ 1 个确认 6 条已修(作 DAG 前置)+ 2 个扫 88 文件 diff 找执行新引入的不对称/新债(R09 第 4 抄、新 except 群)。同文件兄弟债的 agent 互相告知 sibling id。
- **A2 对抗核验 ≈ 44**:11 承重 + 4 个"像重复实为护栏" + 全部 high/medium 债(~30 条)**逐条 1:1 独立核验**(第二个 agent 重新 grep、挑战其调用者/承重/分层判断,不一致即标争议、升级第三方裁);其余低危债 ~3 条/agent 批验 ≈ 14。

**Layer 2 · 干扰图重建 + 红队(2 轮)**
- **B1 构建 ≈ 10**:C01(67 债)按 ~18 碰撞文件拆 8 个重算边 + 1 个管 C02/孤点 + 1 个聚原子簇/拓扑排序/验环。标注哪些边因漂移/已修而变化。
- **B2 红队 ≈ 5**:第 1 轮 3 个("你漏了哪条跨债边?哪个簇该拆/该并?哪条排序约束错?")→ 修订 → 第 2 轮 2 个复检。

**Layer 3 · 逐簇爆炸对抗(核心,3 轮)≈ 106**
- 第 1 轮:~18 原子簇 × 3 透镜 skeptic(承重误删 / 分层导入环 / 灵魂线热路径 raise)= **54**。
- 第 2 轮:按第 1 轮发现修订后,~18 簇 × 2 再攻 = **36**。
- 第 3 轮:仍存争议 + 含承重的高危簇(~8)× 2 终攻 = **16**。
- 默认怀疑、多数推翻即标红。每轮质问点见末尾。

**Layer 4 · 全计划红队(3 轮)+ 综合 ≈ 14**
- D1 装配安全批次计划(§八结构)1 个。
- **红队第 1 轮 3 个:当作真要执行,逐批在脑内跑一遍,专找"按这个顺序改到第 N 批会炸/某两批顺序反了/某簇没拆开就改"**。
- D2 按红队意见打补丁 1 个 → **红队第 2 轮 3 个**复攻补丁后的计划 → **第 3 轮 2 个**签收(收敛确认无新爆点)。
- 跨批一致性核查 1 个 + completeness-critic 2 个("还有哪条债没分析透 / 哪个收口没验行为等价 / 哪个簇没对抗满 3 轮")——发现盲区即回炉(loop-until-dry)。

> **总计 ≈ 250 个 agent 次(±30),其中对抗/核验占 ~65%(约 165 个)**——这是"照此修复不会全炸"的信心来源,不是装饰。三个对抗层各司其职:A2 查"档案本身对不对",B2 查"干扰图有没有漏边",L3 查"逐簇按下去会不会炸",L4 查"整盘按顺序执行会不会炸"。Phase D critic 触发回炉时实际更多——质量优先,预期如此。
>
> **每轮 skeptic 必查的质问点**:会不会误删/弱化承重护栏?跨层 import 或导入环(击穿 0 分层违规)?P4 改 raise 落在扫历史/legacy 热路径=可用性放大事故?与 schema CHECK / v18·v19 迁移耦合(改码不改迁移=启动探针炸)?收口点与被删副本**逐分支行为是否等价**(R09↔R04 的 None vs raise 是反例)?删 facade/改签名前先迁哪些测试?

---

## 八、交付物(计划文档结构,颗粒度到债)

1. **每条债档案**:当前真实 file:line(grep 回盘)+ 状态 + 病理/严重度/桶/簇 + 修法类 + 同文件碰撞债 + 同收口点债 + 收口行为差异及所需 parity 测试 + 爆炸半径(消费者清单+灾难链)+ 承重毗邻标记 + 分层/导入环风险 + 测试耦合(先迁哪些)+ 前置依赖。
2. **干扰图与原子簇**:边类型分布、重灾区文件(navigation_context/dispatch_rules/execution_review 等)、原子簇清单、拓扑批次顺序、验环结果。
3. **每批计划**:成员 / 是否原子 / **前置安全网(先补哪些契约·parity·回归测试)** / 不可碰清单 / 收口行为差异检查项 / **批后门禁(`tests/test_architecture_fitness.py` 21 项全绿 + 0 分层违规 + 语义雷达 `.codestable/semantics/` 无新漂移 + v18/v19 DB CHECK 不破)** / go-no-go / 人裁断闸门标记。
4. **全局风险 register** + 与旧 MASTER-PLAN 的差异说明。
5. 每条断言**附当前代码 file:line 证据**。

---

## 九、质量标准(不限时,只看质量)

- 颗粒度到每条债;**每个 file:line 必须在当前代码上 grep 回盘核过**,不许照抄旧 location。
- 每个"安全"结论都要对抗验证(默认怀疑,找不到反证才算安全)。
- **不许静默截断**:若对某批/某些债做了 top-N、采样、跳过,必须 `log` 出来并说明。
- 重灾区(C01 的 67 债、A 族 4 层、双配置栈、R09 四抄)必须逐条交代,不许"其余从略"。
- 结论与已有分析冲突时,给出当前代码证据再下判。

---

### 一句话收尾给执行者
**先立约、再动手**:这份计划的价值不是"怎么修",而是"按什么顺序修、哪些必须一起改、哪些碰都不能碰、每批修完怎么验证没炸"。把散在远处的护栏意图、爆炸半径、收口顺序钉成一张可执行的图——这是让无记忆的协作者还债时**不闯祸**的唯一保险。
