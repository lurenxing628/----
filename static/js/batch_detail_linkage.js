(() => {
  "use strict";

  const cfg = window.__APS_BATCH_DETAIL_LINKAGE__ || {};
  const machineOperators = cfg.machineOperators || {};
  function buildOperatorMachinesFromMachineOperators(src) {
    const reverse = {};
    try {
      Object.keys(src || {}).forEach((mcId) => {
        const ops = Array.isArray(src[mcId]) ? src[mcId] : [];
        for (const opId of ops) {
          if (!opId) continue;
          if (!reverse[opId]) reverse[opId] = [];
          reverse[opId].push(mcId);
        }
      });
    } catch (_e) {
      return {};
    }
    return reverse;
  }
  const operatorMachines = cfg.operatorMachines || buildOperatorMachinesFromMachineOperators(machineOperators);
  const machineOperatorMeta = cfg.machineOperatorMeta || {};
  const preferPrimarySkill = cfg.preferPrimarySkill === true;
  const lazySelectEnabled = cfg.lazySelectEnabled === true;

  function ensureSelectOptionsLoaded(selectEl, tplId) {
    if (!lazySelectEnabled) return;
    if (!selectEl) return;
    // 保护：仅处理标记了 data-lazy="1" 的下拉，避免误用到非懒加载 select
    if (selectEl.dataset && selectEl.dataset.lazy !== "1") return;
    if (selectEl.dataset && selectEl.dataset.optionsLoaded === "1") return;

    const tpl = document.getElementById(tplId);
    if (!tpl || !tpl.content) {
      // 模板缺失时不阻断页面：保留原 options；标记失败便于排障
      if (selectEl.dataset) selectEl.dataset.optionsLoadFailed = "1";
      return;
    }

    const selected = (selectEl.value || "").toString();
    const prevHTML = (() => {
      try {
        return selectEl.innerHTML || "";
      } catch (_e) {
        return "";
      }
    })();
    // 记录当前选中项文本 / 克隆已选项：用于在懒加载替换 options 后回显“缺失/已删除”的占位项
    let selectedText = "";
    let selectedOptClone = null;
    try {
      const idx = selectEl.selectedIndex;
      if (idx >= 0 && selectEl.options && selectEl.options[idx]) {
        const opt0 = selectEl.options[idx];
        selectedText = opt0.text || "";
        if (selected && (opt0.value || "") === selected) {
          try {
            selectedOptClone = opt0.cloneNode(true);
          } catch (_e2) {
            selectedOptClone = null;
          }
        }
      }
    } catch (_e3) {
      // ignore
    }
    let loadOk = false;
    try {
      selectEl.innerHTML = "";
      selectEl.appendChild(tpl.content.cloneNode(true));
      loadOk = true;
    } catch (_e4) {
      loadOk = false;
    }
    // 防御：避免替换失败导致 <select> 被洗空且不再重试
    if (loadOk) {
      try {
        if (!selectEl.options || selectEl.options.length <= 0) loadOk = false;
      } catch (_e5) {
        loadOk = false;
      }
    }
    if (!loadOk) {
      try {
        selectEl.innerHTML = prevHTML;
      } catch (_e6) {
        // ignore
      }
      if (selectEl.dataset) selectEl.dataset.optionsLoadFailed = "1";
      return;
    }

    // 先尝试在新 options 中恢复已选值（优先 opt.selected=true，其次 select.value=...）
    let restored = false;
    if (selected) {
      try {
        const opts = selectEl.options || [];
        for (let i = 0; i < opts.length; i++) {
          if ((opts[i].value || "") === selected) {
            opts[i].selected = true;
            restored = true;
            break;
          }
        }
      } catch (_e7) {
        // ignore
      }
      if (!restored) {
        try {
          selectEl.value = selected;
        } catch (_e8) {
          // ignore
        }
        if ((selectEl.value || "") === selected) restored = true;
      }
    }

    // 若已选值不在模板 options 中：回插一个“已删除”占位项，并强制保持选中，避免首次交互时静默丢值
    if (selected && !restored) {
      try {
        const orphanOpt = selectedOptClone ? selectedOptClone : document.createElement("option");
        orphanOpt.value = selected;

        let label = (selectedText || orphanOpt.text || "").toString().trim();
        // 旧 HTML 的兜底项通常只显示 ID，这里补充“已删除”标注，便于用户察觉
        if (!label || label === selected) label = selected + "（已删除）";
        else if (label.indexOf("（") < 0) label = label + "（已删除）";
        orphanOpt.textContent = label;

        // 标记为“孤儿/已删除”项，便于后续排查/样式扩展
        try {
          orphanOpt.dataset.orphan = "1";
        } catch (_e9) {
          orphanOpt.setAttribute("data-orphan", "1");
        }

        // 禁用且永远保持 disabled（避免被联动过滤重新启用）
        orphanOpt.disabled = true;
        try {
          orphanOpt.dataset.staticDisabled = "1";
        } catch (_e10) {
          orphanOpt.setAttribute("data-static-disabled", "1");
        }

        // 尽量插在空选项后面，避免被排序到最底部不易发现
        try {
          if (selectEl.options && selectEl.options.length > 0 && !(selectEl.options[0].value || "")) {
            selectEl.insertBefore(orphanOpt, selectEl.options[1] || null);
          } else {
            selectEl.insertBefore(orphanOpt, selectEl.options[0] || null);
          }
        } catch (_e11) {
          try {
            selectEl.appendChild(orphanOpt);
          } catch (_e12) {
            // ignore
          }
        }

        // 强制选中：不依赖“仅设置 select.value”以避免部分浏览器对 disabled option 的差异行为
        try {
          orphanOpt.selected = true;
        } catch (_e13) {
          // ignore
        }
        try {
          selectEl.value = selected;
        } catch (_e14) {
          // ignore
        }
      } catch (_e15) {
        // ignore
      }
    }
    if (selectEl.dataset) {
      selectEl.dataset.optionsLoaded = "1";
      try {
        delete selectEl.dataset.optionsLoadFailed;
      } catch (_e16) {
        try {
          selectEl.removeAttribute("data-options-load-failed");
        } catch (_e17) {
          // ignore
        }
      }
    }
  }

  function isSelectedOrphan(selectEl) {
    if (!selectEl) return false;
    try {
      const idx = selectEl.selectedIndex;
      const opt = idx >= 0 && selectEl.options && selectEl.options[idx] ? selectEl.options[idx] : null;
      if (!opt) return false;
      if (opt.dataset && opt.dataset.orphan === "1") return true;
      const text = ((opt.textContent || opt.text || "") || "").toString();
      return text.indexOf("（已删除）") >= 0;
    } catch (_e) {
      return false;
    }
  }

  function skillScore(skillLevel) {
    const v = (skillLevel || "").toString().toLowerCase();
    if (v === "expert") return 2;
    if (v === "normal") return 1;
    if (v === "beginner") return 0;
    return 0;
  }

  function reorderOperatorOptionsByPreference(selectEl, machineId, allowedOps) {
    if (!preferPrimarySkill) return;
    if (!selectEl) return;
    const mc = (machineId || "").trim();
    if (!mc) return;

    const metaMap = machineOperatorMeta && machineOperatorMeta[mc] ? machineOperatorMeta[mc] : {};
    const selected = selectEl.value || "";
    const opts = Array.from(selectEl.options || []);
    if (opts.length <= 2) return;

    const emptyOpts = opts.filter((o) => !o.value);
    const others = opts.filter((o) => !!o.value);

    function rank(opt) {
      const val = opt.value || "";
      const staticDisabled = opt.dataset && opt.dataset.staticDisabled === "1" ? 1 : 0;
      const allowed = allowedOps ? (allowedOps.has(val) ? 0 : 1) : 0;
      const meta = metaMap && metaMap[val] ? metaMap[val] : {};
      const primary = meta.is_primary === "yes" ? 0 : 1;
      const skill = -skillScore(meta.skill_level);
      return [staticDisabled, allowed, primary, skill, val];
    }

    others.sort((a, b) => {
      const ra = rank(a);
      const rb = rank(b);
      for (let i = 0; i < ra.length; i++) {
        if (ra[i] < rb[i]) return -1;
        if (ra[i] > rb[i]) return 1;
      }
      return 0;
    });

    const frag = document.createDocumentFragment();
    for (const o of emptyOpts) frag.appendChild(o);
    for (const o of others) frag.appendChild(o);
    selectEl.appendChild(frag);

    // 保持已选值
    try {
      selectEl.value = selected;
    } catch (_e) {
      // ignore
    }
  }

  function setSelectOptionsByAllowed(selectEl, allowedSet) {
    if (!selectEl) return;
    const options = Array.from(selectEl.options || []);
    for (const opt of options) {
      // 空选项永远可用
      if (!opt.value) {
        opt.disabled = false;
        continue;
      }
      // 后端标记为“不可用”的选项（停用/维修等）永远保持 disabled
      if (opt.dataset && opt.dataset.staticDisabled === "1") {
        opt.disabled = true;
        continue;
      }
      // 未触发过滤：全部启用
      if (!allowedSet) {
        opt.disabled = false;
        continue;
      }
      opt.disabled = !allowedSet.has(opt.value);
    }
  }

  function setHintVisible(hintEl, visible) {
    if (!hintEl) return;
    if (hintEl.classList) {
      hintEl.classList.toggle("is-hidden", !visible);
    }
    hintEl.style.display = visible ? "block" : "none";
  }

  function applyLinkageForRow(rowEl) {
    const mSel = rowEl.querySelector(".js-machine-select");
    const oSel = rowEl.querySelector(".js-operator-select");
    const hint = rowEl.querySelector(".js-linkage-hint");

    if (!mSel || !oSel || !hint) return;

    // 懒加载：首次交互时再填充完整 options（避免首屏/切页卡顿）
    ensureSelectOptionsLoaded(mSel, "tplMachineOptions");
    ensureSelectOptionsLoaded(oSel, "tplOperatorOptions");

    const machineId = (mSel.value || "").trim();
    const operatorId = (oSel.value || "").trim();

    const machineOrphan = machineId ? isSelectedOrphan(mSel) : false;
    const operatorOrphan = operatorId ? isSelectedOrphan(oSel) : false;

    // “已删除/孤儿资源”不参与联动过滤：避免把另一侧下拉全部禁用，用户无法快速改正
    const allowedOps = !machineOrphan && machineId ? new Set(machineOperators[machineId] || []) : null;
    const allowedMcs = !operatorOrphan && operatorId ? new Set(operatorMachines[operatorId] || []) : null;

    setSelectOptionsByAllowed(oSel, allowedOps);
    setSelectOptionsByAllowed(mSel, allowedMcs);
    reorderOperatorOptionsByPreference(oSel, machineId, allowedOps);

    let msg = "";
    if (machineOrphan) msg = `设备“${machineId}”已删除：请改选或清空。`;
    if (operatorOrphan) msg = (msg ? msg + " " : "") + `人员“${operatorId}”已删除：请改选或清空。`;

    // 删除/孤儿提示优先级最高：存在删除时跳过“未配置关联/组合不匹配”等提示，避免误导
    if (!msg) {
      if (machineId && allowedOps && allowedOps.size === 0) {
        msg = `设备“${machineId}”尚未配置可操作人员（请先在人员/设备管理维护关联）。`;
      }
      if (operatorId && allowedMcs && allowedMcs.size === 0) {
        msg = `人员“${operatorId}”尚未配置可操作设备（请先在人员/设备管理维护关联）。`;
      }
      if (machineId && operatorId) {
        const ok = Array.isArray(machineOperators[machineId]) && machineOperators[machineId].includes(operatorId);
        if (!ok) {
          const opCode = rowEl.dataset ? rowEl.dataset.opCode || "" : "";
          msg =
            `当前设备/人员组合不匹配：${machineId} × ${operatorId}` +
            (opCode ? `（工序 ${opCode}）` : "") +
            "。保存时系统将提示错误，请改选匹配项或清空其中一个。";
        }
      }
    }

    if (msg) {
      hint.textContent = msg;
      setHintVisible(hint, true);
    } else {
      hint.textContent = "";
      setHintVisible(hint, false);
    }
  }

  function isLinkageTarget(el) {
    return !!(el && el.matches && el.matches(".js-machine-select, .js-operator-select"));
  }

  function getLinkageRowFromTarget(target) {
    if (!target || !target.closest) return null;
    return target.closest('tr[data-linkage-row="1"]');
  }

  function isRowWarmed(rowEl) {
    if (!rowEl || !rowEl.dataset) return false;
    return rowEl.dataset.linkageWarmed === "1";
  }

  function markRowWarmed(rowEl) {
    if (!rowEl || !rowEl.dataset) return;
    rowEl.dataset.linkageWarmed = "1";
  }

  function warmRowOnce(rowEl) {
    if (!rowEl || isRowWarmed(rowEl)) {
      return;
    }
    applyLinkageForRow(rowEl);
    markRowWarmed(rowEl);
  }

  function initLinkage() {
    const rows = document.querySelectorAll('tr[data-linkage-row="1"]');
    if (!rows || rows.length <= 0) {
      return;
    }
    const table = rows[0].closest("table") || document;

    // 统一用 table 级委托替代逐行绑定：减少 N 行级监听器开销
    table.addEventListener("change", (e) => {
      const target = e.target;
      if (!isLinkageTarget(target)) return;
      const row = getLinkageRowFromTarget(target);
      if (!row) return;
      applyLinkageForRow(row);
      if (lazySelectEnabled) {
        markRowWarmed(row);
      }
    });

    if (lazySelectEnabled) {
      // 首次交互再执行（避免加载时对每行都填充大量 options）
      const warmByEvent = (e) => {
        const target = e.target;
        if (!target || !target.closest) return;
        const hit = target.closest(".js-machine-select, .js-operator-select");
        if (!isLinkageTarget(hit)) return;
        const row = getLinkageRowFromTarget(hit);
        if (!row) return;
        warmRowOnce(row);
      };
      // mousedown capture：尽量在下拉弹出前完成 options 填充与禁用过滤
      table.addEventListener("mousedown", warmByEvent, true);
      table.addEventListener("focusin", warmByEvent, true);
      table.addEventListener("keydown", warmByEvent, true);
    } else {
      for (const row of rows) {
        applyLinkageForRow(row);
      }
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initLinkage);
  } else {
    initLinkage();
  }
})();

