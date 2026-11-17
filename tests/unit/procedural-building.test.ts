import {describe,it,expect} from 'vitest';
import * as THREE from 'three';
import type {Building,Feature} from '../../packages/domain-schemas';
import {proceduralBuilding,proceduralInterior} from '../../packages/scene3d/procedural-building';
const b:Building={id:'B01',name:'Synthetic',use:'창고',floors:2,basement_floors:1,floor_height:4,width:20,depth:10,x:0,z:0,rotation:0,color:'#aaaaaa',entrances:['NORTH'],footprint:[],accuracy:'SIMULATED',window_style:'NONE',roof_style:'FLAT',floor_outlines:[{floor:-1,footprint:[[-3,-2],[9,-2],[9,4],[-3,4]]}]};
describe('실제 기하의 층/절개/앵커',()=>{
 it('지하 선택은 그 층 윤곽과 음수 높이를 사용하고 지상층을 숨긴다',()=>{const group=proceduralBuilding(b,{hiddenFloor:-1,cutaway:true}),bounds=new THREE.Box3().setFromObject(group);expect(group.getObjectByName('B01:floor:-1')).toBeDefined();expect(group.getObjectByName('B01:floor:1')).toBeUndefined();expect(bounds.min.x).toBeCloseTo(-3);expect(bounds.max.x).toBeCloseTo(9);expect(bounds.min.y).toBeCloseTo(-4);expect(bounds.max.y).toBeLessThanOrEqual(0);});
 it('계단/구역의 ID와 층 위치를 보존하고 경고를 별도 연출로 표시한다',()=>{const feature:Feature={id:'STAIR-1',name:'가상 계단',kind:'STAIR',building_id:'B01',floor:-1,x:3,z:5,state:{},width:2,depth:4};const stairs=proceduralInterior(feature,b,{closed:true})!;expect(stairs.position.toArray()).toEqual([3,-4,5]);expect(stairs.children).toHaveLength(12);expect(stairs.children.every(item=>item.userData.featureId===feature.id)).toBe(true);expect(stairs.children[0].userData.assetNode).toContain('통제/위험 연출');});
});
