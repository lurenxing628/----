(function () {
  var api = window.__APS_GANTT_OUTLINE__ || {};
  if (api._inited) return;
  api._inited = true;

  var NS = "http://www.w3.org/2000/svg";
  var OUTER_PAD = 2;
  var INNER_PAD = 1;

  function _numAttr(el, name, fallback) {
    if (!el || typeof el.getAttribute !== "function") return fallback;
    var raw = Number(el.getAttribute(name));
    return isFinite(raw) ? raw : fallback;
  }

  function _getWrapperBar(wrapper) {
    if (!wrapper || typeof wrapper.querySelector !== "function") return null;
    return wrapper.querySelector(".bar");
  }

  function _findOutlineNodes(wrapper) {
    if (!wrapper || typeof wrapper.querySelector !== "function") {
      return { outer: null, inner: null };
    }
    return {
      outer: wrapper.querySelector(".aps-cc-outline-outer"),
      inner: wrapper.querySelector(".aps-cc-outline-inner"),
    };
  }

  function _makeOutlineNode(className) {
    var node = document.createElementNS(NS, "rect");
    node.setAttribute("class", className);
    node.setAttribute("vector-effect", "non-scaling-stroke");
    node.setAttribute("pointer-events", "none");
    return node;
  }

  function _applyOutlineGeometry(node, bar, pad) {
    if (!node || !bar) return;
    var x = _numAttr(bar, "x", 0);
    var y = _numAttr(bar, "y", 0);
    var width = _numAttr(bar, "width", 0);
    var height = _numAttr(bar, "height", 0);
    if (!(width > 0 && height > 0)) return;

    var rx = _numAttr(bar, "rx", 4);
    var ry = _numAttr(bar, "ry", rx);
    if (!(rx >= 0)) rx = 4;
    if (!(ry >= 0)) ry = rx;
    try {
      bar.setAttribute("rx", String(rx));
      bar.setAttribute("ry", String(ry));
    } catch (_) {
      // ignore
    }

    node.setAttribute("x", String(x - pad));
    node.setAttribute("y", String(y - pad));
    node.setAttribute("width", String(width + pad * 2));
    node.setAttribute("height", String(height + pad * 2));
    node.setAttribute("rx", String(rx + pad));
    node.setAttribute("ry", String(ry + pad));
  }

  function ensureCriticalOutlineNodes(wrapper) {
    if (!wrapper) return null;
    var bar = _getWrapperBar(wrapper);
    if (!bar) return null;

    var nodes = _findOutlineNodes(wrapper);
    var outer = nodes.outer || _makeOutlineNode("aps-cc-outline-outer");
    var inner = nodes.inner || _makeOutlineNode("aps-cc-outline-inner");
    var parent = bar.parentNode || wrapper;
    if (!parent) return null;

    if (outer.parentNode !== parent) {
      parent.insertBefore(outer, bar);
    }
    if (inner.parentNode !== parent) {
      parent.insertBefore(inner, bar);
    }

    return { bar: bar, outer: outer, inner: inner };
  }

  function syncCriticalOutlineGeometry(wrapper) {
    var refs = ensureCriticalOutlineNodes(wrapper);
    if (!refs) return null;
    _applyOutlineGeometry(refs.outer, refs.bar, OUTER_PAD);
    _applyOutlineGeometry(refs.inner, refs.bar, INNER_PAD);
    return refs;
  }

  function removeCriticalOutlineNodes(wrapper) {
    var nodes = _findOutlineNodes(wrapper);
    [nodes.outer, nodes.inner].forEach(function (node) {
      if (!node || typeof node.remove !== "function") return;
      try {
        node.remove();
      } catch (_) {
        // ignore
      }
    });
  }

  function setCriticalOutlineEnabled(wrapper, enabled) {
    if (!wrapper) return null;
    if (!enabled) {
      removeCriticalOutlineNodes(wrapper);
      return null;
    }
    ensureCriticalOutlineNodes(wrapper);
    return syncCriticalOutlineGeometry(wrapper);
  }

  function _resolveWrapper(bar) {
    if (!bar) return null;
    if (bar.group) return bar.group;
    if (bar.$bar_wrapper) return bar.$bar_wrapper;
    if (bar.$bar && bar.$bar.parentNode && bar.$bar.parentNode.parentNode) {
      return bar.$bar.parentNode.parentNode;
    }
    return null;
  }

  function _defaultIsCriticalWrapper(wrapper) {
    return !!(wrapper && wrapper.classList && wrapper.classList.contains("aps-critical"));
  }

  function installCriticalOutlineSyncAdapter(gantt, opts) {
    var bars = gantt && Array.isArray(gantt.bars) ? gantt.bars : [];
    var isCriticalWrapper =
      opts && typeof opts.isCriticalWrapper === "function"
        ? opts.isCriticalWrapper
        : _defaultIsCriticalWrapper;
    var wrapped = 0;

    for (var i = 0; i < bars.length; i++) {
      var bar = bars[i];
      if (!bar || typeof bar.update_bar_position !== "function") continue;
      if (bar.__apsCriticalOutlineWrapped) continue;

      var original = bar.update_bar_position;
      bar.update_bar_position = function (payload) {
        var ret = original.call(this, payload);
        var wrapper = _resolveWrapper(this);
        if (!wrapper) return ret;
        if (isCriticalWrapper(wrapper)) {
          setCriticalOutlineEnabled(wrapper, true);
        } else {
          removeCriticalOutlineNodes(wrapper);
        }
        return ret;
      };
      bar.__apsCriticalOutlineWrapped = true;
      wrapped += 1;

      var wrapper = _resolveWrapper(bar);
      if (wrapper && isCriticalWrapper(wrapper)) {
        setCriticalOutlineEnabled(wrapper, true);
      }
    }

    return wrapped;
  }

  function syncAllCriticalOutlines(target, opts) {
    var isCriticalWrapper =
      opts && typeof opts.isCriticalWrapper === "function"
        ? opts.isCriticalWrapper
        : _defaultIsCriticalWrapper;
    var wrappers = [];

    if (typeof target === "string") {
      wrappers = Array.prototype.slice.call(document.querySelectorAll(target));
    } else if (target && typeof target.length === "number") {
      wrappers = Array.prototype.slice.call(target);
    } else if (target) {
      wrappers = [target];
    }

    for (var i = 0; i < wrappers.length; i++) {
      var wrapper = wrappers[i];
      if (!wrapper) continue;
      if (isCriticalWrapper(wrapper)) {
        setCriticalOutlineEnabled(wrapper, true);
      } else {
        removeCriticalOutlineNodes(wrapper);
      }
    }
    return wrappers.length;
  }

  api.ensureCriticalOutlineNodes = ensureCriticalOutlineNodes;
  api.syncCriticalOutlineGeometry = syncCriticalOutlineGeometry;
  api.removeCriticalOutlineNodes = removeCriticalOutlineNodes;
  api.setCriticalOutlineEnabled = setCriticalOutlineEnabled;
  api.installCriticalOutlineSyncAdapter = installCriticalOutlineSyncAdapter;
  api.syncAllCriticalOutlines = syncAllCriticalOutlines;

  window.__APS_GANTT_OUTLINE__ = api;
  if (window.__APS_GANTT__) {
    window.__APS_GANTT__.outline = api;
  }
})();
