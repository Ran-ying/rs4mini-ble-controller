import { RS4Mini } from './rs4mini.js';

export const gimbal = new RS4Mini();
const $ = selector => document.querySelector(selector);
const status = $('#status'), connectButton = $('#connect'), position = $('#position');
const controls = [...document.querySelectorAll('[data-axis]')];
let busy = false, starting = false, lastJoints = null, initialized = false;
const report = error => { status.textContent = error.code === 'RS4MINI_MOVE_CANCELLED' ? '运动已取消' : error.message; };
function enable() {
  for (const button of controls) button.disabled = !gimbal.connected || busy || starting;
  $('#center').disabled = !gimbal.connected || busy || starting;
  $('#useCurrent').disabled = !gimbal.connected || !lastJoints || busy;
  $('#move').disabled = !gimbal.connected || !lastJoints || busy;
  connectButton.disabled = starting;
  const ready = gimbal.connected && !busy && !starting;
  for (const id of ['runTrajectory', 'runExperimental', 'convertOrientation']) $('#' + id).disabled = !ready;
  $('#currentWaypoint').disabled = $('#saveHome').disabled = !ready || !lastJoints;
  $('#returnHome').disabled = !ready || !gimbal.home || gimbal.home.deviceId !== gimbal.deviceId;
}
function fillCurrent() {
  if (!lastJoints) return;
  for (const [axis, field] of [['pan', 'yaw'], ['tilt', 'pitch'], ['roll', 'roll']]) position.elements[axis].value = lastJoints[field].toFixed(2);
}
async function motion(action) {
  busy = true; enable();
  try { return await action(); } finally { busy = false; enable(); }
}
$('#speed').addEventListener('input', event => { $('#speedOut').value = Math.round(event.target.value * 100) + '%'; });
connectButton.addEventListener('click', async () => {
  starting = true; enable();
  try {
    if (gimbal.connected) { await gimbal.disconnect(); status.textContent = '已断开'; }
    else {
      const name = await gimbal.connect();
      status.textContent = '已连接 · ' + name;
      connectButton.textContent = '断开稳定器';
    }
  } catch (error) { report(error); }
  finally { starting = false; enable(); }
});
for (const button of controls) {
  let pointer = null;
  button.addEventListener('pointerdown', async event => {
    if (button.disabled || pointer !== null) return;
    event.preventDefault(); pointer = event.pointerId; button.setPointerCapture(pointer);
    const speed = Number($('#speed').value) * Number(button.dataset.sign);
    try { await gimbal.setVelocity({ [button.dataset.axis]: speed }); } catch (error) { report(error); }
  });
  const release = event => {
    if (pointer === null || event.pointerId !== pointer) return;
    pointer = null; gimbal.stop().catch(report);
  };
  for (const event of ['pointerup', 'pointercancel', 'lostpointercapture']) button.addEventListener(event, release);
}
$('#stop').addEventListener('click', async () => { try { await gimbal.stop(); status.textContent = '停止指令已发送'; } catch (error) { report(error); } });
$('#center').addEventListener('click', () => motion(() => gimbal.recenter()).then(() => { status.textContent = '三轴回中指令已发送'; }).catch(report));
$('#useCurrent').addEventListener('click', fillCurrent);
$('#autoReconnect').addEventListener('change', async event => {
  try {
    if (event.target.checked) gimbal.enableAutoReconnect(); else await gimbal.disableAutoReconnect();
  } catch (error) { report(error); }
});
$('#saveHome').addEventListener('click', async () => {
  try {
    const home = await gimbal.captureHome({ fresh: true });
    $('#homeState').textContent = `已保存 Pan ${home.pan.toFixed(2)}° · Tilt ${home.tilt.toFixed(1)}° · Roll ${home.roll.toFixed(1)}°`;
    enable();
  } catch (error) { report(error); }
});
$('#returnHome').addEventListener('click', () => {
  const axes = ['pan', 'tilt', 'roll'].filter(axis => position.elements[axis + 'On'].checked);
  motion(() => gimbal.moveHome({ axes })).then(() => { status.textContent = '选中轴已返回保存位置的容差范围'; }).catch(report);
});
$('#trajectoryFile').addEventListener('change', async event => {
  const file = event.target.files?.[0]; if (!file) return;
  try {
    const value = JSON.parse(await file.text());
    if (!Array.isArray(value)) throw new TypeError('轨迹文件必须是 JSON 数组');
    $('#trajectoryJson').value = JSON.stringify(value, null, 2);
    $('#trajectoryResult').textContent = '已载入 ' + file.name + '，尚未执行';
  } catch (error) { report(error); }
});
$('#currentWaypoint').addEventListener('click', () => {
  if (!lastJoints) return;
  $('#trajectoryMode').value = 'waypoints';
  $('#trajectoryJson').value = JSON.stringify([{ pan: lastJoints.yaw, tilt: lastJoints.pitch, roll: lastJoints.roll, holdMs: 0 }], null, 2);
  $('#trajectoryResult').textContent = '已生成当前路点，尚未执行';
});
$('#runTrajectory').addEventListener('click', async () => {
  if (busy || !gimbal.connected) return;
  try {
    const points = JSON.parse($('#trajectoryJson').value);
    const result = await motion(() => $('#trajectoryMode').value === 'waypoints' ? gimbal.moveThrough(points) :
      gimbal.runTrajectory(points, { interpolation: $('#interpolation').value || 'linear' }));
    $('#trajectoryResult').textContent = '流程结束并发送停止指令\n' + JSON.stringify(result, null, 2);
  } catch (error) { report(error); }
});
$('#convertOrientation').addEventListener('click', async () => {
  try {
    const value = await gimbal.getOrientation({ componentOrder: $('#quaternionOrder').value, conjugate: !!$('#quaternionConjugate').checked });
    $('#orientationResult').textContent = JSON.stringify(value, null, 2);
  } catch (error) { report(error); }
});
$('#runExperimental').addEventListener('click', async () => {
  if (busy || !gimbal.connected) return;
  try {
    const input = JSON.parse($('#experimentalJson').value);
    if (!input || typeof input !== 'object' || Array.isArray(input)) throw new TypeError('实验指令必须为 JSON 对象');
    const { profile, command, ...options } = input;
    if (!['observe', 'query', 'sleep', 'absolute', 'rate'].includes(command)) throw new TypeError('不支持此实验指令');
    if (command === 'observe' && Object.keys(options).length) throw new TypeError('observe 不能附带其他字段');
    gimbal.experimental.useProfile(profile);
    const result = await motion(() => {
      if (command === 'observe') return { profile, deviceVerified: false };
      if (command === 'query') return gimbal.experimental.query(options);
      if (command === 'sleep') return gimbal.experimental.setSleep(options);
      if (command === 'absolute') return gimbal.experimental.absolute(options);
      return gimbal.experimental.rateFor(options);
    });
    $('#experimentalResult').textContent = '实验结果 · 本机物理执行未验证\n' + JSON.stringify(result, null, 2);
  } catch (error) { report(error); }
});
position.addEventListener('submit', async event => {
  event.preventDefault(); if (busy || !gimbal.connected || !lastJoints) return;
  const target = {};
  for (const axis of ['pan', 'tilt', 'roll']) if (position.elements[axis + 'On'].checked) target[axis] = Number(position.elements[axis].value);
  try {
    const result = await motion(() => gimbal.moveTo(target));
    status.textContent = `目标已进入 ${result.toleranceDeg}° 容差，停止指令已发送`;
  } catch (error) { report(error); }
});
gimbal.onTelemetry = sample => {
  const format = value => `Pitch ${value.pitch.toFixed(1)}° · Roll ${value.roll.toFixed(1)}° · Yaw ${value.yaw.toFixed(2)}°`;
  $('#attitude').textContent = '姿态 · ' + format(sample.attitude);
  if (sample.jointAngles) {
    lastJoints = sample.jointAngles; $('#joints').textContent = '机械关节 · ' + format(lastJoints);
    if (!initialized) { fillCurrent(); initialized = true; }
    enable();
  }
};
gimbal.onDisconnect = () => {
  lastJoints = null; initialized = false; connectButton.textContent = '选择并连接稳定器';
  status.textContent = '连接已断开'; $('#attitude').textContent = '姿态 · 已断开'; $('#joints').textContent = '机械关节 · 已断开'; enable();
};
gimbal.onError = report;
gimbal.onReconnect = value => {
  $('#autoReconnect').checked = value.state !== 'disabled';
  const states = { disabled: '自动重连未启用', idle: '自动重连已启用', waiting: '等待重连', connecting: '正在重连', restored: '连接已恢复，运动未恢复', exhausted: '自动重连已耗尽，请手动检查设备' };
  $('#reconnectState').textContent = states[value.state] + (value.attempt ? ` · ${value.attempt}/5` : '');
  if (value.state === 'restored') connectButton.textContent = '断开稳定器';
  enable();
};
gimbal.onExperimentalStatus = value => { $('#experimentalResult').textContent = '被动实验状态 · 未验证\n' + JSON.stringify(value, null, 2); };
enable();
