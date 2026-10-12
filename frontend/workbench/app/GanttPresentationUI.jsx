(function () {
  'use strict';
  function Axis({ axis, width, offset = 0, printing = false }) {
    const x = value => printing ? value / width * 100 + '%' : value - offset;
    return <div className="wb-gantt-axis">
      {axis.bands.map(band => <div className="wb-gantt-axis-band" key={band.at} style={{ left: x(band.x), width: printing ? band.width / width * 100 + '%' : band.width }} title={band.label}>{band.label}</div>)}
      {axis.ticks.map(tick => <div className="wb-gantt-axis-tick" key={tick.at} style={{ left: x(tick.x) }}>{tick.label}</div>)}
    </div>;
  }
  function useExpanded() {
    const [expanded, setExpanded] = React.useState(false), trigger = React.useRef(null);
    React.useEffect(() => {
      if (!expanded) return;
      const overflow = document.body.style.overflow; document.body.style.overflow = 'hidden';
      const close = event => { if (event.key === 'Escape' && !event.target.closest('input,textarea,select')) { event.preventDefault(); setExpanded(false); } };
      document.addEventListener('keydown', close);
      return () => { document.body.style.overflow = overflow; document.removeEventListener('keydown', close); if (trigger.current && trigger.current.isConnected) trigger.current.focus(); };
    }, [expanded]);
    return { expanded, toggle: event => { if (!expanded) trigger.current = event.currentTarget; setExpanded(value => !value); }, collapse: () => setExpanded(false) };
  }
  window.GanttPresentationUI = { Axis, useExpanded };
})();
