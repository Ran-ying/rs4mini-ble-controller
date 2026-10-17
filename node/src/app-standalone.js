// Explicit source-2 + named value packet from the App's standalone path.
import {bytes} from './bytes.js';
import {parameterReply} from './app-protocol.js';
const axes=['pitch','roll','yaw'];
const groups=[['speed',[80,79,81],0,100],['smoothing',[77,76,78],0,30]];
export function standaloneSelection(options={}) {
  if (!options || typeof options!=='object' || Array.isArray(options) || Object.keys(options).some(k=>!['axis','parameter'].includes(k))) throw new TypeError('Unknown standalone selection');
  if (options.axis!==undefined && !axes.includes(options.axis)) throw new TypeError('axis must be pitch, roll or yaw');
  if (options.parameter!==undefined && !groups.some(([name])=>name===options.parameter)) throw new TypeError('Unknown standalone parameter');
  return groups.flatMap(([parameter,indexes,min,max])=>axes.map((axis,i)=>({axis,parameter,index:indexes[i],size:2,min,max})))
    .filter(row=>(options.axis===undefined || row.axis===options.axis) && (options.parameter===undefined || row.parameter===options.parameter));
}
export function standaloneWrite({inputSource,axis,parameter,value}) {
  if (inputSource!==2) throw new RangeError('Explicit inputSource:2 required for this source path');
  if (axis===undefined || parameter===undefined) throw new TypeError('Standalone write requires axis and parameter');
  const row=standaloneSelection({axis,parameter})[0];
  if (!Number.isInteger(value) || value<row.min || value>row.max) throw new RangeError('value outside named source range');
  return {payload:bytes([72,1,2,row.index,2,value&255,(value>>>8)&255]),axis,parameter,requestedValue:value,requestedInputSource:2};
}
export function standaloneContext(selection) {return [{index:72,size:1},...selection.map(({index,size})=>({index,size}))];}
export function standaloneReply(message,selection) {
  const reply=parameterReply(message,standaloneContext(selection));
  return {...reply,inputSourceRaw:parseInt(reply.parameters[0].rawHex,16),activePresetVerified:false,values:reply.parameters.slice(1).map((record,i)=>{
    const row=selection[i],rawValue=parseInt(record.rawHex.slice(0,2),16)+256*parseInt(record.rawHex.slice(2,4),16);
    return {...record,axis:row.axis,parameter:row.parameter,rawValue,withinSourceRange:rawValue>=row.min && rawValue<=row.max};
  })};
}
