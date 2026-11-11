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
    density = valid(value) ? value : 'comfortable';
    error = value !== null && !valid(value) ? '表格密度设置无效，当前使用舒适密度。' : '';
  } catch (_) {
    density = current ? current.density : 'comfortable';
    error = '无法读取本机表格密度设置，当前密度保持不变。';
  }
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

function get() {
  if (current === null) refresh();
  return { ...current };
}
function subscribe(listener) {
  if (current === null) refresh();
  listeners.add(listener);
  listen();
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0) unlisten();
  };
}

const WorkbenchDensity = { get, set, subscribe, refresh };

let listening = false;
function onStorage(event) {
  if (event.key === key || event.key === null) refresh();
}
function listen() {
  if (listening) return;
  listening = true;
  window.addEventListener('storage', onStorage);
  window.addEventListener('pageshow', refresh);
}
function unlisten() {
  if (!listening) return;
  listening = false;
  window.removeEventListener('storage', onStorage);
  window.removeEventListener('pageshow', refresh);
}

export { get, set, subscribe, refresh, WorkbenchDensity };
export default WorkbenchDensity;
