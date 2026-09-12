"""Workbench UI source contracts; real browser evidence remains explicit opt-in."""

WORKBENCH_UI_REQUIRED_TESTS = (
    "tests/workbench/test_style_build_sources.py",
    "tests/workbench/test_ui_refinement_style_gate.py",
    "tests/workbench/test_ui_refinement_node_contracts.py",
    "tests/workbench/test_ui_refinement_evidence_contract.py",
    "tests/workbench/test_ui_refinement_browser_dependencies.py",
    "tests/gate_meta/test_daily_ui_refinement_opt_in.py",
    "tests/gate_meta/test_workbench_ui_registry.py",
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
        "tests/conftest.py", "tests/workbench/fixtures/schema-v28.sql", "schema.sql",
        "tests/_support/workbench_browser_contract.py", "tests/_support/workbench_browser_probe.cjs",
        "tests/_support/workbench_web_contract.py", "tests/_support/excel_templates.py",
        "app.py", "config.py", "plugins/*.py", "core/plugins/manager.py", "web/bootstrap/**/*.py",
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
