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
  /** Upper bound for each GATT write and cleanup operation; default 3000 ms. */
  ioTimeoutMs?: number;
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
export interface OrientationConvention {
  componentOrder: "wxyz" | "xyzw";
  conjugate?: boolean;
}
export interface OrientationResult {
  quaternion: { w: number; x: number; y: number; z: number };
  inputNorm: number;
  euler: { roll: number; pitch: number; yaw: number };
  componentOrder: "wxyz" | "xyzw";
  conjugate: boolean;
  convention: "right-handed-intrinsic-ZYX";
  deviceConventionVerified: false;
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

export interface AutoReconnectOptions {
  maxAttempts?: number;
  initialDelayMs?: number;
  maxDelayMs?: number;
  backoff?: number;
  timeoutMs?: number;
  directConnectTimeoutMs?: number;
}
export interface ReconnectState {
  state: "disabled" | "idle" | "waiting" | "connecting" | "restored" | "exhausted";
  attempt: number;
  delayMs?: number;
  error?: { code?: string; message: string };
}
export interface VelocityKeyframe extends AxisValues { timeMs: number; }
export interface TrajectoryOptions {
  interpolation?: "linear" | "smoothstep" | "step";
  maxLagMs?: number;
}
export interface TrajectoryResult {
  elapsedMs: number;
  durationMs: number;
  sentFrames: number;
  skippedFrames: number;
}
export type TrajectoryProgress =
  | ({ kind: "velocity" } & TrajectoryResult)
  | { kind: "waypoints"; index: number; count: number };
export interface Waypoint extends AxisValues { holdMs?: number; }
export type PositionSettings = Omit<MoveToOptions, keyof AxisValues>;
export interface HomePosition extends Required<AxisValues> { timestamp: number; deviceId: string | null; }
export type ResearchProfile = "rs3" | "rs3mini";
export interface ResearchWriteResult { sent: true; deviceVerified: false; physicalCompletionVerified: false; }
export interface ResearchStatusBase { profile: ResearchProfile; deviceVerified: false; timestamp: number; payloadHex: string; }
export type ResearchStatus = ResearchStatusBase & (
  | { kind: "sleep"; asleep: boolean }
  | { kind: "calibration"; percent: number; inProgress: boolean }
  | { kind: "battery-status"; rawFields: number[]; batteryPercent: number | null }
  | { kind: "status-tlv"; header: number; fields: { tag: number; size: number; rawHex: string }[] }
);
export interface ExperimentalGimbal {
  readonly profile: ResearchProfile | null;
  readonly status: Partial<Record<ResearchStatus["kind"], ResearchStatus>>;
  useProfile(profile: ResearchProfile): void;
  query(options: { kind: "version" | "position" | "controlStatus" | "type"; timeoutMs?: number }): Promise<DumlMessage>;
  setSleep(options: { asleep: boolean }): Promise<ResearchWriteResult>;
  absolute(options: AxisValues & { parameterByte: number; observeMs?: number }): Promise<ResearchWriteResult>;
  /** Experimental native rates, in degrees/sec in the RS 3 research convention. */
  rateFor(options: AxisValues & { durationMs: number }): Promise<ResearchWriteResult>;
}

export class RS4Mini {
  constructor(options?: RS4MiniOptions);
  readonly connected: boolean;
  nameIncludes: string;
  rateHz: number;
  deviceId: string | null;
  deviceName: string | null;
  readonly velocity: Velocity;
  closed: boolean;
  readonly moveToActive: boolean;
  readonly activeOperation: "setVelocity" | "moveFor" | "moveTo" | "recenter" | "runTrajectory" | "moveThrough" | "experimentalAbsolute" | "experimentalRate" | "experimentalSleep" | "stop" | null;
  readonly latestTelemetry: GimbalTelemetry | null;
  readonly decoder: DumlStreamDecoder;
  readonly reconnectState: ReconnectState;
  readonly trajectoryProgress: TrajectoryProgress | null;
  readonly home: HomePosition | null;
  readonly experimental: ExperimentalGimbal;

  onNotification: ((packet: ByteBuffer) => void | Promise<void>) | null;
  onMessage: ((message: DumlMessage) => void | Promise<void>) | null;
  onTelemetry: ((sample: GimbalTelemetry) => void | Promise<void>) | null;
  onDisconnect: ((reason?: unknown) => void | Promise<void>) | null;
  onError: ((error: Error) => void | Promise<void>) | null;
  onReconnect: ((state: ReconnectState) => void | Promise<void>) | null;
  onExperimentalStatus: ((status: ResearchStatus) => void | Promise<void>) | null;

  connect(options?: ConnectOptions): Promise<string>;
  enableAutoReconnect(options?: AutoReconnectOptions): void;
  disableAutoReconnect(): Promise<void>;
  setVelocity(options?: AxisValues): Promise<void>;
  setVelocityDeg(options?: VelocityDegOptions): Promise<void>;
  moveFor(options: MoveForOptions): Promise<void>;
  getAttitude(options?: TelemetryReadOptions): Promise<AttitudeReading>;
  getJointAngles(options?: TelemetryReadOptions): Promise<JointAnglesReading>;
  getOrientation(options: OrientationConvention & TelemetryReadOptions & { normTolerance?: number }): Promise<OrientationResult & { timestamp: number }>;
  moveTo(options: MoveToOptions): Promise<MoveToResult>;
  runTrajectory(keyframes: VelocityKeyframe[], options?: TrajectoryOptions): Promise<TrajectoryResult>;
  /** timeoutMs applies separately to each waypoint. */
  moveThrough(waypoints: Waypoint[], options?: PositionSettings): Promise<MoveToResult[]>;
  captureHome(options?: TelemetryReadOptions): Promise<HomePosition>;
  moveHome(options?: PositionSettings & { axes?: (keyof AxisValues)[] }): Promise<MoveToResult>;
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
export function orientationFromComponents(components: number[], options: OrientationConvention): OrientationResult;
/** @deprecated Use decodeGimbalTelemetry instead. */
export function decodeGimbalPositionCandidate(message: DumlMessage): GimbalTelemetry | null;
