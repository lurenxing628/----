(function () {
  const ns = window.__APS_RESOURCE_DISPATCH__;
  ns.execution = ns.execution || {};
  const state = ns.state;
  const $ = ns.$;
  const trim = ns.trim;
  const escapeHtml = ns.escapeHtml;
  const show = ns.show;
  const badge = ns.badge;
  const fullTextCell = ns.fullTextCell;

  function currentQueryString() {
    return ns.core.currentQueryString();
  }

  function loadData() {
    return ns.core.loadData();
  }

  function actualImportUrl() {
    const url = state.cfg.actualImportUrl || "";
    if (!url) return "";
    return url.indexOf("?") >= 0 ? url : url + currentQueryString();
  }

  function renderActualImportResult(data) {
    const wrap = $("rdActualImportPreviewWrap");
    if (!wrap) return;
    const payload = data || {};
    const summary = payload.summary || {};
    const rows = Array.isArray(payload.rows) ? payload.rows : [];
    if (!rows.length) {
      wrap.innerHTML = "";
      show(wrap, false);
      return;
    }
    const lines = [];
    lines.push(
      '<div class="aps-execution-inline-form">' +
        '<div class="aps-execution-inline-title">导入结果</div>' +
        '<div class="aps-execution-facts">' +
          '<div><span>匹配成功</span><strong>' + escapeHtml(summary.matched_rows || 0) + '</strong></div>' +
          '<div><span>可导入</span><strong>' + escapeHtml(summary.add_count || 0) + '</strong></div>' +
          '<div><span>空白行</span><strong>' + escapeHtml(summary.skip_count || 0) + '</strong></div>' +
          '<div><span>冲突</span><strong>' + escapeHtml(summary.conflict_count || 0) + '</strong></div>' +
          '<div><span>错误</span><strong>' + escapeHtml(summary.error_count || 0) + '</strong></div>' +
        '</div>' +
        '<div class="aps-table-scroll mt-2">' +
          '<table class="table-sticky table-layout-fixed aps-table-xwide">' +
            '<thead><tr><th>工作表</th><th>行号</th><th>任务识别码</th><th>结果</th><th>说明</th><th>可导入</th><th>空白行</th></tr></thead><tbody>'
    );
    rows.forEach(function (row) {
      const status = trim(row.status);
      const variant = status === "ok" ? "new" : (status === "skip" ? "skip" : "error");
      lines.push(
        '<tr>' +
          '<td>' + escapeHtml(row.sheet || "") + '</td>' +
          '<td>' + escapeHtml(row.row_number || "") + '</td>' +
          '<td>' + escapeHtml(row.task_code || "") + '</td>' +
          '<td>' + badge(row.status_label || "待处理", variant) + '</td>' +
          fullTextCell(row.message || "", "aps-resource-cell") +
          '<td>' + escapeHtml(row.add_count || 0) + '</td>' +
          '<td>' + escapeHtml(row.skip_count || 0) + '</td>' +
        '</tr>'
      );
    });
    lines.push('</tbody></table></div></div>');
    wrap.innerHTML = lines.join("");
    show(wrap, true);
  }

  async function submitActualImport() {
    const fileInput = $("rdActualImportFile");
    const file = fileInput && fileInput.files && fileInput.files[0];
    if (!state.cfg.actualImportUrl) {
      ns.execution.executionNotice("当前查询没有可导入的实际情况。");
      return;
    }
    if (!file) {
      ns.execution.executionNotice("请先选择要导入的 Excel 文件。");
      return;
    }
    const btn = $("rdActualImportSubmit");
    const form = new FormData();
    form.append("file", file);
    if (btn) btn.disabled = true;
    renderActualImportResult(null);
    ns.execution.executionNotice("正在导入实际情况，请稍候。");
    try {
      const resp = await fetch(actualImportUrl(), {
        method: "POST",
        headers: { Accept: "application/json" },
        body: form
      });
      const payload = await resp.json();
      if (!resp.ok || !payload || payload.success !== true) {
        const details = payload && payload.error && payload.error.details ? payload.error.details : {};
        if (details && Array.isArray(details.rows)) {
          renderActualImportResult({ rows: details.rows, summary: details.summary || {} });
        }
        const message = payload && payload.error && payload.error.message ? payload.error.message : "导入实际情况失败，请修改 Excel 后重试。";
        throw new Error(message);
      }
      ns.execution.executionNotice((payload.data && payload.data.message) || "导入实际情况已完成。");
      if (fileInput) fileInput.value = "";
      ns.execution.loadExecutionData();
      loadData();
    } catch (err) {
      ns.execution.executionNotice(err && err.message ? err.message : "导入实际情况失败，请修改 Excel 后重试。");
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  function bindActualImportButtons() {
    const submitBtn = $("rdActualImportSubmit");
    const fileInput = $("rdActualImportFile");
    if (submitBtn) submitBtn.addEventListener("click", submitActualImport);
    if (fileInput) {
      fileInput.addEventListener("change", function () {
        renderActualImportResult(null);
        ns.execution.executionNotice("");
      });
    }
  }

  Object.assign(ns.execution, { bindActualImportButtons: bindActualImportButtons });
})();
