## 09 · core-infra-shared(基础设施与共享脊梁 infrastructure/shared)

**分区健康一句话:** 整条地基(连接/事务 poison/迁移回滚/备份维护窗/日志安全降级/errors)做工扎实、灵魂对齐——except 要么向上抛、要么只降级到 stderr 不丢数据、要么被契约测试钉死;`core/shared` 解析脊梁(strict_parse/field_parse/compat_parse/value_policies/degradation)是真正且唯一的最深层收口点,compat 回退刻意发 `DegradationEvent` 留痕而非静默兜底;**无 P1 写死假冒计算值,无承重不对称护栏被埋**;残渣仅 5 条,集中在双实现漂移面(1 条承重)、半截薄壳化遗漏、两块预建未连线脚手架、以及 1 条被对抗验证"翻案"坐实的备份兜底死角。

> 本次普查共复核 5 条。**5/5 主锚点 `file:line` 在当前代码逐一仍准(✅)**;F5 引用链内有 2 处子引用需就地校正(已在该条标注),不影响其结论。无一条疑似已被修复。

---

### 09-1 · `normalize_yes_no_wide` 在 shared 与归一化矩阵各有一套语义全等实现,无任何测试绑定二者(可静默漂移)

- **病理:** P5(第 N 套私有实现) · **严重度: medium** · **🔩 load_bearing = TRUE(承重护栏,删错即塌)** · 对抗结论 = load_bearing(未被推翻)
- **位置:** `core/shared/boolean_normalize.py:33` `normalize_yes_no_wide` ✅ 主锚点仍准(函数定义在第 33 行)
- **引用链(逐条复核):**
  - shared 侧实现 `core/shared/boolean_normalize.py:33`,宽松别名集硬编码于 `:7-8`(`('y','yes','true','1','on')` / `('n','no','false','0','off','')`) ✅
  - 矩阵侧孪生实现 `core/services/common/normalization_matrix.py:168` `normalize_yes_no_wide_value` ✅(第 168 行),其宽松集由 `:40-41` 的 `NARROW+('on')` / `NARROW+('off','')` 拼出,与 shared 侧逐行同集 ✅
  - 矩阵在 `:5` `from core.models.enums import ... YesNo`——即矩阵自身依赖 `core.models`,故 shared 若改指矩阵会立刻形成 `core.models <-> core.services` 导入环 ✅
  - 活的 `core.models` 消费方:`core/models/schedule_config_runtime_coercion.py:6` `from core.shared.boolean_normalize import normalize_yes_no_wide`,在 `:192 / :201 / :230` 三处调用 ✅
  - **⚠️ 原始证据自带一处更正(本次复核确认其更正正确):** 原 finding 文字称"boolean_normalize 被 core/algorithms/greedy 经 number_utils.to_yes_no 引用"——**此说为假**。`grep core/algorithms/` 对 `boolean_normalize`/`to_yes_no`/`number_utils` 全为空(本次实测 `NONE in core/algorithms`)。真实 `to_yes_no` 消费方全部落在 `core.services.scheduler`:`resource_pool_builder.py:89/280/340`、`config/config_field_coercion.py:25/189/198/227`、`run/schedule_input_collector.py:130/132`、`run/optimizer_config.py:146`、`run/freeze_window.py:84`,且 `to_yes_no` 本身定义在 `core/services/scheduler/number_utils.py:9`,内部 `:5` 转调 `core.shared.boolean_normalize` ✅
  - **关键缺口实测:** `grep normalize_yes_no_wide tests/` = 空,`grep boolean_normalize tests/` = 空——**全仓没有任何测试同时 import 两套实现并断言等价** ✅(漂移风险为真)
- **为何算债:** 同一"宽松是否归一"概念两套独立实现,逻辑当前逐行同义却无任何契约绑定。`YesNo` 枚举值或任一别名集若单边改动(例如有人只改矩阵的 `('on')` 或只改 shared 的 `'on'`),两套会静默漂移、行为分叉而无人察觉。这正是 P5 的漂移风险面。
- **爆炸半径:** `boolean_normalize` 被 `core.models`(下层)直接依赖。若有人以"统一到矩阵"之名删除它、把 coercion 改指 `core.services.common`,会**立刻撞 AST 分层红线(下层 import 上层)**,并制造 `core.models <-> core.services` 导入环,击穿当前 0 违规结构。故该模块的存在本身是分层承重的——它是 `core.shared` 层级及以下唯一的宽松 yes/no 归一器,`core.models`/`core.algorithms` 无替代可调。
- **处置建议(收口方向已锁定,严禁反向):**
  1. **不要删除 shared 模块**。唯一合法的消重方向是:让**上层** `normalization_matrix.normalize_yes_no_wide_value` **反向 delegate** 到**下层** `boolean_normalize.normalize_yes_no_wide`(`services -> shared` 是合法下行边),保留 shared 为唯一事实源、删掉 matrix 内的重复分支。
  2. **优先补一条等价契约测试**(当前真正缺的收口点):断言两函数在「全宽松别名集 × 是/否 × `default`/`passthrough`/`raise`/`no` 全部 `unknown_policy` 分支」上逐一同值,任一单边改动即红灯。这是把"逐行同义"从巧合变成被钉死的不变量。
- **🔩 该补的"我是故意的"承重注释文案(建议加在 `core/shared/boolean_normalize.py:33` `normalize_yes_no_wide` 上方):**
  ```python
  # 【承重·故意双实现,勿合并】本函数是 core.shared 层(及以下)唯一的"宽松是/否"归一器,
  # 被下层 core.models(schedule_config_runtime_coercion:6/192/201/230)、core.algorithms
  # 经 core.services.scheduler.number_utils.to_yes_no 间接依赖。它与上层
  # core.services.common.normalization_matrix.normalize_yes_no_wide_value 语义全等,但【不能】
  # 删除本函数改指矩阵:core.shared 禁止 import core.models(YesNo 枚举在 core.models,故此处
  # 只能硬编码 'yes'/'no' 字面量),下层 import 上层会撞 AST 0 分层违规 + 造 models<->services
  # 导入环。若要消重,唯一合法方向是让上层矩阵反向 delegate 到本函数。两套等价由
  # tests/<待补>_yes_no_wide_equivalence 契约钉死,改任一侧别名集前必跑该测试。
  ```
- **复核结论:** ✅ 证据仍准(主锚点 `:33`、消费链、缺测试均与当前代码一致;原 finding 自带的 core/algorithms 误述已被其对抗证据更正,本次再次实测坐实更正正确)。

---

### 09-2 · `common/number_utils.py` 是 `core/shared/number_utils.py` 的全量函数体拷贝,而同目录 4 个兄弟模块都已是薄 re-export 壳(半截收口)

- **病理:** P3(半截迁移残渣) · **严重度: medium** · load_bearing = false · **对抗结论 = depends(普查员"可安全单边收口"的前提被证伪)**
- **位置:** `core/services/common/number_utils.py:23`(`parse_finite_float`),`:40`(`parse_finite_int`) ✅ 两锚点仍准
- **引用链(逐条复核):**
  - canonical 唯一收口点 `core/shared/number_utils.py:23`(float)、`:39`(int) ✅,内部 `:5-10` 转调 `core.shared.strict_parse` ✅
  - 镜像 `core/services/common/number_utils.py` 保留**全量函数体**(实测 `def-count=6`:2 个 `parse_finite_*` + 4 个 `@overload`),与 canonical 逐行相同,仅多一行中文 docstring(`:24 / :41`) ✅
  - 对照同目录 4 兄弟全为纯 re-export 薄壳(实测 `def-count=0`):`common/compat_parse.py`、`common/value_policies.py`、`common/degradation.py`、`common/field_parse.py` ✅
  - canonical 的活消费方:`core/models/schedule_config_runtime_weights.py:7`、`core/services/scheduler/number_utils.py:6` ✅
  - 镜像的活消费方:`core/services/common/excel_validators.py:26`(在 `:123/:160/:207/:229` 用)、`web/routes/domains/scheduler/scheduler_excel_calendar_rows.py:8`(在 `:79/:94` 用),二者都只 import `parse_finite_*` ✅
  - 钉死测试 `tests/regression_number_utils_facade_delegates_strict_parse.py` 存在(实测在档) ✅,L3 裁定 `.codestable/refactors/2026-06-01-test-gate-cleanup/L3_verdicts.csv:174` = **`KEEP,high`**,2026-06-01 刚复核保留 ✅
- **为何算债:** `core/services/common` 显然在做"统一回落到 `core.shared`"的薄壳化迁移(4/5 兄弟已完成),唯独 `number_utils` 没改成 re-export、留了重复函数体,与 4 个已收口兄弟形成**不对称**。两份体拷当前逐行相同,但重复体可随时单边漂移,是迁移没做完的残渣外观。
- **⚠️ 对抗验证的关键反转(必须写进处置约束):** 普查员设想的"对齐 4 兄弟、单边改成 re-export 薄壳"会**击穿一个活跃 `KEEP/high` 门禁**——
  - `tests/regression_number_utils_facade_delegates_strict_parse.py:19/23-26/45-48/62` 当前 `monkeypatch` 的是 `common.number_utils` **模块级** `parse_required/optional_*(int/float)` 名,并断言 `parse_finite_*` 转调它们。这些名只因 `common` 版**把函数体定义在本模块**、其 `__globals__` 指向 `common.number_utils.__dict__` 才存在且可被 patch。
  - 一旦改成薄壳(`from core.shared.number_utils import *`),`parse_finite_*` 的 `__globals__` 变成 `shared.number_utils`、模块级被 patch 的名不再存在 → `:23` 立即 `AttributeError`、`:62` 断言失败(patch 变空操作)。
  - 该测试 `:69-84` 还钉住灵魂不变量:空白 + `allow_none` → `None`,否则抛 `ValidationError(field 正确)`。
  - 4 兄弟走的是另一种契约:`tests/regression_config_service_component_contract.py:375-411` 的 `*_reexports_shared_identity` **is-同一性**测试(透明壳)。`number_utils` 故意走 delegation-facade 测试,是**两种不同的设计契约**,不对称是有意而非漏改。
- **爆炸半径:** 该重复文件物理上属相邻 `core-svc-domain` 分区,重复源头是本分区 canonical。生产消费方都只用 `parse_finite_*`,两种形态行为字节级一致,运行期灵魂不变量(strict_parse 不静默吞坏数据)不受影响。**风险点不在运行期,而在"误以为可安全单边收口"**:单边改壳会绿灯变红灯。
- **处置建议(收口到 `core/shared/number_utils.py` 这个 canonical,但必须协调式):** 若确要统一为薄壳,**不能单边改**,必须同一笔提交内:(1) 把 facade 测试改写成与 4 兄弟一致的 `*_reexports_shared_identity` 同一性测试;(2) 有意识推翻 `L3_verdicts.csv:174` 的 `KEEP/high` 裁定并记录决定。若不做这套协调,则维持现状、把"故意保留 delegation-facade"写成注释即可——**不建议为消重而消重**。
- **复核结论:** ✅ 证据仍准(锚点 `:23/:40`、4 兄弟 def-count=0、镜像 def-count=6、L3:174=KEEP/high、消费方均与当前代码一致)。但 finding 的 `why_debt` 措辞("可随时单边漂移、可安全收口")需被 `_adv_verdict=depends` 修正:**不对称是有意设计,单边收口非安全债**。

---

### 09-3 · compat 解析的整条"日期"分支(parse_compat_date + 3 个日期策略 + VALUE_DATETIME/READ_FILTER_ONLY)生产零消费,只靠测试续命

- **病理:** P6(死代码/死面包屑) · **严重度: low** · load_bearing = false · 无需对抗
- **位置:** `core/shared/compat_parse.py:198` `parse_compat_date` ✅ 主锚点仍准(定义在第 198 行)
- **引用链(逐条复核):**
  - `parse_compat_date(` 调用点(call 形态)实测全仓 = **仅 2 处**:定义自身 `core/shared/compat_parse.py:198` + 唯一测试 `tests/regression_compat_parse_emits_degradation.py:39`;`core/web/data` 生产侧 = 0 ✅
  - re-export `core/services/common/compat_parse.py:4`,并列入 `:10` `__all__` ✅
  - 上游日期策略项 `core/shared/value_policies.py:180`(`due_date`,VALUE_DATE)、`:190`(`start_time`,VALUE_DATETIME/READ_FILTER_ONLY)、`:200`(`end_time`,同) ✅(三处 `field=` 行号精确)
  - `get_field_policy` 的**唯一生产调用方**是 `core/shared/compat_parse.py:32` `_resolve_compat_policy`,其余调用全在测试(`regression_value_policies_matrix_contract.py:52..93`、`regression_config_service_component_contract.py:399`)✅;而 `_resolve_compat_policy` 的 VALUE_DATE 出口 `parse_compat_date` 已死
  - 生产里真实坏时间留痕走 `core/services/scheduler/_sched_display_utils.py:84` `record_bad_time_row`,内部 `:92` 手搓 `collector.add(code="bad_time_row_skipped")`,**完全绕开** value_policies 的 `start_time`/`end_time` 策略 ✅
  - 对照活分支:`parse_compat_float`/`parse_compat_int` 经 `core/shared/field_parse.py:85`/`:137` 活跃消费 ✅,仅 date 分支死
- **为何算债:** compat 读取子系统按 float/int/date 全矩阵搭建,但 date 能力(`parse_compat_date` + 3 个日期策略项 + `VALUE_DATETIME` 常量 + `READ_FILTER_ONLY` 常量)从未接到任何生产读链——预建却没连线的脚手架。矩阵契约 `tests/regression_value_policies_matrix_contract.py:92-95` 仍在 pin `start_time`/`end_time`(`get_field_policy("start_time"/"end_time")` 在 `:92/:93`,`READ_FILTER_ONLY` 断言在 `:94/:95`),属"测试活、生产死"。
- **爆炸半径:** 纯增生的未消费切片,小。删除只需同步退掉 `regression_compat_parse_emits_degradation.py:39` 的 date 用例与矩阵契约 `:44-45/:92-95` 的 `start_time`/`end_time` 断言。不删则长期作为"看着像在用"的设计噪音,误导后人以为历史日期导入走这条路。
- **处置建议:** 二选一并记决定——(A) 删除整条 date 切片(parse_compat_date + 3 策略项 + 仅 date 用到的常量),同步退测试;(B) 若属"预留待接"的有意脚手架,在 `parse_compat_date:198` 与三策略项 notes 上标注"预建未接线,待 X 功能落地启用",把死面包屑显式化。收口到现有统一点:坏时间留痕已统一在 `record_bad_time_row` + `degradation` 事件,date 策略本就是冗余路径。
- **复核结论:** ✅ 证据仍准(`parse_compat_date:198`、唯一测试调用 `:39`、value_policies `:180/190/200`、矩阵契约断言 `:94-95`、`record_bad_time_row:84/92` 全部与当前代码一致)。

---

### 09-4 · `WRITE_INTERNAL_ONLY` 写模式常量定义 + re-export + `__all__` 白名单齐全,但无任何 FieldPolicy 使用、无任何消费方分支判断

- **病理:** P6(死代码/死面包屑) · **严重度: low** · load_bearing = false · 无需对抗
- **位置:** `core/shared/value_policies.py:9` `WRITE_INTERNAL_ONLY = "write_internal_only"` ✅ 主锚点仍准(第 9 行)
- **引用链(逐条复核 —— 全仓仅 3 处,无一处真正消费):**
  - 定义 `core/shared/value_policies.py:9` ✅
  - re-export `core/services/common/value_policies.py:11`(import)、`:29`(`__all__`)✅
  - **零消费实测:** 全仓唯一读取 `policy.write_mode` 的地方是 `core/shared/compat_parse.py:165 / :188 / :208`,三处一律 `== WRITE_OPTIONAL else ...`,**从不与 `WRITE_INTERNAL_ONLY` 比较** ✅
  - `value_policies.py` 内 16 个 `FieldPolicy` 的 `write_mode=` 赋值实测分布:`WRITE_REQUIRED ×13` / `WRITE_OPTIONAL ×1` / `WRITE_NOT_APPLICABLE ×2`,**无一用 `WRITE_INTERNAL_ONLY`** ✅
- **为何算债:** 定义后无人消费的死常量,却散布在定义点 + re-export + `__all__` 三处制造"在用"假象——符合 P6 死面包屑。它是设计时预留但从未落地的写模式词槽。
- **爆炸半径:** 极小。删除仅触及 `value_policies.py:9` 与 `common/value_policies.py:11,29` 两文件三行,无运行期消费方。
- **处置建议:** 删除三处该常量;若属有意预留,在 `:9` 加一行 notes 注明"预留写模式,尚无字段使用"。无需新建收口点。
- **复核结论:** ✅ 证据仍准(定义 `:9`、re-export `:11/:29`、`write_mode` 读取点 `:165/188/208` 全 `==WRITE_OPTIONAL`、FieldPolicy 赋值分布均与当前代码一致)。

---

### 09-5 · 备份完整性校验(PRAGMA integrity_check)**执行本身**失败时只 warning 不阻断,仍把未通过校验的 `.db` 提升为正式备份

- **病理:** P4(静默兜底死角) · **严重度: low(但影响面是"救命快照可信度",建议升档关注)** · load_bearing = false · **🚩 对抗结论 = real_debt,且 `_adv_refuted = TRUE`:原"护栏"辩护被推翻、坐实为真债**
- **位置:** `core/infrastructure/backup.py:333`(内层 `try:`)✅ 主锚点仍准。精确控制流(本次逐行重映射):
  - `:334` `rows = dest.execute("PRAGMA integrity_check").fetchall() or []`
  - `:335` `except Exception as e:` → `:336` 注释"校验执行失败:不阻断备份" → `:337` `fallback_log(..., "warning", "...执行失败(已忽略)...")`
  - `:338` `else:` → `:339` `msg0=...` → `:340` `if msg0 != "ok":` → `:341` error log → `:342` `raise RuntimeError(...)`
  - `:343` `os.replace(tmp_path, backup_path)` → `:344` info "数据库已备份"
- **引用链(逐条复核):**
  - **核心倒挂(bug 本体):** `:335` except(PRAGMA 执行抛异常 = `database disk image is malformed` 一类**更严重**的损坏迹象)只 warning 后**放行**,控制流落到 `:343` 把未校验的 `.tmp` 升为正式备份、`:344` 报 info "已备份";而 `:340` else 分支(PRAGMA 成功返回但首行 != `ok`,**较轻**)反而 `:342` raise 阻断。**严重度被倒挂** ✅
  - 下游信任这些备份当救命快照:`restore() :415` `self.backup(suffix="before_restore")` 造快照 → `_auto_rollback :387` 经 `_copy_db_file(:354-372)` 用 `source.backup(dest)` 把快照盖回活库,**全程无 integrity 复检** ✅
  - 迁移回滚 `core/infrastructure/migration_backup.py` `restore_db_file_from_backup`(def 在 `:38`,`shutil.copy2` 在 `:55`)裸文件拷贝盖活库,**零完整性校验**,完全信任备份文件可信 ✅(⚠️ 原证据写"migration_backup.py:52-58",`copy2` 实在 `:55`、函数 def 在 `:38`——锚点在区间内但更精确应记 `:38/:55`)
  - 迁移前备份走同一 `backup()`:`core/infrastructure/migration_runner.py:188` `manager.backup(...)`,`:61` 文档契约明写"必须取得可用备份否则阻断迁移";若改 raise,则按 `:191` 重抛阻断——更正确(无法运行 integrity_check 的库不算"可用备份") ✅
  - 消费方均能优雅承接 `backup()` 抛错:`core/services/system/maintenance/backup_task.py:149` `except Exception`(记错不崩)✅;`web/bootstrap/factory.py` 退出备份 `:137` `bm.backup(suffix="exit")` 外包 `except MaintenanceWindowError` + `except Exception`(`:143` 附近,记错不崩)✅(⚠️ 原证据写"factory.py:142",**正确路径是 `web/bootstrap/factory.py`,非 `core/infrastructure/factory.py`(后者不存在)**,行号 `:137-143`);手动路由 `web/routes/system_backup.py:108` `mgr.backup(suffix="manual")` 仅捕 `MaintenanceWindowError`(`:109`),`RuntimeError -> 500` 这条路径**今天已因 else 分支存在**,统一只是多一个触发器经既有路径 ✅
  - finally `:346-352` 的 `.tmp` 清理仍在 ✅(抛错不残留半成品)
  - **无任何测试钉死这条宽松吞咽:** `grep integrity_check tests/` = 空 ✅;`tests/regression_restore_success_condition.py` 全程 `mock.patch`(`:109/136/160/181/207`)BackupManager,根本不触达本校验块 ✅
- **为何算债:** 项目灵魂是"坏数据不准静默兜底、宁可暴露错误"。这里把"这份备份是否可信"这一**本应暴露的缺口**吞成 warning:一个无法被验证完整性的备份仍被当成可信备份落地并报成功(`:344` "数据库已备份"),后续 restore 自动回滚 / 迁移回滚会拿它当救命快照盲拷。`:336` 那句"不阻断备份"注释,正是被对抗验证推翻的**伪"我是故意的"**——"有个备份好过没有"的辩护在"救命快照场景 + 严重度倒挂(更严重的 except 反而放行)"面前不成立。
- **爆炸半径:** 影响备份/恢复可信度。极端场景:用一个未验证(可能已损坏)的备份做自动回滚 / 迁移回滚,**放大数据损坏**。半径覆盖 `restore` 自动回滚、`migrate_with_backup` 回滚两条救命路径。
- **处置建议(收口到"完整性不可验证 = 不可信备份 = 不落地"这一条统一立场):**
  1. **主修:** 把 `:335` except 分支改为与 `:340` else 一致 —— 校验**执行失败**即视为不可信、`raise` 不落地(与"返回非 ok 即 raise"对齐,消除严重度倒挂)。
  2. 顺手收尾(非阻塞):`web/routes/system_backup.py:108-113` 手动路由补一个通用 `except` 把备份失败 `flash` 成清晰错误,而非裸 500(该 500 路径今天已存在,只是多一个触发器)。
  3. 独立加固(可后续):在回滚消费方 `_copy_db_file(:354-372)` 与 `restore_db_file_from_backup(migration_backup.py:38/55)` 各补一次 integrity 复检,封堵"旧版遗留的未校验备份文件被当救命快照盲拷"的残口。
  4. 已核验 `finally :346-352` 仍在、且无任何业务流依赖 `backup()` 在校验失败时仍返回路径,故 `raise` 不丢任何安全不变量。
- **复核结论:** ✅ 证据仍准(主锚点 `:333`、严重度倒挂 except/else、`:343` 落地、下游回滚链、消费方 except、无测试钉死,均与当前代码一致)。**2 处子引用需就地校正(已并入上文,不改变结论):** ① 回滚拷贝在 `migration_backup.py:38(def)/:55(copy2)` 而非泛指 `:52-58`;② 退出备份消费方正确路径是 `web/bootstrap/factory.py:137-143`,而非 `core/infrastructure/factory.py:142`。对抗裁定 `real_debt` 成立、原"护栏"定性已被推翻。
