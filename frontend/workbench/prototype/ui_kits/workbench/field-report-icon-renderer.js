(function () {
  const ns = window.APSFieldReports;
  ns.paintIcons = function (root) {
    for (const el of root.querySelectorAll('[data-lucide]')) {
      const nodes = ns.iconNodes[el.dataset.lucide];
      if (!nodes) throw new Error('Unknown reporting icon: ' + el.dataset.lucide);
      const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      const attrs = { viewBox: '0 0 24 24', width: 16, height: 16, fill: 'none', stroke: 'currentColor', 'stroke-width': 2, 'stroke-linecap': 'round', 'stroke-linejoin': 'round', class: 'lucide', 'aria-hidden': 'true' };
      Object.entries(attrs).forEach(([name, value]) => svg.setAttribute(name, value));
      nodes.forEach(([name, properties]) => {
        const child = document.createElementNS(svg.namespaceURI, name);
        Object.entries(properties).forEach(([key, value]) => child.setAttribute(key, value));
        svg.appendChild(child);
      });
      el.replaceWith(svg);
    }
  };
})();
