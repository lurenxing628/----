# explode r1 · C-EXEC-FACT · 主透镜【分层导入环+迁移耦合】

> skeptic 第1轮 / 只读不改 / HEAD c2aa7501 / 回盘 2026-06-05 / 默认怀疑
> 成员债: LB01 R13 R15 R17 R18 R19 R20
> 主透镜重点: Q2 分层导入环 · Q3 迁移CHECK耦合 · 最危险边 LB01↔R17(同 _build_event_payload) · R15 P4残留 · R19 越层环保 sorted
> 所有 file:line 经本轮独立 rg 回盘，不信旧值。

---

## 逐债判定

### LB01 — 🟢 绿（仅注释，零结构动作）
- 回盘坐实: 写死 service.py:471-473(`SOURCE_SCHEDULE/ROLE_ADOPTED/scenario_id:None`)、硬拒 :369-372、reported_status :475 同属 `_build_event_payload`(def :455)；硬拒上方/写死上方 grep '#' 零命中（注释确未补）。
- 修法纯补两处中文注释，零删/零透传/零统一，owner_pending=false。分层零新增 import(Q2 安全)。
- **唯一约束**: 它是 R17/R20 的承重前置门，必须先落注释再放行同文件删改（见下）。本债自身不炸。

### R17 — 🔴 红（最危险边：删 service:12 / support:81 误碰承重或探针）
**灾难链**: R17 删 service:12 `EXECUTION_EVENT_EXCEPTION` 死import + support:81 推导式项，**两点物理上一个在 `_build_event_payload` 函数体所在文件头、一个在归一表**。爆点有三:
1. **删 :81 误删 :80 活键**(`EXECUTION_ACTION_REPORT_EXCEPTION`) → `"report_exception"` 键消失 → service:475 `_REPORTED_STATUS_BY_ACTION[action]` 对真实报异常 KeyError/归一 :269 校验拒真实操作 → 用户报异常被静默拒（坏数据：异常态落不进库）。修法必须删 :81 不删 :80。
2. **顺手"重构/清理" `_build_event_payload`** → 一旦触 :471-473 写死消毒层 → scenario/candidate 现场事件落库 → execution_fact_provider:40 纯按 op_id 读无过滤 → schedule_execution_guardrails 喂重排护栏 → **预览态污染排产决策（静默，无 raise）**。这是 SCC 最危险边。
3. **误删 `EXECUTION_EVENT_EXCEPTION` 常量定义本体**(event.py:14，被 state_builder/data_contract/web viewmodel/启动探针 6 文件真活) → 全线 ImportError + **启动探针 `_operation_execution_probe_issues`(migration_contract:341-355) 消费该常量链断**。
**修正/禁区**: 必须 LB01 注释先落(裸奔期严禁动 service)；只删 service:12 + support:81 + support:11 三行净删，禁碰 :369-372/:471-475/:80 活键/event.py:14 常量；删后重 rg 回盘行号（:12 删使下方上移），R20 的 :52、R15 的 support:225 须重新定位。原子提交。

### R15 — 🔴 红（provider P4残留收口：空值vs坏值不区分→静默炸或假错）
**回盘坐实双重不等价**: provider `_parse_execution_time`(:84-95) 空→None 坏→None（双静默）；收口去向 `parse_operation_event_time`(event.py:75) 空→`raise event_time is required` 坏→`raise`。**逐分支非平移**。
**灾难链 A（收口一刀切 required+raise）**: provider:52/53 喂 `actual_start_time/actual_end_time`——空 actual 是合法现场态（任务没开始就没开始时间）。统一成 raise → 整个执行事实读取抛错 → 若上层宽 except 吞掉 → 执行事实全空 → 排程按空数据重排（静默坏排程）。
**灾难链 B（坏值仍 return None）**: 坏时间静默 None 进 duration 计算，P4 期望的 loud 升级落空。
**Q3 耦合爆点（本轮新发现）**: 启动探针 migration_contract:349 主动喂 `event_time:"not-a-date"` 靠 DB/契约拒绝判库迁移态；R15 收口若改动 provider 解析的 raise/None 边界语义，须确保不与探针对"坏 event_time 必被拒"的预期冲突。
**修正**: owner_pending=true，裁断前不进批次。禁区铁律：`provider:87 if not text:return None` 必保 optional（空→None），坏值分支改 loud raise 或可观测降级标记，**禁加更深 return None**；support:229 raise 一字不碰。必须先补三处 required/optional parity 再收口。SCC 最前置（先于 R13/R17/R19 同文件落地）。

### R19 — 🟡 黄（条件：保 sorted + 不越层不成环 + parity 钉 missing[0]）
**回盘坐实双阻断**: 阻断A snapshot.py:7 已 import provider，反向收口即环；阻断B repo 无 service import，repo 收 service=data→service 越层。snapshot:40 `return sorted(out)` 喂 :78 sha256 指纹（事实承重）；provider:82/repo:79 不排序。
**条件可做**: provider(同 service 层)可收口到 `positive_op_ids`，但 (1) canonical 实现**必须保 sorted**——误改不排序→build_execution_snapshot 的 sha256 对同输入产不同值→下游4处 guard/publish/scenario 快照比对静默失真（无测试拦截，最严重）；(2) provider 收 sorted 版后 :147 `missing[0]` 报错文案 op_id 变，须 parity 断言或 owner 接受；(3) repo 因分层**不能收 service**，只能保私有版补注释或下沉 core/models（触 red line #3，owner 裁）。
**禁区**: 严禁让 provider import snapshot（成环）、严禁 repo import service（越层）、严禁 canonical 去 sorted。先建 parity（三函数零符号级测试）再动。owner_pending=true，最晚批次。

### R13 — 🟡 黄（条件：死字段被3测试读活，直删须先退测试+owner裁；禁碰 repo stub）
**回盘坐实**: 死字段 :23-24/:56-57 生产0消费，但被 scope_read_contract:108/190-191/220-221 + reschedule:196(`==1`) 钉死。
**条件**: 路A直删须同步退 6 处测试引用（漏退即 TypeError/KeyError，响亮非静默，可接受）；但"死"定性已被重构推翻，**升 owner 二次确认无未来消费**。最危险诱惑=连带删 repo:399 `list_latest_events_by_op_ids`——它是 R18 范畴的 stub raise 护栏，**R13 绝不碰**（删→AttributeError 击穿契约；若改回真查询→复活越身份读取）。
**禁区**: repo:399/401 stub raise、provider:110/113 raise 软禁区不削弱。同文件须 R15→R19→R13 串行或同批（R13 删字段缩文件移动 R15/R19 行号）。

### R18 — 🟢 绿（补注释护栏，前提已被重构消解）
**回盘坐实**: :401 已是单行 stub `raise _unscoped_execution_read_error()`，与 :354/356/399/403/405 同组6格契约护栏；零生产消费；foundation:367 `pytest.raises(ValueError match=完整计划身份)` 是拒绝断言非续命。
- registry「直删+退测试+摘 EXECUTION_EVENT_EXCEPTION import」全失真（该 import 零命中无对象，OperationExecutionEvent 被返回注解占用不可删）。
- 修法=与 R13 共用一条注释覆盖 :399-405，零行为/零签名/零 import 变更，foundation:367 继续绿。
- **唯一红线**: 禁直删（→AttributeError）、禁改 `return {}` 静默兜底（→非scoped读静默返空，调用方误判"无异常事件"）。owner F门点头降级后落注释。

### R20 — 🟢 绿（直删垫片改直连 model，漏改即 ImportError loud）
**回盘坐实**: service:12(R17删点) 与 service:52(R20改点) 同 import 区段，R17 删 :12 一行使 :52 上移。垫片 35 行字节级转发，5 处经垫片+6 处已直连 model。
- 5 处改连 `core.models.operation_execution_labels` 严格等价（同对象引用），分层 services/web/tests→core.models 合法向下，零越层零环（Q2 安全）。R08/R09/R12 同文件边经核全假。
- **禁区/前置**: LB01 注释先落再改 :52；与 R17 串行（后做者重 rg `from .operation_execution_labels import` 真实行，不照抄 :52）；删文件须同批摘 docs_quality_gate:128 + 指南:151（漏=门禁红记账失败，非安全失守）；禁碰 feedback_service:347-356/451-453 LB 禁区。

---

## 漏项（本轮新发现，计划未充分覆盖）

1. **Q3 启动探针未列为 R15/R17 的硬前置门**: `_operation_execution_probe_issues`(migration_operation_execution_contract.py:341-355) 启动主动 INSERT `event_time:"not-a-date"`(:349)、`source_table:candidate_rows`(:355) 靠拒绝判库迁移态。R15 收口动 provider 时间解析边界、R17 删 EXECUTION_EVENT_EXCEPTION 链，均须先确认不撼探针消费链；簇文档 D 节只提 schema.sql CHECK，**未把启动探针列入门控清单**。建议执行清单加「改码前后跑启动探针/迁移自检」F门。
2. **v19 DB CHECK 已下沉但簇文档仍引 schema.sql:190-192**: 回盘 v19.py:14/15/18/19 三态硬钉 `source_table='schedule'`/`effective_plan_role='adopted'`，是 adopted-only 的真·迁移底。LB01 §7 反例链应同时锚 v19，否则改码不改迁移=启动迁移自检炸的探针无人盯。
3. **R13↔R18 共用注释「合批要求」与 R13 owner裁「可能不动 repo」存在张力**: 若 owner 裁 R13 走路B(保留字段)则 R13 完全不入 repo，R18 注释须独立落；簇文档 A4 默认二者合批，需补「R13 路A/路B 决定 R18 注释是否合批」分支。
