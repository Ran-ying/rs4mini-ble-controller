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
  const gimbal = new RS4Mini({ rateHz: 15, deviceId: null });
  gimbal.onNotification = packet => console.log(packet.toString("hex"));
  gimbal.onTelemetry = telemetry => console.log(telemetry.jointAngles?.yaw);
  await gimbal.connect({ timeoutMs: 1000 });
  const angles = await gimbal.getJointAngles({ fresh: true });
  const result: MoveToResult = await gimbal.moveTo({ pan: angles.yaw });
  const value: number = result.current.pan;
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
