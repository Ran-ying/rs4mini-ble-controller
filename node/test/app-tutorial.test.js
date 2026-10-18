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
test('tutorial source, copied nested cache and observer failures remain isolated without writes',async t=>{
 const {gimbal,peripheral:p}=await connected(t);const body=Buffer.from('ffffffffffaa','hex');incoming(p,body);assert.equal(gimbal.appCommands.tutorialStatus,null);gimbal.appCommands.useProfile('ronin-2.2.2');gimbal.onAppStatus=async s=>{if(s.kind==='tutorial'){s.sourceFlags.getIsUnlock=9;s.sourceStepStatus.STEP_FINISH=false;throw Error('observer');}};incoming(p,body);await new Promise(r=>setImmediate(r));const r=gimbal.appCommands.tutorialStatus;assert.equal(r.sourceFlags.getIsUnlock,1);assert.equal(r.sourceStepStatus.STEP_FINISH,true);r.sourceFlags.getIsUnlock=0;assert.equal(gimbal.appCommands.tutorialStatus.sourceFlags.getIsUnlock,1);gimbal.appCommands.useProfile('ronin-2.2.2');assert.equal(gimbal.appCommands.tutorialStatus,null);incoming(p,body);gimbal.experimental.useProfile('rs3');assert.equal(gimbal.appCommands.tutorialStatus,null);gimbal.appCommands.useProfile('ronin-2.2.2');incoming(p,body);assert.equal(p.frames().length,0);await gimbal.disconnect();assert.equal(gimbal.appCommands.tutorialStatus,null);assert.ok(p.frames().every(f=>f.commandId===1));
});
test('tutorial finish-looking packet cannot complete an outstanding App query',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const query=gimbal.appCommands.getWorkMode();await until(()=>p.frames().some(f=>f.commandId===16));const sent=p.frames().find(f=>f.commandId===16);incoming(p,[0,255,255,255,255],{sequence:sent.sequence});assert.equal(gimbal.experimental.pending.size,1);assert.equal(gimbal.appCommands.tutorialStatus.knownSourceStepName,'STEP_FINISH');incoming(p,[0,62,1,2],{sequence:sent.sequence,commandId:16,flags:128});await query;assert.equal(gimbal.experimental.pending.size,0);assert.deepEqual(p.frames().map(f=>f.commandId),[16]);
});
test('tutorial finish-looking packet cannot supply joint feedback or finish moveTo',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const failed=assert.rejects(gimbal.moveTo({pan:5}),{code:'RS4MINI_MOVE_CANCELLED'});await until(()=>gimbal.activeOperation!==null);const owner=gimbal.activeOperation;incoming(p,[255,255,255,255,255]);assert.equal(gimbal.activeOperation,owner);assert.equal(gimbal.latestTelemetry,null);assert.equal(gimbal.appCommands.sensorCalibrationStatus,null);assert.equal(gimbal.appCommands.calibrationStatus,null);await gimbal.stop();await failed;assert.ok(p.frames().every(f=>f.commandId===1));
});
test('tutorial malformed notifications preserve prior full state and send no ACK or steps',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');let events=0;gimbal.onAppStatus=()=>events++;incoming(p,[2,1,0,0,0]);const before=gimbal.appCommands.tutorialStatus;for(const body of [[],[0],[0,0,0,0]])incoming(p,body);incoming(p,[0,255,255,255,255],{flags:128});incoming(p,[0,255,255,255,255],{flags:3});incoming(p,[0,255,255,255,255],{commandId:44});assert.deepEqual(gimbal.appCommands.tutorialStatus,before);assert.equal(events,1);assert.equal(p.frames().length,0);
});
