import os
import sys
import tempfile


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _write_plugin(path: str, *, plugin_id: str, capability: str, provider_name: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(
            "\n".join(
                [
                    f"PLUGIN_ID = '{plugin_id}'",
                    f"PLUGIN_NAME = '{plugin_id}'",
                    "PLUGIN_DEFAULT_ENABLED = 'yes'",
                    "",
                    "def register(registry):",
                    f"    registry.register('{capability}', '{provider_name}')",
                    "",
                ]
            )
        )


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.plugins.manager import PluginManager

    tmpdir = tempfile.mkdtemp(prefix="aps_regression_plugin_conflict_")
    plugins_dir = os.path.join(tmpdir, "plugins")
    os.makedirs(plugins_dir, exist_ok=True)

    _write_plugin(
        os.path.join(plugins_dir, "plugin_a.py"),
        plugin_id="plugin_a",
        capability="demo.capability",
        provider_name="provider_a",
    )
    _write_plugin(
        os.path.join(plugins_dir, "plugin_b.py"),
        plugin_id="plugin_b",
        capability="demo.capability",
        provider_name="provider_b",
    )

    status = PluginManager.load_from_base_dir(
        tmpdir,
        config_reader=lambda _plugin_id: "yes",
        logger=None,
    )

    assert isinstance(status, dict), status
    assert "statuses" in status and "registry" in status and "plugins_dir" in status, status
    assert status.get("plugins_dir") == os.path.join(tmpdir, "plugins"), status
    assert status.get("conflict_policy") == "first_loaded_wins", status

    registry = dict(status.get("registry") or {})
    capabilities = list(registry.get("capabilities") or [])
    assert capabilities == ["demo.capability"], registry

    conflicts = list(status.get("conflicted_capabilities") or [])
    assert len(conflicts) == 1, conflicts
    conflict = conflicts[0]
    assert conflict.get("capability") == "demo.capability", conflict
    assert conflict.get("kept_plugin_id") == "plugin_a", conflict
    assert conflict.get("rejected_plugin_id") == "plugin_b", conflict
    assert conflict.get("policy") == "first_loaded_wins", conflict

    statuses = list(status.get("statuses") or [])
    plugin_a = next((item for item in statuses if item.get("plugin_id") == "plugin_a"), None)
    plugin_b = next((item for item in statuses if item.get("plugin_id") == "plugin_b"), None)
    assert plugin_a is not None and plugin_b is not None, statuses
    assert plugin_a.get("loaded") == "yes", plugin_a
    assert plugin_a.get("capabilities") == ["demo.capability"], plugin_a
    assert plugin_a.get("conflicted_capabilities") == [], plugin_a
    assert plugin_b.get("loaded") == "yes", plugin_b
    assert plugin_b.get("capabilities") == [], plugin_b
    assert plugin_b.get("conflicted_capabilities") == ["demo.capability"], plugin_b

    print("OK")


if __name__ == "__main__":
    main()
