# Attention

本文件是 CodeStable 技能启动必读的项目注意事项入口。所有 CodeStable 子技能开始工作前必须读取它。

## 项目碎片知识

<!-- cs-note managed: 用 cs-note 维护，新条目按下面分节追加 -->

### 编译与构建

### 运行与本地起服务

### 测试

### 命令与脚本陷阱

- 做实现/修复前先用 `python3 -m tools.symbol_locator` 查定义和影响面：用户问“X 在哪”跑 `whereis X`；问“谁调用 X / 改 X 影响谁”跑 `callers X`；问“X 调了啥 / 依赖谁”跑 `callees X`；问“调用链/上下游”同时跑 `callers` + `callees`；用户说“彻底/全量/精确/含 tests”时给 `callers/callees` 加 `--deep`；句首出现“定位:”/“用定位工具”/“上 sl”必须按语境先调本工具。

### 路径与目录约定

### 环境变量与凭证

### 其他
