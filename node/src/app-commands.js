// Device SDK facade: single owner/queue/pending map, no composed motion.
import { appProfile, parameterContext, parameterRequest, sensitivityPayload, appReply, parameterReply } from './app-protocol.js';
import { failure, check } from './async.js';
function optionsOnly(options, keys) {
  if (!options || typeof options !== 'object' || Array.isArray(options) || Object.keys(options).some(key => !keys.includes(key))) throw new TypeError('invalid App command options');
}
export class AppCommands {
  constructor(owner) { this.owner = owner; this._profile = null; }
  get profile() { return this._profile; }
  useProfile(profile) {
    appProfile(profile);
    if (this.owner.activeOperation || this.owner.experimental.pending.size) throw failure('RS4MINI_BUSY', 'Cannot change protocol source during an operation or query');
    this.owner.experimental._profile = null; this.owner.experimental._reset();
    this._profile = profile;
  }
  _requireProfile() { appProfile(this._profile); }
  async readParameters(options = {}) {
    optionsOnly(options, ['parameters', 'timeoutMs']); this._requireProfile();
    const parameters = parameterContext(options.parameters);
    const response = await this.owner.experimental._queryPayloadCommand('App parameters', [4, 0x10], parameterRequest(parameters), options.timeoutMs ?? 3000);
    return parameterReply(response, parameters);
  }
  async getFollowSensitivity(options = {}) {
    optionsOnly(options, ['timeoutMs']);
    const result = await this.readParameters({ parameters: [{ index: 150, size: 1 }], timeoutMs: options.timeoutMs ?? 3000 });
    const rawValue = parseInt(result.parameters[0].rawHex, 16);
    return { ...result, rawValue, mode: [0, 1].includes(rawValue) ? rawValue : null };
  }
  async setFollowSensitivity(options = {}) {
    optionsOnly(options, ['mode', 'timeoutMs']); this._requireProfile();
    const mode = options.mode, payload = sensitivityPayload(mode), timeoutMs = options.timeoutMs ?? 3000;
    // Validate before claiming motion ownership or sending neutral frames.
    if (!Number.isFinite(timeoutMs) || timeoutMs <= 0 || timeoutMs > 60000) throw new RangeError('timeoutMs must be >0..60000');
    return this.owner._run('setFollowSensitivity', async operation => {
      await this.owner._stop(); check(operation.controller.signal);
      const response = await this.owner.experimental._queryPayloadCommand('follow sensitivity', [4, 0x0f], payload, timeoutMs,
        { signal: operation.controller.signal, epoch: this.owner.motionEpoch });
      return { ...appReply(response, 0x0f), requestedMode: mode };
    }, false);
  }
}
