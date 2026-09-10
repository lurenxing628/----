(function () {
  'use strict';
  const Remember = React.createContext(null);
  function Provider({ remember, children }) { return <Remember.Provider value={remember}>{children}</Remember.Provider>; }
  function useSnapshot(value, enabled = true) {
    const remember = React.useContext(Remember), serialized = JSON.stringify(value);
    React.useLayoutEffect(() => {
      if (remember && enabled) remember(JSON.parse(serialized));
    }, [remember, serialized, enabled]);
  }
  window.WorkbenchPageContext = { Provider, useSnapshot };
})();
