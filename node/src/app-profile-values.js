// Distinct source user-profile0 and work-mode62 parameters.
import {bytes} from './bytes.js';
import {parameterReply} from './app-protocol.js';
const parameters={"userProfile":{"index":0,"size":1,"min":0,"max":5},"workMode":{"index":62,"size":1,"min":0,"max":128}};
const workModes={"Free":0,"Flower":1,"Fpv":2,"Center":3};
export function profileValueSelection(kind) {
  if(typeof kind!=='string'||!Object.hasOwn(parameters,kind))throw new TypeError('Unknown profile parameter');
  return {...parameters[kind]};
}
export function profileValueWrite(kind,value) {
  const row=profileValueSelection(kind);let raw=value,metadata;
  if(kind==='userProfile') {
    if(!Number.isInteger(value)||value<0||value>5)throw new RangeError('sourceProfileValue must be integer0..5');
    metadata={requestedSourceProfileValue:value};
  } else {
    if(typeof value!=='string'||!Object.hasOwn(workModes,value))throw new TypeError('Named source work mode required');
    raw=workModes[value];metadata={requestedSourceMode:value};
  }
  return {payload:bytes([row.index,1,raw]),parameter:kind,requestedRawValue:raw,...metadata};
}
export function profileValueReply(message,kind) {
  const row=profileValueSelection(kind),result=parameterReply(message,[{index:row.index,size:1}]),rawValue=parseInt(result.parameters[0].rawHex,16);
  const reading=kind==='userProfile'?{sourceUiName:['M1','M2','M3'][rawValue]??null}:{sourceMode:Object.keys(workModes).find(k=>workModes[k]===rawValue)??null};
  return {...result,parameter:kind,rawValue,withinSourceRange:rawValue<=row.max,...reading,modelLayoutVerified:false,activePresetVerified:false};
}
