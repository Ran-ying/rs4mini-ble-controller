import { frame } from './protocol.js';
import { rs3AbsoluteFrame, rs3RateFrame, researchProfile, researchSleepFrame, decodeResearchStatus } from './experimental-protocol.js';
import { bounded, check, deferred, delay, failure, now } from './async.js';

const clone = value => structuredClone(value);
function optionsOnly(options, keys) {
  if (!options || typeof options !== 'object' || Array.isArray(options) || Object.keys(options).some(key => !keys.includes(key))) throw new TypeError('invalid experimental options');
}
function duration(value, name, zero = true) {
  if (!Number.isFinite(value) || value < (zero ? 0 : Number.MIN_VALUE) || value > 60000) throw new RangeError(`${name} must be ${zero ? '0' : '>0'}..60000 ms`);
}

export class ExperimentalGimbal {
  constructor(owner) { this.owner = owner; this._profile = null; this.pending = new Map(); this._status = {}; }
  get profile() { return this._profile; }
  get status() { return clone(this._status); }
  useProfile(profile) {
    researchProfile(profile);
    if (this.owner.activeOperation || this.pending.size) throw failure('RS4MINI_BUSY', 'Cannot change research profile during an operation or query');
    this._profile = profile; this._status = {};
  }
  _requireProfile(rs3Only = false) {
    researchProfile(this._profile);
    if (rs3Only && this._profile !== 'rs3') throw new TypeError('This command is documented only in the rs3 research profile');
    return this._profile;
  }
  _reset() { this._status = {}; }
  _message(message) {
    const pending = this.pending.get(message.sequence);
    if (pending && pending.session === this.owner.session && message.sender === 4 && message.receiver === 2 &&
      (message.flags & 0x80) && message.commandSet === pending.set && message.commandId === pending.id)
      pending.resolve({ ...message, raw: message.raw.slice(), payload: message.payload.slice() });
    if (!this._profile) return;
    const status = decodeResearchStatus(message, this._profile);
    if (status) { this._status[status.kind] = status; this.owner._emit('onExperimentalStatus', clone(status)); }
  }
  async query(options = {}) {
    optionsOnly(options, ['kind', 'timeoutMs']); this._requireProfile();
    const { kind, timeoutMs = 3000 } = options;
    const commands = { version: [0, 1], position: [4, 2], controlStatus: [4, 0x0b], type: [4, 0x1c] };
    if (!Object.hasOwn(commands, kind)) throw new TypeError('query kind must be version, position, controlStatus or type');
    duration(timeoutMs, 'timeoutMs', false); this.owner._requireConnected();
    if (this.pending.size >= 64) throw failure('RS4MINI_BUSY', 'Too many pending queries');
    const sequence = this.owner._nextSequence(), session = this.owner.session, response = deferred(), controller = new AbortController();
    const [set, id] = commands[kind];
    this.pending.set(sequence, { session, set, id, resolve: response.resolve });
    try {
      return await bounded(async () => {
        await this.owner._enqueue(frame(sequence, set, id, undefined, 0x40), { signal: controller.signal });
        return response.promise;
      }, timeoutMs, { signal: session.controller.signal, error: failure('RS4MINI_RESPONSE_TIMEOUT', `${kind} query had no correlated response`) });
    } finally { this.pending.delete(sequence); controller.abort(failure('RS4MINI_OPERATION_CANCELLED', 'Query finished')); }
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
  async absolute(options = {}) {
    optionsOnly(options, ['pan', 'tilt', 'roll', 'parameterByte', 'observeMs']); this._requireProfile(true);
    const { observeMs = 3000, ...angles } = options; duration(observeMs, 'observeMs'); rs3AbsoluteFrame(0, angles);
    return this.owner._run('experimentalAbsolute', async operation => {
      await this.owner._stop(); check(operation.controller.signal);
      await this.owner._enqueue(rs3AbsoluteFrame(this.owner._nextSequence(), angles), { signal: operation.controller.signal, epoch: this.owner.motionEpoch });
      await delay(observeMs, operation.controller.signal);
      return { sent: true, deviceVerified: false, physicalCompletionVerified: false };
    });
  }
  async rateFor(options = {}) {
    optionsOnly(options, ['pan', 'tilt', 'roll', 'durationMs']); this._requireProfile(true);
    const { durationMs, ...rates } = options; duration(durationMs, 'durationMs'); rs3RateFrame(0, rates);
    return this.owner._run('experimentalRate', async operation => {
      const started = now(), interval = 1000 / this.owner.rateHz;
      this.owner._nativeRateProfile = 'rs3';
      while (now() - started < durationMs) {
        check(operation.controller.signal);
        await this.owner._enqueue(rs3RateFrame(this.owner._nextSequence(), rates), { signal: operation.controller.signal, epoch: this.owner.motionEpoch });
        await delay(Math.min(interval, Math.max(0, durationMs - (now() - started))), operation.controller.signal);
      }
      return { sent: true, deviceVerified: false, physicalCompletionVerified: false };
    });
  }
}
