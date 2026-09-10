(function () {
  'use strict';

  const Publish = React.createContext(null),
    Current = React.createContext(null);
  function useCaption(value) {
    const publish = React.useContext(Publish);
    const serialized = JSON.stringify(value || null);
    React.useLayoutEffect(() => {
      if (!publish) return undefined;
      const caption = JSON.parse(serialized);
      if (caption && ['reference', 'label', 'name', 'status'].some(key => typeof caption[key] !== 'string' || !caption[key].trim())) {
        throw new Error('当前方案信息不完整，未显示其他方案。');
      }
      if (caption && ['version', 'range'].some(key => caption[key] !== undefined && typeof caption[key] !== 'string')) {
        throw new Error('当前方案版本或范围无效。');
      }
      const entry = {
        caption
      };
      publish(entry);
      return () => publish(previous => previous === entry ? null : previous);
    }, [publish, serialized]);
  }
  function Provider({
    children
  }) {
    const [entry, publish] = React.useState(null);
    return /*#__PURE__*/React.createElement(Publish.Provider, {
      value: publish
    }, /*#__PURE__*/React.createElement(Current.Provider, {
      value: entry && entry.caption
    }, children));
  }
  function Caption() {
    const value = React.useContext(Current);
    if (!value) return /*#__PURE__*/React.createElement("div", {
      className: "cap-rich"
    });
    return /*#__PURE__*/React.createElement("div", {
      className: "cap-rich wb-current-plan",
      role: "status",
      "aria-label": "\u5F53\u524D\u65B9\u6848",
      "data-plan-ref": value.reference
    }, /*#__PURE__*/React.createElement("strong", null, value.label), /*#__PURE__*/React.createElement("span", {
      className: "wb-current-name",
      title: value.name
    }, value.name), /*#__PURE__*/React.createElement("span", {
      className: "cap-preview"
    }, value.status), value.version && /*#__PURE__*/React.createElement("span", {
      className: "cap-muted"
    }, value.version), value.range && /*#__PURE__*/React.createElement("span", {
      className: "cap-muted wb-current-range",
      title: value.range
    }, value.range));
  }
  function Styles() {
    return /*#__PURE__*/React.createElement("style", null, `
      .operations-shell .top-header { min-height:64px; height:auto; gap:12px; flex-wrap:wrap; }
      .operations-shell .top-title { flex:0 1 auto; min-width:0; overflow-wrap:anywhere; }
      .operations-shell .cap-rich { flex:1 1 260px; min-width:0; }
      .operations-shell .wb-current-plan { display:flex; align-items:center; flex-wrap:wrap; gap:6px 10px; font-size:12px; line-height:20px; }
      .operations-shell .wb-current-plan strong { font-size:12px; }
      .operations-shell .wb-current-name, .operations-shell .wb-current-range { min-width:0; max-width:100%; overflow-wrap:anywhere; }
      .operations-shell .header-controls { flex:0 0 auto; margin-left:auto; }
      .operations-shell .wb-render-failure { padding:24px 0; }
      @media(max-width:760px) { .operations-shell .cap-rich.wb-current-plan { flex-basis:100%; order:3; } }
    `);
  }
  window.WorkbenchCaption = {
    Provider,
    Caption,
    Styles,
    useCaption
  };
})();
