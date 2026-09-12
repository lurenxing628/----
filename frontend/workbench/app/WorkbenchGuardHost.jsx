(function () {
  'use strict';
  const G = window.WorkbenchGuards, { Modal, Button } = window.ResourceControls;
  function WorkbenchGuardHost() {
    const [prompt, setPrompt] = React.useState(G.getPrompt);
    React.useLayoutEffect(() => G.subscribe(setPrompt), []);
    if (!prompt) return null;
    const close = () => G.resolvePrompt(prompt.id, false);
    return ReactDOM.createPortal(<div className="plana wb-guard-host">
      <Modal title={prompt.locked ? '原请求尚未核实' : '离开前确认'} icon="circle-alert" guardBypass onClose={close}
        footer={<><Button onClick={close}>留在当前页面</Button>
          {!prompt.locked && <Button className="btn danger" onClick={() => G.resolvePrompt(prompt.id, true)}>放弃未保存内容并继续</Button>}</>}>
        <div className="modal-b">
          {prompt.locked && <p role="status">操作结果仍待核实，请保留当前页面并查询原请求，不能放弃或重复提交。</p>}
          <ul>{prompt.messages.map(message => <li key={message}>{message}</li>)}</ul>
          {!prompt.locked && <p>继续后，这些尚未保存的输入将丢失。已经保存的记录不会删除。</p>}
        </div>
      </Modal>
    </div>, document.body);
  }
  window.WorkbenchGuardHost = WorkbenchGuardHost;
})();
