(function () {
  var ns = window.__APS_GANTT__ = window.__APS_GANTT__ || {};
  var api = ns.outline || {};
  if (api._inited) return;
  api._inited = true;

  var SVG_NS = "http://www.w3.org/2000/svg";
  var OUTER_PAD = 2;
  var INNER_PAD = 1;

  function _numAttr(node, name, fallback) {
    if (!node || typeof node.getAttribute !== "function") return fallback;
    var value = Number(node.getAttribute(name));
    return isFinite(value) ? value : fallback;
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

  function _removeNode(node) {
    if (!node || typeof node.remove !== "function") return;
    try {
      node.remove();
    } catch (_) {
      // ignore
    }
  }

  function _clearOutlineNodes(wrapper) {
    var nodes = _findOutlineNodes(wrapper);
    _removeNode(nodes.outer);
    _removeNode(nodes.inner);
    return false;
  }

  function _makeOutlineNode(className) {
    var node = document.createElementNS(SVG_NS, "rect");
    node.setAttribute("class", className);
    node.setAttribute("vector-effect", "non-scaling-stroke");
    node.setAttribute("pointer-events", "none");
    return node;
  }

  function _ensureOutlineNodes(wrapper) {
    if (!wrapper) return null;

    var bar = _getWrapperBar(wrapper);
    if (!bar) {
      _clearOutlineNodes(wrapper);
      return null;
    }

    var parent = bar.parentNode || wrapper;
    if (!parent) {
      _clearOutlineNodes(wrapper);
      return null;
    }

    var nodes = _findOutlineNodes(wrapper);
    var outer = nodes.outer || _makeOutlineNode("aps-cc-outline-outer");
    var inner = nodes.inner || _makeOutlineNode("aps-cc-outline-inner");

    if (outer.parentNode !== parent) {
      parent.insertBefore(outer, bar);
    }
    if (inner.parentNode !== parent) {
      parent.insertBefore(inner, bar);
    }

    return { bar: bar, outer: outer, inner: inner };
  }

  function _applyOutlineGeometry(node, bar, pad) {
    if (!node || !bar) return false;

    var x = _numAttr(bar, "x", 0);
    var y = _numAttr(bar, "y", 0);
    var width = _numAttr(bar, "width", 0);
    var height = _numAttr(bar, "height", 0);
    if (!(width > 0 && height > 0)) return false;

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
    return true;
  }

  function _syncOutlineGeometry(wrapper) {
    var refs = _ensureOutlineNodes(wrapper);
    if (!refs) return false;

    var outerOk = _applyOutlineGeometry(refs.outer, refs.bar, OUTER_PAD);
    var innerOk = _applyOutlineGeometry(refs.inner, refs.bar, INNER_PAD);
    if (!outerOk || !innerOk) {
      _clearOutlineNodes(wrapper);
      return false;
    }
    return true;
  }

  function setCriticalOutlineEnabled(wrapper, enabled) {
    if (!wrapper) return false;
    if (!enabled) {
      _clearOutlineNodes(wrapper);
      return true;
    }
    return _syncOutlineGeometry(wrapper);
  }

  function _resolveWrapper(bar) {
    if (!bar) return null;
    if (bar.group) return bar.group;
    if (bar.$bar_wrapper) return bar.$bar_wrapper;
    if (bar.$bar && typeof bar.$bar.closest === "function") {
      return bar.$bar.closest(".bar-wrapper");
    }
    if (bar.$bar && bar.$bar.parentNode && bar.$bar.parentNode.parentNode) {
      return bar.$bar.parentNode.parentNode;
    }
    return null;
  }

  function _isCriticalWrapper(wrapper) {
    return !!(wrapper && wrapper.classList && wrapper.classList.contains("aps-critical"));
  }

  function installCriticalOutlineSyncAdapter(gantt) {
    var bars = gantt && Array.isArray(gantt.bars) ? gantt.bars : [];
    var wrapped = 0;

    for (var index = 0; index < bars.length; index += 1) {
      var bar = bars[index];
      if (!bar || typeof bar.update_bar_position !== "function") continue;
      if (bar.__apsCriticalOutlineWrapped) continue;

      bar.update_bar_position = (function (original) {
        return function (payload) {
          var result = original.call(this, payload);
          var wrapper = _resolveWrapper(this);
          if (!wrapper) return result;
          if (_isCriticalWrapper(wrapper)) {
            setCriticalOutlineEnabled(wrapper, true);
          } else {
            _clearOutlineNodes(wrapper);
          }
          return result;
        };
      })(bar.update_bar_position);

      bar.__apsCriticalOutlineWrapped = true;
      wrapped += 1;

      var wrapper = _resolveWrapper(bar);
      if (!wrapper) continue;
      if (_isCriticalWrapper(wrapper)) {
        setCriticalOutlineEnabled(wrapper, true);
      } else {
        _clearOutlineNodes(wrapper);
      }
    }

    return wrapped;
  }

  api.setCriticalOutlineEnabled = setCriticalOutlineEnabled;
  api.installCriticalOutlineSyncAdapter = installCriticalOutlineSyncAdapter;
  ns.outline = api;
})();
