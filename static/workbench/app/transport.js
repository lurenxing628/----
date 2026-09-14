(function () {
  'use strict';

  async function decode(response) {
    var type = response.headers.get('content-type') || '';
    if (!type.toLowerCase().includes('application/json')) throw new Error('本机服务返回了非预期的数据格式。');
    var payload;
    try {
      payload = await response.json();
    } catch (error) {
      if (error.name === 'AbortError') throw error;
      throw new Error('本机服务返回的数据无法解析。');
    }
    if (!response.ok || !payload || payload.ok !== true) {
      var message = payload && payload.error && payload.error.message;
      throw new Error(typeof message === 'string' && message ? message : '本机服务未能完成读取，请重试。');
    }
    if (payload.schema_version !== 1 || !payload.meta || payload.meta.source !== 'production' || payload.meta.time_basis !== 'factory_local' || typeof payload.meta.snapshot_ref !== 'string' || !payload.meta.snapshot_ref || typeof payload.meta.request_ref !== 'string' || !payload.meta.request_ref || typeof payload.meta.as_of !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/.test(payload.meta.as_of) || !payload.data || typeof payload.data !== 'object' || Array.isArray(payload.data)) throw new Error('读到的数据不完整，页面没有改动。请刷新后重试。');
    return payload;
  }
  async function read(url, signal) {
    var target = new URL(url, location.href);
    if (target.origin !== location.origin || !target.pathname.startsWith('/api/workbench/v1/')) throw new Error('数据地址不属于本机工作台。');
    var controller = new AbortController(),
      timedOut = false;
    var abort = function () {
      controller.abort();
    };
    if (signal) {
      signal.addEventListener('abort', abort, {
        once: true
      });
      if (signal.aborted) controller.abort();
    }
    var timer = setTimeout(function () {
      timedOut = true;
      controller.abort();
    }, 20000);
    try {
      var response;
      try {
        response = await fetch(target.href, {
          signal: controller.signal,
          credentials: 'same-origin',
          headers: {
            Accept: 'application/json'
          }
        });
      } catch (error) {
        if (error.name === 'AbortError') throw error;
        throw new Error('无法连接本机服务，请确认应用仍在运行后重试。');
      }
      return await decode(response);
    } catch (error) {
      if (timedOut) throw new Error('本机状态读取超时，请稍后重试。');
      throw error;
    } finally {
      clearTimeout(timer);
      if (signal) signal.removeEventListener('abort', abort);
    }
  }
  function downloadJSON(filename, value) {
    var blob = new Blob([JSON.stringify(value, null, 2)], {
      type: 'application/json;charset=utf-8'
    });
    var url = URL.createObjectURL(blob),
      link = document.createElement('a');
    link.href = url;
    link.download = filename;
    try {
      document.body.appendChild(link);
      link.click();
    } finally {
      link.remove();
      setTimeout(function () {
        URL.revokeObjectURL(url);
      }, 1000);
    }
  }
  window.APSWorkbenchTransport = {
    read: read,
    downloadJSON: downloadJSON
  };
})();
