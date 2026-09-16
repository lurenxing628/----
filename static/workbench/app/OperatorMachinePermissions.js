(function () {
  'use strict';

  const C = window.APSResourceContract,
    S = window.APSResourceSession;
  const {
    Button,
    Icon,
    ErrorBox,
    Modal
  } = window.ResourceControls;
  const levels = [['beginner', '初级'], ['normal', '普通'], ['expert', '熟练']];
  const primaries = [['no', '否'], ['yes', '是']];
  const fields = rows => rows.map(({
    machine_ref,
    skill_level,
    is_primary
  }) => ({
    machine_ref,
    skill_level,
    is_primary
  }));
  const isPrimary = value => ['yes', 'y', 'true', '是', '主', '主操', 'on', '1'].includes(String(value).trim().toLowerCase());
  function PermissionSelect({
    value,
    choices,
    label,
    disabled,
    onChange
  }) {
    const old = !choices.some(([item]) => item === value);
    return /*#__PURE__*/React.createElement("select", {
      "aria-label": label,
      value: JSON.stringify(value),
      disabled: disabled,
      onChange: event => onChange(JSON.parse(event.target.value))
    }, old && /*#__PURE__*/React.createElement("option", {
      value: JSON.stringify(value)
    }, "\u539F\u503C\uFF1A", value === null ? '未填写' : String(value)), choices.map(([item, name]) => /*#__PURE__*/React.createElement("option", {
      key: item,
      value: JSON.stringify(item)
    }, name)));
  }
  function OperatorMachinePermissions({
    adapter,
    entity,
    source,
    command,
    onClose,
    refreshState = {},
    onRefresh,
    Feedback
  }) {
    const [current, setCurrent] = React.useState(entity);
    const original = current.relationships.machine_permissions;
    const [rows, setRows] = React.useState(() => Array.isArray(original) ? original.map(row => ({
      ...row
    })) : []);
    const [search, setSearch] = React.useState(''),
      [query, setQuery] = React.useState(''),
      [selected, setSelected] = React.useState('');
    const [preview, setPreview] = React.useState(null),
      [busy, setBusy] = React.useState(false),
      [error, setError] = React.useState(null);
    const done = command.phase === 'done',
      disabled = busy || command.locked || done;
    const read = S.useQuery(signal => adapter.choices('machine', {
      query,
      page: 1,
      size: 20,
      sort: 'business_code',
      direction: 'asc'
    }, signal), [adapter, query]);
    const choices = read.result && read.result.data.entities || [];
    const reason = !Array.isArray(original) ? '设备关联尚未完整读取，请关闭后重新打开人员详情。' : C.blocked(current.write_context, 'operator', 'update', source);
    const owner = window.WorkbenchGuards.useDirtyGuard({
      dirty: !done && JSON.stringify(fields(rows)) !== JSON.stringify(fields(original || [])),
      message: '可操作设备有尚未保存的修改。',
      locked: command.locked
    });
    async function close(detail) {
      if (disabled && !done) return;
      if (!(detail && detail.guardConfirmed === true && detail.guardOwner === owner) && !(await window.WorkbenchGuards.confirmLeave({
        owner
      }))) return;
      onClose();
    }
    function change(next) {
      setRows(next);
      setPreview(null);
      setError(null);
    }
    function edit(ref, key, value) {
      change(rows.map(row => row.machine_ref === ref ? {
        ...row,
        [key]: value
      } : key === 'is_primary' && value === 'yes' && isPrimary(row.is_primary) ? {
        ...row,
        is_primary: 'no'
      } : row));
    }
    function add() {
      const machine = choices.find(item => item.ref === selected);
      if (!machine || rows.some(row => row.machine_ref === selected)) return;
      change(rows.concat({
        machine_ref: machine.ref,
        business_code: machine.business_code,
        label: machine.label,
        skill_level: 'normal',
        is_primary: 'no'
      }));
      setSelected('');
    }
    async function reload() {
      if (disabled || !(await window.WorkbenchGuards.confirmLeave({
        owner
      }))) return;
      setBusy(true);
      setError(null);
      try {
        const result = C.query(await adapter.detail('operator', entity.ref, new AbortController().signal), 'entity');
        if (result.data.ref !== entity.ref || result.meta.source !== source || !Array.isArray(result.data.relationships.machine_permissions)) throw C.failure('没有取得当前人员的完整设备关联。');
        setCurrent(result.data);
        setRows(result.data.relationships.machine_permissions.map(row => ({
          ...row
        })));
        setPreview(null);
        setSelected('');
      } catch (failure) {
        setError(failure);
      } finally {
        setBusy(false);
      }
    }
    async function inspect() {
      if (disabled || reason) return;
      setBusy(true);
      setError(null);
      setPreview(null);
      try {
        const result = await adapter.preview('entities/operator/' + entity.ref + '/machine-permissions/preview', {
          machine_permissions: fields(rows),
          write_token: current.write_context.write_token
        }, new AbortController().signal);
        const data = result && result.data;
        if (!data || data.operator_ref !== entity.ref || !Array.isArray(data.rows) || !data.write_context || data.write_context.capabilities['operator.machine_permissions'] !== true || typeof data.preview_ref !== 'string') throw C.failure('设备关联预检不完整，请重新预检。');
        setPreview(data);
      } catch (failure) {
        setError(failure);
      } finally {
        setBusy(false);
      }
    }
    const changed = preview ? preview.rows.filter(row => row.result !== 'unchanged') : [];
    const display = (key, value) => ((key === 'skill_level' ? levels : primaries).find(([item]) => item === value) || [null, value === null ? '未填写' : String(value)])[1];
    return /*#__PURE__*/React.createElement("div", {
      className: "wb-machine-permissions-host"
    }, /*#__PURE__*/React.createElement(Modal, {
      title: '可操作设备 · ' + current.business_code + ' · ' + current.label,
      icon: "machine",
      onClose: close,
      guardOwner: owner,
      locked: command.locked || busy,
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        onClick: close,
        disabled: command.locked || busy
      }, done ? '关闭' : '取消'), !done && (preview ? /*#__PURE__*/React.createElement(Button, {
        icon: "check",
        className: "btn primary",
        busy: disabled,
        onClick: () => command.submit('operator', 'machine_permissions', entity.ref, preview.write_context, {
          preview_ref: preview.preview_ref
        })
      }, "\u786E\u8BA4\u4FDD\u5B58\u8BBE\u5907\u5173\u8054") : /*#__PURE__*/React.createElement(Button, {
        icon: "check",
        className: "btn primary",
        reason: reason,
        busy: disabled,
        onClick: inspect
      }, "\u9884\u89C8\u53D8\u66F4")))
    }, /*#__PURE__*/React.createElement("div", {
      className: "modal-b scroll wb-machine-permissions"
    }, /*#__PURE__*/React.createElement("p", null, "\u53EF\u64CD\u4F5C\u8BBE\u5907\u51B3\u5B9A\u8FD9\u4E2A\u4EBA\u80FD\u5206\u914D\u5230\u54EA\u4E9B\u8BBE\u5907\u3002\u5DE5\u79CD\u6280\u80FD\u5728\u4EBA\u5458\u8D44\u6599\u4E2D\u5355\u72EC\u7EF4\u62A4\uFF1B\u540C\u4E00\u4EBA\u5458\u6700\u591A\u8BBE\u7F6E\u4E00\u53F0\u4E3B\u64CD\u8BBE\u5907\u3002"), !done && /*#__PURE__*/React.createElement("form", {
      className: "toolbar",
      onSubmit: event => {
        event.preventDefault();
        setQuery(search.trim());
        setSelected('');
      }
    }, /*#__PURE__*/React.createElement("label", {
      className: "search"
    }, /*#__PURE__*/React.createElement("span", {
      className: "ic"
    }, /*#__PURE__*/React.createElement(Icon, {
      name: "search"
    })), /*#__PURE__*/React.createElement("input", {
      type: "search",
      "aria-label": "\u641C\u7D22\u53EF\u5173\u8054\u8BBE\u5907",
      placeholder: "\u8BBE\u5907\u7F16\u53F7\u3001\u540D\u79F0",
      value: search,
      disabled: disabled,
      onChange: event => setSearch(event.target.value)
    })), /*#__PURE__*/React.createElement(Button, {
      icon: "search",
      type: "submit",
      disabled: disabled,
      busy: read.loading
    }, "\u641C\u7D22\u8BBE\u5907"), /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u9009\u62E9\u5173\u8054\u8BBE\u5907",
      value: selected,
      disabled: disabled || read.loading,
      onChange: event => setSelected(event.target.value)
    }, /*#__PURE__*/React.createElement("option", {
      value: ""
    }, "\u8BF7\u9009\u62E9\u8BBE\u5907"), choices.filter(item => !rows.some(row => row.machine_ref === item.ref)).map(item => /*#__PURE__*/React.createElement("option", {
      key: item.ref,
      value: item.ref
    }, item.business_code, " \xB7 ", item.label))), /*#__PURE__*/React.createElement(Button, {
      icon: "plus",
      disabled: disabled || !selected,
      onClick: add
    }, "\u65B0\u589E\u5173\u8054"), read.result && read.result.data.page.total > 20 && /*#__PURE__*/React.createElement("span", {
      className: "muted"
    }, "\u663E\u793A\u524D 20 \u53F0\uFF0C\u8BF7\u8F93\u5165\u7F16\u53F7\u6216\u540D\u79F0\u7F29\u5C0F\u8303\u56F4\u3002")), /*#__PURE__*/React.createElement(ErrorBox, {
      error: read.error
    }), /*#__PURE__*/React.createElement("div", {
      className: "wb-table-frame"
    }, /*#__PURE__*/React.createElement("table", {
      className: "wb-table"
    }, /*#__PURE__*/React.createElement("caption", null, "\u5168\u90E8\u53EF\u64CD\u4F5C\u8BBE\u5907\uFF08", rows.length, " \u53F0\uFF09"), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", null, "\u8BBE\u5907"), /*#__PURE__*/React.createElement("th", null, "\u6280\u80FD\u7B49\u7EA7"), /*#__PURE__*/React.createElement("th", null, "\u4E3B\u64CD\u8BBE\u5907"), /*#__PURE__*/React.createElement("th", null, "\u64CD\u4F5C"))), /*#__PURE__*/React.createElement("tbody", null, rows.map(row => /*#__PURE__*/React.createElement("tr", {
      key: row.machine_ref
    }, /*#__PURE__*/React.createElement("td", null, row.business_code, " \xB7 ", row.label), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(PermissionSelect, {
      value: row.skill_level,
      choices: levels,
      label: '技能等级 ' + row.business_code,
      disabled: disabled,
      onChange: value => edit(row.machine_ref, 'skill_level', value)
    })), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(PermissionSelect, {
      value: row.is_primary,
      choices: primaries,
      label: '主操设备 ' + row.business_code,
      disabled: disabled,
      onChange: value => edit(row.machine_ref, 'is_primary', value)
    })), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Button, {
      disabled: disabled,
      onClick: () => change(rows.filter(item => item.machine_ref !== row.machine_ref))
    }, "\u89E3\u9664\u5173\u8054")))))), !rows.length && /*#__PURE__*/React.createElement("p", {
      className: "muted"
    }, "\u5C1A\u672A\u8BBE\u7F6E\u53EF\u64CD\u4F5C\u8BBE\u5907\u3002")), preview && !done && /*#__PURE__*/React.createElement("section", {
      className: "wb-permission-preview",
      "aria-label": "\u8BBE\u5907\u5173\u8054\u53D8\u66F4\u9884\u68C0"
    }, /*#__PURE__*/React.createElement("h3", null, "\u672C\u6B21\u53D8\u66F4"), changed.length ? /*#__PURE__*/React.createElement("ul", null, changed.map(row => /*#__PURE__*/React.createElement("li", {
      key: row.entity_ref
    }, /*#__PURE__*/React.createElement("strong", null, {
      new: '新增关联',
      delete: '解除关联',
      update: '修改关联'
    }[row.result]), "\uFF1A", row.business_code, " \xB7 ", row.label, row.result === 'update' && Object.entries(row.changes).map(([key, pair]) => /*#__PURE__*/React.createElement("span", {
      key: key
    }, "\uFF1B", key === 'skill_level' ? '技能等级' : '主操设备', "\uFF1A", display(key, pair[0]), " \u2192 ", display(key, pair[1])))))) : /*#__PURE__*/React.createElement("p", null, "\u8BBE\u5907\u5173\u8054\u6CA1\u6709\u53D8\u5316\u3002"), /*#__PURE__*/React.createElement("p", {
      className: "muted"
    }, "\u4FDD\u5B58\u540E\uFF0C\u65B0\u7684\u8D44\u6E90\u5206\u914D\u6309\u8FD9\u4EFD\u8BBE\u5907\u5173\u8054\u5224\u65AD\uFF1B\u5DF2\u4FDD\u5B58\u7684\u8BA1\u5212\u548C\u62A5\u5DE5\u8BB0\u5F55\u4FDD\u7559\u3002")), /*#__PURE__*/React.createElement(ErrorBox, {
      error: error
    }), /*#__PURE__*/React.createElement(Feedback, {
      command: command
    }), !done && (error || command.error) && /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      disabled: disabled,
      onClick: reload
    }, "\u5237\u65B0\u8BBE\u5907\u5173\u8054"), done && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, refreshState.done ? '已刷新人员资料，设备关联已保存。' : refreshState.loading ? '正在刷新人员资料…' : '请刷新保存结果，核对人员资料。'), /*#__PURE__*/React.createElement(ErrorBox, {
      error: refreshState.error
    }), refreshState.error && /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      onClick: onRefresh
    }, "\u5237\u65B0\u4FDD\u5B58\u7ED3\u679C")))));
  }
  window.OperatorMachinePermissions = OperatorMachinePermissions;
})();
