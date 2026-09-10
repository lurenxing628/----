(function () {
  'use strict';

  function ResourceFileActions({
    kind,
    ...props
  }) {
    const contract = React.useMemo(() => window.APSResourceFile.create(kind), [kind]);
    return /*#__PURE__*/React.createElement(window.ResourceFileActionFlow, {
      key: kind,
      ...props,
      contract: contract
    });
  }
  window.ResourceFileActions = ResourceFileActions;
})();
