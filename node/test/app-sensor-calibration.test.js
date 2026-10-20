import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {connected,until} from './fakes.js';
import {frame,crc16} from '../src/protocol.js';
import {sensorCalibrationNotification} from '../src/app-sensor-calibration.js';
const vectors=JSON.parse(readFileSync(new URL('./fixtures/sensor-calibration.json',import.meta.url)));
const body=()=>Buffer.from('6403aabb','hex');
const message=(payload=body(),flags=0)=>({sender:4,receiver:2,commandSet:4,commandId:48,flags,payload});
function incoming(p,payload=body(),flags=0,commandId=48,sequence=1){const b=frame(sequence,4,commandId,payload,flags);b[4]=4;b[5]=2;b.writeUInt16LE(crc16(b.subarray(0,-2)),b.length-2);p.rx.emit('data',b,true);}
test('seven shared sensor vectors preserve state domain, raw progress and tail',()=>{
 assert.equal(vectors.length,7);for(const v of vectors){const r=sensorCalibrationNotification(message(Buffer.from(v.bodyHex,'hex')));for(const [key,value] of Object.entries(v.expected)){if(key==='targetDeviceVerified')assert.equal(r.deviceVerified,value);else assert.deepEqual(r[key],value);}assert.equal(r.requestAssociationVerified,false);assert.equal(r.modelLayoutVerified,false);}
 assert.equal(sensorCalibrationNotification(message()).sourceStatus,'FAIL');assert.equal(sensorCalibrationNotification(message(Buffer.from([50,1]))).sourceStatus,'PROCESSING');assert.equal(sensorCalibrationNotification(message(Buffer.from([50,2]))).sourceStatusKnown,false);
});
test('all unsigned progress and status bytes retained without ordinal or bool conversion',()=>{
 const states=new Map([[0,'COMPLETE'],[1,'PROCESSING'],[3,'FAIL'],[9,'OTHER']]);
 for(let value=0;value<256;value++){const r=sensorCalibrationNotification(message(Buffer.from([value,value])));assert.equal(r.rawProgressValue,value);assert.equal(r.rawStatus,value);assert.equal(r.sourceStatus,states.get(value)??'OTHER');assert.equal(r.sourceStatusKnown,states.has(value));assert.equal(r.progressUnitVerified,false);assert.equal(r.inProgress,undefined);}
});
test('short, encrypted, ACK and wrong envelope messages cannot synthesize default progress',()=>{
 for(const payload of [Buffer.alloc(0),Buffer.from([1]),[]])assert.equal(sensorCalibrationNotification(message(payload)),null);
 for(const patch of [{flags:128},{flags:1},{flags:256},{flags:-1},{flags:true},{flags:undefined},{sender:36},{receiver:4},{commandSet:0},{commandId:8},{commandId:110}])assert.equal(sensorCalibrationNotification({...message(),...patch}),null);
});
test('profile and copied observer snapshots do not write or update other calibration domains',async t=>{
 const {gimbal,peripheral:p}=await connected(t);incoming(p);assert.equal(gimbal.appCommands.sensorCalibrationStatus,null);gimbal.appCommands.useProfile('ronin-2.2.2');const errors=[];gimbal.onError=e=>errors.push(e);gimbal.onAppStatus=s=>{s.rawStatus=0;throw Error('sensor observer');};incoming(p);const r=gimbal.appCommands.sensorCalibrationStatus;assert.equal(r.rawStatus,3);r.sourceStatus='COMPLETE';assert.equal(gimbal.appCommands.sensorCalibrationStatus.sourceStatus,'FAIL');assert.equal(errors.length,1);assert.equal(p.frames().length,0);assert.equal(gimbal.appCommands.calibrationStatus,null);assert.equal('externalDeviceStatus' in gimbal.appCommands,false);assert.deepEqual(gimbal.experimental.status,{});assert.equal(gimbal.latestTelemetry,null);
});
test('invalid packets retain cache; source changes and disconnect clear independent snapshot',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');incoming(p);const before=gimbal.appCommands.sensorCalibrationStatus;incoming(p,Buffer.from([0]));incoming(p,body(),128);incoming(p,body(),1);assert.deepEqual(gimbal.appCommands.sensorCalibrationStatus,before);gimbal.appCommands.useProfile('ronin-2.2.2');assert.equal(gimbal.appCommands.sensorCalibrationStatus,null);incoming(p);gimbal.experimental.useProfile('rs3');assert.equal(gimbal.appCommands.sensorCalibrationStatus,null);incoming(p);assert.equal(gimbal.appCommands.sensorCalibrationStatus,null);gimbal.appCommands.useProfile('ronin-2.2.2');incoming(p);await gimbal.disconnect();assert.equal(gimbal.appCommands.sensorCalibrationStatus,null);assert.equal(p.frames().filter(f=>[8,48,18].includes(f.commandId)).length,0);
});
test('COMPLETE status cannot complete query or moveTo and never requests auto calibration',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const query=gimbal.appCommands.getWorkMode();await until(()=>p.frames().some(f=>f.commandId===16));const r=p.frames().find(f=>f.commandId===16);incoming(p,Buffer.from([100,0]));assert.equal(gimbal.experimental.pending.size,1);incoming(p,Buffer.from([0,62,1,2]),128,16,r.sequence);assert.equal((await query).sourceMode,'Fpv');
 const moving=gimbal.moveTo({pan:5});const rejected=assert.rejects(moving,{code:'RS4MINI_MOVE_CANCELLED'});const owner=gimbal.activeOperation;incoming(p,Buffer.from([100,0]));assert.equal(gimbal.activeOperation,owner);assert.equal(gimbal.appCommands.sensorCalibrationStatus.physicalCompletionVerified,false);await gimbal.stop();await rejected;assert.equal(p.frames().filter(f=>f.commandId===8).length,0);
});
