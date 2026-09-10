(function () {
  'use strict';
  function create() {
    const base = window.APSResourceAPI.create(), C = window.ActualGanttContract;
    return {
      async load(context, signal) {
        const scope = C.scope(context);
        return C.workspace(await base.query('actual-gantt', C.transport(scope), signal), scope);
      },
      async export(context, signal) {
        const scope = C.scope(context, true), output = await base.download('actual-gantt/export', C.transport(scope), signal);
        if (!output || !output.blob || !output.blob.size || output.contentType.split(';')[0] !== 'text/csv' || !/^attachment;/i.test(output.disposition))
          throw window.APSResourceContract.failure('实际甘特下载不是有效的 CSV 附件。');
        return output;
      }
    };
  }
  window.ActualGanttAPI = { create };
})();
