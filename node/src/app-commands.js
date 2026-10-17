import {handheldStickNotification} from './app-handheld-stick.js';
import {profileValueSelection,profileValueWrite,profileValueReply} from './app-profile-values.js';
import {smoothTrackSelection,smoothTrackWrite,smoothTrackReply} from './app-smooth-track.js';
import {axisModeWrite,axisModeReply} from './app-axis-mode.js';
import { fineTuneSpec } from './app-fine-tune.js';
import { handleReply, handleWriteSpec } from './app-handle.js';
import { userParameterNotification } from './app-user-parameters.js';
import { standaloneSelection, standaloneWrite, standaloneContext, standaloneReply } from './app-standalone.js';
import { tuningSelection, tuningWrite, tuningReply } from './app-tuning.js';
import { systemCalibrationPayload, systemCalibrationReply } from './app-system-calibration.js';
import { balanceStartPayload, balanceReply } from './app-balance.js';
// Device SDK facade: single owner/queue/pending map, no composed motion.
import { appProfile, parameterContext, parameterRequest, sensitivityPayload, factoryResetSpec, appReply, parameterReply } from './app-protocol.js';
import { motorSelection, motorWrite, motorReply } from './app-motor.js';
import { frame } from './protocol.js';
import { autoTunePayload, calibrationReply, calibrationNotification } from './app-calibration.js';
import { modeKind, settingsSchema, settingsPatch, decodeSettings, settingsWrite } from './app-settings.js';
import { failure, check, now } from './async.js';
function optionsOnly(options, keys) {
  if (!options || typeof options !== 'object' || Array.isArray(options) || Object.keys(options).some(key => !keys.includes(key))) throw new TypeError('invalid App command options');
}
export class AppCommands {
  constructor(owner) { this.owner = owner; this._profile = null; this._calibrationStatus = null; this._userParameterStatus = null; this._handheldStickStatus = null; }
  get handheldStickStatus() { return structuredClone(this._handheldStickStatus); }
  get userParameterStatus() { return structuredClone(this._userParameterStatus); }
  get profile() { return this._profile; }
  get calibrationStatus() { return structuredClone(this._calibrationStatus); }
  _reset() { this._calibrationStatus = null; this._userParameterStatus = null; this._handheldStickStatus = null; }
  _message(message) {
    if (!this._profile) return;
    const stick=handheldStickNotification(message);
    if(stick) {this._handheldStickStatus=stick;this.owner._emit('onAppStatus',structuredClone(stick));}
    const parameters=userParameterNotification(message);
    if(parameters) {this._userParameterStatus=parameters;this.owner._emit('onAppStatus',structuredClone(parameters));}
    const status = calibrationNotification(message);
    if (status) { this._calibrationStatus = status; this.owner._emit('onAppStatus', structuredClone(status)); }
  }
  useProfile(profile) {
    appProfile(profile);
    if (this.owner.activeOperation || this.owner.experimental.pending.size) throw failure('RS4MINI_BUSY', 'Cannot change protocol source during an operation or query');
    this.owner.experimental._profile = null; this.owner.experimental._reset();
    this._profile = profile; this._reset();
  }
  _requireProfile() { appProfile(this._profile); }
  async sendFineTuneRequest(options={}) {
    optionsOnly(options,['axis','adjustmentDegrees','timeoutMs']);this._requireProfile();
    const spec=fineTuneSpec(options),timeoutMs=options.timeoutMs??3000;
    if(!Number.isFinite(timeoutMs)||timeoutMs<=0||timeoutMs>60000)throw new RangeError('timeoutMs must be >0..60000');
    return this.owner._run('sendFineTuneRequest',async operation=>{
      await this.owner._stop();check(operation.controller.signal);
      const message=await this.owner.experimental._queryPayloadCommand('App fine tune',[4,7],spec.payload,timeoutMs,{signal:operation.controller.signal,epoch:this.owner.motionEpoch});
      const {payload,...requested}=spec;return {...appReply(message,7),...requested,stabilizationStateVerified:false};
    },false);
  }
  getUserProfile(options={}) {return this._getProfileValue('userProfile',options);}
  getWorkMode(options={}) {return this._getProfileValue('workMode',options);}
  async _getProfileValue(kind,options) {
    optionsOnly(options,['timeoutMs']);this._requireProfile();const row=profileValueSelection(kind);
    return profileValueReply(await this.owner.experimental._queryPayloadCommand('App '+kind+' query',[4,0x10],parameterRequest([{index:row.index,size:1}]),options.timeoutMs??3000),kind);
  }
  async sendUserProfileRequest(options={}) {
    optionsOnly(options,['sourceProfileValue','timeoutMs']);this._requireProfile();return this._sendProfileValue('userProfile',profileValueWrite('userProfile',options.sourceProfileValue),options.timeoutMs??3000);
  }
  async sendWorkModeRequest(options={}) {
    optionsOnly(options,['sourceMode','timeoutMs']);this._requireProfile();return this._sendProfileValue('workMode',profileValueWrite('workMode',options.sourceMode),options.timeoutMs??3000);
  }
  async _sendProfileValue(kind,spec,timeoutMs) {
    if(!Number.isFinite(timeoutMs)||timeoutMs<=0||timeoutMs>60000)throw new RangeError('timeoutMs must be >0..60000');
    return this.owner._run(kind==='userProfile'?'sendUserProfileRequest':'sendWorkModeRequest',async operation=>{
      await this.owner._stop();check(operation.controller.signal);
      const message=await this.owner.experimental._queryPayloadCommand('App '+kind+' write',[4,0x0f],spec.payload,timeoutMs,{signal:operation.controller.signal,epoch:this.owner.motionEpoch});
      const {payload,...requested}=spec;return {...appReply(message,0x0f),...requested,activePresetVerified:false,persistenceVerified:false};
    },false);
  }
  async getSmoothTrackAxes(options={}) {
    optionsOnly(options,['axis','timeoutMs']);this._requireProfile();
    const selection=smoothTrackSelection(options.axis),context=selection.map(({index,size})=>({index,size}));
    return smoothTrackReply(await this.owner.experimental._queryPayloadCommand('App smooth track query',[4,0x10],parameterRequest(context),options.timeoutMs??3000),selection);
  }
  async sendSmoothTrackAxesRequest(options={}) {
    optionsOnly(options,['axes','timeoutMs']);this._requireProfile();
    const spec=smoothTrackWrite(options.axes),timeoutMs=options.timeoutMs??3000;
    if(!Number.isFinite(timeoutMs)||timeoutMs<=0||timeoutMs>60000)throw new RangeError('timeoutMs must be >0..60000');
    return this.owner._run('sendSmoothTrackAxesRequest',async operation=>{
      await this.owner._stop();check(operation.controller.signal);
      const message=await this.owner.experimental._queryPayloadCommand('App smooth track axes',[4,0x0f],spec.payload,timeoutMs,{signal:operation.controller.signal,epoch:this.owner.motionEpoch});
      return {...appReply(message,0x0f),requestedAxes:{...spec.requestedAxes},activePresetVerified:false,atomicApplicationVerified:false,persistenceVerified:false};
    },false);
  }
  async getAxisMode(options={}) {
    optionsOnly(options,['timeoutMs']);this._requireProfile();
    return axisModeReply(await this.owner.experimental._queryPayloadCommand('App axis mode query',[4,0x10],parameterRequest([{index:34,size:1}]),options.timeoutMs??3000));
  }
  async sendAxisModeRequest(options={}) {
    optionsOnly(options,['sourceMode','timeoutMs']);this._requireProfile();
    const spec=axisModeWrite(options),timeoutMs=options.timeoutMs??3000;
    if(!Number.isFinite(timeoutMs)||timeoutMs<=0||timeoutMs>60000)throw new RangeError('timeoutMs must be >0..60000');
    return this.owner._run('sendAxisModeRequest',async operation=>{
      await this.owner._stop();check(operation.controller.signal);
      const message=await this.owner.experimental._queryPayloadCommand('App axis mode',[4,0x0f],spec.payload,timeoutMs,{signal:operation.controller.signal,epoch:this.owner.motionEpoch});
      const {payload,...requested}=spec;return {...appReply(message,0x0f),...requested,activePresetVerified:false,otherBitsPreservationVerified:false,persistenceVerified:false};
    },false);
  }
  async sendFactorySettingsResetRequest(options={}) {
    optionsOnly(options,['sourcePlatform','timeoutMs']);this._requireProfile();
    const spec=factoryResetSpec(options),timeoutMs=options.timeoutMs??3000;
    if(!Number.isFinite(timeoutMs)||timeoutMs<=0||timeoutMs>60000)throw new RangeError('timeoutMs must be >0..60000');
    return this.owner._run('sendFactorySettingsResetRequest',async operation=>{
      await this.owner._stop();check(operation.controller.signal);
      const message=await this.owner.experimental._queryPayloadCommand('App factory settings reset',[4,0x13],spec.payload,timeoutMs,{signal:operation.controller.signal,epoch:this.owner.motionEpoch});
      return {...appReply(message,0x13),requestedSourcePlatform:spec.requestedSourcePlatform,targetResetScopeVerified:false,persistenceVerified:false};
    },false);
  }
  async sendHandleSettingRequest(options={}) {
    optionsOnly(options,['setting','value','timeoutMs']);this._requireProfile();
    const spec=handleWriteSpec(options),timeoutMs=options.timeoutMs??3000;
    if(!Number.isFinite(timeoutMs)||timeoutMs<=0||timeoutMs>60000)throw new RangeError('timeoutMs must be >0..60000');
    return this.owner._run('sendHandleSettingRequest',async operation=>{
      await this.owner._stop();check(operation.controller.signal);
      const message=await this.owner.experimental._queryPayloadCommand('App handle setting',[4,0x35],spec.payload,timeoutMs,{signal:operation.controller.signal,epoch:this.owner.motionEpoch});
      const {payload,...requested}=spec;return {...appReply(message,0x35),...requested,unspecifiedByteSemanticsVerified:false,readbackVerified:false,persistenceVerified:false};
    },false);
  }
  async getHandleSettings(options={}) {
    optionsOnly(options,['timeoutMs']);this._requireProfile();
    const message=await this.owner.experimental._queryPayloadCommand('App handle query',[4,0x36],new Uint8Array(0),options.timeoutMs??3000);
    return handleReply(message);
  }
  async readParameters(options = {}) {
    optionsOnly(options, ['parameters', 'timeoutMs']); this._requireProfile();
    const parameters = parameterContext(options.parameters);
    const response = await this.owner.experimental._queryPayloadCommand('App parameters', [4, 0x10], parameterRequest(parameters), options.timeoutMs ?? 3000);
    return parameterReply(response, parameters);
  }
  async getFollowSensitivity(options = {}) {
    optionsOnly(options, ['timeoutMs']);
    const result = await this.readParameters({ parameters: [{ index: 150, size: 1 }], timeoutMs: options.timeoutMs ?? 3000 });
    const rawValue = parseInt(result.parameters[0].rawHex, 16);
    return { ...result, rawValue, mode: [0, 1].includes(rawValue) ? rawValue : null };
  }
  async getAutoCalibrationStatus(options = {}) {
    optionsOnly(options, ['timeoutMs']);
    return systemCalibrationReply(await this.readParameters({parameters:[{index:36,size:1}],timeoutMs:options.timeoutMs ?? 3000}));
  }
  async sendAutoCalibrationRequest(options = {}) {
    optionsOnly(options, ['timeoutMs']); this._requireProfile();
    const timeoutMs=options.timeoutMs ?? 3000;
    if (!Number.isFinite(timeoutMs) || timeoutMs<=0 || timeoutMs>60000) throw new RangeError('timeoutMs must be >0..60000');
    return this.owner._run('sendAutoCalibrationRequest',async operation=>{
      await this.owner._stop(); check(operation.controller.signal);
      const response=await this.owner.experimental._queryPayloadCommand('App system calibration start',[4,0x0f],systemCalibrationPayload(),timeoutMs,{signal:operation.controller.signal,epoch:this.owner.motionEpoch});
      return {...appReply(response,0x0f),requestedValue:1};
    },false);
  }
  async getBalanceTestStatus(options = {}) {
    optionsOnly(options, ['timeoutMs']);
    return balanceReply(await this.readParameters({parameters:[{index:37,size:1}],timeoutMs:options.timeoutMs ?? 3000}));
  }
  async sendBalanceTestRequest(options = {}) {
    optionsOnly(options, ['timeoutMs']); this._requireProfile();
    const timeoutMs=options.timeoutMs ?? 3000;
    if (!Number.isFinite(timeoutMs) || timeoutMs<=0 || timeoutMs>60000) throw new RangeError('timeoutMs must be >0..60000');
    return this.owner._run('sendBalanceTestRequest',async operation=>{
      await this.owner._stop(); check(operation.controller.signal);
      const response=await this.owner.experimental._queryPayloadCommand('App balance start',[4,0x0f],balanceStartPayload(),timeoutMs,{signal:operation.controller.signal,epoch:this.owner.motionEpoch});
      return {...appReply(response,0x0f),requestedValue:64};
    },false);
  }
  async getStandaloneTuning(options={}) {
    optionsOnly(options,['axis','parameter','timeoutMs']);this._requireProfile();
    const {timeoutMs=3000,...filters}=options,selection=standaloneSelection(filters);
    const response=await this.owner.experimental._queryPayloadCommand('App standalone query',[4,0x10],parameterRequest(standaloneContext(selection)),timeoutMs);
    return standaloneReply(response,selection);
  }
  async setStandaloneTuning(options={}) {
    optionsOnly(options,['inputSource','axis','parameter','value','timeoutMs']);this._requireProfile();
    const spec=standaloneWrite(options),timeoutMs=options.timeoutMs ?? 3000;
    if (!Number.isFinite(timeoutMs) || timeoutMs<=0 || timeoutMs>60000) throw new RangeError('timeoutMs must be >0..60000');
    return this.owner._run('setStandaloneTuning',async operation=>{
      await this.owner._stop();check(operation.controller.signal);
      const response=await this.owner.experimental._queryPayloadCommand('App standalone source/value write',[4,0x0f],spec.payload,timeoutMs,{signal:operation.controller.signal,epoch:this.owner.motionEpoch});
      const {payload,...requested}=spec;
      return {...appReply(response,0x0f),...requested,activePresetVerified:false};
    },false);
  }
  getFollowTuning(options = {}) { return this._getTuning('follow',options); }
  setFollowTuning(options = {}) { return this._setTuning('follow',options); }
  getRcTuning(options = {}) { return this._getTuning('rc',options); }
  setRcTuning(options = {}) { return this._setTuning('rc',options); }
  async _getTuning(domain,options) {
    optionsOnly(options,['axis','parameter','timeoutMs']);this._requireProfile();
    const {timeoutMs=3000,...filters}=options,selection=tuningSelection(domain,filters);
    const context=selection.map(({index,size})=>({index,size}));
    const response=await this.owner.experimental._queryPayloadCommand('App numeric tuning',[4,0x10],parameterRequest(context),timeoutMs);
    return tuningReply(response,selection);
  }
  async _setTuning(domain,options) {
    optionsOnly(options,['axis','parameter','value','timeoutMs']);this._requireProfile();
    const spec=tuningWrite(domain,options),timeoutMs=options.timeoutMs ?? 3000;
    if (!Number.isFinite(timeoutMs) || timeoutMs<=0 || timeoutMs>60000) throw new RangeError('timeoutMs must be >0..60000');
    return this.owner._run(domain==='follow'?'setFollowTuning':'setRcTuning',async operation=>{
      await this.owner._stop();check(operation.controller.signal);
      const response=await this.owner.experimental._queryPayloadCommand('App numeric write',[4,0x0f],spec.payload,timeoutMs,{signal:operation.controller.signal,epoch:this.owner.motionEpoch});
      const {payload,...requested}=spec;
      return {...appReply(response,0x0f),...requested,activePresetVerified:false};
    },false);
  }
  async getMotorTuning(options = {}) {
    optionsOnly(options, ['axis','parameter','timeoutMs']); this._requireProfile();
    const {timeoutMs = 3000, ...filters}=options, selection=motorSelection(filters);
    const context=selection.map(({index,size})=>({index,size}));
    const response=await this.owner.experimental._queryPayloadCommand('App motor tuning',[4,0x32],parameterRequest(context),timeoutMs);
    return motorReply(response,selection);
  }
  async setMotorTuning(options = {}) {
    optionsOnly(options, ['axis','parameter','value','timeoutMs']); this._requireProfile();
    const spec=motorWrite(options), timeoutMs=options.timeoutMs ?? 3000;
    if (!Number.isFinite(timeoutMs) || timeoutMs<=0 || timeoutMs>60000) throw new RangeError('timeoutMs must be >0..60000');
    return this.owner._run('setMotorTuning',async operation=>{
      await this.owner._stop(); check(operation.controller.signal);
      const response=await this.owner.experimental._queryPayloadCommand('App motor write',[4,0x31],spec.payload,timeoutMs,{signal:operation.controller.signal,epoch:this.owner.motionEpoch});
      const {payload,...requested}=spec;
      return {...appReply(response,0x31),...requested};
    },false);
  }
  async queryCalibrationStatus(options = {}) {
    optionsOnly(options, ['timeoutMs']); this._requireProfile();
    const response = await this.owner.experimental._queryPayloadCommand('App calibration status', [4, 0x6e], undefined, options.timeoutMs ?? 3000);
    return calibrationReply(response);
  }
  async sendAutoTuneRequest(options = {}) {
    optionsOnly(options, ['start']); this._requireProfile();
    const start = options.start, payload = autoTunePayload(start);
    return this.owner._run('sendAutoTuneRequest', async operation => {
      await this.owner._stop(); check(operation.controller.signal);
      await this.owner._enqueue(frame(this.owner._nextSequence(), 4, 0x6a, payload, 0), { signal: operation.controller.signal, epoch: this.owner.motionEpoch });
      return { profile: this._profile, sent: true, requestedStart: start, acknowledgementRequested: false,
        acknowledged: false, deviceVerified: false, physicalCompletionVerified: false };
    }, false);
  }
  async getFollowSettings(options = {}) {
    optionsOnly(options,['parameter','timeoutMs']); const {parameter,...rest}=options;
    return this._getSettings(modeKind('follow',parameter),rest);
  }
  async setFollowSettings(options = {}) {
    optionsOnly(options,['parameter','pitch','roll','yaw','timeoutMs']); const {parameter,...rest}=options;
    return this._setSettings(modeKind('follow',parameter),rest);
  }
  async getRcSettings(options = {}) {
    optionsOnly(options,['parameter','timeoutMs']); const {parameter,...rest}=options;
    return this._getSettings(modeKind('rc',parameter),rest);
  }
  async setRcSettings(options = {}) {
    optionsOnly(options,['parameter','pitch','roll','yaw','timeoutMs']); const {parameter,...rest}=options;
    return this._setSettings(modeKind('rc',parameter),rest);
  }
  getCustomFollowSettings(options = {}) { return this._getSettings('customFollow', options); }
  getMotorSettings(options = {}) { return this._getSettings('motor', options); }
  setCustomFollowSettings(options = {}) { return this._setSettings('customFollow', options); }
  setMotorSettings(options = {}) { return this._setSettings('motor', options); }
  async _getSettings(kind, options) {
    optionsOnly(options, ['timeoutMs']);
    const { index } = settingsSchema(kind);
    return decodeSettings(await this.readParameters({ parameters: [{ index, size: 1 }], timeoutMs: options.timeoutMs ?? 3000 }), kind);
  }
  async _setSettings(kind, options) {
    const schema = settingsSchema(kind);
    optionsOnly(options, [...Object.keys(schema.fields), 'timeoutMs']); this._requireProfile();
    const { timeoutMs = 3000, ...fields } = options, patch = settingsPatch(kind, fields);
    if (!Number.isFinite(timeoutMs) || timeoutMs <= 0 || timeoutMs > 60000) throw new RangeError('timeoutMs must be >0..60000');
    const name = kind === 'motor' ? 'setMotorSettings' : kind === 'customFollow' ? 'setCustomFollowSettings' : kind.startsWith('follow') ? 'setFollowSettings' : 'setRcSettings';
    return this.owner._run(name, async operation => {
      await this.owner._stop(); check(operation.controller.signal);
      const deadline = now() + timeoutMs;
      const remaining = () => {
        const left = deadline - now();
        if (left <= 0) throw failure('RS4MINI_RESPONSE_TIMEOUT', 'Settings transaction deadline expired');
        return left;
      };
      const parameters = [{ index: schema.index, size: 1 }], context = { signal: operation.controller.signal, epoch: this.owner.motionEpoch };
      const response = await this.owner.experimental._queryPayloadCommand(name + ' read', [4, 0x10], parameterRequest(parameters), remaining(), context);
      const before = decodeSettings(parameterReply(response, parameters), kind);
      check(operation.controller.signal);
      const { payload, requestedRawValue } = settingsWrite(kind, patch, before.rawValue);
      const ack = await this.owner.experimental._queryPayloadCommand(name + ' write', [4, 0x0f], payload, remaining(), context);
      return { ...appReply(ack, 0x0f), previousRawValue: before.rawValue, requestedRawValue, requestedSettings: patch };
    }, false);
  }
  async setFollowSensitivity(options = {}) {
    optionsOnly(options, ['mode', 'timeoutMs']); this._requireProfile();
    const mode = options.mode, payload = sensitivityPayload(mode), timeoutMs = options.timeoutMs ?? 3000;
    // Validate before claiming motion ownership or sending neutral frames.
    if (!Number.isFinite(timeoutMs) || timeoutMs <= 0 || timeoutMs > 60000) throw new RangeError('timeoutMs must be >0..60000');
    return this.owner._run('setFollowSensitivity', async operation => {
      await this.owner._stop(); check(operation.controller.signal);
      const response = await this.owner.experimental._queryPayloadCommand('follow sensitivity', [4, 0x0f], payload, timeoutMs,
        { signal: operation.controller.signal, epoch: this.owner.motionEpoch });
      return { ...appReply(response, 0x0f), requestedMode: mode };
    }, false);
  }
}
