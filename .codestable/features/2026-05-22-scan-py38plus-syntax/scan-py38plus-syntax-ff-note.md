---
doc_type: feature-ff-note
feature: scan-py38plus-syntax
date: 2026-05-22
requirement: 
tags: [python38, quality-gate, compatibility]
---

## 做了什么
新增一个 Python 3.8.10 兼容性扫描脚本，用于快速统计仓库里 Python 3.8 之后才支持的硬语法，以及常见的 3.9+ 运行/语义兼容风险。按 Context7 查到的 Python 文档补了规则来源清单，覆盖 3.9、3.10、3.11、3.12、3.13、3.14 的主要语法变化。

## 改了哪些
- `tools/scan_py38plus_syntax.py` — 新增扫描 CLI，支持文本/JSON 输出、`--syntax-only`、`--fail-on-hit`、路径范围扫描，并在文本报告中打印规则来源。
- `tests/test_scan_py38plus_syntax.py` — 覆盖 match、except*、PEP 695/696、t-string、PEP 584、PEP 585/604/646、syntax-only 和 CLI JSON/退出码。

## 怎么验证的
- `.venv/bin/python -m pytest tests/test_scan_py38plus_syntax.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check tools/scan_py38plus_syntax.py tests/test_scan_py38plus_syntax.py`
- `.venv/bin/python tools/scan_py38plus_syntax.py --syntax-only --max-examples 5`
- `.venv/bin/python tools/scan_py38plus_syntax.py --json`

## 顺手发现（可选，不阻塞）
- 当前全仓硬语法扫描未发现 Python 3.8 解析器拒绝的语法。
- 当前全仓默认扫描命中 303 条，均为注解/类型语义风险：`PEP585_GENERIC_ALIAS=247`、`PEP604_UNION_TYPE=56`；未发现 PEP 584 dict merge/update、PEP 646 variadic generic、PEP 654 except*、PEP 695/696、PEP 750/758 等命中。
