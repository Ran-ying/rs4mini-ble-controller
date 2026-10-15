import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import { RS4Mini } from "../src/index.js";
import { frame } from "../src/protocol.js";

class FakeCharacteristic extends EventEmitter {
  constructor(uuid) { super(); this.uuid = uuid; this.writes = []; }
  async subscribeAsync() { this.subscribed = true; }
  async unsubscribeAsync() { this.subscribed = false; }
  async writeAsync(data, withoutResponse) { this.writes.push([Buffer.from(data), withoutResponse]); }
}

class FakePeripheral extends EventEmitter {
  constructor(id = "CACHED-RS4-MINI-ID", state = "connected") {
    super();
    this.id = id;
    this.state = state;
    this.advertisement = { localName: "DJI RS4 MINI-TEST" };
    this.rx = new FakeCharacteristic("fff4");
    this.tx = new FakeCharacteristic("fff5");
  }
  async discoverSomeServicesAndCharacteristicsAsync() {
    return { characteristics: [this.rx, this.tx] };
  }
  async connectAsync() { this.state = "connected"; }
  async disconnectAsync() { this.state = "disconnected"; this.emit("disconnect", "test"); }
}

class FakeAdapter extends EventEmitter {
  constructor(peripheral, directError = null, emitOnScan = true) {
    super(); this.peripheral = peripheral; this.directError = directError;
    this.emitOnScan = emitOnScan; this.scanCount = 0; this.stopped = false;
  }
  async waitForPoweredOnAsync() {}
  async connectAsync(id) {
    if (this.directError) throw this.directError;
    assert.equal(id, this.peripheral.id);
    return this.peripheral;
  }
  cancelConnect() {}
  async startScanningAsync() {
    this.scanCount++;
    if (this.emitOnScan) queueMicrotask(() => this.emit("discover", this.peripheral));
  }
  async stopScanningAsync() {}
  stop() { this.stopped = true; }
}

const peripheral = new FakePeripheral();
const adapter = new FakeAdapter(peripheral);
const gimbal = new RS4Mini({ deviceId: peripheral.id, adapter, rateHz: 1000 });

assert.equal(await gimbal.connect(), "DJI RS4 MINI-TEST");
assert.equal(gimbal.connected, true);
assert.equal(gimbal.deviceId, peripheral.id);
assert.equal(adapter.scanCount, 0, "cached device ID should bypass scanning");
await assert.rejects(gimbal.connect({ timeuotMs: 1 }), /connect received unknown option: timeuotMs/);
await assert.rejects(
  gimbal.setVelocity({ tile: -1 }),
  /setVelocity received unknown option: tile/,
  "axis typos must fail instead of silently becoming a zero command",
);
await gimbal.stop();
assert.equal(peripheral.tx.writes.length, 6, "three 22-byte stop frames become six GATT writes");

const telemetryPayload = Buffer.alloc(49);
telemetryPayload.writeInt16LE(-1725, 0);
telemetryPayload.writeInt16LE(6, 2);
telemetryPayload.writeInt16LE(806, 4);
telemetryPayload.writeInt16LE(8188, 16);
telemetryPayload.writeInt16LE(41, 20);
telemetryPayload.writeInt16LE(11, 22);
peripheral.rx.emit("data", frame(0x2000, 0x04, 0x05, telemetryPayload), true);
assert.deepEqual(await gimbal.getAttitude(), {
  pitch: -172.5,
  roll: 0.6,
  yaw: 80.6,
  unit: "deg",
  wrap: 180,
  raw: { pitch: -1725, roll: 6, yaw: 806 },
  timestamp: gimbal.latestTelemetry.timestamp,
});
assert.deepEqual(await gimbal.getJointAngles(), {
  pitch: 4.1,
  roll: 1.1,
  yaw: 81.88,
  unit: "deg",
  raw: { pitch: 41, roll: 11, yaw: 8188 },
  timestamp: gimbal.latestTelemetry.timestamp,
});

const freshAttitude = gimbal.getAttitude({ fresh: true, timeoutMs: 100 });
queueMicrotask(() => {
  telemetryPayload.writeInt16LE(812, 4);
  peripheral.rx.emit("data", frame(0x2001, 0x04, 0x05, telemetryPayload), true);
});
assert.equal((await freshAttitude).yaw, 81.2);

const savedGetJointAngles = gimbal.getJointAngles;
const savedInternalSetVelocity = gimbal._setVelocity;
const savedInternalStop = gimbal._stop;
const jointSamples = [
  { pitch: 0, roll: 0, yaw: 0, unit: "deg", raw: {}, timestamp: Date.now() },
  { pitch: 4.5, roll: -3.5, yaw: 4.6, unit: "deg", raw: {}, timestamp: Date.now() + 1 },
];
const velocityCommands = [];
let moveToStops = 0;
gimbal.getJointAngles = async () => jointSamples.shift();
gimbal._setVelocity = async command => velocityCommands.push(command);
gimbal._stop = async () => { moveToStops++; };
const moveResult = await gimbal.moveTo({ pan: 5, tilt: 5, roll: -4, toleranceDeg: 0.75 });
assert.equal(velocityCommands.length, 1);
assert(velocityCommands[0].pan > 0, "positive joint Yaw error should command positive Pan");
assert(velocityCommands[0].tilt < 0, "positive joint Pitch error should command negative Tilt");
assert(velocityCommands[0].roll < 0, "negative joint Roll error should command negative Roll");
assert.deepEqual(moveResult.current, { pan: 4.6, tilt: 4.5, roll: -3.5 });
assert.equal(moveToStops, 1, "moveTo must stop after reaching the target");

let releaseTelemetry;
let jointReadCount = 0;
gimbal.getJointAngles = async () => {
  jointReadCount++;
  if (jointReadCount === 1) return { pitch: 0, roll: 0, yaw: 0 };
  return new Promise(resolve => { releaseTelemetry = resolve; });
};
const cancelledMove = gimbal.moveTo({ pan: 20 });
await new Promise(resolve => setImmediate(resolve));
await assert.rejects(gimbal.setVelocity({ pan: 0.1 }), /cannot run while moveTo is active/);
await assert.rejects(
  gimbal.moveFor({ pan: 0.1, durationMs: 10 }),
  /moveFor cannot run while moveTo is active/,
);
assert.equal(gimbal.moveToActive, true, "a rejected moveFor must not cancel the active moveTo");
await gimbal.stop();
releaseTelemetry({ pitch: 0, roll: 0, yaw: 1 });
await assert.rejects(cancelledMove, error => error.code === "RS4MINI_MOVE_CANCELLED");

gimbal.getJointAngles = savedGetJointAngles;
gimbal._setVelocity = savedInternalSetVelocity;
gimbal._stop = savedInternalStop;

await gimbal.close();
assert.equal(gimbal.connected, false);
assert.equal(adapter.stopped, true);
console.log("cached connection, telemetry getters, closed-loop moveTo, and safe disconnect OK");

const scannedPeripheral = new FakePeripheral("SCANNED-RS4-MINI-ID", "disconnected");
const fallbackAdapter = new FakeAdapter(scannedPeripheral, new Error("stale cached ID"));
const fallback = new RS4Mini({ deviceId: "STALE-ID", adapter: fallbackAdapter });
assert.equal(await fallback.connect(), "DJI RS4 MINI-TEST");
assert.equal(fallbackAdapter.scanCount, 1, "failed direct connection should fall back to scan");
assert.equal(fallback.deviceId, scannedPeripheral.id, "successful scan should replace stale device ID");
await fallback.close();
console.log("stale cache scan fallback OK");

const pendingAdapter = new FakeAdapter(new FakePeripheral("NEVER-DISCOVERED"), null, false);
const pending = new RS4Mini({ adapter: pendingAdapter });
const connecting = pending.connect({ timeoutMs: 10_000 });
await new Promise(resolve => setImmediate(resolve));
await pending.close();
await assert.rejects(connecting, /cancelled by close/);
assert.equal(pendingAdapter.stopped, true);
console.log("pending scan cancellation on close OK");
