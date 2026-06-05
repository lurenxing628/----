# 逐簇爆炸对抗 r3 · C-EXEC-FACT · 主透镜【分层导入环 + 迁移耦合】

> 只读不改 / 默认怀疑 / 行号经 HEAD c2aa7501 本轮 rg 回盘（不信旧值）
> 成员债: LB01 R13 R15 R17 R18 R19 R20 | 主攻 Q2(分层导入环)/Q3(迁移耦合)
> 权威路径以 `_layer2_residual.md` 为准。本轮结论: **分层 0 违规, 但有 2 处条件红线 + 1 处迁移纵深需守**

---

## 逐成员判定

### R19 — 🔴 红（分层主透镜核心爆点）
**最危爆点。** 三处 positive-id 过滤 (snapshot:28`return sorted(out)` / provider:82`return out` / repo:79`return out`) 唯一差异 = 排序。
- **Q2 导入环（阻断A 坐实）**: `execution_snapshot.py:7 from ...execution_fact_provider import` 单向边在；`rg execution_snapshot core/services/scheduler/execution_fact_provider.py` = **0 命中**（provider 零反向 import）。若 naive 收口让 provider/repo `import execution_snapshot.positive_op_ids` → provider→snapshot→provider **service 内成环**，运行时 ImportError（响，可拦但炸启动）。
- **Q2 分层（阻断B 坐实）**: repo import 头(:1-15)仅 `core.models.* / .base_repo / .operation_execution_state_aggregation`，**零 service 层**。repo 收 `core.services.execution_snapshot` = **data→service 越层**，击穿 0 违规 + 撞 test_architecture_fitness。
- **灾难链（静默，最严重）**: 误把 canonical 统一成"不排序"或让 snapshot 走不排序路径 → `build_execution_snapshot`(snapshot:78) sha256 指纹对同一输入产出不同值 → 下游 4 处(persistence_guard:9 / gantt_adjustment_publish:34 / scenario:16 / guardrails:17)快照比对**静默失真**，**无符号级单测拦截**(`rg positive_op_ids tests/` = 0)。
- **新增真同符号边坐实**: `execution_snapshot.py:118-122 __all__` 含 `"positive_op_ids"`，与他簇 R01/R46(`sym:__all__`)共享此块，高顺序敏感。
- **修正**: 禁 naive 全收口。保守解 = provider 收口同层(收 sorted 后 provider:147 `missing[0]` 文案变 `[3]→[1]`，须 parity 显式断言/owner 接文案变) + **repo 保私有版补"我是故意的:顺序无关"注释**(禁下沉触越层/环)。snapshot:40 `return sorted(out)` = 事实承重行(指纹), canonical 强制 sorted。前置: owner 裁落点 + 先建 §7 parity 黄金用例。

### R17 — 🟡 黄（最危险边 LB01↔R17 同 _build_event_payload）
- service:12 死 import + support:11 import + support:81 推导式死键，全坐实。R17 触及 reported_status `service:475` 与 LB01 写死 `:471-473` **同属 `_build_event_payload`(:455-494)同一函数体**。
- **条件红线**: ① LB01 两处"我是故意的"注释(:368/:471 上方, `grep '#'` 零命中=未落)**必须先落**, R17 才能动 service 文件(承重裸奔期严禁改); ② 删 **support:81**（推导式元组项, 非 :80 活键 `EXECUTION_ACTION_REPORT_EXCEPTION`, 删 :80 → "report_exception" 键消失 → 真实报异常被 ValidationError 静默拒); ③ 绝不"顺手重构" `_build_event_payload` 碰 :471-473/:369-371/:374/:382; ④ 绝不删 `event.py:14` 常量定义(6 文件真活)。满足即绿。

### R15 — 🟡 黄（provider 残留唯一真 P4, owner_pending）
- provider:85-95 坏值 **`return None` 静默**坐实(:87 空→None 合法 optional, :95 坏值→None 静默=P4)；support:227 raise 已落地(灵魂线禁区), state_builder:41 已 delegate。
- **条件**: owner 裁 §4 三分叉前不进批次。收口须**区分空值→None(保) vs 坏值→loud raise/可观测降级(改)**;严禁把"空 actual time(合法现场态)"误判 required(炸执行事实读取);严禁给 provider 加更深 return None。Q5 反例: 空/坏 None→raise 是双重语义跃迁非平移。Q2 无虞(收口去 core.models.parse_operation_event_time, 合法下行零新边)。

### R13 — 🟡 黄（死字段被 3 测试读活, 须先迁测试）
- 死字段 :23-24 / 赋值 :56-57 / 生产侧 0 消费坐实；但被测试读活: reschedule:196 `==1` + scope_read_contract:108/190/191/220/221(共 6 处)。
- **条件(Q6 序)**: 直删须**先迁 scope_read_contract(契约源)→reschedule→后删生产代码**, 序错=测试红。删 `_latest_events_by_scope`(:163) 连带清孤儿 import 时, 同行 `EXECUTION_STATUS_NOT_STARTED`(:7,:47 活)/`OperationExecutionScope`(:8,多处活)/`OperationExecutionEventRepo`(:9,:107 活)**只可摘 `operation_execution_scope_from_event`+`OperationExecutionEvent` 两符号, 绝不连带删活符号**。R13 不碰 repo:399/401(属 R18); list_by_op_ids:110/113/142/147 loud raise 软禁区。owner 二次确认"无未来消费"后选路 A/B。

### R18 — 🟢 绿（补注释护栏, 0 行为/0 import）
- repo stub 组 6 格坐实(:354/356/399/401/403/405 全 `raise _unscoped_execution_read_error()`, 定义:82)。修法=补"故意保留 loud-raise"注释, 零删除/零 import/零分层影响。禁区: 禁直删(退化 AttributeError 击穿契约 + 破 foundation:367 断言), 禁改 `return {}`(静默)。与 R13 共注释覆盖 :399-405 整组, 合批天然不撞。

### R20 — 🟢 绿（删垫片改直连 model, 分层更净）
- service labels import service:52 / support:24 坐实。删垫片 5 处改连 `core.models.operation_execution_labels`(6 处直连方早用的事实统一点)。Q2: services/web/tests→core.models 合法下行, 减一次 service→service 横向转发, 0 越层 0 环。漏改即 ImportError(响)。前置: LB01 注释先落 + 与 R17 协调行号(R17 删 service:12 → :52 上移, 后动方重 rg)。

---

## 漏项（本轮新发现, 计划未充分覆盖的爆点/前置）

1. **【Q3 迁移纵深·新坐实】v19 已下沉 adopted-only DB CHECK**: `v19.py:14 CHECK(source_table='schedule')` + `:18 CHECK(effective_plan_role='adopted')`, 启动探针 `migration_operation_execution_contract.py:355-357` 主动 INSERT candidate_rows/baseline_best/__probe_scenario__ 验 CHECK 拒。LB01 service 写死 :471-473 与此 DB CHECK 是写侧↔DB 底**三重纵深**(service coerce-to-safe / repo:241 validate loud raise / v19 DB CHECK)。**本簇无人改迁移/CHECK, 纯注释/收口 → 不击穿, Q3 绿**; 但 LB01 注释口径须钉死"删写死会让合法 adopted 在边界值触发 DB CHECK→AppError 可用性事故", 防后续以"repo/DB 已 validate 故写死冗余"名义误删(三者逐分支不等价)。
2. **R13↔R19 同文件高危撞行(provider)**: R13 删 :56-57 + 可能删 :163-170 → R19 改的 :70-82/:145 集体上移最多 ~13 行; R15 改 :85-95 紧邻。强制串行 **R15(改语义)→R19→R13(删死物)** 或同批, 后改桶禁照旧行号(防误改相邻 raise 语义)。
3. **R19↔R01/R46 `__all__` 边**未在旧 146 显式标, 本轮坐实为真同符号边(snapshot:118-122), 三债改导出须串行对账最终导出表。
