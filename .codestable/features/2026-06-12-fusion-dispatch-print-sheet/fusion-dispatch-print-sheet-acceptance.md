# fusion-dispatch-print-sheet 验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-06-12
> 关联方案 doc：fusion-dispatch-print-sheet-design.md（approved，Codex 设计两轮——首轮 3 阻塞（registrar 登记/警示判定口径/重名供应商错并组）+4 建议全修，复审逐条闭环 PASS-WITH-SUGGESTIONS 且两新建议（thead 跨页身份/非法格式测试）已采纳；实现两轮——首轮 1 阻塞（段内时间序）+2 建议（sp05 真实文件清单/无历史空态测试）全修，复审逐条闭环 PASS-WITH-SUGGESTIONS，末条表述建议直接落进本报告措辞）

## 1. 接口契约核对

- [x] `build_week_plan_print_sheets(rows, *, group_by, day=None) -> List[Dict]` 与 design 2.1 一致：输出 `[{"resource_label", "rows"}]`，行恰七键（drop「现场状态」）。
- [x] 段内行排序：`_sheet_row_sort_key`（日期→时段→批次号，「全天」归一空串排当日最前）——上游周计划排序键无时段（日期→设备→人员→批次→工序），重分组后必须补排（Codex 实现审核阻塞，已修并复审闭环）。精确语义：同日期同时段不同批次按批次号重排；完全同键行保留上游次序（sorted 稳定性）。
- [x] 路由 `GET /scheduler/week-plan/print` 落新文件（scheduler_week_plan.py 483/500 零业务加码，仅 import+print_url 传参）；registrar `_ROUTE_MODULES` + sp05 门禁双清单（`_ROUTE_MODULES` 写死集合 + `SCHEDULER_REAL_ROUTE_FILES`）三处同步登记。

## 2. 行为与决策核对

- [x] 决策 1：独立路由不进 TARGET_PAGE_PATHS（web/viewmodels/ 零 diff）；入口沿 export 先例 url_for，batch_id/resource_type/resource_id 筛选全量透传（页面契约断言 href 五参数）。
- [x] 决策 2：双视图兜底段均排最后——machine 视图全部「外协 {supplier}」+「外协/未分配」行统一归兜底段（重名供应商不错并组，行内「设备」列保留各自串），operator 视图收未派人行。
- [x] 决策 3：七键 drop 现场状态（builder 键集断言）+ 模板行尾空白「备注」列；不设签字栏。
- [x] 决策 4：group_by 非法 / day 格式非法（abc、2026-99-99）/ day 出周 → ValidationError 400 明示；显式不存在版本继承 get_week_plan_rows 的 404 语义（与周计划页一致）；空行集页内空态两分支（无历史「无法生成派工单」/有历史「没有排程记录」）+ 返回链接，不 404 不空白纸。
- [x] 决策 5：模板独立不 extends base.html，显式链 00-tokens.css + print.css(media=print)，表格边框/列宽/页眉排版页内自足；打印态 page-break-after: always 每资源段一页。
- [x] 决策 6：警示判定 `is_current_executable_official_version` 为假即印——三态单测钉死（当前正式零警示/历史正式「已被新版本替代」/其余「非正式方案」）；段页眉放 `<thead>`（跨物理纸每页重复——PDF 目检证实兜底段 26 行跨 2 纸页眉两页都在）；生成时间 format_public_datetime 公开口径。
- [x] 决策 7：测试 8+8=16 条不进 GUARD_TESTS。
- [x] 挂载点 grep：week_plan_print_sheet/scheduler_week_plan_print 消费方唯一；拔除沙盘=删 3 新文件+回退 registrar/sp05/入口/print_url 四处+删测试 → 零悬挂。

## 3. 验收场景核对

- [x] S1 machine 视图：M1/M2 各成段、段内日期+时段序、每行带人员列；外协行（含重名供应商 S1/S2 同名「华东外协」种子）统一入兜底段排最后（PDF 目检页 3-4 证实）。
- [x] S2 operator 视图：未派人工序入「外协/未分配」兜底段固定最后；每行带设备列（截图证实）。
- [x] S3 一资源一页：print-sheet 段容器 page-break；本周无任务资源零出现（day=2026-06-02 时 M1 不出纸断言）。
- [x] S4 页眉：版本/方案身份/生成时间/周范围/数据范围/资源名随段重复在 thead 内；警示三态单测（路由 helper 直测）。
- [x] S5 单日切换：day 过滤+页眉「（单日）」；四类参数错误 400 明示断言。
- [x] S6 备注空白列存在；打印页 HTML「现场状态」零出现（断言钉死 4.11）。
- [x] S7 入口链接五参数透传断言；S7b 打印目检：CDP printToPDF 三态 PDF（machine 4 页/operator/day）——A4 landscape、表格边框、列宽、备注列可手写、页眉每物理纸重复、anchor-baseline 第三节 5 条（侧栏隐藏/A4 landscape/分页保护/sticky 还原/链接黑色）全过。
- [x] S8 回归：周计划全量 344 passed；daily gate 绿（修复后重跑）。

明确不做反向核对：
- [x] gantt_week_plan.py / _sched_display_utils.py / scheduler_workbench_link_query.py 零 diff（git diff HEAD 核空）。
- [x] 新文件 ExecutionFact 零 import（grep 计 0）；全仓 window.print 仅打印模板一处（注释+按钮）。
- [x] 内部字段（op_id/schedule_id）打印模板零出现；零写入路由（仅 GET）；并行 WIP 文件零接触（staged 核对）。

## 4. 术语一致性

「派工单页（≠资源派工页）/资源段（一资源一页）/兜底段（双视图语义各自明确）/单日切换（不静默回落整周）」design、builder docstring、路由 docstring、模板注释、测试 docstring 同口径。

## 5. 架构归并

- [x] ARCHITECTURE.md 周计划条目追加派工单打印段（独立打印路由/重分组纯函数/兜底段防错并组/警示三态进纸面/4.11 纸面零现场事实/全仓首个 window.print）。

## 6. requirement 回写

design frontmatter `requirement` 为空；roadmap 第 31 条即需求载体（2026-06-11 用户拍板）。打印是周计划数据的纸面形态，不涉新用户能力语义。结论：**无独立 requirement 回写**。

## 7. roadmap 回写

- [x] items.yaml：fusion-dispatch-print-sheet `status: done` + feature 回填。
- [x] 主文档第 31 条标 ✅ done；无下游解锁（无条目依赖本条）。

## 8. attention.md 候选盘点

候选 1：「消费重分组的上游行时别假设上游排序键覆盖你的展示维度——周计划排序键是日期→设备→人员→批次→工序（无时段），任何按资源重分组的消费方都要自带段内时间排序」。（仅登记，落不落由用户定。）

## 9. 遗留

- 外协行若业务方将来要求按供应商各自成段分页，需先给 Suppliers.name 加唯一约束或把 supplier_id 带进段行旁路（涉及 #16 段行契约变更）——design 2.5 已列超范围观察，单独立条。
- Codex 沙箱只读跑不动 pytest（git 写 /tmp 都被拦）——两轮实现审核均为源码核对+本地实跑互补，后续审核 prompt 已默认注明不跑测试。
- 资源排班页落地后补打印页导航链接（roadmap 注明非依赖）。
