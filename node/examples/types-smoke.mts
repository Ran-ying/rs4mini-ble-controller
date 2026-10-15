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
}

const bytes = velocityFrame(1, { pan: 0.1 });
bytes.readUInt16LE(6);
const decoder = new DumlStreamDecoder();
for (const message of decoder.push(frame(1, 4, 5, bytes))) {
  console.log(decodeGimbalTelemetry(message)?.attitude.yaw);
}
void sampleConsumer;
