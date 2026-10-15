// Transport-independent primitives shared by Node and Web Bluetooth.
export const now = () => performance.now();
export function failure(code, message, extra = {}) { return Object.assign(new Error(message), { code }, extra); }
export function deferred() {
  let resolve;
  const promise = new Promise(done => { resolve = done; });
  return { promise, resolve };
}
export function check(signal) { if (signal?.aborted) throw signal.reason; }
export function bounded(work, timeoutMs, { signal, error, late } = {}) {
  return new Promise((resolve, reject) => {
    let settled = false, timer;
    const finish = (fn, value) => {
      if (settled) return false;
      settled = true; clearTimeout(timer); signal?.removeEventListener('abort', abort); fn(value); return true;
    };
    const abort = () => finish(reject, signal.reason);
    if (signal?.aborted) { reject(signal.reason); return; }
    signal?.addEventListener('abort', abort, { once: true });
    timer = setTimeout(() => finish(reject, error || failure('RS4MINI_IO_TIMEOUT', 'BLE operation timed out')), Math.max(0, timeoutMs));
    Promise.resolve().then(() => { check(signal); return typeof work === 'function' ? work() : work; }).then(
      value => { if (!finish(resolve, value)) Promise.resolve().then(() => late?.(value)).catch(() => {}); },
      reason => finish(reject, reason),
    );
  });
}
export function delay(ms, signal) {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) { reject(signal.reason); return; }
    const abort = () => { clearTimeout(timer); signal.removeEventListener('abort', abort); reject(signal.reason); };
    const timer = setTimeout(() => { signal?.removeEventListener('abort', abort); resolve(); }, ms);
    signal?.addEventListener('abort', abort, { once: true });
  });
}
