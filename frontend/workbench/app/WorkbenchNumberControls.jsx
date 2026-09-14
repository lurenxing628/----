(function () {
  'use strict';
  const parentOwners = new Map();
  const inputClass = 'wb-number-input', parentClass = 'wb-number-parent', staticClass = 'wb-number-parent-static';

  function editable(input) {
    return window.APSWorkbenchControlBridge.available(input) && input.type === 'number' && !input.matches(':disabled') && !input.closest('.wb-control-popup');
  }
  function numberValue(document, value) {
    const probe = document.createElement('input');
    probe.type = 'number'; probe.value = value;
    return probe.valueAsNumber;
  }
  function declaredStep(input) {
    const value = input.getAttribute('data-wb-step');
    if (value !== null) {
      const amount = numberValue(input.ownerDocument, value);
      if (!Number.isFinite(amount) || amount <= 0) throw new Error('wb_step_must_be_finite_positive');
    }
    return value;
  }
  function nextValue(input, direction) {
    if (!editable(input) || input.validity.badInput || input.value !== '' && !Number.isFinite(input.valueAsNumber)) return null;
    const increment = declaredStep(input);
    if (increment !== null && input.value === '') return null;
    const probe = input.ownerDocument.createElement('input');
    probe.type = 'number';
    ['min', 'max', 'step', 'value'].forEach(name => {
      if (input.hasAttribute(name)) probe.setAttribute(name, input.getAttribute(name));
    });
    const anchored = input.step.toLowerCase() === 'any' || increment !== null;
    if (anchored) {
      // UI increments use the current value as a base, not a validity/rounding grid.
      probe.removeAttribute('min'); probe.removeAttribute('max');
      probe.step = increment === null ? '1' : increment; probe.setAttribute('value', input.value || '0');
    }
    probe.value = input.value;
    if (direction > 0) probe.stepUp(); else probe.stepDown();
    if (anchored) {
      const min = numberValue(input.ownerDocument, input.min), max = numberValue(input.ownerDocument, input.max);
      if (Number.isFinite(min) && Number.isFinite(max) && min > max) return null;
      if (Number.isFinite(min) && probe.valueAsNumber < min) probe.value = input.min;
      if (Number.isFinite(max) && probe.valueAsNumber > max) probe.value = input.max;
      if (input.value !== '' && direction * (probe.valueAsNumber - input.valueAsNumber) <= 0) return null;
    }
    return Number.isFinite(probe.valueAsNumber) && probe.value !== input.value ? probe.value : null;
  }
  function acquire(input, parent) {
    const hadInputClass = input.classList.contains(inputClass);
    let owner = parentOwners.get(parent);
    if (!owner) {
      owner = { count: 0, hadClass: parent.classList.contains(parentClass), hadStatic: parent.classList.contains(staticClass),
        static: getComputedStyle(parent).position === 'static' };
      parentOwners.set(parent, owner);
    }
    owner.count += 1;
    const ensure = () => {
      if (!input.classList.contains(inputClass)) input.classList.add(inputClass);
      if (owner.static && !parent.classList.contains(parentClass)) parent.classList.add(parentClass);
      if (owner.static && !parent.classList.contains(staticClass)) parent.classList.add(staticClass);
    };
    ensure();
    return { ensure, release() {
      if (!hadInputClass) input.classList.remove(inputClass);
      owner.count -= 1;
      if (!owner.count) {
        if (!owner.hadClass) parent.classList.remove(parentClass);
        if (!owner.hadStatic) parent.classList.remove(staticClass);
        parentOwners.delete(parent);
      }
    } };
  }
  function readBox(input, parent) {
    const rect = input.getBoundingClientRect(), host = parent.getBoundingClientRect();
    if (!rect.width || !rect.height || !host.width || !host.height || !input.getClientRects().length) return null;
    const scaleX = parent.offsetWidth ? host.width / parent.offsetWidth : 1;
    const scaleY = parent.offsetHeight ? host.height / parent.offsetHeight : 1;
    return { left: (rect.right - host.left) / scaleX - parent.clientLeft + parent.scrollLeft - 21,
      top: (rect.top - host.top) / scaleY - parent.clientTop + parent.scrollTop + 1,
      right: 'auto', bottom: 'auto', width: 20, height: Math.max(0, rect.height / scaleY - 2) };
  }
  function Arrow({ up }) {
    const nodes = window.APSFieldReports.iconNodes['chevron-down'];
    return <svg className="lucide" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor"
      strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={up ? { transform: 'rotate(180deg)' } : undefined}>
      {nodes.map(([tag, attrs], key) => React.createElement(tag, { ...attrs, key }))}</svg>;
  }
  function Stepper({ input, parent, refreshers }) {
    const [state, setState] = React.useState({ box: null, name: '', up: null, down: null });
    React.useLayoutEffect(() => {
      const classes = acquire(input, parent);
      function refresh() {
        classes.ensure();
        const next = { box: readBox(input, parent), name: window.APSWorkbenchControlBridge.label(input), up: nextValue(input, 1), down: nextValue(input, -1) };
        setState(previous => JSON.stringify(previous) === JSON.stringify(next) ? previous : next);
      }
      const observer = new ResizeObserver(refresh);
      observer.observe(input); observer.observe(parent); refreshers.set(input, refresh); refresh();
      return () => { observer.disconnect(); refreshers.delete(input); classes.release(); };
    }, [input, parent, refreshers]);
    function step(event, direction) {
      event.preventDefault(); event.stopPropagation();
      const value = nextValue(input, direction);
      if (value !== null) window.APSWorkbenchControlBridge.setValue(input, value);
      const refresh = refreshers.get(input); if (refresh) refresh();
    }
    return ReactDOM.createPortal(<span className="wb-number-stepper" style={state.box || { display: 'none' }}>
      {[1, -1].map(direction => {
        const label = (direction > 0 ? '增加' : '减少') + state.name;
        return <button key={direction} type="button" className="wb-number-step" title={label} aria-label={label}
          disabled={(direction > 0 ? state.up : state.down) === null} onMouseDown={event => event.preventDefault()}
          onClick={event => step(event, direction)}><Arrow up={direction > 0} /></button>;
      })}
    </span>, parent);
  }
  function WorkbenchNumberControls() {
    const [entries, setEntries] = React.useState([]), refreshers = React.useRef(new Map());
    React.useEffect(() => {
      let frame = 0, sequence = 0;
      const identities = new WeakMap();
      function scan() {
        frame = 0;
        const inputs = Array.from(document.querySelectorAll('body.aps-workbench input[type="number"]'))
          .filter(input => input.parentElement && !input.closest('.wb-control-popup'));
        const next = inputs.map(input => {
          if (!identities.has(input)) identities.set(input, ++sequence);
          return { input, parent: input.parentElement, key: identities.get(input) };
        });
        setEntries(previous => previous.length === next.length && previous.every((item, index) =>
          item.input === next[index].input && item.parent === next[index].parent) ? previous : next);
        refreshers.current.forEach(refresh => refresh());
      }
      const schedule = () => { if (!frame) frame = requestAnimationFrame(scan); };
      const ownNode = node => node.nodeType === 1 ? node.matches('.wb-number-stepper') || !!node.closest('.wb-number-stepper') :
        !!(node.parentElement && node.parentElement.closest('.wb-number-stepper'));
      const observer = new MutationObserver(records => {
        if (records.some(record => !ownNode(record.target) && (record.type !== 'childList' ||
          Array.from(record.addedNodes).concat(Array.from(record.removedNodes)).some(node => !ownNode(node))))) schedule();
      });
      observer.observe(document.body, { childList: true, subtree: true, attributes: true, characterData: true,
        attributeFilter: ['type', 'min', 'max', 'step', 'value', 'readonly', 'disabled', 'class', 'style', 'hidden', 'inert',
          'aria-label', 'aria-labelledby', 'title', 'id', 'name', 'data-wb-step'] });
      function refreshInput(event) {
        const refresh = refreshers.current.get(event.target); if (refresh) refresh();
      }
      function keydown(event) {
        const input = event.target;
        if (event.defaultPrevented || event.isComposing || !['ArrowUp', 'ArrowDown'].includes(event.key)
            || !(input instanceof window.HTMLElement) || !input.matches('body.aps-workbench input[type="number"][data-wb-step]')
            || !editable(input)) return;
        event.preventDefault();
        const value = nextValue(input, event.key === 'ArrowUp' ? 1 : -1);
        if (value !== null) window.APSWorkbenchControlBridge.setValue(input, value);
        refreshInput(event);
      }
      document.addEventListener('input', refreshInput, true); document.addEventListener('change', refreshInput, true);
      document.addEventListener('keydown', keydown);
      document.addEventListener('reset', schedule, true); document.addEventListener('scroll', schedule, true);
      window.addEventListener('resize', schedule); scan();
      return () => {
        observer.disconnect(); cancelAnimationFrame(frame);
        document.removeEventListener('input', refreshInput, true); document.removeEventListener('change', refreshInput, true);
        document.removeEventListener('keydown', keydown);
        document.removeEventListener('reset', schedule, true); document.removeEventListener('scroll', schedule, true);
        window.removeEventListener('resize', schedule);
      };
    }, []);
    return <>{entries.map(entry => <Stepper key={entry.key} {...entry} refreshers={refreshers.current} />)}</>;
  }
  window.WorkbenchNumberControls = WorkbenchNumberControls;
})();
