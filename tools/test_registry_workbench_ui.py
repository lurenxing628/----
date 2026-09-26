"""Workbench UI source contracts; real browser evidence remains explicit opt-in."""

WORKBENCH_UI_REQUIRED_TESTS = (
    "tests/workbench/test_style_build_sources.py",
    "tests/workbench/test_ui_refinement_style_gate.py",
    "tests/workbench/test_ui_refinement_node_contracts.py",
    # 2026-09-21 弹窗关闭后焦点回到启动器/工作区容器、tooltip 原因按钮 aria-disabled 的 vm 合同。
    "tests/workbench/test_modal_focus_restore_contract.py",
    # 2026-09-21 新增工种弹窗“刷新最新资料”后仍可保存的 vm 合同（编译组件 + 最小 hooks 运行时）。
    "tests/workbench/test_process_op_type_create_contract.py",
    # 2026-09-21 现场报工“填 0 / 填剩余数”只填草稿不写入的 vm 合同。
    "tests/workbench/test_field_editor_fill_contract.py",
    "tests/workbench/test_ui_refinement_evidence_contract.py",
    "tests/workbench/test_ui_refinement_browser_dependencies.py",
    "tests/gate_meta/test_daily_ui_refinement_opt_in.py",
    "tests/gate_meta/test_workbench_ui_registry.py",
    "tests/workbench/test_ui_copy_glossary.py",
    "tests/workbench/test_handler_memory.py",
    "tests/workbench/test_run_progress_ledger.py",
    "tests/workbench/test_workbench_delete_icons.py",
)

WORKBENCH_UI_BROWSER_TARGETS = (
    "tests/workbench/test_ui_refinement_geometry.py",
    "tests/workbench/test_ui_navigation_guard.py",
    "tests/workbench/test_shared_controls_widgets.py",
    "tests/workbench/test_dashboard_ui_refinement.py",
)

# Runtime-backed companions remain explicit selections; none joins default required tests.
WORKBENCH_UI_SUPPLEMENTAL_TESTS = (
    *WORKBENCH_UI_BROWSER_TARGETS,
    "tests/workbench/test_dirty_guard_widgets.py",
    "tests/workbench/test_ui_refinement_reports_review.py",
    "tests/workbench/test_wbui_actual_keyboard.py",
    "tests/workbench/test_wbui_plan_first_screen.py",
    "tests/workbench/test_wbui_plan_gantt_models.py",
    "tests/workbench/test_short_screen_layout.py",
    "tests/workbench/test_workbench_visual_controls.py",
    "tests/workbench/test_operator_machine_permissions_widgets.py",
    "tests/workbench/test_plan_print.py",
    "tests/workbench/test_candidate_print_regressions.py",
    "tests/workbench/test_trial_microsecond_editor.py",
    "tests/workbench/test_resource_rail_storage.py",
    "tests/workbench/test_workbench_print_values.py",
)

WORKBENCH_UI_REQUIRED_REGRESSION_GROUPS = ({
    "group_id": "workbench_ui_refinement",
    "label": "Workbench UI build, styles, format, terms, density and evidence contracts",
    "target_paths": WORKBENCH_UI_REQUIRED_TESTS,
    "input_file_scopes": (
        "frontend/workbench/app/*.js", "frontend/workbench/app/*.jsx", "frontend/workbench/app/styles/*.css",
        "scripts/workbench/build.py", "scripts/workbench/asset_sources.py", "scripts/workbench/build-order.json",
        "static/workbench/asset-manifest.json", "templates/workbench/index.html",
        "tests/workbench-*.cjs", "tests/workbench/ui_refinement_*.py", "tests/workbench/ui_refinement_*.cjs",
        "tests/workbench/analysis_ui_contract.cjs",
        "tests/_support/workbench_browser_contract.py", "tests/_support/workbench_browser_probe.cjs",
        "tests/workbench/handler_memory_probe.cjs", "tests/workbench/deletion_icon_contract.cjs",
        "tests/workbench/modal_focus_restore_contract.cjs", "tests/workbench/process_op_type_create_contract.cjs",
        "tests/workbench/field_editor_fill_contract.cjs",
        "core/services/workbench/run/progress.py", "core/services/workbench/run/jobs.py", "core/services/workbench/run/worker.py",
        "core/services/scheduler/run/schedule_candidate_runner.py",
        # 文案词表（test_ui_copy_glossary.py）扫的是 tools/ui_copy_glossary.json 里那四类范围，
        # 而这里原来只覆盖了 frontend 一类：改说明书、改工作台服务层的提示语都不会触发它。
        # 2026-09-21 就这么把一个停用词写进说明书第 14 章，只有跑全目录才发现。
        # 词表本身改了同样要重扫。
        "tools/ui_copy_glossary.json", "tools/scan_ui_copy.py",
        "static/docs/scheduler_manual.md", "static/docs/aps_three_gap_user_guide.md",
        "templates/workbench/**/*.html", "templates/error.html", "templates/error_base.html",
        "core/services/workbench/**/*.py", "web/routes/workbench/*.py", "web/routes/workbench/**/*.py",
        # 2026-09-21 执行台账的 gap 提示直接上屏（现场记录详情、报表中心数据缺口列），词表扫描范围同步加了这里。
        "core/services/execution/*.py", "core/services/execution/**/*.py",
        # 2026-09-21 工艺定额锁定与模板来源的拒绝文案写在 core/services/process、core/services/scheduler 的共享策略模块里，
        # 经 core/services/workbench 适配层原样上屏（api_endpoint 直接 str(exc)），词表扫描范围同步加了这三个文件。
        "core/services/process/quota_protection.py",
        "core/services/scheduler/template_lineage.py", "core/services/scheduler/template_lineage_query.py",
        # 2026-09-21 工种/供应商/零件/批次领域服务的 BusinessError 经 _domain_failure 原样透出 exc.message，执行记录适配器的 AppError 经试调锚点 / 排产准入取 exc.message 上屏（原先是 str(exc)，会带错误码前缀），词表同步加了这五个文件。
        "core/services/process/op_type_service.py", "core/services/process/supplier_service.py", "core/services/process/part_service.py",
        "core/services/batch/service.py", "core/services/scheduler/execution/execution_ledger_adapter.py",
        # 2026-09-21 设备/人员领域服务的 BusinessError 同样经 resource/entities.py 的 create/delete → _domain_failure 透出 exc.message；班组服务当前没有工作台入口，为让整文件扫描归零一并纳入。词表同步加了这三个文件。
        "core/services/equipment/machine_service.py", "core/services/personnel/operator_service.py",
        "core/services/personnel/resource_team_service.py",
        "frontend/workbench/prototype/ui_kits/workbench/*.jsx",
        "frontend/workbench/prototype/ui_kits/workbench/*.js",
        "frontend/workbench/prototype/ui_kits/workbench/assets/*.js",
        "core/models/workbench_*.py", "web/error_boundary.py", "web/error_handlers.py",
        "web/bootstrap/workbench_*.py", "data/repositories/workbench_run_repo.py",
    ),
    "env_keys": ("WORKBENCH_NODE", "NODE_PATH", "node_executable_realpath", "node_version"),
},)

WORKBENCH_UI_SUPPLEMENTAL_REGRESSION_GROUPS = ({
    "group_id": "workbench_ui_refinement_browser",
    "label": "Workbench UI browser and installed-runtime component probes; explicit selection only",
    "target_paths": WORKBENCH_UI_SUPPLEMENTAL_TESTS,
    "input_file_scopes": (
        "frontend/workbench/app/*.js", "frontend/workbench/app/*.jsx", "frontend/workbench/app/styles/*.css",
        "frontend/workbench/prototype/**/*", "frontend/workbench/vendor/**/*", "static/workbench/**/*",
        "scripts/workbench/*.py", "scripts/workbench/*.cjs", "scripts/workbench/build-order.json",
        "tests/workbench/ui_refinement_*.cjs", "tests/workbench/shared_controls_probe.cjs",
        "tests/workbench/dirty_guard_probe.cjs", "tests/workbench/dirty_guard_fixture.jsx",
        "tests/workbench/wbui_actual_keyboard_probe.cjs",
        "tests/workbench/wbui_plan_first_screen_probe.cjs", "tests/workbench/test_wbui_plan_gantt_models.cjs",
        "tests/workbench/wbui_gantt_display_format.cjs",
        "tests/workbench/plan_ui_*.cjs", "tests/workbench/test_plan_ui.py",
        "tests/workbench/dashboard_widgets_probe.cjs", "tests/workbench/*_support.py",
        "tests/workbench/test_live_browser.py", "tests/workbench/live_environment.py",
        "tests/workbench/short_screen_layout_probe.cjs",
        "tests/workbench/operator_machine_permissions_probe.cjs",
        "tests/workbench/test_candidate_print_regressions.cjs",
        "tests/workbench/test_trial_microsecond_editor.cjs",
        "tests/workbench/test_plan_print.cjs", "tests/workbench/test_resource_rail_storage.cjs",
        "tests/workbench/workbench_print_values.cjs",
        "tests/conftest.py", "tests/workbench/fixtures/schema-v28.sql", "schema.sql",
        "tests/_support/workbench_browser_contract.py", "tests/_support/workbench_browser_probe.cjs",
        "tests/_support/workbench_web_contract.py", "tests/_support/excel_templates.py",
        "app.py", "web/bootstrap/app_config.py", "plugins/*.py", "core/plugins/manager.py", "web/bootstrap/**/*.py",
        "web/routes/workbench/pages.py", "web/routes/workbench/assets.py", "web/routes/workbench/registration.py",
        "web/routes/workbench/navigation_boot.py", "web/routes/workbench/navigation_metadata.py",
        "templates/workbench/index.html",
        "tests/gate_meta/workbench_round1_registry_support.py",
    ),
    # Runtime identity probes track PATH resolution; an irrelevant PATH append is not a new input.
    "env_keys": ("WORKBENCH_NODE", "WORKBENCH_BROWSER", "NODE_PATH", "NODE_OPTIONS", "HOME",
                 "APS_SYSTEM_JOURNAL_DIR", "APS_STATIC_VERSION", "SECRET_KEY", "WERKZEUG_RUN_MAIN",
                 "node_executable_realpath", "node_version"),
},)
