"""full_test_debt 长门禁条目的整体复用语义（P2 已塌缩增量引擎）。

历史上本模块是 ~2000 行的增量重跑引擎：按 git 变更分类（测试/助手/生产代码/
台账）、做 AST import 影响分析、经 long_gate_test_body_diff 做测试体差分精确
选择 nodeid、增量跑后把结果合并回上次全量 payload，并维护 7.7MB 的
full_test_debt_node_cache.json 节点缓存（ledger_only 快路同属此机器）。

P2 治理将缓存语义塌缩为「指纹全中→整体复用上次成功；任何 miss→全量重跑」，
由 long_gate_cache.evaluate_reuse 的通用路径承担，增量机器整体退役：
- 不再有特殊执行模式与节点缓存（产物文件不再写出）；
- NODE_CACHE_REL 常量保留为旧产物路径的锚点（门禁契约测试引用）；
  clean-worktree 排除与 git hook 拦截走 quality_gate_shared 常量与
  git_hook_blocked_paths 字面量，二者继续防旧产物入库。
"""

from __future__ import annotations

from tools.quality_gate_shared import QUALITY_GATE_FULL_TEST_DEBT_NODE_CACHE_REL

NODE_CACHE_REL = QUALITY_GATE_FULL_TEST_DEBT_NODE_CACHE_REL.replace("\\", "/")

__all__ = ["NODE_CACHE_REL"]
