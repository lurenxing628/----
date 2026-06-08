# 逐簇爆炸对抗 r1 · C-RESOURCE-REPO · 主透镜 SOUL（灵魂线热路径+收口等价）

> skeptic r1，只读不改，默认怀疑。行号全部 rg 现盘回盘（2026-06-05），不信旧值。
> 成员债：R05 / R67 / R34 / R35 / R36 / R37 / R38 / R39
> 主透镜聚焦 Q4（灵魂线热路径）/ Q5（收口等价）/ Q6（测试迁移序）。

---

## 回盘坐实（rg 现盘，全部命中）

| 项 | 现盘 file:line | 结论 |
|---|---|---|
| R05 collar 类型集 | schedule_resource_filter.py:8 `SUPPORTED={machine,operator}` | **无 team**，坐实 |
| R05 collar column_name | schedule_resource_filter.py:19-23（machine_id/operator_id，team→空串） | 单列，team 表达不了 |
| R05 collar 空id raise | schedule_resource_filter.py:65-66 `if resource_type_text and not resource_id_text: raise` | 空id 当前强制 raise，坐实反例① |
| R05 禁区·空id全量 | schedule_plan_query_repo.py:455 operator `<> ''` / :460 machine `<> ''` | 承重，在 |
| R05 禁区·team双join | schedule_plan_query_repo.py:462 `((o.team_id=?) OR (m.team_id=?))` | 承重第三轴，在（dossier 写 :461-463，实盘双join行=:462） |
| R05 服务私写 | resource_dispatch_service.py:59 `_normalize_scope_type` / :65 `_normalize_team_axis` | 在，:269/:353 两消费点 |
| R05 续命测试 | tests/resource_dispatch/test_scheduler_resource_dispatch_invalid_query_cleanup.py:340 `_normalize_scope_type("bad")` | 删/改名即红，坐实 |
| R34 死方法 | schedule_repo.py:36/:114/:128 | 在 |
| R34 repoint 目标 | schedule_plan_query_service.py:210 `get_plan_time_span_for_resolution` | **存在**（dossier 正文误判，Layer1+verify 已纠，实盘坐实） |
| R34 活方法保护 | schedule_repo.py:71 `list_version_rows_by_op_ids_start_range` / :160 `list_by_version_with_details` | 活，禁误删 |
| R34 facade 断言 | facade_delegation.py:31/:36(死)/:37(活)/:39-40 | :37 是活方法 |
| R34 detail_queries 消费 | rg -c = **10**（registry 写"六个"是 registry 笔误） | 坐实 |
| R34 critical_chain monkeypatch | tests/gantt/test_gantt_critical_chain_unavailable.py:59 patch 死方法 / :60·:162·:171·:186 用活方法 | :59 删安全，:60 起禁动 |
| R35 list_between | schedule_repo.py:61-69（夹在 R34 :59↘:114） | 零引用，坐标耦合真 |
| R36 | batch_operation_repo.py:25 / :50 | ISOLATED 零引用 |
| R37 死方法 | operator_machine_repo.py:82-90 | 在 |
| R37 活近亲 | operator_machine_repo.py:92，被 equipment_pages.py:142 + facade :105 + tests :194/:222 | **活**，误删静默炸设备页人机分组 |
| R38 三份 | op_type_repo.py:73 / operator_repo.py:85 / part_repo.py:71 | 三 SQL 列集异，禁抽 helper |
| R39 list_unparsed | part_repo.py:32（体:33→self.list），R38 在:71，中间 create/update/delete :35-69 | 删 R39 致 R38 上移，坐标耦合真 |
| R67 共享常量 | `REPORT_RESOURCE_FILTER_ARG_KEYS` 全仓 NOT FOUND | 4 处手抄，第4处 scheduler_navigation_links.py 不在 all_files |
| R67 收口点 | report_context_filters.py:119 | 在，4 抄点中①②调它、③④只拼URL/拷字段 |

---

## 逐成员判定

### 🔴 R05 — 会炸（承重第三轴 + 跨轨收口污染 + 反序静默丢谓词）
- **灾难链 A（反序·主透镜 Q5 收口不等价）**：若 R34 detail_queries 迁移或任何收敛先于 R05 步1，把派工读取收敛到只认 column_name 的现状 collar → schedule_plan_query_repo.py:462 team 双join 谓词凭空消失 → 班组视角 column_name 返空串无谓词 → **静默返全量坏数据**（无报错，最难发现）；operator/machine 空id 走 collar:65-66 raise → 全量视图整页 500。逐分支不等价坐实：(operator,"")旧路全量(:455) vs 新路raise(:65)；(team,*)旧路双join(:462) vs 新路空串全量。
- **灾难链 B（计划未点明·跨轨污染，本轮新发现）**：`normalize_schedule_resource_filter` 是**双轨共用收口点**——被 schedule_resource_sql_filters.py:9（超期/明细轨，依赖 column_name 单列 + 空id→raise 挡坏查询）+ report_context_filters.py（报表轨）同时调用。R05 步1 "放开空id=全量" 若裸改 collar:65-66 raise 行为 → **同时污染超期/明细轨 + 报表轨**，那两轨当前靠"空id→raise"挡掉坏查询。
- **修正**：步1 扩 collar 必须给派工轨**单独入口**（新接口 `where_predicate(scope_type,scope_id)→(sql,params)` 或新参数 allow_empty_as_all），**禁裸改 :65-66 raise**（会击穿另两轨）；team 双join 谓词由 collar 产纯字符串+参数序列，**禁 core.models 反向 import data 的 SQL builder**（model→data 越层+导入环）。步1扩+步2 parity 5条先落，才门控步3 把 :455/:460/:462 搬进收口点。空id=全量是**显式扩语义**，须写中文注释，禁 except 吞错/默认空串静默放行；team+scope_id 缺失须显式走全量或 loud raise。owner_pending=true 维持，F-决策①接口形态②(team,"")语义不给终态。

### 🟡 R34 — 有条件可做（软约束选错=用例被 R05 二次推翻；facade import 误删诱导）
- **条件1（Q6 测试迁移序）**：detail_queries 10 用例若选"迁活孪生"，落点 `schedule_plan_query_repo.list_dispatch_rows`:430 正是 R05 步1要改 WHERE 的战场 → 软约束**回升为硬前置**：必须排 R05 之后迁，否则用例断言一个即将变行为的方法、随后被 R05 改动二次推翻（测试红或假绿）。若选"整删用例"则与 R05 解耦。owner 须先裁"整删 vs 迁移"才能定 R34 对 R05 的依赖性质。
- **条件2（facade import 误删，本轮新发现漏项）**：facade_delegation.py:11 `ScheduleDetailRow` 被 **:36(死方法 list_overlapping_with_details) + :37(活方法 list_by_version_with_details) 共用**。删 R34 时若按"哪些 import 随死方法走"机械判断，:11 被 :36 引用会**诱导误删** → :37 活断言 import 缺失 → 响亮 NameError。dossier 结论（保留 :11、只删 :12/:14）正确，但**理由必须钉在 ":37 活方法仍用 ScheduleDetailRow"**，不可因 :36 删而顺手删 :11。
- **其余坐实**：repoint 目标 :210 存在；benchmark:503 漏改=响亮 AttributeError（非静默）；critical_chain:59 删安全（:60 起禁动）；活方法 :71/:160 + facade :33/:37 禁误删。生产零引用，删错全响亮无静默炸点。
- **修正**：同提交、按符号名自下而上删；R35 同批；detail_queries owner 裁断后才定 R05 依赖；facade 删 import 严格只删 :12/:14，:11 保留并注明理由。

### 🟡 R37 — 有条件可做（活近亲一字之差，误删静默炸设备页）
- **条件（误删护栏，非承重但高危）**：死方法 `list_links_with_machine_names`:82-90 与活近亲 `list_links_with_operator_info`:92 仅一字之差（machine_names vs operator_info），SQL 维度截然不同（JOIN Machines 取机器名 vs LEFT JOIN Operators 取操作员信息）。活近亲被 equipment_pages.py:142 + facade :105 + tests :194/:222 实际依赖。误删活的那条 → **静默炸设备页人机联动分组**（页面数据缺失，非编译期报错，最难察觉）。
- **修正**：单独成 commit，diff 严格锁 :82-90，删后立即 grep `list_links_with_operator_info`:92 仍在。R37↔R41 是伪干扰边（R37 不碰 equipment_pages.py），删边。

### 🟢 R35 — 安全（纯死叶子直删）
零引用零测试零 callgraph 入边坐实。唯一约束=与 R34 同 schedule_repo.py 同提交防行号二次漂移（:61-69 夹在 R34 :59↘:114），按符号名定位。owner_pending=false 给终态直删。无灵魂线/承重/分层风险。

### 🟢 R36 — 安全（ISOLATED 纯死直删）
batch_operation_repo.py:25-35 + :50-61，零碰撞零跨边零引用（实际被调=get/list_by_batch/create/delete_by_batch，这两个不在内）。从后往前删。无承重无收口无灵魂线改动。本桶最早可落之一。

### 🟢 R38 — 安全（三笔独立直删，禁抽 helper）
三份 SQL 列集异（op_type_id,name,category / operator_id,name,status,remark,team_id / part_no,part_name,route_raw），结构同形非同体，抽 helper=新建零消费活死代码。三处零引用。part 份与 R39 同 part_repo.py 硬同批；op_type/operator 两份物理隔离可独立随簇。记三笔。

### 🟢 R39 — 安全（壳删，被包活方法 list:20 不动）
part_repo.py:32-33 删壳，`self.list(route_parsed="no")` 走活方法 list:20（被 part_service.py:105 等多处用，入边充足）。零引用。与 R38 part 份同批（删 R39 致 R38 上移 ~2 行）。无灵魂线（一行透传非 except/兜底）。

### 🟡 R67 — 有条件可做（半截去重 = 比现状更危险的假统一）
- **条件（Q5 等价·静默缺key）**：4 处手抄 6 键别名清单，抽常量时漏一键（如漏 scope_id）→ 受影响入口对该资源维度**静默不筛**（不报错不崩数据不坏，blast low）。最大风险=**半截去重**：只换 1~2 处其余仍手抄 → "看似统一实则分裂"假象，未来改别名更易漏，比现状更危险。第4处 scheduler_navigation_links.py 不在 registry all_files，漏它=半截。
- **修正**：①②纯6键必收（喂收口点、零新增依赖）；③④superset 元组收编须 `(...前缀,*KEYS)` 拼接、tuple 保序（③④依赖URL/字段遍历序），且④跨层边 web.viewmodels→core.services 待 AST 门（有先例 scheduler_resource_dispatch_execution.py:23）。禁动收口点签名 :119-127、禁改 superset 非资源键成员（R42+navigation 地盘）、禁统一4处读取逻辑。owner_pending=true。R67↔R42 diff-hunk 串行覆盖 reports_export_support.py + scheduler_navigation_links.py 两文件。

---

## 漏项 / 本轮新发现（未被簇计划充分覆盖的爆点）

1. **【新·跨轨收口污染】R05 步1 裸改 collar:65-66 raise 会击穿另两轨**：`normalize_schedule_resource_filter` 被 schedule_resource_sql_filters.py:9（超期/明细轨）+ report_context_filters.py（报表轨）共用，两轨依赖"空id→raise"挡坏查询。簇计划只说"扩 collar 放开空id=全量"，未点明这是**双轨共用收口点**，裸改会污染另两轨。须给派工轨单独入口/参数，禁改既有 :65-66 raise 行为。这是 R05 红的第二独立理由（不只是 team 谓词）。

2. **【新·facade import 误删诱导】R34 facade_delegation.py:11 `ScheduleDetailRow` 被死方法 :36 与活方法 :37 共用**：簇计划/dossier 给了"保留 :11"的正确结论，但未点明"保留理由是 :37 活方法"——执行者若按"import 随死方法退场"机械判断会被 :36 诱导误删 :11 → :37 活断言 NameError。建议把判据从"随死方法"改为"grep 该 import 在文件内是否还有活引用"。

3. **【确认·非漏】R05↔R34 依赖性质由 owner 裁 detail_queries"整删 vs 迁移"反转**：簇计划已记为软约束，但其硬/软取决于 owner 未裁的分叉——本轮坐实迁移落点 list_dispatch_rows:430 确是 R05 步1 战场，迁移=硬前置成立。建议 owner 裁断前 R34 不进批次终态（与 owner_pending 一致）。

4. **【提示】R05 续命测试 :340 + R34 facade :31/:39-40 + critical_chain :59 是"测试绿但护栏可破"的反向钉**：删 `_normalize_scope_type` 名 → :340 红（响亮）；这些都是响亮失败非静默，但若先收敛后退测试（序错）会出现"测试复活旧兜底"假象。Q6 序：先迁/退测试 → 同提交删 impl。
