import assert from 'node:assert/strict';
import {updateLitePanel} from '../web/panels/legacy_lite_panel.js';
const element=()=>({textContent:'',children:[],checked:true,getAttribute:()=> 'true',replaceChildren(){this.children=[];this.textContent='';},append(p){this.children.push(p);}});
globalThis.document={createElement:element};
const selected={key:'R',solver_id:'R',cad_floor:'B3',cad_room:'R6'};
const score={degree:[1.25],weakest:['fuel'],strongest:['oxygen']};
const base={time_s:[0],rooms:[selected],fires:[],events:[],solvers:{R:{ODu:[0],height_m:3,h:[3],Qsolid_kW:[0],conditions:Object.fromEntries(['FO','FGI','backdraft'].map(k=>[k,{scores:score}]))}}};
function render(data,clicked=true){const elements=new Map();const $=id=>{if(!elements.has(id))elements.set(id,element());return elements.get(id);};updateLitePanel({data,index:0,selected,clicked,playing:false,floor:'B3',$,selectionLabel:element(),riskStatus:''});return $('liteScores');}
let output=render(base);assert.equal(output.children.length,3);assert.match(output.children[0].textContent,/125/);assert.match(output.children[0].textContent,/fuel/);
const sparse=structuredClone(base);for(const c of Object.values(sparse.solvers.R.conditions)){c.scores={degree:[null]};}
output=render(sparse);assert.equal(output.children.length,3);assert.match(output.children[0].textContent,/미평가/);assert.doesNotMatch(output.children[0].textContent,/NaN/);
const invalid=structuredClone(sparse);invalid.status='physically_invalid';for(const c of Object.values(invalid.solvers.R.conditions))c.status='physically_invalid';
output=render(invalid);assert.equal(output.children.length,0);assert.match(output.textContent,/검사 실패/);
delete invalid.status;output=render(invalid);assert.equal(output.children.length,0);
invalid.physical_validation={status:'physically_invalid'};output=render(invalid);assert.equal(output.children.length,0);assert.match(output.textContent,/표시 제외/);
assert.equal(render(base,false).children.length,0);
console.log('PASS: 6 legacy panel cases: valid, sparse, invalid playback, invalid condition, validation flag, no selection');
