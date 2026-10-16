import { AppCommands } from './app-commands.js';
// Device access only. No dependency on controller, trajectories or position algorithms.
import { recenterFrame, velocityFrame } from './protocol.js';
import { DumlStreamDecoder, decodeGimbalTelemetry } from './telemetry.js';
import { bounded, check, deferred, delay, failure, now } from './async.js';
import { bytes } from './bytes.js';
import { ExperimentalDevice } from './experimental-device.js';
import { rs3RateFrame } from './experimental-protocol.js';
import { known, positive, velocity } from './values.js';

const SERVICE = 'fff0', NOTIFY = 'fff4', WRITE = 'fff5';
const zero = () => ({ pan: 0, tilt: 0, roll: 0 });
const copy = value => value == null ? value : structuredClone(value);

export class BleDevice {
  constructor({ nameIncludes = 'DJI RS4 MINI', rateHz = 15, deviceId = null, adapter, ioTimeoutMs = 3000 } = {}) {
    positive(rateHz, 'rateHz'); positive(ioTimeoutMs, 'ioTimeoutMs');
    if (typeof nameIncludes !== 'string' || !nameIncludes.trim()) throw new TypeError('nameIncludes must be a nonempty string');
    if (!adapter) throw new TypeError('A BLE adapter is required');
    this.nameIncludes = nameIncludes.toUpperCase(); this.rateHz = rateHz; this.ioTimeoutMs = ioTimeoutMs;
    this.deviceId = deviceId; this.adapter = adapter;
    this.peripheral = this.rx = this.tx = this.deviceName = null;
    this.session = null; this.connection = null;
    this.sequence = 0x0100; this._velocity = zero(); this.streamPromise = null; this.streamController = null;
    this.writeChain = Promise.resolve(); this.motionEpoch = 0;
    this.connectPromise = this.disconnectPromise = this.closePromise = this.stopPromise = null;
    this.operation = null; this.closed = false;
    this.onNotification = this.onMessage = this.onTelemetry = this.onDisconnect = this.onError = null;
    this._latestTelemetry = null; this.telemetryWaiters = new Set();
    this.decoder = new DumlStreamDecoder(); this.cleanupTasks = new Set();
    this.reconnectPolicy = null; this.reconnectTask = null; this.reconnectController = null;
    this._reconnectState = { state: 'disabled', attempt: 0 }; this.onReconnect = null;
    this.experimental = new ExperimentalDevice(this); this.onExperimentalStatus = null;
    this.appCommands = new AppCommands(this); this.onAppStatus = null;
  }

  get connected() { return !!this.session?.ready && this.peripheral?.state === 'connected'; }

  get activeOperation() { return this.operation?.kind || (this.stopPromise ? 'stop' : null); }

  get velocity() { return { ...this._velocity }; }

  get latestTelemetry() { return copy(this._latestTelemetry); }

  get reconnectState() { return copy(this._reconnectState); }

  async connect(options = {}) {
    known(options, ['timeoutMs', 'deviceId', 'directConnectTimeoutMs'], 'connect');
    const { timeoutMs = 30000, deviceId = this.deviceId, directConnectTimeoutMs = 5000 } = options;
    positive(timeoutMs, 'timeoutMs'); positive(directConnectTimeoutMs, 'directConnectTimeoutMs');
    if (deviceId !== null && (typeof deviceId !== 'string' || !deviceId)) throw new TypeError('deviceId must be a string or null');
    if (this.closed) throw new Error('RS4Mini controller is closed; create a new instance');
    if (this.disconnectPromise) throw failure('RS4MINI_BUSY', 'disconnect is active');
    if (this.connectPromise) return this.connectPromise;
    if (this.connected) return this.deviceName;
    const context = { controller: new AbortController(), deadline: now() + timeoutMs, peripheral: null, deviceId };
    this.connection = context;
    const promise = this._connect(context, deviceId, directConnectTimeoutMs);
    this.connectPromise = promise;
    try { return await promise; }
    finally { if (this.connection === context) this.connection = null; if (this.connectPromise === promise) this.connectPromise = null; }
  }

  _connectionWait(context, work, stage, cap = Infinity, late) {
    const remaining = context.deadline - now();
    if (remaining <= 0) return Promise.reject(failure('RS4MINI_CONNECT_TIMEOUT', `RS 4 Mini connection timed out during ${stage}`));
    return bounded(work, Math.min(cap, remaining), { signal: context.controller.signal,
      error: failure('RS4MINI_CONNECT_TIMEOUT', `RS 4 Mini connection timed out during ${stage}`), late });
  }

  async _connect(context, deviceId, directTimeout) {
    let session;
    const disposeLate = peripheral => this._discardPeripheral(peripheral);
    try {
      await this._waitForPower(context);
      if (deviceId) {
        try {
          context.peripheral = await this._connectionWait(context, () => this.adapter.connectAsync(deviceId), 'cached connection', directTimeout, disposeLate);
        } catch (error) {
          try { this.adapter.cancelConnect?.(deviceId); } catch {}
          check(context.controller.signal);
          if (now() >= context.deadline) throw error;
        }
      }
      if (!context.peripheral) {
        context.peripheral = await this._scan(context);
        const candidate = context.peripheral;
        await this._connectionWait(context, () => candidate.connectAsync(), 'peripheral connection', Infinity, () => disposeLate(candidate));
      }
      check(context.controller.signal);
      const peripheral = context.peripheral;
      session = { peripheral, rx: null, tx: null, ready: false, controller: new AbortController() };
      this.session = session;
      session.disconnected = reason => this._lostSession(session, reason);
      peripheral.on('disconnect', session.disconnected);
      const { characteristics } = await this._connectionWait(context,
        () => peripheral.discoverSomeServicesAndCharacteristicsAsync([SERVICE], [NOTIFY, WRITE]), 'GATT discovery');
      session.rx = characteristics.find(item => item.uuid.toLowerCase() === NOTIFY);
      session.tx = characteristics.find(item => item.uuid.toLowerCase() === WRITE);
      if (!session.rx || !session.tx) throw new Error('FFF4/FFF5 control characteristics were not found');
      session.data = (data, notification) => { if (notification && this.session === session) this._notification(data); };
      session.rx.on('data', session.data);
      this.decoder.reset(); this._latestTelemetry = null;
      await this._connectionWait(context, () => session.rx.subscribeAsync(), 'notification subscription', Infinity, () => {
        if (this.session?.peripheral !== peripheral) this._background(() => session.rx.unsubscribeAsync());
      });
      check(context.controller.signal); check(session.controller.signal);
      this.peripheral = peripheral; this.rx = session.rx; this.tx = session.tx;
      this.deviceId = peripheral.id; this.deviceName = peripheral.advertisement?.localName || peripheral.id;
      session.ready = true;
      return this.deviceName;
    } catch (error) {
      context.controller.abort(error);
      if (session) this._invalidate(session, error);
      if (context.peripheral) this._discardPeripheral(context.peripheral);
      throw error;
    }
  }

  async _waitForPower(context) {
    // Noble's convenience waiter keeps its own timeout alive after cancellation.
    // Own this listener instead so close/disconnect releases it immediately.
    if (typeof this.adapter.state !== 'string')
      return this._connectionWait(context, () => this.adapter.waitForPoweredOnAsync(context.deadline - now()), 'Bluetooth power');
    let listener;
    const powered = new Promise((resolve, reject) => {
      listener = state => {
        if (state === 'poweredOn') resolve();
        else if (state === 'unauthorized' || state === 'unsupported') reject(failure('RS4MINI_BLUETOOTH_UNAVAILABLE', `Bluetooth state: ${state}`));
      };
      this.adapter.on('stateChange', listener);
      listener(this.adapter.state);
    });
    try { await this._connectionWait(context, powered, 'Bluetooth power'); }
    finally { this.adapter.removeListener('stateChange', listener); }
  }

  async _scan(context) {
    const found = deferred();
    const discovered = peripheral => {
      const normalize = name => name.toUpperCase().replace(/\s/g, '');
      const name = peripheral.advertisement?.localName || '';
      if (normalize(name).includes(normalize(this.nameIncludes))) found.resolve(peripheral);
    };
    this.adapter.on('discover', discovered);
    try {
      await this._connectionWait(context, () => this.adapter.startScanningAsync([], true), 'scan start', Infinity,
        () => { if (!this.connection || this.connection === context) this._background(() => this.adapter.stopScanningAsync()); });
      return await this._connectionWait(context, found.promise, 'scan');
    } finally {
      this.adapter.removeListener('discover', discovered);
      const work = () => this.adapter.stopScanningAsync();
      if (!context.controller.signal.aborted && now() < context.deadline) {
        try { await this._connectionWait(context, work, 'scan stop'); } catch (error) { context.controller.abort(error); throw error; }
      } else this._background(work);
    }
  }

  _background(work) {
    const task = bounded(work, this.ioTimeoutMs).catch(error => this._report(error));
    this.cleanupTasks.add(task); task.finally(() => this.cleanupTasks.delete(task)); return task;
  }

  _discardPeripheral(peripheral) {
    if (this.session?.peripheral === peripheral) return;
    if (this.connection && !this.connection.controller.signal.aborted &&
      (this.connection.peripheral === peripheral || this.connection.deviceId === peripheral.id)) return;
    try { this.adapter.cancelConnect?.(peripheral.id); } catch {}
    return this._background(() => peripheral.disconnectAsync());
  }

  _invalidate(session, reason) {
    session.ready = false; session.controller.abort(reason);
    if (session.data) session.rx?.removeListener('data', session.data);
    if (session.disconnected) session.peripheral.removeListener('disconnect', session.disconnected);
    if (this.session !== session) return;
    this.session = null; this.peripheral = this.rx = this.tx = this.deviceName = null;
    this._latestTelemetry = null; this.decoder.reset(); this._velocity = zero(); this.motionEpoch++;
    this._nativeRateProfile = null; this.experimental._reset(); this.appCommands._reset();
    this.streamController?.abort(reason); this.operation?.controller.abort(reason); this._rejectWaiters(reason);
  }

  _lostSession(session, reason) {
    if (this.session !== session) return;
    const wasReady = session.ready;
    const error = failure('RS4MINI_DISCONNECTED', 'RS 4 Mini disconnected', { cause: reason });
    this.connection?.controller.abort(error); this._invalidate(session, error); this._emit('onDisconnect', reason);
    if (wasReady) this._scheduleReconnect();
  }

  enableAutoReconnect(options = {}) {
    known(options, ['maxAttempts', 'initialDelayMs', 'maxDelayMs', 'backoff', 'timeoutMs', 'directConnectTimeoutMs'], 'enableAutoReconnect');
    if (this.closed) throw new Error('RS4Mini controller is closed');
    const policy = { maxAttempts: 5, initialDelayMs: 500, maxDelayMs: 10000, backoff: 2, timeoutMs: 10000, directConnectTimeoutMs: 5000, ...options };
    for (const [name, value] of Object.entries(policy)) positive(value, name);
    for (const name of ['initialDelayMs', 'maxDelayMs', 'timeoutMs', 'directConnectTimeoutMs'])
      if (policy[name] > 0x7fffffff) throw new RangeError(`${name} exceeds timer range`);
    if (!Number.isSafeInteger(policy.maxAttempts) || policy.maxAttempts > 100 || policy.backoff < 1 || policy.maxDelayMs < policy.initialDelayMs)
      throw new RangeError('invalid reconnect retry policy');
    this.reconnectPolicy = policy;
    if (!this.reconnectTask) this._reconnectStatus('idle', 0);
  }

  async disableAutoReconnect() {
    this._cancelReconnect();
    await this.reconnectTask;
  }

  _cancelReconnect() {
    this.reconnectPolicy = null;
    const reason = failure('RS4MINI_CONNECT_CANCELLED', 'Automatic reconnect cancelled');
    this.reconnectController?.abort(reason);
    if (this.connection?.reconnectOwner === this.reconnectController) this.connection.controller.abort(reason);
    this._reconnectStatus('disabled', 0);
  }

  _reconnectStatus(state, attempt, extra = {}) {
    this._reconnectState = { state, attempt, ...extra };
    this._emit('onReconnect', this.reconnectState);
  }

  _scheduleReconnect() {
    if (!this.reconnectPolicy || this.closed || this.disconnectPromise) return;
    if (this.reconnectTask) { this.reconnectAgain = true; return; }
    const controller = new AbortController(), policy = { ...this.reconnectPolicy };
    this.reconnectController = controller;
    const task = (async () => {
      // Drain old ownership and late cleanup before reusing a peripheral.
      await Promise.allSettled([this.connectPromise, this.operation?.done.promise, this.streamPromise, this.writeChain, ...this.cleanupTasks]);
      for (let attempt = 1; attempt <= policy.maxAttempts; attempt++) {
        check(controller.signal);
        if (this.connected) { this._reconnectStatus('restored', attempt - 1); return; }
        const delayMs = Math.min(policy.maxDelayMs, policy.initialDelayMs * policy.backoff ** (attempt - 1));
        this._reconnectStatus('waiting', attempt, { delayMs });
        await delay(delayMs, controller.signal); check(controller.signal);
        this._reconnectStatus('connecting', attempt); check(controller.signal);
        try {
          let pending;
          this._autoConnecting = true;
          try { pending = this.connect({ timeoutMs: policy.timeoutMs, directConnectTimeoutMs: policy.directConnectTimeoutMs }); }
          finally { this._autoConnecting = false; }
          if (this.connection) this.connection.reconnectOwner = controller;
          await pending; check(controller.signal);
          this._reconnectStatus('restored', attempt); return;
        } catch (error) {
          check(controller.signal);
          if (attempt === policy.maxAttempts) this._reconnectStatus('exhausted', attempt, { error: { code: error.code, message: error.message } });
        }
      }
    })().catch(error => { if (!controller.signal.aborted) this._report(error); });
    this.reconnectTask = task;
    task.finally(() => {
      if (this.reconnectTask === task) {
        this.reconnectTask = null; this.reconnectController = null;
        const again = this.reconnectAgain; this.reconnectAgain = false;
        if (again && !this.connected) this._scheduleReconnect();
      }
    });
  }

  _notification(data) {
    let messages;
    try { messages = this.decoder.push(data); } catch (error) { this._report(error); return; }
    this._emit('onNotification', bytes(data));
    for (const message of messages) {
      this.experimental._message(message);
      this.appCommands._message(message);
      const telemetry = decodeGimbalTelemetry(message);
      if (telemetry) {
        this._latestTelemetry = telemetry;
        for (const waiter of [...this.telemetryWaiters]) if (telemetry[waiter.field]) waiter.resolve(telemetry);
      }
      this._emit('onMessage', { ...message, raw: bytes(message.raw), payload: bytes(message.payload) });
      if (telemetry) this._emit('onTelemetry', copy(telemetry));
    }
  }

  _emit(name, value) {
    try {
      const result = this[name]?.(value);
      if (result?.then) Promise.resolve(result).catch(error => { if (name !== 'onError') this._report(error); });
    } catch (error) { if (name !== 'onError') this._report(error); }
  }

  _report(error) { this._emit('onError', error); }

  _requireConnected() { if (!this.connected) throw failure('RS4MINI_DISCONNECTED', 'RS 4 Mini is not connected'); }

  _begin(kind) {
    this._requireConnected();
    if (this.closed || this.disconnectPromise || this.connectPromise || this.stopPromise || this.operation) {
      const active = this.operation?.kind || (this.stopPromise ? 'stop' : 'connection cleanup');
      throw failure('RS4MINI_BUSY', `${kind} cannot run while ${active} is active`);
    }
    const operation = { kind, controller: new AbortController(), done: deferred(), haltPromise: null };
    this.operation = operation; return operation;
  }

  async _run(kind, body, stopAfter = true, { cancelAsMove = false } = {}) {
    const operation = this._begin(kind);
    let result, error;
    try {
      if (kind !== 'setVelocity' && (this.streamPromise || Object.values(this.velocity).some(value => value !== 0))) {
        await this._stop(); check(operation.controller.signal);
      }
      result = await body(operation); check(operation.controller.signal);
    }
    catch (reason) { error = operation.controller.signal.reason?.code === 'RS4MINI_MOVE_TIMEOUT' ? operation.controller.signal.reason : reason; }
    finally {
      if (stopAfter || error) {
        try { await (operation.haltPromise ||= this._stop()); }
        catch (cleanupError) { if (error) error.cleanupError = cleanupError; else error = cleanupError; }
      }
      if (this.operation === operation) this.operation = null;
      operation.done.resolve();
    }
    if (error) {
      if (operation.controller.signal.aborted && cancelAsMove && operation.controller.signal.reason.code !== 'RS4MINI_MOVE_TIMEOUT')
        throw failure('RS4MINI_MOVE_CANCELLED', `${kind} was cancelled by stop() or disconnection`, { cause: error, cleanupError: error.cleanupError });
      throw error;
    }
    return result;
  }

  async setVelocity(options = {}) {
    const values = velocity(options);
    return this._run('setVelocity', operation => this._setVelocity(values, operation), false);
  }

  async _setVelocity(values, operation) {
    check(operation.controller.signal); this._velocity = { ...values };
    if (Object.values(values).every(value => value === 0)) return this._stop();
    const epoch = this.motionEpoch;
    await this._writeVelocity(values, operation, epoch);
    check(operation.controller.signal); this._startStream();
  }

  async _reading(kind, options = {}, signal) {
    known(options, ['fresh', 'timeoutMs'], kind === 'jointAngles' ? 'getJointAngles' : 'getAttitude');
    const { fresh = false, timeoutMs = 3000 } = options;
    if (typeof fresh !== 'boolean') throw new TypeError('fresh must be boolean');
    positive(timeoutMs, 'timeoutMs'); this._requireConnected(); check(signal);
    const sample = !fresh && this.latestTelemetry?.[kind] ? this.latestTelemetry :
      await this._waitForTelemetry(timeoutMs, { signal, joints: kind === 'jointAngles' });
    return { ...copy(sample[kind]), timestamp: sample.timestamp };
  }

  requestDegreeInfo(options = {}) {
    known(options, ['timeoutMs'], 'requestDegreeInfo');
    return this.experimental._queryCommand('degreeInfo', [4, 0x1e], options.timeoutMs ?? 3000);
  }

  getAttitude(options = {}) { return this._reading('attitude', options); }

  getJointAngles(options = {}) { return this._reading('jointAngles', options); }

  async stop() {
    const operation = this.operation;
    operation?.controller.abort(failure('RS4MINI_OPERATION_CANCELLED', 'Operation cancelled by stop()'));
    const stopping = operation ? (operation.haltPromise ||= this._stop()) : this._stop();
    let error;
    try { await stopping; } catch (reason) { error = reason; }
    await operation?.done.promise;
    if (error) throw error;
  }

  _stop() {
    if (this.stopPromise) return this.stopPromise;
    this._velocity = zero(); this.motionEpoch++;
    const nativeRate = this._nativeRateProfile; this._nativeRateProfile = null;
    this.streamController?.abort(failure('RS4MINI_OPERATION_CANCELLED', 'Velocity stream stopped'));
    const promise = (async () => {
      await this.streamPromise;
      if (!this.connected) return;
      if (nativeRate) await this._enqueue(rs3RateFrame(this._nextSequence(), {}, true));
      for (let index = 0; index < 3; index++) { await this._enqueue(velocityFrame(this._nextSequence())); await delay(1000 / this.rateHz); }
    })();
    this.stopPromise = promise;
    promise.then(() => { if (this.stopPromise === promise) this.stopPromise = null; }, () => { if (this.stopPromise === promise) this.stopPromise = null; });
    return promise;
  }

  async recenter() {
    return this._run('recenter', async operation => {
      await this._stop(); check(operation.controller.signal);
      await this._enqueue(recenterFrame(this._nextSequence()), { signal: operation.controller.signal, epoch: this.motionEpoch });
    });
  }

  disconnect() {
    this._cancelReconnect();
    if (this.disconnectPromise) return this.disconnectPromise;
    this.connection?.controller.abort(failure('RS4MINI_CONNECT_CANCELLED', `RS 4 Mini connection was cancelled by ${this.closed ? 'close' : 'disconnect'}()`));
    if (this.connection) try { this.adapter.cancelConnect?.(this.connection.peripheral?.id || this.connection.deviceId); } catch {}
    const promise = this._disconnect(); this.disconnectPromise = promise;
    promise.then(() => { if (this.disconnectPromise === promise) this.disconnectPromise = null; }, () => { if (this.disconnectPromise === promise) this.disconnectPromise = null; });
    return promise;
  }

  async _disconnect() {
    let error; const session = this.session;
    this._rejectWaiters(failure('RS4MINI_DISCONNECTED', 'RS 4 Mini disconnected while waiting for telemetry'));
    try { await this.stop(); } catch (reason) { error = reason; }
    try {
      if (this.connectPromise) await this.connectPromise.catch(() => {});
      await this.reconnectTask;
      if (session && this.session === session) {
        this._invalidate(session, failure('RS4MINI_DISCONNECTED', 'RS 4 Mini disconnected'));
        try { if (session.rx) await bounded(() => session.rx.unsubscribeAsync(), this.ioTimeoutMs); } catch (reason) { error ||= reason; }
        try { await bounded(() => session.peripheral.disconnectAsync(), this.ioTimeoutMs); } catch (reason) { error ||= reason; }
        this._emit('onDisconnect');
      }
    } finally { if (session && this.session === session) this._invalidate(session, failure('RS4MINI_DISCONNECTED', 'Disconnected')); }
    if (error) throw error;
  }

  close() {
    if (this.closePromise) return this.closePromise;
    this.closed = true;
    this.closePromise = (async () => {
      try { await this.disconnect(); }
      finally {
        await Promise.allSettled([...this.cleanupTasks]);
        try { await bounded(() => this.adapter.stopScanningAsync(), this.ioTimeoutMs); } finally { this.adapter.stop?.(); }
      }
    })();
    return this.closePromise;
  }

  _enqueue(packet, { signal, epoch } = {}) {
    const session = this.session;
    const promise = this.writeChain.catch(() => {}).then(async () => {
      check(signal);
      if (!session || this.session !== session || !session.ready) throw failure('RS4MINI_DISCONNECTED', 'BLE session changed before write');
      if (epoch !== undefined && epoch !== this.motionEpoch) throw failure('RS4MINI_OPERATION_CANCELLED', 'Queued motion was cancelled');
      try {
        // Finish a started DUML frame before stopping; never interleave its GATT chunks.
        for (let offset = 0; offset < packet.length; offset += 20) {
          check(session.controller.signal);
          await bounded(() => session.tx.writeAsync(packet.subarray(offset, offset + 20), true), this.ioTimeoutMs, { signal: session.controller.signal });
        }
      } catch (error) {
        const wasReady = session.ready;
        this._invalidate(session, error); this._discardPeripheral(session.peripheral);
        if (wasReady) this._emit('onDisconnect', error);
        if (wasReady) this._scheduleReconnect();
        throw error;
      }
    });
    this.writeChain = promise; return promise;
  }

  _nextSequence() {
    while (this.experimental.pending.has(this.sequence)) this.sequence = (this.sequence + 1) & 0xffff;
    const current = this.sequence; this.sequence = (current + 1) & 0xffff; return current;
  }

  _startStream() {
    if (this.streamPromise) return;
    const controller = new AbortController(), epoch = this.motionEpoch;
    this.streamController = controller;
    const promise = (async () => {
      while (this.connected && Object.values(this.velocity).some(value => value !== 0)) {
        await delay(1000 / this.rateHz, controller.signal);
        await this._enqueue(velocityFrame(this._nextSequence(), this.velocity), { signal: controller.signal, epoch });
      }
    })().catch(error => {
      if (!controller.signal.aborted || !['RS4MINI_OPERATION_CANCELLED', 'RS4MINI_DISCONNECTED'].includes(error.code)) this._report(error);
    });
    this.streamPromise = promise;
    promise.then(() => { if (this.streamPromise === promise) { this.streamPromise = null; this.streamController = null; } });
  }

  _waitForTelemetry(timeoutMs, { signal, joints = false, field = joints ? 'jointAngles' : 'attitude' } = {}) {
    this._requireConnected(); check(signal);
    return new Promise((resolve, reject) => {
      let timer;
      const cleanup = () => { clearTimeout(timer); this.telemetryWaiters.delete(waiter); signal?.removeEventListener('abort', abort); };
      const waiter = { field, resolve: value => { cleanup(); resolve(value); }, reject: error => { cleanup(); reject(error); } };
      const abort = () => waiter.reject(signal.reason);
      this.telemetryWaiters.add(waiter); signal?.addEventListener('abort', abort, { once: true });
      timer = setTimeout(() => waiter.reject(failure('RS4MINI_TELEMETRY_TIMEOUT', `Timed out waiting for RS 4 Mini telemetry after ${timeoutMs} ms`)), timeoutMs);
    });
  }

  _rejectWaiters(error) { for (const waiter of [...this.telemetryWaiters]) waiter.reject(error); }

  _writeVelocity(values, operation, epoch = this.motionEpoch) {
    this._velocity = { ...values };
    return this._enqueue(velocityFrame(this._nextSequence(), values), { signal: operation.controller.signal, epoch });
  }
}
