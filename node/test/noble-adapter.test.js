import assert from 'node:assert/strict';
import test from 'node:test';
import { EventEmitter } from 'node:events';
import { NobleAdapter } from '../src/noble-adapter.js';
import { RS4Mini } from '../src/index.js';

test('unused Noble adapter closes without initializing native Bluetooth', async () => {
  const native = new EventEmitter(); native.stop = () => { throw new Error('must not stop an unstarted native manager'); };
  const adapter = new NobleAdapter(native); await adapter.stopScanningAsync(); adapter.stop();
  assert.equal(adapter.started, false);
});
test('Noble wrapper owns one manager and stops it only once', async () => {
  const native = new EventEmitter(); let stops = 0, scans = 0;
  native.state = 'poweredOn'; native.stop = () => { stops++; }; native.stopScanningAsync = async () => { scans++; };
  const adapter = new NobleAdapter(native); assert.equal(adapter.state, 'poweredOn');
  await adapter.stopScanningAsync(); adapter.stop(); adapter.stop(); await adapter.stopScanningAsync();
  assert.equal(stops, 1); assert.equal(scans, 1);
});
test('default controllers own distinct lazy backends and can close without connecting', async () => {
  const first = new RS4Mini(), second = new RS4Mini();
  assert.notEqual(first.adapter.native, second.adapter.native);
  assert.equal(first.adapter.started, false); await first.close(); await second.close();
});
