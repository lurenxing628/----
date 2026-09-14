(function () {
  'use strict';

  const {
      Button,
      Modal
    } = window.ResourceControls,
    {
      hours
    } = window.CalibrationControls;
  const time = value => value ? window.WorkbenchFormat.dateTime(value, {
    seconds: true
  }) : '未知';
  const scope = '已有批次工时、历史计划和现场记录保持原样。新批次使用前，要在基础资料里重新确认模板工时。';
  function Facts({
    row
  }) {
    return /*#__PURE__*/React.createElement("dl", {
      className: "cad-facts"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u6A21\u677F\u5DE5\u5E8F"), /*#__PURE__*/React.createElement("dd", null, row.part_no, " \xB7 ", row.sequence, " ", row.operation_label)), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u6A21\u677F\u7248\u672C"), /*#__PURE__*/React.createElement("dd", null, "\u7B2C ", row.template_revision, " \u7248")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u539F\u5B9A\u989D"), /*#__PURE__*/React.createElement("dd", null, hours(row.old_unit_hours), " / \u4EF6")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u5EFA\u8BAE\u5B9A\u989D"), /*#__PURE__*/React.createElement("dd", null, hours(row.suggested_unit_hours, '暂无建议'), " / \u4EF6")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u53EF\u7528\u8BB0\u5F55\u6570"), /*#__PURE__*/React.createElement("dd", null, row.sample_count, " \u6761")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u672A\u91C7\u7528\u8BB0\u5F55\u6570"), /*#__PURE__*/React.createElement("dd", null, row.excluded_count, " \u6761")));
  }
  function Samples({
    preview,
    detail
  }) {
    const rows = preview.samples;
    return /*#__PURE__*/React.createElement("section", {
      className: "cad-samples",
      "aria-label": "\u91C7\u7528\u9884\u68C0\u7684\u5B8C\u5DE5\u8BB0\u5F55"
    }, /*#__PURE__*/React.createElement("h4", null, "\u672C\u6B21\u91C7\u7528\u7684\u53EF\u7528\u5B8C\u5DE5\u8BB0\u5F55\uFF08", rows.length, " \u6761\uFF09"), /*#__PURE__*/React.createElement("table", {
      className: "ca-table"
    }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", null, "\u6279\u6B21 / \u5DE5\u5E8F"), /*#__PURE__*/React.createElement("th", null, "\u6570\u91CF"), /*#__PURE__*/React.createElement("th", null, "\u52A0\u5DE5\u5DE5\u65F6\uFF08\u5C0F\u65F6\uFF09"), /*#__PURE__*/React.createElement("th", null, "\u5355\u4EF6\uFF08\u5C0F\u65F6\uFF09"), /*#__PURE__*/React.createElement("th", null, "\u6765\u6E90\u4E0E\u7248\u672C"))), /*#__PURE__*/React.createElement("tbody", null, rows.map(row => /*#__PURE__*/React.createElement("tr", {
      key: row.sample_ref,
      "data-adoption-sample": row.sample_ref
    }, /*#__PURE__*/React.createElement("td", null, row.batch_code, /*#__PURE__*/React.createElement("small", null, row.operation_code)), /*#__PURE__*/React.createElement("td", null, row.completed_quantity), /*#__PURE__*/React.createElement("td", null, row.effective_processing_hours), /*#__PURE__*/React.createElement("td", null, row.unit_hours), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement("details", null, /*#__PURE__*/React.createElement("summary", null, "\u6A21\u677F\u7B2C ", row.template_revision, " \u7248"), /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      entries: {
        '完工记录编号': row.sample_ref,
        '来源证据编号': row.lineage_evidence_ref,
        '记录版本': row.sample_revision
      }
    }))))))), detail && /*#__PURE__*/React.createElement("details", {
      className: "cad-records"
    }, /*#__PURE__*/React.createElement("summary", null, "\u6392\u9664\u4E0E\u672A\u5173\u8054\u7684\u8BB0\u5F55\uFF08", detail.samples.filter(row => !row.selected).length, " \u6761\uFF09"), detail.samples.filter(row => !row.selected).map(row => /*#__PURE__*/React.createElement("div", {
      key: row.sample_ref
    }, row.batch_code, " \xB7 ", row.template_operation_ref === null ? '未关联' : '已排除', "\uFF1A", row.exclusion_reasons.map(item => item.message).join('；')))));
  }
  function Receipt({
    value
  }) {
    const d = value.data;
    return /*#__PURE__*/React.createElement("section", {
      "aria-label": "\u91C7\u7528\u4E0E\u9501\u5B9A\u7ED3\u679C"
    }, /*#__PURE__*/React.createElement("p", {
      className: "cad-success",
      role: "status"
    }, window.WorkbenchTerms.outcomes.done('采用', '新定额 ' + hours(d.new_unit_hours) + ' / 件，定额已锁定（来自工时校准）')), /*#__PURE__*/React.createElement("dl", {
      className: "cad-facts"
    }, [['原定额', hours(d.old_unit_hours)], ['新定额', hours(d.new_unit_hours)], ['版本变化', '第 ' + d.template_revision_before + ' 版 → 第 ' + d.template_revision_after + ' 版'], ['采用时间', time(d.adopted_at)], ['经办人', d.declared_operator], ['记录人', d.application_operator], ['采用原因', d.reason], ['用户确认', d.confirmed ? '已确认' : '未确认']].map(([label, value]) => /*#__PURE__*/React.createElement("div", {
      key: label
    }, /*#__PURE__*/React.createElement("dt", null, label), /*#__PURE__*/React.createElement("dd", null, value)))), /*#__PURE__*/React.createElement("p", {
      className: "ca-muted"
    }, "\u8FD9\u662F\u672C\u6B21\u63D0\u4EA4\u7559\u4E0B\u7684\u7ED3\u679C\u8BB0\u5F55\u3002", scope), /*#__PURE__*/React.createElement("div", {
      className: "cad-records"
    }, /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      entries: {
        '结果编号': value.receipt_ref,
        '采用记录编号': d.adoption_ref
      }
    })));
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
      title: result ? '模板采用与锁定结果' : pending ? '查询上次采用结果' : '预检并采用模板定额',
      icon: "check",
      onClose: s.close,
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        onClick: s.close
      }, pending ? '关闭并保留上次操作' : '关闭'), result ? /*#__PURE__*/React.createElement(Button, {
        icon: "check",
        onClick: s.finish
      }, "\u5B8C\u6210") : pending ? /*#__PURE__*/React.createElement(Button, {
        icon: "refresh-cw",
        busy: s.busy,
        onClick: s.lookup
      }, window.WorkbenchTerms.actions.query_result) : /*#__PURE__*/React.createElement(React.Fragment, null, saved && /*#__PURE__*/React.createElement(Button, {
        disabled: s.busy || !!s.storageError,
        onClick: s.finish
      }, "\u7ED3\u675F\u672C\u6B21\u672A\u91C7\u7528"), /*#__PURE__*/React.createElement(Button, {
        icon: "refresh-cw",
        disabled: s.busy || typeof onRefresh !== 'function',
        onClick: refresh
      }, "\u5237\u65B0\u6240\u9009\u6A21\u677F"), /*#__PURE__*/React.createElement(Button, {
        icon: "search",
        busy: s.busy,
        disabled: blocked,
        onClick: s.inspect
      }, "\u8BFB\u53D6\u771F\u5B9E\u9884\u68C0"), /*#__PURE__*/React.createElement(Button, {
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
    }, "\u5237\u65B0\u4E0A\u6B21\u64CD\u4F5C\u8BB0\u5F55"), s.notice && /*#__PURE__*/React.createElement("p", {
      className: "cad-notice",
      role: "status"
    }, s.notice), other && /*#__PURE__*/React.createElement("p", {
      className: "cad-notice"
    }, "\u4E0A\u6B21\u64CD\u4F5C\u5C5E\u4E8E\u53E6\u4E00\u4E2A\u6A21\u677F\uFF0C\u5F53\u524D\u9009\u62E9\u4E0D\u4F1A\u6539\u52A8\u5B83\u3002\u8BF7\u5148\u70B9\u300C\u67E5\u8BE2\u7ED3\u679C\u300D\u786E\u8BA4\u4E0A\u6B21\u7ED3\u679C\u3002"), stale && !pending && !result && /*#__PURE__*/React.createElement("p", {
      className: "cad-notice"
    }, window.WorkbenchTerms.outcomes.stale), /*#__PURE__*/React.createElement("p", {
      className: "ca-muted"
    }, scope), row && /*#__PURE__*/React.createElement(Facts, {
      row: row
    }), result ? /*#__PURE__*/React.createElement(Receipt, {
      value: result
    }) : pending ? /*#__PURE__*/React.createElement("dl", {
      className: "cad-facts"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u539F\u91C7\u7528\u539F\u56E0"), /*#__PURE__*/React.createElement("dd", null, saved.input.reason)), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u539F\u7ECF\u529E\u4EBA"), /*#__PURE__*/React.createElement("dd", null, saved.input.declared_operator))) : /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
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
    })), /*#__PURE__*/React.createElement("label", null, "\u7ECF\u529E\u4EBA", /*#__PURE__*/React.createElement("input", {
      "aria-label": "\u7ECF\u529E\u4EBA",
      type: "text",
      maxLength: 100,
      value: s.draft.declared_operator,
      disabled: s.busy,
      onChange: e => s.change({
        ...s.draft,
        declared_operator: e.target.value
      })
    }), /*#__PURE__*/React.createElement("small", null, "\u7ECF\u529E\u4EBA\u5355\u72EC\u7559\u75D5\uFF0C\u4E0D\u4EE3\u8868\u767B\u5F55\u8EAB\u4EFD\uFF1B\u8BB0\u5F55\u4EBA\u7531\u7CFB\u7EDF\u53E6\u884C\u8BB0\u5F55\u3002"))), preview && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("p", {
      className: preview.validation.can_adopt ? 'cad-success' : 'cad-notice',
      role: "status"
    }, preview.validation.can_adopt ? '当前预检可以采用：来源、原定额和可用完工记录已核对。' : '当前不能采用。'), preview.validation.issues.map(item => /*#__PURE__*/React.createElement("p", {
      className: "cad-notice",
      key: item.code
    }, item.message)), preview.quota_lock && /*#__PURE__*/React.createElement("p", {
      className: "cad-notice"
    }, "\u5B9A\u989D\u5DF2\u9501\u5B9A\uFF08\u6765\u81EA\u5DE5\u65F6\u6821\u51C6\uFF09\uFF1A", hours(preview.quota_lock.locked_unit_hours), " / \u4EF6\uFF1B\u9501\u5B9A\u65F6\u95F4 ", time(preview.quota_lock.locked_at), "\u3002"), /*#__PURE__*/React.createElement(Samples, {
      preview: preview,
      detail: detail
    }), preview.validation.can_adopt && /*#__PURE__*/React.createElement("label", {
      className: "cad-consent"
    }, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      checked: s.consent,
      disabled: s.busy || blocked,
      onChange: e => s.setConsent(e.target.checked)
    }), /*#__PURE__*/React.createElement("span", null, "\u6211\u5DF2\u6838\u5BF9\u5B8C\u5DE5\u8BB0\u5F55\u3001\u539F\u5B9A\u989D\u4E0E\u5EFA\u8BAE\u503C\uFF0C\u786E\u8BA4\u91C7\u7528\u5E76\u9501\u5B9A\uFF0C\u53EA\u7528\u4E8E\u4EE5\u540E\u65B0\u589E\u7684\u5DE5\u5E8F\u3002")), /*#__PURE__*/React.createElement("p", {
      className: "ca-muted"
    }, "\u9884\u68C0\u65F6\u95F4\uFF1A", time(preview.generated_at), preview.write_context.expires_at && ' · 有效至 ' + time(preview.write_context.expires_at)))), /*#__PURE__*/React.createElement("div", {
      className: "cad-records",
      ...(saved ? {
        'data-adoption-key': saved.request_key
      } : {})
    }, /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      entries: {
        ...(row ? {
          '模板工序编号': row.template_operation_ref,
          '模板数据版本': row.template_snapshot
        } : {}),
        ...(saved ? {
          '操作编号': saved.request_key
        } : {})
      }
    }))));
  }
  function Styles() {
    return null;
  }
  window.CalibrationAdoptionControls = {
    Button,
    Dialog,
    Styles
  };
})();
