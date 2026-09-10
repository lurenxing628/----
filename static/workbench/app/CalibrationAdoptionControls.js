(function () {
  'use strict';

  const {
      Button,
      Modal
    } = window.ResourceControls,
    {
      hours
    } = window.CalibrationControls;
  const scope = '已有批次工时、历史计划和执行记录保持原样。新批次使用前，须在基础资料重新确认模板工时。';
  function Facts({
    row
  }) {
    return /*#__PURE__*/React.createElement("dl", {
      className: "cad-facts"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u6A21\u677F\u5DE5\u5E8F"), /*#__PURE__*/React.createElement("dd", null, row.part_no, " \xB7 ", row.sequence, " ", row.operation_label)), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u6A21\u677F\u4FEE\u8BA2"), /*#__PURE__*/React.createElement("dd", null, row.template_revision)), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u65E7\u5B9A\u989D"), /*#__PURE__*/React.createElement("dd", null, hours(row.old_unit_hours), " / \u4EF6")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u5EFA\u8BAE\u5B9A\u989D"), /*#__PURE__*/React.createElement("dd", null, hours(row.suggested_unit_hours, '暂无建议'), " / \u4EF6")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u5408\u683C\u6837\u672C"), /*#__PURE__*/React.createElement("dd", null, row.sample_count, " \u4E2A")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u672A\u9009\u7528\u5B9E\u4F8B"), /*#__PURE__*/React.createElement("dd", null, row.excluded_count, " \u4E2A")));
  }
  function Samples({
    preview,
    detail
  }) {
    const rows = preview.samples;
    return /*#__PURE__*/React.createElement("section", {
      className: "cad-samples",
      "aria-label": "\u91C7\u7528\u9884\u89C8\u6837\u672C"
    }, /*#__PURE__*/React.createElement("h4", null, "\u672C\u6B21\u91C7\u7528\u7684\u5408\u683C\u6837\u672C\uFF08", rows.length, "\uFF09"), /*#__PURE__*/React.createElement("table", {
      className: "ca-table"
    }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", null, "\u6279\u6B21 / \u5DE5\u5E8F"), /*#__PURE__*/React.createElement("th", null, "\u6570\u91CF"), /*#__PURE__*/React.createElement("th", null, "\u52A0\u5DE5\u5C0F\u65F6"), /*#__PURE__*/React.createElement("th", null, "\u5355\u4EF6 h"), /*#__PURE__*/React.createElement("th", null, "\u6765\u6E90\u4E0E\u4FEE\u8BA2"))), /*#__PURE__*/React.createElement("tbody", null, rows.map(row => /*#__PURE__*/React.createElement("tr", {
      key: row.sample_ref,
      "data-adoption-sample": row.sample_ref
    }, /*#__PURE__*/React.createElement("td", null, row.batch_code, /*#__PURE__*/React.createElement("small", null, row.operation_code)), /*#__PURE__*/React.createElement("td", null, row.completed_quantity), /*#__PURE__*/React.createElement("td", null, row.effective_processing_hours), /*#__PURE__*/React.createElement("td", null, row.unit_hours), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement("details", null, /*#__PURE__*/React.createElement("summary", null, "\u6A21\u677F\u4FEE\u8BA2 ", row.template_revision), /*#__PURE__*/React.createElement("div", null, "\u5B9E\u4F8B\uFF1A", row.sample_ref), /*#__PURE__*/React.createElement("div", null, "\u590D\u5236\u8BC1\u636E\uFF1A", row.lineage_evidence_ref), /*#__PURE__*/React.createElement("div", null, "\u6837\u672C\u4FEE\u8BA2\uFF1A", row.sample_revision))))))), detail && /*#__PURE__*/React.createElement("details", {
      className: "cad-records"
    }, /*#__PURE__*/React.createElement("summary", null, "\u6392\u9664\u4E0E\u672A\u5173\u8054\u5B9E\u4F8B\uFF08", detail.samples.filter(row => !row.selected).length, "\uFF09"), detail.samples.filter(row => !row.selected).map(row => /*#__PURE__*/React.createElement("div", {
      key: row.sample_ref
    }, row.batch_code, " \xB7 ", row.template_operation_ref === null ? '未关联' : '已排除', "\uFF1A", row.exclusion_reasons.map(item => item.message).join('；')))));
  }
  function Receipt({
    value
  }) {
    const d = value.data;
    return /*#__PURE__*/React.createElement("section", {
      "aria-label": "\u91C7\u7528\u9501\u5B9A\u56DE\u6267"
    }, /*#__PURE__*/React.createElement("p", {
      className: "cad-success",
      role: "status"
    }, "\u5DF2\u6838\u5B9E\u91C7\u7528\uFF0C\u65B0\u5B9A\u989D ", hours(d.new_unit_hours), " / \u4EF6\uFF0C\u6A21\u677F\u5B9A\u989D\u5DF2\u9501\u5B9A\u3002"), /*#__PURE__*/React.createElement("dl", {
      className: "cad-facts"
    }, [['原定额', hours(d.old_unit_hours)], ['新定额', hours(d.new_unit_hours)], ['修订变化', d.template_revision_before + ' → ' + d.template_revision_after], ['采用时间', d.adopted_at], ['声明人', d.declared_operator], ['本机操作者', d.application_operator], ['采用原因', d.reason], ['用户确认', d.confirmed ? '已明确确认' : '未确认']].map(([label, value]) => /*#__PURE__*/React.createElement("div", {
      key: label
    }, /*#__PURE__*/React.createElement("dt", null, label), /*#__PURE__*/React.createElement("dd", null, value)))), /*#__PURE__*/React.createElement("p", {
      className: "ca-muted"
    }, "\u8FD9\u662F\u672C\u6B21\u63D0\u4EA4\u7684\u6301\u4E45\u56DE\u6267\u3002", scope), /*#__PURE__*/React.createElement("div", {
      className: "cad-records"
    }, "\u56DE\u6267\uFF1A", value.receipt_ref, /*#__PURE__*/React.createElement("br", null), "\u91C7\u7EB3\u8BB0\u5F55\uFF1A", d.adoption_ref));
  }
  function Dialog({
    session: s,
    detail,
    stale,
    onRefresh
  }) {
    const {
        saved,
        preview
      } = s,
      pending = saved && saved.phase === 'pending',
      result = saved && saved.phase === 'committed' ? saved.receipt : null;
    const other = saved && detail && saved.baseline.template_operation_ref !== detail.suggestion.template_operation_ref;
    const row = saved ? saved.baseline : detail && detail.suggestion;
    const blocked = stale || other || !!s.storageError || !detail;
    const refresh = () => {
      s.setConsent(false);
      s.change(s.draft);
      if (typeof onRefresh === 'function') onRefresh();
    };
    return /*#__PURE__*/React.createElement(Modal, {
      title: result ? '模板采用与锁定回执' : pending ? '核实原采纳请求' : '预览并采用模板定额',
      icon: "check",
      onClose: s.close,
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        onClick: s.close
      }, pending ? '关闭并保留请求' : '关闭'), result ? /*#__PURE__*/React.createElement(Button, {
        icon: "check",
        onClick: s.finish
      }, "\u5B8C\u6210\u6838\u5B9E") : pending ? /*#__PURE__*/React.createElement(Button, {
        icon: "refresh-cw",
        busy: s.busy,
        onClick: s.lookup
      }, "\u67E5\u8BE2\u539F\u8BF7\u6C42") : /*#__PURE__*/React.createElement(React.Fragment, null, saved && /*#__PURE__*/React.createElement(Button, {
        disabled: s.busy || !!s.storageError,
        onClick: s.finish
      }, "\u7ED3\u675F\u672C\u6B21\u672A\u91C7\u7528"), /*#__PURE__*/React.createElement(Button, {
        icon: "refresh-cw",
        disabled: s.busy || typeof onRefresh !== 'function',
        onClick: refresh
      }, "\u660E\u786E\u5237\u65B0\u6240\u9009\u8BB0\u5F55"), /*#__PURE__*/React.createElement(Button, {
        icon: "search",
        busy: s.busy,
        disabled: blocked,
        onClick: s.inspect
      }, "\u8BFB\u53D6\u771F\u5B9E\u9884\u89C8"), /*#__PURE__*/React.createElement(Button, {
        icon: "check",
        className: "btn primary",
        busy: s.busy,
        disabled: blocked || !preview || !preview.validation.can_adopt || !s.consent,
        onClick: s.submit
      }, "\u786E\u8BA4\u91C7\u7528\u5E76\u9501\u5B9A")))
    }, /*#__PURE__*/React.createElement("div", {
      className: "modal-body cad-body"
    }, (s.error || s.storageError) && /*#__PURE__*/React.createElement("p", {
      className: "cad-notice",
      role: "alert"
    }, s.storageError || s.error), s.storageError && /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      onClick: s.sync
    }, "\u91CD\u8BFB\u6062\u590D\u8BB0\u5F55"), s.notice && /*#__PURE__*/React.createElement("p", {
      className: "cad-notice",
      role: "status"
    }, s.notice), other && /*#__PURE__*/React.createElement("p", {
      className: "cad-notice"
    }, "\u539F\u8BF7\u6C42\u5C5E\u4E8E\u53E6\u4E00\u6A21\u677F\uFF0C\u5F53\u524D\u9009\u62E9\u4E0D\u4F1A\u6539\u53D8\u539F\u8BF7\u6C42\u5BF9\u8C61\u3002\u8BF7\u5148\u6838\u5B9E\u539F\u56DE\u6267\u3002"), stale && !pending && !result && /*#__PURE__*/React.createElement("p", {
      className: "cad-notice"
    }, "\u6240\u9009\u5FEB\u7167\u5DF2\u5931\u6548\uFF0C\u8BF7\u660E\u786E\u5237\u65B0\u540E\u91CD\u65B0\u9884\u89C8\u3002"), /*#__PURE__*/React.createElement("p", {
      className: "ca-muted"
    }, scope), row && /*#__PURE__*/React.createElement(Facts, {
      row: row
    }), result ? /*#__PURE__*/React.createElement(Receipt, {
      value: result
    }) : pending ? /*#__PURE__*/React.createElement("dl", {
      className: "cad-facts"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u539F\u91C7\u7528\u539F\u56E0"), /*#__PURE__*/React.createElement("dd", null, saved.input.reason)), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u539F\u58F0\u660E\u4EBA"), /*#__PURE__*/React.createElement("dd", null, saved.input.declared_operator))) : /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "cad-fields"
    }, /*#__PURE__*/React.createElement("label", null, "\u91C7\u7528\u539F\u56E0", /*#__PURE__*/React.createElement("textarea", {
      "aria-label": "\u91C7\u7528\u539F\u56E0",
      rows: 2,
      maxLength: 2000,
      value: s.draft.reason,
      disabled: s.busy,
      onChange: e => s.change({
        ...s.draft,
        reason: e.target.value
      })
    })), /*#__PURE__*/React.createElement("label", null, "\u58F0\u660E\u4EBA", /*#__PURE__*/React.createElement("input", {
      "aria-label": "\u58F0\u660E\u4EBA",
      type: "text",
      maxLength: 100,
      value: s.draft.declared_operator,
      disabled: s.busy,
      onChange: e => s.change({
        ...s.draft,
        declared_operator: e.target.value
      })
    }), /*#__PURE__*/React.createElement("small", null, "\u4E1A\u52A1\u58F0\u660E\u72EC\u7ACB\u7559\u75D5\uFF0C\u4E0D\u4EE3\u8868\u767B\u5F55\u8EAB\u4EFD\uFF1B\u672C\u673A\u64CD\u4F5C\u8005\u53E6\u7531\u670D\u52A1\u8BB0\u5F55\u3002"))), preview && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("p", {
      className: preview.validation.can_adopt ? 'cad-success' : 'cad-notice',
      role: "status"
    }, preview.validation.can_adopt ? '当前预览可采用：来源、旧定额和合格样本已核对。' : '当前不能采用。'), preview.validation.issues.map(item => /*#__PURE__*/React.createElement("p", {
      className: "cad-notice",
      key: item.code
    }, item.message)), preview.quota_lock && /*#__PURE__*/React.createElement("p", {
      className: "cad-notice"
    }, "\u5DF2\u9501\u5B9A\u5B9A\u989D ", hours(preview.quota_lock.locked_unit_hours), " / \u4EF6\uFF1B\u9501\u5B9A\u65F6\u95F4 ", preview.quota_lock.locked_at, "\u3002"), /*#__PURE__*/React.createElement(Samples, {
      preview: preview,
      detail: detail
    }), preview.validation.can_adopt && /*#__PURE__*/React.createElement("label", {
      className: "cad-consent"
    }, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      checked: s.consent,
      disabled: s.busy || blocked,
      onChange: e => s.setConsent(e.target.checked)
    }), /*#__PURE__*/React.createElement("span", null, "\u6211\u5DF2\u6838\u5BF9\u6837\u672C\u3001\u65E7\u5B9A\u989D\u4E0E\u5EFA\u8BAE\u503C\uFF0C\u786E\u8BA4\u91C7\u7528\u5E76\u9501\u5B9A\uFF0C\u4EC5\u4F9B\u672A\u6765\u6A21\u677F\u4F7F\u7528\u3002")), /*#__PURE__*/React.createElement("p", {
      className: "ca-muted"
    }, "\u9884\u89C8\u65F6\u95F4\uFF1A", preview.generated_at, preview.write_context.expires_at && ' · 有效至 ' + preview.write_context.expires_at))), /*#__PURE__*/React.createElement("details", {
      className: "cad-records"
    }, /*#__PURE__*/React.createElement("summary", null, "\u5BF9\u8C61\u4E0E\u8BF7\u6C42\u8BB0\u5F55"), row && /*#__PURE__*/React.createElement("div", null, "\u6A21\u677F\uFF1A", row.template_operation_ref, /*#__PURE__*/React.createElement("br", null), "\u6A21\u677F\u5FEB\u7167\uFF1A", row.template_snapshot), saved && /*#__PURE__*/React.createElement("div", {
      "data-adoption-key": saved.request_key
    }, "\u539F\u8BF7\u6C42\uFF1A", saved.request_key))));
  }
  function Styles() {
    return /*#__PURE__*/React.createElement("style", null, `
      .plana.calibration-adoption{display:inline-flex;gap:8px;align-items:center;flex-wrap:wrap;width:auto;padding:0;max-width:100%;min-width:0;color:var(--ui-text);letter-spacing:0}
      .calibration-adoption *{box-sizing:border-box;letter-spacing:0}.calibration-adoption .modal-bg{z-index:1100}
      .calibration-adoption .modal.lg{width:900px;max-width:calc(100vw - 48px);max-height:calc(100vh - 48px);display:flex;flex-direction:column;color:var(--ui-text);background:var(--ui-card-bg)}
      .calibration-adoption .modal-head,.calibration-adoption .modal-f{flex-shrink:0}.calibration-adoption .modal-f{gap:8px;padding:12px 20px}
      .calibration-adoption .cad-body{padding:12px 22px;overflow:auto;min-height:0;max-height:70vh;font-size:13px;line-height:1.6;color:var(--ui-text)}
      .calibration-adoption .cad-facts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px 24px;margin:0;padding:12px 0;border-bottom:1px solid var(--ui-border)}
      .calibration-adoption dt,.calibration-adoption small{color:var(--ui-info-muted);font-size:12px}.calibration-adoption dd{margin:3px 0 0;overflow-wrap:anywhere}
      .calibration-adoption .cad-fields{display:grid;grid-template-columns:2fr 1fr;gap:16px;padding:14px 0}.calibration-adoption label{display:grid;gap:5px;min-width:0;color:var(--ui-text)}
      .calibration-adoption textarea,.calibration-adoption input[type=text]{width:100%;color:var(--ui-text);background:var(--ui-card-bg);font:inherit;border:1px solid var(--ui-border);border-radius:4px;padding:8px 10px}
      .calibration-adoption textarea{resize:vertical;min-height:66px;max-height:180px}.calibration-adoption .cad-consent{display:flex;align-items:flex-start;gap:8px;margin:14px 0}
      .calibration-adoption .cad-consent input{flex:none;width:16px;height:16px;margin-top:3px;accent-color:var(--ui-info-text)}
      .calibration-adoption .cad-notice{padding:8px 12px;border-left:3px solid var(--ui-warning);background:var(--ui-surface-muted);overflow-wrap:anywhere}
      .calibration-adoption .cad-success{color:var(--ui-success-text)}.calibration-adoption .cad-records{font-size:12px;color:var(--ui-info-muted);overflow-wrap:anywhere;padding-top:10px}
      .calibration-adoption h4{font-size:13px;margin:12px 0 8px}.calibration-adoption .cad-samples{min-width:0}.calibration-adoption .ca-table{min-width:0;font-size:12px}
      .calibration-adoption .ca-table th,.calibration-adoption .ca-table td{padding:7px 8px}.calibration-adoption button{white-space:normal;max-width:100%}
      .calibration-adoption .cad-inline{font-size:12px;color:var(--ui-info-muted);max-width:380px;overflow-wrap:anywhere}
      @media(max-width:700px){.calibration-adoption .cad-fields,.calibration-adoption .cad-facts{grid-template-columns:1fr}.calibration-adoption .cad-body{padding:12px}}
    `);
  }
  window.CalibrationAdoptionControls = {
    Button,
    Dialog,
    Styles
  };
})();
