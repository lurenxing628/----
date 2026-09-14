(function () {
  'use strict';

  function iconURL(name, color) {
    const nodes = window.APSFieldReports.iconNodes[name];
    if (!nodes) throw new Error('control_icon_missing: ' + name);
    const ns = 'http://www.w3.org/2000/svg',
      svg = document.createElementNS(ns, 'svg');
    Object.entries({
      viewBox: '0 0 24 24',
      fill: 'none',
      stroke: color,
      'stroke-width': '1.75',
      'stroke-linecap': 'round',
      'stroke-linejoin': 'round'
    }).forEach(([key, value]) => svg.setAttribute(key, value));
    nodes.forEach(([tag, attributes]) => {
      const node = document.createElementNS(ns, tag);
      Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, value));
      svg.appendChild(node);
    });
    return 'url("data:image/svg+xml,' + encodeURIComponent(new XMLSerializer().serializeToString(svg)) + '")';
  }
  // Variable names are spelled out in full so the style contract can trace where 20-controls.css gets these custom properties from.
  const ICONS = Object.freeze({
    '--wb-control-select-icon': 'chevron-down',
    '--wb-control-date-icon': 'calendar-days',
    '--wb-control-time-icon': 'clock-3',
    '--wb-control-disclosure-icon': 'chevron-right'
  });
  function themedIcons() {
    const color = getComputedStyle(document.documentElement).getPropertyValue('--ui-info-muted').trim();
    if (!color || !CSS.supports('color', color)) throw new Error('control_theme_color_unavailable');
    return Object.entries(ICONS).map(([name, icon]) => [name, iconURL(icon, color)]);
  }
  function WorkbenchControlStyles() {
    React.useLayoutEffect(() => {
      const style = document.body.style;
      const names = Object.keys(ICONS);
      const previous = names.map(name => [name, style.getPropertyValue(name), style.getPropertyPriority(name)]);
      const update = () => themedIcons().forEach(([name, value]) => style.setProperty(name, value));
      const observer = new MutationObserver(update);
      observer.observe(document.documentElement, {
        attributes: true,
        attributeFilter: ['data-theme']
      });
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
