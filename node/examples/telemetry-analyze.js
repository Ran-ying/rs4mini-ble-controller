import { readFile } from "node:fs/promises";
import { DumlStreamDecoder, decodeGimbalTelemetry } from "../src/index.js";

const inputFile = process.argv[2];
if (!inputFile) {
  console.error("Usage: node examples/telemetry-analyze.js <native-capture.log>");
  process.exit(2);
}

const decoder = new DumlStreamDecoder();
const text = await readFile(inputFile, "utf8");
const messages = [];
let phase = "unlabeled";

for (const line of text.split(/\r?\n/)) {
  const phaseMatch = /^phase=([^\s]+)(?:\s+axis=([^\s]+))?/.exec(line.trim());
  if (phaseMatch) {
    phase = phaseMatch[2] ? `${phaseMatch[2]}:${phaseMatch[1]}` : phaseMatch[1];
    continue;
  }
  const match = /^rx=([0-9.]+)\s+([0-9a-f]+)$/i.exec(line.trim());
  if (!match) continue;
  const receivedAt = Number(match[1]) * 1000;
  for (const message of decoder.push(Buffer.from(match[2], "hex"))) {
    messages.push({ ...message, receivedAt, phase });
  }
}

const groups = new Map();
for (const message of messages) {
  const key = `${hex(message.commandSet)}:${hex(message.commandId)}`;
  const group = groups.get(key) || { count: 0, lengths: new Set(), first: null, last: null };
  group.count++;
  group.lengths.add(message.payload.length);
  group.first ||= message;
  group.last = message;
  groups.set(key, group);
}

console.log("valid DUML frames:", messages.length);
console.log("decoder:", {
  invalidFrames: decoder.invalidFrames,
  discardedBytes: decoder.discardedBytes,
  bufferedBytes: decoder.buffer.length,
});
console.log("commands:");
for (const [key, group] of [...groups].sort()) {
  const elapsed = (group.last.receivedAt - group.first.receivedAt) / 1000;
  const rate = group.count > 1 && elapsed > 0 ? (group.count - 1) / elapsed : 0;
  console.log(
    `  ${key} count=${group.count} payloadLengths=${[...group.lengths].sort((a, b) => a - b).join(",")} rate=${rate.toFixed(2)}Hz`,
  );
}

const samples = messages.map(decodeGimbalTelemetry).filter(Boolean);
if (samples.length) {
  console.log("04:05 telemetry:");
  for (const sample of samples) {
    console.log(
      `  attitude(p=${sample.attitude.pitch.toFixed(1)} r=${sample.attitude.roll.toFixed(1)} y=${sample.attitude.yaw.toFixed(1)})` +
      (sample.jointAngles
        ? ` joints(p=${sample.jointAngles.pitch.toFixed(1)} r=${sample.jointAngles.roll.toFixed(1)} y=${sample.jointAngles.yaw.toFixed(2)})`
        : " joints(unavailable)"),
    );
  }

  const byPhase = new Map();
  for (const message of messages) {
    const sample = decodeGimbalTelemetry(message);
    if (!sample) continue;
    const list = byPhase.get(message.phase) || [];
    list.push(sample);
    byPhase.set(message.phase, list);
  }
  if (byPhase.size > 1) {
    console.log("04:05 ranges by labeled phase:");
    for (const [name, phaseSamples] of byPhase) {
      console.log(`  ${name} n=${phaseSamples.length} attitude(${rangeText(phaseSamples, sample => sample.attitude)})`);
      if (phaseSamples.every(sample => sample.jointAngles)) {
        console.log(`    joints(${rangeText(phaseSamples, sample => sample.jointAngles, 2)})`);
      }
    }
  }

  const positionMessages = messages.filter(message => message.commandSet === 0x04 && message.commandId === 0x05);
  const inspectBytes = Math.min(24, ...positionMessages.map(message => message.payload.length));
  console.log("04:05 signed int16 ranges by payload offset:");
  for (let offset = 0; offset + 1 < inspectBytes; offset += 2) {
    const values = positionMessages.map(message => message.payload.readInt16LE(offset));
    const min = Math.min(...values);
    const max = Math.max(...values);
    console.log(`  +${offset.toString().padStart(2, "0")}: ${min}..${max} span=${max - min}`);
  }
}

function hex(value) {
  return value.toString(16).padStart(2, "0");
}

function rangeText(samples, select = sample => sample, digits = 1) {
  return ["pitch", "roll", "yaw"].map(axis => {
    const values = samples.map(sample => select(sample)[axis]);
    return `${axis}=${Math.min(...values).toFixed(digits)}..${Math.max(...values).toFixed(digits)}`;
  }).join(" ");
}
