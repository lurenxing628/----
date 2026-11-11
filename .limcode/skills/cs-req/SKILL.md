---
name: cs-req
description: 在用户授权范围内起草或更新能力需求文档，区分未来愿景、当前能力和过时记录。复用已有场景与决定，不把每个功能自动扩成需求文档流程。
---

# 能力需求文档

启动、授权与续作遵守根目录 `AGENTS.md`；读取或复用 `.codestable/attention.md`。路径、状态与收尾按需查 `.codestable/reference/shared-conventions.md`。

requirements 说明一个能力解决什么问题、为什么需要、边界在哪；实现结构属于 architecture，执行计划属于 roadmap。

## 模式与状态

- **draft**：用户已明确的未来能力，状态 `draft`；可以独立于排期和实现存在。
- **backfill**：依据已运行代码和可追溯场景补档，状态 `current`。
- **update**：按实际能力变化更新已有文档；移除或不再维护的能力标 `outdated`，保留历史。
- 完整功能验收真正通过且已授权回写时，draft → current；保留原始愿景并用变更日志记录实现变化。

纯内部重构、技术债和工具维护未增加用户能力时，不强制创建 requirement。用户要求批量整理时按独立能力分组完成，不强制一次一份。

## 操作

1. 从用户要求和已有记录确定目标、模式和范围；只有影响能力含义的缺项才澄清。
2. 先读 `requirements/VISION.md` 索引，检索相关 req 判断重复和互引；按需读相关架构、feature、roadmap 和有效决定，不全量读取其他 req。
3. draft 只依据用户已说明的需求及可追溯场景；backfill/update 还要核实实际实现与边界，不编造用户故事或假装功能已存在。
4. 按同目录 `reference.md` 起草或更新。正文简述用户故事、痛点、解法和边界，不搬入函数、算法等实现细节。需要语气示例时再读项目 `requirement-example.md`。
5. 自查来源、状态、能力边界和重复内容。已授权且事实明确的修订直接完成；存在实质需求取舍或用户要求先审稿时，交付完整草稿等待决定。
6. 写入 `requirements/{slug}.md`，保留现有 slug；按 status 分组同步 `VISION.md` 的简短 pitch 和状态。结构性变更及 draft → current 添加变更日志。

保留 `doc_type: requirement`、`slug`、`pitch`、`status`、`last_reviewed`、`implemented_by`、`tags`。pitch 是帮助读者理解的一句话，不要求写成宣传口号。

## 完成标准

已授权文档及索引已更新，状态与事实一致，愿景历史没有被覆盖；缺少事实明确标注。只问需求现状时直接只读回答，不自动归档。发现无关架构或代码问题只报告，不擅自扩大范围。
