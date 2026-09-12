(function () {
  'use strict';

  const A = window.TrialAPI,
    C = window.TrialContract,
    U = window.TrialControls,
    S = window.TrialSession;
  function Directory({
    revision,
    onOpen,
    filterBase,
    fixedBase
  }) {
    const [collection, setCollection] = React.useState('drafts'),
      [query, setQuery] = React.useState({
        page: 1,
        size: 20,
        status: 'all'
      });
    const [onlyBase, setOnlyBase] = React.useState(false),
      [reload, refresh] = React.useReducer(n => n + 1, 0);
    React.useEffect(() => {
      setQuery(q => ({
        page: 1,
        size: q.size,
        status: q.status
      }));
    }, [revision]);
    const selectedBase = fixedBase || (onlyBase ? filterBase : null);
    const q = {
      ...query,
      ...(selectedBase ? {
        base_kind: Object.keys(selectedBase)[0],
        base_ref: Object.values(selectedBase)[0]
      } : {})
    };
    const read = S.useRead(async signal => {
      const v = await A.read('/trial/' + collection, q, signal);
      C.catalog(v, collection, q);
      return v;
    }, [collection, JSON.stringify(q), revision, reload]);
    function reset(patch = {}) {
      setQuery({
        page: 1,
        size: query.size,
        status: query.status,
        ...patch
      });
      refresh();
    }
    return /*#__PURE__*/React.createElement("section", {
      "aria-label": "\u6301\u4E45\u8BD5\u8C03\u76EE\u5F55",
      className: "tt-directory"
    }, /*#__PURE__*/React.createElement("div", {
      className: "tt-heading"
    }, /*#__PURE__*/React.createElement(U.Tabs, {
      value: collection,
      label: "\u8BD5\u8C03\u76EE\u5F55\u7C7B\u522B",
      options: [["drafts", '试调草稿'], ['scenarios', '已存场景']],
      onChange: value => {
        setCollection(value);
        reset({
          status: 'all'
        });
      }
    }), /*#__PURE__*/React.createElement("div", {
      className: "tt-tools"
    }, /*#__PURE__*/React.createElement("label", null, "\u72B6\u6001 ", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u76EE\u5F55\u72B6\u6001",
      value: query.status,
      onChange: e => reset({
        status: e.target.value
      })
    }, (collection === 'drafts' ? ['all', 'editing', 'saved', 'discarded'] : ['all', 'saved']).map(s => /*#__PURE__*/React.createElement("option", {
      key: s,
      value: s
    }, s === 'all' ? '全部' : U.statusLabel(s))))), /*#__PURE__*/React.createElement("label", null, "\u6BCF\u9875 ", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u76EE\u5F55\u6BCF\u9875\u6570\u91CF",
      value: query.size,
      onChange: e => reset({
        size: Number(e.target.value)
      })
    }, [10, 20, 50].map(n => /*#__PURE__*/React.createElement("option", {
      key: n
    }, n)))), filterBase && /*#__PURE__*/React.createElement("label", {
      className: "tt-check"
    }, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      checked: !!fixedBase || onlyBase,
      disabled: !!fixedBase,
      onChange: e => {
        setOnlyBase(e.target.checked);
        reset();
      }
    }), "\u4EC5\u6B64\u539F\u6765\u6E90"), /*#__PURE__*/React.createElement(U.Button, {
      icon: "refresh-cw",
      "aria-label": "\u91CD\u65B0\u8BFB\u53D6\u8BD5\u8C03\u76EE\u5F55",
      busy: read.busy,
      onClick: () => reset()
    }))), /*#__PURE__*/React.createElement(U.ErrorBox, {
      error: read.error
    }), read.busy && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u6B63\u5728\u8BFB\u53D6\u76EE\u5F55\u2026"), read.result && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "tt-directory-scroll"
    }, /*#__PURE__*/React.createElement("table", {
      className: "tt-table",
      "aria-label": "\u8BD5\u8C03\u76EE\u5F55"
    }, /*#__PURE__*/React.createElement("caption", {
      className: "wb-visually-hidden"
    }, "试调目录"), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u540D\u79F0"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u539F\u6765\u6E90"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u72B6\u6001"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u5B89\u6392"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u66F4\u65B0\u65F6\u95F4"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u672C\u673A\u64CD\u4F5C\u8005"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u64CD\u4F5C"))), /*#__PURE__*/React.createElement("tbody", null, read.result.data.items.map(r => /*#__PURE__*/React.createElement("tr", {
      key: r.detail_target,
      "data-trial-ref": r.open_target.draft_ref || r.open_target.scenario_ref
    }, /*#__PURE__*/React.createElement("td", null, r.display_name), /*#__PURE__*/React.createElement("td", null, r.base_display_name), /*#__PURE__*/React.createElement("td", null, U.statusLabel(r.status)), /*#__PURE__*/React.createElement("td", null, r.task_count), /*#__PURE__*/React.createElement("td", null, U.timeLabel(r.updated_at)), /*#__PURE__*/React.createElement("td", null, r.local_operator), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(U.Button, {
      icon: "arrow-right",
      onClick: () => onOpen(r.open_target)
    }, "\u6253\u5F00")))))), !read.result.data.items.length && /*#__PURE__*/React.createElement("div", {
      className: "tt-empty"
    }, "\u6B64\u8303\u56F4\u6682\u65E0", collection === 'drafts' ? '草稿' : '场景')), /*#__PURE__*/React.createElement(U.Pager, {
      page: read.result.data.page,
      label: "\u76EE\u5F55",
      onPage: page => setQuery({
        ...query,
        page,
        snapshot_ref: read.result.meta.snapshot_ref
      })
    }), /*#__PURE__*/React.createElement("div", {
      className: "tt-muted"
    }, "\u76EE\u5F55\u672A\u6267\u884C\u7EA6\u675F\u6821\u9A8C\uFF1B\u6253\u5F00\u8349\u7A3F\u540E\u8BFB\u53D6\u5F53\u524D\u68C0\u67E5\uFF0C\u573A\u666F\u4E3A\u4FDD\u5B58\u65F6\u5FEB\u7167\u3002")));
  }
  function SourceCatalog({
    onSelect,
    selected
  }) {
    const [kind, setKind] = React.useState('plan'),
      [run, setRun] = React.useState(null),
      [q, setQ] = React.useState({}),
      [epoch, refresh] = React.useReducer(n => n + 1, 0);
    const path = kind === 'plan' ? '/plans' : run ? '/scheduling/runs/' + run.run_ref + '/candidates' : '/scheduling/runs';
    const query = kind === 'plan' ? {
      collection: 'history',
      size: 10,
      ...q
    } : {
      page: 1,
      size: 10,
      ...q
    };
    const read = S.useRead(async signal => {
      const v = await A.read(path, query, signal),
        d = v.data;
      if (kind === 'plan') {
        C.check(Array.isArray(d.plans) && d.page.collection === 'history' && d.page.size === 10 && typeof d.page.has_more === 'boolean');
        C.check(d.plans.every(r => C.object(r.capabilities) && typeof r.display_name === 'string'));
      } else {
        const rows = run ? d.candidates : d.runs;
        C.check(Array.isArray(rows) && d.page.number === query.page && d.page.size === query.size && C.count(d.page.total) && rows.length <= query.size);
        C.check(rows.every(r => C.ref(run ? r.candidate_ref : r.run_ref)));
        if (run) C.check(d.run_ref === run.run_ref);
      }
      return v;
    }, [path, JSON.stringify(query), epoch]);
    const d = read.result && read.result.data,
      rows = d ? kind === 'plan' ? d.plans.filter(p => p.kind === 'official') : run ? d.candidates : d.runs : [];
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(U.Tabs, {
      label: "\u539F\u6765\u6E90\u7C7B\u578B",
      value: kind,
      options: [["plan", '原正式计划'], ['candidate', '排产候选']],
      onChange: value => {
        setKind(value);
        setRun(null);
        setQ({});
      }
    }), /*#__PURE__*/React.createElement("div", {
      className: "tt-heading"
    }, /*#__PURE__*/React.createElement("span", null, run ? '候选来源：' + U.timeLabel(run.accepted_at) : kind === 'plan' ? '正式计划目录' : '运行目录'), /*#__PURE__*/React.createElement("div", {
      className: "tt-tools"
    }, run && /*#__PURE__*/React.createElement(U.Button, {
      icon: "chevron-left",
      onClick: () => {
        setRun(null);
        setQ({});
      }
    }, "\u8FD0\u884C\u76EE\u5F55"), /*#__PURE__*/React.createElement(U.Button, {
      icon: "refresh-cw",
      "aria-label": "\u91CD\u8BFB\u539F\u6765\u6E90\u76EE\u5F55",
      busy: read.busy,
      onClick: () => {
        setQ({});
        refresh();
      }
    }))), /*#__PURE__*/React.createElement(U.ErrorBox, {
      error: read.error
    }), read.busy && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u6B63\u5728\u8BFB\u53D6\u539F\u6765\u6E90\u2026"), d && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "tt-source-list"
    }, rows.map(r => {
      const key = kind === 'plan' ? 'plan_ref' : run ? 'candidate_ref' : 'run_ref',
        id = r[key];
      const title = kind === 'plan' ? U.sourceLabel(r) : run ? r.label || '未命名候选' : U.timeLabel(r.accepted_at) + ' · ' + U.statusLabel(r.state);
      const disabled = kind === 'plan' ? !C.ref(id) || !r.capabilities.view : run ? !r.capabilities.view || !r.task_count : !r.candidate_count;
      return /*#__PURE__*/React.createElement("div", {
        key: id || title,
        className: "tt-source-row"
      }, key === 'run_ref' ? /*#__PURE__*/React.createElement(U.Button, {
        icon: "arrow-right",
        disabled: disabled,
        onClick: () => {
          setRun(r);
          setQ({});
        }
      }, title) : /*#__PURE__*/React.createElement("label", null, /*#__PURE__*/React.createElement("input", {
        type: "radio",
        name: "trial-base",
        disabled: disabled,
        checked: !!selected && selected[key] === id,
        onChange: () => onSelect({
          [key]: id
        }, title)
      }), title), /*#__PURE__*/React.createElement("span", {
        className: "tt-muted"
      }, kind === 'plan' ? r.is_current_official ? '当前正式' : '历史正式' : r.task_count + ' 道安排', run && ' · ' + U.statusLabel(r.status)));
    }), !rows.length && /*#__PURE__*/React.createElement("p", {
      className: "tt-empty"
    }, "\u672C\u9875\u6CA1\u6709\u53EF\u9009\u6765\u6E90")), kind === 'plan' ? /*#__PURE__*/React.createElement("div", {
      className: "tt-tools"
    }, /*#__PURE__*/React.createElement(U.Button, {
      icon: "chevron-left",
      disabled: !q.cursor,
      onClick: () => setQ({})
    }, "\u9996\u6279\u7248\u672C"), /*#__PURE__*/React.createElement(U.Button, {
      icon: "chevron-right",
      disabled: !d.page.has_more,
      onClick: () => setQ({
        cursor: d.page.next_cursor,
        snapshot_ref: read.result.meta.snapshot_ref
      })
    }, "\u4E0B\u4E00\u6279\u7248\u672C")) : /*#__PURE__*/React.createElement(U.Pager, {
      label: "\u6765\u6E90",
      page: d.page,
      onPage: page => setQ({
        ...q,
        page,
        snapshot_ref: read.result.meta.snapshot_ref
      })
    })));
  }
  function Create({
    initialBase,
    initialScope = {},
    commands,
    onClose,
    fixedBase = false,
    onExisting
  }) {
    const [base, setBase] = React.useState(initialBase || null),
      [label, setLabel] = React.useState(initialBase ? '指定原来源' : ''),
      [epoch, refresh] = React.useReducer(n => n + 1, 0);
    const [inspect, setInspect] = React.useState(false),
      [agreed, setAgreed] = React.useState(false);
    const input = {
      base,
      scope: initialScope
    };
    const baseline = React.useRef(initialBase || null);
    const guardOwner = window.WorkbenchGuards.useDirtyGuard({
      dirty: JSON.stringify(base) !== JSON.stringify(baseline.current),
      locked: commands.busy || !!commands.key,
      message: '新建试调的来源选择或确认尚未提交。'
    });
    async function close(detail) {
      if (detail && detail.guardConfirmed === true && detail.guardOwner === guardOwner || (await window.WorkbenchGuards.confirmLeave({
        owner: guardOwner
      }))) onClose();
    }
    const read = S.useRead(signal => A.preview(input, signal), [JSON.stringify(input), epoch], inspect && !!base);
    function select(value, title) {
      setBase(value);
      setLabel(title);
      setInspect(false);
      setAgreed(false);
    }
    const d = read.result && read.result.data;
    return /*#__PURE__*/React.createElement(U.Modal, {
      title: "\u4ECE\u539F\u6765\u6E90\u521B\u5EFA\u8BD5\u8C03",
      icon: "square-pen",
      onClose: close,
      guardOwner: guardOwner,
      locked: commands.busy || !!commands.key,
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(U.Button, {
        icon: "x",
        disabled: commands.busy || !!commands.key,
        onClick: close
      }, "\u53D6\u6D88"), onExisting && /*#__PURE__*/React.createElement(U.Button, {
        icon: "folder-open",
        disabled: commands.busy || !!commands.key,
        onClick: async () => {
          if (await window.WorkbenchGuards.confirmLeave({
            owner: guardOwner
          })) onExisting();
        }
      }, "\u6253\u5F00\u5DF2\u6709\u8349\u7A3F"), /*#__PURE__*/React.createElement(U.Button, {
        icon: "refresh-cw",
        disabled: !base || commands.busy,
        onClick: () => {
          commands.restore();
          setInspect(true);
          setAgreed(false);
          refresh();
        }
      }, "\u6838\u5BF9\u539F\u6765\u6E90"), /*#__PURE__*/React.createElement(U.Button, {
        icon: "plus",
        className: "btn primary",
        disabled: !d || !agreed || commands.blocked,
        onClick: () => commands.execute({
          action: 'create',
          input
        }, d.write_context.write_token)
      }, "\u786E\u8BA4\u521B\u5EFA\u8349\u7A3F"))
    }, /*#__PURE__*/React.createElement("div", {
      className: "trial-modal-body"
    }, !fixedBase && /*#__PURE__*/React.createElement(SourceCatalog, {
      selected: base,
      onSelect: select
    }), /*#__PURE__*/React.createElement("p", null, "\u5DF2\u9009\u62E9\uFF1A", label || '尚未选择'), /*#__PURE__*/React.createElement(U.ErrorBox, {
      error: read.error
    }), /*#__PURE__*/React.createElement(U.ErrorBox, {
      error: commands.error
    }), read.busy && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u6B63\u5728\u6838\u5BF9\u5B8C\u6574\u539F\u6765\u6E90\u2026"), d && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("p", null, "\u539F\u6765\u6E90\u5171 ", d.task_count, " \u9053\u5B89\u6392\uFF0C\u5B8C\u6574\u590D\u5236\uFF1B\u663E\u793A\u8303\u56F4\u4E0D\u622A\u65AD\u8349\u7A3F\u3002"), /*#__PURE__*/React.createElement(U.Issues, {
      rows: d.validation.issues
    }), /*#__PURE__*/React.createElement("label", {
      className: "tt-check"
    }, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      checked: agreed,
      onChange: e => setAgreed(e.target.checked)
    }), "\u786E\u8BA4\u57FA\u4E8E\u6B64\u6765\u6E90\u521B\u5EFA\u72EC\u7ACB\u8349\u7A3F\uFF0C\u6B63\u5F0F\u8BA1\u5212\u4FDD\u6301\u4E0D\u53D8"))));
  }
  window.TrialCatalog = {
    Directory,
    Create
  };
})();
