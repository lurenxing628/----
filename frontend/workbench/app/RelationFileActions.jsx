import React from './shared/runtime/react.js';
import APSRelationFile from './RelationFileContract.js';
import { ResourceFileActionFlow } from './ResourceMaterialActions.jsx';

function RelationFileActions({ kind, ...props }) {
  const contract = React.useMemo(() => APSRelationFile.create(kind), [kind]);
  return <ResourceFileActionFlow key={kind} {...props} contract={contract} />;
}

export { RelationFileActions };
export default RelationFileActions;
