(function () {
  'use strict';
  function iconURL(name, color) {
    const nodes = window.APSFieldReports.iconNodes[name];
    if (!nodes) throw new Error('Workbench control icon missing: ' + name);
    const ns = 'http://www.w3.org/2000/svg', svg = document.createElementNS(ns, 'svg');
    Object.entries({ viewBox: '0 0 24 24', fill: 'none', stroke: color, 'stroke-width': '1.75', 'stroke-linecap': 'round', 'stroke-linejoin': 'round' })
      .forEach(([key, value]) => svg.setAttribute(key, value));
    nodes.forEach(([tag, attributes]) => {
      const node = document.createElementNS(ns, tag);
      Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, value));
      svg.appendChild(node);
    });
    return 'url("data:image/svg+xml,' + encodeURIComponent(new XMLSerializer().serializeToString(svg)) + '")';
  }
  function themedIcons() {
    const color = getComputedStyle(document.documentElement).getPropertyValue('--ui-info-muted').trim();
    if (!color || !CSS.supports('color', color)) throw new Error('Workbench control theme color is unavailable.');
    return Object.entries({ select: 'chevron-down', date: 'calendar-days', time: 'clock-3', disclosure: 'chevron-right' })
      .map(([kind, name]) => ['--wb-control-' + kind + '-icon', iconURL(name, color)]);
  }
  function WorkbenchControlStyles() {
    React.useLayoutEffect(() => {
      const style = document.body.style;
      const names = ['select', 'date', 'time', 'disclosure'].map(kind => '--wb-control-' + kind + '-icon');
      const previous = names.map(name => [name, style.getPropertyValue(name), style.getPropertyPriority(name)]);
      const update = () => themedIcons().forEach(([name, value]) => style.setProperty(name, value));
      const observer = new MutationObserver(update);
      observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
      update();
      document.body.dataset.workbenchControlIcons = 'ready';
      return () => {
        observer.disconnect();
        previous.forEach(([name, value, priority]) => value ? style.setProperty(name, value, priority) : style.removeProperty(name));
        delete document.body.dataset.workbenchControlIcons;
      };
    }, []);
    return null;
  }
  window.WorkbenchControlStyles = WorkbenchControlStyles;
})();
