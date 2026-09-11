import test from 'node:test';
import assert from 'node:assert/strict';
import {resolveState,canSelect,STATES} from '../src/state/experienceState.js';
import {aircraftPose} from '../src/animation/aircraftTimeline.js';
import {cameraPose} from '../src/animation/engineZoom.js';
test('extra scroll cannot unlock the engine without selection',()=>{
 assert.equal(resolveState(1,0,false),STATES.SETTLED);
 assert.equal(resolveState(1,1,false),STATES.SETTLED);
 assert.equal(canSelect(.9,false),false);assert.equal(canSelect(1,false),true);
});
test('selected experience reverses through engine to aircraft',()=>{
 assert.deepEqual([resolveState(1,1,true),resolveState(1,.5,true),resolveState(1,0,true),resolveState(.5,0,true),resolveState(0,0,true)],[STATES.HERO,STATES.ZOOM,STATES.SELECTED,STATES.FLIGHT,STATES.INTRO]);
});
test('flight and camera paths are deterministic in either direction',()=>{
 const points=[0,.25,.5,.75,1];const forward=points.map(aircraftPose);
 assert.deepEqual(points.slice().reverse().map(aircraftPose).reverse(),forward);
 const before=cameraPose(.5,1.6,1);cameraPose(1,1.6,1);
 assert.deepEqual(cameraPose(.5,1.6,1),before);
 assert.equal(cameraPose(1,1.6,1).opacity,.1);
});
