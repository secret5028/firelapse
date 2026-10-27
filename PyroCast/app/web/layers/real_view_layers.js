import {createRealViewSession} from './real_view.js';
import {createSmokeLayer} from './smoke.js';
import {createFlameLayer} from './flame.js';
import {createPlumeLayer} from './plume.js';
export function createRealViewLayers(THREE,options){
 const session=createRealViewSession(THREE,options);
 return [createSmokeLayer(session),createFlameLayer(session),createPlumeLayer(session)];
}
