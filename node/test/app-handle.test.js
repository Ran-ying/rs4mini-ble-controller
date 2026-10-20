import test from 'node:test';
import assert from 'node:assert/strict';
import { connected } from './fakes.js';
test('removed active queries are absent while passive calibration remains',async t=>{
 const {gimbal,peripheral:p}=await connected(t);
 assert.equal(gimbal.appCommands.getHandleSettings,undefined);
 assert.equal(gimbal.appCommands.queryCalibrationStatus,undefined);
 assert.equal(gimbal.appCommands.calibrationStatus,null);
 assert.equal(p.frames().length,0);
});
test('retired subscription handle stick and reset SDK entries are absent',async t=>{
 const {gimbal}=await connected(t);
 for(const name of ['sendParameterSubscriptionRequest','sendProgramStatusSubscriptionRequest','sendHandleSettingRequest','sendHandheldStickControlRequest','sendFactorySettingsResetRequest','parameterSubscriptionKeys'])assert.equal(gimbal.appCommands[name],undefined);
});

test("ineffective legacy calibration and balance entries are absent",async t=>{const {gimbal}=await connected(t);for(const name of ["getAutoCalibrationStatus", "sendAutoCalibrationRequest", "getBalanceTestStatus", "sendBalanceTestRequest"])assert.equal(gimbal.appCommands[name],undefined);});
