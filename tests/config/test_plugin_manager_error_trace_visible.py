"""回归测试：PluginManager.load_from_base_dir 加载在 register 阶段抛异常的 enabled 插件时不崩溃，状态中 enabled=yes/loaded=no，且 error 字段同时包含异常消息与 Traceback（即使 logger.error 不支持 exc_info）。"""

import os
import tempfile


class _StubLogger:
    def __init__(self):
        self.errors = []

    # 故意不支持 exc_info 参数，验证 manager.py 的回退逻辑不会崩溃
    def error(self, msg: str):
        self.errors.append(str(msg))


def test_plugin_manager_error_trace_visible() -> None:

    from core.plugins.manager import PluginManager

    tmpdir = tempfile.mkdtemp(prefix="aps_regression_plugins_")
    plugins_dir = os.path.join(tmpdir, "plugins")
    os.makedirs(plugins_dir, exist_ok=True)

    # 一个会在 register 阶段抛异常的插件（enabled=yes）
    plugin_py = os.path.join(plugins_dir, "bad_plugin.py")
    with open(plugin_py, "w", encoding="utf-8") as f:
        f.write(
            "\n".join(
                [
                    "PLUGIN_ID = 'bad_plugin'",
                    "PLUGIN_NAME = 'Bad Plugin'",
                    "PLUGIN_DEFAULT_ENABLED = 'yes'",
                    "",
                    "def register(registry):",
                    "    raise RuntimeError('boom')",
                    "",
                ]
            )
        )

    st = PluginManager.load_from_base_dir(tmpdir, conn=None, logger=_StubLogger())
    statuses = st.get("statuses") or []
    bad = next((x for x in statuses if (x.get("plugin_id") == "bad_plugin")), None)
    assert bad is not None, f"未找到 bad_plugin 状态：{statuses!r}"
    assert bad.get("enabled") == "yes", f"enabled 口径异常：{bad!r}"
    assert bad.get("loaded") == "no", f"loaded 口径异常：{bad!r}"
    err = str(bad.get("error") or "")
    assert "boom" in err, f"错误信息未包含异常：{err!r}"
    assert "Traceback" in err, f"错误信息未包含 traceback：{err!r}"
