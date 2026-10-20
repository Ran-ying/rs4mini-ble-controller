// Opt-in real Node device-SDK coverage; never imported by tests or CI.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import { BleDevice } from '../../node/src/device-node.js';
if (process.argv.includes('--help')) {
  console.log('RS4MINI_SDK_TEST=yes RS4MINI_ALLOW_SETTINGS=yes RS4MINI_DEVICE_ID=<local ID> node tools/hardware/sdk-node-continuous.mjs');
  process.exit(0);
}
if (process.env.RS4MINI_SDK_TEST !== 'yes' || process.env.RS4MINI_ALLOW_SETTINGS !== 'yes' || !process.env.RS4MINI_DEVICE_ID)
  throw Error('Explicit SDK test, authorized same-value settings batch and local device ID required');
const axes = ['pitch', 'roll', 'yaw'], t = { timeoutMs: 4000 };
const g = new BleDevice({ deviceId: process.env.RS4MINI_DEVICE_ID.replaceAll('-', '').toLowerCase() });
const a = g.appCommands, rows = [], counts = { notification: 0, message: 0, telemetry: 0, disconnect: 0, errors: 0, status: {} };
let passiveObserved = {};
const decoderSessions = [];
const caches = ['tutorialStatus', 'sensorCalibrationStatus', 'externalDeviceStatus', 'peripheralStatus', 'programStatus', 'abnormalStatus', 'batteryStatus', 'handheldStickStatus', 'userParameterStatus', 'calibrationStatus'];
const startedAt = new Date().toISOString(), capture = new URL('../../node/captures/node-continuous-' + Date.now() + '.jsonl', import.meta.url);
fs.mkdirSync(new URL('../../node/captures/', import.meta.url), { recursive: true });
const save = (type, data) => fs.appendFileSync(capture, JSON.stringify({ at: Date.now(), type, data }) + '\n');
g.onNotification = () => counts.notification++;
g.onMessage = m => { counts.message++; save('message', m); };
g.onTelemetry = () => counts.telemetry++;
g.onDisconnect = () => counts.disconnect++;
g.onError = e => { counts.errors++; save('error', { code: e.code, message: e.message }); };
g.onAppStatus = s => { counts.status[s.kind] = (counts.status[s.kind] || 0) + 1; save('status', s); };
async function check(name, fn) {
  const start = Date.now();
  try { const value = await fn(); save(name, { ok: true, value }); rows.push({ name, ok: true, elapsedMs: Date.now() - start }); console.error('PASS', name); return value; }
  catch (e) { save(name, { ok: false, code: e.code, message: e.message }); rows.push({ name, ok: false, elapsedMs: Date.now() - start, code: e.code || e.name }); console.error('FAIL', name, e.code || e.name); if (!g.connected) throw e; return null; }
}
function ack(r) { assert.equal(r.acknowledged, true); assert.equal(r.statusCode, 0); }
async function echo(name, read, write, key = r => r.rawValue) {
  return check(name, async () => {
    const before = await read(); save('backup.' + name, before);
    const response = await write(before); ack(response);
    const after = await read(); assert.deepEqual(key(after), key(before)); return { response, before, after };
  });
}
async function readValues(name, fn, count) {
  return check(name, async () => { const r = await fn(); assert.equal(r.values.length, count); return r; });
}
const connect = () => g.connect({ timeoutMs: 15000, directConnectTimeoutMs: 8000 });
try {
  await connect(); rows.push({ name: 'connect', ok: g.connected });
  await check('deviceLayerOnly', () => assert.equal(typeof g.moveTo, 'undefined'));
  a.useProfile('ronin-2.2.2');
  for (let i = 0; i < 3; i++) {
    await check('attitude.fresh.' + i, () => g.getAttitude({ fresh: true, timeoutMs: 3000 }));
    await check('joints.fresh.' + i, () => g.getJointAngles({ fresh: true, timeoutMs: 3000 }));
  }
  await check('attitude.cached', () => g.getAttitude());
  await check('joints.cached', () => g.getJointAngles());
  await check('telemetry.copy', () => { const r = g.latestTelemetry; const before = structuredClone(r); r.timestamp = -1; assert.deepEqual(g.latestTelemetry, before); });
  await check('setVelocity.zero', async () => { await g.setVelocity({ pan: 0, tilt: 0, roll: 0 }); assert.deepEqual(g.velocity, { pan: 0, tilt: 0, roll: 0 }); });
  await check('degreeInfo', () => g.requestDegreeInfo(t));
  for (const program of ['track', 'timelapse', 'panorama'])
    await check('program.single.' + program, async () => { const r = await a.sendProgramStatusRequest({ ...t, program }); ack(r); assert.equal(r.freshStatusVerified, false); return r; });
  // Only the already used source version. Other formats are not negotiated device support.
  await check('center.Ver1_1', async () => { const r = await a.getCenterActivationInfo({ ...t, sourceVersion: 'Ver1_1' }); ack(r); return r; });
  await check('readParameters.knownMixedWidths', async () => { const r = await a.readParameters({ ...t, parameters: [{ index: 150, size: 1 }, { index: 3, size: 2 }] }); assert.equal(r.parameters.length, 2); return r; });
  await echo('sensitivity.echo', () => a.getFollowSensitivity(t), b => a.setFollowSensitivity({ ...t, mode: b.mode }));
  await check('sensitivity.changeRestore', async () => {
    const b = await a.getFollowSensitivity(t); assert.ok([0, 1].includes(b.mode)); save('backup.sensitivity.change', b);
    try { ack(await a.setFollowSensitivity({ ...t, mode: 1 - b.mode })); assert.equal((await a.getFollowSensitivity(t)).rawValue, 1 - b.rawValue); }
    finally { ack(await a.setFollowSensitivity({ ...t, mode: b.mode })); assert.equal((await a.getFollowSensitivity(t)).rawValue, b.rawValue); }
    return { restored: true };
  });
  for (const [label, get, set, field] of [
    ['customFollow', 'getCustomFollowSettings', 'setCustomFollowSettings', 'settings'],
    ['motorSettings', 'getMotorSettings', 'setMotorSettings', 'settings'],
    ['axisMode', 'getAxisMode', 'sendAxisModeRequest', 'sourceMode'],
    ['userProfile', 'getUserProfile', 'sendUserProfileRequest', 'sourceProfileValue'],
    ['workMode', 'getWorkMode', 'sendWorkModeRequest', 'sourceMode'],
  ]) await echo(label + '.echo', () => a[get](t), b => a[set]({ ...t, ...(field === 'settings' ? b.settings : { [field]: field === 'sourceProfileValue' ? b.rawValue : b[field] }) }));
  await echo('smoothTrack.echo', () => a.getSmoothTrackAxes(t), b => {
    assert.ok(b.values.every(v => [0, 1].includes(v.rawValue)));
    return a.sendSmoothTrackAxesRequest({ ...t, axes: Object.fromEntries(b.values.map(v => [v.axis, v.rawValue === 1])) });
  }, b => b.values.map(v => v.rawValue));
  for (const axis of axes) await readValues('smoothTrack.' + axis, () => a.getSmoothTrackAxes({ ...t, axis }), 1);
  for (const [domain, parameters] of [['Follow', ['speed', 'acceleration', 'deadZone']], ['Rc', ['speed', 'deadZone', 'smoothing']]]) {
    for (const parameter of parameters)
      await echo(domain + '.mode.' + parameter, () => a['get' + domain + 'Settings']({ ...t, parameter }), b => a['set' + domain + 'Settings']({ ...t, parameter, ...b.settings }));
    await readValues(domain + '.all', () => a['get' + domain + 'Tuning'](t), 9);
    for (const axis of axes) await readValues(domain + '.axis.' + axis, () => a['get' + domain + 'Tuning']({ ...t, axis }), 3);
    for (const parameter of parameters) {
      await readValues(domain + '.parameter.' + parameter, () => a['get' + domain + 'Tuning']({ ...t, parameter }), 3);
      for (const axis of axes) await echo(domain + '.numeric.' + axis + '.' + parameter,
        () => a['get' + domain + 'Tuning']({ ...t, axis, parameter }),
        b => a['set' + domain + 'Tuning']({ ...t, axis, parameter, value: b.values[0].rawValue }), b => b.values.map(v => v.rawValue));
    }
  }
  await readValues('motor.all', () => a.getMotorTuning(t), 12);
  for (const axis of axes) await readValues('motor.axis.' + axis, () => a.getMotorTuning({ ...t, axis }), 4);
  for (const parameter of ['stiffness', 'strength', 'gyroFiltering', 'preControl']) {
    await readValues('motor.parameter.' + parameter, () => a.getMotorTuning({ ...t, parameter }), 3);
    for (const axis of axes) await echo('motor.numeric.' + axis + '.' + parameter,
      () => a.getMotorTuning({ ...t, axis, parameter }), b => a.setMotorTuning({ ...t, axis, parameter, value: b.values[0].rawValue }), b => b.values.map(v => v.rawValue));
  }
  await readValues('standalone.all', () => a.getStandaloneTuning(t), 6);
  for (const axis of axes) await readValues('standalone.axis.' + axis, () => a.getStandaloneTuning({ ...t, axis }), 2);
  for (const parameter of ['speed', 'smoothing']) {
    await readValues('standalone.parameter.' + parameter, () => a.getStandaloneTuning({ ...t, parameter }), 3);
    for (const axis of axes) await readValues('standalone.single.' + axis + '.' + parameter, () => a.getStandaloneTuning({ ...t, axis, parameter }), 1);
  }
  // Latest continuous non-calibration batch: echo all six existing values only when source is already2.
  for (const parameter of ['speed', 'smoothing']) for (const axis of axes)
    await echo('standalone.echo.' + axis + '.' + parameter, () => a.getStandaloneTuning({ ...t, axis, parameter }), b => {
      assert.equal(b.inputSourceRaw, 2); assert.equal(b.values[0].withinSourceRange, true);
      return a.setStandaloneTuning({ ...t, inputSource: 2, axis, parameter, value: b.values[0].rawValue });
    }, b => [b.inputSourceRaw, b.values[0].rawValue]);
  await check('callbacks', () => { assert.ok(counts.notification > 0 && counts.message > 0 && counts.telemetry > 0); assert.equal(counts.errors, 0); return counts; });
  passiveObserved = Object.fromEntries(caches.map(k => [k, a[k] !== null]));
  save('passiveObserved', passiveObserved);
  for (let round = 0; round < 3; round++) {
    await check('decoder.session.' + round, () => {
      const counters = { invalidFrames: g.decoder.invalidFrames, discardedBytes: g.decoder.discardedBytes };
      decoderSessions.push(counters); assert.deepEqual(counters, { invalidFrames: 0, discardedBytes: 0 });
    });
    await check('disconnect.' + round, async () => { await g.disconnect(); assert.equal(g.connected, false); assert.equal(g.latestTelemetry, null); for (const k of caches) assert.equal(a[k], null); });
    await connect();
    await check('reconnect.' + round, async () => { assert.equal(g.connected, true); assert.deepEqual(g.velocity, { pan: 0, tilt: 0, roll: 0 }); return g.getJointAngles({ fresh: true, timeoutMs: 3000 }); });
  }
  await check('autoReconnect.enableDisable', async () => { g.enableAutoReconnect({ maxAttempts: 2, initialDelayMs: 250, maxDelayMs: 500 }); assert.equal(g.reconnectState.state, 'idle'); await g.disableAutoReconnect(); assert.equal(g.reconnectState.state, 'disabled'); });
  await check('stop', () => g.stop());
  await check('decoder.finalSession', () => { assert.equal(g.decoder.invalidFrames, 0); assert.equal(g.decoder.discardedBytes, 0); });
  save('observedBeforeFinalClose', { passiveObserved, counts });
} catch (e) { rows.push({ name: 'session', ok: false, code: e.code || e.name }); save('sessionError', { code: e.code, message: e.message }); }
finally {
  try { await g.close(); assert.equal(g.connected, false); assert.equal(g.closed, true); rows.push({ name: 'close', ok: true }); }
  catch (e) { rows.push({ name: 'close', ok: false, code: e.code || e.name }); }
}
console.log(JSON.stringify({ port: 'node', sdkVersion: '0.7.38', entry: 'BleDevice', startedAt, finishedAt: new Date().toISOString(),
  exclusions: ['autotune start/stop', 'horizontal calibration', 'fine tune already tested', 'recenter outside small sweep', 'nonzero motion not repeated', 'other-model experimental writes', 'unnegotiated CENTER source versions'],
  rows, counts, passiveObserved, decoderSessions }, null, 2));
if (rows.some(r => !r.ok)) process.exitCode = 1;
