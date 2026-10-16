// Ordinary named numeric parameters only; never selects presets or input source.
import {bytes} from './bytes.js';
import {parameterReply} from './app-protocol.js';
const axes=['pitch','roll','yaw'];
const groups={follow:[['speed',[3,12,2],2,1,100],['acceleration',[15,16,14],2,1,100],['deadZone',[5,13,4],2,0,100]],
  rc:[['speed',[42,43,41],2,0,100],['deadZone',[27,40,26],1,0,100],['smoothing',[9,39,8],2,0,30]]};
export function tuningSelection(domain,options={}) {
  if (typeof domain!=='string' || !Object.hasOwn(groups,domain)) throw new TypeError('Unknown tuning domain');
  if (!options || typeof options!=='object' || Array.isArray(options) || Object.keys(options).some(key=>!['axis','parameter'].includes(key))) throw new TypeError('Unknown tuning selection');
  if (options.axis!==undefined && !axes.includes(options.axis)) throw new TypeError('axis must be pitch, roll or yaw');
  if (options.parameter!==undefined && !groups[domain].some(([name])=>name===options.parameter)) throw new TypeError('Unknown named tuning parameter');
  return groups[domain].flatMap(([parameter,indexes,size,min,max])=>axes.map((axis,i)=>({axis,parameter,index:indexes[i],size,min,max})))
    .filter(row=>(options.axis===undefined || row.axis===options.axis) && (options.parameter===undefined || row.parameter===options.parameter));
}
export function tuningWrite(domain,{axis,parameter,value}) {
  if (axis===undefined || parameter===undefined) throw new TypeError('Tuning write requires axis and parameter');
  const row=tuningSelection(domain,{axis,parameter})[0];
  if (!Number.isInteger(value) || value<row.min || value>row.max) throw new RangeError('value outside named source range');
  return {payload:bytes([row.index,row.size,...Array.from({length:row.size},(_,i)=>(value>>>(8*i))&255)]),axis,parameter,requestedValue:value};
}
export function tuningReply(message,selection) {
  const result=parameterReply(message,selection.map(({index,size})=>({index,size})));
  return {...result,activePresetVerified:false,values:result.parameters.map((record,i)=>{
    const row=selection[i];let rawValue=0;
    for(let b=0;b<row.size;b++)rawValue+=parseInt(record.rawHex.slice(2*b,2*b+2),16)*2**(8*b);
    return {...record,axis:row.axis,parameter:row.parameter,rawValue,withinSourceRange:rawValue>=row.min && rawValue<=row.max};
  })};
}
