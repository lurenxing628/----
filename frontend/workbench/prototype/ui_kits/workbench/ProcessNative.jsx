// APS Workbench · 工艺 / 物料 / 日历（流程主线 · 方案A）— native screen.
// Replaces the old iframe embed. React renders ONLY the empty .plana root;
// plana-logic.js paints the page into it as real light-DOM nodes, so every
// element is individually selectable / annotatable (the iframe used to expose
// the whole page as a single opaque element) and the screen loads instantly.
function ProcessNative({ onNav }) {
  const ref = React.useRef(null);
  React.useEffect(() => {
    const root = ref.current;
    if (root && window.APSPlanAInit) window.APSPlanAInit(root, onNav);
    // APSPlanAInit retains this session subtree and reattaches it on the next mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return <div className="plana" ref={ref} />;
}

window.ProcessNative = ProcessNative;
