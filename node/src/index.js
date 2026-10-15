import noble from "@stoprocent/noble";
import { recenterFrame, velocityFrame } from "./protocol.js";
import { DumlStreamDecoder, decodeGimbalTelemetry } from "./telemetry.js";

const SERVICE = "fff0";
const NOTIFY = "fff4";
const WRITE = "fff5";
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

export class RS4Mini {
  constructor({
    nameIncludes = "DJI RS4 MINI",
    rateHz = 15,
    deviceId = null,
    adapter = noble,
  } = {}) {
    if (!Number.isFinite(rateHz) || rateHz <= 0) throw new RangeError("rateHz must be greater than 0");
    this.nameIncludes = nameIncludes.toUpperCase();
    this.rateHz = rateHz;
    this.deviceId = deviceId;
    this.adapter = adapter;
    this.peripheral = null;
    this.rx = null;
    this.tx = null;
    this.deviceName = null;
    this.sequence = 0x0100;
    this.velocity = { pan: 0, tilt: 0, roll: 0 };
    this.streamPromise = null;
    this.streamGeneration = 0;
    this.writeChain = Promise.resolve();
    this.connectPromise = null;
    this.disconnectPromise = null;
    this.closePromise = null;
    this.cancelScan = null;
    this.pendingDirectDeviceId = null;
    this.closed = false;
    this.onNotification = null;
    this.onMessage = null;
    this.onTelemetry = null;
    this.onDisconnect = null;
    this.onError = null;
    this.latestTelemetry = null;
    this.telemetryWaiters = new Set();
    this.moveToActive = false;
    this.moveToCancelled = false;
    this.decoder = new DumlStreamDecoder();
  }

  get connected() { return this.peripheral?.state === "connected"; }

  async connect(options = {}) {
    assertKnownKeys(options, ["timeoutMs", "deviceId", "directConnectTimeoutMs"], "connect");
    if (this.closed) throw new Error("RS4Mini controller is closed; create a new instance");
    if (this.connected) return this.deviceName;
    if (this.connectPromise) return this.connectPromise;
    this.connectPromise = this._connect(options);
    try { return await this.connectPromise; }
    finally { this.connectPromise = null; }
  }

  async _connect({
    timeoutMs = 30000,
    deviceId = this.deviceId,
    directConnectTimeoutMs = 5000,
  } = {}) {
    if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) throw new RangeError("timeoutMs must be greater than 0");
    if (!Number.isFinite(directConnectTimeoutMs) || directConnectTimeoutMs <= 0)
      throw new RangeError("directConnectTimeoutMs must be greater than 0");
    const deadline = Date.now() + timeoutMs;
    await this.adapter.waitForPoweredOnAsync(timeoutMs);

    let peripheral;
    let directError = null;
    if (deviceId) {
      try {
        this.pendingDirectDeviceId = deviceId;
        const remaining = Math.max(1, deadline - Date.now());
        peripheral = await withTimeout(
          this.adapter.connectAsync(deviceId),
          Math.min(directConnectTimeoutMs, remaining),
          `Direct connection to cached RS 4 Mini timed out`,
        );
      } catch (error) {
        directError = error;
        try { this.adapter.cancelConnect(deviceId); } catch {}
        if (this.closed) throw new Error("RS 4 Mini connection was cancelled by close()");
        await sleep(200);
      } finally {
        this.pendingDirectDeviceId = null;
      }
    }

    if (!peripheral) {
      if (this.closed) throw new Error("RS 4 Mini connection was cancelled by close()");
      const remaining = Math.max(1, deadline - Date.now());
      try { peripheral = await this._scan(remaining); }
      catch (scanError) {
        if (directError) {
          throw new Error(
            `${scanError.message}; cached direct connection also failed: ${directError.message}`,
            { cause: scanError },
          );
        }
        throw scanError;
      }
      await peripheral.connectAsync();
    }

    try {
      const { characteristics } = await peripheral.discoverSomeServicesAndCharacteristicsAsync(
        [SERVICE], [NOTIFY, WRITE],
      );
      this.rx = characteristics.find(characteristic => characteristic.uuid.toLowerCase() === NOTIFY);
      this.tx = characteristics.find(characteristic => characteristic.uuid.toLowerCase() === WRITE);
      if (!this.rx || !this.tx) throw new Error("FFF4/FFF5 control characteristics were not found");
      this.peripheral = peripheral;
      this.deviceId = peripheral.id;
      this.deviceName = peripheral.advertisement?.localName || peripheral.id;
      this.decoder.reset();
      this.latestTelemetry = null;
      this.rx.on("data", (data, isNotification) => {
        if (!isNotification) return;
        const chunk = Buffer.from(data);
        this.onNotification?.(chunk);
        for (const message of this.decoder.push(chunk)) {
          this.onMessage?.(message);
          const telemetry = decodeGimbalTelemetry(message);
          if (telemetry) {
            this.latestTelemetry = telemetry;
            this._resolveTelemetryWaiters(telemetry);
            this.onTelemetry?.(telemetry);
          }
        }
      });
      peripheral.once("disconnect", reason => {
        if (this.peripheral !== peripheral) return;
        this.velocity = { pan: 0, tilt: 0, roll: 0 };
        this.moveToCancelled = true;
        void this._cancelStream();
        this._rejectTelemetryWaiters(new Error("RS 4 Mini disconnected while waiting for telemetry"));
        this.peripheral = this.rx = this.tx = null;
        this.deviceName = null;
        this.onDisconnect?.(reason);
      });
      await this.rx.subscribeAsync();
      return this.deviceName;
    } catch (error) {
      if (peripheral.state === "connected") {
        try { await peripheral.disconnectAsync(); } catch {}
      }
      this.peripheral = this.rx = this.tx = null;
      this.deviceName = null;
      throw error;
    }
  }

  async _scan(timeoutMs) {
    try {
      return await new Promise(async (resolve, reject) => {
        let settled = false;
        const cleanup = () => {
          this.adapter.removeListener("discover", discovered);
          clearTimeout(timeout);
        };
        const discovered = candidate => {
          const name = (candidate.advertisement?.localName || "").toUpperCase();
          if (!name.includes(this.nameIncludes) || settled) return;
          settled = true; cleanup(); resolve(candidate);
        };
        const timeout = setTimeout(() => {
          if (settled) return;
          settled = true; cleanup(); reject(new Error(`RS 4 Mini scan timed out after ${timeoutMs} ms`));
        }, timeoutMs);
        const cancel = message => {
          if (settled) return;
          settled = true; cleanup(); reject(new Error(message));
        };
        this.cancelScan = cancel;
        this.adapter.on("discover", discovered);
        try { await this.adapter.startScanningAsync([], true); }
        catch (error) { if (!settled) { settled = true; cleanup(); reject(error); } }
      });
    } finally {
      this.cancelScan = null;
      try { await this.adapter.stopScanningAsync(); } catch {}
    }
  }

  async setVelocity(options = {}) {
    this._assertNoMoveTo("setVelocity");
    return this._setVelocity(options);
  }

  async _setVelocity(options = {}) {
    assertKnownKeys(options, ["pan", "tilt", "roll"], "setVelocity");
    const { pan = 0, tilt = 0, roll = 0 } = options;
    this._requireConnected();
    this.velocity = {
      pan: normalizeAxis(pan, "pan"),
      tilt: normalizeAxis(tilt, "tilt"),
      roll: normalizeAxis(roll, "roll"),
    };
    if (Object.values(this.velocity).every(value => value === 0)) return this._stop();
    await this._enqueue(velocityFrame(this._nextSequence(), this.velocity));
    this._startStream();
  }

  async setVelocityDeg(options = {}) {
    assertKnownKeys(
      options,
      ["pan", "tilt", "roll", "panFullScale", "tiltFullScale", "rollFullScale"],
      "setVelocityDeg",
    );
    const {
      pan = 0,
      tilt = 0,
      roll = 0,
      panFullScale = 37.5,
      tiltFullScale = 27.5,
      rollFullScale = 30,
    } = options;
    for (const [name, value] of Object.entries({ panFullScale, tiltFullScale, rollFullScale })) {
      if (!Number.isFinite(value) || value <= 0) throw new RangeError(`${name} must be greater than 0`);
    }
    await this.setVelocity({
      pan: Number(pan) / panFullScale,
      tilt: Number(tilt) / tiltFullScale,
      roll: Number(roll) / rollFullScale,
    });
  }

  async moveFor(options = {}) {
    this._assertNoMoveTo("moveFor");
    assertKnownKeys(options, ["durationMs", "pan", "tilt", "roll"], "moveFor");
    const { durationMs, pan = 0, tilt = 0, roll = 0 } = options;
    if (!Number.isFinite(durationMs) || durationMs < 0) {
      throw new RangeError("durationMs must be a non-negative finite number");
    }
    try {
      await this.setVelocity({ pan, tilt, roll });
      await sleep(durationMs);
    } finally {
      await this.stop();
    }
  }

  async getAttitude(options = {}) {
    assertKnownKeys(options, ["fresh", "timeoutMs"], "getAttitude");
    const { fresh = false, timeoutMs = 3000 } = options;
    assertBoolean(fresh, "fresh");
    assertPositiveFinite(timeoutMs, "timeoutMs");
    this._requireConnected();

    const sample = fresh || !this.latestTelemetry
      ? await this._waitForTelemetry(timeoutMs)
      : this.latestTelemetry;
    if (!sample.attitude) throw new Error("The telemetry sample does not contain attitude data");
    return cloneAngleReading(sample.attitude, sample.timestamp);
  }

  async getJointAngles(options = {}) {
    assertKnownKeys(options, ["fresh", "timeoutMs"], "getJointAngles");
    const { fresh = false, timeoutMs = 3000 } = options;
    assertBoolean(fresh, "fresh");
    assertPositiveFinite(timeoutMs, "timeoutMs");
    this._requireConnected();

    let sample = fresh || !this.latestTelemetry
      ? await this._waitForTelemetry(timeoutMs)
      : this.latestTelemetry;
    if (!sample.jointAngles && !fresh) sample = await this._waitForTelemetry(timeoutMs);
    if (!sample.jointAngles) throw new Error("The telemetry sample does not contain joint-angle data");
    return cloneAngleReading(sample.jointAngles, sample.timestamp);
  }

  async moveTo(options = {}) {
    assertKnownKeys(
      options,
      [
        "pan", "tilt", "roll", "toleranceDeg", "timeoutMs", "telemetryTimeoutMs",
        "gain", "minSpeed", "maxSpeed",
      ],
      "moveTo",
    );
    const {
      pan,
      tilt,
      roll,
      toleranceDeg = 1,
      timeoutMs = 30_000,
      telemetryTimeoutMs = 3000,
      gain = 0.02,
      minSpeed = 0.05,
      maxSpeed = 0.18,
    } = options;
    this._requireConnected();
    if (pan === undefined && tilt === undefined && roll === undefined) {
      throw new TypeError("moveTo requires at least one of pan, tilt, or roll");
    }
    const target = {
      pan: pan === undefined ? undefined : normalizeTargetAngle(pan, "pan"),
      tilt: tilt === undefined ? undefined : normalizeTargetAngle(tilt, "tilt"),
      roll: roll === undefined ? undefined : normalizeTargetAngle(roll, "roll"),
    };
    assertPositiveFinite(toleranceDeg, "toleranceDeg");
    assertPositiveFinite(timeoutMs, "timeoutMs");
    assertPositiveFinite(telemetryTimeoutMs, "telemetryTimeoutMs");
    assertPositiveFinite(gain, "gain");
    assertUnitInterval(minSpeed, "minSpeed");
    assertUnitInterval(maxSpeed, "maxSpeed");
    if (minSpeed > maxSpeed) throw new RangeError("minSpeed must not be greater than maxSpeed");
    if (this.moveToActive) throw new Error("Another moveTo operation is already active");

    this.moveToActive = true;
    this.moveToCancelled = false;
    const startedAt = Date.now();
    const deadline = startedAt + timeoutMs;
    let current = null;
    try {
      current = await this.getJointAngles({
        fresh: true,
        timeoutMs: Math.min(telemetryTimeoutMs, Math.max(1, deadline - Date.now())),
      });
      this._throwIfMoveToCancelled();
      while (true) {
        const errors = {
          pan: target.pan === undefined ? 0 : shortestAngleDelta(target.pan, current.yaw),
          tilt: target.tilt === undefined ? 0 : target.tilt - current.pitch,
          roll: target.roll === undefined ? 0 : target.roll - current.roll,
        };
        const activeErrors = [
          target.pan === undefined ? null : Math.abs(errors.pan),
          target.tilt === undefined ? null : Math.abs(errors.tilt),
          target.roll === undefined ? null : Math.abs(errors.roll),
        ].filter(value => value !== null);

        if (activeErrors.every(error => error <= toleranceDeg)) {
          return {
            target: { ...target },
            current: jointToAxes(current),
            error: errors,
            toleranceDeg,
            elapsedMs: Date.now() - startedAt,
          };
        }
        if (Date.now() >= deadline) {
          const error = new Error(
            `moveTo timed out after ${timeoutMs} ms; final joint angles: ` +
            JSON.stringify(jointToAxes(current)),
          );
          error.code = "RS4MINI_MOVE_TIMEOUT";
          error.target = { ...target };
          error.current = jointToAxes(current);
          throw error;
        }

        await this._setVelocity({
          pan: target.pan === undefined ? 0 : proportionalSpeed(errors.pan, { gain, minSpeed, maxSpeed }),
          // RS 4 Mini's positive virtual-stick Tilt direction decreases the decoded joint Pitch.
          tilt: target.tilt === undefined ? 0 : -proportionalSpeed(errors.tilt, { gain, minSpeed, maxSpeed }),
          roll: target.roll === undefined ? 0 : proportionalSpeed(errors.roll, { gain, minSpeed, maxSpeed }),
        });

        const remaining = deadline - Date.now();
        if (remaining <= 0) continue;
        current = await this.getJointAngles({
          fresh: true,
          timeoutMs: Math.min(telemetryTimeoutMs, remaining),
        });
        this._throwIfMoveToCancelled();
      }
    } catch (error) {
      if (this.moveToCancelled) {
        const cancelled = new Error("moveTo was cancelled by stop() or disconnection", { cause: error });
        cancelled.code = "RS4MINI_MOVE_CANCELLED";
        throw cancelled;
      }
      throw error;
    } finally {
      this.moveToActive = false;
      this.moveToCancelled = false;
      await this._stop();
    }
  }

  async stop() {
    if (this.moveToActive) this.moveToCancelled = true;
    return this._stop();
  }

  async _stop() {
    this.velocity = { pan: 0, tilt: 0, roll: 0 };
    await this._cancelStream();
    if (!this.connected) return;
    for (let index = 0; index < 3; index++) {
      await this._enqueue(velocityFrame(this._nextSequence()));
      await sleep(1000 / this.rateHz);
    }
  }

  async recenter() {
    this._assertNoMoveTo("recenter");
    this._requireConnected();
    await this.stop();
    await this._enqueue(recenterFrame(this._nextSequence()));
  }

  async disconnect() {
    if (this.disconnectPromise) return this.disconnectPromise;
    this.disconnectPromise = this._disconnect();
    try { await this.disconnectPromise; }
    finally { this.disconnectPromise = null; }
  }

  async close() {
    if (this.closePromise) return this.closePromise;
    this.closed = true;
    this.closePromise = this._close();
    return this.closePromise;
  }

  async _close() {
    this.cancelScan?.("RS 4 Mini connection was cancelled by close()");
    if (this.pendingDirectDeviceId) {
      try { this.adapter.cancelConnect(this.pendingDirectDeviceId); } catch {}
    }
    await this.disconnect();
    try {
      await withTimeout(this.adapter.stopScanningAsync(), 1000, "BLE scan stop timed out");
    } catch {}
    this.adapter.stop?.();
  }

  async _disconnect() {
    this.velocity = { pan: 0, tilt: 0, roll: 0 };
    this.moveToCancelled = true;
    this._rejectTelemetryWaiters(new Error("RS 4 Mini disconnected while waiting for telemetry"));
    await this._cancelStream();
    if (!this.peripheral) return;
    const peripheral = this.peripheral;
    const rx = this.rx;
    if (this.connected) {
      await this.stop();
      try { await rx?.unsubscribeAsync(); } catch {}
      try { await withTimeout(peripheral.disconnectAsync(), 3000, "BLE disconnect timed out"); } catch {}
    }
    this.peripheral = this.rx = this.tx = null;
    this.deviceName = null;
  }

  _enqueue(packet) {
    this.writeChain = this.writeChain.catch(() => {}).then(async () => {
      this._requireConnected();
      for (let offset = 0; offset < packet.length; offset += 20)
        await this.tx.writeAsync(packet.subarray(offset, offset + 20), true);
    });
    return this.writeChain;
  }

  _nextSequence() {
    const current = this.sequence;
    this.sequence = (this.sequence + 1) & 0xffff;
    return current;
  }

  _startStream() {
    if (this.streamPromise) return;
    const generation = ++this.streamGeneration;
    this.streamPromise = (async () => {
      while (this.connected && generation === this.streamGeneration) {
        await sleep(1000 / this.rateHz);
        if (!this.connected || generation !== this.streamGeneration) break;
        if (Object.values(this.velocity).every(value => value === 0)) break;
        await this._enqueue(velocityFrame(this._nextSequence(), this.velocity));
      }
    })().catch(error => this.onError?.(error)).finally(() => {
      if (generation === this.streamGeneration) this.streamPromise = null;
    });
  }

  _waitForTelemetry(timeoutMs) {
    this._requireConnected();
    return new Promise((resolve, reject) => {
      const waiter = {
        resolve: telemetry => {
          clearTimeout(waiter.timer);
          this.telemetryWaiters.delete(waiter);
          resolve(telemetry);
        },
        reject: error => {
          clearTimeout(waiter.timer);
          this.telemetryWaiters.delete(waiter);
          reject(error);
        },
        timer: null,
      };
      waiter.timer = setTimeout(
        () => waiter.reject(new Error(`Timed out waiting for RS 4 Mini telemetry after ${timeoutMs} ms`)),
        timeoutMs,
      );
      this.telemetryWaiters.add(waiter);
    });
  }

  _resolveTelemetryWaiters(telemetry) {
    for (const waiter of [...this.telemetryWaiters]) waiter.resolve(telemetry);
  }

  _rejectTelemetryWaiters(error) {
    for (const waiter of [...this.telemetryWaiters]) waiter.reject(error);
  }

  async _cancelStream() {
    this.streamGeneration++;
    const pending = this.streamPromise;
    this.streamPromise = null;
    if (pending) await pending;
  }

  _requireConnected() {
    if (!this.connected || !this.tx) throw new Error("RS 4 Mini is not connected");
  }

  _assertNoMoveTo(methodName) {
    if (this.moveToActive) {
      throw new Error(`${methodName} cannot run while moveTo is active; call stop() to cancel it first`);
    }
  }

  _throwIfMoveToCancelled() {
    if (this.moveToCancelled) throw new Error("moveTo cancellation requested");
  }
}

function normalizeAxis(value, name) {
  const number = Number(value);
  if (!Number.isFinite(number)) throw new TypeError(`${name} must be a finite number`);
  return Math.max(-1, Math.min(1, number));
}

function normalizeTargetAngle(value, name) {
  const number = Number(value);
  if (!Number.isFinite(number)) throw new TypeError(`${name} must be a finite number`);
  if (number < -180 || number > 180) throw new RangeError(`${name} must be between -180 and 180 degrees`);
  return number;
}

function assertBoolean(value, name) {
  if (typeof value !== "boolean") throw new TypeError(`${name} must be a boolean`);
}

function assertPositiveFinite(value, name) {
  if (!Number.isFinite(value) || value <= 0) throw new RangeError(`${name} must be greater than 0`);
}

function assertUnitInterval(value, name) {
  if (!Number.isFinite(value) || value < 0 || value > 1) {
    throw new RangeError(`${name} must be between 0 and 1`);
  }
}

function cloneAngleReading(reading, timestamp) {
  return {
    ...reading,
    raw: reading.raw ? { ...reading.raw } : reading.raw,
    timestamp,
  };
}

function shortestAngleDelta(target, current) {
  return ((target - current + 540) % 360) - 180;
}

function proportionalSpeed(error, { gain, minSpeed, maxSpeed }) {
  if (error === 0) return 0;
  const magnitude = Math.min(maxSpeed, Math.max(minSpeed, Math.abs(error) * gain));
  return Math.sign(error) * magnitude;
}

function jointToAxes(joint) {
  return { pan: joint.yaw, tilt: joint.pitch, roll: joint.roll };
}

function assertKnownKeys(options, allowedKeys, methodName) {
  if (!options || typeof options !== "object" || Array.isArray(options)) {
    throw new TypeError(`${methodName} options must be an object`);
  }
  const unknown = Object.keys(options).filter(key => !allowedKeys.includes(key));
  if (unknown.length) {
    throw new TypeError(
      `${methodName} received unknown option${unknown.length === 1 ? "" : "s"}: ${unknown.join(", ")}`,
    );
  }
}

function withTimeout(promise, timeoutMs, message) {
  let timer;
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error(message)), timeoutMs);
  });
  return Promise.race([promise, timeout]).finally(() => clearTimeout(timer));
}

export { crc8, crc16, frame, velocityFrame, stopFrame, recenterFrame } from "./protocol.js";
export {
  parseDumlFrame,
  DumlStreamDecoder,
  decodeGimbalTelemetry,
  decodeGimbalPositionCandidate,
} from "./telemetry.js";
