(function () {
  'use strict';
  function create() {
    const base = window.APSResourceAPI.create(), C = window.ActualGanttContract;
    return window.APSReadBoundary.verified({
      async load(context, signal) {
        const scope = C.scope(context);
        return C.workspace(await base.query('actual-gantt', C.transport(scope), signal), scope);
      },
      async export(context, signal) {
        const scope = C.scope(context, true), output = await base.download('actual-gantt/export', C.transport(scope), signal, { timeout: 60000 });
        if (!output || !output.blob || !output.blob.size || output.contentType.split(';')[0] !== 'text/csv' || !/^attachment;/i.test(output.disposition))
          throw window.APSResourceContract.failure('下载的现场实际甘特不是有效的 CSV 附件。');
        return output;
      }
    }, ['load']);
  }
  function adapter(value) {
    const C = window.ActualGanttContract;
    return window.APSReadBoundary.checked(value, {
      load: (result, context) => C.workspace(result, context)
    });
  }
  window.ActualGanttAPI = { create, adapter };
})();
