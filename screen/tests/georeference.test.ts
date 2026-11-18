import {expect,it} from 'vitest';
import * as T from 'three';
import {cameraPose,enuBasis,mapViewport,toENU,validCamera} from '../src/georeference';
import type {SceneState} from '../src/types';

it('keeps clockwise front/b/c/d bearings in the east-north-up basis',()=>{
 for(const [bearing,expected] of [[0,[0,10,2]],[90,[10,0,2]],[180,[0,-10,2]],[270,[-10,0,2]]]as const){
  toENU([0,2,10],bearing).forEach((n,i)=>expect(n).toBeCloseTo(expected[i]));
 }
 const local=new T.Vector3(12,6,-17),m=new T.Matrix4().fromArray(enuBasis(123));
 local.clone().applyMatrix4(m).toArray().forEach((n,i)=>expect(n).toBeCloseTo(toENU([12,6,-17],123)[i]));
 expect(m.determinant()).toBeCloseTo(1);
});
const state={site:{latitude:37.5,longitude:127,front_bearing:180},buildings:[{x:20,z:30,floors:3,floor_height:4}],entities:[{kind:'command',visible:true,x:45,y:1,z:70}],messages:['PRIVATE_NOTE'],future:['PRIVATE_FUTURE']}as unknown as SceneState;
it('places the commander at the configured visible command post and other cameras around the selected building',()=>{
 expect(cameraPose(state,'commander').position).toEqual([45,3.2,70]);
 expect(cameraPose(state,'A').position[0]).toBe(62);
 expect(cameraPose(state,'A').target).toEqual([20,5.4,30]);
});
it('sends only viewport coordinates to the SDK, excluding all training arrays and labels',()=>{
 const wire=mapViewport(state,'commander');expect(Object.keys(wire).sort()).toEqual(['latitude','longitude','position','target']);
 expect(JSON.stringify(wire)).not.toContain('PRIVATE');expect(wire.position).toEqual([45,-70,3.2]);
 expect(validCamera({view:Array(16).fill(1),projection:Array(16).fill(1),root:Array(16).fill(1)})).toBe(true);
 for(const bad of [null,{}, {view:Array(200).fill(0)},{view:Array(16).fill(NaN)}])expect(validCamera(bad)).toBe(false);
});
