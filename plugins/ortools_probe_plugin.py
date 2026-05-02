"""
可选插件：OR-Tools 探测（Win7 离线高风险项）。

用途：
- 仅用于“能力探测/可观测”：启用后尝试 import ortools，成功则注册 capability；
  若失败（DLL load failed 等），会在系统管理页展示错误原因，便于现场判断。

注意：
- 本插件不提供实际求解器接入（求解器接入应作为独立插件/任务实现）。
"""

PLUGIN_ID = "ortools_probe"
PLUGIN_NAME = "深度优化环境检测"
PLUGIN_VERSION = "1.0"
PLUGIN_DEFAULT_ENABLED = "no"


def register(registry):
    import ortools

    registry.register("dependency.ortools", {"version": getattr(ortools, "__version__", None)})
