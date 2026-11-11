import React from './shared/runtime/react.js';
import ReportWorkspace from './ReportWorkspace.jsx';

// The shared report workspace publishes the real review plan once, without competing hooks.
function Workspace(props) { return <ReportWorkspace {...props} mode="review" />; }

const ReviewWorkspace = Workspace;

export { ReviewWorkspace, Workspace };
export default ReviewWorkspace;
