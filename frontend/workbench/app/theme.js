(function () {
  'use strict';
  var listeners = [], current, error = '';
  var valid = function (value) { return value === 'light' || value === 'dark'; };
  function read() {
    try {
      // 本机偏好只有 aps_theme 一个键；没有时用服务端模板也在读的同名 cookie。
      var stored = localStorage.getItem('aps_theme');
      var cookie = document.cookie.match(/(?:^|;\s*)aps_theme=(light|dark)(?:;|$)/);
      return { theme: valid(stored) ? stored : cookie ? cookie[1] : 'light',
        error: stored && !valid(stored) ? '已忽略无效的主题设置。' : '' };
    } catch (_) { return { theme: 'light', error: '无法读取本机主题偏好，当前使用浅色。' }; }
  }
  function notify() { listeners.forEach(function (listener) { listener({ theme: current, error: error }); }); }
  function refresh() {
    var result = read();
    // Window focus and pageshow re-read the preference; an unchanged value must not re-render the whole shell.
    if (result.theme === current && result.error === error) return;
    current = result.theme; error = result.error;
    document.documentElement.setAttribute('data-theme', current); notify();
  }
  function set(value) {
    if (!valid(value)) throw new Error('主题值无效。');
    current = value; error = '';
    document.documentElement.setAttribute('data-theme', value);
    try {
      localStorage.setItem('aps_theme', value);
      document.cookie = 'aps_theme=' + value + '; Path=/; Max-Age=31536000; SameSite=Lax';
    } catch (_) { error = '主题已切换，但本机偏好未保存。'; }
    notify(); return { theme: current, error: error };
  }
  window.APSWorkbenchTheme = {
    get: function () { return { theme: current, error: error }; }, set: set,
    subscribe: function (listener) {
      listeners.push(listener);
      return function () { listeners = listeners.filter(function (item) { return item !== listener; }); };
    }
  };
  window.addEventListener('storage', function (event) {
    if (event.key === 'aps_theme' || event.key === null) refresh();
  });
  window.addEventListener('pageshow', refresh);
  window.addEventListener('focus', refresh);
  refresh();
})();
