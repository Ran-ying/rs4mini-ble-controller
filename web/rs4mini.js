const SERVICE = 0xfff0;
const NOTIFY = 0xfff4;
const WRITE = 0xfff5;

function crc8(bytes) {
  let value = 0x77;
  for (const byte of bytes) {
    value ^= byte;
    for (let i = 0; i < 8; i++) value = value & 1 ? (value >>> 1) ^ 0x8c : value >>> 1;
  }
  return value & 0xff;
}

function crc16(bytes) {
  let value = 0x3692;
  for (const byte of bytes) {
    value ^= byte;
    for (let i = 0; i < 8; i++) value = value & 1 ? (value >>> 1) ^ 0x8408 : value >>> 1;
  }
  return value & 0xffff;
}

function rcUnits(value) {
  return 1024 + Math.round(Math.max(-1, Math.min(1, Number(value) || 0)) * 660);
}

function buildFrame(sequence, commandSet, commandId, payload = [], flags = 0) {
  const total = 13 + payload.length;
  const frame = new Uint8Array(total);
  frame[0] = 0x55;
  frame[1] = total & 0xff;
  frame[2] = 0x04 | ((total >>> 8) & 0x03);
  frame[3] = crc8(frame.subarray(0, 3));
  frame[4] = 0x02; // app
  frame[5] = 0x04; // gimbal
  frame[6] = sequence & 0xff;
  frame[7] = (sequence >>> 8) & 0xff;
  frame[8] = flags;
  frame[9] = commandSet;
  frame[10] = commandId;
  frame.set(payload, 11);
  const check = crc16(frame.subarray(0, total - 2));
  frame[total - 2] = check & 0xff;
  frame[total - 1] = check >>> 8;
  return frame;
}

export function velocityFrame(sequence, pan = 0, tilt = 0, roll = 0) {
  const view = new DataView(new ArrayBuffer(9));
  view.setInt16(0, rcUnits(tilt), true);
  view.setInt16(2, rcUnits(roll), true);
  view.setInt16(4, rcUnits(pan), true);
  view.setInt16(6, 0, true);
  view.setUint8(8, 0x02);
  return buildFrame(sequence, 0x04, 0x01, new Uint8Array(view.buffer));
}

export class RS4Mini {
  constructor() {
    this.device = null;
    this.tx = null;
    this.rx = null;
    this.sequence = 0x0100;
    this.velocity = [0, 0, 0];
    this.timer = null;
    this.writeChain = Promise.resolve();
    this.onDisconnect = null;
  }

  get connected() { return !!this.device?.gatt?.connected; }

  async connect() {
    if (!navigator.bluetooth) throw new Error("This browser does not support Web Bluetooth");
    // Must be called directly from a click/touch handler.
    this.device = await navigator.bluetooth.requestDevice({
      filters: [
        { namePrefix: "DJI R" },
        { services: [SERVICE] },
      ],
      optionalServices: [SERVICE],
    });
    this.device.addEventListener("gattserverdisconnected", () => {
      this._clearTimer();
      this.onDisconnect?.();
    });
    const server = await this.device.gatt.connect();
    const service = await server.getPrimaryService(SERVICE);
    this.rx = await service.getCharacteristic(NOTIFY);
    this.tx = await service.getCharacteristic(WRITE);
    await this.rx.startNotifications();
    return this.device.name;
  }

  async setVelocity({ pan = 0, tilt = 0, roll = 0 } = {}) {
    this._requireConnected();
    this.velocity = [pan, tilt, roll].map(v => Math.max(-1, Math.min(1, Number(v) || 0)));
    if (!this.timer) this.timer = setInterval(() => this._velocityTick(), 1000 / 15);
    await this._write(velocityFrame(this._nextSequence(), ...this.velocity));
  }

  async stop() {
    this.velocity = [0, 0, 0];
    this._clearTimer();
    if (!this.connected) return;
    for (let i = 0; i < 3; i++) {
      await this._write(velocityFrame(this._nextSequence(), 0, 0, 0));
      await new Promise(resolve => setTimeout(resolve, 67));
    }
  }

  async recenter() {
    this._requireConnected();
    await this.stop();
    await this._write(buildFrame(this._nextSequence(), 0x04, 0x4c, [0xfe, 0x01], 0x40));
  }

  async disconnect() {
    await this.stop();
    try { await this.rx?.stopNotifications(); } catch {}
    this.device?.gatt?.disconnect();
    this.tx = this.rx = null;
  }

  _velocityTick() {
    if (!this.connected) return this._clearTimer();
    if (this.velocity.every(v => v === 0)) return;
    this._write(velocityFrame(this._nextSequence(), ...this.velocity));
  }

  _write(frame) {
    this.writeChain = this.writeChain.then(async () => {
      this._requireConnected();
      for (let offset = 0; offset < frame.length; offset += 20) {
        await this.tx.writeValueWithoutResponse(frame.slice(offset, offset + 20));
      }
    });
    return this.writeChain;
  }

  _nextSequence() {
    const value = this.sequence;
    this.sequence = (this.sequence + 1) & 0xffff;
    return value;
  }

  _clearTimer() {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
  }

  _requireConnected() {
    if (!this.connected || !this.tx) throw new Error("RS 4 Mini is not connected");
  }
}
