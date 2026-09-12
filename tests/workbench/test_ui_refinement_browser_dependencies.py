"""Partial browser fixtures keep required shared globals in production order."""

from tests._support.workbench_browser_contract import REQUIRED_INPUTS, component_inputs


def test_independent_navigation_models_do_not_load_rendering_helpers():
    assert component_inputs(("frontend/workbench/app/WorkbenchNavigation.js",)) == (
        "frontend/workbench/app/WorkbenchNavigation.js",)
    assert len(REQUIRED_INPUTS) == 3


def test_list_and_detail_controls_follow_resource_controls_once():
    prefix = "static/workbench/app/"
    values = component_inputs((prefix + "resource-contract.js", prefix + "ResourceControls.js",
                               prefix + "ResourceForms.js", prefix + "WorkbenchListControls.js"))
    assert values == tuple(prefix + name + ".js" for name in (
        "resource-contract", "WorkbenchGuards", "WorkbenchReferences", "ResourceControls", "ResourceForms", "WorkbenchControlBridge", "WorkbenchControls", "WorkbenchListControls"))
