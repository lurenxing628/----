# Layer4 终检·签收复检1（sign1）— 红队两轮采纳修订核对

> 视角：只读不改，默认怀疑。任务=核「红队两轮采纳是否真改对 / 批次序无环 / 三不变式守 / 11标红+6硬阻断落位」。
> 基线 HEAD c2aa7501，所有 file:line 2026-06-05 rg 回盘，权威路径以 _layer2_residual.md 为准。

## 判定：PASS

## 核验明细（逐项实盘回盘成立）

### 一、红队两轮采纳（RT1 9项 + RT2 9项）真改对
- GF1（RT1-P0-1/RT2-2）：`rg reject_integer_float`=0；`parse_required_int` 在 `strict_parse.py:81`，文件 130 行无 :46；§1.1 已重定性「新建 kwarg」+ 新增 O38。✅
- ready_queue 双文件（RT1-P0-2/RT2-3）：impl `core/algorithms/greedy/dispatch/ready_queue.py:103` / 垫片 `core/services/scheduler/graph/ready_queue.py:9`（11 行）；§1.3/§2 三锁定。✅
- collar 宿主（RT1-P1-4/RT2-1）：`web/viewmodels/scheduler_workbench_links.py:187`，三 fail-open 键仅下游 :294-296/:369 消费、collar 体内零产；爆点#1 订正在位。✅
- R42 跨文件删点（RT1-P1-3）：dashboard `:92 "plan_id"`（136 行）+ collar `:191` 形参，§2 已拆两文件两行。✅
- R09 family（RT1-P2-6）：`def _positive_int` 9 文件命中（+_set/_text/异签=12），§2 嵌 12 行对照表，收编只动 A/B 两 Optional。✅
- R64/R65（RT3-P01 + RT2-1纠性质）：R64 `_has_navigation_date_range:66` 全仓 1 命中（def 自身）真零调用；R65 `_target_url:74` 活函数，`:160` 经 `or` 短路真引用，孤儿 import :4/:6，dossier R65 独立证 9/9 非空=死分支三件套，非零调用——§0.1/§1.2 已去同质化。✅
- R49（RT3-P02）：`dispatch_rules.py:28 parse_dispatch_rule`，§1.3 加 R49-self 串行边。✅
- RQErr=16（RT3-P03）：`rg -c ReadyQueueContractError test_ready_queue.py`=16、test_=31，四处「15→16」已纠。✅
- 三批四单元串行块（P-RT22-01）：nav_links 205 行，R64/R65@A + R42@C + R67@C（`_REPORT_CONTEXT_FIELD_NAMES:11`/`preserved_report_context_fields:186`），§1.0 升编排块。✅
- E16 伪串行边降级（P-RT22-02）：三 `__all__` 在三文件（410/118/340），R46 不动 __all__；§1.4/§2 降登记备查，go-no-go 三处同步去门。✅
- R13 退场四处（P-RT22-03）：字段 :23 + `_fact_from_state:40`/形参/赋值 :56 + 实参 `latest_events.get:123` + 孤儿 `_latest_events_by_scope:163`，§1.4 G09 补全四处同原子。✅
- E17 两分支（P-RT22-04）+ 门禁总纲4条（RT2-3）：v19 CHECK 两列 :14/15/18/19、v18 零 CHECK、fitness=21 全部实盘对得上。✅

### 二、批次序仍无环
ROOT→A→B→C→D 拓扑成立；§0.1「环成员=空」+ _interference DFS 验环不变；E16 降级是**减**一条伪依赖，未引新边。无依赖反序。✅

### 三、三不变式仍守
承重前置先落（ROOT 全承重注释+parity 早于任何删改批）；facade 最晚（R26/G18 经 E07/E08/E09 晚于 R29/R33/R52 三桶）；parity 先于收敛（R22/R54/R05/GF1/LB07 全在 ROOT）。R56 navigation_context.py:79 现盘 fail-CLOSED（`plan_role if plan_role in VALID_PLAN_ROLES else ROLE_ADOPTED`）与 §3.2 方向硬门一致。✅

### 四、11标红 + 6硬阻断全落位
11 标红（R09/R15/R19/R52/R14/R69/R54/R04/R42/R22/R05）每条 §2 专项 + 批次落位 + owner 闸门齐。6 硬阻断（#1/#7/#19/#20/#21/#22/#23）逐条闭合到 ROOT/Batch-C 前置安全网或 owner 闸门。owner 闸门 O01-O38 共 38 条，全「只标待裁」未给终态、未分配执行批次（R69 owner_pending=false 仍只给方向选项）。✅

## 残留（非阻断，备查）
- §189 R49 消费图「greedy 多文件消费」是夸大（实盘仅 2 命中）——RT2 已登记为非硬伤，串行结论保守无害。
- collar 真调用方 7→8（多 navigation_context.py）——计数下沉，删形参安全性不受影响（**kwargs plan_id=0，爆点#12 已覆盖）。
- §0.3/§3.2 个别裸写 collar 路径仍存——计划已声明「执行时以本记录宿主 web/viewmodels/ 为准」，可执行性不破。

签收：两轮采纳真改对、批次无环、三不变式守、11标红+6硬阻断全落位、owner_pending 只标不给终态。PASS。
