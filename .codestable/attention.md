# Attention

本文件保存 CodeStable 的项目注意事项，补充适用的 AGENTS.md。本轮已读取且未变化时复用，内容丢失或文件变化时重读；不因切换子技能重复加载。

## 项目碎片知识

<!-- cs-note managed: 用 cs-note 维护，新条目按下面分节追加 -->

### 编译与构建

### 运行与本地起服务

### 测试

- “被测试锁定”只有在锁住的行为生产可达时，才是留下防御分支或旧入口的理由：先确认真实生产调用链会走到这条行为，只有测试会构造的输入或调用组合不算。
- 复审放行口径（D2-4）：① 终轮 MINOR 不因“本轮已收敛、不再空转”整体放行，逐条判“修 / 推迟（写重启条件）/ 驳回（写事实依据）”；② 以“测试锁定”放行，须证明锁住的行为生产可达；③ “非本轮引入”只记来源，不作放行理由；④ 多部分发现逐子项记账；⑤ 记账文字只写问题与事实，不写“可选”“保留”一类实现方案。

### 命令与脚本陷阱

- 产品函数定位与影响分析用 `python3 -m tools.symbol_locator`，具体选择见 `.codestable/reference/symbol-locator.md`。
- 上游收口（改名、删参、改返回形状、删字段）的同一提交里，再 `rg` 一遍下游 `frontend/`、`tests/**/*.cjs`、`scripts/workbench/`：这些 JS 引用对 `symbol_locator` 等 Python 工具不可见。
- 死代码扫描 `tools.scan_dead_code_islands` 是共用棘轮（`tools/boundary_baseline.py`）：日常门禁与完整门禁都跑 `--mode quick --fail-on-new`，新增、计数增加或条目失效即失败；条目分 `suspect_dead`（没有任何引用）与 `test_only`（只有 `tests/`、`tools/host_tests/` 引用）。隐式入口（MRO 派发、`super()`、dataclass 初始化链、运算与外部 API 调用的协议成员、外部框架回调、赋给 `Flask.wsgi_app` 的服务器调用、实参绑定）已由 `tools/dead_code_usage/` 的规则建模，误报回扫描器规则修。类型传播是上下文不敏感的欠近似：字面量容器多到拓宽后结果依赖遍历次序；求解按稳定次序，同一份代码结果固定，但一处改动可能让共用通用 helper 的无关函数证据增减，棘轮报的新增先看是不是这种连带变化。报出的疑似项仍是静态结论，删之前先动态验证（coverage / 运行时 patch 计数跑触发测试 / “删了跑全量测试”兜底），只有**显式具名函数调用**的 grep/静态结论可信；反例：DC-07 `OwnedSegments.__eq__` 按 `rg` 只看到测试调用，动态实测在 `sgs_checkpoint_tail.py` 的检查点比较（`==`/`!=`）里有生产调用。
- 死代码基线只用 `--mode quick --refresh` 刷新，默认拒绝新增条目，报出项不靠刷新消掉；`--allow-growth` 表示人工逐条核对后按当前扫描整份重写、不读旧基线。`--mode precise`（SCIP）只出报告、不读写基线（带 `--fail-on-new` 或 `--refresh` 直接报参数错误），运行前要求工作区干净、索引是当前 HEAD（`python -m tools.symbol_locator build-index` 重建）。
- CodeStable / LimCode 的本机维护、检索和体检工具故意使用宿主 Python 3.14；不要把 APS 运行时的 Python 3.8 语法约束强加给 `.limcode/skills/` 与这类宿主工具。APS 的 `core/`、`web/`、`data/`、项目测试、打包和最终质量门禁仍须兼容 Python 3.8 / Win7 x64，宿主工具不得进入离线运行包。

### 路径与目录约定

### 环境变量与凭证

### 其他
