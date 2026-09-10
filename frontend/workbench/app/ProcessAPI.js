(function () {
  'use strict';
  function create(resourceAdapter) {
    const base = window.APSResourceAPI.create('process'), fail = window.APSResourceContract.failure;
    const resources = resourceAdapter || window.APSResourceAPI.create();
    function part(kind, ref) {
      if (kind !== 'part' || ref != null && (typeof ref !== 'string' || !/^[0-9a-f]{48}$/.test(ref)))
        throw fail('工艺对象引用不正确，请返回列表重新选择。');
      return 'entities/part' + (ref == null ? '' : '/' + ref);
    }
    function tableRequest(scope) {
      const value = { ...scope };
      ['sort', 'column_filters'].forEach(key => { if (Array.isArray(value[key]) || window.APSResourceContract.object(value[key])) value[key] = JSON.stringify(value[key]); });
      return value;
    }
    function facetPath(kind, request, selection) {
      part(kind);
      if (!window.APSProcessContract.columns.some(column => column.key === request.column)) throw fail('此工艺列不支持筛选。');
      return 'process-table/' + (selection ? 'facet-selection/' : 'facets/') + request.column;
    }
    function filePath(kind, action) {
      if (!['route', 'hours'].includes(kind)) throw fail('文件类型必须是工艺路线或工时定额。');
      return 'process-files/' + kind + '/' + action;
    }
    return {
      resourceAdapter: resources,
      choices: resources.choices,
      lookup: base.lookup,
      readPending: base.readPending,
      savePending: base.savePending,
      clearPending: base.clearPending,
      list(kind, scope, signal) { return base.query(part(kind), tableRequest(scope), signal); },
      facets(kind, request, signal) {
        const { column, scope, ...query } = request;
        return base.query(facetPath(kind, request, false), { ...query, scope: JSON.stringify(scope) }, signal);
      },
      facetSelection(kind, request, signal) {
        const { column, scope, ...query } = request;
        return base.query(facetPath(kind, request, true), { ...query, scope: JSON.stringify(scope) }, signal);
      },
      bulkPreview(body, signal) { return base.preview('process/parts/bulk-preview', body, signal); },
      filePreview(kind, mode, body, signal) {
        if (!['import', 'export'].includes(mode)) throw fail('工艺文件操作不正确。');
        return base.preview(filePath(kind, mode === 'import' ? 'preview' : 'export-preview'), body, signal);
      },
      fileDownload(kind, template, scope, signal) {
        if (typeof template !== 'boolean') throw fail('工艺文件下载操作不正确。');
        return base.download(filePath(kind, template ? 'template' : 'export'), scope, signal);
      },
      detail(kind, ref, signal) {
        if (ref == null) throw fail('工艺详情缺少对象引用。');
        return base.query(part(kind, ref), {}, signal);
      },
      routePreview(ref, body, signal) {
        if (ref == null) throw fail('工艺预检缺少对象引用。');
        part('part', ref);
        return base.preview('process/' + ref + '/route-preview', body, signal);
      },
      stagePreview(ref, action, input, snapshotRef, signal) {
        part('part', ref);
        if (ref == null || action !== 'source_confirm' || typeof snapshotRef !== 'string' || !snapshotRef)
          throw fail('归属检查缺少当前零件资料，请重新读取。');
        return base.preview('process/' + ref + '/stage-preview', { action, input, snapshot_ref: snapshotRef }, signal);
      },
      command(kind, action, ref, body, signal) {
        if (kind === 'process' && action === 'create' && ref === null) return base.execute('process/parts/create', body, signal);
        if (kind === 'process_bulk' && action === 'confirm' && typeof ref === 'string' && /^[A-Za-z0-9_-]{32}$/.test(ref)
            && body.input && body.input.preview_ref === ref) return base.execute('process/parts/bulk-confirm', body, signal);
        if (['process_route_import', 'process_hours_import'].includes(kind) && action === 'confirm' && typeof ref === 'string' && /^[A-Za-z0-9_-]{32}$/.test(ref)
            && body.input && body.input.preview_ref === ref) return base.execute(filePath(kind === 'process_route_import' ? 'route' : 'hours', 'confirm'), body, signal);
        part('part', ref);
        if (kind !== 'process' || ref == null || !['route_confirm', 'source_confirm', 'hours_confirm'].includes(action))
          throw fail('工艺操作与所选零件不一致。');
        return base.execute('process/' + ref + '/' + action, body, signal);
      }
    };
  }
  window.APSProcessAPI = { create };
})();
