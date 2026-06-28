# Attention

本文件是 CodeStable 技能启动必读的项目注意事项入口。所有 CodeStable 子技能开始工作前必须读取它。

## 项目碎片知识

<!-- cs-note managed: 用 cs-note 维护，新条目按下面分节追加 -->

### 编译与构建

### 运行与本地起服务

### 测试

### 命令与脚本陷阱

- 做实现/修复前先用 `python3 -m tools.symbol_locator` 查定义和影响面：用户问“X 在哪”跑 `whereis X`；问“谁调用 X / 改 X 影响谁”跑 `callers X`；问“X 调了啥 / 依赖谁”跑 `callees X`；问“调用链/上下游”同时跑 `callers` + `callees`；用户说“彻底/全量/精确/含 tests”时给 `callers/callees` 加 `--deep`；句首出现“定位:”/“用定位工具”/“上 sl”必须按语境先调本工具。
- dead-code 门禁(`tools/scan_dead_code_islands.py`)：pre-push 的 `--mode quick` 对鸭子接口回调 / dataclass `__post_init__` / 反射会**误报**死代码(连 `--mode precise` 的 SCIP 都会漏)，报“新增疑似死代码”别急着删——先动态验证(coverage / 运行时 patch 计数跑触发测试 / “删了跑全量测试”兜底)，只有**显式具名函数调用** grep/静态才可信。
- 刷上面这条基线消噪用 `--mode quick --refresh`(与 pre-push 同口径)；**别**用脚本注释/hook 建议的 `--mode precise --refresh`(precise≈33 vs quick≈178 口径差大，precise 刷完 quick pre-push 反而报上百个“新增”)；precise 模式前要先 `python -m tools.symbol_locator build-index` 重建到当前 HEAD 的新鲜 SCIP 索引。

### 路径与目录约定

### 环境变量与凭证

### 其他
