# C-PARSE-INT 逐簇爆炸对抗 r1（SOUL 透镜：灵魂线热路径 + 收口等价）

> skeptic r1，只读不改，默认怀疑。行号 2026-06-05 rg 回盘。
> 主透镜 Q4/Q5/Q6：P4 改 raise 落热路径、R09 收编静默放宽、收口逐分支等价、测试迁移序。
> 成员债：R01 / R04 / R09 / R28 / R59 / R08。

---

## 判定速览

| 债 | 判定 | 一句话 |
|---|---|---|
| R09 | 🔴 红 | A/B 裸收口到 scope.parse_positive_execution_int 把 float/bool 由「截断/1」静默放宽路径反向——实为「收紧」，但若 owner 选「保 A/B 宽松」改 sink 则连锁污染 C 路收口语义；双 owner_pending 未裁前任何收编都炸语义对账 |
| R04 | 🔴 红 | F1 默认值 + 6 处 except 异常逃逸双重热路径：F1 默认 True 炸 sgs_graph 8 处 op.id 解析；ValidationError 非 ValueError 子类，漏改任一 except → 脏 op_id 由静默 skip 变整链 raise |
| R59 | 🟡 黄 | 裸收口(F1 前)撞续命测试 :247/:250（CI 显性红，非静默）；F1 后收口须保 blank 短路 + 错误文案漂移（友好串→strict 串，match 仍过）须 owner 认账 |
| R08 | 🟡 黄 | 死分支删除安全（(T,F) 三路不可达 + guardrail 双层短路），但 owner_pending 未裁「总开关预埋」+ 误删 feedback_write_enabled 参数 → :234 按钮门禁塌缩静默放开误填 |
| R28 | 🟢 绿 | 静默吞错→loud raise 正方向；上游 batch_operation/part_operation:92/75 已 parse_optional_float 严校，except 分支不可达，allow_none=True 承接空值，零生产行为变化 |
| R01 | 🟢 绿 | 纯删死码，0 生产消费、闭合自环，误删只以 ImportError/SyntaxError/SP05 红响亮暴露，无静默业务损坏路径 |

---

## 🔴 R09 — 收编静默放宽 + 双 owner_pending（最危）

**灾难链（Q5 收口等价反例，实证）**：scope.py:9 `parse_positive_execution_int`：:10 `isinstance bool→raise`、:16 `text.isdigit()→raise`、:11 `<=0 raise`。C 路 context.py:30 委托它 + :31 `except ValueError→None`，故 C：`5.9→None`、`3.0→None`、`True→None`（严格）。A 副本 service.py:24-29 / B 副本 viewmodel:33-38 是裸 `int(value)` + `except(TypeError,ValueError)→None` + `>0 else None`，故 A/B：`5.9→5`、`3.0→3`、`True→1`（宽松）。**A/B 与 C 对 float/bool 不逐分支等价**。
→ 改 X：把 A/B 收口到 scope（与 C 同 sink）→ A/B 对 `5.9` 由「截断 5 参与行比对」变「None 跳过」=**收紧**（安全方向）；但簇文件/Layer2 残留表给的 sink hint 是「字节对齐 A/B 的 int()」→ 若 owner 裁「保 A/B 宽松」会去改 sink 或新建宽松 sink → 静默 → C 路若也并到该宽松 sink，C 的 `5.9→None` 变 `5` → `_row_matches_feedback_target`(context:96/97/271/272) 用 op_id=5 误命中相邻行 → 现场记录写到错任务（静默错配，无报错）流到 Y=DB 现场记录。
→ 第二条链（误用禁区符号）：误把 R04 的 parse_finite_int（raise 契约）或 STRICT 变体替本助手 → 遍历 DB 行/任务卡渲染遇非正值不再跳过而 raise → 整页任务卡/任务列表渲染崩。
**修正建议**：(前置) owner 先裁两要点——①sink 落点 ②A/B/C 取严格(C)还是宽松(A/B)语义；裁前 R09 不进批次、只标 owner_pending。(顺序) 强串行于 R07(已 fixed,service.py)/R08(B01) 之后，B01 落定后重 rg 回盘 A:24/B:33 再迁（删行会位移）。(parity) 收口前必写两路 parity：test_AB(对 int/str/blank/垃圾) + test_C_float_bool(专钉 5.9/3.0/True 收口前后是否变)。(禁区) STRICT 4 处一字不碰：operation_execution_feedback_support.py:161(field 参 raise)、scheduler_public_errors.py:167、scope.py:9、operation_execution_event_repo.py:100。

## 🔴 R04 — F1 默认值 + 异常逃逸双热路径

**灾难链 1（Q4 F1 默认值落热路径）**：F1 = 给 strict_parse.py:46 `_parse_finite_int` 加 `reject_integer_float`，经 :81/:36 `parse_required_int` 透传。回盘 `parse_required_int` 被 core/algorithms 大量调用：sgs_graph.py 8 处（:13/:28/:155-157/:169/:175 `parse_required_int(op.id/seq, ...)`）、ordering.py:117-118、auto_assign.py:395、sgs.py:143-144、sgs_scoring.py:224-225。
→ 改 X：F1 默认 True → 所有 `parse_required_int(getattr(op,"id",0))` 调用方：op.id 若为 SQLite/ORM 取出的 `3.0` float 由「接受→3」变「raise ValidationError」→ 静默 → SGS 图构建/排序热路径在排程中段抛错 → 整次排程崩（配置/排程回归）流到 Y=调度主流程。**F1 必须默认 False**，自带 parity（True→3.0 raise / False→3.0 接受）先绿。
**灾难链 2（Q5 + 异常逃逸）**：ValidationError 是 AppError(Exception)(errors.py:63/97)，**非 ValueError 子类**。strict_parse 抛 ValidationError；R04 主符号 A schedule_payload_contract.py:50 的 6 处 except 全是 `(TypeError,ValueError)`(:73/:150/:199/:309/:325/:373 逐行回盘确认)。
→ 改 X：收口 A 委托 parse_required_int(抛 ValidationError) 而漏改任一 except → 脏 op_id 由「静默 skip/字段化错误」变「ValidationError 一路上抛」→ 经 count_actionable_schedule_rows:90→_iter:67→A → 原本「脏行不计数」变「排程统计崩 / 本应正常的持久化整体 abort」=low 踩 P0。
**修正建议**：(前置) F1 默认 False + parity 先绿。(同 PR 不可拆) 6 处 except 同步加 ValidationError，与 A 收口同一提交。(同批) 与 R01 同 PR（R01 先删 :67-87 含 :72 调用点 → A 收口面 6→5，R04 按删后新行号重 rg）。(禁区) 哨兵 B auto_assign:114(→0)、C schedule_persistence_errors:13(→None) **只补注释绝不改 raise**——二者在错误处理路径，改 raise = 二次异常掩盖主诊断（灵魂线红线）；LB08 文案/正则桥(:126+ AUTO_ASSIGN_RESOURCE_ERROR_PREFIXES)一行不碰。

## 🟡 R59 — 续命测试 + 文案漂移

裸收口(F1 前)：`parse_required_int('1.0'/1.0)` 接受→1（strict_parse:56 `1e-9` 容差），撞续命测试 regression_web_silent_fallback_contract.py:247/250 `pytest.raises(ValidationError, match="导出行数")`——**CI 显性红，非静默，良性炸法**。故 F1 是硬前置互锁。F1 后 `reject_integer_float=True` 兑现 raise。
**条件/认账点**：①删 `_parse_plain_report_int`(:54-70)/`_INT_TEXT_PATTERN`(:9) 时必须迁出 blank 短路（:63 `return int(blank_default)`，现状 blank→0；strict_parse 对 blank `raise`），漏迁 → 导出空值场景由「降级 0」变「报错」炸 web 导出。②错误文案漂移：现状 :89 抛 `f"{label}不是有效整数，请检查{source_label}。"`；委托 strict_parse 后抛 `f"“{field}”必须是整数"`。包装 reports_export_support.py:45 传 `field=label="导出行数"` → strict 文案含「导出行数」→ `match="导出行数"` 仍过 ✓，但**面向用户文案变了**（可观测行为差异），owner 须认账或在委托外层 try/except 转回友好串。(禁区) 禁动兄弟 parse_report_int(:36，别 field 语义，接受 '2000.0' 有意)、禁动 `__all__`。

## 🟡 R08 — 死分支删除（owner 待裁）

(T,F) 不可达三路并集确认：service:127≡:130 同 key 同 bool() 恒等、反馈卡路径硬传 True、_empty_context(F,F)。额外双层护城河：build_execution_payload `guardrail_text: "" if can_write else disabled_reason`，can_write=True 时恒空。死分支①viewmodel:227-228、②:367-368 恒不命中，删安全。
**条件**：①owner_pending 未裁「feedback_write_enabled 是否未来『现场记录保护总开关』预埋」——若是预埋则转「补注释 + 钉 :127≡:130 守卫」而非删。②**禁误删 feedback_write_enabled 参数**：它仍被活路径 :234 `fill_enabled = bool(can_write and feedback_write_enabled and ...)` + :238/:256/:277 消费 → 连参数删 → 按钮门禁塌成只看 can_write → 已完工状态亮按钮 → 静默放开误填实际记录（最大爆炸）。③候选 A 只删 :25 常量 + :227-228 + :367-368。(前置) 先在测试钉 service:127≡:130 同源不变式，把 (T,F) 不可达从偶然变契约；等本文件在途 task_key 重构 diff 落定后再动(行号在漂)；R08(B01) 先于 R09(B05) 串行。

## 🟢 R28 — 静默吞错收口（安全）

batch_service.py:55-64 `_safe_float`：`try float(value) except Exception: return None` 静默吞。收口到已存在 parse_finite_float(垃圾/NaN/inf/bool→raise)=P4 正方向。上游 batch_operation.py:92 / part_operation.py:75 `ext_days=parse_optional_float(..., field="ext_days")` 已严校 → 流入 `_safe_float` 恒为 None 或合法 float，except 分支不可达=冗余防御，收口后生产零行为变化。allow_none=True 承接 Optional 空值（非兜底）。(纪律,非红) 必须 allow_none=True（用 False 炸所有 ext_days 空批次）；禁越界动消费点 `setup/unit_hours=float(...or 0.0)` 工时兜底；同步退/留 fitness 白名单 test_architecture_fitness.py:77（先跑 `pytest -k allowlist` 定夺）。完全独立叶子，不阻塞。

## 🟢 R01 — 死码直删（安全）

schedule_payload_contract.py 死簇 :67-87(_iter)/:90-91(count)/:94-95(has) 闭合自环，0 外部入边（callgraph 实证），__all__:414-415 + 两层 re-export + SP05:54-55 plumbing。删后 typing:5 `Iterator` 成孤儿须同删。所有误删以 ImportError(误删 :13-15 ValidatedSchedulePayload)/SyntaxError/SP05 红响亮暴露，**无静默业务损坏路径**。(顺序) R01 先删（缩 R04 收口面 :72）→ R04 后收口，同 PR 原子（强行号互撞）。

---

## 漏项（本轮新发现，计划未覆盖）

1. **【归类矛盾，需 owner 仲裁】Layer2 残留表 §R09 收编面把 `auto_assign_resource_errors.py:114 _positive_int` 列入「STRICT 4 处(`->int`,loud raise,一字不碰)」——实测错**。该函数真身 :115 `int(value or 0)` / :117 `except Exception: return 0` / :119 `>0 else 0`=**→0 宽松哨兵**，不 raise。它正是 R04 dossier 的「哨兵 B」。真正 STRICT raise 是 operation_execution_feedback_support.py:161(`(value,field)` + raise) 与 scheduler_public_errors.py:167。两份分析对同一符号给了矛盾依据（R04=宽松补注释 / R09 残留表=STRICT 禁碰），**最终纪律一致（都别动它的 raise/别误删）所以结论不炸，但归类依据打架**——执行者若信 R09 残留表会误以为 :114 是 loud raise 写入闸，影响 R04 对它的「→0 哨兵补注释」修法判断。建议回写残留表：STRICT 4 处应为 scope:9 / feedback_support:161 / scheduler_public_errors:167 / event_repo:100，剔除 auto_assign:114。
2. **【R59 文案漂移未登记】** dossier 字段4 委派方案让 strict ValidationError 直透或外层 try/except 转友好串，二者面向用户文案不同（`"“导出行数”必须是整数"` vs `"导出行数不是有效整数，请检查报表导出数据。"`），match 子串虽过但属可观测行为变化，owner 须认账走哪条——计划只标了「续命测试绿」未标文案对账。
3. **【R28 fitness 白名单去留未定】** 方案 b(保名薄壳)收口后 fitness 探测器按 name(:64 LOCAL_PARSE_HELPER_NAMES)还是按体判定决定 :77 白名单退/留，dossier 自陈待定——这是「测试绿但守卫语义」开放项，须动手前 `pytest -k allowlist` 实测，否则漏退/漏留任一向都 CI 红（loud，非静默，非阻塞但须前置）。
