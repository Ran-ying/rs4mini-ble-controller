import type { RS4MiniOptions, ConnectOptions, AxisValues, TelemetryReadOptions,
  AttitudeReading, JointAnglesReading, Velocity, GimbalTelemetry, AutoReconnectOptions,
  ReconnectState, ByteBuffer, DumlMessage, ExperimentalGimbal, ResearchStatus } from "./types.js";
export class BleDevice {
  constructor(options?: RS4MiniOptions);
  readonly connected: boolean;
  readonly closed: boolean;
  readonly activeOperation: string | null;
  readonly deviceName: string | null;
  deviceId: string | null;
  readonly velocity: Velocity;
  readonly latestTelemetry: GimbalTelemetry | null;
  readonly reconnectState: ReconnectState;
  readonly experimental: Pick<ExperimentalGimbal, "profile" | "status" | "useProfile" | "query" | "setSleep">;
  connect(options?: ConnectOptions): Promise<string>;
  disconnect(): Promise<void>;
  close(): Promise<void>;
  setVelocity(options?: AxisValues): Promise<void>;
  stop(): Promise<void>;
  recenter(): Promise<void>;
  /** Returns the correlated raw 04:1E reply; no feedback-rate guarantee. */
  requestDegreeInfo(options?: { timeoutMs?: number }): Promise<DumlMessage>;
  getAttitude(options?: TelemetryReadOptions): Promise<AttitudeReading>;
  getJointAngles(options?: TelemetryReadOptions): Promise<JointAnglesReading>;
  enableAutoReconnect(options?: AutoReconnectOptions): void;
  disableAutoReconnect(): Promise<void>;
  onNotification: ((packet: ByteBuffer) => void | Promise<void>) | null;
  onMessage: ((message: DumlMessage) => void | Promise<void>) | null;
  onTelemetry: ((sample: GimbalTelemetry) => void | Promise<void>) | null;
  onDisconnect: ((reason?: unknown) => void | Promise<void>) | null;
  onError: ((error: Error) => void | Promise<void>) | null;
  onReconnect: ((state: ReconnectState) => void | Promise<void>) | null;
  onExperimentalStatus: ((status: ResearchStatus) => void | Promise<void>) | null;
}
