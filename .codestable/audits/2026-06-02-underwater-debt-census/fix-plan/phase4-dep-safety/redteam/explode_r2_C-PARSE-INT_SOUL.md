# 逐簇爆炸对抗 r2 · C-PARSE-INT · 主透镜【灵魂线热路径+收口等价】

> skeptic 第2轮 · 只读不改 · 默认怀疑 · 2026-06-05 当前工作区 rg 回盘
> 主攻 Q4/Q5/Q6：P4改raise落热路径 / R09收编静默放宽 / R15空vs坏 / R69坏seq / 收口逐分支不等价 / 测试迁移序错复活兜底
> 成员：R01 / R04 / R09 / R28 / R59 / R08

---

## 0) 回盘实证（不信旧值，全部本轮 rg/sed 复盘）

| 锚点 | 回盘结果 | 与 dossier/cluster |
|---|---|---|
| R09 收口点 scope.py:9 `parse_positive_execution_int(value, field)->int` | `:10 isinstance bool→raise`、`:16 text=str(value or "").strip(); not isdigit→raise`、`:20 <=0 raise` | 一致。**loud raise，STRICT，一字不碰** |
| R09 A 副本 service.py:24 body 25-29 | 裸 `int(value)` + `except(TypeError,ValueError)→None` + `>0 else None` | 一致（5.9→5 / True→1） |
| R09 B 副本 viewmodel:33 body 34-38 | 与 A **字节同体** | 一致 |
| R09 C 副本 context.py:28-34 | wrap `parse_positive_execution_int` + `except ValueError→None` | 一致（5.9→None / True→None）**异构** |
| R09 B 调用 :257/:258 | `_positive_int(...) or 0` **外层兜底** | dossier 提及，下文放大 |
| F1 `reject_integer_float` 全仓 | **rg core/ web/ tests = 0 命中** | 未落地，坐实 |
| strict_parse `_parse_finite_int:46` / `:56 1e-9` / `parse_required_int:81` | 在，`:56` 容差接受 3.0→3 | 一致 |
| `parse_required_int` 调用方 | sgs_graph.py(8处)/sgs.py/sgs_scoring.py/ordering.py/auto_assign.py 热路径大量 `getattr(op,"id"/"seq",0)` | **F1 默认 True 会炸排程算法** 坐实 |
| R04 `_strict_positive_int:50` 6 调用点 :72/149/198/308/324/372，6 except 全 `(TypeError,ValueError)` :73/150/199/309/325/373 | 一致 | |
| `ValidationError(AppError(Exception))` errors.py:97/63 | **非 ValueError 子类** | 异常逃逸链坐实 |
| R59 续命测试 :247 `report_nonnegative_int("1.0")` / :250 `(1.0)` | 均 `pytest.raises(ValidationError, match="导出行数")` | 一致 |
| R08 死分支 viewmodel :227-228 / :367-368 + 常量 :25 | 在 | 一致 |
| R08 service 同源 :127≡:130 同 key `can_write_feedback` bool() | 一致；context :229/237/246 硬传 `feedback_write_enabled=True` | (T,F) 不可达坐实 |
| R28 `_safe_float:56` 旧 `except Exception→None` 已删；当前收口 `parse_finite_float(..., allow_none=True)` overload 已存在 | fixed | 2026-06-08 已落地 |
| R01 死簇 :67/:90/:91/:94/:95 + __all__:414-415；全仓消费方（排 plumbing）= **空** | 一致，零外部边 | |

---

## Q1 承重误删 / Q2 分层环 / Q3 迁移耦合（三 Q 本簇横扫）

- **Q1**：6 成员自身全 load_bearing=false。承重门来自毗邻 LB08（auto_assign 文案/正则桥）、N1（context:129-130 can_write_feedback 收敛）、F1 默认值（准承重）。无任一修法以 DRY/对齐签名名义抹承重不对称——R04 只动哨兵 B 注释、R09 把 STRICT 4 处划禁区。**无承重误删**。
- **Q2**：R09 sink 落 core/models(scope，C 已用)或 core/shared，三副本 import 方向 services/web→core 向下，0 越层 0 环。R28 services→shared 向下。R04/R59 收口零新增 import（文件已 import）。**0 违规**。
- **Q3**：本簇纯解析助手，**不耦合 schema CHECK / v18·v19 DB CHECK**（adopted-only 下沉在 plan_identity 域，非本簇）。无启动探针炸。

三 Q 全绿，下以主透镜逐成员定级。

---

## 逐成员判定（主透镜 Q4/Q5/Q6 为重）

### 🔴 R09 — 收编静默放宽（本簇最高危，红）
**判定 🔴红**（owner_pending=true，本就只标不给终态；红=「一旦按某些 hint 收口必炸」）

证据逐分支（本轮 sed 实证三副本 + scope 收口点）：
- A/B `int(5.9)=5`、`int(True)=1`；C/scope `5.9→raise→None`、`True→raise→None`。**C 与 A/B 对 float/bool 不等价**（cluster 字段7 反例，本轮 100% 复现）。

灾难链 ①（cluster hint「sink 字节对齐 A/B」路线）：
> 若 sink=A/B 式裸 int → 收口 C 时 C 的 `5.9→None` 变 `5`、`True→None` 变 `1` → **C 经 request.args/payload 的用户输入路径**（context :107 payload、:258 request.args）放宽 → `5.9` 当 op_id=5 进 `_row_matches_feedback_target`(:96/97) 行比对 → 误命中相邻行 → **现场记录静默写到错任务**，无报错。

灾难链 ②（误用 raise 版替本助手）：
> 若 A/B 错收口到 STRICT `parse_positive_execution_int`(scope:9，**不 catch**)或 R04 的 `parse_finite_int`(raise) → 遍历可信 DB 行/任务卡渲染遇任何非正/非整 → 不再「跳过坏行」而是 raise → **整页任务卡/任务列表渲染崩**。

**主透镜新放大点（本轮新发现，下文漏项详列）**：B 副本 `:257/:258 _positive_int(...) or 0`。若 A/B 收口到 scope 严格版（catch→None），`5.9` 由 `int→5`（现状）变 `None or 0 = 0` → op_id/schedule_id **从 5 变 0**（不是放宽到 5，是塌成 0）→ 0 是 scope `<=0` 的非法值，但外层 `or 0` 把它吃成 0 静默注入 task_card → 下游以 schedule_id=0 渲染/比对。**方向与灾难链①相反但同样静默坏数据**。

修正建议（前置/禁区）：
1. owner 先裁「保 C 严格 None / 还是放宽到 A/B 截断」——**这是收口前提，未裁不进批次**。
2. 收 A/B **必须分两路 parity**：`test_parity_AB`（裸 int 零漂移）+ `test_parity_C_float_bool`（钉 5.9/3.0/True 在收口前后接受性）。
3. **禁区**：scope:9 / scheduler_public_errors:167 / auto_assign:114 / operation_execution_feedback_support:161 这 **STRICT 4 处一字不碰**；R04 的 parse_finite_int(raise 契约)严禁复用。
4. 若收 A/B，须先评估 B 的 `or 0` 兜底：要么 sink 保 A/B 宽松语义（int 截断，`or 0` 行为不变），要么同步审计 `or 0` 是否该删（owner 裁）。
5. 强串行于 B01(R07 已 fixed / R08)之后 + B01 落地后**重 grep 行号再迁**（A 现 :24、B :33、C :28，B01 会位移）。

### 🟡 R04 — 异常类型逃逸 + F1 默认值（条件可做）
**判定 🟡黄**（owner_pending=false，但 3 个致命前置全满足才绿）

证据：6 except 全 `(TypeError,ValueError)`，`ValidationError` 非其子类（本轮 errors.py:97/63 实证）。`_strict_positive_int:51` 拒 float 比收口点 `:56`(接受3.0) 严。F1 全仓 0。

灾难链（异常逃逸，low 踩 P0）：
> 收口 A→委托 `parse_required_int(...,reject_integer_float=True)` 抛 ValidationError，**漏改任一 except** → 脏 op_id 由「静默 continue/跳过」变「ValidationError 一路上抛」→ 经 `count_actionable_schedule_rows:90→_iter:67→A(:72)` → 排程结果统计崩 / `has_actionable...:94` 返 bool 变抛异常 → **本应正常的排程持久化整体 abort**。

灾难链（F1 默认值，本轮坐实爆炸面）：
> `reject_integer_float` 若默认 **True** → 波及 sgs_graph.py(8处)/sgs.py/sgs_scoring.py/ordering.py/auto_assign.py 等**排程算法热路径**的 `parse_required_int(getattr(op,"id"/"seq",0))` → 这些调用方对 `3.0` 类输入由接受变 raise → **排程/配置静默回归**。

条件（全满足才转绿）：
1. **F1 必须默认 False** + 自带 parity（True→3.0 raise / False→3.0 接受）先绿。
2. **6 处 except 同 PR 加 `ValidationError`，漏一处即炸**——不可拆分提交。
3. **R01 先删 → R04 后收口**（R01 删 :67-87 含 :72，R04 收口面 6→5，须按删后新行号 rg 重定位；强行号互撞同 PR）。
4. 哨兵 B(auto_assign:114→0)/C(persistence:13→None)**仅注释禁改 raise**（错误处理路径降级是故意的，改 raise=二次异常掩盖主诊断，灵魂线红线）。
5. LB08 认账注释先落/同批（R04 在 auto_assign 只动哨兵 B 数值解析，天然不碰文案/正则桥 :126+）。

### 🟡 R59 — 裸收口撞续命测试（条件可做）
**判定 🟡黄**（与 F1 互锁）

证据：续命测试 :247 `"1.0"`、:250 `1.0` 均 raise；现私有正则 `_INT_TEXT_PATTERN:9 ^[+-]?\d+$` 拒含小数点串（天然满足）；收口点 `parse_required_int` 现接受 1.0→1。

灾难链：
> 裸收口（F1 前）→ `'1.0'`/`1.0` 由 raise 变接受 1 → 直撞 :247/:250 → **CI 显性红**（良性炸法，测试到位）。
> 更危险静默炸法：删续命测试 或 `reject_integer_float` 漏传/设 False → 导出行数字段接受 `2000.0`/`1e9` → `_export_nonnegative_int` 档位决策阈值被 float 污染 → web 导出参数静默放宽。
> 删 `_parse_plain_report_int` 漏迁 **blank 短路**（:62-63 `return blank_default`）→ blank 由 0 变 `parse_required_int` raise → 导出空值场景从容错降级变报错中断。

条件：F1 先落 → 收口委托 `reject_integer_float=True, min_value=0` + **保留 blank 短路** + parity 钉 :247/:250 维持 + 对照 `parse_report_int("2000.0")` 接受（禁顺手统一兄弟 field）。F1 前只能停「注释+parity 临时态」。

### 🟢 R28 — P4 静默吞错改 raise（2026-06-08 已 fixed）
**判定 🟢绿**（完全独立叶子，不依赖 F1，已闭合）

证据：当前 `_safe_float:56-57` 已保名薄包装到 `parse_finite_float(value, field="ext_days", allow_none=True)`；收口 `parse_finite_float`(overload 已存在)对垃圾/NaN/inf/bool 全 raise=P4 正方向；上游 batch_operation:92/part_operation:75 已 `parse_optional_float` 严校 → 爆炸半径极小。

灾难链（仅在收口用错时）：
> `allow_none=False` → None ext_days 直接 raise → **炸所有 ext_days 为空的正常批次**（ext_days 合法可空）。必须 `allow_none=True`。
> 越界把消费点 `setup/unit_hours = float(... or 0.0)`(:170-171/:70-71)一并统一 → 「未填工时」由默认 0 变建批次失败 → **静默炸建批次/复制工序主流程**。禁动。

已闭合条件：`allow_none=True` 已落；`pytest -k test_no_new_local_parse_helpers` 已定夺 fitness 白名单 :77 保留；setup/unit_hours 兜底未碰。

### 🟢 R01 — 纯删死簇（安全）
**判定 🟢绿**

证据：全仓消费方（排 plumbing）= **空**；闭合自环 `has→count→_iter`；零生产边。删 :67-87/:90-91/:94-95 + __all__:414-415 + run import :16-17 + scheduler :3/:5 + SP05 :54-55 + 孤儿 `Iterator`(typing:5)。所有误删以 ImportError/SyntaxError/SP05 红响亮暴露，**无静默业务损坏路径**。
前置：R01 先 / R04 后同 PR（行号互撞）；删函数+删 SP05 断言同提交（中间态会红）；严守只删 run import :16-17（误删 :13-15 ValidatedSchedulePayload 等=生产 ImportError，唯一真爆点）。

### 🟢 R08 — 死分支删除（安全，但 owner_pending）
**判定 🟢绿**（owner 裁「是否预埋总开关」前只标不删）

证据：(T,F) 不可达（service :127≡:130 同源 + context 硬传 True + _empty(F,F)），死分支 :227-228/:367-368 恒不命中；`build_execution_payload:373 guardrail_text = "" if can_write else disabled_reason` 二次短路 = 双层护城河；零测试 PIN 死文案。
前置/禁区：**保留 `feedback_write_enabled` 参数**（活路径 :234 仍消费，连参删→「填写实际」按钮门禁塌缩静默放开误填，最大爆点）；先钉 service :127≡:130 同源守卫（把 (T,F) 不可达从偶然变契约）；N1 注释先落；等本文件在途 task_key 重构 diff 落定再动（否则行号再漂）。owner 裁预埋问题前不进批次。

---

## 漏项（本轮新发现 / 计划未充分覆盖）

1. **【新放大点】R09 B 副本 `:257/:258 _positive_int(...) or 0` 与收口语义交叉**：cluster 字段7 只讲「C 放宽」，未点出 **B 的 `or 0` 外层兜底**。若 A/B 收口到 scope 严格版，`5.9` 由 `int→5` 变 `None or 0 = 0`，op_id/schedule_id 塌成 0 静默注入 task_card（与 C 放宽方向相反的另一条坏数据流）。前置须补：收 B 时同步审计 `or 0` 是否随 sink 语义变更（owner 裁 sink 取严格还是宽松后才定 `or 0` 去留）。**计划缺此前置**。
2. **R09 sink 落点二义**：cluster 说 sink 落 core/models(scope) 或 core/shared 二选一未定，但 scope:9 是 STRICT raise 契约、C 已 wrap+catch；若 owner 选「保 C 严格」则 A/B 应收口到「wrap scope + catch」的新 Optional sink（**非裸 scope，非 parse_finite_int**），cluster 未明确这条第三选项。漏前置：sink 必须是「catch→None 的 Optional 封装」，直接指 scope:9 会把 A/B 变 raise（炸渲染）。
3. **R04 F1 默认值守卫缺测试锚**：F1 默认 False 的 parity 必须显式覆盖 sgs_graph/ordering 这些 `getattr(op,"id",0)` 调用方对 `3.0` 仍接受——cluster 只说「默认 False」未要求把这些热路径调用方纳入 F1 parity 断言。漏：F1 parity 应直接断言一条 sgs_graph 风格调用 `3.0` 不 raise。
4. **R08 在途 diff 门**：本文件当前工作区 task_key/state_key 重构未提交，R08 死分支绝对行号已漂（dossier 字段1 +1~+6）。计划须显式列「F-worktree-settle」前置，否则照 cluster 静态行号删会撞在途 diff。
