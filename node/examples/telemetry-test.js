import assert from "node:assert/strict";
import { frame } from "../src/protocol.js";
import {
  DumlStreamDecoder,
  decodeGimbalTelemetry,
  decodeGimbalPositionCandidate,
  parseDumlFrame,
} from "../src/telemetry.js";

const payload = Buffer.alloc(49);
payload.writeInt16LE(-123, 0);
payload.writeInt16LE(45, 2);
payload.writeInt16LE(901, 4);
payload[6] = 0x40;
payload.writeInt8(-3, 7);
payload.writeInt16LE(-890, 8);
payload[10] = 0x04;
payload[11] = 0x01;
payload.writeInt16LE(-8765, 16);
payload.writeInt16LE(-35, 20);
payload.writeInt16LE(27, 22);
[0.5, -0.5, 0.5, -0.5].forEach((value, index) => payload.writeFloatLE(value, 24 + index * 4));

const packet = frame(0x1234, 0x04, 0x05, payload);
const parsed = parseDumlFrame(packet);
parsed.receivedAt = 1_700_000_000_000;
assert.equal(parsed.commandSet, 0x04);
assert.equal(parsed.commandId, 0x05);
assert.equal(parsed.sequence, 0x1234);

const telemetry = decodeGimbalTelemetry(parsed);
assert.equal(telemetry.pitch, -12.3);
assert.equal(telemetry.roll, 4.5);
assert.equal(telemetry.yaw, 90.1);
assert.equal(telemetry.modeFlags, 0x40);
assert.equal(telemetry.rollAdjust, -3);
assert.equal(telemetry.limitFlags, 0x04);
assert.equal(telemetry.stateFlags, 0x01);
assert.equal(telemetry.yawAngle, -89);
assert.deepEqual(telemetry.attitude.raw, { pitch: -123, roll: 45, yaw: 901 });
assert.equal(telemetry.jointAngles.pitch, -3.5);
assert.equal(telemetry.jointAngles.roll, 2.7);
assert.equal(telemetry.jointAngles.yaw, -87.65);
assert.deepEqual(telemetry.orientationQuaternion.components, [0.5, -0.5, 0.5, -0.5]);
assert.equal(telemetry.orientationQuaternion.norm, 1);
assert.equal(telemetry.verified, true);
assert.deepEqual(decodeGimbalPositionCandidate(parsed), telemetry);

const decoder = new DumlStreamDecoder();
assert.deepEqual(decoder.push(packet.subarray(0, 5)), []);
assert.deepEqual(decoder.push(packet.subarray(5, 17)), []);
const decoded = decoder.push(packet.subarray(17));
assert.equal(decoded.length, 1);
assert.equal(decoded[0].raw.toString("hex"), packet.toString("hex"));

const second = frame(0x1235, 0x04, 0x01, Buffer.alloc(9));
const combined = new DumlStreamDecoder().push(Buffer.concat([Buffer.from([1, 2, 3]), packet, second]));
assert.equal(combined.length, 2);

const corrupted = Buffer.from(packet);
corrupted[12] ^= 0xff;
const recovered = new DumlStreamDecoder().push(Buffer.concat([corrupted, second]));
assert.equal(recovered.length, 1);
assert.equal(recovered[0].sequence, 0x1235);

console.log("DUML stream reassembly, CRC validation, attitude, and joint-angle decoding OK");
