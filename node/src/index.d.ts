export * from "./types.js";
import type { AxisValues, ByteBuffer, Velocity, RS4MiniOptions, ConnectOptions, VelocityDegOptions, MoveForOptions, TelemetryReadOptions, RawAngles, AttitudeReading, JointAnglesReading, OrientationQuaternion, OrientationConvention, OrientationResult, GimbalTelemetry, DumlMessage, MoveToOptions, MoveToResult, AutoReconnectOptions, ReconnectState, VelocityKeyframe, TrajectoryOptions, TrajectoryResult, TrajectoryProgress, Waypoint, PositionSettings, HomePosition, ResearchProfile, ResearchWriteResult, ResearchStatusBase, ResearchStatus, ExperimentalGimbal, AppCommands, AppStatus } from "./types.js";

export class RS4Mini {
  constructor(options?: RS4MiniOptions);
  readonly appCommands: AppCommands;
  onAppStatus: ((status: AppStatus) => void | Promise<void>) | null;
  readonly connected: boolean;
  nameIncludes: string;
  rateHz: number;
  deviceId: string | null;
  deviceName: string | null;
  readonly velocity: Velocity;
  closed: boolean;
  readonly moveToActive: boolean;
  readonly activeOperation: "sendFactorySettingsResetRequest" | "sendHandleSettingRequest" | "sendFineTuneRequest" | "sendAutoCalibrationRequest" | "sendBalanceTestRequest" | "setMotorTuning" | "sendAutoTuneRequest" | "setFollowSensitivity" | "setCustomFollowSettings" | "setMotorSettings" | "setFollowSettings" | "setRcSettings" | "setFollowTuning" | "setRcTuning" | "setStandaloneTuning" | "setVelocity" | "moveFor" | "moveTo" | "recenter" | "runTrajectory" | "moveThrough" | "experimentalAbsolute" | "experimentalRate" | "experimentalSleep" | "stop" | null;
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
  /** Returns the correlated raw 04:1E reply; no feedback-rate guarantee. */
  requestDegreeInfo(options?: { timeoutMs?: number }): Promise<DumlMessage>;
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
