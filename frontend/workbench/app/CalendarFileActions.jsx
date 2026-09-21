(function () {
  'use strict';
  // Load after CalendarFileContract.js and ResourceMaterialActions.jsx.
  const K = window.APSCalendarContract;
  const { Button, Field } = window.ResourceControls;
  function monthRange(month) {
    const key = K.monthKey(month.year, month.month);
    return { start_date: key + '-01', end_date: key + '-' + K.monthDays(month.year, month.month) };
  }
  function thisMonth() {
    const now = new Date();
    return { year: now.getFullYear(), month: now.getMonth() + 1 };
  }
  function People({ value, onChange, refs, disabled }) {
    return <fieldset style={{ border: 0, margin: 0, padding: 0 }} disabled={disabled}>
      <legend className="seclabel">人员范围</legend>
      {[['all', '全部人员', '所有人员在这段时间里单独设置过的日期'],
        ['selected', '已选人员', refs.length + ' 人，含非当前页和当前筛选外的勾选记录']].map(([key, title, detail]) =>
        <label key={key} className={'iorow' + (value === key ? ' on' : '')}>
          <input type="radio" name="operator-calendar-people" value={key} checked={value === key} onChange={() => onChange(key)} />
          <div><div className="iotitle">{title}</div><div className="iosub">{detail}</div></div></label>)}
    </fieldset>;
  }
  function ExportScope({ value, onChange, disabled, refs = [] }) {
    const id = React.useId();
    const set = (key, next) => onChange({ ...value, [key]: next });
    return <>
      {value.people !== undefined && <People value={value.people} onChange={next => set('people', next)} refs={refs} disabled={disabled} />}
      <fieldset style={{ border: 0, margin: 0, padding: 0 }} disabled={disabled}>
        <legend className="seclabel">导出范围</legend>
        <div className="fgrid">
          <Field label="开始日期" path="start_date" required>
            <input id={id + '-from'} type="date" value={value.start_date} disabled={disabled}
              onChange={event => set('start_date', event.target.value)} /></Field>
          <Field label="结束日期" path="end_date" required>
            <input id={id + '-to'} type="date" value={value.end_date} disabled={disabled}
              onChange={event => set('end_date', event.target.value)} /></Field>
        </div>
        <p className="iohint">只导出这段时间里单独配置过的日期。没有单独配置过的日期按默认规则算，不会出现在文件里，
          所以导出的文件原样导回来不会有任何改动。</p>
      </fieldset></>;
  }
  function CalendarFileActions({ kind, month, request, ...props }) {
    const refs = Array.isArray(request && request.refs) ? request.refs : [];
    const people = kind === window.APSCalendarFile.peopleKind;
    const contract = React.useMemo(() => ({
      ...window.APSCalendarFile.create(kind),
      // 个人日历从人员列表打开，勾了人就默认只导这些人；全局日历没有这一维。
      exportScopeInitial: { ...monthRange(month || thisMonth()), ...(people ? { people: refs.length ? 'selected' : 'all' } : {}) },
      ExportScope
    }), [kind, people, refs.length, month && month.year, month && month.month]);
    return <window.ResourceFileActionFlow key={kind} {...props} request={request} contract={contract} />;
  }
  window.CalendarFileActions = CalendarFileActions;
  window.CalendarFileActions.ExportScope = ExportScope;
  window.CalendarFileActions.monthRange = monthRange;
})();
