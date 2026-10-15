import assert from 'node:assert/strict';
import test from 'node:test';
import { gate, until } from '../../node/test/fakes.js';

// Exercise the real page event handlers without a display, permission chooser or BLE.
class Element extends EventTarget {
  constructor() { super(); this.disabled = false; this.value = ''; this.textContent = ''; this.dataset = {}; }
  setPointerCapture() {}
}
test('page initializes disabled, maps feedback, owns position UI and resets on disconnect', async t => {
  const document = new EventTarget(), window = new EventTarget();
  const nodes = Object.fromEntries(['status', 'connect', 'position', 'speed', 'speedOut', 'center', 'useCurrent', 'move', 'stop', 'attitude', 'joints',
    'autoReconnect', 'reconnectState', 'saveHome', 'returnHome', 'homeState', 'trajectoryMode', 'trajectoryFile', 'trajectoryJson', 'interpolation',
    'currentWaypoint', 'runTrajectory', 'trajectoryResult', 'quaternionOrder', 'quaternionConjugate', 'convertOrientation', 'orientationResult',
    'experimentalJson', 'runExperimental', 'experimentalResult'].map(id => [id, new Element()]));
  const controls = [new Element(), new Element()];
  controls[0].dataset = { axis: 'pan', sign: '1' }; controls[1].dataset = { axis: 'tilt', sign: '-1' };
  nodes.position.elements = {};
  for (const axis of ['pan', 'tilt', 'roll']) {
    nodes.position.elements[axis] = new Element(); nodes.position.elements[axis + 'On'] = new Element();
    nodes.position.elements[axis + 'On'].checked = axis === 'pan';
  }
  document.querySelector = selector => nodes[selector.slice(1)]; document.querySelectorAll = () => controls;
  globalThis.document = document; globalThis.window = window;
  const { gimbal } = await import('../controller.js'); t.after(() => gimbal.close());
  assert(controls.every(button => button.disabled)); assert.equal(nodes.move.disabled, true);
  let connected = false;
  Object.defineProperty(gimbal, 'connected', { get: () => connected });
  gimbal.connect = async () => { connected = true; return 'Test device'; };
  gimbal.disconnect = async () => { gimbal._cancelReconnect(); connected = false; gimbal.onDisconnect(); };
  nodes.connect.dispatchEvent(new Event('click'));
  await until(() => nodes.connect.textContent === '断开稳定器'); assert(controls.every(button => !button.disabled));
  assert.equal(nodes.move.disabled, true);
  gimbal.onTelemetry({ attitude: { pitch: 180, roll: 0, yaw: 2 }, jointAngles: { pitch: -1, roll: 0.3, yaw: 12.34 } });
  assert.equal(nodes.position.elements.pan.value, '12.34'); assert.equal(nodes.move.disabled, false);
  assert.match(nodes.joints.textContent, /12.34/);
  nodes.position.elements.pan.value = '15';
  const block = gate(); let target;
  gimbal.moveTo = async options => { target = options; await block.promise; return { toleranceDeg: 1 }; };
  nodes.position.dispatchEvent(new Event('submit', { cancelable: true }));
  assert.deepEqual(target, { pan: 15 }); assert.equal(nodes.move.disabled, true); assert(controls.every(button => button.disabled));
  block.resolve(); await until(() => !nodes.move.disabled); assert.match(nodes.status.textContent, /容差/);
  nodes.autoReconnect.checked = true; nodes.autoReconnect.dispatchEvent(new Event('change'));
  assert.equal(gimbal.reconnectState.state, 'idle'); assert.match(nodes.reconnectState.textContent, /已启用/);
  gimbal.deviceId = 'PAGE-TEST';
  gimbal.captureHome = async options => { assert.equal(options.fresh, true); gimbal._home = { pan: 12.34, tilt: -1, roll: .3, deviceId: gimbal.deviceId }; return gimbal.home; };
  nodes.saveHome.dispatchEvent(new Event('click')); await until(() => !nodes.returnHome.disabled);
  assert.match(nodes.homeState.textContent, /12.34/);
  let returnedAxes;
  gimbal.moveHome = async options => { returnedAxes = options.axes; };
  nodes.returnHome.dispatchEvent(new Event('click')); await until(() => !nodes.move.disabled);
  assert.deepEqual(returnedAxes, ['pan']);
  const trajectoryBlock = gate(); let timeline;
  gimbal.runTrajectory = async (points, options) => { timeline = { points, options }; await trajectoryBlock.promise; return { sentFrames: 2 }; };
  nodes.trajectoryMode.value = 'velocity'; nodes.interpolation.value = 'smoothstep';
  nodes.trajectoryJson.value = '[{"timeMs":0,"pan":0.05},{"timeMs":100,"pan":0}]';
  nodes.runTrajectory.dispatchEvent(new Event('click'));
  assert.equal(timeline.options.interpolation, 'smoothstep'); assert.equal(nodes.runTrajectory.disabled, true); assert(controls.every(button => button.disabled));
  trajectoryBlock.resolve(); await until(() => !nodes.runTrajectory.disabled); assert.match(nodes.trajectoryResult.textContent, /sentFrames/);
  nodes.currentWaypoint.dispatchEvent(new Event('click'));
  assert.equal(nodes.trajectoryMode.value, 'waypoints'); assert.equal(JSON.parse(nodes.trajectoryJson.value)[0].pan, 12.34);
  let waypoints;
  gimbal.moveThrough = async points => { waypoints = points; return [{ target: points[0] }]; };
  nodes.runTrajectory.dispatchEvent(new Event('click')); await until(() => !nodes.runTrajectory.disabled); assert.equal(waypoints[0].tilt, -1);
  nodes.trajectoryFile.files = [{ name: 'sample.json', text: async () => '[{"pan":3}]' }];
  nodes.trajectoryFile.dispatchEvent(new Event('change')); await until(() => nodes.trajectoryResult.textContent.includes('sample.json'));
  assert.deepEqual(JSON.parse(nodes.trajectoryJson.value), [{ pan: 3 }]); assert.match(nodes.trajectoryResult.textContent, /尚未执行/);
  nodes.experimentalJson.value = '{"profile":"rs3","command":"observe"}';
  nodes.runExperimental.dispatchEvent(new Event('click')); await until(() => !nodes.runExperimental.disabled);
  assert.equal(gimbal.experimental.profile, 'rs3'); assert.match(nodes.experimentalResult.textContent, /deviceVerified/);
  nodes.experimentalJson.value = '{"profile":"rs3","command":"calibrate"}';
  nodes.runExperimental.dispatchEvent(new Event('click')); await until(() => nodes.status.textContent.includes('不支持'));
  let convention;
  gimbal.getOrientation = async options => { convention = options; return { euler: { yaw: 90 }, deviceConventionVerified: false }; };
  nodes.quaternionOrder.value = 'xyzw'; nodes.quaternionConjugate.checked = true;
  nodes.convertOrientation.dispatchEvent(new Event('click')); await until(() => nodes.orientationResult.textContent.includes('deviceConventionVerified'));
  assert.deepEqual(convention, { componentOrder: 'xyzw', conjugate: true });
  gimbal.setVelocity = async () => { throw new Error('controlled write error'); };
  nodes.speed.value = '0.1'; const down = new Event('pointerdown', { cancelable: true }); down.pointerId = 1;
  controls[0].dispatchEvent(down); await until(() => nodes.status.textContent === 'controlled write error');
  nodes.connect.dispatchEvent(new Event('click')); await until(() => !connected && nodes.connect.textContent === '选择并连接稳定器');
  assert(controls.every(button => button.disabled)); assert.equal(nodes.move.disabled, true); assert.match(nodes.joints.textContent, /已断开/);
  assert.equal(nodes.runTrajectory.disabled, true); assert.equal(nodes.runExperimental.disabled, true); assert.equal(nodes.autoReconnect.checked, false);
});
