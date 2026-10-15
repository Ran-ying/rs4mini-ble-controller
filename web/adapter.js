// Small Noble-compatible adapter; browser and Node share the control state machine.
class Emitter {
  constructor() { this.listeners = new Map(); }
  on(event, callback) {
    if (!this.listeners.has(event)) this.listeners.set(event, new Set());
    this.listeners.get(event).add(callback); return this;
  }
  removeListener(event, callback) { this.listeners.get(event)?.delete(callback); return this; }
  emit(event, ...values) { for (const callback of [...(this.listeners.get(event) || [])]) callback(...values); }
}
class Characteristic extends Emitter {
  constructor(native, uuid) {
    super(); this.native = native; this.uuid = uuid;
    this.changed = event => {
      const value = event.target.value;
      this.emit('data', new Uint8Array(value.buffer, value.byteOffset, value.byteLength).slice(), true);
    };
  }
  on(event, callback) {
    if (event === 'data' && !this.listeners.get(event)?.size) this.native.addEventListener('characteristicvaluechanged', this.changed);
    return super.on(event, callback);
  }
  removeListener(event, callback) {
    super.removeListener(event, callback);
    if (event === 'data' && !this.listeners.get(event)?.size) this.native.removeEventListener('characteristicvaluechanged', this.changed);
    return this;
  }
  subscribeAsync() { return this.native.startNotifications(); }
  unsubscribeAsync() { return this.native.stopNotifications(); }
  writeAsync(data) { return this.native.writeValueWithoutResponse(data); }
}
class Peripheral extends Emitter {
  constructor(device) {
    super(); this.device = device; this.id = device.id; this.advertisement = { localName: device.name || 'DJI RS4 MINI' };
    this.disconnected = () => this.emit('disconnect', 'gattserverdisconnected');
  }
  get state() { return this.device.gatt?.connected ? 'connected' : 'disconnected'; }
  on(event, callback) {
    if (event === 'disconnect' && !this.listeners.get(event)?.size) this.device.addEventListener('gattserverdisconnected', this.disconnected);
    return super.on(event, callback);
  }
  removeListener(event, callback) {
    super.removeListener(event, callback);
    if (event === 'disconnect' && !this.listeners.get(event)?.size) this.device.removeEventListener('gattserverdisconnected', this.disconnected);
    return this;
  }
  connectAsync() { return this.device.gatt.connect(); }
  async disconnectAsync() { this.device.gatt?.disconnect(); }
  async discoverSomeServicesAndCharacteristicsAsync() {
    const service = await this.device.gatt.getPrimaryService(0xfff0);
    const rx = await service.getCharacteristic(0xfff4), tx = await service.getCharacteristic(0xfff5);
    return { characteristics: [new Characteristic(rx, 'fff4'), new Characteristic(tx, 'fff5')] };
  }
}
export class BrowserAdapter extends Emitter {
  constructor(bluetooth) { super(); this.bluetooth = bluetooth; this.peripheral = null; this.selection = null; this.generation = 0; }
  select() {
    if (!this.bluetooth) throw new Error('This browser does not support Web Bluetooth');
    if (this.selection || this.peripheral) return;
    // Invoke synchronously in the user's click handler to retain transient activation.
    const generation = this.generation;
    this.selection = this.bluetooth.requestDevice({ filters: [{ namePrefix: 'DJI R' }, { services: [0xfff0] }], optionalServices: [0xfff0] })
      .then(device => { const peripheral = new Peripheral(device); if (this.generation === generation) this.peripheral = peripheral; return peripheral; });
    this.selection.catch(() => {});
  }
  async waitForPoweredOnAsync() { if (!this.bluetooth) throw new Error('This browser does not support Web Bluetooth'); }
  async connectAsync(id) {
    if (this.peripheral?.id !== id) throw new Error('Select the device from a click handler first');
    await this.peripheral.connectAsync(); return this.peripheral;
  }
  async startScanningAsync() {
    const selection = this.selection, generation = this.generation;
    try {
      const peripheral = this.peripheral || await selection;
      if (!peripheral) throw new Error('Device selection requires a user gesture');
      if (this.generation === generation) this.emit('discover', peripheral);
    }
    finally { if (this.selection === selection) this.selection = null; }
  }
  async stopScanningAsync() {}
  cancelConnect() { this.peripheral?.device.gatt?.disconnect(); }
  resetSelection() { this.generation++; this.peripheral = null; this.selection = null; }
  stop() { this.resetSelection(); }
}
