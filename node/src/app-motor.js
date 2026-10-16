// Current App's Ronin motor namespace (04:31/32), separate from 04:0F/10.
import { bytes } from './bytes.js';
import { parameterReply } from './app-protocol.js';
const axes = ['pitch','roll','yaw'];
const groups = [ ['stiffness',5], ['strength',1], ['gyroFiltering',0], ['preControl',0] ];
const catalog = groups.flatMap(([parameter,min], group) => axes.map((axis, index) => ({axis,parameter,index:group*3+index,size:1,min,max:100})));
export function motorSelection(options = {}) {
  if (!options || typeof options !== 'object' || Array.isArray(options) || Object.keys(options).some(key=>!['axis','parameter'].includes(key))) throw new TypeError('Unknown motor selection');
  if (options.axis !== undefined && !axes.includes(options.axis)) throw new TypeError('axis must be pitch, roll or yaw');
  if (options.parameter !== undefined && !groups.some(([name])=>name===options.parameter)) throw new TypeError('Unknown named motor parameter');
  return catalog.filter(row=>(options.axis === undefined || row.axis===options.axis) && (options.parameter === undefined || row.parameter===options.parameter)).map(row=>({...row}));
}
export function motorWrite(options) {
  const {axis,parameter,value}=options;
  if (axis===undefined || parameter===undefined) throw new TypeError('Motor write requires axis and parameter');
  const row=motorSelection({axis,parameter})[0];
  if (!Number.isInteger(value) || value<row.min || value>row.max) throw new RangeError('value outside named source range');
  return {payload:bytes([row.index,1,value]),requestedValue:value,axis,parameter};
}
export function motorReply(message, selection) {
  const result=parameterReply(message,selection.map(({index,size})=>({index,size})),0x32);
  return {...result,values:result.parameters.map((record,i)=>{
    const row=selection[i],rawValue=parseInt(record.rawHex,16);
    return {...record,axis:row.axis,parameter:row.parameter,rawValue,withinSourceRange:rawValue>=row.min && rawValue<=row.max};
  })};
}
