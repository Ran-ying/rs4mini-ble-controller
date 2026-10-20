import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';
import {tutorialNotification} from '../src/app-tutorial.js';import {connected,until} from './fakes.js';import {frame,crc16} from '../src/protocol.js';
const message=(body,flags=0)=>({sender:4,receiver:2,commandSet:4,commandId:43,flags,payload:Buffer.from(body)});
function incoming(p,body,overrides={}){const m={sequence:1,sender:4,receiver:2,commandSet:4,commandId:43,flags:0,...overrides};const b=frame(m.sequence,m.commandSet,m.commandId,Buffer.from(body),m.flags);b[4]=m.sender;b[5]=m.receiver;b.writeUInt16LE(crc16(b.subarray(0,-2)),b.length-2);p.rx.emit('data',b,true);}
test('tutorial source contracts preserve full word, fallback and Java step-bit views',()=>{
 const rows=JSON.parse(fs.readFileSync(new URL('./fixtures/tutorial-status.json',import.meta.url)));assert.equal(rows.length,8);
 for(const v of rows){const r=tutorialNotification(message(Buffer.from(v.bodyHex,'hex')));for(const [key,value] of Object.entries(v.expected))assert.deepEqual(r[key],value,v.name+':'+key);assert.equal(r.physicalCompletionVerified,false);assert.equal(r.requestAssociationVerified,false);}
 for(let value=0;value<256;value++){const r=tutorialNotification(message([value,0,0,0,0]));assert.equal(r.rawStep,value);assert.equal(r.knownSourceStepName!==null,value<11);if(value>=11)assert.equal(r.sourceFindResult,'STEP_FINISH');}
 for(let bit=0;bit<32;bit++){const b=Buffer.alloc(5);b.writeUInt32LE((2**bit)>>>0,1);const r=tutorialNotification(message(b));assert.equal(r.rawCompletionWord,2**bit);assert.equal(Object.values(r.sourceFlags).reduce((a,b)=>a+b,0),Number(bit<9));assert.equal(r.sourceStepStatus.STEP_FINISH,bit===30);assert.equal(r.sourceStepStatus.STEP_START,bit===31);assert.equal(r.sourceSignedCompletionWord,bit===31?-2147483648:2**bit);}
});
test('tutorial rejects incomplete and nonplain notification envelopes',()=>{
 for(let size=0;size<5;size++)assert.equal(tutorialNotification(message(Buffer.alloc(size))),null);
 for(const flags of [128,1,2,3,4,5,6,7,-1,256,true,undefined])assert.equal(tutorialNotification({...message(Buffer.alloc(5)),flags}),null);
 for(const key of ['sender','receiver','commandSet','commandId'])assert.equal(tutorialNotification({...message(Buffer.alloc(5)),[key]:0}),null);
 assert.equal(tutorialNotification({...message(Buffer.alloc(5)),payload:[0,0,0,0,0]}),null);
});
test('tutorial finish-looking packet cannot supply joint feedback or finish moveTo',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const failed=assert.rejects(gimbal.moveTo({pan:5}),{code:'RS4MINI_MOVE_CANCELLED'});await until(()=>gimbal.activeOperation!==null);const owner=gimbal.activeOperation;incoming(p,[255,255,255,255,255]);assert.equal(gimbal.activeOperation,owner);assert.equal(gimbal.latestTelemetry,null);assert.equal(gimbal.appCommands.sensorCalibrationStatus,null);assert.equal(gimbal.appCommands.calibrationStatus,null);await gimbal.stop();await failed;assert.ok(p.frames().every(f=>f.commandId===1));
});
