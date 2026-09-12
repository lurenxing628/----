(function () {
  'use strict';

  const listeners = new Set(),
    key = 'aps_density';
  let current = {
    density: 'comfortable',
    error: ''
  };
  const valid = value => value === 'comfortable' || value === 'compact';
  function publish(density, error) {
    current = {
      density,
      error
    };
    document.documentElement.setAttribute('data-density', density);
    listeners.forEach(listener => listener({
      ...current
    }));
    return {
      ...current
    };
  }
  function refresh() {
    try {
      const value = localStorage.getItem(key);
      return publish(valid(value) ? value : 'comfortable', value !== null && !valid(value) ? '表格密度设置无效，当前使用舒适密度。' : '');
    } catch (_) {
      return publish(current.density, '无法读取本机表格密度设置，当前密度保持不变。');
    }
  }
  function set(value) {
    if (!valid(value)) throw new TypeError('表格密度只能是舒适或紧凑。');
    let error = '';
    try {
      localStorage.setItem(key, value);
    } catch (_) {
      error = '表格密度已切换，但本机偏好未保存。';
    }
    return publish(value, error);
  }
  window.WorkbenchDensity = {
    get: () => ({
      ...current
    }),
    set,
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    }
  };
  window.addEventListener('storage', event => {
    if (event.key === key || event.key === null) refresh();
  });
  window.addEventListener('pageshow', refresh);
  refresh();
})();
