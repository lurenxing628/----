(function () {
  'use strict';
  // Load after RelationFileContract.js and ResourceMaterialActions.jsx.
  function RelationFileActions({ kind, ...props }) {
    const contract = React.useMemo(() => window.APSRelationFile.create(kind), [kind]);
    return <window.ResourceFileActionFlow key={kind} {...props} contract={contract} />;
  }
  window.RelationFileActions = RelationFileActions;
})();
