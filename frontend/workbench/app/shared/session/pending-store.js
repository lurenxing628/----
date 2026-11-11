const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);

function fault(message, details) {
  return Object.assign(new Error(message), {
    code: null, fields: [], conflicts: [], committed: false, status: null,
    requestRef: null, requestKey: null, resultTarget: null
  }, details);
}

function canonical(value) {
  return JSON.stringify(value, (_, item) => object(item) ? Object.keys(item).sort().reduce((out, key) => { out[key] = item[key]; return out; }, {}) : item);
}

const equal = (a, b) => canonical(a) === canonical(b);

function raise(spec, cause, extra) {
  const err = !spec ? cause : typeof spec === 'function' ? spec() : new Error(spec);
  if (extra) Object.assign(err, extra);
  throw err;
}

// 跨页互斥的唯一入口：同名的本机待确认记录转换在所有标签页之间串行。不带 wait 时拿不到锁立即返回 acquired:false。
async function exclusive(name, { wait }, fn) {
  const locks = window.navigator && window.navigator.locks;
  if (!locks) throw fault('当前浏览器不支持，请用 Chrome 打开。', { code: 'locks_unavailable' });
  return locks.request(name, wait ? {} : { ifAvailable: true },
    async lock => lock ? { acquired: true, value: await fn() } : { acquired: false, value: undefined });
}

// 本页内每个存储对象、每个通道与键的槽位表：按 channel + '\0' + key 隔离持久化与各领域会话状态，
// 处理 storageGetter() 抛 SecurityError 时的 lastTarget 回退与独立 orphan 迁移。只在本页内存里，不跨页共享。
const pageSlots = new WeakMap();

function storageSlot(storageGetter, channel, key, createInitial, migrateOrphan) {
  const slotKey = channel + '\0' + key;
  let orphan = null, lastTarget;
  return function slotOf(knownTarget) {
    let target = knownTarget;
    if (arguments.length === 0) {
      try { target = storageGetter(); } catch (_) {}
    }
    const valid = object(target) ? target : undefined;
    if (valid !== undefined) lastTarget = valid;
    const effective = valid !== undefined ? valid : lastTarget;
    if (effective === undefined) return orphan || (orphan = createInitial());
    let slots = pageSlots.get(effective);
    if (!slots) pageSlots.set(effective, slots = new Map());
    let slot = slots.get(slotKey);
    if (!slot) slots.set(slotKey, slot = createInitial());
    if (orphan) {
      const pendingOrphan = orphan;
      orphan = null;
      migrateOrphan(slot, pendingOrphan);
    }
    return slot;
  };
}

// 待确认意图的本机存储：统一读、校验、CAS 写、清除与同页事件通知，错误文案由各领域指定；跨页串行由调用方用 exclusive 保证。
// 每个存储必须提供 validate：磁盘读取边界唯一的领域校验，非空记录（原始串模式校验原始串，其余校验解析后的值）都要通过；
// 写入的值由领域从已校验的网络结果或本存储读到的记录构造，写前不再重验。
function pendingStore({ key, storage = () => window.localStorage, event, raw = false, validate,
    encode = value => value, readError, corruptError = readError, invalidError = corruptError,
    conflictError, writeError, removeError = writeError }) {
  const slotOf = storageSlot(storage, 'store', key, () => ({ known: undefined, pending: null }), (slot, prev) => {
    if (prev.pending) { slot.pending = prev.pending; slot.known = prev.known; }
  });
  const matches = (left, right) => left === null || right === null ? left === right
    : raw ? equal(left, right) : equal(encode(left), encode(right));
  const notify = value => { if (event) window.dispatchEvent(new CustomEvent(event, { detail: value })); };
  const put = (target, value) => value === null ? target.removeItem(key) : target.setItem(key, raw ? value : JSON.stringify(encode(value)));
  const conflict = () => raise(conflictError, undefined, { conflict: true });
  // 磁盘原始串的唯一解码点：null 表示没有记录；原始串模式只校验，其余先解析再校验。
  function decode(text) {
    if (text === null) return null;
    let value = text;
    if (!raw) {
      try { value = JSON.parse(text); } catch (error) { raise(corruptError, error); }
    }
    if (!validate(value)) raise(invalidError);
    return value;
  }
  // 每次转换只调一次 getItem。未刷盘记录只在磁盘仍是它记下的旧值时有效，否则别处已经写过，丢弃它。
  // 读不到磁盘时先让 settle（save 的冲突核对与未刷盘记录）处理本页状态，再在读取边界报错。
  function effectiveRead(settle) {
    let target, text;
    try { target = storage(); text = target.getItem(key); }
    catch (error) {
      const slot = slotOf(target);
      if (settle) settle(slot);
      raise(readError, error, slot.pending ? { saved: slot.pending.value } : undefined);
    }
    const slot = slotOf(target), disk = decode(text);
    if (slot.pending && !matches(disk, slot.pending.disk)) slot.pending = null;
    slot.known = slot.pending ? slot.pending.value : disk;
    return { target, slot, disk, current: slot.known };
  }
  // 已登记结算还欠着的附属写入：写本键前补做，成功立即清掉，之后本键写失败再重试也不会重复执行。
  // 补做失败时登记原样保留，按这条结算的写入失败报出并带上它的权威值。
  function replay(slot) {
    const pending = slot.pending;
    if (!pending || !pending.beforeWrite) return;
    try { pending.beforeWrite(); }
    catch (error) { raise(pending.value === null ? removeError : writeError, error, { saved: pending.value }); }
    pending.beforeWrite = null;
  }
  // 把已登记的结算写进磁盘：先补附属写入，再写本键；任一步失败都保留登记并带出 saved，由 flush 或下一次 save 再写。
  function writeBack(target, slot) {
    replay(slot);
    const { value } = slot.pending;
    try { put(target, value); } catch (error) { raise(value === null ? removeError : writeError, error, { saved: value }); }
    slot.pending = null;
    return value;
  }
  // 只读不写，锁外也能调。本页还有仍有效的未刷盘记录时，照写失败报出并带 saved，由持锁的 flush 或下一次 save 写回。
  function read() {
    const { slot, current } = effectiveRead();
    if (slot.pending) raise(current === null ? removeError : writeError, undefined, { saved: current });
    return current;
  }
  // 和 save 一样由调用方在本键的跨页锁里调用：本页未刷盘记录仍有效时写进磁盘，返回当前值。
  function flush() {
    const { target, slot, current } = effectiveRead();
    if (slot.pending) writeBack(target, slot);
    return current;
  }
  // 不读直接写：只给不做 CAS 的附属记录用（如最近排产结论）。
  function write(value) {
    try { put(storage(), value); } catch (error) { raise(value === null ? removeError : writeError, error); }
    notify(value);
    return value;
  }
  const ctx = { effectiveRead, matches, conflict, notify, replay, writeBack, put, writeError, removeError };
  const save = (value, previous, beforeWrite = null) => saveStoreRecord(ctx, value, previous, beforeWrite);
  const subscribe = createStoreSubscribe(key, event);
  return { read, flush, write, save, subscribe };
}

// CAS 转换：当前值仍是 previous 才写入 value。当前已是 value 时无操作（重复的结束、清除、关联都幂等）；但本页还有未刷盘记录时，
// 只有这条记录的发起方（previous 是记录的旧值或目标值）能接着写回，过时调用方不能接管。
// CAS 通过后先补完旧结算欠着的附属写入，补不上就保留旧登记直接报错，不替换它、也不发布新值。
// 结算类转换随后先登记整次结算（权威值与 beforeWrite）并通知，再做附属写与本键写入；写不进去时登记留在本页，错误带出 saved。
// 新建待确认记录这类非结算转换不预先登记，写成功后才通知。beforeWrite 只写别的键，只随结算登记；
// getItem 失败时它还没执行，随登记留下，由 flush 或下一次 save 写本键前补做。
function saveStoreRecord(ctx, value, previous, beforeWrite) {
  const settling = previous !== null && (value === null || value.phase !== 'pending');
  const { target, slot, disk, current } = ctx.effectiveRead(slot => {
    const view = slot.pending ? slot.pending.value : slot.known;
    if (view !== undefined && !ctx.matches(view, previous) && !ctx.matches(view, value)) ctx.conflict();
    if (settling && !(view !== undefined && ctx.matches(view, value))) {
      // 还欠着 beforeWrite 的记录不能被接在它后面的结算顶掉。
      if (slot.pending && slot.pending.beforeWrite) ctx.conflict();
      slot.pending = { disk: slot.pending ? slot.pending.disk : view !== undefined ? view : previous, value, beforeWrite };
      slot.known = value; ctx.notify(value);
    }
  });
  if (ctx.matches(current, value)) {
    if (!slot.pending) return value;
    if (ctx.matches(previous, slot.pending.disk) || ctx.matches(previous, value)) return ctx.writeBack(target, slot);
    ctx.conflict();
  }
  if (!ctx.matches(current, previous)) ctx.conflict();
  ctx.replay(slot);
  if (settling) {
    slot.pending = { disk: slot.pending ? slot.pending.disk : disk, value, beforeWrite };
    slot.known = value; ctx.notify(value);
    return ctx.writeBack(target, slot);
  }
  try { ctx.put(target, value); } catch (error) { raise(value === null ? ctx.removeError : ctx.writeError, error); }
  slot.pending = null; slot.known = value; ctx.notify(value);
  return value;
}

function createStoreSubscribe(key, event) {
  const listeners = new Set();
  const onEvent = e => {
    if (e && e.type === 'storage' && e.key && e.key !== key) return;
    for (const fn of listeners) fn(e);
  };
  return function subscribe(listener) {
    if (!listeners.size) {
      window.addEventListener('storage', onEvent);
      if (event) window.addEventListener(event, onEvent);
    }
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
      if (!listeners.size) {
        window.removeEventListener('storage', onEvent);
        if (event) window.removeEventListener(event, onEvent);
      }
    };
  };
}

export { pendingStore, storageSlot, exclusive, canonical, equal };
export default { pendingStore, storageSlot, exclusive, canonical, equal };
