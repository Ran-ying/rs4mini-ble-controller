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
