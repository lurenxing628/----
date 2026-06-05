# 逐簇爆炸对抗 r1 · C-COMPAT-DISPATCH · 主透镜 SOUL（灵魂线热路径+收口等价）

> 只读不改任何 .py。行号均 2026-06-05 rg 回盘。skeptic 默认怀疑。
> 成员债 R30 / R33 / R29 / R49 / R50 / R51。本轮主攻 Q4/Q5/Q6。

---

## 逐债判定

### R33 — 🟢绿（但带硬序前置，序错=响声非静默）
- 三壳 def=0 纯 re-export，生产零消费（`rg core.services.common.{compat_parse,field_parse,value_policies} core/ web/ data/ scripts/` = 0），仅 3 测试续命（回盘确认）。
- 灵魂线：纯减法，不新增兜底/raise，无 P4 改造需求。Q4 干净。
- Q6 测试迁移序：步骤1 必须先迁 `emits_degradation.py:18`（经 `core.services.common.compat_parse` import）+ `matrix_contract.py:18`（经 `core.services.common.value_policies` import READ_FILTER_ONLY）到 `core.shared.*`。**回盘双证**：两测试当前确经壳 import。
- 禁区死保 `config_contract.py:15 degradation`（grep -n 实测 :15，元组 :14-19）—— degradation 是真承重实现（385B，20+ 生产直连），非壳，删元组只动 :14/:16/:19。
- 序错后果是 ImportError/AttributeError（CI 即见），非静默 → 不标红，但**前置硬**。

### R30 — 🟡黄（facade 漏改→ImportError 打挂全表面；非静默，但是本簇最大爆点，须同窗口）
- 灾难链：R30 删 `value_policies.py` 三常量（:12/:16/:17）+ 三 date 策略（:179-208）+ `compat_parse.py` parse_compat_date(:198)/_date_fallback(:143)。**若 facade re-export（`services/common/value_policies.py:6-8/:24-26`）+ 两测试 import 未同窗口处理 → `from core.services.common.value_policies import` 即 ImportError → 打挂经此 facade 的存活消费者（含 matrix_contract:18 取 READ_FILTER_ONLY）**。回盘证实 facade 三 re-export + 测试 import 全在原位。
- Q5 收口等价：R30 不收口（P6 直删），无 parity 义务。date 回退语义（invalid_due_date）与 float/int（invalid_number）**不可统一**，禁误当收口合并。
- Q4 灵魂线：生产零走三策略（坏时间走 `_sched_display_utils record_bad_time_row` 独立路径），删死分支无「悄丢降级事件」。干净。
- 黄因：爆点真实但可控（同窗口 R33步1迁import→R30删→R33步2/3删壳+:411）。禁误删同 import 块 float/int 名（:9-17）与存活函数体。

### R51 — 🟡黄（收口等价故意不等价，测试 :25 兜底断言禁迁/禁保留=复活红线）
- Q5 收口逐分支：回盘 require_choice 体（optimizer_config:64-69 `str(value or "").strip().lower()` not in set→raise；schedule_params `_require_choice:71-78` 空串+未知双 raise）。旧宽容路 `:25` 静默 `return default`。**未知/空值：旧=default vs 收口=loud raise，故意不等价**。
- Q6 灵魂线红线：续命测试 `regression_dispatch_rule_case_insensitive.py:25` + `regression_sort_strategy_case_insensitive.py:25` 钉死 `parse_*("unknown",default=X)==X`，正是 P4 兜底。**严禁保留续命、严禁迁兜底语义**——保留=把已铲的静默回退钉成契约=灵魂线复活。两测试须随函数整体退场。
- 收口点 :277/:346/166/189 全回盘在位（loud raise），删 R51 不夺依赖。黄因：删错碰收口点即静默炸排产，须按符号名定点 + 收口点只读。

### R49 — 🟡黄（同名陷阱：全局删=铲 sgs_scoring 活函数 NameError 炸派工评分）
- 5 死别名零读取（回盘 `_due_exclusive`/`_parse_due_date` 定义后 0 调用）。直删安全。
- Q6/灾难链：**`sgs_scoring.py:34 def _parse_due_date`（活，:223 调用）vs `evaluation.py:40 _parse_due_date=parse_date`（死别名）同名**。按符号名全局删→铲活函数→`:223` NameError 炸派工评分（loud，但是误删炸生产）。另 `evaluation.py:26 _parse_due_date_state`/`ordering.py:59 _parse_due_date_for_sort` 重前缀活函数同禁。黄因：必须 file:line 定点删，严禁符号名全局删。

### R50 — 🟢绿（直删，禁区 import math 已锁）
- mean_positive(:112-132) 生产零消费（真均值在 sgs.py:150 `_average_proc_hours` 内联 sum/len，语义不等价但不进生产）。Q4/Q5 不适用（直删非收口）。
- 删 `import statistics`(:4) 安全（全文件仅 :132 用）；**`import math`(:3) 必保留**（:78/:95/:128 真用，误删→启动 ImportError）。外科退 `nonfinite_proc_hours_safe.py:20` import名+:61-63，死保 :26-59 build_dispatch_key 回退活契约。绿。

### R29 — 🟡黄/owner-pending（只标不给终态；薄壳化前置在计划里指错了文件）
- 客观在场：`number_utils.py:5` import + parse_finite_float/int 全量 delegate→`core.shared.strict_parse`，半截迁移不对称。授权 CSV ABSENT → planned(owner-pending)。
- **本轮新发现（计划失准）**：簇文档/A4 称薄壳化前置须「先重写 `regression_ortools_warmstart_failure_contract.py:136` 的 monkeypatch」——回盘该 monkeypatch 是给 **ortools/cp_model**（:81-84/:109/:124）的，**与 number_utils 无关**。R29 真正的 delegation 续命/身份测试是 `tests/regression_number_utils_facade_delegates_strict_parse.py`（:23-51 monkeypatch number_utils.parse_required_* 成 fake 再断言 parse_finite_* delegate）。**若 R29 走 B 收敛/薄壳化，须先重写这份测试，warmstart:136 是误指**。KEEP 路只补注释，不阻塞。本 Layer 不给终态。

---

## 编排矛盾（本轮新发现）
- **R50 跨 Batch 与「同 diff」自相矛盾**：R50 dossier §5/§12 称「R50 在 Batch-6、R51 在 Batch-7」，但同文件 dispatch_rules.py 三债（R49:25/R51:28/R50:112）A2 判「必须同一原子 diff 避免行号互撞」。跨 Batch 拆 = 违同 diff 约束。须统一编排为同批，或显式声明「R50 先 Batch-6 落地后 dispatch_rules 稳定，R49/R51 Batch-7 再按符号名重盘」二选一，禁两种叙事并存。

## 行号校正（不撼结论）
- `_resolve_strategy` 实测 schedule_params.py **:265**（R51/R33 dossier 写 :266，差 1）。
- config_contract degradation 死保实测 **:15**（准）。
