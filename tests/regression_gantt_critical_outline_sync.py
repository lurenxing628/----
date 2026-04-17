from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_node_outline_check(outline_js_path: Path) -> dict:
    node_code = r"""
const fs = require("fs");

const outlinePath = String(process.env.APS_GANTT_OUTLINE_JS || "");
if (!outlinePath) {
  console.error("APS_GANTT_OUTLINE_JS missing");
  process.exit(2);
}

class FakeClassList {
  constructor(owner) {
    this.owner = owner;
    this.values = new Set();
  }
  add(...names) {
    names.forEach((name) => {
      if (name) this.values.add(String(name));
    });
  }
  remove(...names) {
    names.forEach((name) => this.values.delete(String(name)));
  }
  contains(name) {
    return this.values.has(String(name));
  }
  toggle(name, force) {
    const key = String(name);
    if (typeof force === "boolean") {
      if (force) this.values.add(key);
      else this.values.delete(key);
      return force;
    }
    if (this.values.has(key)) {
      this.values.delete(key);
      return false;
    }
    this.values.add(key);
    return true;
  }
}

class FakeNode {
  constructor(tagName) {
    this.tagName = String(tagName || "").toLowerCase();
    this.children = [];
    this.parentNode = null;
    this.attrs = Object.create(null);
    this.classList = new FakeClassList(this);
    this.style = { setProperty() {} };
    this.isConnected = true;
  }

  appendChild(child) {
    if (!child) return child;
    child.parentNode = this;
    this.children.push(child);
    return child;
  }

  insertBefore(child, ref) {
    if (!child) return child;
    child.parentNode = this;
    const idx = this.children.indexOf(ref);
    if (idx < 0) {
      this.children.push(child);
    } else {
      this.children.splice(idx, 0, child);
    }
    return child;
  }

  removeChild(child) {
    const idx = this.children.indexOf(child);
    if (idx >= 0) {
      this.children.splice(idx, 1);
      child.parentNode = null;
    }
    return child;
  }

  remove() {
    if (this.parentNode) {
      this.parentNode.removeChild(this);
    }
    this.isConnected = false;
  }

  setAttribute(name, value) {
    const key = String(name);
    const text = String(value);
    this.attrs[key] = text;
    if (key === "class") {
      this.classList = new FakeClassList(this);
      text.split(/\s+/).filter(Boolean).forEach((part) => this.classList.add(part));
    }
  }

  getAttribute(name) {
    return Object.prototype.hasOwnProperty.call(this.attrs, name) ? this.attrs[name] : null;
  }

  matches(selector) {
    const s = String(selector || "").trim();
    if (!s) return false;
    if (s.startsWith(".")) return this.classList.contains(s.slice(1));
    return this.tagName === s.toLowerCase();
  }

  querySelector(selector) {
    const found = this.querySelectorAll(selector);
    return found.length > 0 ? found[0] : null;
  }

  querySelectorAll(selector) {
    const selectors = String(selector || "")
      .split(",")
      .map((part) => part.trim())
      .filter(Boolean);
    const out = [];
    const visit = (node) => {
      if (!node || !Array.isArray(node.children)) return;
      node.children.forEach((child) => {
        if (selectors.some((sel) => child.matches(sel))) {
          out.push(child);
        }
        visit(child);
      });
    };
    visit(this);
    return out;
  }
}

global.window = {};
global.document = {
  createElementNS(_ns, tagName) {
    return new FakeNode(tagName);
  },
};

const code = fs.readFileSync(outlinePath, "utf8");
eval(code);

const api = window.__APS_GANTT_OUTLINE__;
if (!api) {
  console.error("window.__APS_GANTT_OUTLINE__ missing");
  process.exit(3);
}

const wrapper = new FakeNode("g");
wrapper.classList.add("bar-wrapper", "aps-critical");
wrapper.setAttribute("data-id", "T1");

const barGroup = new FakeNode("g");
barGroup.classList.add("bar-group");
wrapper.appendChild(barGroup);

const bar = new FakeNode("rect");
bar.classList.add("bar");
bar.setAttribute("x", "10");
bar.setAttribute("y", "20");
bar.setAttribute("width", "30");
bar.setAttribute("height", "12");
bar.setAttribute("rx", "4");
bar.setAttribute("ry", "4");
barGroup.appendChild(bar);

api.ensureCriticalOutlineNodes(wrapper);
api.syncCriticalOutlineGeometry(wrapper);

const outer1 = wrapper.querySelector(".aps-cc-outline-outer");
const inner1 = wrapper.querySelector(".aps-cc-outline-inner");
const firstState = {
  outerX: outer1 && outer1.getAttribute("x"),
  outerWidth: outer1 && outer1.getAttribute("width"),
  innerX: inner1 && inner1.getAttribute("x"),
  innerWidth: inner1 && inner1.getAttribute("width"),
  count: wrapper.querySelectorAll(".aps-cc-outline-outer, .aps-cc-outline-inner").length,
};

bar.setAttribute("x", "28");
bar.setAttribute("width", "46");
api.ensureCriticalOutlineNodes(wrapper);
api.syncCriticalOutlineGeometry(wrapper);

const outer2 = wrapper.querySelector(".aps-cc-outline-outer");
const inner2 = wrapper.querySelector(".aps-cc-outline-inner");
const secondState = {
  sameOuterRef: outer1 === outer2,
  sameInnerRef: inner1 === inner2,
  outerX: outer2 && outer2.getAttribute("x"),
  outerWidth: outer2 && outer2.getAttribute("width"),
  innerX: inner2 && inner2.getAttribute("x"),
  innerWidth: inner2 && inner2.getAttribute("width"),
  count: wrapper.querySelectorAll(".aps-cc-outline-outer, .aps-cc-outline-inner").length,
};

const barApi = {
  group: wrapper,
  $bar: bar,
  update_bar_position(payload) {
    if (payload && payload.x !== null && typeof payload.x !== "undefined") {
      bar.setAttribute("x", String(payload.x));
    }
    if (payload && payload.width !== null && typeof payload.width !== "undefined") {
      bar.setAttribute("width", String(payload.width));
    }
    return "ok";
  },
};

api.installCriticalOutlineSyncAdapter(
  { bars: [barApi] },
  {
    isCriticalWrapper(currentWrapper) {
      return !!(currentWrapper && currentWrapper.classList && currentWrapper.classList.contains("aps-critical"));
    },
  }
);

barApi.update_bar_position({ x: 60, width: 55 });

const outer3 = wrapper.querySelector(".aps-cc-outline-outer");
const inner3 = wrapper.querySelector(".aps-cc-outline-inner");
const adapterState = {
  outerX: outer3 && outer3.getAttribute("x"),
  outerWidth: outer3 && outer3.getAttribute("width"),
  innerX: inner3 && inner3.getAttribute("x"),
  innerWidth: inner3 && inner3.getAttribute("width"),
  count: wrapper.querySelectorAll(".aps-cc-outline-outer, .aps-cc-outline-inner").length,
};

api.setCriticalOutlineEnabled(wrapper, false);

const disabledCount = wrapper.querySelectorAll(".aps-cc-outline-outer, .aps-cc-outline-inner").length;

process.stdout.write(JSON.stringify({ firstState, secondState, adapterState, disabledCount }));
"""
    p = subprocess.run(
        ["node", "-"],
        input=node_code,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={"APS_GANTT_OUTLINE_JS": str(outline_js_path)},
    )
    if p.returncode != 0:
        raise RuntimeError(f"node 执行失败：rc={p.returncode} stderr={p.stderr[:500]!r}")
    return json.loads(p.stdout or "{}")


def test_outline_helper_is_shared_and_syncs_geometry_without_duplication() -> None:
    outline_js_path = REPO_ROOT / "static" / "js" / "gantt_outline.js"
    ret = _run_node_outline_check(outline_js_path)

    first_state = ret["firstState"]
    assert first_state["count"] == 2
    assert first_state["outerX"] == "8"
    assert first_state["outerWidth"] == "34"
    assert first_state["innerX"] == "9"
    assert first_state["innerWidth"] == "32"

    second_state = ret["secondState"]
    assert second_state["sameOuterRef"] is True
    assert second_state["sameInnerRef"] is True
    assert second_state["count"] == 2
    assert second_state["outerX"] == "26"
    assert second_state["outerWidth"] == "50"
    assert second_state["innerX"] == "27"
    assert second_state["innerWidth"] == "48"

    adapter_state = ret["adapterState"]
    assert adapter_state["count"] == 2
    assert adapter_state["outerX"] == "58"
    assert adapter_state["outerWidth"] == "59"
    assert adapter_state["innerX"] == "59"
    assert adapter_state["innerWidth"] == "57"

    assert ret["disabledCount"] == 0


def test_live_and_preview_wire_shared_outline_helper() -> None:
    render_js = (REPO_ROOT / "static" / "js" / "gantt_render.js").read_text(encoding="utf-8")
    preview_script = (REPO_ROOT / "tests" / "run_complex_case_and_export_gantt.py").read_text(encoding="utf-8")
    legacy_tpl = (REPO_ROOT / "templates" / "scheduler" / "gantt.html").read_text(encoding="utf-8")
    v2_tpl = (REPO_ROOT / "web_new_test" / "templates" / "scheduler" / "gantt.html").read_text(encoding="utf-8")

    assert "installCriticalOutlineSyncAdapter" in render_js
    assert "on_date_change" in render_js
    assert "on_progress_change" in render_js
    assert render_js.count("function upsertCriticalOutlines(") == 1
    assert "upsertCriticalOutlines = function" not in render_js

    assert "js/gantt_outline.js" in legacy_tpl
    assert "js/gantt_outline.js" in v2_tpl

    assert "../../static/js/gantt_outline.js" in preview_script
    assert "function upsertCriticalOutlines(" not in preview_script
    assert "_legacyUpsertCriticalOutlines" not in preview_script
