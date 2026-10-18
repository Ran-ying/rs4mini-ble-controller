import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {connected,gate} from './fakes.js';
import {parameterSubscriptionKeys,parameterSubscriptionSpec,parameterSubscriptionFrame,parameterSubscriptionSent} from '../src/app-parameter-subscription.js';
import {DumlStreamDecoder} from '../src/telemetry.js';
const vectors=JSON.parse(readFileSync(new URL('./fixtures/parameter-subscription.json',import.meta.url)));
test('named source vectors use highest channel and LSB bitmap with aliases deduplicated',()=>{
 for(const v of vectors){const spec=parameterSubscriptionSpec(v.keys);assert.equal(spec.requestBodyHex,v.bodyHex);const frames=new DumlStreamDecoder().push(parameterSubscriptionFrame(123,spec));assert.equal(frames.length,1);assert.equal(frames[0].receiver,229);assert.equal(frames[0].flags,0);assert.equal(frames[0].commandId,18);assert.equal(frames[0].payload.toString('hex'),v.bodyHex);}
});
test('catalog is copied, all names encode, resource and model conditions are reported',()=>{
 const keys=parameterSubscriptionKeys();assert.equal(keys.length,152);keys.pop();assert.equal(parameterSubscriptionKeys().length,152);
 const spec=parameterSubscriptionSpec(parameterSubscriptionKeys());assert.equal(spec.payload.length,36);assert.equal(spec.metadataConditionalKeys.length,21);assert.equal(spec.modelConditionalKeys.length,2);assert.equal(spec.sourceGroups.reduce((n,g)=>n+g.channels.length,0),121);
 const sent=parameterSubscriptionSent(spec);assert.equal(sent.payload,undefined);for(const [k,v] of Object.entries(sent))if(k.endsWith('Verified')||k==='acknowledged'||k==='acknowledgementRequested')assert.equal(v,false);
});
test('empty selection is not remote stop and raw controls are rejected',()=>{
 for(const keys of [[],null,'UserProfile',[0],['__proto__'],['unknown'],Array(153).fill('UserProfile')])assert.throws(()=>parameterSubscriptionSpec(keys));
});
test('profile and argument errors occur before neutral or subscription frames',async t=>{
 const {gimbal,peripheral:p}=await connected(t);await assert.rejects(gimbal.appCommands.sendParameterSubscriptionRequest({keys:['UserProfile']}));gimbal.appCommands.useProfile('ronin-2.2.2');
 for(const o of [{keys:[]},{keys:['UserProfile'],enabled:false},{keys:['UserProfile'],receiver:4}])await assert.rejects(gimbal.appCommands.sendParameterSubscriptionRequest(o));assert.equal(p.frames().length,0);
});
test('explicit request snapshots input, stops host motion, sends once without ACK or retry',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const keys=['UserProfile'];const q=gimbal.appCommands.sendParameterSubscriptionRequest({keys});keys[0]='SilentMode';const r=await q;
 assert.deepEqual(r.requestedKeys,['UserProfile']);assert.deepEqual(p.frames().map(f=>f.commandId),[1,1,1,18]);assert.equal(p.frames().at(-1).payload.toString('hex'),'100001');assert.equal(gimbal.experimental.pending.size,0);assert.equal(gimbal.activeOperation,null);
 await new Promise(resolve=>setTimeout(resolve,30));assert.equal(p.frames().length,4);assert.equal(gimbal.appCommands.userParameterStatus,null);
});

test('stop before subscription cancels preamble without any subscription or inverse write',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const q=gimbal.appCommands.sendParameterSubscriptionRequest({keys:['UserProfile']});const rejected=assert.rejects(q,{code:'RS4MINI_OPERATION_CANCELLED'});await gimbal.stop();await rejected;assert.ok(p.frames().every(f=>f.commandId===1));assert.equal(gimbal.activeOperation,null);
});
test('started multi-chunk subscription finishes frame before cancellation cleanup',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const blocked=gate(),started=gate(),original=p.tx.writeAsync.bind(p.tx);
 p.tx.writeAsync=async(chunk,mode)=>{if(chunk[0]===85&&chunk[9]===4&&chunk[10]===18){started.resolve();await blocked.promise;}return original(chunk,mode);};
 const q=gimbal.appCommands.sendParameterSubscriptionRequest({keys:gimbal.appCommands.parameterSubscriptionKeys});const rejected=assert.rejects(q,{code:'RS4MINI_OPERATION_CANCELLED'});await started.promise;
 await assert.rejects(gimbal.setVelocity({pan:.1}),{code:'RS4MINI_BUSY'});assert.throws(()=>gimbal.appCommands.useProfile('ronin-2.2.2'),{code:'RS4MINI_BUSY'});
 const stop=gimbal.stop();blocked.resolve();await stop;await rejected;const frames=p.frames();assert.deepEqual(frames.map(f=>f.commandId),[1,1,1,18,1,1,1]);assert.equal(frames[3].payload.length,36);assert.equal(gimbal.experimental.pending.size,0);assert.equal(gimbal.activeOperation,null);
});
test('subscription write failure invalidates link without retry',async t=>{
 const {gimbal,peripheral:p}=await connected(t);gimbal.appCommands.useProfile('ronin-2.2.2');const original=p.tx.writeAsync.bind(p.tx);let attempts=0;
 p.tx.writeAsync=async(chunk,mode)=>{if(chunk[0]===85&&chunk[10]===18){attempts++;throw Error('fake write failure');}return original(chunk,mode);};
 await assert.rejects(gimbal.appCommands.sendParameterSubscriptionRequest({keys:['UserProfile']}));assert.equal(attempts,1);assert.equal(p.state,'disconnected');assert.equal(gimbal.experimental.pending.size,0);assert.equal(p.frames().filter(f=>f.commandId===18).length,0);
});
test('subscription write timeout invalidates link without delayed resend',async t=>{
 const {gimbal,peripheral:p}=await connected(t,{ioTimeoutMs:15});gimbal.appCommands.useProfile('ronin-2.2.2');const original=p.tx.writeAsync.bind(p.tx);let attempts=0;
 p.tx.writeAsync=async(chunk,mode)=>{if(chunk[0]===85&&chunk[10]===18){attempts++;return new Promise(()=>{});}return original(chunk,mode);};
 await assert.rejects(gimbal.appCommands.sendParameterSubscriptionRequest({keys:['UserProfile']}),{code:'RS4MINI_IO_TIMEOUT'});assert.equal(attempts,1);assert.equal(p.state,'disconnected');assert.equal(gimbal.activeOperation,null);
});
