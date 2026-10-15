import { EventEmitter } from 'node:events';
import { setImmediate as tick } from 'node:timers/promises';
import { RS4Mini } from '../src/controller.js';
import { frame } from '../src/protocol.js';
import { DumlStreamDecoder } from '../src/telemetry.js';

export function gate() { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; }
export async function until(predicate) {
  const deadline = performance.now() + 1500;
  while (!predicate()) { if (performance.now() > deadline) throw new Error('Test condition did not become true'); await tick(); }
}
export class Characteristic extends EventEmitter {
  constructor(uuid) { super(); this.uuid = uuid; this.writes = []; this.subscribeCount = this.unsubscribeCount = 0; }
  async subscribeAsync() { this.subscribeCount++; }
  async unsubscribeAsync() { this.unsubscribeCount++; }
  async writeAsync(data, withoutResponse) { this.writes.push([Buffer.from(data), withoutResponse]); }
}
export class Peripheral extends EventEmitter {
  constructor() {
    super(); this.id = 'TEST-ID'; this.state = 'disconnected';
    this.advertisement = { localName: 'DJI RS 4 MINI-TEST' };
    this.rx = new Characteristic('fff4'); this.tx = new Characteristic('fff5'); this.disconnectCount = 0;
  }
  async connectAsync() { this.state = 'connected'; }
  async disconnectAsync() { this.disconnectCount++; this.state = 'disconnected'; this.emit('disconnect', 'test'); }
  async discoverSomeServicesAndCharacteristicsAsync() { return { characteristics: [this.rx, this.tx] }; }
  telemetry({ yaw = 0, pitch = 0, roll = 0, short = false } = {}) {
    const payload = Buffer.alloc(short ? 6 : 49);
    if (!short) { payload.writeInt16LE(Math.round(yaw * 100), 16); payload.writeInt16LE(Math.round(pitch * 10), 20); payload.writeInt16LE(Math.round(roll * 10), 22); }
    this.rx.emit('data', frame(1, 4, 5, payload), true);
  }
  frames() { return new DumlStreamDecoder().push(Buffer.concat(this.tx.writes.map(([chunk]) => chunk))); }
}
export class Adapter extends EventEmitter {
  constructor(peripheral) { super(); this.peripheral = peripheral; this.scans = 0; this.cancelled = []; this.stopped = false; }
  async waitForPoweredOnAsync() {}
  async connectAsync() { await this.peripheral.connectAsync(); return this.peripheral; }
  cancelConnect(id) { this.cancelled.push(id); }
  async startScanningAsync() { this.scans++; queueMicrotask(() => this.emit('discover', this.peripheral)); }
  async stopScanningAsync() {}
  stop() { this.stopped = true; }
}
export function setup(options = {}) {
  const peripheral = new Peripheral(), adapter = new Adapter(peripheral);
  const gimbal = new RS4Mini({ adapter, rateHz: 1000, ioTimeoutMs: 100, ...options });
  return { gimbal, adapter, peripheral };
}
export async function connected(t, options) {
  const result = setup(options);
  await result.gimbal.connect();
  t.after(() => result.gimbal.close().catch(() => {}));
  return result;
}
