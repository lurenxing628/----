# 逐簇爆炸对抗 · 第1轮 · C-RESOURCE-REPO · 主透镜【承重误删】(LB)

> skeptic r1 · 只读不改 · 默认怀疑 · 行号全部 rg 现盘回盘(不信 dossier 旧值)
> 成员: R05 / R67 / R34 / R35 / R36 / R37 / R38 / R39
> 主透镜 Q1 承重误删为重,六质问点全过。

---

## 0) 现盘回盘校正(rg 实证,纠 dossier/簇文档行号偏移)

| 项 | dossier/簇文档旧值 | **现盘实证** | 偏移 |
|---|---|---|---|
| R05 team 双 join | schedule_plan_query_repo.py:**461-463** | **:462-463**(`((o.team_id = ?) OR (m.team_id = ?))` :462 / `params.extend` :463) | **+1**,簇文档D节/dossier§9 系统性偏 1 |
| R05 空 id 全量(operator) | :454-455 | **:455**(`TRIM(COALESCE(s.operator_id,'')) <> ''`) | +1 |
| R05 空 id 全量(machine) | :459-460 | **:460**(`...machine_id...<>''`) | +1 |
| R05 collar「类型有 id 空 raise」 | :65-70 | **:66-70**(`if resource_type_text and not resource_id_text: raise`) | +1 |
| R05 collar SUPPORTED 类型集 | :8 | **:8**(`={"machine","operator"}`,**无 team**) | 0 ✅ |
| R05 `_normalize_scope_type` | :59-63 | **:59**(def)/`:62` raise | 0 ✅ |
| R05 毗邻第四套 `_normalize_team_axis` | :65-69 | **:65**(def)/`:68` raise | 0 ✅ |
| R34 三死方法 | :36/:114/:128 | **:36/:114/:128** | 0 ✅ |
| R34 活方法(禁误删) | :71/:160 | **:71** list_version_rows.../ **:160** list_by_version_with_details | 0 ✅ |
| R34 repoint 目标 get_plan_time_span_for_resolution | dossier正文称「不存在」 | **存在=schedule_plan_query_service.py:210**(layer1/2 已纠回,verify 对) | — |
| R35 list_between | :61-69 | **:61** | 0 ✅ |
| R36 | :25/:50 | **:25/:50** | 0 ✅ |
| R37 死方法/活近亲 | :82/:92 | **:82** list_links_with_machine_names / **:92** list_links_with_operator_info | 0 ✅ |
| R38 三处 | 73/85/71 | **op_type:73 / operator:85 / part:71** | 0 ✅ |
| R39 死壳/活方法 | :32 / list:20 | **:32** / **:20** | 0 ✅ |

> **执行红线①**:R05 禁区行按 dossier 旧值(:461-463/:454-460)定位会偏 1 行,落刀必以现盘 **:462-463 / :455 / :460** 为准,且执行前重新 rg(可能再漂)。承重三轴本体坐实未变,仅坐标 +1。

---

## 1) 逐成员判定(承重透镜为重)

### 🔴 R05 — 唯一承重点,本簇最危爆点(verdict=load_bearing, refuted=False)

**判定 🔴红**(条件红:违序即炸;按 dossier AC-3 三步严格执行才转黄。owner_pending=true,本就不该单提交)

**承重三轴坐实(Q1 主攻)**:collar `column_name`(:19 单列,team→空串)+ `SUPPORTED`(:8 无 team)+ `normalize`(:66 类型有 id 空强制 raise)三者**结构上表达不了**:
- 第三轴 A: team 双 join `((o.team_id=?) OR (m.team_id=?))`(**:462-463**)——单列 column_name 塌缩=班组谓词凭空消失;
- 第三轴 B: 空 id 全量 `TRIM(COALESCE(...,''))<>''`(**:455/:460**)——而 collar :66 对「类型有 id 空」**强制 raise**,直塞=全量入口整页 500。

**灾难链(Q1+Q5 反例,逐分支实证)**:
1. 改X=步3 先收敛(把 repo :452-463 字面量 + 服务 `_normalize_scope_type` 收敛到**未扩 team 的现状 collar**)→ 静默: `("team","TEAM-OP")` 走 collar column_name 返空串→无谓词→**班组视角静默返全量坏数据(无报错,最难发现)**→坏数据流到 `/resource-dispatch` 页 + `/data` JSON(cross_team_rows) + `/export`。
2. 改X=直塞空 id 进现状 collar → collar :66 raise → 「全部人员/全部设备」全量视图**整页 500**(smoke `test_scheduler_resource_dispatch_smoke.py:177-194` 班组活用例为证)。

**Q6 续命测试坐实**: `tests/regression_scheduler_resource_dispatch_invalid_query_cleanup.py:340` 直调 `svc._normalize_scope_type("bad")`——改名/删即响亮红。

**修正建议(承重前置·步内不可换序,owner_pending 暂不给终态)**:
- 前置门: **步1 扩 collar(加 team 双 join 谓词接口 + 放开「类型有/id空=全量」,收口点写明中文注释「id 空→全量视图(故意,派工全部人员/设备入口)」,禁 except 吞错/默认空串静默放行) → 步2 落 5 条 parity(team-only / operator-空-全量 / machine-空-全量 / team-空-未定义裁断 / bad-raise) → 步3 才搬 :462-463/:455/:460 进收口点**。parity 先于收敛是硬序。
- **禁区行(只能先扩收口点搬过去并保语义,绝不裸删/裸合并)**: schedule_plan_query_repo.py **:462-463**(team 双 join,以现盘为准) + **:455/:460**(空 id 全量)。
- **分层红线(Q2)**: collar 在 core.models,步1 加接口须**只产 SQL fragment 文本+参数序列**,禁让 core.models 反向 import data.repositories SQL builder(否则 model→data 越层+导入环)。0 AST 违规。
- **灵魂线红线(Q4)**: team 收敛时 scope_id 缺失须显式走全量分支或 loud raise,禁静默返全量坏数据;「放开空 id=全量」是显式扩语义非兜底。
- F-决策①(team 谓词接口形态) + F-决策②(`(team,"")`=全量 or loud raise) 待 owner 裁。

### 🟢 R34 — 纯删死方法(承重=false,实证零生产引用)

**判定 🟢绿(执行纪律前提下)**。Q1 排雷: `rg get_version_time_span|list_overlapping_with_details|list_dispatch_rows_with_resource_context core/ web/ data/`(排除 def/`_dates`)= **空**,生产零引用坐实。这不是「看着像该统一」的承重——是真死孪生,护栏本在活孪生(schedule_plan_query_repo source_table 分支 + `_require_*` + 未知 source raise)。删错全是响亮 AttributeError(facade get_type_hints / detail_queries 用例 / benchmark / monkeypatch),**无静默炸点**。

**唯一执行红线(相邻活方法保护,非承重)**: schedule_repo.py **:71** `list_version_rows_by_op_ids_start_range`(freeze_window 用)+ **:160** `list_by_version_with_details`(gantt_critical_chain 用)及其 facade 断言 :32-34/:37 **必须保留**,按符号名删勿按行号。owner_pending=true(detail_queries 整删 vs 迁移 + benchmark repoint 层级待裁);若选「迁用例到活孪生 list_dispatch_rows」则须排 R05 之后(迁移落点是 R05 team-join 战场,反序被 R05 二次推翻)。

### 🟢 R35 — 纯死方法直删(零引用)

**判定 🟢绿**。`rg list_between` 全仓仅 :61 def 行,callgraph 零入边。承重=false 无禁区。唯一约束=与 R34 同 schedule_repo.py 同提交、按符号名自下而上删(:61-69 夹在 R34 删段 :59↘:114 之间,违序致行号二次漂移误删相邻活方法)。owner_pending=false 给终态。

### 🟢 R36 — 两死方法直删(ISOLATED 零碰撞)

**判定 🟢绿**。get_by_op_code(:25) / list_by_status(:50) 全仓零非-def 引用,getattr 动态分发排查命中均为读 BatchOperation.op_code 对象属性(非 repo 方法)。承重=false 无禁区。同文件零兄弟,从后往前删。本桶最早可落之一。

### 🟢 R37 — 死方法直删(承重=false,误删护栏明确)

**判定 🟢绿(执行纪律前提下)**。Q1: 死方法 `list_links_with_machine_names`(:82,JOIN Machines 取机器名)与活近亲 `list_links_with_operator_info`(:92,LEFT JOIN Operators 取操作员信息)**取数维度截然不同,非可统一重复**——不落「该统一」陷阱。活近亲被 equipment_pages.py:142 + facade :104-105 + test_query_services:194/222 实际依赖。
**唯一执行红线**: diff 严格锁 **:82-90**,删后 grep 活近亲仍在 **:92**。误删活的那条=**静默炸设备页人机联动分组**(页面数据缺失,非编译期报错,最难察觉)。R37↔R41 经实证为伪干扰(R37 不碰 equipment_pages.py),删边。

### 🟢 R38 — 三处 list_as_dicts 直删(三笔独立,禁抽 helper)

**判定 🟢绿**。三处(op_type:73 / operator:85 / part:71)零消费;SQL 列集各异(`op_type_id,name,category` / `operator_id,name,status,remark,team_id` / `part_no,part_name,route_raw`)**结构同形非字面同体**。Q1 陷阱: 误当「同体」抽 helper=新建零消费活死代码,违收口规则——**记三笔独立删,禁抽 helper**。part 份与 R39 同 part_repo.py 硬同批。承重=false 无禁区。

### 🟢 R39 — list_unparsed 死壳直删

**判定 🟢绿**。:32-33(`return self.list(route_parsed="no")`)零引用(含反射/字符串挑战零反证);被包活方法 `list`(:20)被 part_service:105 等多方消费,删壳不孤立活方法。承重=false。唯一约束=与 R38(part 份:71)同 part_repo.py 同提交(删 R39 致下方行号上移 2 行,R38 patch 基于旧 :71 打偏),按符号名删。owner_pending=false 给终态。

### 🟡 R67 — 抽单一常量(owner_pending,半截去重风险)

**判定 🟡黄(有条件可做)**。承重=false,不动收口点签名,非承重误删。Q1 风险=**半截去重**: `REPORT_RESOURCE_FILTER_ARG_KEYS` 全仓 NOT FOUND(实证 exit=1)坐实 4 处仍手抄;只换 1~2 处反造「看似统一实则分裂」假象,未来改别名更易漏 →某入口静默缺一个资源 key(筛选/导出静默缺失,不报错不坏数据)。

**条件**:①②(纯 6 键喂收口点,viewmodels 已有 `web.viewmodels→core.services` 先例 :23,过 AST 门概率高)**必收**;③④(superset 元组,资源键尾块)**全收或全不收,忌只收一半**,收编须 `(...前缀, *KEYS)` 元组拼接且 tuple 保序(③④依赖 URL/字段遍历序)。
**禁区(契约/越界非承重)**: 收口点签名 report_context_filters.py:**119**-127 禁动;③④ superset 非资源键成员(plan_id 等=R42 地盘)禁改;禁统一 4 处读取逻辑。第 4 处 scheduler_navigation_links.py **不在 registry all_files**,漏它=半截。R67↔R42 diff-hunk 串行覆盖 reports_export_support.py + scheduler_navigation_links.py 两元组文件(非语义冲突)。

---

## 2) 六质问点全局对账

- **Q1 承重误删**: 唯一承重 R05🔴(三轴坐实,违序静默丢 team/整页500);R67🟡(半截去重静默缺 key);其余🟢死代码,但 R34/R37/R39/R38 各带「相邻活方法/活近亲误删护栏」(按符号名删)。R38 带「禁抽 helper」陷阱。无「以 DRY/对齐名义抹承重」被放行。
- **Q2 分层导入环**: 仅 R05 步1 扩 collar 有 model→data 越层风险(collar 须只产 fragment 文本)。R67 第4处新增 web.viewmodels→core.services 边有先例(合法下行)。余皆纯删只减边,0 违规。
- **Q3 迁移耦合**: 本簇无成员与 v18/v19 DB CHECK / schema CHECK 耦合(adopted-only 下沉点不在 repo/collar 战场)。改码不改迁移无启动探针炸点。
- **Q4 灵魂线热路径**: 仅 R05 步1「放开空 id=全量」须显式扩语义+收口点中文注释,team 缺 scope_id 须显式全量或 loud raise,禁新增兜底/静默回退/吞错。其余纯删不触灵魂线。
- **Q5 收口行为等价**: 仅 R05 有真等价风险(`(operator,"")`→旧路全量 vs 现状 collar :66 raise;`(team,*)`→旧路双 join vs 现状 collar 空串)——5 条 parity 钉死,owner 裁 `(team,"")` 语义。R34 死孪生 vs 活孪生 SOURCE_SCHEDULE 分支逐字符等价(已 verify)。
- **Q6 测试迁移序**: R05 步3 前先迁 smoke:177-194 + 续命 :340;R34 删前先退 facade 断言 + detail_queries 10 用例 + benchmark:503 repoint;违序=测试红/复活兜底。R34↔R35、R38↔R39 同 commit 防行号二次漂移。

---

## 3) 漏项(本轮新发现,计划未覆盖/缺失前置)

1. **【行号系统性 +1 漂移·中危】** dossier R05 §9 与簇文档 D 节的承重禁区行(:461-463/:454-460/:65-70)相对现盘**全部偏 1 行**,真值 :462-463 / :455 / :460 / :66-70。计划文档若被下游 Layer4 直接抄旧行号定位禁区,落刀会偏 1 行(虽承重本体坐实未变)。**前置补强**: Layer4/执行期必须以「按符号名 rg 现盘」为唯一定位法,禁抄 dossier 数字行号。
2. **【R05 收敛误伤毗邻第四套·中危,计划已点名但未上升为硬护栏】** `_normalize_scope_type`(:59)与 `_normalize_team_axis`(:65)紧邻,且消费点 **成对调用**(:269-270 / :353-354 两处 scope_type+team_axis 连写)。步3 收敛 `_normalize_scope_type` 时极易顺手把紧邻的 `_normalize_team_axis` 一并「对齐/统一」——但它管 team 展示轴(operator/machine 轴)**不在 R05 收口范围**,误删=班组「按人/按机展开」轴静默失效。**前置补强**: 步3 diff 须显式声明 `_normalize_team_axis`(:65-69)为禁触行,且 5 条 parity 之外补一条 team_axis 轴回归。dossier 仅作「毗邻提示」,建议升为执行硬护栏。
3. **【R05 步1 收口点签名旁敲 facade 契约·低危】** dossier §8 列扩 collar 会波及 `regression_schedule_service_facade_delegation.py:39`(R34 facade 返回类型契约)+ `regression_report_context_filters_contract.py`(R67 collar 别名契约)。R05/R34/R67 三债共振于 collar/facade 契约面——扩 collar 后须确认这两契约仍绿,作「没碰坏邻居」护栏。计划已列但散在三处 dossier,建议 Layer4 合并为 R05 步1 的统一验收门。
