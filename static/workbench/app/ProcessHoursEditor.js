(function () {
  'use strict';

  const C = window.APSResourceContract,
    P = window.APSProcessContract,
    E = window.ProcessStageEditor,
    {
      Button
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
        external_days: numericText(row.external_days),
        confirmed: !!(row.confirmation && row.confirmation.hours.state === 'confirmed')
      }])),
      groups: Object.fromEntries(mergedGroups(entity).map(row => [row.ref, numericText(row.total_days)])),
      zero: false
    };
  }
  function reconcile(draft, before, after) {
    const next = build(after),
      original = build(before),
      old = new Map(before.operations.map(row => [row.ref, row]));
    const oldGroups = new Map(before.external_groups.map(row => [row.ref, row])),
      newGroups = new Map(after.external_groups.map(row => [row.ref, row]));
    E.active(after).forEach(row => {
      const current = draft.operations[row.ref],
        previous = original.operations[row.ref],
        fresh = next.operations[row.ref];
      fresh.confirmed = false;
      if (!current || !previous || old.get(row.ref).source !== row.source) return;
      const fields = row.source === 'internal' ? ['setup_hours', 'unit_hours'] : ['external_days'];
      fields.forEach(key => {
        if (current[key] !== previous[key]) fresh[key] = current[key];
      });
      fresh.confirmed = E.same(old.get(row.ref), row) && E.same(oldGroups.get(row.external_group_ref), newGroups.get(row.external_group_ref)) && current.confirmed;
    });
    mergedGroups(after).forEach(row => {
      if (C.own(original.groups, row.ref) && C.own(draft.groups, row.ref) && draft.groups[row.ref] !== original.groups[row.ref]) next.groups[row.ref] = draft.groups[row.ref];
    });
    return next;
  }
  function number(text, label, positive) {
    if (text === null || text === undefined || String(text).trim() === '' || !Number.isFinite(Number(text)) || (positive ? Number(text) <= 0 : Number(text) < 0)) throw C.failure(label + (positive ? '必须填写大于 0 的有限数。' : '必须填写大于等于 0 的有限数；空值不能按 0 保存。'));
    return Number(text);
  }
  function input(entity, draft) {
    const merged = new Set(mergedGroups(entity).map(row => row.ref));
    const operations = E.active(entity).map(row => {
      const current = draft.operations[row.ref];
      if (!current.confirmed) throw C.failure('请明确勾选确认工序 ' + row.sequence + ' 的工时 / 周期。');
      if (row.source === 'external') return {
        ref: row.ref,
        external_days: P.groupCycle(row, entity.external_groups) || merged.has(row.external_group_ref) && current.external_days.trim() === '' && !row.issues.some(item => item.code === 'value_invalid') ? null : number(current.external_days, '工序 ' + row.sequence + ' 外协周期', true)
      };
      if (row.source !== 'internal') throw C.failure('工序 ' + row.sequence + ' 尚未明确归属。');
      return {
        ref: row.ref,
        setup_hours: number(current.setup_hours, '工序 ' + row.sequence + ' 换型工时', false),
        unit_hours: number(current.unit_hours, '工序 ' + row.sequence + ' 单件工时', false)
      };
    });
    if (!operations.length) throw C.failure('尚无有效工序，不能保存工时。');
    if (operations.some(row => row.unit_hours === 0) && !draft.zero) throw C.failure('单件工时为 0，需要明确勾选复核。');
    return {
      operations,
      groups: mergedGroups(entity).map(row => ({
        ref: row.ref,
        total_days: number(draft.groups[row.ref], '外协组 ' + row.start_sequence + ' 至 ' + row.end_sequence + ' 总周期', true)
      })),
      confirm_zero_unit_hours: draft.zero
    };
  }
  function ProcessHoursEditor({
    adapter,
    result,
    command,
    disabled,
    saved,
    onDirty,
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
      paging = E.usePage(entity.operations);
    const blocked = disabled || command.locked || command.phase === 'done',
      stageReason = E.reason(model, adapter, 'hours');
    const editBlocked = blocked || entity.workflow.source.state !== 'confirmed' || entity.capabilities.stage_confirm !== true;
    function change(ref, patch) {
      model.edit(current => ({
        ...current,
        zero: false,
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
      model.edit(current => {
        const operations = {
          ...current.operations
        };
        E.active(entity).filter(row => row.external_group_ref === ref).forEach(row => {
          operations[row.ref] = {
            ...operations[row.ref],
            confirmed: false
          };
        });
        return {
          ...current,
          operations,
          groups: {
            ...current.groups,
            [ref]: total
          }
        };
      });
    }
    async function save() {
      if (blocked || stageReason) return;
      try {
        const body = input(entity, draft);
        model.setError(null);
        await command.submit('process', 'hours_confirm', entity.ref, entity.write_context, body);
      } catch (error) {
        model.setError(error);
      }
    }
    const all = paging.rows.filter(row => row.status === 'active');
    return /*#__PURE__*/React.createElement("section", {
      "data-process-hours-editor": true
    }, /*#__PURE__*/React.createElement("div", {
      className: "toolbar"
    }, /*#__PURE__*/React.createElement(E.Search, {
      paging: paging,
      disabled: blocked
    }), /*#__PURE__*/React.createElement("span", null, "\u6709\u6548\u5DE5\u5E8F ", E.active(entity).length), /*#__PURE__*/React.createElement("span", {
      className: "tb-spacer"
    }), /*#__PURE__*/React.createElement(window.ProcessFileButtons, {
      capabilities: entity.capabilities,
      disabled: blocked,
      hoursOnly: true,
      onAction: onFileAction
    })), /*#__PURE__*/React.createElement("div", {
      className: "toolbar"
    }, /*#__PURE__*/React.createElement("label", null, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      "aria-label": "\u786E\u8BA4\u672C\u9875\u5DF2\u6838\u5BF9\u5DE5\u65F6",
      checked: !!all.length && all.every(row => draft.operations[row.ref].confirmed),
      disabled: editBlocked || !all.length,
      onChange: event => {
        const confirmed = event.target.checked;
        model.edit(current => {
          const operations = {
            ...current.operations
          };
          all.forEach(row => {
            operations[row.ref] = {
              ...operations[row.ref],
              confirmed
            };
          });
          return {
            ...current,
            operations
          };
        });
      }
    }), "\u786E\u8BA4\u672C\u9875\u5DF2\u6838\u5BF9\u5DE5\u65F6")), /*#__PURE__*/React.createElement("div", {
      className: "wb-table-frame"
    }, /*#__PURE__*/React.createElement("div", {
      className: "card-scroll wb-table-shell"
    }, /*#__PURE__*/React.createElement("table", {
      className: "tbl wb-table",
      "aria-label": "\u5DE5\u65F6\u5B9A\u989D\u660E\u7EC6",
      style: {
        minWidth: 1000,
        tableLayout: 'fixed'
      }
    }, /*#__PURE__*/React.createElement("caption", {
      className: "wb-visually-hidden"
    }, "工时定额明细"), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      scope: "col",
      style: {
        width: 180
      }
    }, "\u5DE5\u5E8F / \u5DE5\u79CD"), /*#__PURE__*/React.createElement("th", {
      scope: "col",
      style: {
        width: 85
      }
    }, "\u5F52\u5C5E"), /*#__PURE__*/React.createElement("th", {
      scope: "col",
      style: {
        width: 140
      }
    }, "\u6362\u578B\u5DE5\u65F6\uFF08h\uFF09"), /*#__PURE__*/React.createElement("th", {
      scope: "col",
      style: {
        width: 140
      }
    }, "\u5355\u4EF6\u5DE5\u65F6\uFF08h\uFF09"), /*#__PURE__*/React.createElement("th", {
      scope: "col",
      style: {
        width: 140
      }
    }, "\u5916\u534F\u5468\u671F\uFF08\u5929\uFF09"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u6838\u5BF9 / \u786E\u8BA4\u8BB0\u5F55"))), /*#__PURE__*/React.createElement("tbody", null, paging.rows.map(row => {
      const current = draft.operations[row.ref],
        inactive = !current,
        cycle = P.groupCycle(row, entity.external_groups);
      const cell = (key, title) => /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement("input", {
        className: "wt-in",
        type: "number",
        step: "any",
        min: "0",
        "aria-label": '工序 ' + row.sequence + ' ' + title,
        placeholder: "\u672A\u586B\u5199",
        value: current ? current[key] : numericText(row[key]),
        disabled: editBlocked || inactive,
        onChange: event => change(row.ref, {
          [key]: event.target.value,
          confirmed: false
        }),
        style: {
          width: '100%'
        }
      }), key === 'unit_hours' && current && current[key].trim() !== '' && Number(current[key]) === 0 && /*#__PURE__*/React.createElement("span", {
        className: "prov"
      }, "0 \xB7 \u8BF7\u590D\u6838"));
      return /*#__PURE__*/React.createElement("tr", {
        key: row.ref
      }, /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement("b", null, row.sequence), " ", row.label, /*#__PURE__*/React.createElement("div", {
        className: "muted"
      }, row.op_type_label || '未绑定工种')), /*#__PURE__*/React.createElement("td", null, window.APSProcessContract.sourceLabel(row.source)), row.source === 'external' ? /*#__PURE__*/React.createElement("td", {
        colSpan: 2,
        className: "muted"
      }, "\u5916\u534F\u5DE5\u5E8F\u4E0D\u586B\u5DE5\u65F6") : /*#__PURE__*/React.createElement(React.Fragment, null, cell('setup_hours', '换型工时'), cell('unit_hours', '单件工时')), row.source === 'external' ? cycle ? /*#__PURE__*/React.createElement("td", {
        "data-process-cycle-group": row.external_group_ref
      }, cycle) : cell('external_days', '外协周期') : /*#__PURE__*/React.createElement("td", {
        className: "muted"
      }, "\u4E0D\u9002\u7528"), /*#__PURE__*/React.createElement("td", null, inactive ? '已停用工序' : /*#__PURE__*/React.createElement("label", null, /*#__PURE__*/React.createElement("input", {
        type: "checkbox",
        "aria-label": '确认工序 ' + row.sequence + ' 工时',
        checked: current.confirmed,
        disabled: editBlocked,
        onChange: event => change(row.ref, {
          confirmed: event.target.checked
        })
      }), "\u5DF2\u6838\u5BF9"), /*#__PURE__*/React.createElement("div", {
        className: "muted"
      }, /*#__PURE__*/React.createElement(E.Confirmation, {
        record: row.confirmation && row.confirmation.hours
      })), /*#__PURE__*/React.createElement(window.ResourceControls.Issues, {
        issues: row.issues
      })));
    }), !paging.rows.length && /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("td", {
      colSpan: 6
    }, entity.operations.length ? '没有匹配的工序。' : '尚无工序记录。')))))), /*#__PURE__*/React.createElement(E.Pager, {
      paging: paging,
      disabled: blocked
    }), /*#__PURE__*/React.createElement(E.Groups, {
      rows: entity.external_groups,
      totals: draft.groups,
      disabled: editBlocked,
      onTotal: changeGroup
    }), /*#__PURE__*/React.createElement("p", null, /*#__PURE__*/React.createElement("label", null, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      "aria-label": "\u5DF2\u590D\u6838\u5355\u4EF6\u5DE5\u65F6\u4E3A0",
      checked: draft.zero,
      disabled: editBlocked,
      onChange: event => model.edit(current => ({
        ...current,
        zero: event.target.checked
      }))
    }), "\u5DF2\u590D\u6838\u5355\u4EF6\u5DE5\u65F6\u4E3A 0\uFF0C\u786E\u8BA4\u6309 0 \u4FDD\u5B58")), /*#__PURE__*/React.createElement(E.Feedback, {
      model: model,
      disabled: blocked
    }), /*#__PURE__*/React.createElement("div", {
      className: "pd-foot"
    }, /*#__PURE__*/React.createElement("span", {
      className: "muted"
    }, "\u7A7A\u503C\u4E0D\u8865 0\uFF1B\u5408\u5E76\u7EC4\u6210\u5458\u5468\u671F\u53EF\u7A7A\uFF0C\u6309\u7EC4\u603B\u5468\u671F\u3002\u5DF2\u586B\u5468\u671F\u5FC5\u987B\u5927\u4E8E 0\u3002"), /*#__PURE__*/React.createElement(Button, {
      className: "btn primary",
      icon: "check",
      disabled: blocked,
      reason: stageReason,
      onClick: save
    }, "\u4FDD\u5B58\u5DE5\u65F6")));
  }
  window.ProcessHoursEditor = ProcessHoursEditor;
})();
