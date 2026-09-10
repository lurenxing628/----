"""回归测试：插件 register() 中途失败（先注册能力、后抛错）时，PluginManager 必须整体回滚
该插件本次写入 registry 的增量——loaded=no 的插件不得以半初始化 provider 残留接管能力路由
（如 excel_backend.pandas 抢走 Excel 读写），也不得以 first_loaded_wins 残留 key 挡住后续
同名健康插件注册；既有健康插件的能力不受回滚误伤。"""

import os
import tempfile


def _write_plugin(plugins_dir: str, filename: str, lines) -> None:
    with open(os.path.join(plugins_dir, filename), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _make_plugins_dir() -> str:
    tmpdir = tempfile.mkdtemp(prefix="aps_regression_plugins_rollback_")
    plugins_dir = os.path.join(tmpdir, "plugins")
    os.makedirs(plugins_dir, exist_ok=True)
    return tmpdir


def test_register_partial_failure_rolls_back_registry_and_keeps_healthy_plugin() -> None:

    from core.plugins.manager import PluginManager, get_plugin_registry, reset_plugin_state
    from core.services.common.excel_backend_factory import get_excel_backend
    from core.services.common.openpyxl_backend import OpenpyxlBackend

    tmpdir = _make_plugins_dir()
    plugins_dir = os.path.join(tmpdir, "plugins")

    # 插件 A（先加载）：健康插件，注册一个无关能力——验证回滚不误伤别人
    _write_plugin(
        plugins_dir,
        "a_healthy_plugin.py",
        [
            "PLUGIN_ID = 'healthy_plugin'",
            "PLUGIN_DEFAULT_ENABLED = 'yes'",
            "",
            "def register(registry):",
            "    registry.register('probe.healthy', 'healthy-provider')",
        ],
    )
    # 插件 B（后加载）：register 内先注册 excel_backend.pandas，再抛错——半初始化场景
    _write_plugin(
        plugins_dir,
        "b_half_bad_plugin.py",
        [
            "PLUGIN_ID = 'half_bad_plugin'",
            "PLUGIN_DEFAULT_ENABLED = 'yes'",
            "",
            "def register(registry):",
            "    registry.register('excel_backend.pandas', 'half-initialized-provider')",
            "    raise RuntimeError('boom-after-register')",
        ],
    )

    try:
        st = PluginManager.load_from_base_dir(tmpdir, conn=None, logger=None)
        statuses = {s["plugin_id"]: s for s in (st.get("statuses") or [])}

        bad = statuses.get("half_bad_plugin")
        assert bad is not None, f"未找到 half_bad_plugin 状态：{statuses!r}"
        assert bad["loaded"] == "no", f"register 抛错的插件 loaded 应为 no：{bad!r}"
        assert bad["capabilities"] == [], f"loaded=no 的插件不得上报能力：{bad!r}"
        assert "boom-after-register" in str(bad.get("error") or ""), f"错误信息应可见：{bad!r}"

        reg = get_plugin_registry()
        assert reg.get("excel_backend.pandas") is None, "register 失败后能力仍残留 registry（半初始化 provider 未回滚）"
        assert "excel_backend.pandas" not in reg.capability_owners, "register 失败后 capability_owners 仍残留"
        assert "excel_backend.pandas" not in (st.get("registry") or {}).get("capabilities", []), "状态页 registry 快照仍残留失败插件能力"

        # 健康插件不受回滚误伤
        healthy = statuses.get("healthy_plugin")
        assert healthy is not None and healthy["loaded"] == "yes", f"健康插件状态异常：{healthy!r}"
        assert reg.get("probe.healthy") == "healthy-provider", "回滚误伤了健康插件已注册的能力"

        # Excel 后端路由不受影响：auto 模式回到 openpyxl，而不是半初始化 provider
        backend = get_excel_backend("auto")
        assert isinstance(backend, OpenpyxlBackend), f"auto 模式应降回 openpyxl，实际={type(backend)!r}"
    finally:
        reset_plugin_state()


def test_register_failure_leaves_no_first_loaded_wins_residue_blocking_reregistration() -> None:

    from core.plugins.manager import PluginManager, get_plugin_registry, reset_plugin_state

    tmpdir = _make_plugins_dir()
    plugins_dir = os.path.join(tmpdir, "plugins")

    # 插件 A（先加载）：注册 excel_backend.pandas 后抛错——若无回滚，残留 key 会以
    # first_loaded_wins 挡住后面的健康插件
    _write_plugin(
        plugins_dir,
        "a_half_bad_plugin.py",
        [
            "PLUGIN_ID = 'half_bad_plugin'",
            "PLUGIN_DEFAULT_ENABLED = 'yes'",
            "",
            "def register(registry):",
            "    registry.register('excel_backend.pandas', 'half-initialized-provider')",
            "    raise RuntimeError('boom-after-register')",
        ],
    )
    # 插件 B（后加载）：健康插件，注册同名能力，应成功接管
    _write_plugin(
        plugins_dir,
        "b_reclaim_plugin.py",
        [
            "PLUGIN_ID = 'reclaim_plugin'",
            "PLUGIN_DEFAULT_ENABLED = 'yes'",
            "",
            "def register(registry):",
            "    registry.register('excel_backend.pandas', 'reclaim-provider')",
        ],
    )

    try:
        st = PluginManager.load_from_base_dir(tmpdir, conn=None, logger=None)
        statuses = {s["plugin_id"]: s for s in (st.get("statuses") or [])}

        reclaim = statuses.get("reclaim_plugin")
        assert reclaim is not None and reclaim["loaded"] == "yes", f"健康插件状态异常：{reclaim!r}"
        assert reclaim["capabilities"] == ["excel_backend.pandas"], f"健康插件应成功注册同名能力：{reclaim!r}"
        assert reclaim["conflicted_capabilities"] == [], f"回滚后不应产生冲突记录：{reclaim!r}"

        reg = get_plugin_registry()
        assert reg.get("excel_backend.pandas") == "reclaim-provider", "失败插件残留 key 挡住了健康插件的同名注册"
        assert reg.capability_owners.get("excel_backend.pandas") == "reclaim_plugin"
        assert st.get("conflicted_capabilities") == [], f"不应留下冲突记录：{st.get('conflicted_capabilities')!r}"
    finally:
        reset_plugin_state()
