// Offline only: verify the document's independent Python codec against Node.
// Does not import device-node/Noble, instantiate a controller or access Bluetooth.
import fs from 'node:fs';
import {spawnSync} from 'node:child_process';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
import {frame,crc8,crc16,velocityFrame,recenterFrame} from '../node/src/protocol.js';
import {parseDumlFrame,DumlStreamDecoder,decodeGimbalTelemetry} from '../node/src/telemetry.js';
import {parameterRequest,parameterReply,sensitivityPayload} from '../node/src/app-protocol.js';
import {settingsWrite} from '../node/src/app-settings.js';
import {tuningSelection,tuningWrite} from '../node/src/app-tuning.js';
import {standaloneSelection,standaloneWrite} from '../node/src/app-standalone.js';
import {motorSelection,motorWrite} from '../node/src/app-motor.js';
import {axisModeWrite} from '../node/src/app-axis-mode.js';
import {smoothTrackWrite} from '../node/src/app-smooth-track.js';
import {profileValueWrite} from '../node/src/app-profile-values.js';
import {fineTuneSpec} from '../node/src/app-fine-tune.js';
import {autoTunePayload,calibrationRecords,calibrationNotification} from '../node/src/app-calibration.js';
import {componentCalibrationPayload,componentCalibrationReply} from '../node/src/app-component-calibration.js';
import {sensorCalibrationNotification} from '../node/src/app-sensor-calibration.js';
import {programStatusRequestSpec} from '../node/src/app-program-request.js';
import {programStatusNotification} from '../node/src/app-program-status.js';
import {sourceStatusNotification} from '../node/src/app-source-status.js';
import {centerInfoSpec,centerInfoReply} from '../node/src/app-center-info.js';
import {rs3AbsoluteFrame,rs3RateFrame,researchSleepFrame} from '../node/src/experimental-protocol.js';
import {BleDevice} from '../node/src/device.js';
import {RS4Mini} from '../node/src/controller.js';
import {AppCommands} from '../node/src/app-commands.js';
import {ExperimentalDevice} from '../node/src/experimental-device.js';
import {ExperimentalGimbal} from '../node/src/experimental.js';

const path=new URL('../docs/SDK_RECONSTRUCTION_SPEC.md',import.meta.url);
let doc=fs.readFileSync(path,'utf8');
const hex=b=>Buffer.from(b).toString('hex');
const pick=(v,keys)=>Object.fromEntries(keys.map(k=>[k,v[k]]));
const message=(body,id=16,flags=128,sender=4)=>({raw:Buffer.alloc(0),sender,receiver:2,commandSet:4,commandId:id,flags,payload:Buffer.from(body)});
const compactFrame=m=>({...pick(m,['length','sender','receiver','sequence','flags','commandSet','commandId']),rawHex:hex(m.raw),payloadHex:hex(m.payload)});
function makeFrame(k){const p=frame(k.sequence,k.commandSet,k.commandId,Buffer.from(k.payloadHex??'','hex'),k.flags??0);p[4]=k.sender??2;p[5]=k.receiver??4;p.writeUInt16LE(crc16(p.subarray(0,-2)),p.length-2);return p;}
const statusKeys={
 calibration:['records','rawState','state','rawPercent','percent','bodyHex'],
 sensor:['rawProgressValue','rawStatus','sourceStatus','sourceStatusKnown','bodyHex','trailingHex'],
 component:['bodyHex','businessComplete','calibration','responsePartMatchesRequested'],
 program:['commandId','bodyHex','format','sourceValues','rawSuccessByte','sourceSuccess','records'],
 abnormal:['bodyHex','sourceValues'],
 center:['activeByte','sourceActiveBit','unknownActiveBits','dateRaw','serialNumberRawHex','sourceSerialNumber','serialNumberLength','trailingBodyHex','bodyHex'],
};
function compactTelemetry(r){return {attitude:pick(r.attitude,['pitch','roll','yaw']),jointAngles:r.jointAngles?pick(r.jointAngles,['pitch','roll','yaw']):null,components:r.orientationQuaternion?.components??null,aux:pick(r,['modeFlags','rollAdjust','yawAngle','limitFlags','stateFlags'])};}
function status(kind,m,k={}){
 let r;
 if(kind==='telemetry'){r=decodeGimbalTelemetry(m);return r?compactTelemetry(r):null;}
 if(kind==='calibration')r=calibrationNotification(m);
 if(kind==='sensor')r=sensorCalibrationNotification(m);
 if(kind==='program')r=programStatusNotification(m);
 if(kind==='abnormal'){r=sourceStatusNotification(m);if(r?.kind!=='abnormal')return null;}
 if(kind==='component')r=componentCalibrationReply(m,0);
 if(kind==='center')r=centerInfoReply({...m,commandSet:0,commandId:50,sender:229},k.sourceVersion);
 return r?pick(r,statusKeys[kind]):null;
}
function source(c){
 const k=c.args??{},b=Buffer.from(k.hex??'','hex');
 if(c.op==='frame')return hex(makeFrame(k));
 if(c.op==='parse')return compactFrame(parseDumlFrame(b));
 if(c.op==='selection')return k.domain==='motor'?motorSelection(pickFilters(k)):k.domain==='standalone'?standaloneSelection(pickFilters(k)):tuningSelection(k.domain,pickFilters(k));
 if(c.op==='payload'){
  let out;
  switch(c.kind){
   case'velocity':out=velocityFrame(1,k).subarray(11,-2);break;
   case'recenter':out=recenterFrame(1).subarray(11,-2);break;
   case'read':out=parameterRequest(k.parameters);break;
   case'sensitivity':out=sensitivityPayload(k.mode);break;
   case'numeric':out=(k.domain==='motor'?motorWrite(k):k.domain==='standalone'?standaloneWrite(k):tuningWrite(k.domain,k)).payload;break;
   case'settings':out=settingsWrite(k.kind,k.patch,k.raw).payload;break;
   case'axis_mode':out=axisModeWrite(k).payload;break;
   case'smooth':out=smoothTrackWrite(k.axes).payload;break;
   case'user_profile':out=profileValueWrite('userProfile',k.sourceProfileValue).payload;break;
   case'work_mode':out=profileValueWrite('workMode',k.sourceMode).payload;break;
   case'fine':out=fineTuneSpec(k).payload;break;
   case'autotune':out=autoTunePayload(k.start);break;
   case'component':out=componentCalibrationPayload(k.sourcePart);break;
   case'program':out=programStatusRequestSpec(k.program).payload;break;
   case'center':out=centerInfoSpec(k.sourceVersion).payload;break;
   case'research_sleep':out=researchSleepFrame(1,k.profile,k.asleep).subarray(11,-2);break;
   case'research_absolute':out=rs3AbsoluteFrame(1,k).subarray(11,-2);break;
   case'research_rate':{const {release,...axes}=k;out=rs3RateFrame(1,axes,release??false).subarray(11,-2);break;}
   default:throw Error('unhandled payload '+c.kind);
  }
  return hex(out);
 }
 if(c.op==='parameters')return pick(parameterReply(message(b),k.parameters),['bodyHex','parameters']);
 if(c.op==='decode'){
  if(c.kind==='calibration')return calibrationRecords(b);
  const id={telemetry:5,sensor:48,program:k.commandId,abnormal:39,component:8,center:50}[c.kind];
  const r=status(c.kind,message(b,id,['component','center'].includes(c.kind)?128:0),k);if(!r)throw Error('incomplete body');return r;
 }
 if(c.op==='notification')return status(c.kind,{...k,raw:Buffer.alloc(0),payload:Buffer.from(k.payloadHex,'hex')});
 if(c.op==='stream'){
  const d=new DumlStreamDecoder({maxBufferedBytes:k.limit??8192}),messages=[];
  for(const chunk of k.chunks)messages.push(...d.push(Buffer.from(chunk,'hex')).map(compactFrame));
  return {messages,invalidFrames:d.invalidFrames,discardedBytes:d.discardedBytes,bufferHex:hex(d.buffer)};
 }
 throw Error('unhandled op '+c.op);
}
function pickFilters(k){return Object.fromEntries(['axis','parameter'].filter(n=>k[n]!==undefined).map(n=>[n,k[n]]));}
function expected(c){try{return {ok:true,value:JSON.parse(JSON.stringify(source(c)))};}catch{return {ok:false};}}
const api=Object.fromEntries([BleDevice,AppCommands,RS4Mini,ExperimentalDevice,ExperimentalGimbal].map(C=>[C.name,Object.getOwnPropertyNames(C.prototype).filter(n=>n!=='constructor'&&!n.startsWith('_')).sort()]));

const vectors=[];
function vector(name,k){const frameHex=hex(makeFrame({sequence:256,...k}));vectors.push({name,...k,sequence:256,frameHex});}
vector('stop',{commandSet:4,commandId:1,flags:0,payloadHex:hex(velocityFrame(256).subarray(11,-2))});
vector('pan-positive-0.1',{commandSet:4,commandId:1,payloadHex:hex(velocityFrame(256,{pan:.1}).subarray(11,-2))});
vector('recenter',{commandSet:4,commandId:76,flags:64,payloadHex:'fe01'});
vector('degree-info',{commandSet:4,commandId:30,flags:64,payloadHex:''});
vector('sensitivity-read',{commandSet:4,commandId:16,flags:64,payloadHex:'96'});
vector('sensitivity-read-ACK-header9',{commandSet:4,commandId:16,flags:128,sender:4,receiver:2,payloadHex:'00960901'});
vector('sensitivity-write1',{commandSet:4,commandId:15,flags:64,payloadHex:'960101'});
vector('parameter-write-ACK',{commandSet:4,commandId:15,flags:128,sender:4,receiver:2,payloadHex:'00'});
vector('follow-pitch-acceleration1',{commandSet:4,commandId:15,flags:64,payloadHex:'0f020100'});
vector('follow-speed-pitch-high-raw55',{commandSet:4,commandId:15,flags:64,payloadHex:hex(settingsWrite('followSpeed',{pitch:'high'},0x55).payload)});
vector('standalone-pitch-speed50',{commandSet:4,commandId:15,flags:64,payloadHex:'48010250023200'});
vector('motor-pitch-stiffness-read',{commandSet:4,commandId:50,flags:64,payloadHex:'00'});
vector('motor-pitch-stiffness-read-ACK41',{commandSet:4,commandId:50,flags:128,sender:4,receiver:2,payloadHex:'00000129'});
vector('motor-pitch-stiffness-write41',{commandSet:4,commandId:49,flags:64,payloadHex:'000129'});
vector('smooth-yaw-true-roll-false',{commandSet:4,commandId:15,flags:64,payloadHex:'110101130100'});
vector('axis-mode-ThreeDRoll360',{commandSet:4,commandId:15,flags:64,payloadHex:'220118'});
vector('profile2',{commandSet:4,commandId:15,flags:64,payloadHex:'000102'});
vector('work-mode-Center',{commandSet:4,commandId:15,flags:64,payloadHex:'3e0103'});
vector('fine-pitch-minus2',{commandSet:4,commandId:7,flags:64,payloadHex:'ec02'});
vector('autotune-start',{commandSet:4,commandId:106,flags:0,payloadHex:'000101'});
vector('autotune-stop',{commandSet:4,commandId:106,flags:0,payloadHex:'000100'});
vector('autotune-complete-push',{commandSet:4,commandId:110,flags:0,sender:4,receiver:2,payloadHex:'00020264'});
vector('horizontal-AUTO',{commandSet:4,commandId:8,flags:64,payloadHex:'00'});
vector('horizontal-ACK',{commandSet:4,commandId:8,flags:128,sender:4,receiver:2,payloadHex:'000001aa'});
vector('horizontal-complete-push',{commandSet:4,commandId:48,flags:0,sender:4,receiver:2,payloadHex:'6400aa'});
for(const program of ['track','timelapse','panorama'])vector('program-single-'+program,{commandSet:4,commandId:107,flags:64,payloadHex:hex(programStatusRequestSpec(program).payload)});
vector('track-status-record',{commandSet:4,commandId:107,flags:0,sender:4,receiver:2,payloadHex:'00620401020304'});
vector('standalone-timelapse-status',{commandSet:4,commandId:56,flags:0,sender:4,receiver:2,payloadHex:'ff020304'});
vector('standalone-panorama-status',{commandSet:4,commandId:100,flags:0,sender:4,receiver:2,payloadHex:'00ffff0080'});
vector('abnormal-status',{commandSet:4,commandId:39,flags:0,sender:4,receiver:2,payloadHex:'04ff3e6701aabb'});
vector('CENTER-Ver1_1-read',{commandSet:0,commandId:50,flags:64,receiver:229,payloadHex:'11'});
vector('CENTER-synthetic-ACK-AI42',{commandSet:0,commandId:50,flags:128,sender:229,receiver:2,payloadHex:'0001ea070a150c22380441493432'});
const telemetry=Buffer.alloc(49);telemetry.writeInt16LE(-123,0);telemetry.writeInt16LE(45,2);telemetry.writeInt16LE(1799,4);telemetry[6]=3;telemetry.writeInt8(-2,7);telemetry.writeInt16LE(123,8);telemetry[10]=17;telemetry[11]=34;telemetry.writeInt16LE(9160,16);telemetry.writeInt16LE(-8,20);telemetry.writeInt16LE(-5,22);telemetry.writeFloatLE(1,24);
vector('synthetic-telemetry49',{commandSet:4,commandId:5,flags:0,sender:4,receiver:2,payloadHex:hex(telemetry)});
for(const [kind,set,id]of [['version',0,1],['controlStatus',4,11],['type',4,28]])vector('research-query-'+kind,{commandSet:set,commandId:id,flags:64,payloadHex:''});
vector('research-absolute-pan1.25',{commandSet:4,commandId:20,flags:64,payloadHex:hex(rs3AbsoluteFrame(256,{pan:1.25,parameterByte:20}).subarray(11,-2))});
vector('research-rate-release',{commandSet:4,commandId:12,flags:64,payloadHex:hex(rs3RateFrame(256,{},true).subarray(11,-2))});
for(const profile of ['rs3','rs3mini'])vector('research-sleep-'+profile,{commandSet:4,commandId:15,flags:64,payloadHex:hex(researchSleepFrame(256,profile,true).subarray(11,-2))});

const goldenSection='<!-- GOLDEN_VECTORS_BEGIN -->\n### 16.1 完整合成帧向量\n\n以下均为公开合成示例，序号固定256；`AI42`是虚构SN，非用户数据。字段为十进制JSON，frameHex/payloadHex为十六进制。flags未给时为0，sender/receiver未给时为2/4。每项是一条DUML帧，不包含第12节可能附加的先行/收尾中位帧，不是完整连接会话脚本。例程不要求逐条向真机发送，尤其维护和研究包只供离线核对。\n\n```json\n'+JSON.stringify(vectors,null,2)+'\n```\n<!-- GOLDEN_VECTORS_END -->';
const apiSection='<!-- PUBLIC_API_BEGIN -->\n### 16.2 当前公开原型成员清单\n\n仅列公开方法和getter名，不包括构造器、下划线内部方法、实例回调字段或Python别名。继承成员由父层提供，不应建立重复连接。\n\n```json\n'+JSON.stringify(api,null,2)+'\n```\n<!-- PUBLIC_API_END -->';
if(process.argv.includes('--update')){
 if(doc.includes('<!-- GOLDEN_VECTORS_PLACEHOLDER -->'))doc=doc.replace('<!-- GOLDEN_VECTORS_PLACEHOLDER -->',goldenSection+'\n\n'+apiSection);
 else {doc=doc.replace(/<!-- GOLDEN_VECTORS_BEGIN -->[\s\S]*?<!-- GOLDEN_VECTORS_END -->/,goldenSection);doc=doc.replace(/<!-- PUBLIC_API_BEGIN -->[\s\S]*?<!-- PUBLIC_API_END -->/,apiSection);}
 fs.writeFileSync(path,doc);
}
function block(begin,end,language){const part=doc.split('<!-- '+begin+' -->')[1]?.split('<!-- '+end+' -->')[0];assert.ok(part,'missing '+begin);const code=part.match(new RegExp('```'+language+'\\r?\\n([\\s\\S]*?)```'));assert.ok(code,'missing fenced '+language);return code[1];}
assert.deepEqual(JSON.parse(block('GOLDEN_VECTORS_BEGIN','GOLDEN_VECTORS_END','json')),vectors,'document golden frames differ; inspect source changes before --update');
assert.deepEqual(JSON.parse(block('PUBLIC_API_BEGIN','PUBLIC_API_END','json')),api,'document public API differs');
const code=block('REFERENCE_PYTHON_BEGIN','REFERENCE_PYTHON_END','python');
const nativeHeader=fs.readFileSync(new URL('../macos/RSBleDevice.h',import.meta.url),'utf8');
const nativeFacade=fs.readFileSync(new URL('../macos/RSGimbal.h',import.meta.url),'utf8').replace('#import "RSBleDevice.h"\n','');
assert.equal(block('NATIVE_PUBLIC_BEGIN','NATIVE_PUBLIC_END','objc'),nativeHeader+'\n'+nativeFacade,'native ABI documentation differs');
const packageVersion=JSON.parse(fs.readFileSync(new URL('../node/package.json',import.meta.url),'utf8')).version;
assert.ok(doc.includes('Node/Python SDK **'+packageVersion+'**'),'document SDK version differs');
const cases=[];
const add=(op,kind,args)=>cases.push({op,...(kind?{kind}:{}),args});
for(const v of vectors){add('frame',null,v);add('parse',null,{hex:v.frameHex});}
for(const length of [0,1,242,243,255,256,1010,1011]){
 const args={sequence:65536,commandSet:4,commandId:1,payloadHex:hex(Buffer.alloc(length,0x55))};
 add('frame',null,args);
 if(length<=1010)add('parse',null,{hex:hex(makeFrame(args))});
}
for(const args of [{},{pan:.1},{pan:-1,tilt:1,roll:-.25},{pan:-.5/660},{pan:.5/660},{pan:2,tilt:-2}])add('payload','velocity',args);
add('payload','recenter',{});
for(const domain of ['follow','rc','standalone','motor']){
 const rows=source({op:'selection',args:{domain}});add('selection',null,{domain});
 for(const axis of ['pitch','roll','yaw'])add('selection',null,{domain,axis});
 for(const parameter of new Set(rows.map(r=>r.parameter)))add('selection',null,{domain,parameter});
 for(const row of rows){add('selection',null,{domain,axis:row.axis,parameter:row.parameter});for(const value of [row.min,row.max,row.min-1,row.max+1])add('payload','numeric',{domain,axis:row.axis,parameter:row.parameter,value,...(domain==='standalone'?{inputSource:2}:{})});}
}
for(const kind of ['customFollow','motor','followSpeed','followAcceleration','followDeadZone','rcSpeed','rcDeadZone','rcSmoothing']){
 const mode=!['customFollow','motor'].includes(kind),fields=mode?['pitch','roll','yaw']:kind==='motor'?['enabled','forbidSelfie','forbidVertical','roll360']:['enabled','pitch','roll','yaw'];
 for(let raw=0;raw<=(kind==='customFollow'?15:255);raw++)for(const value of mode?['custom','low','middle','high']:[false,true])add('payload','settings',{kind,raw,patch:Object.fromEntries(fields.map(n=>[n,value]))});
}
for(const mode of [0,1,2,-1,true])add('payload','sensitivity',{mode});
for(const sourceMode of ['ThreeAxis','TwoAxis','Roll360','ThreeDRoll360','Other'])add('payload','axis_mode',{sourceMode});
for(const axes of [{yaw:true},{pitch:false},{roll:true},{yaw:false,pitch:true,roll:false},{yaw:1},{}])add('payload','smooth',{axes});
for(let value=-1;value<=6;value++)add('payload','user_profile',{sourceProfileValue:value});
for(const sourceMode of ['Free','Flower','Fpv','Center','PF'])add('payload','work_mode',{sourceMode});
for(const axis of ['pitch','roll'])for(const adjustmentDegrees of [-2,-1.29,-.15,-.01,0,.125,1.999,2,2.1])add('payload','fine',{axis,adjustmentDegrees});
for(const start of [true,false,1])add('payload','autotune',{start});
for(const sourcePart of ['AUTO','GYRO'])add('payload','component',{sourcePart});
for(const program of ['track','timelapse','panorama','other'])add('payload','program',{program});
for(const sourceVersion of ['Ver1_0','Ver1_1','Ver1_3','Ver13','other'])add('payload','center',{sourceVersion});
for(const profile of ['rs3','rs3mini'])for(const asleep of [true,false])add('payload','research_sleep',{profile,asleep});
for(const args of [{pan:1.25,parameterByte:20},{tilt:-.15,roll:2.5,parameterByte:255},{pan:-180,tilt:180,parameterByte:0}])add('payload','research_absolute',args);
for(const args of [{},{pan:360,tilt:-360,roll:-.15},{release:true}])add('payload','research_rate',args);
for(const parameters of [[{index:150,size:1}],[{index:0,size:1},{index:3,size:2},{index:255,size:8}],[],[{index:2,size:3}]])add('payload','read',{parameters});
for(const [body,parameters]of [['00960901',[{index:150,size:1}]],['0000090203023412',[{index:0,size:1},{index:3,size:2}]],['009601',[{index:150,size:1}]],['00970101',[{index:150,size:1}]],['0096010100',[{index:150,size:1}]],['01960101',[{index:150,size:1}]]])add('parameters',null,{hex:body,parameters});
for(let size=0;size<=60;size++)add('decode','telemetry',{hex:hex(Buffer.concat([telemetry,Buffer.alloc(12)]).subarray(0,size))});
const nonfinite=Buffer.from(telemetry);for(const [offset,value]of [[24,-0],[28,NaN],[32,Infinity],[36,-Infinity]])nonfinite.writeFloatLE(value,offset);
add('decode','telemetry',{hex:hex(nonfinite)});
for(const body of ['','00020264','000201ff','00020264010100','0101aa','000102','ff00','00030264aa00020132'])add('decode','calibration',{hex:body});
for(let rawStatus=0;rawStatus<256;rawStatus++)add('decode','sensor',{hex:hex(Buffer.from([255,rawStatus,170]))});
for(const body of ['00','0000','000001aa','000502','00ffff','01'])add('decode','component',{hex:body});
for(const v of vectors.filter(v=>v.name.startsWith('CENTER-synthetic')))for(const sourceVersion of ['Ver1_1','Ver1_3','Ver13'])add('decode','center',{hex:v.payloadHex,sourceVersion});
add('decode','center',{hex:'0082ea070a150c22384149414243313233343536aa',sourceVersion:'Ver1_0'});
add('decode','center',{hex:'0001ea070a150c2238028000ff',sourceVersion:'Ver13'});
for(const commandId of [56,100,107])for(const body of ['','00','ff','ff020304','00ffff0080','00620401020304','016204010203043704ff020304630500ffff0080ff00','0262','00620100','006280','00ff00'])add('decode','program',{hex:body,commandId});
for(let offset=0;offset<5;offset++)for(let bit=0;bit<8;bit++){const b=Buffer.alloc(5);b[offset]=1<<bit;add('decode','abnormal',{hex:hex(b)});}
for(const [kind,id,body]of [['telemetry',5,telemetry],['sensor',48,Buffer.from([100,0])],['calibration',110,Buffer.from('00020264','hex')],['program',107,Buffer.from('00620401020304','hex')],['abnormal',39,Buffer.alloc(5)]]){
 for(const flags of [0,64,128,1,3,131,255,-1,256,true])add('notification',kind,{sender:4,receiver:2,commandSet:4,commandId:id,flags,payloadHex:hex(body)});
 for(const [key,value]of [['sender',229],['receiver',4],['commandSet',0],['commandId',0]])add('notification',kind,{sender:4,receiver:2,commandSet:4,commandId:id,flags:0,payloadHex:hex(body),[key]:value});
}
const stop=Buffer.from(vectors[0].frameHex,'hex'),broken=Buffer.from(stop);broken[broken.length-1]^=1;
for(const chunks of [[...stop].map(v=>hex([v])),[hex(Buffer.concat([stop,stop]))],['deadbeef',hex(broken),hex(stop)],['55','00','00','00',hex(stop)],['5516',hex(stop)]])add('stream',null,{chunks});
add('stream',null,{limit:13,chunks:[hex(Buffer.alloc(30,1)),hex(stop)]});
const version=Buffer.from(stop);version[2]|=0x80;version[3]=crc8(version.subarray(0,3));version.writeUInt16LE(crc16(version.subarray(0,-2)),version.length-2);add('parse',null,{hex:hex(version)});
for(const bytes of [broken,stop.subarray(0,10),Buffer.alloc(13)])add('parse',null,{hex:hex(bytes)});

const python=process.env.RS4MINI_PYTHON??'python3';
const run=spawnSync(python,['-c',code],{input:JSON.stringify(cases),encoding:'utf8',maxBuffer:16*1024*1024});
assert.equal(run.status,0,run.stderr);const actual=JSON.parse(run.stdout);assert.equal(actual.length,cases.length);
for(let i=0;i<cases.length;i++){
 try{assert.deepEqual(actual[i],expected(cases[i]));}
 catch(e){throw new Error('Independent document reference mismatch at case '+i+' '+JSON.stringify(cases[i])+'\n'+e.message);}
}
const self=spawnSync(python,['-c',code,'--self-test'],{encoding:'utf8'});assert.equal(self.status,0,self.stderr);
const proofPath=new URL('../protocol/SDK_RECONSTRUCTION_CONFORMANCE.json',import.meta.url);
if(fs.existsSync(proofPath)){
 const proof=JSON.parse(fs.readFileSync(proofPath,'utf8'));
 assert.equal(proof.independentCases,cases.length,'refresh audited conformance record after changing cases');
 assert.equal(proof.completeSyntheticFrameVectors,vectors.length);
 assert.equal(proof.nodePublicPrototypeMembers,Object.values(api).reduce((n,v)=>n+v.length,0));
}
console.log(JSON.stringify({document:fileURLToPath(path),referencePython:python,independentCases:cases.length,completeFrameVectors:vectors.length,publicApiClasses:Object.keys(api).length,publicPrototypeMembers:Object.values(api).reduce((n,v)=>n+v.length,0),selfTest:'passed',bluetoothInitialized:false},null,2));
