// Existing experimental read queries only; no model-specific motion/sleep writes.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import { BleDevice } from '../../node/src/device-node.js';
if (process.argv.includes('--help')) { console.log('RS4MINI_SDK_TEST=yes RS4MINI_DEVICE_ID=<local ID> node tools/hardware/sdk-node-research-queries.mjs'); process.exit(0); }
if (process.env.RS4MINI_SDK_TEST !== 'yes' || !process.env.RS4MINI_DEVICE_ID) throw Error('Explicit SDK test and local device ID required');
const g = new BleDevice({ deviceId: process.env.RS4MINI_DEVICE_ID.replaceAll('-', '').toLowerCase() }), rows = [];
const capture = new URL('../../node/captures/node-research-queries-' + Date.now() + '.jsonl', import.meta.url);
fs.mkdirSync(new URL('../../node/captures/', import.meta.url), { recursive: true });
g.onMessage = m => fs.appendFileSync(capture, JSON.stringify(m) + '\n');
try {
  await g.connect({ timeoutMs: 15000, directConnectTimeoutMs: 8000 });
  g.experimental.useProfile('rs3');
  for (const kind of ['version', 'controlStatus', 'type']) {
    try {
      const r = await g.experimental.query({ kind, timeoutMs: 4000 });
      assert.equal(r.sender, 4); assert.equal(r.receiver, 2); assert.ok(r.flags & 128);
      rows.push({ name: 'experimental.query.' + kind, ok: true, flags: r.flags, commandSet: r.commandSet, commandId: r.commandId, payloadLength: r.payload.length, semanticsVerified: false });
    } catch (e) { rows.push({ name: 'experimental.query.' + kind, ok: false, code: e.code || e.name }); }
  }
  assert.equal(g.decoder.invalidFrames, 0); assert.equal(g.decoder.discardedBytes, 0);
  rows.push({ name: 'decoder', ok: true });
} catch (e) { rows.push({ name: 'session', ok: false, code: e.code || e.name }); }
finally {
  try { await g.close(); assert.equal(g.connected, false); rows.push({ name: 'close', ok: true }); }
  catch (e) { rows.push({ name: 'close', ok: false, code: e.code || e.name }); }
}
console.log(JSON.stringify({ port: 'node', entry: 'BleDevice', sdkVersion: '0.7.39', sourceProfile: 'rs3', rows, targetModelLayoutVerified: false }, null, 2));
if (rows.some(r => !r.ok)) process.exitCode = 1;
