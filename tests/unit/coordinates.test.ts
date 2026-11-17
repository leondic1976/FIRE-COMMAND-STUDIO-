import {describe,expect,it} from 'vitest';
import {localToWGS84,rotateLocal} from '../../packages/scene3d/coordinates';
describe('3D·지도 좌표 일치',()=>{
 it('양의 Y 회전을 지도에서도 같은 방향으로 적용한다',()=>{const [x,z]=rotateLocal(10,0,90);expect(x).toBeCloseTo(0);expect(z).toBeCloseTo(-10);});
 it('로컬 원점과 동·북 방향을 WGS84에 근사 투영한다',()=>{expect(localToWGS84(37.5,127,0,0)).toEqual([37.5,127]);const east=localToWGS84(37.5,127,10,0),north=localToWGS84(37.5,127,0,-10);expect(east[1]).toBeGreaterThan(127);expect(north[0]).toBeGreaterThan(37.5);});
 it('SDK 지원 범위를 벗어난 좌표를 거절한다',()=>{expect(()=>localToWGS84(90,127,0,0)).toThrow();expect(()=>localToWGS84(Number.NaN,127,0,0)).toThrow();});
});
