'use strict';
// Node 契约共用的浏览器本机存储（localStorage / sessionStorage）内存替身，契约都从这里取，不再各写一份。
// 照浏览器的规则：值存成字符串，没有的键读出 null。
// records 是初始记录 [[键, 值], ...]；传另一个替身的 data 就是同一来源的另一个页面：存储对象是新的
// （pending-store 按存储对象区分页面），记录共用那一份。
// - data：背后的 Map，契约直接预置或查看记录；
// - writes：按顺序记下每次 setItem / removeItem 尝试的 ['set' | 'remove', 键]，写失败的那次也记；
// - failGet / failSet / failRemove：设成错误对象后，对应方法每次都抛出它（浏览器拒绝访问、配额写满），设回 null 恢复；
// - onAccess(方法名, 键, 'before' | 'after')：每次访问前后调用。契约用它计数、在访问中途插入别的页面的动作，
//   或在 'before' 里抛错，只让某个键的某次访问失败。'before' 先于 fail* 生效；访问失败时没有 'after'。
function memoryStorage(records = []) {
  const data = records instanceof Map ? records : new Map(records), writes = [];
  const storage = { data, writes, failGet: null, failSet: null, failRemove: null, onAccess: null,
    getItem(key) {
      enter('getItem', key, storage.failGet);
      const value = data.has(key) ? data.get(key) : null;
      leave('getItem', key);
      return value;
    },
    setItem(key, value) { writes.push(['set', key]); enter('setItem', key, storage.failSet); data.set(key, String(value)); leave('setItem', key); },
    removeItem(key) { writes.push(['remove', key]); enter('removeItem', key, storage.failRemove); data.delete(key); leave('removeItem', key); } };
  function enter(method, key, failure) {
    if (storage.onAccess) storage.onAccess(method, key, 'before');
    if (failure) throw failure;
  }
  function leave(method, key) { if (storage.onAccess) storage.onAccess(method, key, 'after'); }
  return storage;
}

module.exports = { memoryStorage };
