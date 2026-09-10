// Keep the native dashboard lifecycle separate from the application shell.
function DashboardScreen({ onNav } = {}) {
  const root = React.useRef(null);
  const navigation = React.useRef(onNav);
  navigation.current = onNav;
  React.useEffect(() => window.APSDashboard.mount(root.current, (page, context) => {
    if (typeof navigation.current !== 'function') throw new Error('页面导航尚未接入，未离开值班台。');
    return navigation.current(page, context);
  }), []);
  return <section id="aps-decision" ref={root} aria-label="计划员值班台" />;
}

window.DashboardScreen = DashboardScreen;
