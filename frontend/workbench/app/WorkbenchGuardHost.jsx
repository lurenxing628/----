(function () {
  'use strict';
  const G = window.WorkbenchGuards, { Modal, Button } = window.ResourceControls;
  function WorkbenchGuardHost() {
    const [prompt, setPrompt] = React.useState(G.getPrompt);
    React.useLayoutEffect(() => G.subscribe(setPrompt), []);
    if (!prompt) return null;
    const close = () => G.resolvePrompt(prompt.id, false);
    return ReactDOM.createPortal(<div className="plana wb-guard-host">
      <Modal title={prompt.locked ? '上次操作还没有确认结果' : '离开前确认'} icon="circle-alert" guardBypass onClose={close}
        footer={<><Button onClick={close}>留在当前页面</Button>
          {!prompt.locked && <Button className="btn danger" onClick={() => G.resolvePrompt(prompt.id, true)}>放弃未保存内容并继续</Button>}</>}>
        <div className="modal-b">
          {prompt.locked && <p role="status">上次操作的结果还没查到，请留在本页点「查询结果」，不要放弃或重复提交。</p>}
          <ul>{prompt.messages.map(message => <li key={message}>{message}</li>)}</ul>
          {!prompt.locked && <p>继续将放弃尚未保存的输入。</p>}
        </div>
      </Modal>
    </div>, document.body);
  }
  window.WorkbenchGuardHost = WorkbenchGuardHost;
})();
