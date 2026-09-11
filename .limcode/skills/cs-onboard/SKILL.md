---
name: cs-onboard
description: 把新仓库或有零散文档的仓库接入 CodeStable 体系，两条路径自动判断：空仓库从零搭骨架，已有文档走审计 + 迁移映射。触发：用户说"在这个项目里用 CodeStable"、"搭 CodeStable 结构"、"初始化 CodeStable"、"迁移到 CodeStable"。
---

# cs-onboard

把仓库**接入 CodeStable 工作流体系**——白纸或已有零散文档的都行。本技能只做两件事：**搭骨架**、**归旧档**。骨架搭好后子工作流（feature / issue / compound 等）即可直接运行。

---

## 两条路径

| 路径 | 适用 | 产出 |
|---|---|---|
| **空仓库** | 仓库内无 spec 类文档，也没有 `.codestable/` | 完整骨架 + 必要骨架文件 |
| **迁移** | 仓库内有零散文档 / `docs/` / 部分 `.codestable/` 结构 | 审计报告 + 迁移映射方案（用户逐条确认）+ 落盘 |

启动后**先扫一次自动判断**，不要让用户选——TA 大概率不知道项目里现有哪些文档。扫描结果模糊（如只有 README）就明说判断依据并问用户。

---

## 标准骨架（目标状态）

> 项目里的 `.codestable/reference/shared-conventions.md` 是该项目的现行约定。技能包只提供初始化模板，不能自动覆盖项目定制。下面列出可创建或检查的骨架。

```
.codestable/
├── attention.md                CodeStable 技能启动必读的项目注意事项
├── requirements/               需求聚合根（空目录 .gitkeep）
├── architecture/
│   └── ARCHITECTURE.md         架构总入口（首次创建为占位模板）
├── roadmap/                    规划层聚合根
├── features/                   feature 聚合根
├── issues/                     issue 聚合根
├── refactors/                  refactor 聚合根
├── audits/                     主动审计发现清单
├── brainstorms/                开放 brainstorm 创意空间
├── compound/                   沉淀类统一目录（learning / trick / decision / explore）
├── tools/                      跨工作流共享脚本（onboard 释放）
│   ├── search-yaml.py
│   └── validate-yaml.py
└── reference/                  跨子技能共享参考（onboard 释放）
    ├── system-overview.md
    ├── shared-conventions.md
    ├── tools.md
    ├── code-dimensions.md
    ├── requirement-example.md
    └── maintainer-notes.md
```


---

## 启动检查

**先检查一次现状**：

1. **检查 `.codestable/`**：不存在 → 空仓库候选；存在但不完整 → 迁移（部分补齐）
2. **旧版目录升级**：如果 `.codestable/` 不存在但发现历史旧目录（例如早期名称目录），先按实际检测到的目录提示用户，不要把旧目录名当成当前推荐路径：

   > 检测到旧版 `{旧目录}/`。建议把它重命名为 `.codestable/`，结构 / frontmatter 完全兼容，rename 后即用。要我执行吗？

   同意 → 对用户确认的那个实际旧目录执行一次 rename 到 `.codestable/`，按迁移路径走（这时只需补齐可能缺失的 `attention.md`、`tools/` 和 `reference/`）。如果发现多个候选旧目录，先停下让用户选哪个才是当前版本，不自动合并。想保留旧目录 → 告诉他子技能只读 `.codestable/`，旧目录不会被读；按空仓库路径走新骨架

3. **Glob 全仓库 `.md`**（排除 `node_modules/` `.git/`）：根目录 `DESIGN.md` / `ARCHITECTURE.md` / `SPEC.md` / `README.md`；`docs/` `doc/` `design/` `spec/` `wiki/`；现有 `.codestable/` 下文件
4. **检查 `.codestable/attention.md`**：缺失则列为骨架待补齐项
5. **汇报扫描结论**：找到的相关文档（列路径）+ 走哪条路径 + 判断依据 + 不确定项

---

## 空仓库路径

**步骤 1：和用户确认范围**

- 项目名 / 简介（用于填 `ARCHITECTURE.md` 占位）
- attention.md 只建最小骨架；用户已经给出的项目硬约束才写入，不凭空代填

**步骤 2：创建目录骨架**

按下面顺序执行，**不等用户逐步确认**——骨架是整体一次性的：

- `.codestable/{requirements,roadmap,features,issues,refactors,audits,brainstorms,compound}/.gitkeep`
- `.codestable/attention.md`（最小骨架模板见同目录 `reference.md`）
- `.codestable/architecture/ARCHITECTURE.md`（占位模板见同目录 `reference.md`）
- `.codestable/tools/` 和 `.codestable/reference/`：仅向确认不存在的目标复制技能包文件；目标已有内容时按下方“安全更新”处理。

> 文件复制使用标准文件工具并核对内容校验值，不经模型转述重建文件。禁止整目录强制覆盖；备份不等于获得覆盖授权。

**步骤 3：attention.md 提醒**

attention.md 已创建但默认只有空骨架。汇报时提醒用户：有编译前置、测试命令、目录禁区、凭证规则这类"每次 CodeStable 技能启动都必须知道"的信息，后续用 `cs-note` 一条条追加。

**步骤 4：验收汇报**

列建了哪些文件：

> CodeStable 骨架已就绪。现在可以：开始新功能 `cs-feat` / 报告问题 `cs-issue` / 沉淀知识 `cs-learn`

---

## 迁移路径

**步骤 1：生成审计报告**

| 现有文件 | 推测内容类型 | 建议归入 CodeStable | 置信度 |
|---|---|---|---|
| `docs/DESIGN.md` | 项目架构 | `.codestable/architecture/ARCHITECTURE.md` | 高 |
| `docs/feature-auth.md` | 功能设计稿 | `.codestable/features/YYYY-MM-DD-auth/auth-design.md` | 中 |
| `SPEC.md` | 功能需求？ | 需用户确认 | 低 |

**置信度**：高 = 语义明确匹配；中 = 可推断有歧义；低 = 不明确或映射多个位置都合理。

**步骤 2：逐条对齐**

中 / 低置信度且现有要求无法确定的，用当前宿主支持的方式澄清，不假定存在某个固定提问工具：

- 中：给推断理由，问"按这个方式归位？"
- 低：描述文件内容，给 2-3 个候选位置 + "跳过"

高置信度不逐条问但要在汇报里列，给用户复审机会——逐条问会让节奏失控。

**步骤 3：处理已部分存在的 .codestable/**

- 命名不符规范（`YYYY-MM-DD-{slug}` 格式）但有内容 → 提示用户问是否重命名
- 空占位（`.gitkeep` / 空 `.md`）→ 直接补齐不问

**步骤 4：补齐缺失骨架**

对照标准骨架补齐**用户确认后仍缺失**的目录 / 文件。已有内容不覆盖。

**安全更新**：技能包是候选模板，不自动认定比项目文件更新或更权威。

1. 比较明确目标的路径、文件类型和内容校验值，区分：目标缺失、完全相同、内容不同。遇到符号链接或文件类型冲突先说明，不跨链接覆盖。
2. 缺失项：在已确认的初始化范围内新增；相同项：跳过。
3. 不同项：展示差异、来源和保留方案。用户已明确批准具体差异时可执行；否则保留原文件，不以“刷新骨架”作为覆盖许可。
4. 覆盖或合并已获授权的文件前，保存可恢复副本并记录校验值；实际写入前复核文件未被其他任务改动。
5. 只更新获准文件，保留项目额外文件；不删除、清空目录，不运行整目录强制覆盖。核对新增和修改结果，并确认未授权文件的校验值不变。

技能包目录指本文件所在目录。本仓库使用 `.limcode/skills/cs-onboard/` 中的模板；其他宿主使用实际加载的技能目录。项目有自己的模板时先核实其适用性，不根据目录名或时间戳猜测权威版本。共享工具使用宿主运行环境，不改产品依赖或交付兼容要求。

**步骤 5：处理不迁移的文件**

用户选"跳过"的文件：**不移动 / 不删除 / 不重命名**，汇报标"保留原位（未纳入 CodeStable）"。**绝不允许未经确认就动**——onboard 只允许 AI 整理不允许替用户做删除决定。

**步骤 6：attention.md 提醒**（同空仓库路径步骤 3）

**步骤 7：验收汇报**

列：迁移文件清单（from → to）、新建骨架、未迁移文件（保留原位）、下一步建议。

---

## 骨架文件模板

`ARCHITECTURE.md` 占位模板和 `attention.md` 最小模板见同目录 `reference.md`。

---

## 退出条件

- [ ] `.codestable/` 标准子目录都存在：requirements / architecture / roadmap / features / issues / refactors / audits / brainstorms / compound / tools / reference
- [ ] `.codestable/attention.md` 已建
- [ ] `.codestable/tools/` 和 `.codestable/reference/` 的适用缺项已补齐；相同项已跳过，不同项按授权更新或明确保留，未覆盖项目定制
- [ ] `.codestable/architecture/ARCHITECTURE.md` 已建
- [ ] 迁移路径：每条映射都有明确处理结果（迁移 / 保留原位）
- [ ] 迁移路径：没有未经确认就移动的文件
- [ ] 验收汇报已给出

---

## 容易踩的坑

- **未经确认就移动 / 删除已有文件**——迁移核心原则是用户拍板
- **替用户填 attention.md 实质内容**——必须项目 owner 来定，AI 只提供模板
- **混淆入口职责**——`.codestable/attention.md` 保存流程注意事项，适用的 `AGENTS.md` 等项目规则仍须遵守。
- **建完骨架立刻开始 feature/issue**——onboard 是"搭环境"不是"开始干活"
- **低置信度直接执行**——低 = 必须问
- **把模板升级当成覆盖许可**——有差异先核对并保留；只执行用户已批准的更新。
- **复制后只看文件名**——还要验证内容以及未授权文件未变。
- **Glob 时忘记排除 `node_modules/` `.git/`**——会让扫描结果充斥噪声

---

## 相关文档

- `.codestable/reference/system-overview.md` — CodeStable 体系总览
- `.codestable/reference/shared-conventions.md` — 目录结构和共享口径的权威版本
- `.codestable/attention.md` — CodeStable 技能启动必读的项目注意事项
- `.codestable/architecture/ARCHITECTURE.md` — 架构总入口骨架
