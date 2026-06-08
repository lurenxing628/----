# 干扰图全局综合（Layer2 重建 · 只读不改产物）

> 输入：12 簇产物 clusters/*.md + _layer1_corrections.md（workflow ww7k5dwir / 149 agent / 第二双眼睛 verify 双核）
> 回盘 HEAD c2aa7501，行号全部簇内 rg 实盘，不信旧值。本档只综合不改任何 .py。
> 铁律遵守：承重只补注释/收口+parity、不删/统一/透传；灵魂线不新增兜底；P5 收口到已存在点；分层 0 违规；原 owner_pending 均按 OWNER-DECISIONS 裁后口径执行。

---

## 1) 全局原子簇清单

> 汇总 12 簇拆出的全部原子子簇。**原子单元 = 必须同一次提交（或显式串行+逐步重 rg）才安全的最小工作组**。
> 编号 G## 为全局唯一。⏸ 表示该单元曾需 owner 裁断，执行时一律按 OWNER-DECISIONS 的裁后口径。承重门标 🔒。

| G# | 所属簇 | 成员债 | 原子原因（一句话定性） | 内部顺序 |
|---|---|---|---|---|
| **G01** | NAV-PLANID | {R42, R60} AS-1 | 同符号 build_workbench_plan_context co-change + 共享 emit 点 link_query:118/154（只删一次,归 R42）+ 半截即新 P3 残渣 | 无先后必合并单提交；emit:118/154 归 R42 删,R60 不动；先迁 contract 三断言(:109/122/126,留 back_to)→删生产→自证 |
| **G02** | NAV-PLANID | {R64, R65} AS-2 | 同文件 navigation_links.py 双删,行号互漂（R64:66-67↑R65:74-78）；**逻辑零耦合**(不分提交也不 NameError,实盘 R64 `_has_navigation_date_range` 与 R65 `_target_url`/import 无符号交叉，:35 `_has_value`/:7 `TARGET_PAGE_PATHS` 留),原子仅为防行号二次漂移 | 同提交按行号自上而下;分提交则 R65 先 R64 后;均按符号定位。〔红队第1轮修订 R2-P6 精化〕真正驱动顺序的是 **R65 删 :4(urlencode)/:6(query_for_target) import 上移幅度最大**(致 R64 :66 上移)，非 def 位置——故按符号定位优先于裸行号。R65 自身三件套硬原子(删 def:74-78+化简:160+删 import:4/:6,缺一 NameError) |
| **G03** | NAV-PLANID | {R66} AS-3 | 孤立,删私有死副本 _context_summary(suffix 签名定位):150-163 | 单债;红线=不动 workbench_links:258 LIVE 同名异签 |
| **G04** | NAV-GUARD | {R58, R54, R44} SEQ-NAV | 三债同物理文件 navigation_publish.py(M/MM 漂移态),任一先落即移彼此行号；**R54 跨 5 物理文件**(见内部顺序) | 硬序 R58(纯注释:91 上方)→R54(B01 guard 收口+parity)→R44(B02 收 selected_plan_role 到 core,动手前重 rg :6/:36-37)。〔红队第1轮修订 R2-P1〕**R54 五套手维面必须同窗口、按符号收口、收口后逐套重 rg 复核字段集一致**：L2 navigation_publish.py:12(16键 G04 物理含)、L4 dashboard_workbench_context.py:8(16键≡L2 逐字)、L3 resource_dispatch.py:64(15键缺 plan_role_status)、L1 reports_workbench.py:36(12键别名源键缺三阻断态)、L5 gantt_task_detail.py:8(别名元组)；**分三组基数各钉 parity 守卫，禁任意 surface 向 16 键看齐**(补 plan_role_status=统一改行为违 R54 承重红线) |
| **G05** | EXEC-REVIEW | {LB02, LB05} A1 | 🔒 同一承重不对称两 finding,钉同段(签名:209+五硬钉:58/:180-181/:191-192/:221/:236),同一次注释+同一组回归 | 无先后一次落地;只增注释行不动 dict 键序 |
| **G06** | EXEC-REVIEW | {R62} A2 | 三档身份死分支(dict 三连键+模板 !=+xlsx or)三处消费方强原子,删一处不同步即半截残骸 | 被 G05 门控(A1 先 Batch-1,R62 后 Batch-3);动手按符号名 _resource_pair_payload+!= 重 grep |
| **G07** | EXEC-FACT | {LB01, R17, R20} A1(service) | 🔒 LB01 承重门控同文件 service.py 删改;R17 删:12/R20 改:52 同 import 块行号耦合;最危险边 LB01↔R17 同 _build_event_payload | 强序 LB01 注释先落(符号上方)→R17 删 service:12→R20 改 service:52(R17 后重 rg) |
| **G08** | EXEC-FACT | {R15, R17, R20} A2(support) | 同文件 support.py;R17 删:11/:81 推导式项→位移 R15:225/R20:24 | R15 先(已落地,守:225 raise)→R17 删:81/:11→R20 改:24;宜与 G07 同原子提交(R17/R20 跨 service+support) |
| **G09** | EXEC-FACT | {R15, R19, R13} A3(provider) ⏸ | 同文件 provider.py 删改互移行号;先收口语义(R15/R19)后删死物(R13) | O03/O05/O06/O37 已裁：强序 R15 先(SCC 最前置,收口解析)→R19 改:70-82→R13 末(删字段)；R13 删前 owner 再确认 |
| **G10** | EXEC-FACT | {R18, R19, R13关心:399} A4(repo) ⏸ | R18 改:401+R13 关心:399 同组 6 格 stub 共用一条护栏注释合批;R19:67 物理隔离仅文件级串行 | R18+R13(repo):399 共注释合批;R19 repo 处独立保守串行,无逻辑先后 |
| **G11** | GANTT | {R11≡R63} A1 | 同一物理动作（去重两份 _normalize:32+:113 收口到 gantt_critical_chain.py）,非两动作 | 无先后本就一次落地;禁拆两人各删一份(调用悬空) |
| **G12** | GANTT | {R12} A2 | 加 dropped_count/critical_chain_partial,**必须加在 G11 统一后的单份** helper | G11 先于 G12(强偏序);_empty_result:54 也须带 dropped_count |
| **G13** | GANTT | {R55} A3 ⏸ | **O09 已裁本轮不做**；仅保留暂停占位，重启条件=怀疑者过三问 + R11/R63 单份化前置就绪 | 本轮不得随 G12 同改 _normalize；禁破坏 `:385 None 回退` + support:55-56 分流判据 |
| **G14** | GANTT | {R10} | 删死方法 gantt_service.py:60-62+stub:59-60,逻辑零重叠,纯物理同 PR | 与 G11/12/13 同 PR(PHASE0§3 同文件勿并发改),任意序;删后 grep 复核 resolve_version:64 在 |
| **G15** | CONFIG-DUAL | {LB07, R71, R47} ASC-1 ⏸ | 🔒 config 双栈 helper 锁步收敛;LB07 承重安全网前置 R71/R47;R71 owner 已裁仅 parity 守卫、不物理合并 | 硬序 LB07 先(注释+扩 parity,Batch-1 ROOT)→R47 对称删动作；R71 只落 parity 守卫，物理收敛本轮不做 |
| **G16** | CONFIG-DUAL | {R45 ≡ R48} ASC-2 | 同一物理文件 config_adapter.py 整文件删,两叙述视角=一次删除 | 无先后合并单提交+同提交退 sp06:15;漏退→FileNotFoundError 响亮非静默 |
| **G17** | CONFIG-DUAL | {R31} ASC-3 | 删 shared 源 value_policies.py:9 死常量,跨簇绑 R33 删序 | 单债;R33 不晚于 R31(否则 facade:11 残 import loud ImportError) |
| **G18** | CONFIG-DUAL | {R26} ASC-4 ⏸ | 5 顶层 shim 删,三步迁移须同窗口,但与本簇余成员无原子绑定,Batch-14 全局最晚 | 晚于 R29/R33/R52 三桶收敛(facade 删晚于收敛硬约束) |
| **G19** | PARSE-INT | {R01, R04} A1 | 同文件 schedule_payload_contract.py 强行号互撞(R04:72 落在 R01 删的 _iter:67-87 内) | 强序 R01 先删(:67-87 含:72,缩收口面 6→5)→R04 后收口(剩 5 点,6 处 except 同步加 ValidationError 不可拆);必同 PR;依赖 F1 |
| **G20** | PARSE-INT | {R59} A2 | 独立文件 report_number_parsing.py,与 R04 共享 F1 门(reject_integer_float) | F1 落地后 R59 才收口(否则撞续命测试:247/:250);F1 后可独立提交 |
| **G21** | PARSE-INT | {R28} A3 | 完全独立叶子,收口到已存在 parse_finite_float,不改 number_utils 任何行,不依赖 F1 | 任意排期;唯一同步=退/留 fitness 白名单:77 |
| **G22** | PARSE-INT | {R08, R09} A4 ⏸ | 同文件 viewmodel 串行避免行号互撞;R09 跨子簇(B 副本归此,A 副本归 G19 邻域) | R08 先(B01)→R09 后(B05)串行;O01/O02 已裁：只收编 A/B 两 Optional 副本，C 严格保持不动，persistence_errors:13 归 R04 禁区+注释；R09 双路 parity(C 严格 5.9→None vs A/B 宽松 5.9→5) |
| **GF1** | PARSE-INT | F1(reject_integer_float 非债) | A1/A2 共享前置门,加在 strict_parse:46 经:81 透传,**必默认 False**(默认 True 炸 sgs_graph 等 parse_required_int 调用方) | 最先落+默认 False+自带 parity;门控 G19(R04)/G20(R59) |
| **G23** | COMPAT-DISPATCH | {R33, R30} A1 | 同改 config_service_component_contract 测试+R30 删 shared 实现/R33 删壳 re-export,删序错即 ImportError | 硬序 R33 步1(迁两测试 import)→R30(删 shared 实现/三 FieldPolicy/三常量)→R33 步2/3(删壳+:411 断言) |
| **G24** | COMPAT-DISPATCH | {R49, R50, R51} A2 | 同物理文件 dispatch_rules.py 三债行号互撞(R51 删首函数上移 R49/R50) | 一次原子 diff 按符号名/快照同删;心智序 R49(清场)→R51(删解析器+连退测试)→R50(删 mean_positive+import statistics);从大行号往小删 |
| **G25** | COMPAT-DISPATCH | {R49 之 evaluation/ortools 4 行} A3 | R49 同债旁支，不再作为 Batch-A 独立动作 | 并回 G24(R49+R50+R51) 一次原子执行；删后 `rg parse_dispatch_rule` 零生产残引用 |
| **G26** | COMPAT-DISPATCH | {R29} A4 | O20 已裁 KEEP；授权 CSV ABSENT+全量 delegation-facade 半截在场 | 只补显性「有意保留」注释，不进任何薄壳化/删除批，不阻塞 G18 |
| **G27** | PLAN-IDENTITY | {R22, R21} ① ⏸ | dpr_dict wrapper precondition 强耦合;R21 删 import 区位移 R22 wrapper 锚 | 硬序同窗口 R22 先(parity 24 键 exact Batch-1→收口委托 build_plan_identity/to_dict)→R21 后(删 3 死 shim+3 import,严守保留:32-39 wrapper) |
| **G28** | PLAN-IDENTITY | {R23} ② | 独立先落(无前置债),收口 model _normalize_role | 单债;软序与同文件 R34 协调(R23 先落后 R34 按符号重 rg 定位);与 R22 无序约束 |
| **G29** | PLAN-IDENTITY | {R72} ③ ⏸ | 独立叶子,收口落点 web scheduler_utils,与 R44 协调非排序 | O19 已裁：web/core 各落各点 + 补 request import；与 R21/R55/R44 同文件行号联动，谁后做谁重 rg |
| **G30** | RESOURCE-REPO | {R34, R35} AC-1 | 同物理文件 schedule_repo.py 硬同批,R35:61-69 夹在 R34 删段:59↘:114 之间 | O10 已裁纯删；无功能先后作一原子 diff,按符号名自下而上删；若未来另改裁迁 detail_queries 活孪生，才回升为 R05 后置前置 |
| **G31** | RESOURCE-REPO | {R38-part, R39} AC-2 | 同文件 part_repo.py 硬同批,删 R39:32 致 R38:71 上移 2 | 无功能先后同 commit 按符号名;分 hunk 则先 R39 再以新行号定位 R38 |
| **G32** | RESOURCE-REPO | {R38 op_type:73/operator:85 份} AC-2′ | R38 三处 list_as_dicts 死簇,op_type/operator 两份无同文件兄弟,SQL 列集各异禁抽 helper | 可独立删,随 R38 同 PR 但物理隔离;记三笔独立删 |
| **G33** | RESOURCE-REPO | {R05} AC-3 🔒⏸ | 🔒 收口点扩容三原子小步,步内不可换序;本簇唯一承重(verdict=LB) | O15/O16 已裁：强序 步1 扩 collar(含 include_team_context + 派工轨单独入口 + 空 id 全量)→步2 补 5 条 parity→步3 收敛 repo:461-463/:454-460+_normalize_scope_type |
| **G34** | RESOURCE-REPO | {R67} AC-4 ⏸ | 抽单一常量,4 处手抄须全收或①②必收③④酌情;半截去重比现状更危险 | O18 已裁：①②必收，第 4 处 superset 保现状（③④全收或全不收）；常量须 tuple 保序 |
| **G35** | RESOURCE-REPO | {R36} | ISOLATED,直删 batch_operation_repo.py:25-35/50-61 两方法 | 单债从后往前删;本桶最早可落之一 |
| **G36** | RESOURCE-REPO | {R37} | 直删 operator_machine_repo.py:82-90;同文件零碰撞 | 单债;删后 grep 活近亲 list_links_with_operator_info:92 仍在(误删静默炸人机分组) |
| **G37** | GRAPH-ERR-DIAG | {R02} A1 | 独立单债,test-only re-export 壳,生产零消费 | 单债内两步不可颠倒:先拆测试 import(只 build_first_wave_ready_nodes 改指)→后删壳:461-475 |
| **G38** | GRAPH-ERR-DIAG | {R06, R27, gantt 空包} A2 | **同收口点同两行**(SP05:310 存在循环+:315 delayed 循环),逐增量摘产生中间态致 old_string 失配 | 无先后,只有"四包同提交"单一安全顺序:一次改:310 成三元组+删:315-316+删四目录 |
| **G39** | GRAPH-ERR-DIAG | {R52, R25} A3 | O07 已裁 B 保留：impl 留作差分 oracle，R25 垫片保留 | 只补「我是故意的」注释；不删 impl、不删垫片、不新建 `test_sgs_graph_ready.py` |
| **G40** | GRAPH-ERR-DIAG | {LB08, R46} A4 🔒⏸ | 🔒 同文件 scheduler_public_errors.py,LB08 注释钉死承重边界后 R46 才能保护下删:162-164 | LB08 注释先落(或同提交先于 R46)→R46 删:162-164(按符号 grep 重定位,不照搬);O35 已裁：注释产出点按 `internal_operation.py:119/148/150/152/154` 实证改写，禁贴 planned/auto_assign |
| **G41** | GRAPH-ERR-DIAG | {R14} A5 ⏸ | 独立单债,delay 诊断死三件套;非裸删,删前三步前置+跨簇 LB01 同符号让位 | 前置三步(迁灵魂线测试/改 roadmap/确认无树外调用)后删:42-54+:114-139;删死门不得顺手修 resolve_plan 静默回退(铁律 4) |
| **G42** | GRAPH-ERR-DIAG | {R24} A6 | O23 已改裁保留不删：core 预留件留作诊断回归 core 契约层未来地基 | 只补「故意保留」注释 + 事实记录；不删 core 文件、不剪测试、不调和 roadmap；路 B 改活 web 路径仍违铁律 5 |

**计数：42 个原子单元（G01–G42）+ 1 个共享前置门 GF1（reject_integer_float，非债，是 R04/R59 共享的 strict_parse 改造）= 共 43 个调度单元。**
- 多债强原子（≥2 债同提交/同 diff）：G01,G02,G04,G07,G08,G09,G10,G11,G15,G16,G19,G22,G23,G24,G27,G30,G31,G38,G39,G40 = 20 个
- 单债原子单元：G03,G05*,G06,G12,G13,G14,G17,G18,G20,G21,G25,G26,G28,G29,G32,G33,G34,G35,G36,G37,G41,G42 = 22 个（G05 名义两债 LB02/LB05 但实为同一承重不对称的一次注释，归并计）
- 承重门 🔒：G05,G07,G15,G33,G40（含 GF1 准承重默认值门）
- 原 owner_pending ⏸ 裁后分流：G09/G10/G22/G27/G29/G33/G34/G40/G41 按 OWNER-DECISIONS 执行；G13/R55 本轮暂停，G15/R71 仅 parity，G26/R29、G30/R34、G39/R52、G42/R24 已裁后去挂起。

> 注：73 条债（80 原始 − 已 fixed/误标净化）全部归入上述单元。已 fixed 6 债（LB03/LB06/R07/R16/R56/R57，corrections E）不占调度单元，仅作前置已完成态 + 认账残留（见 §5）。新债 N1/N2（corrections C）不单独成原子单元，挂在毗邻单元同期处置（N1↔G04/G22、N2↔G04/G22 邻接，补注释+绑契约）。

---

## 2) 全局有向边表 + 拓扑排序 + DFS 验环

### 2.1 跨原子簇有向边表（仅留**跨单元**边；单元内顺序已在 §1 内部顺序列固化）

> 关系类型：**H**=硬序（违序即 ImportError/NameError/契约红/承重失效）；**S**=软序（零成本先后/重 rg 纪律）；**P**=前置已完成（fixed 满足）。
> 方向 `A→B` 读作「A 先于 B / A 门控 B」。

| # | 边（源→汇） | 关系 | 类型 | 实盘依据 |
|---|---|---|---|---|
| E01 | GF1 → G19(R04) | 共享前置门 | **H** | reject_integer_float 默认 False 先绿,R04 才收口(否则现有 parse_required_int 调用方 3.0 由接受变 raise) |
| E02 | GF1 → G20(R59) | 共享前置门 | **H** | 同上;R59 裸收口撞续命测试:247/:250 |
| E03 | G04(R54) → G01(R42/R60) | 同符号 co-change build_workbench_plan_context | **H** | R54 guard 字段已落 workbench_links:206-207,R42 删 plan_id 形参:191 须 rebase 其后(签名互撞)。批次张力:R42 batch_hint=3 vs 须与 R54 batch=2 同批,owner 裁。〔红队第1轮修订 R2-P5〕**R42 删形参的安全性取决于 collar 全调用方**，实盘 6 个生产调用方：navigation_context:57/76、dashboard_workbench_context:119、resource_dispatch:95、gantt_task_detail:78、reports_workbench:77、navigation_links:40，**外加第 6 个未登记的 analysis_links.py:24**——已 rg 确认 analysis_links:24 调用**未传 plan_id**(kwargs 无)，故删形参对它安全；但它是 collar 签名只读确认点，删形参前须复核全 6 调用方无一传 plan_id= 防 TypeError(analysis_links 不抄 guard 字段=benign passthrough，非第 6 套手维面，不增 R54 计数) |
| E04 | G04(R54) → G03(R66) | 同文件行号前置 | **S** | R54 改 reports_workbench:36 漂移 R66:150,R66 按 suffix 符号重定位 |
| E05 | G23(R33) → G17(R31) | facade 删序 | **H** | R33 删 value_policies 壳须不晚于 R31 删 shared 源:9,否则 facade:11 残 import loud ImportError |
| E06 | G23(R33) → G17(R30,R31) | 三常量 re-export facade | **H** | 〔红队第1轮修订 R3-发现2〕实盘壳:6-8 `import (READ_FILTER_ONLY,VALUE_DATE,VALUE_DATETIME)`+:11 WRITE_INTERNAL_ONLY；R30(删 shared 三常量:12/16/17)与 R31(删 shared WRITE_INTERNAL_ONLY:9)同为 shared 侧删动作彼此无序，真硬约束源是壳 R33 先停 import。原标 `R30→R31` 在两个对等删动作间生造方向，已改 `R33→{R30,R31}`(R30/R31 同窗口同 diff，唯一硬前置 R33 步1) |
| E07 | G26(R29) → G18(R26) | facade 删晚于收敛 | **H** | PHASE0§10.2;R26 顶层 shim 2 离线消费者经老路径,先删 shim 致其测试红；O20 KEEP 注释闭合后视为满足 |
| E08 | G23(R33) → G18(R26) | facade 删晚于收敛 | **H** | 同上(B06 桶) |
| E09 | G39(R52) → G18(R26) | facade 删晚于收敛 | **H** | 同上(B09 桶)；O07 KEEP 注释闭合后视为满足 |
| E10 | G15(R71) → G18(R26) | 转出边 | **S** | R71(B03)先 R26(B14)后天然满足,不同文件不撞行号 |
| E11 | G18(R26) ↔ G19(R01) / R43 | SP05 同文件串行 | **S** | 各改 SP05 不同模块键段,串行编辑避 git 行号漂移误合,无逻辑依赖 |
| E12 | LB03(B01 承重)+G27p(R22 parity) → G27(R22/R21) | parity 先于收敛 + same_symbol build_plan_identity | **H** | LB03(B01 承重注释+guard 收口)须全局先落于 B02 身份族;R22 先落 24 键 exact parity 钉键集再收敛 |
| E13 | G07a(LB01 承重注释) → G41(R14) | 承重让位 + same_symbol _resolve_strict_plan | **H** | R14 删:134-139 前 LB01 承重裁断必先行(同符号,删除让位) |
| E14 | G41(R14) → G05(LB02/LB05) / R61 | report_engine 邻域避让 | **S** | R14 迁灵魂线测试触碰 report_engine.py 邻域,LB02/LB05 锁某段须避让 |
| E15 | G40(R46) → G22(R09) | _positive_int:167 软位移 | **S** | 同文件无调用关系;R46 删:162-164 后 R09 动:167 按符号 grep 重定位 |
| E16 | G09/G10(R19) ↔ G19(R01) / G40(R46) | __all__ 同符号块 | **S（伪串行降级）** | 红队第2轮 P-RT22-02 已判伪串行：R19/R01/R46 三个 `__all__` 分属三文件且 R46 根本不动 `__all__`；登记备查，不作执行门 |
| E17 | G33(R67) → G01(R42) | diff-hunk 串行 | **S** | 共享 reports_export_support.py + scheduler_navigation_links.py 两元组,改不同键零语义冲突,串行避 hunk 互撞 |
| E18 | G33(R05) → G30(R34) | 软约束(条件硬) | **S** | R05 Batch-8 先于 R34 Batch-13 零成本;仅 R34 选"迁 detail_queries 用例到活孪生"才回升硬前置 |
| E19 | G28(R23) → G30(R34) | 同文件行号联动 | **S** | R23 最小落法让 query_service 后续锚点净上移 4 行（import +1、重复块 -5；`get_plan_time_span_for_resolution:210→206`）,R34 基于删后符号重 rg 定位 |
| E20 | G27(R21) → G04(R44) | 收口范式先例 | **S** | R21 删 selected_plan_role re-export shim,R44 应直接 re-export core 不照抄 |
| E21 | G29(R72) → G04(R44) | 收口落点协调(非排序) | **S** | R72→web scheduler_utils,R44→core view_context,两落点;owner 共识 web/core 各落各点 |
| E22 | G13(R55) → G27(R21)/G04(R44)/G29(R72) | 消费者只读触发条件勿砍 | **S** | R55 本轮不执行；他债改 scheduler_gantt:345-351 时仍勿砍 resource_type/resource_id 触发条件 |
| E23 | G39(R52) → G24(R50) | sgs.py 弱边 | **S** | R52 impl 在 ready_queue.py 不动 sgs.py,仅簇内共现登记 |
| E24 | G19(R04) ↔ G40(LB08) | 承重认账协同(毗邻) | **S** | R04 在 auto_assign_resource_errors.py 改哨兵 B 补注释前,须确认 LB08 认账注释已落或同批 |
| E25 | G22(R09) → R07(已 fixed) | 前置已完成 | **P** | R07 结构前置已 fixed；O31 已裁需统一成 AppError/ErrorCode.NOT_FOUND 并补 schedule=None→raise 回归；R09 收 A 副本(service:24)仍按符号重盘 |
| E26 | N1 → G22(R08) / G04(R54/R58) | 新承重邻接(execution_context:129-130) | **H(注释)/S(行号)** | R08 删死分支依赖 service:127≡:130 同源,N1 补"我是故意的"注释+绑 parity 守卫先于 R08 删;N1 与 R54/R58 同护栏概念 Batch-2 同期不同文件不撞行号 |
| E27 | N2 ↔ G04 / G22 / LB01宿主(feedback_service) | 新承重(event:156-163 return 0) | **S** | 〔红队第1轮修订 R1-P4 升精〕event.py 被 feedback_service(LB01宿主)/viewmodel(R08R09宿主)/operation_execution_feedback_actions/gantt_adjustment_publish_service 多处 import(rg 实盘命中)；sentinel 0 进 previous_event_id 下游拼接(:205/:218/:246)。补注释(末位无后继允许 0)+绑"非末位缺 id 必抛错"契约——**禁删 `if index<total: raise`(:161/:162) 之外，:179 return 0(__suggest_reschedule 默认)+:205 previous_event_id=0 初值同为承重 sentinel，禁顺手统一/置非 0**。本簇不触发结构动作，但 event-id 契约与 LB01 宿主同源(均经写侧消毒层) |
| E28 | R09(G22) ↔ LB01 最终底(operation_execution_scope.py:36-50) | 同文件承重毗邻 | **S** | 〔红队第1轮修订 R1-P1〕R09 收口家 `parse_positive_execution_int`:9 与 LB01「配套最终底」`validate_current_official_execution_scope`:36(三 raise :44/:47/:50) 同住一个 3499B 小文件(:77-79 调用点把两者夹一起)。R09 收编时**禁碰 :36-50**(删空行/调 import/移函数都会漂 raise 锚点)，按符号非行号定位。EXEC-FACT §D 仅说「禁删其 raise」此前未回连到 R09/G22 |
| E29 | N1 ↔ R09(C 路 context.py:28-30) | 同文件承重毗邻 | **S** | 〔红队第1轮修订 R1-P3〕R09「C 路严格 5.9→None」parity 实证锚点 = context.py:28-30(`_positive_int` wrap `parse_positive_execution_int`，调用点 :96/:97/:107/:258/:271/:272)，而 N1 注释落点 can_write_feedback :129-130 在**同文件**。E26 原只连 N1↔R08/R54/R58，漏 N1↔R09。收编 A/B 副本前先在此文件钉死 C 路 parity；N1 注释与 R09 C 路同期改同文件，谁后做谁重 rg |

### 2.2 拓扑排序（DAG 批次草案）

> 仅对 **H 边**做拓扑分层（S 边作批内/相邻软编排,不约束分层；P 边=前置已满足不入排序）。
> 全局承重根（B01/B03 承重注释门）必须最先。⏸ 单元按 OWNER-DECISIONS 裁后口径落入对应批次。

```
ROOT（承重注释 + 共享前置门，纯增量零结构，最先落）
  ├─ GF1   reject_integer_float 默认 False + parity          [门控 G19/G20]
  ├─ G15a  LB07 双栈 @dataclass 注释 + 扩 spec_sync parity    [门控 G15 收敛/R47 删参]🔒
  ├─ G07a  LB01 两处「我是故意的」注释                          [门控 G07 service 删改]🔒
  ├─ G05   LB02/LB05 承重注释 + 回归(173 行既有)               [门控 G06]🔒
  ├─ G40a  LB08 承重注释 + 绑 regression 契约                  [门控 G40 删 R46]🔒⏸(O35 已裁 internal_operation 产出点)
  ├─ G33a  R05 步1 扩 collar + 步2 五条 parity                [门控 G33 步3 收敛]🔒⏸
  ├─ LB03  B01 承重注释 + guard 收口(全局承重族,他簇)          [门控 G27/全 B02 身份族]🔒
  └─ G27p  R22 24 键 exact parity 先落                        [门控 G27 收敛]⏸

Batch-A（独立死叶子 / 零前置 / owner=false，最早可落）
  G14(R10) G16(R45≡R48) G21(R28)
  G28(R23) G31(R38part+R39) G32(R38 op_type/operator) G35(R36) G37(R02)
  G11(R11≡R63) G38(R06+R27+gantt)
  *G03 受 E04 软序 → 实际延后紧随 G04；G25 并回 G24，不在 Batch-A 单独落

Batch-B（依赖 ROOT 承重门 / 单门控前置）
  G06(R62)         ← G05
  G07(R17/R20)     ← G07a 🔒
  G08(R15/R17/R20) ← 与 G07 同原子提交(R17/R20 跨 service+support)
  G12(R12)         ← G11
  G13(R55)⏸        ← O09 已裁本轮不做，仅暂停占位
  G19(R01+R04)     ← GF1（+ E24 与 G40a 认账协同）
  G20(R59)         ← GF1
  G24(R49含G25旁支+R50+R51) ← schedule_params/optimizer_config 收口点只读在位（已满足）
  G40(R46)         ← G40a 🔒⏸
  G30(R34+R35)     ← O10 已裁纯删（E18 软自 G33；未来若迁活孪生才回升前置）
  G36(R37)
  G39(R52+R25)     ← O07 已裁 KEEP：保留 impl+垫片，只补注释

Batch-C（身份族收敛 / 收口委托，依赖承重族 + parity）
  G04(R58→R54→R44) ← LB03(B01) + R22 parity；同批带走 E03→G01
  G01(R42+R60)     ← G04(E03 硬同批 同符号 rebase)
  G27(R22+R21)     ← LB03 + G27p（E12）
  G09(R15→R19→R13)⏸ ← O03/O05/O06/O37 已裁：R15→R19→R13 串行，R13 删前 owner 再确认
  G10(R18+R19+R13)⏸ ← O06 已裁 R13 删前再确认；R18 stub 保契约护栏
  G29(R72)⏸        ← O19 已裁 web/core 各落各点 + 补 request import（E21 软自 G04）
  G15(R47+R71)⏸    ← G15a 🔒（R71 已裁仅 parity，不物理合并）
  G22(R08+R09)⏸    ← N1 注释(E26) + R07 前置(E25,已满足)；O01/O02 已裁双路 parity
  G33(R05 步3)🔒⏸  ← G33a 步1/步2（按 owner 已裁 collar 形态）
  G34(R67)⏸        ← 按 O18 裁定处理第 4 处 superset 收编
  G17(R31)         ← E05/E06 与 G23 同窗口
  G23(R30+R33)     ← R33 步1 先（簇内硬序）

Batch-D（facade 删除最晚 / 跨 owner-pending 收口）
  G18(R26)         ← G26(R29) + G23(R33) + G39(R52) 三桶收敛后（E07/E08/E09 硬前置）+ E10 软自 G15
  G26(R29)         ← O20 已裁 KEEP + 注释，不阻塞 G18
  G41(R14)⏸        ← LB01 承重裁断（E13 硬让位）+ 三步前置（迁灵魂线/改 roadmap/确认）
  G42(R24)         ← O23 已裁 KEEP + 注释 + 事实记录，不删不调和 roadmap（‖ G41 可并行）
```

### 2.3 DFS 验环结果

**结论：无环（DAG 成立）。** 对全部 H 边做 DFS（按 §2.1 方向，三色标记 white/gray/black）：

- 承重根层（GF1/LB01/LB02/LB05/LB08/LB07/LB03/R05-step1/R22-parity）零入边，是纯 source。
- 唯一双向标记的边均为 **S（同文件行号联动 / 历史伪串行登记 / 认账协同）**，不构成 H 环：
  - E16（R19↔R01/R46 __all__）：红队第2轮已降为伪串行登记，三处 `__all__` 不在同一物理文件，且 R46 不动 `__all__`，不作执行门。
  - E24（R04↔LB08）：认账协同非删除依赖，LB08 注释先落（ROOT）→ R04（Batch-B），单向。
  - E11（R26↔R01/R43 SP05）：同文件串行编辑各改各段，无逻辑依赖，可任意定序，非环。
- 跨簇 H 链全部单向收敛：`GF1→{G19,G20}`、`G04→G01`、`G23→G17`、`{G26,G23,G39}→G18`、`G07a/LB01→G41`、`LB03+G27p→G27`、`G15→G18(S)`——无任一汇点回指其源。
- **特别核查 R09 跨子簇（G19 邻域 A 副本 + G22 B 副本）**：A 副本随 G19/R07 前置，B 副本随 G22；两副本分两路 parity，不互为前置 → 无环。
- **特别核查 G04 内部 SEQ-NAV（R58→R54→R44）与 E03（R54→R42/R60）**：R54 在 G04 中位，对外 E03 出边指向 G01；R42/R60(G01) 不回指 G04 任何成员 → 无回边。
- 〔红队第1轮修订〕**新增 E28/E29 复核**：E28(R09↔LB01 最终底 operation_execution_scope.py:36-50)、E29(N1↔R09 C 路 context.py:28-30) 均为 **S 软边（同文件承重毗邻，按符号定位+重 rg 纪律，非删除依赖）**，不引入 H 回边；A14/E06/A15 方向修正只纠正既有 H 边指向不新增边 → DAG 仍成立。

> **环成员清单：空（NONE）。** 全图为单向收敛 DAG，可拓扑分层执行（红队第1轮修订后仍无环）。

---

## 3) 重灾区文件清单（≥2 债命中且顺序敏感）

> 判据：**同一物理 .py（或同一测试文件 / 同一 emit 点）被 ≥2 债改动 + 行号/符号/键互相位移或互撞**。按危险度排序。
> 「改动段」均 2026-06-05 簇内 rg 实盘。

| 危险度 | 物理文件 | 命中债 | 改动段（互相位移/互撞点） | 顺序约束 |
|---|---|---|---|---|
| 🔴 最危 | `core/services/scheduler/operation_execution_feedback_service.py` | **LB01**(承重) + R17 + R20 | LB01 硬拒:369-371/第二门:381/写死消毒:471-473/审计 dict:347-356；R17 删死 import:12；R20 改 labels import:52；**LB01↔R17 同 _build_event_payload(:455-494)函数体**(最危险边) | G07 强序：LB01 注释先落→R17 删:12→R20 改:52(R17 后重 rg)；🔒承重门控全文件删改 |
| 🔴 最危 | `core/services/report/execution_review.py` | **LB02+LB05**(承重) + R62 | 承重五硬钉:58/:180-181/:191-192/:221/:236+签名:209(禁加形参)；R62 三档死分支:358-441(dict 三连键+_resource_pair_payload:417+早退:437-441)；护栏区:58-236 vs 死分支:358-441 零重叠但 A1 注释下推 R62 行号 | G05 注释先落(Batch-1)→G06 后做(Batch-3)；R62 按符号名+!= 重 grep,绝不照抄行号；禁碰禁区+禁加形参 |
| 🔴 最危 | `core/services/scheduler/gantt_critical_chain_provider.py` | R11/R63 + R12 + R55 + R13(EXEC-FACT 跨簇,实为 execution_fact_provider 不同文件) | R11/R63 去重 _normalize:113(call:180)；R12 加 dropped_count;R55 加 scope(须补 _copy:104-110)；`_copy:104` 与 `_normalize:113` 两独立 staticmethod **禁误删 _copy** | G11 统一单份 helper 先→G12/G13 加键穿三道白名单；A1 先于 A2/A3 强偏序 |
| 🟠 高 | `core/services/scheduler/gantt_service.py` | R10 + R55 + (R34/R21/R63/R11/R12 同文件弱) | R10 删死方法:60-62(禁误删活 resolve_version:64)；R55 filtered 病灶:344/:384/:385 None 回退；相距 280+ 行物理不重叠 | 同 PR 物理串行(PHASE0§3)；R10 任意序删后 grep:64；R34/R21 勿两 PR 并发改 |
| 🟠 高 | `core/services/scheduler/scheduler_navigation_publish.py` | **R58**(承重邻) + R54 + R44 | R58 注释:91 上方；R54 _PLAN_GUARD_FIELD_NAMES:12/_plan_guard_fields:82；R44 删 selected_plan_role def:36-37+import:6-7；M/MM 漂移态任一先落即移彼此行号 | G04 硬序 R58(注释)→R54(guard 收口)→R44(删 def,重 rg :6/:36-37)；禁动:91 整行/禁剔键 |
| 🟠 高 | `web/.../scheduler_workbench_links.py` | R42(NAV-PLANID) + R54(NAV-GUARD,跨簇) + R60 邻 | R54 加 guard 字段(签名:187/dict:229-258,已落:206-207)；R42 删 plan_id 形参:191/dict:233；**同符号 build_workbench_plan_context co-change MUST 同批** | E03 硬序 R54 先→R42 后 rebase 新签名；禁动 dict:229-258 guard 段/禁翻:292-304 fail-open;LIVE _context_summary:258 别误删(R66 跨文件红线) |
| 🟠 高 | `core/algorithms/dispatch_rules.py` | R49 + R50 + R51 | R49 删:25；R51 删首函数:28-35；R50 删末函数:112-132+import statistics:4；删任一处位移其下,R51 删首函数上移 R49/R50 ~7-8 行 | G24 一次原子 diff 按符号名/快照同删；心智序 R49→R51→R50,从大行号往小删；保 import math:3、:39 DispatchInputs |
| 🟠 高 | `core/models/schedule_payload_contract.py` | R01 + R04 | R01 删 _iter:67-87/count:90/has:94-95/__all__:414-415/孤儿 import:5；R04 收口 _strict_positive_int:50+6 调用点(**:72 落在 R01 删的 _iter body 内**) | G19 强序 R01 先删(:67-87 缩 R04 收口面 6→5)→R04 后收口(剩 5 点 rg 重定位,6 处 except 同步加 ValidationError);必同 PR |
| 🟠 高 | `core/data/repositories/schedule_repo.py` | R34 + R35 | R34 删:36-59/:114-126/:128-158；R35 删:61-69(**夹在 R34 删段:59↘:114 之间**) | O10 已裁纯删；G30 一原子 diff 按符号名自下而上删(:128-158→:114-126→:61-69→:36-59) |
| 🟡 中 | `core/services/scheduler/config/config_snapshot.py` + `core/models/schedule_config_runtime_coercion.py`(双栈对称) | **LB07**(承重) + R71 + R47 | LB07 双栈 @dataclass:7/:24 注释；R71 三 helper 收敛；R47 删死参 raw_value(model:83/service:63,在三 helper 之下)；改任一函数体位移彼此锚行 | G15 硬序 LB07 注释+parity 先(Batch-1)→R47+R71 同批(先删 R47 死参再 R71 收敛);禁碰 coercion loud raise 块(按符号非行号) |
| 🟡 中 | `web/viewmodels/scheduler_resource_dispatch_execution.py` | R08 + R09(B 副本) | R08 改死常量:25/死分支:227-228/:367-368；R09 改 B 副本 def:33+调用点:257/:258/:353；同文件删行位移彼此锚点 | O01/O02 已裁：G22 串行 R08 先(B01)→R09 后(B05)；只收 A/B Optional 副本，C 严格不动，persistence_errors:13 归 R04 禁区+注释 |
| 🟡 中 | `core/services/scheduler/gantt_plan_query.py` | R21 + R22(precondition) | R21 删 3 死 shim:42/46/59+import:14-25；R22 收口委托(dpr_dict wrapper:32-39 是 R22 precondition,R21 删 import 区上移 wrapper ~9 行) | G27 硬序 R22 先(parity+收口)→R21 后(严守保留:32-39 wrapper+:50-156 LIVE 函数);R22 用符号名锚 |
| 🟡 中 | `core/services/scheduler/schedule_plan_query_service.py` | R23 + R34 | R23 最小落法：import 增 `_normalize_role` 一行 + 删本地 `_normalize_role` 重复块（含分隔空行）→其后行号净上移 4；R34 benchmark repoint 旧锚 `get_plan_time_span_for_resolution:210` 落 R23 后为 `:206`(不改体) | E19 软序 R23 先落让 R34 基于删后符号重 rg 定位;R23 不碰:105-108 双段 |
| 🟡 中 | `core/data/repositories/part_repo.py` | R38(part 份) + R39 | R39 删 list_unparsed:32→R38 list_as_dicts:71 上移 2 | G31 同 commit 按符号名;分 hunk 则先 R39 再以新行号定位 R38 |
| 🟡 中 | `core/models/scheduler_public_errors.py` | **LB08**(承重) + R46 | LB08 注释:62 上方+禁区:62/:94/:142/:175/:218/:284/:340；R46 删死别名:162-164；双向行号位移(LB08 插 N 行下移:162;R46 删 3 行上移禁区);**含 R09 _positive_int:167 跨簇毗邻** | G40 LB08 注释先落→R46 删:162-164(按符号 grep 重定位);R46 删段与禁区零重叠 |
| 🟡 中 | `core/services/common/value_policies.py`(壳) + `core/shared/value_policies.py`(源) | R30 + R33 + R31 | R30 删 shared 三常量+三 FieldPolicy；R33 删 service 壳 re-export(:11/:29)；R31 删 shared 源:9；删序错即 ImportError | E05/E06 硬序 R33 步1→R30→R33 步2/3;R31 不晚于 R33;死保 config_contract:15 degradation |
| 🟡 中 | `tests/gate_meta/test_sp05_path_topology_contract.py` | R06 + R27 + gantt 空包(+R01/R26/R43 改别段) | R06/R27/gantt **同改:310 存在循环+:315 delayed 循环**(逐增量摘致 old_string 失配)；R01 改 schedule_persistence 键块:53-56；R26 改 SERVICE_BEHAVIOR_*:20-82；R43 改 ROUTE_* 段 | G38 四包一次性同提交(改:310 成三元组+删:315-316);禁碰:173 def/:318 断言;R01/R26/R43 串行各改各段重 rg |
| 🟡 中 | `tests/config/test_config_service_component_contract.py` | R33 + R30(交界) | R33 删:14/:16/:19 元组+:393-411 身份断言；交界:411 `parse_compat_date is` 在 R30 删实现后失效由 R33 步2 删 | G23 内 R33 步2/3 在 R30 之后 |
| 🟢 低-中 | `core/services/scheduler/execution_snapshot.py` | R19 + R01 + R46(__all__ 伪串行登记) | R19 收口点 positive_op_ids:28-40+导出:118-123；`:40 return sorted` 事实承重(sha256 指纹)；R01/R46 的 `__all__` 不在本文件 | E16 已降登记备查；R19 强制保 sorted |
| 🟢 低 | `web/.../reports_export_support.py` + `scheduler_navigation_links.py`(两元组) | R42 + R60 + R67 | R42/R60 删 plan_id:14/:11-12；R67 改资源键尾块元组；改不同键零语义冲突 | E17 diff-hunk 串行避互撞;R65 在 navigation_links 删 _target_url 三件套(:7 TARGET_PAGE_PATHS 禁删) |
| 🔴 承重邻 | `core/models/operation_execution_scope.py` | **R09 收口家**(:9) + **LB01 配套最终底**(:36-50) | 〔红队第1轮修订 R1-P1〕收口点 `parse_positive_execution_int`:9(:11/:17/:20 raise) 与 LB01 最终底 `validate_current_official_execution_scope`:36(三 raise :44/:47/:50) 同住一个 3499B 小文件，:77-79 调用点夹两者 | E28 同文件承重毗邻；R09 收编**禁碰 :36-50**(按符号定位，删空行/调 import/移函数都漂 raise 锚点)；承重文件 +1=6 |
| 🟡 中 | `web/viewmodels/scheduler_reports_workbench.py`(L1) | **R54·L1**(12 键别名源键) + R66(死副本) + R42/R60(邻) | 〔红队第1轮修订 R2-P1/P2/P4〕`_copy_plan_guard_fields`:36(12 键，**别名源键** data.get("requested_role")/("selected_role")/("is_official")/("is_preview")，缺 plan_role_status + 三阻断态)；调用点:98；R66 死副本 _context_summary:150 | R54 五套同窗口收口后逐套重 rg；**禁向 16 键看齐**(补 plan_role_status=统一改行为违承重红线) |
| 🟡 中 | `web/viewmodels/dashboard_workbench_context.py`(L4) | **R54·L4**(16 键，≡L2 逐字) | 〔红队第1轮修订 R2-P1/P4〕`_PLAN_GUARD_FIELD_NAMES`:8(16 键含 plan_role_status+三阻断态)；消费:130；collar 调用:119 | R54 五套同窗口；viewmodels 层(非 routes) |
| 🟡 中 | `web/routes/domains/scheduler/scheduler_resource_dispatch.py`(L3) | **R54·L3**(15 键，缺 plan_role_status) | 〔红队第1轮修订 R2-P1/P2/P3〕`_copy_plan_guard_fields` def:64(15 键，**缺 plan_role_status**=第三种基数)，guard 调用唯一 :109(非 §0 旧标的 call×2 :95/:199；:95 是 collar 调用)；:267 的 plan_role_status 是无关 internal_filters 不在元组内 | R54 五套同窗口；**禁补 plan_role_status「补齐」16 键**(违承重红线)；注：R08/R09 在另一文件 scheduler_resource_dispatch_execution.py，不并 |
| 🟡 中 | `web/viewmodels/scheduler_gantt_task_detail.py`(L5) | **R54·L5**(别名元组异机制) | 〔红队第1轮修订 R2-P1/P4〕`_PLAN_GUARD_FIELD_ALIASES`:8(别名元组，含 plan_role_status)；消费:94；collar 调用:78 | R54 五套同窗口；别名元组机制与同名键三套不同，禁混并 |

**重灾区计数：24 个物理文件/测试文件**（原 19 + 红队第1轮补登 5：operation_execution_scope.py + R54 缺席四文件 reports_workbench/dashboard_workbench_context/resource_dispatch/gantt_task_detail）被 ≥2 债命中且顺序敏感。其中 **6 个含承重点**（execution_review.py、feedback_service.py、navigation_publish.py、config_snapshot/coercion 双栈、scheduler_public_errors.py、**operation_execution_scope.py**），**3 个为「最危险边」宿主**（feedback_service.py 的 LB01↔R17 同函数体、execution_review.py 的承重五钉↔R62、gantt_critical_chain_provider.py 的 _copy↔_normalize 误删风险）。
> **R54 跨文件原子性补强**：R54 五套手维面跨 **5 个物理文件、3 种字段基数（L2/L4=16 键、L3=15 键缺 plan_role_status、L1=12 键缺三阻断态+别名源键、L5 别名元组）、跨两分层（3 viewmodels + 2 routes/domains/scheduler）**。G04 原子单元物理只锁 navigation_publish.py(L2) 1 套，另 4 文件须由「5 套字段集 parity」守卫钉同窗口同 diff，分三组基数各钉 parity，禁任意 surface 向 16 键看齐（详见 §1 G04 内部顺序 + §3.1）。

### 3.1 `_positive_int` 同符号 family 对照表（R1-P6 最高误删风险显性化）

> 〔红队第1轮修订 R1-P6〕全仓 `def _positive_int`/`parse_positive_execution_int` 同名但跨**两个语义 family**，2026-06-05 rg 实盘分类。收编者全仓 grep 一次撞 9+ 处同名异义函数，极易误删 STRICT 版当「重复副本」——这恰是灵魂线（坏值 raise）被静默削弱的入口。**顺序敏感铁律：收编只动 Optional family，STRICT family 一字不碰。**

| family | 语义 | 文件:行 | 性质 |
|---|---|---|---|
| **STRICT-raise**（`-> int`，坏值直接 raise，**R09 禁区，禁删当重复**） | bool/非数字/<=0 loud raise | `core/models/operation_execution_scope.py:9` | **R09 收口点本体**(:11/:17/:20 raise)；灵魂线 |
| | | `core/services/scheduler/operation_execution_feedback_support.py:161` | STRICT，禁碰 |
| | | `core/models/scheduler_public_errors.py:167` | STRICT，R46 删段(:162-164)毗邻但**不是同函数**，禁误删 |
| | | `core/services/scheduler/run/auto_assign_resource_errors.py:114` | STRICT，禁碰 |
| **Optional-None**（`-> Optional[int]`，R09 收口/收编候选） | 宽松归 None / 可 `or 0` | `web/viewmodels/scheduler_resource_dispatch_execution.py:33` | **B 副本**（已认，宽松 5.9→5，G22） |
| | | `core/services/scheduler/resource_dispatch_execution_service.py:24` | **A 副本**（已认，def:24 + 调用点 :169/:180/:181，放宽点在 :180-181 `==int(...)` 比较；G19 邻域/G22） |
| | | `web/routes/domains/scheduler/scheduler_resource_dispatch_execution_context.py:28` | **C 路已收口**（wrap 收口点，严格 5.9→None；调用点 :96/:97/:107/:258/:271/:272；与 N1:129-130 同文件，见 E29） |
| | | `core/services/scheduler/operation_execution_scope_read.py:21` | 已收口 C 族 |
| | | `core/services/scheduler/run/schedule_persistence_errors.py:13` | 〔R1-P2 新认，O02 已裁〕**第 3 份裸内联未收口**：`int(value or 0)` **不** wrap 收口点，调用点 :24/:56(`or 0`)/:77。归 R04 禁区+注释，不纳入 R09 收编面；执行 G22 时不得把它当 Optional 副本一起改。 |

> **R1-P2 收编面订正 + O02 裁后口径**：corrections A/§5.1 原称「剩 2 旧内联副本（viewmodel:33 + service:24）」。实盘 Optional-family 未收口副本中，R09 只收编已认的 2 份（viewmodel:33 / service:24）；schedule_persistence_errors:13 归 R04 禁区+注释。service A 副本不止 def:24 一处，含调用点 :169/:180/:181，parity 须钉调用点比较语义（5.9→5 vs 5.9→None 放宽点在 :180-181），不是改 def 一处即可。

### 3.2 承重护栏方向硬门（R1-P5 反向 fail-OPEN 污染防护）

> 〔红队第1轮修订 R1-P5〕corrections D + 三簇 §E 反复警告「LB03/LB06 勿粘 §90 LB-B4 反向 fail-OPEN 文案——现盘已 fail-CLOSED」，此前仅停在文字提醒，未在禁区表设硬门。R42 删 plan_id 时若顺手补 R56/LB06 认账注释，极易粘错方向（fail-CLOSED→fail-OPEN）= 承重护栏反转，**比漏边更危险**。以下为方向硬门（与承重禁区同级）：

| 禁区行 | 现盘方向(实盘 rg) | 认账注释必须写 | 严禁 |
|---|---|---|---|
| `web/navigation_context.py:79` (R56 退化禁区行) | **fail-CLOSED**：`plan_role=plan_role if plan_role in VALID_PLAN_ROLES else ROLE_ADOPTED`(非法 role→强制 adopted) | plan_role 非法→强制 ROLE_ADOPTED | 粘 §90 LB-B4 的 fail-OPEN 旧文案（写成「非法 role 放行/默认开放」） |
| `web/.../reports_page_support.py`(LB06) | **fail-CLOSED**：execution-review 强制 adopted + scenario=None | execution-review→强制 adopted+scenario=None | 同上方向反转 |

> 凡 R42/R66 认账注释动作触碰上述行，**先核现盘 fail-CLOSED 方向再下笔**，方向写反 = 承重击穿，按 P0 级处理。

---

## 4) 边类型分布 + 相对旧 146 边总变化

### 4.1 重建后边类型分布（跨原子簇边，§2.1 29 条 + 单元内固化边不计）

> 〔红队第1轮修订〕原 27 条 → 29 条：新增 E28(R09↔LB01 最终底同文件承重毗邻,R1-P1)、E29(N1↔R09 C 路同文件,R1-P3) 两条 S 边；E27 升精不增边；H 边方向修正(A14/E06=R3-发现1/2)不增减条数。

| 关系类型 | 条数 | 占比 | 说明 |
|---|---|---|---|
| **H 硬序**（违序即破坏） | 13 | 45% | E01,E02,E03,E05,E06,E07,E08,E09,E12,E13,E26(注释面),GF1 两门；E16(部分)为历史计数溯源，已降伪串行登记，不作执行门 |
| **S 软序**（零成本先后/重 rg 纪律） | 14 | 48% | E04,E10,E11,E14,E15,E17,E18,E19,E20,E21,E22,E23,E24,E27,**E28(R1-P1)**,**E29(R1-P3)**；E16 已降登记备查 |
| **P 前置已完成**（fixed 满足） | 2 | 7% | E25(R07),（LB03 列承重门非 P，仍待落注释） |

> 单元**内部**边（同一原子单元成员间的硬序，如 G04 的 R58→R54→R44、G19 的 R01→R04、G24 的 R49→R51→R50）已在 §1「内部顺序」列固化，不重复计入跨簇边。

### 4.2 相对旧 146 边总变化（删 N / 新 N / 降 N，逐条）

> 口径：旧 codemap registry 共 **146 条 interference_edge**（绝大多数 `same_file=true, same_symbol=false` 的粗匹配）。本轮经 corrections B 节假边清单 + 各簇 rg 回盘逐条裁定。

#### 删除（假边 / 已修前置对消）— 共 **27 条**

| # | 删除边 | 来源簇 | 删因 |
|---|---|---|---|
| D01 | R42↔R56 | NAV-PLANID | R56 fixed(E),退化为禁区行约束 |
| D02 | R42↔R57 | NAV-PLANID | R57 fixed(E) |
| D03 | R42↔LB06 | NAV-PLANID | LB06 fixed(D/E) |
| D04 | R60↔LB05 | NAV-PLANID | LB05 primary 实为 execution_review.py,link_query 共置噪声 |
| D05 | R42↔LB02 | NAV-PLANID | same_file 粗匹配,same_symbol=false |
| D06 | R66↔LB02 | NAV-PLANID | 同上 |
| D07 | R20↔R08 | EXEC-FACT/PARSE-INT | corrections B:R20 在 context.py:11 不碰 ..._execution.py |
| D08 | R20↔R09 | EXEC-FACT/PARSE-INT | 同上 |
| D09 | R20↔R12 | EXEC-FACT/GANTT | corrections B:gantt_tasks.py:8 直连 model 不经垫片 |
| D10 | R15↔R32 | EXEC-FACT | corrections B:os.replace(R32 backup) vs str.replace(R15:89)同名异物 |
| D11 | R16↔R15 | EXEC-FACT | R16 fixed,R15 state_builder 处已落地,边消解 |
| D12 | R45↔LB07 | CONFIG-DUAL | corrections B:schedule_params.py 是 greedy 同目录他文件非 config_adapter.py |
| D13 | R45↔R33 | CONFIG-DUAL/COMPAT | 同上 |
| D14 | R45↔R51 | CONFIG-DUAL/COMPAT | 同上 |
| D15 | R48↔LB07 | CONFIG-DUAL | R48≡R45 同物理文件,registry 同误标 |
| D16 | R48↔R33 | CONFIG-DUAL | 同上 |
| D17 | R48↔R51 | CONFIG-DUAL | 同上 |
| D18 | R26↔R43 | CONFIG-DUAL | scheduler_config.py basename 假碰撞(web/routes vs core/services) |
| D19 | R26↔R71(config_snapshot) | CONFIG-DUAL | 顶层 shim 5 行 vs 深实现 17655B,不同物理文件 |
| D20 | R50↔R25 | COMPAT-DISPATCH | sgs.py 假碰撞(R25=ready_queue.py,R50=dispatch_rules.py) |
| D21 | LB04↔R33 | COMPAT-DISPATCH | 不同 primary(boolean_normalize.py vs compat_parse.py 壳) |
| D22 | LB04↔LB07 | CONFIG/LEAF | corrections B:不同 primary_file,algorithms 零消费假引用 |
| D23 | R22↔R23 | PLAN-IDENTITY | view_context 假同文件(R23 真改 schedule_plan_role.py) |
| D24 | R22↔R44 | PLAN-IDENTITY | R44 真 primary=navigation_publish.py |
| D25 | R22↔R54 | PLAN-IDENTITY | R54 真改 viewmodels 不触 view_context |
| D26 | R37↔R41 | RESOURCE-REPO | 伪干扰:R37 不碰 equipment_pages.py |
| D27 | R02↔R25 | GRAPH-ERR-DIAG | 不同文件(R02=dispatch_context.py,R25=ready_queue.py),懒 import 非模块级边 |

> 另有 R13↔R18 强耦合**解除**（corrections B「解耦」）—算入「降级」非删除（边仍在但从硬→零耦合各自独立）。

#### 新增 / 强化（旧图缺或仅标 same_file，本轮坐实为真依赖）— 共 **17 条**

| # | 新增/强化边 | 来源簇 | 类型 | 依据 |
|---|---|---|---|---|
| A01 | R54→R42（same_symbol co-change 强化） | NAV-PLANID/GUARD | H | workbench_links:206-207 guard 字段已落,R42 删形参须 rebase |
| A02 | R54→R66（同文件行号前置） | NAV-PLANID | S | R54 改:36 漂移 R66:150 |
| A03 | R54 第 5 套手维面 gantt_task_detail:9-15 | NAV-GUARD | — | corrections C 升 3/4→5 套,别名元组机制 |
| A04 | R54/R58→N1（execution_context:129-130） | NAV-GUARD/PARSE | H(注释) | 执行重构新债,同护栏概念 Batch-2 同期 |
| A05 | R54→reports 第二注入路径（双分叉） | NAV-GUARD | — | reports 缺三阻断态字段经 overrides 另一路 |
| A06 | LB01→R17（同 _build_event_payload 强化） | EXEC-FACT | H | 最危险边,承重门控 |
| A07 | R19→R01/R46（__all__ 同符号登记） | EXEC-FACT/GRAPH | S(伪串行降级) | 红队第2轮 P-RT22-02 已判伪串行：三处 `__all__` 在三文件，R46 不动 `__all__`；仅登记备查 |
| A08 | R11/R63→R12（收口前置硬边 A1→A2） | GANTT | H | R12 加键必须在统一后单份 helper |
| A09 | R11/R63→R55（历史收口前置，本轮暂停） | GANTT | H(暂停占位) | O09 已裁 R55 本轮不做；仅保留重启条件，不能触发本轮执行 |
| A10 | R12⟂R55（历史同批提醒，本轮作废） | GANTT | S(作废) | O09 已裁 R55 不随 G12 改 _normalize |
| A11 | R29→R26（facade 删晚于收敛） | CONFIG-DUAL | H | 普查"0 消费者"被推翻,2 离线消费者；O20 KEEP 注释闭合后才放行 R26 |
| A12 | R33→R26（facade 删晚于收敛） | CONFIG-DUAL | H | 同上；G23 收敛先于 G18 |
| A13 | R52→R26（facade 删晚于收敛） | CONFIG-DUAL | H | 同上；O07 KEEP 注释闭合后才放行 R26 |
| A14 | R33→R31（删序硬约束） | CONFIG/COMPAT | H | 〔红队第1轮修订 R3-发现1〕原标 `R31→R33` 与 E05 `R33→R31` 自相矛盾。实盘壳 value_policies.py:3-11 import shared 源:9 WRITE_INTERNAL_ONLY，依赖方向=壳 import 源，须**先删壳 import(R33)再删源定义(R31)**否则 facade:11 残 import loud ImportError。已改 R33→R31 与 E05 对齐 |
| A15 | R33→{R30,R31}（B13 facade 三常量 re-export 硬序） | COMPAT-DISPATCH | H | 〔红队第1轮修订 R3-发现2〕原标 `R30→R31` 把两个对等 shared 删动作生造方向。实盘壳:6-8 import 三常量、:11 import WRITE_INTERNAL_ONLY；R30(删三常量定义)/R31(删 WRITE_INTERNAL_ONLY 定义)同侧无序，真硬前置是壳 R33 步1 先停 import |
| A16 | R04⇄R59（F1 reject_integer_float 互锁） | PARSE-INT | H | R59 收口强依赖 R04 的 F1 先落 |
| A17 | R04→6 处 except 同改 + R09 双副本分裂 + LB03+G27p→G27(R22/R21) + R67→R42 第二文件 + R06+R27+gantt SP05 两行 + R24 KEEP注释 | 多簇 | H/S | 见各簇 §C（合并计为 1 行多项,实条数另见下注） |

> A17 实含 6 个独立新增点（R04→6except 内部、R09 双副本分裂、LB03+G27p→G27、R67→R42 第二文件覆盖、R06+R27+gantt SP05 同两行原子边、R24 KEEP注释+事实记录）。**新增总计按独立边/原子点核：17 条**（A01–A16 + A17 折算 LB03+G27p→G27 + R06+R27+gantt SP05 + R67→R42 第二文件三条跨簇真边；其余 R04→6except / R09 双副本 / R24 KEEP 属单元内覆盖扩展不计跨簇）。

#### 降级（硬→软 / 解耦 / 方向反转）— 共 **18 条**

| # | 降级边 | 来源簇 | 降法 |
|---|---|---|---|
| L01 | R65↔R42 | NAV-PLANID | 节奏脱钩(R42 在该文件无改点)→弱同文件提示 |
| L02 | R64↔R42 | NAV-PLANID | same_file 噪声→非阻塞提示 |
| L03 | R60↔R54(navigation_links 元组) | NAV-PLANID | R54 all_files 不含该文件→零冲突无协调依赖 |
| L04 | R44「web 多兜底」方向 | NAV-GUARD | **refuted 反转**:core 更防御,import 真来源 schedule_plan_query_service,危险度降 low |
| L05 | R58「生产漏洞」 | NAV-GUARD | 降为潜伏护栏削弱(零生产消费,真放行走:469) |
| L06 | R54↔LB06 | NAV-GUARD/EXEC-REVIEW | LB06 fixed→非活动前置边 |
| L07 | R62↔A1(LB02/LB05) | EXEC-REVIEW | 同收口点语义竞争→同文件行号位移软序(零行重叠) |
| L08 | LB02/LB05↔LB06 | EXEC-REVIEW | 阻塞前置→认账协同(LB06 fixed) |
| L09 | R13↔R18 强耦合 | EXEC-FACT | **解除**:repo 已 stub raise,R13 不碰 repo,R18 独立补注释 |
| L10 | R13 自身性质 | EXEC-FACT | 死字段被 3 测试读活,直删→升 owner 二次确认 |
| L11 | R10↔R55 | GANTT | 硬同文件撞→软同 PR 物理串行(相距 280+ 行) |
| L12 | R12↔{R10/R11/R21/R34/R63} same_file 噪声 | GANTT | →非约束(gantt_critical_chain.py 内 same_file_siblings=[]) |
| L13 | R55→R21/R44/R72 | GANTT | 同文件→消费者只读触发条件勿砍软提醒 |
| L14 | R45↔R48 | CONFIG-DUAL | 同删合并(ASC-2),依赖边→合并标记 |
| L15 | R26↔R71 | CONFIG-DUAL | 转出边软相关,非硬阻塞串行 |
| L16 | R28↔{R04,R29,R33} | PARSE-INT | number_utils same_file 硬→软(R28 只调用不改) |
| L17 | R50 跨桶序 + R51→R49 运行期序 | COMPAT-DISPATCH | →同 diff 软编排 + 人工心智序 |
| L18 | R21↔R44 + R72↔R44 + R21/R72/R55 + R05→R34 + R46→R09 | 多簇 | 同文件硬碰撞→行号联动/落点协调软序 + R05→R34 硬→软 + R46→R09 软位移 |

> L18 合并多簇同质降级（PLAN-IDENTITY 三条 + RESOURCE-REPO R05→R34 + GRAPH-ERR-DIAG R46→R09）。**降级独立条数：18**。

### 4.3 净变化汇总

```
旧 146 边
  − 删除 27（假边 22 + 已修前置对消 5）
  + 新增 17 +2（红队第1轮补 E28/E29 同文件承重毗邻 S 边）= 19（同符号 co-change 坐实 / 收口前置硬边 / 执行重构新债 N1N2 邻接 / facade 删序 / 承重收口家同文件毗邻）
  ~ 降级 18（硬→软 / 解耦 / 方向反转，边仍在但不门控分层）
─────────────────────────────
重建后约 138 条边，其中跨原子簇有效约束边 29 条（H 13 / S 14 / P 2）；
其余 ~109 条降为单元内固化序 + same_file 软纪律（重 rg 即可，不入 DAG 分层）。
注：H 边仍 13 条（A14/E06 方向修正不增减条数，仅纠有向边方向）；全图仍无环（E28/E29 均 S 软边，零入环）。
```

> **结论**：旧 146 边大量是 `same_file=true/same_symbol=false` 的粗匹配噪声。本轮净化后，**真正门控批次分层的硬边仅 13 条**，全图无环，可安全拓扑执行。误删风险点全部收敛到 5 个承重文件 + 3 条「最危险边」（已在 §3 标定禁区）。

---

## 5) 与旧 MASTER-PLAN 16 批 DAG 的差异

> 因 Layer1 校正（corrections A/B/C/D/E/F）需对旧 16 批 DAG 做的结构性调整。逐条列。

### 5.1 修法被实质推翻 → 批次内容/前提改写

| 校正 | 旧 MASTER-PLAN 假设 | 校正后 | 对 DAG 的影响 |
|---|---|---|---|
| **R09 收口点已存在** | 「唯一批准新建 parse_optional_positive_int」 | 收口点 `operation_execution_scope.py:9 parse_positive_execution_int` **已存在**（执行重构新建,bool/非数字/<=0 loud raise）；3 新文件已正确收口 | **作废「新建模块」批次步骤**。〔红队第1轮修订 R1-P2 + O01/O02 裁定〕R09 只收编 2 个旧内联 Optional 副本（viewmodel:33 B副本 + service:24 A副本，A 副本含调用点 :169/:180/:181，放宽点在 :180-181 比较）；schedule_persistence_errors.py:13 归 R04 禁区+注释，不进 R09 收编面。须**分两路 parity**（C 路严格 5.9→None，实证锚点 context.py:28-30 见 E29 vs A/B 宽松 5.9→5）。收口点同住一文件的 LB01 最终底:36-50 禁碰（E28）。同名异义 family 对照见 §3.1（STRICT 4 处禁删 vs Optional 5 处）。G22 不再含「建模块」步，改「收编+分路 parity」。R46→R09 由「同文件硬边」降软位移（E15） |
| **R13 解耦 R18** | R13 连带删 repo:254 方法,与 R18 同原子提交 | 死字段被 3 测试读活（reschedule:196、scope_read_contract:108/190/220）；repo:399/401 已 stub raise（契约护栏）,R13 **不碰 repo**,R18 独立补注释 | **拆分原 R13+R18 同原子批**。R13(G09 provider 链) 与 R18(G10 repo 链) 解耦各自独立；planned_fix 步 3/4 作废；O06 已裁先迁 3 测试后删，删前 owner 再确认一次 |
| **R34 纯删** | 「收敛到 column_name」 | 纯删死方法；repoint 目标 `get_plan_time_span_for_resolution` **存在**（旧锚 schedule_plan_query_service.py:210，R23 后现盘 :206，dossier 误判,verify 已纠） | R34(G30) 由「收敛重构」降「纯删」；**R05→R34 硬依赖降软约束**（E18,仅 detail_queries 选迁活孪生才回升硬） |
| **R54 五套** | 报告 3 套 / registry 4 套手维列表 | **5 套**（dashboard:8 / nav:12 / resource_dispatch:64 / reports:36 / gantt_task_detail:8 别名元组异机制）；〔红队第1轮修订 R2-P2〕原述「双分叉（源键分叉+字段集分叉）」**低估**——实盘是 **3 种字段基数 + L1 别名源键分叉**：L2 nav_publish=16 键、L4 dashboard=16 键(≡L2 逐字)、**L3 resource_dispatch=15 键(缺 plan_role_status，第三基数)**、**L1 reports=12 键(缺 plan_role_status+三阻断态 plan_identity_error/blocking_error/blocking_scope，且用别名源键 data.get("requested_role")/("selected_role")/("is_official")/("is_preview"))**、L5 gantt=别名元组(含 plan_role_status)。归属订正：用别名源键的是 **L1 reports**(非泛指)，L3 resource_dispatch 是**同名键但缺 plan_role_status** | R54(G04) delegate 面 +1（gantt_task_detail 别名元组）；**禁统一键名 / 禁并 reports 两注入路径**（丢阻断态）；**「禁统一键名」承重红线须建在三基数图上：分三组(16/15/12)各钉 parity，严禁把 L3 的 15 键当 16 键「补齐」plan_role_status=统一改行为违 R54 承重红线**；新增 A03/A05 边，详见 §3 + §3.1 |
| **R56 偏离已修** | 承重只补注释 | 走高风险结构路线删 `_is_execution_review_request` 本体（违铁律 3）,护栏重定位页级 identity_error+blocked,未 fail-open,契约钉死 | R56 **入 fixed**（DAG 起点已完成）；残留=owner 认账偏离 + 确认 navigation_context/reports_page_support/reports_execution_review_context/契约测试同提交入账。退化为 R42 删 plan_id 的**禁区行**（:79 plan_role 强制语义）非协调边 |
| **R03 四态** | 全死分支 | `_baseline_missing_or_failed(:267 return True)` 使 **missing 态生产可达**,只 failed 态不可达 | R03 由「全删死分支」改**四态 parity**：missing 态保留+补不可达注释 vs failed 态收敛,owner 裁。（R03 在 LEAF-DUP-P4 簇,本综合未含其单元；记入差异：R03-A 承重注释门控 B 段清理,missing 态:267 四态 parity 禁裸删 workbench:156） |

### 5.2 执行重构新引入债（纳入清单，承重认账项）

| 新债 | 落点 | 性质 | DAG 处置 |
|---|---|---|---|
| **N1** | scheduler_resource_dispatch_execution_context.py:129-130 `_identity_allows_query_membership_check` 收敛成单字段 can_write_feedback | 行为安全但承重契约从显式自证退化成隐式远端依赖,**零注释=新承重不对称（失忆债）**,load_bearing 倾向 true | 补「我是故意的」注释（钉 can_write_feedback⇒adopted-only 来源链）+绑 parity；**门控 G22 的 R08 删死分支**（依赖 service:127≡:130 同源,先钉不变式守卫）；新增 E26 边；不单独成单元,挂 Batch-2 同期 |
| **N2** | operation_execution_event.py:156-163 `_event_id_for_revision` 末位 `return 0` sentinel | 新承重逻辑无注释,该 0 进 previous_event_id 下游 revision 拼接 | 补注释（末位无后继其 id 不参与下游拼接故允许 0）+绑「非末位缺 id 必抛错」契约（禁删 `if index<total: raise`）；新增 E27 边,不触发结构动作 |

### 5.3 fixed 态重算批次起点（corrections E）

- **已结构性消除 6 债**：LB03 / LB06 / R07 / R16 / R56 / R57 → **DAG 前置已完成,从批次中移除占位**，仅留认账残留（见各簇 §E）：
  - LB03/LB06：仅缺认账注释（勿粘 §90 LB-B4 反向 fail-OPEN 文案——现盘 fail-CLOSED）
  - R07：O31 已裁统一成 AppError/ErrorCode.NOT_FOUND，并补 schedule=None→raise 回归
  - R56：偏离铁律 3,owner 认账（见 5.1）
  - R16：已修,R15 state_builder 处已落地,原「R15 避让 R16 删表」前置消解
- **R29 误标纠回 planned**：权威 CSV 整目录 ABSENT,common/number_utils.py 仍全量 delegation-facade、4 兄弟全薄壳,半截迁移不对称客观在场。**重新入排后 O20 已裁 KEEP+注释**；E07 已纠为 R29/G26 先闭合、R26/G18 后删 facade。

### 5.4 verify 纠 dossier 自身错误（最终以 verify 为准）

| 项 | dossier 误值 | verify 纠正 | 对 DAG |
|---|---|---|---|
| R43 roadmap 延期行 | 521 | **522** | 不撼批次,纠正引用行号 |
| R47 parity 测试方法名后缀 | `_emit_ln` | `_emit_blank_required`（@:210/:107 真存在） | 不撼 split |
| R54 键数 | L1=13/L4=12 | L1=12/L4=16（L2/L4 逐字相同） | 不撼 split 与承重结论 |
| R34 repoint 目标 | 「不存在」 | `get_plan_time_span_for_resolution` 存在=旧锚 service:210，R23 后现盘 service:206，执行按符号重 rg | R34 repoint 可行,见 5.1 |

### 5.5 旧 16 批 DAG → 重建后批次的净结构差异（汇总）

1. **批次数收缩**：旧 16 批因含「新建模块（R09）」「R13+R18 同原子」「R34 收敛重构」「R56 承重待做」等已被推翻/已完成的占位批。重建后有效分层为 **ROOT + 4 大批（A/B/C/D）**（§2.2），其中 A/B 多为零前置可早落，C/D 集中裁后收敛与承重收敛。
2. **承重根前置统一上提**：GF1 默认值门 + LB01/LB02/LB05/LB07/LB08/LB03/R05-step1/R22-parity 全部上提为 ROOT（纯增量零结构，先落），是 13 条 H 边的共同 source。
3. **owner_pending 单元裁后分流**：原 G09/G10/G13/G15/G18/G22/G26/G27/G29/G30/G33/G34/G39/G40/G41/G42 已由 owner 裁定分流；G26/R29、G30/R34、G39/R52、G42/R24 走裁后去挂起或 KEEP，G13/R55 本轮暂停，其余按裁后门控落。
4. **R26 最晚硬约束坐实**：因 R29 复活 + 2 离线消费者，R26（G18）须晚于 R29/R33/R52 三桶收敛（E07/E08/E09），是全局最晚批（Batch-D）。
5. **誤删风险全收敛**：**6 承重文件**（红队第1轮 +operation_execution_scope.py，R09 收口家↔LB01 最终底同文件）+ 3 最危险边（§3）+ 各簇禁区行（按符号非行号定位、删后 grep 复核活近亲）+ §3.1 `_positive_int` family 对照表（STRICT 4 禁删）+ §3.2 fail-CLOSED 方向硬门，无新增 import、0 分层违规、灵魂线 raise 全程不削弱。

---

## 红队第1轮修订

> 输入：三份红队报告 redteam/round1_{1,2,3}.md（攻击角度=漏边 / 簇拆并 / 排序约束）。逐条裁定，行号全部 2026-06-05 rg 回 HEAD c2aa7501 实盘复核，不信红队报文旧值。
> 裁定原则：承重(load_bearing/N1/N2)只补「我是故意的」注释+绑契约/parity，绝不删/统一/透传；灵魂线不新增兜底；P5 收口到已存在点；分层 0 违规；原 owner_pending 按 OWNER-DECISIONS 裁后口径执行。
> 共 14 条候选（round1×6 + round2×6 + round3×2，含 2 条澄清/降级）。**采纳 11 条 / 驳回 0 条 / 降级保留 3 条（红队自降，按提示采纳精度修正）。** 逐条裁定见下，关键修订已回写正文对应小节并在此登记。

### 裁定总表

| 红队条 | 角度 | 裁定 | 一句话理由（rg 实盘） |
|---|---|---|---|
| R1-P1 | 漏边 | **采纳** | scope.py:9 收口点与 :36 validate(三 raise :44/47/50)同住 3499B 小文件，§3 漏登该文件、§2.1 漏边 → 补 E28 + §3 第 20 行 + 承重文件 5→6 |
| R1-P2 | 漏边/漏副本 | **采纳** | schedule_persistence_errors.py:13 第 3 份裸 `-> Optional[int]`(`int(value or 0)` 不 wrap 收口点)实盘存在；service A 副本 def:24 + 调用点 :169/:180/:181（放宽点 :180-181 比较） |
| R1-P3 | 漏边 | **采纳** | N1(:129-130) 与 C 路收口副本(:28-30 wrap 收口点)同住 context.py；调用点实盘 :96/:97/:107/:258/:271/:272 → 补 E29 |
| R1-P4 | 漏边 | **采纳** | event.py 除 :161 raise/:163 return 0 外，:179 return 0 + :205 previous_event_id=0 同语义 sentinel；feedback_service/viewmodel/actions/gantt_adjustment 均 import → E27 升精 |
| R1-P5 | 标注精度·反向风险 | **采纳** | navigation_context.py:79 实盘 fail-CLOSED(非法 role→ROLE_ADOPTED)，§3 补方向硬门防认账注释粘 §90 反向 fail-OPEN |
| R1-P6 | 标注精度·同名异义 | **采纳** | 全仓 `def _positive_int` 实盘 STRICT(-> int raise) 4 处 vs Optional(-> None) 5 处，同名异义无对照表 → 新增 §3.1 family 对照表 |
| R2-P1 | 簇拆并·该并未并 | **采纳** | R54 五套手维面跨 5 文件，G04 物理只锁 navigation_publish 1 套，另 4 文件缺席 §3 → G04 内部顺序补 5 file:line + §3 补登 4 文件 |
| R2-P2 | 簇拆并·字段集分叉 | **采纳** | 实盘 3 种基数：L2/L4=16 键、L3=15 键缺 plan_role_status、L1=12 键缺三阻断态+别名源键 → §5.1 R54 行「双分叉」改「三基数+别名」 |
| R2-P3 | 行号漂移误值 | **采纳** | L3 resource_dispatch guard 调用唯一 :109，:95 是 collar 调用，:199 无对应 → 簇锚点 def:64/call:109（仅文档侧记录，正文重灾区已按 :109 修） |
| R2-P4 | layer 误标 | **采纳** | R54 5 套实盘 3 viewmodels(dashboard/reports/gantt_task_detail) + 2 routes，非「都在 routes」→ §3 补全路径前缀 |
| R2-P5 | collar 第6调用方漏盘 | **采纳** | analysis_links.py:24 调 collar 实盘**未传 plan_id**(kwargs 无)，R42 删形参对它安全，但须登记为只读确认点 → E03 补注 |
| R2-P6 | 拆分定性 | **降级保留**（采纳精度） | R64/R65 逻辑零耦合结论成立无误拆；仅内部顺序理由按红队建议精化为「R65 删 :4/:6 import 上移幅度最大」 |
| R3-发现1 | 排序·自相矛盾 | **采纳** | A14 标 `R31→R33` 与 E05 `R33→R31` 相反；实盘壳:3-11 import 源:9，正确硬序 R33 先 → A14 改 R33→R31 |
| R3-发现2 | 排序·方向误导 | **采纳** | R30/R31 同为 shared 侧删动作彼此无序，真约束源是壳 R33 先停 import(:6-8) → E06/A15 改 `R33→{R30,R31}` |
| R3-发现3~6 | 排序 | 核查通过（非问题） | R09 收口点存在/R13-R18 解耦/parity 先于收敛三主线/facade 晚于收敛——红队自核通过，正文无需改 |

### 采纳项的正文修订（已回写）

**[R3-发现1+发现2] 修正 facade 三常量删序有向边方向（A14/E06/A15）**——见 §2.1 E05/E06、§4.2 A14/A15 行内修订标记。簇内实际落地序「R33 步1→R30→R33 步2/3」不变，仅修有向边方向避免误导下游拓扑工具。

**[R1-P1+R1-P3] 新增两条同文件承重毗邻边 E28/E29**——见 §2.1 边表末尾。

**[R1-P4] E27 升精**——见 §2.1 E27 行。

**[R1-P5+R1-P6+R2-P1~P4] §3 重灾区补登 + family 对照表 + 方向硬门**——见 §3 表末 + 新增 §3.1。

**[R2-P5] E03 补 collar 全调用方确认**——见 §2.1 E03 行。

**[R2-P2] §5.1 R54 行三基数改述**——见 §5.1 表 R54 行。

---

## 返回摘要

原子簇 42 个（G01–G42）+1 共享前置门 GF1 = 43 调度单元（多债强原子 20 / 单债 22 / 承重门 5🔒；原待裁清单已裁后分流，R29/R52/R24 走 KEEP，R55 本轮暂停）。
验环：**无环（DAG 成立，环成员=空）**——13 条 H 硬边全单向收敛，唯一双向标记的 E16/E24/E11 均为 S 软序可定向。
批次草案（序）：ROOT（GF1 默认 False + LB01/LB02/LB05/LB07/LB08/LB03/R05-step1/R22-parity 承重注释+parity，纯增量零结构）→ Batch-A（零前置死叶子 G14/G16/G21/G28/G31/G32/G35/G37/G11/G38，G03 延后，G25 并回 G24）→ Batch-B（单门控前置 G06/G07/G08/G12/G19/G20/G24含G25旁支/G40/G30/G36/G39 KEEP；G13/R55 本轮跳过）→ Batch-C（身份族收敛 G04→G01/G27/G09/G10/G29/G15/G22/G33/G34/G17/G23）→ Batch-D（facade 最晚 G18←三桶收敛 + G26 KEEP/G41/G42 KEEP）。
重灾区：**24 文件**（红队第1轮 +5：operation_execution_scope.py + R54 缺席四文件）≥2 债顺序敏感，最危 3 个=feedback_service.py(LB01↔R17 同 _build_event_payload)、execution_review.py(承重五钉↔R62)、gantt_critical_chain_provider.py(_copy↔_normalize 误删)；**6 承重文件**全标禁区（含 operation_execution_scope.py R09 收口家↔LB01 最终底同文件）。
边总变化：旧 146 −删 27（假边 22+已修对消 5）+新 **19**（同符号 co-change/收口前置硬边/N1N2 邻接/facade 删序 +红队 E28/E29 同文件承重毗邻）~降 18（硬→软/解耦/方向反转）= 重建约 **138 边，跨簇有效约束边 29 条（H 13/S 14/P 2）**，真门控分层硬边仍 13 条。
与旧 DAG 主要差异：R09 收口点已存在→作废建模块改双路 parity；R13 解耦 R18 各自独立，按 O06 先迁 3 测试后删、删前 owner 再确认；R34 纯删（repoint 目标存在）+R05→R34 降软；R54 升 5 套手维面（gantt_task_detail 别名元组+**三基数 16/15/12 禁统一键名**）；R56 入 fixed（偏离铁律 3 待认账）；新债 N1（can_write_feedback 失忆债门控 R08）/N2（return 0 sentinel）补注释+绑契约；R03 四态 parity（missing 态:267 生产可达，非全死分支）；R29 误标纠回 planned 后 O20 裁 KEEP，E07 改为 R29/G26 先闭合、R26/G18 后删 facade；批次由 16 收缩为 ROOT+4 大批，待裁项按裁后口径执行。
红队第1轮：**采纳 11 / 驳回 0 / 降级保留 3（按提示采纳精度）**。关键修订=补 E28(R09 收口家↔LB01 最终底同文件)/E29(N1↔R09 C 路同文件)两 S 边；§3 补登 5 文件(承重 5→6、重灾区 19→24)；新增 §3.1 `_positive_int` family 对照表(STRICT 4 禁删 vs Optional 5 收候选，O02 后定 schedule_persistence_errors:13 归 R04 禁区+注释)+§3.2 fail-CLOSED 方向硬门(防认账注释粘反向 fail-OPEN)；R54 三基数(16/15/12)分组 parity 禁向 16 键看齐；facade 删序方向修正 A14→R33→R31、E06/A15→R33→{R30,R31}；E03 补 collar 第 6 调用方 analysis_links:24(未传 plan_id 安全)。全图仍无环。
产物：/Users/lurenxing/Documents/GitHub/----/docs/_panorama_data/phase4_dep_safety/_interference_rebuilt.md
