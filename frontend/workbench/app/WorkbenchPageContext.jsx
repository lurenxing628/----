import React from './shared/runtime/react.js';

const Remember = React.createContext(null), Navigate = React.createContext(null);

function Provider({ remember, navigate, children }) {
  return <Remember.Provider value={remember}><Navigate.Provider value={navigate}>{children}</Navigate.Provider></Remember.Provider>;
}

function useNavigate() { return React.useContext(Navigate); }

function useSnapshot(value, enabled = true) {
  const remember = React.useContext(Remember), serialized = JSON.stringify(value);
  React.useLayoutEffect(() => {
    if (remember && enabled) remember(value);
  }, [remember, serialized, enabled]);
}

const WorkbenchPageContext = { Provider, useSnapshot, useNavigate };
export { Provider, useSnapshot, useNavigate, WorkbenchPageContext };
export default WorkbenchPageContext;
