// Maintainer/device SDK entry. Applications import RS4Mini from the package root.
import { BleDevice as DeviceCore } from './device.js';
import { createNobleAdapter } from './noble-adapter.js';
export class BleDevice extends DeviceCore {
  constructor(options = {}) { super({ ...options, adapter: options.adapter ?? createNobleAdapter() }); }
}
