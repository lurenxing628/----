(function () {
  'use strict';

  function create() {
    const base = window.APSResourceAPI.create(),
      C = window.ActualGanttContract;
    return window.APSReadBoundary.verified({
      async load(context, signal) {
        const scope = C.scope(context);
        return C.workspace(await base.query('actual-gantt', C.transport(scope), signal), scope);
      },
      async related(context, target, original, signal) {
        const scope = C.scope(context);
        return C.related(await base.query('actual-gantt/chain', {
          ...C.transport(scope),
          target_task_ref: target
        }, signal), scope, original, target);
      },
      async export(context, signal) {
        const scope = C.scope(context, true),
          output = await base.download('actual-gantt/export', C.transport(scope), signal);
        if (!output || !output.blob || !output.blob.size || output.contentType.split(';')[0] !== 'text/csv' || !/^attachment;/i.test(output.disposition)) throw window.APSResourceContract.failure('下载的现场实际甘特不是有效的 CSV 附件。');
        return output;
      }
    }, ['load', 'related']);
  }
  function adapter(value) {
    const C = window.ActualGanttContract;
    return window.APSReadBoundary.checked(value, {
      load: (result, context) => C.workspace(result, C.scope(context)),
      related: (chain, context, target, original) => C.relatedChain(chain, C.scope(context), original, target)
    });
  }
  window.ActualGanttAPI = {
    create,
    adapter
  };
})();
