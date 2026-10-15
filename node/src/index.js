import { createNobleAdapter } from './noble-adapter.js';
import { RS4Mini as Controller } from './controller.js';

export class RS4Mini extends Controller {
  constructor(options = {}) { super({ ...options, adapter: options.adapter ?? createNobleAdapter() }); }
}

export { crc8, crc16, frame, velocityFrame, stopFrame, recenterFrame } from './protocol.js';
export { parseDumlFrame, DumlStreamDecoder, decodeGimbalTelemetry, decodeGimbalPositionCandidate } from './telemetry.js';
export { orientationFromComponents } from './orientation.js';
