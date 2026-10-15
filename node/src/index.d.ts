export interface AxisValues {
  pan?: number;
  tilt?: number;
  roll?: number;
}

/** Minimal Node.js Buffer surface exposed without requiring @types/node. */
export interface ByteBuffer extends Uint8Array {
  toString(encoding?: string): string;
  subarray(begin?: number, end?: number): ByteBuffer;
  readInt8(offset: number): number;
  readInt16LE(offset: number): number;
  readUInt16LE(offset: number): number;
  readFloatLE(offset: number): number;
}

export interface Velocity extends Required<AxisValues> {}

export interface RS4MiniOptions {
  nameIncludes?: string;
  rateHz?: number;
  deviceId?: string | null;
  /** Custom Noble-compatible adapter; primarily intended for tests. */
  adapter?: unknown;
}

export interface ConnectOptions {
  timeoutMs?: number;
  deviceId?: string | null;
  directConnectTimeoutMs?: number;
}

export interface VelocityDegOptions extends AxisValues {
  panFullScale?: number;
  tiltFullScale?: number;
  rollFullScale?: number;
}

export interface MoveForOptions extends AxisValues {
  durationMs: number;
}

export interface TelemetryReadOptions {
  /** Wait for the next telemetry frame instead of returning the cached sample. */
  fresh?: boolean;
  timeoutMs?: number;
}

export interface RawAngles {
  pitch: number;
  roll: number;
  yaw: number;
}

export interface AttitudeReading {
  pitch: number;
  roll: number;
  yaw: number;
  unit: "deg";
  wrap: 180;
  raw: RawAngles;
  timestamp: number;
}

export interface JointAnglesReading {
  pitch: number;
  roll: number;
  yaw: number;
  unit: "deg";
  raw: RawAngles;
  timestamp: number;
}

export interface OrientationQuaternion {
  components: [number, number, number, number];
  norm: number;
  componentOrder: "unverified";
}

export interface GimbalTelemetry {
  kind: "gimbal-telemetry";
  verified: true;
  pitch: number;
  roll: number;
  yaw: number;
  raw: RawAngles;
  attitude: Omit<AttitudeReading, "timestamp">;
  jointAngles: Omit<JointAnglesReading, "timestamp"> | null;
  orientationQuaternion: OrientationQuaternion | null;
  modeFlags: number | null;
  rollAdjust: number | null;
  yawAngle: number | null;
  limitFlags: number | null;
  stateFlags: number | null;
  payloadHex: string;
  sequence: number;
  timestamp: number;
}

export interface DumlMessage {
  raw: ByteBuffer;
  length: number;
  sender: number;
  receiver: number;
  sequence: number;
  flags: number;
  commandSet: number;
  commandId: number;
  payload: ByteBuffer;
  receivedAt?: number;
}

export interface MoveToOptions extends AxisValues {
  toleranceDeg?: number;
  timeoutMs?: number;
  telemetryTimeoutMs?: number;
  gain?: number;
  minSpeed?: number;
  maxSpeed?: number;
}

export interface MoveToResult {
  target: AxisValues;
  current: Required<AxisValues>;
  error: Required<AxisValues>;
  toleranceDeg: number;
  elapsedMs: number;
}

export class RS4Mini {
  constructor(options?: RS4MiniOptions);
  readonly connected: boolean;
  nameIncludes: string;
  rateHz: number;
  deviceId: string | null;
  deviceName: string | null;
  velocity: Velocity;
  closed: boolean;
  moveToActive: boolean;
  latestTelemetry: GimbalTelemetry | null;

  onNotification: ((packet: ByteBuffer) => void) | null;
  onMessage: ((message: DumlMessage) => void) | null;
  onTelemetry: ((sample: GimbalTelemetry) => void) | null;
  onDisconnect: ((reason?: unknown) => void) | null;
  onError: ((error: Error) => void) | null;

  connect(options?: ConnectOptions): Promise<string>;
  setVelocity(options?: AxisValues): Promise<void>;
  setVelocityDeg(options?: VelocityDegOptions): Promise<void>;
  moveFor(options: MoveForOptions): Promise<void>;
  getAttitude(options?: TelemetryReadOptions): Promise<AttitudeReading>;
  getJointAngles(options?: TelemetryReadOptions): Promise<JointAnglesReading>;
  moveTo(options: MoveToOptions): Promise<MoveToResult>;
  stop(): Promise<void>;
  recenter(): Promise<void>;
  disconnect(): Promise<void>;
  close(): Promise<void>;
}

export class DumlStreamDecoder {
  constructor(options?: { maxBufferedBytes?: number });
  maxBufferedBytes: number;
  buffer: ByteBuffer;
  discardedBytes: number;
  invalidFrames: number;
  reset(): void;
  push(chunk: Uint8Array): DumlMessage[];
}

export function crc8(bytes: Uint8Array): number;
export function crc16(bytes: Uint8Array): number;
export function frame(
  sequence: number,
  commandSet: number,
  commandId: number,
  payload?: Uint8Array,
  flags?: number,
): ByteBuffer;
export function velocityFrame(sequence: number, velocity?: AxisValues): ByteBuffer;
export function stopFrame(sequence: number): ByteBuffer;
export function recenterFrame(sequence: number): ByteBuffer;
export function parseDumlFrame(bytes: Uint8Array): DumlMessage;
export function decodeGimbalTelemetry(message: DumlMessage): GimbalTelemetry | null;
/** @deprecated Use decodeGimbalTelemetry instead. */
export function decodeGimbalPositionCandidate(message: DumlMessage): GimbalTelemetry | null;
