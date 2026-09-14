(function () {
  'use strict';

  const C = window.APSResourceContract;
  const token = value => typeof value === 'string' && /^[A-Za-z0-9_-]{32}$/.test(value);
  const count = value => Number.isSafeInteger(value) && value >= 0;
  function create(kind = 'material', label = '物料') {
    const fields = {
      business_code: '物料编号',
      label: '名称',
      spec: '规格',
      unit: '单位',
      stock_qty: '库存数量',
      status: '状态',
      remark: '备注',
      created_at: '创建时间'
    };
    const results = {
      new: '新增',
      update: '更新',
      unchanged: '不变',
      delete: '删除',
      rejected: '拒绝'
    };
    const paths = {
      import: 'imports/' + kind + '/preview',
      bulk: 'entities/' + kind + '/bulk-preview',
      export: 'exports/' + kind + '/preview',
      download: 'exports/' + kind,
      template: 'templates/' + kind
    };
    function envelope(raw) {
      if (raw && raw.ok === false) throw raw;
      if (!C.object(raw) || raw.ok !== true || raw.schema_version !== 1 || !C.object(raw.data) || !C.object(raw.meta) || !['production', 'demo'].includes(raw.meta.source) || raw.meta.time_basis !== 'factory_local' || typeof raw.meta.snapshot_ref !== 'string' || !raw.meta.snapshot_ref || !Array.isArray(raw.warnings)) throw C.failure('读到的' + label + '数据不完整，请刷新重试。');
      return raw;
    }
    function preview(raw, mode, expected) {
      const result = envelope(raw),
        data = result.data;
      if (!token(data.preview_ref) || data.operation !== kind + (mode === 'import' ? '.import' : '.bulk_delete') || data.commit_policy !== 'atomic' || typeof data.can_confirm !== 'boolean' || !C.object(data.summary) || !Array.isArray(data.rows) || !C.object(data.write_context) || !C.object(data.write_context.capabilities) || !token(data.write_context.write_token) || !Number.isFinite(Date.parse(data.expires_at))) throw C.failure('预检结果不完整，本批没有提交。请重新预检。');
      if (!Object.keys(results).every(key => count(data.summary[key])) || Object.keys(results).reduce((sum, key) => sum + data.summary[key], 0) !== data.rows.length) throw C.failure('预检统计与明细不一致，本批没有提交。');
      const validRow = row => C.object(row) && count(row.row) && row.row > 0 && C.own(results, row.result) && (row.business_code === null || typeof row.business_code === 'string') && (row.before === null || C.object(row.before)) && (row.after === null || C.object(row.after)) && C.object(row.changes) && Array.isArray(row.errors) && row.errors.every(error => C.object(error) && typeof error.message === 'string') && typeof row.requires_confirmation === 'boolean' && count(row.reference_count);
      if (!data.rows.every(validRow) || new Set(data.rows.map(row => row.row)).size !== data.rows.length || !Object.keys(results).every(key => data.rows.filter(row => row.result === key).length === data.summary[key]) || data.can_confirm && data.summary.rejected !== 0) throw C.failure('预检行内容不完整或统计不一致，本批没有提交。');
      if (mode === 'import' && (data.format !== expected || data.mode !== 'upsert' || data.template_version !== 1 || typeof data.file_sha256 !== 'string' || !/^[0-9a-f]{64}$/.test(data.file_sha256))) throw C.failure('导入预检的文件格式或增量方式不一致，本批没有提交。');
      if (mode === 'bulk' && (!Array.isArray(expected) || data.rows.length !== expected.length || !data.rows.every((row, index) => row.entity_ref === expected[index]))) throw C.failure('删除预检与勾选的' + label + '不一致，本批没有提交。');
      return result;
    }
    function exportPreview(raw, selection) {
      const result = envelope(raw),
        data = result.data;
      if (!token(data.export_ref) || data.selection !== selection || !count(data.row_count) || !Array.isArray(data.formats) || !data.formats.every(value => ['csv', 'xlsx'].includes(value)) || !Number.isFinite(Date.parse(data.expires_at))) throw C.failure('导出预检内容不完整，没有开始下载。');
      return result;
    }
    function source(request) {
      return request.source || request.scope && request.scope.source;
    }
    function selection(request) {
      if (!Array.isArray(request.refs) || request.refs.some(ref => typeof ref !== 'string' || !/^[0-9a-f]{48}$/.test(ref)) || new Set(request.refs).size !== request.refs.length) throw C.failure('缺少明确勾选的' + label + '，不会按页面内容推算。');
      return request.refs.slice();
    }
    function listContext(request) {
      const input = request.scope || {},
        scope = {};
      ['query', 'status', 'sort', 'direction'].forEach(key => {
        if (C.own(input, key) && input[key] !== undefined && !(key === 'status' && (input[key] === '' || input[key] === null))) scope[key] = input[key];
      });
      if (C.own(input, 'column_filters')) {
        if (!C.object(input.column_filters)) throw C.failure('列筛选范围不完整，请刷新列表。');
        if (Object.keys(input.column_filters).length) scope.column_filters = JSON.parse(JSON.stringify(input.column_filters));
      }
      if (kind === 'op_type') {
        if (!['internal', 'external'].includes(input.category)) throw C.failure('缺少工种类别，请关闭向导，重新打开自制或外协工种。');
        scope.category = input.category;
      }
      const snapshot = request.snapshot_ref || input.snapshot_ref;
      const size = request.page && request.page.size || request.page_size || input.size;
      if (!token(snapshot) || !Number.isSafeInteger(size) || size < 1 || size > 200) throw C.failure('翻页位置已失效，请关闭向导后回到第 1 页重新查询。');
      return {
        scope,
        snapshot_ref: snapshot,
        page_size: size
      };
    }
    function requestBody(mode, request, selected) {
      const body = listContext(request);
      if (mode === 'bulk') return {
        ...body,
        action: 'delete',
        refs: selection(request)
      };
      return {
        ...body,
        selection: selected,
        ...(selected === 'selected' ? {
          refs: selection(request)
        } : {})
      };
    }
    function blocked(result, requestedSource) {
      if (!result) return '请先完成预检。';
      if (requestedSource !== 'production' || result.meta.source !== 'production') return '当前不是生产数据，不能提交。';
      const data = result.data,
        context = data.write_context;
      if (!data.can_confirm || data.summary.rejected) return '预检里有拒绝行，本批不能提交。错误行不会跳过。';
      if (context.capabilities[data.operation] !== true) {
        const reasons = context.blocked_reasons || [];
        const reason = reasons.find(item => item.action === data.operation);
        return reason && reason.message || '系统不允许本次确认。';
      }
      if (Date.now() >= Date.parse(data.expires_at)) return '预检结果已过期，请重新预检。';
      return '';
    }
    async function validateFile(file, format) {
      if (!file || !['csv', 'xlsx'].includes(format) || !file.name.toLowerCase().endsWith('.' + format)) throw C.failure('请选择与文件格式一致的 .csv 或 .xlsx 文件。');
      if (!file.size) throw C.failure('文件为空，请重新选择。');
      const bytes = new Uint8Array(await file.slice(0, 4).arrayBuffer());
      if (format === 'xlsx' && (bytes[0] !== 80 || bytes[1] !== 75 || bytes[2] !== 3 || bytes[3] !== 4)) throw C.failure('文件内容不是 XLSX 工作簿，请勿只修改扩展名。');
      if (format === 'csv' && (bytes.includes(0) || bytes[0] === 80 && bytes[1] === 75)) throw C.failure('文件内容不是 UTF-8 CSV，请核对文件格式。');
    }
    function filename(disposition, format) {
      if (typeof disposition !== 'string' || !/^attachment(?:;|$)/i.test(disposition)) throw C.failure('下载内容缺少文件名，没有保存文件。');
      const extended = /(?:^|;)\s*filename\*\s*=\s*UTF-8''([^;]+)/i.exec(disposition);
      const plain = /(?:^|;)\s*filename\s*=\s*(?:"((?:[^"\\]|\\.)*)"|([^;]+))/i.exec(disposition);
      let name;
      try {
        name = extended ? decodeURIComponent(extended[1].trim()) : plain && (plain[1] ? plain[1].replace(/\\(.)/g, '$1') : plain[2].trim());
      } catch (_) {
        throw C.failure('下载文件名编码无效，没有保存文件。');
      }
      if (!name || /[\x00-\x1f\x7f/\\]/.test(name) || !name.toLowerCase().endsWith('.' + format)) throw C.failure('下载文件名与所选格式不一致，没有保存文件。');
      return name;
    }
    async function saveDownload(download, format, signal) {
      const mime = format === 'csv' ? 'text/csv' : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
      if (!download || !(download.blob instanceof Blob) || download.blob.size === 0 || String(download.contentType).split(';')[0].trim().toLowerCase() !== mime) throw C.failure('下载内容或文件类型不正确，没有把错误内容保存成文件。');
      const name = filename(download.disposition, format);
      const bytes = new Uint8Array(await download.blob.slice(0, 4).arrayBuffer());
      if (format === 'xlsx' && (bytes[0] !== 80 || bytes[1] !== 75 || bytes[2] !== 3 || bytes[3] !== 4)) throw C.failure('下载内容不是 XLSX 工作簿，没有保存文件。');
      if (signal && signal.aborted) throw new DOMException('下载已取消', 'AbortError');
      const url = URL.createObjectURL(download.blob),
        link = document.createElement('a');
      try {
        link.href = url;
        link.download = name;
        document.body.appendChild(link);
        link.click();
      } finally {
        link.remove();
        window.setTimeout(() => URL.revokeObjectURL(url), 30000);
      }
      return name;
    }
    return {
      kind,
      label,
      fields,
      results,
      paths,
      preview,
      exportPreview,
      source,
      selection,
      listContext,
      requestBody,
      blocked,
      validateFile,
      filename,
      saveDownload
    };
  }
  window.APSResourceMaterial = {
    ...create(),
    create
  };
})();
