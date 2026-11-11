let listeners = [], current, error = '';
const valid = value => value === 'light' || value === 'dark';

function read() {
  try {
    // 本机偏好只有 aps_theme 一个键；没有时用服务端模板也在读的同名 cookie。
    const stored = localStorage.getItem('aps_theme');
    const cookie = document.cookie.match(/(?:^|;\s*)aps_theme=(light|dark)(?:;|$)/);
    return {
      theme: valid(stored) ? stored : cookie ? cookie[1] : 'light',
      error: stored && !valid(stored) ? '已忽略无效的主题设置。' : ''
    };
  } catch (_) {
    return { theme: 'light', error: '无法读取本机主题偏好，当前使用浅色。' };
  }
}

function notify() {
  listeners.forEach(listener => {
    listener({ theme: current, error });
  });
}

function refresh() {
  const result = read();
  // Window focus and pageshow re-read the preference; an unchanged value must not re-render the whole shell.
  if (result.theme === current && result.error === error) return;
  current = result.theme;
  error = result.error;
  document.documentElement.setAttribute('data-theme', current);
  notify();
}

function set(value) {
  if (!valid(value)) throw new Error('主题值无效。');
  current = value;
  error = '';
  document.documentElement.setAttribute('data-theme', value);
  try {
    localStorage.setItem('aps_theme', value);
    document.cookie = 'aps_theme=' + value + '; Path=/; Max-Age=31536000; SameSite=Lax';
  } catch (_) {
    error = '主题已切换，但本机偏好未保存。';
  }
  notify();
  return { theme: current, error };
}

function get() {
  if (current === undefined) refresh();
  return { theme: current, error };
}

function subscribe(listener) {
  if (current === undefined) refresh();
  listeners.push(listener);
  listen();
  return () => {
    listeners = listeners.filter(item => item !== listener);
    if (listeners.length === 0) unlisten();
  };
}

let listening = false;
function onStorage(event) {
  if (event.key === 'aps_theme' || event.key === null) refresh();
}
function listen() {
  if (listening) return;
  listening = true;
  window.addEventListener('storage', onStorage);
  window.addEventListener('pageshow', refresh);
  window.addEventListener('focus', refresh);
}
function unlisten() {
  if (!listening) return;
  listening = false;
  window.removeEventListener('storage', onStorage);
  window.removeEventListener('pageshow', refresh);
  window.removeEventListener('focus', refresh);
}

const APSWorkbenchTheme = { get, set, subscribe, refresh };
export { get, set, subscribe, refresh, APSWorkbenchTheme };
export default APSWorkbenchTheme;
