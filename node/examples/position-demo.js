import { readFile } from "node:fs/promises";
import { RS4Mini } from "../src/index.js";

const deviceCacheFile = new URL("../.rs4mini-device.json", import.meta.url);
const axis = (process.env.RS4MINI_POSITION_AXIS ?? "pan").toLowerCase();
const deltaDeg = Number(process.env.RS4MINI_POSITION_DELTA ?? 5);

if (!["pan", "tilt", "roll"].includes(axis)) {
  throw new RangeError("RS4MINI_POSITION_AXIS must be pan, tilt, or roll");
}
if (!Number.isFinite(deltaDeg) || deltaDeg === 0 || Math.abs(deltaDeg) > 90) {
  throw new RangeError("RS4MINI_POSITION_DELTA must be a non-zero number between -90 and 90");
}

async function loadCachedDeviceId() {
  try { return JSON.parse(await readFile(deviceCacheFile, "utf8")).deviceId || null; }
  catch { return null; }
}

function wrap180(angle) {
  return ((angle + 540) % 360) - 180;
}

const gimbal = new RS4Mini({ deviceId: await loadCachedDeviceId() });
let shutdownPromise = null;
let interruptedBy = null;

function shutdown(signal) {
  if (shutdownPromise) return;
  interruptedBy = signal;
  console.log(`\n${signal}: stopping safely...`);
  shutdownPromise = gimbal.close();
  shutdownPromise.catch(error => console.error('BLE cleanup failed:', error));
}

process.on("SIGINT", () => shutdown("SIGINT"));
process.on("SIGTERM", () => shutdown("SIGTERM"));

try {
  console.log("connected:", await gimbal.connect({ timeoutMs: 30_000 }));

  const attitude = await gimbal.getAttitude({ fresh: true });
  const start = await gimbal.getJointAngles();
  console.log("attitude:", attitude);
  console.log("joint angles:", start);

  const jointKey = { pan: "yaw", tilt: "pitch", roll: "roll" }[axis];
  const startAngle = start[jointKey];
  const target = axis === "pan" ? wrap180(startAngle + deltaDeg) : startAngle + deltaDeg;
  if (target < -180 || target > 180) throw new RangeError(`${axis} target is outside -180°…+180°`);
  console.log(`moving ${axis} joint from ${startAngle.toFixed(2)}° to ${target.toFixed(2)}°...`);
  console.log(await gimbal.moveTo({ [axis]: target, toleranceDeg: 1, timeoutMs: 15_000 }));

  console.log(`returning ${axis} joint to ${startAngle.toFixed(2)}°...`);
  console.log(await gimbal.moveTo({ [axis]: startAngle, toleranceDeg: 1, timeoutMs: 15_000 }));
} catch (error) {
  if (!interruptedBy) throw error;
} finally {
  if (shutdownPromise) await shutdownPromise;
  else await gimbal.close();
  if (interruptedBy) process.exitCode = 130;
}
