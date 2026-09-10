(function () {
  'use strict';
  // Geometry applies to command controls only; navigation, charts and calendar cells keep their layout.
  const command = 'body.aps-workbench :is(button.wb-control,button.wb-action,button.btn,button.mini,button.pg,button.cal-nav,button.hdr-pill,button.sm-button,button.modal-x,button.hb-r-next,button.ph-help,button.gb-tb-btn,button.fg-icon-button,button.fg-return,button.aw-reset,button.aw-more,button.wb-picker-nav,button.wb-picker-trigger,input[type="button"],input[type="submit"],input[type="reset"])';
  const text = 'body.aps-workbench :is(input:not([type]),input[type="text"],input[type="search"],input[type="number"],input[type="email"],input[type="url"],input[type="tel"],input[type="password"],input[type="date"],input[type="datetime-local"],input[type="time"],input[type="month"],input[type="week"],select,textarea)';
  const binary = 'body.aps-workbench input:is([type="checkbox"],[type="radio"])';
  const primary = 'body.aps-workbench :is(button.wb-primary,button.btn.primary,button.sm-primary-button,button.hb-r-next)';
  const compact = ':is(.toolbar,.pager,.sm-filters,.sm-pager,.sm-session-settings,.rm-preview-toolbar,.rm-pagination,.rc-pattern-table,.wb-control-popup)';
  function iconURL(name, color) {
    const nodes = window.APSFieldReports.iconNodes[name];
    if (!nodes) throw new Error('Workbench control icon missing: ' + name);
    const ns = 'http://www.w3.org/2000/svg', svg = document.createElementNS(ns, 'svg');
    Object.entries({ viewBox: '0 0 24 24', fill: 'none', stroke: color, 'stroke-width': '1.75', 'stroke-linecap': 'round', 'stroke-linejoin': 'round' })
      .forEach(([key, value]) => svg.setAttribute(key, value));
    nodes.forEach(([tag, attributes]) => {
      const node = document.createElementNS(ns, tag);
      Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, value));
      svg.appendChild(node);
    });
    return 'url("data:image/svg+xml,' + encodeURIComponent(new XMLSerializer().serializeToString(svg)) + '")';
  }
  function themedIcons() {
    const color = getComputedStyle(document.documentElement).getPropertyValue('--ui-info-muted').trim();
    if (!color || !CSS.supports('color', color)) throw new Error('Workbench control theme color is unavailable.');
    return 'body.aps-workbench {' + Object.entries({ select: 'chevron-down', date: 'calendar-days', time: 'clock-3', disclosure: 'chevron-right' })
      .map(([kind, name]) => '--wb-control-' + kind + '-icon:' + iconURL(name, color) + ';').join('') + '}';
  }
  function WorkbenchControlStyles() {
    const [icons, setIcons] = React.useState(themedIcons);
    React.useLayoutEffect(() => {
      const update = () => setIcons(themedIcons());
      const observer = new MutationObserver(update);
      observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
      update();
      return () => observer.disconnect();
    }, []);
    return <style data-workbench-control-styles>{icons + `
      /* Secondary copy on the light canvas; dark retains its own lighter ink. */
      html:not([data-theme="dark"]) body.aps-workbench { --ui-muted: #607087; }
      body.aps-workbench {
        --wb-control-height: 32px;
        --wb-control-edit-height: 36px;
        --wb-control-radius: 4px;
        --wb-control-focus: var(--ui-primary);
        --wb-control-edge-hover: var(--ui-info-muted);
      }
      body.aps-workbench :is(button,input,select,textarea,summary) {
        box-sizing: border-box;
        -webkit-appearance: none;
        appearance: none;
        font-family: var(--font-family);
        letter-spacing: 0;
        text-shadow: none;
      }
      body.aps-workbench button { cursor: pointer; color: var(--ui-text); }
      body.aps-workbench :is(button,input,select,textarea):disabled,
      body.aps-workbench :is(button,[role="button"])[aria-disabled="true"] { cursor: default; }
      body.aps-workbench :is(button,input,select,textarea,summary,[role="button"],[role="tab"],a[href]):focus-visible {
        outline: 2px solid var(--wb-control-focus) !important;
        outline-offset: 2px;
        box-shadow: none !important;
      }
      body.aps-workbench :is(.sm-work-row,.hb-tile,.hb-cal-block,.cal-cell,.tr-bar,.gb-bar,.fg-bar,[role="tab"]):focus-visible {
        outline-offset: -2px;
      }
      ${command} {
        display: inline-flex !important;
        align-items: center;
        justify-content: center;
        gap: 6px;
        min-height: var(--wb-control-height) !important;
        height: auto !important;
        max-width: 100%;
        padding: 5px 10px !important;
        border: 1px solid var(--ui-border) !important;
        border-radius: var(--wb-control-radius) !important;
        color: var(--ui-text) !important;
        background: var(--ui-card-bg) !important;
        font: 500 13px/20px var(--font-family) !important;
        white-space: normal !important;
        overflow-wrap: anywhere;
        text-overflow: clip;
        box-shadow: none !important;
        transform: none !important;
        filter: none;
        transition: background-color .12s, border-color .12s, color .12s;
      }
      ${command}:hover:not(:disabled):not([aria-disabled="true"]) {
        border-color: var(--wb-control-edge-hover) !important;
        background: var(--ui-surface-muted) !important;
      }
      ${command}:active:not(:disabled):not([aria-disabled="true"]) {
        background: var(--ui-info-bg) !important;
        border-color: var(--ui-primary) !important;
      }
      ${command} svg { flex: none; }
      body.aps-workbench :is(button.pg,button.sm-icon-button,button.modal-x,button.cal-nav:not(.cal-today-btn),button.wb-picker-nav,button.wb-picker-trigger) {
        width: var(--wb-control-height);
        min-width: var(--wb-control-height);
        padding: 5px !important;
        flex: none;
      }
      body.aps-workbench button.mini { min-height: 30px !important; padding: 4px 9px !important; }
      body.aps-workbench .resource-catalog .rc-list button.mini { width: 30px; min-width: 30px; padding: 4px !important; }
      body.aps-workbench button.modal-x { background: transparent !important; border-color: transparent !important; color: var(--ui-info-muted) !important; }
      ${primary} {
        background: var(--ui-info-text) !important;
        border-color: var(--ui-info-text) !important;
        color: var(--ui-card-bg) !important;
      }
      ${primary}:hover:not(:disabled):not([aria-disabled="true"]) {
        background: var(--ui-info-text) !important;
        border-color: var(--ui-info-text) !important;
        filter: brightness(.94);
        box-shadow: none !important;
      }
      ${primary}:active:not(:disabled):not([aria-disabled="true"]) {
        background: var(--ui-info-text) !important;
        border-color: var(--ui-info-text) !important;
        color: var(--ui-card-bg) !important;
        filter: brightness(.88);
      }
      body.aps-workbench :is(button.btn.danger,button.mini.danger) { color: var(--ui-danger-text) !important; }
      body.aps-workbench :is(button.btn.danger,button.mini.danger):hover:not(:disabled) {
        color: var(--ui-danger-text) !important;
        border-color: var(--ui-danger-border) !important;
        background: var(--ui-danger-bg) !important;
      }
      body.aps-workbench :is(button.btn.danger,button.mini.danger):active:not(:disabled) { border-color: var(--ui-danger-text) !important; }
      ${command}:is(:disabled,[aria-disabled="true"]) {
        background: var(--ui-surface-muted) !important;
        color: var(--ui-info-muted) !important;
        border-color: var(--ui-border) !important;
        opacity: 1 !important;
        filter: none;
      }
      body.aps-workbench :is(.lnk,.linkbtn,.aps-fp-clear):is(button),
      body.aps-workbench th > button:not([class]) {
        border: 0; background: transparent; color: var(--ui-info-text);
        font: inherit; line-height: inherit; letter-spacing: 0; text-align: left;
      }
      body.aps-workbench :is(button.lnk,button.linkbtn):hover:not(:disabled) { text-decoration: underline; text-underline-offset: 3px; }
      body.aps-workbench :is(button.lnk,button.linkbtn,th > button):disabled { color: var(--ui-info-muted) !important; text-decoration: none; }
      ${text} {
        --wb-field-height: var(--wb-control-height);
        height: var(--wb-field-height);
        min-height: var(--wb-field-height);
        min-width: 0;
        max-width: 100%;
        border: 1px solid var(--ui-border);
        border-radius: var(--wb-control-radius) !important;
        color: var(--ui-text);
        background-color: var(--ui-card-bg);
        padding: 5px 10px;
        font: 400 13px/20px var(--font-family);
        box-shadow: none !important;
        transition: background-color .12s, border-color .12s;
      }
      body.aps-workbench :is(.field,.sm-config-form) :is(input,select,textarea) { --wb-field-height: var(--wb-control-edit-height); }
      body.aps-workbench ${compact} :is(input,select,textarea) { --wb-field-height: var(--wb-control-height); height: var(--wb-field-height); min-height: var(--wb-field-height); }
      body.aps-workbench :is(.modal-f,.sm-form-footer) :is(button.btn,button.wb-action,button.sm-button) { min-height: var(--wb-control-edit-height) !important; padding-top: 7px !important; padding-bottom: 7px !important; }
      body.aps-workbench .search input { padding-left: 34px; }
      body.aps-workbench .rc-toolbar .search input { padding-left: 10px; }
      ${text}:hover:not(:disabled):not([readonly]) { border-color: var(--wb-control-edge-hover); }
      ${text}:focus-visible { border-color: var(--wb-control-focus) !important; outline-width: 1px !important; outline-offset: 0; transition-property: background-color; }
      ${text}:is(:disabled,[readonly]) { background-color: var(--ui-surface-muted); color: var(--ui-info-muted); opacity: 1; }
      ${text}[readonly] { cursor: text; }
      ${text}::placeholder { color: var(--ui-muted); opacity: 1; }
      ${text}[aria-invalid="true"],
      body.aps-workbench .field.err :is(input,select,textarea) { border-color: var(--ui-danger) !important; }
      ${text}[aria-invalid="true"]:focus-visible,
      body.aps-workbench .field.err :is(input,select,textarea):focus-visible { outline-color: var(--ui-danger) !important; }
      ${text}:is(textarea) { height: auto; min-height: 76px; padding: 8px 10px; resize: vertical; line-height: 20px; }
      body.aps-workbench select {
        padding-right: 32px !important;
        background-image: var(--wb-control-select-icon, none) !important;
        background-position: right 8px center !important;
        background-size: 16px 16px !important;
        background-repeat: no-repeat !important;
        cursor: pointer;
      }
      body.aps-workbench select[multiple] { height: auto; min-height: 96px; padding-right: 10px !important; background-image: none !important; }
      body.aps-workbench select option,body.aps-workbench select optgroup { background: var(--ui-card-bg); color: var(--ui-text); }
      body.aps-workbench select option:disabled { color: var(--ui-info-muted); }
      body.aps-workbench input[type="number"] { font-variant-numeric: tabular-nums; }
      body.aps-workbench input::-webkit-inner-spin-button,
      body.aps-workbench input::-webkit-outer-spin-button { -webkit-appearance: none; margin: 0; display: none; }
      body.aps-workbench .wb-number-parent { position: relative; }
      body.aps-workbench input.wb-number-input { padding-right: 34px !important; }
      body.aps-workbench .wb-number-stepper {
        position: absolute; top: 1px; right: 1px; bottom: 1px;
        display: flex; flex-direction: column; width: 24px;
        box-sizing: border-box; border-left: 1px solid var(--ui-border);
        border-radius: 0 3px 3px 0; overflow: hidden;
        color: var(--ui-info-muted); background: var(--ui-card-bg);
      }
      body.aps-workbench button.wb-number-step {
        display: flex; align-items: center; justify-content: center; flex: 1 1 0;
        width: 100%; min-width: 0; min-height: 0; height: auto;
        margin: 0; padding: 0; border: 0; border-radius: 0;
        background: transparent; color: inherit; box-shadow: none;
        font: 12px/1 var(--font-family); cursor: pointer;
      }
      body.aps-workbench .wb-number-step + .wb-number-step { border-top: 1px solid var(--ui-border); }
      body.aps-workbench .wb-number-step svg { width: 12px; height: 12px; flex: none; }
      body.aps-workbench .wb-number-step:hover:not(:disabled) { background: var(--ui-info-bg); color: var(--ui-info-text); }
      body.aps-workbench .wb-number-step:active:not(:disabled) { background: var(--ui-surface-muted); color: var(--ui-info-text); }
      body.aps-workbench .wb-number-step:focus-visible { outline-width: 1px !important; outline-offset: -1px; }
      body.aps-workbench .wb-number-step:disabled { background: var(--ui-surface-muted); color: var(--ui-info-muted); cursor: default; }
      body.aps-workbench input:is([type="date"],[type="datetime-local"],[type="time"],[type="month"],[type="week"]) {
        position: relative;
        padding-right: 32px !important;
        background-image: var(--wb-control-date-icon) !important;
        background-position: right 8px center !important;
        background-size: 16px 16px !important;
        background-repeat: no-repeat !important;
      }
      body.aps-workbench input[type="time"] { background-image: var(--wb-control-time-icon) !important; }
      body.aps-workbench input::-webkit-calendar-picker-indicator {
        display: block; position: absolute; right: 0; top: 0;
        width: 32px; height: 100%; margin: 0; padding: 0; opacity: 0; cursor: pointer;
      }
      body.aps-workbench input:is(:disabled,[readonly])::-webkit-calendar-picker-indicator { pointer-events: none; cursor: default; }
      body.aps-workbench input::-webkit-date-and-time-value { text-align: left; }
      body.aps-workbench input::-webkit-datetime-edit { padding: 0; }
      body.aps-workbench input::-webkit-datetime-edit-year-field:focus,
      body.aps-workbench input::-webkit-datetime-edit-month-field:focus,
      body.aps-workbench input::-webkit-datetime-edit-day-field:focus,
      body.aps-workbench input::-webkit-datetime-edit-hour-field:focus,
      body.aps-workbench input::-webkit-datetime-edit-minute-field:focus,
      body.aps-workbench input::-webkit-datetime-edit-second-field:focus,
      body.aps-workbench input::-webkit-datetime-edit-millisecond-field:focus,
      body.aps-workbench input::-webkit-datetime-edit-ampm-field:focus { color: var(--ui-info-text); background: var(--ui-info-bg); border-radius: 2px; outline: none; }
      body.aps-workbench input::-webkit-search-decoration,
      body.aps-workbench input::-webkit-search-cancel-button { -webkit-appearance: none; display: none; }
      ${binary} {
        display: inline-grid;
        place-content: center;
        flex: none;
        width: 16px !important;
        height: 16px !important;
        min-width: 16px !important;
        min-height: 16px !important;
        max-width: 16px;
        padding: 0 !important;
        margin: 0;
        border: 1px solid var(--ui-info-muted) !important;
        border-radius: 3px !important;
        background: var(--ui-card-bg);
        color: var(--ui-card-bg);
        vertical-align: middle;
        cursor: pointer;
        box-shadow: none;
      }
      ${binary}:hover:not(:disabled) { border-color: var(--ui-primary) !important; }
      ${binary}:checked,${binary}:indeterminate { border-color: var(--ui-info-text) !important; background: var(--ui-info-text); }
      ${binary}::before { content: ''; display: block; box-sizing: border-box; visibility: hidden; }
      body.aps-workbench input[type="checkbox"]:checked::before {
        visibility: visible; width: 9px; height: 5px;
        border-left: 2px solid currentColor; border-bottom: 2px solid currentColor;
        transform: translateY(-1px) rotate(-45deg);
      }
      body.aps-workbench input[type="checkbox"]:indeterminate::before {
        visibility: visible; width: 8px; height: 2px; background: currentColor;
        border: 0; transform: none;
      }
      body.aps-workbench input[type="radio"] { border-radius: 50% !important; }
      body.aps-workbench input[type="radio"]:checked { background: var(--ui-card-bg); color: var(--ui-info-text); }
      body.aps-workbench input[type="radio"]:checked::before { visibility: visible; width: 8px; height: 8px; border-radius: 50%; background: currentColor; }
      ${binary}:disabled { background: var(--ui-surface-muted); border-color: var(--ui-border) !important; color: var(--ui-info-muted); opacity: 1; }
      body.aps-workbench input[type="range"] {
        display: inline-block; min-width: 80px; max-width: 100%; height: 32px;
        margin: 0; padding: 0; border: 0; background: transparent; vertical-align: middle;
        cursor: pointer; accent-color: var(--ui-info-text);
      }
      body.aps-workbench input[type="range"]::-webkit-slider-runnable-track { height: 4px; border: 1px solid var(--ui-border); border-radius: 2px; background: var(--ui-info-bg); }
      body.aps-workbench input[type="range"]::-webkit-slider-thumb {
        -webkit-appearance: none; appearance: none; width: 16px; height: 16px; margin-top: -7px;
        border: 2px solid var(--ui-info-text); border-radius: 50%; background: var(--ui-card-bg); box-shadow: none;
      }
      body.aps-workbench input[type="range"]:active:not(:disabled)::-webkit-slider-thumb { background: var(--ui-info-text); }
      body.aps-workbench input[type="range"]:disabled::-webkit-slider-runnable-track { background: var(--ui-surface-muted); }
      body.aps-workbench input[type="range"]:disabled::-webkit-slider-thumb { border-color: var(--ui-info-muted); background: var(--ui-surface-muted); }
      body.aps-workbench input[type="file"] { max-width: 100%; color: var(--ui-text); font: 13px/20px var(--font-family); }
      body.aps-workbench input[type="file"]::file-selector-button {
        -webkit-appearance: none; appearance: none; min-height: 32px; margin: 0 10px 0 0; padding: 5px 10px;
        border: 1px solid var(--ui-border); border-radius: var(--wb-control-radius);
        background: var(--ui-card-bg); color: var(--ui-text); font: inherit; cursor: pointer;
      }
      body.aps-workbench input[type="file"]:hover:not(:disabled)::file-selector-button { background: var(--ui-surface-muted); border-color: var(--wb-control-edge-hover); }
      body.aps-workbench input[type="file"]:disabled::file-selector-button { background: var(--ui-surface-muted); color: var(--ui-info-muted); cursor: default; }
      body.aps-workbench summary { display: flex; align-items: center; gap: 8px; width: fit-content; max-width: 100%; min-height: 28px; list-style: none; color: var(--ui-info-text); cursor: pointer; overflow-wrap: anywhere; }
      body.aps-workbench summary::-webkit-details-marker { display: none; }
      body.aps-workbench summary::marker { content: ''; }
      body.aps-workbench summary::before {
        content: ''; flex: none; width: 14px; height: 14px; background-color: currentColor;
        -webkit-mask: var(--wb-control-disclosure-icon) center / 14px 14px no-repeat;
        mask: var(--wb-control-disclosure-icon) center / 14px 14px no-repeat;
      }
      body.aps-workbench details[open] > summary::before { transform: rotate(90deg); }
      body.aps-workbench summary:hover { color: var(--ui-text); }
      body.aps-workbench .seg > button {
        min-height: 36px; height: auto; padding: 7px 10px; border-radius: var(--wb-control-radius);
        font: 500 13px/20px var(--font-family); white-space: normal; overflow-wrap: anywhere; box-shadow: none;
      }
      body.aps-workbench .seg > button:is(.on,[aria-pressed="true"]) { color: var(--ui-info-text); background: var(--ui-info-bg); border-color: var(--ui-primary); }
      body.aps-workbench .seg > button:disabled { color: var(--ui-info-muted); background: var(--ui-surface-muted); border-color: var(--ui-border); cursor: default; }
      body.aps-workbench .seg.re-mode button:not(.on) { color: var(--ui-info-muted); }
      body.aps-workbench .seg.re-mode button.on,
      body.aps-workbench .seg.re-mode button.on:hover { color: var(--ui-card-bg); background: var(--ui-info-text); border-color: var(--ui-info-text); }
      body.aps-workbench .seg.re-mode button:disabled,
      body.aps-workbench .seg.re-mode button:disabled:hover { color: var(--ui-info-muted); background: var(--ui-surface-muted); border-color: var(--ui-border); }
      body.aps-workbench .seg.re-mode button.on:disabled,
      body.aps-workbench .seg.re-mode button.on:disabled:hover { color: var(--ui-info-text); background: var(--ui-info-bg); border-color: var(--ui-border); }
      /* Accent tokens identify categories; semantic text tokens supply readable selected fills. */
      body.aps-workbench .segm button:not(.on),
      body.aps-workbench .subtab:not(.on),body.aps-workbench .subtab:not(.on) .cnt { color: var(--ui-info-muted); }
      body.aps-workbench .segm button:not(.on):hover:not(:disabled) { color: var(--ui-text); }
      body.aps-workbench .segm button.on.int { background: var(--ui-info-text); color: var(--ui-card-bg); }
      body.aps-workbench .segm button.on.ext { background: var(--ui-warning-text); color: var(--ui-card-bg); }
      body.aps-workbench .segm button:disabled { background: var(--ui-surface-muted); color: var(--ui-info-muted); opacity: 1; }
      body.aps-workbench .segm button.on.int:disabled { background: var(--ui-info-bg); color: var(--ui-info-text); }
      body.aps-workbench .segm button.on.ext:disabled { background: var(--ui-warning-bg); color: var(--ui-warning-text); }
      body.aps-workbench .stp.active .stp-n { background: var(--ui-info-text); border-color: var(--ui-info-text); color: var(--ui-card-bg); }
      body.aps-workbench .stp.active .stp-s { color: var(--ui-info-muted); }
      body.aps-workbench .subtab.on .cnt { color: var(--ui-info-text); }
      body.aps-workbench .wb-control-popup {
        position: fixed; z-index: 12000; display: flex; flex-direction: column;
        box-sizing: border-box; min-width: 160px; max-width: calc(100vw - 16px); max-height: calc(100vh - 16px);
        padding: 4px; border: 1px solid var(--ui-border); border-radius: var(--wb-control-radius);
        color: var(--ui-text); background: var(--ui-card-bg); font: 13px/20px var(--font-family); letter-spacing: 0;
        box-shadow: 0 2px 6px rgba(0,0,0,.14); overflow: auto; overscroll-behavior: contain;
      }
      body.aps-workbench .wb-popup-option {
        display: flex; align-items: center; gap: 8px; flex: none; width: 100%; min-height: 32px;
        margin: 0; padding: 6px 8px; border: 1px solid transparent; border-radius: var(--wb-control-radius);
        color: var(--ui-text); background: transparent; font: inherit; text-align: left;
        white-space: normal; overflow-wrap: anywhere; box-shadow: none; cursor: pointer;
      }
      body.aps-workbench .wb-popup-option:hover:not(:disabled):not([aria-disabled="true"]),
      body.aps-workbench .wb-popup-option[data-active="true"] { background: var(--ui-surface-muted); border-color: var(--ui-border); }
      body.aps-workbench .wb-popup-option[aria-selected="true"] { color: var(--ui-info-text); background: var(--ui-info-bg); font-weight: 600; }
      body.aps-workbench .wb-popup-option[aria-selected="true"][data-active="true"] { border-color: var(--ui-primary); }
      body.aps-workbench .wb-popup-option:is(:disabled,[aria-disabled="true"]) { color: var(--ui-info-muted); background: var(--ui-surface-muted); cursor: default; }
      body.aps-workbench .wb-popup-option svg { width: 16px; height: 16px; flex: none; }
      body.aps-workbench .wb-popup-option > span { min-width: 0; flex: 1 1 0; overflow-wrap: anywhere; }
      body.aps-workbench .wb-popup-option > svg:last-child { margin-left: auto; }
      body.aps-workbench .wb-popup-group { padding: 9px 8px 4px; color: var(--ui-info-muted); font-size: 12px; line-height: 18px; font-weight: 500; overflow-wrap: anywhere; }
      body.aps-workbench .wb-popup-group:first-child { padding-top: 5px; }
      body.aps-workbench .wb-popup-search { flex: none; width: 100%; margin-bottom: 4px; }
      body.aps-workbench .wb-popup-header { display: flex; align-items: center; gap: 8px; flex: none; padding: 6px 4px 10px; border-bottom: 1px solid var(--ui-border); margin-bottom: 4px; }
      body.aps-workbench .wb-popup-header > :is(h2,h3,strong) { flex: 1; min-width: 0; margin: 0; font-size: 13px; line-height: 20px; font-weight: 600; }
      body.aps-workbench .wb-popup-footer { display: flex; align-items: center; justify-content: flex-end; flex-wrap: wrap; gap: 8px; flex: none; padding: 8px 4px 4px; border-top: 1px solid var(--ui-border); margin-top: 4px; }
      body.aps-workbench .wb-date-picker .wb-popup-header { position: sticky; top: 0; z-index: 1; background: var(--ui-card-bg); }
      body.aps-workbench .wb-date-picker .wb-popup-footer { position: sticky; bottom: 0; z-index: 1; background: var(--ui-card-bg); }
      body.aps-workbench .wb-control-popup :is([role="status"],[role="alert"],.wb-popup-empty) { margin: 4px; color: var(--ui-info-muted); overflow-wrap: anywhere; white-space: normal; }
      body.aps-workbench .wb-control-popup [role="alert"] { color: var(--ui-danger-text); }
      body.aps-workbench .wb-picker-grid { display: grid; grid-template-columns: repeat(7,minmax(0,1fr)); grid-auto-rows: 32px; gap: 3px; min-width: 0; padding: 4px; }
      body.aps-workbench .wb-picker-weekday { display: flex; justify-content: center; align-items: center; min-height: 26px; color: var(--ui-info-muted); font-size: 12px; }
      body.aps-workbench .wb-picker-day {
        display: flex; justify-content: center; align-items: center; width: 100%; min-width: 0; min-height: 32px; height: 32px; max-height: 32px; aspect-ratio: auto;
        margin: 0; padding: 3px; border: 1px solid transparent; border-radius: var(--wb-control-radius);
        font: 13px/20px var(--font-family); font-variant-numeric: tabular-nums;
        color: var(--ui-text); background: transparent; box-shadow: none; cursor: pointer;
      }
      body.aps-workbench .wb-picker-day:hover:not(:disabled):not([aria-disabled="true"]) { background: var(--ui-surface-muted); border-color: var(--ui-border); }
      body.aps-workbench .wb-picker-day:is([data-active="true"],[aria-selected="true"]) { background: var(--ui-info-bg); border-color: var(--ui-primary); color: var(--ui-info-text); }
      body.aps-workbench .wb-picker-day[aria-current="date"] { font-weight: 700; text-decoration: underline; text-underline-offset: 4px; }
      body.aps-workbench .wb-picker-day:is([data-outside="true"],[data-other-month="true"],:disabled,[aria-disabled="true"]) { color: var(--ui-info-muted); }
      body.aps-workbench .wb-picker-day:is(:disabled,[aria-disabled="true"]) { background: var(--ui-surface-muted); cursor: default; }
      body.aps-workbench .wb-date-picker[data-picker-type="month"] .wb-picker-grid { grid-auto-rows: 40px; }
      body.aps-workbench .wb-date-picker[data-picker-type="month"] .wb-picker-day { min-height: 40px; height: 40px; max-height: 40px; }
      body.aps-workbench :is(.wb-picker-day,.wb-picker-nav,.wb-popup-option):focus-visible { outline-width: 1px !important; outline-offset: -1px; border-color: var(--wb-control-focus); }
      body.aps-workbench .wb-picker-actions { display: flex; justify-content: flex-end; align-items: center; flex-wrap: wrap; gap: 8px; padding: 8px 4px 4px; }
      body.aps-workbench .wb-picker-fields { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); align-items: end; gap: 8px; padding: 8px 4px; }
      body.aps-workbench .wb-picker-field { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
      body.aps-workbench .wb-picker-fields label { display: flex; flex-direction: column; gap: 4px; min-width: 0; color: var(--ui-info-muted); font-size: 12px; }
      body.aps-workbench .wb-picker-fields :is(input,select) { width: 100%; }
      body.aps-workbench .wb-picker-field .wb-picker-actions { flex-wrap: nowrap; justify-content: space-between; padding: 0; }
      body.aps-workbench .wb-picker-field button.wb-picker-nav { width: auto; min-width: 0; flex: 1 1 0; }
      @media (prefers-reduced-motion: reduce) {
        body.aps-workbench :is(button,input,select,textarea) { transition: none !important; }
      }
    `}</style>;
  }
  window.WorkbenchControlStyles = WorkbenchControlStyles;
})();
