// Compile-only consumer example. Do not execute it as a hardware demo.
import {
  RS4Mini,
  DumlStreamDecoder,
  decodeGimbalTelemetry,
  frame,
  type MoveToResult,
} from "../src/index.js";
import { velocityFrame } from "../src/protocol.js";

async function sampleConsumer() {
  const gimbal = new RS4Mini({ rateHz: 15, deviceId: null, ioTimeoutMs: 3000 });
  gimbal.onNotification = packet => console.log(packet.toString("hex"));
  gimbal.onTelemetry = telemetry => console.log(telemetry.jointAngles?.yaw);
  gimbal.onMessage = async message => { console.log(message.payload.toString("hex")); };
  const operation: string | null = gimbal.activeOperation;
  void operation;
  await gimbal.connect({ timeoutMs: 1000 });
  gimbal.enableAutoReconnect({ maxAttempts: 3 });
  gimbal.onReconnect = state => { console.log(state.state, state.attempt); };
  const home = await gimbal.captureHome();
  await gimbal.moveHome({ axes: ['pan'], toleranceDeg: 1 });
  await gimbal.moveThrough([{ pan: home.pan, holdMs: 10 }], { timeoutMs: 1000 });
  const trajectory = await gimbal.runTrajectory([{ timeMs: 0 }, { timeMs: 10 }], { interpolation: 'smoothstep' });
  console.log(trajectory.skippedFrames, gimbal.trajectoryProgress?.kind);
  await gimbal.disableAutoReconnect();
  const orientation = await gimbal.getOrientation({ componentOrder: 'wxyz', fresh: true });
  console.log(orientation.euler.yaw, orientation.deviceConventionVerified);
  gimbal.experimental.useProfile('rs3');
  const version = await gimbal.experimental.query({ kind: 'version' });
  console.log(version.payload.toString('hex'));
  await gimbal.experimental.absolute({ pan: 2, parameterByte: 20, observeMs: 3000 });
  await gimbal.experimental.rateFor({ pan: 2, durationMs: 500 });
  await gimbal.experimental.setSleep({ asleep: true });
  gimbal.onExperimentalStatus = status => { console.log(status.kind, status.deviceVerified); };
  // @ts-expect-error experimental angle parameter has no assumed time unit
  await gimbal.experimental.absolute({ pan: 2 });
  // @ts-expect-error axis names are checked
  await gimbal.moveHome({ axes: ['yaw'] });
  // @ts-expect-error trajectory keyframes need timeMs
  await gimbal.runTrajectory([{ pan: 0 }]);
  const angles = await gimbal.getJointAngles({ fresh: true });
  const result: MoveToResult = await gimbal.moveTo({ pan: angles.yaw });
  const value: number = result.current.pan;
  await gimbal.moveFor({ durationMs: 1, pan: 0 });
  await gimbal.stop();
  gimbal.decoder.reset();
  await gimbal.close();
  return value;
const balanceStatus = await gimbal.appCommands.getBalanceTestStatus();
const balanceResult: 'PASS'|'MARGINAL'|'FAIL'|null = balanceStatus.balance.axisResults.yaw.result;
await gimbal.appCommands.sendBalanceTestRequest({timeoutMs:3000});
// @ts-expect-error balance stop value is not a documented operation
await gimbal.appCommands.sendBalanceTestRequest({value:0});
void balanceResult;

  const systemCalibration=await gimbal.appCommands.getAutoCalibrationStatus();
  const systemState:'DEFAULT'|'START'|'FAIL'|'SUCCESS'|null=systemCalibration.systemCalibration.state;
  await gimbal.appCommands.sendAutoCalibrationRequest();
  // @ts-expect-error no inferred abort or numeric action
  await gimbal.appCommands.sendAutoCalibrationRequest({start:false});
  void systemState;

  await gimbal.appCommands.setFollowSettings({parameter:'speed',yaw:'low'});
  await gimbal.appCommands.getRcSettings({parameter:'smoothing'});
  // @ts-expect-error axis update is required
  await gimbal.appCommands.setRcSettings({parameter:'speed'});
  // @ts-expect-error no raw values or guessed modes
  await gimbal.appCommands.setFollowSettings({parameter:'speed',yaw:1});

  await gimbal.appCommands.setFollowTuning({axis:'pitch',parameter:'speed',value:100});
  await gimbal.appCommands.getRcTuning({parameter:'smoothing'});
  // @ts-expect-error tuning takes raw integer values, not mode names
  await gimbal.appCommands.setRcTuning({axis:'yaw',parameter:'speed',value:'low'});
  // @ts-expect-error standalone create fields are not ordinary tuning selectors
  await gimbal.appCommands.getRcTuning({parameter:'gimbal_create_max_speed_yaw'});

  await gimbal.appCommands.setStandaloneTuning({inputSource:2,axis:'pitch',parameter:'smoothing',value:20});
  const standalone = await gimbal.appCommands.getStandaloneTuning();
  const inputSourceRaw:number=standalone.inputSourceRaw;void inputSourceRaw;
  // @ts-expect-error explicit input source is required because the request changes it
  await gimbal.appCommands.setStandaloneTuning({axis:'pitch',parameter:'speed',value:20});

}

const bytes = velocityFrame(1, { pan: 0.1 });
bytes.readUInt16LE(6);
const decoder = new DumlStreamDecoder();
for (const message of decoder.push(frame(1, 4, 5, bytes))) {
  console.log(decodeGimbalTelemetry(message)?.attitude.yaw);
}
void sampleConsumer;

// Device SDK is deliberately narrower than the application entry.
import { BleDevice } from "../src/device-node.js";
const device = new BleDevice();
void device.requestDegreeInfo({ timeoutMs: 100 });
void RS4Mini.prototype.requestDegreeInfo;
// @ts-expect-error position control belongs to the application wrapper
void device.moveTo({ pan: 1 });
// @ts-expect-error trajectories belong to the application wrapper
void device.runTrajectory([]);

// Parameter research records remain tagged raw values or per-record errors.
import type { ResearchStatus as ParameterResearchStatus } from '../src/index.js';
const consumeParameterReport = (status: ParameterResearchStatus) => {
  if (status.kind === 'user-parameters') {
    for (const record of status.parameters) {
      if ('index' in record) console.log(record.index, record.size, record.rawHex);
      else console.log(record.errorCode);
    }
  } else if (status.kind === 'user-parameter-ack') console.log(status.statusCode);
};
void consumeParameterReport;


async function currentAppCommands() {
  const { RS4Mini } = await import('../src/index.js');
  const gimbal = new RS4Mini();
  gimbal.appCommands.useProfile('ronin-2.2.2');
  const reading = await gimbal.appCommands.getFollowSensitivity({ timeoutMs: 1000 });
  const mode: 0 | 1 | null = reading.mode;
  await gimbal.appCommands.setFollowSensitivity({ mode: 1 });
  await gimbal.appCommands.readParameters({ parameters: [{ index: 150, size: 1 }] });
  // @ts-expect-error source setter only accepts its two supported enum modes
  await gimbal.appCommands.setFollowSensitivity({ mode: 2 });
  // @ts-expect-error unsupported scalar width
  await gimbal.appCommands.readParameters({ parameters: [{ index: 150, size: 3 }] });
  return mode;
}
void currentAppCommands;

async function sourceSettingsTypes(gimbal: RS4Mini) {
  const flags = await gimbal.appCommands.getMotorSettings();
  const enabled: boolean = flags.settings.enabled;
  const raw: number = flags.unknownBits;
  await gimbal.appCommands.setCustomFollowSettings({ yaw: true });
  await gimbal.appCommands.setMotorSettings({ enabled: false, forbidVertical: true });
  // @ts-expect-error at least one named setting is required
  await gimbal.appCommands.setMotorSettings({ timeoutMs: 1000 });
  // @ts-expect-error no PF preset is inferred from bitfields
  await gimbal.appCommands.setCustomFollowSettings({ preset: 'PF' });
  // @ts-expect-error booleans are required
  await gimbal.appCommands.setMotorSettings({ roll360: 1 });
  return [enabled, raw];
}

async function calibrationTypes(gimbal: RS4Mini) {
  gimbal.onAppStatus = status => { if(status.kind==='calibration') {const raw:number|null=status.rawState;console.log(raw);} else {const raw:number=status.preset.rawValue;console.log(raw);} };
  const fine=await gimbal.appCommands.sendFineTuneRequest({axis:'pitch',adjustmentDegrees:-.1});
  const tenths:number=fine.encodedTenths;void tenths;
  // @ts-expect-error yaw source action is not established
  await gimbal.appCommands.sendFineTuneRequest({axis:'yaw',adjustmentDegrees:.1});
  const handle=await gimbal.appCommands.getHandleSettings();
  const handleRaw:number=handle.values[0].rawValue;void handleRaw;
  const parameters=gimbal.appCommands.userParameterStatus;void parameters;
  const sent = await gimbal.appCommands.sendAutoTuneRequest({start: false});
  const noAck: false = sent.acknowledged;
  const status = await gimbal.appCommands.queryCalibrationStatus();
  const percent: number | null = status.calibration.percent;
  // @ts-expect-error no numeric action or implicit coercion
  await gimbal.appCommands.sendAutoTuneRequest({start: 1});
  return [noAck, percent];
}

async function motorTuningTypes(gimbal: RS4Mini) {
  const read=await gimbal.appCommands.getMotorTuning({axis:'yaw'});
  const raw: number=read.values[0].rawValue;
  await gimbal.appCommands.setMotorTuning({axis:'roll',parameter:'stiffness',value:50});
  // @ts-expect-error motor axis names are source pitch/roll/yaw, not virtual-stick pan
  await gimbal.appCommands.getMotorTuning({axis:'pan'});
  // @ts-expect-error no guessed motor parameter names
  await gimbal.appCommands.setMotorTuning({axis:'yaw',parameter:'speed',value:50});
  return raw;
}

async function handleWriteTypes(gimbal: RS4Mini) {
void gimbal.appCommands.sendHandleSettingRequest({setting:'panDirection',value:1});
// @ts-expect-error excluded raw value
void gimbal.appCommands.sendHandleSettingRequest({setting:'panDirection',value:255});
// @ts-expect-error excluded camera setting
void gimbal.appCommands.sendHandleSettingRequest({setting:'zoom2Speed',value:1});

}
