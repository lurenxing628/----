import React from './shared/runtime/react.js';
import APSResourceFile from './ResourceFileContract.js';
import { ResourceFileActionFlow } from './ResourceMaterialActions.jsx';

function ResourceFileActions({ kind, ...props }) {
  const contract = React.useMemo(() => APSResourceFile.create(kind), [kind]);
  return <ResourceFileActionFlow key={kind} {...props} contract={contract} />;
}

export { ResourceFileActions };
export default ResourceFileActions;
