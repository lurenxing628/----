---
name: cs-feat-ff
description: feature 流程的超轻量通道——不写 design / checklist 直接动手，但先指引 AI 查 CodeStable 知识库再开工。触发：用户说"快速模式"、"fastforward"、"别那么多步骤"、"直接开干"，且需求小到不值得走 design 流程。
---

# cs-feat-ff

## 启动必读

在项目内执行本技能时，按需读取 `.codestable/attention.md`；本轮已读且未变化则复用，内容丢失或文件变化时重读。它补充而不替代适用的 `AGENTS.md`。文件或目录缺失时说明限制，不自动初始化，也不阻止只读调查或已授权的小范围工作。只有用户选择完整 CodeStable 流程时，才补齐该流程实际需要的材料。

用户让你做小功能时本来 AI 就会直接动手——这个技能**不改变这件事**。它只做一件事：动手前把项目里已沉淀的 CodeStable 知识指给你，按需搜一下，写出来的代码就比裸写多一层保护；动手后回写一份**最简的 `{slug}-ff-note.md`** 让这次工作可追溯、可被 cs-arch / cs-req backfill 看到、能纳入 scoped-commit 提交。

很轻：没有 design doc / checklist / 验收清单 / 动手前的用户确认。看完指引，该读代码读、该写代码写、写完回写一段话。

---

## 动手前先扫一眼 .codestable/

Glob `.codestable/` 发现可用目录和文档，按需取用：

- **`architecture/`** — ARCHITECTURE.md 总入口 + 子系统 doc。改跨模块的东西前看一眼避免违反边界
- **`compound/`** — learning / trick / decision / explore 四类沉淀：
  ```bash
  python .codestable/tools/search-yaml.py --dir .codestable/compound --filter doc_type=learning --query "关键词"
  python .codestable/tools/search-yaml.py --dir .codestable/compound --filter doc_type=decision --query "关键词"
  python .codestable/tools/search-yaml.py --dir .codestable/compound --filter doc_type=trick --query "关键词"
  ```
- **`requirements/`** — 有相关 req 时读边界
- **`features/`** — 有同类 feature 时参考其 design
- **`reference/`** — shared-conventions.md / tools.md

---

## 怎么用

动手前问 2 个问题：

1. **这块代码以前有人栽过跟头吗？** → 搜 `compound/` 的 learning
2. **这块代码有没有已经拍板的写法约束？** → 搜 `compound/` 的 decision + 看 `architecture/` 相关子系统

命中就把结论融进实现（**按约束来写**，不是抄）。没命中按自己判断写很正常。搜不到换几个关键词再试。

---

## 写代码时守住这几条

design / implement 的硬约束在 fastforward 的精简版。没 design doc 不代表可以不讲——这些是让你"直接动手"时不偏向 AI 默认会踩的坑。

### 先想"放在哪儿"再写

30 秒回答：**这次要加的东西在项目结构里属于哪儿？**

- 现有模块本该承担？→ 在那扩展，别另起
- 横跨多个模块？→ 抽公共层 / 让某一方主导
- 已有模块叫法不同？→ grep 同义词
- 跟现有都不像？→ 多半该切回完整 design 流程

默认坑：**不思考就往眼前最顺手的文件里加**——加完就成"什么都装的筐"。

### 扫一眼要改的文件现在什么状况

开写前看一眼：文件多长？承担几件事？类有多少方法？新加的是自然扩展还是把它推向"什么都能干"？

已有职责内直接扩展。局部且必要的内部调整可一起验证；独立重构、职责重划或模块拆合先说明影响并确认，不因文件长就自动重构。

### 默认写最少的代码

只写用户明确要的。不顺手加：

- "以后可能要"的配置项 / 参数开关 / 抽象层 / 接口 / 工厂
- 没人要的防御性兜底 / try-catch
- 与任务无关、无证据支持的假想边界处理；影响本次正确性、错误反馈和数据安全的边界仍必须处理

判据：写完觉得"是不是还得加点 X"——X 是不是用户能感知到的？不是就别加。多出来的代码不是中性的，是后人维护的负担。

### 只动该动的

只改要改的函数。同文件里别的函数丑 / 命名怪——**除非和这次冲突，否则别碰**。新代码风格匹配当前文件已有写法。看到值得改的别处 → "顺手发现：{文件:行号} {问题}，不在本次范围"让用户决定。

### 按现有职责决定位置

已有模块的自然扩展就近修改；只有独立职责、真实复用或项目边界需要时才新建文件，不为新增几行逻辑固定拆文件。

### 不打补丁分支

必要的输入校验、错误处理和边界分支应正常实现并验证。警惕无依据的兼容猜测、吞错或改变业务规则的特例；先核实根因，涉及范围或约定变化再确认，不因出现条件分支就停止。

### 用结构信号检查风险

- 往 > 300 行文件追加 / 往 > 10 个方法的类加方法
- 函数做的事越来越多超过一屏
- 写第二段"跟上面那段基本一样改了两个变量"的代码
- 函数参数加到第 4 个
- 往 `utils.ts` / `helpers.ts` 万能 util 堆东西
- 新起概念名时先 grep 同名 / 近义命名

这些数字是观察提示，不是强制拆分阈值；是否调整按职责与本次影响判断。完整清单看 `.codestable/reference/shared-conventions.md` 第 7 节。

---

## 写完回写 `{slug}-ff-note.md`

代码写完并完成适用验证后再记录，不为等待一句重复确认而阻断收尾。需要用户现场验收的部分明确标为待确认。未采用 CodeStable 的项目可在最终答复中记录，不自动初始化。

### 自动生成 slug

不问用户。规则：

- 从用户最初的请求里抽 2-4 个英文 kebab-case 词概括动作 / 对象（如 "rename-cwd-helper"、"add-export-button"、"fix-toolbar-layout"）
- 不抽业务名词缩写、不音译中文、保持小写连字符
- 拿不准就保守一点："tweak-{对象}" / "small-{动作}" 也比强求精准好

最终路径：`.codestable/features/YYYY-MM-DD-{slug}/{slug}-ff-note.md`，日期用今天。

### 模板

```markdown
---
doc_type: feature-ff-note
feature: {slug}
date: YYYY-MM-DD
requirement: {req-slug 或留空}
tags: [...]
---

## 做了什么
{1-3 句：解决什么需求 / 加了什么能力，业务视角}

## 改了哪些
- {file:行号区间或函数名} — {一句话说改了什么}
- ...

## 怎么验证的
{1-2 句：跑了哪些验证 / 浏览器走通了哪条路径 / 跑了什么测试}

## 顺手发现（可选，不阻塞）
- {文件:行号} {问题简述} — 不在本次范围
```

**写得真的轻**：每节就那么几行，不要把它写成迷你 design / 迷你 acceptance。这份文档的目标是"半年后有人看 git log 能跳进来 30 秒搞清楚做了啥"，不是替代标准流程。

落盘后告诉用户："已写 `{slug}-ff-note.md`，本次 fastforward 闭环。"

---

## 不做什么

- **不写 design doc / checklist / acceptance**——这就是 fastforward 的意义。要写就去 `cs-feat-design`
- **不跟用户确认方案**——用户让你做小功能就是不想等你开会
- **不在 `.codestable/` 里留 `{slug}-ff-note.md` 之外的新文件**——除非发现值得沉淀的坑 / 技巧，另起对话用 `cs-learn` / `cs-trick` 写

---

## 什么时候跳出 fastforward

干到一半发现下面任一情况，**停下来告诉用户"这比想象的复杂，建议切回完整流程"**：

- 改动涉及 3 个以上子系统
- 需要引入新术语或和现有术语冲突
- 要动 `.codestable/architecture/` 既定的模块边界
- 用户追加的要求让范围翻倍

切回方式：触发 `cs-feat-design`。已写的代码在 design 里标"已部分实现"即可。

---

## 退出条件

- [ ] 代码和适用验证完成，待用户现场验收的部分明确列出
- [ ] 已按现有项目约定记录本次工作，未采用该流程时在最终答复中给出记录
- [ ] 没有未对齐的"顺手发现"（都进 ff-note 末节，留给后续）

---

## 收尾提交

按 `.codestable/reference/shared-conventions.md` 第 4 节"scoped-commit"规则执行。本通道：

- **提交范围**：本次代码改动 + `{slug}-ff-note.md`
- ff-note 落盘后告诉用户"已就绪，是否代为 commit？"，用户明确同意才执行

确有必要时合并提出一次后续建议，不逐项追问；未授权的归档与提交不执行：

1. 暴露的坑 → "沉淀 learning？（`cs-learn`）"
2. 拍板的长期约束 → "归档决定？（`cs-decide`）"
3. 最后问是否代为 scoped-commit

---

## 容易踩的坑

- 完全跳过知识检索就写——这个技能的唯一理由就是让你搜一下再写
- 把搜到的 learning / decision 当"参考"而不是"约束"——decision 拍过板，违反要么重新 decision 要么别做
- 开始写 design doc——fastforward 就是不写 design
- 发现任务变复杂还硬在 fastforward 推——切回成本远低于带着错误方案改到底
- **动手前就建 ff-note 空壳**——破坏 fastforward 的轻体感，必须代码 + 验证完才回写
- **把 ff-note 写成迷你 design / 迷你 acceptance**——四节加一起十几行就够，多了说明这事不该走 fastforward
- **跳过 ff-note 直接 commit**——和 issue-ff 强制 fix-note 同样的理由：没记录后人追溯不了
