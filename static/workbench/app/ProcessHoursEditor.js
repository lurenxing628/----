(function () {
  'use strict';

  const C = window.APSResourceContract,
    P = window.APSProcessContract,
    E = window.ProcessStageEditor,
    {
      Button,
      Modal,
      Issues
    } = window.ResourceControls;
  const numericText = value => value === null ? '' : String(value);
  function mergedGroups(entity) {
    const refs = new Set(E.active(entity).map(row => row.external_group_ref));
    return entity.external_groups.filter(row => row.merge_mode === 'merged' && refs.has(row.ref));
  }
  function build(entity) {
    return {
      operations: Object.fromEntries(E.active(entity).map(row => [row.ref, {
        ref: row.ref,
        setup_hours: numericText(row.setup_hours),
        unit_hours: numericText(row.unit_hours),
        external_days: numericText(row.external_days)
      }])),
      groups: Object.fromEntries(mergedGroups(entity).map(row => [row.ref, numericText(row.total_days)]))
    };
  }
  function reconcile(draft, before, after) {
    const next = build(after),
      original = build(before),
      old = new Map(before.operations.map(row => [row.ref, row]));
    E.active(after).forEach(row => {
      const current = draft.operations[row.ref],
        previous = original.operations[row.ref],
        fresh = next.operations[row.ref];
      if (!current || !previous || old.get(row.ref).source !== row.source) return;
      (row.source === 'internal' ? ['setup_hours', 'unit_hours'] : ['external_days']).forEach(key => {
        if (current[key] !== previous[key]) fresh[key] = current[key];
      });
    });
    mergedGroups(after).forEach(row => {
      if (C.own(original.groups, row.ref) && C.own(draft.groups, row.ref) && draft.groups[row.ref] !== original.groups[row.ref]) next.groups[row.ref] = draft.groups[row.ref];
    });
    return next;
  }
  function number(text, label, positive) {
    if (text === null || text === undefined || String(text).trim() === '' || !Number.isFinite(Number(text)) || (positive ? Number(text) <= 0 : Number(text) < 0)) throw C.failure(label + (positive ? '必须填写大于 0 的数。' : '必须填写大于等于 0 的数。'));
    return Number(text);
  }
  function input(entity, draft, pageSize) {
    const merged = new Set(mergedGroups(entity).map(row => row.ref));
    const operations = E.active(entity).map(row => {
      const current = draft.operations[row.ref];
      try {
        if (row.source === 'external') return {
          ref: row.ref,
          external_days: P.groupCycle(row, entity.external_groups) || merged.has(row.external_group_ref) && current.external_days.trim() === '' && !row.issues.some(item => item.code === 'value_invalid') ? null : number(current.external_days, '工序 ' + row.sequence + ' 外协周期', true)
        };
        if (row.source !== 'internal') throw C.failure('工序 ' + row.sequence + ' 请先选定归属。');
        return {
          ref: row.ref,
          setup_hours: number(current.setup_hours, '工序 ' + row.sequence + ' 换型工时', false),
          unit_hours: number(current.unit_hours, '工序 ' + row.sequence + ' 单件工时', false)
        };
      } catch (error) {
        error.locate_page = Math.floor(entity.operations.indexOf(row) / pageSize) + 1;
        throw error;
      }
    });
    if (!operations.length) throw C.failure('尚无有效工序，不能保存工时。');
    return {
      operations,
      groups: mergedGroups(entity).map(row => ({
        ref: row.ref,
        total_days: number(draft.groups[row.ref], '外协组 ' + row.start_sequence + ' 至 ' + row.end_sequence + ' 总周期', true)
      })),
      confirm_zero_unit_hours: false
    };
  }
  function zeroRows(entity, body) {
    const before = new Map(entity.operations.map(row => [row.ref, row]));
    return body.operations.filter(row => {
      const old = before.get(row.ref);
      return row.unit_hours === 0 && (old.confirmation.hours.state !== 'confirmed' || old.unit_hours !== row.unit_hours || old.setup_hours !== row.setup_hours);
    }).map(row => before.get(row.ref));
  }
  function ProcessHoursEditor({
    adapter,
    result,
    command,
    disabled,
    saved,
    onDirty,
    onOverlay,
    onFileAction
  }) {
    const model = E.useDraft({
      result,
      adapter,
      stage: 'hours',
      build,
      reconcile,
      saved,
      onDirty
    });
    const entity = model.base.data,
      draft = model.draft,
      paging = E.usePage(entity.operations),
      [zero, setZero] = React.useState(null);
    const blocked = disabled || command.locked || command.phase === 'done',
      stageReason = E.reason(model, adapter, 'hours');
    const editBlocked = blocked || entity.workflow.source.state !== 'confirmed' || entity.capabilities.stage_confirm !== true;
    React.useEffect(() => {
      setZero(null);
    }, [draft, model.base, model.review, disabled]);
    React.useEffect(() => {
      if (onOverlay) onOverlay(!!zero);
      return () => {
        if (onOverlay) onOverlay(false);
      };
    }, [!!zero, onOverlay]);
    function change(ref, patch) {
      model.edit(current => ({
        ...current,
        operations: {
          ...current.operations,
          [ref]: {
            ...current.operations[ref],
            ...patch
          }
        }
      }));
    }
    function changeGroup(ref, total) {
      model.edit(current => ({
        ...current,
        groups: {
          ...current.groups,
          [ref]: total
        }
      }));
    }
    async function save(acknowledged = false) {
      if (blocked || stageReason) return;
      try {
        const body = input(entity, draft, paging.page.size),
          rows = zeroRows(entity, body);
        if (rows.length && !acknowledged) {
          setZero(rows);
          return;
        }
        setZero(null);
        model.setError(null);
        await command.submit('process', 'hours_confirm', entity.ref, entity.write_context, {
          ...body,
          confirm_zero_unit_hours: acknowledged === true
        });
      } catch (error) {
        model.setError(error);
      }
    }
    const active = E.active(entity),
      internal = paging.rows.filter(row => row.source !== 'external'),
      external = paging.rows.filter(row => row.source === 'external');
    function operation(row) {
      return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("b", null, row.sequence), " ", row.label, /*#__PURE__*/React.createElement("div", {
        className: "muted"
      }, row.op_type_label || '未选工种'));
    }
    function record(row) {
      return /*#__PURE__*/React.createElement(React.Fragment, null, row.status !== 'active' ? '已停用工序' : /*#__PURE__*/React.createElement(E.Confirmation, {
        record: row.confirmation && row.confirmation.hours
      }), /*#__PURE__*/React.createElement(Issues, {
        issues: row.issues.filter(item => item.code !== 'zero_unit_hours_review')
      }));
    }
    function cell(row, key, title, positive = false) {
      const current = draft.operations[row.ref];
      return /*#__PURE__*/React.createElement("input", {
        className: "wt-in",
        type: "number",
        step: "any",
        min: "0",
        "aria-label": '工序 ' + row.sequence + ' ' + title,
        placeholder: positive ? '大于 0' : '未填写',
        value: current ? current[key] : numericText(row[key]),
        disabled: editBlocked || !current,
        onChange: event => change(row.ref, {
          [key]: event.target.value
        })
      });
    }
    return /*#__PURE__*/React.createElement("section", {
      "data-process-hours-editor": true
    }, /*#__PURE__*/React.createElement("div", {
      className: "toolbar"
    }, /*#__PURE__*/React.createElement(E.Search, {
      paging: paging,
      disabled: blocked
    }), /*#__PURE__*/React.createElement("span", null, "\u5171 ", active.length, " \u9053\u6709\u6548\u5DE5\u5E8F"), /*#__PURE__*/React.createElement("span", {
      className: "tb-spacer"
    }), /*#__PURE__*/React.createElement(window.ProcessFileButtons, {
      capabilities: entity.capabilities,
      disabled: blocked,
      hoursOnly: true,
      onAction: onFileAction
    })), /*#__PURE__*/React.createElement("section", {
      className: "process-hours-section",
      "aria-label": "\u81EA\u5236\u5DE5\u65F6"
    }, /*#__PURE__*/React.createElement("h3", null, "\u81EA\u5236\u5DE5\u65F6"), /*#__PURE__*/React.createElement("p", {
      className: "muted"
    }, "\u52A0\u5DE5\u65F6\u957F = \u6362\u578B\u5DE5\u65F6 + \u5355\u4EF6\u5DE5\u65F6 \xD7 \u6279\u6B21\u6570\u91CF\u3002"), /*#__PURE__*/React.createElement("div", {
      className: "wb-table-frame"
    }, /*#__PURE__*/React.createElement("table", {
      className: "tbl wb-table wb-table--editable",
      "aria-label": "\u81EA\u5236\u5DE5\u65F6\u660E\u7EC6"
    }, /*#__PURE__*/React.createElement("caption", {
      className: "wb-visually-hidden"
    }, "\u81EA\u5236\u5DE5\u65F6\u660E\u7EC6"), /*#__PURE__*/React.createElement("colgroup", null, /*#__PURE__*/React.createElement("col", {
      style: {
        width: '32%'
      }
    }), /*#__PURE__*/React.createElement("col", {
      style: {
        width: '22%'
      }
    }), /*#__PURE__*/React.createElement("col", {
      style: {
        width: '22%'
      }
    }), /*#__PURE__*/React.createElement("col", {
      style: {
        width: '24%'
      }
    })), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u5DE5\u5E8F / \u5DE5\u79CD"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u6362\u578B\u5DE5\u65F6\uFF08\u5C0F\u65F6\uFF09"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u5355\u4EF6\u5DE5\u65F6\uFF08\u5C0F\u65F6\uFF09"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u4FDD\u5B58\u8BB0\u5F55"))), /*#__PURE__*/React.createElement("tbody", null, internal.map(row => /*#__PURE__*/React.createElement("tr", {
      key: row.ref
    }, /*#__PURE__*/React.createElement("td", null, operation(row)), /*#__PURE__*/React.createElement("td", null, cell(row, 'setup_hours', '换型工时')), /*#__PURE__*/React.createElement("td", null, cell(row, 'unit_hours', '单件工时')), /*#__PURE__*/React.createElement("td", null, record(row)))), !internal.length && /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("td", {
      colSpan: 4
    }, "\u5F53\u524D\u9875\u6CA1\u6709\u81EA\u5236\u5DE5\u5E8F\u3002")))))), /*#__PURE__*/React.createElement("section", {
      className: "process-hours-section",
      "aria-label": "\u5916\u534F\u5468\u671F"
    }, /*#__PURE__*/React.createElement("h3", null, "\u5916\u534F\u5468\u671F"), /*#__PURE__*/React.createElement("div", {
      className: "wb-table-frame"
    }, /*#__PURE__*/React.createElement("table", {
      className: "tbl wb-table wb-table--editable",
      "aria-label": "\u5916\u534F\u5468\u671F\u660E\u7EC6"
    }, /*#__PURE__*/React.createElement("caption", {
      className: "wb-visually-hidden"
    }, "\u5916\u534F\u5468\u671F\u660E\u7EC6"), /*#__PURE__*/React.createElement("colgroup", null, /*#__PURE__*/React.createElement("col", {
      style: {
        width: '32%'
      }
    }), /*#__PURE__*/React.createElement("col", {
      style: {
        width: '22%'
      }
    }), /*#__PURE__*/React.createElement("col", {
      style: {
        width: '22%'
      }
    }), /*#__PURE__*/React.createElement("col", {
      style: {
        width: '24%'
      }
    })), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u5DE5\u5E8F / \u5DE5\u79CD"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u4F9B\u5E94\u5546"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u5468\u671F\uFF08\u5929\uFF09"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u4FDD\u5B58\u8BB0\u5F55"))), /*#__PURE__*/React.createElement("tbody", null, external.map(row => {
      const cycle = P.groupCycle(row, entity.external_groups);
      return /*#__PURE__*/React.createElement("tr", {
        key: row.ref
      }, /*#__PURE__*/React.createElement("td", null, operation(row)), /*#__PURE__*/React.createElement("td", null, row.supplier_label || '未选供应商'), /*#__PURE__*/React.createElement("td", null, cycle ? /*#__PURE__*/React.createElement("span", {
        className: "process-group-cycle",
        "data-process-cycle-group": row.external_group_ref
      }, cycle, /*#__PURE__*/React.createElement("small", null, "\u5728\u4E0B\u65B9\u5916\u534F\u7EC4\u586B\u5199\u7EDF\u4E00\u5468\u671F")) : cell(row, 'external_days', '外协周期', true)), /*#__PURE__*/React.createElement("td", null, record(row)));
    }), !external.length && /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("td", {
      colSpan: 4
    }, "\u5F53\u524D\u9875\u6CA1\u6709\u5916\u534F\u5DE5\u5E8F\u3002"))))), !!mergedGroups(entity).length && /*#__PURE__*/React.createElement(E.Groups, {
      rows: mergedGroups(entity),
      totals: draft.groups,
      disabled: editBlocked,
      onTotal: changeGroup
    })), /*#__PURE__*/React.createElement(E.Pager, {
      paging: paging,
      disabled: blocked
    }), /*#__PURE__*/React.createElement(E.Feedback, {
      model: model,
      disabled: blocked,
      paging: paging
    }), /*#__PURE__*/React.createElement("div", {
      className: "pd-foot"
    }, /*#__PURE__*/React.createElement("span", {
      className: "muted"
    }, "\u4FDD\u5B58\u5168\u90E8 ", active.length, " \u9053\u6709\u6548\u5DE5\u5E8F\uFF0C\u5305\u542B\u5176\u4ED6\u9875\u548C\u7B5B\u9009\u9690\u85CF\u7684\u5DE5\u5E8F\u3002"), /*#__PURE__*/React.createElement(Button, {
      className: "btn primary",
      icon: "check",
      disabled: blocked,
      reason: stageReason,
      onClick: () => save()
    }, "\u4FDD\u5B58\u5DE5\u65F6")), zero && ReactDOM.createPortal(/*#__PURE__*/React.createElement("div", {
      className: "plana process-detail"
    }, /*#__PURE__*/React.createElement(Modal, {
      title: "\u6309\u96F6\u5355\u4EF6\u5DE5\u65F6\u4FDD\u5B58",
      icon: "check",
      onClose: () => setZero(null),
      locked: blocked,
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        disabled: blocked,
        onClick: () => setZero(null)
      }, "\u8FD4\u56DE\u4FEE\u6539"), /*#__PURE__*/React.createElement(Button, {
        className: "btn primary",
        icon: "check",
        disabled: blocked,
        onClick: () => save(true)
      }, "\u6309 0 \u4FDD\u5B58"))
    }, /*#__PURE__*/React.createElement("div", {
      className: "modal-b"
    }, /*#__PURE__*/React.createElement("p", null, "\u4EE5\u4E0B\u5DE5\u5E8F\u7684\u5355\u4EF6\u5DE5\u65F6\u4E3A 0\uFF0C\u6392\u4EA7\u53EA\u8BA1\u7B97\u6362\u578B\u5DE5\u65F6\uFF0C\u6570\u91CF\u589E\u52A0\u4E0D\u4F1A\u589E\u52A0\u52A0\u5DE5\u65F6\u957F\u3002"), /*#__PURE__*/React.createElement("ul", null, zero.map(row => /*#__PURE__*/React.createElement("li", {
      key: row.ref
    }, "\u5DE5\u5E8F ", row.sequence, " \xB7 ", row.label)))))), document.body));
  }
  window.ProcessHoursEditor = ProcessHoursEditor;
})();
