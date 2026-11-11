(() => {
  // frontend/workbench/app/shared/runtime/theme.js
  var listeners = [];
  var current;
  var error = "";
  var valid = (value) => value === "light" || value === "dark";
  function read() {
    try {
      const stored = localStorage.getItem("aps_theme");
      const cookie = document.cookie.match(/(?:^|;\s*)aps_theme=(light|dark)(?:;|$)/);
      return {
        theme: valid(stored) ? stored : cookie ? cookie[1] : "light",
        error: stored && !valid(stored) ? "已忽略无效的主题设置。" : ""
      };
    } catch (_) {
      return { theme: "light", error: "无法读取本机主题偏好，当前使用浅色。" };
    }
  }
  function notify() {
    listeners.forEach((listener) => {
      listener({ theme: current, error });
    });
  }
  function refresh() {
    const result = read();
    if (result.theme === current && result.error === error) return;
    current = result.theme;
    error = result.error;
    document.documentElement.setAttribute("data-theme", current);
    notify();
  }

  // frontend/workbench/app/theme.js
  refresh();
})();
