# CodeStable 共享口径

由 `cs-onboard` 复制到项目的 `.codestable/reference/shared-conventions.md`。所有 CodeStable 子技能用项目相对路径 `.codestable/reference/shared-conventions.md` 引用本文件——跨子技能的项目现行共享约定。技能包内同名文件仅是新项目模板，不能覆盖平台规则、适用的 AGENTS.md 或项目已有定制。

本文件是产物路径和状态协议的维护位置。任务授权、完成与读取范围遵守适用的 AGENTS.md；按需要读取对应节，不在每个技能重复这些规则。

---

## 0. 目录结构与路径命名

onboard 完成后骨架（`cs-onboard` 负责搭建）：

```
.codestable/
├── attention.md           项目注意事项（已读且未变时复用）
├── requirements/          能力愿景层（"用户需要什么、系统提供什么能力来满足"，过去/现在/未来）
│   ├── VISION.md           中心索引（按 status 分组，每条带 pitch 一句话）
│   └── {slug}.md           一个能力一份，扁平（cs-req 产出）
├── architecture/          架构中心目录（"用什么结构实现"，只记现状）
│   ├── ARCHITECTURE.md    总入口（索引 + 关键架构决定）
│   └── {type}-{slug}.md   子系统 / 模块 doc（cs-arch 产出）
├── roadmap/               规划层（"接下来怎么做这块大需求 + 模块怎么切 + 接口怎么定"）
│   └── {slug}/            一个大需求一个子目录（cs-roadmap 产出）
│       ├── {slug}-roadmap.md   主文档：背景 / 范围 / 模块拆分 / 接口契约 / 子 feature 清单 / 排期
│       ├── {slug}-items.yaml   机器可读子 feature 清单，acceptance 回写状态
│       └── drafts/             可选
├── features/              feature spec 聚合根
│   └── YYYY-MM-DD-{slug}/  每个 feature 一个目录
│       ├── {slug}-brainstorm.md  （可选，case 2 时产出）
│       ├── {slug}-design.md      （标准流程）
│       ├── {slug}-checklist.yaml （标准流程）
│       ├── {slug}-acceptance.md  （标准流程）
│       └── {slug}-ff-note.md     （fastforward 通道唯一产物，与上面四份互斥）
├── issues/                issue spec 聚合根
│   └── YYYY-MM-DD-{slug}/
│       ├── {slug}-report.md
│       ├── {slug}-analysis.md   （根因不显然才有）
│       └── {slug}-fix-note.md
├── refactors/             refactor spec 聚合根
│   └── YYYY-MM-DD-{slug}/
│       ├── {slug}-scan.md
│       ├── {slug}-refactor-design.md
│       ├── {slug}-checklist.yaml
│       └── {slug}-apply-notes.md
├── audits/                主动审计发现清单（cs-audit 产出）
│   └── YYYY-MM-DD-{slug}/
│       ├── index.md
│       └── finding-NN.md
├── compound/              沉淀类文档统一目录
│   └── YYYY-MM-DD-{doc_type}-{slug}.md
│                          doc_type ∈ {learning, trick, decision, explore}
├── brainstorms/           开放 brainstorm 创意空间（cs-brainstorm case 4 产出）
│   └── {slug}/            一次 spike 一个子目录，文件名随意
│                          验完不强制清理，结论回写到对应 brainstorm note
├── tools/                 跨工作流共享脚本（onboard 从技能包释放）
└── reference/             共享参考文档（onboard 从技能包释放）
```

### 命名规则

- 需求文档：`requirements/{slug}.md`（能力愿景，不带日期前缀，扁平不分组）；中心索引 `requirements/VISION.md`
- roadmap：`roadmap/{slug}/`（不带日期前缀，平铺不嵌套）
- feature / issue / refactor 目录：带日期前缀 `YYYY-MM-DD-{slug}`
- audit 目录：带日期前缀 `audits/YYYY-MM-DD-{slug}/`，目录内固定 `index.md` + `finding-NN.md`
- 开放 brainstorm：`brainstorms/{slug}/`，不带日期前缀，保留发散材料给后续 roadmap 读取
- 沉淀类：`compound/YYYY-MM-DD-{doc_type}-{slug}.md`，日期用**归档当天**
- 架构 doc：`architecture/{type}-{slug}.md`（长效，不带日期前缀）；总入口固定 `ARCHITECTURE.md`
- 项目注意事项入口为 `.codestable/attention.md`，按任务需要读取；本轮已读且未变化时复用，变化或上下文丢失时重读。它补充而不替代适用的 `AGENTS.md`；缺失不阻断只读调查和已授权的局部工作

### 架构 doc 分组规则

新文档沿用现有类别与命名，目录是否需要分组按检索和维护需要决定，不按固定数量自动搬迁。局部更新不重排其他文档；明确整理目录时先留快照，同步索引和引用，保留历史追溯。

### 改目录结构

项目当前约定维护在 `.codestable/reference/shared-conventions.md`。可复用变化再同步 `cs-onboard/reference/shared-conventions.md` 模板；同步时保留项目定制，不能整份模板覆盖已有项目。

---

## 1. 共享元数据口径

**feature spec**：brainstorm / design / acceptance 共用 `doc_type` / `feature` / `status` / `summary` / `tags`。子技能只补特有字段。`status`：brainstorm = `confirmed`（落盘即确认无 draft）；design = `draft` / `approved`；acceptance 见对应技能。

**issue spec**：report / analysis / fix-note 共用 `doc_type` / `issue` / `status` / `tags`。`severity` / `root_cause_type` / `path` 由对应阶段按需补。

**归档类（compound）**：

- learning / trick / decision / explore 四类**统一写入 `.codestable/compound/`**
- 每个文档 frontmatter 顶部带 `doc_type`（learning / trick / decision / explore）作跨子技能归属判定
- 文件名 `YYYY-MM-DD-{doc_type}-{slug}.md`——日期打头便于 `ls` 排序，type 段在中间便于 grep
- 各子技能在 `doc_type` 之外保留专属 frontmatter（learning 的 `track` / trick 的 `type` / decision 的 `category` / explore 的 `type`）
- 各子技能按 `doc_type` 维护自己负责的产物；可以读取其他类型的相关证据，不越权修改其他产物
- `status` 等通用字段语义和本文件保持一致

**外部读者文档**（guidedoc / libdoc）：frontmatter 由各自子技能定义。无特殊说明：`draft` = 待 review，`current` = 当前有效，`outdated` = 代码已变更待同步。

**主动审计文档**（audit）：

- index 文档 `doc_type: audit-index`
- 单条发现 `doc_type: audit-finding`
- 审计只负责列发现；用户明确要求修复时，修复动作仍按 issue / refactor / 直接定点修复的边界处理

**写作约束**：子技能提字段时优先写"额外字段"或"阶段状态变化"，不重复展开整套通用字段。

---

## 2. {slug}-checklist.yaml 生命周期

- 是 feature 工作流的唯一执行清单
- 由 `cs-feat-design` 在 design 确认通过后一次生成 `steps` + `checks`
- `cs-feat-ff` **不生成** checklist（也不写 design / acceptance），是跳过 spec 流程直接写代码的超轻量通道；唯一留下的痕迹是动手后回写的 `{slug}-ff-note.md`（轻量回顾，参与 scoped-commit、可被 cs-arch / cs-req backfill 检索到）

`steps` 按独立可验证的行为和依赖划分，不固定步数、分钟数或实现架构。任务可以按实际需要细化到文件；不把计划细节误当不可调整的业务契约。

**design 的职责**：从方案中的必要变化、公开契约、范围边界和验收场景提取步骤与检查项。每步具有可验证的退出条件，保留清单字段和状态协议。

**implement 的职责**：

- 按 `steps` 顺序执行，每步完成把 status `pending` → `done`
- 实现到具体文件级时可在原范围内细分步骤并记录；新增前置重构扩大范围、改变业务或外部约定时，说明影响并确认后再追加
- 不改写 `checks`

**acceptance 的职责**：只更新 `checks[].status`（`pending` → `passed` / `failed`），不重写 `steps`。

**写作约束**：子技能描述 checklist 时只补本阶段读 / 写哪一部分，不重新定义生命周期。

---

## 2.5 roadmap ↔ feature 衔接协议

`.codestable/roadmap/{slug}/{slug}-items.yaml` 是规划层和 feature 执行层的唯一接口。三个技能共同读写它——是 skill 都读写项目共享产物，不算耦合。

**items.yaml 状态机**：

```
planned  → in-progress  （cs-feat-design 启动 feature 时改）
in-progress → done      （cs-feat-accept 验收完成时改）
planned  → dropped      （cs-roadmap update 模式，用户决定不做时改）
```

`done` / `dropped` 是终态。需要回退重做的新加一条 slug 略改的条目，不改终态。

**cs-roadmap 的职责**：生成和维护 roadmap 主文档 + items.yaml；把 `planned` 改 `dropped`（用户放弃时）；不改 `in-progress` / `done`（feature 技能负责）。

**cs-feat-design 的职责**（从 roadmap 起头时）：

1. design.md frontmatter 加 `roadmap: {roadmap-slug}` + `roadmap_item: {子 feature slug}`
2. items.yaml 对应条目 `status: in-progress` + `feature: YYYY-MM-DD-{slug}`
3. 校验 yaml

直接起 feature（非 roadmap 来）两字段留空，不触发 roadmap 写。

**cs-feat-accept 的职责**：

1. 读 design frontmatter `roadmap` / `roadmap_item`
2. 空 → 跳过
3. 有值 → items.yaml 对应条目 `status: done`；同步主文档子 feature 清单显示状态；校验 yaml

回写是**实际写文件的动作**，验收报告要明确记录回写结果。

**最小闭环标记**：items.yaml 每份只有一条 `minimal_loop: true`，标记"做完后系统能端到端跑通最窄路径"。design 启动 `minimal_loop` 条目时优先级最高。

---

## 3. 阶段收尾推荐

根据本次工作实际影响，完成已授权的架构/需求/路线图回写或轻量任务记录。发现长期经验、约束、指南或 API 参考需要更新时，按既有授权处理；未授权的额外工作只合并提示一次。不要逐项追问，也不为填满模板制造文档。

提交单独遵守第 4 节。

---

## 4. 收尾提交（scoped-commit）

用户明确要求提交时，将本次相关产物按完整改动组织提交：

- **范围**：本次工作改到的代码 + 相关 spec 文档 + 本次实际更新过的架构 doc + 本次实际更新过的 roadmap items.yaml / 主文档
- **不该进**：和本次工作无关的顺手修改；属于"下次另起 feature / issue"的扩大范围
- **提交前确认**：用户没明确同意不要 `git commit`
- **commit message**：一句话说清"做了什么"，不贴 spec 目录路径

子技能只描述本阶段特有提交范围，通用规则看这里。

---

## 5. 归档检索规则

feature-design / issue-analyze / issue-fix 动手前到 `.codestable/compound/` 搜已有沉淀：

- 按任务相关性检索 `architecture/` 和 `compound/`；本轮已有且未变化的相关结果直接复用。不存在时说明限制，不为调查自动初始化
- 在 `compound/` 用 `doc_type` 过滤（learning / trick / decision / explore）
- 搜到的结果只作参考输入，不盲目套用——可能已 `outdated` 或不适合当前上下文
- 搜到和当前方向冲突的 decision → **必须**正面回应"为什么仍然这么做"或调整方向

子技能只补本阶段查询命令。完整搜索语法看 `.codestable/reference/tools.md`。

---

## 6. 归档类子技能共享守护规则

`cs-learn` / `cs-trick` / `cs-decide` / `cs-explore` 共享下面这组规则。子技能正文只写特有反模式，通用看这里：

1. **只增不删**——已归档除非被明确取代（`status=superseded`）否则不删；理由丢失成本极高
2. **宁缺毋滥**——用户说不出理由的节直接省略，不要 AI 编造
3. **不替用户写实质内容**——AI 负责起草结构和串联语言，实质结论必须来自用户或可追溯的代码证据
4. **attention.md 检查**——只把跨任务必要的短约束放在 attention，具体方法留在主题参考。用户已授权维护注意事项时直接处理，否则不扩展写入范围
5. **起草前先查重叠**——动手写前用 `search-yaml.py --query` 查语义相近的旧文档。按用户意图和证据选择以下路径；只有取代关系或范围仍不明确时才问：
   - **更新已有**（默认优先）：沿用原文件名和原创建日期，**不新建**；frontmatter 补 `updated: YYYY-MM-DD`；超出小修在文末加"YYYY-MM-DD 更新"简述
   - **supersede**：旧文档保留原文，`status: superseded` + `superseded-by: {新文件名}`，正文顶部加 `**[已取代]** 见 {新 slug}`；新文档 frontmatter 带 `supersedes: {旧文件名}`
   - **确实是不同主题**：新建，文末"相关文档"列出已有那条说明区别
6. **识别用户意图是"改已有"还是"记新的"**——用户说"改 / 更新 / 修订 / 补充 {某条}"、明确指向某条旧文档、或话题高度重合时默认走"更新已有"，不要闷头新建。分不清就问。

各子技能按 `doc_type` 区分写入归属；允许读取其他类型的相关证据，跨类型更新须属于本轮授权范围。

---

## 7. 实现结构检查

实现或修复时，按实际变化检查职责、依赖、错误语义和契约。复用现有模式，不为固定函数长度、参数数量或重复次数强行拆分，也不规避项目真实质量门禁。

原范围内必要的内部调整可自行实现并验证；跨模块重划、公开接口变化或独立重构按 AGENTS.md 的授权边界处理。可疑死代码先验证真实调用、回调或反射路径；静态未命中不是删除证据。
