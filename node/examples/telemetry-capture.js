import { mkdir, readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { RS4Mini } from "../src/index.js";

const here = dirname(fileURLToPath(import.meta.url));
const deviceCacheFile = resolve(here, "../.rs4mini-device.json");
const captureDirectory = resolve(here, "../captures");
const durationMs = Number(process.env.RS4MINI_CAPTURE_MS || 10_000);
if (!Number.isFinite(durationMs) || durationMs <= 0 || durationMs > 60_000) throw new RangeError('RS4MINI_CAPTURE_MS must be in 0..60000');

async function loadCachedDeviceId() {
  try { return JSON.parse(await readFile(deviceCacheFile, "utf8")).deviceId || null; }
  catch { return null; }
}

const gimbal = new RS4Mini({ deviceId: await loadCachedDeviceId() });
await mkdir(captureDirectory, { recursive: true });
const stamp = new Date().toISOString().replaceAll(":", "-");
const outputFile = resolve(captureDirectory, `telemetry-${stamp}.jsonl`);
const rows = [];
const commandCounts = new Map();
let telemetryCount = 0;

gimbal.onMessage = message => {
  const command = `${message.commandSet.toString(16).padStart(2, "0")}:${message.commandId.toString(16).padStart(2, "0")}`;
  commandCounts.set(command, (commandCounts.get(command) || 0) + 1);
  rows.push(JSON.stringify({
    type: "duml",
    time: Date.now(),
    sender: message.sender,
    receiver: message.receiver,
    sequence: message.sequence,
    flags: message.flags,
    commandSet: message.commandSet,
    commandId: message.commandId,
    payloadHex: message.payload.toString("hex"),
    frameHex: message.raw.toString("hex"),
  }));
};

gimbal.onTelemetry = telemetry => {
  telemetryCount++;
  process.stdout.write(
    `\rattitude p=${telemetry.attitude.pitch.toFixed(1)} r=${telemetry.attitude.roll.toFixed(1)} y=${telemetry.attitude.yaw.toFixed(1)}` +
    (telemetry.jointAngles
      ? ` | joints p=${telemetry.jointAngles.pitch.toFixed(1)} r=${telemetry.jointAngles.roll.toFixed(1)} y=${telemetry.jointAngles.yaw.toFixed(2)}   `
      : "   "),
  );
};

try {
  console.log("connected:", await gimbal.connect());
  console.log(`capturing FFF4 for ${durationMs} ms without moving the gimbal...`);
  await new Promise(resolve => setTimeout(resolve, durationMs));
} finally {
  try { await writeFile(outputFile, rows.length ? `${rows.join("\n")}\n` : "", "utf8"); }
  finally { await gimbal.close(); }
}

console.log("\nDUML command counts:", Object.fromEntries([...commandCounts].sort()));
console.log("telemetry samples:", telemetryCount);
console.log("decoder stats:", {
  invalidFrames: gimbal.decoder.invalidFrames,
  discardedBytes: gimbal.decoder.discardedBytes,
  bufferedBytes: gimbal.decoder.buffer.length,
});
console.log("capture saved:", outputFile);
