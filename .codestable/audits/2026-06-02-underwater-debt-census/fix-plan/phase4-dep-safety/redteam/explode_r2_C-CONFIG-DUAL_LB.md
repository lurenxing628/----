# 逐簇爆炸对抗 r2 · C-CONFIG-DUAL · 主透镜【承重误删】

> skeptic 第2轮，只读不改。默认怀疑：多数维度存疑即标红，不放过「测试绿但护栏已破」的静默失效。
> 回盘日 2026-06-05，行号 rg 实测回盘（不信旧值）。成员：LB07 R47 R71 R45 R48 R26 R31。

## 回盘事实底座（本轮独立 rg，权威）

- **LB07 两栈字段计数**：model `schedule_config_runtime_snapshot.py:8-39` = **30**，service `config/config_snapshot.py:25-56` = **30**，`diff` 去缩进后 **byte-for-byte 一致**。dossier 早期"27"字样是误差，簇文档"30"为准，当前 parity 成立、零漂移。
- **承重禁区行（coercion.py 实测）**：置零 `:470`；loud raise 族 `:72`(MISSING_POLICY_ERROR)/`:153`/`:165`/`:208`/`:220`/`:258`/`:302`/`:385`(TypeError)。registry "73-80" 旧值作废，**禁区按符号语义认定不按行号**。
- **R47 死参真相（关键纠偏）**：`raw_value: Any` 形参在 coercion 出现 **4 次**：`:88`(`_record_blank_choice_degradation`=死)、`:106`(`_record_invalid_choice_degradation`=活，:116/:119 读)、`:124`(`_choice_with_degradation`=活，:150/:166 读)、`:182`(`_yes_no_with_degradation`=活，:203/:220 读)。R47 只删 :88 死参 + 其 blank 分支两实参(:159/:214)。service 对称(:68 死 / :86/:128/:179 活)。
- **R71 三 helper**：model coercion `:31`/`:49`、read `:68`；service field_coercion `:45`/`:29`、snapshot `:153`。`rg` 全 tests/ 三 helper **零命中** → 改任一函数体测试不红 = **护栏未建即破**。收口方向 `core.services→core.models` 合法（config/ 已有 config_page_outcome.py/config_field_spec.py import core.models），model 反向 import core.services **NONE** 不成环。
- **R45/R48**：config_adapter.py 27 行，`rg` 生产/测试零符号引用，唯一 sp06:15 路径成员。
- **R31/R33**：WRITE_INTERNAL_ONLY 仅 3 处(shared :9 源 / common facade :11 import / :29 __all__)，common facade 37 行存在，matrix_contract:18 经 common facade import。
- **Q3 迁移耦合**：本簇符号与 v18/v19 DB CHECK **零耦合**，Q3 不适用。

---

## 逐成员判定

### 🟡 LB07（承重根 / load_bearing=true / owner_pending）
**判定：黄（候选修法本身安全，但 owner 裁断门 + parity 前置缺位是硬条件）。**
- Q1：候选修法严格限「补『我是故意的』注释 + 扩 parity」，零删/统一/透传，承重不对称被钉非被抹 → 不红。
- **条件**：① owner 须先裁「永久双栈仅 parity 锁步」vs「R71 物理收敛」；注释+扩 parity 在任一裁断下成立可先行（Batch-1 ROOT）。② 注释落点对侧路径互填，禁粘任何"反向文案"。③ **禁区行 :470/:72/:153/... 只补注释**，R47/R71 改 coercion 后须按符号重新回盘（行号会漂）。
- 灾难链（若违条件）：以"统一/DRY/简化"名义删一栈或合并漏字段 → 非 strict 路坏/缺数据静默兜默认 → 算法用旧默认值、配置页存新值 → 排产权重/降级判定**无声分叉污染正确性**（灵魂线）。**双实现是分层被迫护栏（算法层不能 import 服务层，已 rg 实证），DRY 不可直接套**。

### 🔴 R71（三 helper 双栈 / owner_pending）— 本簇最危静默爆点
**判定：红（护栏当前为空，落点全在 LB07 承重文件，序错即静默漂移）。**
- 灾难链：**当前三 helper 零 parity 守卫（tests/ 零命中已实证）**。若在 LB07 注释+helper 级 parity **未落地前**就动 R71 物理收敛（删 service 副本改 import）→ 锁步守卫缺位 → 日后 LLM 单边改 `_coerce_degradation_event` 的 `except:count=1` / `_float_matches_choice` 的 `<=1e-9` 容差 / `_normalize_valid_texts` 的保序去重 → 算法侧(model)与配置页侧(service)对同一字段合法值/降级口径**静默分叉** → 排产被污染且**无任何报错**（灵魂线）。
- 修正建议（前置/顺序/禁区）：① **硬前置 = LB07 注释 + 扩 spec_sync_contract 覆盖三 helper 逐分支真值表（空 choices→True、1e-9 inclusive、非数字串 except→continue、非 dict→None、count `max(1,int(..or 1))`、tuple 保序）四元断言(返回值+是否 raise+field+degradation 计数)全绿**，此为收敛准入门。② owner 裁断门：物理收敛 vs 仅 parity 待 B03 裁，未裁不分配执行批次。③ 禁区行 coercion:470/:72…、read.py:10(read_runtime_cfg_raw_value 承重入口)/:33(raise from exc) 只在三 helper 函数体内动，**禁顺手把 `except Exception: continue` 改 loud raise**（改行为=另立债，灵魂线）。④ 与 R47 同批、改后统一回盘。

### 🔴 R47（死参 raw_value / 终态可给）— 误删活参陷阱
**判定：红（dossier "6 编辑点"口径会诱导误删 4 处活 raw_value 形参）。**
- 灾难链：`raw_value` 在 **4 个函数**都有形参，仅 `_record_blank_choice_degradation`(:88) 是死的；`_record_invalid_choice_degradation`(:106)/`_choice_with_degradation`(:124)/`_yes_no_with_degradation`(:182) 全是**活参**（:116/:119/:150/:166/:203/:220 实读）。若执行者按"删 raw_value 死参"模糊指令一锅端 → 误删活参 → `_choice_with_degradation` 拿不到 raw_value 构 text/降级消息 → **配置校验静默错算**（且 :220 loud raise 行物理紧邻 :214 实参，删时极易误伤 raise）。
- 修正建议：① **只删 6 行**：model :88 形参 + :159/:214 实参，service :68 形参 + :158/:211 实参，逐行核对在 `if text==""` 非 strict 分支内、与 :153/:208 strict raise 语义隔离。② **绝不删 :106/:124/:182 活形参、不删 `_record_invalid_choice_degradation`、不删 `collector.add(blank_required)` 降级记录**（删后者=可观测降级变静默，踩灵魂线，且 regression 红）。③ 与 R71 同批先删参后收敛。④ parity 守门测试真实名 `..._emit_blank_required`(@:210/:107，非 dossier 误写 `_emit_ln`)，取基线用真名否则匹配不到误判无守门。⑤ load_bearing=false 但毗邻 LB07，须在 LB07 注释 Batch-1 后动。

### 🟢 R45 ≡ R48（config_adapter 整文件删，单提交）
**判定：绿（纯死叶子，零承重耦合，误删响亮非静默）。**
- Q1/Q9：config_adapter.py 非承重、无禁区行、`load_bearing=false`；27 行生产/测试零符号引用（rg 实证）。registry 把 schedule_params.py 误标 same_file 是假边（不同文件，R45 删壳不进 schedule_params.py），zero 碰撞。
- 唯一约束：**单提交整删 + 同提交退 sp06:15 路径成员**，漏退 → `path.read_text` 抛 FileNotFoundError → sp06 红（**响亮非静默**，CI 即捕）。`:22-23` 吞异常随整文件删除消除，**不改写为 raise**（无消费方，超范围）。与双栈收敛正交，Batch-1 后任意点可先落。

### 🟢 R31（WRITE_INTERNAL_ONLY 源定义删，跨簇绑 R33）
**判定：绿（死常量直删，唯一序陷阱是 loud 非静默）。**
- Q1：仅 3 处散布，源 :9 零生产/零测试消费（FieldPolicy 16 处无一用它、compat_parse :165/:188/:208 只比 WRITE_OPTIONAL）。非承重、无禁区。
- 唯一序约束：**R33 删 common facade(:11/:29) 不晚于 R31 删 shared 源 :9**，反序 → facade :11 残留 `import WRITE_INTERNAL_ONLY` **loud ImportError**（CI 拦截，非静默）。禁顺手动 :6/:7/:8 三个活常量（16 FieldPolicy 在用，删=静默改解析语义）。

### 🟡 R26（5 顶层 shim 删 / owner_pending）— 晚序 facade
**判定：黄（前置门最重，序错则他桶测试红；本体误删响亮非静默）。**
- Q1/Q6：5 shim 纯转出非承重、无禁区，is-identity 解析同对象，不收口（搬入口到已存在深路径，非新建模块，铁律 5 合规）。误删只响亮 ImportError。
- **条件（硬前置，序错=测试红）**：① **晚于 B05(R29)/B06(R33)/B09(R52) 三桶收敛**（PHASE0 §10.2 facade 删晚于收敛），先删则他桶经老路径测试红。② **软前置 R71 先**（R26 shim 转出目标正是 R71 编辑的深 config/config_snapshot.py，让 R71 parity 落地再搬入口；Batch-14 vs B03 天然满足）。③ 迁 **2 离线消费者**(tools/capture_networkx_phase0_baseline.py:17 + audit/2026-03/20260316_schedule_audit_probes.py:87，活引用，普查"0 生产"被推翻)否则离线 ImportError，须纳入删前手动验证清单。④ 重指 **53 文件 / ~93 处 import**（registry 旧值 71 会漏 ~22 处悬空，以 93 为准）。⑤ 改 SP05 的 **BEHAVIOR_* 两字典(:20-31/:33-82) + 文档树(:640-658)**，非 STRONG_*（registry 误标）。owner 须裁 SP05 冻结解冻许可。

---

## 漏项（本轮新发现，没被计划充分覆盖）

1. **【R47 高危漏项】dossier "6 编辑点"口径未在主指令层强调"raw_value 形参在 4 函数共存、3 活 1 死"**——计划只说"删两栈对称死参"，执行者极易把 :106/:124/:182 活形参一并删，造成配置校验静默错算 + 误伤紧邻 :220 loud raise。须在批次指令显式列出"只动 :88/:68 死参函数 + blank 分支两实参，禁触 invalid/choice/yes_no 三活函数"。
2. **【R71 护栏当前为零的时间窗】**计划把 parity 列为 R71 前置，但未点明**当前状态下三 helper 已经零守卫**——即在 LB07/R71 动手前的整个窗口里，任何其它债（LB04/R33 改 coercion 上半部）位移 helper 行号或有人顺手改函数体都**无测试拦截**。建议 Batch-1 扩 parity 不仅为 R71 铺路，更应作为**簇内一切碰 coercion.py 动作的前置安全网**提前落。
3. **【R47 实参点比 dossier 多】**rg 实测 model 含 :173/:225 等额外 `raw_value=raw_value`（属 invalid/yes_no 活调用），dossier 只列 :159/:214 两 blank 实参——须明确这些额外实参是活的不在删除面，回盘清单别误纳。
4. **【R26 离线脚本 CI 盲区】**2 离线消费者若 CI 不跑，删 shim 后 ImportError 延迟暴露——须把这两脚本写进删前手动 gate，否则"测试全绿"是假绿。
