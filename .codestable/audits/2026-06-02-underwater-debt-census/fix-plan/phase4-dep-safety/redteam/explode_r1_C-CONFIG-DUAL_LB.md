# 逐簇爆炸对抗 r1 · C-CONFIG-DUAL · 主透镜【承重误删】

> skeptic r1 / 只读不改 / 默认怀疑。回盘日 2026-06-05,cwd=/Users/lurenxing/Documents/GitHub/----。
> 成员债 7:LB07 R47 R71 R45 R48 R26 R31。主透镜 Q1 承重误删,六质问点全过。
> 本轮独立 rg 全量回盘,行号不信旧值。结论:**1 黄(R47 删参误伤面被 dossier 低估)+ 6 绿/条件绿,无新增红**;但抓出 1 个全簇执行级漏项(R47 字面量盲删陷阱)+ 1 个排序前置确认。

---

## 回盘锚点(本轮独立 rg,权威以此为准)

| 事实 | 回盘结果 | 来源 |
|---|---|---|
| LB07 双栈字段计数 | model `snapshot.py:8-39`=**30** / service `config_snapshot.py:25-56`=**30**,parity 成立零漂移 | grep -cE |
| LB07 承重置零 | model `coercion.py:470` ✅命中 / service helper `config_snapshot.py:89` 调用 `:295/:450` ✅ | rg |
| LB07 loud raise(灵魂线) | `coercion.py:71-72`(MISSING_POLICY)/`:152-153`/`:207-208`/`:220`/`:258`/`:302` 全命中;service 对称 `field_coercion.py:114/156/205/217/255/299` | rg |
| 非strict 降级 | `coercion.py:434` `MISSING_POLICY_FALLBACK_WITH_DEGRADATION if not strict`=已设计可观测降级 | rg |
| R71 三 helper 双栈 | model coercion `:31/:49` + read `:68`;service field_coercion `:45/:29` + snapshot `:153`,零漂移 | rg |
| **parity 守卫缺口** | 三 helper 名在 `tests/` **零命中** → 删/改任一 helper 体不会让任何测试变红,LB07 锁步守卫缺位**实证在场** | rg tests/ |
| R71 收口方向 | service 当前**未** import `core.models.schedule_config_runtime`(R71 确未动);model 栈**不**反向 import core.services → 收敛 `core.services→core.models` 合法、不成环 | rg(双向皆空) |
| R45/R48 | config_adapter.py **27 行**,生产零引用(全仓除自身仅 sp06:15 路径成员),sp06 `:73 path.read_text` 漏退=loud FileNotFoundError | wc/rg |
| R31 | `WRITE_INTERNAL_ONLY` 仅 3 命中:shared 源 `:9` / common facade `:11`(import)/`:29`(__all__),零消费 | rg |
| R26 双 config_snapshot | 顶层 shim 199B vs 深 17655B = **不同物理文件**(假碰撞坐实);2 离线消费者活引用 `tools/...:17`+`audit/...:87` 坐实 | ls/rg |
| R26 前置 facade | `core/services/common/{number_utils,value_policies}.py` **仍在**=R29/R33 未收敛 → R26 晚序硬约束成立 | ls |

---

## 逐成员判定

### 🟡 R47 — 删死参 raw_value【条件绿,但 dossier 误伤面低估,须升执行纪律】
**判定黄(非红):修法本体正确(死参真死),但 dossier 字段1/字段4 只列了 2 个死实参 `:159/:214`(model)、`:158/:211`(service),漏报了同函数体内混居的活参。**

实测 `raw_value=raw_value` 在 model 栈出现 **4 次**(`:159/:173/:214/:225`)、service 栈 **4 次**(`:158/:170/:211/:222`):
- `:159/:214`(model)、`:158/:211`(service)→ `_record_blank_choice_degradation`(**死参,该删**,函数体 message 只插 `{label}/{fallback}`、sample=None,从不读 raw_value)。
- `:173/:225`(model)、`:170/:222`(service)→ `_record_invalid_choice_degradation`(**活参,禁删**)。已 rg 函数体确认:`message=f"...当前值：{raw_value}..."` + `sample=str(raw_value or "")` **两处读 raw_value**。

**灾难链(若按字面量盲删):** 执行者照 dossier「删 raw_value=raw_value」用字面量批量删 → 误删 `:173/:225/:170/:222` 的活参 → `_record_invalid_choice_degradation` 调用缺 raw_value → **TypeError(loud,被现成 regression 抓,非静默)** 或若同步删形参则 invalid_choice 降级消息丢失采样值=可观测降级降质(轻静默)。两者都踩灵魂线边缘。

**修正建议(执行纪律,必前置):**
1. R47 删参**只按调用函数名认定**(`_record_blank_choice_degradation` 的 6 处:2 形参+4 死实参),**严禁按 `raw_value=raw_value` 字面量盲删** —— 该字面量在同函数 `_choice_with_degradation`/`_yes_no_with_degradation` 体内与活参 1:1 混居。
2. 死实参精确清单:model 删形参 `:88` + 实参 `:159/:214`;service 删形参 `:68` + 实参 `:158/:211`。**保留** model `:173/:225`、service `:170/:222`(invalid 活参)。
3. 行号在 R71/LB04 改 coercion 上半部后必漂,**R47+R71 同批改后统一回盘**(R71 删 service 三 helper :29/:45 会上移 `_record_blank`:63 及其下全部 R47 调用点)。
4. 禁区行隔离 OK:6 个死参编辑点全在 `if text==""` 非strict 分支,与紧邻 loud raise(coercion `:153/:208`、service `:156/:205`)物理相邻语义隔离,删时逐行核对勿误伤 raise。

### 🟢 LB07 — 仅补注释+扩 parity【承重前置,安全】
30/30 字段 parity 成立、零漂移;候选修法纯增量(两栈 @dataclass 上方注释 + 扩 spec_sync 覆盖三 helper),零删除/统一/透传。承重禁区(`coercion:470` 置零 / `:71-72`+族 loud raise / 30 字段锁步表 / `read.py:10/:33`)只补注释。分层零新增 import,0 AST 违规。owner_pending 仅标不给终态。**门控硬不降:LB07 注释+helper-parity 必须先于 R71 物理收敛/R47 删参。** Q1-Q6 全绿。

### 🟢/⏸ R71 — service 反向复用 model 三 helper【收敛方向安全,待 owner 裁,前置门齐】
收口收到**已存在**的 model 三符号(coercion `:31/:49`、read `:68`),`core.services→core.models` 合法下行边、不成环(双向 rg 实证)。禁止新建第三模块。三 helper 现有 `except Exception:continue`/`count=1`/非dict→None 是**已存在行为,parity 须逐字保真,禁顺手改 loud raise**(改了=反转 静默→loud 方向,排产侧降级读取从「静默丢弃」变「崩」)。前置:parity 守卫缺口实证在场(tests/ 零命中)→ 必须先扩 parity 再收敛。owner_pending 物理收敛待裁。Q2/Q3/Q5 绿。

### 🟢 R45 ≡ R48 — config_adapter 整文件删【单提交,最低风险一刀】
同一物理文件两视角,**合并单提交**整删 27 行 + 同提交退 sp06:15。生产零引用(rg 三重证:符号名+文件名字符串+SP05 排除)。`schedule_params.py` 是 `core/algorithms/greedy/` 同目录他文件(registry same_file 误标),删 adapter 零碰 LB07/R33/R51。删壳方向 algorithms→models 合法,只减边。唯一约束链=漏退 sp06:15 → `:73 read_text` loud FileNotFoundError(非静默)。owner_pending=false。与双栈收敛正交。Q1-Q6 全绿。

### 🟢 R31 — WRITE_INTERNAL_ONLY 源定义直删【条件绿:删序锁死】
三处零消费(16 FieldPolicy 无一赋值、compat_parse 三分支只比 WRITE_OPTIONAL)。**删序硬约束(唯一陷阱):R33 删 common facade `:11/:29` 须不晚于 R31 删 shared 源 `:9`**,否则 facade 残留 `import WRITE_INTERNAL_ONLY` → loud ImportError(CI 拦,非静默)。禁顺手动 `:6/:7/:8`(活常量,16 处在用)。删一行只减边,零越层。Q1-Q6 绿(条件=删序)。

### 🟢/⏸ R26 — 顶层 5 shim 删【Batch-14 全局最晚,前置最重,待 owner 裁】
纯转出零逻辑,误删只 loud ImportError(无静默炸点,honors 灵魂线)。**晚序硬前置已客观成立**:回盘 `common/{number_utils,value_policies}.py` 仍在=R29(B05)/R33(B06)未收敛 → R26 先删 shim 会让经老路径的桶测试红。普查「0 生产消费者」被推翻=2 离线活引用(tools:17/audit:87)须先迁否则 ImportError。R71 软前置(转出边非原子,不同物理文件不撞行号,R71 在早桶天然在前)。改 SP05 认准 **BEHAVIOR_*** 两字典(非 STRONG_*,registry 误标已纠);重指基数用 **93 处/53 文件**(非旧值 71,漏~22)。owner_pending 仅标。Q2-Q6 绿。

---

## 本轮新发现(漏项 / 计划未充分覆盖)

1. **【执行级·必补,本轮最大新发现】R47 死参与活参字面量混居 1:1。** dossier 字段1/4 只给 `_record_blank`(死)的 2 个死实参,未点名同函数体内 `_record_invalid_choice_degradation`(活)的 `raw_value=raw_value` 在 model `:173/:225`、service `:170/:222`。`raw_value=raw_value` 全栈各 4 处而非 2 处。计划须显式写「按调用函数名删,禁字面量盲删,保留 invalid 活参」否则执行者大概率误删活参(TypeError loud 或采样降质)。
2. **【前置确认】R26 晚序的客观依据已落实**(common facade 仍在=R29/R33 未收敛),非仅 owner 裁断;Batch-14 排期前须确认 B05/B06/B09 三桶真收敛后再放行,否则经老路径测试红。
3. **【回盘纪律】R71 删 service 三 helper(:29/:45/snapshot:153)会上移 `_record_blank`(:63)及其下全部 R47 调用点** → R47+R71 必须同批、改后统一回盘,任一单独先行会令对侧 file:line 全失效(计划 ASC-1 已覆盖,此处加证)。
