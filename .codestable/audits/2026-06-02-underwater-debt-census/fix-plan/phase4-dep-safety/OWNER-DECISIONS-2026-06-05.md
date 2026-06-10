# 80 条水下债 · owner 裁决记录（2026-06-05）

> 对 `PHASE4-SAFE-BATCH-PLAN.md` §3 owner 裁断汇总表（O01–O38）的**最终裁定**。
> owner: lurenxing，2026-06-05 逐条拍板（共 38 个闸门，R52 子门 O08 因 O07 选"留"自动消解）。
> 裁定后这些单元方可锁 patch、进执行批次（ROOT→A→B→C→D）；裁前一律 STOP。

---

## 一、坏数据取向（拦 / 放）—— 全部选"拦 / 严格"

| 闸门 | 债 | 裁定 | 落地要点 |
|---|---|---|---|
| O01 | R09 | **严格拒掉**（5.9→非法丢弃，防脏 op_id 冒充） | 收编只动 Optional A/B 两份（viewmodel:33 + service:24）→ scope.py:9；STRICT 4 处一字不碰；分两路 parity 防静默放宽 5.9→5 |
| O03 | R15 | **报错拦住** | ⚠执行层留一手：合法空时间仍 `if not text: return None` 安静返回，只炸真坏值（防误炸合法空，RK07） |
| O24 | R69 | **报错抛出** | 上游已近清洗、误伤极低；loud 只动 except 域，合法路径不卷入（RK13） |
| O27 | R32 | **硬报错拦住** | 校验不过不让升正式备份，纠正"校验不过照升"倒挂 |

## 二、最危险的 R54（5 套 guard 面收口，P0）

| 闸门 | 裁定 |
|---|---|
| O11 collar 取数 | **上游传进来**（plan_resolution 入参，方案 I） |
| O12 与 R42 删形参 | **绑同一次提交**（E03 硬序，防撞行号） |
| O13 缺字段默认 | **fail-CLOSED 默认拦** |

> 三基数 16/15/12 分组各钉 parity，**禁向 16 键看齐**（RK10）。ROOT 必须先扩 collar 产 3 键，否则 delegate=抹键 fail-OPEN 脏写不可逆（RK01）。

## 三、资源筛选 R05

| 闸门 | 裁定 |
|---|---|
| O16 空班组（空字符串） | **看全部（全量）** |
| O15 collar 形态 | 接口带 `include_team_context` 信号 + 派工轨单独入口；禁裸改 :65-66 raise；硬序 步1扩collar→步2落5条parity→步3搬谓词（RK05） |

## 四、删 / 留（需项目记忆）

| 闸门 | 债 | 裁定 |
|---|---|---|
| O06 | R13 死字段 | **先迁 3 测试后删**，删前 owner 再确认一次 |
| O07 | R52 旧全量算法 | **留着当差分校验尺子**（方向 B + "我是故意的"注释）→ **O08 子门自动消解** |
| O09 | R55 关键链子集冒充整版 | **本轮先不动**（等怀疑者过三问 + 前置 R11/R63 合并）；None 回退是有意降级，禁删 |
| O20 | R29 转发壳 number_utils | **留着 + 注释**（KEEP，不阻塞，与 [[phase4-debt-safe-batch-plan-2026-06]] 一致） |

## 五、流程 / 已修偏离认账

| 闸门 | 债 | 裁定 | 落地 |
|---|---|---|---|
| O29 | R43 9 个旧路由 wrapper | **认账提前删** | 改 `p1-scheduler-debt-cleanup-roadmap.md:522`"先保留"→"已批准收口" + 删 9 门牌 + 迁 **22** 测试（registry 低估为 15）+ 清 SP05 三表 + 同步清 `scheduler_config.py:94-98` 软 fallback |
| O30 | R56 复盘护栏修偏 | **认账接受** | 结构重定位更硬 + 契约锁死、未 fail-open；确认 4 改动文件同提交入账 |
| O31 | R07 错误类 | **统一成 AppError/NOT_FOUND** | 补 `AppError, ErrorCode` import + 补 schedule=None→raise 回归测试 |
| O17 | R71 配置 3 对双份函数 | **只加对账锁（parity），不物理合并** | 前置必做：先落 LB07 承重注释 + helper parity；与 R47 同节奏 |

## 六、用户可见

| 闸门 | 债 | 裁定 | 落地 |
|---|---|---|---|
| O14 | R22 no_history | **接受新 True（显示提示）** | ⚠**前端文案要重写成中性措辞**（如"本方案暂无排产摘要"，禁用"解析失败/缺失"吓用户）；先 Batch-1 parity（24 键 exact）再收口；保留 gantt_plan_query wrapper loud 文案；R21 不得先删 wrapper |
| O26 | R41 6 处中文标签 | **C 全收口（6 族尽量全换标准版）** | 见下方配套裁定 |

R41（O26）配套裁定：
- **ready 空值 → 未齐套**（绝不让未齐套冒充齐套放行；收口点打补丁强制，因标准版默认"齐套"，RK20）
- **operator inactive → 保留"停用/休假"**（打补丁，标准版只给"停用"）
- **source → 顺手修"外协误判自制"bug**
- priority / day_type 空值 → 接受从"-"变"普通"/"工作日"
- **batch_status → 无收口点，保留私有**（禁新建 batch_status_label = 新 P5）
- 测试改 **loud 暴露**，禁删重钉静默；前置 LB04 承重注释 + 安全网先落

## 七、真取舍 3 个

| 闸门 | 债 | 裁定 |
|---|---|---|
| O23 | R24 死副本诊断契约 | **保留 + 注释 + 事实记录** → `.codestable/compound/2026-06-05-decision-r24-diagnostic-contract-keep.md`。绝不删、绝不反向让活路径改指它（会丢护栏踩 P4） |
| O25 | R03 失败态管道 | **保留 + 注释**（failed 半边不可达但 missing 半边生产可达 + 涉落库枚举契约；只给"failed 不可达"补可观测注释，不动枚举）；承重三禁区行 :28/:216/:217 仅补注释 |
| O28 | R40 库存静默兜底 | **删兜底自然报错（方向 A）**：删 :70-72、保留 :69 float 让其自然抛 ValueError + "我是故意的"注释 + 补 repo 层 raise 回归测试；不引 core（避 data→core 耦合） |

## 八、工程铁律（全照推荐）

| 闸门 | 裁定 |
|---|---|
| O02 R09 第3副本(persistence_errors:13) | 不收编，归 R04 禁区 + 注释（收编会违 R04 灵魂线二次抛错） |
| O04 R19 指纹排序 | 保留私有版 + "顺序无关"注释（避越层/环） |
| O05 R15/R19/R13 | 同批改（串行序见 O37） |
| O10 R34 | 纯删（repoint 目标旧锚 service:210 存在；R23 落后现盘为 service:206，执行按符号重 rg） |
| O18 R67 | 前两处必收，第 4 处(superset)保现状（③④全收或全不收） |
| O19 R72 | web/core 各落各点 + 补 request import |
| O21 R14 | :328 钉 resolve_existing_plan 层、**禁平移**（防灵魂线被 fallback 吞，RK14） |
| O22 R14 | :358 可平移 |
| O36 R58 | 本轮只注释（Phase2 改单键须补两反例 parity，排 R54 后） |
| O37 EXEC-FACT | 确认串行序 **R15→R19→R13** |
| O38 GF1 | **合规**（加 kwarg 默认 False 非新建模块；落 strict_parse.py:81 parse_required_int） |

## 九、认账注释文案纪律（执行时严守，非选择题）

- **O32 LB03/LB06**：注释落 `reports_execution_review_context` + `reports_request_support`（**非** reports_page_support）；**严防粘 §90 LB-B4 反向 fail-OPEN 文案**（现盘是 fail-CLOSED）。
- **O33 N1**（can_write_feedback 失忆债）：钉真闸 `feedback_service:369-382`，禁引幻觉 :89/:70-84。
- **O34 N2**（_event_id_for_revision return 0 sentinel）：补注释 + 绑"非末位缺 id 必抛错"契约，**禁删** `if index<total: raise`。
- **O35 LB08**：按实证改写 `internal_operation.py:119/148/150/152/154`，禁贴 planned 草稿指 auto_assign（消费方）。
- **通用方向硬门**：触碰 `navigation_context:79` / LB06 双宿主时，**先核现盘 fail-CLOSED 方向再下笔**（§3.2，写反 = 承重击穿按 P0，RK02）。

---

## 下一步

以上裁定单元现可锁 patch、按 **ROOT→Batch-A→B→C→D** 序列进执行。全程铁律：承重护栏只"补注释/绑契约"，6 承重文件禁区行按符号定位、删后 grep 复核活近亲；无新增 import、0 分层违规、灵魂线 raise 全程不削弱。

top 5 必盯爆点（全 P0）：RK01（R54 collar 扩产）/ RK02（注释方向）/ RK03（STRICT 误删）/ RK04（R42 :92 漏删）/ RK05（R05 硬序）。
