(function () {
  'use strict';
  // 经办人记忆：只记住这台机器上最后一次填写的经办人，作为下次的默认值。它不是登录身份，
  // 服务端仍按每次提交的字面值校验；本机存储不可用时按空值处理，并把原因随结果返回给调用方。
  const KEY = 'aps_workbench_handler_v1';
  const valid = value => typeof value === 'string' && value.trim() === value && value.length > 0 && value.length <= 100 && !value.includes('\u0000');
  const parsed = raw => raw === null ? { value: '', error: '' } : valid(raw) ? { value: raw, error: '' } : { value: '', error: '本机记住的经办人格式无效，这次不预填。' };
  function read() {
    try {
      const raw = window.localStorage.getItem(KEY);
      return parsed(raw);
    } catch (_) { return { value: '', error: '本机经办人记忆无法读取，这次不预填。' }; }
  }
  const listeners = new Set();
  function write(value) {
    const text = typeof value === 'string' ? value.trim() : '';
    if (!valid(text)) return { saved: false, error: '经办人为空或过长，没有记住。' };
    let result;
    try { window.localStorage.setItem(KEY, text); result = { saved: true, value: text, error: '' }; }
    catch (_) { result = { saved: false, value: '', error: '本机经办人记忆无法写入，下次仍需手填。' }; }
    for (const listener of listeners) listener(result);
    return result;
  }
  // 经办人输入框下方的说明：解释预填值从哪来，或者为什么这次没能用上记忆。
  function hint(current, memory) {
    if (memory.error) return memory.error;
    return memory.value && memory.value === current ? '已按本机上次填写的经办人预填，可以直接改。' : '';
  }
  function useHint(current) {
    const [memory, setMemory] = React.useState(read);
    React.useEffect(() => {
      listeners.add(setMemory);
      const changed = event => { if (event.key === KEY || event.key === null) setMemory(parsed(event.key === null ? null : event.newValue)); };
      window.addEventListener('storage', changed);
      return () => { listeners.delete(setMemory); window.removeEventListener('storage', changed); };
    }, []);
    return hint(current, memory);
  }
  window.WorkbenchHandlerMemory = Object.freeze({ read, write, useHint });
})();
