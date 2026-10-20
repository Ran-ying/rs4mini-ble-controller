import test from 'node:test';
import assert from 'node:assert/strict';
import {connected, until} from './fakes.js';
import {frame, crc16} from '../src/protocol.js';
const retired=['tutorialStatus','externalDeviceStatus','peripheralStatus','batteryStatus','handheldStickStatus','userParameterStatus'];
const reports=[[43,Buffer.alloc(5)],[105,Buffer.from([2,7,1,0,128,255,127,0,0])],[102,Buffer.from([1,34,2,10,0])],[51,Buffer.from([50])],[87,Buffer.alloc(6)],[36,Buffer.alloc(78)]];
function incoming(p,id,payload,sequence=1,flags=0){const b=frame(sequence,4,id,payload,flags);b[4]=4;b[5]=2;b.writeUInt16LE(crc16(b.subarray(0,-2)),b.length-2);p.rx.emit('data',b,true);}
test('retired status entries absent and complete source reports remain raw without SDK events',async t=>{
 const {gimbal:g,peripheral:p}=await connected(t);g.appCommands.useProfile('ronin-2.2.2');let raw=0,events=0;
 g.onMessage=()=>raw++;g.onAppStatus=()=>events++;
 for(const name of retired)assert.equal(name in g.appCommands,false);
 for(const [id,body] of reports)incoming(p,id,body);
 assert.equal(raw,6);assert.equal(events,0);assert.equal(p.frames().length,0);assert.equal(g.latestTelemetry,null);
 const query=g.appCommands.getFollowSensitivity();await until(()=>p.frames().some(f=>f.commandId===16));const seq=p.frames().find(f=>f.commandId===16).sequence;
 for(const [id,body] of reports)incoming(p,id,body,seq);
 assert.equal(g.experimental.pending.size,1);assert.equal(events,0);
 incoming(p,16,Buffer.from([0,150,1,1]),seq,128);assert.equal((await query).rawValue,1);
 g.experimental.useProfile('rs3');const before=p.frames().length;await assert.rejects(g.experimental.query({kind:'position'}),TypeError);assert.equal(p.frames().length,before);
});
test('retained abnormal state remains copied, observer-isolated and source-scoped',async t=>{
 const {gimbal:g,peripheral:p}=await connected(t);g.appCommands.useProfile('ronin-2.2.2');const errors=[];g.onError=e=>errors.push(e);
 g.onAppStatus=s=>{s.sourceValues.getSleepMode=99;throw Error('observer');};
 incoming(p,39,Buffer.from('04ff3e6701aabb','hex'));assert.equal(g.appCommands.abnormalStatus.sourceValues.getSleepMode,1);assert.equal(errors.length,1);
 const copy=g.appCommands.abnormalStatus;copy.sourceValues.getSleepMode=0;assert.equal(g.appCommands.abnormalStatus.sourceValues.getSleepMode,1);
 g.appCommands.useProfile('ronin-2.2.2');assert.equal(g.appCommands.abnormalStatus,null);
 incoming(p,39,Buffer.from('04ff3e6701aabb','hex'));await g.disconnect();assert.equal(g.appCommands.abnormalStatus,null);
});
