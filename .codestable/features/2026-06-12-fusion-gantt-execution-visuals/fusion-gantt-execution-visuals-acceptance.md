# fusion-gantt-execution-visuals 验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-06-13
> 关联方案 doc：fusion-gantt-execution-visuals-design.md（approved，Codex 设计两轮——首轮 2 阻塞（罩层 hover/active 闪回紫、overdue 优先级靠顺序不稳+dark 覆盖）+4 建议全修，复审逐条闭环 PASS-WITH-SUGGESTIONS 且两新建议（CSS 契约锁值/frappe hover 改 fill 既有边界标注）已采纳；实现两轮——首轮零阻塞 3 建议（图例注释言过其实/无事实回归证明力/dark 契约锁值）全修，复审逐条闭环 PASS-WITH-SUGGESTIONS，末条注释精度建议（digest 重建措辞）已采纳）

## 1. 接口契约核对

- [x] payload 增量与 design 2.1 示例一致：completed→`progress 100`+`execution-completed`；processing/paused/exception→`progress 0`+各自类；无事实→与现状逐字节一致（冻结期望值断言 custom_class=="priority-normal"）。
- [x] **实现期结构调整（复杂度门禁逼出）**：design 预计在 `_build_one_task` 就地加逻辑，实跑 daily gate 圈复杂度 C(15) 红线报 20（原 19+新分支）——抽 `_execution_visuals(fact, *, has_record) -> (css, progress)` 纯函数，语义与 design 决策 1/2 完全等价（has_record 门槛短路/四态白名单/completed 两态）。已纳入 Codex 实现审核范围，零阻塞。
- [x] meta 键集零新增（断言钉死）；raw 状态码不进 meta（`actual_status` not in meta），只在服务端拼 class 消费一次。

## 2. 行为与决策核对

- [x] 决策 1：progress 两态——`has_execution_record` 复用 `_execution_detail_meta` 布尔（不二次复制判断），completed 直读 `fact.actual_status == EXECUTION_STATUS_COMPLETED`；4.10 红线无 quantity_done（grep 零出现）。
- [x] 决策 2：四态白名单 `_EXECUTION_CSS_STATUSES` frozenset（注释写明为何不用 STATUS_LABELS 全集）；not_started 假记录/未知码零类断言。
- [x] 决策 3（CSS 写法钉死非顺序）：completed 罩层普通/:hover/.active 三态选择器一组（特异性 (0,5,0) > frappe hover/active (0,4,0)）`fill: var(--ui-success); fill-opacity: 0.45`；三描边 `:not(.overdue)` 守卫（overdue 并存时 execution 规则不命中→纯红边 2.5）；dark 块重申四规则（dark 基础 (0,4,1) 会盖 (0,4,0)；dark overdue 用 var(--ui-danger) 避免新增裸 hex——hex 冻结 115 门禁绿）。
- [x] 决策 4：侧栏补 优先级/加工方式/时长 三行（publicPriorityLabel/publicSourceLabel 现成 helper + formatDurationMinutes 展示格式化——0/负/NaN→"-"）；popup 补「现场：actual_summary_label」行（escapeHtml 包裹）。
- [x] 决策 5：legend 标记行四执行状态样例（uiColor 从 getComputedStyle 取 --ui-* 当时值；注释如实说明「主题切换不主动刷图例是既有行为，下次图例重建（digest 变化）时刷新」——审核确认与 common_theme.js 实际行为一致）。
- [x] 决策 6 测试：后端 payload 断言 6 条 + CSS 写法契约 3 条（正则锁选择器+token 值+opacity 值）+ JS contract 扩展（fixture 补三键、断言补侧栏三行 popup 现场行）。
- [x] 挂载点 grep：execution- 类源头唯一（_execution_visuals）；拔除沙盘=回退 4 文件改动段+删测试 → payload/DOM/图例回现状零悬挂。

## 3. 验收场景核对

- [x] S1 completed：progress 100+绿罩层——CDP 实测 computed style `fill rgb(22,163,74) fill-opacity 0.45`（即 --ui-success）。
- [x] S2 三描边：亮色实测 rgb(37,99,235)/rgb(217,119,6)/rgb(220,38,38)（--ui-primary/--ui-warning/--ui-danger）；overdue 并存（B5 种子超期+exception）红边胜出由 `:not(.overdue)` 选择器语义+CSS 契约断言保证。
- [x] S3 无事实（含 preview 身份语义）：payload 逐字节回归断言+冻结期望值。
- [x] S4 not_started 假记录/未知码：零类零 progress 防御断言。
- [x] S5 侧栏三行+popup 现场行：JS contract 断言（急件/自制/2 小时 30 分钟/现场：暂未记录现场实际）+CDP 截图目检（侧栏可见 优先级 普通/加工方式 自制/时长 4 小时/现场状态 已完工）。
- [x] S6 legend 四样例：CDP 实测图例文案「已完工(绿罩)/生产中(蓝边)/已暂停(琥珀边)/异常中(红边)」双主题齐全。
- [x] S7 hex 冻结门禁绿（aps_gantt.css 115 上限未动）；tests/gantt/ 全量 184 passed；daily gate 绿（复杂度修复后重跑）。
- [x] S8 双主题目检：dark 主题描边 computed style 实测生效（dark 重申规则压回成功）；罩层双主题可读。

明确不做反向核对：
- [x] resource_dispatch_rows.py / gantt_color.js / gantt_service.py / execution_fact_provider.py 零 diff（git diff HEAD 核空，Codex 复核同结论）。
- [x] statusKeyForTask/「按工序状态」配色零接触（计划态语义归 #27）；popup「状态」行语义未动。
- [x] 无 quantity_done；meta 无新增内部字段；并行 WIP 零接触（staged 核对）。

## 4. 术语一致性

「执行着色类（四态白名单）/完工罩层（三态接管）/双向互缺（收口方向明确）」design、代码注释、CSS 注释、测试 docstring 同口径；「无事实=计划行原样」不变量措辞与 4.10/req 文档一致。

## 5. 架构归并

- [x] ARCHITECTURE.md 甘特任务详情区条目追加执行可视化段（progress 两态红线/白名单门槛/视觉通道分离/CSS 写法守卫）。
- [x] ui-gantt.md 只读边界节补 progress 服务端两态与 CSS 协议指针。

## 6. requirement 回写

`shop-floor-execution-feedback.md`（current）**已 update**：用户故事追加「甘特图一眼看出完工/生产中/异常」、变更日志追加 2026-06-13 条目、last_reviewed 同步。

## 7. roadmap 回写

- [x] items.yaml：fusion-gantt-execution-visuals `status: done` + feature 回填。
- [x] 主文档第 12 条标 ✅ done；**解锁 #13 chain-walk / #14 fix-pack / #15 load-strip / #27 controls-rework 甘特链四条**。

## 8. attention.md 候选盘点

候选 1：「frappe-gantt.css 对 .bar/.bar-progress 有 hover/active 高特异性规则——任何接管条形视觉的 CSS 必须普通/:hover/.active 三态一组写齐，且 dark 块基础 stroke 规则 (0,4,1) 会盖 (0,4,0)，dark 下要重申」。（仅登记，落不落由用户定。）

## 9. 遗留

- 「按工序状态」配色（计划态）与现场执行态两套语义并存——归 #27 controls-rework 拍板。
- frappe hover/active 改主条 .bar fill 的既有边界（「fill 归配色模式」悬停瞬间不完全成立）——非本次引入，归 #14/#27。
- gantt_color.js/aps_gantt.css 存量 hex 迁 token 归 #6 hex-migration。
