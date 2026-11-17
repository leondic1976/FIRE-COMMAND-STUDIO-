import {describe,it,expect} from 'vitest';
import type {Building} from '../../packages/domain-schemas';
import {buildingFloors,buildingPresets,floorElevation,floorPlan,sceneObjectBudget,siteRadius} from '../../packages/domain-schemas/building-plan';
import {crc32,zipStored} from '../../packages/domain-schemas/zip-store';
const building:Building={id:'B01',name:'가상',use:'창고',floors:3,basement_floors:2,floor_height:4,width:20,depth:10,x:0,z:0,rotation:0,color:'#aaaaaa',entrances:['NORTH'],footprint:[],accuracy:'SIMULATED'};
describe('가상 건물의 층/윤곽과 자원 제한',()=>{
 it('지하 음수층·대지0 제외·지상층을 구분한다',()=>{expect(buildingFloors(building)).toEqual([-2,-1,1,2,3]);expect(floorElevation(-2,4)).toBe(-8);expect(floorElevation(1,4)).toBe(0);});
 it('층별 윤곽→기본 윤곽→치수 순서로 같은 계획을 선택한다',()=>{expect(floorPlan(building,1)).toEqual([[-10,-5],[10,-5],[10,5],[-10,5]]);const points=[[0,0],[4,0],[0,4]];expect(floorPlan({...building,floor_outlines:[{floor:2,footprint:points}]},2)).toBe(points);});
 it('10개 용도 제안을 제공하고 지하·내부 요소도 장면 예산에 포함한다',()=>{expect(Object.keys(buildingPresets)).toHaveLength(10);expect(sceneObjectBudget([building],[])).toBeGreaterThan(sceneObjectBudget([{...building,basement_floors:0}],[]));});
 it('치수보다 큰 층 윤곽과 현재 통제 반경도 지도/카메라 범위에 포함한다',()=>{expect(siteRadius({buildings:[{...building,footprint:[[0,0],[200,0],[200,100],[0,100]]}],features:[]})).toBeGreaterThanOrEqual(Math.hypot(200,100));expect(siteRadius({buildings:[],features:[{id:'P',name:'가상 통제선',kind:'PERIMETER',building_id:null,floor:0,x:300,z:0,state:{radius:15}}]},{P:{radius:100}})).toBe(400);});
 it('출입구가 많아도 작은 기본 치수로 장면 제한을 우회하지 못한다',()=>expect(sceneObjectBudget([{...building,entrances:Array(16000).fill('NORTH')}],[])).toBeGreaterThan(15000));
 it('실제 자유 윤곽의 긴 둘레/층수로 생성되는 창호도 제한한다',()=>{const footprint=[[-150,-150],[150,-150],[150,150],...Array.from({length:48},(_,i)=>[i%2===0?-100:150,144-i*6])];expect(sceneObjectBudget([{...building,width:3,depth:3,floors:80,footprint}],[])).toBeGreaterThan(15000);});
 it('초기값보다 큰 현재 사건의 연기 효과도 제한한다',()=>{const features=Array.from({length:1000},(_,i)=>({id:'ZONE-'+i,name:'가상',kind:'ZONE' as const,building_id:'B01',floor:1,x:0,z:0,state:{smoke:0}})),state=Object.fromEntries(features.map(f=>[f.id,{smoke:4}]));expect(sceneObjectBudget([building],features,state)).toBeGreaterThan(15000);});
});
describe('제한된 장면 ZIP 묶음',()=>{
 it('표준 CRC32 검증 벡터와 ZIP 위치/중앙 디렉터리를 보존한다',()=>{const data=new TextEncoder().encode('123456789');expect(crc32(data)).toBe(0xcbf43926);const zip=zipStored([{name:'scene.json',bytes:data}]),view=new DataView(zip.buffer);expect(view.getUint32(0,true)).toBe(0x04034b50);expect(view.getUint32(14,true)).toBe(0xcbf43926);const end=zip.length-22,central=view.getUint32(end+16,true);expect(view.getUint32(central,true)).toBe(0x02014b50);expect(view.getUint32(central+42,true)).toBe(0);expect(view.getUint16(end+10,true)).toBe(1);});
 it('경로·중복·금지 형식은 출력 전에 거부한다',()=>{for(const name of ['../secret.json','scene.exe','a/scene.json'])expect(()=>zipStored([{name,bytes:new Uint8Array()}])).toThrow();expect(()=>zipStored([{name:'scene.json',bytes:new Uint8Array()},{name:'scene.json',bytes:new Uint8Array()}])).toThrow();});
});
