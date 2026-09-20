---
doc_type: decision
category: architecture
date: 2026-09-20
slug: schema-single-source-of-truth
status: active
area: data
tags: [schema, migrations, sqlite, infrastructure, quality-gate]
---

## 背景

数据库结构过去有三个手写来源：`schema.sql`（新库直接执行）、`core/infrastructure/migrations/`（老库逐版升级）、`migration_state.py` 里按表手写的列清单（运行期结构契约）。三处各自演进，2026-09 架构评估时已出现列清单落后于迁移链、`schema.sql` 与迁移结果只靠一条对账测试兜底的情况。基础边界治理路线图（`.codestable/roadmap/foundation-boundary-governance/`）D 模块负责收口，2026-09-20 用户裁决"按我的意见做，全部干完"。

## 决定

1. **迁移链是唯一手写的结构来源。** 新增或修改表、列、索引、触发器、种子行，只在 `core/infrastructure/migrations/vNN.py` 及各子系统的 `*_schema.py` 对象清单里写。
2. **`schema.sql` 是生成产物，不手改。** 由 `tools/generate_schema_sql.py` 从 v4 基线夹具跑完整迁移链后转储 `sqlite_master` 生成；文件头两行固定注释声明"生成产物"；种子行来自各 DDL 模块的 `*_initialization_sql()`。`--check` 进门禁：生成结果与仓库文件不一致即失败；改迁移后用 `--write` 重生成并一起提交。
3. **运行期结构契约改为派生比对，不再手写列清单。** `core/infrastructure/schema_declaration.py` 在内存 SQLite 里执行 `schema.sql` 解析出声明结构；`current_schema_contract_issues(conn, schema_sql=...)` 用它与真实库比对核心表，子系统专属对象由各自的 `objects()` 清单负责。
4. **DDL 文本比较只认规范化形式。** `_canonical_sql` 去注释、归一标点空白、按子句排序后再比；快照与冻结夹具都走同一函数，避免因空格或注释差异误报。

## 理由

- 三源并存时，任何一处漏改都要等到运行期才暴露，且"哪个才对"没有裁决依据。只留迁移链一个手写源，其余派生，冲突在生成或门禁阶段就消失。
- 迁移链必须保留（老库升级路径不可替代），而 `schema.sql` 只是它在"空库"上的投影，天然适合生成。
- 派生比对比手写列清单可靠：手写清单只覆盖作者记得的表，派生比对覆盖声明里的全部核心表。

## 考虑过的替代方案

- **保留手写 `schema.sql`，只加对账测试**：对账测试只能告诉你"不一致"，不能告诉你哪边对；仍然三源。
- **删掉 `schema.sql`，新库也走迁移链**：新库初始化要跑几十个版本的迁移，冷启动变慢，且打包/离线交付场景希望一条脚本建库；生成而非删除兼顾两者。
- **引入 ORM 或迁移框架**：与 Win7 x64 / Python 3.8 / 离线交付约束冲突，也不是本项目的痛点。

## 后果

- 改结构的工作流固定为：写迁移 → `python -m tools.generate_schema_sql --write` → 跑 `tests/migration_db/test_generate_schema_sql.py` 与结构对账测试 → 提交迁移、`schema.sql` 与测试。
- 直接改 `schema.sql` 的提交会被 `--check` 门禁拦下。
- `ensure_schema_version` / `detect_schema_is_current` 等入口带 `schema_sql` 参数贯通，测试可注入声明文本；不再有 `database_bootstrap` 的正则解析路径。

## 相关文档

- `.codestable/roadmap/foundation-boundary-governance/foundation-boundary-governance-roadmap.md` §D、§4.3
- `tools/generate_schema_sql.py`、`core/infrastructure/schema_declaration.py`、`core/infrastructure/migration_state.py`
- 提交 `bcb400f3`
