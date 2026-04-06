(() => {
  "use strict";

  function toggleScope() {
    const t = document.getElementById("scopeType");
    const v = t ? t.value : "machine";
    const m = document.getElementById("scopeMachine");
    const c = document.getElementById("scopeCategory");
    if (m) m.style.display = v === "machine" ? "block" : "none";
    if (c) c.style.display = v === "category" ? "block" : "none";

    // 注意：隐藏的控件仍会随表单提交；这里只提交当前范围对应的 scope_value
    const mSel = document.getElementById("scopeValueMachine");
    const cSel = document.getElementById("scopeValueCategory");
    if (mSel) mSel.disabled = v !== "machine";
    if (cSel) cSel.disabled = v !== "category";
  }

  function init() {
    const scopeType = document.getElementById("scopeType");
    if (scopeType) {
      scopeType.addEventListener("change", toggleScope);
    }
    toggleScope();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

