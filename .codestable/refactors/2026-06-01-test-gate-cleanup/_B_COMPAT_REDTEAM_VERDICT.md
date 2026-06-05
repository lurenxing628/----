所有关键证据已实证核实。我现在掌握了 5 路红队结论的真实地基,可以下裁决。核心确认:

1. **RT2 是真雷且 my_change_at_fault=true** — import 链三段模块级硬 import 全坐实,PLAN.md:121 删 architecture_scan_cache 与之精确相交,4 份加固文档零提及该约束。
2. **summary.json:294-295 簇残留为真** — 仍列两文件,分布数 KEEP427/MERGE39/DWT7,与 CSV(429/37/6/HOLD1)冲突。
3. **CSV 机读真值自洽** — 429/37/6/HOLD1/DROP38,总 645,算术正确。HOLD_FOR_R51 选择器安全(PLAN:92 只认 =='DROP')。
4. **多份文档 427/39/7 数字漂移**为真(GOVERNANCE/BASELINE/PLAN/L3§4标题)。
5. **dispatch_rule P7 不构成硬锁死** — P7 只三项新文件检查,无禁删白名单。

---

# 红队对抗裁决报告:B-COMPAT 加固改动复核

## 一句话结论

**整体站得住,核心裁定(锁 architecture_fitness=KEEP、sort_strategy→HOLD_FOR_R51、priority 独立 KEEP)全部正确,CSV 机读真值自洽,A 的自动化不会误删。但有 1 个 high 真问题必须立即修:我锁了 architecture_fitness=KEEP 并宣称它"缓存被砍仍独立有价值",却没在任何加固文档里钉下"P2.2 删 architecture_scan_cache.py 时必须保住它的 import 链"这条配套约束——这是我锁 KEEP 后新生的义务而我漏了。** 不修的话,A 跑完 P2 门禁直接 collection-error 红,B 靠它做 go-no-go 也起不来。建议补一轮修改(4 处文件,见第四节)。

---

## 二、分层裁决

### 必须修(high,is_real=true)

**[H-1] 锁 architecture_fitness=KEEP 却未约束 P2.2 保住其依赖链,且 CSV reason 写下"缓存被砍仍独立有价值"的不实断言**
*(来源 RT2 issue#1;RT4/RT5 未独立命中此链,RT2 是唯一抓到的,且我已逐行复现坐实)*

- **是不是我引入**:**是(my_change_at_fault=true)**。锁 KEEP 是我改的;"缓存被砍仍独立有价值"是我写进 CSV reason 的;漏写配套约束也是我。底层 P2.2 表述粗糙(删模块却留 live import)是 A 计划固有坑(那部分 false-fault),但"把这个坑钉成 B go-no-go 必须满足的约束"是我锁 KEEP 后才产生的义务。
- **证据(已亲自 Read 复现)**:
  - `tests/test_architecture_fitness.py:25` → `from tools.quality_gate_support import (...)`(模块级,AST 确认非 try/非函数内)
  - `tools/quality_gate_support.py:32` → `from .quality_gate_operations import (...)`(模块级)
  - `tools/quality_gate_operations.py:5` → `from .architecture_scan_cache import aggregate_architecture_scan, scan_files_with_cache`(AST 确认顶层,lineno=5)
  - 运行期二次坐实:`quality_gate_operations.py:751/752/764` 的 `architecture_oversize_scan_map`/`architecture_complexity_scan_map`/`architecture_silent_scan_entries`(正是 test_architecture_fitness 直接 import 的符号)在函数体内调 `aggregate_architecture_scan`/`scan_files_with_cache` — 删模块连运行期都 NameError,不止 collection
  - `scripts/run_quality_gate.py:26` → 顶层 `from tools.architecture_scan_cache import architecture_scan_cache_metadata`(live 门禁也直连)
  - `PLAN.md:121` → "删 `architecture_scan_cache.py` + 缓存"(明令删,无改接说明)
  - `L3_verdicts.csv:620` reason 含"门禁缓存层被砍仍独立有价值,严禁随工具删"
  - 4 份加固文档 grep `architecture_scan_cache` 仅命中 `PLAN.md:121` 那条删除指令本身;`_B_COMPAT_SAFEGUARDS.md:93` 的 P2.2 条目只写"删 verify_required / 简化 long_gate",对 architecture_scan_cache **零字提及**,且整条已标"（已降级）"
- **危害**:A 跑完 P2.2 删模块 → test_architecture_fitness 一 import 即 ImportError → collection error → A 的 P2 门禁红;B 靠它做全批次 go-no-go(R28 白名单 :77/:254 + C-EXEC-FACT 分层红线)也起不来。**这正是我锁 KEEP 想保护的安全网被 A 自己的 P2 步骤砍断。**
- **修法**:见第四节补丁清单 P1-P3。

> 注:RT2 把它评 high,我同意 high(不升 blocker)。理由:它确实会让 A 的 P2 失败 + B 起不来(够 blocker 的后果),但它不是"现在文档里就有错数据导致立即数据错乱",而是"漏了一条必须补的约束";只要在 A 真正执行 P2.2 之前补上(P2 在 P5/P6 之前,有充足窗口),不会失败。按 severity 定义(blocker=直接执行失败)它在边界上,从严可记 blocker、从实可记 high——**无论哪级,都必须修**,定性一致。

---

### 建议修(medium,is_real=true)

**[M-1] summary.json 是改前快照:仍把 sort_strategy 当活的 2 文件 MERGE 簇 + 分布数与 CSV 冲突**
*(RT1 issue#1 评 high / RT5 对照项;我复核后下调为 medium,理由见下)*

- **是不是我引入**:**是**(我解散了 CSV 里的簇,没同步 summary.json)。
- **证据**:`summary.json:293-296` sort_strategy_case_insensitive 簇仍列 `regression_sort_strategies_priority_case_insensitive.py` + `regression_sort_strategy_case_insensitive.py` 两文件,无解散标记;`summary.json:4/6/8` KEEP427/MERGE39/DROP_WITH_TOOL7,无 HOLD_FOR_R51 键;`summary.json:18` `l3_csv_path: /tmp/regovern/L3_verdicts.csv`(指向仓库外)。对照 CSV 实算 KEEP429/MERGE37/DWT6/HOLD1。
- **为何不是 high(对 RT1 的修正)**:RT1 担心"若 A 用 summary.json 的 multi_file_cluster_detail 驱动合并会复活 B-1"。但 `_B_COMPAT_SAFEGUARDS.md:29` 的 A 执行校验明确规定"合并阶段确认 sort_strategy 簇已不存在:`rg sort_strategy_case_insensitive L3_verdicts.csv` 应仅命中 HOLD_FOR_R51 行",`:14` 也写死"严禁裸筛 csv verdict 后机械 git rm"——A 的权威机读源被钉死为 **CSV**,summary.json 的 l3_csv_path 还指向 `/tmp/regovern`(仓库外、已不存在),没人会拿它驱动合并。所以"复活 B-1"需要 A 执行人主动违反 safeguards 去用一个指向 /tmp 的过期 json,概率低。**真实危害是"机读源对不上、手动复核会困惑",medium 足够。**
- **修法**:见第四节 P4(二选一:同步 summary.json 三处 / 或加 `_stale` 注记 + safeguards 校验补一句)。

**[M-2] L3_VERDICTS.md 文件内部自相矛盾:§1 脚注(429/37/6)vs §4 标题(39文件/11簇/净减11)**
*(RT1 issue#2 / RT4 issue#2 / RT5 issue#2 三路一致命中)*

- **是不是我引入**:**是**(我加了 §1:22 脚注和 §4.1:116 簇划删,但没改 §4 标题)。
- **证据**:`L3_VERDICTS.md:22` 脚注 MERGE37/簇解散 vs `:102` "MERGE,39 文件 → 11 多文件簇,净减 11" + `:104` "多文件簇(11 个)" + `:16` "MERGE 39 ... 11 多文件簇"。实算活簇=10(§4.1 表逐行点:excel6/gantt4/seed4/wb_context3/req_svc3/real_db3/batch2/wb_links2/route_parser2/sched_route2,sort_strategy 那行已划删)。
- **修法**:见第四节 P5。

---

### 误报 / 可不管(is_real=false 或 low)

**[L-1] PLAN.md:123 / GOVERNANCE.md:112 DROP_WITH_TOOL 仍写"7 个",CSV 实为 6** — is_real=true,**my_change_at_fault=false**(标题"7"是 A 原有,我没顺手改)。不会误删:`PLAN.md:124` 紧随"修正:architecture_fitness 保留"、`GOVERNANCE.md:112` 同句带"(example 例外保留)"、CSV:620 已是 KEEP、PLAN:92 的 rm 硬筛只认 `verdict=='DROP'`(与 DROP_WITH_TOOL 无关)。纯台账数字陈旧,low。建议顺手改。

**[L-2] GOVERNANCE.md:50/108 / PLAN.md:98 / BASELINE.md:80/82/188 仍写"KEEP 427"** — is_real=true,my_change_at_fault=true(我编辑过 GOVERNANCE/PLAN 没回填)。实际影响极小(docstring 覆盖差 2 个文件,architecture_fitness 已有 docstring)。`GOVERNANCE.md:50` 把"KEEP 427"作 live 不变量陈述,易被当回退验证基线,这条建议至少改一处。low。建议顺手改。

**[L-3] py38 契约在 §5 与 sp05/sp06 等同处理** — RT4 issue#1,is_real=true/my_change_at_fault=true,但 severity=low(RT4 自己注明 digest 对 py38 同时有 medium 与 low 两种口径,且 py38 是前瞻性静默护栏不是退断言对象)。可在 §5 单列一条 py38 的 KEEP-until-B / ruff target-version 二选一。可不阻断。

**[L-4] raw_verdicts/B10+B14 仍是改前埋雷值,无回灌警示** — RT5 issue#3 评 medium,我下调为 **low-info**。理由:全仓 grep `raw_verdicts`/`regovern` 在 `*.py`/`*.sh` = 0,无任何自动脚本回灌(build_test_inventory.py 只建 L2 test_inventory.csv);summary.json 的 l3_csv_path 指向已不存在的 /tmp。这是"未来手动重跑 L3 workflow 才触发"的远端隐患,非现态问题。建议在 GOVERNANCE.md:161 raw_verdicts 那行加一句警示即可,但不阻断先 A 后 B。

**[L-5] B-10 括注"目录现已补回"措辞精度** — RT4 issue#4,is_real=true 但 severity=none(措辞问题,不影响动作正确性)。可选优化。

**[F-1~F-5] 已证伪项(is_real=false)**:
- HOLD_FOR_R51 触发 KeyError/被 !=KEEP 误删 — **伪**。全仓无代码读 L3_verdicts.csv;选择器是 PLAN:92 内嵌 `r['verdict'].strip()=='DROP'`(精确值比较非键查找,645 行 verdict 列全在,无 KeyError);MERGE 走 `MERGE:` 前缀;HOLD_FOR_R51 两者都不匹配 → 安全跳过 = 正是"交棒 R51"所需。我已实测 645 行 0 ragged。
- merge_cluster 清空致汇总脚本出错 — **伪**。与 verdict 的 MERGE: 后缀冗余,无仓库内消费者,DictReader 把空单元读成 ''。
- dispatch_rule 被 P7 锁死致 B 删不掉 — **伪**(RT3 issue-d)。`PLAN.md §9 P7`(:198)实为三项**新文件**检查(拦 main-style 新文件 / 强制 docstring / 新源文件须有 scope),**不维护禁删既有 KEEP 测试的白名单**,不会机械锁死。我在 csv:323 + safeguards:32 的前瞻护栏已缓解。建议(非必须)在 PLAN §9 补一句"P7 不得拿 KEEP 清单当禁删白名单"固化纪律。
- B-1/B-4/B-6/B-11 底层裁定 / CSV 列完整性 / 645 总数 / RT5-c(PLAN §1.5 永久保留与 KEEP 不冲突)— **全部核验通过,无反例**。priority 文件 grep parse_strategy=0、测 StrategyFactory、与 R51 无关,独立 KEEP 正确;sort_strategy:25 坏值兜底断言确存在,绑 R51 整体退场正确。

---

## 三、特别确认:RT2(architecture_fitness KEEP vs P2 删工具连锁)

**RT2 结论成立,是本轮唯一的真雷,我已亲自逐行复现而非采信转述。**

- **锁 KEEP 本身对且必要**:architecture_fitness 是 B 全批次 go-no-go 门禁载体(L3_VERDICTS.md:98 + :186 坐实,B 计划树 7 个文件引用它含 4 份 C-EXEC-FACT redteam),DROP_WITH_TOOL→KEEP 在所有 actionable 文档(CSV:620 / PLAN:41,124 / GOVERNANCE:112 / L3:98)一致无残留 DROP 引用,机读安全。**这部分我做对了。**
- **错在配套约束缺失**:我在 CSV:620 reason 写"门禁缓存层被砍仍独立有价值",但 import 链(test→support:32→operations:5→architecture_scan_cache)是三段模块级硬 import,删模块时这句话在字面上为假——会 collection-error。我锁 KEEP 创造了"必须保证依赖链不被 P2 砍断"的新义务,而 `_B_COMPAT_SAFEGUARDS.md` 全文没写这条(P2.2 条目只提 verify_required/long_gate,已降级)。
- **A 固有坑的边界澄清(RT2 issue#2,my_change_at_fault=false)**:P2.2"删 architecture_scan_cache.py"本身就和 A 自己冲突 — `run_quality_gate.py:26` live 门禁直连它,`test_architecture_scan_cache.py:9` 该模块专属测试还被判 KEEP_TRIM(CSV:8)。即 A 一边要删模块、一边留它的 live 入口和自测。这坑先于我存在、会独立于我让 A 的 live 门禁失败。我的过错不是"P2 会删依赖"(A 早有的坑),而是"我锁 KEEP 并宣称独立有价值,却没把这个坑钉成 B 必须配套的约束"。

---

## 四、是否需要再补一轮修改:**需要**

补丁清单(按优先级,P1-P3 为 high 必补,P4-P5 为 medium 建议补,L 级可顺手):

**P1(high)— `_B_COMPAT_SAFEGUARDS.md` 改 §4 的 P2.2 行(:93)**
将现"P2.2 删工具 | 删 verify_required / 简化 long_gate | ...（已降级）"扩写为(或新增一条紧邻、撤销"已降级"):
> P2.2 删 `architecture_scan_cache.py` 必须与"改接 `quality_gate_operations.py:5` + `scripts/run_quality_gate.py:26` 的 import、保留 `architecture_oversize_scan_map`/`architecture_complexity_scan_map`/`architecture_silent_scan_entries`/`aggregate_architecture_scan`/`scan_files_with_cache` 的公共 API 行为、同步处理 `tests/test_architecture_scan_cache.py`(CSV:8 KEEP_TRIM)"放**同一原子提交**;否则 `test_architecture_fitness.py`(已锁 KEEP)collection-error,A 的 P2 门禁红、B go-no-go 起不来。

**P2(high)— `L3_verdicts.csv:620` 改 reason**
把"门禁缓存层被砍仍独立有价值,严禁随工具删"改为"其依赖的 `architecture_*_scan_map` 公共 API 必须在 P2.2 cache 塌缩后保留(改接 import,见 `_B_COMPAT_SAFEGUARDS.md` P2.2 条),严禁随工具删"。

**P3(high)— `PLAN.md` P2.4 验证(:126 附近)补一行命令**
`.venv/bin/python -m pytest tests/test_architecture_fitness.py --collect-only`(证明删 cache 后 collection 不炸);并建议把 `PLAN.md:121` 的"删 architecture_scan_cache.py + 缓存"细化为"塌缩缓存层:删模块 + 改接 run_quality_gate.py:26 与 quality_gate_operations.py:5 + 同步处理 test_architecture_scan_cache.py"(此项即便不为 B 也该修,否则 A 自身 P2 后 live 门禁 ImportError — RT2 issue#2)。

**P4(medium)— `summary.json` 二选一**
(a) 删/标记 `:293-296` sort_strategy 簇 + 改 `:4/6/8` 分布 + 加 HOLD_FOR_R51:1;或更省事 (b) 在 summary.json 顶部加 `_stale_since:2026-06-05`,并在 `_B_COMPAT_SAFEGUARDS.md` 校验区(:29 附近)补一句"summary.json 为变更前快照(l3_csv_path 指向已不存在的 /tmp/regovern),机读簇一律以 L3_verdicts.csv 的 MERGE: 前缀为准,勿用 summary.json 驱动合并"。推荐 (b),成本低且与现有"CSV 为权威"口径一致。

**P5(medium)— `L3_VERDICTS.md` §4 标题对齐**
`:16/:102/:104` 的"39 文件 / 11 多文件簇 / 净减 11"改为"37 文件 / 10 多文件簇 + 6 单挂靠 / 净减 9",或就近加注"(B-COMPAT 解散 sort_strategy 簇后真值见 §1:22 脚注)"。

**L 级(顺手,不阻断)**:`PLAN.md:123`/`GOVERNANCE.md:112` 的"7 个"→"6 个(architecture_fitness 例外移出)";`GOVERNANCE.md:50/108`/`PLAN.md:98`/`BASELINE.md:80/82/188` 的"427"→"429"或加脚注;`PLAN.md §9` 补"P7 不得拿 KEEP 清单当禁删白名单";`GOVERNANCE.md:161` raw_verdicts 行加回灌警示。

---

## 五、实事求是的自我认领

- **该认的错(my_change_at_fault=true)**:H-1(锁 KEEP 却漏配套约束 + CSV 写了字面为假的"缓存被砍仍独立有价值")是我这轮最实的过失;M-1/M-2/L-2/L-3 的数字与机读源不同步,是我"只同步了 L3_VERDICTS.md §1 一处脚注、没把 +2/-2/-1 的改动推到 summary.json、§4 标题、GOVERNANCE/BASELINE/PLAN"造成的"改一处漏其余"。
- **不背的锅(my_change_at_fault=false)**:P2.2 删模块却留 live import/自测(RT2 issue#2)、DROP_WITH_TOOL 标题"7"、summary.json 的 479/57/121 宽口径、dispatch_rule 与 R51 的 A-KEEP/B-删交接张力 — 这些都是 A 计划固有,先于我的改动存在。
- **方向无需回退**:所有底层裁定(architecture_fitness=KEEP、sort_strategy→HOLD_FOR_R51、priority 独立 KEEP、清 merge_cluster)经实证全部正确,CSV 机读真值自洽(429/37/6/HOLD1/DROP38=645)、A 自动化只认 DROP/MERGE:* 不会误删 HOLD_FOR_R51。**不需要撤销任何 verdict,只需补 H-1 的配套约束 + 同步几处数字。**

**最终建议**:补 P1-P3(high,在 A 执行 P2.2 前必须落地),P4-P5 顺手一起做。完成后即可放心"先 A 后 B"。

相关文件(绝对路径):
- `/Users/lurenxing/Documents/GitHub/----/.codestable/refactors/2026-06-01-test-gate-cleanup/_B_COMPAT_SAFEGUARDS.md`
- `/Users/lurenxing/Documents/GitHub/----/.codestable/refactors/2026-06-01-test-gate-cleanup/L3_verdicts.csv`(:620 / :432 / :323 / :431)
- `/Users/lurenxing/Documents/GitHub/----/.codestable/refactors/2026-06-01-test-gate-cleanup/PLAN.md`(:121 / :126 / §9)
- `/Users/lurenxing/Documents/GitHub/----/.codestable/refactors/2026-06-01-test-gate-cleanup/L3_VERDICTS.md`(:16/:22/:102/:104)
- `/Users/lurenxing/Documents/GitHub/----/.codestable/refactors/2026-06-01-test-gate-cleanup/summary.json`(:4-8/:18/:293-296)
- `/Users/lurenxing/Documents/GitHub/----/.codestable/refactors/2026-06-01-test-gate-cleanup/GOVERNANCE.md`(:50/:108/:112/:161)
- `/Users/lurenxing/Documents/GitHub/----/.codestable/refactors/2026-06-01-test-gate-cleanup/BASELINE.md`(:80/:82/:188)
- 证据源:`/Users/lurenxing/Documents/GitHub/----/tools/quality_gate_operations.py:5,751-764`、`/Users/lurenxing/Documents/GitHub/----/tools/quality_gate_support.py:32`、`/Users/lurenxing/Documents/GitHub/----/tests/test_architecture_fitness.py:25`、`/Users/lurenxing/Documents/GitHub/----/scripts/run_quality_gate.py:26`