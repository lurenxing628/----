# fusion-label-single-source 验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-06-12
> 关联方案 doc：fusion-label-single-source-design.md（approved，Codex 设计两轮 BLOCK→PASS + 实现一轮零阻塞 PASS-WITH-SUGGESTIONS，建议全采纳）
> 实现提交：feat(词表) 主体 + 强化(词表守卫) 建议四条

## 1. 接口契约核对

- [x] 真源公开接口与 design 2.1 一致：`result_status_display_labels()`（5 键展示字典）/`resolve_result_status()`（别名归一），已进 `__all__`。
- [x] 模板消费形态唯一化：`it.result_status_label`/`it.strategy_label` 行级标签；version_option_label 宏吃 decorated 字段。
- [x] 实现期零偏差（design 两轮审核已把 reports 第二裸点/dataclass to_dict/strategy 两层对账提前钉死，实现照做）。

## 2. 行为与决策核对

- [x] 决策 1 真源口径 C：别名表只剩 ok/fail；simulated 复合标签保留（test_scheduler_week_plan_summary_observability「模拟排产 / 有问题，需检查」断言绿）。
- [x] 决策 2 行级收编：12 个 `{% set %}` 全删（grep 零命中，analysis.html 后端注入豁免仍在）；不注入全局词表。
- [x] 决策 3 两裸点：dashboard `.to_dict()` 后 decorate（SimpleNamespace 桩同步改贴真实契约）；reports index versions 过 decorate；latest_history_time_display 路径不动（test_dashboard_schedule_time_display 绿）。
- [x] 决策 4 ok2 全删：别名表/analysis_overview/guardrail/9 模板/2 夹具；残值走 unknown（夹具断言「有问题，需检查」）；真源注释留证。
- [x] 决策 5 派生：两文件无手写 status 字典（守卫断言）；未知态统一（future_status→「有问题，需检查」直锁测试）。
- [x] 决策 6 身份证：registry 2 条（result_status 别名政策+ok2 死键留证；strategy allowed/display_compat 两层）+ 概念卡 2 md + check 对账段实跑 ✅ + 快照 2 json（.venv-semantic 15 passed）。
- [x] 决策 7 守卫 4 断言先红后绿（回贴 set 块即红）；双登记 manifest 自洽 26 绿；{%- trim 形态兼容（Codex 建议）。
- [x] 决策 8 v2_strategy_zh docstring 已更新（收编完成口径）。
- [x] 挂载点 6 项全落地；拔除沙盘：还原 9 模板 set 块 + 还原 3 viewmodel + 删守卫/登记/身份证即完全退出。

## 3. 验收场景核对

- [x] S1 grep 零命中 + 渲染输出一致（真渲染抽查中文标签全对）。
- [x] S2 dashboard 卡与 reports 首页行标签正常；时间格式不回归（15 条 dashboard 系测试绿）。
- [x] S3 ok2 零现身（守卫扫 templates+web；注释豁免逻辑保留真源考古留证）。
- [x] S4 未知态全链路「有问题，需检查」（直锁测试 + week_plan observability 复合标签断言）。
- [x] S5 真源派生断言绿；analysis 页渲染零变化（255 条 analysis 系回归绿）。
- [x] S6 守卫先红后绿；双登记自洽。
- [x] S7 语义守卫双命令：主 .venv check_concept_registry ✅；.venv-semantic 15 passed（快照基线 APS_UPDATE_SEMANTIC_SNAPSHOTS=1 建立后断言模式复跑绿）。
- [x] S8 真渲染五类页：dashboard 别名归一（manual/ok→手动排产/成功）、reports//gantt/week-plan/resource-dispatch 全 200 零残留。
- [x] S9 daily gate passed（并行 WIP stash 隔离；过程中抓出 reports_page_support 501 行超门禁——删注释压回 500，门禁本身工作正常）。

## 4. 术语一致性

- 「词表/行级标签/输入别名/死键」四术语 design、真源注释、守卫 docstring、概念卡同口径。

## 5. 架构归并

- [x] ARCHITECTURE.md 补「排产词表唯一字源」条目（见归并提交）。
- [x] 概念身份证落档 .codestable/semantics/（registry 即决策载体，无需另立 ADR）。

## 6. requirement 回写

design frontmatter `requirement` 为空；工程收敛（模块 C 语义单源）非新增用户能力。结论：**无 requirement 回写**。

## 7. roadmap 回写

- [x] items.yaml：fusion-label-single-source `status: done`。
- [x] 主文档第 8 条标 ✅ done。
- [x] 解锁：fusion-plan-context-capsule（第 9 条）就绪。

## 8. attention.md 候选盘点

候选 1：「测试桩要贴真实服务契约（SimpleNamespace 桩掩盖了 query service 返回 dataclass 的事实，路由加 to_dict 后桩先炸）——改桩为真实模型对象而非放宽路由」。
（仅登记，落不落由用户定。）

## 9. 遗留

- strategy 7 键瘦身（improve/greedy 防御键）归 cs-refactor，需老库考古——身份证 forbidden_meanings 已先钉住语义。
- analysis_labels 其余三子表（mode/dispatch_mode/dispatch_rule）单消费方维持现状；第二消费方出现时走 decorate 模式。
- analysis.html 的后端注入形态（status_zh = analysis_labels.get）保留——其数据已 decorate，兜底「结果状态未知」不可达；若未来清理归 plan-context-capsule 顺手。
