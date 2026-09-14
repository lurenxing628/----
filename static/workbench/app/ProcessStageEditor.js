(function () {
  'use strict';

  const C = window.APSResourceContract,
    P = window.APSProcessContract;
  const {
    Button,
    ErrorBox,
    Issues
  } = window.ResourceControls;
  const active = entity => entity.operations.filter(row => row.status === 'active');
  const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
  const value = item => item === null || item === undefined ? '未填写' : String(item);
  function confirmationTime(text) {
    if (!text) return '未填写';
    return /(?:Z|[+-]\d\d:\d\d)$/.test(text) ? window.WorkbenchFormat.instant(text, {
      seconds: true
    }) : window.WorkbenchFormat.dateTime(text, {
      seconds: true
    });
  }
  function Confirmation({
    record
  }) {
    return /*#__PURE__*/React.createElement("span", {
      className: "process-confirmation"
    }, record && record.state === 'confirmed' ? /*#__PURE__*/React.createElement(React.Fragment, null, "\u5DF2\u786E\u8BA4", record.confirmed_at && /*#__PURE__*/React.createElement("time", {
      dateTime: record.confirmed_at,
      title: record.confirmed_at
    }, confirmationTime(record.confirmed_at)), record.confirmed_by && /*#__PURE__*/React.createElement(React.Fragment, null, " \xB7 ", record.confirmed_by)) : '未人工确认');
  }
  function location(stage, operationRef, groupRef) {
    const ref = item => typeof item === 'string' && /^[0-9a-f]{48}$/.test(item);
    if (stage != null && !['route', 'source', 'hours'].includes(stage) || operationRef != null && !ref(operationRef) || groupRef != null && !ref(groupRef)) throw C.failure('要定位的阶段或工序已失效，不会按序号或名称找相近的替代。');
    return {
      stage: stage || null,
      operationRef: operationRef || null,
      groupRef: groupRef || null
    };
  }
  function locate(entity, target) {
    const operation = target.operationRef && entity.operations.find(row => row.ref === target.operationRef);
    const group = target.groupRef && entity.external_groups.find(row => row.ref === target.groupRef);
    if (target.operationRef && (!operation || operation.status !== 'active')) throw C.failure('目标工序已删除、停用或不属于此零件，未按序号或同名替代。');
    if (target.groupRef && !group) throw C.failure('目标外协组已删除或不属于此零件，未按工序范围替代。');
    if (operation && group && operation.external_group_ref !== group.ref) throw C.failure('要定位的工序不属于指定外协组，不能混用两种定位。');
    return target;
  }
  function useFocus(root, ref, page) {
    React.useEffect(() => {
      if (!ref || !root.current) return undefined;
      const frame = requestAnimationFrame(() => {
        const row = root.current && Array.from(root.current.querySelectorAll('[data-process-location]')).find(node => node.dataset.processLocation === ref);
        if (row) {
          row.focus({
            preventScroll: true
          });
          row.scrollIntoView({
            block: 'center',
            inline: 'nearest'
          });
        }
      });
      return () => cancelAnimationFrame(frame);
    }, [root, ref, page]);
  }
  function usePage(rows, focusRef = null) {
    const [query, setQuery] = React.useState(''),
      [number, setNumber] = React.useState(1),
      [size, setSize] = React.useState(50);
    React.useEffect(() => {
      if (!focusRef) return;
      const index = rows.findIndex(row => row.ref === focusRef);
      if (index >= 0) {
        setQuery('');
        setNumber(Math.floor(index / size) + 1);
      }
    }, [rows, focusRef, size]);
    const filtered = React.useMemo(() => rows.filter(row => !query || [row.sequence, row.label, row.op_type_label].some(item => String(item || '').toLowerCase().includes(query.toLowerCase()))), [rows, query]);
    const pages = Math.max(1, Math.ceil(filtered.length / size)),
      page = Math.min(number, pages);
    return {
      query,
      setQuery: text => {
        setQuery(text);
        setNumber(1);
      },
      setNumber,
      setSize: next => {
        setSize(next);
        setNumber(1);
      },
      rows: filtered.slice((page - 1) * size, page * size),
      page: {
        number: page,
        size,
        total: filtered.length,
        pages,
        sort: []
      }
    };
  }
  function Pager({
    paging,
    disabled
  }) {
    return paging.page.total > 50 || paging.page.pages > 1 ? /*#__PURE__*/React.createElement(window.ResourceTables.Pager, {
      page: paging.page,
      disabled: disabled,
      onPage: paging.setNumber,
      onSize: paging.setSize
    }) : null;
  }
  function Search({
    paging,
    disabled
  }) {
    return /*#__PURE__*/React.createElement("label", {
      className: "search"
    }, /*#__PURE__*/React.createElement("input", {
      type: "search",
      "aria-label": "\u641C\u7D22\u5DE5\u5E8F\u3001\u5DE5\u79CD",
      placeholder: "\u641C\u7D22\u5DE5\u5E8F\u3001\u5DE5\u79CD\u2026",
      value: paging.query,
      disabled: disabled,
      onChange: event => paging.setQuery(event.target.value)
    }));
  }
  function Groups({
    rows,
    affected = [],
    discarded = [],
    onDiscard,
    totals,
    onTotal,
    disabled,
    title = '外协组原记录',
    empty = '尚无外协组记录。',
    focusRef = null
  }) {
    const selected = new Set(discarded),
      changed = new Set(affected);
    const paging = usePage(rows, focusRef),
      root = React.useRef(null);
    useFocus(root, focusRef, paging.page.number);
    return /*#__PURE__*/React.createElement("section", {
      ref: root
    }, /*#__PURE__*/React.createElement("h3", null, title), !rows.length ? /*#__PURE__*/React.createElement("p", {
      className: "muted"
    }, empty) : /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "wb-table-frame"
    }, /*#__PURE__*/React.createElement("div", {
      className: "card-scroll wb-table-shell"
    }, /*#__PURE__*/React.createElement("table", {
      className: "tbl wb-table",
      "aria-label": title,
      style: {
        minWidth: 850,
        tableLayout: 'fixed'
      }
    }, /*#__PURE__*/React.createElement("caption", {
      className: "wb-visually-hidden"
    }, title), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u5DE5\u5E8F\u8303\u56F4"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u5468\u671F\u7B97\u6CD5"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u603B\u5468\u671F\uFF08\u5929\uFF09"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u4F9B\u5E94\u5546"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u5907\u6CE8 / \u95EE\u9898"), onDiscard && /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u89E3\u9664\u539F\u7EC4"))), /*#__PURE__*/React.createElement("tbody", null, paging.rows.map(row => /*#__PURE__*/React.createElement("tr", {
      key: row.ref,
      "data-process-location": row.ref,
      tabIndex: row.ref === focusRef ? -1 : undefined,
      "aria-current": row.ref === focusRef ? 'true' : undefined
    }, /*#__PURE__*/React.createElement("td", null, row.start_sequence, " \u81F3 ", row.end_sequence, row.ref === focusRef && /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      value: row.ref
    })), /*#__PURE__*/React.createElement("td", null, {
      merged: '合并设置',
      separate: '分别设置'
    }[row.merge_mode] || value(row.merge_mode)), /*#__PURE__*/React.createElement("td", null, onTotal && row.merge_mode === 'merged' && C.own(totals, row.ref) ? /*#__PURE__*/React.createElement("input", {
      className: "wt-in",
      type: "number",
      step: "any",
      min: "0",
      "aria-label": '外协组 ' + row.start_sequence + ' 至 ' + row.end_sequence + ' 总周期',
      value: totals[row.ref],
      disabled: disabled,
      onChange: event => onTotal(row.ref, event.target.value),
      style: {
        width: '100%'
      }
    }) : P.valueText(row.total_days)), /*#__PURE__*/React.createElement("td", null, value(row.supplier_label)), /*#__PURE__*/React.createElement("td", {
      style: {
        whiteSpace: 'pre-wrap'
      }
    }, value(row.remark), /*#__PURE__*/React.createElement(Issues, {
      issues: row.issues || []
    })), onDiscard && /*#__PURE__*/React.createElement("td", null, changed.has(row.ref) ? /*#__PURE__*/React.createElement("label", null, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      "aria-label": '解除外协组 ' + row.start_sequence + ' 至 ' + row.end_sequence,
      checked: selected.has(row.ref),
      disabled: disabled,
      onChange: event => onDiscard(event.target.checked ? discarded.concat(row.ref) : discarded.filter(ref => ref !== row.ref))
    }), "\u660E\u786E\u89E3\u9664") : '保持原组'))))))), /*#__PURE__*/React.createElement(Pager, {
      paging: paging,
      disabled: disabled
    })));
  }
  function changes(before, after) {
    const result = [],
      old = new Map(before.operations.map(row => [row.ref, row]));
    const oldGroups = new Map(before.external_groups.map(row => [row.ref, row])),
      newGroups = new Map(after.external_groups.map(row => [row.ref, row]));
    const range = group => group ? value(group.start_sequence) + ' 至 ' + value(group.end_sequence) : '范围未填写';
    const state = item => ({
      missing: '未录入',
      present: '已有记录，未人工确认',
      locked: '待前一步确认',
      unconfirmed: '未人工确认',
      confirmed: '已确认'
    })[item] || '状态未明确';
    const stage = item => ({
      route: '工艺路线',
      source: '归属',
      hours: '工时定额',
      ready: '已就绪'
    })[item] || '阶段未明确';
    const cycleMode = item => ({
      merged: '合并设置',
      separate: '分别设置'
    })[item] || (item === null ? '未设置' : '原周期算法未明确');
    function field(label, previous, current, format = value) {
      if (!same(previous, current)) result.push({
        label,
        previous: format(previous),
        current: format(current)
      });
    }
    function relation(label, previousRef, currentRef, previousLabel, currentLabel) {
      if (previousRef === currentRef && previousLabel === currentLabel) return;
      const previous = previousRef ? previousLabel || '名称未填写' : '未选';
      let current = currentRef ? currentLabel || '名称未填写' : '未选';
      if (previousRef && currentRef && previousRef !== currentRef && previous === current) current += '（关联记录已更换）';
      result.push({
        label,
        previous,
        current
      });
    }
    function confirmation(label, previous, current) {
      field(label + '状态', previous.state, current.state, state);
      field(label + '时间', previous.confirmed_at, current.confirmed_at, confirmationTime);
      if (previous.confirmed_by !== current.confirmed_by) result.push({
        label: label + '记录',
        previous: '原确认记录',
        current: '确认记录已更新'
      });
    }
    after.operations.forEach(row => {
      const previous = old.get(row.ref);
      old.delete(row.ref);
      if (!previous) result.push({
        label: '工序 ' + row.sequence,
        previous: '不存在',
        current: '新增记录'
      });else {
        const prefix = '工序 ' + row.sequence + ' · ';
        [['sequence', '序号'], ['label', '工序名称'], ['setup_hours', '换型工时（小时）'], ['unit_hours', '单件工时（小时）'], ['external_days', '外协周期（天）']].forEach(([key, label]) => field(prefix + label, previous[key], row[key]));
        field(prefix + '归属', previous.source, row.source, P.sourceLabel);
        field(prefix + '状态', previous.status, row.status, item => ({
          active: '有效',
          deleted: '已停用'
        })[item] || '原状态未明确');
        relation(prefix + '工种', previous.op_type_ref, row.op_type_ref, previous.op_type_label, row.op_type_label);
        relation(prefix + '供应商', previous.supplier_ref, row.supplier_ref, previous.supplier_label, row.supplier_label);
        relation(prefix + '外协组', previous.external_group_ref, row.external_group_ref, range(oldGroups.get(previous.external_group_ref)), range(newGroups.get(row.external_group_ref)));
        confirmation(prefix + '归属确认', previous.confirmation.source, row.confirmation.source);
        confirmation(prefix + '工时确认', previous.confirmation.hours, row.confirmation.hours);
      }
    });
    old.forEach(row => result.push({
      label: '工序 ' + row.sequence,
      previous: row.label,
      current: '已移除'
    }));
    new Set([...oldGroups.keys(), ...newGroups.keys()]).forEach(ref => {
      const previous = oldGroups.get(ref),
        current = newGroups.get(ref),
        prefix = '外协组 ' + range(current || previous) + ' · ';
      if (!previous || !current) result.push({
        label: prefix + '记录',
        previous: previous ? '原有外协组' : '无原记录',
        current: current ? '新增外协组' : '已移除'
      });
      [['工序范围', range], ['周期算法', row => cycleMode(row.merge_mode)], ['总周期（天）', row => value(row.total_days)], ['备注', row => value(row.remark)]].forEach(([label, format]) => {
        field(prefix + label, previous ? format(previous) : '无原记录', current ? format(current) : '已移除');
      });
      relation(prefix + '供应商', previous && previous.supplier_ref, current && current.supplier_ref, previous && previous.supplier_label, current && current.supplier_label);
    });
    field('当前阶段', before.workflow.stage, after.workflow.stage, stage);
    field('工艺就绪状态', before.workflow.ready, after.workflow.ready, ready => ready ? '已就绪' : '未就绪');
    field('工艺记录来源', before.workflow.origin, after.workflow.origin, origin => ({
      legacy: '原有工艺记录',
      managed: '三阶段工艺记录'
    })[origin] || '来源未明确');
    ['route', 'source', 'hours'].forEach(key => confirmation(stage(key) + ' · 确认', before.workflow[key], after.workflow[key]));
    return result;
  }
  function Review({
    before,
    after,
    onAccept,
    disabled
  }) {
    const rows = React.useMemo(() => changes(before, after), [before, after]),
      paging = usePage(rows);
    return /*#__PURE__*/React.createElement("section", {
      className: "match-note",
      style: {
        display: 'block'
      },
      role: "status"
    }, /*#__PURE__*/React.createElement("p", null, "\u6700\u65B0\u8D44\u6599\u5DF2\u8BFB\u53D6\uFF0C\u8349\u7A3F\u6CA1\u6709\u88AB\u66FF\u6362\u3002\u5DEE\u5F02 ", rows.length, " \u9879\uFF0C\u8BF7\u6838\u5BF9\u4E0B\u8868\u548C\u5F53\u524D\u8349\u7A3F\u3002\u70B9\u300C\u91C7\u7528\u6700\u65B0\u8D44\u6599\u300D\u540E\uFF1A\u60A8\u6539\u8FC7\u7684\u9879\u4FDD\u7559\uFF0C\u5176\u4F59\u6309\u6700\u65B0\u503C\uFF1B\u6709\u53D8\u5316\u7684\u5DE5\u5E8F\u8981\u91CD\u65B0\u786E\u8BA4\uFF0C\u5DF2\u79FB\u9664\u7684\u5DE5\u5E8F\u4E0D\u518D\u63D0\u4EA4\u3002"), !!rows.length && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "card-scroll"
    }, /*#__PURE__*/React.createElement("table", {
      className: "tbl wb-table",
      "aria-label": "\u6700\u65B0\u8D44\u6599\u5DEE\u5F02",
      style: {
        tableLayout: 'fixed',
        width: '100%'
      }
    }, /*#__PURE__*/React.createElement("caption", {
      className: "wb-visually-hidden"
    }, "最新资料差异"), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u9879\u76EE"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u7F16\u8F91\u524D\u8D44\u6599"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u6700\u65B0\u8D44\u6599"))), /*#__PURE__*/React.createElement("tbody", null, paging.rows.map((row, index) => /*#__PURE__*/React.createElement("tr", {
      key: index
    }, /*#__PURE__*/React.createElement("td", null, row.label), /*#__PURE__*/React.createElement("td", {
      style: {
        overflowWrap: 'anywhere'
      }
    }, row.previous), /*#__PURE__*/React.createElement("td", {
      style: {
        overflowWrap: 'anywhere'
      }
    }, row.current)))))), /*#__PURE__*/React.createElement(Pager, {
      paging: paging,
      disabled: disabled
    })), /*#__PURE__*/React.createElement(Button, {
      icon: "check",
      disabled: disabled,
      onClick: onAccept
    }, "\u91C7\u7528\u6700\u65B0\u8D44\u6599"));
  }
  function useDraft({
    result,
    adapter,
    stage,
    build,
    reconcile,
    saved,
    onDirty
  }) {
    const [base, setBase] = React.useState(result),
      [draft, setDraft] = React.useState(() => build(result.data));
    const [review, setReview] = React.useState(null),
      [error, setError] = React.useState(null),
      [busy, setBusy] = React.useState(false);
    const baseline = React.useMemo(() => build(base.data), [base.data]);
    const dirty = React.useMemo(() => !same(draft, baseline), [draft, baseline]);
    const seenSaved = React.useRef(saved),
      request = React.useRef(null);
    React.useEffect(() => () => {
      if (request.current) request.current.abort();
    }, []);
    React.useEffect(() => {
      if (onDirty) onDirty(stage, dirty);
    }, [dirty, stage, onDirty]);
    React.useLayoutEffect(() => {
      if (base === result) return;
      if (seenSaved.current !== saved || !dirty) {
        setBase(result);
        setDraft(build(result.data));
        setReview(null);
        setError(null);
      } else setReview(result);
      seenSaved.current = saved;
    }, [result, saved]);
    function edit(next) {
      setDraft(next);
      setError(null);
    }
    async function reload() {
      if (busy) return;
      const controller = new AbortController();
      request.current = controller;
      setBusy(true);
      setError(null);
      try {
        const fresh = P.detail(await adapter.detail('part', base.data.ref, controller.signal), base.data.ref);
        if (!controller.signal.aborted) setReview(fresh);
      } catch (failure) {
        if (!controller.signal.aborted) setError(failure);
      } finally {
        if (!controller.signal.aborted) setBusy(false);
        if (request.current === controller) request.current = null;
      }
    }
    function accept() {
      setDraft(reconcile(draft, base.data, review.data));
      setBase(review);
      setReview(null);
      setError(null);
    }
    return {
      base,
      draft,
      edit,
      dirty,
      review,
      error,
      setError,
      busy,
      reload,
      accept
    };
  }
  function Feedback({
    model,
    disabled,
    paging
  }) {
    const page = model.error && model.error.locate_page;
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(ErrorBox, {
      error: model.error
    }), page && paging && /*#__PURE__*/React.createElement(Button, {
      icon: "arrow-right",
      disabled: disabled,
      onClick: () => {
        paging.setQuery('');
        paging.setNumber(page);
      }
    }, "\u5B9A\u4F4D\u5230\u7B2C ", page, " \u9875"), /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      busy: model.busy,
      disabled: disabled,
      onClick: model.reload
    }, "\u5237\u65B0\u8BE6\u60C5\u5E76\u4FDD\u7559\u8349\u7A3F"), model.review && /*#__PURE__*/React.createElement(Review, {
      before: model.base.data,
      after: model.review.data,
      disabled: disabled || model.busy,
      onAccept: model.accept
    }));
  }
  // Unconfirmed operations are reported with the page they sit on (unfiltered order, current page size),
  // so a 120-operation part can be fixed without paging blind; the first offending page rides on the error.
  function unconfirmed(rows, all, size, label) {
    const pages = new Map();
    rows.forEach(row => {
      const page = Math.floor(all.indexOf(row) / size) + 1;
      pages.set(page, (pages.get(page) || []).concat(row.sequence));
    });
    const ordered = Array.from(pages.entries()).sort((a, b) => a[0] - b[0]);
    const error = C.failure('还有 ' + rows.length + ' 道工序的' + label + '没有勾选确认：' + ordered.map(([page, sequences]) => '第 ' + page + ' 页工序 ' + sequences.join('、')).join('；') + '。');
    error.locate_page = ordered[0][0];
    return error;
  }
  function reason(model, adapter, stage) {
    const entity = model.base.data;
    return model.review ? '请先核对最新资料。' : model.busy ? '正在读取最新资料。' : P.reason(entity.capabilities, 'stage_confirm', typeof adapter.command === 'function') || (entity.workflow[stage === 'source' ? 'route' : 'source'].state !== 'confirmed' ? stage === 'source' ? '请先确认路线。' : '请先确认归属。' : '') || (stage === 'source' ? model.base.meta.source !== 'production' ? '当前不是生产数据，不能保存。' : '' : C.blocked(entity.write_context, 'process', stage + '_confirm', model.base.meta.source));
  }
  window.ProcessStageEditor = {
    active,
    same,
    value,
    confirmationTime,
    Confirmation,
    usePage,
    Pager,
    Search,
    Groups,
    Review,
    useDraft,
    Feedback,
    reason,
    location,
    locate,
    useFocus,
    unconfirmed
  };
})();
