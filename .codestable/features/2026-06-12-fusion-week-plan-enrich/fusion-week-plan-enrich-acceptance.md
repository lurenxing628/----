# fusion-week-plan-enrich 验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-06-12
> 关联方案 doc：fusion-week-plan-enrich-design.md（approved，Codex 设计两轮——决策 3 归属与数据流两阻塞收口后 PASS；实现两轮——第一轮 BLOCK（1 阻塞+2 建议），修复后第二轮逐条判定【已闭环】零源码新阻塞；其总判定 BLOCK 仅因 Codex 只读沙箱跑不动 pytest——`.venv/bin/pytest` shebang 残留搬家前 Documents 旧路径+无可写临时目录，验证由本地实跑 312 passed + daily gate 补足）

## 1. 接口契约核对

- [x] `build_week_plan_rows(*, rows, wr, execution_facts_by_op_id=None) -> Tuple[BuildOutcome[List[Dict]], Dict[str, int]]` 与 design 2.1 双返回签名一致；minutes_by_date 旁路、段行零内部键。
- [x] `build_week_plan_daily_summary(minutes_by_date, *, calendar, week_start, week_end) -> List[Dict]` 新文件 78 行，唯一归属路由层（calendar 取 `g.services.calendar_service`），gantt_service 零 calendar 接触。
- [x] gantt_service 接线 ~4 行（facts 取数+解包+data `daily_planned_minutes` 键），498/500 红线达标。
- [x] **实现期结构调整（已核偏差→当场处理）**：design 2.1 预计空周升级落 `scheduler_week_plan.py`，实现中该文件触 534 行超 500 红线——拆出纯装配模块 `scheduler_week_plan_preview.py`（`week_plan_span_jump` + `build_week_plan_preview_state`，76 行，无路由）。拆分已纳入 Codex 实现审核范围，零阻塞。

## 2. 行为与决策核对

- [x] 决策 1 注入点：`_split_by_day` 拆分前按 `row["op_id"]` 取状态（拆分后段行丢 op_id——roadmap 核证硬约束）；facts=None →「-」、无 fact →「待开工」（EXECUTION_STATUS_NOT_STARTED 与甘特详情缺省一致）、跨日段行同状态。词表 `operation_execution_labels.STATUS_LABELS` 单源。
- [x] 决策 2 事实读取复用 `self._execution_facts_by_op_id(rows, plan_resolution)` 现成链路（甘特页同款，失败语义继承）。
- [x] 决策 3（4.6 协议）：正午采样 `policy_for_datetime(datetime.combine(day, time(12,0)))` 的 shift_hours×efficiency；休息日容量 0；**禁直调 capacity_hours**——grep 守卫测试钉死四个链路文件；容量来源明示文案+「利用率暂时算不了」诚实降级。
- [x] 决策 4 空周升级：`plan_role_resolution` 真实方案身份透传（selected_role/scenario_id——Codex 实现审核阻塞「读错键误当 adopted」已修并复审闭环）；无计划行零跳转；span 异常 per-call 宽 catch+logger.warning 留痕回落。坏时间过滤态清空跳转链接（复审建议 1 已采纳）。
- [x] 决策 5 Excel：headers 第 8 列「现场状态」、text_cols+列宽同步；**导出不含合计行**（断言钉死「容量」零出现）。
- [x] 决策 6 模板：列 th/td、汇总条（仅有数据日渲染）、空周跳转链接形态同 history 先例。
- [x] **不修项及理由**：复审建议「宽 catch 会吞 try 块编程错误」不修——design 决策 4 已裁决该口径（升级是锦上添花，读取失败不能反把页面搞挂；logger.warning 留痕不静默），且 `get_plan_time_span_dates` 契约固定返回 start/end_date 无缺键路径；Codex 自注「没有把它判成当前阻塞」。
- [x] 挂载点 grep 反向核对：两新模块（week_plan_daily_summary/scheduler_week_plan_preview）唯一消费方均为 scheduler_week_plan.py；拔除沙盘=删 2 新文件+回退 5 文件改动即完全退出，零悬挂引用。

## 3. 验收场景核对

- [x] S1 有事实工序中文标签+跨日两段同状态（单测 test_fact_status_label/test_cross_day_segments）。
- [x] S2 无事实「待开工」/facts=None「-」（单测两态区分）。
- [x] S3 每日合计聚合（540min→9 小时）+正午采样跨午夜钉死（_CalendarStub 断言 sampled==[datetime(2026,6,1,12,0)]）。
- [x] S4 休息日容量 0→「利用率暂时算不了」+来源明示文案页面渲染断言。
- [x] S5 空周三态：有计划行→区间文案+跳转链接（URL 带 week_start 与方案身份——非 adopted/scenario 透传 5 条补强单测）；无计划行→现有文案零跳转；span 异常→回落 {}（Flask app context 单测）。
- [x] S6 Excel 第 8 列与页面同值（openpyxl 断言 headers 八列+「待开工」单元格）；导出无合计行。
- [x] S7 段行恰好八个中文键零内部键（键集断言）；daily_planned_minutes 日聚合字典（{"2026-06-01": 540, "2026-06-02": 120} 跨午夜归属断言）。
- [x] S8 回归：route_view 全目录+页面+observability 312 passed；test_scheduler_result_navigation_contract 解包同步；daily gate 绿（1705+220 impact+5 focused，并行 WIP stash 隔离后跑、跑完即恢复）。
- [x] 浏览器目检：有数据周（列+汇总条）与空周（升级文案+跳转）两态已核（实现阶段 CDP 截图）。

明确不做反向核对：
- [x] `_split_by_day`/`fmt_day_segment` 零 diff（git diff grep 计 0）；`_sched_display_utils` 未触碰。
- [x] calculations.capacity_hours 零新调用（grep 钉死+守卫测试常驻）。
- [x] resource_dispatch/gantt 事实消费零 diff（git diff --name-only 核空）。
- [x] 无新表、无新算法（模块 W 纪律——只消费现成服务/字段）。

## 4. 术语一致性

「现场状态列（状态属于工序不属于日段）/每日合计行（4.6 单资源简化口径必须明示）/空周升级（锦上添花不变新故障点）」在 design、模块 docstring、测试 docstring、模板注释同口径；「待开工=没有事实，不是数据缺口」措辞与甘特详情区/req 文档一致。

## 5. 架构归并

- [x] `.codestable/architecture/ARCHITECTURE.md` 新增「周计划页增强」条目（甘特任务详情区条目之后）：注入点约束、双返回旁路、4.6 首落地（正午采样/禁 capacity_hours/明示文案/诚实降级）、空周升级方案身份透传、Excel 同列无合计行。
- [x] design 第 4 节预告的归并点全部落账；ui-gantt.md 无需更新（周计划非甘特渲染链）。

## 6. requirement 回写

`shop-floor-execution-feedback.md`（current）**已 update**：用户故事追加「周计划页直接看到现场状态」、怎么解决追加周计划消费段（词表同源/待开工语义/仍只读）、变更日志追加 2026-06-12 条目、last_reviewed 同步。本 feature 的每日合计/空周升级属页面工程增强，不单独立 req。

## 7. roadmap 回写

- [x] items.yaml：fusion-week-plan-enrich `status: done` + feature 字段回填。
- [x] 主文档第 16 条标 ✅ done（日期/feature/审核轮次）；解锁第 31 条（fusion-dispatch-print-sheet 唯一依赖本条）。

## 8. attention.md 候选盘点

候选 1：「服务层 data dict 的方案身份键名是 `plan_role_resolution`（attach_plan_metadata 写入），不是 `plan_resolution`——下游读错键会静默把非正式方案/模拟预览当 adopted。新增消费点先 grep 键名真源，别按直觉拼」。（仅登记，落不落由用户定。）

## 9. 遗留

- `.venv/bin/pytest` 入口脚本 shebang 仍指搬家前 `/Users/lurenxing/Documents/...` 旧路径（本地用 `.venv/bin/python -m pytest` 不受影响；Codex 复审验证因此受阻）——属环境债非本 feature 范围，建议择机重建 venv 或改 shebang。
- 每日合计是「单资源容量」简化口径（4.6 明示）；按设备/人员细分容量归后续（#15 负荷条带不在本条）。
- 周派工单打印（#31）依赖本条的周选择器/空周提示，已解锁待排。
