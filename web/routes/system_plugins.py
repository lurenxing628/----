from __future__ import annotations

import re

from flask import current_app, flash, g, redirect, request, url_for

from core.services.system import SystemConfigService

from .system_bp import bp


@bp.post("/plugins/toggle")
def plugin_toggle():
    """
    保存插件开关（写入 SystemConfig：plugin.<id>.enabled）。

    说明：插件是在应用启动时加载，因此修改后需要重启应用才能生效。
    """
    plugin_id = (request.form.get("plugin_id") or "").strip()
    if not plugin_id:
        flash("缺少 plugin_id。", "error")
        return redirect(url_for("system.backup_page"))

    if not re.fullmatch(r"[A-Za-z0-9_-]+", plugin_id):
        flash("plugin_id 不合法（仅允许字母数字、_、-）。", "error")
        return redirect(url_for("system.backup_page"))

    enabled = "yes" if (request.form.get("enabled") or "").strip().lower() in ("on", "yes", "true", "1") else "no"
    key = f"plugin.{plugin_id}.enabled"
    SystemConfigService(g.db, logger=current_app.logger).set_value(key, enabled, description=None)

    if getattr(g, "op_logger", None) is not None:
        g.op_logger.info(
            module="plugins",
            action="toggle",
            target_type="plugin",
            target_id=plugin_id,
            detail={"enabled": enabled, "note": "修改后需重启应用生效"},
        )

    flash(f"插件开关已保存：{plugin_id} = {enabled}（重启后生效）", "success")
    return redirect(url_for("system.backup_page"))

