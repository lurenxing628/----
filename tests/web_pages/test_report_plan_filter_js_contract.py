"""回归测试：static/js/report_plan_filter.js 的场景保持契约——在 Node 桩里驱动版本/计划角色下拉的 change/submit 事件，验证改动 version 会清空 scenario_id、改回初始 version 才恢复 SCENARIO-RPT；但当 plan-role 也偏离初始值时，恢复 version 不应恢复 scenario，唯有 role 也改回初始并提交后才恢复。"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from tests._support.paths import REPO_ROOT


def test_report_plan_filter_restores_scenario_when_identity_returns_to_initial() -> None:
    source = (REPO_ROOT / "static" / "js" / "report_plan_filter.js").read_text(encoding="utf-8")
    harness = r"""
const listeners = {};
global.document = {addEventListener: (name, fn) => { listeners[name] = fn; }};
eval(process.env.REPORT_PLAN_FILTER_SOURCE);
function element(value, attrs) {
  return {
    value,
    attrs: Object.assign({}, attrs),
    form: null,
    hasAttribute(name) { return Object.prototype.hasOwnProperty.call(this.attrs, name); },
    getAttribute(name) { return this.attrs[name] || ""; },
    setAttribute(name, value) { this.attrs[name] = value; },
    matches(selector) {
      return selector.includes("data-report-plan-version-select") && this.hasAttribute("data-report-plan-version-select")
        || selector.includes("data-report-plan-role-select") && this.hasAttribute("data-report-plan-role-select");
    },
  };
}
const version = element("12", {"data-report-plan-version-select": "", "data-initial-version": "12"});
const role = element("adopted", {"data-report-plan-role-select": "", "data-initial-plan-role": "adopted"});
const scenario = element("SCENARIO-RPT", {});
const form = {
  querySelector(selector) { return selector === 'input[name="scenario_id"]' ? scenario : null; },
  querySelectorAll() { return [version, role]; },
};
version.form = role.form = form;
version.value = "13";
listeners.change({target: version});
if (scenario.value !== "") throw new Error("changed version must clear scenario");
version.value = "12";
listeners.change({target: version});
if (scenario.value !== "SCENARIO-RPT") throw new Error("restored version must restore scenario");
role.value = "baseline_best";
listeners.submit({target: form});
if (scenario.value !== "") throw new Error("changed role must clear scenario before submit");
version.value = "13";
listeners.change({target: version});
version.value = "12";
listeners.change({target: version});
if (scenario.value !== "") throw new Error("restored version must not restore scenario while role changed");
role.value = "adopted";
listeners.submit({target: form});
if (scenario.value !== "SCENARIO-RPT") throw new Error("restored role must restore scenario before submit");
console.log(JSON.stringify({scenario_id: scenario.value}));
"""
    result = subprocess.run(
        ["node", "-e", harness],
        cwd=str(REPO_ROOT),
        env={**os.environ, "REPORT_PLAN_FILTER_SOURCE": source},
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(result.stdout)["scenario_id"] == "SCENARIO-RPT"
