# plugins/（自研插件目录）

## 约定

应用启动时会扫描 `plugins/*.py` 并尝试加载插件元信息。插件可选实现：

- `PLUGIN_ID` / `PLUGIN_NAME` / `PLUGIN_VERSION`
- `PLUGIN_DEFAULT_ENABLED`：`yes` / `no`（默认 `no`）
- `register(registry)`：当 enabled=yes 时调用，可向注册表写入能力

插件文件建议 **不要在顶层 import 重依赖**（如 pandas/ortools），而是在 `register()` 内再 import，
这样在“禁用/缺失依赖”时也能展示插件状态，不影响主程序启动。

## 已提供插件

- `pandas_backend_plugin.py`：可选 pandas/numpy Excel 后端（默认关闭，Win7 离线锁定版本）
- `ortools_probe_plugin.py`：OR-Tools 探测插件（默认关闭，用于现场判断是否能 import）

