// Device SDK facade: single owner/queue/pending map, no composed motion.
import { appProfile, parameterContext, parameterRequest, sensitivityPayload, appReply, parameterReply } from './app-protocol.js';
import { frame } from './protocol.js';
import { autoTunePayload, calibrationReply, calibrationNotification } from './app-calibration.js';
import { settingsSchema, settingsPatch, decodeSettings, settingsWrite } from './app-settings.js';
import { failure, check, now } from './async.js';
function optionsOnly(options, keys) {
  if (!options || typeof options !== 'object' || Array.isArray(options) || Object.keys(options).some(key => !keys.includes(key))) throw new TypeError('invalid App command options');
}
export class AppCommands {
  constructor(owner) { this.owner = owner; this._profile = null; this._calibrationStatus = null; }
  get profile() { return this._profile; }
  get calibrationStatus() { return structuredClone(this._calibrationStatus); }
  _reset() { this._calibrationStatus = null; }
  _message(message) {
    if (!this._profile) return;
    const status = calibrationNotification(message);
    if (status) { this._calibrationStatus = status; this.owner._emit('onAppStatus', structuredClone(status)); }
  }
  useProfile(profile) {
    appProfile(profile);
    if (this.owner.activeOperation || this.owner.experimental.pending.size) throw failure('RS4MINI_BUSY', 'Cannot change protocol source during an operation or query');
    this.owner.experimental._profile = null; this.owner.experimental._reset();
    this._profile = profile; this._reset();
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
  async queryCalibrationStatus(options = {}) {
    optionsOnly(options, ['timeoutMs']); this._requireProfile();
    const response = await this.owner.experimental._queryPayloadCommand('App calibration status', [4, 0x6e], undefined, options.timeoutMs ?? 3000);
    return calibrationReply(response);
  }
  async sendAutoTuneRequest(options = {}) {
    optionsOnly(options, ['start']); this._requireProfile();
    const start = options.start, payload = autoTunePayload(start);
    return this.owner._run('sendAutoTuneRequest', async operation => {
      await this.owner._stop(); check(operation.controller.signal);
      await this.owner._enqueue(frame(this.owner._nextSequence(), 4, 0x6a, payload, 0), { signal: operation.controller.signal, epoch: this.owner.motionEpoch });
      return { profile: this._profile, sent: true, requestedStart: start, acknowledgementRequested: false,
        acknowledged: false, deviceVerified: false, physicalCompletionVerified: false };
    }, false);
  }
  getCustomFollowSettings(options = {}) { return this._getSettings('customFollow', options); }
  getMotorSettings(options = {}) { return this._getSettings('motor', options); }
  setCustomFollowSettings(options = {}) { return this._setSettings('customFollow', options); }
  setMotorSettings(options = {}) { return this._setSettings('motor', options); }
  async _getSettings(kind, options) {
    optionsOnly(options, ['timeoutMs']);
    const { index } = settingsSchema(kind);
    return decodeSettings(await this.readParameters({ parameters: [{ index, size: 1 }], timeoutMs: options.timeoutMs ?? 3000 }), kind);
  }
  async _setSettings(kind, options) {
    const schema = settingsSchema(kind);
    optionsOnly(options, [...Object.keys(schema.fields), 'timeoutMs']); this._requireProfile();
    const { timeoutMs = 3000, ...fields } = options, patch = settingsPatch(kind, fields);
    if (!Number.isFinite(timeoutMs) || timeoutMs <= 0 || timeoutMs > 60000) throw new RangeError('timeoutMs must be >0..60000');
    const name = kind === 'motor' ? 'setMotorSettings' : 'setCustomFollowSettings';
    return this.owner._run(name, async operation => {
      await this.owner._stop(); check(operation.controller.signal);
      const deadline = now() + timeoutMs;
      const remaining = () => {
        const left = deadline - now();
        if (left <= 0) throw failure('RS4MINI_RESPONSE_TIMEOUT', 'Settings transaction deadline expired');
        return left;
      };
      const parameters = [{ index: schema.index, size: 1 }], context = { signal: operation.controller.signal, epoch: this.owner.motionEpoch };
      const response = await this.owner.experimental._queryPayloadCommand(name + ' read', [4, 0x10], parameterRequest(parameters), remaining(), context);
      const before = decodeSettings(parameterReply(response, parameters), kind);
      check(operation.controller.signal);
      const { payload, requestedRawValue } = settingsWrite(kind, patch, before.rawValue);
      const ack = await this.owner.experimental._queryPayloadCommand(name + ' write', [4, 0x0f], payload, remaining(), context);
      return { ...appReply(ack, 0x0f), previousRawValue: before.rawValue, requestedRawValue, requestedSettings: patch };
    }, false);
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
