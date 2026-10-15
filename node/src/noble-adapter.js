import noble from '@stoprocent/noble';

// Each controller gets its own lazy Noble instance. Closing an unused controller
// must not initialize Bluetooth, and closing one must not stop a future instance.
export class NobleAdapter {
  constructor(native) { this.native = native; this.started = false; this.stopped = false; }
  get state() { this.started = true; return this.native.state; }
  on(event, callback) { this.native.on(event, callback); return this; }
  removeListener(event, callback) { this.native.removeListener(event, callback); return this; }
  waitForPoweredOnAsync(timeout) { this.started = true; return this.native.waitForPoweredOnAsync(timeout); }
  startScanningAsync(...args) { this.started = true; return this.native.startScanningAsync(...args); }
  stopScanningAsync() { return this.started && !this.stopped ? this.native.stopScanningAsync() : Promise.resolve(); }
  connectAsync(...args) { this.started = true; return this.native.connectAsync(...args); }
  cancelConnect(id) { if (this.started && !this.stopped && id) this.native.cancelConnect(id); }
  stop() { if (this.started && !this.stopped) { this.stopped = true; this.native.stop(); } }
}
export function createNobleAdapter() { return new NobleAdapter(noble.withBindings()); }
