import React from './shared/runtime/react.js';

const Publish = React.createContext(null), Current = React.createContext(null);

function useCaption(value) {
  const publish = React.useContext(Publish);
  const serialized = JSON.stringify(value || null);
  React.useLayoutEffect(() => {
    if (!publish) return undefined;
    const entry = { caption: value || null }; publish(entry);
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
  return <div className="cap-rich wb-current-plan" role="status" aria-label="当前计划" data-plan-ref={value.reference}>
    <strong>{value.label}</strong><span className="wb-current-name" title={value.name}>{value.name}</span>
    <span className="cap-preview">{value.status}</span>
    {value.version && <span className="cap-muted">{value.version}</span>}
    {value.range && <span className="cap-muted wb-current-range" title={value.range}>{value.range}</span>}
  </div>;
}

const WorkbenchCaption = { Provider, Caption, useCaption };
export { Provider, Caption, useCaption, WorkbenchCaption };
export default WorkbenchCaption;
