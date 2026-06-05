# Verdict V1 — Layer3 回炉争议裁定（争议组 V1）

> 裁定 agent：只读不改。所有行号经当前代码 rg 回盘（HEAD c2aa7501），不信旧值。
> 真实路径以 `_layer2_residual.md` 权威表为准。
> 争议组：①EXEC-FACT 串行序 / ⑤persistence_errors:13 归属 / ⑥STRICT 4 处分类失真。
> 凡属 owner 业务裁断者，给选项+建议+【待owner】标记，不给终态修法、不分配执行批次。

---

## 争议① EXEC-FACT provider 三债串行序拍定（R15 / R19 / R13）

### 矛盾来源
- 簇 A3（r1-LB explode 正文）自身就乱：第 63 行写 `R15→R13→R19`，第 77 行又自承「簇 A3 写 R15→R19→R13」与「R13 dossier §5 写 R13→R19→R15」两处矛盾未拍。
- R13 dossier §5（:66/:67/:145）主张 **R13 先删（收缩文件）→ R19 → R15**。
- R15 dossier §5（:69/:70/:75）主张 **R15 先于所有 B11/B13 兄弟**（R15→R13、R15→R19）。
- R19 dossier §5（:52/:53）引「Phase1 边 R15→R13」「R15 先」，与 R15 dossier 一致、与 R13 dossier 对立。

### 当前代码物理回盘（execution_fact_provider.py，HEAD c2aa7501，共 173 行）
| 债 | 改动符号 | 实测行号（自上而下） |
|---|---|---|
| R13 | `last_event_schedule_*` 字段定义 + 赋值 | dataclass 定义 **:23-24**、`_fact_from_state` 返回块赋值 **:56-57**（**文件最上**） |
| R19 | `_positive_op_ids` def | **:70**-82（文件中段） |
| R15 | `_parse_execution_time` def | **:85**-95（文件最下；调用点 :52/53 在 `_fact_from_state` 返回块内） |

行号铁序：`23-24` < `52-57` < `70` < `85-95`，三符号互不重叠（dataclass 字段 vs 两个独立函数体），R13 与 R15/R19 不撞 dict 键。

### 【裁定】采纳 **R15 → R19 → R13**（先改语义/最下方 → 中段 → 最后删死物/最上方）。R13 dossier「R13 先」判负。

物理依据（删上方位移下方锚点）：
- R13 删 :23-24 + :56-57 横跨 dataclass 与 `_fact_from_state` 返回块，会让其下**所有**锚点（R19:70、R15:85）整体上移，若 R13 先动则 R19/R15 必须按未知新行号重 rg——制造二次漂移。
- R15 改 :85-95 在文件最末段，改它**不位移任何下游桶**；R19 改 :70-82 仅位移其下的 R15。先改最下方、再中段、最后删最上方 = 后改者锚点永不被先改者冲掉。
- 工程闸门加固：R15 owner_pending=true（收口语义未裁），R19 owner_pending=true（repo 落点未裁）。两者必须**同批 owner 裁断**，否则先落者 Edit 会漂移另一方锚点（_layer3_explosion.md #1 已点名）。R13 owner_pending=false 但「死」定性被 5 处测试读活推翻（_layer1_corrections.md §A R13），须升级 owner 二次确认后才删，天然殿后最稳。

### 【证据】file:line（rg 回盘）
- R13：`core/services/scheduler/execution_fact_provider.py:23-24`（字段定义）、`:56-57`（赋值）。
- R19：`core/services/scheduler/execution_fact_provider.py:70`（`_positive_op_ids` def）、`:145`（调用点）。
- R15：`core/services/scheduler/execution_fact_provider.py:85-95`（`_parse_execution_time` def，含 `:92 strptime`、`:88 .replace`）；调用点 `:52-53`（`_fact_from_state` 返回块）。
- R15 活债佐证：`git log -- execution_fact_provider.py` 末三提交（70a3a032/afcf9e7e/a0cfa3e7）未触本函数体；坏值 `return None` 静默仍在 = 真 P4 残留（_layer1_corrections.md §A R15）。
- 软禁区 raise（不得削弱）：provider `:110`/`:113`/`:142`/`:147` loud raise（R13 dossier §9）。

### 对批次计划的影响
- **串行链固定**：B06(R15) → B13(R19) → B11(R13)，每步落地后**强制重 rg** 下方锚点。
- **owner 闸门**：R15+R19 双 owner_pending 必须**同一 owner 决议批**裁断（R15 取 None/raise 收口语义；R19 取 repo 落点），裁前不进批次。R13 升级一次 owner 确认「字段无未来消费」后再选路 A（直删）/路 B（保留+注释）。
- **禁区（按符号）**：R15 保 `if not text: return None` 空值短路在 provider 本地（禁整体 delegate 把合法空时间炸 raise）；R19 canonical 必保 `sorted`（指纹承重）；R13 不碰 provider `:110/:113/:142/:147` raise，且 **R13 不碰 repo:399/401**（属 R18，解除 R13↔R18 强耦合，_layer1_corrections.md §B）。
- **迁移序**（R13 内部）：先迁 `scope_read_contract`（契约源头）→ `reschedule:196` → 最后删生产字段。

---

## 争议⑤ schedule_persistence_errors.py:13 `_positive_int` 归属拍定

### 矛盾来源
- 权威表 _layer2_residual.md §37 把它列为「**Optional 5 处** 收编面之一……**第 3 份未收编，`int(value or 0)` 不 wrap，owner 复核**」。
- _layer3_explosion.md R09 行（:42）写「persistence_errors.py:13 归 **R04 禁区**不归 R09 收编面（矛盾指令，见回炉）」。
- 即：到底归 R09 收编面（Optional 副本，可收口到 scope.py:9）还是归 R04 禁区（独立 run/解析器族，不动）。

### 当前代码回盘（core/services/scheduler/run/schedule_persistence_errors.py，共 150 行）
```
:13  def _positive_int(value: Any) -> Optional[int]:
:14      try:
:15          number = int(value or 0)
:16      except (TypeError, ValueError):
:17          return None
:18      return number if number > 0 else None
```
- 签名 `-> Optional[int]`（**返 None，非 raise，非塌 0**），语义 = 宽松归一化（`value or 0` 使 `5.9→int→5`、`True→1`；坏值/<=0→None）。
- module-private：`__all__`（:150）只导出 `missing_internal_resource_samples` / `raise_no_actionable_schedule_error`，**不导出 `_positive_int`**。
- 调用者语义（仅本文件内 3 处）：`:24`（`_normalize_positive_ids` 过滤展示 op_id 集合）、`:56`（`seq` 展示样本）、`:77`（按 op id 匹配展示样本）。喂的全是 **「无可保存结果」错误样本展示侧**（`missing_internal_resource_samples` / `raise_no_actionable_schedule_error` 的 details 文案），**不是写库主键、不经 request.args 用户输入路径**。

### 【裁定】归 **R04 禁区族（独立解析器副本），不归 R09 收编面**。但**标【待owner】二次确认收编与否**（业务裁断）。
- 客观事实：它确是「`_positive_int` 同名 family」的第 N 份内联副本（与 R09 的 A/B 宽松副本同形），技术上**可**收口到 `operation_execution_scope.py:9`——但 scope.py:9 是 STRICT（坏值 raise），而本处坏值返 None，**直接收口会把展示侧容错炸成 raise（静默放宽的反向——制造假错）**，与 R09 的「静默放宽」风险镜像对称。
- 关键差异判 R04：调用语义纯展示容错、零用户输入路径、module-private、坏值返 None 不影响写库决策（写库门禁在别处）——**风险面与 R09 收编面（C 路经 request.args schedule_id 误命中相邻行）不同量级**。R09 收编面的危害是「错任务静默写库」，本处最坏只是「错误样本展示里少/错一个 op_id 标签」。
- 故拍：**不纳入 R09 收编串行链**（避免被 R09 的「字节对齐 A/B」逻辑顺手收口到 STRICT sink），归 R04 独立处置，保持现状。

### owner 选项（业务裁断，【待owner】）
- **选项 A（建议，默认）**：保持现状 `-> Optional[int]` 不动，补「我是故意的：展示侧容错，坏值返 None 不报错」注释 + 钉 parity（`5.9→5`、`True→1`、坏值→None）。理由：展示侧 loud raise 反而会让「无可保存结果」错误页因脏 seq 而二次崩。
- **选项 B**：若 owner 要全局统一正整数解析语义，则须**新建展示侧 Optional 收口符号**（非复用 scope.py:9 STRICT），三处指向它——但这是「序列/展示容错」语义，与 scope.py:9「写库严格校验」语义不同，**不应混为一个 sink**。
- 不论 A/B：**禁直接收口到 `operation_execution_scope.py:9`**（语义反转风险）。

### 对批次计划的影响
- 从 R09 收编面**摘除** schedule_persistence_errors.py:13，R09 收编串行链只剩 _layer2_residual.md §37 标的 2 个真未收编 Optional 副本（`resource_dispatch_execution_service.py:24`、`scheduler_resource_dispatch_execution.py viewmodel:33`）。
- 本债独立归 R04 桶，owner 闸门：是否收编 = owner 二次裁；裁前保持现状仅可补注释。

---

## 争议⑥ STRICT 4 处分类失真复核（scope:9 / public_errors:167 / auto_assign:114 / feedback_support:161）

### 复核口径
_layer2_residual.md §36 + R09 dossier（:48/:122/:163）把这 4 处统称「`-> int`，**loud raise**，一字不碰（STRICT 4）」。逐处 rg 验签名与函数体活性如下。

### 逐处回盘
| # | file:line | 签名 | 函数体真实行为 | 真 STRICT(loud raise)？ |
|---|---|---|---|---|
| 1 | `core/models/operation_execution_scope.py:9` `parse_positive_execution_int(value, field) -> int` | bool→raise(:11)、非数字→raise(:17)、<=0→raise(:20) | **是，真 loud raise 活体** ✅ |
| 2 | `core/models/scheduler_public_errors.py:167` `_positive_int(value) -> int` | `try int(value or 0) except: return 0`(:172)；`return number if >0 else 0`(:173) | **否，坏值/<=0 静默塌 0，不 raise** ❌ 分类错 |
| 3 | `core/services/scheduler/run/auto_assign_resource_errors.py:114` `_positive_int(value) -> int` | 与 #2 字节级相同：`except: return 0`；`>0 else 0` | **否，坏值/<=0 静默塌 0，不 raise** ❌ 分类错 |
| 4 | `core/services/scheduler/operation_execution_feedback_support.py:161` `_positive_int(value, field) -> int` | `_parse_int` 坏→raise(:165 `_invalid_field_value`)、<=0→raise(:167) | **是，真 loud raise 活体** ✅ |

### 【裁定】
- **#1 scope.py:9 与 #4 feedback_support:161 = 真 STRICT 活体，分类正确，一字不碰。** 二者均 loud raise，是写库/写入门禁，确属灵魂线守卫。
- **#2 public_errors:167 与 #3 auto_assign:114 分类失真**：签名虽 `-> int`，但函数体是「坏值/非正**静默返回 0**」，**根本不是 loud raise**，更不是写入闸门。R09 dossier 把 public_errors:167 写成「`_positive_int→raise`、写入闸门」（:48/:122/:163）= **与当前代码矛盾的失真**，须纠正。
- 调用语义佐证「非写入闸门」：public_errors `make_public_error` 内 `op_id_number=_positive_int(op_id); if op_id_number>0: item["op_id"]=...`（:204/:207 区）——展示侧错误对象组装，塌 0 后被 `>0` 守卫挡掉（不填键）；auto_assign `:85` 喂展示 seq、`:180 _operation_sequence` 喂排序键。纯**展示/排序容错**，零用户输入写库路径。

### 这对「一字不碰」结论的修正
- #2/#3 标签错（不是 STRICT），但**最终处置仍是「不纳入 R09 收编面、保持现状」**——因为它们是展示侧静默容错，收口到 scope.py:9 STRICT 会把展示路径炸 raise（与⑤同型语义反转）。
- 即：**「STRICT 4 处一字不碰」这条禁令在执行效果上对 #2/#3 仍成立（不碰）**，但**理由从「它们是 loud raise 灵魂线」改为「它们是展示侧静默容错、收口会反向放宽/制造假错」**。R09 收编面的禁区注释文案须据此改写，不得继续宣称 public_errors:167 是 raise。
- 真正的 loud-raise 灵魂线只有 #1 与 #4（外加 R09 dossier:48 另列的 `operation_execution_event_repo.py:100 _required_positive_int→raise`，本组未点名，未复核签名）。

### 对批次计划的影响
- **禁区注释纠偏**：R09 收编面禁区清单里 `scheduler_public_errors.py:167` 与 `auto_assign_resource_errors.py:114` 的「→raise/写入闸门」描述**必须改写**为「展示侧静默塌 0 容错，禁收口到 STRICT sink（反向放宽风险），保持现状」。
- **真 STRICT 禁区收窄**：loud-raise「一字不碰」硬禁区确认为 `scope.py:9` + `feedback_support:161`（+ 未复核的 repo:100）。
- 不新增执行批次：#2/#3 处置与⑤同族（owner 若要统一展示侧解析，须建独立 Optional/容错 sink，禁混入 scope.py:9）。【待owner】是否统一展示侧解析语义。

---

## 对批次计划的影响汇总（禁区 / 前置 / owner 闸门）

1. **EXEC-FACT 串行链定为 R15 → R19 → R13**（B06→B13→B11），每步重 rg；R13 dossier「R13 先」作废。R15+R19 双 owner_pending 同批裁断，R13 殿后并升一次 owner 确认。
2. **R13↔R18 解耦确认**：R13 只动 provider 文件，不碰 repo:399/401（属 R18）。
3. **R09 收编面摘除 2 项**：① schedule_persistence_errors.py:13（归 R04 禁区，争议⑤）；② 连带把 public_errors:167 / auto_assign:114 的「STRICT/raise」误标纠正为「展示侧静默塌 0 容错」（争议⑥）。R09 收编串行链真正待收编的 Optional 副本只剩 resource_dispatch_execution_service.py:24 + scheduler_resource_dispatch_execution.py viewmodel:33。
4. **loud-raise 硬禁区（一字不碰）收窄为**：`operation_execution_scope.py:9` + `operation_execution_feedback_support.py:161`（+ 未复核 repo:100）。public_errors:167 / auto_assign:114 仍「不碰」但理由改为「展示侧容错，禁收口 STRICT sink」。
5. **禁区注释纠偏（文档侧）**：R09 收编面禁区文案凡称 `scheduler_public_errors.py:167 _positive_int→raise/写入闸门` 处全部改写——当前代码该函数返 0 不 raise。
6. **owner 闸门清单（本组）**：
   - 【待owner】R15 收口语义（坏值 None 保留 / loud raise / 可观测降级标记）+ R19 repo 落点（core/models 下沉 vs repo 私有保留）——同批裁。
   - 【待owner】R13 字段是否真无未来消费（选路 A 直删 / 路 B 保留+注释）。
   - 【待owner】schedule_persistence_errors.py:13 是否收编（建议否，保持现状+注释）。
   - 【待owner】展示侧解析语义（public_errors:167 / auto_assign:114 / persistence:13）是否统一到独立 Optional sink（禁混入 scope.py:9）。
7. **分层 0 违规复核**：本组涉及文件 import 均为 `core.services→core.models/data.repositories` 合法层序（provider :7-11、scope.py、public_errors）；R19 若 repo 收 service 则 data→service 越层（已在 R19 dossier §6 标禁，本裁定不触）。

---

## 逐条「争议→裁定一句话」
- **①EXEC-FACT 串行序**：采纳 **R15→R19→R13**（先改最下方语义、中段、最后删最上方死字段，删上方位移下方锚点；R15 改 :85-95 不位移任何人，R13 删 :23-24/:56-57 位移全员）；R13 dossier「R13 先」判负。
- **⑤persistence_errors:13**：归 **R04 禁区**（独立展示侧 Optional 容错副本，`-> Optional[int]` 返 None、module-private、零用户输入写库路径），**不归 R09 收编面**；禁收口到 STRICT scope.py:9；是否统一【待owner】。
- **⑥STRICT 4 处**：scope.py:9 与 feedback_support:161 = **真 loud-raise 活体，分类正确一字不碰**；public_errors:167 与 auto_assign:114 = **分类失真**（签名 `-> int` 但坏值/<=0 静默塌 0、非 raise、非写入闸门，是展示侧容错），处置仍「不碰」但禁区理由须纠偏。
