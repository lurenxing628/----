(function () {
  'use strict';

  const C = window.APSResourceContract,
    S = window.APSResourceSession;
  const {
    Button,
    Icon,
    ErrorBox,
    Issues,
    Status
  } = window.ResourceControls;
  const kinds = {
    machines: 'machine',
    operators: 'operator',
    suppliers: 'supplier'
  };
  const names = {
    machines: '关联设备',
    operators: '关联人员',
    suppliers: '关联供应商'
  };
  const ref = value => typeof value === 'string' && /^[0-9a-f]{48}$/.test(value);
  const count = value => Number.isSafeInteger(value) && value >= 0;
  function query(result, parent, scope) {
    if (result && result.ok === false) throw result;
    const meta = result && result.meta,
      data = result && result.data,
      page = data && data.page;
    if (!C.object(result) || result.ok !== true || result.schema_version !== 1 || !C.object(meta) || !['production', 'demo'].includes(meta.source) || meta.time_basis !== 'factory_local' || !['snapshot_ref', 'request_ref', 'as_of'].every(key => typeof meta[key] === 'string' && meta[key]) || !Array.isArray(result.warnings) || !C.object(data) || !C.object(data.basis) || typeof data.basis.code !== 'string' || !data.basis.code || typeof data.basis.message !== 'string' || !data.basis.message || !ref(parent) || data.parent_ref !== parent || data.parent_kind !== 'op_type' || data.relation !== scope.relation || !C.own(kinds, scope.relation) || !Array.isArray(data.entities) || !data.entities.every(item => C.object(item) && item.kind === kinds[scope.relation] && ref(item.ref) && typeof item.business_code === 'string' && typeof item.label === 'string' && (item.status === null || typeof item.status === 'string') && C.object(item.fields) && Array.isArray(item.issues) && item.write_context === null) || new Set(data.entities.map(item => item.ref)).size !== data.entities.length || !C.object(page) || page.number !== scope.page || page.size !== scope.size || !count(page.total) || !count(page.pages) || page.pages !== Math.max(1, Math.ceil(page.total / page.size)) || page.number < 1 || page.number > Math.max(1, page.pages) || data.entities.length !== Math.min(page.size, Math.max(0, page.total - (page.number - 1) * page.size)) || !Array.isArray(page.sort) || page.sort.length !== 1 || page.sort[0].field !== 'business_code' || page.sort[0].direction !== 'asc' || scope.snapshot_ref && meta.snapshot_ref !== scope.snapshot_ref) throw C.failure('关联资料或分页范围不一致，请重新读取。');
    return result;
  }
  function Association({
    adapter,
    entity,
    relation,
    onOpen
  }) {
    const [scope, setScope] = React.useState({
      relation,
      query: '',
      page: 1,
      size: 5
    });
    const [search, setSearch] = React.useState('');
    const read = S.useQuery(async signal => {
      if (!adapter || typeof adapter.relations !== 'function') throw C.failure('关联资料读取接口尚未接入。');
      return query(await adapter.relations(entity.ref, scope, signal), entity.ref, scope);
    }, [adapter, entity.ref, scope]);
    const data = read.result && read.result.data,
      title = names[relation];
    function refresh() {
      setScope(current => ({
        ...current,
        page: 1,
        snapshot_ref: undefined
      }));
    }
    function next(page) {
      setScope(current => ({
        ...current,
        page,
        snapshot_ref: read.result.meta.snapshot_ref
      }));
    }
    return /*#__PURE__*/React.createElement("section", {
      className: "wb-resource-association",
      "aria-label": title
    }, /*#__PURE__*/React.createElement("form", {
      className: "wb-resource-association-head",
      onSubmit: event => {
        event.preventDefault();
        setScope({
          relation,
          query: search.trim(),
          page: 1,
          size: 5
        });
      }
    }, /*#__PURE__*/React.createElement("h4", null, title, data && /*#__PURE__*/React.createElement("span", {
      className: "muted"
    }, " ", data.page.total)), /*#__PURE__*/React.createElement("div", {
      className: "search"
    }, /*#__PURE__*/React.createElement("span", {
      className: "ic"
    }, /*#__PURE__*/React.createElement(Icon, {
      name: "search"
    })), /*#__PURE__*/React.createElement("input", {
      type: "search",
      "aria-label": '搜索' + title,
      value: search,
      placeholder: "\u7F16\u53F7\u3001\u540D\u79F0",
      onChange: event => setSearch(event.target.value)
    })), /*#__PURE__*/React.createElement(Button, {
      icon: "search",
      type: "submit",
      "aria-label": '查询' + title,
      busy: read.loading
    }), /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      "aria-label": '刷新' + title,
      busy: read.loading,
      onClick: refresh
    })), read.loading && /*#__PURE__*/React.createElement(window.WorkbenchControls.EmptyState, {
      kind: "loading",
      title: '正在读取' + title + '…'
    }), read.error && /*#__PURE__*/React.createElement(window.WorkbenchControls.EmptyState, {
      kind: "error",
      error: read.error,
      action: /*#__PURE__*/React.createElement(Button, {
        icon: "refresh-cw",
        onClick: refresh
      }, "\u91CD\u65B0\u8BFB\u53D6", title)
    }), data && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("p", {
      className: "muted wb-resource-association-basis"
    }, data.basis.message), /*#__PURE__*/React.createElement("div", {
      className: "wb-resource-association-list"
    }, data.entities.map(item => /*#__PURE__*/React.createElement("div", {
      key: item.ref
    }, /*#__PURE__*/React.createElement("button", {
      type: "button",
      className: "wb-resource-relation",
      onClick: () => onOpen(item.kind, item.ref),
      "aria-label": '查看' + C.resourceName(item.kind) + ' ' + item.business_code + ' ' + item.label,
      disabled: !onOpen
    }, /*#__PURE__*/React.createElement("span", {
      className: "wb-resource-relation-content"
    }, /*#__PURE__*/React.createElement("span", {
      className: "lnk"
    }, item.business_code, " \xB7 ", item.label), item.fields.relation_source_label && /*#__PURE__*/React.createElement("span", {
      className: "muted"
    }, item.fields.relation_source_label), relation === 'operators' && /*#__PURE__*/React.createElement("span", {
      className: "muted"
    }, "\u5339\u914D\u8BBE\u5907\u6388\u6743 ", count(item.fields.matching_machine_authorization_count) ? item.fields.matching_machine_authorization_count : '未知', " \u9879", typeof item.fields.qualification_matches === 'boolean' && (item.fields.qualification_matches ? ' · 工种资格匹配' : ' · 工种资格不匹配'))), /*#__PURE__*/React.createElement(Status, {
      kind: item.kind,
      entity: item
    }), /*#__PURE__*/React.createElement(Icon, {
      name: "chevron-right"
    })), /*#__PURE__*/React.createElement(Issues, {
      issues: item.issues
    })))), !data.entities.length && !read.loading && !read.error && /*#__PURE__*/React.createElement(window.WorkbenchControls.EmptyState, {
      kind: scope.query ? 'filtered' : 'empty',
      action: scope.query ? /*#__PURE__*/React.createElement(Button, {
        onClick: () => {
          setSearch('');
          setScope({
            relation,
            query: '',
            page: 1,
            size: 5
          });
        }
      }, "\u6E05\u9664\u7B5B\u9009") : undefined
    }), data.page.pages > 1 && /*#__PURE__*/React.createElement(window.WorkbenchControls.Pager, {
      page: data.page,
      sizes: [5],
      unit: "\u9879",
      label: title,
      disabled: read.loading,
      onPage: next
    }), /*#__PURE__*/React.createElement(Issues, {
      issues: read.result.warnings
    })));
  }
  function ResourceDetailRelations({
    adapter,
    entity,
    onOpen
  }) {
    const relations = entity.fields.category === 'internal' ? ['machines', 'operators'] : ['suppliers'];
    return /*#__PURE__*/React.createElement("div", {
      className: "wb-resource-relations"
    }, null, entity.fields.category === 'internal' && /*#__PURE__*/React.createElement("p", {
      className: "muted"
    }, "\u9759\u6001\u53EF\u7528\u6570\u91CF\uFF1A\u8BBE\u5907 ", C.availability(entity.availability) ? entity.availability.machines : '未知', " \u53F0 \xB7 \u4EBA\u5458 ", C.availability(entity.availability) ? entity.availability.operators : '未知', " \u4EBA\u3002\u5173\u8054\u8BB0\u5F55\u5305\u62EC\u505C\u7528\u6216\u8D44\u683C\u5F85\u6838\u5BF9\u8D44\u6E90\uFF0C\u4E0D\u4EE3\u8868\u5F53\u524D\u65F6\u6BB5\u53EF\u6392\u3002"), relations.map(relation => /*#__PURE__*/React.createElement(Association, {
      key: relation,
      adapter: adapter,
      entity: entity,
      relation: relation,
      onOpen: onOpen
    })));
  }
  ResourceDetailRelations.query = query;
  window.ResourceDetailRelations = ResourceDetailRelations;
})();
