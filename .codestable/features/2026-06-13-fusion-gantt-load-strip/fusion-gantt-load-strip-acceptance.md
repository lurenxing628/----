# fusion-gantt-load-strip 验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-06-13
> 关联方案 doc：fusion-gantt-load-strip-design.md（approved，Codex 设计两轮——首轮 3 阻塞（capacity_hours 禁直调验收守卫漏 grep/微重构改签名越界/挂载点混入内部实现）+3 建议（calendar 注入/前端导出钉死/is_internal_source 反向依赖）全修，二轮逐条闭环 **CLEAN** 且裁决「薄壳化+helper 提升单源化均在只搬不改行为边界内」；实现两轮——首轮 3 阻塞（scroll 监听容器重建失联/筛到空条带留陈旧负荷/降级码公开消息表泛化）+2 建议（checklist 后置流程说明/snapshot 锁 v3+8 字段）全修，二轮 **CLEAN**）

## 1. 五步逐项核对

- [x] **s1 微重构腾位**：gantt_service.py overdue marker 三方法保签名薄壳化（方法体搬 gantt_service_support.py 模块函数；`_overdue_batch_ids_from_history` 被测试 monkeypatch、`_log_*` 被当 callback 传出——名字全保留）；`capacity_hours_at_noon` 从 week_plan_daily_summary 私有提升为 _sched_display_utils 公共单源（原文件 import as 别名保住 #16 守卫 grep 白名单）。gantt_service.py 498→477 行；tests/gantt+schedule 零改动全绿。
- [x] **s2 后端**：gantt_resource_load.py 聚合（calendar 注入可桩测；SourceType.INTERNAL 同等判断零 report import；坏时间行跳过不登记——build_tasks 是 bad_time_row_skipped 唯一计数面，初版重复登记被 test_gantt_degradation_surface 抓出已修；复杂度门禁 C19 逼出 _accumulate_hours/_build_load_rows 拆分）；契约 resource_load 三处+CONTRACT_VERSION 2→3；新降级码 `resource_load_capacity_failed` 登记 STABLE_DEGRADATION_CODES + 公开消息表专用中文文案（实现审核阻塞 3）。
- [x] **s3 web 装饰**：scheduler_gantt_load_strip.py——severity 四档阈值 import dashboard_workbench_cards 唯一字源（文件内零 0.75/0.90 字面量，docstring 也避开）；links build_workbench_link 两条（resource_dispatch preview disabled+原因 / utilization_report 沿 detail_links 的 execution_review 同款不 disable）；幂等（severity in row 跳过）；路由 decorate_gantt_task_detail_payload 后串接。
- [x] **s4 前端**：gantt_load_strip.js 顶层 `ns.initResourceLoad`/`ns.renderLoadStrip`（buildLoadStripHtml/buildLoadPopupHtml 纯函数导出供 shim 字符串断言）；Top 5 截断+「另有 N 个资源」；unknown 显 ?；弹层过滤 allTasks 当天任务+links（disabled 不渲 a 带原因 title）；computeBaseOffset 实测 SVG 左缘对齐（量不到退化止损线）；bindScrollSync 按容器实例重绑（实现审核阻塞 1——full render 重建 .gantt-container 旧 listener 随节点销毁）；gantt_render 两个早退分支补 renderLoadStrip 清陈旧条带（阻塞 2）；CSS button.aps-load-cell 双类压 style.css button:not(.btn) 背景+hover 同组重申（#12 纪律，浏览器实测白底已修）。
- [x] **s5 实测**：浏览器 CDP——条带可见/容量来源文案/弹层任务+完整 query 链接/hour 级 dayWidth 跟随/暗色 computed rgb(6,78,59)=--ui-success-bg dark 值/缩放重建容器后滚动同步 translateX(-450px)/筛到空 hiddenWhenEmpty=true 清筛 backVisible=true；截图 /tmp/fix15-final-dark.png。

## 2. 验收场景核对

- [x] S1 聚合：同日两段 3h+2h→5.0；跨午夜 22:00→02:00 切两日各 2h；窗口前伸入只算窗口内；外协行与无 id 行不计。
- [x] S2 容量与降级：8h×0.9→7.2 正午采样断言（sampled 全 12 点）；shift_hours=0→capacity 0.0+ratio None；日历异常→capacity None+ratio None+「容量暂时算不了」中文事件恰一条。
- [x] S3 severity 边界：None→unknown/0.74→normal/0.75→warning/0.89→warning/0.90→danger/1.25→danger 锁值；阈值无第三份（grep 全仓仍仅 dashboard_workbench_cards.py，装饰层文件零字面量断言）。
- [x] S4 条带渲染：7 资源 Top 5 保序+「另有 2 个」；空数组/无几何整体隐藏；容量来源文案断言；unknown 格 ? 非 0%。
- [x] S5 弹层：当天任务过滤（6-16 任务不混入 6-15 弹层）；链接 href 来自后端（浏览器实测完整 query：version/plan_role/date/scope/machine_id）；preview disabled 不渲 a 带原因。
- [x] S6 像素对齐：x 公式断言 [[0,36],[76,36]]（day 级 2 日偏移 76px）；浏览器 baseOffset 修正后格与图区同步平移；hour 级 dayWidth 1152 跟随。**止损线未触发**（对齐达标，无需退化）。
- [x] S7 契约：snapshot 锁 contract_version==3+resource_load 顶层 key+行恰 8 字段（6 事实+severity/links）越界即炸；纯函数输出恰 6 公开字段断言。
- [x] S8 回归：tests/gantt 214（含新 13 条）+web_pages+schedule 共 1177 passed；daily gate 绿（stash 隔离并行 WIP，pop 后 AA 冲突取新版解决，误 stage 的 WIP 已 restore --staged 退回）。

## 3. 明确不做反向核对

- [x] 4.6 红线 grep 守卫：`capacity_hours(` 零直调（gantt_resource_load/gantt_service/scheduler_gantt 三文件，`capacity_hours_at_noon(` 白名单豁免）；新文件零 `from core.services.report` import。
- [x] calculations.capacity_hours 定义零 diff；algo evaluation.py 零 diff；报表 utilization 链零 diff。
- [x] 无新图表库（package 零增）；无第三份阈值常量；机器/人员容量细分明确不做（机器级日历无数据来源）。
- [x] #12/#13/#14 已落段零 diff；并行 WIP 零接触（staged 核净）。

## 4. 术语一致性

「负荷条带/资源日负荷行（6 事实字段+2 展示字段）/severity 四档（unknown 不混 notice）/容量正午采样单源/Top 5 承接老 11」design、模块注释、测试 docstring、ui-gantt.md 同口径。

## 5. 架构归并

- [x] ui-gantt.md：script 顺序协议补 gantt_load_strip.js（holidays 后 decorations 前+理由）+ 模块清单行 + 资源负荷条带段。
- [x] ARCHITECTURE.md 甘特条目补 4.6 第二落地实例句。

## 6. requirement 回写

design frontmatter `requirement` 为空；条带是甘特只读查看的资源压力可视化增强，gantt-readonly-result-view req 的「只读边界」未变（条带纯展示零写操作）。结论：**无 requirement 回写**。

## 7. roadmap 回写

- [x] items.yaml：fusion-gantt-load-strip `status: done` + feature 回填。
- [x] 主文档第 15 条标 ✅ done；解锁下游 #24 performance-budget 的一条前置（仍待 #17/#19）。
- [x] **老 roadmap aps-frontend-workbench item 11 标 dropped 指向本条**（主文档表格行+items.yaml status/description，B 案拍板兑现）。

## 8. attention.md 候选盘点

候选 1：「全局 button:not(.btn)（style.css:243）有背景+hover 刷新——甘特区新增 button 元素必须用元素+类选择器压回并 hover 同组重申，否则白底闪回」。（仅登记，落不落由用户定。）

## 9. 遗留

- 条带行数>5 的「另有 N」只给文字提示，不做展开/分页——资源筛选已是缩小范围的正路，归 #27 控件重排时再评估。
- machine 视图 label 与报表 utilization 的 display_machine 同源，但「外协 {supplier}」行在条带被资源 id 过滤天然排除——与设计「外协不占内部容量」一致，无需处理。
- heredoc 静默失败在本会话频发（bash stdin 长中文），现场已全部改走 /tmp 脚本文件或 Edit 工具；后续会话建议直接跳过 heredoc。
