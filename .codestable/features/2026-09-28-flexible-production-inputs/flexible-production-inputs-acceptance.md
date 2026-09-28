---
doc_type: feature-acceptance
feature: flexible-production-inputs
status: passed-related-scope
date: 2026-09-28
---

# 相关范围验收

三项用户批准的能力及后续页面/默认时间要求已完成。用户明确不跑全门禁，本记录只证明相关测试、相关类型/静态检查及实际浏览器验证；不声明完整仓库通过或clean-worktree proof。

## 功能证据

- 工序用料与分次到料：真实baseline及graph候选中前序先排、后序等料；整批模式全部等待；缺料不偷偷拆数量；数量变化需重新核对。合并外协段按最后成员用料日期整段等待，实际计算起止一致。
- 拆分：HTTP只读预览100/40/60；取消不变；确认保持需求、已有到料及逐次到料总量，准确绑定子批工序；同request_key重放不多建；到料并发变化使预览失效；分配完成后注入故障仍整体回滚。
- 策略：候选捕获、采用及正式计划→试调保留所选策略；采用重新核对材料日期及资源/日历约束。日期到来时齐套显示和筛选只读更新。
- 设备与工种：同一设备车/铣两个能力分别选择具有对应技能的人员；设备ID仍共用。双归属页面保存、多选设备能力、可读文件维护及已有工序确认保留均验证。
- 工作日历：默认08:30–11:50、13:30–17:30（7小时20分），页面可修改并持久化；逐日覆盖及清除恢复默认，多工作时段文件往返；跨午休不误报容量不足、裁剪视窗不误报开工越界。

## 已执行证据

证据目录：`evidence/flexible-production-20260928/`。下面各批次有重叠，不相加充当独立测试总数。

| 范围 | 实际结果 | 日志 |
|---|---|---|
| 物料/拆分/排产/采用/试调/工种/日历/旧库迁移相关回归 | 267 passed | regressions-267.log |
| 拆分、分阶段计算、路由与模板契约 | 88 passed | delivery-contracts-88.log |
| 分阶段材料（含合并外协等待、日期只读投影） | 6 passed | merged-stage-materials-6.log |
| 工艺确认、表描述和采用基线完整性相关 | 137 passed | policy-and-descriptors-137.log |
| 路由、Schema导出/契约和旧迁移相关 | 64 passed | schema-contracts-64.log |
| 原排产页真实Chrome109范围/检查流程 | 1 passed | preflight-browser.log |
| 默认时间、覆盖清除、双归属、多能力、用料、拆分、重检真实页面 | 1 test / 7 flows passed | flexible-browser.log、flexible-production-browser.json |
| 目标产品文件Pyright | 0 errors | pyright.log |
| 本轮Python文件Ruff、产品复杂度≤15 | passed | ruff.log、complexity.log |

浏览器使用临时隔离SQLite与实际宿主。`server-final.json`确认服务停止、运行锁释放、零隔离违规；没有使用生产DB。已看截图`quantity-split-preview.png`、`default-work-periods.png`、`material-stage-and-arrivals.png`，复用现有样式与自定义时间/选择控件，未增加CSS。构建ID：`75bfb859d7a3a22ee487360997f63a125a8067317a460b7deafe53ebdc74ffde`。

另已核对schema.sql与v36迁移链一致、模板说明与表描述一致、git diff无空白错误。此前相关大批次的有效结果保留但不计入此表；曾失败的旧默认/迁移断言已由上述后续相关回归覆盖。

## 交付范围

2026-09-28 后续复核补充：上面的首轮相关测试未覆盖后来确认的 8 处边界/衔接问题。用户授权后已逐项修复，并补验证候选先试调再采用、分件阶段放行、真实 DATE 连接拆分和班次切换保存；当前结果、构建 ID 与本轮限定范围见 [修复记录](../../issues/2026-09-28-flexible-production-repair/flexible-production-repair-fix-note.md)。上表保留为首轮历史证据，不替代后续修复验证。

代码、静态离线产物、迁移、相关测试、用户手册及需求/系统速查表已同步。未提交、未推送、未发布；工作区原有未提交内容保留，不能称为干净工作区。数量拆分按件数同比，固定整批耗用需先人工核对；不自动扣减库存、不自动更换工序归属、不强拆受保护批次。
