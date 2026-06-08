# Layer3 爆炸对抗综合 + completeness-critic

> 来源：62 份 explode_r*.md（r1=12簇×3透镜 LB/LAYER/SOUL=36，r2=9高危簇×2 LB/SOUL=18，r3=4承重簇×2 LAYER/SOUL=8）。
> 综合规则：多轮多透镜多数红即标红；承重(load_bearing/N1/N2/R03/R05/R54/R58)只补注释+绑契约/parity，绝不删/统一/透传；P5 收口到已存在点；owner_pending 只标不给终态。
> 只读不改，行号以各产物 rg 回盘值为准。本档不改任何 .py。

---

## 一、每条债 go/no-go 最终判定（综合多轮多透镜）

> 判定列规则：🔴=多数透镜红/多维存疑/会静默炸；🟡=有条件可做（前置/禁区/顺序全绑才放行）；🟢=安全（条件极轻）。
> 投票列记录该债在各 explode 文件里的颜色（多数红即红）。owner_pending 债「只标不给终态」，下表终判=「该债排批/收口前会不会炸」的 go/no-go，不替 owner 拍语义。

### tier3 承重簇（4 簇）

| 债 | 簇 | 投票（r1LB/r1LAY/r1SOUL · r2LB/r2SOUL · r3LAY/r3SOUL） | 终判 | 灾难链一句 | 强制前置 / 禁区 / 顺序 |
|---|---|---|---|---|---|
| R54 | NAV-GUARD | 🟡🟡🔴·🟡🔴·🟡🔴 | 🔴 | 5 套手维 guard 列表收口时漏拷 is_comparison/is_superseded（fail-OPEN 键）或抹 L5 `is_comparison_plan` OR 兜底 → `_is_current_official_identity:294` `not None`=True → 旧/比较版冒充现行采用版 → can_emit_feedback_write_urls:469 放行 → 向历史/比较方案脏写现场事实（不可逆） | 前置：collar `build_workbench_plan_context` 当前**不产**三 fail-open 键、无 plan_resolution 入参 → 「5 套 delegate 到 collar」前必须先把 collar 扩成 3 键 guard 产出点（走 view_context default_plan_resolution_dict 的 fail-CLOSED 默认）当独立承重改动审；L5 路径 = `web/viewmodels/scheduler_gantt_task_detail.py`（非 routes）；逐键四态 parity（缺失/None/False/True×拦放，含「key 在值=None」分叉、L5「is_comparison_plan=True 但函数重算=False」反例）；reports 第二注入路径禁并一条（丢 3 阻断态）。禁区：links.py:292-296 判定方向、:149-161 gate、:248、:469-473、view_context fail-closed 默认。顺序：与 R42/R60 同改 collar 签名 MUST 同批；co-change 同查 `ln(` 别名调用点。owner_pending。 |
| R58 | NAV-GUARD | 🟢🟡🟡·🟢🟡·🟢🟡 | 🟡 | 本轮仅 :91 上方插注释=安全；Phase2「剔 update 里 can_write_feedback 单键」会把 preview-adopted/非adopted 路径静默 True→False 翻转，现 keep_plan_guard_fields 用例 builder-gated≡raw≡True 仍绿（测试盲点） | 本轮只注释（钉「:88 喂 raw 故意、:91 覆盖回 raw 零消费故意」）；按符号 `context.update(guard_fields)` 重定位禁照抄 :86。Phase2 须先补 preview-adopted+非adopted 两反例 parity、排 R54 之后、owner 拍板。禁删整行（连带丢 can_dispatch）。 |
| R44 | NAV-GUARD | 🟢🟢🟢·🟢🟢·🟢🟢 | 🟢 | core 收口点比 web 更防御，只喂模板显示 kwarg 不碰闸门；唯一差 None→AttributeError vs "adopted"（生产不可达） | 排 SEQ-NAV 末位（R58→R54→R44），动手前重盘 :6/:36-37；仅动 :6-7 import+:36-37 删 def；owner 裁 None 边界。 |
| LB02 | EXEC-REVIEW | 🟢🟡🟢·🟢🟢·🟢🟢 | 🟢 | 纯护栏注释；被注释挡住的灾难链=他人给 :209 加 plan_role/scenario_id 形参→helpers 透传→resolve_plan_view scenario 非空切 _resolve_scenario_plan 换 source_table→预览静默冒充正式复盘并导出 | 仅 :209 上方+五处硬钉（:58/:180-181/:191-192/:221/:236）旁补注释，零删/零透传/零加形参；注释须交叉引用 web 真定义宿主（reports_request_support.py:75 / reports_execution_review_context.py:8，非 reports_page_support）+ v19 DB CHECK 双列；勿粘 §90 LB-B4 反向 fail-OPEN 文案。 |
| LB05 | EXEC-REVIEW | 🟢🟡🟢·🟢🟢·🟢🟢 | 🟢 | ≡LB02 第二 finding，同点同动作，一次注释满足两条 | 同 LB02；:58 第 7 钉是新增且方向与不变量一致非削弱。 |
| R62 | EXEC-REVIEW | 🟡🟡🟡·🟡🟡·🟢🟡 | 🟡 | 三键恒等删 no-op 行为等价，但原子面是「四处」含模板 title 属性；漏改 title → Jinja undefined → `title=""` 可观测 UI 降级；漏穿 xlsx/dict 留半截残骸 | A1 注释先落（Batch-1）→ R62 后做（Batch-3）；按符号 `_resource_pair_payload`+`!=` 重 grep 禁照抄行号；payload+dict+模板（`!=`副行+title 改回 _label）+xlsx 四处同 commit；收口面**零现成断言**须先写 3 套 parity 快照（升为硬前置门非建议）；禁碰 :58-236 护栏段、禁删 state 层 latest_*/counterpart_* 真身份键。 |
| LB01 | EXEC-FACT | 🟢🟢🟡·🟢🟢·🟢🟢 | 🟢 | 纯补两处注释；被注释挡住的灾难链=以「repo 已 validate 故写死冗余」名义删 :471-473 写死消毒 → scenario/candidate 现场事件落库污染重排护栏 | 注释先落且锚符号上方（门控整个 service 文件删改）；禁区 :369-374/:381-382/:471-473 只补注释；文案禁出现「写死冗余」式措辞；交叉引用 schema:284 candidate_rows 第二表 + v19 CHECK。 |
| R17 | EXEC-FACT | 🟡🔴🔴·🟡🔴·🟡— | 🟡 | 删 service:12 死 import + support:81 推导式死键安全，但同 `_build_event_payload` 函数体毗邻 LB01 写死 :471-473；「顺手清理」打穿写死消毒，误删 :80 活键则 report_exception 静默拒 | LB01 注释先落（裸奔期禁动 service 文件）；只删 service:12+support:11+support:81 三行，删 :81 非 :80 活键；绝不重构 _build_event_payload；删后重 rg（:225/:52/:471 上移）。r1-LAYER/r1-SOUL 标红=毗邻爆面，r2-LB/r3 复核降黄（删的是 import 行不碰 :471-475，无 dict 键位移耦合）。 |
| R15 | EXEC-FACT | 🔴🔴🔴·🔴🔴·🟡🔴 | 🔴 | provider:87-95 空→None（合法 optional）+ 坏→None（P4 残留）双静默；收口符号 parse_operation_event_time **空值也 raise** → 整体 delegate 把「任务未开始」合法空时间炸成 raise → _fact_from_state:52/53 内联 kwarg 构造、facts_by_scope 链全程**裸奔无 except** → 正常读历史计划 500 / 上层吞掉则执行事实全空喂重排 | owner 先裁（owner_pending）；收口必须分支级非整体 delegate——`if not text: return None` 留在 provider 本地，仅坏值走收口符号；坏值方向选 loud raise（须确认下游接得住）或可观测降级标记，禁更深 return None；先补三处 required/optional parity（含空值分支断言）；启动探针喂 not-a-date 边界须不冲突。r3-LAY 单标黄（只看 Q2/Q3 分层/迁移维度无虞），其余 4 透镜全红。 |
| R19 | EXEC-FACT | 🔴🟡🟡·🔴🔴·🔴🟡 | 🔴 | snapshot:40 `return sorted(out)` 喂 :78→:91 sha256 指纹（事实承重）；naive「三处统一到不排序版」或让 snapshot 走不排序 → 同输入 sha256 漂移 → 下游 4 处 guard/publish/scenario 快照比对静默失真（三函数零符号级测试无拦截）；repo 收 service=data→service 越层、provider 反向 import snapshot=环 | owner 裁 repo 落点；canonical 强制 sorted+「指纹依赖排序」注释；provider 收口同层（收 sorted 后 missing[0]:147 文案变须 parity 断言）；repo 保私有版补「顺序无关」注释禁下沉；先补 positive_op_ids 黄金用例（F-fingerprint 门）；与 R01/R46 共享 __all__:118-122 串行对账。 |
| R18 | EXEC-FACT | 🟢🟢🟢·🟢🟢·🟢🟡 | 🟢 | repo:399-405 六格 stub `raise _unscoped_execution_read_error()` 是拒非 scoped 读契约护栏非死码；registry「直删」失真（直删→AttributeError 击穿契约+破 foundation:367） | owner F 门确认降级为注释护栏；补 :399-405 整组护栏注释；禁直删/禁退 :367 断言/禁改 return {} 静默；与 R13 共注释合批。 |
| R20 | EXEC-FACT | 🟢🟡🟡·🟢🟢·🟢🟢 | 🟢 | 删 service labels 垫片改直连 core.models，`from X import Y` 同对象字节级等价，漏改即 ImportError（loud 非静默） | LB01 注释先落；与 R17 串行（R17 删 :12 后 :52 上移须重 rg）；只改 :52 import 块禁碰 LB01 禁区；删文件同摘门禁 docs_quality_gate:128+指南:151。 |
| R13 | EXEC-FACT | 🟡🟡🔴·🟡🟡·—🟡 | 🟡 | 死字段生产零消费但被 5 处测试读活（reschedule:196 + scope_read_contract:108/190-191/220-221）；「死」定性被推翻，无脑直删破契约（漏退 kwarg→TypeError）；误碰 repo:399 改回查询=复活越身份读取 | owner 二次确认字段无未来消费；先迁 scope_read_contract（契约源头）→reschedule→后删生产代码；R13 不碰 repo（属 R18）；不削弱 provider:110/113 raise；同文件串行 R15→R19→R13。r1-SOUL 标红（连带删 latest 链=信号永久静默消失），其余降黄。 |
| LB07 | CONFIG-DUAL | 🟢🔴🟡·🟡🟡·🟢🟢 | 🟡 | 30/30 双栈字段 parity 当前成立但三 helper 在 tests/ 零命中=「碰巧等价非守卫等价」；注释+扩 parity 前置门未落时，R71/R47 任何函数体改动处于「测试绿但护栏破」静默失效区；单边改 helper → 算法栈 vs 配置页栈对同字段口径静默分叉污染排产 | 两栈 @dataclass 上方补注释（对侧路径互填）+ 扩 spec_sync_contract 覆盖三 helper 逐分支（含「非dict→None 不抛」「count 坏值→1 不抛」「空 choices→True」「except continue 静默跳」逐字保真，含 `_handle_missing_value` 的 INHERIT_LEGACY 两栈不对称——见新爆点）；Batch-1 ROOT 最先落；禁区 coercion:470 置零/:71-72 等 loud raise 族/30 字段表只补注释。r1-LAYER 标红=parity 守卫缺口实证在场。 |
| R71 | CONFIG-DUAL | 🟢🟡🟡·🔴🟡·🟡🟡 | 🟡 | 三 helper byte 等价，收口 service→core.models 合法无环；但守卫缺口下收敛若顺手把 `except continue`/`return None` 改 loud raise = 静默→loud 反转，下游降级读取从「静默丢弃」变「崩」 | 硬前置 LB07 注释+helper parity 先绿；owner 裁物理收敛 vs 仅 parity；逐字保真已存在吞错语义（改 loud 另立债）；与 R47 同批改后统一回盘；禁新建第三模块。r2-LB 标红=守卫为空时序错即静默漂移。 |
| R47 | CONFIG-DUAL | 🟡🔴🟡·🔴🟢·🟡🔴 | 🟡 | 删死参 `_record_blank_choice_degradation` 的 raw_value 安全，但同文件 `_record_invalid_choice_degradation` 是结构孪生且 raw_value 是活参（:116/:119 读）；`raw_value=raw_value` 全栈 8 处文本逐字相同，盲 grep/sed 必误删活参 → invalid 降级证据静默丢失，且现成 blank parity 测试不覆盖 invalid 路（测试绿但护栏破） | 按调用函数名逐块手删（只删 model:88/:159/:214 + service:68/:158/:211 死点），禁全局替换/sed；禁碰 invalid 4 活实参（model:173/:225 / service:170/:222）；删后跑 blank+invalid 两路 degradation 回归；守门测试真名 `_emit_blank_required`（非 dossier 误写 `_emit_ln`）；与 R71 同批回盘。r1-LAYER/r2-LB/r3-SOUL 标红=误删活参静默降质。 |
| R45 / R48 | CONFIG-DUAL | 🟢🟢🟢·🟢—·🟢🟢 | 🟢 | 2026-06-08 已 fixed：旧 27 行 `config_adapter.py` 死壳已删除，当前生产/测试/工具零引用 | 旧 sp06 文件已由 A P1.1 删除，`NO_CFG_GET_TARGETS` 零命中，退行 no-op；后续只做残留 rg，禁碰 schedule_params.py（same_file 误标零碰撞）。 |
| R31 | CONFIG-DUAL | 🟢🟢🟢·🟢—·🟢🟢 | 🟢 | WRITE_INTERNAL_ONLY 死常量三处零消费 | R33 删 common facade 不晚于 R31 删 shared 源 :9（反序→facade :11 残留 import loud ImportError）；只删 :9 禁碰 :6/:7/:8 活常量。 |
| R26 | CONFIG-DUAL | 🟢🟡🟡·🟡—·🟢🟡 | 🟡 | 顶层 5 shim 删；误删只 loud ImportError；但 2 离线消费者（tools:17/audit:87）活引用先删即炸、CI 不跑=延迟暴露 | 晚于 R29(B05)/R33(B06)/R52(B09) 三桶收敛+R71 收口；迁 2 离线消费者（手动验证清单）；重指基数用 ~93 处/53 文件（非旧值 71）；改 SP05 BEHAVIOR_* 两字典（:20-31/:33-82）非 STRONG_*，:638 第二处不碰；owner 裁解冻。 |

### tier2 簇（5 簇）

| 债 | 簇 | 投票（r1LB/r1LAY/r1SOUL · r2LB/r2SOUL） | 终判 | 灾难链一句 | 强制前置 / 禁区 / 顺序 |
|---|---|---|---|---|---|
| R09 | PARSE-INT | 🔴🔴🔴·🔴🔴 | 🔴 | A/B 副本 `int(value)`（5.9→5/True→1）vs C 收口点 STRICT（5.9→None/True→None）；按「字节对齐 A/B」新建宽松 sink 把 C 一并收口 → C 经用户输入路径（request.args schedule_id）放宽 → 5.9 当 op_id=5 进 `_row_matches_feedback_target` 误命中相邻行 → 现场记录静默写到错任务 | owner 先裁 C 取严格 None 还是放宽 A/B（裁前不进批次）；收编只动 A/B 两 Optional 副本收口到已存在 scope.py:9，C 保持不动；分两路 parity（test_AB 零漂移 + test_C_float_bool 钉 5.9/3.0/True）；STRICT 4 处一字不碰；persistence_errors.py:13 归 R04 禁区不归 R09 收编面（矛盾指令，见回炉）；B 副本 `or 0` 外层兜底审计（5.9→int→5 变 None or 0=0 塌成 0 另一条坏数据流）；强串行 R07/R08 后重 grep。5 透镜全红，最高置信红。 |
| R04 | PARSE-INT | 🔴🔴🔴·🟡🟡 | 🔴 | F1 `reject_integer_float` 默认 True → sgs_graph 8 处等 algorithms 调用方 3.0 由接受变 raise 排程静默回归；ValidationError 非 ValueError 子类，6 处 except 漏改任一 → 脏 op_id 由静默 skip 变 ValidationError 一路上抛炸排程统计/持久化 | F1 必默认 False+自带 parity（True→3.0 raise/False→3.0 接受，含 sgs_graph 风格调用断言）；6 处 except 同 PR 加 ValidationError 不可拆；R01 先删→R04 按新行号重 rg；哨兵 B(auto_assign:114→0)/C(persistence:13→None)仅注释禁改 raise；LB08 文案/正则桥不碰。r1 两透镜红，r2 复核降黄（前置全绑即可做），综合维持红（F1+异常逃逸双爆点）。 |
| R59 | PARSE-INT | 🟡🟡·🟡🟡 | 🟡 | F1 前裸收口 `'1.0'`/`1.0`→1 撞续命测试 :247/:250 raise（CI 显性红良性）；删 _parse_plain_report_int 漏迁 blank 短路 → 导出空值由降级 0 变报错中断 | F1 先落+默认 False 后委托 reject_integer_float=True；保留 blank 短路（:62-63）；文案漂移 owner 认账（friendly 串→strict 串，match 仍过但可观测变）；禁动兄弟 parse_report_int:36。 |
| R28 | PARSE-INT | 🟢🟢·🟢— | 🟢 | 2026-06-08 已 fixed：_safe_float 已保名收口到 parse_finite_float，静默吞错→loud raise 正方向，上游已 parse_optional_float 严校 | 已用 allow_none=True；`pytest -k test_no_new_local_parse_helpers` 证明 fitness 白名单保留；未动消费点工时兜底。 |
| R01 | PARSE-INT | 🟢🟢·🟢— | 🟢 | 死簇闭合自环零外部边，误删均 loud（ImportError/SyntaxError/SP05 红） | 同删孤儿 Iterator:5；只删 run import :16-17 保 :13-15；与 R04 同 PR R01 先删；删函数+删 SP05 断言同提交。 |
| R08 | PARSE-INT | 🟡🟡🟡·🟡🟢 | 🟡 | 死分支 (T,F) 不可达依赖 service:127≡:130 同源不变式（无守卫即脆）；删死分支必保 feedback_write_enabled 参数（:234 活消费），误删参数→「填写实际」按钮门禁塌缩静默放开误填现场记录 | owner 裁「是否总开关预埋」；先钉 :127≡:130 同源守卫；候选 A 只删 :25/:227-228/:367-368 保参数；等本文件在途 task_key 重构 diff 落定再动（行号已漂+1~6）；R08→R09 串行。 |
| R55 | GANTT | 🟡🟡🔴·🟡🟡 | 🟡 | 加 scope=filtered/full；裸删 filtered 过滤=filtered 视图变整版反砍业务；helper 内靠「filters 空否」反推 scope，provider full 路径无 filters 上下文反推必错 | owner+怀疑者过 PHASE0 §6 三问（owner_pending+needs_adversarial+verdict=null）后才锁终态；A1 先；scope 调用点显式赋值禁反推；禁破坏 :385 None 回退+support:55-56 分流判据；穿单份 _normalize+contract unavailable 分支（_copy 无须补）。r1-SOUL 标红=三门未过却排进可执行，是流程红非「会炸」红。 |
| R12 | GANTT | 🟡🔴🟡·🟡🟡 | 🟡 | 加 dropped_count/critical_chain_partial；裸删 :84 过滤→None 流入 sort:114/max:262→TypeError→出口 try/except 接住→整链 available:False 功能回归；新键不穿 _normalize 白名单被剥离；_empty_result:54 available:True 不带 dropped（全坏行最该报警反而无信号） | A1{R11≡R63}先；保留 :84 仅补 collector；:54 与 :328-334 双补 dropped_count；contract available=False 分支（:22-39）须显式保留新键（r1-LAYER 标红的真因——计划只说 contract:40 透传不卡，漏 available=False 硬重建分支吞 dropped_count）。 |
| R11 / R63 | GANTT | 🟢🟢🟢·🟢🟢 | 🟢 | 2026-06-08 已 fixed：两份 _normalize 已收口为 `gantt_critical_chain.py:67-88` 单份 helper；support/provider 两路调用同一函数；parity 测试覆盖 11 个 legacy 边界 | 已保留 available=0→True + bool(is_available) 包裹；未 return raw；未误删 provider _copy:108-114。A1 前置已满足，后续 R12/R55 只能在单份 helper 上加键。 |
| R10 | GANTT | 🟢🟢🟢·🟢🟢 | 🟢 | 删死方法 get_latest_version_or_1 零调用 | 删 :60-62+stub:59 后立即 grep 复核活方法 resolve_version:64 在（名字均含 version，误删静默炸周计划版本解析）。 |
| R51 | COMPAT-DISPATCH | 🟡🔴🟡·🟡🟡 | 🟡 | 删两宽容解析器+续命测试 :25 兜底断言（`parse_*("unknown",default)==default` 正是 P4 静默回退）；若保留/迁移 :25 = 把已铲兜底钉成契约 → 未来复用复活静默兜底 | 两测试整体退场禁迁移禁保留 :25 断言禁保留函数改 raise；收口点 schedule_params:277/346 + optimizer_config:166/189 loud raise 已在位（只读确认）；A2 同 diff 删 :28-35 后重盘 R49/R50 行号。r1-LAYER 标红=灵魂线复活红线，但实为「序错/续命即复活」的 loud 风险非静默炸，综合黄。 |
| R30 | COMPAT-DISPATCH | 🟡🟡🟡·🟡🟡 | 🟡 | 删 shared date 三常量后若 facade re-export（services.common.value_policies:6-8/:24-26）未同窗删 → ImportError 打挂 facade 全表面（但只炸测试面 = 响声债非静默 fail-open） | R33 步1 迁 import 先；删 shared 三常量与 R31/facade 删 re-export 同窗口；import 块按行精删死保 float/int/is_blank/READ_COMPAT；date 回退语义与 float/int 不可统一。 |
| R33 | COMPAT-DISPATCH | 🟡🟡🟢·🟡🟡 | 🟡 | 删三 re-export 壳；死保元组 degradation:15（其性质 r1=真承重实现 20+生产直连 vs r2-SOUL=17 行纯 re-export 壳，内部矛盾未拍定，见回炉）；删元组只动 :14/:16/:19，:15/:17/:18 全保留 | 三步硬序 R33步1（迁 emits_degradation:18+matrix:18）→R30（删实现）→R33步2/3（删 :411+元组三条+三壳）；绝不碰 core.shared 三模块全文；degradation:15 无论性质都死保。 |
| R29 | COMPAT-DISPATCH | 🟡⏸🟡·🟡🟡 | 🟡 | number_utils 全量 delegation-facade owner-pending；有 2 个活生产消费者（excel_calendar_rows:8/excel_validators:26）非死壳，薄壳化须同改 | 只标 owner-pending 不给终态；KEEP 仅补注释；走 B 薄壳化前置=先重写 monkeypatch 为身份测试，真续命点是 `regression_number_utils_facade_delegates_strict_parse.py:45-48`（非 dossier 误指的 warmstart:136）。 |
| R49 | COMPAT-DISPATCH | 🟡🟢🟡·🟢🟢 | 🟢 | 删 5 行死模块别名；按符号名全局删 `_parse_due_date` 会铲 sgs_scoring:34 活函数 NameError 炸派工评分（另 ordering:59 第 3 个同前缀活函数 dossier 漏列） | file:line 定点删 5 行禁符号名全局删；import 行保留；dispatch_rules:25 卷入 A2 原子 diff。 |
| R50 | COMPAT-DISPATCH | 🟢🟢🟢·🟢🟢 | 🟢 | 删 mean_positive 死函数 + import statistics | 保留 import math:3（:78/:95/:128 真用，误删启动 ImportError）；外科退测试只动 :20+:61-63 死保 :26-59 build_dispatch_key 回退活契约。 |
| R52 | GRAPH-ERR-DIAG | 🔴🔴🔴·🔴🔴 | 🔴 | 裸删 impl ready_queue.py:103 → R25 垫片 :9 import ImportError → test_ready_queue.py 整文件 31 用例蒸发（dossier「~23」严重失真，约 18 个走 `_ready()`→全量版断 ReadyQueueContractError，dossier 没安排其归属）+ 4 条 LIVE ValidationError 契约 + `_full_scan_ready_ids:79` helper 一并炸 → LIVE sgs_graph 行为覆盖一次性清零 | owner 先裁 A/B；走 A 先新建 test_sgs_graph_ready.py 按 31 用例全量分流（LIVE→新文件、full_scan 差分→改字面量 + 删 :79 helper、ReadyQueueContractError 全量合同用例 owner 显式裁归属）；parity 异常类不同只能断「均拒绝」禁断同类型；None 分支两路分别写；同提交退 lazy_runtime:27+metrics_topology:140；契约行号按符号重定位（:299/:311/:326/:352 非 :302/:326/:361）。4 透镜全红，高置信红。 |
| R14 | GRAPH-ERR-DIAG | 🔴🔴🟡·🟡🟡 | 🔴 | 删死门 _resolve_strict_plan:134（非 scenario 走 resolve_existing_plan loud raise「无回退」）；把 :328 候选灵魂线平移活门 diagnose（活门走 resolve_plan fallback_to_adopted 静默不 raise）→ 解析被 fallback 吃→「非 scenario 缺角色应 raise（无静默回退）」灵魂线覆盖被悄悄丢；撞 LB01 同符号承重 | 跨簇 LB01 承重裁断先行（:134-139 让位）；owner 裁 :328 改钉 resolve_existing_plan 层禁平移活门；:358 scenario 灵魂线两门同源可平移；删死门不得顺手修 resolve_plan 静默回退（铁律 4）；改 roadmap:485-498+items.yaml:83。r1 两透镜红，r2 降黄但双门 owner_pending 维持红（删动作牵动灵魂线覆盖）。 |
| R24 | GRAPH-ERR-DIAG | 🔴🟡🟡·🟡🟡 | 🟡 | 路 A 删 core 死副本安全；路 B 把活 web 路径改指零消费 core 合同 → core 对 NaN/Inf/bool 静默透传 vs web 孪生 safe_int/safe_float loud raise NonFiniteDiagnosticNumber → 丢护栏退化静默吞坏值（P4）+ 立零消费 core 为收口点违铁律 5 | 只走路 A 删 core（owner 默认推 A，路 B 强制前置护栏先下沉+3 parity 反例）；先调和 networkx roadmap items.yaml:435/:480/:481（:480 ruff+:481 pyright 都含 core 文件名只摘 core 保留 web helpers）；测试逐条剪混合用例 :83 单行；绝不反删 web 孪生护栏。r1-LB 标红=路 B 隐患，路 A 安全故综合黄。 |
| LB08 | GRAPH-ERR-DIAG | 🟡🟡🟡·🟡🟡 | 🟡 | 承重 legacy 正则反解桥；删→legacy 中文串 fullmatch 失配静默降级通用文案+code 丢失（P4）；注释逐字文案产出点指错（planned 指 auto_assign 是消费方，真产出在 internal_operation.py:119/148/150/152/154+resource_validation:86） | 仅补注释+绑契约 regression_scheduler_user_visible_messages.py:678 绝不删/统一/透传；注释先落钉死承重边界 R46 才删；产出点 owner 按实证改写禁贴 planned 草稿（否则注释指消费方=埋新失忆债）；禁区 :62/:94/:142/:175/:218/:284/:340。 |
| R46 | GRAPH-ERR-DIAG | 🟡🟡🟡·🟡🟡 | 🟡 | 死别名 _safe_identifier 直删；同名陷阱 v4_sanitizers.py:37 _safe_identifier 活函数（SQL 标识符 sanitize），按符号名跨文件删→v4 迁移 NameError 崩 | 文件+行号+符号三锁定删 scheduler_public_errors.py:163-165；LB08 注释先落后行号下移须按符号重 grep；禁区与 LB08 零重叠。 |
| R02 | GRAPH-ERR-DIAG | 🟢🟢🟢·🟢🟢 | 🟢 | 死壳直删，先拆测试 import :11 单符号改指 resource_matching_context 后三符号留原路径 | 先拆 import 再删壳 :461-475；禁连删兄弟壳 :478（report.py:180 承重）+ GraphInputContractError 守卫。 |
| R06 / R27 | GRAPH-ERR-DIAG | 🟢🟡🟡·🟡🟡 | 🟡 | 四空包同提交直删；逐增量摘→中间态 old_string 失配；漏删 _assert_init_has_no_imports:173 调用块边界→:409 NameError | 四包一次性原子提交（:310 改三元组+删 :315-316+删四目录）；保留 :173 定义；:310 内 config/run/summary 真包只留不摘；:638 第二处三元组不碰。 |
| R25 | GRAPH-ERR-DIAG | 🟡🟡🟡·—🟡 | 🟡 | 删 service 垫片 11 行；先删垫片而 R52 未迁测试→test_ready_queue.py:16 import + _full_scan_ready_ids:79 双红 | 与 R52 同提交且晚于测试迁移；同提交退两处模块路径断言；命运由 R52 决策门定。 |
| R70 | LEAF-DUP-P4 | 🔴🟢🟢·🟢🟢 | 🟢 | 纯删 schedule_service.py:46-50 死副本，live 在 run/input_collector.py:79 | 保 :7 ValidationError import（:217 仍用）。r1-LB 误判「:46 是承重正式函数 _raise_schedule_empty_result」，r2 逐符号 rg 推翻（:46 就是死副本本体本文件零调用），见回炉。 |
| R43 | LEAF-DUP-P4 | 🔴🟢🟡·🟡🟡 | 🟡 | 删 9 wrapper + compat + 清 scheduler_config.py:95 软 fallback；roadmap 延期行 :522（dossier 体内 :521 自污染） | owner 认账 roadmap 延期决定；删 wrapper 与迁/删测试同 PR；迁 22 文件（19 plain+3 契约）；R43↔R26 共碰 scheduler_config.py+SP05 串行。r1-LB 误判「scheduler_run.py 仅 8 行薄壳=wrapper 失踪」，r2 推翻（:8 薄壳即债本体，9 wrapper 实存），见回炉。 |
| R69 | LEAF-DUP-P4 | 🔴🔴🔴·🟢🔴 | 🔴 | 坏 seq 静默 return 0（persistence_guard:49+runtime_support:19 两份）；P4 改 loud 若粗暴把 `seq=0/None`（合法默认，`int(getattr(op,"seq",0) or 0)` 兜）也卷入 raise → :207/:262 合法短路（completed_seq<=0 放空）翻成 `_completed_downstream_rows`+`_downstream_operations` 双热路径 raise 可用性放大 | owner 裁 loud vs 可观测降级；loud 只对非数/坏类型（TypeError/ValueError 域）raise，`or 0` 兜的 None/0/空串合法路径不卷入；两份原子同改否则 parity 裂；parity 两份同钉 seq=0/None（不 raise）+ seq="abc"（raise）；只动 `_op_seq` 两份，`_seed_*` 一字不碰（r1-LB 误把 :178/:193 的 `_seed_op_id`/`_seed_seq` 当 R69 漏口，r2 推翻但底层有「DRY 三者一起改」真坑）；收口家 schedule_input_contracts.py 已存在无回指。r1 三透镜红+r2-SOUL 红=灵魂线热路径反向爆点；r2-LB 标绿（仅就锚点正确性，与灵魂线维度不同），综合红。 |
| R03 | LEAF-DUP-P4 | 🟡🟡🔴·🟡🔴 | 🟡 | (A) 承重注释段安全；(B) 段四态 parity 未建即清理 → 静默吞 baseline-missing 真告警；`_baseline_missing_or_failed:267 return True` missing 态生产可达（下游 6 处消费 dashboard_workbench:156 等，非 1 处） | (A) 注释随 Batch-1 落（:216 上方三行禁碰 :28/:216/:217 三禁区）；(B) owner 裁 ScheduleCandidate.status 枚举契约前禁动，先建 None/missing/failed/completed 四态 parity，missing 态保留+补不可达注释；绝不裸删 6 消费点任一。r1-SOUL/r2-SOUL 标红=(B) 段灵魂线，(A)/(B) 分判综合黄。 |
| R41 | LEAF-DUP-P4 | 🟢🟡🔴·—🔴 | 🟡 | 收口对全 6 枚举族改语义（非仅 ready）：ready 空串「未齐套」→「齐套」（调度员把未齐套批当齐套放行）、operator「停用/休假」→「停用」丢休假、unknown 透传→「未知」丢值、空串「-」→default-label；测试 :18/:19/:25/:26 钉旧态，改断言贴合收口=接受静默改写复活 | owner 多裁断硬门（≥6 处，含 machine/operator unknown 透传去留 + ready 空串 + operator 停用/休假）；全 6 族×{合法/空串/None/未知/多枚举态} parity 逐格；test_enum_display_consistency.py:18/19/25/26/59/60/61 改 loud 暴露禁贴回收口输出；排 Batch-1（LB04 安全网）之后。r1-SOUL/r2-SOUL 标红=空串/operator 静默翻面，r2-LB owner_pending 维度黄，综合黄（owner_pending 只标）。 |
| R68 | LEAF-DUP-P4 | 🟢🟡🟡·—🟡 | 🟡 | 收口 _meta_bool_state；downtime 同文件 _meta_int_state:23 与待删 _meta_bool_state:30 仅隔 7 行紧邻+二元组同形（int/bool 首位混淆）；压扁 `(bool,parse_failed)` 二元组→坏 meta 静默当 default 前端丢降级提示 | parity 先于收敛（Batch-1→Batch-15）；逐符号删禁碰 downtime:23 _meta_int_state；禁压扁二元组保 parse_failed 位；只提升 degradation:123 单符号到 summary_count_parse.py。 |
| R32 | LEAF-DUP-P4 | 🟢🟢🟡·—🟡 | 🟡 | integrity except:335 warning 吞→落 :343 os.replace 升正式（重症放行/轻症 :341 raise 倒挂）；system_backup:181 只 catch MaintenanceWindowError→RuntimeError 裸 500 | owner 裁硬 raise vs 可观测降级（dossier 灾难链描述偏大，:342 已 raise 拦不通过份，仅「PRAGMA 执行异常」窄路 fail-open）；禁区 :339 else raise 不改弱/:343 os.replace 不加二次兜底/finally 保留；强制回归项=else 未被连带改弱。 |
| R40 | LEAF-DUP-P4 | 🟢🟢🟡·—🟡 | 🟡 | 删 material_repo.py:70-72 静默回退坏值；误连删 :69 float→坏值落 REAL 列退化；生产 service _norm_float 已拦改 raise 零行为影响 | 方向 A 只删 :70-72 保 :69 float；方向 B 引 core.ValidationError 造 data→core 错误耦合不推荐；owner 裁错误分类。 |
| R53 | LEAF-DUP-P4 | 🟢🟢🟢·—🟢 | 🟢 | 纯删 batch_order.py:74 `_ = scheduled_count` 一行 | :58 仍真用故无 unused-arg 复发；禁区 :39/:58/:75。 |
| R61 | LEAF-DUP-P4 | 🟢🟢🟢·—🟢 | 🟢 | 直删 plan 死簇 :160/164/172-187 + 重定向负向测试 | 禁删 live 孪生 _row_text:156/normalize_report_resource_filter:119/filter_downtime_*:274；删函数+改测试同 PR 原子。 |
| LB04 | LEAF-DUP-P4 | 🟡🔴🟢·🟢🟢 | 🟡 | boolean_normalize 真叶子；以「统一到 matrix/DRY」名义删 shared 改指 services → core.models→core.services.common→core.models.enums 导入环+越层击穿 0 违规；单边改 matrix 别名集→personnel/plugin/system_config 链 vs 调度开关链对同串给相反 yes/no 静默无报警 | 仅 :33 上方补注释（algorithms 标「前瞻」）+ 新建全矩阵 parity 网；绝对禁删 shared 改指 services；唯一合法消重=matrix 反向 delegate 到 shared 本批不执行；是 Batch-1 所有 yes/no 收敛动作的安全网前置。r1-LAYER 标红=主透镜核心爆点+安全网前置，计划只补注释故 r1-SOUL/r2 标绿，综合黄（前置门性质）。 |

### tier1 簇（3 簇）

| 债 | 簇 | 投票（r1LB/r1LAY/r1SOUL） | 终判 | 灾难链一句 | 强制前置 / 禁区 / 顺序 |
|---|---|---|---|---|---|
| R42 | NAV-PLANID | 🟡🔴🟡 | 🔴 | dossier 漏 dashboard_workbench_context.py:92 删点（plan_id 落点迁到同名不同文件，经 :119 `build_workbench_plan_context(**_context_kwargs)` 的 `**` 展开真实流入被删形参）→ 删 :191 形参后 dashboard 值班台首页 TypeError 500 启动即炸；C1 emit 误删邻参（link_query:117-120 三真身份参夹住 plan_id）→ URL 丢 version 静默错位 | 删点清单 MUST 补 dashboard_workbench_context.py:92 与 :191 形参同提交；删 emit :118/:154 按符号删 plan_id 单行绝不连片；parity 扩成「删后 version/plan_role/scenario_id/back_to 逐字==删前」含 emit-A/emit-B 两 plan_style（contract 现状零断言这三参=最大静默口）；R54 先落 R42 rebase；与 R60 同提交。r1-LAYER 标红=修法清单不完整照单执行必炸，综合红。 |
| R60 | NAV-PLANID | 🟡🟡🟡 | 🟡 | 字段表删 plan_id 时误删相邻承重透传键（back_to/scope_*/version/plan_role）→ 隐藏表单/导出 URL 丢上下文跨页静默丢 date_range/resource/scope；半截（R60 删表 R42 留读存）=新 P3 | 三张表只删 plan_id 一项绝不连带邻键；MUST 与 R42 单次提交；emit:118/154 归 R42 删 R60 不重复删；先迁测试（去 plan_id 留 back_to）后删生产。 |
| R65 | NAV-PLANID | 🟡🟡🟡 | 🟡 | _target_url 死分支三件套；误删 :7 TARGET_PAGE_PATHS（:177 build_report_navigation_links 真用）→ NameError 报表导航条全挂；化简 :160 等价仅依赖「9 specs plain_url 恒非空」无护栏 | 三件套硬原子同提交（删 def+化简 :160 留 plain_url+删 :4/:6 孤儿 import）；:7 必保留；补不变量护栏 test_all_nav_specs_have_nonempty_plain_url。 |
| R64 | NAV-PLANID | 🟢🟢🟢 | 🟢 | _has_navigation_date_range 零调用纯删 | 锚定单符号 def 删避免手滑碰相邻活函数；与 R65 同提交吸收行号漂移。 |
| R66 | NAV-PLANID | 🟢🟢🟡 | 🟢 | 死副本 reports_workbench.py:150 纯删；跨文件误删 LIVE 同名异签 workbench_links.py:258（:448 真调）→ context_summary 文案静默丢失/NameError | 严格按 suffix 签名定位本文件 :150 绝不跨文件批量 rename；R54 改 :36 后按 suffix 符号实时重定位禁照搬 :150。 |
| R22 | PLAN-IDENTITY | 🔴🔴🟡 | 🔴 | 收口委托 build_plan_identity 后 no_history 页 `result_summary_parse_failed` 取值 **False→True 翻转**（`_summary_unavailable(None,·)=(True,'排产摘要缺失')`），下游 reports_plan_template_fields:45/61 + 3 套手维列表渲染态翻转（无历史方案被标「摘要解析失败」）；且删 view_context:74 normalize_plan_role 行→R21 wrapper field=="plan_role" raise 精度失效→bad role builder 静默归一 adopted（计划「键集 exact==」parity 抓不到取值翻转，evidence_contract:194 superset 双重逃逸） | parity 升级为「键集+取值」exact 双断言（对 no_history 实参断言 result_summary_parse_failed 具体取值）+「bad-role 仍抛 field=plan_role」断言；evidence_contract:194 升 24 键 exact；view_context:74 normalize_plan_role 绝不删/绕过（R21 wrapper 精度唯一上游来源）；owner 裁 no_history 取值保旧 False 还是接受新 True；B01/LB03 先行 R22 只 CALL 不改 builder:158/PlanIdentity.to_dict:46-71。LB+LAYER 两透镜红（不同红因互补），SOUL 黄（触发面窄 medium），综合红（行为变化确凿）。 |
| R21 | PLAN-IDENTITY | 🟢🟡🟡 | 🟡 | 纯删 3 死 shim 安全；误删 dpr_dict wrapper :32-39（+ :11-13 命脉 import 别名）→ R22 precondition 失效+契约测试红；误判整模块死连带删 4 LIVE range 函数→甘特周计划范围静默断裂 | R22 先锁「wrapper 保留」约束 R21 紧随同提交；整文件保留只删 :42/:46/:59 三段+三 import；禁删 :11-13 import 别名（清 import 时显式跳过）；删后跑 `default_plan_resolution_dict("bad")` 自证；R22 锚 wrapper 用符号名（删 import 致上移~9 行）。 |
| R23 | PLAN-IDENTITY | 🟢🟡🟢 | 🟢 | 两份 _normalize_role 字节级相同纯 dedup 收口到已存在 model；误并入 view_context:65 normalize_plan_role（带 VALID 校验抛 ValidationError）→ resolve_plan("bogus") 抛错类型 ValueError→ValidationError 抛点前移→上游 catch ValueError 静默漏接错误角色当合法放行 | 已收口为 model:21 真相源 + service:17 import/:102 调用，绝不并入 view_context:65；resolve_plan 双段 :101-104 只换 :102 符号来源不改语义；与 R34 软序：R23 最小落法后续锚点净上移 4 行，R34 按符号重 rg。 |
| R72 | PLAN-IDENTITY | 🟢🟢🟡 | 🟢 | 两份 _get_plan_role_arg 字节级相同纯 dedup 落 web scheduler_utils.py；分层红线绝不下沉 core（core→flask 越层）；必补 `from flask import request`（现仅 import g，latent NameError） | owner 裁公开名+与 R44 落点共识；必补 request import；空串→None 语义原样保留禁加 ROLE_ADOPTED 兜底；落地前实时 rg 重盘 week_plan.py 高频漂移行号。 |
| R05 | RESOURCE-REPO | 🔴🔴🔴 | 🔴 | collar（column_name 单列 team→空串 + SUPPORTED 无 team + :66 类型有 id 空 raise）结构表达不了承重三轴；步3 先收敛把派工读取收口到未扩 team 现状 collar → team 双 join 谓词（repo:462-463）凭空消失 → 班组视角静默返全量坏数据；空 id 直塞→collar:66 raise→全量视图整页 500；且 normalize_schedule_resource_filter 是双轨共用收口点（超期/明细轨+报表轨），裸改 :65-66 raise 污染另两轨；team 谓词依赖 build_schedule_detail_sql(include_team_context=True)，搬谓词漏带该布尔→no such column: o.team_id | 硬序不可换：步1 扩 collar（team 谓词接口含 include_team_context 信号 + 放开 id 空=全量 + 中文注释，禁 except 吞错/默认空串静默放行，给派工轨单独入口禁裸改 :65-66 raise）→步2 落 5 条 parity（team-only/operator-空-全量/machine-空-全量/team-空-裁断/bad-raise）→步3 才搬 :462-463/:455/:460 进收口点；collar 只产 SQL fragment 文本+参数禁反向 import data SQL builder（model→data 越层+环）；禁误并毗邻 _normalize_team_axis:65（展示轴）；行号系统性 +1 漂移按符号 rg 现盘。3 透镜全红。 |
| R67 | RESOURCE-REPO | 🟡🟡🟡 | 🟡 | 抽单一常量；半截去重（只换 1-2 处其余手抄）=「看似统一实则分裂」未来改别名更易漏→某入口静默缺一资源 key；第 4 处 scheduler_navigation_links.py 不在 all_files 漏它=半截 | ①②纯 6 键必收（喂收口点零新增依赖）；③④ superset 全收或全不收 tuple 保序；第 4 处 owner 未拍前保持现状/仅注释；禁动收口点签名 :119-127；R67↔R42 diff-hunk 串行。 |
| R34 | RESOURCE-REPO | 🟢🟢🟡 | 🟢 | 纯删死方法（repoint 目标 get_plan_time_span_for_resolution 旧锚 :210 存在，R23 后现盘 :206，dossier 正文「不存在」已纠）；删错全响亮 AttributeError | 禁误删活近亲 schedule_repo.py:71/:160 及 facade 断言 :33/:37；facade :11 ScheduleDetailRow 被死 :36+活 :37 共用，只删 :12/:14 保 :11（理由钉「:37 活方法仍用」）；detail_queries 若迁活孪生 list_dispatch_rows 须排 R05 之后（落点是 R05 team-join 战场）；与 R35 同 commit。 |
| R35 | RESOURCE-REPO | 🟢🟢🟢 | 🟢 | list_between 死方法零引用纯删 | 与 R34 同 commit 按符号名自下而上删（:61-69 夹在 R34 删段间防行号二次漂移）。 |
| R36 | RESOURCE-REPO | 🟢🟢🟢 | 🟢 | get_by_op_code/list_by_status 两死方法 ISOLATED 零碰撞纯删 | 从后往前删；本桶最早可落之一。 |
| R37 | RESOURCE-REPO | 🟢🟢🟡 | 🟢 | 死方法 list_links_with_machine_names:82-90 纯删；活近亲 list_links_with_operator_info:92 一字之差，误删活的→静默炸设备页人机联动分组 | diff 严格锁 :82-90，删后立即 grep 活近亲 :92 仍在；R37↔R41 伪干扰删边。 |
| R38 | RESOURCE-REPO | 🟢🟢🟢 | 🟢 | 三处 list_as_dicts 结构同形非同体（SQL 列集各异）三笔独立删 | 禁抽 helper（造零消费活死代码）；part 份与 R39 同 part_repo.py 硬同批。 |
| R39 | RESOURCE-REPO | 🟢🟢🟢 | 🟢 | list_unparsed 死壳 :32-33 纯删，被包活方法 list:20 多消费者不孤立 | 与 R38 part 份同 commit（删 R39 致下方上移 2 行 R38 patch 同基线）按符号名删。 |

---

## 二、跨轮收敛：最终确认标红 vs 已澄清虚惊

### 2.1 最终确认标红清单（11 条，多轮多透镜多数红 / 跨轮被确认）

| 债 | 簇 | 跨轮确认状态 | 一句话 |
|---|---|---|---|
| R09 | PARSE-INT | r1×3 红 + r2×2 红，全 5 透镜一致 | A/B 宽松 vs C 严格不可合并，收编静默放宽→脏 op_id 错配现场记录。最高置信红。 |
| R15 | EXEC-FACT | r1×3 红 + r2×2 红（r3-LAY 仅分层维度黄） | 收口符号空值也 raise，整体 delegate 炸合法空时间，热路径裸奔无 except 直接 500。 |
| R19 | EXEC-FACT | r1-LB/r2×2/r3-LAY 红（r1-LAY/SOUL/r3-SOUL 黄） | sorted 指纹事实承重，统一到不排序版 sha256 静默漂移无单测拦截 + repo 越层/环。多数轮红。 |
| R52 | GRAPH-ERR-DIAG | r1×3 + r2×2 全红 | 31 用例蒸发（dossier「~23」严重失真，18 个走全量版断 ReadyQueueContractError 无归属）+ 异常类不等价。 |
| R14 | GRAPH-ERR-DIAG | r1-LB/r1-LAY 红，r1-SOUL/r2×2 黄；双门 owner_pending | 删死门把候选灵魂线平移活门→fallback 吃 raise→「无静默回退」覆盖被悄丢；撞 LB01。综合维持红。 |
| R69 | LEAF-DUP-P4 | r1×3 + r2-SOUL 红（r2-LB 仅锚点维度绿） | loud 化把 seq=0 合法短路也卷入 raise→双热路径可用性放大；r2-LB 推翻的是锚点不是灵魂线。 |
| R54 | NAV-GUARD | r1-SOUL/r3-SOUL 红，r1-LB/LAY/r2×2/r3-LAY 黄 | collar 当前不产 3 fail-open 键，「5 套 delegate」=直接抹键 fail-OPEN 脏写。r3-SOUL 挖出 collar 扩产前裸 delegate 必连环炸，综合红。 |
| R04 | PARSE-INT | r1-LB/r1-SOUL 红，r2×2 黄 | F1 默认值 + 6 处 except 异常逃逸双爆点；r2 复核「前置全绑可做」降黄，综合维持红（双爆点叠加）。 |
| R42 | NAV-PLANID | r1-LAY 红，r1-LB/r1-SOUL 黄 | dossier 漏 dashboard_workbench_context.py:92 删点，照单删 :191 形参 dashboard 启动即 TypeError 500。修法清单不完整=红。 |
| R22 | PLAN-IDENTITY | r1-LB/r1-LAY 红（两红因互补），r1-SOUL 黄 | no_history result_summary_parse_failed False→True 取值翻转 + 删 view_context:74 破 bad-role raise 护栏；parity 只验键集抓不到。 |
| R05 | RESOURCE-REPO | r1×3 全红 | 承重三轴塌缩 + 双轨共用收口点裸改污染 + team 谓词 builder 耦合(include_team_context)；硬序步1扩collar先于步3收敛。 |

### 2.2 已澄清虚惊清单（r1 标红被 r2/r3 逐符号 rg 推翻 / 澄清为 owner 裁断或 loud 响声而非静默会炸）

| 项 | r1 误判 | r2/r3 推翻依据 |
|---|---|---|
| **R70**（LEAF-DUP-P4） | r1-LB🔴：「schedule_service.py:46 是承重正式函数 `_raise_schedule_empty_result`，死副本锚点不存在」 | r2 逐符号 rg：`:46` 就是死副本本体（本文件零调用），live 在 run/input_collector.py:79。r1 把函数名当承重。**纯删安全🟢**。 |
| **R43**（LEAF-DUP-P4） | r1-LB🔴：「9 wrapper + :522 延期行全仓失踪，scheduler_run.py 仅 8 行薄壳」 | r2：9 wrapper 实存，`:8` 薄壳即债本体（薄=债非失踪），roadmap rg 实测 :522 在场。**降🟡 owner_pending**。 |
| **R69 锚点**（LEAF-DUP-P4） | r1-LB🔴：「runtime_support :178/:193 两处 return 0 漏登」 | r2：那是 `_seed_op_id`/`_seed_seq` 两个无关函数的 return 0，不在 `_op_seq` 收口范围（顺手统一反而是 Q1 越界误删）。**但 R69 因灵魂线另立红，非此项**。 |
| **R03 (B) 禁区**（LEAF-DUP-P4） | r1-LB「dashboard_workbench:156 被别名 `comparison.get("n")` 遮蔽，rg 零命中禁区失踪」 | r2 实测 :156 = `if comparison.get("baseline_missing_or_failed")` 真键直命中无别名遮蔽，helpers:390 同；别名 `n` 陷阱是 R42/build_workbench_plan_context 的不波及 baseline 键。禁区在场。 |
| **R30/R33 facade**（COMPAT-DISPATCH） | 「facade 漏改 ImportError 打挂 facade 全表面/存活消费者」夸大 | 两 facade 均无活生产消费者只有 3 测试 import = **CI 响声债（loud ImportError 立即可见）非静默 fail-open 坏数据不流入生产**。 |
| **R51 复活**（COMPAT-DISPATCH） | r1-LAYER🔴「灵魂线复活红线」 | 灵魂线复活是「序错/续命即复活」的 loud 风险（删错碰收口点 raise 或测试保留报红），非静默炸；前置全绑（两测试整退禁迁）即黄。 |
| **R55 三门**（GANTT） | r1-SOUL🔴 | 红因是 owner_pending+needs_adversarial+verdict=null 三流程门未过却被排进可执行 A3，是**流程门未通过**非「会炸」；分析已透，门过后降黄。 |
| **R24 路 B**（GRAPH-ERR-DIAG） | r1-LB🔴 | 红因是路 B（改指零消费 core 丢护栏）；只走路 A（删 core 死副本）安全，owner 默认推路 A，综合黄。 |
| **R34「不存在」**（RESOURCE-REPO/也涉 PLAN-IDENTITY） | dossier 正文「repoint 目标 get_plan_time_span_for_resolution 不存在」 | Layer1 + verify + 本轮回盘三纠：旧锚存在于 schedule_plan_query_service.py:210；R23 后现盘为 :206，执行按符号重 rg。纯删安全。 |
| **R13 死字段「直删」**（EXEC-FACT） | registry「无脑直删」 | 被 5 处测试读活「死」定性被推翻，须先迁测试，但非会炸（漏退即 TypeError 响亮可接受）；r1-SOUL 红（连带删 latest 链静默信号消失）是另一维度，债本身黄。 |

> **跨轮规律**：r1-LB 在 LEAF-DUP-P4 的 3 条红全系**自身 rg 回盘误判**（把薄壳别名当失踪、把同名函数当承重、把无关 return 0 当漏口），r2 逐符号独立回盘全部推翻——这是 cs-audit-verify 提示的「别拿被测对象自身当核查基线会自污染」的典型，最终以 r2 逐符号 rg 为准。但 R69/R03/R41 在 SOUL 透镜下另有**灵魂线维度**的独立红/黄（与锚点维度正交），不被 r2-LB 的锚点推翻所抵消——同一债不同透镜的红因须分维度对账，不可互相抵消。

---

## 三、completeness-critic：回炉建议清单（12 条）

> 标准：透镜没覆盖 / 轮次不足 / 争议未解 / 各轮结论互相矛盾未拍定 / 收口没验行为等价。

| # | 债/簇 | 没攻透的点 | 回炉建议（一句） |
|---|---|---|---|
| 1 | EXEC-FACT 同文件串行顺序 | **各轮结论互相矛盾未拍定**：r1-LB 簇 A3 写 `R15→R19→R13`，但 R13 dossier §5 写 `R13→R19→R15`，r1-LB §漏项5 与 r3-SOUL 都点名此矛盾未拍 | 回炉拍定 provider 三债串行序（建议 R15 先收口语义→R19→R13 删死物，每步重 rg），且 R15/R19 双 owner_pending 须同批裁断否则先落者漂移另一方 Edit 锚点。 |
| 2 | COMPAT-DISPATCH degradation 性质 | **各轮自相矛盾未拍定**：r1-LB/r1-LAYER 称 degradation.py 是「真承重实现 385B 20+生产直连」，r2-SOUL 逐字推翻为「17 行纯 re-export 壳」 | 回炉用一次 `wc -l + cat` 拍定 degradation.py 究竟是壳还是真实现——结论不撼「:15 死保」但执行者据「真实现 vs 壳」判断是否可删的认知会反转。 |
| 3 | R22 收口（PLAN-IDENTITY） | **收口行为等价未验透 + 两红因是否同一动作未合并**：LB 透镜红因=no_history result_summary_parse_failed False→True 取值翻转；LAYER 透镜红因=删 view_context:74 破 bad-role raise——两红因都关于 R22 但 SOUL 透镜判黄（触发面窄 medium） | 回炉合并三透镜：parity 必须同时含「键集+取值 exact」+「bad-role 仍抛 field=plan_role」双断言，且 owner 显式裁 no_history 取值语义（保旧 False vs 接受新 True）——这是「收口没验行为等价」的标准回炉项。 |
| 4 | R54 collar 扩产（NAV-GUARD） | **轮次间认知跃迁未闭合**：r1/r2 假设「collar 能内部产 guard 全集」，r3-SOUL 实读 collar 187-258 当前**不产** 3 fail-open 键、无 plan_resolution 入参 | 回炉把「collar 扩成 3 键 guard 产出点 + fail-CLOSED 默认」立为独立承重前置改动 owner 审过，再谈「5 套 delegate」；否则裸 delegate=连环 fail-OPEN，r3 这个发现 r1/r2 都没攻到。 |
| 5 | R09↔R04 persistence_errors:13 归属 | **争议未解（跨债矛盾指令）**：R04 dossier 列其为「禁收口的错误路径降级哨兵仅注释」，_layer2_residual:37 列为「R09 第 3 份未收编 Optional 副本 owner 复核收编」，两份计划相反指令 | 回炉 owner 裁定 schedule_persistence_errors.py:13 归 R04 禁区还是 R09 收编面——按 R09 收编它会违 R04 灵魂线在错误路径抛二次异常。 |
| 6 | STRICT 4 处分类（PARSE-INT） | **基线口径失真未回写**：_layer2_residual「STRICT 4 处 `->int` loud raise 一字不碰」部分失真，实测 auto_assign:114 与 scheduler_public_errors:167 body 是 `except: return 0`（→0 哨兵非 loud raise） | 回炉回写残留表：STRICT 真 loud raise 仅 scope:9 + feedback_support:161 两处，auto_assign:114/public_errors:167 是 →0 哨兵——分类依据打架虽不撼 R09 结论但误导执行者对 R04 哨兵补注释的判断。 |
| 7 | R52 全量版 18 用例归属（GRAPH-ERR-DIAG） | **测试迁移清单严重失真**：dossier「~23 LIVE-only」实测 31 用例，约 18 个走 `_ready()`→全量版断 ReadyQueueContractError（异常类≠LIVE ValidationError），迁移方案没安排这 18 个归属 | 回炉 owner 决策门前按 `_ready` vs `_graph_state` 两类 helper 重新分桶 31 用例，显式裁定 18 个全量版合同用例随删（接受丢 ReadyQueueContractError 合同）还是 LIVE 已等价覆盖（须逐分支证 parity 非「均拒绝」一句带过）。 |
| 8 | R41 改面范围（LEAF-DUP-P4） | **收口非等价面被严重低估**：r1/dossier 只盯 ready 一处，r2-SOUL 逐 def 对照发现改面是全 6 枚举族（空串「-」→default-label、unknown 透传→「未知」、operator「停用/休假」→「停用」、ready 空串翻面），owner 裁断门从 4 处扩到 ≥6 处 | 回炉 owner 裁断材料须覆盖全 6 族×5 类，parity 逐格；且把 test_enum_display_consistency.py:18/19/25/26 改 loud 暴露列为硬门（禁贴回收口输出复活静默）。 |
| 9 | R69 双消费者 parity（LEAF-DUP-P4） | **收口等价的 seq=0 合法路径只在 SOUL 透镜攻到**：`_op_seq` 体 `int(getattr(op,"seq",0) or 0)` 两层兜 None/0/空串，与 except 域正交；loud 化误把 seq=0 卷入 raise=可用性放大，且 guard:207 + runtime:262 双短路两份须原子同改 | 回炉 parity 必须两份同钉 seq=0/None（走短路不 raise）+ seq="abc"（loud raise），证明 loud 化没污染合法 0 短路；LB 透镜只盯锚点没攻到这个等价分叉。 |
| 10 | GANTT _copy 卡口认知（GANTT） | **计划过度告警未在所有轮统一纠正**：r1-LAYER/r1-SOUL/r2 一致发现 `_copy_critical_chain_result:104` 首行 `dict(result)` 整体浅拷天然保留新键**非 strip 点**，但簇计划/dossier 反复称「_copy 会丢须补」 | 回炉回写计划：真卡口只有「单份 _normalize（必改）+ contract unavailable 分支:22-39（须补）」两道，_copy 非卡口，contract:40 透传分支不卡——框定错位会让 review 把注意力放错且越改 _copy 越接近误删（6 处缓存浅拷在用）。 |
| 11 | R29 monkeypatch 续命点（COMPAT-DISPATCH） | **前置指错文件全轮一致但计划未回写**：dossier A4/Layer1 称续命点 `regression_ortools_warmstart_failure_contract.py:136`，实测该文件 monkeypatch 的是 ortools/cp_model 与 number_utils 无关，真点是 `regression_number_utils_facade_delegates_strict_parse.py:45-48` | 回炉回写：R29 走薄壳化前置=重写 `regression_number_utils_facade_delegates_strict_parse.py` 为身份测试，warmstart:136 是误指；照误指改 warmstart 会以为前置满足实则没动真续命点。 |
| 12 | R42 navigation_context:57 override kwargs（NAV-PLANID） | **收口面未审透**：r1-LAYER 漏项2，:57 走 `_navigation_context_override()` 的 `**kwargs` 路径，其 kwargs 是否含 plan_id 键未回盘——若含且不删=同 C0 TypeError | 回炉 owner/执行前补审 :57 override 的 kwargs 来源是否含 plan_id，连同 :92 dict 键纳入 R42 同提交删除清单。 |

---

## 四、每簇一段汇总

> 每簇：原子性最终判定 / 承重禁区清单（按符号）/ 必须先落的 parity·注释 / 测试迁移顺序。

### tier3 承重簇

**C-NAV-GUARD（R54🔴 / R58🟡 / R44🟢 + 邻接 N1🟡/N2🟡）**
- 原子性最终判定：R54↔R42↔R60 同改 `build_workbench_plan_context` 签名/dict **MUST 同批**（batch_hint R42=Batch-3 vs deps 同 R54=Batch-2 张力 owner 裁）；R58→R54→R44 同 nav_publish 文件硬序。
- 承重禁区（按符号）：`_is_current_official_identity:292-296` 判定方向、`_feedback_guard_context:149-161`、门控落点 `:248`、`can_emit_feedback_write_urls:469-473`、view_context `default_plan_resolution_dict` fail-closed 默认；N1 `can_write_feedback` 单字段（禁放宽成 or/禁加 preview 旁路）；N2 `_event_id_for_revision` 末位 return 0（禁删 `if index<total: raise`）。
- 必须先落 parity/注释：R54 逐键四态 parity（含 L5 is_comparison_plan 反例 + reports 第二注入路径阻断态）+ collar 扩 3 键产出点；R58 注释钉 :88/:91 双入口；N1 注释钉「真闸在 feedback_service:369-382 双 raise，本字段仅 query 优化短路」（禁引 dossier 幻觉的 :89/:70-84）。
- 测试迁移序：删任一手维列表前先令对应契约测试改读 collar 输出，删列表与改测试同 commit。

**C-EXEC-REVIEW（LB02🟢 / LB05🟢 / R62🟡）**
- 原子性最终判定：LB02/LB05 一次注释满足两条；R62 三处消费方（dict / 模板 `!=`副行+title / xlsx `or`）+ 早退块 :438-440 强原子同 commit。
- 承重禁区（按符号）：`execution_review` 签名 :209（不收 plan_role/scenario_id）、五处硬钉 :58/:180-181/:191-192/:221/:236、:65/:69 兜底、`_resolve_plan` Protocol:121；state 层 latest_*/counterpart_* 真身份键（删 R62 绝不触）。
- 必须先落 parity/注释：A1 注释交叉引用 web 真定义宿主（reports_request_support.py:75 / reports_execution_review_context.py:8）+ v19 DB CHECK 双列 + schema:284 candidate_rows 第二表；R62 收口面**零现成断言**须先写 3 套 parity 快照（dict/xlsx/模板含 title）红→绿基线。
- 测试迁移序：A1 注释先落 Batch-1 → R62 后做 Batch-3，按符号 `_resource_pair_payload`+`!=` 重 grep 禁照抄行号。

**C-EXEC-FACT（LB01🟢 / R17🟡 / R15🔴 / R19🔴 / R18🟢 / R20🟢 / R13🟡）**
- 原子性最终判定：LB01 注释门控整个 service 文件删改先落；R17 三行净删；R20 改 :52 与 R17 串行；provider 三债串行序待拍（回炉#1）；R18+R13 共注释覆盖 repo:399-405 整组合批。
- 承重禁区（按符号）：LB01 硬拒 :369-374/:381-382 + 写死消毒 :471-473 + reported_status :475（与 R17 同 `_build_event_payload`）；R15 provider `if not text: return None` 空值短路 + support:228 raise；R19 snapshot:40 `return sorted`（事实承重）；R18 repo:399-405 六格 stub raise；R13 provider:110/113 raise 软禁区。
- 必须先落 parity/注释：R15 三处 required/optional parity（含空值分支断言）；R19 positive_op_ids 黄金用例（F-fingerprint 门）；R13 先迁 scope_read_contract→reschedule。
- 测试迁移序：R13 先 scope_read_contract（契约源头）→reschedule→生产删字段最后；R17 删 :81 死键确认 :80 活键不动、6 文件常量不碰。

**C-CONFIG-DUAL（LB07🟡 / R71🟡 / R47🟡 / R45·R48🟢 / R31🟢 / R26🟡）**
- 原子性最终判定：LB07 注释+扩 parity 是 R71 物理收敛/R47 删参的唯一准入门 Batch-1 ROOT 先落；R47+R71 同批改后统一回盘（禁按旧行号核 :470/:153 禁区）；R45≡R48 已 fixed，不再施工，旧 sp06 锚点为 no-op。
- 承重禁区（按符号）：coercion `graph_downstream_weight=0` 置零(:470) + loud raise 族(MISSING_POLICY_ERROR:71-72 等按符号语义认定非行号) + 30 字段锁步表 + read_runtime_cfg_raw_value 入口 + `_handle_missing_value` INHERIT_LEGACY 两栈不对称（新爆点，须纳 parity）；R47 invalid 4 活实参 + collector.add(blank_required)；R31 :6/:7/:8 活常量。
- 必须先落 parity/注释：LB07 三 helper 逐分支 + `_handle_missing_value` 真值表逐字保真（含「非dict→None 不抛」「count 坏值→1 不抛」）；R47 守门真名 `_emit_blank_required`（非 `_emit_ln`）。
- 测试迁移序：R31/R33 删序（R33 删 facade 不晚于 R31 删源）；R26 晚于 R29/R33/R52 三桶收敛 + 迁 2 离线消费者。

### tier2 簇

**C-PARSE-INT（R09🔴 / R04🔴 / R59🟡 / R28🟢 / R01🟢 / R08🟡）**
- 原子性最终判定：R01 先删→R04 按新行号收口同 PR；R04 6 处 except 同 PR 加 ValidationError 不可拆；F1（R04+R59 共用）必默认 False 自带 parity；R08 等在途 task_key 重构落定再动。
- 承重禁区（按符号）：STRICT 真 loud raise scope:9 + feedback_support:161（auto_assign:114/public_errors:167 是 →0 哨兵，分类回写见回炉#6）；R04 哨兵 B/C 仅注释禁改 raise + LB08 文案/正则桥；R08 feedback_write_enabled 参数（:234 活消费）+ service:127≡:130 同源不变式。
- 必须先落 parity/注释：R09 两路 parity（test_AB + test_C_float_bool 含 B 副本 `or 0` 审计）；R04 F1 含 sgs_graph 风格调用断言；R08 先钉 :127≡:130 守卫。
- 测试迁移序：R59 先 parity 钉 '1.0' raise + blank 短路→F1 后收口；R01 删函数+删 SP05 断言必须同提交（中间提交必红）。

**C-GANTT（R10🟢 / R11·R63🟢 / R12🟡 / R55🟡）**
- 原子性最终判定：A1{R11≡R63}已 fixed 且已先于 A2{R12}/A3{R55}；R12 与 R55 后续同批一次穿白名单（同改单份 _normalize + contract unavailable 分支）；R10 已 fixed。
- 承重禁区（按符号）：support:58 禁 `return raw`、`_copy_critical_chain_result:104`（6 处缓存浅拷，非 strip 点）、:84 过滤、sort:114/max:262、出口 try/except :338-341/:352-359、:385 None 回退 + support:55-56 分流判据、`_is_current_official_identity` 方向；R10 邻接活方法 resolve_version:64。
- 必须先落 parity/注释：normalize parity 黄金基线已落，当前 `tests/gantt/test_gantt_critical_chain_normalize_parity.py` 钉住 11 个边界；R12 dropped_count 后续双补 :54 与 :328-334 且穿 _normalize 白名单 + contract:22-39；R55 scope 调用点显式赋值禁反推。
- 测试迁移序：删旧符号前先建 parity（snapshot subset 抓不到字段分叉）；R55 owner+怀疑者过 PHASE0 §6 三问后才锁终态。

**C-COMPAT-DISPATCH（R30🟡 / R33🟡 / R29🟡 / R49🟢 / R50🟢 / R51🟡）**
- 原子性最终判定：A1 硬序 R33步1（迁 import）→R30（删实现+三常量与 R31/facade 同窗删 re-export）→R33步2/3；A2{R49/R50/R51}同改 dispatch_rules.py 一次性删从大行号往小（R51 删 :28-35 致下移 7~8 行）。
- 承重禁区（按符号）：core.shared 三模块全文、degradation:15+身份测试:375-390+forbidden:355、import math:3、compat_parse float/int import 块、sgs_scoring:34 同名活函数、收口点 schedule_params/optimizer_config（只读）。
- 必须先落 parity/注释：R51 收口点 loud raise 只读确认；R29 KEEP 仅补注释。
- 测试迁移序：R51 两续命测试整体退场禁迁移禁保留 :25 兜底断言（保留=复活 P4）；R29 走 B 先重写 number_utils_facade 测试为身份测试。

**C-GRAPH-ERR-DIAG（R52🔴 / R14🔴 / R24🟡 / LB08🟡 / R46🟡 / R02🟢 / R06·R27🟡 / R25🟡）**
- 原子性最终判定：R52 方向 A 先新建 test_sgs_graph_ready.py 按 31 用例分流→再删 impl+R25 垫片同提交；R06+R27+gantt 四空包同一原子提交；LB08 注释先落→R46 才删；R18 风格 R46 按符号重 grep（LB08 插行后下移）。
- 承重禁区（按符号）：LB08 LEGACY_PUBLIC_PATTERNS:62 等正则桥（删→静默降级通用文案）、R52 ReadyQueueContractError 抛错链 loud raise、R24 web 孪生 NonFiniteDiagnosticNumber/safe_int/safe_float、R46 同名陷阱 v4_sanitizers:37、R14 _resolve_strict_plan（撞 LB01）、R02 兄弟壳 :478+GraphInputContractError 守卫、R06 _assert_init_has_no_imports:173+SP05:638 第二处三元组。
- 必须先落 parity/注释：R52 parity 异常类只断「均拒绝」+ None 分支两路分别写 + 删 _full_scan_ready_ids:79 helper 与改 6 oracle 原子；LB08 注释产出点按实证 internal_operation.py:119/148/150/152/154 改写禁贴 planned 草稿。
- 测试迁移序：R52 先迁后删（含 31 用例 + 4 ValidationError 契约，行号按符号 :299/:311/:326/:352）；R14 候选灵魂线 :328 owner 裁改钉 resolve_existing_plan 层禁平移活门。

**C-LEAF-DUP-P4（R70🟢 / R43🟡 / R69🔴 / R03🟡 / R41🟡 / R68🟡 / R32🟡 / R40🟡 / R53🟢 / R61🟢 / LB04🟡）**
- 原子性最终判定：LB04 注释+parity 网是 Batch-1 所有 yes/no 收敛动作安全网前置；R69 两份 `_op_seq` 原子同改；R61 删函数+重定向负向测试同 PR；R68 parity 先于收敛（Batch-1→Batch-15）；R43↔R26 共碰 scheduler_config.py+SP05 串行。
- 承重禁区（按符号）：LB04 boolean_normalize（禁删 shared 改指 services=环+越层）、R69 `_op_seq` 两份（禁碰 `_seed_*`、loud 只动 except 域）、R03 CandidateTrialFailure:28/except:216/_failed_plan:217、R41 test_enum_display_consistency:59-61 钉静默断言、R68 downtime _meta_int_state:23（禁碰禁压扁二元组）、R32 :339 else raise+:343 os.replace、R40 :69 float、R70 :7 ValidationError import。
- 必须先落 parity/注释：LB04 全矩阵 parity（algorithms 标「前瞻」）；R69 两份同钉 seq=0/None 不 raise + 坏类型 raise；R03 四态 parity（missing 态保留+补不可达注释）；R41 全 6 族×5 类逐格；R68 钉 `(bool,parse_failed)` 二元组禁压扁。
- 测试迁移序：R41 测试改 loud 暴露禁贴回收口输出（复活硬门）；R32 强制回归项=else 未被连带改弱。

### tier1 簇

**C-NAV-PLANID（R42🔴 / R60🟡 / R65🟡 / R64🟢 / R66🟢）**
- 原子性最终判定：R42⇔R60 强制单次提交（emit:118/154 唯一归 R42）；R65 三件套硬原子（删 def+化简 :160+删 :4/:6）；R54 先落 → R42 删 :191 形参 rebase + R66 按 suffix 重定位。
- 承重禁区（按符号）：link_query:117/119/120+:153/155 三真身份参（夹 plan_id）、navigation_context:79/80（R56 adopted 强制）、:7 TARGET_PAGE_PATHS（:177 真用）、workbench_links.py:258 LIVE _context_summary、三张字段表非 plan_id 键、`_EXECUTION_REVIEW_FORBIDDEN_EXTRA_PARAMS:266` 禁参集。
- 必须先落 parity/注释：R42 parity 扩成「删后 version/plan_role/scenario_id/back_to 逐字==删前」含 emit-A/emit-B 两 plan_style（contract 现状零断言三参=最大静默口）+ 补 dashboard_workbench_context:92 删点；R65 补 test_all_nav_specs_have_nonempty_plain_url 不变量护栏。
- 测试迁移序：R42+R60 共享 contract :109/:122/:126 只迁一次（去 plan_id 留 back_to）先于删生产。

**C-PLAN-IDENTITY（R22🔴 / R21🟡 / R23🟢 / R72🟢）**
- 原子性最终判定：B01/LB03 先行→Batch-1 parity（24 键 exact + bad-role raise 双断言）→R22 收口→R21 删 3 shim（严守保留 wrapper+不影响 :74）；R23 与 R34 软序：R23 最小落法后续锚点净上移 4 行，R34 后续按符号重 rg。
- 承重禁区（按符号）：view_context:74 normalize_plan_role（R21 wrapper field=plan_role 精度唯一上游来源，R22 绝不删/绕）、builder:158 build_plan_identity + PlanIdentity.to_dict:46-71（LB03 承重 R22 只 CALL）、gantt_plan_query.py:32-39 wrapper + :11-13 import 别名 + :50-156 四 LIVE range 函数、normalize_plan_role:65（R23 绝不并入第三变体）。
- 必须先落 parity/注释：R22 parity 升「键集+取值」exact + evidence_contract:194 升 24 键 exact（双重逃逸口）；R72 必补 `from flask import request`。
- 测试迁移序：R22 先升 parity 再收口；续命测试 :294-301 R21/R22 都不碰（R22 保留 wrapper）。

**C-RESOURCE-REPO（R05🔴 / R67🟡 / R34🟢 / R35🟢 / R36🟢 / R37🟢 / R38🟢 / R39🟢）**
- 原子性最终判定：R05 硬序步1扩collar→步2 落 5 parity→步3 才搬 repo 字面量（不可换序）；R34↔R35 同 commit；R38↔R39 part 份硬同批；R34 detail_queries 若迁活孪生须排 R05 之后（落点是 R05 team-join 战场）。
- 承重禁区（按符号，行号系统性 +1 漂移按符号 rg 现盘）：repo team 双 join :462-463 + 空 id 全量 :455/:460、collar :65-66 raise（双轨共用收口点禁裸改给派工轨单独入口）、_normalize_team_axis:65（展示轴禁误并）、R34 活近亲 schedule_repo.py:71/:160 + facade :11 ScheduleDetailRow（:37 活方法仍用保留）、R37 活近亲 :92、R67 收口点签名 :119-127。
- 必须先落 parity/注释：R05 步1 collar 接口含 include_team_context 信号（禁反向 import data SQL builder=越层+环）+ 中文注释「id 空→全量（故意）」；5 条 parity（team-only/operator-空/machine-空/team-空-裁断/bad-raise）先于步3。
- 测试迁移序：R05 步3 前先迁 smoke:177-194 + 续命 :340；R34 删前先退 facade 断言 + detail_queries 10 用例 + benchmark:505 repoint。

---

## 五、Layer3 新爆点登记

> 三轮新发现、cluster/dossier 计划未覆盖的「计划外爆点」。已并入上方各债前置，此处独立登记便于 Layer4 排批校验。

| # | 爆点 | 簇/债 | 性质 | 一句话 |
|---|---|---|---|---|
| 1 | **collar 当前根本不产 3 个 fail-open 键** | NAV-GUARD/R54 | 致命·计划假设被推翻 | r3-SOUL 实读 `build_workbench_plan_context` 187-258 只 emit is_preview/can_write_feedback(已门控)，is_comparison/is_superseded/is_current_executable 一个都不产、也无 plan_resolution 入参——「5 套 delegate 到 collar」在 collar 扩产前=直接抹掉三键的 fail-OPEN 入口，须把「collar 扩成 guard 产出点」立为独立承重前置。 |
| 2 | **guard 第 6 面 `_PUBLIC_FILTER_DROP_KEYS`** | NAV-GUARD/R54 | 计划漏列第 6 个手维面 | `scheduler_resource_dispatch.py:40-73` 脱敏 drop 集（:270 `if key not in _PUBLIC_FILTER_DROP_KEYS`）含三关键键 + L1-L5 都没有的 is_current_executable_version:69/schedule_result_status:63/scenario_name:72，机制≠guard 投影但键集独立手维；R54 统一时误当第 7 套 guard 去并/漏同步 → 公开 filters 漏脱敏/误删。 |
| 3 | **L5 `is_comparison_plan` 二次衍生 OR 兜底** | NAV-GUARD/R54 | 计划「禁统一键名」未点名具体丢键路径 | `scheduler_gantt_task_detail.py:98 context["is_comparison"]=bool(get(is_comparison) or data.get("is_comparison_plan"))` + 别名元组 :13——L5 唯一吃 is_comparison_plan 回退别名；收口源 view_context 用 `is_comparison_plan(role,source_table)` 函数重算不读原始键，统一时丢回退 → 「源键 True 但函数重算 False」的 gantt 比较版 fail-OPEN。 |
| 4 | **N1 蕴含链幻觉锚点** | NAV-GUARD/N1 | 承重链注释自身就是错链 | cluster D/corrections C 钉 N1 注释引 `_can_write_feedback:89`/`_is_official_plan:70-84` 在 execution_context.py——实盘该文件无此二符号（:129-130 是裸 `bool(identity.get("can_write_feedback"))`）；真闸在 feedback_service:369-382 双 raise，本字段仅 query 优化短路；照计划守不存在的禁区行=守空气，注释须钉真闸。 |
| 5 | **R62 模板 title 第四处** | EXEC-REVIEW/R62 | 原子面少算一处 | 簇文 §A2 只列模板 `!=` 死副行 :138/139/142/143，漏同行 `title="{{ r.X_identity_label }}"` 也读 identity_label；删键漏改 title → Jinja undefined → `title=""` 可观测 UI 降级（非逐字节等价）；parity 须断 title 属性前后相等。 |
| 6 | **A1 注释缺 v19 DB CHECK 交叉引用** | EXEC-REVIEW/LB02·LB05 | 失忆债残留 | 三 dossier 把 :57/:58 仅当「第 7 处硬钉」，未点明与 v19 `CHECK(source_table='schedule')`+`CHECK(effective_plan_role='adopted')` 双列 1:1 对应；读侧无 DB CHECK 兜底（v19 只护写表），A1 注释须补「此硬钉是 v19 CHECK 服务层前哨，读侧唯一最后一道」。 |
| 7 | **R15 收口符号空值即 raise** | EXEC-FACT/R15 | 比计划口径更狠一层 | 计划只写「区分空值→None vs 坏值→raise」，但 `parse_operation_event_time:80` **空值本身就 raise**；provider 调用点 `_fact_from_state:52/53` 内联进 ExecutionFact kwarg 构造、facts_by_scope 链全程**裸奔无 except**——整体 delegate 把合法空时间炸 raise=正常读历史 500，收口必须分支级保 `if not text: return None` 在 provider 本地。 |
| 8 | **启动探针喂 not-a-date** | EXEC-FACT/R15·R17 | 迁移耦合门未列入清单 | `migration_operation_execution_contract.py:349/355` 启动主动 INSERT `event_time:"not-a-date"`+`source_table:candidate_rows` 靠拒绝判库迁移态；R15 改 provider 时间解析边界 / R17 删 EXECUTION_EVENT_EXCEPTION 链须先确认不撼探针对「坏 event_time 必被拒」的预期，簇文档只提 schema.sql CHECK 未列启动探针。 |
| 9 | **R19 sorted 指纹承重 + 零符号级测试** | EXEC-FACT/R19 | 收口无护栏先行 | snapshot:40 `return sorted(out)` 喂 :91 sha256 是事实承重，三函数 tests/ 0 符号级测试——naive 统一成不排序版 → 下游 4 处 guard/publish/scenario 快照比对静默失真无单测拦截；canonical 必保 sorted（等同承重待遇）。 |
| 10 | **R47 死参与活参 1:1 字面量混居** | CONFIG-DUAL/R47 | 盲删活参静默降质 | `raw_value=raw_value` 全栈 8 处文本逐字相同，死参（`_record_blank_choice_degradation`）与活参（`_record_invalid_choice_degradation`，:116/:119 读）紧邻；现成 blank parity 测试不覆盖 invalid 路 → 盲 grep/sed 删活参=invalid 降级证据静默丢失且测试全绿。 |
| 11 | **`_handle_missing_value` 两栈非 byte 等价** | CONFIG-DUAL/LB07·R71 | parity 范围漏掉真实不对称 | service `config_field_coercion.py:115` 多一条 `if policy==MISSING_POLICY_INHERIT_LEGACY_OMISSION` 分支 + 返回 Tuple，model 栈无此分支返回裸 Any；LB07 parity 守卫范围（3 helper+spec）不覆盖它，R71 收敛/「DRY 统一」该函数 → legacy-omission 语义静默丢失或解包错位且 parity 全绿。 |
| 12 | **R09 B 副本 `or 0` 外层兜底塌成 0** | PARSE-INT/R09 | 与放宽方向相反的另一条坏数据流 | B 副本 `:257/:258 _positive_int(...) or 0`——若 A/B 收口到 scope 严格版（catch→None），`5.9` 由 `int→5` 变 `None or 0=0`，op_id/schedule_id 从 5 塌成 0（scope <=0 非法值被 `or 0` 静默吃成 0）注入 task_card；cluster 字段7 只讲「C 放宽」漏此点。 |
| 13 | **persistence_errors:13 双重认领矛盾指令** | PARSE-INT/R04↔R09 | 跨债相反指令未拍 | R04 dossier 列其为「禁收口的错误路径降级哨兵仅注释」，_layer2_residual:37 列为「R09 第 3 份未收编 Optional 副本 owner 复核收编」；按 R09 收编它会违 R04 灵魂线在错误路径抛二次异常。 |
| 14 | **contract available=False 分支吞 R12 dropped_count** | GANTT/R12 | 第三道真卡口 计划只标两道 | `gantt_contract.py:22-39` available=False 时硬重建固定 5 键 dict 丢 dropped_count/critical_chain_partial；最该报警的「全坏行」恰落 available=False 分支被吞——计划只把「两份 _normalize」列卡口、明示「contract:40 透传不卡」对 available=False 路径是错的，须在 :22-39 显式保留新键。 |
| 15 | **R69 seq=0 合法短路被 loud 化击穿** | LEAF-DUP-P4/R69 | loud 化反向爆点 | `_op_seq` 体 `int(getattr(op,"seq",0) or 0)` 两层兜 None/0/空串，:207/:262 `completed_seq<=0` 把这当合法「无有效完成态」短路（放空不报错）；P4 粗暴把 seq=0 也卷入 raise → `_completed_downstream_rows`+`_downstream_operations` 双热路径从静默放空翻成 raise 可用性放大，loud 只能动 except 域。 |
| 16 | **R52 `_full_scan_ready_ids:79` 隐性二次爆点** | GRAPH-ERR-DIAG/R52 | helper 体调 impl 漏改 NameError | 该 helper `return get_ready_operation_ids(...)`，impl 一删不仅 import 红，6 处差分 oracle（:275/278/281/284/296）调它也炸；删 :79 helper 与改 6 oracle 改字面量期望是同一原子动作顺序锁死。 |
| 17 | **R52 dossier「~23 测试」严重失真** | GRAPH-ERR-DIAG/R52 | 迁移清单 18 用例无归属 | 实测 test_ready_queue.py 共 31 用例，约 18 个走 `_ready()`→全量版断 ReadyQueueContractError（异常类≠LIVE ValidationError），迁移方案没安排这 18 个归属 → 删 impl 即静默丢该异常类合同覆盖。 |
| 18 | **R62/R22 读侧无 DB 兜底** | EXEC-REVIEW/PLAN-IDENTITY | 读侧护栏 100% 压应用层 | v19 DB CHECK 只护写表（OperationExecutionEvents），execution_review 读路径透传灾难 + R22 收口 no_history 翻转 DB 层均不兜底——放大 LB02/LB05 注释欠补严重度，A1 注释须明写「读侧无 DB CHECK 兜底此硬钉是读路径唯一最后一道」。 |
| 19 | **R05 team 谓词 builder 耦合 include_team_context** | RESOURCE-REPO/R05 | 步3 收敛漏带布尔即 loud / 反向 import 越层 | team 谓词 `o.team_id`/`m.team_id` 别名来自 `:466 build_schedule_detail_sql(include_team_context=True)`，join 体在 schedule_detail_query.py:64-65/72-74 由 :80-87 闸控；步3 搬谓词字符串漏带该布尔 → `no such column: o.team_id`，或为产谓词反向 import builder → core.models→data 越层+导入环击穿 0 违规。 |
| 20 | **R05 normalize_schedule_resource_filter 双轨共用收口点** | RESOURCE-REPO/R05 | 裸改 collar raise 污染另两轨 | collar `:65-66 raise` 被 schedule_resource_sql_filters.py:9（超期/明细轨）+ report_context_filters.py（报表轨）共用，两轨靠「空 id→raise」挡坏查询；R05 步1「放开空 id=全量」裸改 :65-66 → 同时污染另两轨，须给派工轨单独入口。 |
| 21 | **R42 dashboard_workbench_context.py:92 漏删点** | NAV-PLANID/R42 | 同名不同文件落点经 ** 展开真实流入 | dossier 把 dashboard_workbench.py:121 判为「消失」，但 plan_id 落点迁到同名不同文件 dashboard_workbench_context.py:92，经 :119 `build_workbench_plan_context(**_context_kwargs)` 的 ** 展开真实流入被删形参；删 :191 形参后 dashboard 启动即 TypeError 500。 |
| 22 | **R22 no_history result_summary_parse_failed 取值翻转** | PLAN-IDENTITY/R22 | parity 只验键集抓不到取值翻转 | `_summary_unavailable(None,·)=(True,'排产摘要缺失')` → 收口委托 build_plan_identity 后该键 False→True，下游 reports_plan_template_fields:45/61 + 3 套手维列表渲染态翻转（无历史方案被标「摘要解析失败」）；evidence_contract:194 superset 双重逃逸，须升「键集+取值」exact。 |
| 23 | **R22 删 view_context:74 破 bad-role raise** | PLAN-IDENTITY/R22 | R21 wrapper 精度唯一上游来源 | R21 wrapper `field=="plan_role"` 重抛精度的唯一来源是 view_context:74 `normalize_plan_role(plan_role)`（在 :77-100 dict 体外），build_plan_identity 对坏 role 静默归一 adopted；R22「委托 builder 即可」删 :74 → bad role 静默吞成 adopted 伪造身份，24 键 parity 仍全绿（典型测试绿护栏破）。 |

> 共 **23 个计划外爆点**。其中 #1（collar 不产键）、#7（空值即 raise）、#19/#20（R05 双轨+builder 耦合）、#21（R42 漏删点）、#22/#23（R22 双翻）是「照 cluster/dossier 计划直接执行即炸」的硬阻断爆点，须在 Layer4 出批次前逐条闭合。
