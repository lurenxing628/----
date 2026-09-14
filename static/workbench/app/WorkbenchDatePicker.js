(function () {
  'use strict';

  const M = window.WorkbenchDatePickerModel,
    C = window.APSCalendarContract;
  const {
    Icon
  } = window.ResourceControls;
  const weekdays = ['一', '二', '三', '四', '五', '六', '日'];
  function NavButton({
    name,
    icon,
    ...props
  }) {
    return /*#__PURE__*/React.createElement("button", {
      ...props,
      type: "button",
      className: "btn wb-picker-nav",
      title: name,
      "aria-label": name
    }, /*#__PURE__*/React.createElement(Icon, {
      name: icon
    }));
  }
  function NumberField({
    label,
    value,
    maximum,
    width = 2,
    onChange,
    initial
  }) {
    const id = React.useId();
    const invalid = value !== '' && Number(value) > maximum;
    function change(next) {
      if (new RegExp('^\\d{0,' + width + '}$').test(next)) onChange(next);
    }
    function increment(delta) {
      const next = value === '' ? delta > 0 ? 0 : maximum : Number(value) + delta;
      if (next >= 0 && next <= maximum) onChange(M.pad(next, width));
    }
    return /*#__PURE__*/React.createElement("div", {
      className: "wb-picker-field",
      style: {
        minWidth: 0
      }
    }, /*#__PURE__*/React.createElement("label", {
      htmlFor: id
    }, label), /*#__PURE__*/React.createElement("div", {
      style: {
        position: 'relative'
      }
    }, /*#__PURE__*/React.createElement("input", {
      id: id,
      className: "wb-number-input",
      type: "text",
      inputMode: "numeric",
      autoComplete: "off",
      value: value,
      maxLength: width,
      placeholder: '-'.repeat(width),
      "data-picker-initial": initial || undefined,
      "aria-invalid": invalid || undefined,
      onChange: event => change(event.target.value),
      onBlur: () => {
        if (value && !invalid) onChange(M.pad(Number(value), width));
      },
      onKeyDown: event => {
        if (['ArrowUp', 'ArrowDown'].includes(event.key)) {
          event.preventDefault();
          event.stopPropagation();
          increment(event.key === 'ArrowUp' ? 1 : -1);
        }
      }
    }), /*#__PURE__*/React.createElement("span", {
      className: "wb-number-stepper",
      style: {
        width: 20
      }
    }, [1, -1].map(delta => /*#__PURE__*/React.createElement("button", {
      key: delta,
      type: "button",
      className: "wb-number-step",
      "aria-label": (delta > 0 ? '增加' : '减少') + label,
      title: (delta > 0 ? '增加' : '减少') + label,
      disabled: value !== '' && (delta > 0 ? Number(value) >= maximum : Number(value) <= 0),
      onMouseDown: event => event.preventDefault(),
      onClick: () => increment(delta)
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        display: 'flex',
        transform: delta > 0 ? 'rotate(180deg)' : undefined
      }
    }, /*#__PURE__*/React.createElement(Icon, {
      name: "chevron-down"
    })))))));
  }
  function TimeFields({
    time,
    units,
    onChange,
    initial
  }) {
    const fields = [['hour', '时', 23], ['minute', '分', 59]].concat(units.seconds ? [['second', '秒', 59]] : [], units.fraction ? [['millisecond', '毫秒', 999]] : []);
    return /*#__PURE__*/React.createElement("div", {
      className: "wb-picker-fields",
      role: "group",
      "aria-label": "\u65F6\u95F4\uFF0824\u5C0F\u65F6\u5236\uFF09",
      style: {
        display: 'grid',
        gridTemplateColumns: 'repeat(' + fields.length + ', minmax(0, 1fr))',
        gap: 8
      }
    }, fields.map(([key, label, maximum]) => /*#__PURE__*/React.createElement(NumberField, {
      key: key,
      label: label,
      maximum: maximum,
      width: key === 'millisecond' ? 3 : 2,
      initial: initial && key === 'hour',
      value: time[key],
      onChange: value => onChange({
        ...time,
        [key]: value
      })
    })));
  }
  function DateGrid({
    view,
    cursor,
    selected,
    props,
    root,
    onBrowse,
    onChoose
  }) {
    const first = view.slice(0, 7) + '-01',
      leading = M.weekday(first),
      count = C.monthDays(Number(view.slice(0, 4)), Number(view.slice(5, 7)));
    const dates = Array.from({
      length: 42
    }, (_, index) => {
      const offset = index - leading;
      if (first === '0001-01-01' && offset < 0 || first === '9999-12-01' && offset >= count) return null;
      return M.moveDay(first, offset);
    });
    function keydown(event, day) {
      const offsets = {
        ArrowLeft: -1,
        ArrowRight: 1,
        ArrowUp: -7,
        ArrowDown: 7,
        Home: -M.weekday(day),
        End: 6 - M.weekday(day)
      };
      let next;
      if (Object.prototype.hasOwnProperty.call(offsets, event.key)) next = M.moveDay(day, offsets[event.key]);else if (['PageUp', 'PageDown'].includes(event.key)) next = M.moveMonth(day, (event.key === 'PageUp' ? -1 : 1) * (event.shiftKey ? 12 : 1));else if (['Enter', ' '].includes(event.key)) {
        event.preventDefault();
        event.stopPropagation();
        onChoose(day);
        return;
      } else return;
      event.preventDefault();
      event.stopPropagation();
      onBrowse(next, true);
    }
    return /*#__PURE__*/React.createElement("div", {
      className: "wb-picker-grid",
      ref: root,
      role: "grid",
      "aria-label": view.slice(0, 4) + ' 年 ' + Number(view.slice(5, 7)) + ' 月',
      style: {
        display: 'grid',
        gridTemplateColumns: 'repeat(7, minmax(0, 1fr))'
      }
    }, /*#__PURE__*/React.createElement("div", {
      role: "row",
      style: {
        display: 'contents'
      }
    }, weekdays.map(day => /*#__PURE__*/React.createElement("span", {
      role: "columnheader",
      className: "wb-picker-weekday",
      key: day
    }, "\u5468", day))), Array.from({
      length: 6
    }, (_, week) => /*#__PURE__*/React.createElement("div", {
      role: "row",
      key: week,
      style: {
        display: 'contents'
      }
    }, dates.slice(week * 7, week * 7 + 7).map((day, index) => {
      if (!day) return /*#__PURE__*/React.createElement("span", {
        key: 'empty-' + index,
        role: "gridcell"
      });
      const allowed = M.daySelectable(props, day),
        outside = day.slice(0, 7) !== view.slice(0, 7);
      return /*#__PURE__*/React.createElement("button", {
        key: day,
        type: "button",
        role: "gridcell",
        "data-date": day,
        "data-outside": outside || undefined,
        className: 'wb-picker-day' + (outside ? ' is-outside' : '') + (day === selected ? ' is-selected' : ''),
        "aria-label": day,
        title: day + (allowed ? '' : '（不可选）'),
        "aria-selected": day === selected,
        "aria-disabled": !allowed,
        "aria-current": day === M.today() ? 'date' : undefined,
        tabIndex: day === cursor ? 0 : -1,
        "data-picker-initial": day === cursor || undefined,
        onFocus: () => {
          if (day !== cursor) onBrowse(day, false, true);
        },
        onKeyDown: event => keydown(event, day),
        onClick: () => {
          if (allowed) onChoose(day);
        }
      }, Number(day.slice(8)));
    }))));
  }
  function MonthGrid({
    view,
    cursor,
    selected,
    props,
    root,
    onBrowse,
    onChoose,
    browseMonth
  }) {
    const year = view.slice(0, 4),
      selectedMonth = selected.slice(0, 7),
      currentMonth = M.today().slice(0, 7);
    const availability = React.useMemo(() => Array.from({
      length: 12
    }, (_, index) => M.monthSelectable(props, year + '-' + M.pad(index + 1))), [year, props.type, props.value, props.valueAttribute, props.min, props.max, props.step]);
    function keydown(event, key) {
      const month = Number(key.slice(5)),
        offsets = {
          ArrowLeft: -1,
          ArrowRight: 1,
          ArrowUp: -3,
          ArrowDown: 3,
          Home: -((month - 1) % 3),
          End: 2 - (month - 1) % 3,
          PageUp: -12,
          PageDown: 12
        };
      if (Object.prototype.hasOwnProperty.call(offsets, event.key)) {
        const boundary = event.key === 'PageUp' && key.startsWith('0001-') || event.key === 'PageDown' && key.startsWith('9999-');
        event.preventDefault();
        event.stopPropagation();
        onBrowse(boundary ? key + '-01' : M.moveMonth(key, offsets[event.key]), true);
      } else if (['Enter', ' '].includes(event.key)) {
        event.preventDefault();
        event.stopPropagation();
        onChoose(key);
      }
    }
    return /*#__PURE__*/React.createElement("div", {
      className: "wb-picker-grid",
      ref: root,
      role: "grid",
      "aria-label": view.slice(0, 4) + ' 年月份',
      style: {
        display: 'grid',
        gridTemplateColumns: 'repeat(3, minmax(0, 1fr))'
      }
    }, Array.from({
      length: 4
    }, (_, row) => /*#__PURE__*/React.createElement("div", {
      role: "row",
      style: {
        display: 'contents'
      },
      key: row
    }, Array.from({
      length: 3
    }, (_, column) => {
      const number = row * 3 + column + 1,
        key = year + '-' + M.pad(number),
        allowed = availability[number - 1];
      return /*#__PURE__*/React.createElement("button", {
        type: "button",
        role: "gridcell",
        key: key,
        "data-date": key,
        "data-view-month": key === browseMonth || undefined,
        className: 'wb-picker-day' + (key === selectedMonth ? ' is-selected' : ''),
        "aria-label": key,
        "aria-selected": key === selectedMonth,
        "aria-current": key === currentMonth ? 'date' : undefined,
        "aria-disabled": !allowed,
        tabIndex: key === cursor.slice(0, 7) ? 0 : -1,
        "data-picker-initial": key === cursor.slice(0, 7) || undefined,
        title: key + (key === browseMonth ? '（当前浏览）' : '') + (allowed ? '' : '（不可选）'),
        onKeyDown: event => keydown(event, key),
        onFocus: () => {
          if (key !== cursor.slice(0, 7)) onBrowse(key + '-01', false, true);
        },
        onClick: () => {
          if (allowed) onChoose(key);
        }
      }, number, " \u6708");
    }))));
  }
  function DatePickerBody(props) {
    const {
      type,
      value = '',
      onCommit,
      onClose,
      label
    } = props;
    const initial = M.seed(props),
      units = M.precision(props),
      root = React.useRef(null),
      focus = React.useRef(false);
    const [view, setView] = React.useState(initial),
      [cursor, setCursor] = React.useState(initial);
    const [pickerView, setPickerView] = React.useState(type === 'month' ? 'months' : type === 'time' ? 'time' : 'days');
    const monthAnchor = React.useRef(initial),
      showMonths = pickerView === 'months';
    const [year, setYear] = React.useState(initial.slice(0, 4)),
      [yearError, setYearError] = React.useState('');
    const [selected, setSelected] = React.useState(type === 'month' ? M.monthParts(value) ? value : '' : M.dateParts(value.slice(0, 10)) ? value.slice(0, 10) : '');
    const [time, setTime] = React.useState(() => M.readTime(value, units)),
      [edited, setEdited] = React.useState(false);
    const hasDate = type !== 'time',
      hasTime = ['time', 'datetime-local'].includes(type);
    const clock = M.timeValue(time, units),
      candidate = type === 'datetime-local' ? selected && clock ? selected + 'T' + clock : '' : type === 'time' ? clock : selected;
    const check = M.validate(props, candidate),
      id = React.useId();
    React.useLayoutEffect(() => {
      if (!focus.current || !root.current) return;
      focus.current = false;
      const cell = root.current.querySelector('[data-date="' + (showMonths ? cursor.slice(0, 7) : cursor) + '"]');
      if (cell) cell.focus();
    }, [cursor, view, showMonths]);
    function browse(next, shouldFocus, keepView) {
      focus.current = shouldFocus;
      setCursor(next);
      if (!keepView) {
        setView(next);
        setYear(next.slice(0, 4));
        setYearError('');
      }
    }
    function choose(next) {
      if (hasDate && (!/^\d{1,4}$/.test(year) || Number(year) < 1 || M.pad(Number(year), 4) !== view.slice(0, 4))) {
        applyYear();
        return;
      }
      const allowed = type === 'month' ? M.validate(props, next).valid : M.daySelectable(props, next);
      if (!allowed) return;
      setEdited(true);
      setSelected(next);
      if (type !== 'month') setPickerView('days');
      if (type === 'datetime-local') browse(next, false);else onCommit(M.validate(props, next).value);
    }
    function chooseMonth(key) {
      if (type === 'month') {
        choose(key);
        return;
      }
      if (!yearApplied) {
        applyYear();
        return;
      }
      if (!M.monthSelectable(props, key)) return;
      const [targetYear, targetMonth] = M.monthParts(key),
        targetDay = Math.min(Number(monthAnchor.current.slice(8)), C.monthDays(targetYear, targetMonth));
      setPickerView('days');
      browse(M.dateKey(targetYear, targetMonth, targetDay), true);
    }
    function toggleMonths() {
      const anchor = yearApplied ? cursor : applyYear();
      if (!anchor) return;
      if (showMonths) {
        setPickerView('days');
        browse(monthAnchor.current, true);
      } else {
        monthAnchor.current = anchor;
        setPickerView('months');
        browse(anchor, true);
      }
    }
    function applyYear() {
      if (!/^\d{1,4}$/.test(year) || Number(year) < 1 || Number(year) > 9999) {
        setYearError('年份须为 1 至 9999。');
        return;
      }
      const month = Number(view.slice(5, 7)),
        day = Math.min(Number(cursor.slice(8)), C.monthDays(Number(year), month));
      const next = M.dateKey(Number(year), month, day);
      browse(next, false);
      return next;
    }
    const yearApplied = !hasDate || /^\d{1,4}$/.test(year) && Number(year) >= 1 && M.pad(Number(year), 4) === view.slice(0, 4);
    function confirm() {
      if (!yearApplied) {
        applyYear();
        return;
      }
      if (check.valid && !yearError) onCommit(check.value);else setEdited(true);
    }
    const shortcut = type === 'month' ? M.today().slice(0, 7) : M.today();
    const shortcutAllowed = hasDate && (type === 'month' ? M.validate(props, shortcut).valid : M.daySelectable(props, shortcut));
    const move = showMonths ? 12 : 1;
    const browseYear = /^\d{1,4}$/.test(year) && Number(year) >= 1 ? Number(year) : Number(view.slice(0, 4));
    const browseBase = M.dateKey(browseYear, Number(view.slice(5, 7)), Math.min(Number(view.slice(8)), C.monthDays(browseYear, Number(view.slice(5, 7)))));
    const previous = M.moveMonth(browseBase, -move),
      next = M.moveMonth(browseBase, move);
    const title = label || {
      date: '选择日期',
      time: '选择时间',
      month: '选择月份',
      'datetime-local': '选择日期和时间'
    }[type];
    return /*#__PURE__*/React.createElement("div", {
      className: "wb-date-picker",
      "data-picker-type": type,
      "data-picker-view": pickerView,
      style: {
        width: 336,
        maxWidth: '100%',
        minWidth: 0
      },
      onKeyDown: event => {
        if (event.key === 'Enter' && event.target.tagName === 'INPUT' && event.target.closest('.wb-picker-fields')) {
          event.preventDefault();
          event.stopPropagation();
          confirm();
        }
      }
    }, /*#__PURE__*/React.createElement("div", {
      className: "wb-popup-header"
    }, /*#__PURE__*/React.createElement("strong", {
      id: id,
      style: {
        minWidth: 0,
        overflowWrap: 'anywhere'
      }
    }, title), /*#__PURE__*/React.createElement(NavButton, {
      icon: "x",
      name: "\u5173\u95ED\u65E5\u671F\u65F6\u95F4\u9009\u62E9",
      onClick: onClose
    })), hasDate && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "wb-picker-actions",
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: 8
      }
    }, /*#__PURE__*/React.createElement(NavButton, {
      name: showMonths ? '上一年' : '上个月',
      icon: "chevron-left",
      disabled: showMonths ? browseYear <= 1 : previous === view,
      onClick: () => browse(previous, false)
    }), /*#__PURE__*/React.createElement("label", {
      className: "wb-picker-year",
      style: {
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        flex: '1 1 auto',
        minWidth: 0
      }
    }, /*#__PURE__*/React.createElement("input", {
      type: "text",
      inputMode: "numeric",
      "aria-label": "\u5E74\u4EFD",
      value: year,
      maxLength: 4,
      autoComplete: "off",
      style: {
        width: 72
      },
      "aria-invalid": !!yearError,
      onChange: event => {
        if (/^\d{0,4}$/.test(event.target.value)) {
          setYear(event.target.value);
          setYearError('');
        }
      },
      onBlur: applyYear,
      onKeyDown: event => {
        if (event.key === 'Enter') {
          event.preventDefault();
          event.stopPropagation();
          applyYear();
        }
      }
    }), "\u5E74"), type !== 'month' && /*#__PURE__*/React.createElement("button", {
      type: "button",
      className: "btn",
      "aria-label": showMonths ? '返回日历' : '选择月份',
      "aria-expanded": showMonths,
      title: showMonths ? '返回日历' : '选择月份',
      onClick: toggleMonths,
      style: {
        flex: '0 0 100px',
        width: 100,
        marginLeft: 'auto',
        whiteSpace: 'nowrap'
      }
    }, showMonths ? '返回日历' : Number(view.slice(5, 7)) + ' 月', /*#__PURE__*/React.createElement("span", {
      style: {
        display: 'flex',
        transform: showMonths ? 'rotate(180deg)' : undefined
      }
    }, /*#__PURE__*/React.createElement(Icon, {
      name: "chevron-down"
    }))), /*#__PURE__*/React.createElement(NavButton, {
      name: showMonths ? '下一年' : '下个月',
      icon: "chevron-right",
      disabled: showMonths ? browseYear >= 9999 : next === view,
      onClick: () => browse(next, false)
    })), showMonths ? /*#__PURE__*/React.createElement(MonthGrid, {
      view,
      cursor,
      selected,
      props,
      root,
      browseMonth: type === 'month' ? undefined : monthAnchor.current.slice(0, 7),
      onBrowse: browse,
      onChoose: chooseMonth
    }) : /*#__PURE__*/React.createElement(DateGrid, {
      view,
      cursor,
      selected,
      props,
      root,
      onBrowse: browse,
      onChoose: choose
    })), hasTime && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "wb-picker-actions",
      style: {
        marginTop: hasDate ? 12 : 0
      }
    }, /*#__PURE__*/React.createElement("span", null, type === 'datetime-local' ? selected || '尚未选择日期' : '24 小时制')), /*#__PURE__*/React.createElement(TimeFields, {
      time: time,
      units: units,
      initial: type === 'time',
      onChange: nextTime => {
        setTime(nextTime);
        setEdited(true);
      }
    })), (yearError || edited && !check.valid && hasTime) && /*#__PURE__*/React.createElement("div", {
      role: "status",
      className: "wb-picker-error",
      style: {
        color: 'var(--ui-danger-text)',
        overflowWrap: 'anywhere',
        marginTop: 8
      }
    }, yearError || check.message), /*#__PURE__*/React.createElement("div", {
      className: "wb-popup-footer",
      style: {
        display: 'flex',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: 8
      }
    }, /*#__PURE__*/React.createElement("button", {
      type: "button",
      className: "btn",
      onClick: () => onCommit('')
    }, "\u6E05\u9664"), hasDate && /*#__PURE__*/React.createElement("button", {
      type: "button",
      className: "btn",
      disabled: !shortcutAllowed,
      onClick: () => choose(shortcut)
    }, type === 'month' ? '当前月份' : '今天'), /*#__PURE__*/React.createElement("span", {
      style: {
        flex: '1 1 auto'
      }
    }), /*#__PURE__*/React.createElement("button", {
      type: "button",
      className: "btn",
      onClick: onClose
    }, "\u53D6\u6D88"), hasTime && /*#__PURE__*/React.createElement("button", {
      type: "button",
      className: "btn primary wb-action wb-primary",
      disabled: !check.valid || !!yearError || !yearApplied,
      onClick: confirm
    }, /*#__PURE__*/React.createElement(Icon, {
      name: "check"
    }), "\u786E\u8BA4")));
  }
  function WorkbenchDatePicker(props) {
    return /*#__PURE__*/React.createElement(DatePickerBody, {
      key: JSON.stringify([props.type, props.value, props.valueAttribute, props.min, props.max, props.step]),
      ...props
    });
  }
  window.WorkbenchDatePicker = WorkbenchDatePicker;
})();
