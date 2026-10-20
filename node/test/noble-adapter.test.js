import assert from 'node:assert/strict';
import test from 'node:test';
import { EventEmitter } from 'node:events';
import { NobleAdapter } from '../src/noble-adapter.js';
import { RS4Mini } from '../src/index.js';
import { setup } from './fakes.js';

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
test('Noble selects connection-scoped notification teardown only on CoreBluetooth', () => {
  assert.equal(new NobleAdapter(new EventEmitter()).unsubscribeBeforeDisconnect, process.platform !== 'darwin');
});
test('connection-scoped teardown removes listeners and really disconnects without a CCCD write', async () => {
  const { gimbal, adapter, peripheral } = setup();
  adapter.unsubscribeBeforeDisconnect = false;
  peripheral.rx.unsubscribeAsync = async () => { throw new Error('unexpected notification mutation'); };
  await gimbal.connect(); assert.equal(peripheral.rx.listenerCount('data'), 1);
  await gimbal.close();
  assert.equal(peripheral.disconnectCount, 1); assert.equal(peripheral.state, 'disconnected');
  assert.equal(peripheral.rx.listenerCount('data'), 0); assert.equal(gimbal.connected, false);
  assert.equal(gimbal.closed, true); assert.equal(adapter.stopped, true);
});
test('connection-scoped teardown still rejects real disconnect failures and closes the manager', async () => {
  const { gimbal, adapter, peripheral } = setup(); adapter.unsubscribeBeforeDisconnect = false;
  await gimbal.connect(); peripheral.disconnectAsync = async () => { throw new Error('disconnect failed'); };
  await assert.rejects(gimbal.close(), /disconnect failed/);
  assert.equal(gimbal.connected, false); assert.equal(adapter.stopped, true);
});
test('other adapters retain explicit unsubscribe errors and still disconnect', async () => {
  const { gimbal, adapter, peripheral } = setup(); await gimbal.connect();
  peripheral.rx.unsubscribeAsync = async () => { throw new Error('unsubscribe failed'); };
  await assert.rejects(gimbal.close(), /unsubscribe failed/);
  assert.equal(peripheral.disconnectCount, 1); assert.equal(adapter.stopped, true);
});
