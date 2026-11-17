# CodeStable 工具用法参考

本文件由 `cs-onboard` 复制到项目的 `.codestable/reference/tools.md`，所有 CodeStable 子技能用项目相对路径 `.codestable/reference/tools.md` 引用。

`.codestable/tools/` 下共享脚本的完整用法参考。子技能里只写本技能特有的 1-2 行典型查询；完整语法和示例看这里。

---

## 1. search-yaml.py

通用 YAML frontmatter 搜索工具。从项目根目录运行，无需安装额外依赖（PyYAML 可选，有则用，无则内建 fallback parser）。

### 基本语法

```bash
python .codestable/tools/search-yaml.py --dir {目录} [--filter key=value]... [--query "全文关键词"] [--sort-by FIELD [--order asc|desc]] [--full] [--json]
```

### filter 语法

- `key=value`：字段精确匹配（大小写不敏感）
- `key~=value`：字符串字段子串匹配；列表字段元素包含匹配
- `key=a|b|c` / `key~=a|b|c`：同一字段多个候选值，候选之间是 OR；在 PowerShell / Bash 中请给整个 filter 加引号，例如 `--filter "doc_type=decision|explore|learning"`

### 排序语法

- `--sort-by FIELD`：按 frontmatter 字段排序（典型字段：`last_reviewed`、`date`、`updated_at`）
- `--order desc|asc`：`desc` 默认，新的在前；`asc` 老的在前（查"谁最久没更新"用这个）
- 字段缺失 / 值为空的文档一律排到最后，不干扰前排结论

### 常用命令

沉淀类文档统一在 `.codestable/compound/`，用 `doc_type` 字段区分四个子技能的产物，内部还有各自的细分字段：

```bash
# 按 doc_type 筛选
python .codestable/tools/search-yaml.py --dir .codestable/compound --filter doc_type=learning
python .codestable/tools/search-yaml.py --dir .codestable/compound --filter "doc_type=decision|explore|learning" --filter status=active
python .codestable/tools/search-yaml.py --dir .codestable/compound --filter doc_type=decision --filter status=active
python .codestable/tools/search-yaml.py --dir .codestable/compound --filter doc_type=trick --filter status=active
python .codestable/tools/search-yaml.py --dir .codestable/compound --filter doc_type=explore --filter status=active

# doc_type + 子技能内部细分字段
python .codestable/tools/search-yaml.py --dir .codestable/compound --filter doc_type=learning --filter track=pitfall
python .codestable/tools/search-yaml.py --dir .codestable/compound --filter doc_type=decision --filter category=constraint
python .codestable/tools/search-yaml.py --dir .codestable/compound --filter doc_type=trick --filter type=pattern
python .codestable/tools/search-yaml.py --dir .codestable/compound --filter doc_type=explore --filter type=question

# 按 tag（列表元素包含匹配）
python .codestable/tools/search-yaml.py --dir .codestable/compound --filter tags~=prisma

# 全文搜索
python .codestable/tools/search-yaml.py --dir .codestable/compound --query "shadow database"

# 按领域/框架/语言筛选
python .codestable/tools/search-yaml.py --dir .codestable/compound --filter doc_type=decision --filter area=frontend
python .codestable/tools/search-yaml.py --dir .codestable/compound --filter doc_type=trick --filter framework~=vue
python .codestable/tools/search-yaml.py --dir .codestable/compound --filter doc_type=trick --filter language=typescript

# 搜索 feature 方案 doc
python .codestable/tools/search-yaml.py --dir .codestable/features --filter doc_type=feature-design --filter status=approved

# 输出控制
python .codestable/tools/search-yaml.py --dir .codestable/compound --filter doc_type=decision --filter status=active --full
python .codestable/tools/search-yaml.py --dir .codestable/compound --filter tags~=llm --json

# 按时间排序
python .codestable/tools/search-yaml.py --dir .codestable/compound --sort-by date --order desc                     # 最近归档的在前
python .codestable/tools/search-yaml.py --dir .codestable/library-docs --sort-by last_reviewed --order asc         # 最久没 review 的在前（找陈旧文档）
python .codestable/tools/search-yaml.py --dir .codestable/guides --filter status=current --sort-by last_reviewed --order asc
```

### 典型使用场景

| 场景 | 命令建议 |
|---|---|
| feature-design 开始前查已有归档 | 搜 `.codestable/compound` 目录，按 `--query "{关键词}"` 全文搜；要分类看就加 `--filter "doc_type=learning\|trick\|decision\|explore"` |
| issue-analyze 根因分析前查历史 | 搜 `.codestable/compound` `--filter doc_type=learning --filter track=pitfall`、再搜 `--filter doc_type=trick --filter type=library`，按相关组件/框架过滤 |
| 归档落盘后查重叠 | 搜 `.codestable/compound --query "{关键词}" --json`，看有无语义重叠 |
| 新人了解项目规约 | `--dir .codestable/compound --filter doc_type=decision --filter status=active` |
| 按技术栈浏览技巧 | `--dir .codestable/compound --filter doc_type=trick --filter language={语言} --filter status=active` |
| 找最久没 review 的库文档 / 指南 | `--dir {目录} --filter status=current --sort-by last_reviewed --order asc` |
| 看最近沉淀了哪些经验 | `--dir .codestable/compound --filter doc_type=learning --sort-by date --order desc` |

---

## 2. validate-yaml.py

YAML 语法校验工具。与 `search-yaml.py` 共用同目录 `_yaml_frontmatter.py` 解析模块，用于验证 Markdown frontmatter 或纯 YAML 文件语法及必填字段。

```bash
# 校验单个 markdown 文件的 frontmatter
python .codestable/tools/validate-yaml.py --file {文件路径}

# 校验纯 YAML 文件（如 manifest.yaml）
python .codestable/tools/validate-yaml.py --file {文件路径} --yaml-only

# 校验必填字段
python .codestable/tools/validate-yaml.py --file {文件路径} --require doc_type --require status

# 批量校验目录下所有文件（分别为 Markdown 与纯 YAML 指定必填字段）
python .codestable/tools/validate-yaml.py --dir {目录} --require doc_type --require status --require-yaml steps

# 目录里同时有 manifest.yaml 这类纯 YAML 文件时，只校验 markdown 文档
python .codestable/tools/validate-yaml.py --dir {目录} --markdown-only --require doc_type --require status

# 只校验目录下的纯 YAML 文件
python .codestable/tools/validate-yaml.py --dir {目录} --yaml-only

# 排除草稿目录或特定文件
python .codestable/tools/validate-yaml.py --dir {目录} --require status --exclude-dir drafts --exclude-file README.md
```

---

## 3. quality_gate_scan.py

项目质量门禁扫描工具。当前静默回退收口验收使用以下真实入口，不再使用旧速记 `tools.quality_gate_scan --strict`。

```bash
# 严格静默回退门禁：成功时保持无输出，退出码为 0
.venv/bin/python -m tools.quality_gate_scan --strict

# 严格静默回退门禁计数快照：输出 JSON，用于留存 evidence
.venv/bin/python -m tools.quality_gate_scan --strict --json

# 历史生产范围 inventory 摘要：用于复核 2026-05-20 原始静态清单口径，不等同于当前 unresolved count
.venv/bin/python -m tools.quality_gate_scan --inventory-summary --json

# 技术债务台账一致性检查：本仓库需用 venv Python，普通 python 可能缺 radon
.venv/bin/python scripts/sync_debt_ledger.py check
```

关键口径：

- `--strict` 用 `tools.quality_gate_operations.architecture_silent_scan_entries(repo_root, collect_quality_rule_files(repo_root))`（`tools/quality_gate_scan.py` 里 `repo_root` 取 `ctx.repo_root`）的扫描结果与 `开发文档/技术债务治理台账.md` 静默回退的非 `fixed` 条目按 `(path, symbol, except_ordinal)` 逐键比较：身份集合、处理器内容（`handler_signature`/`handler_context`）与 `fallback_kind` 都要一致。`scripts/sync_debt_ledger.py check` 与 `refresh --mode refresh-auto-fields` 共用同一个范围视图函数，各自只决定扫描哪些文件。
- `--strict` 成功时无输出；漂移或台账格式错误会向 stderr 打印 `ERROR:` 并以退出码 `2` 失败。
- `--strict --json` 当前用于生成 `evidence/QualityGate/silent_fallback_inventory_acceptance/strict_scan_json.log`。
- 2026-05-22 静默回退收口证据统一放在 `evidence/QualityGate/silent_fallback_inventory_acceptance/`，索引见 `.codestable/compound/2026-05-20-explore-current-silent-fallback-inventory.md`。

## 4. 工作台前端快速检查

旧 opt-in 浏览器自动化通道、pre-push 轮转抽样及对应的历史占位脚本（原 `scripts/run_workbench_opt_in_browser.py` 与 `scripts/run_browser_test_lane.py`）均已删除。工作台 UI Node 契约并入日常测试，现场浏览器检查按任务需要执行。

保留的纯 JavaScript 契约通过 `tests/workbench/test_ui_refinement_node_contracts.py` 进入普通 pytest 套件，测试分组统一在 `tools/test_registry_data.py` 中维护。

```bash
# 只检查保留的前端 JavaScript 契约
.venv/bin/python -m pytest tests/workbench/test_ui_refinement_node_contracts.py -q

# 执行全部保留的业务测试，包含上述 JavaScript 契约
.venv/bin/python -m pytest tests -q
```

关键口径：

- Node 依次从 `WORKBENCH_NODE`、`PATH`、Codex 宿主自带运行时定位；这些检查不需要浏览器运行时。
- 前端契约随普通套件执行，无需额外打开环境开关或单独轮转抽样。
- 工作台界面变更仍可按任务需要做现场浏览器检查，旧通道不再作为自动化门禁。

## 5. scan_constant_arguments.py

只读审计扫描，找两类线索：一是有默认值的形参，生产与宿主工具代码里的调用都没传，或都传同一个字面量；二是模块级空容器，生产与宿主工具代码对它只有不改写、不传出的读取。它不进门禁，也没有基线，结果只作人工复核的输入。

```bash
# 按定义文件分组的文本报告：每条给出定义行、全部调用点或读取点，以及测试偏差
.venv/bin/python -m tools.scan_constant_arguments

# 同样的结论输出为 JSON，另带默认值原文和取值来源，便于脚本复核
.venv/bin/python -m tools.scan_constant_arguments --json

# 扫描另一个检出目录，例如 HEAD 的临时 worktree
.venv/bin/python -m tools.scan_constant_arguments --repo-root <path>
```

关键口径：

- 事实只取自 `tools/dead_code_usage` 的公开引用索引 `build_reference_index` 及其实参绑定，扫描器自己不另做解析或绑定。全仓一次约 20 秒，`.venv` 的 Python 3.8 即可运行。
- 结论只看生产与宿主工具角色的引用（角色定义见 `tools/path_roles.py`）。测试引用不影响结论；与结论不符的测试引用列为“只有测试传了别的值”或“只有测试改写或传出”。
- 索引是欠近似，不可判定的情形一律不报，包括：
  - 有同名的未解析属性访问；
  - 有逃逸或隐式使用；
  - 调用处用了 `*` / `**`，或绑定对不上；
  - 没有来自别处的调用或读取；
  - 方法名在多个类里都有定义；
  - dunder 名与 lambda。
- 非常量名的 `getattr`、`globals()`、星号导入和字符串里的代码，扫描器都看不见。动手前要按调用方逐条复核。
- 2026-11-15 在当前仓库跑出的结果见 `.codestable/audits/2026-11-15-deferred-backlog-root-causes/pipeline/batch-2/evidence/constant_arguments_scan.md`。
