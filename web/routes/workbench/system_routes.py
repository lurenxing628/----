"""Host-owned registration: import and call once, without changing global __init__."""


def register_system_maintenance_routes(bp):
    from .system_actions import system_config_save, system_file_action, system_job_result, system_result
    from .system_backup_export import system_backup_export
    from .system_exports import system_log_export
    from .system_reads import system_collection, system_config_read

    base = "/api/workbench/v1/system"
    for kind in ("backups", "logs"):
        bp.add_url_rule(base + "/" + kind, endpoint="system_" + kind + "_read", view_func=system_collection,
                        defaults={"kind": kind}, methods=["GET"])
    bp.add_url_rule(base + "/config", view_func=system_config_read, methods=["GET"])
    bp.add_url_rule(base + "/config/save", view_func=system_config_save, methods=["POST"])
    for action in ("create", "delete", "restore"):
        bp.add_url_rule(base + "/backups/" + action, endpoint="system_backup_" + action, view_func=system_file_action,
                        defaults={"action": action}, methods=["POST"])
    bp.add_url_rule(base + "/backups/<backup_ref>/download", view_func=system_backup_export, methods=["GET"])
    bp.add_url_rule(base + "/results/<request_key>", view_func=system_result, methods=["GET"])
    bp.add_url_rule(base + "/jobs/<job_ref>", view_func=system_job_result, methods=["GET"])
    for format_name in ("csv", "zip"):
        bp.add_url_rule(base + "/logs/export/" + format_name, endpoint="system_logs_" + format_name,
                        view_func=system_log_export, defaults={"format_name": format_name}, methods=["GET"])
