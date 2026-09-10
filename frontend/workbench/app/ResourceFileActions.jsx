(function () {
  'use strict';
  function ResourceFileActions({ kind, ...props }) {
    const contract = React.useMemo(() => window.APSResourceFile.create(kind), [kind]);
    return <window.ResourceFileActionFlow key={kind} {...props} contract={contract} />;
  }
  window.ResourceFileActions = ResourceFileActions;
})();
