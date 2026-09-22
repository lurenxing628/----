(function () {
  'use strict';
  const listeners = new Set(), key = 'aps_density';
  let current = null;
  const valid = value => value === 'comfortable' || value === 'compact';
  function publish(density, error) {
    current = { density, error };
    document.documentElement.setAttribute('data-density', density);
    listeners.forEach(listener => listener({ ...current }));
    return { ...current };
  }
  function refresh() {
    let density, error;
    try {
      const value = localStorage.getItem(key);
      density = valid(value) ? value : 'comfortable'; error = value !== null && !valid(value) ? '表格密度设置无效，当前使用舒适密度。' : '';
    } catch (_) { density = current ? current.density : 'comfortable'; error = '无法读取本机表格密度设置，当前密度保持不变。'; }
    // pageshow and storage re-read the preference; an unchanged value must not re-render every subscriber.
    if (current && density === current.density && error === current.error) return { ...current };
    return publish(density, error);
  }
  function set(value) {
    if (!valid(value)) throw new TypeError('表格密度只能是舒适或紧凑。');
    let error = '';
    try { localStorage.setItem(key, value); }
    catch (_) { error = '表格密度已切换，但本机偏好未保存。'; }
    return publish(value, error);
  }
  window.WorkbenchDensity = {
    get: () => ({ ...current }), set,
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    }
  };
  window.addEventListener('storage', event => { if (event.key === key || event.key === null) refresh(); });
  window.addEventListener('pageshow', refresh);
  refresh();
})();
