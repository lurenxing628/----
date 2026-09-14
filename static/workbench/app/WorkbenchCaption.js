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
        throw new Error('当前计划信息不完整，没有显示其他计划。');
      }
      if (caption && ['version', 'range'].some(key => caption[key] !== undefined && typeof caption[key] !== 'string')) {
        throw new Error('当前计划的版本或范围无效。');
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
      "aria-label": "\u5F53\u524D\u8BA1\u5212",
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
    return null;
  }
  window.WorkbenchCaption = {
    Provider,
    Caption,
    Styles,
    useCaption
  };
})();
