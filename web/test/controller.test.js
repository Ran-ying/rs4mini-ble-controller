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
    const {sourceStatusNotification} = await import('./node/src/app-source-status.js');
    const source=sourceStatusNotification({sender:4,receiver:2,commandSet:4,commandId:39,flags:0,payload:new Uint8Array([4,255,62,103,1])});
    assert.equal(source.sourceValues.isYawLocked,true);assert.equal(source.sourceValues.isGimbalLocked,false);assert.equal(source.sourceValues.getGimbalGravity,3);
    const {handheldStickNotification} = await import('./node/src/app-handheld-stick.js');
    const stick=handheldStickNotification({sender:4,receiver:2,commandSet:4,commandId:87,flags:0,payload:new Uint8Array([0,128,255,127,3,128])});
    assert.equal(stick.sourceStickX,-32768);assert.equal(stick.unknownStateBits,32768);assert.equal(stick.bodyHex,'0080ff7f0380');
    const app = await import('./node/src/app-protocol.js');
    assert.equal(app.parameterRequest([{ index: 150, size: 1 }])[0], 150);
    const reply = app.parameterReply({ sender: 4, receiver: 2, commandSet: 4, commandId: 16,
      flags: 128, raw: new Uint8Array(), payload: new Uint8Array([0,150,9,255]) }, [{index:150,size:1}]);
    assert.equal(reply.parameters[0].rawHex, 'ff');
    assert.equal(reply.parameters[0].headerByte, 9);
    assert(reply.message.payload instanceof Uint8Array);
    assert.deepEqual([...app.factoryResetSpec({sourcePlatform:'HG724'}).payload],[1,0,1]);
    const profiles=await import('./node/src/app-profile-values.js');assert.deepEqual([...profiles.profileValueWrite('userProfile',0).payload],[0,1,0]);assert.deepEqual([...profiles.profileValueWrite('workMode','Fpv').payload],[62,1,2]);
    const smooth=await import('./node/src/app-smooth-track.js');assert.deepEqual([...smooth.smoothTrackWrite({yaw:true,pitch:true,roll:true}).payload],[17,1,1,18,1,1,19,1,1]);
    const axisMode=await import('./node/src/app-axis-mode.js');assert.deepEqual([...axisMode.axisModeWrite({sourceMode:'ThreeDRoll360'}).payload],[34,1,24]);
    const settings = await import('./node/src/app-settings.js');
    assert.equal(settings.settingsWrite('motor', { enabled: true }, 255).payload[2], 254);
    const calibration = await import('./node/src/app-calibration.js');
    assert.equal(calibration.calibrationRecords(new Uint8Array([0,2,1,40])).state, 'Processing');
    const systemCalibration = await import('./node/src/app-system-calibration.js');
    assert.deepEqual([...systemCalibration.systemCalibrationPayload()], [36,1,1]);
    assert.equal(systemCalibration.systemCalibrationFields(255).state, null);
    const balance = await import('./node/src/app-balance.js');
    assert.deepEqual([...balance.balanceStartPayload()], [37,1,64]);
    assert.equal(balance.balanceFields(0).axisResults.yaw.result, null);
    const packedModes = await import('./node/src/app-settings.js');
    assert.deepEqual([...packedModes.settingsWrite('followSpeed',{yaw:'custom'},255).payload], [65,1,63]);
    const fine = await import('./node/src/app-fine-tune.js');
    assert.deepEqual([...fine.fineTuneSpec({axis:'pitch',adjustmentDegrees:-1.29}).payload],[244,2]);
    const handle = await import('./node/src/app-handle.js');
    assert.deepEqual([...handle.handleWriteSpec({setting:'panDirection',value:1}).payload],[255,255,1,255,255,255,255,255]);
    assert.equal(handle.handleReply({sender:4,receiver:2,commandSet:4,commandId:54,flags:128,payload:new Uint8Array([0,7,1,0,255,3,2,3,254])}).values[3].rawValue,255);
    const userParams = await import('./node/src/app-user-parameters.js');
    const fixed=new Uint8Array(74);fixed[9]=0x34;fixed[10]=0x12;
    assert.equal(userParams.userParameterNotification({sender:4,receiver:2,commandSet:4,commandId:36,flags:0,payload:fixed}).values.find(v=>v.sourceGetter==='getYawSpeed').rawValue,4660);
    const standalone = await import('./node/src/app-standalone.js');
    assert.deepEqual([...standalone.standaloneWrite({inputSource:2,axis:'pitch',parameter:'speed',value:100}).payload],[72,1,2,80,2,100,0]);
    const numeric = await import('./node/src/app-tuning.js');
    assert.deepEqual([...numeric.tuningWrite('follow',{axis:'pitch',parameter:'speed',value:100}).payload], [3,2,100,0]);
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

test('Web source stick candidate uses shared SDK cache and sends no control request',async t=>{
  const {gimbal,device}=setup();t.after(()=>gimbal.close());await gimbal.connect();
  const incoming=()=>{const data=frame(1,4,87,new Uint8Array([255,255,0,128,2,128,99]),0);data[4]=4;data[5]=2;new DataView(data.buffer,data.byteOffset,data.byteLength).setUint16(data.length-2,crc16(data.subarray(0,-2)),true);device.rx.notify(data);};
  incoming();assert.equal(gimbal.appCommands.handheldStickStatus,null);gimbal.appCommands.useProfile('ronin-2.2.2');incoming();
  assert.equal(gimbal.appCommands.handheldStickStatus.sourceStickX,-1);assert.equal(gimbal.appCommands.handheldStickStatus.sourceStickY,-32768);assert.equal(gimbal.appCommands.handheldStickStatus.sourceStickControlEnabled,true);assert.equal(device.tx.writes.length,0);assert.equal(gimbal.latestTelemetry,null);
  await gimbal.disconnect();assert.equal(gimbal.appCommands.handheldStickStatus,null);
});

test('Web source abnormal and battery candidates stay separate without commands',async t=>{
 const {gimbal,device}=setup();t.after(()=>gimbal.close());await gimbal.connect();gimbal.appCommands.useProfile('ronin-2.2.2');
 const incoming=(command,body)=>{const data=frame(1,4,command,new Uint8Array(body),0);data[4]=4;data[5]=2;new DataView(data.buffer,data.byteOffset,data.byteLength).setUint16(data.length-2,crc16(data.subarray(0,-2)),true);device.rx.notify(data);};
 incoming(39,[4,255,62,103,1,99]);incoming(51,[255,99]);assert.equal(gimbal.appCommands.abnormalStatus.sourceValues.isGimbalLocked,false);assert.equal(gimbal.appCommands.batteryStatus.rawCapacityValue,255);assert.equal(device.tx.writes.length,0);assert.equal(gimbal.latestTelemetry,null);assert.equal(gimbal.appCommands.handheldStickStatus,null);await gimbal.disconnect();assert.equal(gimbal.appCommands.abnormalStatus,null);assert.equal(gimbal.appCommands.batteryStatus,null);
});

test('Web program candidates use request bodies without Buffer or automatic subscription ACK',async t=>{
 const {gimbal,device}=setup();t.after(()=>gimbal.close());await gimbal.connect();
 const incoming=(command,body,flags=64)=>{const data=frame(1,4,command,new Uint8Array(body),flags);data[4]=4;data[5]=2;new DataView(data.buffer,data.byteOffset,data.byteLength).setUint16(data.length-2,crc16(data.subarray(0,-2)),true);device.rx.notify(data);};
 incoming(107,[0,98,4,1,2,3,4]);assert.equal(gimbal.appCommands.programStatus,null);gimbal.appCommands.useProfile('ronin-2.2.2');incoming(107,[1,254,0,55,4,252,254,255,128]);assert.equal(gimbal.appCommands.programStatus.records[1].sourceValues.status,4);incoming(56,[252,254,255,128]);assert.equal(gimbal.appCommands.programStatus.sourceValues.status,0);assert.equal(device.tx.writes.length,0);assert.equal(gimbal.latestTelemetry,null);await gimbal.disconnect();assert.equal(gimbal.appCommands.programStatus,null);
 execFileSync(process.execPath,['--input-type=module','-e',`globalThis.Buffer=undefined;const {programStatusNotification}=await import(${JSON.stringify(new URL('../../node/src/app-program-status.js',import.meta.url).href)});const r=programStatusNotification({sender:4,receiver:2,commandSet:4,commandId:107,flags:0,payload:new Uint8Array([0,98,4,255,1,2,3])});if(r.records[0].sourceValues.status!==255)throw Error('Buffer-free program decode failed');`]);
});


test('Web explicit single program request awaits ACK independently of passive status',async t=>{
 const {gimbal,device,window}=setup();t.after(()=>gimbal.close());await gimbal.connect();gimbal.appCommands.useProfile('ronin-2.2.2');
 const request=gimbal.appCommands.sendProgramStatusRequest({program:'track'});
 await until(()=>device.frames().some(f=>f.commandId===107));const outgoing=device.frames().find(f=>f.commandId===107);
 assert.equal(outgoing.payload.toString('hex'),'00020162');assert.equal(outgoing.flags,64);
 const incoming=(body,flags)=>{const data=frame(outgoing.sequence,4,107,new Uint8Array(body),flags);data[4]=4;data[5]=2;new DataView(data.buffer,data.byteOffset,data.byteLength).setUint16(data.length-2,crc16(data.subarray(0,-2)),true);device.rx.notify(data);};
 incoming([0,98,4,1,2,3,4],0);const before=gimbal.appCommands.programStatus;
 assert.equal(gimbal.experimental.pending.size,1);window.dispatchEvent(new Event('blur'));assert.equal(gimbal.experimental.pending.size,1);
 incoming([0,254],128);const reply=await request;assert.equal(reply.bodyHex,'fe');assert.equal(reply.requestedProgram,'track');assert.equal(reply.freshStatusVerified,false);assert.deepEqual(gimbal.appCommands.programStatus,before);
 assert.equal(device.frames().filter(f=>f.commandId===107).length,1);
 const pending=gimbal.appCommands.sendProgramStatusRequest({program:'panorama'});const rejected=assert.rejects(pending,{code:'RS4MINI_DISCONNECTED'});await until(()=>device.frames().filter(f=>f.commandId===107).length===2);await gimbal.disconnect();await rejected;
 execFileSync(process.execPath,['--input-type=module','-e',`globalThis.Buffer=undefined;const {programStatusRequestSpec}=await import(${JSON.stringify(new URL('../../node/src/app-program-request.js',import.meta.url).href)});if(programStatusRequestSpec('panorama').payload.join(',')!=='0,2,1,99')throw Error('Buffer-free request failed');`]);
});


test('Web explicit subscription requests never automatically stop restart or assert remote state',async t=>{
 const {gimbal,device,window}=setup();t.after(()=>gimbal.close());await gimbal.connect();gimbal.appCommands.useProfile('ronin-2.2.2');
 let count=0;
 for(const enabled of [true,false]){const pending=gimbal.appCommands.sendProgramStatusSubscriptionRequest({program:'track',enabled});++count;await until(()=>device.frames().filter(f=>f.commandId===107).length===count);const outgoing=device.frames().filter(f=>f.commandId===107).at(-1);assert.equal(outgoing.payload.toString('hex'),enabled?'00000162':'00010162');
 const incoming=(body,flags)=>{const data=frame(outgoing.sequence,4,107,new Uint8Array(body),flags);data[4]=4;data[5]=2;new DataView(data.buffer,data.byteOffset,data.byteLength).setUint16(data.length-2,crc16(data.subarray(0,-2)),true);device.rx.notify(data);};
 incoming([0,98,4,1,2,3,4],0);const before=gimbal.appCommands.programStatus;assert.equal(gimbal.experimental.pending.size,1);window.dispatchEvent(new Event('blur'));assert.equal(gimbal.experimental.pending.size,1);incoming([0,254],128);const reply=await pending;assert.equal(reply.requestedEnabled,enabled);assert.equal(reply.remoteSubscriptionStateVerified,false);assert.equal(reply.notificationStreamVerified,false);assert.equal(reply.bodyHex,'fe');assert.deepEqual(gimbal.appCommands.programStatus,before);}
 assert.equal(device.frames().filter(f=>f.commandId===107).length,2);await gimbal.disconnect();assert.equal(device.frames().filter(f=>f.commandId===107).length,2);
 execFileSync(process.execPath,['--input-type=module','-e',`globalThis.Buffer=undefined;const {programStatusSubscriptionSpec}=await import(${JSON.stringify(new URL('../../node/src/app-program-request.js',import.meta.url).href)});if(programStatusSubscriptionSpec('panorama',false).payload.join(',')!=='0,1,1,99')throw Error('Buffer-free subscription failed');`]);
});


test('Web peripheral source catalog retains collision views without Buffer or sends',async t=>{
 const {gimbal,device}=setup();t.after(()=>gimbal.close());await gimbal.connect();const incoming=()=>{const data=frame(3,4,102,new Uint8Array([1,21,1,100]),64);data[4]=4;data[5]=2;new DataView(data.buffer,data.byteOffset,data.byteLength).setUint16(data.length-2,crc16(data.subarray(0,-2)),true);device.rx.notify(data);};
 incoming();assert.equal(gimbal.appCommands.peripheralStatus,null);gimbal.appCommands.useProfile('ronin-2.2.2');incoming();const r=gimbal.appCommands.peripheralStatus.records[0];assert.equal(r.ambiguous,true);assert.deepEqual(r.sourceTypes,['YGyroOut','PAcceOut']);assert.deepEqual(r.sourceViews.map(v=>v.value),[1,10]);assert.equal(device.tx.writes.length,0);assert.equal(gimbal.latestTelemetry,null);await gimbal.disconnect();assert.equal(gimbal.appCommands.peripheralStatus,null);
 execFileSync(process.execPath,['--input-type=module','-e',`globalThis.Buffer=undefined;const {peripheralNotification}=await import(${JSON.stringify(new URL('../../node/src/app-peripheral.js',import.meta.url).href)});const r=peripheralNotification({sender:4,receiver:2,commandSet:4,commandId:102,flags:0,payload:new Uint8Array([1,21,1,100])});if(r.records[0].sourceViews.length!==2)throw Error('Buffer-free peripheral failed');`]);
});

test('Web named parameter subscription is explicit one-shot with no Buffer dependency',async t=>{
 const {gimbal,device}=setup();t.after(()=>gimbal.close());await gimbal.connect();gimbal.appCommands.useProfile('ronin-2.2.2');const result=await gimbal.appCommands.sendParameterSubscriptionRequest({keys:['UserProfile']});
 assert.deepEqual(device.frames().map(f=>f.commandId),[1,1,1,18]);const f=device.frames().at(-1);assert.equal(f.receiver,229);assert.equal(f.flags,0);assert.equal(f.payload.toString('hex'),'100001');assert.equal(result.notificationStreamVerified,false);assert.equal(gimbal.experimental.pending.size,0);
 execFileSync(process.execPath,['--input-type=module','-e',`globalThis.Buffer=undefined;const m=await import(${JSON.stringify(new URL('../../node/src/app-parameter-subscription.js',import.meta.url).href)});const spec=m.parameterSubscriptionSpec(['UserProfile']);const b=m.parameterSubscriptionFrame(1,spec);if(b[5]!==229||spec.requestBodyHex!=='100001')throw Error('Buffer-free frame failed');`]);
});

test('Web external-device passive cache is independent and Buffer-free',async t=>{
 const {gimbal,device}=setup();t.after(()=>gimbal.close());await gimbal.connect();const body=Buffer.from('0207010080ff7f0000','hex');
 const incoming=(payload=body,flags=0)=>{const b=frame(1,4,105,payload,flags);b[4]=4;b[5]=2;b.writeUInt16LE(crc16(b.subarray(0,-2)),b.length-2);device.rx.notify(b);};
 incoming();assert.equal(gimbal.appCommands.externalDeviceStatus,null);gimbal.appCommands.useProfile('ronin-2.2.2');incoming();const r=gimbal.appCommands.externalDeviceStatus;assert.equal(r.records[0].speedControl.sourcePitchSpeed,-32768);r.records[0].speedControl.sourcePitchSpeed=1;assert.equal(gimbal.appCommands.externalDeviceStatus.records[0].speedControl.sourcePitchSpeed,-32768);incoming(body,128);assert.equal(gimbal.appCommands.externalDeviceStatus.records[0].speedControl.sourcePitchSpeed,-32768);assert.equal(device.tx.writes.length,0);assert.equal(gimbal.latestTelemetry,null);await gimbal.disconnect();assert.equal(gimbal.appCommands.externalDeviceStatus,null);
 execFileSync(process.execPath,['--input-type=module','-e',`globalThis.Buffer=undefined;const {externalDeviceNotification}=await import(${JSON.stringify(new URL('../../node/src/app-external-device.js',import.meta.url).href)});const r=externalDeviceNotification({sender:4,receiver:2,commandSet:4,commandId:105,flags:0,payload:new Uint8Array([2,7,1,0,128,255,127,0,0])});if(r.records[0].speedControl.sourcePitchSpeed!==-32768)throw Error('Buffer-free external candidate failed');`]);
});
