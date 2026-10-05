(function () {
  'use strict';

  const Remember = React.createContext(null),
    Navigate = React.createContext(null);
  function Provider({
    remember,
    navigate,
    children
  }) {
    return /*#__PURE__*/React.createElement(Remember.Provider, {
      value: remember
    }, /*#__PURE__*/React.createElement(Navigate.Provider, {
      value: navigate
    }, children));
  }
  function useNavigate() {
    return React.useContext(Navigate);
  }
  function useSnapshot(value, enabled = true) {
    const remember = React.useContext(Remember),
      serialized = JSON.stringify(value);
    React.useLayoutEffect(() => {
      if (remember && enabled) remember(JSON.parse(serialized));
    }, [remember, serialized, enabled]);
  }
  window.WorkbenchPageContext = {
    Provider,
    useSnapshot,
    useNavigate
  };
})();
