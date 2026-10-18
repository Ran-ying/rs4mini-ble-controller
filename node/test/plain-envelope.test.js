import test from 'node:test';
import assert from 'node:assert/strict';
import {connected,until} from './fakes.js';
import {frame,crc16} from '../src/protocol.js';
import {appReply} from '../src/app-protocol.js';
import {calibrationNotification} from '../src/app-calibration.js';
import {decodeGimbalTelemetry} from '../src/telemetry.js';
import {decodeResearchStatus} from '../src/experimental-protocol.js';
const message=(flags,payload=Buffer.from([0]),commandId=15)=>({sender:4,receiver:2,commandSet:4,commandId,flags,payload,raw:Buffer.from([1])});
function incoming(p,id,body,flags,sequence=1){const b=frame(sequence,4,id,body,flags);b[4]=4;b[5]=2;b.writeUInt16LE(crc16(b.subarray(0,-2)),b.length-2);p.rx.emit('data',b,true);}
test('App ACK rejects all encrypted and invalid flag values before status code interpretation',()=>{
 for(const flags of [129,130,131,132,133,134,135,-128,384,128.5,true,undefined,NaN])for(const status of [0,7])assert.throws(()=>appReply(message(flags,Buffer.from([status])),15),{code:'RS4MINI_PROTOCOL_ERROR'});
 assert.equal(appReply(message(128),15).acknowledged,true);assert.throws(()=>appReply(message(128,Buffer.from([7])),15),{code:'RS4MINI_DEVICE_ERROR'});assert.throws(()=>appReply(message(128,[0]),15),{code:'RS4MINI_PROTOCOL_ERROR'});
});
test('typed feedback, legacy status and auto-tune notifications reject ciphertext and ACK feedback',()=>{
 for(const flags of [1,2,3,4,5,6,7,128,undefined,-1,256,true])assert.equal(decodeGimbalTelemetry(message(flags,Buffer.alloc(49),5)),null);
 for(const flags of [1,2,3,4,5,6,7,128,undefined,-1,256,true])assert.equal(calibrationNotification(message(flags,Buffer.from([0,2,2,100]),110)),null);
 for(const flags of [1,2,3,4,5,6,7,undefined,-1,256,true])assert.equal(decodeResearchStatus(message(flags,Buffer.from([100,1]),48),'rs3'),null);
 assert.ok(decodeGimbalTelemetry(message(0,Buffer.alloc(49),5)));assert.equal(calibrationNotification(message(0,Buffer.from([0,2,2,100]),110)).state,'Complete');
});
test('encrypted parameter read cannot advance motor settings read-modify-write',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const pending=gimbal.appCommands.setMotorSettings({forbidSelfie:true});const rejected=assert.rejects(pending,{code:'RS4MINI_PROTOCOL_ERROR'});await until(()=>p.frames().some(f=>f.commandId===16));const r=p.frames().find(f=>f.commandId===16);incoming(p,16,Buffer.from([0,35,1,0]),131,r.sequence);await rejected;assert.equal(p.frames().filter(f=>f.commandId===15).length,0);assert.equal(gimbal.activeOperation,null);assert.equal(gimbal.experimental.pending.size,0);
});
test('encrypted auto-tune-looking notification preserves prior status and triggers no sends',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');incoming(p,110,Buffer.from([0,2,1,20]),0);const before=gimbal.appCommands.calibrationStatus;incoming(p,110,Buffer.from([0,2,2,100]),3);assert.deepEqual(gimbal.appCommands.calibrationStatus,before);assert.equal(p.frames().length,0);
});
test('encrypted joint target remains raw and cannot satisfy or drive moveTo',async t=>{
 const {gimbal,peripheral:p}=await connected(t);const raw=[];gimbal.onMessage=m=>raw.push(m);const pending=gimbal.moveTo({pan:5});const rejected=assert.rejects(pending,{code:'RS4MINI_MOVE_CANCELLED'});await until(()=>gimbal.activeOperation!==null);const owner=gimbal.activeOperation;const payload=Buffer.alloc(49);payload.writeInt16LE(500,16);incoming(p,5,payload,3);await until(()=>raw.length===1);assert.equal(raw[0].flags,3);assert.deepEqual(Buffer.from(raw[0].payload),payload);assert.equal(gimbal.latestTelemetry,null);assert.equal(gimbal.activeOperation,owner);await gimbal.stop();await rejected;assert.ok(p.frames().every(f=>f.commandId===1&&f.payload.readInt16LE(0)===1024&&f.payload.readInt16LE(2)===1024&&f.payload.readInt16LE(4)===1024));
});
test('research ciphertext remains available as raw message without structured status',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.experimental.useProfile('rs3');const raw=[];gimbal.onMessage=m=>raw.push(m);incoming(p,48,Buffer.from([100,1]),3);assert.deepEqual(gimbal.experimental.status,{});assert.equal(raw.length,1);incoming(p,48,Buffer.from([100,1]),0);assert.ok(gimbal.experimental.status.calibration);assert.equal(p.frames().length,0);
});
