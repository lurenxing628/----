# 逐簇爆炸对抗 r2 · C-CONFIG-DUAL · 主透镜【灵魂线热路径+收口等价】

> skeptic 第2轮 只读不改 | 回盘日 2026-06-05 | 成员 [LB07,R47,R71,R45,R48,R26,R31]
> 主攻 Q4/Q5/Q6(灵魂线+收口等价),六质问点全过。行号全部 rg 当场回盘,不信旧值。
> 默认怀疑:多数维度存疑即红;放大「测试绿但护栏已破」的静默失效。

---

## 回盘真相源(本轮当场 rg,权威)

| 锚点 | 当前真实 file:line | 与计划 |
|---|---|---|
| LB07 model @dataclass | `core/models/schedule_config_runtime_snapshot.py:7/8` | ✅一致 |
| LB07 service @dataclass | `core/services/scheduler/config/config_snapshot.py:24/25` | ✅一致 |
| LB07 字段计数 | model :8-39 = **30** / service :25-56 = **30** | ✅parity 成立零漂移 |
| LB07 承重置零 | `coercion.py:470` `graph_downstream_weight=0 if critical==0 and impact==0 else ...` | ✅禁区 |
| LB07 loud raise | `coercion.py:72`(MISSING_POLICY_ERROR) / :153 / :208(strict 空值) / :165 :220 :258 :302 | ✅禁区,registry「:73-80」实测 :71-72,按符号认定 |
| R47 死参 def | model `coercion.py:83`(形参 :88) / service `config_field_coercion.py:63`(形参 :68) | ✅双栈对称 |
| R47 函数体 | model :91-98 / service :71-78 `collector.add(code="blank_required",sample=None)` **从不读 raw_value** | ✅死参坐实 |
| R47 调用点 | model :155→:159 / :210→:214 ; service :158 / :207→:211 | ✅6 编辑点 |
| R71 三 helper | `_float_matches_choice` coercion:31↔field_coercion:45 ; `_normalize_valid_texts` coercion:49↔:29 ; `_coerce_degradation_event` read:68↔config_snapshot:153 | ✅零漂移,byte-for-byte 已逐行核 |
| R71 收口方向 | service→models 合法边已存在(config_page_outcome.py/config_field_spec.py 已 import core.models);model 栈不反向 import services | ✅不成环 |
| R45/R48 | config_adapter.py **27 行**,符号 :10/:16/:26,except :22;生产零引用(唯一外部 sp06:15);sp06 read_text:73 | ✅死壳 |
| R31 | shared 源 :9 / common facade import :11 / __all__ :29(全 3 处);R33 facade 文件仍 37 行未删 | ✅一致 |
| R26 | SP05 BEHAVIOR_* 在 :20/:33(registry 误标 STRONG :15 坐实);2 离线消费者 tools:17/audit:87 活引用 | ✅verdict=depends |

---

## 逐成员判定(主透镜 Q4/Q5/Q6 为重)

### 🟡 LB07 [承重根/load_bearing/owner_pending] — 黄(条件:注释+helper-parity 必须先落且零结构)
- **判定依据**:本债修法=纯增量(补「我是故意的」注释 + 扩 parity),零删除零结构,Q1/Q2/Q3 全绿。Q4 灵魂线:`coercion:434` 非 strict 走 `MISSING_POLICY_FALLBACK_WITH_DEGRADATION` 带 DegradationCollector(:70)是**已设计可观测降级**,strict 走 `MISSING_POLICY_ERROR`(:406)loud raise——两路当前真实并存,补注释**不得**把非 strict 降级当 bug 删、**不得**把 raise 改兜底。
- **条件/灾难链(若违)**:若收敛阶段(R71)在 helper-parity 落地前抢跑 → 锁步守卫缺位 → 未来单边加字段 → 算法用旧默认值、配置页存新值 → **静默分叉污染排产权重/降级判定且无 loud 信号**(灵魂暗线)。修正:LB07 注释+三 helper 逐分支 parity(strict/非strict × 缺/坏/越界,断言 返回值+是否raise+ValidationError.field+degradation计数 四者全等)是 R71 物理收敛的硬准入门,Batch-1 ROOT 最先落。owner_pending 只标不给终态。

### 🟢 R47 [死参 raw_value 双栈/owner_pending=false] — 绿(条件:两栈对称同删 + 保 collector.add)
- **判定依据**:逐字核实 `_record_blank_choice_degradation` 函数体(model :91-98 / service :71-78)`sample=None`、消息只用 `label`/`fallback`,**确不读 raw_value**=纯签名收缩零行为面。Q5 不适用(直删非收口,无新旧分支)。Q6:0 测试直接 import 该私有函数,2 条现成 degradation regression 守门(注:dossier 方法名后缀 `_emit_ln` 系笔误,真名 `_emit_blank_required`,照旧名 pytest -k 会匹配不到)。
- **轻条件**:必两栈对称同删(单边删=造新锁步差,与 R71/LB07 收敛相悖);绝不误删 `collector.add(code="blank_required")`(=静默吞可观测降级,踩灵魂线);6 编辑点全在 `if text==""` 非strict 分支,与紧邻 loud raise(:153/:220 model;:156/:217 service)物理相邻语义隔离,删时逐行核不误伤。漏改某调用点=loud TypeError 非静默,低危。

### 🟡 R71 [三 helper 双栈/owner_pending] — 黄(条件:LB07 parity 先落 + 与 R47 同批 + 收口逐字保真)
- **判定依据**:三对 helper byte-for-byte 等价已逐行核(`_coerce_degradation_event` 双栈 :68-94 ↔ :153-179 完全相同)。收口方向 service→models 合法不成环(已核)。**但本簇主透镜最尖锐爆点在此**:Q5 收口等价——`_coerce_degradation_event` 非 dict → `return None`(:72/:156 静默丢弃)、三字段空 → None(:78/:163)、坏 count → except → count=1(:86/:171);`_float_matches_choice` 含非数字 choices → `except Exception: continue`(静默跳过)。
- **灾难链(若违)**:收敛/parity 时一旦「顺手」把 `return None` 改 loud raise 或动 `count` 下限 → 算法侧降级事件读取从「静默丢弃」突变「崩」、或两栈对 choices 匹配/count 口径分叉 → **静默→loud 方向反转 / 口径无声分叉污染排产**(灵魂线正中)。修正:R71 收敛**必须逐字保真**这些已存在吞错行为(parity 守卫钉死,不得"修好它",改 loud 需另立债);硬前置 LB07 注释+helper-parity 先 green;与 R47 同批同方向(批内先删死参后收敛,parity 比对更干净)。owner_pending 只标双栈去留待裁,不给物理收敛终态。

### 🟢 R45 ≡ R48 [config_adapter 整文件删/owner_pending=false] — 绿(单提交整删 + 同提交退 sp06:15)
- **判定依据**:同一物理文件两视角,非两次动作=一次整文件删。生产零引用三重证实(符号名+字符串 config_adapter+SP05 排除)。Q1-Q6 全绿:非承重(config_adapter.py 零 LB)、删只减 algorithms→models 合法边(Q2 绿)、无迁移耦合(`_snapshot_attr@schedule_params.py:59` 已 loud-raise 收敛后形态,Q3 绿)、非收口无 parity(Q5 不适用)。灵魂线:`except :22` 吞异常成 .error 随整文件删消失=净收益,无消费方不必改 raise。
- **唯一约束链**:漏退 sp06:15(NO_CFG_GET_TARGETS)→ read_text:73 抛 FileNotFoundError → sp06 红(**响亮非静默**,CI 立拦)。禁区:绝不顺手动 schedule_params.py(LB07/R33/R51 居所,registry same_file 误标,零碰撞)。

### 🟢 R31 [WRITE_INTERNAL_ONLY 死常量/owner_pending=false] — 绿(条件:R33 删 facade 不晚于 R31 删源)
- **判定依据**:三处 :9/:11/:29 零漂移,死常量零生产零测试消费(16 FieldPolicy 无一用、compat_parse 只比 WRITE_OPTIONAL)。Q1-Q6 全绿:非承重无禁区(只删 :9,禁动 :6/:7/:8 三活常量)、删一行不新增 import 只减边(Q2 绿)、非收口无 parity。
- **唯一陷阱(顺序)**:若 R31 抢先删 shared :9 而 R33 facade 未删 → common facade :11 残留 `import WRITE_INTERNAL_ONLY` → **loud ImportError**(非静默,CI 拦)。修正:R33(Batch-7)删 facade 整文件吸收 :11/:29 须不晚于 R31(Batch-14)删 :9 源。

### 🟡 R26 [顶层 5 shim/owner_pending] — 黄(条件:晚于 R29/R33/R52 收敛 + 迁 2 离线消费者 + 改 SP05 BEHAVIOR_*)
- **判定依据**:纯转出 shim,误删只 loud ImportError 不破不变量(Q4 灵魂线绿,honors loud-fail)。但 Q6 测试迁移序是真约束:**facade 删除必须晚于 B05(R29)/B06(R33)/B09(R52)收敛**(若其测试仍经 R26 顶层老路径,先删 shim 令其变红),Batch-14 全局最晚硬约束。R26↔R71 经"shim→深文件"转出边软相关(R71 先 R26 后,天然满足),不撞行号(顶层 shim vs 深 config/config_snapshot.py 不同文件)。
- **条件/灾难链**:① 漏迁 2 离线消费者(tools:17/audit:87 活引用)→ 删 shim 即 ImportError(离线才暴露,CI 若不跑这俩=延迟发现,须纳入删前手动验证清单);② 以 registry 旧值「71 处 import」为重指基数 → 漏 ~22 处悬空老路径(回盘 ~93 处/53 文件为准);③ 删 SP05 须改 BEHAVIOR_COMPAT_SYMBOLS(:20-31)+ PUBLIC(:33-82),**非** STRONG(:15-18,registry 误标)。owner_pending 待裁 SP05 解冻许可,只标不给终态。

---

## 漏项 / 本轮新发现(计划未充分覆盖的前置)

1. **R47 守门测试名笔误(执行陷阱,L1-F 节已抓但计划正文沿用旧名)**:dossier/计划字段引 `..._emit_ln`,真名 `..._emit_blank_required`(regression_config_validator_preset_degradation.py:210 / regression_schedule_config_snapshot_optional_guard.py:107)。执行者照旧名 `pytest -k ..._emit_ln` → **匹配不到测试 → 误判无守门即删**,删后两栈降级漂移无人拦。前置:取基线前先用真名 `_emit_blank_required` 确认测试在场。

2. **R71 收口的「保真」无硬测试钉(主透镜最尖锐残口)**:计划把 helper-parity 列为 R71 准入门,但当前 `regression_scheduler_config_spec_sync_contract.py` 只 pin spec 字段、**整个 tests/ 三 helper 名零命中**——即此刻删/改任一 helper 函数体(含把 `return None` 改 raise、动 count 下限)**不会让任何测试变红**。守卫缺口=客观在场。前置硬化:parity 必须显式断言「非dict→None」「三字段空→None」「坏count→count=1」「空choices→True」「except continue 静默跳过」这些**已存在吞错分支**逐字保真,而非只比正常值——否则 LB07 门是空门,R71 收敛仍可静默放宽灵魂线。

3. **R47/R71 同批后承重锚行须统一回盘**:R47 删 model :88/:159/:214(在三 helper :31/:49 之下,只推移下方符号不动 helper 定义行——已核 :83>:31/:49)、但 service :63 在三 helper :29/:45 之下同理;同批改后 coercion :470/:72/:153 等承重禁区行号必整组回盘,禁按本轮旧值。
