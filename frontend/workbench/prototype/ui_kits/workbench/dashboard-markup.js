window.APSDashboard.markup = `

  <div class="d-body">
    <div class="d-heading"><h1>计划员值班台</h1><span class="d-date">示例工作日 · 2026年9月7日 星期一</span></div>
    <div class="d-context">
      <span class="d-inline"><span class="d-dot d-good"></span><b id="d-plan-label"></b></span>
      <span>排产生成 <b id="d-plan-generated"></b></span><span>计划范围 <b id="d-plan-range"></b></span>
      <span>录入截至 <b id="d-input-time">11:40</b></span>
    </div>
    <p class="d-source-boundary">本页为独立值班样例，批次不与排产、现场报工样例关联；处理记录仅保存在当前会话。</p>
    <div id="d-input-changed" class="d-changed" hidden><i data-lucide="info" aria-hidden="true"></i><span>录入数据已更新；交期与候选结果仍是原测算快照。</span></div>
    <section class="d-overview wb-metrics" style="--wb-columns:5" aria-label="全局关注概览" id="d-metrics"></section>
    <div class="d-workbench">
      <aside class="d-queue" aria-label="问题清单">
        <div class="d-queue-head"><h3>需要关注</h3><span class="d-caption">6 类问题</span><select name="d-category" class="d-category-picker" aria-label="异常类别"></select></div>
        <div class="d-case-list" id="d-cases"></div><div class="d-queue-foot">按异常条目处置；同一批次的不同问题分别记录。</div>
      </aside>
      <section class="d-detail" aria-labelledby="d-detail-title">
        <div class="d-detail-head" id="d-detail-head"></div>
        <div class="d-tabs" role="tablist" aria-label="问题详情视图">
          <button class="d-tab" id="d-tab-items" data-tab="items" role="tab" aria-controls="d-content" aria-selected="true">处置清单</button>
          <button class="d-tab" id="d-tab-analysis" data-tab="analysis" role="tab" aria-controls="d-content" aria-selected="true">影响分析</button>
          <button class="d-tab" id="d-tab-compare" data-tab="compare" role="tab" aria-controls="d-content" aria-selected="false" tabindex="-1">方案对比</button>
          <button class="d-tab" id="d-tab-records" data-tab="records" role="tab" aria-controls="d-content" aria-selected="false" tabindex="-1">处置历史</button>
        </div>
        <div class="d-panel" id="d-content" role="tabpanel" aria-labelledby="d-tab-analysis" tabindex="0"></div>
      </section>
    </div>
    <footer class="d-footer"><span class="d-inline"><i data-lucide="database" aria-hidden="true"></i>基础资料 / 人工回填 / 排程测算</span><span id="d-status" aria-live="polite">示例会话 · 未连接生产数据库</span></footer>
  </div>
  <div class="d-modal-layer" id="d-modal-layer" hidden></div>
`;
