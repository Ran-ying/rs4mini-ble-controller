// Inherited current-App fine-tune request; source units are not physical proof.
import {bytes} from './bytes.js';
const axes={"roll":0,"pitch":2};
export function fineTuneSpec({axis,adjustmentDegrees}) {
  if(typeof axis!=='string'||!Object.hasOwn(axes,axis))throw new TypeError('axis must be pitch or roll');
  if(!Number.isFinite(adjustmentDegrees)||adjustmentDegrees < -2||adjustmentDegrees > 2)throw new RangeError('adjustmentDegrees must be finite -2..2');
  const encodedTenths=Math.trunc(Math.fround(Math.fround(adjustmentDegrees)*10))||0;
  return {payload:bytes([encodedTenths&255,axes[axis]]),axis,requestedAdjustmentDegrees:adjustmentDegrees,encodedTenths,nominalAdjustmentDegrees:encodedTenths/10};
}
