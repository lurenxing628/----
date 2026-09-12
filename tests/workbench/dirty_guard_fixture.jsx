(function () {
  const G = window.WorkbenchGuards, R = window.ResourceControls;
  window.guardResults = [];
  function Editor({ owner }) {
    const [value, setValue] = React.useState(''), [locked, setLocked] = React.useState(false);
    G.useDirtyGuard({ owner, dirty: value !== '', locked, message: owner + ' 未保存' });
    return <section><label>{owner}<input aria-label={owner} value={value} onChange={event => setValue(event.target.value)} /></label>
      <label><input type="checkbox" aria-label={owner + ' pending'} checked={locked} onChange={event => setLocked(event.target.checked)} />请求待核实</label></section>;
  }
  function FormModal({ onClose }) {
    const [value, setValue] = React.useState('');
    const owner = G.useDirtyGuard({ dirty: value !== '', message: '弹窗未保存' });
    async function close(detail) {
      if (detail && detail.guardConfirmed === true && detail.guardOwner === owner || await G.confirmLeave({ owner })) onClose();
    }
    return <R.Modal title="编辑弹窗" onClose={close} guardOwner={owner} footer={<R.Button onClick={close}>取消编辑</R.Button>}>
      <label>弹窗输入<input aria-label="弹窗输入" value={value} onChange={event => setValue(event.target.value)} /></label></R.Modal>;
  }
  function Fixture() {
    const [modal, setModal] = React.useState(false), [readOnly, setReadOnly] = React.useState(false);
    window.askGuard = options => G.confirmLeave(options).then(value => window.guardResults.push(value));
    return <><window.WorkbenchGuardHost /><Editor owner="A" /><Editor owner="B" />
      <button id="request-all" onClick={() => window.askGuard({})}>离开全部</button>
      <button id="request-a" onClick={() => window.askGuard({ owner: 'A' })}>离开 A</button>
      <button id="open-edit" onClick={() => setModal(true)}>打开编辑弹窗</button>
      <button id="open-read" onClick={() => setReadOnly(true)}>打开只读弹窗</button>
      <button id="external" onClick={() => G.leaveExternal(() => location.assign('/left'))}>外部离开</button>
      {modal && <FormModal onClose={() => setModal(false)} />}
      {readOnly && <R.Modal title="只读弹窗" onClose={() => setReadOnly(false)}><p>只读内容</p></R.Modal>}</>;
  }
  const root = ReactDOM.createRoot(document.getElementById('root'));
  root.render(<Fixture />);
})();
