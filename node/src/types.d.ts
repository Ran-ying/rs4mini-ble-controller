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
export type ResearchParameter = { index: number; size: 1 | 2 | 4 | 8; rawHex: string } | { errorCode: number };
export type ResearchStatus = ResearchStatusBase & (
  | { kind: "user-parameters"; layoutSource: "legacy-duml"; statusCode: number; parameters: ResearchParameter[] }
  | { kind: "user-parameter-ack"; layoutSource: "legacy-duml"; statusCode: number }
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


/** Current-App source profile; opt-in does not assert device compatibility. */
export interface AppParameterContext { index: number; size: 1 | 2 | 4 | 8; }
export interface AppCommandReply {
  profile: "ronin-2.2.2";
  statusCode: 0;
  acknowledged: true;
  deviceVerified: false;
  physicalCompletionVerified: false;
  bodyHex: string;
  message: DumlMessage;
}
export interface AppParameterReply extends AppCommandReply {
  parameters: Array<AppParameterContext & { headerByte: number; rawHex: string }>;
}
export interface CustomFollowSettings { enabled: boolean; pitch: boolean; roll: boolean; yaw: boolean; }
export interface MotorSettings { enabled: boolean; forbidSelfie: boolean; forbidVertical: boolean; roll360: boolean; }
export type SettingsUpdate<T> = { [K in keyof T]: Pick<T, K> & Partial<Omit<T, K>> }[keyof T] & { timeoutMs?: number };
export interface AppSettingsReading<T> extends AppParameterReply { settings: T; rawValue: number; unknownBits: number; }
export interface AppSettingsWriteResult<T> extends AppCommandReply { previousRawValue: number; requestedRawValue: number; requestedSettings: Partial<T>; }
export interface AppCalibrationRecords {
  records: Array<{tag: number; size: number; rawHex: string}>;
  rawState: number | null;
  state: "UnStart" | "Processing" | "Complete" | "Failure" | "UnKnown" | null;
  rawPercent: number | null;
  percent: number | null;
  bodyHex: string;
}
export interface AppCalibrationStatus extends AppCalibrationRecords {
  kind: "calibration"; profile: "ronin-2.2.2"; timestamp: number;
  deviceVerified: false; physicalCompletionVerified: false;
}
export interface AppAutoTuneSent {
  profile: "ronin-2.2.2"; sent: true; requestedStart: boolean;
  acknowledgementRequested: false; acknowledged: false;
  deviceVerified: false; physicalCompletionVerified: false;
}
export type MotorTuningAxis = "pitch" | "roll" | "yaw";
export type MotorTuningParameter = "stiffness" | "strength" | "gyroFiltering" | "preControl";
export interface MotorTuningReading extends AppParameterContext { axis: MotorTuningAxis; parameter: MotorTuningParameter; headerByte: number; rawHex: string; rawValue: number; withinSourceRange: boolean; }
export interface AppBalanceState {
  rawValue:number; stateCode:number; state:'DEFAULT'|'TESTING'|'FINISH'|'ERROR';
  axisResults:Record<'roll'|'pitch'|'yaw',{rawValue:number; result:'PASS'|'MARGINAL'|'FAIL'|null}>;
  axisFieldsValid:boolean;
}
export interface AppSystemCalibrationState {rawValue:number; state:'DEFAULT'|'START'|'FAIL'|'SUCCESS'|null;}
export interface AppCommands {
  getAutoCalibrationStatus(options?: {timeoutMs?:number}):Promise<AppParameterReply & {systemCalibration:AppSystemCalibrationState}>;
  sendAutoCalibrationRequest(options?: {timeoutMs?:number}):Promise<AppCommandReply & {requestedValue:1}>;
  getBalanceTestStatus(options?: {timeoutMs?:number}):Promise<AppParameterReply & {balance:AppBalanceState}>;
  sendBalanceTestRequest(options?: {timeoutMs?:number}):Promise<AppCommandReply & {requestedValue:64}>;
  readonly profile: "ronin-2.2.2" | null;
  readonly calibrationStatus: AppCalibrationStatus | null;
  getMotorTuning(options?: {axis?: MotorTuningAxis; parameter?: MotorTuningParameter; timeoutMs?: number}): Promise<AppParameterReply & {values: MotorTuningReading[]}>;
  setMotorTuning(options: {axis: MotorTuningAxis; parameter: MotorTuningParameter; value: number; timeoutMs?: number}): Promise<AppCommandReply & {axis: MotorTuningAxis; parameter: MotorTuningParameter; requestedValue: number}>;
  queryCalibrationStatus(options?: { timeoutMs?: number }): Promise<AppCommandReply & {calibration: AppCalibrationRecords}>;
  sendAutoTuneRequest(options: {start: boolean}): Promise<AppAutoTuneSent>;
  getCustomFollowSettings(options?: { timeoutMs?: number }): Promise<AppSettingsReading<CustomFollowSettings>>;
  getMotorSettings(options?: { timeoutMs?: number }): Promise<AppSettingsReading<MotorSettings>>;
  setCustomFollowSettings(options: SettingsUpdate<CustomFollowSettings>): Promise<AppSettingsWriteResult<CustomFollowSettings>>;
  setMotorSettings(options: SettingsUpdate<MotorSettings>): Promise<AppSettingsWriteResult<MotorSettings>>;
  useProfile(profile: "ronin-2.2.2"): void;
  readParameters(options: { parameters: AppParameterContext[]; timeoutMs?: number }): Promise<AppParameterReply>;
  getFollowSensitivity(options?: { timeoutMs?: number }): Promise<AppParameterReply & { rawValue: number; mode: 0 | 1 | null }>;
  setFollowSensitivity(options: { mode: 0 | 1; timeoutMs?: number }): Promise<AppCommandReply & { requestedMode: 0 | 1 }>;
}
