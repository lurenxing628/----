# CodeStable 工具用法参考

本文件由 `cs-onboard` 复制到项目的 `.codestable/reference/tools.md`，所有 CodeStable 子技能用项目相对路径 `.codestable/reference/tools.md` 引用。

`.codestable/tools/` 下共享脚本的完整用法参考。子技能里只写本技能特有的 1-2 行典型查询；完整语法和示例看这里。

---

## 1. search-yaml.py

通用 YAML frontmatter 搜索工具。从项目根目录运行，无需安装额外依赖（PyYAML 可选，有则用，无则内建 fallback parser）。

### 基本语法

```bash
python .codestable/tools/search-yaml.py --dir {目录} [--filter key=value] [--query "全文关键词"] [--sort-by FIELD [--order asc|desc]] [--full] [--json]
```

需要多个过滤条件时，重复写 `--filter`。

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
python .codestable/tools/search-yaml.py --dir docs/api --sort-by last_reviewed --order asc                         # 最久没 review 的 API 参考在前
python .codestable/tools/search-yaml.py --dir docs/dev --filter status=current --sort-by last_reviewed --order asc # 最久没 review 的开发者指南在前
python .codestable/tools/search-yaml.py --dir docs/user --filter status=current --sort-by last_reviewed --order asc # 最久没 review 的用户指南在前
```

### 典型使用场景

| 场景 | 命令建议 |
|---|---|
| feature-design 开始前查已有归档 | `python .codestable/tools/search-yaml.py --dir .codestable/compound --query "{关键词}"`；要分类看就追加 `--filter doc_type=learning`（或 trick / decision / explore） |
| issue-analyze 根因分析前查历史 | `python .codestable/tools/search-yaml.py --dir .codestable/compound --filter doc_type=learning --filter track=pitfall`，再用 `python .codestable/tools/search-yaml.py --dir .codestable/compound --filter doc_type=trick --filter type=library --query "{关键词}"` |
| 归档落盘后查重叠 | `python .codestable/tools/search-yaml.py --dir .codestable/compound --query "{关键词}" --json`，看有无语义重叠 |
| 新人了解项目规约 | `python .codestable/tools/search-yaml.py --dir .codestable/compound --filter doc_type=decision --filter status=active` |
| 按技术栈浏览技巧 | `python .codestable/tools/search-yaml.py --dir .codestable/compound --filter doc_type=trick --filter language={语言} --filter status=active` |
| 找最久没 review 的 API 参考 / 指南 | `python .codestable/tools/search-yaml.py --dir docs/api --sort-by last_reviewed --order asc`；指南改用 `--dir docs/dev` 或 `--dir docs/user` 并追加 `--filter status=current` |
| 看最近沉淀了哪些经验 | `python .codestable/tools/search-yaml.py --dir .codestable/compound --filter doc_type=learning --sort-by date --order desc` |

---

## 2. validate-yaml.py

YAML 语法校验工具。用于验证 frontmatter 语法和必填字段。

```bash
# 校验单个 markdown 文件的 frontmatter
python .codestable/tools/validate-yaml.py --file {文件路径}

# 校验纯 YAML 文件（如 manifest.yaml）
python .codestable/tools/validate-yaml.py --file {文件路径} --yaml-only

# 校验必填字段
python .codestable/tools/validate-yaml.py --file {文件路径} --require doc_type --require status

# 批量校验目录下所有文件
python .codestable/tools/validate-yaml.py --dir {目录} --require doc_type --require status

# 目录里同时有 manifest.yaml 这类纯 YAML 文件时，只校验 markdown 文档
python .codestable/tools/validate-yaml.py --dir {目录} --markdown-only --require doc_type --require status

# 只校验目录下的纯 YAML 文件
python .codestable/tools/validate-yaml.py --dir {目录} --yaml-only
```
