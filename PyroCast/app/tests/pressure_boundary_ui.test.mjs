import assert from 'node:assert/strict';
import {isBelowGrade} from '../web/panels/explore.js';
const floors=[{name:'1F',z:15.7},{name:'B3',z:0},{name:'5F',z:30},{name:'P1',z:10}];
assert.equal(isBelowGrade(floors[1],floors),true);assert.equal(isBelowGrade(floors[2],floors),false);assert.equal(isBelowGrade(floors[3],floors),true);assert.equal(isBelowGrade({name:'B3',z:0,below_grade:false},floors),false);assert.equal(isBelowGrade({name:'strange',below_grade:true},[]),true);assert.equal(isBelowGrade({name:'B3',z:0},[]),false);
console.log('PASS: underground advice uses grade and explicit flags, not B3 label');
