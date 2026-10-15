import { RS4Mini as Controller } from '../node/src/controller.js';
import { velocityFrame as encodeVelocity } from '../node/src/protocol.js';
import { BrowserAdapter } from './adapter.js';

// Keep the original positional Web encoder API, alongside Node's object API.
export function velocityFrame(sequence, pan = 0, tilt = 0, roll = 0) {
  return encodeVelocity(sequence, typeof pan === 'object' ? pan : { pan, tilt, roll });
}
export { DumlStreamDecoder, decodeGimbalTelemetry } from '../node/src/telemetry.js';
export { orientationFromComponents } from '../node/src/orientation.js';

export class RS4Mini extends Controller {
  constructor({ bluetooth = globalThis.navigator?.bluetooth, document = globalThis.document,
    window = globalThis.window, ...options } = {}) {
    super({ ...options, adapter: new BrowserAdapter(bluetooth) });
    this.pageDocument = document; this.pageWindow = window;
    this.pageStop = () => { this.stop().catch(error => this._report(error)); };
    this.visibilityStop = () => { if (document.hidden) this.pageStop(); };
    document?.addEventListener('visibilitychange', this.visibilityStop);
    window?.addEventListener('blur', this.pageStop);
    window?.addEventListener('pagehide', this.pageStop);
  }
  get device() { return this.adapter.peripheral?.device || null; }
  async connect(options = {}) {
    const automatic = this._autoConnecting;
    const result = super.connect(options);
    const context = this.connection;
    // Base validation and reservation run synchronously before its first await.
    if (!automatic && this.connection && !this.connection.controller.signal.aborted) {
      try { this.adapter.select(); } catch (error) { this.connection.controller.abort(error); }
    }
    try { return await result; }
    catch (error) {
      if (!automatic && context && !this.connected && (!this.connection || this.connection === context)) this.adapter.resetSelection();
      throw error;
    }
  }
  close() {
    this.pageDocument?.removeEventListener('visibilitychange', this.visibilityStop);
    this.pageWindow?.removeEventListener('blur', this.pageStop);
    this.pageWindow?.removeEventListener('pagehide', this.pageStop);
    return super.close();
  }
}
