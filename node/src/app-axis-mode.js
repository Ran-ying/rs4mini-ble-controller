// Source axis mode parameter34; independent of motor control parameter35.
import {bytes} from './bytes.js';
import {parameterReply} from './app-protocol.js';
const modes={"ThreeAxis":0,"TwoAxis":8,"Roll360":16,"ThreeDRoll360":24};
const names=['ThreeAxis','TwoAxis','Roll360','ThreeDRoll360'];
export function axisModeWrite({sourceMode}) {
  if(typeof sourceMode!=='string'||!Object.hasOwn(modes,sourceMode))throw new TypeError('Explicit source axis mode required');
  return {payload:bytes([34,1,modes[sourceMode]]),requestedSourceMode:sourceMode,requestedRawValue:modes[sourceMode]};
}
export function axisModeReply(message) {
  const result=parameterReply(message,[{index:34,size:1}]),rawValue=parseInt(result.parameters[0].rawHex,16),sourceModeValue=(rawValue>>>3)&3;
  return {...result,rawValue,sourceModeValue,sourceMode:names[sourceModeValue],unknownBits:rawValue&231,modelLayoutVerified:false,activePresetVerified:false};
}
