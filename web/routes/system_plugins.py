from __future__ import annotations

import re

from flask import flash, g, redirect, request, url_for

from .system_bp import bp
from .system_utils import _get_system_config_service


@bp.post("/plugins/toggle")
def plugin_toggle():
    """
    保存扩展功能开关（写入 SystemConfig 中对应的扩展功能配置）。

    说明：扩展功能是在应用启动时加载，因此修改后需要重启应用才能生效。
    """
    plugin_id = (request.form.get("plugin_id") or "").strip()
    if not plugin_id:
        flash("没有收到要修改的扩展功能编号，请刷新页面后重新操作。", "error")
        return redirect(url_for("system.backup_page"))

    if not re.fullmatch(r"[A-Za-z0-9_-]+", plugin_id):
        flash("扩展功能编号格式不正确。请刷新页面后重新操作；如果仍然出现，请联系管理员检查扩展功能配置。", "error")
        return redirect(url_for("system.backup_page"))

    enabled = "yes" if (request.form.get("enabled") or "").strip().lower() in ("on", "yes", "true", "1") else "no"
    key = f"plugin.{plugin_id}.enabled"
    svc = _get_system_config_service()
    svc.set_value(key, enabled, description=None)

    if getattr(g, "op_logger", None) is not None:
        g.op_logger.info(
            module="plugins",
            action="toggle",
            target_type="plugin",
            target_id=plugin_id,
            detail={"enabled": enabled, "note": "修改后需重启应用生效"},
        )

    enabled_label = "已开启" if enabled == "yes" else "已关闭"
    flash(f"扩展功能开关已保存，当前选择为{enabled_label}。重启软件后生效。", "success")
    return redirect(url_for("system.backup_page"))
