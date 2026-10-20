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
