import { ExperimentalDevice } from './experimental-device.js';
import { check, delay, now } from './async.js';

function optionsOnly(options, keys) {
  if (!options || typeof options !== 'object' || Array.isArray(options) || Object.keys(options).some(key => !keys.includes(key))) throw new TypeError('invalid experimental options');
}
function duration(value, name, zero = true) {
  if (!Number.isFinite(value) || value < (zero ? 0 : Number.MIN_VALUE) || value > 60000) throw new RangeError(`${name} must be ${zero ? '0' : '>0'}..60000 ms`);
}

export class ExperimentalGimbal extends ExperimentalDevice {
  async absolute(options = {}) {
    optionsOnly(options, ['pan', 'tilt', 'roll', 'parameterByte', 'observeMs']);
    const { observeMs = 3000, ...angles } = options; duration(observeMs, 'observeMs'); this._validateAbsolute(angles);
    return this.owner._run('experimentalAbsolute', async operation => {
      await this.owner._stop(); check(operation.controller.signal);
      await this._writeAbsolute(angles, operation);
      await delay(observeMs, operation.controller.signal);
      return { sent: true, deviceVerified: false, physicalCompletionVerified: false };
    });
  }
  async rateFor(options = {}) {
    optionsOnly(options, ['pan', 'tilt', 'roll', 'durationMs']);
    const { durationMs, ...rates } = options; duration(durationMs, 'durationMs'); this._validateRate(rates);
    return this.owner._run('experimentalRate', async operation => {
      const started = now(), interval = 1000 / this.owner.rateHz;
      this._beginRate();
      while (now() - started < durationMs) {
        check(operation.controller.signal);
        await this._writeRate(rates, operation);
        await delay(Math.min(interval, Math.max(0, durationMs - (now() - started))), operation.controller.signal);
      }
      return { sent: true, deviceVerified: false, physicalCompletionVerified: false };
    });
  }
}
