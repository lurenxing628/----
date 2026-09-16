(function () {
  'use strict';

  const C = window.APSResourceContract;
  // Local SVG paths supplement the bundled action and navigation icons.
  const railPaths = {
    machine: ['M3 20h18', 'M5 20V9l5 3V9l5 3V6l4 2v12'],
    wrench: ['M15 5.2a3.6 3.6 0 00-4.7 4.6L4 16.1 7.9 20l6.3-6.3A3.6 3.6 0 0018.8 9l-2.2 2.2-2-2L16.8 7z'],
    truck: ['M3 6h11v9H3z', 'M14 9h3.5L21 12.2V15h-7z'],
    'arrow-right': ['M5 12h13M13 6l6 6-6 6'],
    'arrow-left': ['M19 12H5M11 6l-6 6 6 6'],
    copy: ['M9 9h12v12H9Z', 'M5 15H3V3h12v2'],
    filter: ['M4 4h16l-6 7v8l-4 2V11Z'],
    'chevron-up': ['m6 15 6-6 6 6'],
    'trash-2': ['M3 6h18', 'M19 6v14a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V6', 'M8 6V3h8v3', 'M10 10v7M14 10v7'],
    files: ['M15 3H8a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h9a2 2 0 0 0 2-2V7l-4-4Z', 'M15 3v4h4M3 8v11a2 2 0 0 0 2 2h9'],
    'list-checks': ['m3 6 2 2 3-4M11 6h10m-18 8 2 2 3-4M11 14h10M11 21h10'],
    lock: ['M5 10h14v11H5Z', 'M8 10V6a4 4 0 0 1 8 0v4M12 14v3'],
    'git-compare-arrows': ['M3 3h5v5H3Zm13 13h5v5h-5Z', 'M8 5h8a3 3 0 0 1 3 3v4m-3-3 3 3 3-3M16 19H8a3 3 0 0 1-3-3v-4m-3 3 3-3 3 3'],
    eye: ['M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z', 'M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0'],
    'rotate-ccw': ['M3 3v6h6', 'M3 9a9 9 0 1 1 .7 8']
  };
  function Icon({
    name,
    className
  }) {
    const nodes = window.APSFieldReports && window.APSFieldReports.iconNodes[name];
    if (nodes) return /*#__PURE__*/React.createElement("svg", {
      className: className,
      "data-wb-icon": name,
      viewBox: "0 0 24 24",
      width: "18",
      height: "18",
      fill: "none",
      stroke: "currentColor",
      strokeWidth: "1.75",
      strokeLinecap: "round",
      strokeLinejoin: "round",
      "aria-hidden": "true"
    }, nodes.map(([tag, attrs], index) => React.createElement(tag, {
      ...attrs,
      key: index
    })));
    if (name === 'refresh-cw' && typeof SMIcon === 'function') return /*#__PURE__*/React.createElement(SMIcon, {
      name: name
    });
    if (railPaths[name]) return /*#__PURE__*/React.createElement("svg", {
      className: className,
      "data-wb-icon": name,
      viewBox: "0 0 24 24",
      width: "18",
      height: "18",
      fill: "none",
      stroke: "currentColor",
      strokeWidth: "1.75",
      strokeLinecap: "round",
      strokeLinejoin: "round",
      "aria-hidden": "true"
    }, railPaths[name].map((d, index) => /*#__PURE__*/React.createElement("path", {
      key: index,
      d: d
    })), name === 'truck' && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("circle", {
      cx: "7",
      cy: "18",
      r: "1.9"
    }), /*#__PURE__*/React.createElement("circle", {
      cx: "17",
      cy: "18",
      r: "1.9"
    })));
    return typeof Ico === 'function' ? /*#__PURE__*/React.createElement(Ico, {
      name: name
    }) : null;
  }
  function Search({
    className = '',
    ...props
  }) {
    return /*#__PURE__*/React.createElement("label", {
      className: 'search wb-search ' + className
    }, /*#__PURE__*/React.createElement(Icon, {
      name: "search"
    }), /*#__PURE__*/React.createElement("input", {
      ...props,
      type: "search"
    }));
  }
  // reasonDisplay: 'inline' shows the reason next to the control; 'tooltip' keeps it in the title and a hidden description (table cells, toolbars).
  function Button({
    icon,
    transfer,
    children,
    reason,
    reasonDisplay = 'inline',
    busy,
    className = 'btn',
    ...props
  }) {
    if (reasonDisplay !== 'inline' && reasonDisplay !== 'tooltip') throw new TypeError('Unknown reasonDisplay: ' + reasonDisplay);
    const reasonId = React.useId(),
      inlineReason = reason && reasonDisplay === 'inline',
      hiddenReason = reason && reasonDisplay === 'tooltip';
    const title = reason || props.title || (typeof children === 'string' ? children : props['aria-label']);
    if (className.split(/\s+/).includes('primary')) className = Array.from(new Set(className.split(/\s+/).concat(['wb-action', 'wb-primary']))).join(' ');
    return /*#__PURE__*/React.createElement("span", {
      title: title,
      className: inlineReason ? 'wb-button-reason' : undefined,
      style: inlineReason ? undefined : {
        display: 'inline-flex',
        maxWidth: '100%'
      }
    }, /*#__PURE__*/React.createElement("button", {
      ...props,
      type: props.type || 'button',
      className: className + (transfer ? ' wb-action wb-transfer' : ''),
      "data-wb-transfer": transfer,
      "data-wb-disabled-reason": reason || undefined,
      disabled: !!reason || busy || props.disabled,
      style: className.startsWith('mini') ? {
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 5,
        ...props.style
      } : props.style,
      title: title,
      "aria-label": props['aria-label'] || (reason && !inlineReason && typeof children === 'string' ? children + '：' + reason : undefined),
      "aria-busy": busy || undefined,
      "aria-describedby": [props['aria-describedby'], (inlineReason || hiddenReason) && reasonId].filter(Boolean).join(' ') || undefined
    }, transfer ? /*#__PURE__*/React.createElement(window.APSWorkbenchUI.TransferIcon, {
      kind: transfer
    }) : icon && /*#__PURE__*/React.createElement(Icon, {
      name: icon
    }), children), inlineReason && /*#__PURE__*/React.createElement("span", {
      id: reasonId,
      className: "wb-reason",
      role: "status"
    }, reason), hiddenReason && /*#__PURE__*/React.createElement("span", {
      id: reasonId,
      className: "wb-visually-hidden"
    }, reason));
  }
  const fieldPath = path => String(path || '').replace(/^input\./, '');
  function uniqueFieldErrors(error, errors) {
    const seen = new Set();
    return (errors || C.fieldErrors(error)).filter(row => {
      if (!row || typeof row.path !== 'string' || typeof row.message !== 'string') return false;
      const key = fieldPath(row.path) + '\n' + row.message;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }
  function ErrorBox({
    error,
    excludePaths = []
  }) {
    if (!error) return null;
    const excluded = new Set(excludePaths.map(fieldPath));
    const all = uniqueFieldErrors(error),
      fields = all.filter(row => !excluded.has(fieldPath(row.path)));
    const message = C.message(error),
      hideMessage = all.some(row => excluded.has(fieldPath(row.path)) && row.message === message);
    return /*#__PURE__*/React.createElement(window.WorkbenchError, {
      error: error.error ? {
        ...error,
        ...error.error
      } : error,
      fields: fields,
      hideMessage: hideMessage
    });
  }
  function Field({
    label,
    path,
    error,
    errors,
    required,
    full,
    hint,
    children
  }) {
    const generated = React.useId(),
      child = React.Children.only(children),
      id = child.props.id || generated;
    const messages = Array.from(new Set(uniqueFieldErrors(error, errors).filter(row => fieldPath(row.path) === fieldPath(path)).map(row => row.message)));
    const describedBy = [child.props['aria-describedby'], hint && id + '-hint', messages.length && id + '-error'].filter(Boolean).join(' ');
    return /*#__PURE__*/React.createElement("div", {
      className: 'field wb-field' + (full ? ' full' : '') + (messages.length ? ' err' : ''),
      "data-field-path": path
    }, /*#__PURE__*/React.createElement("label", {
      htmlFor: id
    }, label, required && /*#__PURE__*/React.createElement("span", {
      className: "req",
      "aria-hidden": "true"
    }, "*")), React.cloneElement(child, {
      id,
      'aria-required': required || child.props['aria-required'] || undefined,
      'aria-label': child.props['aria-label'] || (typeof label === 'string' ? label : undefined),
      'aria-invalid': messages.length ? true : child.props['aria-invalid'],
      'aria-describedby': describedBy || undefined
    }), hint && /*#__PURE__*/React.createElement("span", {
      id: id + '-hint',
      className: "fhint"
    }, hint), messages.length > 0 && /*#__PURE__*/React.createElement("span", {
      id: id + '-error',
      className: "wb-field-error"
    }, messages.join(' ')));
  }
  function focusFirstInvalid(form) {
    if (!form || typeof form.querySelectorAll !== 'function') return false;
    const element = Array.from(form.querySelectorAll('[aria-invalid="true"]')).find(node => {
      if (node.disabled || typeof node.focus !== 'function' || node.closest('[hidden],[inert],[aria-hidden="true"]')) return false;
      for (let parent = node.parentElement; parent && form.contains(parent); parent = parent.parentElement) {
        if (parent.tagName === 'DETAILS') parent.open = true;
      }
      return node.getClientRects().length && !['hidden', 'collapse'].includes(getComputedStyle(node).visibility);
    });
    if (!element) return false;
    element.scrollIntoView({
      block: 'center',
      inline: 'nearest'
    });
    element.focus({
      preventScroll: true
    });
    return true;
  }
  function Issues({
    issues = []
  }) {
    // The same message from several records reads once, with the record count; the records themselves are untouched.
    const rows = [];
    for (const issue of issues) {
      const text = typeof issue === 'string' ? issue : issue.message || '该记录存在待核对问题。';
      const row = rows.find(item => item.text === text);
      if (row) row.count += 1;else rows.push({
        text,
        count: 1
      });
    }
    return rows.length ? /*#__PURE__*/React.createElement("div", {
      className: "match-note",
      role: "status",
      style: {
        display: 'block',
        overflowWrap: 'anywhere'
      }
    }, rows.map(row => /*#__PURE__*/React.createElement("div", {
      key: row.text
    }, row.text, row.count > 1 && /*#__PURE__*/React.createElement("span", {
      className: "wb-issue-count"
    }, "\uFF08", row.count, " \u6761\uFF09")))) : null;
  }
  function Status({
    kind,
    entity
  }) {
    const value = entity.status,
      tone = value === 'active' ? 'ok' : value === 'inactive' && entity.fields.inactive_reason !== 'unknown' ? 'off' : 'warn';
    return /*#__PURE__*/React.createElement("span", {
      className: 'pill ' + tone,
      style: {
        whiteSpace: 'normal'
      }
    }, /*#__PURE__*/React.createElement("span", {
      className: "dot"
    }), C.statusLabel(kind, value, entity.fields));
  }
  const ModalFocusParent = React.createContext(null),
    modalStack = [];
  const modalSelector = 'button,input,select,textarea,a[href],[tabindex]';
  let modalFocusQueued = false,
    modalRestores = [],
    modalScrollStyles = [];
  function lockModalScroll() {
    modalScrollStyles = [document.documentElement, document.body].map(node => {
      const properties = Array.from(node.style).filter(name => /^overflow(?:-[xy])?$/.test(name)).map(name => [name, node.style.getPropertyValue(name), node.style.getPropertyPriority(name)]);
      node.style.setProperty('overflow', 'hidden', 'important');
      return {
        node,
        properties
      };
    });
  }
  function unlockModalScroll() {
    modalScrollStyles.forEach(({
      node,
      properties
    }) => {
      node.style.removeProperty('overflow');
      properties.forEach(([name, value, priority]) => node.style.setProperty(name, value, priority));
    });
    modalScrollStyles = [];
  }
  function modalVisible(node) {
    return !!(node && node.isConnected && node.getClientRects().length && !node.closest('[hidden],[inert],[aria-hidden="true"]') && !['hidden', 'collapse'].includes(getComputedStyle(node).visibility));
  }
  function modalFocusable(node) {
    return modalVisible(node) && node.matches(modalSelector) && !node.matches(':disabled') && typeof node.focus === 'function';
  }
  function topModal() {
    return modalStack.slice().reverse().find(entry => !entry.suspended && modalVisible(entry.root));
  }
  function modalItems(entry) {
    return Array.from(entry.root.querySelectorAll(modalSelector)).filter(node => node.tabIndex >= 0 && modalFocusable(node));
  }
  function focusModal(entry, preferred) {
    const items = modalItems(entry);
    const target = [preferred, entry.last].find(node => modalFocusable(node) && entry.root.contains(node)) || items.find(node => node.matches('input,select,textarea')) || items[0] || entry.root;
    if (document.activeElement !== target) target.focus();
  }
  function syncModalFocus() {
    if (modalFocusQueued) return;
    modalFocusQueued = true;
    // React may clean up parents before children, or replay effects. Restore only after the commit settles.
    queueMicrotask(() => {
      modalFocusQueued = false;
      const restores = modalRestores;
      modalRestores = [];
      const top = topModal(),
        candidates = [];
      if (top && !modalScrollStyles.length) lockModalScroll();else if (!top && modalScrollStyles.length) unlockModalScroll();
      restores.reverse().forEach(entry => {
        for (let item = entry; item; item = item.parent) candidates.push(item.previous);
      });
      if (top) {
        const previous = candidates.find(node => modalFocusable(node) && top.root.contains(node));
        if (previous || !top.root.contains(document.activeElement) || !modalFocusable(document.activeElement)) focusModal(top, previous);
      } else {
        const previous = candidates.find(node => modalFocusable(node) && !modalStack.some(entry => entry.root.contains(node)));
        if (previous) previous.focus();
      }
    });
  }
  function modalKeydown(event) {
    const entry = topModal();
    if (!entry || event.defaultPrevented) return;
    if (event.key === 'Escape' && event.target.closest && event.target.closest('[data-wb-table-filter],.wb-control-popup')) return;
    if (event.key === 'Escape') {
      event.preventDefault();
      event.stopPropagation();
      if (!entry.locked) entry.close();
    }
    if (event.key === 'Tab') {
      const items = modalItems(entry),
        start = items[0] || entry.root,
        end = items[items.length - 1] || entry.root;
      if (event.shiftKey && (document.activeElement === start || document.activeElement === entry.root || !entry.root.contains(document.activeElement))) {
        event.preventDefault();
        end.focus();
      } else if (!event.shiftKey && (document.activeElement === end || document.activeElement === entry.root || !entry.root.contains(document.activeElement))) {
        event.preventDefault();
        start.focus();
      }
    }
  }
  function retainModalFocus(event) {
    const entry = topModal();
    if (!entry) return;
    if (entry.root.contains(event.target)) entry.last = event.target;else focusModal(entry);
  }
  function mountModal(entry) {
    // Portal descendants retain React ancestry even when their DOM is outside the parent dialog.
    const index = modalStack.findIndex(item => {
      for (let parent = item.parent; parent; parent = parent.parent) if (parent === entry) return true;
      return false;
    });
    modalStack.splice(index < 0 ? modalStack.length : index, 0, entry);
    if (modalStack.length === 1) {
      document.addEventListener('keydown', modalKeydown);
      document.addEventListener('focusin', retainModalFocus);
    }
    syncModalFocus();
    return () => {
      modalStack.splice(modalStack.indexOf(entry), 1);
      modalRestores.push(entry);
      if (!modalStack.length) {
        document.removeEventListener('keydown', modalKeydown);
        document.removeEventListener('focusin', retainModalFocus);
      }
      syncModalFocus();
    };
  }
  function Modal({
    title,
    icon,
    children,
    footer,
    onClose,
    locked,
    labelId,
    suspended,
    guardOwner,
    guardBypass = false
  }) {
    // Capture before this commit disables the launcher and moves focus back to the body.
    const ref = React.useRef(null),
      entry = React.useRef({
        previous: document.activeElement
      }),
      parent = React.useContext(ModalFocusParent);
    const backdropStart = React.useRef(false),
      id = React.useId();
    const closing = React.useRef(false);
    async function requestClose() {
      if (closing.current || entry.current.locked || topModal() !== entry.current) return;
      closing.current = true;
      try {
        if (guardOwner && !guardBypass) {
          if (!window.WorkbenchGuards) throw new Error('WorkbenchGuards is required for guarded dialogs');
          if (!(await window.WorkbenchGuards.confirmLeave({
            owner: guardOwner
          }))) return;
        }
        if (!entry.current.locked) onClose({
          guardConfirmed: true,
          guardOwner
        });
      } finally {
        closing.current = false;
      }
    }
    React.useLayoutEffect(() => {
      Object.assign(entry.current, {
        root: ref.current,
        close: requestClose,
        locked,
        suspended
      });
      syncModalFocus();
    });
    React.useLayoutEffect(() => {
      entry.current.parent = parent || modalStack.slice().reverse().find(item => item.root.contains(entry.current.previous)) || null;
      return mountModal(entry.current);
    }, []);
    const canClose = () => topModal() === entry.current && !entry.current.locked;
    return /*#__PURE__*/React.createElement(ModalFocusParent.Provider, {
      value: entry.current
    }, /*#__PURE__*/React.createElement("div", {
      className: "modal-bg",
      style: suspended ? {
        visibility: 'hidden'
      } : undefined,
      onPointerDown: event => {
        backdropStart.current = canClose() && event.button === 0 && event.target === event.currentTarget;
      },
      onPointerUp: event => {
        backdropStart.current = backdropStart.current && event.target === event.currentTarget;
      },
      onPointerCancel: () => {
        backdropStart.current = false;
      },
      onClick: event => {
        const dismiss = backdropStart.current && event.target === event.currentTarget;
        backdropStart.current = false;
        if (dismiss && canClose()) entry.current.close();
      }
    }, /*#__PURE__*/React.createElement("div", {
      className: "modal lg",
      role: "dialog",
      "aria-modal": suspended ? undefined : true,
      "aria-labelledby": labelId || id,
      ref: ref,
      tabIndex: -1
    }, /*#__PURE__*/React.createElement("div", {
      className: "modal-head"
    }, /*#__PURE__*/React.createElement("span", {
      className: "modal-ico"
    }, /*#__PURE__*/React.createElement(Icon, {
      name: icon
    })), /*#__PURE__*/React.createElement("div", {
      style: {
        minWidth: 0,
        overflowWrap: 'anywhere'
      }
    }, /*#__PURE__*/React.createElement("div", {
      className: "modal-h2",
      id: labelId || id
    }, title)), /*#__PURE__*/React.createElement("span", {
      style: {
        marginLeft: 'auto'
      }
    }, /*#__PURE__*/React.createElement(Button, {
      className: "modal-x",
      icon: "x",
      "aria-label": "\u5173\u95ED",
      onClick: () => {
        if (canClose()) entry.current.close();
      },
      reason: locked ? '操作结果还没确认，请保留当前页面。' : ''
    }))), children, /*#__PURE__*/React.createElement("div", {
      className: "modal-f wb-actions",
      style: {
        flexWrap: 'wrap',
        marginLeft: 0,
        width: '100%',
        boxSizing: 'border-box'
      }
    }, footer))));
  }
  function relationLabels(entity, key) {
    if (!entity) return [];
    const objects = {
      op_type_ref: 'op_type',
      group_ref: 'group',
      shift_profile_ref: 'shift_profile',
      skill_refs: 'skills',
      op_type_refs: 'op_types'
    };
    const related = entity.relationships[objects[key]],
      refs = entity.relationships[key];
    if (Array.isArray(related) && Array.isArray(refs)) return refs.map(ref => ({
      ref,
      label: (related.find(item => item.ref === ref) || {}).label
    }));
    if (C.object(related) && related.ref === refs) return [{
      ref: refs,
      label: related.label
    }];
    const map = {
      op_type_ref: 'op_type_label',
      group_ref: 'group_label',
      shift_profile_ref: 'shift_profile_label',
      skill_refs: 'skill_labels',
      op_type_refs: 'op_type_labels',
      machine_refs: 'machine_labels'
    };
    const value = entity && entity.relationships[key],
      labels = entity && entity.relationships[map[key]];
    if (Array.isArray(value)) return value.map((ref, index) => ({
      ref,
      label: Array.isArray(labels) ? labels[index] : C.object(labels) ? labels[ref] : null
    }));
    return value ? [{
      ref: value,
      label: typeof labels === 'string' ? labels : null
    }] : [];
  }
  function Relation({
    entity,
    field,
    onOpen
  }) {
    const items = relationLabels(entity, field);
    return items.length ? /*#__PURE__*/React.createElement("span", {
      className: "chipline"
    }, items.map(item => onOpen ? /*#__PURE__*/React.createElement(Button, {
      key: item.ref,
      className: "mini",
      icon: "arrow-right",
      onClick: () => onOpen(item.ref),
      style: {
        whiteSpace: 'normal',
        overflowWrap: 'anywhere',
        textAlign: 'left'
      }
    }, item.label || '名称未填写') : /*#__PURE__*/React.createElement("span", {
      className: "chip",
      key: item.ref,
      style: {
        whiteSpace: 'normal',
        overflowWrap: 'anywhere'
      }
    }, item.label || '名称未填写'))) : /*#__PURE__*/React.createElement("span", {
      className: "muted"
    }, entity.relationships[field] === null || Array.isArray(entity.relationships[field]) ? '未选' : '未读取');
  }
  function Choice({
    adapter,
    field,
    value,
    original,
    onChange,
    disabled,
    onCatalog,
    catalogBusy,
    error
  }) {
    const [search, setSearch] = React.useState(''),
      [query, setQuery] = React.useState('');
    const [page, setPage] = React.useState(1),
      [snapshot, setSnapshot] = React.useState(undefined);
    const [known, setKnown] = React.useState({});
    const id = React.useId();
    const errors = uniqueFieldErrors(error).filter(row => ['relationships.' + field.key, field.key].includes(fieldPath(row.path)));
    const invalid = errors.length > 0,
      describedBy = invalid ? id + '-error' : undefined;
    const S = window.APSResourceSession;
    const request = S.useQuery(async signal => {
      if (typeof adapter.choices !== 'function') throw C.failure('dependency not wired: adapter.choices');
      const scope = {
        query,
        page,
        size: 50
      };
      if (field.category) scope.category = field.category;
      if (snapshot) scope.snapshot_ref = snapshot;
      return C.query(await adapter.choices(field.kind, scope, signal), 'choices');
    }, [adapter, field.kind, field.category, query, page, snapshot]);
    const response = request.result;
    React.useEffect(() => {
      if (!response) return;
      setKnown(current => {
        const result = {
          ...current
        };
        response.data.entities.forEach(item => {
          result[item.ref] = item;
        });
        return result;
      });
    }, [response]);
    const selected = field.multiple ? value : value ? [value] : [];
    const originals = relationLabels(original, field.key);
    const rows = response ? response.data.entities : [];
    const available = new Map(rows.map(item => [item.ref, item]));
    selected.forEach(ref => {
      if (!available.has(ref)) {
        const old = originals.find(item => item.ref === ref);
        available.set(ref, known[ref] || {
          ref,
          label: old && old.label || '原关联（未在当前选项中）',
          status: 'missing',
          fields: {}
        });
      }
    });
    function selectable(item) {
      return (item.status === 'active' || field.kind === 'op_type' && item.status === null) && (!field.category || item.fields.category === field.category);
    }
    function choose(ref, checked) {
      if (field.multiple) onChange(checked ? selected.concat(ref) : selected.filter(item => item !== ref));else onChange(ref);
    }
    const changePage = next => {
      setSnapshot(response.meta.snapshot_ref);
      setPage(next);
    };
    const runSearch = () => {
      setQuery(search);
      setPage(1);
      setSnapshot(undefined);
      request.reload();
    };
    const options = Array.from(available.values());
    return /*#__PURE__*/React.createElement("div", {
      className: 'field wb-field' + (field.multiple ? ' full' : '') + (invalid ? ' err' : ''),
      style: {
        minWidth: 0
      },
      "data-field-path": 'relationships.' + field.key
    }, /*#__PURE__*/React.createElement("label", {
      htmlFor: id
    }, field.label), /*#__PURE__*/React.createElement("div", {
      className: "rowact"
    }, /*#__PURE__*/React.createElement("div", {
      className: "search",
      style: {
        maxWidth: '100%',
        flex: '1 1 auto',
        minWidth: 0
      }
    }, /*#__PURE__*/React.createElement("span", {
      className: "ic"
    }, /*#__PURE__*/React.createElement(Icon, {
      name: "search"
    })), /*#__PURE__*/React.createElement("input", {
      "aria-label": '搜索' + field.label,
      value: search,
      disabled: disabled,
      onChange: event => setSearch(event.target.value),
      onKeyDown: event => {
        if (event.key === 'Enter') {
          event.preventDefault();
          runSearch();
        }
      }
    })), /*#__PURE__*/React.createElement(Button, {
      icon: "search",
      "aria-label": '执行' + field.label + '搜索',
      disabled: disabled,
      onClick: runSearch
    })), field.multiple ? /*#__PURE__*/React.createElement("div", {
      id: id,
      role: "group",
      "aria-label": field.label,
      "aria-invalid": invalid || undefined,
      "aria-describedby": describedBy,
      tabIndex: invalid ? -1 : undefined,
      className: "fchips",
      style: {
        maxHeight: 160,
        overflowY: 'auto'
      }
    }, options.map(item => /*#__PURE__*/React.createElement("label", {
      key: item.ref,
      className: 'fchip' + (selected.includes(item.ref) ? ' on' : ''),
      style: {
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        whiteSpace: 'normal',
        overflowWrap: 'anywhere'
      }
    }, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      style: {
        width: 15,
        height: 15,
        padding: 0,
        flex: 'none'
      },
      checked: selected.includes(item.ref),
      disabled: disabled || !selected.includes(item.ref) && !selectable(item),
      onChange: event => choose(item.ref, event.target.checked)
    }), item.label, !selectable(item) ? '（停用 / 未确认）' : ''))) : /*#__PURE__*/React.createElement("select", {
      id: id,
      value: value,
      disabled: disabled,
      "aria-invalid": invalid || undefined,
      "aria-describedby": describedBy,
      onChange: event => choose(event.target.value)
    }, /*#__PURE__*/React.createElement("option", {
      value: ""
    }, "\u672A\u9009"), options.map(item => /*#__PURE__*/React.createElement("option", {
      key: item.ref,
      value: item.ref,
      disabled: !selectable(item) && item.ref !== value
    }, item.label, !selectable(item) ? '（停用 / 未确认）' : ''))), invalid && /*#__PURE__*/React.createElement("span", {
      id: describedBy,
      className: "wb-field-error"
    }, Array.from(new Set(errors.map(row => row.message))).join(' ')), request.loading && /*#__PURE__*/React.createElement("span", {
      role: "status",
      className: "fhint"
    }, "\u6B63\u5728\u8BFB\u53D6\u9009\u9879\u2026"), /*#__PURE__*/React.createElement(ErrorBox, {
      error: request.error
    }), request.error && /*#__PURE__*/React.createElement(Button, {
      disabled: disabled,
      onClick: () => {
        setPage(1);
        setSnapshot(undefined);
        request.reload();
      }
    }, "\u5237\u65B0\u9009\u9879"), response && /*#__PURE__*/React.createElement(Pager, {
      page: response.data.page,
      unit: "\u9879",
      label: field.label,
      disabled: disabled,
      onPage: changePage
    }), field.catalog && /*#__PURE__*/React.createElement(Button, {
      icon: "plus",
      busy: catalogBusy,
      disabled: disabled,
      reason: typeof adapter.openCatalog !== 'function' ? '维护' + field.label + '尚未开通。' : '',
      onClick: () => onCatalog(field, request.reload)
    }, "\u7EF4\u62A4", field.label));
  }
  // 列表基础件（EmptyState / Pager）和按钮、错误框放在同一层：Choice 用 Pager 翻页，Pager 又用 Button 画按钮，
  // 分到两个文件就会互相依赖、无法排出加载顺序。WorkbenchListControls / WorkbenchControls 只是它们的既有入口名。
  const titles = {
    empty: '暂无记录',
    filtered: '当前筛选没有匹配项',
    loading: '正在读取…',
    error: '读取未完成'
  };
  function EmptyState({
    kind = 'empty',
    title,
    hint,
    action,
    error
  }) {
    if (!Object.prototype.hasOwnProperty.call(titles, kind)) throw new TypeError('empty_state_kind_unknown: ' + kind);
    if ((kind === 'filtered' || kind === 'error') && !action) throw new TypeError('empty_state_requires_action: ' + kind);
    return /*#__PURE__*/React.createElement("div", {
      className: 'wb-empty wb-empty-' + kind,
      role: kind === 'error' ? undefined : 'status',
      "aria-busy": kind === 'loading' || undefined
    }, /*#__PURE__*/React.createElement("p", {
      className: "wb-empty-title"
    }, title || titles[kind]), hint && /*#__PURE__*/React.createElement("p", {
      className: "wb-empty-hint"
    }, hint), kind === 'error' && error && /*#__PURE__*/React.createElement(ErrorBox, {
      error: error
    }), action && /*#__PURE__*/React.createElement("div", {
      className: "wb-empty-action"
    }, action));
  }
  function Pager({
    page = 1,
    pages,
    total,
    size,
    sizes,
    unit = '项',
    onPage,
    onSize,
    disabled,
    busy,
    label = '记录',
    sizeLabel,
    mode = 'pages',
    hasPrevious,
    hasNext,
    onPrevious,
    onNext,
    showPageSelect = false,
    showPageJump = false,
    jumpLabel = '跳转页码',
    jumpActionLabel = '跳转'
  }) {
    const data = page && typeof page === 'object' ? page : {
      number: page,
      pages,
      total,
      size
    };
    const number = data.number || 1,
      count = data.total == null ? total : data.total,
      perPage = data.size || size;
    const pageCount = data.pages || pages || (Number.isFinite(count) && perPage ? Math.max(1, Math.ceil(count / perPage)) : undefined);
    const [jump, setJump] = React.useState(String(number)),
      [jumpError, setJumpError] = React.useState(false);
    const jumpErrorId = React.useId();
    React.useEffect(() => {
      setJump(String(number));
      setJumpError(false);
    }, [number]);
    if (!['pages', 'cursor'].includes(mode)) throw new TypeError('pager_mode_unknown: ' + mode);
    if (onSize && (!Array.isArray(sizes) || !sizes.length || !sizes.every(value => Number.isSafeInteger(value) && value > 0))) {
      throw new TypeError('pager_sizes_not_declared_by_domain_api');
    }
    const locked = disabled || busy;
    const previous = mode === 'cursor' ? !!hasPrevious : number > 1;
    const next = mode === 'cursor' ? !!hasNext : pageCount != null ? number < pageCount : !!hasNext;
    const previousAction = onPrevious || onPage && (() => onPage(number - 1));
    const nextAction = onNext || onPage && (() => onPage(number + 1));
    function goToPage() {
      const target = Number(jump);
      if (!/^\d+$/.test(jump) || !Number.isSafeInteger(target) || target < 1 || target > pageCount) {
        setJumpError(true);
        return;
      }
      setJumpError(false);
      onPage(target);
    }
    return /*#__PURE__*/React.createElement("nav", {
      className: "wb-pager",
      "aria-label": label + '分页',
      "aria-busy": busy || undefined
    }, /*#__PURE__*/React.createElement("span", {
      className: "wb-pager-summary"
    }, mode === 'cursor' ? '按读取顺序翻页' : /*#__PURE__*/React.createElement(React.Fragment, null, count != null && /*#__PURE__*/React.createElement(React.Fragment, null, "\u5171 ", count, " ", unit, " \xB7 "), "\u7B2C ", number, pageCount != null && /*#__PURE__*/React.createElement(React.Fragment, null, " / ", pageCount), " \u9875")), /*#__PURE__*/React.createElement("div", {
      className: "wb-pager-actions"
    }, mode === 'pages' && showPageSelect && pageCount && onPage && /*#__PURE__*/React.createElement("label", {
      className: "wb-pager-size"
    }, "\u9875\u7801", /*#__PURE__*/React.createElement("select", {
      "aria-label": label + '页码',
      value: number,
      disabled: locked,
      onChange: event => onPage(Number(event.target.value))
    }, Array.from({
      length: pageCount
    }, (_, index) => index + 1).map(value => /*#__PURE__*/React.createElement("option", {
      key: value,
      value: value
    }, value)))), mode === 'pages' && showPageJump && pageCount && onPage && /*#__PURE__*/React.createElement("div", {
      className: "wb-pager-jump"
    }, /*#__PURE__*/React.createElement("input", {
      type: "number",
      "aria-label": jumpLabel,
      "aria-invalid": jumpError || undefined,
      "aria-describedby": jumpError ? jumpErrorId : undefined,
      min: 1,
      max: pageCount,
      step: 1,
      value: jump,
      disabled: locked,
      onChange: event => {
        setJump(event.target.value);
        setJumpError(false);
      },
      onKeyDown: event => {
        if (event.key === 'Enter') {
          event.preventDefault();
          goToPage();
        }
      }
    }), /*#__PURE__*/React.createElement(Button, {
      "aria-label": jumpActionLabel,
      disabled: locked,
      onClick: goToPage
    }, "\u8DF3\u8F6C"), jumpError && /*#__PURE__*/React.createElement("span", {
      id: jumpErrorId,
      role: "status",
      className: "wb-field-error"
    }, "\u8BF7\u8F93\u5165 1 \u5230 ", pageCount, " \u4E4B\u95F4\u7684\u9875\u7801\u3002")), onSize && /*#__PURE__*/React.createElement("label", {
      className: "wb-pager-size"
    }, "\u6BCF\u9875", /*#__PURE__*/React.createElement("select", {
      "aria-label": sizeLabel || label + '每页条数',
      value: perPage,
      disabled: locked,
      onChange: event => onSize(Number(event.target.value))
    }, !sizes.includes(perPage) && /*#__PURE__*/React.createElement("option", {
      value: perPage,
      disabled: true
    }, perPage, " ", unit, "\uFF08\u5F53\u524D\uFF09"), sizes.map(value => /*#__PURE__*/React.createElement("option", {
      key: value,
      value: value
    }, value, " ", unit)))), /*#__PURE__*/React.createElement(Button, {
      icon: "chevron-left",
      "aria-label": label + '上一页',
      disabled: locked || !previous || !previousAction,
      onClick: previousAction
    }, "\u4E0A\u4E00\u9875"), /*#__PURE__*/React.createElement(Button, {
      icon: "chevron-right",
      "aria-label": label + '下一页',
      disabled: locked || !next || !nextAction,
      onClick: nextAction
    }, "\u4E0B\u4E00\u9875")));
  }
  // 时间轴缩放：计划甘特、候选甘特、值班台分析时间轴共用同一组按钮、叫法和快捷键（+ 或 = 放大，- 缩小，F 显示完整范围）。
  // 上限由各时间轴按自己的绘制方式（DOM 或 canvas）和时间跨度申报，这里只负责一致地呈现和夹紧。
  function timelineZoomStep(zoom, direction, max) {
    return Math.max(1, Math.min(max, direction > 0 ? zoom * 2 : zoom / 2));
  }
  function timelineZoomKey(event) {
    if (event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey || event.target.closest('input,textarea,select,[role=dialog]')) return null;
    if (event.key === '+' || event.key === '=') return 'in';
    if (event.key === '-') return 'out';
    if (event.key === 'f' || event.key === 'F') return 'fit';
    return null;
  }
  function TimelineZoom({
    zoom,
    max,
    scope = '',
    onZoom,
    onFit,
    disabled,
    className = 'btn',
    fitClassName
  }) {
    const axis = scope + '时间轴',
      range = scope + '时间范围';
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
      icon: "minus",
      className: className,
      "aria-label": '缩小' + axis,
      title: '缩小' + axis + ' (-)',
      disabled: disabled || zoom <= 1,
      onClick: () => onZoom(timelineZoomStep(zoom, -1, max))
    }), /*#__PURE__*/React.createElement("span", {
      className: "wb-zoom-level"
    }, zoom, "\xD7"), /*#__PURE__*/React.createElement(Button, {
      icon: "plus",
      className: className,
      "aria-label": '放大' + axis,
      title: '放大' + axis + ' (+)',
      disabled: disabled || zoom >= max,
      onClick: () => onZoom(timelineZoomStep(zoom, 1, max))
    }), /*#__PURE__*/React.createElement(Button, {
      icon: "unfold-vertical",
      className: (fitClassName || className) + ' wb-zoom-fit',
      "aria-label": '显示完整' + range,
      title: '显示完整' + range + ' (F)',
      disabled: disabled || zoom <= 1,
      onClick: onFit
    }));
  }
  window.ResourceControls = {
    Icon,
    Button,
    Search,
    ErrorBox,
    Issues,
    Status,
    Modal,
    Relation,
    relationLabels,
    Choice,
    Field,
    focusFirstInvalid,
    EmptyState,
    Pager,
    TimelineZoom,
    timelineZoomKey,
    timelineZoomStep
  };
})();
