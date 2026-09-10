// The report model stays alive when navigating to the existing actual Gantt.
function FieldRecordScreen() {
  const root = React.useRef(null);
  React.useEffect(() => window.APSFieldReports.mount(root.current), []);
  return <section id="aps-reporting" ref={root} aria-label="现场记录" />;
}

window.FieldRecordScreen = FieldRecordScreen;
