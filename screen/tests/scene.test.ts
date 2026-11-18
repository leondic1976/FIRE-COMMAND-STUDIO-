import {describe,it,expect} from 'vitest';
import * as T from 'three';
import {batchStatic,box,material} from '../src/world';
import {entityPosition,timeText,type Building,type Entity} from '../src/types';

describe('static batching preserves site coordinates and movable parts',()=>{
 it('bakes nested transforms without moving the world twice',()=>{
  const root=new T.Group();root.rotation.y=.7;root.position.set(3,0,4);
  for(const x of[-10,12]){const child=new T.Group();child.position.set(x,2,5);child.rotation.y=.3;box(child,3,4,5,material('#cccccc'),2,1,0);root.add(child);}
  const before=new T.Box3().setFromObject(root,true);batchStatic(root);const after=new T.Box3().setFromObject(root,true);
  expect(before.min.distanceTo(after.min)).toBeLessThan(.0001);expect(before.max.distanceTo(after.max)).toBeLessThan(.0001);
  let meshes=0;root.traverse(o=>{if((o as T.Mesh).isMesh)meshes++;});expect(meshes).toBe(1);
 });
 it('retains articulated ladders and individually reviewed model visibility',()=>{
  const root=new T.Group();const model=new T.Group();model.userData.noBatch=true;const ladder=new T.Group();ladder.name='ladder';root.add(model,ladder);
  const m=box(model,2,3,2,material('#cccccc')),l=box(ladder,8,.2,1,material('#cccccc'));batchStatic(root);
  expect(m.parent).toBe(model);expect(l.parent).toBe(ladder);
 });
});
describe('A B C D attachments',()=>{
 const building={id:'B',x:10,z:20,width:40,depth:30,floor_height:4}as Building;
 const entity={kind:'fire',building_id:'B',floor:2,x:5,z:2,y:0,status:'active'}as Entity;
 it.each([['A',[15,6.1,35.4]],['B',[-10.4,6.1,22]],['C',[5,6.1,4.6]],['D',[30.4,6.1,18]]]as const)('%s is clockwise in the top view',(side,expected)=>{
  entityPosition({...entity,side},[building]).forEach((v,i)=>expect(v).toBeCloseTo(expected[i]));
 });
 it('uses explicit ground positions after rescue, with a stable clock label',()=>{
  expect(entityPosition({...entity,status:'rescued',x:48,z:42},[building])).toEqual([48,0,42]);expect(timeText(61.8)).toBe('01:01');
 });
});
