# Attention

本文件保存 CodeStable 的项目注意事项，补充适用的 AGENTS.md。本轮已读取且未变化时复用，内容丢失或文件变化时重读；不因切换子技能重复加载。

## 项目碎片知识

<!-- cs-note managed: 用 cs-note 维护，新条目按下面分节追加 -->

### 编译与构建

### 运行与本地起服务

### 测试

### 命令与脚本陷阱

- 产品函数定位与影响分析用 `python3 -m tools.symbol_locator`，具体选择见 `.codestable/reference/symbol-locator.md`。
- dead-code 门禁(`tools/scan_dead_code_islands.py`)：pre-push 的 `--mode quick` 对鸭子接口回调 / dataclass `__post_init__` / 反射会**误报**死代码(连 `--mode precise` 的 SCIP 都会漏)，报“新增疑似死代码”别急着删——先动态验证(coverage / 运行时 patch 计数跑触发测试 / “删了跑全量测试”兜底)，只有**显式具名函数调用** grep/静态才可信。
- 刷上面这条基线消噪用 `--mode quick --refresh`(与 pre-push 同口径)；**别**用脚本注释/hook 建议的 `--mode precise --refresh`(precise≈33 vs quick≈178 口径差大，precise 刷完 quick pre-push 反而报上百个“新增”)；precise 模式前要先 `python -m tools.symbol_locator build-index` 重建到当前 HEAD 的新鲜 SCIP 索引。
- CodeStable / LimCode 的本机维护、检索和体检工具故意使用宿主 Python 3.14；不要把 APS 运行时的 Python 3.8 语法约束强加给 `.limcode/skills/` 与这类宿主工具。APS 的 `core/`、`web/`、`data/`、项目测试、打包和最终质量门禁仍须兼容 Python 3.8 / Win7 x64，宿主工具不得进入离线运行包。

### 路径与目录约定

### 环境变量与凭证

### 其他
