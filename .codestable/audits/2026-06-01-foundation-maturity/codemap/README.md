# CODEMAP —— 全项目静态分析真值底座（第二轮深钻共享数据）

由 `../codemap_extract.py` + `../dynamic_refs.py` 一次性提取，覆盖 648 个一方模块 / 12.5 万行（不含 tests）。
**所有第二轮深钻 Agent 必须先读本说明，再用这些 JSON 作为事实起点，避免各自重复 grep、各凭感觉。**

## 可靠用法（import 图的强项，可直接采信）
- `summary.json` —— 全局统计：各层模块数/行数、重名符号 Top、复制函数体簇。
- `layering.json` —— **分层违规候选，当前 0 条**。已 AST 全量验证：algorithms↛services、models↛上层、viewmodels↛禁区、routes↛repositories、business↛tools 全部为 0。这是地基最硬的证据，可直接采信。
- `dup_bodies.json` —— **复制粘贴函数体**（结构归一化指纹，15 簇 94 处）。每簇列出每一处 `rel:line`。可直接作为去重靶子，但需 Agent 区分"该消灭的复制"vs"dataclass/repo 惯用样板"（如 to_dict/delete_all/from_row）。
- `dup_symbols.json` / `symbol_index.json` —— 重名符号（≥3 处定义）及全符号 -> 定义位置索引。
- `import_edges.json` / `layer_edges.json` —— 模块级 / 层级 import 有向边。可靠地回答"A 是否静态依赖 B"。
- `defs.json` —— 6182 个函数/类/方法定义清单（名、文件:行、私有否、参数数、所属类、层）。
- `modules.json` —— 每模块：路径、层、行数、一方 import、定义符号。

## 不可靠用法（import 图的盲区，禁止直接采信）
- `orphan_candidates.json`（167）/ `orphan_refined.json`（115）—— **"零被静态 import"≠ 死代码**。
  Flask 蓝图 side-effect 注册、`g.services` registry property 装配、`importlib` 动态加载、字符串模块名引用都抓不到。
  名单里 `gantt_service.py`/`report_engine.py`/所有 `*_repo.py`/`calendar.py` 显然都活着。
  **死代码判定必须由 Agent 回到代码用 grep 实证调用点**（像第二轮专题 B 那样逐方法 grep），不得用本名单直接下结论。
  `dynamic_refs.json` 记录了已识别的动态引用证据，仅供参考。

## 重要事实速查
- 648 模块 / 125435 行（不含 tests）/ 6182 定义 / 2011 import 边。
- 最大层：core.services.scheduler（128 模块）。
- 最大重复：`_text`(23) + `_normalize_text`(13) = 36 处字符串清洗同义函数。
- 分层违规：0（地基红线全部成立）。
