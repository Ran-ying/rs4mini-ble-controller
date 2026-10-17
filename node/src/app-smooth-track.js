// Ordinary source axis switches17/18/19, not custom-follow bitfield132.
import {bytes} from './bytes.js';
import {parameterReply} from './app-protocol.js';
const axes={"yaw":17,"pitch":18,"roll":19};
export function smoothTrackSelection(axis) {
  if(axis!==undefined&&(typeof axis!=='string'||!Object.hasOwn(axes,axis)))throw new TypeError('axis must be yaw, pitch or roll');
  return Object.entries(axes).filter(([name])=>axis===undefined||name===axis).map(([axis,index])=>({axis,index,size:1}));
}
export function smoothTrackWrite(patch) {
  if(!patch||typeof patch!=='object'||Array.isArray(patch)||!Object.keys(patch).length||Object.keys(patch).some(k=>!Object.hasOwn(axes,k)||typeof patch[k]!=='boolean'))throw new TypeError('One or more named boolean axes required');
  const selection=smoothTrackSelection().filter(r=>Object.hasOwn(patch,r.axis)),requestedAxes=Object.fromEntries(selection.map(r=>[r.axis,patch[r.axis]]));
  return {payload:bytes(selection.flatMap(r=>[r.index,1,Number(requestedAxes[r.axis])])),requestedAxes};
}
export function smoothTrackReply(message,selection) {
  const result=parameterReply(message,selection.map(({index,size})=>({index,size})));
  return {...result,modelLayoutVerified:false,activePresetVerified:false,values:result.parameters.map((record,i)=>{const rawValue=parseInt(record.rawHex,16),withinSourceRange=rawValue<=1;return {...record,axis:selection[i].axis,rawValue,withinSourceRange,sourceEnabled:rawValue===1,enabled:withinSourceRange?rawValue===1:null};})};
}
