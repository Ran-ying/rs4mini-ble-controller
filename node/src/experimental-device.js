import {view} from './bytes.js';
import { frame, crc16 } from './protocol.js';
import { rs3AbsoluteFrame, rs3RateFrame, researchProfile, researchSleepFrame, decodeResearchStatus } from './experimental-protocol.js';
import { bounded, check, deferred, failure } from './async.js';

const clone = value => structuredClone(value);
function optionsOnly(options, keys) {
  if (!options || typeof options !== 'object' || Array.isArray(options) || Object.keys(options).some(key => !keys.includes(key))) throw new TypeError('invalid experimental options');
}
function duration(value, name, zero = true) {
  if (!Number.isFinite(value) || value < (zero ? 0 : Number.MIN_VALUE) || value > 60000) throw new RangeError(`${name} must be ${zero ? '0' : '>0'}..60000 ms`);
}

export class ExperimentalDevice {
  constructor(owner) { this.owner = owner; this._profile = null; this.pending = new Map(); this._status = {}; }
  get profile() { return this._profile; }
  get status() { return clone(this._status); }
  useProfile(profile) {
    researchProfile(profile);
    if (this.owner.activeOperation || this.pending.size) throw failure('RS4MINI_BUSY', 'Cannot change research profile during an operation or query');
    this._profile = profile; this._status = {};
    if (this.owner.appCommands) { this.owner.appCommands._profile = null; this.owner.appCommands._reset(); }
  }
  _requireProfile(rs3Only = false) {
    researchProfile(this._profile);
    if (rs3Only && this._profile !== 'rs3') throw new TypeError('This command is documented only in the rs3 research profile');
    return this._profile;
  }
  _reset() { this._status = {}; }
  _message(message) {
    const pending = this.pending.get(message.sequence);
    if (pending && pending.session === this.owner.session && message.sender === pending.receiver && message.receiver === 2 &&
      (message.flags & 0x80) && message.commandSet === pending.set && message.commandId === pending.id)
      pending.resolve({ ...message, raw: message.raw.slice(), payload: message.payload.slice() });
    if (!this._profile) return;
    const status = decodeResearchStatus(message, this._profile);
    if (status) { this._status[status.kind] = status; this.owner._emit('onExperimentalStatus', clone(status)); }
  }
  async query(options = {}) {
    optionsOnly(options, ['kind', 'timeoutMs']); this._requireProfile();
    const { kind, timeoutMs = 3000 } = options;
    const commands = { version: [0, 1], controlStatus: [4, 0x0b], type: [4, 0x1c] };
    if (!Object.hasOwn(commands, kind)) throw new TypeError('query kind must be version, controlStatus or type');
    return this._queryCommand(kind, commands[kind], timeoutMs);
  }
  async _queryCommand(kind, command, timeoutMs = 3000) {
    return this._queryPayloadCommand(kind, command, undefined, timeoutMs);
  }
  async _queryPayloadCommand(kind, [set, id], payload, timeoutMs = 3000, { signal, epoch, receiver = 4 } = {}) {
    if (receiver !== 4 && !(receiver === 229 && set === 0 && id === 50 && this.owner.appCommands?.profile === "ronin-2.2.2" && payload instanceof Uint8Array && payload.length === 1 && [1,17].includes(payload[0]))) throw new TypeError("Unsupported query route");
    duration(timeoutMs, 'timeoutMs', false); this.owner._requireConnected(); check(signal);
    if (this.pending.size >= 64) throw failure('RS4MINI_BUSY', 'Too many pending queries');
    const sequence = this.owner._nextSequence(), session = this.owner.session, response = deferred(), controller = new AbortController();
    const parents = [session.controller.signal, signal].filter(Boolean), listeners = [];
    for (const parent of parents) {
      const abort = () => controller.abort(parent.reason);
      if (parent.aborted) abort();
      else { parent.addEventListener('abort', abort, { once: true }); listeners.push([parent, abort]); }
    }
    this.pending.set(sequence, { session, set, id, receiver, resolve: response.resolve });
    try {
      return await bounded(async () => {
        const packet=frame(sequence,set,id,payload,0x40);
        if(receiver===229){packet[5]=receiver;view(packet).setUint16(packet.length-2,crc16(packet.subarray(0,-2)),true);}
        await this.owner._enqueue(packet, { signal: controller.signal, epoch });
        return response.promise;
      }, timeoutMs, { signal: controller.signal, error: failure('RS4MINI_RESPONSE_TIMEOUT', `${kind} query had no correlated response`) });
    } finally {
      this.pending.delete(sequence);
      for (const [parent, abort] of listeners) parent.removeEventListener('abort', abort);
      controller.abort(failure('RS4MINI_OPERATION_CANCELLED', 'Query finished'));
    }
  }
  async setSleep(options = {}) {
    optionsOnly(options, ['asleep']); const profile = this._requireProfile();
    researchSleepFrame(0, profile, options.asleep);
    return this.owner._run('experimentalSleep', async operation => {
      await this.owner._stop(); check(operation.controller.signal);
      await this.owner._enqueue(researchSleepFrame(this.owner._nextSequence(), profile, options.asleep), { signal: operation.controller.signal, epoch: this.owner.motionEpoch });
      return { sent: true, deviceVerified: false, physicalCompletionVerified: false };
    }, false);
  }
  _validateAbsolute(options) {
    this._requireProfile(true); rs3AbsoluteFrame(0, options);
  }
  _validateRate(options) {
    this._requireProfile(true); rs3RateFrame(0, options);
  }
  _writeAbsolute(options, operation) {
    return this.owner._enqueue(rs3AbsoluteFrame(this.owner._nextSequence(), options), { signal: operation.controller.signal, epoch: this.owner.motionEpoch });
  }
  _beginRate() { this.owner._nativeRateProfile = 'rs3'; }
  _writeRate(options, operation) {
    this._beginRate();
    return this.owner._enqueue(rs3RateFrame(this.owner._nextSequence(), options), { signal: operation.controller.signal, epoch: this.owner.motionEpoch });
  }
}
