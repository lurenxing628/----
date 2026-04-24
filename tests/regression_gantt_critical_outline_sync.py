from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_gantt_contract_clears_unavailable_critical_chain_payload() -> None:
    from core.services.scheduler.gantt_contract import build_gantt_contract

    payload = build_gantt_contract(
        contract_version=1,
        tasks=[],
        calendar_days=[],
        view="machine",
        version=7,
        week_start="2026-04-13",
        week_end="2026-04-19",
        critical_chain={
            "available": False,
            "reason": "repo_exception",
            "reason_code": "repo_exception",
            "ids": ["RAW-1"],
            "edges": [{"from": "RAW-1", "to": "RAW-2"}],
            "edge_count": 1,
            "cache_hit": False,
        },
    )

    critical_chain = payload["critical_chain"]
    assert critical_chain["available"] is False
    assert critical_chain["ids"] == []
    assert critical_chain["edges"] == []
    assert critical_chain["edge_count"] == 0
    assert critical_chain["reason_code"] == "repo_exception"
    assert critical_chain["reason"] == "关键链计算异常"


DOM_SHIM_JS = r"""
const fs = require("fs");
const vm = require("vm");
const SVG_NS = "http://www.w3.org/2000/svg";

function datasetKey(name) {
  return String(name || "")
    .replace(/^data-/, "")
    .replace(/-([a-z])/g, (_m, ch) => ch.toUpperCase());
}

function makeStyle() {
  return {
    setProperty(name, value) {
      this[String(name)] = String(value);
    },
    removeProperty(name) {
      delete this[String(name)];
    },
    getPropertyValue(name) {
      return this[String(name)] || "";
    },
  };
}

class FakeClassList {
  constructor(owner) {
    this.owner = owner;
    this.values = new Set();
  }

  _syncAttr() {
    this.owner.attrs["class"] = Array.from(this.values).join(" ");
  }

  _setFromText(text) {
    this.values = new Set(String(text || "").split(/\s+/).filter(Boolean));
    this._syncAttr();
  }

  add(...names) {
    names.forEach((name) => {
      const text = String(name || "").trim();
      if (text) this.values.add(text);
    });
    this._syncAttr();
  }

  remove(...names) {
    names.forEach((name) => this.values.delete(String(name || "").trim()));
    this._syncAttr();
  }

  contains(name) {
    return this.values.has(String(name || "").trim());
  }

  toggle(name, force) {
    const text = String(name || "").trim();
    if (!text) return false;
    if (typeof force === "boolean") {
      if (force) this.values.add(text);
      else this.values.delete(text);
      this._syncAttr();
      return force;
    }
    if (this.values.has(text)) {
      this.values.delete(text);
      this._syncAttr();
      return false;
    }
    this.values.add(text);
    this._syncAttr();
    return true;
  }

  toString() {
    return Array.from(this.values).join(" ");
  }
}

class FakeEvent {
  constructor(type) {
    this.type = type || "";
    this.bubbles = true;
    this.cancelable = true;
    this.defaultPrevented = false;
    this.target = null;
    this.currentTarget = null;
  }

  initEvent(type, bubbles, cancelable) {
    this.type = type || "";
    this.bubbles = !!bubbles;
    this.cancelable = !!cancelable;
  }

  preventDefault() {
    if (this.cancelable) {
      this.defaultPrevented = true;
    }
  }
}

function simpleSelectorTokens(selector) {
  return String(selector || "").trim().match(/[#.]?[A-Za-z0-9_-]+/g) || [];
}

function matchesSimpleSelector(node, selector) {
  const text = String(selector || "").trim();
  if (!text || text === "*") return true;
  if (!node || node.nodeType !== 1) return false;
  const tokens = simpleSelectorTokens(text);
  if (tokens.length === 0) return false;
  let tag = "";
  let id = "";
  const classes = [];
  tokens.forEach((token) => {
    if (token.startsWith("#")) id = token.slice(1);
    else if (token.startsWith(".")) classes.push(token.slice(1));
    else tag = token.toLowerCase();
  });
  if (tag && node.tagName !== tag) return false;
  if (id && node.getAttribute("id") !== id) return false;
  return classes.every((cls) => node.classList.contains(cls));
}

function matchesSelector(node, selector) {
  return String(selector || "")
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean)
    .some((part) => {
      const chain = part.split(/\s+/).filter(Boolean);
      if (chain.length === 0) return false;
      let current = node;
      if (!matchesSimpleSelector(current, chain[chain.length - 1])) return false;
      for (let index = chain.length - 2; index >= 0; index -= 1) {
        current = current.parentNode;
        while (current && !matchesSimpleSelector(current, chain[index])) {
          current = current.parentNode;
        }
        if (!current) return false;
      }
      return true;
    });
}

function numericAttr(node, name, fallback) {
  const raw = Number(node && typeof node.getAttribute === "function" ? node.getAttribute(name) : NaN);
  return Number.isFinite(raw) ? raw : fallback;
}

function mergeBoxes(boxes) {
  const usable = boxes.filter((box) => box && Number.isFinite(box.width) && Number.isFinite(box.height));
  if (usable.length === 0) {
    return { x: 0, y: 0, width: 0, height: 0 };
  }
  let minX = usable[0].x;
  let minY = usable[0].y;
  let maxX = usable[0].x + usable[0].width;
  let maxY = usable[0].y + usable[0].height;
  usable.slice(1).forEach((box) => {
    minX = Math.min(minX, box.x);
    minY = Math.min(minY, box.y);
    maxX = Math.max(maxX, box.x + box.width);
    maxY = Math.max(maxY, box.y + box.height);
  });
  return { x: minX, y: minY, width: maxX - minX, height: maxY - minY };
}

class FakeNodeBase {
  constructor() {
    this.parentNode = null;
    this.ownerDocument = null;
    this.isConnected = false;
    this._listeners = Object.create(null);
  }

  _setConnected(flag) {
    this.isConnected = !!flag;
    const children = Array.isArray(this.children) ? this.children : [];
    children.forEach((child) => child._setConnected(!!flag));
  }

  addEventListener(type, listener) {
    const key = String(type || "");
    if (!this._listeners[key]) this._listeners[key] = [];
    this._listeners[key].push(listener);
  }

  removeEventListener(type, listener) {
    const key = String(type || "");
    const list = this._listeners[key];
    if (!list) return;
    const index = list.indexOf(listener);
    if (index >= 0) list.splice(index, 1);
  }

  dispatchEvent(event) {
    const evt = event || new FakeEvent("");
    if (!evt.target) evt.target = this;
    evt.currentTarget = this;
    const list = (this._listeners[evt.type] || []).slice();
    list.forEach((listener) => listener.call(this, evt));
    if (evt.bubbles && this.parentNode) {
      this.parentNode.dispatchEvent(evt);
    }
    return !evt.defaultPrevented;
  }
}

class FakeElement extends FakeNodeBase {
  constructor(tagName, namespaceURI) {
    super();
    this.nodeType = 1;
    this.tagName = String(tagName || "").toLowerCase();
    this.nodeName = this.tagName.toUpperCase();
    this.namespaceURI = namespaceURI || null;
    this.attrs = Object.create(null);
    this.children = [];
    this.style = makeStyle();
    this.classList = new FakeClassList(this);
    this.dataset = {};
    this._textContent = "";
    this.clientWidth = 0;
    this.clientHeight = 0;
    this.scrollLeft = 0;
  }

  get parentElement() {
    return this.parentNode;
  }

  get childNodes() {
    return this.children;
  }

  get firstChild() {
    return this.children.length > 0 ? this.children[0] : null;
  }

  get lastChild() {
    return this.children.length > 0 ? this.children[this.children.length - 1] : null;
  }

  get className() {
    return this.classList.toString();
  }

  set className(value) {
    this.setAttribute("class", value);
  }

  get textContent() {
    if (this.children.length === 0) return this._textContent;
    return this.children.map((child) => child.textContent || "").join("");
  }

  set textContent(value) {
    this.children = [];
    this._textContent = String(value ?? "");
  }

  get innerHTML() {
    return this.textContent;
  }

  set innerHTML(value) {
    const text = String(value ?? "");
    this.children = [];
    this._textContent = text.replace(/<[^>]+>/g, "");
  }

  appendChild(child) {
    if (!child) return child;
    if (child.nodeType === 11) {
      child.children.slice().forEach((node) => this.appendChild(node));
      child.children = [];
      return child;
    }
    if (child.parentNode) {
      child.parentNode.removeChild(child);
    }
    child.parentNode = this;
    child.ownerDocument = this.ownerDocument;
    this.children.push(child);
    child._setConnected(this.isConnected);
    return child;
  }

  insertBefore(child, ref) {
    if (!child) return child;
    if (child.nodeType === 11) {
      child.children.slice().forEach((node) => this.insertBefore(node, ref));
      child.children = [];
      return child;
    }
    if (child.parentNode) {
      child.parentNode.removeChild(child);
    }
    child.parentNode = this;
    child.ownerDocument = this.ownerDocument;
    const index = ref ? this.children.indexOf(ref) : -1;
    if (index < 0) this.children.push(child);
    else this.children.splice(index, 0, child);
    child._setConnected(this.isConnected);
    return child;
  }

  removeChild(child) {
    const index = this.children.indexOf(child);
    if (index >= 0) {
      this.children.splice(index, 1);
      child.parentNode = null;
      child._setConnected(false);
    }
    return child;
  }

  remove() {
    if (this.parentNode) {
      this.parentNode.removeChild(this);
    }
  }

  setAttribute(name, value) {
    const key = String(name);
    const text = String(value);
    this.attrs[key] = text;
    if (key === "class") this.classList._setFromText(text);
    if (key.startsWith("data-")) this.dataset[datasetKey(key)] = text;
    if (key === "width" && !this.clientWidth) this.clientWidth = numericAttr(this, "width", 0);
    if (key === "height" && !this.clientHeight) this.clientHeight = numericAttr(this, "height", 0);
  }

  getAttribute(name) {
    const key = String(name);
    if (key === "class") return this.classList.toString() || null;
    return Object.prototype.hasOwnProperty.call(this.attrs, key) ? this.attrs[key] : null;
  }

  removeAttribute(name) {
    const key = String(name);
    delete this.attrs[key];
    if (key === "class") this.classList._setFromText("");
    if (key.startsWith("data-")) delete this.dataset[datasetKey(key)];
  }

  matches(selector) {
    return matchesSelector(this, selector);
  }

  closest(selector) {
    let current = this;
    while (current) {
      if (current.nodeType === 1 && current.matches(selector)) return current;
      current = current.parentNode;
    }
    return null;
  }

  querySelectorAll(selector) {
    const out = [];
    const visit = (node) => {
      if (!node || !Array.isArray(node.children)) return;
      node.children.forEach((child) => {
        if (child.matches(selector)) out.push(child);
        visit(child);
      });
    };
    visit(this);
    return out;
  }

  querySelector(selector) {
    const list = this.querySelectorAll(selector);
    return list.length > 0 ? list[0] : null;
  }

  getBBox() {
    if (this.tagName === "rect") {
      return {
        x: numericAttr(this, "x", 0),
        y: numericAttr(this, "y", 0),
        width: numericAttr(this, "width", 0),
        height: numericAttr(this, "height", 0),
      };
    }
    if (this.tagName === "line") {
      const x1 = numericAttr(this, "x1", 0);
      const y1 = numericAttr(this, "y1", 0);
      const x2 = numericAttr(this, "x2", 0);
      const y2 = numericAttr(this, "y2", 0);
      return {
        x: Math.min(x1, x2),
        y: Math.min(y1, y2),
        width: Math.abs(x2 - x1),
        height: Math.abs(y2 - y1),
      };
    }
    if (this.tagName === "text") {
      const text = this.textContent || "";
      return {
        x: numericAttr(this, "x", 0),
        y: numericAttr(this, "y", 0) - 10,
        width: Math.max(text.length * 7, 1),
        height: 14,
      };
    }
    if (this.tagName === "polygon") {
      const points = String(this.getAttribute("points") || "")
        .split(/\s+/)
        .filter(Boolean)
        .map((part) => part.split(",").map((value) => Number(value)));
      const xs = points.map((pair) => pair[0]).filter(Number.isFinite);
      const ys = points.map((pair) => pair[1]).filter(Number.isFinite);
      if (xs.length > 0 && ys.length > 0) {
        return {
          x: Math.min(...xs),
          y: Math.min(...ys),
          width: Math.max(...xs) - Math.min(...xs),
          height: Math.max(...ys) - Math.min(...ys),
        };
      }
    }
    if (this.tagName === "path") {
      const nums = String(this.getAttribute("d") || "")
        .match(/-?\d+(?:\.\d+)?/g) || [];
      const values = nums.map((value) => Number(value)).filter(Number.isFinite);
      const xs = [];
      const ys = [];
      for (let index = 0; index < values.length; index += 2) {
        xs.push(values[index]);
        if (index + 1 < values.length) ys.push(values[index + 1]);
      }
      if (xs.length > 0 && ys.length > 0) {
        return {
          x: Math.min(...xs),
          y: Math.min(...ys),
          width: Math.max(...xs) - Math.min(...xs),
          height: Math.max(...ys) - Math.min(...ys),
        };
      }
    }
    if (this.children.length > 0) {
      return mergeBoxes(this.children.map((child) => child.getBBox()));
    }
    return {
      x: numericAttr(this, "x", 0),
      y: numericAttr(this, "y", 0),
      width: numericAttr(this, "width", this.clientWidth || 0),
      height: numericAttr(this, "height", this.clientHeight || 0),
    };
  }

  getBoundingClientRect() {
    const box = this.getBBox();
    const width = box.width || this.clientWidth || 1200;
    const height = box.height || this.clientHeight || 32;
    return {
      x: box.x || 0,
      y: box.y || 0,
      width: width,
      height: height,
      top: box.y || 0,
      left: box.x || 0,
      right: (box.x || 0) + width,
      bottom: (box.y || 0) + height,
    };
  }
}

class FakeDocumentFragment extends FakeNodeBase {
  constructor() {
    super();
    this.nodeType = 11;
    this.children = [];
  }

  appendChild(child) {
    if (!child) return child;
    if (child.parentNode) child.parentNode.removeChild(child);
    child.parentNode = this;
    this.children.push(child);
    return child;
  }
}

class FakeHTMLElement extends FakeElement {
  constructor(tagName) {
    super(tagName, null);
  }
}

class FakeSVGElement extends FakeElement {
  constructor(tagName, namespaceURI) {
    super(tagName, namespaceURI || SVG_NS);
  }
}

class FakeDocument extends FakeNodeBase {
  constructor() {
    super();
    this.nodeType = 9;
    this.readyState = "complete";
    this.documentElement = new FakeHTMLElement("html");
    this.documentElement.ownerDocument = this;
    this.head = new FakeHTMLElement("head");
    this.head.ownerDocument = this;
    this.body = new FakeHTMLElement("body");
    this.body.ownerDocument = this;
    this.documentElement.appendChild(this.head);
    this.documentElement.appendChild(this.body);
    this.documentElement._setConnected(true);
  }

  createElement(tagName) {
    const node = new FakeHTMLElement(tagName);
    node.ownerDocument = this;
    return node;
  }

  createElementNS(namespaceURI, tagName) {
    const node = new FakeSVGElement(tagName, namespaceURI);
    node.ownerDocument = this;
    return node;
  }

  createDocumentFragment() {
    const frag = new FakeDocumentFragment();
    frag.ownerDocument = this;
    return frag;
  }

  createEvent() {
    return new FakeEvent("");
  }

  querySelector(selector) {
    return this.documentElement.querySelector(selector);
  }

  querySelectorAll(selector) {
    return this.documentElement.querySelectorAll(selector);
  }

  getElementById(id) {
    const target = String(id || "");
    return [this.documentElement].concat(this.documentElement.querySelectorAll("*")).find((node) => node.getAttribute && node.getAttribute("id") === target) || null;
  }
}

const document = new FakeDocument();
const windowObject = global;
windowObject.window = windowObject;
windowObject.self = windowObject;
windowObject.document = document;
windowObject.navigator = { userAgent: "node" };
windowObject.location = { origin: "http://localhost" };
windowObject.HTMLElement = FakeHTMLElement;
windowObject.SVGElement = FakeSVGElement;
windowObject.Event = FakeEvent;
windowObject.requestAnimationFrame = function (callback) {
  callback();
  return 1;
};
windowObject.cancelAnimationFrame = function () {};
windowObject.getComputedStyle = function (node) {
  return {
    getPropertyValue(name) {
      return node && node.style && typeof node.style.getPropertyValue === "function"
        ? node.style.getPropertyValue(name)
        : "";
    },
  };
};
global.window = windowObject;
global.document = document;
global.HTMLElement = FakeHTMLElement;
global.SVGElement = FakeSVGElement;
global.Event = FakeEvent;
global.requestAnimationFrame = windowObject.requestAnimationFrame;
global.cancelAnimationFrame = windowObject.cancelAnimationFrame;
global.getComputedStyle = windowObject.getComputedStyle;

function loadScript(path) {
  const code = fs.readFileSync(path, "utf8");
  vm.runInThisContext(code, { filename: path });
  if (typeof Gantt !== "undefined") {
    window.Gantt = Gantt;
    global.Gantt = Gantt;
  }
}

function createHost(id) {
  const node = document.createElement("div");
  node.setAttribute("id", id);
  node.clientWidth = 1200;
  node.clientHeight = 320;
  document.body.appendChild(node);
  return node;
}

function findWrapperById(taskId) {
  const wrappers = document.querySelectorAll("#gantt .bar-wrapper");
  for (let index = 0; index < wrappers.length; index += 1) {
    if (String(wrappers[index].getAttribute("data-id") || "") === String(taskId)) {
      return wrappers[index];
    }
  }
  return null;
}

function createWrapper(taskId) {
  const wrapper = document.createElementNS(SVG_NS, "g");
  wrapper.setAttribute("class", "bar-wrapper aps-critical");
  wrapper.setAttribute("data-id", String(taskId));
  const group = document.createElementNS(SVG_NS, "g");
  group.setAttribute("class", "bar-group");
  wrapper.appendChild(group);
  const bar = document.createElementNS(SVG_NS, "rect");
  bar.setAttribute("class", "bar");
  bar.setAttribute("x", "10");
  bar.setAttribute("y", "20");
  bar.setAttribute("width", "30");
  bar.setAttribute("height", "12");
  bar.setAttribute("rx", "4");
  bar.setAttribute("ry", "4");
  group.appendChild(bar);
  return { wrapper, group, bar };
}

function readOutlineState(wrapper) {
  const outer = wrapper && wrapper.querySelector(".aps-cc-outline-outer");
  const inner = wrapper && wrapper.querySelector(".aps-cc-outline-inner");
  return {
    count: wrapper ? wrapper.querySelectorAll(".aps-cc-outline-outer, .aps-cc-outline-inner").length : 0,
    outerX: outer ? outer.getAttribute("x") : null,
    outerWidth: outer ? outer.getAttribute("width") : null,
    innerX: inner ? inner.getAttribute("x") : null,
    innerWidth: inner ? inner.getAttribute("width") : null,
  };
}

function applyPayload(barElement, payload) {
  if (payload && payload.x !== null && typeof payload.x !== "undefined") {
    barElement.setAttribute("x", String(payload.x));
  }
  if (payload && payload.width !== null && typeof payload.width !== "undefined") {
    barElement.setAttribute("width", String(payload.width));
  }
}
"""


def _preview_bootstrap() -> str:
    module_path = REPO_ROOT / "tests" / "run_complex_case_and_export_gantt.py"
    spec = importlib.util.spec_from_file_location("run_complex_case_and_export_gantt", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load preview helper from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build_preview_client_bootstrap("tasks", "calendarDays", "criticalChain")


def _run_node_json(code: str) -> dict:
    completed = subprocess.run(
        ["node", "-"],
        input=code,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=os.environ.copy(),
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"node execution failed rc={completed.returncode}\nstdout={completed.stdout[:1000]!r}\nstderr={completed.stderr[:1000]!r}"
        )
    return json.loads(completed.stdout or "{}")


def _outline_js() -> str:
    return json.dumps(str(REPO_ROOT / "static" / "js" / "gantt_outline.js"))


def _vendor_js() -> str:
    return json.dumps(str(REPO_ROOT / "static" / "js" / "frappe-gantt.min.js"))


def _gantt_js() -> str:
    return json.dumps(str(REPO_ROOT / "static" / "js" / "gantt.js"))


def _gantt_color_js() -> str:
    return json.dumps(str(REPO_ROOT / "static" / "js" / "gantt_color.js"))


def _gantt_render_js() -> str:
    return json.dumps(str(REPO_ROOT / "static" / "js" / "gantt_render.js"))


def _gantt_contract_js() -> str:
    return json.dumps(str(REPO_ROOT / "static" / "js" / "gantt_contract.js"))


def _gantt_boot_js() -> str:
    return json.dumps(str(REPO_ROOT / "static" / "js" / "gantt_boot.js"))


def _load_preview_module():
    module_path = REPO_ROOT / "tests" / "run_complex_case_and_export_gantt.py"
    spec = importlib.util.spec_from_file_location("run_complex_case_and_export_gantt", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load preview helper from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _template_static_scripts(template_path: Path) -> list[str]:
    text = template_path.read_text(encoding="utf-8")
    return re.findall(r"url_for\('static',\s*filename='([^']+)'\)", text)


def test_gantt_contract_asset_is_tracked_and_loaded_before_render_in_all_templates() -> None:
    expected_order = [
        "js/frappe-gantt.min.js",
        "js/gantt.js",
        "js/gantt_color.js",
        "js/gantt_outline.js",
        "js/gantt_contract.js",
        "js/gantt_render.js",
        "js/gantt_ui.js",
        "js/gantt_boot.js",
    ]
    for template_rel in ("templates/scheduler/gantt.html", "web_new_test/templates/scheduler/gantt.html"):
        scripts = [
            item
            for item in _template_static_scripts(REPO_ROOT / template_rel)
            if item.startswith("js/gantt") or item == "js/frappe-gantt.min.js"
        ]
        assert scripts == expected_order, template_rel

    contract_path = REPO_ROOT / "static" / "js" / "gantt_contract.js"
    assert contract_path.is_file()
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "static/js/gantt_contract.js"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert tracked.returncode == 0, tracked.stderr


def test_outline_helper_contract_and_adapter_binding() -> None:
    node_code = f"""
{DOM_SHIM_JS}
createHost("gantt");
loadScript({_outline_js()});

const api = window.__APS_GANTT__ && window.__APS_GANTT__.outline;
if (!api) {{
  throw new Error("outline namespace missing");
}}

const host = document.getElementById("gantt");
const first = createWrapper("T1");
host.appendChild(first.wrapper);

const enabled = api.setCriticalOutlineEnabled(first.wrapper, true);
const enabledState = readOutlineState(first.wrapper);
api.setCriticalOutlineEnabled(first.wrapper, false);
const disabledState = readOutlineState(first.wrapper);

api.setCriticalOutlineEnabled(first.wrapper, true);
first.bar.setAttribute("width", "0");
const invalidGeometry = api.setCriticalOutlineEnabled(first.wrapper, true);
const invalidState = readOutlineState(first.wrapper);

const missingWrapper = document.createElementNS(SVG_NS, "g");
missingWrapper.setAttribute("class", "bar-wrapper aps-critical");
const missingBar = api.setCriticalOutlineEnabled(missingWrapper, true);
const missingState = readOutlineState(missingWrapper);

const calls = [];
const second = createWrapper("A");
const third = createWrapper("B");
host.appendChild(second.wrapper);
host.appendChild(third.wrapper);
const barA = {{
  group: second.wrapper,
  $bar: second.bar,
  update_bar_position(payload) {{
    calls.push("A:" + JSON.stringify(payload || {{}}));
    applyPayload(second.bar, payload);
    return "A";
  }},
}};
const barB = {{
  group: third.wrapper,
  $bar: third.bar,
  update_bar_position(payload) {{
    calls.push("B:" + JSON.stringify(payload || {{}}));
    applyPayload(third.bar, payload);
    return "B";
  }},
}};

const wrappedCount = api.installCriticalOutlineSyncAdapter({{ bars: [barA, barB] }});
const retA = barA.update_bar_position({{ x: 55 }});
const retB = barB.update_bar_position({{ width: 44 }});
const stateA = readOutlineState(second.wrapper);
const stateB = readOutlineState(third.wrapper);

process.stdout.write(JSON.stringify({{
  hasLegacyGlobal: Object.prototype.hasOwnProperty.call(window, "__APS_GANTT_OUTLINE__"),
  enabled,
  enabledState,
  disabledState,
  invalidGeometry,
  invalidState,
  missingBar,
  missingState,
  wrappedCount,
  retA,
  retB,
  calls,
  stateA,
  stateB,
}}));
"""
    result = _run_node_json(node_code)

    assert result["hasLegacyGlobal"] is False
    assert result["enabled"] is True
    assert result["enabledState"]["count"] == 2
    assert result["enabledState"]["outerX"] == "8"
    assert result["enabledState"]["outerWidth"] == "34"
    assert result["disabledState"]["count"] == 0

    assert result["invalidGeometry"] is False
    assert result["invalidState"]["count"] == 0
    assert result["missingBar"] is False
    assert result["missingState"]["count"] == 0

    assert result["wrappedCount"] == 2
    assert result["retA"] == "A"
    assert result["retB"] == "B"
    assert result["calls"] == ['A:{"x":55}', 'B:{"width":44}']
    assert result["stateA"]["outerX"] == "53"
    assert result["stateB"]["outerWidth"] == "48"


def test_live_render_syncs_outline_with_real_vendor_and_no_runtime_sweeps() -> None:
    tasks = [
        {
            "id": "T1",
            "name": "Critical Task",
            "start": "2026-01-26",
            "end": "2026-01-27",
            "progress": 0,
            "dependencies": "",
            "meta": {
                "batch_id": "B001",
                "source": "internal",
                "priority": "critical",
                "status": "pending",
                "machine_id": "MC001",
                "machine": "CNC-01",
                "operator_id": "OP001",
                "operator": "Alice",
                "piece_id": "B001-1",
                "part_no": "P_A",
                "seq": 10,
                "due_date": "2026-01-27",
            },
        },
        {
            "id": "T2",
            "name": "Normal Task",
            "start": "2026-01-27",
            "end": "2026-01-28",
            "progress": 0,
            "dependencies": "",
            "meta": {
                "batch_id": "B002",
                "source": "internal",
                "priority": "normal",
                "status": "pending",
                "machine_id": "MC002",
                "machine": "CNC-02",
                "operator_id": "OP002",
                "operator": "Bob",
                "piece_id": "B002-1",
                "part_no": "P_B",
                "seq": 20,
                "due_date": "2026-01-30",
            },
        },
    ]
    calendar_days = [
        {"date": "2026-01-28", "day_type": "holiday", "shift_hours": 0, "is_holiday": True, "is_nonworking": True}
    ]

    node_code = f"""
{DOM_SHIM_JS}
createHost("gantt");
createHost("ganttEmpty");
createHost("ganttError");
createHost("ganttLegend");

loadScript({_vendor_js()});
const RealGantt = Gantt;
let lastOptions = null;
function CapturingGantt(selector, tasks, options) {{
  lastOptions = options || {{}};
  return new RealGantt(selector, tasks, options);
}}
CapturingGantt.prototype = RealGantt.prototype;
window.Gantt = CapturingGantt;
global.Gantt = CapturingGantt;

loadScript({_gantt_js()});
loadScript({_gantt_color_js()});
loadScript({_outline_js()});
loadScript({_gantt_contract_js()});
loadScript({_gantt_render_js()});

const ns = window.__APS_GANTT__;
const state = ns.state;
state.cfg = {{
  view: "machine",
  startDate: "2026-01-26",
  endDate: "2026-02-02",
  weekStart: "2026-01-26",
}};
state.allTasks = {json.dumps(tasks)};
state.critical = {{ ids: ["T1"], edges: [], makespan_end: "2026-01-27" }};
state.ccIdSet = new Set(["T1"]);
state.ccPrevByTo = new Map();
state.ccEdgeMetaByTo = new Map();
state.calendarDays = {json.dumps(calendar_days)};
state.ui.viewMode = "Day";
state.ui.colorMode = "batch";
state.ui.depsMode = "critical";
state.ui.highlightCC = true;
state.ui.onlyOverdue = false;
state.ui.onlyExternal = false;
state.ui.filterBatch = "";
state.ui.filterResource = "";

function snapshot(taskId) {{
  const wrapper = findWrapperById(taskId);
  const outline = readOutlineState(wrapper);
  return {{
    outline: outline,
    isCritical: !!(wrapper && wrapper.classList.contains("aps-critical")),
  }};
}}

ns.render();
const nonCritical = snapshot("T2");
const bar = state.gantt.get_bar("T1");
const start = snapshot("T1");
bar.update_bar_position({{ x: numericAttr(bar.$bar, "x", 0) + 38 }});
const drag = snapshot("T1");
bar.update_bar_position({{ width: numericAttr(bar.$bar, "width", 0) + 38 }});
const right = snapshot("T1");
bar.update_bar_position({{
  x: numericAttr(bar.$bar, "x", 0) + 19,
  width: numericAttr(bar.$bar, "width", 0) - 19,
}});
const left = snapshot("T1");

state.ui.viewMode = "Week";
ns.render();
const weekBar = state.gantt.get_bar("T1");
const weekStart = snapshot("T1");
weekBar.update_bar_position({{ x: numericAttr(weekBar.$bar, "x", 0) + 20 }});
const weekDrag = snapshot("T1");
weekBar.update_bar_position({{ width: numericAttr(weekBar.$bar, "width", 0) + 20 }});
const week = snapshot("T1");

state.ui.viewMode = "Month";
ns.render();
const monthBar = state.gantt.get_bar("T1");
const monthStart = snapshot("T1");
monthBar.update_bar_position({{ x: numericAttr(monthBar.$bar, "x", 0) + 14 }});
const monthDrag = snapshot("T1");
monthBar.update_bar_position({{ width: numericAttr(monthBar.$bar, "width", 0) + 14 }});
const month = snapshot("T1");

process.stdout.write(JSON.stringify({{
  options: {{
    onDateChangeType: typeof lastOptions.on_date_change,
    onProgressChangeType: typeof lastOptions.on_progress_change,
  }},
  nonCritical,
  start,
  drag,
  right,
  left,
  weekStart,
  weekDrag,
  week,
  monthStart,
  monthDrag,
  month,
}}));
"""
    result = _run_node_json(node_code)

    assert result["options"]["onDateChangeType"] == "undefined"
    assert result["options"]["onProgressChangeType"] == "undefined"
    assert result["nonCritical"]["isCritical"] is False
    assert result["nonCritical"]["outline"]["count"] == 0

    assert result["start"]["outline"]["count"] == 2
    assert result["drag"]["outline"]["outerX"] != result["start"]["outline"]["outerX"]
    assert result["right"]["outline"]["outerWidth"] != result["drag"]["outline"]["outerWidth"]
    assert result["left"]["outline"]["outerX"] != result["right"]["outline"]["outerX"]
    assert result["weekStart"]["outline"]["count"] == 2
    assert result["weekStart"]["outline"]["outerWidth"] != result["start"]["outline"]["outerWidth"]
    assert result["weekDrag"]["outline"]["outerX"] != result["weekStart"]["outline"]["outerX"]
    assert result["week"]["outline"]["count"] == 2
    assert result["monthStart"]["outline"]["count"] == 2
    assert result["monthStart"]["outline"]["outerWidth"] != result["weekStart"]["outline"]["outerWidth"]
    assert result["monthDrag"]["outline"]["outerX"] != result["monthStart"]["outline"]["outerX"]
    assert result["month"]["outline"]["count"] == 2


def test_preview_bootstrap_syncs_outline_with_real_vendor() -> None:
    tasks = [
        {
            "id": "T1",
            "name": "Critical Preview Task",
            "start": "2026-01-26",
            "end": "2026-01-27",
            "progress": 0,
            "dependencies": "",
            "meta": {"batch_id": "B001", "source": "internal"},
        },
        {
            "id": "T2",
            "name": "Normal Preview Task",
            "start": "2026-01-27",
            "end": "2026-01-28",
            "progress": 0,
            "dependencies": "",
            "meta": {"batch_id": "B002", "source": "external"},
        },
    ]
    calendar_days = [
        {"date": "2026-01-28", "day_type": "holiday", "shift_hours": 0, "is_holiday": True, "is_nonworking": True}
    ]
    critical_chain = {"ids": ["T1"], "edges": [], "makespan_end": "2026-01-27"}
    bootstrap_js = _preview_bootstrap()

    node_code = f"""
{DOM_SHIM_JS}
createHost("gantt");
createHost("legend");
loadScript({_vendor_js()});
loadScript({_outline_js()});
loadScript({_gantt_contract_js()});

const tasks = {json.dumps(tasks)};
const calendarDays = {json.dumps(calendar_days)};
const criticalChain = {json.dumps(critical_chain)};
vm.runInThisContext({json.dumps(bootstrap_js)}, {{ filename: "preview_bootstrap.js" }});

function snapshot(taskId) {{
  const wrapper = findWrapperById(taskId);
  return {{
    outline: readOutlineState(wrapper),
    isCritical: !!(wrapper && wrapper.classList.contains("aps-critical")),
  }};
}}

const preview = window.__APS_GANTT_PREVIEW__;
const gantt = preview.gantt;
const start = snapshot("T1");
const nonCritical = snapshot("T2");
const bar = gantt.get_bar("T1");
bar.update_bar_position({{ x: numericAttr(bar.$bar, "x", 0) + 38 }});
const drag = snapshot("T1");
bar.update_bar_position({{ width: numericAttr(bar.$bar, "width", 0) + 38 }});
const right = snapshot("T1");
bar.update_bar_position({{
  x: numericAttr(bar.$bar, "x", 0) + 19,
  width: numericAttr(bar.$bar, "width", 0) - 19,
}});
const left = snapshot("T1");

gantt.change_view_mode("Week");
const weekBar = gantt.get_bar("T1");
const weekStart = snapshot("T1");
weekBar.update_bar_position({{ x: numericAttr(weekBar.$bar, "x", 0) + 20 }});
const weekDrag = snapshot("T1");
weekBar.update_bar_position({{ width: numericAttr(weekBar.$bar, "width", 0) + 20 }});
const week = snapshot("T1");

gantt.change_view_mode("Month");
const monthBar = gantt.get_bar("T1");
const monthStart = snapshot("T1");
monthBar.update_bar_position({{ x: numericAttr(monthBar.$bar, "x", 0) + 14 }});
const monthDrag = snapshot("T1");
monthBar.update_bar_position({{ width: numericAttr(monthBar.$bar, "width", 0) + 14 }});
const month = snapshot("T1");

process.stdout.write(JSON.stringify({{
  start,
  nonCritical,
  drag,
  right,
  left,
  weekStart,
  weekDrag,
  week,
  monthStart,
  monthDrag,
  month,
}}));
"""
    result = _run_node_json(node_code)

    assert result["start"]["outline"]["count"] == 2
    assert result["nonCritical"]["isCritical"] is False
    assert result["nonCritical"]["outline"]["count"] == 0
    assert result["drag"]["outline"]["outerX"] != result["start"]["outline"]["outerX"]
    assert result["right"]["outline"]["outerWidth"] != result["drag"]["outline"]["outerWidth"]
    assert result["left"]["outline"]["outerX"] != result["right"]["outline"]["outerX"]
    assert result["weekStart"]["outline"]["count"] == 2
    assert result["weekStart"]["outline"]["outerWidth"] != result["start"]["outline"]["outerWidth"]
    assert result["weekDrag"]["outline"]["outerX"] != result["weekStart"]["outline"]["outerX"]
    assert result["week"]["outline"]["count"] == 2
    assert result["monthStart"]["outline"]["count"] == 2
    assert result["monthStart"]["outline"]["outerWidth"] != result["weekStart"]["outline"]["outerWidth"]
    assert result["monthDrag"]["outline"]["outerX"] != result["monthStart"]["outline"]["outerX"]
    assert result["month"]["outline"]["count"] == 2


def test_boot_reports_missing_outline_dependency_explicitly() -> None:
    node_code = f"""
{DOM_SHIM_JS}
createHost("gantt");
createHost("ganttError");
document.readyState = "loading";

loadScript({_gantt_js()});
const ns = window.__APS_GANTT__;
ns.initCalendarDays = function () {{}};
ns.refreshFilterSelectOptions = function () {{}};
ns.applyUiFromUrl = function () {{}};
ns.bindUi = function () {{}};
ns.readUi = function () {{}};
ns.persistUiToUrl = function () {{}};
ns.render = function () {{}};

loadScript({_gantt_boot_js()});
const errEl = document.getElementById("ganttError");
process.stdout.write(JSON.stringify({{
  message: errEl ? errEl.textContent : "",
}}));
"""
    result = _run_node_json(node_code)

    assert "outline.setCriticalOutlineEnabled" in result["message"]
    assert "outline.installCriticalOutlineSyncAdapter" in result["message"]


def test_formal_page_and_preview_share_critical_edge_tooltip_and_help_semantics() -> None:
    tasks = [
        {
            "id": "T1",
            "name": "Upstream Critical",
            "start": "2026-01-26",
            "end": "2026-01-27",
            "progress": 0,
            "dependencies": "",
            "meta": {
                "batch_id": "B001",
                "source": "internal",
                "priority": "critical",
                "status": "pending",
                "machine_id": "MC001",
                "machine": "CNC-01",
                "operator_id": "OP001",
                "operator": "Alice",
                "piece_id": "B001-1",
                "part_no": "P_A",
                "seq": 10,
                "due_date": "2026-01-27",
            },
        },
        {
            "id": "T2",
            "name": "Controlled Critical",
            "start": "2026-01-27",
            "end": "2026-01-28",
            "progress": 0,
            "dependencies": "P999",
            "meta": {
                "batch_id": "B001",
                "source": "internal",
                "priority": "critical",
                "status": "pending",
                "machine_id": "MC002",
                "machine": "CNC-02",
                "operator_id": "OP002",
                "operator": "Bob",
                "piece_id": "B001-2",
                "part_no": "P_A",
                "seq": 20,
                "due_date": "2026-01-28",
            },
        },
    ]
    critical_chain = {
        "ids": ["T1", "T2"],
        "edges": [
            {
                "from": "T1",
                "to": "T2",
                "edge_type": "machine",
                "reason": "控制前驱",
                "gap_minutes": 30,
            }
        ],
        "makespan_end": "2026-01-28",
        "available": True,
    }
    bootstrap_js = _preview_bootstrap()

    formal_node = f"""
{DOM_SHIM_JS}
createHost("gantt");
createHost("ganttEmpty");
createHost("ganttError");
createHost("ganttLegend");
createHost("ganttDegradationWarning");
createHost("ganttOverdueWarning");
const helpList = document.createElement("ul");
helpList.setAttribute("id", "ganttHelpList");
document.body.appendChild(helpList);
document.readyState = "loading";

loadScript({_vendor_js()});
const RealGantt = Gantt;
function CapturingGantt(selector, list, options) {{
  return new RealGantt(selector, list, options);
}}
CapturingGantt.prototype = RealGantt.prototype;
window.Gantt = CapturingGantt;
global.Gantt = CapturingGantt;

loadScript({_gantt_js()});
loadScript({_gantt_color_js()});
loadScript({_outline_js()});
loadScript({_gantt_contract_js()});
loadScript({_gantt_render_js()});
const ns = window.__APS_GANTT__;
ns.applyUiFromUrl = function () {{}};
ns.bindUi = function () {{}};
ns.readUi = function () {{}};
ns.persistUiToUrl = function () {{}};
const host = document.getElementById("gantt");
host.setAttribute("data-url", "/api/mock-gantt");
host.setAttribute("data-view", "machine");
host.setAttribute("data-week-start", "2026-01-26");
host.setAttribute("data-start-date", "2026-01-26");
host.setAttribute("data-end-date", "2026-02-02");
host.setAttribute("data-version", "7");
host.setAttribute("data-has-history", "1");

global.fetch = function () {{
  return Promise.resolve({{
    ok: true,
    json() {{
      return Promise.resolve({{
        success: true,
        data: {{
          tasks: {json.dumps(tasks)},
          calendar_days: [],
          critical_chain: {json.dumps(critical_chain)},
          degradation_events: [],
          degradation_counters: {{}},
        }},
      }});
    }},
  }});
}};

loadScript({_gantt_boot_js()});
(async function () {{
  await ns.loadAndRender();
  const task = ns.state.currentTasks.find((item) => item.id === "T2");
  const popup = ns.state.gantt && ns.state.gantt.options && typeof ns.state.gantt.options.custom_popup_html === "function"
    ? ns.state.gantt.options.custom_popup_html(task)
    : "";
  process.stdout.write(JSON.stringify({{
    dependency: task ? String(task.dependencies || "") : "",
    popup: popup,
    legend: document.getElementById("ganttLegend").textContent || "",
    help: document.getElementById("ganttHelpList").textContent || "",
  }}));
}})().catch((error) => {{
  console.error(error && error.stack ? error.stack : error);
  process.exit(1);
}});
"""
    preview_node = f"""
{DOM_SHIM_JS}
createHost("gantt");
createHost("legend");
createHost("ganttDegradationWarning");
const helpList = document.createElement("ul");
helpList.setAttribute("id", "ganttHelpList");
document.body.appendChild(helpList);

loadScript({_vendor_js()});
loadScript({_outline_js()});
loadScript({_gantt_contract_js()});

const tasks = {json.dumps(tasks)};
const calendarDays = [];
const criticalChain = {json.dumps(critical_chain)};
vm.runInThisContext({json.dumps(bootstrap_js)}, {{ filename: "preview_bootstrap.js" }});

const preview = window.__APS_GANTT_PREVIEW__;
const task = preview.gantt.get_task("T2");
const popup = preview.gantt.options && typeof preview.gantt.options.custom_popup_html === "function"
  ? preview.gantt.options.custom_popup_html(task)
  : "";
const deps = Array.isArray(task && task.dependencies) ? task.dependencies.join(",") : String((task && task.dependencies) || "");
process.stdout.write(JSON.stringify({{
  dependency: deps,
  popup: popup,
  legend: document.getElementById("legend").textContent || "",
  help: document.getElementById("ganttHelpList").textContent || "",
}}));
"""

    formal = _run_node_json(formal_node)
    preview = _run_node_json(preview_node)

    assert formal["dependency"] == "T1"
    assert preview["dependency"] == "T1"
    assert "关键链（全版本/本窗口可见）2/2" in formal["legend"]
    assert "关键链 2" in preview["legend"]

    for result in (formal, preview):
      assert "关键链前驱：T1" in result["popup"]
      assert "设备前驱" in result["popup"]
      assert "控制前驱" in result["popup"]
      assert "关键链控制前驱" in result["legend"]
      assert "控制前驱" in result["help"]
      assert "工艺依赖，后一工序依赖前一工序" not in result["help"]


def test_critical_chain_unavailable_semantics_match_formal_preview_and_export_html(tmp_path: Path) -> None:
    tasks = [
        {
            "id": "T1",
            "name": "Unavailable Raw Critical",
            "start": "2026-01-26",
            "end": "2026-01-27",
            "progress": 0,
            "dependencies": "",
            "meta": {"batch_id": "B001", "source": "internal"},
        },
        {
            "id": "T2",
            "name": "Unavailable Controlled Task",
            "start": "2026-01-27",
            "end": "2026-01-28",
            "progress": 0,
            "dependencies": "P999",
            "meta": {"batch_id": "B001", "source": "internal"},
        },
    ]
    critical_chain = {
        "ids": ["T1", "T2"],
        "edges": [{"from": "T1", "to": "T2", "edge_type": "machine", "reason": "控制前驱"}],
        "makespan_end": None,
        "available": False,
        "reason": "缓存缺失",
    }
    bootstrap_js = _preview_bootstrap()

    formal_node = f"""
{DOM_SHIM_JS}
createHost("gantt");
createHost("ganttEmpty");
createHost("ganttError");
createHost("ganttLegend");
createHost("ganttDegradationWarning");
createHost("ganttOverdueWarning");
const helpList = document.createElement("ul");
helpList.setAttribute("id", "ganttHelpList");
document.body.appendChild(helpList);
document.readyState = "loading";

loadScript({_vendor_js()});
loadScript({_gantt_js()});
loadScript({_gantt_color_js()});
loadScript({_outline_js()});
loadScript({_gantt_contract_js()});
loadScript({_gantt_render_js()});
const ns = window.__APS_GANTT__;
ns.applyUiFromUrl = function () {{}};
ns.bindUi = function () {{}};
ns.readUi = function () {{}};
ns.persistUiToUrl = function () {{}};
const host = document.getElementById("gantt");
host.setAttribute("data-url", "/api/mock-gantt");
host.setAttribute("data-view", "machine");
host.setAttribute("data-week-start", "2026-01-26");
host.setAttribute("data-start-date", "2026-01-26");
host.setAttribute("data-end-date", "2026-02-02");
host.setAttribute("data-version", "8");
host.setAttribute("data-has-history", "1");

global.fetch = function () {{
  return Promise.resolve({{
    ok: true,
    json() {{
      return Promise.resolve({{
        success: true,
        data: {{
          tasks: {json.dumps(tasks)},
          calendar_days: [],
          critical_chain: {json.dumps(critical_chain)},
          degradation_events: [],
          degradation_counters: {{}},
        }},
      }});
    }},
  }});
}};

loadScript({_gantt_boot_js()});
(async function () {{
  await ns.loadAndRender();
  const task = ns.state.currentTasks.find((item) => item.id === "T2");
  const popup = ns.state.gantt && ns.state.gantt.options && typeof ns.state.gantt.options.custom_popup_html === "function"
    ? ns.state.gantt.options.custom_popup_html(task)
    : "";
  const t1 = findWrapperById("T1");
  const t2 = findWrapperById("T2");
  process.stdout.write(JSON.stringify({{
    dependency: task ? String(task.dependencies || "") : "",
    popup: popup,
    t1Critical: !!(t1 && t1.classList.contains("aps-critical")),
    t2Critical: !!(t2 && t2.classList.contains("aps-critical")),
    t1Outline: readOutlineState(t1).count,
    t2Outline: readOutlineState(t2).count,
    warning: document.getElementById("ganttDegradationWarning").textContent || "",
    legend: document.getElementById("ganttLegend").textContent || "",
    help: document.getElementById("ganttHelpList").textContent || "",
  }}));
}})().catch((error) => {{
  console.error(error && error.stack ? error.stack : error);
  process.exit(1);
}});
"""
    preview_node = f"""
{DOM_SHIM_JS}
createHost("gantt");
createHost("legend");
createHost("ganttDegradationWarning");
const helpList = document.createElement("ul");
helpList.setAttribute("id", "ganttHelpList");
document.body.appendChild(helpList);

loadScript({_vendor_js()});
loadScript({_outline_js()});
loadScript({_gantt_contract_js()});

const tasks = {json.dumps(tasks)};
const calendarDays = [];
const criticalChain = {json.dumps(critical_chain)};
vm.runInThisContext({json.dumps(bootstrap_js)}, {{ filename: "preview_bootstrap.js" }});

const preview = window.__APS_GANTT_PREVIEW__;
const task = preview.gantt.get_task("T2");
const deps = Array.isArray(task && task.dependencies) ? task.dependencies.join(",") : String((task && task.dependencies) || "");
const popup = preview.gantt.options && typeof preview.gantt.options.custom_popup_html === "function"
  ? preview.gantt.options.custom_popup_html(task)
  : "";
const t1 = findWrapperById("T1");
const t2 = findWrapperById("T2");
process.stdout.write(JSON.stringify({{
  dependency: deps,
  popup: popup,
  t1Critical: !!(t1 && t1.classList.contains("aps-critical")),
  t2Critical: !!(t2 && t2.classList.contains("aps-critical")),
  t1Outline: readOutlineState(t1).count,
  t2Outline: readOutlineState(t2).count,
  warning: document.getElementById("ganttDegradationWarning").textContent || "",
  legend: document.getElementById("legend").textContent || "",
  help: document.getElementById("ganttHelpList").textContent || "",
}}));
"""

    formal = _run_node_json(formal_node)
    preview = _run_node_json(preview_node)

    assert formal["dependency"] == preview["dependency"] == ""
    assert formal["warning"] == preview["warning"]
    assert "关键链（全版本/本窗口可见）0/0" in formal["legend"]
    assert "关键链 0" in preview["legend"]
    assert "关键链 2" not in preview["legend"]
    assert "关键链(停用)" in preview["legend"]
    for result in (formal, preview):
      assert result["t1Critical"] is False
      assert result["t2Critical"] is False
      assert result["t1Outline"] == 0
      assert result["t2Outline"] == 0
      assert "关键链前驱：T1" not in result["popup"]
      assert "关键链暂不可用" in result["warning"]
      assert "缓存缺失" in result["warning"]
      assert "仅展示普通甘特任务与资源排程" in result["warning"]
      assert "关键链暂不可用" in result["legend"]
      assert "关键链(停用)" in result["legend"] or "关键链 0" in result["legend"]
      assert "缓存缺失" in result["help"]
      assert "任务条外框高亮，表示该任务仍在当前版本关键链上" not in result["help"]
      assert "默认展示关键链控制前驱" not in result["help"]

    preview_module = _load_preview_module()
    html_path = preview_module._write_html(
        str(tmp_path),
        "preview_unavailable.html",
        "preview unavailable",
        {"view": "machine"},
        tasks,
        calendar_days=[],
        critical_chain=critical_chain,
    )
    html = Path(html_path).read_text(encoding="utf-8")
    assert "../../static/js/gantt_contract.js" in html
    assert 'id="ganttDegradationWarning"' in html
    assert "工艺依赖，后一工序依赖前一工序" not in html


def test_gantt_templates_use_contract_rendered_help_list() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    for rel_path in ("templates/scheduler/gantt.html", "web_new_test/templates/scheduler/gantt.html"):
        html = (repo_root / rel_path).read_text(encoding="utf-8")
        assert 'id="ganttHelpList"' in html
        assert "任务条会出现<strong>外框高亮</strong>" not in html


def test_gantt_contract_sanitizes_render_task_names_and_preserves_raw_name() -> None:
    node_code = f"""
{DOM_SHIM_JS}
loadScript({_gantt_contract_js()});
const api = window.__APS_GANTT__.contract;
const tasks = [
  {{
    id: "T1",
    name: "<img src=x onerror=alert(1)>",
    start: "2026-01-26",
    end: "2026-01-27",
    dependencies: "",
    meta: {{ batch_id: "B001" }},
  }},
];
const rendered = api.buildRenderTasks(tasks, "none", {{ ids: [], edges: [], available: true }});
process.stdout.write(JSON.stringify({{
  name: rendered[0].name,
  rawName: rendered[0].meta._raw_name,
  sourceName: tasks[0].name,
}}));
"""
    result = _run_node_json(node_code)

    assert result["name"] == "&lt;img src=x onerror=alert(1)&gt;"
    assert result["rawName"] == "<img src=x onerror=alert(1)>"
    assert result["sourceName"] == "<img src=x onerror=alert(1)>"


def test_gantt_contract_disables_calendar_fallback_when_calendar_load_failed() -> None:
    node_code = f"""
{DOM_SHIM_JS}
loadScript({_gantt_contract_js()});
const api = window.__APS_GANTT__.contract;
process.stdout.write(JSON.stringify({{
  normal: api.shouldUseFallbackCalendarDays({{ degradation_counters: {{}}, empty_reason: "" }}),
  counterFailed: api.shouldUseFallbackCalendarDays({{ degradation_counters: {{ calendar_load_failed: 1 }} }}),
  eventFailed: api.shouldUseFallbackCalendarDays({{ degradation_events: [{{ code: "calendar_load_failed" }}] }}),
  emptyFailed: api.shouldUseFallbackCalendarDays({{ empty_reason: "calendar_load_failed" }}),
}}));
"""
    result = _run_node_json(node_code)

    assert result == {
        "normal": True,
        "counterFailed": False,
        "eventFailed": False,
        "emptyFailed": False,
    }


def test_gantt_contract_calendar_load_failed_message_does_not_echo_raw_event() -> None:
    node_code = f"""
{DOM_SHIM_JS}
loadScript({_gantt_contract_js()});
const api = window.__APS_GANTT__.contract;
const messages = api.buildDegradationMessages({{
  degradation_events: [
    {{ code: "calendar_load_failed", message: "sqlite OperationalError: /tmp/private.db locked" }},
  ],
  degradation_counters: {{ calendar_load_failed: 1 }},
}}, {{ ids: [], edges: [], available: true }});
process.stdout.write(JSON.stringify({{ messages }}));
"""
    result = _run_node_json(node_code)

    assert result["messages"] == ["工作日历加载失败，当前不显示假期/停工背景标注。"]
    assert "sqlite" not in str(result)
    assert "/tmp/private.db" not in str(result)


def test_gantt_contract_critical_unavailable_message_maps_reason_code() -> None:
    node_code = f"""
{DOM_SHIM_JS}
loadScript({_gantt_contract_js()});
const api = window.__APS_GANTT__.contract;
const critical = {{ ids: ["T1"], edges: [], available: false, reason: "repo_exception" }};
const messages = api.buildDegradationMessages({{
  degradation_counters: {{ critical_chain_unavailable: 1 }},
}}, critical);
const help = api.getHelpItems(critical).join(" ");
process.stdout.write(JSON.stringify({{ messages, help }}));
"""
    result = _run_node_json(node_code)

    assert "关键链计算异常" in str(result)
    assert "repo_exception" not in str(result)


def test_gantt_contract_public_history_and_critical_reason_do_not_echo_raw_values() -> None:
    from core.services.scheduler.gantt_contract import build_gantt_contract

    data = build_gantt_contract(
        contract_version=2,
        view="machine",
        version=9,
        week_start="2026-01-26",
        week_end="2026-02-01",
        tasks=[],
        calendar_days=[],
        critical_chain={"ids": [], "edges": [], "available": False, "reason": "repo_exception"},
        degraded=True,
        degradation_events=[],
        degradation_counters={"critical_chain_unavailable": 1},
        include_history=True,
        history={
            "version": 9,
            "result_status": "success",
            "result_summary": '{"degradation_events":[{"message":"sqlite SECRET /tmp/private.db"}]}',
        },
    )

    assert data["critical_chain"]["reason"] == "关键链计算异常"
    assert data["critical_chain"]["reason_code"] == "repo_exception"
    assert data["history"]["version"] == 9
    assert "result_summary" not in data["history"]
    assert "sqlite" not in str(data)
    assert "SECRET" not in str(data)
    assert "/tmp/private.db" not in str(data)


def test_formal_preview_and_export_html_share_degradation_and_overdue_warnings(tmp_path: Path) -> None:
    tasks = [
        {
            "id": "T1",
            "name": "Task A",
            "start": "2026-01-26",
            "end": "2026-01-27",
            "progress": 0,
            "dependencies": "",
            "meta": {"batch_id": "B001", "source": "internal"},
        }
    ]
    critical_chain = {"ids": ["T1"], "edges": [], "available": True, "reason": ""}
    degradation_events = [{"code": "calendar_load_failed", "message": "工作日历加载失败，当前不显示假期/停工背景标注。"}]
    degradation_counters = {"calendar_load_failed": 1, "bad_time_row_skipped": 2}
    overdue_message = "部分超期标记可能不完整，当前仍按已识别条目标记。"
    bootstrap_js = _preview_bootstrap()

    formal_node = f"""
{DOM_SHIM_JS}
createHost("gantt");
createHost("ganttEmpty");
createHost("ganttError");
createHost("ganttLegend");
createHost("ganttDegradationWarning");
createHost("ganttOverdueWarning");
const helpList = document.createElement("ul");
helpList.setAttribute("id", "ganttHelpList");
document.body.appendChild(helpList);
document.readyState = "loading";

loadScript({_vendor_js()});
loadScript({_gantt_js()});
loadScript({_gantt_color_js()});
loadScript({_outline_js()});
loadScript({_gantt_contract_js()});
loadScript({_gantt_render_js()});
const ns = window.__APS_GANTT__;
ns.applyUiFromUrl = function () {{}};
ns.bindUi = function () {{}};
ns.readUi = function () {{}};
ns.persistUiToUrl = function () {{}};
const host = document.getElementById("gantt");
host.setAttribute("data-url", "/api/mock-gantt");
host.setAttribute("data-view", "machine");
host.setAttribute("data-week-start", "2026-01-26");
host.setAttribute("data-start-date", "2026-01-26");
host.setAttribute("data-end-date", "2026-02-02");
host.setAttribute("data-version", "8");
host.setAttribute("data-has-history", "1");

global.fetch = function () {{
  return Promise.resolve({{
    ok: true,
    json() {{
      return Promise.resolve({{
        success: true,
        data: {{
          tasks: {json.dumps(tasks)},
          calendar_days: [],
          critical_chain: {json.dumps(critical_chain)},
          degradation_events: {json.dumps(degradation_events)},
          degradation_counters: {json.dumps(degradation_counters)},
          overdue_markers_degraded: false,
          overdue_markers_partial: true,
          overdue_markers_message: {json.dumps(overdue_message)},
        }},
      }});
    }},
  }});
}};

loadScript({_gantt_boot_js()});
(async function () {{
      await ns.loadAndRender();
      process.stdout.write(JSON.stringify({{
        degradation: document.getElementById("ganttDegradationWarning").textContent || "",
        overdue: document.getElementById("ganttOverdueWarning").textContent || "",
        legend: document.getElementById("ganttLegend").textContent || "",
        help: document.getElementById("ganttHelpList").textContent || "",
      }}));
}})().catch((error) => {{
  console.error(error && error.stack ? error.stack : error);
  process.exit(1);
}});
"""
    preview_node = f"""
{DOM_SHIM_JS}
createHost("gantt");
createHost("legend");
createHost("ganttDegradationWarning");
createHost("ganttOverdueWarning");
const helpList = document.createElement("ul");
helpList.setAttribute("id", "ganttHelpList");
document.body.appendChild(helpList);

loadScript({_vendor_js()});
loadScript({_outline_js()});
loadScript({_gantt_contract_js()});

const tasks = {json.dumps(tasks)};
const calendarDays = [];
const criticalChain = {json.dumps(critical_chain)};
const degradationEvents = {json.dumps(degradation_events)};
const degradationCounters = {json.dumps(degradation_counters)};
const emptyReason = "";
const overdueMarkersDegraded = false;
const overdueMarkersPartial = true;
const overdueMarkersMessage = {json.dumps(overdue_message)};
vm.runInThisContext({json.dumps(bootstrap_js)}, {{ filename: "preview_bootstrap.js" }});

process.stdout.write(JSON.stringify({{
  degradation: document.getElementById("ganttDegradationWarning").textContent || "",
  overdue: document.getElementById("ganttOverdueWarning").textContent || "",
  legend: document.getElementById("legend").textContent || "",
  help: document.getElementById("ganttHelpList").textContent || "",
}}));
"""

    formal = _run_node_json(formal_node)
    preview = _run_node_json(preview_node)

    assert formal["degradation"] == preview["degradation"]
    assert formal["overdue"] == preview["overdue"]
    assert "工作日历加载失败" in formal["degradation"]
    assert "已过滤 2 条时间不合法的排程记录。" in formal["degradation"]
    assert overdue_message in formal["overdue"]
    for result in (formal, preview):
        assert "假期/停工(停用)" in result["legend"]
        assert "假期/停工(背景)" not in result["legend"]
        assert "工作日历加载失败" in result["help"]
        assert "周末默认视为假期" not in result["help"]

    preview_module = _load_preview_module()
    html_path = preview_module._write_html(
        str(tmp_path),
        "preview_degraded.html",
        "preview degraded",
        {"view": "machine"},
        tasks,
        calendar_days=[],
        critical_chain=critical_chain,
        degradation_events=degradation_events,
        degradation_counters=degradation_counters,
        overdue_markers_partial=True,
        overdue_markers_message=overdue_message,
    )
    html = Path(html_path).read_text(encoding="utf-8")
    assert 'id="ganttOverdueWarning"' in html
    assert "calendar_load_failed" in html
    assert "overdueMarkersPartial" in html
