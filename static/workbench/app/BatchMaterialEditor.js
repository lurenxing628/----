(function () {
  'use strict';

  const B = window.APSBatchContract,
    C = window.APSResourceContract,
    S = window.APSResourceSession;
  const {
    Button,
    Modal,
    ErrorBox
  } = window.ResourceControls;
  const toRows = entity => entity.materials.requirements.map(row => ({
    ...row,
    operation_ref: row.operation_ref || null,
    arrivals: row.arrivals || [],
    required_quantity: row.required_quantity == null ? '' : String(row.required_quantity),
    available_quantity: row.available_quantity == null ? '' : String(row.available_quantity)
  }));
  function BatchMaterialEditor({
    adapter,
    entity: initial,
    command,
    onCommitted,
    onClose,
    disabled
  }) {
    const [entity, setEntity] = React.useState(initial),
      [rows, setRows] = React.useState(() => toRows(initial));
    const [removed, setRemoved] = React.useState([]),
      [error, setError] = React.useState(null),
      [review, setReview] = React.useState(null);
    const [scope, setScope] = React.useState({
        query: '',
        page: 1
      }),
      [selected, setSelected] = React.useState('');
    const form = React.useId(),
      done = command.phase === 'done',
      locked = disabled || command.locked || done;
    const seen = React.useRef(null),
      changed = JSON.stringify(rows) !== JSON.stringify(toRows(entity)) || removed.length > 0;
    const owner = window.WorkbenchGuards.useDirtyGuard({
      dirty: !done && !!changed,
      locked: command.locked,
      message: '物料需求有尚未保存的修改。'
    });
    const choices = S.useQuery(signal => adapter.materialChoices(scope, signal), [adapter, scope]);
    const data = choices.result && choices.result.data;
    React.useEffect(() => {
      if (!done || seen.current === command.result.receipt_ref) return;
      try {
        B.receipt(command.result, 'materials_update', entity.ref);
        seen.current = command.result.receipt_ref;
        onCommitted(command.result);
      } catch (e) {
        setError(e);
      }
    }, [done, command.result]);
    async function close(detail) {
      if (command.locked) return;
      if (detail && detail.guardConfirmed && detail.guardOwner === owner || (await window.WorkbenchGuards.confirmLeave({
        owner
      }))) onClose();
    }
    function add() {
      const item = data && data.entities.find(row => row.ref === selected);
      if (!item) return;
      setRows(rows.concat({
        row_key: null,
        material_ref: item.ref,
        business_code: item.business_code,
        label: item.label,
        unit: item.fields.unit,
        required_quantity: '',
        available_quantity: '0',
        operation_ref: null,
        arrivals: []
      }));
      setSelected('');
    }
    function patch(index, change) {
      setRows(old => old.map((row, i) => i === index ? {
        ...row,
        ...change
      } : row));
    }
    async function save(event) {
      event.preventDefault();
      if (locked || review) return;
      try {
        const input = rows.map(row => {
          const values = [row.required_quantity, row.available_quantity].map(value => {
            if (!String(value).trim() || !Number.isFinite(Number(value))) throw C.failure('请填写有效的需求量和到料量，未到料请填 0。');
            return Number(value);
          });
          if (values[0] <= 0 || values[1] < 0) throw C.failure('需求量必须大于 0，到料量不能小于 0。');
          const arrivals = row.arrivals.map(item => {
            const quantity = Number(item.quantity);
            if (!item.arrival_date || !Number.isFinite(quantity) || quantity <= 0) throw C.failure('请填写每次到料日期和大于 0 的数量。');
            return {
              arrival_date: item.arrival_date,
              quantity
            };
          });
          return {
            row_key: row.row_key,
            material_ref: row.material_ref,
            required_quantity: values[0],
            available_quantity: values[1],
            operation_ref: row.operation_ref,
            arrivals
          };
        });
        setError(null);
        await command.submit('batch', 'materials_update', entity.ref, entity.write_context, {
          rows: input,
          removed_keys: removed
        });
      } catch (e) {
        setError(e);
      }
    }
    async function reload() {
      try {
        setReview(B.detail(await adapter.detail('batch', entity.ref), entity.ref).data);
        setError(null);
      } catch (e) {
        setError(e);
      }
    }
    function accept() {
      setEntity(review);
      setRows(toRows(review));
      setRemoved([]);
      setReview(null);
      setError(null);
      command.reset();
    }
    return /*#__PURE__*/React.createElement(Modal, {
      title: '物料需求 · ' + entity.business_code,
      icon: "box",
      onClose: close,
      guardOwner: owner,
      locked: command.locked,
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        onClick: close,
        disabled: command.locked
      }, done ? '关闭' : '取消'), !done && /*#__PURE__*/React.createElement(Button, {
        form: form,
        type: "submit",
        className: "btn primary",
        disabled: locked || !!review
      }, "\u6838\u5BF9\u5E76\u4FDD\u5B58\u9700\u6C42"))
    }, /*#__PURE__*/React.createElement("form", {
      id: form,
      className: "modal-b form",
      onSubmit: save
    }, /*#__PURE__*/React.createElement("p", null, "\u5DF2\u6709\u5230\u6599\u91CF\u4E0E\u4E0B\u65B9\u9010\u6B21\u5230\u6599\u5206\u522B\u7D2F\u8BA1\uFF0C\u8BF7\u52FF\u91CD\u590D\u767B\u8BB0\u3002\u9009\u62E9\u4F7F\u7528\u5DE5\u5E8F\u540E\uFF0C\u524D\u9762\u7684\u5DE5\u5E8F\u53EF\u6309\u672C\u6B21\u6392\u4EA7\u9009\u9879\u5148\u5F00\u5DE5\uFF1B\u672A\u9009\u5DE5\u5E8F\u7684\u7269\u6599\u5FC5\u987B\u5728\u5F00\u5DE5\u524D\u9F50\u5957\u3002"), /*#__PURE__*/React.createElement("div", {
      className: "toolbar"
    }, /*#__PURE__*/React.createElement("input", {
      "aria-label": "\u641C\u7D22\u7269\u6599",
      value: scope.query,
      disabled: locked,
      onChange: e => setScope({
        query: e.target.value,
        page: 1
      })
    }), /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u9009\u62E9\u7269\u6599",
      value: selected,
      disabled: locked || choices.loading,
      onChange: e => setSelected(e.target.value)
    }, /*#__PURE__*/React.createElement("option", {
      value: ""
    }, "\u8BF7\u9009\u62E9\u7269\u6599"), data && data.entities.map(row => /*#__PURE__*/React.createElement("option", {
      key: row.ref,
      value: row.ref
    }, row.business_code, " \xB7 ", row.label))), /*#__PURE__*/React.createElement(Button, {
      onClick: add,
      disabled: locked || !selected
    }, "\u65B0\u589E\u7269\u6599")), data && /*#__PURE__*/React.createElement(window.WorkbenchControls.Pager, {
      page: data.page,
      sizes: [20],
      unit: "\u6761\u7269\u6599",
      label: "\u7269\u6599\u9009\u62E9",
      disabled: locked || choices.loading,
      onPage: page => setScope({
        ...scope,
        page,
        snapshot_ref: choices.result.meta.snapshot_ref
      })
    }), /*#__PURE__*/React.createElement("div", {
      className: "wb-table-frame"
    }, /*#__PURE__*/React.createElement("table", {
      className: "tbl wb-table",
      "aria-label": "\u7EF4\u62A4\u6279\u6B21\u7269\u6599\u9700\u6C42"
    }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", null, "\u7269\u6599"), /*#__PURE__*/React.createElement("th", null, "\u9700\u6C42\u91CF"), /*#__PURE__*/React.createElement("th", null, "\u5DF2\u6709\u5230\u6599\u91CF"), /*#__PURE__*/React.createElement("th", null, "\u5355\u4F4D"), /*#__PURE__*/React.createElement("th", null, "\u64CD\u4F5C"))), /*#__PURE__*/React.createElement("tbody", null, rows.map((row, index) => /*#__PURE__*/React.createElement(React.Fragment, {
      key: row.row_key || row.material_ref + index
    }, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("td", null, row.business_code, " \xB7 ", row.label), ['required_quantity', 'available_quantity'].map((key, column) => /*#__PURE__*/React.createElement("td", {
      key: key
    }, /*#__PURE__*/React.createElement("input", {
      "aria-label": row.business_code + (column ? '到料量' : '需求量'),
      inputMode: "decimal",
      value: row[key],
      disabled: locked,
      onChange: e => setRows(rows.map((item, i) => i === index ? {
        ...item,
        [key]: e.target.value
      } : item))
    }))), /*#__PURE__*/React.createElement("td", null, row.unit || '未填写'), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Button, {
      disabled: locked,
      onClick: () => {
        setRows(rows.filter((_, i) => i !== index));
        if (row.row_key) setRemoved(removed.concat(row.row_key));
      }
    }, "\u79FB\u9664\u9700\u6C42"))), /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("td", {
      colSpan: "5"
    }, /*#__PURE__*/React.createElement("div", {
      className: "fgrid"
    }, /*#__PURE__*/React.createElement(window.ResourceControls.Field, {
      label: row.business_code + '使用工序'
    }, /*#__PURE__*/React.createElement("select", {
      "aria-label": row.business_code + '使用工序',
      value: row.operation_ref || '',
      disabled: locked,
      onChange: e => patch(index, {
        operation_ref: e.target.value || null
      })
    }, /*#__PURE__*/React.createElement("option", {
      value: ""
    }, "\u5F00\u5DE5\u524D\u7528\u6599"), entity.operations.filter(op => !op.piece_id).map(op => /*#__PURE__*/React.createElement("option", {
      key: op.ref,
      value: op.ref
    }, op.sequence, " \xB7 ", op.label)))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("strong", null, "\u5206\u6B21\u5230\u6599\uFF08\u6309\u586B\u5199\u65E5\u671F\u53EF\u7528\uFF09"), row.arrivals.map((item, n) => /*#__PURE__*/React.createElement("div", {
      className: "toolbar",
      key: n
    }, /*#__PURE__*/React.createElement("input", {
      type: "date",
      "aria-label": row.business_code + '第' + (n + 1) + '次到料日期',
      value: item.arrival_date,
      disabled: locked,
      onChange: e => patch(index, {
        arrivals: row.arrivals.map((a, j) => j === n ? {
          ...a,
          arrival_date: e.target.value
        } : a)
      })
    }), /*#__PURE__*/React.createElement("input", {
      inputMode: "decimal",
      "aria-label": row.business_code + '第' + (n + 1) + '次到料数量',
      value: item.quantity,
      disabled: locked,
      onChange: e => patch(index, {
        arrivals: row.arrivals.map((a, j) => j === n ? {
          ...a,
          quantity: e.target.value
        } : a)
      })
    }), /*#__PURE__*/React.createElement(Button, {
      disabled: locked,
      onClick: () => patch(index, {
        arrivals: row.arrivals.filter((_, j) => j !== n)
      })
    }, "\u79FB\u9664\u5230\u6599"))), /*#__PURE__*/React.createElement(Button, {
      disabled: locked || row.arrivals.length >= 200,
      onClick: () => patch(index, {
        arrivals: row.arrivals.concat({
          arrival_date: '',
          quantity: ''
        })
      })
    }, "\u65B0\u589E\u4E00\u6B21\u5230\u6599")))))))))), !rows.length && /*#__PURE__*/React.createElement("p", null, "\u5F53\u524D\u6CA1\u6709\u7269\u6599\u9700\u6C42\u3002\u4FDD\u5B58\u540E\u4FDD\u6301\u672A\u9F50\u5957\uFF1B\u6CA1\u6709\u7528\u6599\u8981\u6C42\u7684\u6279\u6B21\u53EF\u5728\u57FA\u7840\u4FE1\u606F\u4E2D\u660E\u786E\u786E\u8BA4\u9F50\u5957\u3002"), removed.length > 0 && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u672C\u6B21\u5C06\u79FB\u9664 ", removed.length, " \u6761\u5DF2\u6709\u9700\u6C42\uFF0C\u8BF7\u6838\u5BF9\u540E\u4FDD\u5B58\u3002"), /*#__PURE__*/React.createElement(ErrorBox, {
      error: error || choices.error
    }), /*#__PURE__*/React.createElement(window.ResourceForms.Feedback, {
      command: command
    }), !done && /*#__PURE__*/React.createElement(Button, {
      onClick: reload,
      disabled: locked
    }, window.WorkbenchTerms.refresh_latest), review && /*#__PURE__*/React.createElement("div", {
      role: "status"
    }, /*#__PURE__*/React.createElement("p", null, "\u5DF2\u8BFB\u5230\u6700\u65B0\u8D44\u6599\u3002\u91C7\u7528\u540E\u4F1A\u653E\u5F03\u672C\u6B21\u672A\u4FDD\u5B58\u7684\u4FEE\u6539\uFF0C\u5E76\u91CD\u65B0\u6838\u5BF9\u7269\u6599\u9700\u6C42\u3002"), /*#__PURE__*/React.createElement(Button, {
      onClick: accept
    }, "\u91C7\u7528\u6700\u65B0\u8D44\u6599\u5E76\u91CD\u65B0\u586B\u5199"))));
  }
  window.BatchMaterialEditor = BatchMaterialEditor;
})();
