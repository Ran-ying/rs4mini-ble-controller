import { readFile, writeFile } from "node:fs/promises";
import { RS4Mini } from "../src/index.js";

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const deviceCacheFile = new URL("../.rs4mini-device.json", import.meta.url);

async function loadCachedDeviceId() {
  try { return JSON.parse(await readFile(deviceCacheFile, "utf8")).deviceId || null; }
  catch { return null; }
}

async function saveDeviceId(deviceId) {
  await writeFile(deviceCacheFile, `${JSON.stringify({ deviceId }, null, 2)}\n`, "utf8");
}

const gimbal = new RS4Mini({
  nameIncludes: "DJI RS4 MINI",
  rateHz: 15,
  deviceId: await loadCachedDeviceId(),
});
let shutdownPromise = null;
let interruptedBy = null;

// FFF4 currently exposes raw packets. Keep this disabled unless inspecting BLE traffic.
gimbal.onNotification = packet => {
  if (process.env.RS4MINI_LOG_PACKETS === "1") console.log("notify:", packet.toString("hex"));
};
gimbal.onDisconnect = () => console.log("gimbal disconnected");
gimbal.onError = error => console.error("BLE stream error:", error);

function shutdown(signal) {
  if (shutdownPromise) {
    console.error("second interrupt: forcing exit");
    process.exit(130);
  }
  interruptedBy = signal;
  console.log(`\n${signal}: stopping safely...`);
  shutdownPromise = gimbal.close();
}

process.on("SIGINT", () => shutdown("SIGINT"));
process.on("SIGTERM", () => shutdown("SIGTERM"));

function ensureRunning() {
  if (interruptedBy) throw new Error(`Interrupted by ${interruptedBy}`);
}

function wrap180(angle) {
  return ((angle + 540) % 360) - 180;
}

try {
  // 1. Scan, connect, discover FFF4/FFF5, and subscribe to notifications.
  const name = await gimbal.connect({ timeoutMs: 30_000 });
  console.log("connected:", name);
  await saveDeviceId(gimbal.deviceId);
  console.log("device ID cached; later runs can reconnect without waiting for advertising");

  // 2. Read a new telemetry sample, then use joint feedback for a small
  // closed-loop Pan move and return to the original joint angle.
  const attitude = await gimbal.getAttitude({ fresh: true });
  const startJoints = await gimbal.getJointAngles();
  console.log("attitude:", attitude);
  console.log("joint angles:", startJoints);

  ensureRunning();
  const panTarget = wrap180(startJoints.yaw + 5);
  console.log(`closed-loop Pan to ${panTarget.toFixed(2)}°...`);
  console.log(await gimbal.moveTo({ pan: panTarget, toleranceDeg: 1, timeoutMs: 10_000 }));
  await sleep(300);
  ensureRunning();
  console.log(`closed-loop Pan return to ${startJoints.yaw.toFixed(2)}°...`);
  console.log(await gimbal.moveTo({ pan: startJoints.yaw, toleranceDeg: 1, timeoutMs: 10_000 }));
  await sleep(400);

  // 3. Clearly visible, duration-bounded single-axis movements (-1..+1).
  // The previous 5%-12% values could fall near the configured joystick
  // deadband and were too subtle to verify visually.
  ensureRunning();
  console.log("pan right 45%...");
  await gimbal.moveFor({ pan: 0.45, durationMs: 900 });
  await sleep(250);
  ensureRunning();
  console.log("pan left 45%...");
  await gimbal.moveFor({ pan: -0.45, durationMs: 900 });
  await sleep(400);

  ensureRunning();
  console.log("tilt up 35%...");
  await gimbal.moveFor({ tilt: 0.35, durationMs: 700 });
  await sleep(250);
  ensureRunning();
  console.log("tilt down 35%...");
  await gimbal.moveFor({ tilt: -0.35, durationMs: 700 });
  await sleep(400);

  ensureRunning();
  console.log("roll positive 18%...");
  await gimbal.moveFor({ roll: 0.18, durationMs: 600 });
  await sleep(250);
  ensureRunning();
  console.log("roll negative 18%...");
  await gimbal.moveFor({ roll: -0.18, durationMs: 600 });
  await sleep(400);

  // 4. Simultaneous three-axis virtual-stick control, then explicit stop.
  ensureRunning();
  console.log("combined pan/tilt/roll movement...");
  await gimbal.setVelocity({ pan: 0.30, tilt: 0.22, roll: 0.12 });
  await sleep(700);
  await gimbal.stop();
  await sleep(400);

  // 5. Approximate degrees/second. These are empirical conversions, not encoder feedback.
  ensureRunning();
  console.log("approximate speed command: pan -12°/s, tilt -7°/s, roll -4°/s...");
  await gimbal.setVelocityDeg({ pan: -12, tilt: -7, roll: -4 });
  await sleep(700);
  await gimbal.stop();
  await sleep(400);

  // 6. DJI's three-axis recenter command.
  ensureRunning();
  console.log("recentering all three axes...");
  await gimbal.recenter();
  await sleep(2000);
} catch (error) {
  if (!interruptedBy) throw error;
} finally {
  // close() sends neutral frames, disconnects BLE, then stops Noble's native
  // run loop so a completed command exits without requiring Ctrl+C.
  if (shutdownPromise) await shutdownPromise;
  else await gimbal.close();
  if (interruptedBy) process.exitCode = 130;
}
