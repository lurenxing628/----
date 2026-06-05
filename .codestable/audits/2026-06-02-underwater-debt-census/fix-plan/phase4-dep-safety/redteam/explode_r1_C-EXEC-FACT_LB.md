# 逐簇爆炸对抗 r1 · C-EXEC-FACT · 主透镜【承重误删】

> skeptic 第1轮 / 只读不改 / 默认怀疑 / HEAD c2aa7501 / 回盘日 2026-06-05
> 簇成员: LB01 R13 R15 R17 R18 R19 R20 | 最危爆点: LB01↔R17 同 `_build_event_payload`
> 全部行号经本轮独立 rg 回盘（不信旧值）。主透镜 Q1 为重，六质问点全过。

## 回盘坐实总表（本轮 rg，权威）

| 锚点 | 回盘 file:line | 性质 |
|---|---|---|
| LB01 硬拒分支四条件 | feedback_service.py:369-371 + raise :374/:382 | 承重禁区 |
| LB01 写死消毒层 | feedback_service.py:471-473 (SOURCE_SCHEDULE/ROLE_ADOPTED/None) | 承重禁区 |
| reported_status 读表 | feedback_service.py:475 `_REPORTED_STATUS_BY_ACTION[action]` | LB01↔R17 同函数体 (:455-) |
| R17 service 死import | feedback_service.py:12 (body 零用) | 删目标 |
| R17 support 活键/死键 | support.py:80 活(report_exception)/:81 死(exception) 表:74 | 删 :81 非 :80 |
| R15 provider P4 残留 | execution_fact_provider.py:87-88 空→None / :92,95 坏→None | 灵魂线 |
| R15 收口去向空值语义 | operation_execution_event.py:79-80 空→raise / :86 坏→raise | **空值也 raise** |
| R19 三处 | snapshot:40 `return sorted` / provider:82 / repo:79 不排序 | sorted=事实承重 |
| R19 指纹路径 | snapshot:78/109 ids→:91 sha256 | 指纹依赖排序 |
| R19 导出块 | snapshot:118-122 `__all__` 含 positive_op_ids | R01/R46 同符号 |
| R13 死字段 | provider:23-24 定义 / :56-57 赋值 / 生产0消费 | 被测试读活 |
| R13 测试读活 | reschedule:196 `==1` / scope_read_contract:108/190-191/220-221 | 6 处 |
| R18 stub 组 | repo:354/356/399/401/403/405 全 raise；契约测试 foundation:352→:365/:367 | 准禁区 |
| R20 labels import | feedback_service.py:52 / support:24 / context:11 | 改 model 路径 |
| schema 最终底 | schema.sql:190-192 三 CHECK + :284 另一张表 candidate_rows | LB01 反例成立 |

---

## 逐债判定

### LB01 — 🟢 绿（承重，仅补注释，零删除）
- 修法严格锁「仅补两处中文注释 + 认账已存在契约」，禁区 :369-374/:381-382/:471-473 本体不动。dossier §7 三路 parity 主动驳斥「repo 已 validate 故写死可删」最危险诱惑。
- 仅补注释零新增 import → Q2 分层0违规、Q3 不碰迁移、Q5 无收口、Q6 无测试迁移。owner_pending=false 给终态合规。
- **绿的前提（硬）**：必须先于 R17/R20 落注释（门控 service 文件）。注释贴符号上方随符号移动，R17 删 :12 后行号上移由 rg 重定位锚定，不丢。

### R17 — 🟡 黄（条件：LB01 注释先落 + 删 :81 非 :80 + 不碰 :475 逻辑）
- 病理 P6 真实（'exception' 死键 + service:12 死import），纯删安全，但落在最危险边 `_build_event_payload`（:455-）函数体内。
- **黄的三条件**：①LB01 注释必须先落（裸奔期禁动 service 文件，PHASE0 §10.1）；②删 support:81 推导式项**而非** :80 活键（删 :80 → report_exception 键消失 → 真实报异常被 :269 成员校验静默拒为 ValidationError）；③service 只删 :12 import，**绝不顺手重构** `_build_event_payload`，:475 reported_status 读表逻辑一字不碰（与 :471-473 写死同函数体，Q1 主透镜最危处）。
- 灾难链（若违条件②/③）：误删 :80 活键→report_exception 静默拒；或「顺手 DRY 清理」整个 `_build_event_payload`→打穿 :471-473 写死消毒→scenario/candidate 现场事件落库污染重排护栏。
- Q6 测试序：删前确认 foundation 测试只读 EXECUTION_EVENT_EXCEPTION 常量（不读死键），R17 不删常量定义，测试不动；与 R15/R20 同文件须按 R15→R17→R20 串行重 rg 行号。

### R15 — 🔴 红（provider:85 P4 残留收口=空值合法态被静默炸；owner_pending=true）
- **灾难链**：收口符号 `parse_operation_event_time`:79-80 对**空值**就 `raise`（不止坏值！），而 provider:87-88 空→None 是合法现场态（任务未开始→无 actual_start）。若按计划「provider 残债 P4 改 raise」却把空值一并 delegate 下去 → 现场任务的合法空时间被炸成 raise → execution_fact_provider:52/53 读不出 ExecutionFact → 若上游宽 except 吞掉则「执行事实全空」静默喂重排 → 错误排产。
- 计划只说「区分空值→None vs 坏值→raise」；但收口符号空值即 raise，**必须在 provider 侧保留 `if not text: return None` 短路、只让坏值往下走**，不能裸 delegate。多维度存疑（收口去向偏离计划 strict_parse + 坏值 raise 下游是否接住 + support raise 文案契约）→ 红，owner 裁前不进批次。
- 灵魂线禁区：support:225 起 raise 不碰；provider:87/state_builder:39 空→None 不得误判 required。Q2/Q3 安全（同层 core.models 既有边）。

### R18 — 🟢 绿（准禁区 stub，仅补护栏注释，parity 已存在）
- repo:399/401/403/405+:354/356 六格全 `raise _unscoped_execution_read_error()`，是「拒绝非 scoped 读」契约面，非孤儿死码。registry「直删」已失真：直删→AttributeError 击穿契约 + 破 foundation:367 断言。
- 终态=补一条注释覆盖 :399-405 整组 + 跑现成 foundation:352 自证绿。Q4 灵魂线：本就 loud raise，禁改 `return {}` 静默。与 R13 关心的 :399 共用同注释合批、天然不撞。

### R19 — 🔴 红（sorted 指纹=事实承重，naive 收口/统一→指纹静默漂移；owner_pending=true）
- **灾难链**：snapshot:40 `return sorted(out)` 喂 :78/109 ids→:91 sha256 指纹；provider:82/repo:79 不排序。若「DRY 统一三处」误把 canonical 取成不排序版、或让 snapshot 走不排序路径 → 同输入 sha256 revision 漂移 → 下游 4 处 guard/publish/scenario 快照比对**静默失真**（三函数零符号级测试，无单测拦截）。
- naive「三处全收口到 snapshot.positive_op_ids」被双重阻断：阻断A 导入环（snapshot:7 已 import provider，反向即环）；阻断B 分层（repo data层 收 service层 = 越层，撞 test_architecture_fitness）。Q2 击穿0违规风险确凿。
- canonical 必须保 sorted（事实承重待遇，补「我是故意的:指纹依赖排序」）。R19↔R01/R46 共享 `__all__`:118-122 高顺序敏感（Q6 须串行对账导出表）。owner 裁 repo 落点前不进批次。

### R20 — 🟢 绿（直删垫片改连 model，严格等价，漏改即 loud ImportError）
- `from X import Y` 同对象引用，删垫片 5 处改连 core.models.operation_execution_labels 零行为差异；漏改→ImportError 即时炸（非静默）；漏摘门禁:128/指南:151→记账门红（非安全失守）。
- **绿的前提**：①LB01 注释先落（同文件 service:52 在 LB01 区共存，禁碰 :347-356/:451-453）；②与 R17 串行——R17 删 :12 后 :52 上移，R20 动手前重 rg `from .operation_execution_labels import`，不照抄 :52。R08/R09/R12 同文件边经核为假。

### R13 — 🟡 黄（条件：owner 二次确认字段无未来消费 + 先迁 3 测试 + 不碰 repo:399）
- 死字段生产侧 0 消费（rg 排除主文件后空），但被 3 测试读活：reschedule:196 `==1` + scope_read_contract:108/190-191/220-221（6 处）。「死」定性被推翻，非无脑直删。
- **黄的三条件**：①owner 二次确认字段确无未来可观测用途（路A删/路B保留+注释）；②走路A先迁 scope_read_contract 契约（:190-191 dict 键 + :220-221 构造 kwarg，漏退→TypeError/KeyError 即炸）再迁 reschedule:196，测试先表达新契约红→绿；③**绝不顺手删 repo:399** `list_latest_events_by_op_ids`（属 R18 范畴，且删→破 foundation:365 断言；若改回真实查询=复活越身份读取静默破契约）。R13↔R18 强耦合已解除。
- Q1 主透镜：:110/:113 `raise ...完整计划身份...` 与 repo:399/401 raise 是灵魂线软禁区，直删不得削弱。同文件须 R15→R13→R19 串行避撞行号。

---

## 漏项（本轮新发现，计划未充分覆盖的爆点/缺失前置）

1. **R15 收口符号对空值即 raise（非仅坏值）—— 计划口径不足**：计划只写「区分空值→None vs 坏值→raise」，但 `parse_operation_event_time`:79-80 **空值本身就 raise**。若执行者把 provider 整体 delegate 该符号（含空值），合法「任务未开始」空时间会被炸。前置必须显式钉死：provider 侧保留 `if not text: return None` 短路在 delegate **之前**，只把非空坏值交给收口符号。这是比计划描述更狠一层的静默可用性爆点。

2. **R17 删 :80 vs :81 的活/死键陷阱缺前置守卫**：计划/簇文件说「删推导式项」，但未在执行清单强制标注「删 :81 EXECUTION_EVENT_EXCEPTION 而非 :80 EXECUTION_ACTION_REPORT_EXCEPTION」。两行紧邻、命名相似，误删 :80 → report_exception 活键消失 → 真实报异常操作被 :269 成员校验静默拒。建议执行前补一条断言 `"report_exception" in _REPORTED_STATUS_BY_ACTION` 作守卫。

3. **schema:284 第二张表是 LB01 写死消毒的真实兜底缺口**：:190-192 主表三 CHECK 之外，:284 另一张表 `CHECK(source_table IN ('schedule','candidate_rows'))` **允许 candidate_rows**。LB01 §7 反例成立——删 :471-473 写死且事件误路由到该表，candidate_rows 不被拒→脏数据静默落库。任何「统一两表 CHECK」或「删写死靠 schema 兜底」的动作都踩此缺口，须列入 LB01 禁区旁注。

4. **R19 zero 符号级测试 = 收口无护栏先行**：三函数 tests/ 零直接测试（仅间接覆盖），指纹漂移无单测拦截。owner 裁前必须先补 positive_op_ids 黄金用例（钉 sorted）作 F-parity 门，否则任何收口都是裸奔。

5. **同文件串行顺序在 provider 上是三方耦合（R15→R13→R19）**：簇 A3 写 R15→R19→R13，但 R13 dossier §5 写 R13→R19→R15（删字段先收缩文件）。两处顺序矛盾，且 R15 owner_pending。建议统一为：R15 先收口语义（最前置）→ 再删死物 R13 → R19 改，每步重 rg；矛盾须在 Layer4 拍定，否则后改桶照旧行号改错位置。

