(function () {
  'use strict';

  const pickerTypes = ['date', 'time', 'month', 'datetime-local'];
  function label(input) {
    const described = (input.getAttribute('aria-labelledby') || '').split(/\s+/).filter(Boolean).map(id => document.getElementById(id)).filter(Boolean).map(node => node.textContent.trim()).join(' ');
    if (described || input.getAttribute('aria-label')) return described || input.getAttribute('aria-label');
    const labels = Array.from(input.labels || []).map(node => {
      const copy = node.cloneNode(true);
      copy.querySelectorAll('input,select,textarea,button,.req,.fhint').forEach(child => child.remove());
      return copy.textContent.trim();
    }).filter(Boolean);
    return labels.join(' ') || input.name || (input.tagName === 'SELECT' ? '选择选项' : '输入值');
  }
  function available(input) {
    return input.isConnected && !input.matches(':disabled') && !input.readOnly && !input.closest('[inert]');
  }
  function setProperty(input, property, value) {
    if (!available(input)) return false;
    const view = input.ownerDocument.defaultView;
    const constructor = input.tagName === 'SELECT' ? view.HTMLSelectElement : view.HTMLInputElement;
    const descriptor = Object.getOwnPropertyDescriptor(constructor.prototype, property);
    if (!descriptor || !descriptor.set) throw new Error('该控件不支持值更新。');
    const before = input.value;
    // Use the native setter so React observes the existing input/change contract.
    descriptor.set.call(input, value);
    if (input.value !== before) {
      input.dispatchEvent(new Event('input', {
        bubbles: true
      }));
      input.dispatchEvent(new Event('change', {
        bubbles: true
      }));
    }
    return true;
  }
  function kind(input) {
    if (!input || !available(input)) return null;
    if (input.tagName === 'SELECT' && !input.multiple && input.size <= 1) return 'select';
    return input.tagName === 'INPUT' && pickerTypes.includes(input.type) ? input.type : null;
  }
  function rows(input) {
    return Array.from(input.options).map((option, index) => ({
      index,
      value: option.value,
      label: option.label,
      group: option.parentElement.tagName === 'OPTGROUP' ? option.parentElement.label : '',
      disabled: option.disabled || option.parentElement.tagName === 'OPTGROUP' && option.parentElement.disabled,
      hidden: option.hidden || option.parentElement.hidden
    })).filter(row => !row.hidden);
  }
  window.APSWorkbenchControlBridge = {
    label,
    available,
    kind,
    rows,
    setValue: (input, value) => setProperty(input, 'value', value),
    selectIndex: (input, index) => setProperty(input, 'selectedIndex', index)
  };
})();
