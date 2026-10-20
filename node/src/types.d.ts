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
export interface AppComponentCalibrationReply extends AppCommandReply { requestedSourcePart:'AUTO';motorPreflightRawValue:number;motorPreflightEnabled:boolean;businessComplete:boolean;calibration:null|{rawPart:number;sourcePart:string;sourcePartKnown:boolean;rawStatus:number;sourceStatus:'FAIL'|'SUCCESS'|'PROCESSING';sourceStatusKnown:boolean;bodyHex:string;trailingHex:string};responsePartMatchesRequested:boolean|null;modelLayoutVerified:false;motorStatePhysicalVerified:false;businessRequestAssociationVerified:false;firmwareAbortVerified:false; }
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
export interface AppUserParameterStatus {
  kind:'userParameters'; profile:'ronin-2.2.2'; timestamp:number;
  values:Array<{sourceGetter:string;offset:number;size:1|2;rawValue:number;rawHex:string}>;
  preset:{rawValue:number;sourceEnum:'CUSTOM_1'|'CUSTOM_2'|'FAST'|'MEDIUM'|'SLOW'|null};bodyHex:string;
  deviceVerified:false;modelLayoutVerified:false;activePresetVerified:false;physicalCompletionVerified:false;
}
export interface AppSensorCalibrationStatus {
  kind:'sensorCalibration';profile:'ronin-2.2.2';commandId:48;timestamp:number;
  rawProgressValue:number;rawStatus:number;sourceStatus:'COMPLETE'|'PROCESSING'|'FAIL'|'OTHER';sourceStatusKnown:boolean;bodyHex:string;trailingHex:string;
  deviceVerified:false;modelLayoutVerified:false;progressUnitVerified:false;requestAssociationVerified:false;physicalCompletionVerified:false;
}
export interface AppExternalDeviceRecord {
  rawTag:number;sourceSignedTag:number;length:number;payloadHex:string;
  speedControl?:{rawControlType:number;sourceControlType:'CommonStick'|'RockWheel'|'Sensor'|'Other';sourceControlTypeKnown:boolean;sourcePitchSpeed:number;sourceRollSpeed:number;sourceYawSpeed:number;trailingHex:string};
}
export interface AppExternalDeviceStatus {
  kind:'externalDevice';profile:'ronin-2.2.2';commandId:105;timestamp:number;bodyHex:string;records:AppExternalDeviceRecord[];
  deviceVerified:false;modelLayoutVerified:false;unitVerified:false;referenceFrameVerified:false;physicalCompletionVerified:false;
}
export interface AppHandheldStickStatus {
  kind:'handheldStick';profile:'ronin-2.2.2';timestamp:number;
  sourceStickX:number;sourceStickY:number;rawStateWord:number;unknownStateBits:number;
  sourceTriggerPressed:boolean;sourceStickControlEnabled:boolean;bodyHex:string;
  deviceVerified:false;modelLayoutVerified:false;axisMappingVerified:false;physicalCompletionVerified:false;
}
export interface AppAbnormalStatus {
  kind:'abnormal';profile:'ronin-2.2.2';timestamp:number;sourceValues:Record<string,boolean|number>;bodyHex:string;
  deviceVerified:false;modelLayoutVerified:false;physicalCompletionVerified:false;
}
export interface AppBatteryStatus {
  kind:'battery';profile:'ronin-2.2.2';timestamp:number;rawCapacityValue:number;sourceGetter:'getCapacityPercentage';bodyHex:string;
  deviceVerified:false;modelLayoutVerified:false;physicalCompletionVerified:false;
}
export type AppProgramName='track'|'timelapse'|'panorama';
export interface AppProgramStatusRequestReply extends AppCommandReply {
  requestedProgram:AppProgramName;requestedProgramCommandId:98|55|99;requestType:'RequestSinglePush';
  freshStatusVerified:false;programCorrelationVerified:false;modelLayoutVerified:false;
}
export interface AppProgramRecord {
  rawTag:number;sourceSignedTag:number;length:number;payloadHex:string;sourceValues:Record<string,number>|null;
}
export interface AppProgramStatus {
  kind:'program';profile:'ronin-2.2.2';commandId:56|100|107;timestamp:number;bodyHex:string;
  format:'standalone-timelapse'|'standalone-panorama'|'program-records';sourceValues:Record<string,number>|null;
  rawSuccessByte:number|null;sourceSuccess:boolean|null;records:AppProgramRecord[];
  deviceVerified:false;modelLayoutVerified:false;programCorrelationVerified:false;physicalCompletionVerified:false;
}
export interface AppPeripheralRecord {
  rawTag:number;sourceSignedTag:number;length:number;payloadHex:string;sourceTypes:string[];ambiguous:boolean;sourceInt32:number|null;
  sourceViews:Array<{sourceType:string;sourceGetter:string;conversion:string;value:number|boolean}>;
}
export interface AppPeripheralStatus {
  kind:'peripheral';profile:'ronin-2.2.2';commandId:102;timestamp:number;bodyHex:string;rawFlag:number;sourceRecordBranchSelected:boolean;records:AppPeripheralRecord[];
  deviceVerified:false;modelLayoutVerified:false;referenceFrameVerified:false;physicalCompletionVerified:false;
}
export type AppTutorialStep = 'STEP_FINISH'|'STEP_START'|'STEP_UNLOCK_GIMBAL'|'STEP_HOLD_GIMBAL_UPRIGHT'|'STEP_FOLLOW'|'STEP_STICK'|'STEP_LOCK_DIRECTION'|'STEP_RECENTER'|'STEP_SELFIE'|'STEP_PUSH'|'STEP_APP_CONTROL';
export type AppTutorialFlag = 'getIsUnlock'|'getIsUpright'|'getIsFollowFinish'|'getIsStickFinish'|'getIsLockDirectionFinish'|'getIsRecentFinish'|'getIsSelfieFinish'|'getIsHandlePushFinish'|'getIsAppControlFinish';
export interface AppTutorialStatus {kind:'tutorial';profile:'ronin-2.2.2';commandId:43;timestamp:number;rawStep:number;knownSourceStepName:AppTutorialStep|null;sourceFindResult:AppTutorialStep;rawCompletionWord:number;sourceSignedCompletionWord:number;unknownCompletionBits:number;sourceFlags:Record<AppTutorialFlag,0|1>;sourceStepStatus:Record<AppTutorialStep,boolean>;bodyHex:string;trailingHex:string;deviceVerified:false;modelLayoutVerified:false;requestAssociationVerified:false;physicalCompletionVerified:false;}
export type AppStatus = AppTutorialStatus | AppSensorCalibrationStatus | AppExternalDeviceStatus | AppPeripheralStatus | AppCalibrationStatus | AppUserParameterStatus | AppHandheldStickStatus | AppAbnormalStatus | AppBatteryStatus | AppProgramStatus;
export interface AppAutoTuneSent {
  profile: "ronin-2.2.2"; sent: true; requestedStart: boolean;
  acknowledgementRequested: false; acknowledged: false;
  deviceVerified: false; physicalCompletionVerified: false;
}
export type MotorTuningAxis = "pitch" | "roll" | "yaw";
export type MotorTuningParameter = "stiffness" | "strength" | "gyroFiltering" | "preControl";
export interface MotorTuningReading extends AppParameterContext { axis: MotorTuningAxis; parameter: MotorTuningParameter; headerByte: number; rawHex: string; rawValue: number; withinSourceRange: boolean; }
export type AppAxisMode = 'custom'|'low'|'middle'|'high';
export interface AppAxisModes {pitch:AppAxisMode;roll:AppAxisMode;yaw:AppAxisMode;}
export type FollowParameter = 'speed'|'acceleration'|'deadZone';
export type RcParameter = 'speed'|'deadZone'|'smoothing';
export interface AppTuningReading extends AppParameterReply {
  activePresetVerified:false;
  values:Array<AppParameterContext & {headerByte:number;rawHex:string;axis:MotorTuningAxis;parameter:FollowParameter|RcParameter;rawValue:number;withinSourceRange:boolean}>;
}
export type StandaloneParameter='speed'|'smoothing';
export type AppSourceAxisMode='ThreeAxis'|'TwoAxis'|'Roll360'|'ThreeDRoll360';
export type AppSourceWorkMode='Free'|'Flower'|'Fpv'|'Center';
export type AppMotorTuningSingleReply = AppParameterReply & {readMode:'single';values:MotorTuningReading[]};
export interface AppMotorTuningBatchReply {
  profile:'ronin-2.2.2';deviceVerified:false;physicalCompletionVerified:false;
  readMode:'sequential';atomic:false;replies:Array<AppParameterReply & {values:MotorTuningReading[]}>;
  parameters:AppParameterReply['parameters'];values:MotorTuningReading[];
}
export interface AppCommands {
  readonly sensorCalibrationStatus:AppSensorCalibrationStatus|null;
  readonly externalDeviceStatus:AppExternalDeviceStatus|null;
  readonly peripheralStatus:AppPeripheralStatus|null;
  sendProgramStatusRequest(options:{program:AppProgramName;timeoutMs?:number}):Promise<AppProgramStatusRequestReply>;
  getCenterActivationInfo(options:{sourceVersion:'Ver1_0'|'Ver1_1'|'Ver1_3'|'Ver13';timeoutMs?:number}):Promise<AppCommandReply & {sourceVersion:string;receiverByte:229;sourceGetRequestByte:1|17;activeByte:number;sourceActiveBit:boolean;unknownActiveBits:number;dateRaw:{year:number;month:number;day:number;hour:number;minute:number;second:number};serialNumberRawHex:string;sourceSerialNumber:string;serialNumberLength:number;trailingBodyHex:string;dateValidityVerified:false;actualSessionVersionVerified:false;activationValidityVerified:false;modelLayoutVerified:false}>;
  getUserProfile(options?:{timeoutMs?:number}):Promise<AppParameterReply & {parameter:'userProfile';rawValue:number;withinSourceRange:boolean;sourceUiName:'M1'|'M2'|'M3'|null;modelLayoutVerified:false;activePresetVerified:false}>;
  getWorkMode(options?:{timeoutMs?:number}):Promise<AppParameterReply & {parameter:'workMode';rawValue:number;withinSourceRange:boolean;sourceMode:AppSourceWorkMode|null;modelLayoutVerified:false;activePresetVerified:false}>;
  sendUserProfileRequest(options:{sourceProfileValue:0|1|2|3|4|5;timeoutMs?:number}):Promise<AppCommandReply & {parameter:'userProfile';requestedSourceProfileValue:number;requestedRawValue:number;activePresetVerified:false;persistenceVerified:false}>;
  sendWorkModeRequest(options:{sourceMode:AppSourceWorkMode;timeoutMs?:number}):Promise<AppCommandReply & {parameter:'workMode';requestedSourceMode:AppSourceWorkMode;requestedRawValue:number;activePresetVerified:false;persistenceVerified:false}>;
  getSmoothTrackAxes(options?:{axis?:'yaw'|'pitch'|'roll';timeoutMs?:number}):Promise<AppParameterReply & {modelLayoutVerified:false;activePresetVerified:false;values:Array<AppParameterContext & {axis:'yaw'|'pitch'|'roll';rawValue:number;withinSourceRange:boolean;sourceEnabled:boolean;enabled:boolean|null;headerByte:number;rawHex:string}>}>;
  sendSmoothTrackAxesRequest(options:{axes:Partial<Record<'yaw'|'pitch'|'roll',boolean>>;timeoutMs?:number}):Promise<AppCommandReply & {requestedAxes:Partial<Record<'yaw'|'pitch'|'roll',boolean>>;activePresetVerified:false;atomicApplicationVerified:false;persistenceVerified:false}>;
  getAxisMode(options?:{timeoutMs?:number}):Promise<AppParameterReply & {rawValue:number;sourceModeValue:number;sourceMode:AppSourceAxisMode;unknownBits:number;modelLayoutVerified:false;activePresetVerified:false}>;
  sendAxisModeRequest(options:{sourceMode:AppSourceAxisMode;timeoutMs?:number}):Promise<AppCommandReply & {requestedSourceMode:AppSourceAxisMode;requestedRawValue:number;activePresetVerified:false;otherBitsPreservationVerified:false;persistenceVerified:false}>;
  sendComponentCalibrationRequest(options:{sourcePart:'AUTO';timeoutMs?:number}):Promise<AppComponentCalibrationReply>;
  sendFineTuneRequest(options:{axis:'pitch'|'roll';adjustmentDegrees:number;timeoutMs?:number}):Promise<AppCommandReply & {axis:'pitch'|'roll';requestedAdjustmentDegrees:number;encodedTenths:number;nominalAdjustmentDegrees:number;stabilizationStateVerified:false}>;
  readonly programStatus:AppProgramStatus|null;
  readonly abnormalStatus:AppAbnormalStatus|null;
  readonly batteryStatus:AppBatteryStatus|null;
  readonly tutorialStatus:AppTutorialStatus|null;
  readonly handheldStickStatus:AppHandheldStickStatus|null;
  readonly userParameterStatus:AppUserParameterStatus|null;
  getStandaloneTuning(options?:{axis?:MotorTuningAxis;parameter?:StandaloneParameter;timeoutMs?:number}):Promise<AppTuningReading & {inputSourceRaw:number}>;
  setStandaloneTuning(options:{inputSource:2;axis:MotorTuningAxis;parameter:StandaloneParameter;value:number;timeoutMs?:number}):Promise<AppCommandReply & {axis:MotorTuningAxis;parameter:StandaloneParameter;requestedValue:number;requestedInputSource:2;activePresetVerified:false}>;
  getFollowTuning(options?:{axis?:MotorTuningAxis;parameter?:FollowParameter;timeoutMs?:number}):Promise<AppTuningReading>;
  getRcTuning(options?:{axis?:MotorTuningAxis;parameter?:RcParameter;timeoutMs?:number}):Promise<AppTuningReading>;
  setFollowTuning(options:{axis:MotorTuningAxis;parameter:FollowParameter;value:number;timeoutMs?:number}):Promise<AppCommandReply & {axis:MotorTuningAxis;parameter:FollowParameter;requestedValue:number;activePresetVerified:false}>;
  setRcTuning(options:{axis:MotorTuningAxis;parameter:RcParameter;value:number;timeoutMs?:number}):Promise<AppCommandReply & {axis:MotorTuningAxis;parameter:RcParameter;requestedValue:number;activePresetVerified:false}>;
  getFollowSettings(options:{parameter:FollowParameter;timeoutMs?:number}):Promise<AppSettingsReading<AppAxisModes>>;
  setFollowSettings(options:SettingsUpdate<AppAxisModes> & {parameter:FollowParameter}):Promise<AppSettingsWriteResult<AppAxisModes>>;
  getRcSettings(options:{parameter:RcParameter;timeoutMs?:number}):Promise<AppSettingsReading<AppAxisModes>>;
  setRcSettings(options:SettingsUpdate<AppAxisModes> & {parameter:RcParameter}):Promise<AppSettingsWriteResult<AppAxisModes>>;
  readonly profile: "ronin-2.2.2" | null;
  readonly calibrationStatus: AppCalibrationStatus | null;
  getMotorTuning(options?: {axis?: MotorTuningAxis; parameter?: MotorTuningParameter; timeoutMs?: number}): Promise<AppMotorTuningSingleReply | AppMotorTuningBatchReply>;
  setMotorTuning(options: {axis: MotorTuningAxis; parameter: MotorTuningParameter; value: number; timeoutMs?: number}): Promise<AppCommandReply & {axis: MotorTuningAxis; parameter: MotorTuningParameter; requestedValue: number}>;
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
