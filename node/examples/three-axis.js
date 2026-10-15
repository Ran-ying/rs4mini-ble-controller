import { RS4Mini } from "../src/index.js";

const gimbal = new RS4Mini();
let stopping = false;

async function safeStop() {
  if (stopping) return;
  stopping = true;
  try { await gimbal.close(); } finally { process.exit(); }
}

process.on("SIGINT", safeStop);
process.on("SIGTERM", safeStop);

try {
  console.log("connected:", await gimbal.connect());

  // Three independent normalized virtual-stick axes (-1..+1).
  // Begin gently, especially on roll, and always bound movement duration.
  await gimbal.setVelocity({ pan: 0.15, tilt: 0.08, roll: 0.05 });
  await new Promise(resolve => setTimeout(resolve, 1000));
  await gimbal.stop();
  console.log("three-axis movement complete; stop frames sent");
} finally {
  await gimbal.close();
}
