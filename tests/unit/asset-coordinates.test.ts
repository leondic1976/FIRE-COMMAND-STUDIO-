import {describe,expect,it} from 'vitest';
import {AssetBinding,Building,Subject,assetDisplayBuilding} from '../../packages/domain-schemas';
const building={id:'B01',x:10,z:20,rotation:90,width:32,depth:22,footprint:[[0,0],[2,0],[0,2]]} as Building;
const model={building_id:'B01',purpose:'MODEL',unit_scale:2,offset:[5,0,2],rotation_y:25,manifest:{bounds:[[-2,0,-3],[2,9,3]]}} as AssetBinding;
describe('검토 모델과 지도 좌표 일치',()=>{
 it('모델 크기·추가 회전·건물 회전을 포함한 위치 보정을 함께 적용한다',()=>{const subject={north_rotation:0,asset_bindings:[model]} as Subject;const result=assetDisplayBuilding(subject,building);expect(result.x).toBeCloseTo(12);expect(result.z).toBeCloseTo(15);expect(result.width).toBe(8);expect(result.depth).toBe(12);expect(result.rotation).toBe(115);expect(result.footprint).toEqual([]);});
 it('북향 보정을 모델의 로컬 위치 보정에도 적용한다',()=>{const result=assetDisplayBuilding({north_rotation:90,asset_bindings:[model]} as Subject,building);expect(result.x).toBeCloseTo(5);expect(result.z).toBeCloseTo(18);});
 it('관객에게 공개된 모델이 없으면 원래 도식을 유지한다',()=>{expect(assetDisplayBuilding({north_rotation:0,asset_bindings:[]} as unknown as Subject,building)).toBe(building);});
});
