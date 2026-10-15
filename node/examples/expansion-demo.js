// Explicit hardware demos. With no arguments or --help, Bluetooth is not initialized.
import { RS4Mini } from '../src/index.js';

const [operation, profile, ...extra] = process.argv.slice(2);
const usage = 'Usage: node examples/expansion-demo.js read|waypoints|home|velocity|query [rs3|rs3mini]\n'
  + 'waypoints/home: Pan +3 degrees and return; velocity: Pan <=5% for 2 seconds.\n'
  + 'query requires an explicit other-model research profile and queries version only.\n'
  + 'Run only with a balanced, unobstructed gimbal and an operator present.';
if (!operation || operation === '--help') console.log(usage);
else if (extra.length || !['read', 'waypoints', 'home', 'velocity', 'query'].includes(operation) ||
  (operation === 'query' ? !['rs3', 'rs3mini'].includes(profile) : profile !== undefined)) {
  console.error(usage); process.exitCode = 1;
} else {
  await run().catch(error => { console.error(error.code || error.name, error.message); process.exitCode ||= 1; });
}

async function run() {
  const gimbal = new RS4Mini();
  const interrupt = () => { process.exitCode = 130; gimbal.close().catch(() => {}); };
  process.once('SIGINT', interrupt); process.once('SIGTERM', interrupt);
  try {
    console.log(operation === 'velocity' ? 'Pan velocity demo: maximum 5%, total 2 seconds.' :
      ['waypoints', 'home'].includes(operation) ? 'Pan position demo: +3 degrees, then return.' : 'Feedback/query demo; exit sends neutral frames.');
    await gimbal.connect();
    if (operation === 'query') {
      gimbal.experimental.useProfile(profile);
      const response = await gimbal.experimental.query({ kind: 'version' });
      console.log('Unverified research response:', response.payload.toString('hex')); return;
    }
    const start = await gimbal.getJointAngles({ fresh: true });
    console.log('Start joints:', { pan: start.yaw, tilt: start.pitch, roll: start.roll });
    const target = ((start.yaw + 3 + 540) % 360) - 180;
    if (operation === 'waypoints') console.log(await gimbal.moveThrough([{ pan: target, holdMs: 500 }, { pan: start.yaw }]));
    if (operation === 'home') {
      const home = await gimbal.captureHome({ fresh: true });
      await gimbal.moveTo({ pan: ((home.pan + 3 + 540) % 360) - 180 });
      console.log(await gimbal.moveHome({ axes: ['pan'] }));
    }
    if (operation === 'velocity') console.log(await gimbal.runTrajectory([
      { timeMs: 0, pan: 0 }, { timeMs: 1000, pan: .05 }, { timeMs: 2000, pan: 0 },
    ], { interpolation: 'smoothstep' }));
  } finally {
    await gimbal.close(); process.removeListener('SIGINT', interrupt); process.removeListener('SIGTERM', interrupt);
  }
}
