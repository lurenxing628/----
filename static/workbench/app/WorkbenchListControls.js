(function () {
  'use strict';

  const {
    Button,
    ErrorBox
  } = window.ResourceControls;
  const titles = {
    empty: '暂无记录',
    filtered: '当前筛选没有匹配项',
    loading: '正在读取…',
    error: '读取未完成'
  };
  function EmptyState({
    kind = 'empty',
    title,
    hint,
    action,
    error
  }) {
    if (!Object.prototype.hasOwnProperty.call(titles, kind)) throw new TypeError('Unknown empty state kind');
    if ((kind === 'filtered' || kind === 'error') && !action) throw new TypeError(kind + ' state requires a recovery action');
    return /*#__PURE__*/React.createElement("div", {
      className: 'wb-empty wb-empty-' + kind,
      role: kind === 'error' ? undefined : 'status',
      "aria-busy": kind === 'loading' || undefined
    }, /*#__PURE__*/React.createElement("p", {
      className: "wb-empty-title"
    }, title || titles[kind]), hint && /*#__PURE__*/React.createElement("p", {
      className: "wb-empty-hint"
    }, hint), kind === 'error' && error && /*#__PURE__*/React.createElement(ErrorBox, {
      error: error
    }), action && /*#__PURE__*/React.createElement("div", {
      className: "wb-empty-action"
    }, action));
  }
  function Pager({
    page = 1,
    pages,
    total,
    size,
    sizes,
    unit = '项',
    onPage,
    onSize,
    disabled,
    busy,
    label = '记录',
    sizeLabel,
    mode = 'pages',
    hasPrevious,
    hasNext,
    onPrevious,
    onNext,
    showPageSelect = false,
    showPageJump = false,
    jumpLabel = '跳转页码',
    jumpActionLabel = '跳转'
  }) {
    const data = page && typeof page === 'object' ? page : {
      number: page,
      pages,
      total,
      size
    };
    const number = data.number || 1,
      count = data.total == null ? total : data.total,
      perPage = data.size || size;
    const pageCount = data.pages || pages || (Number.isFinite(count) && perPage ? Math.max(1, Math.ceil(count / perPage)) : undefined);
    const [jump, setJump] = React.useState(String(number)),
      [jumpError, setJumpError] = React.useState(false);
    const jumpErrorId = React.useId();
    React.useEffect(() => {
      setJump(String(number));
      setJumpError(false);
    }, [number]);
    if (!['pages', 'cursor'].includes(mode)) throw new TypeError('Unknown pager mode');
    if (onSize && (!Array.isArray(sizes) || !sizes.length || !sizes.every(value => Number.isSafeInteger(value) && value > 0))) {
      throw new TypeError('Pager sizes must explicitly match the domain API');
    }
    const locked = disabled || busy;
    const previous = mode === 'cursor' ? !!hasPrevious : number > 1;
    const next = mode === 'cursor' ? !!hasNext : pageCount != null ? number < pageCount : !!hasNext;
    const previousAction = onPrevious || onPage && (() => onPage(number - 1));
    const nextAction = onNext || onPage && (() => onPage(number + 1));
    function goToPage() {
      const target = Number(jump);
      if (!/^\d+$/.test(jump) || !Number.isSafeInteger(target) || target < 1 || target > pageCount) {
        setJumpError(true);
        return;
      }
      setJumpError(false);
      onPage(target);
    }
    return /*#__PURE__*/React.createElement("nav", {
      className: "wb-pager",
      "aria-label": label + '分页',
      "aria-busy": busy || undefined
    }, /*#__PURE__*/React.createElement("span", {
      className: "wb-pager-summary"
    }, mode === 'cursor' ? '按读取顺序翻页' : /*#__PURE__*/React.createElement(React.Fragment, null, count != null && /*#__PURE__*/React.createElement(React.Fragment, null, "\u5171 ", count, " ", unit, " \xB7 "), "\u7B2C ", number, pageCount != null && /*#__PURE__*/React.createElement(React.Fragment, null, " / ", pageCount), " \u9875")), /*#__PURE__*/React.createElement("div", {
      className: "wb-pager-actions"
    }, mode === 'pages' && showPageSelect && pageCount && onPage && /*#__PURE__*/React.createElement("label", {
      className: "wb-pager-size"
    }, "\u9875\u7801", /*#__PURE__*/React.createElement("select", {
      "aria-label": label + '页码',
      value: number,
      disabled: locked,
      onChange: event => onPage(Number(event.target.value))
    }, Array.from({
      length: pageCount
    }, (_, index) => index + 1).map(value => /*#__PURE__*/React.createElement("option", {
      key: value,
      value: value
    }, value)))), mode === 'pages' && showPageJump && pageCount && onPage && /*#__PURE__*/React.createElement("div", {
      className: "wb-pager-jump"
    }, /*#__PURE__*/React.createElement("input", {
      type: "number",
      "aria-label": jumpLabel,
      "aria-invalid": jumpError || undefined,
      "aria-describedby": jumpError ? jumpErrorId : undefined,
      min: 1,
      max: pageCount,
      step: 1,
      value: jump,
      disabled: locked,
      onChange: event => {
        setJump(event.target.value);
        setJumpError(false);
      },
      onKeyDown: event => {
        if (event.key === 'Enter') {
          event.preventDefault();
          goToPage();
        }
      }
    }), /*#__PURE__*/React.createElement(Button, {
      "aria-label": jumpActionLabel,
      disabled: locked,
      onClick: goToPage
    }, "\u8DF3\u8F6C"), jumpError && /*#__PURE__*/React.createElement("span", {
      id: jumpErrorId,
      role: "status",
      className: "wb-field-error"
    }, "\u8BF7\u8F93\u5165 1 \u5230 ", pageCount, " \u4E4B\u95F4\u7684\u9875\u7801\u3002")), onSize && /*#__PURE__*/React.createElement("label", {
      className: "wb-pager-size"
    }, "\u6BCF\u9875", /*#__PURE__*/React.createElement("select", {
      "aria-label": sizeLabel || label + '每页条数',
      value: perPage,
      disabled: locked,
      onChange: event => onSize(Number(event.target.value))
    }, !sizes.includes(perPage) && /*#__PURE__*/React.createElement("option", {
      value: perPage,
      disabled: true
    }, perPage, " ", unit, "\uFF08\u5F53\u524D\uFF09"), sizes.map(value => /*#__PURE__*/React.createElement("option", {
      key: value,
      value: value
    }, value, " ", unit)))), /*#__PURE__*/React.createElement(Button, {
      icon: "chevron-left",
      "aria-label": label + '上一页',
      disabled: locked || !previous || !previousAction,
      onClick: previousAction
    }, "\u4E0A\u4E00\u9875"), /*#__PURE__*/React.createElement(Button, {
      icon: "chevron-right",
      "aria-label": label + '下一页',
      disabled: locked || !next || !nextAction,
      onClick: nextAction
    }, "\u4E0B\u4E00\u9875")));
  }
  window.WorkbenchListControls = {
    EmptyState,
    Pager
  };
  Object.assign(window.WorkbenchControls, window.WorkbenchListControls);
})();
