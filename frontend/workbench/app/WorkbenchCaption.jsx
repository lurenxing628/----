(function () {
  'use strict';
  const Publish = React.createContext(null), Current = React.createContext(null);
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
      const entry = { caption }; publish(entry);
      return () => publish(previous => previous === entry ? null : previous);
    }, [publish, serialized]);
  }
  function Provider({ children }) {
    const [entry, publish] = React.useState(null);
    return <Publish.Provider value={publish}><Current.Provider value={entry && entry.caption}>{children}</Current.Provider></Publish.Provider>;
  }
  function Caption() {
    const value = React.useContext(Current);
    if (!value) return <div className="cap-rich" />;
    return <div className="cap-rich wb-current-plan" role="status" aria-label="当前方案" data-plan-ref={value.reference}>
      <strong>{value.label}</strong><span className="wb-current-name" title={value.name}>{value.name}</span>
      <span className="cap-preview">{value.status}</span>
      {value.version && <span className="cap-muted">{value.version}</span>}
      {value.range && <span className="cap-muted wb-current-range" title={value.range}>{value.range}</span>}
    </div>;
  }
  function Styles() {
    return null;
  }
  window.WorkbenchCaption = { Provider, Caption, Styles, useCaption };
})();
