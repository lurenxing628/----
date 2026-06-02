## 14 · 第三方 drift 复核(三信源对账)

> 在两遍法(Pass-1 Agent 自由取证 A + Pass-2 NetworkX 调用图机械列嫌疑 B)之外,引入**第三个完全独立、不懂本项目架构的探测器** drift-analyzer 2.51.1(C),对全项目做结构腐蚀扫描,回答一个问题:**一个外来的、只懂"AI 通病"的工具,能不能指出本审计两遍法都漏掉的真出血?**
>
> **取证口径**:drift 扫当前 HEAD `b08162cd` 工作区,产物 `evidence/SemanticDebt/drift/drift-baseline.json`(1606 findings / grade C / 669 文件 / 5918 函数)。本节所有"审计盲区"判定 = drift 标记的组 ∩ (该组涉及文件**不在**审计 findings 引用的 352 个 .py 内),即 **B−A 透镜**的第三方版本。明细见 `evidence/SemanticDebt/agent/drift-mds-blindspot.json` 与 `drift-agent-brief.md`。

### 14.0 总裁定:审计核心结论**站得住**,drift 补了一层"微重复"盲区地图

`drift` 没有推翻本审计任何结论,也**没有指出任何审计漏掉的真出血**(P1/承重护栏/灵魂线层面)。它的增量贡献是:在审计**注意力盲区**(salience-biased,盯承重墙/灵魂线/收口点等"大件",自然忽略 4 行小工具函数的重复)里,补出一批 MDS 细粒度重复。

**权威计数(以 `drift-mds-blindspot.json` 的 `_meta` 为唯一真相源,脚本机械去重得出,见 14.0b 口径说明)**:drift 的 MDS 信号共 **28 组**去重重复;按盲区透镜划分——**文件级盲区 15 组**(审计 findings 从未引用该组涉及的任何文件)、**符号级盲区 25 组**(审计从未单独点名该重复符号,是更严的盲区定义)。其中 **5 组**(14.D1–D5)落在承重/灵魂线敏感区或关联已知承重债,值得记进真债清理册;其余为低危 P5 微重复。**全部 28 组已逐行亲核两侧源码。**

这与 §92 方法论自陈的局限闭环:两遍法对"大件"召回强,对"散落微重复"召回弱;第三方机械全扫正好补这一格。

### 14.0b 【方法修正】盲区透镜:文件级 → 符号级(附计数订正)

本节数字几经修订一度自相矛盾(曾出现 17/24 等),已统一锚定到确定性脚本对干净审计基线(剔除 §14 自身文本,避免自污染)的重算结果。两种盲区粒度并存,定义如下:

- **文件级盲区(15 组)**:该重复组涉及的所有文件都不在审计 findings 引用的文件集内——审计连文件都没碰。
- **符号级盲区(25 组)**:审计从未单独点名该重复**符号**(可能碰过文件但没提这个函数)——更严的盲区定义,故数更大。
- 两者非互斥,文件级盲区 ⊂ 符号级盲区。MDS 去重组总数 **28**。

⚠️ 此前版本误用"17 组/24 组/补 7 组"等数字,且 evidence JSON 的 `_meta` 一度被本节文本自污染成 4/2,均为错误,以本段 **28/15/25** 为准。全部 28 组已逐行读两侧源码,无一例藏有比"重复"更重的病(无新静默兜底、无降级分叉)。其中关联已知承重债的见 14.D4(LB-B2 配料表)、关联 N1 家族的见 14.D5。


### 14.1 三信源对账表

| 类别 | 去重组数 | 裁定 |
|---|---:|---|
| drift 真分叉信号(MDS+PFS) | 91 | — |
| 审计已覆盖(A∩B∩C 三方都碰) | 48 | 互证,无新发现 |
| PFS 目录级"错误处理 N 种写法"统计 | 26 | **噪音**:目录级聚合指标,非具体债,丢弃 |
| **MDS 去重组总数** | **28** | 全部已逐行亲核 |
| **├ 文件级盲区**(审计没碰文件) | **15** | B−A 透镜·文件级 |
| **└ 符号级盲区**(审计没点名符号) | **25** | B−A 透镜·符号级(更严) |

> ⚠️ **工具口径校准(已写入 `drift-agent-brief.md` 与 semantics/README)**:
> - drift 的 **AVS「Architecture Violation」≠ 本审计的「分层违规」**。drift AVS=154 实为 Martin 不稳定度耦合指标(`A.py -> B.py 不稳定依赖`),**非有向越层**;本项目 AST 全量分层违规仍是 **0**。勿把 154 条 AVS 当 154 处越层。
> - drift 的 **MDS「Exact duplicates」里有真护栏**:它独立命中 `normalization_matrix._merge_aliases ↔ boolean_normalize`(=审计 §90 **LB-B1 承重双实现**)并建议"删重复"——而删它会撞分层红线。**这坐实:drift 结果必须过 Agent 语义法医,不能直接采信"删重复"建议。**

### 14.2 值得记进真债清理册的 5 组(14.D1–D5,已亲核两侧代码)

#### 14.D1 【P5 · medium · 灵魂线敏感】`_meta_bool_state` 降级判定逻辑逐字两份

- **位置**:
  - `core/services/scheduler/summary/schedule_summary_degradation.py:123`
  - `core/services/scheduler/summary/schedule_summary_downtime_degradation.py:30`
- **亲核**:约 20 行逐字相同——`meta[key]` 的 bool/int(0,1)/str 多态解析 + `(value, used_default)` 二元返回。两文件 diff 后该函数无差异。
- **为何算债**:这是**降级语义的判定核心**(某 meta 字段是否触发降级、是否回落默认)。两份手维拷贝,改一份漏一份 → 同一份 meta 在普通降级路径与停机降级路径上**判定分叉**,正中灵魂线"降级语义不一致、坏数据静默走不同分支"。性质同 §90 LB-B1,但审计两遍法未扫到此对(两个 summary degradation 文件都不在审计 findings 引用集内)。
- **爆炸半径**:降级摘要正确性——两条降级路径对同一 meta 给出不同 used_default,影响 result_summary 对外的降级标记。
- **处置**:抽公共 `_meta_bool_state` 到两文件共同上游(summary 包内),或收到 `core/shared`;收敛前补 parity 测试钉死两份等价。属真债清理册第三档。

#### 14.D2 【P4 气味 · low · 护栏文件】`_op_seq` 两份 + 均静默兜底,其一在护栏文件内

- **位置**:
  - `core/services/scheduler/run/schedule_execution_persistence_guard.py:48`(**护栏文件**)
  - `core/services/scheduler/run/schedule_input_runtime_support.py:19`
- **亲核**:逐字两份 `int(getattr(op,"seq",0) or 0)` + `except (TypeError, ValueError): return 0`。
- **为何算债**:重复本身低危,但(a)其一落在 execution persistence **护栏文件**内,概念应单一来源;(b)两份都 `except: return 0` 静默吞坏 seq——若 op.seq 是脏字符串会被静默当 0 参与排序,属 P4 静默兜底死角(同 §90 LB-B4 家族的容忍性兜底,但此处无"老库行"理由背书)。
- **爆炸半径**:工序排序键;坏 seq 静默归 0 可能扰乱 persistence guard 的 revision 校验顺序。
- **处置**:收口到单一 `_op_seq`;评估 `except` 是否应改为对脏值 loud(护栏文件内更应暴露)。属真债清理册第三档 + P4 复评。

#### 14.D3 【P5 · low · 主链】`_raise_schedule_empty_result` 逐字两份

- **位置**:
  - `core/services/scheduler/schedule_service.py:46`
  - `core/services/scheduler/run/schedule_input_collector.py:79`
- **亲核**:逐字两份——构造 `ValidationError(message, field="排产")`、塞 `details["reason"]`、raise。
- **为何算债**:主链"空结果报错"的同一段异常装配两份。改其一(如加字段)漏其二 → 两条空结果路径报错结构分叉。低危(都是 loud raise,不踩灵魂线),纯收口卫生。
- **爆炸半径**:排产空结果的错误体结构一致性。
- **处置**:收口到单一 helper(主链共同上游)。属真债清理册第二档。

#### 14.D4 【P3 · medium · 承重关联 LB-B2】config 双栈(model↔service)逐字复制函数群——LB-B2 的"配料表"

- **位置**(model 栈 ↔ service 栈,逐字两份):
  - `_float_matches_choice`:`core/models/schedule_config_runtime_coercion.py:31` ↔ `core/services/scheduler/config/config_field_coercion.py:45`
  - `_normalize_valid_texts`:`schedule_config_runtime_coercion.py:49` ↔ `config_field_coercion.py`
  - `_coerce_degradation_event`:`core/models/schedule_config_runtime_read.py:68` ↔ `core/services/scheduler/config/config_snapshot.py`
  - 近似:`ensure_schedule_config_snapshot ↔ _build_schedule_config_snapshot_from_runtime_cfg`(84%,跨同两栈)
- **为何重要**:§90 **LB-B2「双 ScheduleConfigSnapshot 栈锁步同步」**只说"两栈靠人工锁步、加字段须两栈同改",但**未列出具体被复制的函数**。drift 把它们逐个揪出——这是 LB-B2 承重债的**下层实证/配料表**:不仅 snapshot dataclass 双份,连 coercion/校验的私有 helper 也整组双份。任一份单边改 → 算法栈与配置页栈对"同一份配置"的强制/降级判定分叉(踩 LB-B2 描述的静默分叉)。
- **爆炸半径**:同 LB-B2——配置默认值/降级判定在算法侧与配置页侧分叉,静默污染排产正确性。
- **处置**:并入 LB-B2 收敛(service 栈反向复用 model 栈);收敛前的 parity 测试应**同时覆盖这组 helper**,不只 snapshot 字段。
- **复核**:✅ 已读两侧源码,逐字相同确认。

#### 14.D5 【P5 · low · N1 家族】`_get_plan_role_arg` 在 gantt 与 week_plan 路由各一份

- **位置**:`web/routes/domains/scheduler/scheduler_gantt.py:135` ↔ `scheduler_week_plan.py:60`(逐字:`request.args.get("plan_role")`→strip→`or None`)。
- **为何记**:与 §13 **N1(plan-guard 字段散 3 抄)同族**——plan_role 的读取/投影逻辑在多个 scheduler 路由各自手写。单看低危(纯读 query),但它佐证 N1 的判断:**plan_role 处理在 web 路由层缺单一收口**。审计 N1 盯的是 guard 字段投影,这条是更上游的"取参"也散落。
- **爆炸半径**:低(只读取);维护性——plan_role 取参口径散落多处。
- **处置**:与 N1 一并收口(取参 helper 提到 scheduler 路由公共模块)。属真债清理册第三档。
- **复核**:✅ 已读两侧源码。

### 14.3 低危微重复(14 组,简列 · 真债清理册最低档)

> 全部为 drift MDS 标记、审计盲区、低危 P5 微重复:跨子系统的同名小工具函数逐字/近似重复,删不删不影响正确性。grep 实证后可逐组收口到就近公共点或 `core/shared`。

| 重复符号 | 代表位置(首处) | 备注 |
|---|---|---|
| `_norm_text` (2×) | core/services/material/{material,batch_material}_service.py:25/24 | material 双 service 同款空串归一 |
| `_optional_text` (2×) | core/services/scheduler/graph/input_adapter.py:167 ↔ summary/schedule_summary_degradation.py:172 | 跨 graph/summary 子系统 |
| `_required_text` (2×) | gantt_adjustment_{publish,scenario}_service.py | gantt 调整双 service |
| `_normalize_cell_value` (2×) | core/services/common/{openpyxl,pandas}_backend.py:19 | 两 Excel 后端 |
| `_load_preset_payload` (2×) | core/infrastructure/migrations/v8.py:57 ↔ v9.py | 迁移脚本惯性复制 |
| `_unpack_due_info` (2×) | core/services/system/maintenance/{backup,cleanup}_task.py:51 | 维护任务双份 |
| `_operator_machine_reference_snapshot` (2×) | web/routes/{equipment,personnel}_excel_links.py:65 | 两 Excel 链接路由 |
| `validate_row` (2×) | web/routes/personnel_excel_operators.py:148 | 同文件/同族校验 |
| `_normalize_db_path` (2×) | validate_dist_exe.py:56 ↔ web/bootstrap/runtime_probe.py | 启动探针 vs 打包校验 |
| `_normalize_env_overlay` (2×) | tools/long_gate_fingerprint.py:275 ↔ tools/quality_gate_shared.py | 门禁工具(非生产) |
| `_sha256_file` (3×) | tools/long_gate_*.py + quality_gate_shared.py:59 | 门禁工具(非生产) |
| `_load_payload` (2×) | .codex/hooks/*.py:24 | hook 脚本(非生产) |
| `evaluate_reuse ↔ evaluate_failure_reuse` (82%) | tools/long_gate_cache.py:494 | 近似重复(门禁工具) |
| `maybe_run_auto_backup_cleanup ↔ ..._log_cleanup` (83%) | core/services/system/maintenance/cleanup_task.py:161 | 近似重复(维护) |

> 其中 5 组(`_normalize_env_overlay`/`_sha256_file`/`_load_payload`/`evaluate_*`/门禁工具类)落在 `tools/`、`.codex/`——**非交付生产代码**,收口优先级最低。

### 14.4 本节小结

| 维度 | 结论 |
|---|---|
| 第三方能否证伪审计? | **不能**——drift 未指出任何审计漏掉的真出血,核心结论(P1 真实计数 0、承重护栏清单、灵魂线判定)全部站得住 |
| 三信源最强互证 | drift 独立命中 §90 **LB-B1**(承重双实现)——但建议"删重复"恰是引爆动作,反证"drift 须过 Agent 法医" |
| 增量真发现 | **28 组 MDS 重复(文件级盲区15/符号级盲区25),全逐行亲核**;**5 组值得记**:14.D1 `_meta_bool_state`(降级语义逐字两份,最该收)、14.D2 `_op_seq`(护栏文件+静默兜底)、14.D3、**14.D4 config 双栈复制函数群(=LB-B2 配料表)**、14.D5 `_get_plan_role_arg`(N1 家族) |
| 工具口径校准 | drift AVS≠分层违规(本项目仍 0);drift MDS"删重复"含承重墙,不可盲采 |
| 方法论闭环 | 印证 §92:两遍法对"大件"召回强、对"散落微重复"召回弱,第三方机械全扫补此格;**且暴露本审计自身 B−A 透镜的文件级粒度缺陷,已修正为符号级(14.0b)** |
