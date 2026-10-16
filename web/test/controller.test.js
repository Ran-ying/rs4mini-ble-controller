import assert from 'node:assert/strict';
import test from 'node:test';
import { execFileSync } from 'node:child_process';
import { RS4Mini, velocityFrame } from '../rs4mini.js';
import { frame, crc16 } from '../../node/src/protocol.js';
import { DumlStreamDecoder } from '../../node/src/telemetry.js';
import { gate, until } from '../../node/test/fakes.js';

class Characteristic extends EventTarget {
  constructor() { super(); this.writes = []; this.starts = 0; this.stops = 0; }
  async startNotifications() { this.starts++; }
  async stopNotifications() { this.stops++; }
  async writeValueWithoutResponse(value) { this.writes.push(new Uint8Array(value)); }
  notify(value) {
    this.value = new DataView(value.buffer, value.byteOffset, value.byteLength);
    this.dispatchEvent(new Event('characteristicvaluechanged'));
  }
}
class Device extends EventTarget {
  constructor() {
    super(); this.id = 'WEB-TEST-ID'; this.name = 'DJI RS4 MINI-TEST'; this.rx = new Characteristic(); this.tx = new Characteristic();
    this.gatt = {
      connected: false,
      connect: async () => { this.gatt.connected = true; return this.gatt; },
      disconnect: () => { this.gatt.connected = false; this.dispatchEvent(new Event('gattserverdisconnected')); },
      getPrimaryService: async uuid => { assert.equal(uuid, 0xfff0); return { getCharacteristic: async id => id === 0xfff4 ? this.rx : this.tx }; },
    };
  }
  telemetry(yaw = 0) { const payload = Buffer.alloc(49); payload.writeInt16LE(Math.round(yaw * 100), 16); this.rx.notify(frame(1, 4, 5, payload)); }
  frames() { return new DumlStreamDecoder().push(Buffer.concat(this.tx.writes)); }
}
function setup() {
  const device = new Device(), document = new EventTarget(), window = new EventTarget();
  let selections = 0;
  const bluetooth = { requestDevice: () => { selections++; return Promise.resolve(device); } };
  const gimbal = new RS4Mini({ bluetooth, document, window, rateHz: 1000, ioTimeoutMs: 30 });
  return { device, document, window, gimbal, selections: () => selections };
}
test('Web requests selection in the calling click stack and reads copied telemetry', async t => {
  const { gimbal, device, selections } = setup(); t.after(() => gimbal.close());
  const connecting = gimbal.connect(); assert.equal(selections(), 1); await connecting;
  const reading = gimbal.getJointAngles({ fresh: true }); device.telemetry(12.34);
  assert.equal((await reading).yaw, 12.34);
  await gimbal.disconnect(); await gimbal.connect(); assert.equal(selections(), 1);
  assert.equal(device.rx.starts, 2); assert.equal(device.rx.stops, 1);
});
test('Web adapter serializes GATT chunks and cancels duration motion on blur', async t => {
  const { gimbal, device, window } = setup(); t.after(() => gimbal.close()); await gimbal.connect();
  const motion = gimbal.moveFor({ pan: 0.1, durationMs: 10000 });
  const cancelled = assert.rejects(motion, { code: 'RS4MINI_MOVE_CANCELLED' });
  await until(() => gimbal.streamPromise); window.dispatchEvent(new Event('blur'));
  await cancelled; assert.deepEqual(gimbal.velocity, { pan: 0, tilt: 0, roll: 0 });
  const last = device.frames().slice(-3); assert.equal(last.length, 3);
  for (const item of last) assert.equal(item.payload.readInt16LE(4), 1024);
});
test('Web notification decoding and position loop use the common implementation', async t => {
  const { gimbal, device } = setup(); t.after(() => gimbal.close()); await gimbal.connect();
  const motion = gimbal.moveTo({ pan: 5 }); device.telemetry();
  await until(() => device.frames().some(item => item.payload.readInt16LE(4) > 1024));
  await until(() => gimbal.telemetryWaiters.size > 0); device.telemetry(4.6);
  assert.equal((await motion).current.pan, 4.6);
});
test('Web unexpected disconnect cancels a reader and reconnect has no stale notification callback', async t => {
  const { gimbal, device } = setup(); t.after(() => gimbal.close()); await gimbal.connect();
  const read = gimbal.getAttitude({ fresh: true }); const rejected = assert.rejects(read, { code: 'RS4MINI_DISCONNECTED' });
  device.gatt.disconnect(); await rejected; await gimbal.connect();
  let samples = 0; gimbal.onTelemetry = () => samples++;
  device.telemetry(); assert.equal(samples, 1);
});
test('Web timeout while the chooser is open cannot connect a late selection', async () => {
  const selection = gate(), device = new Device();
  const gimbal = new RS4Mini({ bluetooth: { requestDevice: () => selection.promise }, ioTimeoutMs: 20 });
  await assert.rejects(gimbal.connect({ timeoutMs: 20 }), { code: 'RS4MINI_CONNECT_TIMEOUT' });
  selection.resolve(device); await gimbal.close(); assert.equal(device.gatt.connected, false);
});
test('Web invalid options do not open a chooser; positional encoder stays compatible', async () => {
  const { gimbal, selections } = setup();
  await assert.rejects(gimbal.connect({ timeoutMs: -1 }), /greater than 0/);
  assert.equal(selections(), 0); await gimbal.close();
  assert.equal(velocityFrame(256).toString('hex'), '551604fc020400010004010004000400040000027705');
});
test('a failed selection can be retried from a new click without retaining the wrong device', async () => {
  const { gimbal, device, selections } = setup();
  device.name = 'Other DJI device';
  await assert.rejects(gimbal.connect({ timeoutMs: 15 }), { code: 'RS4MINI_CONNECT_TIMEOUT' });
  device.name = 'DJI RS4 MINI-TEST';
  await gimbal.connect(); assert.equal(selections(), 2); await gimbal.close();
});
test('a chooser result from a timed-out attempt cannot satisfy a newer scan', async () => {
  const first = gate(), second = gate(), oldDevice = new Device(), newDevice = new Device();
  newDevice.id = 'NEW-WEB-TEST'; let calls = 0;
  const gimbal = new RS4Mini({ bluetooth: { requestDevice: () => ++calls === 1 ? first.promise : second.promise }, ioTimeoutMs: 30 });
  await assert.rejects(gimbal.connect({ timeoutMs: 15 }), { code: 'RS4MINI_CONNECT_TIMEOUT' });
  const connecting = gimbal.connect(); first.resolve(oldDevice); second.resolve(newDevice); await connecting;
  assert.equal(gimbal.deviceId, newDevice.id); assert.equal(oldDevice.gatt.connected, false); await gimbal.close();
});
test('protocol, telemetry and controller import without Node Buffer or Node modules', () => {
  execFileSync(process.execPath, ['--input-type=module', '-e', `
    import assert from 'node:assert/strict';
    globalThis.Buffer = undefined;
    const protocol = await import('./node/src/protocol.js');
    const { DumlStreamDecoder, decodeGimbalTelemetry } = await import('./node/src/telemetry.js');
    const { RS4Mini } = await import('./node/src/controller.js');
    const stop = protocol.stopFrame(256);
    assert.equal([...stop].map(x => x.toString(16).padStart(2, '0')).join(''), '551604fc020400010004010004000400040000027705');
    const payload = new Uint8Array(49); new DataView(payload.buffer).setInt16(16, 1234, true);
    const packet = protocol.frame(1, 4, 5, payload);
    const decoder = new DumlStreamDecoder(); assert.equal(decoder.push(packet.subarray(0, 20)).length, 0);
    assert.equal(decodeGimbalTelemetry(decoder.push(packet.subarray(20))[0]).jointAngles.yaw, 12.34);
    const app = await import('./node/src/app-protocol.js');
    assert.equal(app.parameterRequest([{ index: 150, size: 1 }])[0], 150);
    const reply = app.parameterReply({ sender: 4, receiver: 2, commandSet: 4, commandId: 16,
      flags: 128, raw: new Uint8Array(), payload: new Uint8Array([0,150,9,255]) }, [{index:150,size:1}]);
    assert.equal(reply.parameters[0].rawHex, 'ff');
    assert.equal(reply.parameters[0].headerByte, 9);
    assert(reply.message.payload instanceof Uint8Array);
    const settings = await import('./node/src/app-settings.js');
    assert.equal(settings.settingsWrite('motor', { enabled: true }, 255).payload[2], 254);
    const calibration = await import('./node/src/app-calibration.js');
    assert.equal(calibration.calibrationRecords(new Uint8Array([0,2,1,40])).state, 'Processing');
    const motor = await import('./node/src/app-motor.js');
    assert.equal(motor.motorWrite({axis:'roll',parameter:'stiffness',value:50}).payload[0], 1);
    assert.equal(typeof RS4Mini, 'function');
  `], { cwd: new URL('../../', import.meta.url), stdio: 'pipe' });
});
test('Web automatic retries reuse the selected device without opening a chooser', async t => {
  const { gimbal, device, selections } = setup(); t.after(() => gimbal.close()); await gimbal.connect();
  let attempts = 0;
  device.gatt.connect = async () => { if (++attempts === 1) throw new Error('temporary failure'); device.gatt.connected = true; return device.gatt; };
  gimbal.enableAutoReconnect({ initialDelayMs: 2, maxDelayMs: 5, maxAttempts: 3, timeoutMs: 20, directConnectTimeoutMs: 5 });
  device.gatt.disconnect(); await until(() => gimbal.reconnectState.state === 'restored');
  assert.equal(selections(), 1); assert.equal(gimbal.connected, true);
  assert.equal(gimbal.device, device); assert(device.rx.starts >= 2);
});
test('Web blur cancels a shared velocity trajectory and sends only neutrals afterward', async t => {
  const { gimbal, device, window } = setup(); t.after(() => gimbal.close()); await gimbal.connect();
  const motion = gimbal.runTrajectory([{ timeMs: 0, pan: 0.1 }, { timeMs: 1000, pan: 0.1 }]);
  const rejected = assert.rejects(motion, { code: 'RS4MINI_MOVE_CANCELLED' });
  await until(() => device.frames().length > 0); window.dispatchEvent(new Event('blur')); await rejected;
  assert.equal(gimbal.activeOperation, null); assert.equal(gimbal.trajectoryProgress, null);
  for (const item of device.frames().slice(-3)) assert.equal(item.payload.readInt16LE(4), 1024);
});


test('Web current-App parameter SDK shares GATT connection and stops pending config on blur', async t => {
  const { gimbal, device, window } = setup(); t.after(() => gimbal.close()); await gimbal.connect();
  gimbal.appCommands.useProfile('ronin-2.2.2');
  const read = gimbal.appCommands.getFollowSensitivity();
  await until(() => device.frames().some(f => f.commandId === 0x10));
  const request = device.frames().find(f => f.commandId === 0x10);
  assert.equal(request.payload.toString('hex'), '96');
  const response = frame(request.sequence,4,0x10,new Uint8Array([0,150,1,1]),0x80);
  response[4]=4; response[5]=2; new DataView(response.buffer,response.byteOffset).setUint16(response.length-2,crc16(response.subarray(0,-2)),true);
  device.rx.notify(response); assert.equal((await read).mode,1);
  const write = gimbal.appCommands.setFollowSensitivity({ mode:0 });
  const cancelled = assert.rejects(write,{ code:'RS4MINI_OPERATION_CANCELLED' });
  await until(() => device.frames().some(f => f.commandId === 0x0f));
  window.dispatchEvent(new Event('blur')); await cancelled;
  assert.equal(gimbal.experimental.pending.size,0); assert.equal(gimbal.activeOperation,null);
});
test('Web blur cancels an auto-tune preamble before any firmware request', async t => {
  const {gimbal,device,window}=setup(); t.after(()=>gimbal.close()); await gimbal.connect();
  gimbal.appCommands.useProfile('ronin-2.2.2');
  const blocked=gate(), started=gate(), original=device.tx.writeValueWithoutResponse.bind(device.tx);
  let first=true;
  device.tx.writeValueWithoutResponse=async value=>{
    if(first) {first=false;started.resolve();await blocked.promise;}
    return original(value);
  };
  const rejected=assert.rejects(gimbal.appCommands.sendAutoTuneRequest({start:true}),{code:'RS4MINI_OPERATION_CANCELLED'});
  await started.promise; window.dispatchEvent(new Event('blur')); blocked.resolve(); await rejected;
  assert.equal(device.frames().filter(f=>f.commandId===0x6a).length,0);
  assert.equal(gimbal.activeOperation,null);
});
